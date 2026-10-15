# M01.1: factored scales and local dynamics

This stage separates a small displacement from its O(1) center. It implements
exact algebraic rearrangements and measured polynomial residuals. It does not
add a renderer, automate chart transitions, or accelerate long iterations.

## Scales and charts

Let d=t^12 D, with D=u^3 U. Compute X=f(x) and the shifted coefficients
beta_k=f^(k)(X)/k!. Then

\[
L=\sum_{k=1}^7\beta_k d^{k-1},\qquad
Z=f(X),\qquad \Delta=dL=t^{12}C,\quad C=DL.
\]

Thus Delta=f(X+d)-f(X), without subtracting nearby values or even forming
X+d. On the exact portrait, Y=X+d and W=Z+Delta. The implemented charts are:

| Name | Absolute coordinate | Scale order |
|---|---|---|
| zero | x xi = t^4 u xi | 4 |
| one | 1+s xi = 1+t^3 xi | 3 |
| values | X+d xi | 12 |
| cycle | Z+Delta xi | 12 |

`FactoredScale` retains (t,order,unit) and exposes its arbitrary-precision
value, log10 magnitude, and complex phase. The logarithm is computed as
order*log10(abs(t))+log10(abs(unit)). The phase of a zero scale is undefined
and reported as null. `ChartPoint` retains the affine sum until `.absolute()`
is explicitly called. Conversion of an absolute coordinate back into a
local coordinate may already have lost relative digits.

## Critical-cluster and critical-value maps

The zero-cluster map is the primitive, anchored at xi=1, of

\[
\frac{7\lambda}{U}(\xi^2-1)((x\xi-1)^2-s^2)
(x\xi-1-h_0)(x\xi-\omega).
\]

Its images of +1 and -1 are 0 and 1. For the one-cluster map, use the
primitive, also anchored at xi=1, of

\[
\frac{7\lambda}{D}((1+s\xi)^2-x^2)(\xi^2-1)
(\xi-sH)(1+s\xi-\omega).
\]

Add the measured offset (f(1+s)-X)/d. The factor is 1/D, not 1/V: this
preserves the map of the computed polynomial even if the cusp residual is
nonzero. The offset is computed by integrating f' rather than subtracting
two critical values. Primitives are shifted to their anchor once, so each
evaluation is a short Horner calculation multiplied by xi-anchor.

The critical-value map is

\[
\frac{f(X+d\xi)-Z}{\Delta}
=\frac1L\sum_{k=1}^7\beta_k d^{k-1}\xi^k.
\]

These three maps retain the measured polynomial, including its portrait
errors. They need no high-precision subtraction for each evaluation.

## Cycle map and explicit residuals

Let b_k=f^(k)(Z)/k! and define the portrait-constrained map

\[
H(\xi)=1-\xi+\sum_{k=2}^7 b_k\Delta^{k-1}(\xi^k-\xi).
\]

It satisfies H(0)=1 and H(1)=0 algebraically. The actual polynomial in the
same chart is

\[
H_{\rm raw}(\xi)=H(\xi)+r_0(1-\xi)+r_1\xi,
\]

where

\[
r_0=\frac{f(Z)-Z-\Delta}{\Delta},\qquad
e=1+f'(Z)+\sum_{k=2}^7b_k\Delta^{k-1},\qquad r_1=r_0+e.
\]

These residuals are prepared at reference precision. The callable `cycle`
kernel carries them; `cycle.portrait_map` explicitly omits them. On
|xi|<=R the difference is bounded by |r_0|+R|r_1-r_0|. This is an algebraic
bound for the measured residual polynomial, not an interval bound for
reference uncertainty or accumulated floating-point errors.

## Stable multiplier defect

For the portrait map define

\[
P=\sum_{k=2}^7b_k\Delta^{k-2},\quad
R=\sum_{k=2}^7(k-1)b_k\Delta^{k-2},\quad
J=\sum_{k=3}^7(k-2)b_k\Delta^{k-3}.
\]

Its endpoint derivatives are -1-Delta P and -1+Delta R, hence

\[
M=\frac{\mu-1}{\Delta^2}=-J-PR.
\]

There is no subtraction from one. Store mu-1 as t^24 C^2 M. Even if Delta^2
underflows binary64, M and the factored logarithmic size remain meaningful.
The raw derivative-product correction is

\[
f'(Z)f'(Z+\Delta)-\mu=e(-2+\Delta^2J)+e^2.
\]

The raw endpoints need not be an exact cycle, so their derivative product
is not claimed to be the multiplier of an independently located cycle.
The report includes this correction and its size relative to the portrait
defect. A large ratio shows why passing M01's spatial portrait checks does
not suffice to resolve the much smaller temporal signal in the raw data.
No attraction/repulsion classifier is implemented here.

## Stable second-return drift

Write H(xi)=1-xi+Delta A(xi), where

\[
A(\xi)=\sum_{k=2}^7b_k\Delta^{k-2}(\xi^k-\xi).
\]

Then an exact rearrangement gives

\[
\frac{H^2(\xi)-\xi}{\Delta^2}
=\sum_{k=3}^7b_k\Delta^{k-3}
\big((1-\xi)^k-\xi^k+2\xi-1\big)
+A(\xi)\,A[1-\xi,1-\xi+\Delta A(\xi)].
\]

The last divided difference is evaluated using shifted polynomial
coefficients and the separate displacement Delta A(xi). Neither a nearly
equal subtraction nor division by Delta^2 is performed. As t tends to zero,

\[
M\longrightarrow -(b_2^2+b_3)=A_g/2,\qquad
\frac{H^2(\xi)-\xi}{\Delta^2}
\longrightarrow \frac{A_g}{2}\xi(\xi-1)(2\xi-1).
\]

Here A_g is the cubic coefficient in g^2(a+z)=a+z+A_g z^3+O(z^4),
approximately -37.70569499595946. The spatial scale is t^12 and the
generic return displacement is t^24. Computing its coefficient accurately
does not by itself skip the enormous number of small dynamical steps.

## Boundary, precision, and verification

At t=0 all four affine charts collapse. Their normalized polynomial kernels
have formal limits; H becomes 1-xi, while the divided return retains its
nonzero cubic limit. These limits are not a conjugacy for g and cannot be
used in place of its Julia dynamics. Absolute chart operations and binary64
chart preparation reject t=0.

`RescaledFamily` uses the point's existing context and never silently raises
its precision. `binary64()` converts prepared data once; evaluations then
use only built-in complex arithmetic. Conversion rejects nonfinite values
and a nonzero cycle scale that underflows. Small higher-order coefficients
or corrections can still round away, and very large local positions can
overflow. These kernels do not promise accuracy for arbitrary orbit lengths
or global positions. High-precision preprocessing and fallback remain needed.

Tests compare all four maps with direct evaluations of the original
polynomial, including real, nonreal, and t=1e-8 samples. The tiny reference
uses 316 working digits so direct subtraction can independently resolve
the Delta^2-scale multiplier and return. A deliberately perturbed B checks
that residuals are carried rather than silently projected away. Further
tests cover native-complex evaluation, phase, logarithmic scales,
underflow, and formal boundary limits.
