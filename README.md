# Polynomial Cusps

Numerical exploration of the degree-seven parabolic counterexample whose
critically marked portrait closure has an irreducible cusp.

**Current stage: M01.1 — rescaled local coordinates.** There is a command-line
inspector, a Python API, and native-complex local evaluation kernels. The graphical explorer is the next
stage; this version does not render Julia sets or a parameter image.

The intended interaction follows [draw_tricorn](https://github.com/zNe4/draw_tricorn):
select a complex parameter on the left and inspect its Julia set, marked
critical points, prescribed orbits, and free critical orbit on the right.
This repository currently implements the family independently; no source code
from draw_tricorn has been copied.

## Run

Python 3.10 or newer is required. The only runtime dependency is mpmath.

```bash
git clone https://github.com/zNe4/polynomial-cusps.git
cd polynomial-cusps
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Boundary polynomial g.
python -m polynomial_cusps --orbit 20

# A nearby complex parameter.
python -m polynomial_cusps --real 0.1 --imag 0.03 --dps 60 --orbit 40

# Tiny separations, logarithmic sizes, and stable multiplier/return data.
python -m polynomial_cusps --real 1e-8 --dps 60 --orbit 0 --rescaled
```

The output is JSON containing polynomial coefficients (ascending powers), all
six critical labels, the points X,Y,Z,W, equation residuals, separation sizes,
and the first iterates of the free critical point. Decimal strings preserve
the available precision. Nonreal values use `{ "real": "...", "imag": "..." }`.
The installed `polynomial-cusps` command accepts the same arguments.

`--dps` requests accuracy relative to the collapsing orbit gaps. Working
precision is increased by 30 guard digits plus approximately
`-12 log10(|t|)` digits. JSON retains the additional digits needed to
distinguish the cycle points. Use decimal strings in the Python API to avoid
rounding inputs to binary64 first.

```python
from polynomial_cusps import solve_family

point = solve_family(("0.1", "0.03"), dps=60)
print(point.critical_points)          # c1,...,c6; c1 = omega
print(point.portrait_points)          # X,Y,Z,W
print(point.diagnostics())
orbit = point.orbit(point.omega, iterations=40)
z = point.ctx.mpc("0.3", "0.02")
print(point.f(z))
```

Every point has an independent mpmath context. Operations do not change the
global precision. `orbit` includes its starting point and stops early after
crossing a conservative escape bound.

## Rescaled local maps

Prepare references at high precision, then evaluate in local coordinates:

```python
from polynomial_cusps import RescaledFamily, solve_family

reference = RescaledFamily(solve_family("1e-8", dps=60))
kernels = reference.binary64()       # conversion happens once
xi = complex(0.31, 0.17)

value_position = kernels.zero_to_values(xi)
cycle_position = kernels.values_to_cycle(value_position)
next_position = kernels.cycle(cycle_position)  # carries measured residuals

# Explicitly impose the exact portrait, instead of hiding residuals:
portrait_next = kernels.cycle.portrait_map(xi)
M = kernels.cycle.portrait_multiplier_defect_scaled()  # (mu-1)/Delta^2
K = kernels.cycle.portrait_return_drift_scaled(xi)     # (H^2(xi)-xi)/Delta^2

structured_point = reference.charts["cycle"].at(xi)
report = reference.report()          # factored scales, phases, residuals
```

`structured_point` retains its center, scale, and position separately. Calling
`.absolute()` explicitly materializes the sum at reference precision. Passing
that sum through ordinary binary64 can erase its local displacement.

The four arrows are `zero_to_values`, `one_to_values`, `values_to_cycle`,
and `cycle`. Native kernels use Python's built-in complex arithmetic and do
not call mpmath during evaluation. They are intended for bounded local
positions; this stage does not implement automatic chart switching or a
global Julia renderer. Binary64 scale underflow raises an error. The
high-precision factored scale and its logarithm remain available.

Quantities named `portrait_*` use the exact cycle identities. The default
cycle map includes measured endpoint residuals. The report shows how much
the raw derivative product differs from the portrait multiplier: this can
exceed the t^24 signal even when the original t^12 portrait checks pass.
It is not an interval error bound or a classification of the free orbit.

At t=0 the four charts collapse. Only formal limits of their normalized
kernels are available; use the global polynomial g for actual dynamics.
Neither rescaling nor the stable return-drift calculation accelerates time:
the typical local drift per return is still O(t^24).

See [docs/RESCALING.md](docs/RESCALING.md) for the exact formulas, precision
interpretation, and verification strategy.

## Mathematical coordinates

The affine-normalized critical points are

\[
(c_1,c_2,c_3,c_4,c_5,c_6)
=(\omega,x,-x,1+s,1-s,1+h_0),
\]

and the polynomial is uniquely specified by

\[
f'(z)=7\lambda(z^2-x^2)((z-1)^2-s^2)(z-1-h_0)(z-\omega),
\qquad f(0)=B.
\]

At the boundary,

\[
g(z)=\lambda_g z^3(z-1)^4+B_g,\quad
\omega_g=3/7,
\]

where a is the real root in (0.306,0.307) of

\[
64(2a-1)^3(8a-3)^4-(7a-3)^7=0.
\]

The remaining constants are recomputed at the current precision:

\[
\lambda_g=-1/h'(a),\quad B_g=4a(2a-1)/(7a-3),\quad h(z)=z^3(z-1)^4.
\]

They satisfy g(B_g)=g(a)=a and g'(a)=-1. Approximately,
`a = 0.30683924435059343745`,
`lambda_g = -37.425950327538390502`, and
`B_g = 0.55643742561136352757`.

The local parameter is **t in the normalization of the cusp**. It is not a
coordinate chart making the singular curve smooth inside its ambient space,
and is not necessarily the tau used in the exact normal form
`hat_x^3 = hat_s^4`. Its construction is described in
[docs/LOCAL_FAMILY.md](docs/LOCAL_FAMILY.md).

## Numerical interpretation

- The implemented range is `|t| <= 0.2`, with radial continuation from zero.
  This is an operational limit, **not a certified neighborhood radius**.
  Convergence and residual checks are numerical, not interval proofs of
  uniqueness or of exact portrait membership.
- `numerical_ok` checks residuals against the requested tolerance, relative
  to the collapsing critical-value and cycle gaps. `portrait_resolved` also
  requires nonzero t and gaps above the working numerical noise floor.
  At t=0 the collisions are intentional and this flag is false; tiny
  computed gaps there are roundoff.
- For nonzero t, the intended constrained portrait is
  `c2,c4,c5 -> X -> Z -> W -> Z` and `c3,c6 -> Y -> W`.
- The free critical point is not subject to a periodicity equation. Finite
  iteration does not decide whether its forward orbit is infinite, and the
  program does not claim to exclude exceptional preperiodic parameters.
- Long numerical iterations of the prescribed finite orbits can drift from
  their intended cycle. The future GUI should draw the prescribed portrait
  from X,Y,Z,W and show its residuals, rather than conceal that drift.
- This version uses affine-normalized representatives. The monic-centered
  view and the cusp geometry view are planned additions.

## Verify

```bash
python -m unittest discover -s tests -v
```

The suite checks the explicit boundary map, criticality, original dynamical
relations, the divided period-two equation, independent quadrature, the
collapsing orders, conjugation symmetry, precision stability, a tiny parameter,
and the console interface. It also compares all four local maps, the scaled
multiplier and second return with direct high-precision computations, checks
residual propagation on a deliberately perturbed polynomial, and exercises
binary64 kernels and scale underflow. GitHub Actions runs it on Python 3.10,
3.12, and 3.13.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the staged graphical explorer.
