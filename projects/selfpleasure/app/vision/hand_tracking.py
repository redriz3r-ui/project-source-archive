"""Local MediaPipe hand landmarks and stationary-object axis geometry.

This module has no device dependency. Its score is a tracking-quality heuristic,
not a probability of contact or intended interaction.
"""

import json
import math
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.paths import private_data_path, resource_path

DEFAULT_HAND_MODEL_PATH = resource_path(".models", "hand_landmarker.task")
DEFAULT_HAND_CALIBRATION_PATH = private_data_path("config.local.hand-stroke.json")
PALM_INDICES = (0, 5, 9, 13, 17)


@dataclass(frozen=True, slots=True)
class HandCalibration:
    base: tuple[float, float] | None = None
    endpoint: tuple[float, float] | None = None
    marker_anchor: bool = False


class HandCalibrationStore:
    def __init__(self, path: Path = DEFAULT_HAND_CALIBRATION_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._config = self._load()

    def _load(self) -> HandCalibration:
        if not self.path.exists():
            return HandCalibration()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        config = HandCalibration(
            base=tuple(data["base"]) if data.get("base") is not None else None,
            endpoint=tuple(data["endpoint"]) if data.get("endpoint") is not None else None,
            marker_anchor=data.get("marker_anchor", False),
        )
        validate_calibration(config)
        return config

    def snapshot(self) -> HandCalibration:
        with self._lock:
            return self._config

    def update(self, **changes: object) -> HandCalibration:
        with self._lock:
            config = HandCalibration(**{**asdict(self._config), **changes})
            validate_calibration(config)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(self.path)
            self._config = config
            return config


def validate_calibration(config: HandCalibration) -> None:
    for point in (config.base, config.endpoint):
        if point is not None and (len(point) != 2 or not all(
            isinstance(value, (float, int)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 1 for value in point
        )):
            raise ValueError("Axis points must be normalized inside the preview")
    if type(config.marker_anchor) is not bool:
        raise ValueError("marker_anchor must be boolean")
    if config.base is not None and config.endpoint is not None:
        if math.dist(config.base, config.endpoint) < 0.08:
            raise ValueError("Axis endpoints must be at least 8% of the frame apart")


def project_on_axis(hand: tuple[float, float], base: tuple[float, float],
                    endpoint: tuple[float, float], aspect: float) -> tuple[float, float]:
    """Return clamped axial position and lateral distance in axis lengths."""
    bx, by = base[0] * aspect, base[1]
    dx, dy = (endpoint[0] - base[0]) * aspect, endpoint[1] - base[1]
    hx, hy = hand[0] * aspect - bx, hand[1] - by
    length2 = dx * dx + dy * dy
    if length2 < 1e-8:
        raise ValueError("Calibrated axis is too short")
    along = (hx * dx + hy * dy) / length2
    lateral = abs(hx * dy - hy * dx) / length2
    return max(0.0, min(1.0, along)), lateral


@dataclass(frozen=True, slots=True)
class HandTracking:
    state: str = "NO_CALIBRATION"
    hand_detected: bool = False
    hand_count: int = 0
    hand_x: float | None = None
    hand_y: float | None = None
    travel_position: float | None = None
    tracking_confidence: float = 0.0
    base: tuple[float, float] | None = None
    endpoint: tuple[float, float] | None = None
    marker_detected: bool = False


def estimate_hand_axis(hands: list[list[Any]], config: HandCalibration,
                       aspect: float, marker: tuple[float, float] | None = None) -> HandTracking:
    if config.base is None or config.endpoint is None:
        return HandTracking()
    base = config.base
    endpoint = config.endpoint
    if config.marker_anchor:
        if marker is None:
            return HandTracking(state="TRACKING_LOST", hand_count=len(hands),
                                base=base, endpoint=endpoint)
        shift = (marker[0] - base[0], marker[1] - base[1])
        base = marker
        endpoint = (endpoint[0] + shift[0], endpoint[1] + shift[1])
        if math.dist(marker, config.base) > 0.15 or not all(0 <= value <= 1 for value in endpoint):
            return HandTracking(state="OBJECT_DRIFT", hand_count=len(hands),
                                base=base, endpoint=endpoint, marker_detected=True)
    if not hands:
        return HandTracking(state="TRACKING_LOST", base=base, endpoint=endpoint,
                            marker_detected=marker is not None)
    candidates = []
    for landmarks in hands:
        points = [landmarks[i] for i in PALM_INDICES if i < len(landmarks)
                  and math.isfinite(landmarks[i].x) and math.isfinite(landmarks[i].y)
                  and 0 <= landmarks[i].x <= 1 and 0 <= landmarks[i].y <= 1]
        if len(points) < 2:
            continue
        x = float(np.median([point.x for point in points]))
        y = float(np.median([point.y for point in points]))
        position, lateral = project_on_axis((x, y), base, endpoint, aspect)
        quality = (len(points) / len(PALM_INDICES)) * max(0.0, 1.0 - lateral / 0.4)
        if lateral <= 0.4:
            candidates.append((lateral, x, y, position, quality))
    if not candidates:
        return HandTracking(state="TRACKING_LOST", hand_count=len(hands),
                            base=base, endpoint=endpoint, marker_detected=marker is not None)
    if len(candidates) > 1:
        return HandTracking(state="MULTIPLE_HANDS", hand_count=len(hands),
                            base=base, endpoint=endpoint, marker_detected=marker is not None)
    _, x, y, position, quality = candidates[0]
    return HandTracking(state="TRACKED", hand_detected=True, hand_count=len(hands),
                        hand_x=x, hand_y=y, travel_position=position,
                        tracking_confidence=round(quality, 3), base=base,
                        endpoint=endpoint, marker_detected=marker is not None)


class HandLandmarkerService:
    def __init__(self, model_path: Path = DEFAULT_HAND_MODEL_PATH) -> None:
        self.model_path = model_path
        self._landmarker: Any | None = None
        self._mp: Any | None = None

    def open(self) -> None:
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Hand model missing: {self.model_path}. Run python -m app.vision.download_hand_model."
            )
        import mediapipe as mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5, min_tracking_confidence=0.5,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._mp = mp

    def process(self, frame: np.ndarray, timestamp_ms: int) -> list[list[Any]]:
        if self._landmarker is None or self._mp is None:
            raise RuntimeError("Hand Landmarker is not initialized")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        return self._landmarker.detect_for_video(image, timestamp_ms).hand_landmarks

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
        self._landmarker = None
        self._mp = None
