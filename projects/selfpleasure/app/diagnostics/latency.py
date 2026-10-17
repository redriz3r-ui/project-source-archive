"""Bounded monotonic timestamps; no frames, landmarks, names, or device data."""

from collections import OrderedDict, deque
from enum import StrEnum
import statistics
import threading
import time
from collections.abc import Callable


class TraceStage(StrEnum):
    FRAME_READ_STARTED = "frame_read_started"
    FRAME_CAPTURED = "frame_captured"
    FACE_DETECTED = "face_detected"
    HAND_DETECTED = "hand_detected"  # Future Hand Stroke mode.
    OBJECT_DETECTED = "object_detected"
    ORAL_DECIDED = "oral_decided"
    STROKE_DECIDED = "stroke_decided"  # Future Hand Stroke mode.
    EVENT_EMITTED = "event_emitted"
    TRIGGER_ACCEPTED = "trigger_accepted"
    COMMAND_SUBMITTED = "command_submitted"
    COMMAND_COMPLETED = "command_completed"  # API acknowledgement, not physical onset.
    COMMAND_FAILED = "command_failed"


_INTERVALS = {
    "frame_read_ms": (TraceStage.FRAME_READ_STARTED, TraceStage.FRAME_CAPTURED),
    "capture_to_face_ms": (TraceStage.FRAME_CAPTURED, TraceStage.FACE_DETECTED),
    "capture_to_hand_ms": (TraceStage.FRAME_CAPTURED, TraceStage.HAND_DETECTED),
    "capture_to_object_ms": (TraceStage.FRAME_CAPTURED, TraceStage.OBJECT_DETECTED),
    "capture_to_oral_decision_ms": (TraceStage.FRAME_CAPTURED, TraceStage.ORAL_DECIDED),
    "capture_to_stroke_decision_ms": (TraceStage.FRAME_CAPTURED, TraceStage.STROKE_DECIDED),
    "oral_decision_to_event_emitted_ms": (TraceStage.ORAL_DECIDED, TraceStage.EVENT_EMITTED),
    "event_emitted_to_trigger_accepted_ms": (TraceStage.EVENT_EMITTED, TraceStage.TRIGGER_ACCEPTED),
    "capture_to_command_submission_ms": (TraceStage.FRAME_CAPTURED, TraceStage.COMMAND_SUBMITTED),
    "decision_to_command_submission_ms": (TraceStage.TRIGGER_ACCEPTED, TraceStage.COMMAND_SUBMITTED),
    "command_ack_ms": (TraceStage.COMMAND_SUBMITTED, TraceStage.COMMAND_COMPLETED),
}


class LatencyRecorder:
    """Opt-in diagnostic ring; only fixed stage names and numeric times enter it."""

    def __init__(self, capacity: int = 512, clock: Callable[[], int] = time.monotonic_ns) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Latency recorder capacity must be positive")
        self.capacity = capacity
        self._clock = clock
        self._lock = threading.Lock()
        self._records: OrderedDict[int, dict[TraceStage, int]] = OrderedDict()
        self._stop_records: deque[dict[str, object]] = deque(maxlen=capacity)
        self._next_stop_id = 1
        self.enabled = False

    def start(self) -> None:
        with self._lock:
            self._records.clear()
            self._stop_records.clear()
            self.enabled = True

    def stop(self) -> None:
        with self._lock:
            self.enabled = False

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._stop_records.clear()

    def begin_stop(self, reason: str) -> int | None:
        """Record a stop request on the same monotonic clock as frame traces."""
        if reason not in {"disarm", "tracking_lost", "camera_stopped", "camera_loss",
                          "device_lost", "emergency_stop", "shutdown", "deadline",
                          "error", "unspecified", "user_stop", "session_expired"}:
            raise ValueError("Unknown stop reason")
        with self._lock:
            if not self.enabled:
                return None
            token = self._next_stop_id
            self._next_stop_id += 1
            self._stop_records.append({"stop_id": token, "reason": reason,
                                       "requested_ns": self._clock(), "completed_ns": None})
            return token

    def complete_stop(self, token: int | None) -> None:
        if token is None:
            return
        with self._lock:
            for record in reversed(self._stop_records):
                if record["stop_id"] == token:
                    record["completed_ns"] = self._clock()
                    return

    def stop_traces(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            return tuple(record.copy() for record in self._stop_records)

    def mark(self, frame_id: int, stage: TraceStage, at_ns: int | None = None) -> None:
        if type(frame_id) is not int or frame_id < 1 or not isinstance(stage, TraceStage):
            raise ValueError("A positive frame ID and known stage are required")
        if at_ns is not None and (type(at_ns) is not int or at_ns < 0):
            raise ValueError("Stage timestamps must be non-negative monotonic integers")
        with self._lock:
            if not self.enabled:
                return
            stamps = self._records.setdefault(frame_id, {})
            stamps.setdefault(stage, self._clock() if at_ns is None else at_ns)
            while len(self._records) > self.capacity:
                self._records.popitem(last=False)

    def traces(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            return tuple({"frame_id": frame_id,
                          "timestamps_ns": {stage.value: stamp for stage, stamp in stamps.items()}}
                         for frame_id, stamps in self._records.items())

    def report(self) -> dict[str, object]:
        with self._lock:
            records = tuple(stamps.copy() for stamps in self._records.values())
            enabled = self.enabled
        intervals: dict[str, dict[str, float | int] | None] = {}
        for label, (start, end) in _INTERVALS.items():
            values = sorted((stamps[end] - stamps[start]) / 1_000_000
                            for stamps in records if start in stamps and end in stamps
                            and stamps[end] >= stamps[start])
            intervals[label] = ({"count": len(values), "median_ms": round(statistics.median(values), 3),
                                 "p95_ms": round(_percentile(values, 0.95), 3),
                                 "max_ms": round(values[-1], 3)} if values else None)
        return {
            "enabled": enabled,
            "trace_count": len(records),
            "stage_counts": {stage.value: sum(stage in stamps for stamps in records)
                             for stage in TraceStage},
            "intervals": intervals,
            "timestamp_clock": "monotonic_ns",
            "command_completion_meaning": "API acknowledgement, not physical device response",
            "numeric_only": True,
            "frames_saved": False,
        }


def _percentile(sorted_values: list[float], fraction: float) -> float:
    index = (len(sorted_values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)
