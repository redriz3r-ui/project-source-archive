"""A finite, opt-in sequence of existing bounded automation patterns."""

from dataclasses import dataclass
from enum import StrEnum

from app.triggers.patterns import Pattern


class SessionPhase(StrEnum):
    OPENING = "OPENING"
    MIDDLE = "MIDDLE"
    BUILDUP = "BUILDUP"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class SessionSettings:
    opening_pulses: int = 2
    middle_pulses: int = 4
    buildup_pulses: int = 3
    include_buildup: bool = False

    def validate(self) -> None:
        values = (self.opening_pulses, self.middle_pulses, self.buildup_pulses)
        if any(type(value) is not int or not 1 <= value <= 20 for value in values):
            raise ValueError("Each session phase must contain 1–20 bounded pulses")
        if self.total_pulses > 40:
            raise ValueError("A session may contain at most 40 bounded pulses")

    @property
    def total_pulses(self) -> int:
        return self.opening_pulses + self.middle_pulses + (
            self.buildup_pulses if self.include_buildup else 0
        )


@dataclass(frozen=True, slots=True)
class SessionStep:
    phase: SessionPhase
    pattern: Pattern
    intensity_fraction: float


def step_for(settings: SessionSettings, completed_pulses: int) -> SessionStep | None:
    """Select a step by completed pulses, never by inferred physiology."""
    settings.validate()
    if completed_pulses < 0:
        raise ValueError("Completed pulse count cannot be negative")
    if completed_pulses < settings.opening_pulses:
        return SessionStep(SessionPhase.OPENING, Pattern.GENTLE_PULSE, 0.5)
    if completed_pulses < settings.opening_pulses + settings.middle_pulses:
        return SessionStep(SessionPhase.MIDDLE, Pattern.RHYTHMIC_PULSE, 0.75)
    if settings.include_buildup and completed_pulses < settings.total_pulses:
        return SessionStep(SessionPhase.BUILDUP, Pattern.GRADUAL_RAMP, 1.0)
    return None
