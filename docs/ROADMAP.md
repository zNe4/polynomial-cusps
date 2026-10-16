# Explorer roadmap

## M01 — local family (implemented)

- Arbitrary-precision boundary construction from its defining real root.
- Lifted parameter t with s=t^3 and x=t^4 u(t).
- Stable divided equations and radial Newton continuation.
- Marked critical points, portrait points, free orbit, and JSON inspector.
- Independent algebraic/dynamical tests and precision comparisons.

Acceptance: recover g, solve real and complex samples, resolve nonzero
critical/cycle gaps, and compare low/high precision solutions. This is a
numerical implementation of the local construction, not a proof of a uniform
validity radius.

## M01.1 — rescaled coordinates (implemented)

- Four affine charts with separate centers and factored complex scales.
- Stable local maps for both critical clusters, the critical values, and the cycle.
- Explicit raw-polynomial residuals; portrait-constrained quantities are named separately.
- Stable (mu-1)/Delta^2 and (H^2(xi)-xi)/Delta^2 without subtracting nearly equal values.
- High-precision preprocessing with optional native-complex evaluation kernels.
- Logarithmic scale magnitudes and phases; explicit boundary and underflow handling.

Acceptance: compare each local map with the original polynomial at high
precision, including a nonreal parameter and t=1e-8; compare scaled return
and multiplier data with sufficiently precise independent subtraction;
verify that deliberate portrait errors remain visible. See
[RESCALING.md](RESCALING.md).

## M02 — dynamical window (implemented)

- Render an approximation of J(f_t) and optionally shade the filled Julia set.
- Use a valid escape bound for the general degree-seven polynomial; a fixed
  radius copied from the unicritical renderer is insufficient.
- Display all critical labels, X,Y,Z,W, and N free-critical iterates.
- Preserve labels at collisions and provide zoom presets for the clusters
  near 0 and 1 and the cycle near a.
- Add selected-point iteration, orbit visibility controls, and image export.
- Keep parameter construction at high precision. Use accelerated ordinary
  precision rendering where adequate, with an explicit high-precision path
  when the chosen zoom or iteration behavior requires it.
- Build on M01.1 references and kernels. Carry residual diagnostics into
  the UI; do not silently replace a computed polynomial by the constrained
  portrait map. Local O(t^24) slowness needs a separate iteration budget and
  future controlled acceleration, not only a spatial zoom.

Acceptance: g and at least one nonzero complex sample display consistently;
finite iteration is not presented as a proof of Julia or basin membership.
Keep the dynamical viewport fixed when switching parameters.

Implemented with NumPy/Pillow rendering and a cancellable Tk event loop.
The four local maps carry measured polynomial residuals. Guarded native
evaluation restarts problematic pixels in the original polynomial at
reference precision; deep zooms and scale underflow can use MP directly.
The finite-time unresolved state remains explicit. PNG exports include the
numerical snapshot and metadata. See [DYNAMICAL_EXPLORER.md](DYNAMICAL_EXPLORER.md).

## M03 — parameter selection and forward loops (implemented)

- Independent parameter window in the normalization t, with g at zero.
- Click selection, independent zoom, progressive checked cell-center samples,
  continuation cache, cancellation, and explicit failure/unresolved states.
- Two color modes: stable scaled multiplier of the portrait-constrained cycle,
  or finite-time escape of the free critical orbit. Neither is a certificate.
- Closed parameter-circle continuation, independent closing-arc verification,
  measured windings, serial playback, stepping, angle selection, and JSON export.
- Fixed-orientation local charts so critical rotations remain visible.
- Dynamical source loops and actual first/second polynomial images, marked
  regular p, f(p), f²(p), animation/dragging, whole-cluster winding counts,
  and support at g. Second images use stable divided maps near the 2-cycle.
- Loop magnifications and main dynamical overlays follow f while preserving
  the independent marker phase. PNG/JSON exports include the loop snapshot.

Acceptance: compare parameter windings with the collapsing exponents; compare
forward-loop images with independent high-precision polynomial evaluation at g,
a complex sample, and tiny t. Real Tk tests cover selection, independent marker
movement, export, and parameter playback without obsolete frames. See
[PARAMETERS_AND_LOOPS.md](PARAMETERS_AND_LOOPS.md).

## M04 — geometric and normalization views

- Add a monic-centered dynamical view via the affine conjugacy in the proof,
  with an explicitly fixed local sixth-root branch.
- Show selected real slices or projections of the cusp; the complex curve
  lives in real dimension four in its two collision coordinates.
- Explain that the t-plane displays the normalization and does not exhibit
  the ambient cusp as a planar tip.
- Add other parameter paths, including approach-to-g paths, and richer exports.

## Remaining numerical work

- Controlled time acceleration near the parabolic cycle is not implemented.
  Spatial rescaling resolves collapsing gaps but the O(t^24) drift remains.
- Parameter coloring is coarse numerical sampling, not a certified image of
  the locus or a classification of the free critical orbit.
- The original two-window selection and both independent loop motions are
  implemented, including the second forward image. M04 extends the geometry
  rather than being required to use those features.
