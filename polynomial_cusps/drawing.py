"""Shared screen/export overlays and numerical metadata, independent of Tk."""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

from .rendering import colorize


@dataclass(frozen=True)
class OverlayOptions:
    criticals: bool = True
    portrait: bool = True
    free: bool = True
    labels: bool = True
    shade: bool = True


def _font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def pixel(scene, view, absolute, size):
    ctx = scene.point.ctx
    z = scene.local(absolute, view.kind)
    center, span = ctx.mpc(view.real, view.imag), ctx.mpf(view.span)
    v = (z-center)/span
    if abs(v.real) > 2 or abs(v.imag) > 2:
        return None
    return (size*(0.5+float(v.real)), size*(0.5-float(v.imag)))


def _arrow(draw, start, end, color):
    if start is None or end is None:
        return
    dx, dy = end[0]-start[0], end[1]-start[1]
    length = math.hypot(dx, dy)
    if length < 12:
        return
    ux, uy = dx/length, dy/length
    a = (start[0]+6*ux, start[1]+6*uy)
    b = (end[0]-7*ux, end[1]-7*uy)
    draw.line((a, b), fill=color, width=1)
    draw.polygon([b, (b[0]-7*ux+3*uy, b[1]-7*uy-3*ux),
                  (b[0]-7*ux-3*uy, b[1]-7*uy+3*ux)], fill=color)


def compose(scene, result, options=OverlayOptions(), mode="Escape", selected=None, size=None):
    size = size or result.settings.size
    image = Image.fromarray(colorize(result, mode, options.shade))
    if image.width != size:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    font = _font(12)
    nodes = scene.nodes()
    positions = {name: pixel(scene, result.viewport, z, size) for name, z in nodes.items()}
    if options.portrait:
        edges = [("c2", "X"), ("c4", "X"), ("c5", "X"),
                 ("c3", "Y"), ("c6", "Y"), ("X", "Z"),
                 ("Y", "W"), ("Z", "W"), ("W", "Z")]
        for a, b in edges:
            _arrow(draw, positions[a], positions[b], (228, 216, 155, 185))
    if options.free:
        previous = None
        free_labels = []
        for index, z in enumerate(scene.free_orbit):
            pos = pixel(scene, result.viewport, z, size)
            if pos is not None:
                x, y = pos
                if previous is not None:
                    draw.line((previous, pos), fill=(255, 148, 85, 135), width=1)
                draw.ellipse((x-2, y-2, x+2, y+2), fill=(255, 163, 99, 240))
                near_label = any(math.hypot(x-a, y-b) < 20 for a, b in free_labels)
                near_node = any(q is not None and math.hypot(x-q[0], y-q[1]) < 18
                                for q in positions.values())
                if options.labels and not near_label and not near_node and index in (1, 2, 5, 10, 20, len(scene.free_orbit)-1):
                    draw.text((x+4, y+3), str(index), font=font, fill=(255, 178, 123, 255))
                    free_labels.append(pos)
            previous = pos
    # Group coincident screen markers, preserving every critical label at g.
    groups = []
    for name, pos in positions.items():
        if pos is None or not (-10 < pos[0] < size+10 and -10 < pos[1] < size+10):
            continue
        if name.startswith("c") and not options.criticals:
            continue
        if not name.startswith("c") and not options.portrait:
            continue
        for group in groups:
            if math.hypot(pos[0]-group[0][0], pos[1]-group[0][1]) < 9:
                group[1].append(name)
                break
        else:
            groups.append((pos, [name]))
    for (x, y), names in groups:
        if "c1" in names:
            color = (255, 157, 91, 255)
        elif any(name in ("c2", "c3") for name in names):
            color = (99, 188, 255, 255)
        elif any(name in ("c4", "c5", "c6") for name in names):
            color = (100, 225, 170, 255)
        else:
            color = (255, 221, 130, 255)
        draw.ellipse((x-4, y-4, x+4, y+4), fill=color, outline=(7, 17, 28, 255), width=1)
        if options.labels:
            label = "/".join(names)
            box = draw.textbbox((0, 0), label, font=font)
            tx = min(size-(box[2]-box[0])-5, max(4, x+7))
            ty = min(size-20, max(36, y-18))
            draw.rectangle((tx-2, ty-1, tx+box[2]-box[0]+2, ty+15), fill=(9, 18, 29, 205))
            draw.text((tx, ty), label, font=font, fill=color)
    if selected is not None:
        z, iteration = selected
        pos = pixel(scene, result.viewport, z, size)
        if pos:
            x, y = pos
            draw.line((x-8, y, x+8, y), fill=(255, 127, 218, 255), width=2)
            draw.line((x, y-8, x, y+8), fill=(255, 127, 218, 255), width=2)
            draw.text((x+9, y+6), f"z{iteration}", font=font, fill=(255, 160, 230, 255))
    title = "g · parámetro límite" if not scene.point.t else "f(t) · dinámica"
    draw.rectangle((0, 0, size, 32), fill=(9, 18, 29, 230))
    draw.text((10, 7), f"{title}  |  {result.viewport.kind}", font=font, fill=(221, 236, 244, 255))
    return image


def _encode(ctx, value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {k: _encode(ctx, v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_encode(ctx, v) for v in value]
    if value.imag:
        return {"real": ctx.nstr(value.real, ctx.dps-15), "imag": ctx.nstr(value.imag, ctx.dps-15)}
    return ctx.nstr(value.real, ctx.dps-15)


def metadata(scene, result, options, mode, selected):
    return _encode(scene.point.ctx, {
        "format": "polynomial-cusps-dynamical-view-v1", "t": scene.point.t,
        "normalization": "affine: critical midpoints 0 and 1",
        "viewport": asdict(result.viewport), "render": asdict(result.settings),
        "actual_engine": result.engine, "mp_fallback_pixels": result.fallback_pixels,
        "escaped_pixels": result.escaped_count,
        "unresolved_pixels": result.settings.size**2-result.escaped_count,
        "seconds": result.seconds, "overlays": asdict(options), "color_mode": mode,
        "selected_point": selected,
        "coefficients_ascending": scene.point.coefficients,
        "critical_points": scene.point.critical_points, "portrait_points": scene.point.portrait_points,
        "free_orbit": scene.free_orbit, "diagnostics": scene.point.diagnostics(),
        "rescaling": scene.reference.report(),
        "interpretation": "Finite-time escape approximation. Unescaped pixels are unresolved, "
                          "not certified members of the filled Julia set. Raw maps retain measured residuals.",
    })


def save_export(path, scene, result, options=OverlayOptions(), mode="Escape", selected=None):
    path = Path(path)
    if path.suffix.lower() != ".png":
        path = path.with_suffix(".png")
    data = metadata(scene, result, options, mode, selected)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    info = PngImagePlugin.PngInfo()
    info.add_text("polynomial-cusps", text)
    compose(scene, result, options, mode, selected).save(path, pnginfo=info)
    path.with_suffix(".json").write_text(text+"\n", encoding="utf-8")
    return path
