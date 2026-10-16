"""Forward loops around critical clusters, distinct from parameter motion."""

from dataclasses import dataclass

from .parameters import winding
from .rendering import _check
from .family import _horner
from .rescaling import _shift


@dataclass(frozen=True)
class ForwardLoops:
    t: object
    zero_source: tuple
    one_source: tuple
    zero_image: tuple
    one_image: tuple
    zero_criticals: tuple
    one_criticals: tuple
    targets: tuple
    winding_zero: object
    winding_one: object
    physical_radii: tuple
    multiplier: str
    boundary_radius: str
    source_scales: tuple
    image_center: object
    image_scales: tuple
    zero_second_image: tuple
    one_second_image: tuple
    second_center: object
    second_scales: tuple
    second_targets: tuple
    second_winding_zero: object
    second_winding_one: object


def forward_loops(scene, *, multiplier="2.5", boundary_radius="0.03", samples=192, cancel=None):
    """One turn of each source loop and its first two polynomial images.

    Source axes never rotate with x or s. Images share a translated center
    and a positive real scale. No portrait projection is used.
    """
    p, ref, c = scene.point, scene.reference, scene.point.ctx
    factor, epsilon = c.mpf(multiplier), c.mpf(boundary_radius)
    if not c.isfinite(factor) or not 0 < factor <= 20 or not c.isfinite(epsilon) or not 0 < epsilon < c.mpf("0.2"):
        raise ValueError("Use 0 < loop multiplier <= 20 and 0 < boundary radius < 0.2")
    if not isinstance(samples, int) or not 64 <= samples <= 2048:
        raise ValueError("Use 64 to 2048 loop samples")
    zero, one, image0, image1, second0, second1 = [], [], [], [], [], []
    if p.t:
        a, b = abs(p.x), abs(p.s)
        # f(z)-X is evaluated in the already divided local maps.
        target_scale = abs(ref.value_scale.value)
        phase = ref.value_scale.value/target_scale
        def map_zero(xi):
            return phase*(ref.kernels.zero_to_values(xi*a/p.x)-c.mpf("0.5"))
        def map_one(xi):
            return phase*(ref.kernels.one_to_values(xi*b/p.s)-c.mpf("0.5"))
        targets = (-phase/2, phase/2)
        image_center = p.f(p.x)+ref.value_scale.value/2
        image_scales = (target_scale, target_scale)
        cycle_scale = abs(ref.cycle_scale.value)
        cycle_phase = ref.cycle_scale.value/cycle_scale
        second_center = ref.charts["cycle"].center+ref.cycle_scale.value/2
        second_scales = (cycle_scale, cycle_scale)
        second_targets = (-cycle_phase/2, cycle_phase/2)
        def second_map(value, group):
            # Undo only the display translation/positive scaling, then use
            # the divided map. Never form the tiny absolute displacement.
            return cycle_phase*(ref.kernels.values_to_cycle(value/phase+c.mpf("0.5"))-c.mpf("0.5"))
        critical0 = (p.x/a, -p.x/a)
        critical1 = (p.s/b, -p.s/b, p.h0/b)
        radial = factor
    else:
        # At g, evaluate (g(center+epsilon*xi)-B) without subtracting B.
        a = b = epsilon
        radial = c.mpf(1)
        scale0, scale1 = abs(p.lam)*epsilon**3, abs(p.lam)*epsilon**4
        def map_zero(xi):
            return p.lam/abs(p.lam)*xi**3*(epsilon*xi-1)**4
        def map_one(xi):
            return p.lam/abs(p.lam)*(1+epsilon*xi)**3*xi**4
        targets = (c.mpc(0), c.mpc(0))
        critical0, critical1 = (c.mpc(0),)*2, (c.mpc(0),)*3
        image_center, image_scales = p.B, (scale0, scale1)
        second_center = p.f(p.B)
        second_scales = tuple(abs(p.derivative(p.B))*v for v in image_scales)
        second_targets = (c.mpc(0), c.mpc(0))
        shifted = _shift(p.coefficients, p.B)[1:]
        def second_map(value, group):
            displacement = image_scales[group]*value
            return displacement*_horner(shifted, displacement)/second_scales[group]
    for k in range(samples):
        _check(cancel)
        xi = radial*c.exp(2j*c.pi*k/samples)
        zero.append(xi)
        one.append(xi)
        image0.append(map_zero(xi))
        image1.append(map_one(xi))
        second0.append(second_map(image0[-1], 0))
        second1.append(second_map(image1[-1], 1))
    for track in (zero, one, image0, image1, second0, second1):
        track.append(track[0])
    # Count around X for nonzero t, around the common value B at g.
    if min(abs(v-targets[0]) for v in image0+image1) < c.power(10, -p.requested_dps//2):
        raise ValueError("The image loop meets its winding center; choose another radius")
    counts0 = winding(c, [v-targets[0] for v in image0])
    counts1 = winding(c, [v-targets[0] for v in image1])
    counts2 = winding(c, [v-second_targets[0] for v in second0])
    counts3 = winding(c, [v-second_targets[0] for v in second1])
    return ForwardLoops(p.t, tuple(zero), tuple(one), tuple(image0), tuple(image1),
                        critical0, critical1, targets, counts0, counts1,
                        (a*radial, b*radial), str(multiplier), str(boundary_radius),
                        (a, b), image_center, image_scales,
                        tuple(second0), tuple(second1), second_center, second_scales,
                        second_targets, counts2, counts3)
