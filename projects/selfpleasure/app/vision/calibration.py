"""Local numeric calibration only; never stores images or frame samples."""

import json
import math
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import cv2
import numpy as np

from app.paths import private_data_path

DEFAULT_CALIBRATION_PATH = private_data_path("config.local.json")


@dataclass(frozen=True, slots=True)
class Calibration:
    mode: str = "marker"
    marker_hue: int | None = None
    hue_tolerance: int = 12
    saturation_min: int = 70
    value_min: int = 45
    manual_roi: tuple[float, float, float, float] | None = None
    near_distance_mouth_widths: float = 2.0
    sensitivity: float = 0.5
    mouth_width_reference: float | None = None
    neutral_mouth_openness: float | None = None


class CalibrationStore:
    def __init__(self, path: Path = DEFAULT_CALIBRATION_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._config = self._load()
        self._version = 0

    def _load(self) -> Calibration:
        if not self.path.exists():
            return Calibration()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("manual_roi") is not None:
            data["manual_roi"] = tuple(data["manual_roi"])
        config = Calibration(**data)
        self._validate(config)
        return config

    def snapshot(self) -> tuple[Calibration, int]:
        with self._lock:
            return self._config, self._version

    def as_dict(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._config)

    def update(self, **changes: object) -> Calibration:
        with self._lock:
            candidate = replace(self._config, **changes)
            self._validate(candidate)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(candidate), indent=2) + "\n", encoding="utf-8")
            temporary.replace(self.path)
            self._config = candidate
            self._version += 1
            return candidate

    @staticmethod
    def _validate(config: Calibration) -> None:
        if config.mode not in {"marker", "roi"}:
            raise ValueError("Mode must be marker or roi")
        if not 0.4 <= config.near_distance_mouth_widths <= 8:
            raise ValueError("Near distance must be between 0.4 and 8 mouth widths")
        if not math.isfinite(config.sensitivity) or not 0 <= config.sensitivity <= 1:
            raise ValueError("Sensitivity must be between 0 and 1")
        if config.manual_roi is not None:
            x, y, width, height = config.manual_roi
            if not all(math.isfinite(value) for value in config.manual_roi):
                raise ValueError("ROI coordinates must be finite")
            if min(x, y) < 0 or width <= 0.02 or height <= 0.02 or x + width > 1 or y + height > 1:
                raise ValueError("ROI must be a rectangle inside the preview")

    def calibrate_marker(self, frame: np.ndarray, x: float, y: float) -> Calibration:
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in (x, y)):
            raise ValueError("Marker point must be inside the preview")
        height, width = frame.shape[:2]
        px, py = round(x * (width - 1)), round(y * (height - 1))
        patch = frame[max(0, py - 5):min(height, py + 6), max(0, px - 5):min(width, px + 6)]
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        strong = hsv[(hsv[:, 1] >= 55) & (hsv[:, 2] >= 45)]
        if len(strong) < max(8, len(hsv) // 5):
            raise ValueError("Choose a bright, saturated marker area")
        angles = strong[:, 0].astype(float) * (2 * math.pi / 180)
        hue = round((math.atan2(np.sin(angles).mean(), np.cos(angles).mean()) % (2 * math.pi)) * 180 / (2 * math.pi)) % 180
        return self.update(
            marker_hue=hue,
            saturation_min=max(55, int(np.percentile(strong[:, 1], 20)) - 30),
            value_min=max(40, int(np.percentile(strong[:, 2], 20)) - 30),
            mode="marker",
        )
