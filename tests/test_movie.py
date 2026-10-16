"""Checked movie snapshots, cancellation, and coherent cached loop images."""

from dataclasses import replace
from threading import Event
import unittest

import numpy as np

from polynomial_cusps.drawing import compose
from polynomial_cusps.movie import MovieConfig, prepare_movie, unpack_image
from polynomial_cusps.rendering import RenderCancelled, RenderSettings, render


class MovieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MovieConfig(frames=64, dps=30, orbit=2, settings=RenderSettings(8, 4),
                                 display_size=32, loop_size=32)
        cls.movie = prepare_movie(cls.config)

    def test_cache_matches_checked_dynamics_and_independent_render(self):
        movie = self.movie
        self.assertEqual(len(movie.frames), 64)
        self.assertEqual(len(movie.circle.points), 65)
        self.assertEqual(movie.circle.points[0].t, movie.circle.points[-1].t)
        self.assertNotEqual(movie.frames[0].scene.point.t, movie.frames[-1].scene.point.t)
        for index in (0, 13, 37, 63):
            frame = movie.frames[index]
            self.assertTrue(frame.scene.point.diagnostics()["numerical_ok"])
            actual = render(frame.scene, movie.config.view, movie.config.settings)
            np.testing.assert_array_equal(actual.escaped_at, frame.result.escaped_at)
            np.testing.assert_array_equal(actual.magnitude, frame.result.magnitude)
            expected = compose(frame.scene, actual, movie.config.overlays, movie.config.mode, size=32)
            self.assertEqual(unpack_image(frame.png).tobytes(), expected.tobytes())
            self.assertEqual(frame.scene.free_orbit[1], frame.scene.point.f(frame.scene.point.omega))

    def test_cancel_during_rendering_and_budget_rejection_are_atomic(self):
        event, updates = Event(), []
        def progress(value):
            updates.append(value)
            if value > 0.22:
                event.set()
        with self.assertRaises(RenderCancelled):
            prepare_movie(self.config, cancel=event, progress=progress)
        self.assertGreater(updates[-1], 0.22)
        self.assertLess(updates[-1], 1)
        with self.assertRaisesRegex(ValueError, "budget"):
            prepare_movie(self.config, budget=100)
        with self.assertRaisesRegex(ValueError, "budget"):
            prepare_movie(self.config, budget=64*(12*8**2+65536)+1)

    def test_loop_movie_preserves_source_turns_and_both_images(self):
        movie = prepare_movie(replace(self.config, include_loops=True, marker_turns=1.25))
        for index in (0, 17, 63):
            frame = movie.frames[index]
            count = len(frame.loops.zero_source)-1
            self.assertEqual(frame.raw_index/count, 1.25)
            self.assertEqual(frame.loops.t, frame.scene.point.t)
            self.assertEqual(unpack_image(frame.loop_png).size, (96, 64))
            overlay = frame.loops, frame.raw_index % count, "both"
            expected = compose(frame.scene, frame.result, movie.config.overlays,
                               movie.config.mode, size=32, loops=overlay)
            self.assertEqual(unpack_image(frame.png).tobytes(), expected.tobytes())
            p = frame.scene.point
            z = frame.loops.source_scales[0]*frame.loops.zero_source[frame.raw_index % count]
            observed = (p.f(p.f(z))-frame.loops.second_center)/frame.loops.second_scales[0]
            self.assertLess(abs(observed-frame.loops.zero_second_image[frame.raw_index % count]), p.ctx.mpf("1e-25"))


if __name__ == "__main__":
    unittest.main()
