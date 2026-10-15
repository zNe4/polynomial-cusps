# The local family and its numerical equations

This implementation follows the parabolic cusp construction in the supplied
manuscript `7(6).tex`, subsection “An example of a cusp”. It implements that
specific affine-normalized family, not a general solver for portrait loci.

## Eliminate the first divided relation

The condition f(1+s)=f(1-s), divided by s^3, gives E=0. It is solved explicitly:

\[
h_0=s^2 H(x,s,\omega),\qquad
H=\frac{(3-2\omega-x^2)/5+3s^2/35}
{(1-x^2)(1-\omega)+(3-\omega)s^2/5}.
\]

At the boundary H=3/4. This eliminates h_0, leaving four auxiliary unknowns
once the cusp has been desingularized.

## Remove the singular factor

Define the extended critical-value differences

\[
f(-x)-f(x)=x^3 U,\qquad
f(1+h_0)-f(1+s)=s^4 V.
\]

Instead of subtracting almost equal critical values and dividing, compute
U and V as exact integrals of degree-six polynomials:

\[
U=7\lambda\int_1^{-1}(v^2-1)((xv-1)^2-s^2)
(xv-1-h_0)(xv-\omega)\,dv,
\]

\[
V=7\lambda\int_1^{sH}((1+sv)^2-x^2)(v^2-1)
(v-sH)(1+sv-\omega)\,dv.
\]

These expressions extend to x=s=0, where U=4 lambda_g and V=lambda_g.
All integrations in the solver are polynomial operations, with no numerical
quadrature tolerance.

Set s=t^3 and x=t^4 u. The original relation x^3 U=s^4 V becomes, away
from zero, t^12(u^3 U-V)=0. Retain the extended equation

\[
u^3U-V=0.
\]

At zero it gives 4u^3=1. We choose the positive real root
u_0=4^(-1/3). The derivative with respect to u is 3u_0^2 U_0 != 0.
Together with the auxiliary Jacobian established in the manuscript, this
defines a holomorphic lifted family near zero. The other cube-root choices
are alternative parametrizations of the same irreducible germ.

## Solve four equations

With X=f(x), Y=f(1+h_0), Z=f(X), and W=f(Y), solve for
(u,omega,lambda,B) at each t using:

\[
S/\lambda=0,\quad T=0,\quad Q=0,\quad u^3U-V=0,
\]

where S=f(x)-f(1+s), T=f(Z)-W, and

\[
Q=Q_f(Z),\qquad Q_f(z)=\frac{f^2(z)-z}{f(z)-z}.
\]

S is computed by integrating f' between its two endpoints. Q is computed
without a quotient of small quantities, using

\[
Q_f(z)=1+\frac{f(f(z))-f(z)}{f(z)-z}
=1+\sum_{k=1}^7 a_k\sum_{j=0}^{k-1}f(z)^{k-1-j}z^j.
\]

This polynomial expression remains valid at f(z)=z and equals 1+f'(z)
there. In particular it retains the multiplier condition at g.

The initial solution is (u_0,3/7,lambda_g,B_g). The solver uses mpmath's
multidimensional Newton solver along the straight segment from zero to t,
with eight steps by default. A failed solve raises an error. There is no
fallback to a polynomial violating the divided equations.

## Precision and diagnostics

The separations have orders x=O(t^4), s=t^3, h_0=O(t^6), and
Y-X=O(t^12). Since g'(B_g) != 0, Z-W also has order t^12.
The context uses

```
working_dps = requested_dps + 30 + max(0, ceil(-12 log10(|t|)))
```

with no gap term when t=0. This is a precision budget, not a numerical
condition-number bound. The final diagnostics independently evaluate the
undivided critical-value and cycle relations, the divided E and Q equations,
and the extended cusp equation. They also check the two separation identities.

`numerical_ok` requires the maximum absolute residual to be less than
`10^(-requested_dps) * min(1, |Y-X|, |Z-W|)` for nonzero t; at zero the
scale is one. `portrait_resolved` additionally checks all pairwise critical
gaps and both orbit gaps against a working noise floor. These are numerical
consistency checks, not certified interval enclosures.

The code intentionally leaves the free orbit unconstrained. It does not turn
generic infiniteness in the mathematical proof into a claim about an
individually selected numerical parameter.
