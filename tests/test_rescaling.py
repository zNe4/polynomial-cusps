"""Compare local kernels with independent direct high-precision evaluations."""

import json
import subprocess
import sys
import unittest

from polynomial_cusps import RescaledFamily, solve_family
from polynomial_cusps.family import _point


class RescalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = RescaledFamily(solve_family("0.1", dps=80, steps=3))
        cls.nonreal = RescaledFamily(solve_family(("0.08", "0.06"), dps=80, steps=3))
        # Direct return subtraction needs twice the spatial precision budget.
        cls.tiny = RescaledFamily(solve_family("1e-8", dps=190, steps=3))
        cls.boundary = RescaledFamily(solve_family("0", dps=70))

    def assert_close(self, a, b, ctx, digits=60):
        self.assertLess(abs(a-b), ctx.power(10, -digits))

    def test_scales_match_independent_subtraction(self):
        for r in (self.real, self.nonreal, self.tiny):
            p = r.point
            named = p.portrait_points
            d, delta = r.value_scale.value, r.cycle_scale.value
            self.assert_close((named["Y"]-named["X"])/d, 1, p.ctx)
            self.assert_close((named["W"]-named["Z"])/delta, 1, p.ctx)
            self.assert_close(r.cycle_scale.unit/r.value_scale.unit,
                              p.difference(named["X"], named["Y"])/d, p.ctx)

    def test_all_four_maps_against_direct_polynomial(self):
        for r in (self.real, self.nonreal, self.tiny):
            p, k = r.point, r.kernels
            c = p.ctx
            xi = c.mpc("0.31", "0.17")
            X, Z = r.charts["values"].center, r.charts["cycle"].center
            d, delta = r.value_scale.value, r.cycle_scale.value
            cases = (
                (k.zero_to_values, (p.f(p.x*xi)-X)/d),
                (k.one_to_values, (p.f(1+p.s*xi)-X)/d),
                (k.values_to_cycle, (p.f(X+d*xi)-Z)/delta),
                (k.cycle, (p.f(Z+delta*xi)-Z)/delta),
            )
            for kernel, expected in cases:
                self.assert_close(kernel(xi), expected, c)

    def test_chart_points_do_not_materialize_automatically(self):
        r = self.tiny
        chart = r.charts["cycle"]
        start, end = chart.at(0), chart.at(1)
        self.assertNotEqual(start.xi, end.xi)
        self.assertIs(start.chart, chart)
        # Materializing in binary64 loses the separation; the structured points keep it.
        self.assertEqual(complex(start.absolute()), complex(end.absolute()))
        self.assert_close(chart.relative(end.absolute()), 1, r.point.ctx)

    def test_critical_labels_in_local_coordinates(self):
        r = self.nonreal
        p, k = r.point, r.kernels
        c = p.ctx
        self.assert_close(k.zero_to_values(c.mpc(1)), 0, c)
        self.assert_close(k.zero_to_values(c.mpc(-1)), 1, c)
        self.assert_close(k.one_to_values(c.mpc(1)), 0, c)
        self.assert_close(k.one_to_values(c.mpc(-1)), 0, c)
        self.assert_close(k.one_to_values(p.h0/p.s), 1, c)
        self.assert_close(k.values_to_cycle(c.mpc(0)), 0, c)
        self.assert_close(k.values_to_cycle(c.mpc(1)), 1, c)

    def test_portrait_endpoints_and_measured_residuals(self):
        r = self.nonreal
        c, k = r.point.ctx, r.kernels.cycle
        self.assertEqual(k.portrait_map(c.mpc(0)), 1)
        self.assertEqual(k.portrait_map(c.mpc(1)), 0)
        self.assert_close(k(c.mpc(0))-1, k.residual_start, c, digits=110)
        self.assertEqual(k(c.mpc(1)), k.residual_end)

    def test_residuals_are_not_silently_projected_away(self):
        base = self.real.point
        c = base.ctx
        perturbed = _point(c, base.t, base.u, base.omega, base.lam,
                           base.B+c.mpf("1e-16"), base.requested_dps)
        r = RescaledFamily(perturbed)
        k = r.kernels.cycle
        Z, delta = r.charts["cycle"].center, r.cycle_scale.value
        xi = c.mpc("0.31", "0.17")
        raw = (perturbed.f(Z+delta*xi)-Z)/delta
        self.assert_close(k(xi), raw, c)
        self.assertGreater(abs(k(xi)-k.portrait_map(xi)), c.mpf("1e-8"))
        self.assertLessEqual(abs(k(xi)-k.portrait_map(xi)), k.residual_bound(2))
        # The nonzero one-cluster anchor is carried too.
        X, d = r.charts["values"].center, r.value_scale.value
        self.assert_close(r.kernels.one_to_values(xi),
                          (perturbed.f(1+perturbed.s*xi)-X)/d, c)
        with self.assertRaises(ValueError):
            k.residual_bound(-1)

    def test_scaled_multiplier_against_direct_high_precision(self):
        for r in (self.real, self.nonreal, self.tiny):
            p, k = r.point, r.kernels.cycle
            Z, delta = r.charts["cycle"].center, r.cycle_scale.value
            raw = p.derivative(Z)*p.derivative(Z+delta)-1
            projected = delta**2*k.portrait_multiplier_defect_scaled()
            self.assert_close((raw-projected-k.endpoint_product_correction())/delta**2,
                              0, p.ctx, digits=55)

    def test_scaled_drift_against_direct_high_precision_return(self):
        for r in (self.real, self.nonreal, self.tiny):
            c, k = r.point.ctx, r.kernels.cycle
            xi = c.mpc("0.31", "0.17")
            direct = (k.portrait_map(k.portrait_map(xi))-xi)/k.delta**2
            self.assert_close(k.portrait_return_drift_scaled(xi), direct, c, digits=55)

    def test_boundary_limits_are_not_presented_as_genuine_charts(self):
        r = self.boundary
        c, k = r.point.ctx, r.kernels.cycle
        xi = c.mpc("0.31", "0.17")
        for chart in r.charts.values():
            self.assertFalse(chart.available)
            with self.assertRaises(ValueError):
                chart.at(1)
            with self.assertRaises(ValueError):
                chart.relative(1)
        with self.assertRaises(ValueError):
            k(xi)
        with self.assertRaises(ValueError):
            r.binary64()
        self.assertEqual(k.portrait_map(xi), 1-xi)
        M = k.portrait_multiplier_defect_scaled()
        self.assert_close(M, c.mpf("-18.85284749797972881094287"), c, digits=21)
        self.assert_close(k.portrait_return_drift_scaled(xi), M*xi*(xi-1)*(2*xi-1), c)
        # Cubic and quartic critical-value maps have meaningful formal limits.
        self.assert_close(r.kernels.zero_to_values(-1), 1, c)
        self.assert_close(r.kernels.one_to_values(0), 1, c)
        self.assertFalse(r.report()["charts_available"])

    def test_native_complex_kernels_match_reference(self):
        for r in (self.real, self.nonreal, self.tiny):
            native, reference = r.binary64(), r.kernels
            xi = complex(0.31, 0.17)
            pairs = ((native.zero_to_values, reference.zero_to_values),
                     (native.one_to_values, reference.one_to_values),
                     (native.values_to_cycle, reference.values_to_cycle),
                     (native.cycle, reference.cycle),
                     (native.cycle.portrait_return_drift_scaled,
                      reference.cycle.portrait_return_drift_scaled))
            for fast, slow in pairs:
                value = fast(xi)
                self.assertIsInstance(value, complex)
                self.assertLess(abs(value-complex(slow(r.point.ctx.mpc(xi)))), 5e-13)
            self.assertLess(abs(native.cycle.portrait_multiplier_defect_scaled()-complex(
                reference.cycle.portrait_multiplier_defect_scaled())), 5e-13)

    def test_multiplier_keeps_information_when_delta_squared_underflows(self):
        r = RescaledFamily(solve_family("1e-16", dps=40, steps=2))
        k = r.binary64().cycle
        self.assertNotEqual(k.delta, 0)
        self.assertEqual(k.delta**2, 0)
        self.assertGreater(abs(k.portrait_multiplier_defect_scaled()), 1)
        report = r.report()["portrait_multiplier_defect"]
        self.assertEqual(report["order"], 24)
        self.assertLess(report["log10_abs"], -370)
        self.assertNotEqual(report["value"], 0)

    def test_scale_underflow_is_explicit(self):
        r = RescaledFamily(solve_family("1e-30", dps=40, steps=2))
        self.assertNotEqual(r.cycle_scale.value, 0)
        with self.assertRaises(OverflowError):
            r.binary64()

    def test_phase_and_logarithms_match_reference(self):
        r, c = self.nonreal, self.nonreal.point.ctx
        for scale in (r.value_scale, r.cycle_scale):
            self.assert_close(scale.log10_abs, c.log10(abs(scale.value)), c)
            self.assert_close(scale.phase, c.arg(scale.value), c)

    def test_cli_rescaled_report_and_boundary_nulls(self):
        for t in ("0", "1e-8"):
            result = subprocess.run([sys.executable, "-m", "polynomial_cusps",
                                     "--real", t, "--dps", "40", "--steps", "2",
                                     "--orbit", "0", "--rescaled"],
                                    capture_output=True, text=True, check=True)
            report = json.loads(result.stdout)["rescaled"]
            self.assertEqual(report["charts_available"], t != "0")
            self.assertEqual(report["scales"]["cycle"]["order"], 12)
            if t == "0":
                self.assertIsNone(report["normalized_residuals"]["cycle_start"])
                self.assertIsNone(report["scales"]["cycle"]["phase"])
            else:
                self.assertIsNotNone(report["raw_endpoint_product_correction"])


if __name__ == "__main__":
    unittest.main()
