# Fast preview and a wider parameter disk

The explorer now covers |t| <= 0.5, compared with the original 0.2 limit.
This is an operational numerical domain, not a theorem that t gives a
single global coordinate on the entire portrait locus. The affine
normalization and marked family are unchanged. Outside the original disk,
reference continuation uses segments of length at most 0.025 and still
checks the final undivided portrait residuals.

The outer circle was checked against independent radial continuations.
At radius 0.5, sampled cycle multiplier defects have magnitudes around
10^-3, so attraction/repulsion can become much more visible than the
roughly 10^-20 defects at radius 0.1. The Julia renderer still has a finite
iteration budget. This change does not implement time acceleration.

## Two parameter-image modes

The initial **Rápido: Taylor** view evaluates a bundled degree-128 polynomial
table on a 129×129 grid. It approximates the stability of the
portrait-constrained cycle. It contains no checked family solutions.
Comparing degrees 96 and 128 supplies an empirical truncation indicator;
the calculation also includes a numerical roundoff allowance. Cells whose
stability signal is smaller than this indicator remain gray/unresolved.
These estimates are not certified interval bounds.

**Verificado: Newton** computes each cell center as a checked family
solution, starting with 9×9 samples. The free-critical escape mode always
uses checked family parameters. In either mode, choosing t constructs and
verifies the polynomial at the selected continuous coordinate. The rendered
dynamics and loop exports never use an uncorrected Taylor family point.

**Ampliado** displays a square of width 1.1 containing the radius-0.5 disk;
**Cerca de g** returns to width 0.28. Wheel and rectangle zoom are independent
of the dynamical viewport. The parameter readout shows the pointer coordinate
and current width. Points outside the operating disk remain unavailable.

Grid verification pauses when a dynamical render is requested, avoiding
competition between CPU-heavy family calculations and selection. The status
shows the requested parameter while the previous completed frame is retained.
Cancellation is checked between Newton solves; an individual solve finishes
before its worker stops. Closing a window joins its cancelled worker before
destroying the corresponding Tk objects.

## What the table contains

For a reference radius R=0.5, the file stores coefficients of (t/R)^n for

\[
u(t),\quad \omega(t),\quad \lambda(t),\quad B(t),\quad
D(t),\quad C(t),\quad M(t),
\]

where

\[
x=t^4u(t),\quad s=t^3,\quad Y-X=t^{12}D(t),\quad
\Delta=W-Z=t^{12}C(t),\quad \mu-1=\Delta^2M(t).
\]

The regular factors D,C,M are approximated directly. The preview never
recovers the small gaps or multiplier defect by subtracting nearby large
numbers. It uses the unit phase (t/|t|)^12 C/|C| and the scaled stability
signal described in [PARAMETERS_AND_LOOPS.md](PARAMETERS_AND_LOOPS.md).
This preserves angular sectors even when |t|^24 underflows binary64.

The offline builder follows 256 checked points around the radius-0.5
circle, requests 70 decimal digits, verifies independent closure, and
computes discrete Cauchy coefficients through degree 128. Finite sampling
introduces aliasing, so these are numerical coefficient approximations.
The JSON file is bundled in the Python package; opening the app does not
rebuild it. To reproduce it from the repository root:

```bash
python -m tools.generate_taylor
```

`solve_explorer_family` evaluates the family-variable series at reference
precision and uses that point as a Newton predictor. It accepts the result
only after the ordinary portrait checks and a small-correction check.
Failure or a large correction falls back to the reference radial solver.
The public `solve_family` and console inspector remain independent of the
table, providing a separate comparison path.

## Numerical evidence

Independent radial comparisons included real and nonreal parameters near g
and close to the outer boundary. The largest observed relative table error
among u,omega,lambda,B,D,C,M at t=0.5 was approximately 1.4×10^-14. Newton
correction restored agreement with the independent 50-digit reference well
below 10^-45. These are sampled checks, not uniform error guarantees.

On the development machine, a 129×129 cycle preview took about 0.04 s.
Selected-family preparation with Taylor and Newton took about 0.05–0.07 s,
compared with roughly 0.8–1.2 s for the tested outer radial continuations.
These measurements exclude the subsequent Julia rendering and will vary
by machine. Higher resolution, MP rendering, and long iteration budgets
can still be expensive.
The loop inspector also adapts its sampling in the wider disk: second
images may have larger winding counts than the local 3/4 pattern, so it
checks successive resolutions and preserves the source marker's angle.

Tests cover independent reference comparisons, preview colors across the
wider disk, outer-circle closure and branch comparisons, tiny-parameter
phase preservation, domain rejection, cancellation, GUI selection priority,
and distribution of the table in the installed package.
