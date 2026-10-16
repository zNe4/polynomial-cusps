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
        self.app = self.root = None
        # Collect Tcl-owned cycles on the Tk thread before the next test starts
        # a numerical worker which might otherwise trigger Python's collector.
        import gc
        gc.collect()

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

    def test_parameter_selection_and_independent_dynamic_loop_marker(self):
        from polynomial_cusps.parameter_gui import ParameterWindow
        self.render()
        self.app.parameter_window = ParameterWindow(self.app, autostart=False)
        parameters = self.app.parameter_window
        previous = self.app.frame
        parameters.canvas.event_generate("<ButtonPress-1>", x=parameters.size*3//4, y=parameters.size//2)
        parameters.canvas.event_generate("<ButtonRelease-1>", x=parameters.size*3//4, y=parameters.size//2)
        self.wait_for(lambda: self.app.frame is not previous)
        self.assertGreater(abs(self.app.scene.point.t), 0)
        self.app.open_loops()
        loops = self.app.loop_window
        old_parameter = self.app.scene.point.t
        old_frame = self.app.frame
        loops.set_index(31)
        self.assertEqual(self.app.scene.point.t, old_parameter)
        self.assertIs(self.app.frame, old_frame)  # moving p does not rerender/change f
        self.assertEqual(self.app.loop_overlay()[1], 31)
        self.assertEqual(float(loops.data.winding_zero.real), 3)
        self.assertEqual(float(loops.data.winding_one.real), 4)
        self.assertEqual(loops.canvas.winfo_reqwidth(), 3*loops.size)
        self.assertEqual(len(loops.data.zero_second_image), len(loops.data.zero_source))
        self.assertEqual(float(loops.data.second_winding_one.real), 4)
        with tempfile.TemporaryDirectory() as folder:
            import json
            path = Path(folder)/"loops.png"
            with patch("polynomial_cusps.gui.filedialog.asksaveasfilename", return_value=str(path)):
                self.app.export()
            data = json.loads(path.with_suffix(".json").read_text())
            self.assertEqual(data["dynamic_loops"]["marker_index"], 31)
            self.assertIn("zero_second_image", data["dynamic_loops"]["data"])
            self.assertIn("second_scales", data["dynamic_loops"]["data"])
        previous = self.app.frame
        self.app.boundary()
        self.wait_for(lambda: self.app.frame is not previous)
        self.assertFalse(loops.data.t)
        self.assertEqual(loops.index, 31)

    def test_parameter_circle_playback_waits_for_dynamic_frame(self):
        from polynomial_cusps.parameter_gui import ParameterWindow
        self.render()
        self.app.parameter_window = ParameterWindow(self.app, autostart=False)
        window = self.app.parameter_window
        window.frames.set("64")
        window.build_circle()
        self.wait_for(lambda: window.circle is not None)
        self.wait_for(lambda: self.app.scene.point.t == window.circle.points[0].t)
        window.toggle_play()
        self.wait_for(lambda: window.index >= 1)
        window.pause()
        previous_index = window.index
        self.wait_for(lambda: self.app.scene.point.t == window.circle.points[previous_index].t)
        self.assertFalse(window.playing)
        window.select_index(len(window.circle.points)-1)
        self.wait_for(lambda: self.app.scene.point.t == window.circle.points[-1].t)
        self.assertAlmostEqual(float(window.circle.windings["x"].real), 4)
        self.assertAlmostEqual(float(window.circle.windings["s"].real), 3)

    def test_fast_wide_plane_and_selection_priority(self):
        from polynomial_cusps.parameter_gui import ParameterWindow
        self.render()
        self.app.parameter_window = ParameterWindow(self.app, autostart=False)
        window = self.app.parameter_window
        window.render_grid()
        self.wait_for(lambda: window.grid is not None)
        self.assertTrue(window.grid.approximate)
        self.assertEqual(window.grid.states.shape, (129, 129))
        window.quality.set("Verificado: Newton")
        window.configure_sampling()
        window.render_grid()
        old = self.app.frame
        self.app.apply_parameter(self.app.scene.point.ctx.mpc("0.4", "0.1"))
        self.assertIsNone(window._task)  # CPU-heavy grid stops for the requested dynamics
        self.wait_for(lambda: self.app.frame is not old)
        self.assertGreater(abs(self.app.scene.point.t), self.app.scene.point.ctx.mpf("0.2"))
        self.assertTrue(self.app.scene.point.diagnostics()["numerical_ok"])

    def test_loop_refinement_preserves_marker_angle_and_turns(self):
        self.render()
        self.app.open_loops()
        loops = self.app.loop_window
        count = len(loops.data.zero_source)-1
        loops.set_index(count+count//4)
        old = self.app.frame
        self.app.apply_parameter(self.app.scene.point.ctx.mpc("0.35", "0.35"))
        self.wait_for(lambda: self.app.frame is not old)
        new_count = len(loops.data.zero_source)-1
        self.assertGreater(new_count, count)
        self.assertAlmostEqual(loops.raw_index/new_count, 1.25)
        self.assertAlmostEqual(float(loops.slider.get()), 90)
        self.assertEqual(self.app.loop_overlay()[1], new_count//4)

    def test_ctrl_q_closes_only_loops_then_quits_from_dynamic_window(self):
        import tkinter as tk
        self.render()
        self.app.open_parameters()
        self.app.open_loops()
        loops = self.app.loop_window
        loops.toggle_play()
        loops.slider.focus_force()
        self.root.update()
        loops.slider.event_generate("<Control-q>")
        self.root.update()
        self.assertIsNone(self.app.loop_window)
        self.assertFalse(loops.playing)
        self.assertFalse(loops.window.winfo_exists())
        self.assertTrue(self.root.winfo_exists())
        self.assertTrue(self.app.parameter_window.window.winfo_exists())
        self.app.open_loops()  # Can reopen after the shortcut.
        self.app.info.focus_force()
        self.root.update()
        self.app.info.event_generate("<Control-Q>")
        self.assertTrue(self.app._closed)
        self.assertIsNone(self.app.loop_window)
        self.assertIsNone(self.app.parameter_window)
        with self.assertRaises(tk.TclError):
            self.root.winfo_exists()

    def test_ctrl_q_from_parameter_control_quits_during_calculation(self):
        import tkinter as tk
        from polynomial_cusps.parameter_gui import ParameterWindow
        self.app.parameter_window = ParameterWindow(self.app, autostart=False)
        parameters = self.app.parameter_window
        parameters.slider.focus_force()
        self.root.update()
        parameters.quality.set("Verificado: Newton")
        parameters.configure_sampling()
        parameters.render_grid()
        self.app.request_render()
        parameters.slider.event_generate("<Control-q>")
        self.assertTrue(self.app._closed)
        self.assertTrue(parameters._closed)
        self.assertIsNone(self.app.parameter_window)
        with self.assertRaises(tk.TclError):
            self.root.winfo_exists()


if __name__ == "__main__":
    unittest.main()
