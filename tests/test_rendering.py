"""Rendering, fallback, export, and generation ownership checks."""

from pathlib import Path
from threading import Event
import json
import tempfile
import time
import unittest

import numpy as np
from PIL import Image

from polynomial_cusps.drawing import OverlayOptions, compose, save_export
from polynomial_cusps.jobs import BackgroundJobs
from polynomial_cusps.rendering import (
    RenderCancelled, RenderSettings, Viewport, colorize, prepare_scene, render,
)


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boundary = prepare_scene(orbit=12)
        cls.real = prepare_scene("0.1", orbit=12)
        cls.nonreal = prepare_scene("0.08", "0.06", orbit=12)

    def test_native_global_escape_matches_direct_high_precision(self):
        for scene in (self.boundary, self.real, self.nonreal):
            fast = render(scene, settings=RenderSettings(12, 24, "double"))
            slow = render(scene, settings=RenderSettings(12, 24, "mp"))
            np.testing.assert_array_equal(fast.escaped_at, slow.escaped_at)
            self.assertGreater(fast.escaped_count, 0)
            self.assertLess(fast.escaped_count, 144)

    def test_all_local_chart_transitions_match_direct_polynomial(self):
        for kind in ("zero", "one", "values", "cycle"):
            view = Viewport.preset(kind)
            fast = render(self.nonreal, view, RenderSettings(4, 12))
            slow = render(self.nonreal, view, RenderSettings(4, 12, "mp"))
            self.assertEqual(fast.engine, "rescaled")
            np.testing.assert_array_equal(fast.escaped_at, slow.escaped_at)
            np.testing.assert_allclose(fast.magnitude, slow.magnitude, atol=1e-12)

    def test_large_local_positions_restart_from_original_pixels(self):
        view = Viewport("cycle", "10000000", "0", "4")
        fast = render(self.real, view, RenderSettings(4, 10))
        slow = render(self.real, view, RenderSettings(4, 10, "mp"))
        self.assertEqual(fast.fallback_pixels, 16)
        np.testing.assert_array_equal(fast.escaped_at, slow.escaped_at)
        np.testing.assert_allclose(fast.magnitude, slow.magnitude, atol=1e-12)

    def test_deep_zoom_requires_mp_and_preserves_viewport(self):
        view = Viewport("global", "0.3", "0", "1e-20")
        result = render(self.boundary, view, RenderSettings(4, 5))
        self.assertEqual(result.engine, "mp")
        self.assertEqual(result.viewport, view)
        with self.assertRaises(ValueError):
            render(self.boundary, view, RenderSettings(4, 5, "double"))

    def test_underflow_switches_to_mp_and_auto_preview_is_recorded(self):
        scene = prepare_scene("1e-30", orbit=0)
        result = render(scene, Viewport.preset("cycle"), RenderSettings(8, 3), mp_preview_size=4)
        self.assertEqual(result.engine, "mp")
        self.assertEqual(result.settings.size, 4)
        self.assertEqual(result.escaped_at.shape, (4, 4))

    def test_cancellation_never_returns_partial_result(self):
        event = Event()
        event.set()
        with self.assertRaises(RenderCancelled):
            render(self.boundary, cancel=event)
        with self.assertRaises(RenderCancelled):
            prepare_scene(cancel=event)
        event.clear()
        with self.assertRaises(RenderCancelled):
            render(self.boundary, settings=RenderSettings(16, 64), cancel=event,
                   progress=lambda fraction: event.set())

    def test_invalid_views_and_reference_precision_fail_explicitly(self):
        for view in (Viewport(span="0"), Viewport(real="nan"), Viewport(kind="other"),
                     Viewport(span="1e-500"), Viewport.preset("cycle")):
            with self.assertRaises(ValueError):
                render(self.boundary, view, RenderSettings(4, 3))
        with self.assertRaises(ValueError):
            RenderSettings(0, 20).validate()

    def test_viewport_zoom_preserves_cursor_position(self):
        c = self.real.point.ctx
        view = Viewport()
        new = view.zoom(c, "0.25", "0.3", "0.8")
        self.assertLess(abs(new.coordinate(c, "0.3", "0.8")-view.coordinate(c, "0.3", "0.8")), c.mpf("1e-70"))
        self.assertEqual(c.mpf(new.span), c.mpf(view.span)/4)

    def test_boundary_preserves_all_six_critical_labels(self):
        nodes = self.boundary.nodes()
        self.assertEqual(len([name for name in nodes if name.startswith("c")]), 6)
        self.assertEqual(nodes["c2"], nodes["c3"])
        self.assertEqual(nodes["c4"], nodes["c5"])
        self.assertEqual(nodes["c4"], nodes["c6"])

    def test_palette_and_export_include_completed_numerical_snapshot(self):
        scene = self.nonreal
        result = render(scene, settings=RenderSettings(32, 32))
        for mode in ("Escape", "Julia"):
            rgb = colorize(result, mode)
            self.assertEqual(rgb.dtype, np.uint8)
            self.assertEqual(rgb.shape, (32, 32, 3))
            self.assertEqual(compose(scene, result, mode=mode).size, (32, 32))
        with tempfile.TemporaryDirectory() as folder:
            path = save_export(Path(folder)/"frame.png", scene, result,
                               OverlayOptions(), "Julia", (scene.point.omega, 0))
            data = json.loads(path.with_suffix(".json").read_text())
            with Image.open(path) as image:
                self.assertEqual(json.loads(image.info["polynomial-cusps"]), data)
                self.assertEqual(image.size, (32, 32))
            self.assertEqual(data["t"], {"real": "0.08", "imag": "0.06"})
            self.assertEqual(data["render"]["iterations"], 32)
            self.assertIn("unresolved", data["interpretation"])
            self.assertIn("normalized_residuals", data["rescaling"])

    def test_latest_generation_owns_results_and_progress(self):
        jobs = BackgroundJobs()
        started, release = Event(), Event()
        try:
            def old(cancel, progress):
                started.set()
                release.wait(2)
                progress(0.9)
                return "obsolete"
            jobs.submit(old)
            self.assertTrue(started.wait(2))
            jobs.submit(lambda cancel, progress: "current")
            release.set()
            messages = []
            deadline = time.monotonic()+3
            while time.monotonic() < deadline:
                messages.extend(jobs.poll())
                if any(kind == "result" for kind, value in messages):
                    break
                time.sleep(0.005)
            self.assertEqual(messages, [("result", "current")])
            jobs.cancel()
            self.assertEqual(jobs.poll(), [])
        finally:
            release.set()
            jobs.close()


if __name__ == "__main__":
    unittest.main()
