"""Galactic Unicorn hardware boundary for the v2 RGB runtime."""

WIDTH, HEIGHT = 53, 11


class GalacticDisplay:
    def __init__(self, brightness=.18, max_brightness=.60):
        from galactic import GalacticUnicorn
        from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN
        self.GalacticUnicorn = GalacticUnicorn
        self.gu = GalacticUnicorn()
        self.graphics = PicoGraphics(display=DISPLAY_GALACTIC_UNICORN)
        self.max_brightness = max(0.05, min(1.0, float(max_brightness)))
        self.value = 0
        self.set_brightness(brightness)
        self._pens = {}

    def set_brightness(self, value):
        self.value = max(0.0, min(self.max_brightness, float(value)))
        self.gu.set_brightness(self.value)

    def adjust_brightness(self, delta):
        self.set_brightness(self.value + delta)

    def ambient_light(self):
        return self.gu.light()

    def pressed(self, name):
        constant = getattr(self.GalacticUnicorn, name)
        return self.gu.is_pressed(constant)

    def show(self, pixels):
        # Quantise to 16 levels/channel: bounded pen cache and visually smooth on LEDs.
        if len(self._pens) > 512:
            self._pens = {}
        for y in range(HEIGHT):
            for x in range(WIDTH):
                i = (y * WIDTH + x) * 3
                rgb = tuple((pixels[i + n] >> 4) * 17 for n in range(3))
                pen = self._pens.get(rgb)
                if pen is None:
                    pen = self.graphics.create_pen(*rgb)
                    self._pens[rgb] = pen
                self.graphics.set_pen(pen)
                self.graphics.pixel(x, y)
        self.gu.update(self.graphics)

    def clear(self):
        self.show(bytearray(WIDTH * HEIGHT * 3))

    def cue(self, frequency=660):
        channel=self.gu.synth_channel(0)
        channel.play_tone(frequency,volume=.08,attack=.01,release=.08)
        self.gu.play_synth()


class VirtualDisplay:
    def __init__(self, brightness=.18, max_brightness=.60):
        self.value = brightness
        self.max_brightness = max_brightness
        self.pixels = bytearray(WIDTH * HEIGHT * 3)
        self.buttons = {}
        self.light_value = 2048

    def set_brightness(self, value):
        self.value = max(0, min(self.max_brightness, float(value)))

    def adjust_brightness(self, delta): self.set_brightness(self.value + delta)
    def ambient_light(self): return self.light_value
    def pressed(self, name): return self.buttons.get(name, False)
    def show(self, pixels): self.pixels[:] = pixels
    def clear(self): self.pixels[:] = bytes(len(self.pixels))
    def cue(self, frequency=660): pass
