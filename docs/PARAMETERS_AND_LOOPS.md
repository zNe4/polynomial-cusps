# Parameter circles and forward dynamical loops

Launch `python -m polynomial_cusps --gui` after installing `.[gui]` and Tk.
The parameter and dynamical windows open together. **Lazos** opens auxiliary
magnifications of curves in the same dynamical plane.

## Selecting the polynomial

The parameter plane is the normalization coordinate t, with g at t=0 and
implemented domain |t| <= 0.2. This is a numerical operating range, not a
certified local validity radius. Click to select a continuous parameter;
drag a rectangle or use the wheel to zoom independently of the Julia view.
The circle and selected-parameter marker stay in this parameter plane.

The image is a coarse grid of individually checked cell-center solutions,
displayed without interpolation. Each completed row appears progressively.
The solver uses an LRU cache and the previous solution as a continuation
seed, with radial fallback if seeded Newton fails. Family preparation and
image work run in cancellable workers; obsolete generations cannot replace
newer results. Selection remains usable while the grid is calculated.

The two color modes have different meanings:

| Mode | Interpretation |
| --- | --- |
| Ciclo: retrato exacto | Turquoise/violet indicates numerical attraction/repulsion of the portrait-constrained cycle. Gold indicates a small unresolved stability signal. |
| Órbita libre: escape | Orange means the free critical orbit crossed the escape bound within the dynamical window's iteration budget; gray means unresolved. |

The boundary sample g is pale yellow; failed solves are red and samples
outside the implemented domain are dark. A colored cell represents its
center, not a proof about its whole area. Cycle coloring is not a test of
the free orbit or a claim about hyperbolic components.

To avoid subtracting a tiny defect from one, cycle coloring evaluates the
sign of

\[
\frac{|1+\Delta^2 M|^2-1}{|\Delta|^2}
=2\operatorname{Re}\!\left((\Delta/|\Delta|)^2M\right)
 + |\Delta|^2|M|^2,
\qquad M=(\mu-1)/\Delta^2.
\]

Here M is the stable **portrait-constrained** defect. Raw-polynomial
residuals remain visible in the dynamical diagnostics. Near-neutral colors
are numerical tolerances, not exact neutral loci.

## Moving around g in parameter space

Enter r and a frame count (64–720), then press **Preparar vuelta**. The
program solves t=r exp(i theta) by continuation and independently solves
the last arc back to the initial t. It checks closure of the marked family
before accepting the circle. **Reproducir / pausa**, **Paso**, and the angle
slider select these polynomials; playback waits for each completed
dynamical frame. Manual selection or a new rendering request pauses it.
**Datos de vuelta** exports the path and measured windings as JSON.

For sufficiently small circles, the measured windings are

| Quantity | Turns per turn of t |
| --- | ---: |
| x | 4 |
| s | 3 |
| Y-X | 12 |
| W-Z | 12 |

These express x=t^4 u(t), s=t^3 and the order-t^12 orbit gaps, with nonzero
leading factors. Counts use accumulated principal increments; a detected
large angular increment rejects an undersampled path. This sampling check
is not a certified winding calculation.

Use **Críticos en 0** or **Críticos en 1** and leave **Ejes locales sin
girar** enabled. The coordinates are then z=|x| xi and z=1+|s| xi, so the
critical points rotate visibly instead of being fixed by a rotating chart.
The group near 1 also contains 1+h0. The collapsing scale still changes
with t; these views preserve orientation, not absolute magnification.

## Moving p around a dynamical loop

This operation keeps the current f fixed. Press **Lazos** to draw circles
around both critical groups and their actual forward images. Blue denotes
the group near 0; green denotes the group near 1. The source markers p0,p1
are ordinary points on these circles, distinct from the critical markers.
Both p and f(p) are drawn over the main Julia view. The inspector's four
panels are translated, positively rescaled magnifications of these same
dynamical curves, with source panels on the left and image panels on the
right. They are not another parameter space.

Use **Mover p / pausa**, the loop angle slider, or click/drag on a source
circle in the main dynamical window. Moving p updates f(p) without solving
another parameter or recalculating the Julia image. **Ambos grupos** or
the group selector controls the main overlays. The two source markers use
the same angle. **Dibujar en el Julia** controls their main-plane visibility.

For nonzero t the source circles are

\[
p_0(\phi)=R|x|e^{i\phi},\qquad
p_1(\phi)=1+R|s|e^{i\phi},\qquad R=2.5\text{ by default}.
\]

The image paths are evaluated using the divided local polynomial maps,
retaining their measured residuals. Centering at X+(Y-X)/2 and using the
positive scale |Y-X| keeps very small image loops distinguishable even at
t=10^-8. Displaying the whole polynomial globally can make these loops
too small to resolve, so use the magnifications or local views.

At g the source radius is the absolute value **Radio en g**, default 0.03.
The code evaluates the exact factored expressions

\[
g(\epsilon\xi)-B_g
=\lambda_g\epsilon^3\xi^3(\epsilon\xi-1)^4,
\qquad
g(1+\epsilon\xi)-B_g
=\lambda_g\epsilon^4(1+\epsilon\xi)^3\xi^4,
\]

without subtracting nearly equal values. Positive magnifications
|lambda_g| epsilon^3 and |lambda_g| epsilon^4 resolve the image curves.

For the default small whole-cluster loops, one positive source turn gives
image winding **3 near 0 and 4 near 1**, measured about X (about B_g at g).
At g these are the local degrees. At a nearby f they count zeros of f(z)-X
inside the source loop, with multiplicity. They are not a general rule
that every loop enclosing k critical points must have image winding k+1
about any center. In particular, a sufficiently small loop around one
simple critical point has local degree 2 about its own critical value.
Changing the radius can change the count; a loop through the winding
center is rejected when detected numerically.

The parameter-circle and source-marker clocks are independent and can run
together. On a change of f, the loop geometry follows the new polynomial
and the marker angle is preserved. PNG/JSON export saves the completed
dynamical scene, source/image tracks, scales, marked index, and windings.

## Verification and limits

Tests compare seeded and independent radial family solutions, independently
verify parameter-circle closure, check the 4/3/12/12 windings, and compare
cycle coloring against a direct higher-precision multiplier. Forward-loop
samples are checked against the original polynomial at g and a nonreal t;
tiny-t tests verify that the divided images remain resolved. Native and MP
renderers agree for fixed-orientation axes. Real Tk acceptance covers
selection, independent marker movement, g, export, and serial playback.

Spatial rescaling resolves tiny separations; it does not accelerate the
O(t^24) return drift. Julia/escape images remain finite-time approximations,
and the parameter image and winding calculations are numerical observations.
