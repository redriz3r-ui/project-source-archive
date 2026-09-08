"""Layered, deterministic scene renderer."""

from __future__ import annotations

from .canvas import Canvas
from .effects import create_effect
from .scene import parse_color, validate_scene
from .transitions import apply_transition


class SceneRenderer:
    def __init__(self, scene):
        self.scene = validate_scene(scene)
        self.canvas = Canvas()
        self._effects = [
            [create_effect(layer, seed=si * 101 + li) for li, layer in enumerate(step["layers"])]
            for si, step in enumerate(self.scene["steps"])
        ]
        self.total_duration = sum(float(step["duration"]) for step in self.scene["steps"])

    def render(self, elapsed: float) -> Canvas:
        if self.scene["loop"]:
            elapsed %= self.total_duration
        else:
            elapsed = min(elapsed, self.total_duration - .0001)
        offset = 0.0
        index = len(self.scene["steps"]) - 1
        for i, step in enumerate(self.scene["steps"]):
            if elapsed < offset + float(step["duration"]):
                index = i
                break
            offset += float(step["duration"])
        local_time = elapsed - offset
        self._render_step(index, local_time, self.canvas)
        transition = self.scene["transition"]
        duration = float(transition.get("duration", 0))
        if index > 0 and duration > 0 and local_time < duration:
            previous = Canvas()
            previous_duration = float(self.scene["steps"][index - 1]["duration"])
            self._render_step(index - 1, previous_duration, previous)
            self.canvas = apply_transition(previous, self.canvas, local_time / duration, transition["type"])
        return self.canvas

    def _render_step(self, index, local_time, canvas):
        canvas.clear(parse_color(self.scene["background"]))
        for effect in self._effects[index]:
            effect.render(canvas, local_time)
