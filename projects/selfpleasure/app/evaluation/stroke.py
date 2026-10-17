"""Opt-in local stroke labels and numeric-only per-session evaluation."""

import json
import math
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.events import Event
from app.paths import private_data_path


DEFAULT_DIRECTORY = private_data_path("evaluation-data", "strokes")
LABELS = frozenset({"STROKES", "NO_STROKES", "UNCERTAIN"})
MAX_SECONDS = 1_800.0
MAX_SAMPLES = 45_000
MATCH_WINDOW_S = 1.0


def score_stroke_session(document: dict[str, object]) -> dict[str, object]:
    """Match completion timestamps to user button presses, one-to-one."""
    labels = document["label_changes"]
    truth = [item for item in document["manual_strokes"]
             if _label_at(labels, item["elapsed_s"]) == "STROKES"]
    predictions = [item for item in document["detected_strokes"]
                   if _label_at(labels, item["elapsed_s"]) != "UNCERTAIN"]
    available = set(range(len(predictions)))
    latencies = []
    matched = 0
    for mark in truth:
        options = sorted((abs(predictions[i]["elapsed_s"] - mark["elapsed_s"]), i)
                         for i in available
                         if _label_at(labels, predictions[i]["elapsed_s"]) == "STROKES")
        if options and options[0][0] <= MATCH_WINDOW_S:
            _, index = options[0]
            available.remove(index)
            matched += 1
            latencies.append(round(predictions[index]["elapsed_s"] - mark["elapsed_s"], 3))
    fp = len(available)
    fn = len(truth) - matched
    negative_seconds = 0.0
    samples = document["samples"]
    for first, second in zip(samples, samples[1:]):
        if first["label"] == second["label"] == "NO_STROKES":
            negative_seconds += min(0.25, max(0, second["elapsed_s"] - first["elapsed_s"]))
    negative_fp = sum(_label_at(labels, predictions[i]["elapsed_s"]) == "NO_STROKES"
                      for i in available)
    actual_count = len(truth)
    predicted_count = len(predictions)
    count_accuracy = (1.0 if actual_count == predicted_count == 0 else
                      max(0.0, 1 - abs(predicted_count - actual_count) / max(1, actual_count)))
    return {
        "manual_strokes": actual_count,
        "detected_strokes": predicted_count,
        "matched_strokes": matched,
        "missed_strokes": fn,
        "false_detections": fp,
        "stroke_count_accuracy": round(count_accuracy, 3),
        "precision": round(matched / (matched + fp), 3) if matched + fp else None,
        "recall": round(matched / (matched + fn), 3) if matched + fn else None,
        "negative_labeled_seconds": round(negative_seconds, 3),
        "false_detections_per_hour": round(negative_fp * 3600 / negative_seconds, 2)
        if negative_seconds > 0 else None,
        "detection_latencies_s": latencies,
        "mean_detection_latency_s": round(sum(latencies) / len(latencies), 3)
        if latencies else None,
        "matching_window_s": MATCH_WINDOW_S,
        "warning": "Manual button timing and unlabeled intervals limit these descriptive metrics.",
    }


def _label_at(changes: list[dict[str, object]], elapsed: float) -> str:
    return next((item["label"] for item in reversed(changes)
                 if item["elapsed_s"] <= elapsed), "UNCERTAIN")


class StrokeEvaluationService:
    def __init__(self, directory: Path = DEFAULT_DIRECTORY, clock=time.monotonic) -> None:
        self.directory = directory
        self._clock = clock
        self._lock = threading.RLock()
        self._draft: dict[str, object] | None = None
        self._active = False
        self._recording = False
        self._started = 0.0
        self._error: str | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def start(self, consent: bool) -> dict[str, object]:
        if consent is not True:
            raise ValueError("Explicit numeric-collection consent is required")
        with self._lock:
            if self._active or self._draft is not None:
                raise RuntimeError("Finish or discard the previous stroke evaluation first")
            self._started = self._clock()
            self._error = None
            self._draft = {
                "schema_version": 1, "id": uuid4().hex,
                "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "samples": [], "detected_strokes": [], "manual_strokes": [],
                "label_changes": [{"elapsed_s": 0.0, "label": "UNCERTAIN"}],
                "privacy": {"numeric_only": True, "frames_saved": False, "uploaded": False},
            }
            self._active = self._recording = True
            return self.snapshot()

    def label(self, label: str) -> dict[str, object]:
        if label not in LABELS:
            raise ValueError("Label must be STROKES, NO_STROKES, or UNCERTAIN")
        with self._lock:
            if not self._active or not self._recording or self._draft is None:
                raise RuntimeError("Start stroke evaluation before labeling")
            if self._draft["label_changes"][-1]["label"] != label:
                self._draft["label_changes"].append({
                    "elapsed_s": round(self._clock() - self._started, 3), "label": label,
                })
            return self.snapshot()

    def mark_stroke(self) -> dict[str, object]:
        with self._lock:
            if not self._active or not self._recording or self._draft is None:
                raise RuntimeError("Start stroke evaluation before marking strokes")
            if self._draft["label_changes"][-1]["label"] != "STROKES":
                raise RuntimeError("Select Testing strokes before marking a traversal")
            self._draft["manual_strokes"].append({
                "elapsed_s": round(self._clock() - self._started, 3),
            })
            return self.snapshot()

    def ingest(self, event: Event) -> None:
        if event.topic not in {"stroke_observation", "stroke_completed"}:
            return
        data = event.payload.get("stroke")
        observed = event.payload.get("observed_at")
        if not isinstance(data, dict) or not isinstance(observed, (int, float)):
            return
        with self._lock:
            if not self._active or not self._recording or self._draft is None or observed < self._started:
                return
            captured_ns = data.get("timestamp_ns")
            if isinstance(captured_ns, int) and captured_ns / 1e9 < self._started:
                return  # A frame captured before consent must not enter the draft.
            elapsed = observed - self._started
            if elapsed > MAX_SECONDS or len(self._draft["samples"]) >= MAX_SAMPLES:
                self._recording = False
                self._error = "Stroke evaluation reached its 30-minute / 45,000-sample limit"
                return
            if event.topic == "stroke_completed":
                if type(data.get("stroke_id")) is int:
                    self._draft["detected_strokes"].append({
                        "elapsed_s": round(elapsed, 3), "stroke_id": data["stroke_id"],
                    })
                return
            allowed = ("frame_id", "hand_position", "speed", "travel", "tracking_confidence", "stroke_id")
            sample = {"elapsed_s": round(elapsed, 3),
                      "label": _label_at(self._draft["label_changes"], elapsed),
                      "tracking_state": event.payload.get("tracking_state")
                      if event.payload.get("tracking_state") in {
                          "TRACKED", "TRACKING_LOST", "OBJECT_DRIFT",
                          "MULTIPLE_HANDS", "NO_CALIBRATION",
                      } else "UNKNOWN"}
            for key in allowed:
                value = data.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    sample[key] = round(value, 4)
                else:
                    sample[key] = None
            sample["direction"] = (str(data.get("direction")) if data.get("direction") in {
                "FORWARD", "REVERSE", "STILL", "UNKNOWN",
            } else "UNKNOWN")
            self._draft["samples"].append(sample)

    def note_camera_stopped(self) -> None:
        with self._lock:
            if self._active:
                self._recording = False

    def fail(self, reason: str) -> None:
        with self._lock:
            if self._active:
                self._recording = False
                self._error = reason

    def stop(self) -> dict[str, object]:
        with self._lock:
            if not self._active or self._draft is None:
                raise RuntimeError("Stroke evaluation is not active")
            self._active = self._recording = False
            self._draft["ended_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            return self.snapshot()

    def discard(self) -> None:
        with self._lock:
            self._draft = None
            self._active = self._recording = False
            self._error = None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            draft = self._draft
            return {
                "active": self._active, "recording": self._recording,
                "draft_id": draft["id"] if draft else None,
                "current_label": draft["label_changes"][-1]["label"] if draft and self._active else None,
                "sample_count": len(draft["samples"]) if draft else 0,
                "manual_stroke_count": len(draft["manual_strokes"]) if draft else 0,
                "detected_stroke_count": len(draft["detected_strokes"]) if draft else 0,
                "recent_samples": draft["samples"][-12:] if draft else [],
                "report": score_stroke_session(draft) if draft and not self._active else None,
                "numeric_only": True, "error": self._error,
            }

    def draft_detail(self) -> dict[str, object]:
        with self._lock:
            if self._draft is None:
                raise KeyError("No stroke draft")
            return {**self._draft, "report": score_stroke_session(self._draft)}

    def save(self, consent: bool) -> dict[str, object]:
        if consent is not True:
            raise ValueError("Explicit save consent is required")
        with self._lock:
            if self._draft is None or self._active:
                raise RuntimeError("Stop stroke evaluation before saving")
            document = self.draft_detail()
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            target = self.directory / f"{document['id']}.json"
            temporary = self.directory / f".{document['id']}.{uuid4().hex}.tmp"
            try:
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump(document, output, separators=(",", ":"))
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            self._draft = None
            return {"id": document["id"], "report": document["report"]}

    def _path(self, identifier: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("Invalid session ID")
        return self.directory / f"{identifier}.json"

    def saved(self, identifier: str) -> dict[str, object]:
        path = self._path(identifier)
        if not path.is_file():
            raise KeyError(identifier)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_saved(self) -> list[dict[str, object]]:
        if not self.directory.is_dir():
            return []
        result = []
        for path in sorted(self.directory.glob("*.json"), reverse=True)[:100]:
            if not re.fullmatch(r"[0-9a-f]{32}\.json", path.name):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result.append({"id": data["id"], "started_at": data["started_at"],
                               "report": data["report"]})
            except (ValueError, KeyError, OSError, TypeError):
                continue
        return result

    def delete(self, identifier: str) -> None:
        try:
            self._path(identifier).unlink()
        except FileNotFoundError as exc:
            raise KeyError(identifier) from exc
