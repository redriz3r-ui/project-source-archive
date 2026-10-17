"""Opt-in in-memory drafts and private local JSON sessions; never stores frames."""

import json
import math
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.evaluation.metrics import LABELS, UNCERTAIN, score_samples
from app.events import Event
from app.paths import private_data_path


DEFAULT_DIRECTORY = private_data_path("evaluation-data")
MAX_SAMPLES = 45_000  # About 30 minutes at 24 FPS.
MAX_SECONDS = 1_800.0


class EvaluationService:
    def __init__(self, directory: Path = DEFAULT_DIRECTORY,
                 clock=time.monotonic) -> None:
        self.directory = directory
        self._clock = clock
        self._lock = threading.RLock()
        self._active = False
        self._recording = False
        self._draft: dict[str, object] | None = None
        self._started_monotonic = 0.0
        self._label = UNCERTAIN
        self._error: str | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def start(self, consent_to_collect_numeric: bool) -> dict[str, object]:
        if consent_to_collect_numeric is not True:
            raise ValueError("Explicit consent to collect numeric observations is required")
        with self._lock:
            if self._active:
                raise RuntimeError("Evaluation is already active")
            if self._draft is not None:
                raise RuntimeError("Save or discard the previous draft first")
            self._started_monotonic = self._clock()
            self._label = UNCERTAIN
            self._error = None
            self._draft = {
                "schema_version": 1,
                "id": uuid4().hex,
                "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "samples": [],
                "label_changes": [{"elapsed_s": 0.0, "label": UNCERTAIN}],
                "privacy": {"numeric_only": True, "frames_saved": False, "uploaded": False},
            }
            self._active = True
            self._recording = True
            return self.snapshot()

    def set_label(self, label: str) -> dict[str, object]:
        if label not in LABELS:
            raise ValueError("Label must be INTENDED, NO_INTERACTION, or UNCERTAIN")
        with self._lock:
            if not self._active or not self._recording or self._draft is None:
                raise RuntimeError("Start evaluation before labeling")
            if label != self._label:
                self._label = label
                self._draft["label_changes"].append({
                    "elapsed_s": round(self._clock() - self._started_monotonic, 6),
                    "label": label,
                })
            return self.snapshot()

    def ingest(self, event: Event) -> None:
        data = event.payload.get("evaluation")
        if not isinstance(data, dict):
            return
        with self._lock:
            if not self._active or not self._recording or self._draft is None:
                return
            observed_at = event.payload.get("observed_at")
            if (not isinstance(observed_at, (int, float)) or not math.isfinite(observed_at)
                    or observed_at < self._started_monotonic):
                return  # Ignore queued observations from before explicit consent.
            elapsed = observed_at - self._started_monotonic
            samples: list[dict[str, object]] = self._draft["samples"]
            if elapsed > MAX_SECONDS or len(samples) >= MAX_SAMPLES:
                self._recording = False
                self._error = "Evaluation reached its 30-minute / 45,000-sample limit; stop and review"
                return
            allowed = {
                "face_detected", "mouth_detected", "mouth_x", "mouth_y",
                "mouth_width", "mouth_openness", "head_motion", "face_quality",
                "object_detected", "object_x", "object_y", "object_quality",
                "object_source", "distance_mouth_widths", "confidence", "state",
            }
            if not isinstance(data.get("state"), str):
                return
            sample = {}
            for key, value in data.items():
                if key not in allowed:
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sample[key] = round(float(value), 4) if math.isfinite(value) else None
                elif isinstance(value, (bool, str)) or value is None:
                    sample[key] = value
            sample["elapsed_s"] = round(elapsed, 3)
            sample["label"] = next((change["label"] for change in reversed(self._draft["label_changes"])
                                    if change["elapsed_s"] <= elapsed), UNCERTAIN)
            samples.append(sample)

    def note_camera_stopped(self, observed_at: float | None = None) -> None:
        with self._lock:
            if self._active and (observed_at is None or observed_at >= self._started_monotonic):
                self._recording = False

    def fail(self, reason: str) -> None:
        with self._lock:
            if self._active:
                self._recording = False
                self._error = reason

    def stop(self) -> dict[str, object]:
        with self._lock:
            if not self._active or self._draft is None:
                raise RuntimeError("Evaluation is not active")
            self._active = False
            self._recording = False
            self._draft["ended_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            return self.snapshot()

    def discard(self) -> None:
        with self._lock:
            self._active = False
            self._recording = False
            self._draft = None
            self._label = UNCERTAIN
            self._error = None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            draft = self._draft
            samples = draft["samples"] if draft is not None else []
            return {
                "active": self._active,
                "recording": self._recording,
                "draft_id": draft["id"] if draft else None,
                "label": self._label if self._active else None,
                "sample_count": len(samples),
                "started_at": draft["started_at"] if draft else None,
                "report": score_samples(samples) if draft and not self._active else None,
                "recent_samples": samples[-12:],
                "numeric_only": True,
                "error": self._error,
            }

    def save(self, consent_to_save: bool) -> dict[str, object]:
        if consent_to_save is not True:
            raise ValueError("Explicit consent to save numeric observations is required")
        with self._lock:
            if self._active or self._draft is None:
                raise RuntimeError("Stop evaluation before saving a draft")
            document = {**self._draft, "report": score_samples(self._draft["samples"])}
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
            self._label = UNCERTAIN
            return {"id": document["id"], "report": document["report"],
                    "sample_count": len(document["samples"]), "saved_at": document["ended_at"]}

    def draft_detail(self) -> dict[str, object]:
        with self._lock:
            if self._draft is None:
                raise KeyError("draft")
            return {**self._draft, "samples": list(self._draft["samples"]),
                    "label_changes": list(self._draft["label_changes"]),
                    "report": score_samples(self._draft["samples"])}

    def _saved_path(self, identifier: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("Invalid session ID")
        return self.directory / f"{identifier}.json"

    def saved(self, identifier: str) -> dict[str, object]:
        path = self._saved_path(identifier)
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
                               "ended_at": data["ended_at"], "sample_count": len(data["samples"]),
                               "report": data["report"]})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return result

    def delete(self, identifier: str) -> None:
        path = self._saved_path(identifier)
        try:
            path.unlink()
        except FileNotFoundError as exc:
            raise KeyError(identifier) from exc
