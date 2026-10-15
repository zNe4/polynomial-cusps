"""Local charts with factored scales and optional binary64 evaluation kernels.

The default cycle map carries the measured polynomial residuals. Methods
named ``portrait_*`` explicitly impose the exact cycle relations instead.
"""

from dataclasses import dataclass
from math import comb, isfinite

from .family import _h0_and_H, _horner, _multiply


def _shift(coefficients, center):
    """Taylor coefficients p^(k)(center)/k!, without numerical differentiation."""
    return tuple(sum(coefficients[j]*comb(j, k)*center**(j-k)
                     for j in range(k, len(coefficients)))
                 for k in range(len(coefficients)))


def _divided_shift(coefficients, center, displacement):
    """p[center,center+displacement], without forming the second endpoint."""
    return _horner(_shift(coefficients, center)[1:], displacement)


def _primitive(factors, factor):
    coefficients = [factor]
    for polynomial in factors:
        coefficients = _multiply(coefficients, polynomial)
    return (0,) + tuple(a/(k+1) for k, a in enumerate(coefficients))


def _as_double(value, *, require_nonzero=False):
    result = complex(value)
    if not isfinite(result.real) or not isfinite(result.imag):
        raise OverflowError("A chart quantity is outside binary64 range")
    if require_nonzero and value != 0 and result == 0:
        raise OverflowError("The chart scale underflows binary64; retain high precision")
    return result


@dataclass(frozen=True)
class FactoredScale:
    """t^order * unit, retaining its complex phase and logarithmic size."""

    ctx: object
    t: object
    order: int
    unit: object

    @property
    def value(self):
        return self.t**self.order * self.unit

    @property
    def log10_abs(self):
        if self.unit == 0 or (self.t == 0 and self.order):
            return -self.ctx.inf
        return self.order*self.ctx.log10(abs(self.t)) + self.ctx.log10(abs(self.unit))

    @property
    def phase(self):
        if self.value == 0:
            return None
        return self.ctx.arg(self.value)

    def report(self):
        return {"order": self.order, "unit": self.unit, "value": self.value,
                "log10_abs": self.log10_abs, "phase": self.phase}


@dataclass(frozen=True)
class ChartPoint:
    """A center, scale, and local position, kept as an unevaluated affine sum."""

    chart: object
    xi: object

    def absolute(self):
        """Explicitly materialize the affine sum, using the reference context."""
        return self.chart.center + self.chart.scale.value * self.xi


@dataclass(frozen=True)
class AffineChart:
    center: object
    scale: FactoredScale

    @property
    def available(self):
        return self.scale.value != 0

    def at(self, xi):
        if not self.available:
            raise ValueError("This chart collapses at t=0; use the global boundary map")
        return ChartPoint(self, self.scale.ctx.mpc(xi))

    def relative(self, z):
        """Convert an absolute reference value; this may lose relative digits."""
        if not self.available:
            raise ValueError("This chart collapses at t=0")
        return (self.scale.ctx.mpc(z)-self.center)/self.scale.value


@dataclass(frozen=True)
class AnchoredMap:
    coefficients: tuple
    anchor: object
    offset: object = 0

    @classmethod
    def from_primitive(cls, primitive, anchor, offset=0):
        return cls(_shift(primitive, anchor)[1:], anchor, offset)

    def __call__(self, xi):
        displacement = xi-self.anchor
        return self.offset + displacement*_horner(self.coefficients, displacement)

    def binary64(self):
        return AnchoredMap(tuple(_as_double(v) for v in self.coefficients),
                           _as_double(self.anchor), _as_double(self.offset))


@dataclass(frozen=True)
class CycleKernel:
    delta: object
    b: tuple
    residual_start: object
    residual_end: object

    def portrait_map(self, xi):
        """Impose f(Z)=W and f(W)=Z; at delta=0 return the formal limit."""
        return 1-xi + sum(self.b[k]*self.delta**(k-1)*(xi**k-xi)
                          for k in range(2, 8))

    def __call__(self, xi):
        """The actual polynomial map in the chart, with measured residuals."""
        if self.residual_start is None:
            raise ValueError("No cycle chart at t=0; only its portrait limit is defined")
        return self.portrait_map(xi) + self.residual_start*(1-xi) + self.residual_end*xi

    def residual_bound(self, radius=2):
        """Bound |raw H - portrait H| on |xi|<=radius (not a roundoff bound)."""
        if radius < 0:
            raise ValueError("radius must be nonnegative")
        if self.residual_start is None:
            raise ValueError("No polynomial cycle chart at t=0")
        return abs(self.residual_start) + radius*abs(self.residual_end-self.residual_start)

    def portrait_multiplier_defect_scaled(self):
        """M=(mu-1)/delta^2 for the portrait map, with no subtraction from one."""
        P = sum(self.b[k]*self.delta**(k-2) for k in range(2, 8))
        R = sum((k-1)*self.b[k]*self.delta**(k-2) for k in range(2, 8))
        J = sum((k-2)*self.b[k]*self.delta**(k-3) for k in range(3, 8))
        return -J-P*R

    def endpoint_product_correction(self):
        """Raw f'(Z)f'(Z+delta) minus the portrait multiplier.

        The raw endpoints need not be an exact cycle. This quantity is not
        called a multiplier of a nearby, independently solved cycle.
        """
        if self.residual_start is None:
            raise ValueError("No endpoint product at t=0 in this chart")
        e = self.residual_end-self.residual_start
        J = sum((k-2)*self.b[k]*self.delta**(k-3) for k in range(3, 8))
        return e*(-2+self.delta**2*J)+e*e

    def portrait_return_drift_scaled(self, xi):
        """(H(H(xi))-xi)/delta^2, analytically extended to delta=0.

        An exact algebraic rearrangement; this neither advances time nor
        approximates the return by a differential equation.
        """
        a = [0, -sum(self.b[k]*self.delta**(k-2) for k in range(2, 8))]
        a.extend(self.b[k]*self.delta**(k-2) for k in range(2, 8))
        A = _horner(a, xi)
        B = sum(self.b[k]*self.delta**(k-3) * (
            (1-xi)**k-xi**k+2*xi-1
        ) for k in range(3, 8))
        return B + A*_divided_shift(a, 1-xi, self.delta*A)

    def binary64(self):
        delta = _as_double(self.delta, require_nonzero=True)
        return CycleKernel(delta, tuple(_as_double(v) for v in self.b),
                           None if self.residual_start is None else _as_double(self.residual_start),
                           None if self.residual_end is None else _as_double(self.residual_end))


@dataclass(frozen=True)
class ChartKernels:
    """The arrows zero/one -> values -> cycle -> cycle."""

    zero_to_values: AnchoredMap
    one_to_values: AnchoredMap
    values_to_cycle: AnchoredMap
    cycle: CycleKernel

    def binary64(self):
        """Convert references once; subsequent evaluations use native complex arithmetic."""
        return ChartKernels(self.zero_to_values.binary64(), self.one_to_values.binary64(),
                            self.values_to_cycle.binary64(), self.cycle.binary64())


class RescaledFamily:
    """Prepare local references at high precision, once per chosen polynomial."""

    def __init__(self, point):
        self.point = point
        c, t, x, s, w = point.ctx, point.t, point.x, point.s, point.omega
        U, V = point.separation_factors()
        D = point.u**3*U
        self.value_scale = FactoredScale(c, t, 12, D)
        d = self.value_scale.value
        X = point.f(x)
        bx = _shift(point.coefficients, X)
        L = _horner(bx[1:], d)
        self.cycle_scale = FactoredScale(c, t, 12, D*L)
        delta = self.cycle_scale.value
        Z = point.f(X)
        b = _shift(point.coefficients, Z)
        self.charts = {
            "zero": AffineChart(c.mpc(0), FactoredScale(c, t, 4, point.u)),
            "one": AffineChart(c.mpc(1), FactoredScale(c, t, 3, c.mpc(1))),
            "values": AffineChart(X, self.value_scale),
            "cycle": AffineChart(Z, self.cycle_scale),
        }
        # h0/s = sH has a holomorphic extension at zero.
        _, H = _h0_and_H(c, x, s, w)
        zero = _primitive([[-1, 0, 1], [1-s*s, -2*x, x*x],
                           [-1-point.h0, x], [-w, x]], 7*point.lam/U)
        one = _primitive([[1-x*x, 2*s, s*s], [-1, 0, 1],
                          [-s*H, 1], [1-w, s]], 7*point.lam/D)
        values = (c.mpc(0),) + tuple(bx[k]*d**(k-1)/L for k in range(1, 8))
        if t:
            one_offset = point.difference(x, 1+s)/d
            r0 = (point.f(Z)-Z-delta)/delta
            e = 1+point.derivative(Z)+sum(b[k]*delta**(k-1) for k in range(2, 8))
            r1 = r0+e
            self.value_residual = (point.f(1+point.h0)-X-d)/d
        else:
            one_offset = c.mpc(0)
            r0 = r1 = self.value_residual = None
        self.kernels = ChartKernels(
            AnchoredMap.from_primitive(zero, c.mpc(1)),
            AnchoredMap.from_primitive(one, c.mpc(1), one_offset),
            AnchoredMap.from_primitive(values, c.mpc(0)), CycleKernel(delta, b, r0, r1)
        )

    def binary64(self):
        if not self.point.t:
            raise ValueError("At t=0 use the global boundary map; these charts collapse")
        return self.kernels.binary64()

    def report(self):
        cycle = self.kernels.cycle
        M = cycle.portrait_multiplier_defect_scaled()
        defect = FactoredScale(self.point.ctx, self.point.t, 24, self.cycle_scale.unit**2*M)
        correction = cycle.endpoint_product_correction() if self.point.t else None
        return {
            "charts_available": bool(self.point.t),
            "centers": {name: chart.center for name, chart in self.charts.items()},
            "scales": {name: chart.scale.report() for name, chart in self.charts.items()},
            "normalized_residuals": {
                "one_to_values_anchor": self.kernels.one_to_values.offset if self.point.t else None,
                "value_at_c6": self.value_residual,
                "cycle_start": cycle.residual_start, "cycle_end": cycle.residual_end,
                "cycle_map_bound_radius_2": cycle.residual_bound(2) if self.point.t else None,
            },
            "portrait_multiplier_defect_scaled": M,
            "portrait_multiplier_defect": defect.report(),
            "raw_endpoint_product_correction": correction,
            "raw_correction_over_portrait_defect":
                abs(correction/defect.value) if self.point.t and defect.value else None,
            "note": "Portrait quantities impose the exact cycle; raw maps retain measured residuals. "
                    "At t=0 only formal limits of the normalized kernels are defined.",
        }
