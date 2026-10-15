"""Real Tk event-loop acceptance, run under a display or xvfb-run in CI."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from polynomial_cusps.rendering import Viewport


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk acceptance needs a display")
class GuiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from polynomial_cusps.gui import Explorer
        self.root = tk.Tk()
        self.app = Explorer(self.root, autostart=False)
        self.app.resolution.set("48")
        self.app.iterations.set("32")
        self.root.update()

    def tearDown(self):
        self.app.close()

    def wait_for(self, condition):
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.005)
        self.fail(f"GUI timeout: {self.app.status.get()}")

    def render(self):
        previous = self.app.frame
        self.app.request_render()
        self.wait_for(lambda: self.app.frame is not None and self.app.frame is not previous)

    def test_boundary_real_complex_and_local_presets(self):
        self.render()
        self.assertEqual(self.app.frame.viewport.kind, "global")
        self.app.viewport = Viewport("global", "0.4", "0.1", "1.2")
        self.app.real.set("0.1")
        self.render()
        self.assertEqual(self.app.frame.viewport.span, "1.2")
        self.app.real.set("0.08")
        self.app.imag.set("0.06")
        self.render()
        for name, kind in (("Críticos en 0", "zero"), ("Críticos en 1", "one"),
                           ("Valores críticos", "values"), ("Ciclo Z / W", "cycle")):
            previous = self.app.frame
            self.app.view_name.set(name)
            self.app.change_view()
            self.wait_for(lambda: self.app.frame is not previous)
            self.assertEqual(self.app.frame.viewport.kind, kind)
            self.assertEqual(self.app.frame.engine, "rescaled")
        previous = self.app.frame
        self.app.boundary()
        self.wait_for(lambda: self.app.frame is not previous)
        self.assertEqual(self.app.frame.viewport.kind, "global")

    def test_point_step_zoom_toggles_and_export(self):
        self.render()
        self.app.canvas.event_generate("<ButtonPress-1>", x=120, y=180)
        self.app.canvas.event_generate("<ButtonRelease-1>", x=120, y=180)
        self.root.update()
        self.assertIsNotNone(self.app.selected)
        self.assertEqual(self.app.selected[1], 0)
        self.app.select_free()
        omega = self.app.scene.point.omega
        self.app.step()
        self.assertEqual(self.app.selected, (self.app.scene.point.f(omega), 1))
        self.app.flags["free"].set(False)
        self.app.redraw()
        previous = self.app.frame
        self.app.zoom("0.5")
        self.wait_for(lambda: self.app.frame is not previous)
        self.assertEqual(self.app.scene.point.ctx.mpf(self.app.frame.viewport.span),
                         self.app.scene.point.ctx.mpf("0.9"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"gui.png"
            with patch("polynomial_cusps.gui.filedialog.asksaveasfilename", return_value=str(path)):
                self.app.export()
            self.assertTrue(path.exists())
            self.assertTrue(path.with_suffix(".json").exists())

    def test_error_keeps_previous_frame_and_cancel_is_responsive(self):
        self.render()
        old = self.app.frame
        self.app.real.set("nan")
        self.app.request_render()
        self.wait_for(lambda: self.app.status.get().startswith("No se pudo"))
        self.assertIs(self.app.frame, old)
        self.app.real.set("0")
        self.app.engine.set("mp")
        self.app.iterations.set("4096")
        self.app.request_render()
        self.app.cancel()
        self.root.update()
        self.assertIs(self.app.frame, old)
        self.assertIn("cancelado", self.app.status.get())


if __name__ == "__main__":
    unittest.main()
