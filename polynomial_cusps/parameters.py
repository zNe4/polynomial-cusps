"""Checked parameter samples, continuation caches, and closed parameter circles."""

from collections import OrderedDict
from dataclasses import dataclass

import mpmath
import numpy as np

from .family import MAX_PARAMETER_ABS, solve_family
from .taylor import preview_values, solve_explorer_family
from .rendering import Viewport, _check
from .rescaling import RescaledFamily


# Cell states. Attraction refers only to the structurally constrained cycle.
UNRESOLVED, ATTRACTING, REPELLING, NEUTRAL, BOUNDARY, ESCAPED, FAILED, OUTSIDE = range(8)
COLORS = np.array([(45, 58, 74), (52, 164, 176), (178, 107, 192), (222, 186, 100),
                   (246, 226, 164), (232, 143, 82), (186, 66, 75), (13, 22, 34)], dtype=np.uint8)


class FamilyCache:
    def __init__(self, capacity=4096):
        self.capacity = capacity
        self.points = OrderedDict()

    def get(self, real, imag, dps=40, seed=None, cancel=None):
        _check(cancel)
        key = (str(real), str(imag), dps)
        if key in self.points:
            self.points.move_to_end(key)
            return self.points[key]
        try:
            point = (solve_family((real, imag), dps=dps, steps=1, seed=seed) if seed is not None
                     else solve_explorer_family((real, imag), dps=dps))
        except RuntimeError:
            _check(cancel)
            point = solve_family((real, imag), dps=dps)
        _check(cancel)
        self.points[key] = point
        if len(self.points) > self.capacity:
            self.points.popitem(last=False)
        return point


def cycle_state(reference):
    p, c = reference.point, reference.point.ctx
    if not p.t:
        return BOUNDARY
    delta = reference.cycle_scale.value
    M = reference.kernels.cycle.portrait_multiplier_defect_scaled()
    # (|1+delta^2 M|^2-1)/|delta|^2. No tiny subtraction from one.
    signal = 2*c.re((delta/abs(delta))**2*M) + abs(delta)**2*abs(M)**2
    tolerance = c.power(10, -min(20, p.requested_dps//2))*max(1, abs(M))
    if abs(signal) < tolerance:
        return NEUTRAL
    return ATTRACTING if signal < 0 else REPELLING


@dataclass(frozen=True)
class ParameterGrid:
    view: Viewport
    states: np.ndarray
    points: dict
    mode: str
    dps: int
    iterations: int
    approximate: bool = False


def parameter_preview(view=Viewport("global", "0", "0", "1.1"), *, size=129, cancel=None):
    """Fast cycle-color preview from the table, without checked family points.

    Uncertain degree comparisons remain unresolved. This is numerical preview
    evidence only; clicking always constructs and verifies the actual family.
    """
    if not isinstance(size, int) or not 3 <= size <= 1025:
        raise ValueError("Preview samples must be between 3 and 1025")
    span, center = float(view.span), complex(float(view.real), float(view.imag))
    if not np.isfinite(span) or span <= 0 or not np.isfinite(center):
        raise ValueError("Preview viewport must be finite with positive span")
    if center and span/size < 8*np.finfo(float).eps*abs(center):
        raise ValueError("This parameter zoom needs the verified precision mode")
    _check(cancel)
    offsets = (np.arange(size)+0.5)/size-0.5
    t = center+span*(offsets[None, :]-1j*offsets[:, None])
    radius = np.abs(t)
    inside = radius <= float(MAX_PARAMETER_ABS)
    safe_t = np.where(inside, t, 0)
    values, errors = preview_values(safe_t)
    C, M = values["C"], values["M"]
    c_abs, m_abs = np.abs(C), np.abs(M)
    phase_t = np.ones_like(t)
    np.divide(t, radius, out=phase_t, where=radius > 0)
    phase = phase_t**12*C/np.maximum(c_abs, 1e-300)
    quadratic = np.abs(safe_t)**24*c_abs**2*m_abs**2
    signal = 2*np.real(phase**2*M)+quadratic
    relative_c = errors["C"]/np.maximum(c_abs, 1e-300)
    tolerance = (4*errors["M"]+16*m_abs*relative_c
                 +8*quadratic*(relative_c+errors["M"]/np.maximum(m_abs, 1)))
    reliable = inside & np.isfinite(signal) & (relative_c < 0.01)
    states = np.full(t.shape, OUTSIDE, dtype=np.uint8)
    states[inside] = UNRESOLVED
    states[reliable & (signal < -tolerance)] = ATTRACTING
    states[reliable & (signal > tolerance)] = REPELLING
    states[inside & (radius == 0)] = BOUNDARY
    _check(cancel)
    return ParameterGrid(view, states, {}, "cycle", 0, 0, approximate=True)


def parameter_grid(view=Viewport("global", "0", "0", "0.28"), *, size=17,
                   dps=40, iterations=128, mode="cycle", cache=None, cancel=None, progress=None):
    if not isinstance(size, int) or not 3 <= size <= 81:
        raise ValueError("Parameter samples must be between 3 and 81")
    if mode not in ("cycle", "free") or not 1 <= iterations <= 100000:
        raise ValueError("Invalid parameter mode or iteration limit")
    c = mpmath.mp.clone()
    c.dps = max(50, dps+20)
    span, center = c.mpf(view.span), c.mpc(view.real, view.imag)
    if not c.isfinite(span) or span <= 0 or not c.isfinite(center):
        raise ValueError("Parameter viewport must be finite with positive span")
    cache = cache or FamilyCache()
    states = np.full((size, size), OUTSIDE, dtype=np.uint8)
    points, seed = {}, None
    for row in range(size):
        columns = range(size) if row % 2 == 0 else range(size-1, -1, -1)
        for col in columns:
            _check(cancel)
            t = view.coordinate(c, (c.mpf(col)+c.mpf("0.5"))/size,
                                (c.mpf(row)+c.mpf("0.5"))/size)
            if abs(t) > c.mpf(MAX_PARAMETER_ABS):
                continue
            try:
                point = cache.get(c.nstr(t.real, c.dps), c.nstr(t.imag, c.dps), dps, seed, cancel)
                reference = RescaledFamily(point)
                if mode == "cycle":
                    state = cycle_state(reference)
                elif not point.t:
                    state = BOUNDARY
                else:
                    z, bound, state = point.omega, point.escape_radius(), UNRESOLVED
                    for n in range(iterations+1):
                        if n % 16 == 0:
                            _check(cancel)
                        if abs(z) > bound:
                            state = ESCAPED
                            break
                        z = point.f(z)
                states[row, col], points[(row, col)], seed = state, point, point
            except (RuntimeError, ValueError, ZeroDivisionError):
                states[row, col] = FAILED
        if progress:
            progress(((row+1)/size, states.copy()))
    return ParameterGrid(view, states, points, mode, dps, iterations)


class WindingUndersampled(ValueError):
    """Successive samples cannot yet resolve the change of argument."""


def winding(ctx, values):
    if any(value == 0 for value in values):
        raise ValueError("Cannot measure winding through zero")
    angles = [ctx.arg(b/a) for a, b in zip(values, values[1:])]
    if max(abs(a) for a in angles) >= ctx.pi*ctx.mpf("0.8"):
        raise WindingUndersampled("Winding is undersampled; increase frames")
    return sum(angles)/(2*ctx.pi)


@dataclass(frozen=True)
class ParameterCircle:
    radius: str
    points: tuple
    windings: dict


def parameter_circle(radius="0.08", *, frames=96, dps=60, cache=None, cancel=None, progress=None):
    if not isinstance(frames, int) or not 64 <= frames <= 720:
        raise ValueError("Use 64 to 720 frames to resolve the winding")
    c = mpmath.mp.clone()
    c.dps = dps+30
    r = c.mpf(radius)
    if not c.isfinite(r) or not 0 < r <= c.mpf(MAX_PARAMETER_ABS):
        raise ValueError(f"Circle radius must satisfy 0 < r <= {MAX_PARAMETER_ABS}")
    cache, points, seed = cache or FamilyCache(), [], None
    for k in range(frames):
        _check(cancel)
        t = r*c.exp(2j*c.pi*k/frames)
        t *= min(c.mpf(1), r/abs(t))
        point = cache.get(c.nstr(t.real, c.dps), c.nstr(t.imag, c.dps), dps, seed, cancel)
        points.append(point)
        seed = point
        if progress:
            progress((k+1)/frames)
    # Independently continue the final arc back to the original parameter.
    # Reusing the first cached point here would conceal a branch mismatch.
    first = points[0]
    closing = solve_family((first.t.real, first.t.imag), dps=dps, steps=1, seed=seed)
    if max(abs(getattr(closing, name)-getattr(first, name))
           for name in ("u", "omega", "lam", "B")) > c.power(10, -dps//2):
        raise RuntimeError("The marked parameter continuation did not close")
    points.append(closing)
    tracks = {"x": [], "s": [], "Y-X": [], "W-Z": []}
    for p in points:
        ref = RescaledFamily(p)
        for name, value in (("x", p.x), ("s", p.s), ("Y-X", ref.value_scale.value),
                            ("W-Z", ref.cycle_scale.value)):
            tracks[name].append(c.mpc(value))
    counts = {name: winding(c, values) for name, values in tracks.items()}
    return ParameterCircle(str(radius), tuple(points), counts)
