"""Prepare complete, checked parameter-circle movies without any Tk objects."""

from dataclasses import dataclass
from io import BytesIO
import time

from PIL import Image

from .drawing import OverlayOptions, compose, scene_text
from .loop_drawing import loop_image, loop_text
from .loops import resolved_forward_loops
from .parameters import parameter_circle
from .rendering import RenderSettings, Viewport, _check, render, scene_from_point


@dataclass(frozen=True)
class MovieConfig:
    radius: str = "0.08"
    frames: int = 240
    dps: int = 60
    orbit: int = 40
    view: Viewport = Viewport()
    settings: RenderSettings = RenderSettings(192, 256)
    overlays: OverlayOptions = OverlayOptions()
    mode: str = "Julia"
    display_size: int = 620
    include_loops: bool = False
    loop_multiplier: str = "2.5"
    boundary_radius: str = "0.03"
    marker_turns: float = 0
    loop_group: str = "both"
    show_loops: bool = True
    loop_size: int = 270


@dataclass(frozen=True)
class MovieFrame:
    scene: object
    result: object
    png: bytes
    text: str
    loops: object
    loop_png: bytes | None
    loop_status: str
    raw_index: int
    real: str
    imag: str


@dataclass(frozen=True)
class Movie:
    config: MovieConfig
    circle: object
    frames: tuple
    seconds: float
    estimated_bytes: int


def pack_image(image):
    stream = BytesIO()
    image.save(stream, format="PNG", compress_level=1)
    return stream.getvalue()


def unpack_image(data):
    with Image.open(BytesIO(data)) as image:
        return image.convert("RGB")


def prepare_movie(config, *, cancel=None, progress=None, budget=512*1024**2):
    """Return an atomic cache of complete frames; cancel never returns a partial movie.

    Images are compressed in RAM. Numeric escape arrays and checked scenes are
    retained for coherent interaction/export after pausing. The budget estimates
    cache storage, not the total process RSS or temporary renderer allocations.
    """
    config.settings.validate()
    if not isinstance(config.frames, int) or not 64 <= config.frames <= 720:
        raise ValueError("Use 64 to 720 movie frames")
    if not 4 <= config.display_size <= 2048 or not 32 <= config.loop_size <= 512:
        raise ValueError("Invalid movie image dimensions")
    if config.frames*(12*config.settings.size**2+65536) > budget:
        raise ValueError("Movie cache budget exceeded; reduce frames or resolution")
    start = time.monotonic()
    _check(cancel)
    circle = parameter_circle(config.radius, frames=config.frames, dps=config.dps, cancel=cancel,
                              progress=(lambda value: progress(0.2*value)) if progress else None)
    frames, storage = [], 0
    # Closure is independently checked by parameter_circle. The duplicate
    # endpoint is omitted from playback to avoid a pause at the seam.
    for index, point in enumerate(circle.points[:-1]):
        _check(cancel)
        scene = scene_from_point(point, config.orbit, cancel)
        result = render(scene, config.view, config.settings, cancel,
                        (lambda value: progress(0.2+0.8*(index+0.7*value)/config.frames)) if progress else None,
                        mp_preview_size=96)
        loops, loop_png, status, raw_index, overlay = None, None, "", 0, None
        if config.include_loops:
            loops = resolved_forward_loops(scene, multiplier=config.loop_multiplier,
                                           boundary_radius=config.boundary_radius, cancel=cancel)
            count = len(loops.zero_source)-1
            raw_index = round(config.marker_turns*count)
            loop_png = pack_image(loop_image(loops, raw_index % count, config.loop_size))
            status = loop_text(scene, loops, raw_index)
            if config.show_loops:
                overlay = loops, raw_index % count, config.loop_group
        png = pack_image(compose(scene, result, config.overlays, config.mode,
                                 size=config.display_size, loops=overlay))
        storage += result.escaped_at.nbytes+result.magnitude.nbytes+len(png)+len(loop_png or b"")+65536
        if loops is not None:
            # Account conservatively for arbitrary-precision coordinates as well
            # as tuples and Python owners. Deep precision can be costly.
            storage += 6*len(loops.zero_source)*(512+point.ctx.prec//4)
        if storage > budget:
            raise ValueError("Movie cache budget exceeded; reduce frames, resolution or loops")
        frames.append(MovieFrame(scene, result, png, scene_text(scene, result), loops,
                                 loop_png, status, raw_index,
                                 point.ctx.nstr(point.t.real, point.ctx.dps-15),
                                 point.ctx.nstr(point.t.imag, point.ctx.dps-15)))
        _check(cancel)
        if progress:
            progress(0.2+0.8*(index+1)/config.frames)
    return Movie(config, circle, tuple(frames), time.monotonic()-start, storage)
