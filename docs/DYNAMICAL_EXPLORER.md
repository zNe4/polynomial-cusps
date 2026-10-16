# Dynamical explorer

Launch with `python -m polynomial_cusps --gui` after installing `.[gui]`
and the operating system's Tk package. The same application is exposed as
`polynomial-cusps-gui`. The parameter window opens alongside the dynamical window. Choose t there
or enter it numerically. See [PARAMETERS_AND_LOOPS.md](PARAMETERS_AND_LOOPS.md)
for parameter circles and marked forward loops.

## Views and overlays

The global view uses z. The other views use the four affine coordinates
from M01.1: z=x xi, z=1+s xi, z=X+d xi, and z=Z+Delta xi. The displayed
axes in a local view are xi, not absolute z. By default **Ejes locales sin girar** replaces the complex scale by its
positive magnitude, preserving the orientation of the absolute plane while
magnifying it. This makes critical-point rotation visible during a parameter
circle. Disable it to restore the complex chart scale and its phase.
The selected convention is recorded in the exported viewport's `fixed_axes`.

Critical labels c1,...,c6 are preserved. Coincident screen markers are grouped
and all their names remain in the label. At g this gives c2/c3 and c4/c5/c6.
The free critical point c1=omega and its finite forward orbit are orange;
the prescribed orbit graph is yellow. Its arrows express the prescribed
portrait and use computed X,Y,Z,W, rather than long iterations of rounded
critical points. The diagnostic panel retains the measured relation errors.

Click a point to select it, then press Space or the iteration button to
apply the current polynomial once. The selection is held at reference
precision. Its coordinates and iteration count appear in the panel. An
escaped selection is not iterated indefinitely. A parameter change clears
the selection; a zoom or view change for the same parameter preserves it.

## Escape data and color modes

The renderer samples pixel centers, iterating the computed polynomial until
escape or the finite limit. It uses the conservative escape radius from
M01. A pixel not crossing that radius is marked -1 (unresolved), never
certified as belonging to the filled Julia set.

**Julia** displays the finite-resolution boundary between escaped and
unresolved samples. **Escape** additionally colors escape times. Optional
shading marks unresolved samples. These are finite-time approximations;
increasing iterations, resolution, or precision can change the boundary.

Near the tiny collapsing cycle, many or all samples can remain unresolved
within a practical iteration limit. The return has drift O(t^24). The UI
states this explicitly instead of manufacturing a local Julia boundary.
This stage does not implement Fatou-coordinate acceleration or time skipping.

## Numerical engines

- **auto:** vectorized complex128 globally, M01.1 native local kernels in
  nonzero charts, and MP when coordinates cannot resolve individual pixels
  or a local scale underflows. Automatically selected MP renders a preview
  of at most 96 by 96 samples; the completed frame records its actual size.
- **double:** request ordinary precision explicitly. The renderer refuses
  a viewport whose pixel spacing or local scale cannot be represented.
- **mp:** iterate the original polynomial at the family point's arbitrary
  precision for every pixel. This honors the selected sampling size and
  can be much slower. Cancellation is checked during pixel iteration.

Native local iteration follows zero/one -> values -> cycle -> cycle. It uses
the raw cycle map carrying r0 and r1, never the portrait-projected map. An
absolute sum is formed only for the coarse escape test; iteration keeps the
local displacement separate. If a local coordinate grows beyond 1e6 or an
arithmetic result is nonfinite, the affected pixel restarts from its original
coordinate using MP. This guard is operational, not a rigorous error bound
for arbitrary trajectories. The diagnostic records the fallback pixel count.

Viewport spacing is also checked against the reference context's available
precision. An insufficient context raises an error suggesting more digits.
The renderer does not silently change the chosen polynomial or claim certified
orbit accuracy. In particular, ordinary precision may not resolve a tiny
multiplier defect, even when the graph of the cycle is well separated.

## Worker ownership and export

Family preparation and image calculation run in one background worker.
Every new request cancels the previous generation; only the current
generation's progress, result, or error is accepted by Tk. Workers never
call Tk. A failed or cancelled calculation preserves the last completed
frame. The UI remains interactive while computing and exporting always
uses the completed numerical scene, not text fields for a pending request.

PNG export includes the visible overlay settings, selected point, and
forward loops with their marked p, f(p), and f²(p) when enabled. The
image uses the completed render's sampling dimensions; the on-screen canvas
may scale that image for display. JSON metadata is embedded in the PNG and
also written alongside it. It includes t, normalization, viewport, render
settings, actual engine, finite-time counts, polynomial coefficients,
critical and portrait points, free orbit, and the M01/M01.1 diagnostics.

## Acceptance evidence

Tests compare native global and all local chart transitions with direct
high-precision polynomial iteration. Additional cases cover MP selection,
reference limits, restart of out-of-range local coordinates, cancellation,
obsolete worker results, grouped critical identities, palette output, and
PNG/JSON snapshot consistency.

Ten tests use a real Tk event loop: boundary/real/nonreal parameter changes
and all local presets; selection, iteration, zoom, toggles, and export;
failure/cancellation while preserving the previous frame; parameter selection
and independent loop movement, including g and export; and serial parameter
circle playback that waits for each dynamical frame; and the fast wider
parameter preview with selection priority over grid verification; loop
refinement preserving marker angle and turns; and Ctrl+Q closing only the
focused loop inspector or quitting the whole app from either main window,
including cancellation of active work; and prepared movie playback,
snapshot consistency, repeat, interaction pause, and preparation cancellation.
See [PARAMETER_MOVIES.md](PARAMETER_MOVIES.md). GitHub Actions
runs all tests under Xvfb on Python 3.10, 3.12, and 3.13. Local headless runs
skip only these ten display-dependent acceptance tests.
