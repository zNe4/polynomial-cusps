"""Arbitrary-precision continuation in the desingularized local parameter.

Coefficients are stored in ascending order. Every point owns an mpmath
context; constructing a point never changes the global working precision.
"""

from dataclasses import dataclass, field
import mpmath


def _multiply(a, b):
    result = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            result[i + j] += ai * bj
    return result


def _integral_product(factors, lower, upper):
    """Exactly integrate a polynomial product after mapping [lower,upper] to [0,1]."""
    width = upper - lower
    result = [1]
    for factor in factors:
        # factor(lower + width*v), via polynomial Horner composition.
        composed = [factor[-1]]
        for coefficient in reversed(factor[:-1]):
            composed = _multiply(composed, [lower, width])
            composed[0] += coefficient
        result = _multiply(result, composed)
    return width * sum(coefficient / (i + 1) for i, coefficient in enumerate(result))


def _horner(coefficients, z):
    value = coefficients[-1]
    for coefficient in reversed(coefficients[:-1]):
        value = value * z + coefficient
    return value


def _h0_and_H(ctx, x, s, omega):
    H = ((3 - 2 * omega - x*x) / 5 + ctx.mpf(3) / 35 * s*s) / (
        (1 - x*x) * (1 - omega) + (3 - omega) / 5 * s*s
    )
    return s*s * H, H


@dataclass(frozen=True)
class FamilyPoint:
    """An affine-normalized polynomial, with all six critical labels retained."""

    ctx: object = field(repr=False, compare=False)
    t: object
    u: object
    x: object
    s: object
    h0: object
    omega: object
    lam: object
    B: object
    requested_dps: int
    coefficients: tuple = field(repr=False)

    @property
    def critical_points(self):
        return (self.omega, self.x, -self.x, 1+self.s, 1-self.s, 1+self.h0)

    def f(self, z):
        return _horner(self.coefficients, self.ctx.mpc(z))

    def derivative(self, z):
        return 7 * self.lam * (z*z-self.x*self.x) * (
            (z-1)**2-self.s*self.s
        ) * (z-1-self.h0) * (z-self.omega)

    def difference(self, lower, upper):
        """Compute f(upper)-f(lower) without subtracting nearby values."""
        return 7 * self.lam * _integral_product(
            [[-self.x*self.x, 0, 1], [1-self.s*self.s, -2, 1],
             [-1-self.h0, 1], [-self.omega, 1]], lower, upper
        )

    def period_two_quotient(self, z):
        """Polynomial Q_f(z), including its value at fixed points.

        Q_f(z) = 1 + [f(f(z))-f(z)]/[f(z)-z].  The divided difference
        is evaluated algebraically, so no tiny denominator is used.
        """
        y = self.f(z)
        divided = self.ctx.mpc(0)
        power_sum = self.ctx.mpc(1)
        for k in range(1, len(self.coefficients)):
            if k > 1:
                power_sum = y * power_sum + z ** (k-1)
            divided += self.coefficients[k] * power_sum
        return 1 + divided

    def separation_factors(self):
        """Holomorphic extensions U and V, valid also at t=0."""
        x, s, w = self.x, self.s, self.omega
        _, H = _h0_and_H(self.ctx, x, s, w)
        U = 7 * self.lam * _integral_product(
            [[-1, 0, 1], [1-s*s, -2*x, x*x],
             [-1-self.h0, x], [-w, x]], self.ctx.mpf(1), self.ctx.mpf(-1)
        )
        V = 7 * self.lam * _integral_product(
            [[1-x*x, 2*s, s*s], [-1, 0, 1], [-s*H, 1], [1-w, s]],
            self.ctx.mpf(1), s*H
        )
        return U, V

    @property
    def portrait_points(self):
        X = self.f(self.x)
        Y = self.f(1+self.h0)
        return {"X": X, "Y": Y, "Z": self.f(X), "W": self.f(Y)}

    def equations(self):
        p = self.portrait_points
        U, V = self.separation_factors()
        return (
            self.difference(1+self.s, self.x) / self.lam,
            self.f(p["Z"]) - p["W"],
            self.period_two_quotient(p["Z"]),
            self.u**3 * U - V,
        )

    def diagnostics(self):
        """Numerical residuals, not interval-certified statements."""
        ctx = self.ctx
        p = self.portrait_points
        X, Y, Z, W = (p[k] for k in ("X", "Y", "Z", "W"))
        U, V = self.separation_factors()
        h = self.h0
        E = 28 * self.lam * (
            (1-self.x*self.x)*(1-self.omega)*h/3
            - (3-2*self.omega-self.x*self.x)*self.s**2/15
            + (3-self.omega)*h*self.s**2/15 - self.s**4/35
        )
        residuals = {
            "E": abs(E),
            "S": abs(self.f(self.x)-self.f(1+self.s)),
            "T": abs(self.f(Z)-W),
            "Q": abs(self.period_two_quotient(Z)),
            "F_scaled": abs(self.u**3*U-V),
            "critical_value_c4_c5": abs(self.f(1+self.s)-self.f(1-self.s)),
            "critical_value_c3_c6": abs(self.f(-self.x)-Y),
            "cycle_W_to_Z": abs(self.f(W)-Z),
            "cubic_separation_identity": abs((Y-X)-self.x**3*U),
            "quartic_separation_identity": abs((Y-X)-self.s**4*V),
        }
        critical = self.critical_points
        named = critical + (X, Y, Z, W)
        gaps = {
            "critical_min": min(abs(a-b) for i, a in enumerate(critical)
                                for b in critical[i+1:]),
            "critical_values": abs(Y-X),
            "cycle": abs(Z-W),
            "named_point_min": min(abs(a-b) for i, a in enumerate(named)
                                   for b in named[i+1:]),
        }
        tolerance = ctx.power(10, -self.requested_dps)
        # Residuals must also be small compared with the collapsing orbit gaps.
        scale = min(ctx.mpf(1), gaps["critical_values"], gaps["cycle"]) if self.t else ctx.mpf(1)
        numerical_ok = max(residuals.values()) < tolerance * scale
        roundoff = ctx.power(10, -ctx.dps+15) * max(
            ctx.mpf(1), *(abs(v) for v in self.coefficients)
        )
        resolved = self.t != 0 and min(gaps.values()) > roundoff and numerical_ok
        return {"residuals": residuals, "gaps": gaps,
                "numerical_ok": numerical_ok, "portrait_resolved": resolved,
                "working_dps": ctx.dps}

    def escape_radius(self):
        """Cauchy comparison bound ensuring |f(z)|>|z| beyond this radius."""
        # Include the extra |z| in the coefficient comparison, so this is an
        # escape bound, not merely a root bound for f itself.
        return 1 + max((abs(a) + (1 if i == 1 else 0))/abs(self.lam)
                       for i, a in enumerate(self.coefficients[:-1]))

    def orbit(self, z, iterations=20):
        """Include z and stop at the first iterate beyond a valid escape bound."""
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 0:
            raise ValueError("iterations must be a nonnegative integer")
        values = [self.ctx.mpc(z)]
        bound = self.escape_radius()
        for _ in range(iterations):
            if abs(values[-1]) > bound:
                break
            values.append(self.f(values[-1]))
        return tuple(values)


def _point(ctx, t, u, omega, lam, B, requested_dps):
    x, s = t**4 * u, t**3
    h0, _ = _h0_and_H(ctx, x, s, omega)
    derivative = [7*lam]
    for c in (omega, x, -x, 1+s, 1-s, 1+h0):
        derivative = _multiply(derivative, [-c, 1])
    coefficients = (B,) + tuple(v/(i+1) for i, v in enumerate(derivative))
    return FamilyPoint(ctx, t, u, x, s, h0, omega, lam, B,
                       requested_dps, coefficients)


def _parse_t(ctx, t):
    if isinstance(t, (tuple, list)):
        if len(t) != 2:
            raise ValueError("t must be real or a (real, imaginary) pair")
        return ctx.mpc(t[0], t[1])
    return ctx.mpc(t)


def solve_family(t="0", *, dps=60, steps=8):
    """Continue the positive-real u(0)=4^(-1/3) branch along a radial path.

    t may be a real decimal string, a pair of real/imaginary decimal strings,
    or a numeric value. |t| <= 0.2 is an operational exploration limit, not
    a mathematically certified chart radius. Failure raises an exception;
    no approximation off the portrait is silently returned.
    """
    if isinstance(dps, bool) or not isinstance(dps, int) or dps < 30:
        raise ValueError("dps must be an integer >= 30")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be a positive integer")
    ctx = mpmath.mp.clone()
    ctx.dps = dps + 30
    target = _parse_t(ctx, t)
    if not ctx.isfinite(target) or abs(target) > ctx.mpf("0.2"):
        raise ValueError("t must be finite and satisfy |t| <= 0.2")
    # Orbit gaps are O(t^12). Retain dps digits below their scale.
    loss = max(0, int(ctx.ceil(-12*ctx.log10(abs(target))))) if target else 0
    ctx.dps = dps + 30 + loss
    target = _parse_t(ctx, t)
    theta = lambda a: 64*(2*a-1)**3*(8*a-3)**4-(7*a-3)**7
    a = ctx.findroot(theta, (ctx.mpf("0.306"), ctx.mpf("0.307")))
    hp = a*a * (a-1)**3 * (7*a-3)
    initial = (ctx.root(ctx.mpf(1)/4, 3), ctx.mpf(3)/7,
               -1/hp, 4*a*(2*a-1)/(7*a-3))
    current = _point(ctx, ctx.mpc(0), *initial, dps)
    if target:
        for k in range(1, steps+1):
            tk = target*k/steps
            def equations(u, omega, lam, B):
                return _point(ctx, tk, u, omega, lam, B, dps).equations()
            try:
                solution = ctx.findroot(
                    equations, (current.u, current.omega, current.lam, current.B),
                    tol=ctx.power(10, -ctx.dps+15), maxsteps=40,
                )
            except (ValueError, ZeroDivisionError) as error:
                raise RuntimeError(f"Local continuation failed at step {k}/{steps}") from error
            current = _point(ctx, tk, *solution, dps)
    if not current.diagnostics()["numerical_ok"]:
        raise RuntimeError("Portrait residuals failed the requested numerical tolerance")
    return current
