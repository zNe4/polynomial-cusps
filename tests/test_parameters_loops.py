"""Parameter motion and forward dynamical loops are tested independently."""

from dataclasses import replace
from threading import Event
import unittest

import numpy as np

from polynomial_cusps import solve_family
from polynomial_cusps.loops import forward_loops
from polynomial_cusps.parameters import (
    ATTRACTING, BOUNDARY, FAILED, OUTSIDE, REPELLING, FamilyCache,
    cycle_state, parameter_circle, parameter_grid,
)
from polynomial_cusps.rendering import (
    RenderCancelled, RenderSettings, Viewport, prepare_scene, render,
)
from polynomial_cusps.rescaling import RescaledFamily


class ParameterAndLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boundary = prepare_scene(orbit=0)
        cls.nonreal = prepare_scene("0.08", "0.06", orbit=0)
        cls.circle = parameter_circle("0.08", frames=64, dps=40)

    def test_continuation_seed_matches_independent_radial_solution(self):
        seed = solve_family("0.08", dps=40)
        continued = solve_family(("0.08", "0.06"), dps=50, steps=1, seed=seed)
        radial = self.nonreal.point
        for name in ("u", "omega", "lam", "B"):
            self.assertLess(abs(getattr(continued, name)-getattr(radial, name)), continued.ctx.mpf("1e-45"))
        self.assertTrue(continued.diagnostics()["numerical_ok"])

    def test_parameter_circle_closes_and_measures_cusp_exponents(self):
        circle = self.circle
        first, last = circle.points[0], circle.points[-1]
        self.assertIsNot(first, last)  # closing arc was solved, not copied from cache
        self.assertEqual(first.t, last.t)
        for name in ("x", "s", "omega", "lam", "B"):
            self.assertLess(abs(getattr(first, name)-getattr(last, name)), first.ctx.mpf("1e-35"))
        for name, expected in (("x", 4), ("s", 3), ("Y-X", 12), ("W-Z", 12)):
            self.assertLess(abs(circle.windings[name]-expected), first.ctx.mpf("1e-30"))
        self.assertTrue(all(p.diagnostics()["numerical_ok"] for p in circle.points))

    def test_cycle_color_matches_independent_high_precision_multiplier(self):
        # The two angular sectors have opposite stability for the prescribed cycle.
        for point in (self.circle.points[0], self.circle.points[3]):
            p = solve_family((point.t.real, point.t.imag), dps=100, steps=1, seed=point)
            Z, W = (p.portrait_points[k] for k in ("Z", "W"))
            mu = p.derivative(Z)*p.derivative(W)
            expected = ATTRACTING if abs(mu) < 1 else REPELLING
            self.assertEqual(cycle_state(RescaledFamily(p)), expected)
        self.assertEqual(cycle_state(self.boundary.reference), BOUNDARY)

    def test_parameter_cells_are_checked_and_failures_are_not_inside(self):
        cache = FamilyCache(capacity=100)
        result = parameter_grid(size=5, cache=cache)
        self.assertEqual(result.states.shape, (5, 5))
        self.assertNotIn(FAILED, set(result.states.flat))
        self.assertEqual(result.states[2, 2], BOUNDARY)
        self.assertEqual(len(result.points), 25)
        self.assertTrue(all(p.diagnostics()["numerical_ok"] for p in result.points.values()))
        point = cache.get("0.08", "0", 40)
        self.assertIs(point, cache.get("0.08", "0", 40))
        outside = parameter_grid(Viewport("global", "0.4", "0", "0.01"), size=3)
        self.assertTrue(np.all(outside.states == OUTSIDE))
        self.assertEqual(outside.points, {})

    def test_forward_source_points_are_regular_and_images_are_actual_f(self):
        for scene in (self.boundary, self.nonreal):
            p, c = scene.point, scene.point.ctx
            loops = forward_loops(scene, samples=96)
            self.assertLess(abs(loops.winding_zero-3), c.mpf("1e-40"))
            self.assertLess(abs(loops.winding_one-4), c.mpf("1e-40"))
            for group, sources, images in ((0, loops.zero_source, loops.zero_image),
                                           (1, loops.one_source, loops.one_image)):
                for index in (0, 13, 37, 79):
                    z = group+loops.source_scales[group]*sources[index]
                    image = loops.image_center+loops.image_scales[group]*images[index]
                    self.assertGreater(abs(p.derivative(z)), c.mpf("1e-20"))
                    self.assertLess(abs((p.f(z)-image)/loops.image_scales[group]), c.mpf("1e-50"))
            self.assertEqual(loops.zero_source[0], loops.zero_source[-1])
            self.assertEqual(loops.one_image[0], loops.one_image[-1])

    def test_small_parameter_loops_still_resolve_forward_images(self):
        scene = prepare_scene("1e-8", orbit=0)
        loops = forward_loops(scene, samples=96)
        self.assertLess(abs(loops.winding_zero-3), scene.point.ctx.mpf("1e-40"))
        self.assertLess(abs(loops.winding_one-4), scene.point.ctx.mpf("1e-40"))
        self.assertGreater(abs(loops.zero_image[0]-loops.zero_image[13]), 1)

    def test_second_images_match_direct_double_iteration_at_all_scales(self):
        for scene in (self.boundary, self.nonreal, prepare_scene("1e-8", orbit=0)):
            p, c = scene.point, scene.point.ctx
            loops = forward_loops(scene, samples=96)
            for group, sources, second in ((0, loops.zero_source, loops.zero_second_image),
                                            (1, loops.one_source, loops.one_second_image)):
                self.assertEqual(second[0], second[-1])
                for index in (0, 13, 37, 79):
                    z = group+loops.source_scales[group]*sources[index]
                    # Direct high-precision evaluation is independent of the
                    # divided composition used to construct the displayed path.
                    observed = (p.f(p.f(z))-loops.second_center)/loops.second_scales[group]
                    self.assertLess(abs(observed-second[index]), c.mpf("1e-50"))
                self.assertGreater(abs(second[0]-second[13]), c.mpf("0.1"))
            self.assertLess(abs(loops.second_winding_zero-3), c.mpf("1e-40"))
            self.assertLess(abs(loops.second_winding_one-4), c.mpf("1e-40"))

    def test_nonrotating_local_axes_show_the_critical_turn(self):
        scene = self.nonreal
        c, p = scene.point.ctx, scene.point
        native = scene.local(p.x, "zero")
        fixed = scene.local(p.x, "zero", True)
        self.assertLess(abs(native-1), c.mpf("1e-70"))
        self.assertGreater(abs(fixed-1), c.mpf("0.1"))
        self.assertLess(abs(abs(fixed)-1), c.mpf("1e-70"))
        view = replace(Viewport.preset("zero"), fixed_axes=True)
        self.assertTrue(view.zoom(c, "0.5").fixed_axes)
        fast = render(scene, view, RenderSettings(4, 12))
        slow = render(scene, view, RenderSettings(4, 12, "mp"))
        np.testing.assert_allclose(fast.magnitude, slow.magnitude, atol=1e-12)

    def test_invalid_and_cancelled_paths_are_explicit(self):
        event = Event()
        event.set()
        with self.assertRaises(RenderCancelled):
            parameter_grid(size=3, cancel=event)
        with self.assertRaises(RenderCancelled):
            parameter_circle(cancel=event)
        with self.assertRaises(RenderCancelled):
            forward_loops(self.nonreal, cancel=event)
        for radius in ("0", "0.21", "nan"):
            with self.assertRaises(ValueError):
                parameter_circle(radius)
        with self.assertRaises(ValueError):
            parameter_circle(frames=16)
        with self.assertRaises(ValueError):
            forward_loops(self.boundary, boundary_radius="0")


if __name__ == "__main__":
    unittest.main()
