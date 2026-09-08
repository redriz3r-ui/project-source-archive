"""Canvas-to-canvas transition operators."""

from __future__ import annotations

import random

from .canvas import Canvas


def apply_transition(previous: Canvas, current: Canvas, progress: float, kind: str) -> Canvas:
    progress = max(0.0, min(1.0, progress))
    if kind == "cut" or progress >= 1:
        return current.copy()
    result = Canvas(current.width, current.height)
    if kind == "fade":
        for i, value in enumerate(current.pixels):
            result.pixels[i] = int(previous.pixels[i] * (1 - progress) + value * progress)
    elif kind == "wipe":
        edge = int(current.width * progress)
        for y in range(current.height):
            for x in range(current.width):
                source = current if x < edge else previous
                i = (y * current.width + x) * 3
                result.pixels[i:i + 3] = source.pixels[i:i + 3]
    elif kind == "dissolve":
        for y in range(current.height):
            for x in range(current.width):
                source = current if random.Random(x * 991 + y * 313).random() < progress else previous
                i = (y * current.width + x) * 3
                result.pixels[i:i + 3] = source.pixels[i:i + 3]
    elif kind == "glitch":
        amount = int((1 - progress) * 8)
        for y in range(current.height):
            shift = ((y * 7 + int(progress * 100)) % (amount * 2 + 1)) - amount if amount else 0
            source = current if y % 3 else previous
            for x in range(current.width):
                sx = max(0, min(current.width - 1, x + shift))
                si, di = (y * current.width + sx) * 3, (y * current.width + x) * 3
                result.pixels[di:di + 3] = source.pixels[si:si + 3]
    else:
        raise ValueError(f"unknown transition: {kind}")
    return result

