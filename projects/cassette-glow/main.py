"""Copy main.py and cassette/ to the board root; run in Thonny."""
import gc
import time
from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN
from cassette import settings as S
from cassette.inputs import DemoInput
from cassette.scene import Scene


def run():
    gu = GalacticUnicorn()
    graphics = PicoGraphics(DISPLAY_GALACTIC_UNICORN)
    gu.set_brightness(S.BRIGHTNESS)
    source = DemoInput()
    scene = Scene()
    frame_ms = max(1, int(1000 / S.FPS))
    previous = time.ticks_ms()
    elapsed = 0.0
    gc.collect()
    try:
        while True:
            start = time.ticks_ms()
            dt = time.ticks_diff(start, previous) / 1000.0
            previous = start
            # A debugger pause should not jump the visual forward several seconds.
            dt = min(dt, 0.1)
            elapsed += dt
            canvas = scene.update(dt, source.sample(elapsed))
            canvas.show(graphics)
            gu.update(graphics)
            remaining = frame_ms - time.ticks_diff(time.ticks_ms(), start)
            if remaining > 0:
                time.sleep_ms(remaining)
    finally:
        gu.clear()


if __name__ == '__main__':
    run()
