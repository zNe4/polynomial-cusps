"""Forward loops and marked regular points in the dynamical plane."""

import math
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from .drawing import pixel
from .loops import resolved_forward_loops
from .theme import SURFACE
from .loop_drawing import loop_image, loop_text


class LoopWindow:
    def __init__(self, app, *, prepared=None):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.configure(background=SURFACE)
        self.window.title("Lazos en el plano dinámico · p, f(p), f²(p)")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Control-q>", app._quit)
        self.window.bind("<Control-Q>", app._quit)
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
        if prepared is None:
            self.update_scene(app.scene)
        else:
            self.show_prepared(prepared)

    def show_prepared(self, frame):
        from .movie import unpack_image
        self.playing = False
        self.scene, self.data, self.raw_index = frame.scene, frame.loops, frame.raw_index
        self._slider_lock = True
        self.slider.set(360*self.index/(len(self.data.zero_source)-1))
        self._slider_lock = False
        self.photo = ImageTk.PhotoImage(unpack_image(frame.loop_png), master=self.window)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.status.set(frame.loop_status)

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
        image = loop_image(d, self.index, size)
        self.photo = ImageTk.PhotoImage(image, master=self.window)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.status.set(loop_text(self.scene, d, self.raw_index))

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
        if self.app.movie_window is not None:
            self.app.movie_window.pause()
        self.playing = False
        if self._timer is not None:
            self.window.after_cancel(self._timer)
        self.app.loop_window = None
        self.window.destroy()
        if not self.app._closed:
            self.app.redraw()
