"""Parameter selection and non-overlapping playback of a circle around g."""

import tkinter as tk
from tkinter import ttk, filedialog
import json
from pathlib import Path

import mpmath
import numpy as np
from PIL import Image, ImageDraw, ImageTk

from .jobs import BackgroundJobs
from .drawing import _encode
from .parameters import COLORS, FamilyCache, parameter_circle, parameter_grid
from .rendering import Viewport


class ParameterWindow:
    def __init__(self, app, *, autostart=True):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Polynomial Cusps · Parámetros t alrededor de g")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.size = min(480, max(320, app.root.winfo_screenheight()-370))
        self.jobs, self.cache = BackgroundJobs(), FamilyCache()
        self.ctx = mpmath.mp.clone()
        self.ctx.dps = 100
        self.view = Viewport("global", "0", "0", "0.28")
        self.samples = tk.StringVar(value="17")
        self.mode = tk.StringVar(value="Ciclo: retrato exacto")
        self.radius, self.frames = tk.StringVar(value="0.08"), tk.StringVar(value="96")
        self.status = tk.StringVar(value="Clic: elegir t · arrastrar/rueda: zoom independiente")
        self.angle_text = tk.StringVar(value="theta = 0 grados")
        self.states = np.full((17, 17), 7, dtype=np.uint8)
        self.grid = self.circle = None
        self.selected = app.scene.point.t if app.scene else self.ctx.mpc(0)
        self.index = 0
        self.playing, self._token, self._closed = False, 0, False
        self._timer = None
        self._auto_id = None
        top = ttk.Frame(self.window, padding=10)
        top.pack(fill="x")
        ttk.Combobox(top, textvariable=self.mode, values=("Ciclo: retrato exacto", "Órbita libre: escape"),
                     state="readonly", width=25).pack(side="left")
        ttk.Combobox(top, textvariable=self.samples, values=(9, 17, 25, 41), width=4).pack(side="left", padx=6)
        ttk.Button(top, text="Calcular", command=self.render_grid).pack(side="left")
        ttk.Button(top, text="Cancelar", command=self.cancel).pack(side="left", padx=3)
        self.canvas = tk.Canvas(self.window, width=self.size, height=self.size,
                                bg="#0d1724", highlightthickness=1, highlightbackground="#344c60")
        self.canvas.pack(padx=10)
        self.canvas.bind("<ButtonPress-1>", lambda e: setattr(self, "_start", (e.x, e.y)))
        self.canvas.bind("<ButtonRelease-1>", self.pick)
        self.canvas.bind("<MouseWheel>", lambda e: self.zoom("0.5" if e.delta > 0 else "2", e))
        self.canvas.bind("<Button-4>", lambda e: self.zoom("0.5", e))
        self.canvas.bind("<Button-5>", lambda e: self.zoom("2", e))
        ttk.Label(self.window, text="Turquesa: ciclo atractor · violeta: repulsor (retrato)\n"
                  "Naranja: escape libre · gris: no resuelto · rojo: cálculo fallido\n"
                  "Plano t: normalización de la cúspide; g corresponde a t=0.",
                  wraplength=self.size, padding=(10, 5)).pack(fill="x")
        buttons = ttk.Frame(self.window, padding=(10, 0))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Restablecer plano", command=self.reset).pack(side="left")
        ttk.Button(buttons, text="Mostrar lazos dinámicos", command=app.open_loops).pack(side="left", padx=6)
        ttk.Button(buttons, text="Datos de vuelta", command=self.export_circle).pack(side="left")
        circle = ttk.LabelFrame(self.window, text="Vuelta paramétrica: t = r exp(i theta)", padding=8)
        circle.pack(fill="x", padx=10, pady=8)
        for title, variable, width in (("r", self.radius, 12), ("Fotogramas", self.frames, 5)):
            ttk.Label(circle, text=title).pack(side="left", padx=(0, 4))
            ttk.Entry(circle, textvariable=variable, width=width).pack(side="left", padx=(0, 6))
        ttk.Button(circle, text="Preparar vuelta", command=self.build_circle).pack(side="left")
        row = ttk.Frame(self.window, padding=(10, 0))
        row.pack(fill="x")
        ttk.Button(row, text="Reproducir / pausa", command=self.toggle_play).pack(side="left")
        ttk.Button(row, text="Paso", command=lambda: self.select_index(self.index+1)).pack(side="left", padx=4)
        self.slider = ttk.Scale(row, from_=0, to=96, command=self.scrub)
        self.slider.pack(side="left", fill="x", expand=True)
        ttk.Label(self.window, textvariable=self.angle_text, padding=(10, 5)).pack(fill="x")
        self.progress = ttk.Progressbar(self.window, maximum=1)
        self.progress.pack(fill="x", padx=10)
        ttk.Label(self.window, textvariable=self.status, wraplength=self.size, padding=10).pack(fill="x")
        self._slider_lock = False
        self._poll_id = self.window.after(50, self.poll)
        self.window.update_idletasks()
        x = min(app.root.winfo_rootx()+app.root.winfo_width()+12,
                max(0, self.window.winfo_screenwidth()-self.window.winfo_reqwidth()-20))
        self.window.geometry(f"+{x}+20")
        self.redraw()
        if autostart:
            self._auto_id = self.window.after(100, self.render_grid)

    def render_grid(self):
        self.pause()
        try:
            size = int(self.samples.get())
            view = self.view
            mode = "cycle" if self.mode.get().startswith("Ciclo") else "free"
            iterations = int(self.app.iterations.get())
        except ValueError as error:
            self.status.set(str(error))
            return
        self.states = np.full((size, size), 7, dtype=np.uint8) if 3 <= size <= 81 else self.states
        self.redraw()
        self.status.set("Calculando celdas verificadas; la selección sigue disponible.")
        self.jobs.submit(lambda cancel, progress: ("grid", parameter_grid(
            view, size=size, mode=mode, iterations=iterations,
            cache=self.cache, cancel=cancel, progress=progress)))

    def build_circle(self):
        self.pause()
        self.circle = None
        try:
            frames, dps = int(self.frames.get()), int(self.app.dps.get())
        except ValueError as error:
            self.status.set(str(error))
            return
        self.status.set("Preparando una vuelta cerrada y midiendo sus números de giro…")
        radius = self.radius.get()
        self.jobs.submit(lambda cancel, progress: ("circle", parameter_circle(
            radius, frames=frames, dps=dps, cache=self.cache, cancel=cancel, progress=progress)))

    def poll(self):
        if self._closed:
            return
        for kind, data in self.jobs.poll():
            if kind == "progress":
                if isinstance(data, tuple):
                    value, self.states = data
                    self.redraw()
                else:
                    value = data
                self.progress["value"] = value
            elif kind == "error":
                self.status.set(f"Cálculo detenido: {data}")
            else:
                tag, result = data
                if tag == "grid":
                    self.grid, self.states = result, result.states
                    self.status.set(f"{len(result.points)} muestras verificadas. Cada celda usa su centro; no hay interpolación.")
                else:
                    self.circle, self.index = result, 0
                    self.slider.configure(to=len(result.points)-1)
                    counts = ", ".join(f"{name}: {float(count.real):.0f}" for name, count in result.windings.items())
                    self.status.set(f"Vueltas medidas al cerrar el parámetro: {counts}. Reproducir mueve f(t).")
                    self.select_index(0)
                self.progress["value"] = 1
                self.redraw()
        self._poll_id = self.window.after(50, self.poll)

    def _position(self, t):
        c = self.ctx
        z = (c.mpc(t)-c.mpc(self.view.real, self.view.imag))/c.mpf(self.view.span)
        if abs(z.real) > 4 or abs(z.imag) > 4:
            return None
        return self.size*(0.5+float(z.real)), self.size*(0.5-float(z.imag))

    def redraw(self):
        image = Image.fromarray(COLORS[self.states]).resize((self.size, self.size), Image.Resampling.NEAREST)
        draw = ImageDraw.Draw(image)
        origin = self._position(0)
        if origin:
            x, y = origin
            draw.line((0, y, self.size, y), fill="#617384")
            draw.line((x, 0, x, self.size), fill="#617384")
            draw.ellipse((x-3, y-3, x+3, y+3), fill="#ffe2a1")
            draw.text((x+5, y+5), "g", fill="#ffe2a1")
        if self.circle:
            positions = [self._position(p.t) for p in self.circle.points]
            for a, b in zip(positions, positions[1:]):
                if a is not None and b is not None:
                    draw.line((a, b), fill="#e6c97e", width=2)
        selection = self._position(self.selected)
        if selection:
            x, y = selection
            draw.ellipse((x-5, y-5, x+5, y+5), fill="#fff4d4", outline="#061421", width=2)
        self.photo = ImageTk.PhotoImage(image, master=self.window)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

    def mark_selected(self, point):
        self.selected = point.t
        self.redraw()

    def pick(self, event):
        self.pause()
        x, y = getattr(self, "_start", (event.x, event.y))
        distance = max(abs(x-event.x), abs(y-event.y))
        if distance > 7:
            center = self.view.coordinate(self.ctx, str((x+event.x)/2/self.size), str((y+event.y)/2/self.size))
            self.view = Viewport("global", self.ctx.nstr(center.real, 90), self.ctx.nstr(center.imag, 90),
                                 self.ctx.nstr(self.ctx.mpf(self.view.span)*distance/self.size, 90))
            self.render_grid()
            return
        t = self.view.coordinate(self.ctx, str(event.x/self.size), str(event.y/self.size))
        if abs(t) > self.ctx.mpf("0.2"):
            self.status.set("Fuera del dominio local implementado: |t| <= 0.2.")
            return
        self.app.apply_parameter(t)

    def zoom(self, factor, event):
        self.view = self.view.zoom(self.ctx, factor, str(event.x/self.size), str(event.y/self.size))
        self.render_grid()

    def reset(self):
        self.view = Viewport("global", "0", "0", "0.28")
        self.render_grid()

    def select_index(self, index, *, autoplay=False):
        if self.circle is None:
            return
        if not autoplay:
            self.pause()
        self.index = max(0, min(index, len(self.circle.points)-1))
        self._slider_lock = True
        self.slider.set(self.index)
        self._slider_lock = False
        self.angle_text.set(f"theta = {360*self.index/(len(self.circle.points)-1):.1f} grados")
        token = self._token
        def completed():
            if self.playing and token == self._token and not self._closed:
                if self.index >= len(self.circle.points)-1:
                    self.pause()
                else:
                    self._timer = self.window.after(100, lambda: self.select_index(self.index+1, autoplay=True))
        self.app.apply_parameter(self.circle.points[self.index].t, self.circle.points[self.index], completed if autoplay else None)

    def scrub(self, value):
        if not self._slider_lock:
            self.select_index(int(round(float(value))))

    def toggle_play(self):
        if self.circle is None:
            self.status.set("Prepara primero una vuelta paramétrica.")
            return
        if self.playing:
            self.pause()
        else:
            self.playing = True
            self._token += 1
            self.select_index(0 if self.index >= len(self.circle.points)-1 else self.index, autoplay=True)

    def pause(self):
        self.playing = False
        self._token += 1
        if self._timer is not None:
            self.window.after_cancel(self._timer)
            self._timer = None

    def cancel(self):
        self.pause()
        self.jobs.cancel()
        self.status.set("Cálculo paramétrico cancelado.")

    def export_circle(self):
        if self.circle is None:
            self.status.set("Prepara una vuelta antes de exportar sus datos.")
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".json",
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = {"format": "polynomial-cusps-parameter-circle-v1", "radius": self.circle.radius,
                "windings": self.circle.windings,
                "points": [{name: getattr(p, name) for name in ("t", "x", "s", "h0", "omega", "lam", "B")}
                           for p in self.circle.points],
                "interpretation": "A closed parameter circle, distinct from a source loop for fixed f."}
        try:
            Path(path).write_text(json.dumps(_encode(self.circle.points[0].ctx, data), indent=2)+"\n", encoding="utf-8")
            self.status.set(f"Datos de vuelta exportados: {path}")
        except OSError as error:
            self.status.set(f"No se pudo exportar: {error}")

    def close(self):
        self._closed = True
        self.pause()
        self.window.after_cancel(self._poll_id)
        if self._auto_id is not None:
            self.window.after_cancel(self._auto_id)
        self.jobs.close()
        self.app.parameter_window = None
        self.window.destroy()
