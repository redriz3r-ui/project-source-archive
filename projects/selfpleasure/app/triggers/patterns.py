"""Pure, bounded vibration envelopes. A preview never talks to a device."""

from dataclasses import asdict, dataclass
from enum import StrEnum
import math


class Pattern(StrEnum):
    SHORT_PULSE = "SHORT_PULSE"
    GENTLE_PULSE = "GENTLE_PULSE"
    RHYTHMIC_PULSE = "RHYTHMIC_PULSE"
    GRADUAL_RAMP = "GRADUAL_RAMP"


@dataclass(frozen=True, slots=True)
class PatternStep:
    intensity: float
    duration: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


_ENVELOPES: dict[Pattern, tuple[tuple[float, float], ...]] = {
    Pattern.SHORT_PULSE: ((1.0, 1.0),),
    Pattern.GENTLE_PULSE: ((0.4, 0.28), (0.0, 0.12), (0.55, 0.28),
                           (0.0, 0.12), (0.4, 0.20)),
    Pattern.RHYTHMIC_PULSE: ((0.7, 0.18), (0.0, 0.07), (0.7, 0.18),
                             (0.0, 0.07), (0.7, 0.18), (0.0, 0.07),
                             (0.7, 0.18), (0.0, 0.07)),
    Pattern.GRADUAL_RAMP: ((0.25, 0.25), (0.45, 0.25),
                            (0.7, 0.25), (1.0, 0.25)),
}


def build_pattern(pattern: Pattern | str, intensity: float, duration: float,
                  max_intensity: float = 0.5) -> tuple[PatternStep, ...]:
    """Return positive-duration steps within the fixed activation deadline."""
    try:
        selected = Pattern(pattern)
    except ValueError as exc:
        raise ValueError("Unsupported vibration pattern") from exc
    if not all(math.isfinite(value) for value in (intensity, duration, max_intensity)):
        raise ValueError("Pattern settings must be finite")
    if not (0 < intensity <= min(max_intensity, 0.5) and 0 < duration <= 2.0):
        raise ValueError("Pattern exceeds conservative intensity or duration limits")
    envelope = _ENVELOPES[selected]
    total_weight = sum(weight for _, weight in envelope)
    return tuple(PatternStep(intensity * level, duration * weight / total_weight)
                 for level, weight in envelope)
