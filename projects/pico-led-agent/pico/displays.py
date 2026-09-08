"""Minimal display drivers. Coordinates are always x=0..7, y=0..7."""


class VirtualDisplay:
    def __init__(self, **_kwargs):
        self.rows = [0] * 8

    def brightness(self, _value):
        pass

    def show_rows(self, rows):
        self.rows[:] = rows

    def clear(self):
        self.show_rows([0] * 8)


class GalacticDisplay:
    """Pimoroni Galactic Unicorn's built-in 53x11 RGB matrix."""

    width = 53
    height = 11

    def __init__(self, brightness=3, color=(40, 180, 255), **_kwargs):
        from galactic import GalacticUnicorn
        from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN

        self.gu = GalacticUnicorn()
        self.graphics = PicoGraphics(display=DISPLAY_GALACTIC_UNICORN)
        self.black = self.graphics.create_pen(0, 0, 0)
        self.color = self.graphics.create_pen(*color)
        self.brightness(brightness)
        self.clear()

    def brightness(self, value):
        self.gu.set_brightness(max(0, min(15, int(value))) / 15.0)

    def _blank(self):
        self.graphics.set_pen(self.black)
        self.graphics.clear()
        self.graphics.set_pen(self.color)

    def show_rows(self, rows):
        self._blank()
        left = (self.width - 8) // 2
        top = (self.height - 8) // 2
        for y in range(8):
            for x in range(8):
                if rows[y] & (1 << (7 - x)):
                    self.graphics.pixel(left + x, top + y)
        self.gu.update(self.graphics)

    def text_width(self, text):
        return self.graphics.measure_text(text, 1)

    def show_text(self, text, x):
        self._blank()
        self.graphics.text(text, int(x), 2, scale=1)
        self.gu.update(self.graphics)

    def clear(self):
        self._blank()
        self.gu.update(self.graphics)


class MAX7219Display:
    _NOOP = 0
    _DECODE = 9
    _INTENSITY = 10
    _SCAN_LIMIT = 11
    _SHUTDOWN = 12
    _DISPLAY_TEST = 15

    def __init__(self, spi_id, pin_sck, pin_mosi, pin_cs, brightness=3,
                 rotation=0, flip_x=False, flip_y=False):
        from machine import Pin, SPI

        self.spi = SPI(spi_id, baudrate=10_000_000, polarity=0, phase=0,
                       sck=Pin(pin_sck), mosi=Pin(pin_mosi))
        self.cs = Pin(pin_cs, Pin.OUT, value=1)
        self.rotation = rotation
        self.flip_x = flip_x
        self.flip_y = flip_y
        self._write(self._DISPLAY_TEST, 0)
        self._write(self._SCAN_LIMIT, 7)
        self._write(self._DECODE, 0)
        self.brightness(brightness)
        self._write(self._SHUTDOWN, 1)
        self.clear()

    def _write(self, register, value):
        self.cs(0)
        self.spi.write(bytes((register, value)))
        self.cs(1)

    def brightness(self, value):
        self._write(self._INTENSITY, max(0, min(15, int(value))))

    def _transform(self, x, y):
        if self.flip_x:
            x = 7 - x
        if self.flip_y:
            y = 7 - y
        if self.rotation == 90:
            x, y = 7 - y, x
        elif self.rotation == 180:
            x, y = 7 - x, 7 - y
        elif self.rotation == 270:
            x, y = y, 7 - x
        return x, y

    def show_rows(self, rows):
        output = [0] * 8
        for y in range(8):
            for x in range(8):
                if rows[y] & (1 << (7 - x)):
                    tx, ty = self._transform(x, y)
                    output[ty] |= 1 << (7 - tx)
        for row, value in enumerate(output, 1):
            self._write(row, value)

    def clear(self):
        self.show_rows([0] * 8)


def create(config):
    driver = getattr(config, "DISPLAY_DRIVER", "virtual").lower()
    if driver == "virtual":
        return VirtualDisplay()
    if driver == "galactic":
        return GalacticDisplay(
            brightness=getattr(config, "BRIGHTNESS", 3),
            color=getattr(config, "COLOR", (40, 180, 255)),
        )
    if driver == "max7219":
        return MAX7219Display(
            spi_id=config.SPI_ID, pin_sck=config.PIN_SCK,
            pin_mosi=config.PIN_MOSI, pin_cs=config.PIN_CS,
            brightness=getattr(config, "BRIGHTNESS", 3),
            rotation=getattr(config, "ROTATION", 0),
            flip_x=getattr(config, "FLIP_X", False),
            flip_y=getattr(config, "FLIP_Y", False),
        )
    raise ValueError("unknown DISPLAY_DRIVER: " + driver)
