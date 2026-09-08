import sys
import unittest
from pathlib import Path

PICO = Path(__file__).parents[1] / "pico_v2"
sys.path.insert(0, str(PICO))

from controls import Controls
from display import VirtualDisplay


class RecordingRuntime:
    def __init__(self):
        self.submissions = []
        self.stops = []

    def submit(self, scene, now):
        self.submissions.append((scene, now))

    def stop(self, clear=False):
        self.stops.append(clear)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.display = VirtualDisplay(brightness=.20)
        self.runtime = RecordingRuntime()
        self.controls = Controls(self.display, self.runtime, auto_brightness=False)

    def press(self, name, now=100):
        self.display.buttons[name] = True
        self.controls.tick(now)

    def release(self, name, now=110):
        self.display.buttons[name] = False
        self.controls.tick(now)

    def test_brightness_buttons_are_edge_triggered(self):
        self.press("SWITCH_BRIGHTNESS_UP")
        self.controls.tick(101)
        self.assertAlmostEqual(self.display.value, .25)
        self.release("SWITCH_BRIGHTNESS_UP")
        self.press("SWITCH_BRIGHTNESS_DOWN", 120)
        self.assertAlmostEqual(self.display.value, .20)

    def test_effect_buttons_submit_expected_scenes(self):
        expected = {
            "SWITCH_A": "rain",
            "SWITCH_B": "fire",
            "SWITCH_C": "eyes",
            "SWITCH_D": "plasma",
        }
        for index, (button, effect) in enumerate(expected.items()):
            self.press(button, index * 4000)
            scene, _ = self.runtime.submissions[-1]
            self.assertEqual(scene["steps"][0]["layers"][0]["effect"], effect)
            self.release(button, index * 4000 + 1)

    def test_sleep_stops_and_clears_once(self):
        self.press("SWITCH_SLEEP")
        self.controls.tick(101)
        self.assertEqual(self.runtime.stops, [True])

    def test_ambient_brightness_is_smoothed_and_clamped(self):
        controls = Controls(self.display, self.runtime, auto_brightness=True)
        self.display.light_value = 4095
        controls.tick(2000)
        self.assertAlmostEqual(self.display.value, .24)
        self.display.light_value = 99999
        controls.tick(4000)
        self.assertAlmostEqual(self.display.value, .272)


if __name__ == "__main__":
    unittest.main()
