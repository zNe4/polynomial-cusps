"""Bundled numerical Taylor models and Newton-corrected explorer parameters."""

from functools import lru_cache
import json
from pathlib import Path

import mpmath

from .family import MAX_PARAMETER_ABS, _horner, _parse_t, _point, solve_family


@lru_cache(maxsize=1)
def table():
    return json.loads((Path(__file__).parent/"data/family_taylor.json").read_text(encoding="utf-8"))


def predict(ctx, t):
    """High-precision evaluation of an approximate table, not a family solve."""
    data = table()
    if abs(t) > ctx.mpf(data["radius"]):
        raise ValueError("Outside the Taylor preview disk")
    z = t/ctx.mpf(data["radius"])
    return {name: _horner([ctx.mpc(*v) for v in coefficients], z)
            for name, coefficients in data["coefficients"].items()}


def solve_explorer_family(t="0", *, dps=60):
    """Use the series as a predictor; return only a fully checked Newton solve.

    Radial continuation remains the independent fallback and reference solver.
    A large correction is rejected to avoid accepting another distant root.
    """
    if isinstance(dps, bool) or not isinstance(dps, int) or dps < 30:
        return solve_family(t, dps=dps)
    c = mpmath.mp.clone()
    c.dps = dps+30
    target = _parse_t(c, t)
    if not c.isfinite(target) or abs(target) > c.mpf(MAX_PARAMETER_ABS) or not target:
        return solve_family(t, dps=dps)
    c.dps += max(0, int(c.ceil(-12*c.log10(abs(target)))))
    target = _parse_t(c, t)
    try:
        approximation = predict(c, target)
        names = ("u", "omega", "lam", "B")
        seed = _point(c, target, *(approximation[name] for name in names), dps)
        result = solve_family(t, dps=dps, steps=1, seed=seed)
        correction = max(abs(getattr(result, name)-approximation[name])/max(1, abs(approximation[name]))
                         for name in names)
        if correction <= c.mpf("1e-4"):
            return result
    except (OSError, ValueError, RuntimeError, ZeroDivisionError):
        pass
    return solve_family(t, dps=dps)


def preview_values(t):
    """Vectorized binary64 predictions and degree-comparison error indicators.

    Indicators are empirical truncation/roundoff estimates, not interval bounds.
    """
    import numpy as np
    data = table()
    z = np.asarray(t, dtype=np.complex128)/float(data["radius"])
    values, errors = {}, {}
    for name, rows in data["coefficients"].items():
        coefficients = np.array([complex(float(re), float(im)) for re, im in rows])
        full = np.polynomial.polynomial.polyval(z, coefficients)
        shorter = np.polynomial.polynomial.polyval(z, coefficients[:data["comparison_degree"]+1])
        values[name] = full
        errors[name] = 20*np.abs(full-shorter)+1e-12*np.maximum(1, np.abs(full))
    return values, errors
