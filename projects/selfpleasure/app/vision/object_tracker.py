"""Replaceable OpenCV object detector: HSV marker or user-selected CSRT ROI."""

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

from app.vision.calibration import Calibration, CalibrationStore


@dataclass(frozen=True, slots=True)
class ObjectObservation:
    detected: bool = False
    x: float | None = None
    y: float | None = None
    region: tuple[float, float, float, float] | None = None
    tracking_quality: float = 0.0
    marker_axis_degrees: float | None = None
    source: str = "none"


class ObjectDetector(Protocol):
    def process(self, frame: np.ndarray) -> ObjectObservation: ...


class OpenCVObjectTracker:
    def __init__(self, calibration: CalibrationStore) -> None:
        self.calibration = calibration
        self._roi_tracker = None
        self._roi_version = -1

    def process(self, frame: np.ndarray) -> ObjectObservation:
        config, version = self.calibration.snapshot()
        if config.mode == "roi":
            return self._track_roi(frame, config, version)
        self._roi_tracker = None
        return self._track_marker(frame, config)

    def _track_marker(self, frame: np.ndarray, config: Calibration) -> ObjectObservation:
        if config.marker_hue is None:
            return ObjectObservation(source="marker")
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0].astype(np.int16)
        difference = np.abs(hue - config.marker_hue)
        circular_difference = np.minimum(difference, 180 - difference)
        mask = np.where(
            (circular_difference <= config.hue_tolerance)
            & (hsv[:, :, 1] >= config.saturation_min)
            & (hsv[:, :, 2] >= config.value_min), 255, 0,
        ).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return ObjectObservation(source="marker")
        contour = max(contours, key=cv2.contourArea)
        height, width = frame.shape[:2]
        area_fraction = cv2.contourArea(contour) / (height * width)
        if not 0.0002 <= area_fraction <= 0.3:
            return ObjectObservation(source="marker")
        x, y, box_width, box_height = cv2.boundingRect(contour)
        moments = cv2.moments(contour)
        center_x = moments["m10"] / moments["m00"] if moments["m00"] else x + box_width / 2
        center_y = moments["m01"] / moments["m00"] if moments["m00"] else y + box_height / 2
        (_, _), (axis_width, axis_height), angle = cv2.minAreaRect(contour)
        aspect = max(axis_width, axis_height) / max(min(axis_width, axis_height), 1e-6)
        axis_degrees = (angle + (90 if axis_width < axis_height else 0)) % 180 if aspect >= 1.3 else None
        # Quality is a heuristic based on visible marker area, not a probability.
        quality = min(1.0, max(0.25, area_fraction / 0.004))
        return ObjectObservation(
            detected=True,
            x=center_x / width,
            y=center_y / height,
            region=(x / width, y / height, box_width / width, box_height / height),
            tracking_quality=quality,
            marker_axis_degrees=axis_degrees,
            source="marker",
        )

    def _track_roi(self, frame: np.ndarray, config: Calibration, version: int) -> ObjectObservation:
        if config.manual_roi is None:
            return ObjectObservation(source="roi")
        height, width = frame.shape[:2]
        if self._roi_version != version:
            self._roi_version = version
            self._roi_tracker = cv2.TrackerCSRT_create()
            x, y, box_width, box_height = config.manual_roi
            rectangle = (
                round(x * width), round(y * height),
                max(2, round(box_width * width)), max(2, round(box_height * height)),
            )
            self._roi_tracker.init(frame, rectangle)
            return self._roi_observation(rectangle, width, height)
        if self._roi_tracker is None:
            return ObjectObservation(source="roi")
        found, rectangle = self._roi_tracker.update(frame)
        if not found:
            self._roi_tracker = None
            return ObjectObservation(source="roi")
        return self._roi_observation(rectangle, width, height)

    @staticmethod
    def _roi_observation(rectangle: tuple, width: int, height: int) -> ObjectObservation:
        x, y, box_width, box_height = rectangle
        x = max(0.0, min(float(width), float(x)))
        y = max(0.0, min(float(height), float(y)))
        box_width = max(0.0, min(float(width) - x, float(box_width)))
        box_height = max(0.0, min(float(height) - y, float(box_height)))
        if box_width < 2 or box_height < 2:
            return ObjectObservation(source="roi")
        return ObjectObservation(
            detected=True,
            x=(x + box_width / 2) / width,
            y=(y + box_height / 2) / height,
            region=(x / width, y / height, box_width / width, box_height / height),
            tracking_quality=0.65,  # CSRT does not expose a calibrated score.
            source="roi",
        )
