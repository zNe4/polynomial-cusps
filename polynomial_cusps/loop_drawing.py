"""Tk-independent drawing of forward-loop inspectors."""

from PIL import Image, ImageDraw


def loop_image(data, index, size):
    d = data
    image = Image.new("RGB", (3*size, 2*size), "#0d1724")
    draw = ImageDraw.Draw(image)
    specs = ((d.zero_source, d.zero_criticals, "Grupo en 0: p0", "#73c1ff", None),
             (d.zero_image, d.targets, "Imagen: f(p0)", "#73c1ff", ("X", "Y")),
             (d.zero_second_image, d.second_targets, "Segunda: f^2(p0)", "#73c1ff", ("Z", "W")),
             (d.one_source, d.one_criticals, "Grupo en 1: p1", "#6ee7a6", None),
             (d.one_image, d.targets, "Imagen: f(p1)", "#6ee7a6", ("X", "Y")),
             (d.one_second_image, d.second_targets, "Segunda: f^2(p1)", "#6ee7a6", ("Z", "W")))
    for panel, (track, criticals, title, color, names) in enumerate(specs):
        ox, oy = panel % 3*size, panel//3*size
        bound = max(1e-100, max(abs(complex(v)) for v in track+criticals))*1.2
        def pos(v):
            z = complex(v)/bound
            return ox+size*(0.5+0.42*z.real), oy+size*(0.53-0.42*z.imag)
        draw.rectangle((ox+1, oy+1, ox+size-1, oy+size-1), outline="#30465b")
        draw.line([pos(v) for v in track], fill=color, width=2)
        for n, v in enumerate(criticals):
            x, y = pos(v)
            draw.ellipse((x-3, y-3, x+3, y+3), fill="#ffdc84")
            if names is not None:
                label = "/".join(names) if criticals[0] == criticals[1] else names[n]
                if criticals[0] != criticals[1] or n == 0:
                    draw.text((x+5, y+4), label, fill="#ffdc84")
        x, y = pos(track[index])
        draw.ellipse((x-5, y-5, x+5, y+5), fill=color, outline="white")
        draw.text((ox+8, oy+8), title, fill="#e3edf3")
    return image


def loop_text(scene, data, raw_index):
    d = data
    c = scene.point.ctx
    turns = raw_index/(len(d.zero_source)-1)
    return (f"f fijo en este fotograma: t = {c.nstr(d.t, 7)}\n"
                    f"Vueltas de la imagen por vuelta fuente: grupo 0 = {float(d.winding_zero.real):.0f}; "
                    f"grupo 1 = {float(d.winding_one.real):.0f}. "
                    f"Segunda imagen sobre Z: {float(d.second_winding_zero.real):.0f} y "
                    f"{float(d.second_winding_one.real):.0f}. Giro marcado: {turns:.2f} vueltas.\n"
                    "Amarillo: críticos o puntos del retrato. Color: p, f(p), f²(p).")
