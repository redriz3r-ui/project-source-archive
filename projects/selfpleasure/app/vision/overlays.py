"""Diagnostic overlays for the local preview."""

import cv2
import numpy as np

from app.vision.calibration import Calibration
from app.vision.interaction import InteractionEstimate
from app.vision.object_tracker import ObjectObservation
from app.vision.service import FaceObservation


def draw_interaction_overlay(
    frame: np.ndarray, face: FaceObservation, obj: ObjectObservation,
    estimate: InteractionEstimate, config: Calibration,
) -> None:
    height, width = frame.shape[:2]
    if face.mouth_region is not None:
        x, y, box_width, box_height = face.mouth_region
        cv2.rectangle(frame, (round(x * width), round(y * height)),
                      (round((x + box_width) * width), round((y + box_height) * height)),
                      (0, 240, 180), 1)
    if face.mouth_x is not None and face.mouth_y is not None and face.mouth_width is not None:
        center = (round(face.mouth_x * width), round(face.mouth_y * height))
        radius_x = round(config.near_distance_mouth_widths * face.mouth_width * width)
        radius_y = round(config.near_distance_mouth_widths * face.mouth_width * height)
        cv2.ellipse(frame, center, (radius_x, radius_y), 0, 0, 360, (255, 180, 50), 1)
    if obj.region is not None:
        x, y, box_width, box_height = obj.region
        cv2.rectangle(frame, (round(x * width), round(y * height)),
                      (round((x + box_width) * width), round((y + box_height) * height)),
                      (70, 80, 255), 2)
    if obj.detected and obj.x is not None and obj.y is not None and face.mouth_x is not None and face.mouth_y is not None:
        cv2.line(frame, (round(obj.x * width), round(obj.y * height)),
                 (round(face.mouth_x * width), round(face.mouth_y * height)),
                 (150, 180, 255), 1)
    label = f"{estimate.state.value} | score {estimate.confidence:.2f}"
    cv2.rectangle(frame, (0, 0), (min(width, max(360, len(label) * 11)), 29), (10, 15, 20), -1)
    cv2.putText(frame, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (235, 245, 255), 1, cv2.LINE_AA)
