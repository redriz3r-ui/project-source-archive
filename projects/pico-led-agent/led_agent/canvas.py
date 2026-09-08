"""Small dependency-free RGB canvas shared by effects and simulator."""

from __future__ import annotations

from .scene import HEIGHT, WIDTH, parse_color


class Canvas:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT):
        self.width, self.height = width, height
        self.pixels = bytearray(width * height * 3)

    def clear(self, color=(0, 0, 0)) -> None:
        r, g, b = parse_color(color)
        self.pixels[:] = bytes((r, g, b)) * (self.width * self.height)

    def set(self, x: int, y: int, color, opacity: float = 1, blend: str = "alpha") -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        r, g, b = parse_color(color)
        i = (y * self.width + x) * 3
        old = self.pixels[i:i + 3]
        if blend == "replace":
            values = (r, g, b)
        elif blend == "add":
            values = tuple(min(255, old[n] + int(c * opacity)) for n, c in enumerate((r, g, b)))
        elif blend == "max":
            values = tuple(max(old[n], int(c * opacity)) for n, c in enumerate((r, g, b)))
        else:
            values = tuple(int(old[n] * (1 - opacity) + c * opacity) for n, c in enumerate((r, g, b)))
        self.pixels[i:i + 3] = bytes(values)

    def get(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.width + x) * 3
        return tuple(self.pixels[i:i + 3])

    def fade(self, amount: float) -> None:
        factor = max(0, min(1, 1 - amount))
        for i, value in enumerate(self.pixels):
            self.pixels[i] = int(value * factor)

    def copy(self) -> "Canvas":
        result = Canvas(self.width, self.height)
        result.pixels[:] = self.pixels
        return result

