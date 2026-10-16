# Prepared parameter-circle movies

The ordinary circle player solves the family before playback but renders
each dynamical frame in sequence. **Vuelta movie…** also prepares every
Julia image, free-critical orbit, overlay, diagnostic text and optional
loop inspector before enabling playback. Both modes follow t=r exp(i theta)
in the normalization; the dynamical source marker's angle is independent.

The movie controls are a separate small window, opened from **Parámetros**.
Defaults are 240 frames, 192×192 Julia samples and 30 fps, giving eight
seconds per turn. Displayed images are composed at the main canvas size
during preparation. Higher sampling or more frames increases preparation
time and storage. Parameter circles use 64–720 distinct frames plus an
independently solved closing endpoint. The duplicate endpoint does not
appear in playback, so the seam has no extra still frame.

Preparation runs in a cancellable numerical worker. Every family point
passes the existing portrait diagnostics and the circle closure check.
Frames use the current view, engine, precision, iteration budget, free-orbit
length, and visible layers. The existing finite-iteration and MP-preview
limitations still apply. The movie does not interpolate polynomials or
accelerate the near-parabolic time evolution.

With **Incluir lazos dinámicos**, preparation calculates the actual source,
first-image and second-image curves, including their adaptive winding
sampling. The marked point's accumulated turns are captured once; its
angle is preserved even when the loop sample count changes. The six-panel
inspector and its marked images are cached too. A loop-resolution failure
stops preparation explicitly rather than substituting an unchecked curve.

The complete movie becomes available atomically. Cancellation or a failed
frame leaves no playable partial cache and preserves the previously
displayed dynamical snapshot. Images are PNG-compressed in RAM; numerical
arrays, checked scenes and optional loop coordinates remain available for
interaction and export. The estimated cache budget is 512 MiB. It includes
an allowance for numerical objects, but is not a bound on total RSS, worker
temporaries, decoded images, or Tk allocations.

Playback only decodes and displays prepared images and assigns the matching
numerical snapshot. Parameter selection, diagnostics and the inspector
refer to that same f. There are no Newton solves, polynomial iterations,
Julia renders, or loop compositions on the playback path. A monotonic clock
determines the angular position; if displaying a frame is too slow, cached
frames can be skipped to maintain the requested speed. Requested fps is a
target rather than a hardware-independent guarantee.

Pause, step, scrub, repeat and change fps without rebuilding the movie.
Editing the dynamics pauses playback. Resuming restores the captured
settings; prepare again to include changed settings. Closing the loop
inspector pauses the movie, so it stays closed. Showing a cached frame
with loops again can reopen it. Closing the movie window releases its
cache and leaves the last numerical frame usable. Ctrl+Q in the movie
controls quits the app, following the shortcut rule for non-loop windows.

One development-machine check prepared 64 frames at 96×96 Julia samples,
64 iterations, 40 requested digits, 10 free-orbit steps and 150×150 loop panels
in about 16 seconds. Presenting cached frames in all windows took about
9 ms median and 11 ms at the 95th percentile; the 30 fps clock advanced 31
frames in a 1.1-second event-loop sample. These are configuration-specific
measurements, not timings promised on other machines.

Tests compare cached numerical arrays and pixels with independent rendering,
check source marker turns and actual second images, reject an exceeded cache
budget, cancel during preparation, and exercise real Tk playback while
rendering/composition entry points are patched to reject any recalculation.
