"""Inspect a family parameter without starting a GUI."""

import argparse
import json

from .family import solve_family
from .rescaling import RescaledFamily


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", default="0", help="real part of t (decimal)")
    parser.add_argument("--imag", default="0", help="imaginary part of t (decimal)")
    parser.add_argument("--dps", type=int, default=60, help="requested decimal accuracy, >=30")
    parser.add_argument("--steps", type=int, default=8, help="radial continuation steps")
    parser.add_argument("--orbit", type=int, default=20, help="number of free-critical iterates")
    parser.add_argument("--rescaled", action="store_true", help="include factored scales and local-map diagnostics")
    args = parser.parse_args()
    if args.orbit < 0:
        parser.error("--orbit must be nonnegative")
    try:
        point = solve_family((args.real, args.imag), dps=args.dps, steps=args.steps)
    except (ValueError, RuntimeError, ZeroDivisionError) as error:
        parser.error(str(error))
    ctx = point.ctx
    def encode(value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [encode(v) for v in value]
        if isinstance(value, (bool, int)):
            return value
        if hasattr(value, "imag") and value.imag:
            return {"real": ctx.nstr(value.real, ctx.dps-15),
                    "imag": ctx.nstr(value.imag, ctx.dps-15)}
        return ctx.nstr(value.real if hasattr(value, "real") else value, ctx.dps-15)
    output = {
        "normalization": "affine: critical midpoints 0 and 1",
        "t": point.t,
        "parameters": {k: getattr(point, k) for k in ("u", "x", "s", "h0", "omega", "lam", "B")},
        "critical_points": dict(zip((f"c{i}" for i in range(1, 7)), point.critical_points)),
        "coefficients_ascending": point.coefficients,
        "portrait_points": point.portrait_points,
        "diagnostics": point.diagnostics(),
        "free_critical_orbit": point.orbit(point.omega, args.orbit),
        "free_orbit_infinite": "not decided by finite numerical iteration",
    }
    if args.rescaled:
        output["rescaled"] = RescaledFamily(point).report()
    print(json.dumps(encode(output), indent=2))


if __name__ == "__main__":
    main()
