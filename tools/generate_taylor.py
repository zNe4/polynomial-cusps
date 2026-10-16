"""Rebuild the numerical Cauchy/Taylor table: python -m tools.generate_taylor.

This is an offline build tool. The installed explorer loads the bundled table.
The table is a numerical approximation, not a certified convergence radius.
"""

import json
from pathlib import Path

from polynomial_cusps.family import solve_family
from polynomial_cusps.rescaling import RescaledFamily


def generate():
    samples, degree, dps = 256, 128, 70
    first = solve_family("0.5", dps=dps)
    c, seed = first.ctx, first
    radius = c.mpf("0.5")
    values = []
    for k in range(samples):
        t = radius*c.exp(2j*c.pi*k/samples)
        # Avoid a last-bit radius excess at a point on the operational boundary.
        t *= min(c.mpf(1), radius/abs(t))
        p = solve_family(t, dps=dps, steps=1, seed=seed)
        ref = RescaledFamily(p)
        values.append((p.u, p.omega, p.lam, p.B, ref.value_scale.unit,
                       ref.cycle_scale.unit, ref.kernels.cycle.portrait_multiplier_defect_scaled()))
        seed = p
        if k % 32 == 0:
            print(f"Checked samples: {k}/{samples}", flush=True)
    closing = solve_family("0.5", dps=dps, steps=1, seed=seed)
    closure = max(abs(getattr(closing, name)-getattr(first, name))
                  for name in ("u", "omega", "lam", "B"))
    if closure > c.mpf("1e-60"):
        raise RuntimeError("The continuation circle failed to close")
    names = ("u", "omega", "lam", "B", "D", "C", "M")
    coefficients = {name: [] for name in names}
    # Store coefficients of (t/radius)^n, avoiding huge coefficient magnitudes.
    for n in range(degree+1):
        step, weight = c.exp(-2j*c.pi*n/samples), c.mpc(1)
        sums = [c.mpc(0) for _ in names]
        for row in values:
            for j, value in enumerate(row):
                sums[j] += value*weight
            weight *= step
        for name, total in zip(names, sums):
            value = total/samples
            coefficients[name].append([c.nstr(value.real, 70), c.nstr(value.imag, 70)])
    data = {"format": "polynomial-cusps-taylor-v1", "radius": "0.5",
            "degree": degree, "comparison_degree": 96, "samples": samples,
            "requested_dps": dps, "closure_error": c.nstr(closure, 10),
            "interpretation": "Numerical Cauchy/Taylor approximation; selected points require Newton correction.",
            "coefficients": coefficients}
    destination = Path(__file__).resolve().parents[1]/"polynomial_cusps/data/family_taylor.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    print(f"Saved {destination}; closure error {c.nstr(closure, 6)}", flush=True)


if __name__ == "__main__":
    generate()
