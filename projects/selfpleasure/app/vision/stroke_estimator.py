"""Temporal, device-neutral traversal recognition along a calibrated axis."""

from dataclasses import dataclass

from app.vision.hand_tracking import HandTracking
from app.vision.stroke_contract import (
    STROKE_SCHEMA_VERSION, StrokeDirection, StrokeEvent, StrokeEventKind,
    StrokeObservation,
)


@dataclass(frozen=True, slots=True)
class StrokeThresholds:
    start_travel: float = 0.06
    minimum_travel: float = 0.25
    reversal_travel: float = 0.05
    endpoint: float = 0.12
    minimum_speed: float = 0.04
    maximum_speed: float = 3.0
    minimum_confidence: float = 0.5
    maximum_gap_s: float = 0.25
    # MediaPipe can miss an isolated frame while a hand remains plainly in
    # view.  Do not turn that detector jitter into a terminal session fault.
    # No movement event is emitted during this grace period, and the output
    # controller has a separate, shorter freshness deadline.
    loss_grace_s: float = 0.10
    maximum_traversal_s: float = 8.0


class StrokeEstimator:
    """One completion per validated traversal; ambiguity discards active evidence."""

    def __init__(self, thresholds: StrokeThresholds = StrokeThresholds()) -> None:
        self.thresholds = thresholds
        self.reset()

    def reset(self) -> None:
        self._next_id = 1
        self._last_ns: int | None = None
        self._last_raw: float | None = None
        self._smoothed: float | None = None
        self._origin: float | None = None
        self._origin_ns: int | None = None
        self._active_id: int | None = None
        self._direction = StrokeDirection.UNKNOWN
        self._start = 0.0
        self._start_ns = 0
        self._extreme = 0.0
        self._reversal_frames = 0
        self._lost = False
        self._recovering = False
        self._last_valid_ns: int | None = None
        self._completed_direction: StrokeDirection | None = None

    @property
    def recovering(self) -> bool:
        """True only during a brief detector dropout before loss is declared."""
        return self._recovering

    def update(self, tracking: HandTracking, timestamp_ns: int,
               frame_id: int) -> tuple[StrokeObservation, tuple[StrokeEvent, ...]]:
        tracking_valid = (tracking.state == "TRACKED" and tracking.travel_position is not None
                          and tracking.tracking_confidence >= self.thresholds.minimum_confidence)
        valid = tracking_valid
        if self._last_ns is not None and (
            timestamp_ns <= self._last_ns or
            (timestamp_ns - self._last_ns) / 1e9 > self.thresholds.maximum_gap_s
        ):
            valid = False
        position = tracking.travel_position if valid else None
        raw_speed = 0.0
        if position is not None and self._last_raw is not None and self._last_ns is not None:
            raw_speed = abs(position - self._last_raw) / ((timestamp_ns - self._last_ns) / 1e9)
            if raw_speed > self.thresholds.maximum_speed:
                valid = False
                position = None
        if (position is None and not tracking_valid and self._last_valid_ns is not None
                and timestamp_ns > self._last_valid_ns
                and (timestamp_ns - self._last_valid_ns) / 1e9 < self.thresholds.loss_grace_s):
            # Preserve traversal evidence across one or two dropped frames, but
            # publish neither a position nor an UPDATED event.  A recovery past
            # the controller freshness deadline still disarms the mode.
            self._recovering = True
            return self._observation(timestamp_ns, frame_id, None,
                                     StrokeDirection.UNKNOWN, 0, 0, 0,
                                     self._active_id), ()
        if position is None:
            old_id = self._active_id
            was_tracking = self._last_raw is not None or self._active_id is not None
            self._last_ns = timestamp_ns
            self._last_raw = None
            self._smoothed = None
            self._origin = None
            self._origin_ns = None
            self._active_id = None
            self._direction = StrokeDirection.UNKNOWN
            self._completed_direction = None
            self._recovering = False
            self._last_valid_ns = None
            observation = self._observation(timestamp_ns, frame_id, None,
                                            StrokeDirection.UNKNOWN, 0, 0, 0, old_id)
            events = ()
            if was_tracking and not self._lost:
                events = (self._event(observation, StrokeEventKind.TRACKING_LOST),)
            self._lost = True
            return observation, events

        self._lost = False
        self._recovering = False
        self._last_valid_ns = timestamp_ns
        self._last_ns = timestamp_ns
        self._last_raw = position
        self._smoothed = position if self._smoothed is None else 0.55 * position + 0.45 * self._smoothed
        current = self._smoothed
        if self._origin is None:
            self._origin = current
            self._origin_ns = timestamp_ns
        events: list[StrokeEvent] = []
        direction = self._direction if self._active_id is not None else StrokeDirection.STILL
        travel = 0.0
        if self._active_id is None:
            delta = current - self._origin
            elapsed = max((timestamp_ns - self._origin_ns) / 1e9, 1e-6)
            proposed = StrokeDirection.FORWARD if delta > 0 else StrokeDirection.REVERSE
            if abs(delta) >= self.thresholds.start_travel and (
                abs(delta) / elapsed >= self.thresholds.minimum_speed
                and raw_speed <= self.thresholds.maximum_speed
                and proposed != self._completed_direction
            ):
                self._completed_direction = None
                self._direction = proposed
                direction = self._direction
                self._active_id = self._next_id
                self._next_id += 1
                self._start = self._origin
                self._start_ns = self._origin_ns
                self._extreme = current
                travel = abs(current - self._start)
                events.append(self._event(self._observation(
                    timestamp_ns, frame_id, current, direction, raw_speed, travel,
                    tracking.tracking_confidence, self._active_id,
                ), StrokeEventKind.STARTED))
        else:
            sign = 1 if self._direction == StrokeDirection.FORWARD else -1
            progress = sign * (current - self._start)
            extreme_progress = sign * (self._extreme - self._start)
            if progress > extreme_progress:
                self._extreme = current
                extreme_progress = progress
            travel = max(0.0, extreme_progress)
            direction = self._direction
            reverse = sign * (self._extreme - current)
            self._reversal_frames = self._reversal_frames + 1 if reverse >= self.thresholds.reversal_travel else 0
            reached_endpoint = (
                current >= 1 - self.thresholds.endpoint if sign > 0
                else current <= self.thresholds.endpoint
            )
            elapsed = (timestamp_ns - self._start_ns) / 1e9
            complete = (travel >= self.thresholds.minimum_travel and
                        elapsed <= self.thresholds.maximum_traversal_s and
                        (reached_endpoint or self._reversal_frames >= 2))
            observation = self._observation(timestamp_ns, frame_id, current, direction,
                                            raw_speed, travel, tracking.tracking_confidence,
                                            self._active_id)
            if complete:
                events.append(self._event(observation, StrokeEventKind.COMPLETED))
                self._completed_direction = self._direction if reached_endpoint else None
                self._active_id = None
                self._origin = self._extreme
                self._origin_ns = timestamp_ns
                self._reversal_frames = 0
                self._direction = StrokeDirection.UNKNOWN
            elif self._reversal_frames >= 2:
                # Reversed too early: discard the partial traversal, not a stroke.
                self._active_id = None
                self._origin = self._extreme
                self._origin_ns = timestamp_ns
                self._reversal_frames = 0
                self._direction = StrokeDirection.UNKNOWN
            elif elapsed > self.thresholds.maximum_traversal_s:
                self._active_id = None
                self._origin = current
                self._origin_ns = timestamp_ns
                self._direction = StrokeDirection.UNKNOWN
                self._reversal_frames = 0
            elif abs(current - self._extreme) < self.thresholds.reversal_travel:
                events.append(self._event(observation, StrokeEventKind.UPDATED))

        observation = self._observation(timestamp_ns, frame_id, current, direction,
                                        raw_speed, travel, tracking.tracking_confidence,
                                        self._active_id if self._active_id is not None else
                                        events[-1].stroke_id if events else None)
        return observation, tuple(events)

    @staticmethod
    def _observation(timestamp_ns: int, frame_id: int, position: float | None,
                     direction: StrokeDirection, speed: float, travel: float,
                     confidence: float, stroke_id: int | None) -> StrokeObservation:
        return StrokeObservation(STROKE_SCHEMA_VERSION, timestamp_ns, frame_id, position,
                                 direction, speed, travel, confidence, stroke_id)

    @staticmethod
    def _event(observation: StrokeObservation, kind: StrokeEventKind) -> StrokeEvent:
        return StrokeEvent(**{field: getattr(observation, field) for field in
                             StrokeObservation.__dataclass_fields__}, kind=kind)
