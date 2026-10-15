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
