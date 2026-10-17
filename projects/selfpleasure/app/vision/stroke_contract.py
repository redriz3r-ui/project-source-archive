"""Versioned, device-neutral numeric contracts for the future Hand Stroke mode.

Coordinates are calibrated to the object's movement axis: 0 is one endpoint
and 1 is the other. Speed is axis lengths per second; travel is axis lengths
since the current stroke began. Timestamps use a monotonic nanosecond clock.
No image data or device command belongs in this module.
"""

from dataclasses import dataclass
from enum import StrEnum
import math


STROKE_SCHEMA_VERSION = 1


class StrokeDirection(StrEnum):
    FORWARD = "FORWARD"
    REVERSE = "REVERSE"
    STILL = "STILL"
    UNKNOWN = "UNKNOWN"


class StrokeEventKind(StrEnum):
    STARTED = "stroke_started"
    UPDATED = "stroke_updated"
    COMPLETED = "stroke_completed"
    TRACKING_LOST = "tracking_lost"


@dataclass(frozen=True, slots=True)
class StrokeObservation:
    schema_version: int
    timestamp_ns: int
    frame_id: int
    hand_position: float | None
    direction: StrokeDirection
    speed: float
    travel: float
    tracking_confidence: float
    stroke_id: int | None

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != STROKE_SCHEMA_VERSION:
            raise ValueError("Unsupported stroke observation schema version")
        if type(self.timestamp_ns) is not int or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative monotonic integer")
        if type(self.frame_id) is not int or self.frame_id < 1:
            raise ValueError("frame_id must be a positive integer")
        if self.hand_position is not None and not _unit_interval(self.hand_position):
            raise ValueError("hand_position must be normalized to 0–1")
        if not isinstance(self.direction, StrokeDirection):
            raise ValueError("Unknown stroke direction")
        if not _nonnegative(self.speed) or not _nonnegative(self.travel):
            raise ValueError("speed and travel must be non-negative finite numbers")
        if not _unit_interval(self.tracking_confidence):
            raise ValueError("tracking_confidence must be in 0–1")
        if self.stroke_id is not None and (type(self.stroke_id) is not int or self.stroke_id < 1):
            raise ValueError("stroke_id must be a positive integer when present")


@dataclass(frozen=True, slots=True)
class StrokeEvent(StrokeObservation):
    kind: StrokeEventKind

    def __post_init__(self) -> None:
        StrokeObservation.__post_init__(self)
        if not isinstance(self.kind, StrokeEventKind):
            raise ValueError("Unknown stroke event kind")
        if self.kind != StrokeEventKind.TRACKING_LOST and (
            self.stroke_id is None or self.hand_position is None
        ):
            raise ValueError("A stroke event needs an ID and calibrated hand position")


def _nonnegative(value: float) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _unit_interval(value: float) -> bool:
    return _nonnegative(value) and value <= 1
