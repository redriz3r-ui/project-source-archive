"""Normalized bass, mid, treble, overall level; no audio hardware required."""
from math import sin, pi, exp
from cassette import settings as S


def clamp(value):
    return max(0.0, min(1.0, value))


class Levels:
    def __init__(self):
        self.bass = self.mid = self.treble = self.level = 0.0

    def set(self, bass, mid, treble, level):
        self.bass = clamp(bass)
        self.mid = clamp(mid)
        self.treble = clamp(treble)
        self.level = clamp(level)


class DemoInput:
    """Imaginary slow R&B phrasing, not a simulated spectrum analyzer."""
    def __init__(self):
        self.levels = Levels()

    def sample(self, seconds):
        beat = (seconds * 72.0 / 60.0) % 1.0
        pulse = exp(-beat * 6.0)
        self.levels.set(
            0.16 + 0.45 * pulse,
            0.30 + 0.22 * sin(seconds * 0.59),
            0.10 + 0.12 * (0.5 + 0.5 * sin(seconds * 1.17)),
            0.34 + 0.12 * sin(seconds * 2.0 * pi / 9.0))
        return self.levels


class ExternalInput:
    """A future audio reader can call push(), then use this as the source."""
    def __init__(self):
        self.levels = Levels()

    def push(self, bass=0.0, mid=0.0, treble=0.0, level=0.0):
        self.levels.set(bass, mid, treble, level)

    def sample(self, seconds):
        return self.levels


class Envelope:
    def __init__(self):
        self.levels = Levels()

    def update(self, target, dt):
        for name in ('bass', 'mid', 'treble', 'level'):
            old = getattr(self.levels, name)
            value = clamp(getattr(target, name))
            tau = S.ATTACK_SECONDS if value > old else S.RELEASE_SECONDS
            alpha = 1.0 - exp(-dt / tau)
            setattr(self.levels, name, old + (value - old) * alpha)
        return self.levels
