"""Tk dynamical explorer. Launch with python -m polynomial_cusps --gui."""

import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from .drawing import OverlayOptions, compose, save_export
from .jobs import BackgroundJobs
from .family import solve_family
from .rendering import RenderSettings, Viewport, prepare_scene, render, scene_from_point


VIEWS = {"Global": "global", "Críticos en 0": "zero", "Críticos en 1": "one",
         "Valores críticos": "values", "Ciclo Z / W": "cycle"}


class Explorer:
    def __init__(self, root, *, autostart=True, real="0", imag="0", dps=60, orbit=40):
        self.root = root
        root.title("Polynomial Cusps · Explorador dinámico")
        root.configure(bg="#0d1724")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background="#152232", foreground="#dce8ef", fieldbackground="#23354a")
        style.configure("TButton", padding=(8, 5))
        style.configure("TEntry", fieldbackground="#23354a", insertcolor="#ffffff")
        style.configure("TCombobox", fieldbackground="#23354a", selectbackground="#34566a")
        style.map("TCombobox", fieldbackground=[("readonly", "#23354a")],
                  foreground=[("readonly", "#dce8ef")],
                  selectforeground=[("readonly", "#ffffff")])
        style.map("TButton", background=[("active", "#34566a")])
        self.canvas_size = min(620, max(340, root.winfo_screenheight()-250))
        root.geometry(f"{self.canvas_size+350}x{self.canvas_size+210}")
        root.resizable(False, False)
        self.jobs = BackgroundJobs()
        self.frame = None
        self.cache_key = None
        self.scene = None
        self.parameter_window = self.loop_window = None
        self.selected = None
        self.viewport = Viewport()
        self.real, self.imag = tk.StringVar(value=real), tk.StringVar(value=imag)
        self.dps, self.orbit = tk.StringVar(value=str(dps)), tk.StringVar(value=str(orbit))
        self.iterations, self.resolution = tk.StringVar(value="256"), tk.StringVar(value="384")
        self.engine, self.mode = tk.StringVar(value="auto"), tk.StringVar(value="Julia")
        self.view_name = tk.StringVar(value="Global")
        self.fixed_axes = tk.BooleanVar(value=True)
        self.flags = {name: tk.BooleanVar(value=True) for name in ("criticals", "portrait", "free", "labels", "shade")}
        self.status = tk.StringVar(value="Elige un parámetro para comenzar.")
        self.coordinate_text = tk.StringVar(value="Clic: seleccionar · arrastrar: zoom · rueda: acercar/alejar")
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<space>", self._space)
        root.bind("<Control-q>", self._quit)
        root.bind("<Control-Q>", self._quit)
        self._closed = False
        self._poll_id = root.after(50, self._poll)
        self._startup_ids = []
        if autostart:
            self._startup_ids = [root.after(50, self.request_render), root.after(150, self.open_parameters)]

    def _build(self):
        top = ttk.Frame(self.root, padding=(12, 10))
        top.pack(fill="x")
        for col, (text, variable, width) in enumerate((
            ("Re(t)", self.real, 13), ("Im(t)", self.imag, 13),
            ("Dígitos", self.dps, 5), ("Órbita libre N", self.orbit, 5))):
            box = ttk.Frame(top)
            box.grid(row=0, column=col, padx=(0, 10), sticky="w")
            ttk.Label(box, text=text).pack(side="left", padx=(0, 4))
            entry = ttk.Entry(box, textvariable=variable, width=width)
            entry.pack(side="left")
            entry.bind("<Return>", lambda event: self.request_render())
        ttk.Button(top, text="Aplicar", command=self.request_render).grid(row=0, column=4, padx=4)
        ttk.Button(top, text="Volver a g", command=self.boundary).grid(row=0, column=5)
        tools = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        tools.pack(fill="x")
        for label, var, values, width in (
            ("Iteraciones", self.iterations, (64, 128, 256, 512, 1024, 4096), 7),
            ("Muestreo", self.resolution, (48, 96, 192, 384, 640, 960), 5),
            ("Motor", self.engine, ("auto", "double", "mp"), 7)):
            ttk.Label(tools, text=label).pack(side="left", padx=(0, 4))
            ttk.Combobox(tools, textvariable=var, values=values, width=width).pack(side="left", padx=(0, 10))
        ttk.Button(tools, text="Renderizar", command=self.request_render).pack(side="left")
        ttk.Button(tools, text="Cancelar", command=self.cancel).pack(side="left", padx=5)
        ttk.Button(tools, text="Parámetros", command=self.open_parameters).pack(side="left", padx=3)
        ttk.Button(tools, text="Lazos", command=self.open_loops).pack(side="left")
        body = ttk.Frame(self.root, padding=(12, 0))
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, width=self.canvas_size, height=self.canvas_size,
                                bg="#0c1420", highlightthickness=1, highlightbackground="#344c60")
        self.canvas.pack(side="left", anchor="n")
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<MouseWheel>", lambda event: self.zoom("0.5" if event.delta > 0 else "2", event))
        self.canvas.bind("<Button-4>", lambda event: self.zoom("0.5", event))
        self.canvas.bind("<Button-5>", lambda event: self.zoom("2", event))
        panel = ttk.Frame(body, padding=(14, 0))
        panel.pack(side="left", fill="both", expand=True)
        ttk.Label(panel, text="VISTA DINÁMICA", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        views = ttk.Combobox(panel, textvariable=self.view_name, values=list(VIEWS), state="readonly", width=26)
        views.pack(fill="x", pady=(7, 5))
        views.bind("<<ComboboxSelected>>", self.change_view)
        ttk.Checkbutton(panel, text="Ejes locales sin girar", variable=self.fixed_axes,
                        command=self.request_render).pack(anchor="w")
        zooms = ttk.Frame(panel)
        zooms.pack(fill="x", pady=(0, 10))
        for text, action in (("+", lambda: self.zoom("0.5")), ("-", lambda: self.zoom("2")),
                             ("Restablecer", self.reset_view)):
            ttk.Button(zooms, text=text, command=action, width=12 if text == "Restablecer" else 3).pack(side="left", padx=(0, 3))
        mode = ttk.Combobox(panel, textvariable=self.mode, values=("Escape", "Julia"), state="readonly")
        mode.pack(fill="x", pady=(0, 5))
        mode.bind("<<ComboboxSelected>>", lambda event: self.redraw())
        for name, label in (("criticals", "Críticos marcados"), ("portrait", "Retrato X, Y, Z, W"),
                            ("free", "Órbita del crítico libre"), ("labels", "Etiquetas"),
                            ("shade", "Sombrear sin escape observado")):
            ttk.Checkbutton(panel, text=label, variable=self.flags[name], command=self.redraw).pack(anchor="w")
        ttk.Label(panel, text="Azul: c2/c3 · verde: c4/c5/c6\nNaranja: omega y su órbita\nAmarillo: retrato prescrito",
                  wraplength=280).pack(anchor="w", pady=(7, 9))
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Elegir omega", command=self.select_free).pack(side="left")
        ttk.Button(buttons, text="Iterar z · Espacio", command=self.step).pack(side="left", padx=4)
        ttk.Button(panel, text="Exportar PNG + datos", command=self.export).pack(fill="x", pady=10)
        self.info = tk.Text(panel, width=34, height=13, wrap="word", font=("TkFixedFont", 10),
                            bg="#0d1724", fg="#bdd3e2", relief="flat", padx=8, pady=8)
        self.info.pack(fill="both", expand=True)
        self.info.configure(state="disabled")
        ttk.Label(self.root, textvariable=self.coordinate_text, padding=(12, 5)).pack(fill="x")
        self.progress = ttk.Progressbar(self.root, maximum=1)
        self.progress.pack(fill="x", padx=12)
        ttk.Label(self.root, textvariable=self.status, padding=(12, 6), wraplength=self.canvas_size+300).pack(fill="x")

    def options(self):
        return OverlayOptions(**{name: var.get() for name, var in self.flags.items()})

    def request_render(self, *, point=None, on_complete=None):
        if self.parameter_window is not None:
            self.parameter_window.prioritize_selection()
        if self.parameter_window is not None and on_complete is None:
            self.parameter_window.pause()
        try:
            real, imag, dps, orbit = self.real.get(), self.imag.get(), int(self.dps.get()), int(self.orbit.get())
            settings = RenderSettings(int(self.resolution.get()), int(self.iterations.get()), self.engine.get())
            settings.validate()
        except ValueError as error:
            self.status.set(f"Entrada inválida: {error}")
            return
        key = (real, imag, dps, orbit)
        cached = self.scene if self.cache_key == key else None
        view = replace(self.viewport, fixed_axes=self.fixed_axes.get() and self.viewport.kind != "global")
        short = lambda value: value if len(value) <= 22 else value[:19]+"…"
        self.status.set(f"Calculando t = ({short(real)}) + ({short(imag)})i… Se conserva el último fotograma terminado.")
        self.progress["value"] = 0

        def work(cancel, progress):
            if point is not None:
                p = point if point.requested_dps >= dps else solve_family(
                    (real, imag), dps=dps, steps=1, seed=point)
                scene = scene_from_point(p, orbit, cancel)
            else:
                scene = cached or prepare_scene(real, imag, dps, orbit, cancel)
            effective_view = view
            if not scene.point.t and view.kind != "global":
                effective_view = Viewport()
            result = render(scene, effective_view, settings, cancel, progress, mp_preview_size=96)
            return scene, result, key, on_complete
        self.jobs.submit(work)

    def _poll(self):
        if self._closed:
            return
        for kind, value in self.jobs.poll():
            if kind == "progress":
                self.progress["value"] = value
            elif kind == "error":
                self.status.set(f"No se pudo completar: {value}. La imagen anterior sigue visible.")
            elif kind == "result":
                scene, result, key, on_complete = value
                if self.cache_key != key:
                    self.selected = None
                self.scene, self.frame, self.cache_key = scene, result, key
                self.viewport = result.viewport
                if self.parameter_window is not None:
                    self.parameter_window.mark_selected(scene.point)
                if self.loop_window is not None:
                    self.loop_window.update_scene(scene)
                self.view_name.set(next(label for label, name in VIEWS.items() if name == result.viewport.kind))
                self.progress["value"] = 1
                count = result.settings.size**2-result.escaped_count
                text = (f"{result.engine} · {result.settings.size}² · {result.seconds:.2f} s · "
                        f"{count/result.settings.size**2:.1%} sin escape en {result.settings.iterations} iteraciones.")
                if result.engine == "mp" and result.settings.engine == "auto":
                    text += " Vista previa MP; elige motor mp para usar todo el muestreo solicitado."
                if result.viewport.kind != "global":
                    text += " El tiempo local puede crecer como |t|^(-24)."
                self.status.set(text)
                self.redraw()
                if on_complete is not None:
                    on_complete()
        self._poll_id = self.root.after(50, self._poll)

    def redraw(self):
        if self.frame is None:
            return
        image = compose(self.scene, self.frame, self.options(), self.mode.get(), self.selected,
                        self.canvas_size, self.loop_overlay())
        self.photo = ImageTk.PhotoImage(image, master=self.root)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        p, c = self.scene.point, self.scene.point.ctx
        report = self.scene.reference.report()
        def short(value):
            return "n/a" if value is None else c.nstr(value, 8)
        text = (f"Parámetro mostrado:\nt = {short(p.t)}\n\n"
                f"Precisión: {c.dps} dígitos\n"
                f"log10 |Delta| = {short(report['scales']['cycle']['log10_abs'])}\n"
                f"log10 |mu-1| (retrato) =\n{short(report['portrait_multiplier_defect']['log10_abs'])}\n"
                f"Residuo local (radio 2):\n{short(report['normalized_residuals']['cycle_map_bound_radius_2'])}\n"
                f"Corrección relativa de mu-1:\n{short(report['raw_correction_over_portrait_defect'])}\n"
                f"Píxeles MP de respaldo: {self.frame.fallback_pixels}\n")
        if self.selected:
            text += f"\nz{self.selected[1]} =\n{c.nstr(self.selected[0], 16)}\n"
        text += "\nSin escape observado no demuestra pertenencia.\nLos mapas conservan residuos."
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def boundary(self):
        self.real.set("0")
        self.imag.set("0")
        self.viewport = Viewport()
        self.request_render()

    def change_view(self, event=None):
        kind = VIEWS[self.view_name.get()]
        if self.scene is not None and not self.scene.point.t and kind != "global":
            self.status.set("En g las cartas colapsan. Elige un parámetro t distinto de cero.")
            self.view_name.set("Global")
            return
        self.viewport = Viewport.preset(kind)
        self.request_render()

    def reset_view(self):
        self.viewport = Viewport.preset(VIEWS[self.view_name.get()])
        self.request_render()

    def zoom(self, factor, event=None):
        if self.frame is None:
            return
        x, y = (str(event.x/self.canvas_size), str(event.y/self.canvas_size)) if event else ("0.5", "0.5")
        self.viewport = self.frame.viewport.zoom(self.scene.point.ctx, factor, x, y)
        self.request_render()

    def _press(self, event):
        if self.loop_window is not None and self.loop_window.pick_marker(event):
            self._dragging_loop = True
            return
        self.drag_start = (event.x, event.y)

    def _drag(self, event):
        if getattr(self, "_dragging_loop", False):
            self.loop_window.pick_marker(event, dragging=True)
            return
        if not hasattr(self, "drag_start"):
            return
        self.canvas.delete("zoom")
        self.canvas.create_rectangle(*self.drag_start, event.x, event.y, outline="#f5d389", tags="zoom")

    def _release(self, event):
        if getattr(self, "_dragging_loop", False):
            self._dragging_loop = False
            return
        if self.frame is None or not hasattr(self, "drag_start"):
            return
        x, y = self.drag_start
        del self.drag_start
        self.canvas.delete("zoom")
        distance = max(abs(event.x-x), abs(event.y-y))
        c = self.scene.point.ctx
        if distance > 7:
            view = self.frame.viewport
            center = view.coordinate(c, str((event.x+x)/2/self.canvas_size), str((event.y+y)/2/self.canvas_size))
            self.viewport = Viewport(view.kind, c.nstr(center.real, c.dps), c.nstr(center.imag, c.dps),
                                     c.nstr(c.mpf(view.span)*distance/self.canvas_size, c.dps), view.fixed_axes)
            self.request_render()
        else:
            local = self.frame.viewport.coordinate(c, str(event.x/self.canvas_size), str(event.y/self.canvas_size))
            self.selected = (self.scene.absolute(local, self.frame.viewport.kind, self.frame.viewport.fixed_axes), 0)
            self.redraw()

    def _motion(self, event):
        if self.frame is None:
            return
        c = self.scene.point.ctx
        local = self.frame.viewport.coordinate(c, str(event.x/self.canvas_size), str(event.y/self.canvas_size))
        name = "z" if self.frame.viewport.kind == "global" else "xi"
        self.coordinate_text.set(f"{name} = {c.nstr(local, 12)} · Clic: seleccionar · arrastrar: zoom · rueda: zoom")

    def select_free(self):
        if self.scene:
            self.selected = (self.scene.point.omega, 0)
            self.redraw()

    def step(self):
        if self.scene is None:
            return
        if self.selected is None:
            self.select_free()
            return
        z, n = self.selected
        if abs(z) > self.scene.point.escape_radius():
            self.status.set("El punto seleccionado ya cruzó el radio de escape.")
            return
        self.selected = (self.scene.point.f(z), n+1)
        self.redraw()

    def _space(self, event):
        if event.widget.winfo_class() not in ("TEntry", "TCombobox", "Text", "Entry"):
            self.step()
            return "break"

    def cancel(self):
        self.jobs.cancel()
        self.status.set("Cálculo cancelado. Se conserva la última imagen terminada.")
        self.progress["value"] = 0

    def export(self):
        if self.frame is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            try:
                save_export(path, self.scene, self.frame, self.options(), self.mode.get(),
                            self.selected, self.loop_overlay())
                self.status.set(f"Exportado: {path} y sus datos JSON.")
            except (ValueError, OSError) as error:
                messagebox.showerror("Exportación", str(error), parent=self.root)

    def _quit(self, event):
        window = event.widget.winfo_toplevel()
        if self.loop_window is not None and window is self.loop_window.window:
            self.loop_window.close()
        else:
            self.close()
        return "break"

    def close(self):
        if self._closed:
            return
        self._closed = True
        for timer in self._startup_ids:
            self.root.after_cancel(timer)
        if self.parameter_window is not None:
            self.parameter_window.close()
        if self.loop_window is not None:
            self.loop_window.close()
        self.root.after_cancel(self._poll_id)
        self.jobs.close()
        self.root.destroy()

    def open_parameters(self):
        if self.parameter_window is None:
            from .parameter_gui import ParameterWindow
            self.parameter_window = ParameterWindow(self)
        else:
            self.parameter_window.window.lift()

    def open_loops(self):
        if self.loop_window is None:
            from .loop_gui import LoopWindow
            self.loop_window = LoopWindow(self)
        else:
            self.loop_window.window.lift()
        self.redraw()

    def loop_overlay(self):
        return self.loop_window.overlay() if self.loop_window is not None else None

    def apply_parameter(self, t, point=None, on_complete=None):
        c = point.ctx if point is not None else (self.scene.point.ctx if self.scene else None)
        if c is None:
            import mpmath
            c = mpmath.mp
        self.real.set(c.nstr(t.real, c.dps-15))
        self.imag.set(c.nstr(t.imag, c.dps-15))
        self.request_render(point=point, on_complete=on_complete)


def main(*, real="0", imag="0", dps=60, orbit=40):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise SystemExit(f"No se pudo abrir Tk: {error}. Se necesita una sesión gráfica.") from error
    Explorer(root, real=real, imag=imag, dps=dps, orbit=orbit)
    root.mainloop()


if __name__ == "__main__":
    main()
