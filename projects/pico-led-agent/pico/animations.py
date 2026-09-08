import random
import time

EYES_OPEN = [0x00, 0x00, 0x66, 0x66, 0x00, 0x00, 0x00, 0x00]
EYES_HALF = [0x00, 0x00, 0x00, 0x66, 0x00, 0x00, 0x00, 0x00]
BLANK = [0] * 8
HEART_BIG = [0x00, 0x66, 0xFF, 0xFF, 0x7E, 0x3C, 0x18, 0x00]
HEART_SMALL = [0x00, 0x00, 0x24, 0x7E, 0x3C, 0x18, 0x00, 0x00]


class Player:
    def __init__(self, display):
        self.display = display
        self.mode = "stop"
        self.name = None
        self.speed = 1.0
        self.next_tick = 0
        self.frame = 0
        self.rows = [0] * 8
        self.drops = []
        self.text = ""
        self.scroll_x = 8

    def play(self, name, speed=None):
        self.mode = "play"
        self.name = name
        if speed is not None:
            self.speed = max(0.25, min(4.0, float(speed)))
        self.frame = 0
        self.drops = []
        self.next_tick = 0

    def scroll(self, text, speed=None):
        self.mode = "scroll"
        self.text = text
        self.scroll_x = getattr(self.display, "width", 8)
        if speed is not None:
            self.speed = max(0.25, min(4.0, float(speed)))
        self.next_tick = 0

    def stop(self, clear=False):
        self.mode = "stop"
        if clear:
            self.rows = [0] * 8
            self.display.show_rows(self.rows)

    def tick(self):
        now = time.ticks_ms()
        if self.mode == "stop" or time.ticks_diff(now, self.next_tick) < 0:
            return
        delay = 180
        if self.mode == "scroll":
            self._scroll_frame()
            delay = 110
        elif self.name == "eyes":
            sequence = (EYES_OPEN, EYES_OPEN, EYES_OPEN, EYES_HALF, BLANK, EYES_HALF)
            self.rows = sequence[self.frame % len(sequence)]
            self.frame += 1
            delay = 260
        elif self.name == "heart":
            self.rows = HEART_BIG if self.frame % 2 == 0 else HEART_SMALL
            self.frame += 1
            delay = 420
        elif self.name == "rain":
            self._rain_frame()
            delay = 130
        elif self.name == "twinkle":
            self.rows = [random.getrandbits(8) & random.getrandbits(8) for _ in range(8)]
            delay = 180
        if self.mode != "scroll" or not hasattr(self.display, "show_text"):
            self.display.show_rows(self.rows)
        self.next_tick = time.ticks_add(now, int(delay / self.speed))

    def _rain_frame(self):
        self.drops = [(x, y + 1) for x, y in self.drops if y < 7]
        if random.getrandbits(2):
            self.drops.append((random.getrandbits(3), 0))
        self.rows = [0] * 8
        for x, y in self.drops:
            self.rows[y] |= 1 << (7 - x)

    def _scroll_frame(self):
        if hasattr(self.display, "show_text"):
            self.display.show_text(self.text, self.scroll_x)
            self.scroll_x -= 1
            if self.scroll_x < -self.display.text_width(self.text):
                self.scroll_x = self.display.width
            return
        # MicroPython's built-in 8x8 font keeps firmware small.
        import framebuf
        buffer = bytearray(8)
        canvas = framebuf.FrameBuffer(buffer, 8, 8, framebuf.MONO_HLSB)
        canvas.fill(0)
        canvas.text(self.text, self.scroll_x, 0, 1)
        # MONO_HLSB stores one byte per row with x=0 in the low bit.
        self.rows = [_reverse_byte(value) for value in buffer]
        self.scroll_x -= 1
        if self.scroll_x < -(len(self.text) * 8):
            self.scroll_x = 8


def _reverse_byte(value):
    result = 0
    for bit in range(8):
        result |= ((value >> bit) & 1) << (7 - bit)
    return result
