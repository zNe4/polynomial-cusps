"""Independent dynamical and algebraic checks of the local numerical family."""

import json
import subprocess
import sys
import unittest

import mpmath

from polynomial_cusps import solve_family


class FamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boundary = solve_family(dps=50)
        cls.real = solve_family("0.1", dps=50)
        cls.complex = solve_family(("0.08", "0.06"), dps=50)

    def assert_small(self, value, point, digits=45):
        self.assertLess(abs(value), point.ctx.power(10, -digits))

    def test_boundary_matches_explicit_polynomial(self):
        p = self.boundary
        ctx = p.ctx
        for z in (ctx.mpc("0.3", "0.2"), ctx.mpf(0), ctx.mpf(1)):
            self.assert_small(p.f(z)-(p.lam*z**3*(z-1)**4+p.B), p)
        self.assertEqual(p.omega, ctx.mpf(3)/7)
        self.assertLess(abs(p.lam-ctx.mpf("-37.4259503275383905")), ctx.mpf("1e-15"))
        a = p.f(p.B)
        theta = 64*(2*a-1)**3*(8*a-3)**4-(7*a-3)**7
        for error in (theta, p.f(a)-a, p.derivative(a)+1):
            self.assert_small(error, p)
        self.assertTrue(p.diagnostics()["numerical_ok"])
        self.assertFalse(p.diagnostics()["portrait_resolved"])

    def test_critical_marking_and_independent_derivative(self):
        for p in (self.boundary, self.real, self.complex):
            for c in p.critical_points:
                derivative = sum(k*v*c**(k-1) for k, v in enumerate(p.coefficients) if k)
                self.assert_small(derivative, p)
            self.assertEqual(len(p.critical_points), 6)

    def test_original_undivided_portrait_relations(self):
        for p in (self.real, self.complex):
            c1, c2, c3, c4, c5, c6 = p.critical_points
            X, Y = p.f(c2), p.f(c3)
            Z, W = p.f(X), p.f(Y)
            for error in (p.f(c4)-X, p.f(c5)-X, p.f(c6)-Y,
                          p.f(Z)-W, p.f(W)-Z):
                self.assert_small(error, p)
            self.assertGreater(abs(X-Y), p.ctx.mpf("1e-12"))
            self.assertGreater(abs(Z-W), p.ctx.mpf("1e-12"))
            # The cycle has exact period two, not a substituted fixed point.
            self.assertGreater(abs(p.f(Z)-Z), p.ctx.mpf("1e-12"))
            self.assertTrue(p.diagnostics()["portrait_resolved"])

    def test_divided_period_two_equation_at_and_away_from_fixed_point(self):
        p = self.boundary
        a = p.f(p.B)
        self.assert_small(p.period_two_quotient(a)-(1+p.derivative(a)), p)
        z = p.ctx.mpc("0.17", "0.09")
        quotient = (p.f(p.f(z))-z)/(p.f(z)-z)
        self.assert_small(p.period_two_quotient(z)-quotient, p)

    def test_critical_value_separation_factors(self):
        p = self.boundary
        U, V = p.separation_factors()
        self.assert_small(U-4*p.lam, p)
        self.assert_small(V-p.lam, p)
        p = self.complex
        U, V = p.separation_factors()
        self.assert_small(p.f(-p.x)-p.f(p.x)-p.x**3*U, p)
        self.assert_small(p.f(1+p.h0)-p.f(1+p.s)-p.s**4*V, p)

    def test_integration_matches_independent_quadrature(self):
        p = self.complex
        lo, hi = p.ctx.mpc("0.2", "0.3"), p.ctx.mpc("0.7", "0.1")
        integral = p.ctx.quad(lambda v: p.derivative(lo+(hi-lo)*v)*(hi-lo), [0, 1])
        self.assert_small(p.difference(lo, hi)-integral, p)

    def test_collapsing_orders(self):
        p = solve_family("0.05", dps=50)
        q = self.real
        self.assert_small(q.s/p.s-8, p)
        self.assertLess(abs(q.x/p.x-16), p.ctx.mpf("0.001"))
        ratio = q.diagnostics()["gaps"]["critical_values"] / p.diagnostics()["gaps"]["critical_values"]
        self.assertLess(abs(ratio/4096-1), p.ctx.mpf("0.001"))

    def test_tiny_parameter_resolves_gap_below_requested_absolute_precision(self):
        p = solve_family("1e-8", dps=40, steps=2)
        d = p.diagnostics()
        self.assertTrue(d["portrait_resolved"])
        self.assertGreater(d["working_dps"], 160)
        self.assertLess(d["gaps"]["critical_values"], p.ctx.mpf("1e-90"))
        self.assertLess(max(d["residuals"].values()), d["gaps"]["cycle"]*p.ctx.mpf("1e-40"))

    def test_precision_stability_and_context_isolation(self):
        previous_dps = mpmath.mp.dps
        p = solve_family(("0.08", "0.06"), dps=80)
        self.assertEqual(mpmath.mp.dps, previous_dps)
        self.assertEqual(self.complex.ctx.dps, 92)
        for field in ("u", "omega", "lam", "B"):
            self.assert_small(getattr(p, field)-getattr(self.complex, field), p)

    def test_conjugate_parameter_preserves_branch(self):
        p = solve_family(("0.08", "-0.06"), dps=50)
        for field in ("u", "x", "s", "h0", "omega", "lam", "B"):
            self.assert_small(getattr(p, field)-getattr(self.complex, field).conjugate(), p)

    def test_orbit_length_recurrence_and_escape(self):
        p = self.boundary
        orbit = p.orbit(p.omega, 12)
        self.assertEqual(len(orbit), 13)
        self.assertEqual(orbit[0], p.omega)
        for z, image in zip(orbit, orbit[1:]):
            self.assertEqual(p.f(z), image)
        radius = p.escape_radius()
        self.assertGreater(abs(p.f(radius+1)), radius+1)
        self.assertEqual(len(p.orbit(radius+1, 100)), 1)
        with self.assertRaises(ValueError):
            p.orbit(p.omega, -1)

    def test_invalid_inputs(self):
        for kwargs in ({"dps": 20}, {"dps": True}, {"steps": 0}, {"steps": 1.5}):
            with self.assertRaises(ValueError):
                solve_family(**kwargs)
        for t in ("nan", "inf", "0.51", ("0.4", "0.4"), (0, 1, 2)):
            with self.assertRaises(ValueError):
                solve_family(t)

    def test_cli_json_retains_numeric_precision_and_plain_strings(self):
        command = [sys.executable, "-m", "polynomial_cusps", "--real", "0.1",
                   "--imag", "0.03", "--dps", "40", "--orbit", "3"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["normalization"], "affine: critical midpoints 0 and 1")
        self.assertTrue(data["diagnostics"]["portrait_resolved"])
        self.assertEqual(len(data["free_critical_orbit"]), 4)
        self.assertEqual(data["free_orbit_infinite"], "not decided by finite numerical iteration")
        ctx = self.complex.ctx
        def number(v):
            return ctx.mpc(v["real"], v["imag"]) if isinstance(v, dict) else ctx.mpc(v)
        self.assertNotEqual(number(data["portrait_points"]["Z"]), number(data["portrait_points"]["W"]))


if __name__ == "__main__":
    unittest.main()
