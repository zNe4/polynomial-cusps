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

## M02 — dynamical window

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

## M03 — parameter window

- Show a neighborhood in the normalization parameter t, centered at g.
- Click to update the dynamical window; zoom independently in both windows.
- Color by free-critical escape or numerically detected attracting behavior.
  Distinguish escape, detected attraction, and unresolved finite-time behavior.
- Cache/continue family solutions across the image and add progressive
  rendering and cancellation. Solving every pixel independently with the M01
  reference solver is not an interactive rendering strategy.
- Animate parameter paths and the approach to g.

Acceptance: stale renders cannot overwrite a later selection, and every pixel
used in a parameter image is associated with a successfully checked family
solution. Failed/unresolved samples remain visible as such.

## M04 — geometric and normalization views

- Add a monic-centered dynamical view via the affine conjugacy in the proof,
  with an explicitly fixed local sixth-root branch.
- Show selected real slices or projections of the cusp; the complex curve
  lives in real dimension four in its two collision coordinates.
- Explain that the t-plane displays the normalization and does not exhibit
  the ambient cusp as a planar tip.
- Export parameter paths and numerical metadata alongside images.
