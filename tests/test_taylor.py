"""Independent radial checks of the fast model and the wider operating disk."""

import unittest
from threading import Event

import numpy as np

from polynomial_cusps.family import solve_family
from polynomial_cusps.parameters import (
    BOUNDARY, OUTSIDE, UNRESOLVED, cycle_state, parameter_circle, parameter_preview,
)
from polynomial_cusps.rendering import RenderCancelled, Viewport
from polynomial_cusps.rescaling import RescaledFamily
from polynomial_cusps.taylor import predict, preview_values, solve_explorer_family


class TaylorTests(unittest.TestCase):
    def test_table_and_corrected_solutions_against_independent_radial_continuation(self):
        for t in (("0.08", "0.06"), ("0.3", "0.2"), ("0.5", "0"), ("0.35", "0.35")):
            p = solve_family(t, dps=50)
            ref, c = RescaledFamily(p), p.ctx
            expected = {name: getattr(p, name) for name in ("u", "omega", "lam", "B")}
            expected.update(D=ref.value_scale.unit, C=ref.cycle_scale.unit,
                            M=ref.kernels.cycle.portrait_multiplier_defect_scaled())
            approximation = predict(c, p.t)
            for name, value in expected.items():
                self.assertLess(abs(approximation[name]-value)/max(1, abs(value)), c.mpf("1e-10"))
            corrected = solve_explorer_family(t, dps=50)
            self.assertTrue(corrected.diagnostics()["numerical_ok"])
            for name in ("u", "omega", "lam", "B"):
                self.assertLess(abs(getattr(corrected, name)-getattr(p, name)), c.mpf("1e-45"))

    def test_preview_colors_match_checked_samples_across_wider_disk(self):
        grid = parameter_preview(size=17)
        self.assertTrue(grid.approximate)
        self.assertFalse(grid.points)  # no approximate point masquerades as a checked one
        self.assertEqual(grid.states[8, 8], BOUNDARY)
        self.assertEqual(grid.states[0, 0], OUTSIDE)
        c = solve_family().ctx
        for row, col in ((1, 6), (3, 4), (5, 12), (8, 14), (12, 11), (15, 9)):
            t = grid.view.coordinate(c, (c.mpf(col)+c.mpf("0.5"))/17,
                                     (c.mpf(row)+c.mpf("0.5"))/17)
            point = solve_family(t, dps=40)
            self.assertEqual(grid.states[row, col], cycle_state(RescaledFamily(point)))
        # Order-t^24 underflow must not erase the leading stability phase.
        tiny = parameter_preview(Viewport("global", "0", "0", "1e-40"), size=9)
        self.assertTrue(np.any((tiny.states != BOUNDARY) & (tiny.states != UNRESOLVED)))

    def test_preview_error_indicator_covers_observed_outer_sample_errors(self):
        t = complex(0.45, 0.2)
        p = solve_family((str(t.real), str(t.imag)), dps=50)
        r = RescaledFamily(p)
        values, errors = preview_values(np.array([t]))
        for name, actual in (("C", r.cycle_scale.unit), ("M", r.kernels.cycle.portrait_multiplier_defect_scaled())):
            self.assertLess(abs(values[name][0]-complex(actual)), errors[name][0])

    def test_outer_circle_closes_on_radial_branch(self):
        circle = parameter_circle("0.5", frames=64, dps=40)
        for i in (8, 16, 24, 32):
            p = circle.points[i]
            radial = solve_family(p.t, dps=40)
            self.assertLess(abs(p.lam-radial.lam), p.ctx.mpf("1e-35"))
        for name, expected in (("x", 4), ("s", 3), ("Y-X", 12), ("W-Z", 12)):
            self.assertAlmostEqual(float(circle.windings[name]), expected, places=12)

    def test_invalid_and_cancelled_previews(self):
        event = Event()
        event.set()
        with self.assertRaises(RenderCancelled):
            parameter_preview(cancel=event)
        with self.assertRaises(ValueError):
            parameter_preview(size=2048)
        with self.assertRaises(ValueError):
            parameter_preview(Viewport("global", "0.1", "0", "1e-30"))
        with self.assertRaises(ValueError):
            solve_explorer_family("0.6")


if __name__ == "__main__":
    unittest.main()
