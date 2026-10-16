"""Finite-time escape rendering in global or rescaled dynamical coordinates."""

from dataclasses import dataclass, replace
import math
import time

import numpy as np

from .family import solve_family
from .rescaling import RescaledFamily


class RenderCancelled(Exception):
    pass


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise RenderCancelled()


@dataclass(frozen=True)
class Viewport:
    kind: str = "global"
    real: str = "0.5"
    imag: str = "0"
    span: str = "1.8"
    fixed_axes: bool = False

    @classmethod
    def preset(cls, kind):
        if kind == "global":
            return cls()
        if kind not in ("zero", "one", "values", "cycle"):
            raise ValueError("Unknown viewport")
        return cls(kind, "0.5" if kind in ("values", "cycle") else "0", "0", "4")

    def coordinate(self, ctx, horizontal, vertical):
        """Fractions across the square, with imaginary coordinates increasing upward."""
        return ctx.mpc(self.real, self.imag) + ctx.mpf(self.span)*ctx.mpc(
            ctx.mpf(horizontal)-ctx.mpf("0.5"), ctx.mpf("0.5")-ctx.mpf(vertical)
        )

    def zoom(self, ctx, factor, horizontal="0.5", vertical="0.5"):
        factor = ctx.mpf(factor)
        center = self.coordinate(ctx, horizontal, vertical)
        # Keep the position under the cursor fixed.
        old_center = ctx.mpc(self.real, self.imag)
        new_center = center + factor*(old_center-center)
        return Viewport(self.kind, ctx.nstr(new_center.real, ctx.dps),
                        ctx.nstr(new_center.imag, ctx.dps),
                        ctx.nstr(ctx.mpf(self.span)*factor, ctx.dps), self.fixed_axes)


@dataclass(frozen=True)
class RenderSettings:
    size: int = 384
    iterations: int = 256
    engine: str = "auto"

    def validate(self):
        if not isinstance(self.size, int) or not 4 <= self.size <= 2048:
            raise ValueError("Resolution must be between 4 and 2048")
        if not isinstance(self.iterations, int) or not 1 <= self.iterations <= 100000:
            raise ValueError("Iterations must be between 1 and 100000")
        if self.engine not in ("auto", "double", "mp"):
            raise ValueError("Engine must be auto, double, or mp")


@dataclass(frozen=True)
class Scene:
    point: object
    reference: RescaledFamily
    free_orbit: tuple

    def absolute(self, local, kind, fixed_axes=False):
        if kind == "global":
            return self.point.ctx.mpc(local)
        chart = self.reference.charts[kind]
        if fixed_axes:
            if not chart.available:
                raise ValueError("This chart collapses at t=0")
            return chart.center+abs(chart.scale.value)*local
        return chart.at(local).absolute()

    def local(self, absolute, kind, fixed_axes=False):
        if kind == "global":
            return absolute
        chart = self.reference.charts[kind]
        if fixed_axes:
            if not chart.available:
                raise ValueError("This chart collapses at t=0")
            return (absolute-chart.center)/abs(chart.scale.value)
        return chart.relative(absolute)

    def nodes(self):
        points = {f"c{i}": z for i, z in enumerate(self.point.critical_points, 1)}
        points.update(self.point.portrait_points)
        if not self.point.t:
            points["a"] = self.point.f(self.point.B)
        return points


def prepare_scene(real="0", imag="0", dps=60, orbit=40, cancel=None):
    if not isinstance(orbit, int) or not 0 <= orbit <= 5000:
        raise ValueError("Free-orbit steps must be between 0 and 5000")
    _check(cancel)
    from .taylor import solve_explorer_family
    point = solve_explorer_family((real, imag), dps=dps)
    return scene_from_point(point, orbit, cancel)


def scene_from_point(point, orbit=40, cancel=None):
    if not isinstance(orbit, int) or not 0 <= orbit <= 5000:
        raise ValueError("Free-orbit steps must be between 0 and 5000")
    _check(cancel)
    reference = RescaledFamily(point)
    values = [point.omega]
    bound = point.escape_radius()
    for _ in range(orbit):
        _check(cancel)
        if abs(values[-1]) > bound:
            break
        values.append(point.f(values[-1]))
    return Scene(point, reference, tuple(values))


@dataclass(frozen=True)
class RenderResult:
    viewport: Viewport
    settings: RenderSettings
    engine: str
    escaped_at: np.ndarray  # -1 means unresolved at the finite iteration limit
    magnitude: np.ndarray
    fallback_pixels: int
    seconds: float

    @property
    def escaped_count(self):
        return int(np.count_nonzero(self.escaped_at >= 0))


def _grid(view, size):
    center = complex(float(view.real), float(view.imag))
    span = float(view.span)
    positions = (np.arange(size)+0.5)/size-0.5
    return center + span*(positions[None, :]-1j*positions[:, None])


def _pixel_mp(scene, view, settings, row, col, cancel):
    p, ctx = scene.point, scene.point.ctx
    local = view.coordinate(ctx, (ctx.mpf(col)+ctx.mpf("0.5"))/settings.size,
                            (ctx.mpf(row)+ctx.mpf("0.5"))/settings.size)
    z = scene.absolute(local, view.kind, view.fixed_axes)
    bound = p.escape_radius()
    for n in range(settings.iterations+1):
        if n % 8 == 0:
            _check(cancel)
        if abs(z) > bound:
            return n, float(min(abs(z), ctx.mpf("1e300")))
        if n < settings.iterations:
            z = p.f(z)
    return -1, float(abs(z))


def render(scene, view=Viewport(), settings=RenderSettings(), cancel=None, progress=None, *, mp_preview_size=None):
    """Render finite-time escape data; no attraction or membership certification."""
    settings.validate()
    if view.kind not in ("global", "zero", "one", "values", "cycle"):
        raise ValueError("Unknown viewport")
    p, ctx = scene.point, scene.point.ctx
    center, span = ctx.mpc(view.real, view.imag), ctx.mpf(view.span)
    if not ctx.isfinite(center) or not ctx.isfinite(span) or span <= 0:
        raise ValueError("Viewport coordinates must be finite with positive span")
    physical_center = scene.absolute(center, view.kind, view.fixed_axes)  # rejects collapsed charts
    physical_scale = 1 if view.kind == "global" else scene.reference.charts[view.kind].scale.value
    if abs(physical_scale)*span/settings.size < 32*ctx.eps*max(1, abs(physical_center)):
        raise ValueError("Pixel spacing exceeds reference precision; increase dps")
    double_resolved = span/settings.size > ctx.mpf("1e-14")*max(1, abs(center))
    engine = settings.engine
    kernels = None
    if engine != "mp":
        try:
            if not double_resolved:
                raise OverflowError("Pixel spacing needs high precision")
            if not all(math.isfinite(float(v)) for v in (center.real, center.imag, span)):
                raise OverflowError("Viewport is outside binary64 range")
            if view.kind != "global":
                kernels = scene.reference.binary64()
            engine = "double" if view.kind == "global" else "rescaled"
        except OverflowError as error:
            if settings.engine == "double":
                raise ValueError(f"Cannot use double precision: {error}") from error
            engine = "mp"
    if engine == "mp" and settings.engine == "auto" and mp_preview_size is not None:
        settings = replace(settings, size=min(settings.size, mp_preview_size))
        settings.validate()
    size = settings.size
    escaped = np.full((size, size), -1, dtype=np.int32)
    magnitude = np.zeros((size, size), dtype=np.float64)
    start = time.monotonic()
    _check(cancel)
    if engine == "mp":
        for row in range(size):
            for col in range(size):
                escaped[row, col], magnitude[row, col] = _pixel_mp(scene, view, settings, row, col, cancel)
            if progress:
                progress((row+1)/size)
        return RenderResult(view, settings, engine, escaped, magnitude, 0, time.monotonic()-start)

    z = _grid(view, size)
    if view.kind != "global" and view.fixed_axes:
        scale = scene.reference.charts[view.kind].scale.value
        z *= complex(abs(scale)/scale)
    active = np.ones((size, size), dtype=bool)
    fallback = np.zeros_like(active)
    kind = view.kind
    coefficients = tuple(complex(a) for a in p.coefficients)
    bound = float(p.escape_radius())
    for n in range(settings.iterations+1):
        _check(cancel)
        if not active.any():
            break
        # Materialization is used only for a coarse escape test, not to advance
        # orbits whose local displacement would disappear in the absolute sum.
        if kind == "global":
            absolute = z
        else:
            chart = scene.reference.charts[kind]
            absolute = complex(chart.center)+complex(chart.scale.value)*z
        with np.errstate(over="ignore", invalid="ignore"):
            radius = np.abs(absolute)
        newly = active & np.isfinite(radius) & (radius > bound)
        escaped[newly], magnitude[newly] = n, radius[newly]
        active[newly] = False
        # Outside a bounded local range, restart affected pixels in the
        # original polynomial at reference precision rather than invent an exit.
        bad = active & (~np.isfinite(z) | ~np.isfinite(radius))
        if kind != "global":
            bad |= active & (np.abs(z) > 1e6)
        fallback |= bad
        active[bad] = False
        if n == settings.iterations:
            magnitude[active] = radius[active]
            break
        if not active.any():
            break
        values = z[active]
        with np.errstate(over="ignore", invalid="ignore"):
            if kind == "global":
                image = np.full(values.shape, coefficients[-1], dtype=np.complex128)
                for a in reversed(coefficients[:-1]):
                    image = image*values+a
            elif kind == "zero":
                image = kernels.zero_to_values(values)
            elif kind == "one":
                image = kernels.one_to_values(values)
            elif kind == "values":
                image = kernels.values_to_cycle(values)
            else:
                image = kernels.cycle(values)  # retain measured residuals
        z[active] = image
        if kind in ("zero", "one"):
            kind = "values"
        elif kind == "values":
            kind = "cycle"
        if progress and n % 16 == 0:
            progress(n/settings.iterations)
    count = int(fallback.sum())
    for i, (row, col) in enumerate(zip(*np.nonzero(fallback))):
        _check(cancel)
        escaped[row, col], magnitude[row, col] = _pixel_mp(scene, view, settings, int(row), int(col), cancel)
        if progress and i % 32 == 0:
            progress(i/max(1, count))
    return RenderResult(view, settings, engine, escaped, magnitude, count, time.monotonic()-start)


def colorize(result, mode="Escape", shade=True):
    """Color escape data or its finite-resolution boundary; unresolved != inside."""
    escaped = result.escaped_at >= 0
    rgb = np.empty((*escaped.shape, 3), dtype=np.uint8)
    rgb[:] = (12, 20, 32)
    if mode == "Escape":
        steps = result.escaped_at.astype(float)
        smooth = steps.copy()
        mask = escaped & (result.magnitude > 1) & np.isfinite(result.magnitude)
        smooth[mask] -= np.log(np.maximum(1e-100, np.log(result.magnitude[mask])))/np.log(7)
        phase = smooth/22
        density = 1-np.exp(-np.maximum(0, smooth)/8)
        for k, (base, amplitude, offset) in enumerate(((12, 65, 0.0), (27, 160, 0.23), (44, 180, 0.45))):
            channel = base+amplitude*density*(0.65+0.35*np.cos(2*np.pi*(phase+offset)))
            rgb[:, :, k][escaped] = np.clip(channel[escaped], 0, 255).astype(np.uint8)
    elif mode == "Julia":
        rgb[escaped] = (19, 40, 57)
    else:
        raise ValueError("Color mode must be Escape or Julia")
    if shade:
        rgb[~escaped] = (29, 43, 59)
    edge = np.zeros_like(escaped)
    edge[1:, :] |= escaped[1:, :] != escaped[:-1, :]
    edge[:-1, :] |= escaped[:-1, :] != escaped[1:, :]
    edge[:, 1:] |= escaped[:, 1:] != escaped[:, :-1]
    edge[:, :-1] |= escaped[:, :-1] != escaped[:, 1:]
    rgb[edge] = (204, 229, 230)
    return rgb
