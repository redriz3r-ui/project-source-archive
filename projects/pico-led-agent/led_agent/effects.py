"""Parameterized effect plugins for the 53x11 renderer."""

from __future__ import annotations

import math
import random

from .scene import palette_colors


class Effect:
    def __init__(self, layer, seed=0):
        self.layer = layer
        self.rng = random.Random(seed)
        self.palette = palette_colors(layer)
        self.opacity = float(layer.get("opacity", 1))
        self.blend = layer.get("blend", "alpha")
        self.speed = float(layer.get("speed", 1))
        self.intensity = float(layer.get("intensity", .5))

    def dot(self, canvas, x, y, color):
        canvas.set(int(x), int(y), color, self.opacity, self.blend)


class Rain(Effect):
    def render(self, canvas, t):
        # Three apparent depths make the motion read as rain rather than noise.
        count = max(8, int(canvas.width * (.18 + self.intensity * .38)))
        for i in range(count):
            depth = 1 + i % 3
            travel = canvas.height + 3 + depth * 2
            y = int(t * self.speed * (4 + depth * 3) + i * 5.7) % travel - 4
            x = (i * 23 + i * i * 3 + int(t * self.speed * depth)) % canvas.width
            color = self.palette[1 + i % max(1, len(self.palette) - 1)]
            for tail in range(1 + depth):
                fade = 1 - tail / (2 + depth)
                self.dot(canvas, x - tail // 2, y - tail, tuple(int(v * fade) for v in color))


class Snow(Rain):
    def render(self, canvas, t):
        count = max(2, int(canvas.width * (.05 + self.intensity * .18)))
        for i in range(count):
            y = int(t * self.speed * (1 + i % 2) + i * 5) % (canvas.height + 2) - 1
            x = int(i * 13 + math.sin(t * self.speed + i) * 2) % canvas.width
            self.dot(canvas, x, y, self.palette[-1])


class Stars(Effect):
    def render(self, canvas, t):
        threshold = .86 - self.intensity * .25
        tick = int(t * self.speed * 5)
        for y in range(canvas.height):
            for x in range(canvas.width):
                n = random.Random(x * 991 + y * 313 + tick // 2).random()
                if n > threshold and (tick + x + y) % 3:
                    self.dot(canvas, x, y, self.palette[-1])


class Fireflies(Stars):
    def render(self, canvas, t):
        for i in range(max(2, int(3 + self.intensity * 12))):
            x = (i * 19 + math.sin(t * self.speed * .7 + i) * 7) % canvas.width
            y = (i * 5 + math.cos(t * self.speed + i * 2) * 3) % canvas.height
            pulse = (math.sin(t * 4 + i) + 1) / 2
            c = tuple(int(v * pulse) for v in self.palette[-1])
            self.dot(canvas, x, y, c)


class Waves(Effect):
    def render(self, canvas, t):
        for band in range(3):
            amplitude = .8 + self.intensity * (2.7 - band * .45)
            phase = t * self.speed * (2.4 + band * .35) + band * 1.8
            for x in range(canvas.width):
                y = 5 + band * 1.5 + math.sin(x * (.20 + band * .025) + phase) * amplitude
                color = self.palette[(band + 1) % len(self.palette)]
                self.dot(canvas, x, y, color)
                if band == 0: self.dot(canvas, x, y + 1, tuple(v // 3 for v in color))


class Scanner(Effect):
    def render(self, canvas, t):
        span = max(1, (canvas.width - 1) * 2)
        p = int(t * self.speed * 16) % span
        x = p if p < canvas.width else span - p
        for dx in range(-3, 4):
            color = tuple(int(c * (1 - abs(dx) / 4)) for c in self.palette[-1])
            for y in range(canvas.height):
                self.dot(canvas, x + dx, y, color)


class City(Effect):
    def render(self, canvas, t):
        ground = canvas.height - 1
        flicker=float(self.layer.get("window_flicker",.08))
        for x in range(canvas.width):
            height = 3 + ((x * 7 + x // 3) % 7)
            for y in range(ground - height, ground + 1):
                self.dot(canvas, x, y, self.palette[0])
            if x % 3 == 1:
                for y in range(ground - height + 1, ground, 2):
                    lit = random.Random(x * 101 + y * 17 + int(t * self.speed/max(.02,flicker))).random() > .35
                    if lit:
                        self.dot(canvas, x, y, self.palette[-1])


class Plasma(Effect):
    def render(self, canvas, t):
        for y in range(canvas.height):
            for x in range(canvas.width):
                v = (math.sin(x * .25 + t * self.speed) + math.sin(y * .65 - t * self.speed * .7) + 2) / 4
                self.dot(canvas, x, y, self.palette[min(len(self.palette) - 1, int(v * len(self.palette)))])


class Noise(Effect):
    def render(self, canvas, t):
        tick = int(t * self.speed * 8)
        for y in range(canvas.height):
            for x in range(canvas.width):
                if random.Random(x + y * canvas.width + tick * 65537).random() < self.intensity:
                    self.dot(canvas, x, y, self.palette[(x + y + tick) % len(self.palette)])


class Fire(Effect):
    def render(self, canvas, t):
        tick = int(t * self.speed * 12)
        for x in range(canvas.width):
            wave = (math.sin(x * .48 + t * self.speed * 5) + 1) * .5
            jitter = random.Random(x * 97 + tick // 2).random()
            height = 2 + int(self.intensity * 7 * (.6 * wave + .4 * jitter))
            for dy in range(height):
                index = min(len(self.palette) - 1, int((height - dy) / max(1, height) * len(self.palette)))
                self.dot(canvas, x, canvas.height - 1 - dy, self.palette[index])
        for ember in range(int(2 + self.intensity * 7)):
            x = (ember * 19 + tick * 3) % canvas.width
            y = canvas.height - 4 - ((tick + ember * 7) % 8)
            self.dot(canvas, x, y, self.palette[-1])


class Comet(Effect):
    def render(self, canvas, t):
        head = int(t * self.speed * 12) % (canvas.width + 12) - 6
        y = int(canvas.height / 2 + math.sin(t * self.speed) * 3)
        for tail in range(12):
            c = tuple(int(v * (1 - tail / 12)) for v in self.palette[-1])
            self.dot(canvas, head - tail, y, c)


class Lightning(Effect):
    def render(self, canvas, t):
        tick = int(t * self.speed * 5)
        if random.Random(tick).random() > self.intensity * .22:
            return
        x = random.Random(tick + 4).randrange(canvas.width)
        for y in range(canvas.height):
            x += random.Random(tick * 31 + y).choice((-1, 0, 1))
            self.dot(canvas, x, y, self.palette[-1])


class Eyes(Effect):
    def render(self, canvas, t):
        cycle = (t * self.speed) % 7
        blink = 5.55 < cycle < 5.82
        pupil = -3 if cycle < 1.8 else 3 if 2.4 < cycle < 4.2 else 0
        iris = self.palette[-1]
        white = tuple(max(70, min(255, v + 105)) for v in iris)
        for center in (14, 38):
            for x in range(center - 9, center + 10):
                dx = abs(x - center)
                half = 1 if dx > 7 else 2 if dx > 5 else 3
                if blink:
                    self.dot(canvas, x, 5, iris)
                    if dx < 7: self.dot(canvas, x, 6, tuple(v // 4 for v in iris))
                    continue
                for y in range(5 - half, 6 + half): self.dot(canvas, x, y, white)
            if not blink:
                px = center + pupil
                for y in range(3, 8):
                    for x in range(px - 2, px + 3):
                        if abs(x - px) + abs(y - 5) <= 3: self.dot(canvas, x, y, iris)
                self.dot(canvas, px, 5, (0, 0, 0))
                self.dot(canvas, px - 1, 4, (255, 255, 255))


class Heart(Effect):
    def render(self, canvas, t):
        scale = 1 if math.sin(t * self.speed * 5) > -.4 else .75
        cx, cy = canvas.width // 2, 5
        for y in range(-5, 5):
            for x in range(-6, 7):
                nx, ny = x / (5 * scale), -y / (5 * scale)
                if (nx * nx + ny * ny - 1) ** 3 - nx * nx * ny ** 3 <= 0:
                    self.dot(canvas, cx + x, cy + y, self.palette[-1])


class Particles(Effect):
    def render(self, canvas, t):
        for i in range(max(8, int(10 + self.intensity * 24))):
            life = (t * self.speed * (.45 + (i % 5) * .08) + i * .173) % 1
            angle = i * 2.399
            radius = life * (8 + self.intensity * 23)
            x = canvas.width / 2 + math.cos(angle) * radius
            y = canvas.height / 2 + math.sin(angle) * radius * .34
            color = tuple(int(v * (1 - life)) for v in self.palette[1 + i % max(1, len(self.palette)-1)])
            self.dot(canvas, x, y, color)


class Spectrum(Effect):
    def render(self, canvas, t):
        bars = 13
        for bar in range(bars):
            pulse = (math.sin(t * self.speed * (3.2 + bar * .11) + bar * 1.7) + 1) * .5
            height = 1 + int(pulse * (2 + self.intensity * 8))
            color = self.palette[1 + bar % max(1, len(self.palette)-1)]
            x0 = bar * 4 + 1
            for x in range(x0, min(x0 + 3, canvas.width)):
                for y in range(canvas.height - 1, canvas.height - 1 - height, -1): self.dot(canvas, x, y, color)


FONT = {
    " ": (0, 0, 0, 0, 0), "A": (30, 5, 5, 30, 0), "B": (31, 21, 21, 10, 0),
    "C": (14, 17, 17, 10, 0), "D": (31, 17, 17, 14, 0), "E": (31, 21, 21, 17, 0),
    "F": (31, 5, 5, 1, 0), "G": (14, 17, 21, 29, 0), "H": (31, 4, 4, 31, 0),
    "I": (17, 31, 17, 0, 0), "J": (8, 16, 16, 15, 0), "K": (31, 4, 10, 17, 0),
    "L": (31, 16, 16, 16, 0), "M": (31, 2, 4, 2, 31), "N": (31, 2, 4, 31, 0),
    "O": (14, 17, 17, 14, 0), "P": (31, 5, 5, 2, 0), "Q": (14, 17, 25, 30, 0),
    "R": (31, 5, 13, 18, 0), "S": (18, 21, 21, 9, 0), "T": (1, 1, 31, 1, 1),
    "U": (15, 16, 16, 15, 0), "V": (7, 8, 16, 8, 7), "W": (31, 8, 4, 8, 31),
    "X": (17, 10, 4, 10, 17), "Y": (1, 2, 28, 2, 1), "Z": (17, 25, 21, 19, 17),
    "0": (14, 17, 17, 14, 0), "1": (18, 31, 16, 0, 0), "2": (25, 21, 21, 18, 0),
    "3": (17, 21, 21, 10, 0), "4": (7, 4, 4, 31, 4), "5": (23, 21, 21, 9, 0),
    "6": (14, 21, 21, 8, 0), "7": (1, 1, 29, 3, 0), "8": (10, 21, 21, 10, 0),
    "9": (2, 21, 21, 14, 0), "'": (3, 0, 0, 0, 0), "!": (23, 0, 0, 0, 0),
    ":": (10, 0, 0, 0, 0), "-": (4, 4, 4, 0, 0), ".": (16, 0, 0, 0, 0),
}


class Text(Effect):
    def render(self, canvas, t):
        message = str(self.layer.get("text", "")).upper()
        width = sum(len(FONT.get(ch, FONT[" "])) + 1 for ch in message)
        x0 = canvas.width - int(t * self.speed * 10) % max(1, canvas.width + width)
        color = self.palette[-1]
        x = x0
        for char in message:
            columns = FONT.get(char, FONT[" "])
            for dx, bits in enumerate(columns):
                for dy in range(5):
                    if bits & (1 << dy):
                        self.dot(canvas, x + dx, 3 + dy, color)
            x += len(columns) + 1


class Icon(Effect):
    def render(self, canvas, t):
        name = self.layer.get("icon", "heart")
        delegate = Eyes(self.layer) if name == "eyes" else Heart(self.layer)
        delegate.render(canvas, t)


REGISTRY = {
    "rain": Rain, "snow": Snow, "fire": Fire, "plasma": Plasma,
    "noise": Noise, "stars": Stars, "fireflies": Fireflies,
    "particles": Particles, "comet": Comet, "waves": Waves,
    "scanner": Scanner, "city": City, "heart": Heart, "eyes": Eyes,
    "lightning": Lightning, "spectrum": Spectrum, "text": Text, "icon": Icon,
}


def create_effect(layer, seed=0):
    cls = REGISTRY.get(layer["effect"], Stars)
    return cls(layer, seed)
