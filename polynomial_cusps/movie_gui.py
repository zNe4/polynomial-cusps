"""Prepare first, then play checked parameter-circle frames from RAM."""

from dataclasses import replace
import math
import time
import tkinter as tk
from tkinter import ttk

from .jobs import BackgroundJobs
from .movie import MovieConfig, prepare_movie
from .rendering import RenderSettings
from .theme import SURFACE


class MovieWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root, background=SURFACE)
        self.window.title("Vuelta movie · preparar y reproducir")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Control-q>", app._quit)
        self.window.bind("<Control-Q>", app._quit)
        self.jobs = BackgroundJobs()
        self.movie = None
        self.index = 0
        self.playing = self._preparing = self._closed = self._slider_lock = False
        self._timer = None
        radius = app.parameter_window.radius.get() if app.parameter_window is not None else "0.08"
        self.radius, self.frames = tk.StringVar(value=radius), tk.StringVar(value="240")
        self.resolution, self.fps = tk.StringVar(value="192"), tk.StringVar(value="30")
        self.include_loops = tk.BooleanVar(value=app.loop_window is not None)
        self.repeat = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Prepara la película antes de reproducir. Cada fotograma usa un f verificado.")
        box = ttk.Frame(self.window, padding=12)
        box.pack(fill="both", expand=True)
        for row, (label, variable, values) in enumerate((
            ("Radio r", self.radius, None), ("Fotogramas por vuelta", self.frames, (96, 120, 240, 360, 720)),
            ("Muestreo del Julia", self.resolution, (96, 128, 192, 256, 384)),
            ("Velocidad (fps)", self.fps, (12, 24, 30, 60)))):
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 12))
            widget = (ttk.Entry(box, textvariable=variable, width=12) if values is None else
                      ttk.Combobox(box, textvariable=variable, values=values, width=10))
            widget.grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(box, text="Incluir lazos dinámicos", variable=self.include_loops).grid(row=4, columnspan=2, sticky="w")
        ttk.Checkbutton(box, text="Repetir vuelta", variable=self.repeat).grid(row=5, columnspan=2, sticky="w")
        actions = ttk.Frame(box)
        actions.grid(row=6, columnspan=2, sticky="ew", pady=8)
        ttk.Button(actions, text="Preparar película", style="Accent.TButton", command=self.prepare).pack(side="left")
        ttk.Button(actions, text="Cancelar", command=self.cancel).pack(side="left", padx=5)
        self.progress = ttk.Progressbar(box, maximum=1)
        self.progress.grid(row=7, columnspan=2, sticky="ew")
        playback = ttk.Frame(box)
        playback.grid(row=8, columnspan=2, sticky="ew", pady=8)
        ttk.Button(playback, text="Reproducir / pausa", command=self.toggle_play).pack(side="left")
        ttk.Button(playback, text="Paso", command=lambda: self.select(self.index+1)).pack(side="left", padx=5)
        self.slider = ttk.Scale(box, from_=0, to=239, command=self.scrub)
        self.slider.grid(row=9, columnspan=2, sticky="ew")
        ttk.Label(box, textvariable=self.status, wraplength=370).grid(row=10, columnspan=2, sticky="w", pady=8)
        ttk.Label(box, text="Captura la vista, iteraciones, capas y ángulo de p actuales.\n"
                  "Cambiar la dinámica pausa la película. Reproducir restaura su configuración.\n"
                  "240 fotogramas a 30 fps = 8 segundos por vuelta.",
                  style="Muted.TLabel", wraplength=370).grid(row=11, columnspan=2, sticky="w")
        box.columnconfigure(1, weight=1)
        self._poll_id = self.window.after(50, self.poll)

    def prepare(self):
        self.pause()
        try:
            loop = self.app.loop_window
            turns = loop.raw_index/(len(loop.data.zero_source)-1) if loop and loop.data else 0
            config = MovieConfig(radius=self.radius.get(), frames=int(self.frames.get()), dps=int(self.app.dps.get()),
                orbit=int(self.app.orbit.get()), view=replace(self.app.viewport,
                    fixed_axes=self.app.fixed_axes.get() and self.app.viewport.kind != "global"),
                settings=RenderSettings(int(self.resolution.get()), int(self.app.iterations.get()), self.app.engine.get()),
                overlays=self.app.options(), mode=self.app.mode.get(), display_size=self.app.canvas_size,
                include_loops=self.include_loops.get(), loop_multiplier=loop.factor.get() if loop else "2.5",
                boundary_radius=loop.epsilon.get() if loop else "0.03", marker_turns=turns,
                loop_group={"Ambos grupos": "both", "Grupo en 0": "0", "Grupo en 1": "1"}[loop.group.get()] if loop else "both",
                show_loops=loop.show.get() if loop else True,
                loop_size=loop.size if loop else min(270, max(150, (self.app.root.winfo_screenheight()-300)//2),
                    max(150, (self.app.root.winfo_screenwidth()-60)//3)))
            config.settings.validate()
        except ValueError as error:
            self.status.set(f"Entrada inválida: {error}")
            return
        self.app.jobs.cancel()
        if self.app.parameter_window is not None:
            self.app.parameter_window.cancel()
        if loop is not None:
            loop.playing = False
        self.movie = None
        self._preparing = True
        self.progress["value"] = 0
        self.status.set("Preparando parámetros, Julia, órbitas e imágenes… Puedes cancelar.")
        self.app.status.set("Preparando vuelta movie. Se conserva el último fotograma terminado.")
        self.app.progress["value"] = 0
        # Keep all Tk owners out of the numerical worker closure.
        self.jobs.submit(lambda cancel, progress: prepare_movie(config, cancel=cancel, progress=progress))

    def poll(self):
        if self._closed:
            return
        for kind, value in self.jobs.poll():
            if kind == "progress":
                self.progress["value"] = value
            elif kind == "error":
                self._preparing = False
                self.status.set(f"No se pudo preparar: {value}")
                self.app.status.set("Preparación de película detenida. Se conserva el último fotograma terminado.")
            else:
                self.movie, self.index, self._preparing = value, 0, False
                self.slider.configure(to=len(value.frames)-1)
                self.progress["value"] = 1
                self.select(0)
                self.status.set(f"Lista: {len(value.frames)} fotogramas · {value.config.settings.size}² · "
                                f"preparación {value.seconds:.1f} s · caché estimada {value.estimated_bytes/1024**2:.0f} MiB.")
        self._poll_id = self.window.after(50, self.poll)

    def select(self, index, *, autoplay=False):
        if self.movie is None:
            return
        if not autoplay:
            self.pause()
        self.index = max(0, min(index, len(self.movie.frames)-1))
        self.app.show_movie_frame(self.movie, self.index)
        self._slider_lock = True
        self.slider.set(self.index)
        self._slider_lock = False
        self.status.set(f"Fotograma {self.index+1}/{len(self.movie.frames)} · "
                        f"theta = {360*self.index/len(self.movie.frames):.1f}° · imágenes precalculadas.")

    def scrub(self, value):
        if not self._slider_lock:
            self.select(round(float(value)))

    def toggle_play(self):
        if self.playing:
            self.pause()
            return
        if self.movie is None or self._preparing:
            self.status.set("Prepara primero una película completa.")
            return
        try:
            fps = float(self.fps.get())
            if not math.isfinite(fps) or not 1 <= fps <= 60:
                raise ValueError("Usa una velocidad entre 1 y 60 fps")
        except ValueError as error:
            self.status.set(str(error))
            return
        self.app.jobs.cancel()
        if self.app.parameter_window is not None:
            self.app.parameter_window.pause()
            self.app.parameter_window.prioritize_selection()
        if self.app.loop_window is not None:
            self.app.loop_window.playing = False
        self.select(0 if self.index == len(self.movie.frames)-1 else self.index)
        self._fps, self._started, self._start_index = fps, time.monotonic(), self.index
        self.playing = True
        self.tick()

    def tick(self):
        self._timer = None
        if not self.playing or self._closed:
            return
        position = self._start_index+int((time.monotonic()-self._started)*self._fps)
        if not self.repeat.get() and position >= len(self.movie.frames)-1:
            self.select(len(self.movie.frames)-1)
            return
        index = position % len(self.movie.frames)
        if index != self.index:
            self.select(index, autoplay=True)
        self._timer = self.window.after(max(1, round(1000/self._fps)), self.tick)

    def pause(self):
        self.playing = False
        if self._timer is not None:
            self.window.after_cancel(self._timer)
            self._timer = None

    def cancel(self):
        self.pause()
        self.jobs.cancel()
        if self._preparing:
            self.app.status.set("Preparación de película cancelada. Se conserva el último fotograma mostrado.")
        self._preparing = False
        self.status.set("Preparación cancelada. Se conserva el último fotograma mostrado.")

    def close(self):
        self._closed = True
        self.pause()
        if self._preparing and not self.app._closed:
            self.app.status.set("Preparación de película cancelada al cerrar sus controles.")
        self.window.after_cancel(self._poll_id)
        self.jobs.close()
        self.movie = None
        self.app.movie_window = None
        self.window.destroy()
