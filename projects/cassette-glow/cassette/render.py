"""Reusable RGB buffers, bilinear light splats and time-based persistence."""
from array import array
from math import floor, exp
from cassette import settings as S


class Canvas:
    def __init__(self):
        self.width, self.height = S.WIDTH, S.HEIGHT
        size = self.width * self.height * 3
        self.light = array('f', [0.0] * size)
        self.history = array('f', [0.0] * size)

    def begin(self):
        for i in range(len(self.light)):
            self.light[i] = 0.0

    def point(self, x, y, color, strength):
        """Distribute a floating-point position across its four neighbors."""
        ix, iy = int(floor(x)), int(floor(y))
        fx, fy = x - ix, y - iy
        for oy in range(2):
            py = iy + oy
            if not 0 <= py < self.height:
                continue
            wy = fy if oy else 1.0 - fy
            for ox in range(2):
                px = ix + ox
                if not 0 <= px < self.width:
                    continue
                wx = fx if ox else 1.0 - fx
                weight = strength * wx * wy
                index = (py * self.width + px) * 3
                for c in range(3):
                    self.light[index + c] += color[c] * weight

    def glow(self, x, y, color, strength):
        self.point(x, y, color, strength)
        # A sparse cross-shaped halo, kept much dimmer than the core.
        self.point(x - 0.85, y, color, strength * 0.10)
        self.point(x + 0.85, y, color, strength * 0.10)
        self.point(x, y - 0.85, color, strength * 0.10)
        self.point(x, y + 0.85, color, strength * 0.10)

    def persist(self, dt):
        decay = exp(-dt / S.TRAIL_SECONDS)
        for i in range(len(self.light)):
            # Peak-hold decay avoids repeated accumulation washing out the scene.
            self.history[i] = max(self.light[i], self.history[i] * decay)

    def rgb(self, pixel):
        i = pixel * 3
        return tuple(min(255, int(self.history[i + c] + S.BACKGROUND[c] + 0.5))
                     for c in range(3))

    def show(self, graphics):
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self.rgb(y * self.width + x)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)
