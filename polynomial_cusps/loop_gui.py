"""Forward loops and marked regular points in the dynamical plane."""

import math
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from .drawing import pixel
from .loops import resolved_forward_loops


class LoopWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Lazos en el plano dinámico · p, f(p), f²(p)")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.size = min(270, max(150, (app.root.winfo_screenheight()-300)//2),
                        max(150, (app.root.winfo_screenwidth()-60)//3))
        self.factor, self.epsilon = tk.StringVar(value="2.5"), tk.StringVar(value="0.03")
        self.group = tk.StringVar(value="Ambos grupos")
        self.show = tk.BooleanVar(value=True)
        self.status = tk.StringVar()
        self.raw_index = 0
        self.playing, self._timer = False, None
        self.data = self.scene = None
        self._slider_lock = False
        top = ttk.Frame(self.window, padding=8)
        top.pack(fill="x")
        for label, var in (("Radio / escala del grupo", self.factor), ("Radio en g", self.epsilon)):
            ttk.Label(top, text=label).pack(side="left", padx=(0, 3))
            ttk.Entry(top, textvariable=var, width=6).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Aplicar", command=self.apply).pack(side="left")
        row = ttk.Frame(self.window, padding=(8, 0))
        row.pack(fill="x")
        ttk.Checkbutton(row, text="Dibujar en el Julia", variable=self.show, command=app.redraw).pack(side="left")
        combo = ttk.Combobox(row, textvariable=self.group, values=("Ambos grupos", "Grupo en 0", "Grupo en 1"),
                             width=16, state="readonly")
        combo.pack(side="left", padx=8)
        combo.bind("<<ComboboxSelected>>", lambda e: app.redraw())
        ttk.Button(row, text="Mover p / pausa", command=self.toggle_play).pack(side="left")
        self.canvas = tk.Canvas(self.window, width=3*self.size, height=2*self.size, bg="#0d1724", highlightthickness=0)
        self.canvas.pack(padx=8, pady=8)
        self.slider = ttk.Scale(self.window, from_=0, to=360, command=self.scrub)
        self.slider.pack(fill="x", padx=10)
        ttk.Label(self.window, textvariable=self.status, padding=10, wraplength=3*self.size).pack(fill="x")
        ttk.Label(self.window, text="Columnas: p → f(p), cerca de X/Y → f²(p), cerca de Z/W.\n"
                  "Ampliaciones del plano dinámico con ejes sin girar. Arrastra p en el Julia o usa el deslizador.",
                  padding=(10, 0, 10, 10), wraplength=3*self.size).pack(fill="x")
        self.update_scene(app.scene)

    def update_scene(self, scene):
        if scene is None:
            return
        try:
            data = resolved_forward_loops(scene, multiplier=self.factor.get(), boundary_radius=self.epsilon.get())
        except (ValueError, ZeroDivisionError) as error:
            self.status.set(str(error))
            return
        if self.data is not None:
            self.raw_index = round(self.raw_index*(len(data.zero_source)-1)/(len(self.data.zero_source)-1))
        self.data, self.scene = data, scene
        self.redraw()

    def apply(self):
        self.update_scene(self.app.scene)
        self.app.redraw()

    @property
    def index(self):
        return self.raw_index % (len(self.data.zero_source)-1) if self.data else 0

    def overlay(self):
        if not self.show.get() or self.data is None or self.scene is not self.app.scene:
            return None
        group = {"Ambos grupos": "both", "Grupo en 0": "0", "Grupo en 1": "1"}[self.group.get()]
        return self.data, self.index, group

    def redraw(self):
        if self.data is None:
            return
        d, size = self.data, self.size
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
            x, y = pos(track[self.index])
            draw.ellipse((x-5, y-5, x+5, y+5), fill=color, outline="white")
            draw.text((ox+8, oy+8), title, fill="#e3edf3")
        self.photo = ImageTk.PhotoImage(image, master=self.window)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        c = self.scene.point.ctx
        turns = self.raw_index/(len(d.zero_source)-1)
        self.status.set(f"f fijo en este fotograma: t = {c.nstr(d.t, 7)}\n"
                        f"Vueltas de la imagen por vuelta fuente: grupo 0 = {float(d.winding_zero.real):.0f}; "
                        f"grupo 1 = {float(d.winding_one.real):.0f}. "
                        f"Segunda imagen sobre Z: {float(d.second_winding_zero.real):.0f} y "
                        f"{float(d.second_winding_one.real):.0f}. Giro marcado: {turns:.2f} vueltas.\n"
                        "Amarillo: críticos o puntos del retrato. Color: p, f(p), f²(p).")

    def set_index(self, raw_index):
        self.raw_index = max(0, raw_index)
        self._slider_lock = True
        self.slider.set(360*self.index/(len(self.data.zero_source)-1))
        self._slider_lock = False
        self.redraw()
        self.app.redraw()

    def scrub(self, degrees):
        if self.data is not None and not self._slider_lock:
            self.playing = False
            self.set_index(round(float(degrees)/360*(len(self.data.zero_source)-1)))

    def toggle_play(self):
        self.playing = not self.playing
        if self.playing and self._timer is None:
            self.tick()

    def tick(self):
        self._timer = None
        if self.playing and self.data is not None:
            self.set_index(self.raw_index+max(1, round((len(self.data.zero_source)-1)/96)))
            self._timer = self.window.after(60, self.tick)

    def pick_marker(self, event, *, dragging=False):
        if self.data is None or self.app.frame is None or not self.show.get():
            return False
        app, scene = self.app, self.app.scene
        if self.scene is not scene:
            return False
        c, view = scene.point.ctx, app.frame.viewport
        local = view.coordinate(c, str(event.x/app.canvas_size), str(event.y/app.canvas_size))
        z = scene.absolute(local, view.kind, view.fixed_axes)
        groups = [int(self.group.get()[-1])] if self.group.get() != "Ambos grupos" else [0, 1]
        if dragging:
            groups = [self._drag_group]
        for j in groups:
            angle = c.arg(z-j)
            q = j+self.data.physical_radii[j]*c.exp(1j*angle)
            projected = pixel(scene, view, q, app.canvas_size)
            if dragging or (projected and math.hypot(projected[0]-event.x, projected[1]-event.y) < 12):
                self._drag_group = j
                self.playing = False
                self.set_index(round(float(angle % (2*c.pi))/(2*math.pi)*(len(self.data.zero_source)-1)))
                return True
        return False

    def close(self):
        self.playing = False
        if self._timer is not None:
            self.window.after_cancel(self._timer)
        self.app.loop_window = None
        self.window.destroy()
        if not self.app._closed:
            self.app.redraw()
