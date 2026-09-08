"""ANSI true-colour terminal preview for the exact 53x11 canvas."""

from __future__ import annotations

import sys
import time

from .renderer import SceneRenderer


def frame_text(canvas) -> str:
    rows = []
    for y in range(canvas.height):
        row = []
        for x in range(canvas.width):
            r, g, b = canvas.get(x, y)
            row.append(f"\x1b[48;2;{r};{g};{b}m  ")
        rows.append("".join(row) + "\x1b[0m")
    return "\n".join(rows)


def preview(scene, seconds=5, fps=10, stream=sys.stdout):
    renderer = SceneRenderer(scene)
    start = time.monotonic()
    first = True
    while time.monotonic() - start < seconds:
        elapsed = time.monotonic() - start
        frame = frame_text(renderer.render(elapsed))
        if not first:
            stream.write(f"\x1b[{renderer.canvas.height}A")
        stream.write(frame + "\n")
        stream.flush()
        first = False
        time.sleep(1 / fps)

