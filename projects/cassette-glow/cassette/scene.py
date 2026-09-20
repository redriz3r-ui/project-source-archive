"""Two rotating light fragments and an elastic ribbon between their hubs."""
from math import sin, cos, pi
from cassette import settings as S
from cassette.inputs import Envelope
from cassette.render import Canvas


class Scene:
    def __init__(self):
        self.canvas = Canvas()
        self.envelope = Envelope()
        self.phase = 0.0
        self.time = 0.0

    def reel(self, cx, phase, levels):
        radius = S.REEL_RADIUS + levels.bass * 0.22
        # Two unequal tapered arcs; no continuous ring outline.
        for offset, gain, color in ((0.0, 0.72, S.ROSE),
                                    (pi + 0.25, 0.34, S.AMBER)):
            for j in range(13):
                u = j / 12.0
                angle = phase + offset - u * 1.65
                strength = gain * (1.0 - u) ** 2 * (0.65 + levels.level)
                self.canvas.glow(cx + cos(angle) * radius,
                                 S.CENTER_Y + sin(angle) * radius,
                                 color, strength * 0.36)
            self.canvas.glow(cx + cos(phase + offset) * radius,
                             S.CENTER_Y + sin(phase + offset) * radius,
                             S.CREAM, 0.13 + levels.treble * 0.18)
        self.canvas.glow(cx, S.CENTER_Y, S.BURGUNDY, 0.16)

    def update(self, dt, target):
        dt = max(0.0, dt)
        self.time += dt
        levels = self.envelope.update(target, dt)
        self.phase = (self.phase + dt * S.ROTATION_SPEED *
                      (0.8 + levels.level * 0.5)) % (2.0 * pi)
        self.canvas.begin()
        self.reel(S.LEFT_X, self.phase, levels)
        self.reel(S.RIGHT_X, self.phase + 1.1, levels)
        span = S.RIGHT_X - S.LEFT_X
        amplitude = 0.45 + levels.bass * 1.25 + levels.mid * 1.05
        stretch = 1.05 + 0.22 * sin(self.time * 0.23)
        for j in range(int(span * 2) + 1):
            u = j / (span * 2.0)
            taper = sin(pi * u)  # pin the ribbon to both hubs
            wave = (sin(u * 2.0 * pi * stretch - self.time * 0.63) +
                    0.28 * sin(u * 3.0 * pi + self.time * 0.37)) / 1.28
            y = S.CENTER_Y + taper * amplitude * wave
            strength = (0.18 + levels.level * 0.22) * (0.6 + taper * 0.4)
            self.canvas.glow(S.LEFT_X + u * span, y, S.BURGUNDY, strength)
            self.canvas.point(S.LEFT_X + u * span, y, S.ROSE, strength * 0.28)
        self.canvas.persist(dt)
        return self.canvas
