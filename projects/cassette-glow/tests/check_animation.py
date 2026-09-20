"""Run on a desktop: python3 tests/check_animation.py (standard library only)."""
import math
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from cassette.render import Canvas
from cassette.scene import Scene
from cassette.inputs import DemoInput, ExternalInput, Envelope, Levels


class AnimationChecks(unittest.TestCase):
    def test_subpixel_energy(self):
        c = Canvas()
        c.point(10.25, 4.5, (100, 0, 0), 1.0)
        self.assertAlmostEqual(sum(c.light), 100)
        self.assertAlmostEqual(c.light[(4 * 53 + 10) * 3], 37.5)
        self.assertAlmostEqual(c.light[(5 * 53 + 11) * 3], 12.5)

    def test_trails_independent_of_frame_rate(self):
        results = []
        for fps in (20, 40, 60):
            c = Canvas()
            c.point(10, 5, (100, 0, 0), 1)
            c.persist(0)
            c.begin()
            for _ in range(fps):
                c.persist(1 / fps)
            results.append(c.history[(5 * 53 + 10) * 3])
        self.assertLess(max(results) - min(results), 0.001)
        self.assertTrue(0 < results[0] < 100)

    def test_input_clamping_and_smoothing(self):
        source = ExternalInput()
        source.push(-1, 2, 0.5, 1)
        target = source.sample(0)
        self.assertEqual((target.bass, target.mid), (0, 1))
        level = Envelope().update(target, 0.025).level
        self.assertTrue(0 < level < 1)

    def test_one_minute_and_silence(self):
        scene, source = Scene(), DemoInput()
        for frame in range(2400):
            canvas = scene.update(0.025, source.sample(frame / 40))
            self.assertTrue(all(math.isfinite(v) and v >= 0 for v in canvas.history))
        rgb = [canvas.rgb(i) for i in range(53 * 11)]
        self.assertTrue(all(0 <= v <= 255 for pixel in rgb for v in pixel))
        self.assertLess(sum(max(p) > 30 for p in rgb), 120)
        for _ in range(40):
            scene.update(0.025, Levels())


if __name__ == '__main__':
    unittest.main()
