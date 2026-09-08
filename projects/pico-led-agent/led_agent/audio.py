"""Computer-side audio analysis and 53x11 spectrum/beat rendering."""

from __future__ import annotations

import math
from collections import deque

from .canvas import Canvas
from .scene import PALETTES, parse_color


class AudioAnalyzer:
    """Dependency-free analyzer core; microphone adapters only need to call ingest()."""

    def __init__(self, sample_rate=44100, bands=16):
        self.sample_rate, self.bands = sample_rate, bands
        self.history = deque(maxlen=24)

    def analyze(self, samples) -> dict:
        values = [float(x) for x in samples]
        if not values:
            return {"bands": [0.0] * self.bands, "beat": 0.0, "energy": 0.0}
        peak = max(1.0, max(abs(x) for x in values))
        values = [x / peak for x in values]
        # Log-spaced Goertzel bins are efficient enough for small callback windows.
        output = []
        for index in range(self.bands):
            frequency = 55 * ((12000 / 55) ** (index / max(1, self.bands - 1)))
            omega = 2 * math.pi * frequency / self.sample_rate
            coefficient = 2 * math.cos(omega)
            q1 = q2 = 0.0
            for sample in values:
                q0 = coefficient * q1 - q2 + sample
                q2, q1 = q1, q0
            power = max(0.0, q1 * q1 + q2 * q2 - coefficient * q1 * q2)
            output.append(math.sqrt(power) / max(1, len(values)) * 8)
        energy = sum(x * x for x in values) / len(values)
        average = sum(self.history) / len(self.history) if self.history else energy
        beat = max(0.0, min(1.0, (energy / max(.0001, average) - 1.15) / 1.5))
        self.history.append(energy)
        maximum = max(.001, max(output))
        return {"bands": [min(1.0, x / maximum) for x in output], "beat": beat, "energy": energy}


class SpectrumRenderer:
    def __init__(self, palette="cyberpunk"):
        values = PALETTES.get(palette, PALETTES["cyberpunk"])
        self.colors = [parse_color(value) for value in values]

    def render(self, analysis: dict) -> Canvas:
        canvas = Canvas(); canvas.clear(self.colors[0])
        bands = analysis.get("bands", [])
        if not bands:
            return canvas
        for x in range(canvas.width):
            value = bands[min(len(bands) - 1, int(x * len(bands) / canvas.width))]
            height = int(value * canvas.height)
            for y in range(canvas.height - height, canvas.height):
                color_index = min(len(self.colors) - 1, int((canvas.height - y) / canvas.height * len(self.colors)))
                canvas.set(x, y, self.colors[color_index], blend="replace")
        if analysis.get("beat", 0) > .65:
            for x in range(canvas.width): canvas.set(x, 0, self.colors[-1], blend="replace")
        return canvas


class MicrophoneSource:
    """Optional adapter loaded only when live audio is explicitly requested."""

    def __init__(self, callback, sample_rate=44100, blocksize=1024):
        try:
            import sounddevice
        except ImportError as exc:
            raise RuntimeError("live audio needs: pip install -e '.[audio]'") from exc
        def receive(data, _frames, _time, status):
            samples=memoryview(data).cast("h")
            callback(samples,status)
        try:
            self._stream = sounddevice.RawInputStream(
                samplerate=sample_rate, blocksize=blocksize, channels=1,dtype="int16",
                callback=receive,
            )
        except Exception as exc:
            raise RuntimeError(f"could not open microphone: {exc}") from exc

    def __enter__(self): self._stream.start(); return self
    def __exit__(self, *_args): self._stream.stop(); self._stream.close()
