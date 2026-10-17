"""Temporal, heuristic interaction states. No device control imports."""

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import atan2, degrees, hypot

from app.vision.calibration import Calibration
from app.vision.object_tracker import ObjectObservation
from app.vision.service import FaceObservation


class InteractionState(StrEnum):
    NO_FACE = "NO_FACE"
    NO_OBJECT = "NO_OBJECT"
    OBJECT_VISIBLE = "OBJECT_VISIBLE"
    OBJECT_APPROACHING = "OBJECT_APPROACHING"
    POSSIBLE_INTERACTION = "POSSIBLE_INTERACTION"
    INTERACTION_ACTIVE = "INTERACTION_ACTIVE"
    INTERACTION_ENDED = "INTERACTION_ENDED"
    TRACKING_LOST = "TRACKING_LOST"


@dataclass(frozen=True, slots=True)
class InteractionEstimate:
    state: InteractionState = InteractionState.NO_FACE
    confidence: float = 0.0
    distance_mouth_widths: float | None = None
    bearing_degrees: float | None = None
    evidence_frames: int = 0


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    sequence: int
    timestamp: str
    state: InteractionState
    previous_state: InteractionState
    confidence: float
    distance_mouth_widths: float | None
    mouth: tuple[float, float] | None
    object: tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class _Evidence:
    timestamp: float
    distance: float
    relative_x: float
    relative_y: float
    near: bool
    moving: bool


class InteractionEstimator:
    """Conservative state machine using proximity, motion, and dwell time.

    Confidence is an uncalibrated detection score; it does not assert contact.
    """

    def __init__(self) -> None:
        self.estimate = InteractionEstimate()
        self._history: deque[_Evidence] = deque()
        self._last_seen_face = False
        self._last_seen_object = False
        self._loss_started: float | None = None
        self._far_frames = 0
        self._ended_at: float | None = None
        self._previous_timestamp: float | None = None
        self._previous_relative: tuple[float, float] | None = None

    def reset(self) -> None:
        self.__init__()

    def update(
        self, face: FaceObservation, obj: ObjectObservation,
        timestamp: float, config: Calibration,
    ) -> InteractionEstimate:
        previous_state = self.estimate.state
        face_ok = bool(face.face_detected and face.mouth_detected and
                       face.mouth_x is not None and face.mouth_y is not None and
                       face.mouth_width and face.tracking_quality >= 0.4)
        object_ok = bool(obj.detected and obj.x is not None and obj.y is not None and
                         obj.tracking_quality >= 0.2)
        if not face_ok or not object_ok:
            missing_state = InteractionState.NO_FACE if not face_ok else InteractionState.NO_OBJECT
            had_tracking = (self._last_seen_face and self._last_seen_object) or previous_state == InteractionState.TRACKING_LOST
            if self._loss_started is None:
                self._loss_started = timestamp
            self._history.clear()
            self._far_frames = 0
            self._previous_relative = None
            if had_tracking and timestamp - self._loss_started < 0.6:
                state = InteractionState.TRACKING_LOST
            else:
                state = missing_state
            self._last_seen_face = face_ok
            self._last_seen_object = object_ok
            self.estimate = InteractionEstimate(state=state)
            return self.estimate

        self._last_seen_face = True
        self._last_seen_object = True
        self._loss_started = None
        assert face.mouth_x is not None and face.mouth_y is not None and face.mouth_width is not None
        assert obj.x is not None and obj.y is not None
        # Both points use normalized image coordinates. Convert Y to the same
        # pixel/mouth-width scale as X; otherwise 4:3 frames overstate vertical
        # separation by one third (and other aspect ratios by still more).
        mouth_width = max(face.mouth_width, 0.02)
        relative_x = (obj.x - face.mouth_x) / mouth_width
        relative_y = (obj.y - face.mouth_y) / (mouth_width * face.frame_aspect_ratio)
        distance = hypot(relative_x, relative_y)
        bearing = degrees(atan2(relative_y, relative_x))
        if self._previous_relative is not None and self._previous_timestamp is not None:
            elapsed = max(timestamp - self._previous_timestamp, 1e-3)
            speed = hypot(relative_x - self._previous_relative[0],
                          relative_y - self._previous_relative[1]) / elapsed
            if speed > 12:
                self._history.clear()
                self._previous_relative = (relative_x, relative_y)
                self._previous_timestamp = timestamp
                self.estimate = InteractionEstimate(
                    state=InteractionState.TRACKING_LOST,
                    distance_mouth_widths=round(distance, 2),
                    bearing_degrees=round(bearing, 1),
                )
                return self.estimate
        self._previous_relative = (relative_x, relative_y)
        self._previous_timestamp = timestamp

        near_threshold = config.near_distance_mouth_widths
        open_threshold = max(0.08, (config.neutral_mouth_openness or 0.04) + 0.025)
        near = distance <= near_threshold and (face.mouth_openness or 0) >= open_threshold
        reference = next((item for item in reversed(self._history)
                          if timestamp - item.timestamp >= 0.16), None)
        # Alternating motion can return to the same point at the 160 ms
        # reference interval; retain the adjacent-frame displacement too.
        adjacent = self._history[-1] if self._history else None
        movement = max(
            hypot(relative_x - item.relative_x, relative_y - item.relative_y)
            for item in (reference, adjacent) if item is not None
        ) if reference or adjacent else 0.0
        moving_away = bool(adjacent and distance - adjacent.distance > 0.4)
        motion_threshold = 0.24 - 0.14 * config.sensitivity
        moving = movement >= motion_threshold
        self._history.append(_Evidence(timestamp, distance, relative_x, relative_y, near, moving))
        while self._history and timestamp - self._history[0].timestamp > 1.2:
            self._history.popleft()

        near_samples = []
        for item in reversed(self._history):
            if not item.near:
                break
            near_samples.append(item)
        near_samples.reverse()
        moving_samples = sum(item.moving for item in near_samples)
        required_frames = round(8 - 5 * config.sensitivity)
        required_seconds = 0.65 - 0.4 * config.sensitivity
        dwell = near_samples[-1].timestamp - near_samples[0].timestamp if len(near_samples) > 1 else 0.0
        approach = (self._history[0].distance - distance >= 0.3 and
                    timestamp - self._history[0].timestamp <= 1.2)

        if previous_state == InteractionState.INTERACTION_ACTIVE and moving_away:
            state = InteractionState.INTERACTION_ENDED
            self._ended_at = timestamp
            self._history.clear()
            self._far_frames = 0
        elif near:
            self._far_frames = 0
            self._ended_at = None
            if len(near_samples) >= required_frames and dwell >= required_seconds and moving_samples >= 2:
                state = InteractionState.INTERACTION_ACTIVE
            else:
                state = InteractionState.POSSIBLE_INTERACTION
        else:
            self._far_frames += 1
            if previous_state == InteractionState.INTERACTION_ACTIVE:
                state = InteractionState.INTERACTION_ENDED
                self._ended_at = timestamp
                self._history.clear()
            elif previous_state == InteractionState.INTERACTION_ENDED and self._ended_at is not None and timestamp - self._ended_at < 0.5:
                state = InteractionState.INTERACTION_ENDED
            else:
                state = InteractionState.OBJECT_APPROACHING if approach else InteractionState.OBJECT_VISIBLE

        near_score = max(0.0, 1.0 - distance / max(near_threshold * 2, 0.01))
        evidence_score = min(1.0, len(near_samples) / max(required_frames, 1))
        motion_score = min(1.0, moving_samples / 2)
        score = (
            0.25 * face.tracking_quality + 0.25 * obj.tracking_quality +
            0.2 * near_score + 0.15 * evidence_score + 0.15 * motion_score
        )
        self.estimate = InteractionEstimate(
            state=state,
            confidence=round(min(1.0, max(0.0, score)), 2),
            distance_mouth_widths=round(distance, 2),
            bearing_degrees=round(bearing, 1),
            evidence_frames=len(near_samples),
        )
        return self.estimate


def state_change_event(
    sequence: int, previous: InteractionState, estimate: InteractionEstimate,
    face: FaceObservation, obj: ObjectObservation,
) -> InteractionEvent:
    return InteractionEvent(
        sequence=sequence,
        timestamp=datetime.now(UTC).isoformat(timespec="milliseconds"),
        state=estimate.state,
        previous_state=previous,
        confidence=estimate.confidence,
        distance_mouth_widths=estimate.distance_mouth_widths,
        mouth=(face.mouth_x, face.mouth_y) if face.mouth_detected and face.mouth_x is not None and face.mouth_y is not None else None,
        object=(obj.x, obj.y) if obj.detected and obj.x is not None and obj.y is not None else None,
    )
