"""MediaPipe Face Landmarker adapter with local, timestamped video inference."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.paths import resource_path
from app.vision.geometry import mouth_geometry


DEFAULT_MODEL_PATH = resource_path(".models", "face_landmarker.task")


@dataclass(frozen=True, slots=True)
class FaceObservation:
    face_detected: bool = False
    mouth_detected: bool = False
    mouth_x: float | None = None
    mouth_y: float | None = None
    mouth_openness: float | None = None
    mouth_width: float | None = None
    mouth_region: tuple[float, float, float, float] | None = None
    head_motion: float = 0.0
    tracking_quality: float = 0.0
    frame_aspect_ratio: float = 4 / 3


class VisionService:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = model_path
        self.models_loaded = False
        self._landmarker: Any | None = None
        self._mp: Any | None = None
        self._last_face_center: tuple[float, float] | None = None
        self._last_timestamp_ms: int | None = None

    def open(self) -> None:
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Face model missing: {self.model_path}. Run the model download step in README.md."
            )
        import mediapipe as mp

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self._mp = mp
        self.models_loaded = True

    def process(self, frame: np.ndarray, timestamp_ms: int, overlay: bool) -> tuple[FaceObservation, np.ndarray]:
        if self._landmarker is None or self._mp is None:
            raise RuntimeError("Face Landmarker is not initialized")
        inference_frame = frame
        if cv2.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))[0] < 55:
            # Gentle local contrast recovery helps in dim rooms without changing
            # the original preview or storing a processed image.
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            light, a, b = cv2.split(lab)
            light = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(light)
            inference_frame = cv2.cvtColor(cv2.merge((light, a, b)), cv2.COLOR_LAB2BGR)
        rgb = cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        if not result.face_landmarks:
            self._last_face_center = None
            self._last_timestamp_ms = None
            return FaceObservation(), frame
        landmarks = result.face_landmarks[0]
        mouth = mouth_geometry(landmarks)
        anchors = (1, 4, 33, 133, 152, 168, 234, 263, 362, 454)
        valid_anchors = [landmarks[index] for index in anchors if index < len(landmarks)]
        in_frame = sum(0 <= point.x <= 1 and 0 <= point.y <= 1 for point in valid_anchors)
        tracking_quality = in_frame / len(valid_anchors) if valid_anchors else 0.0
        presence = [point.presence for point in valid_anchors if getattr(point, "presence", None) is not None]
        if presence:
            tracking_quality = min(tracking_quality, sum(presence) / len(presence))
        face_center = (landmarks[1].x, landmarks[1].y)
        head_motion = 0.0
        if self._last_face_center is not None and self._last_timestamp_ms is not None:
            elapsed = max((timestamp_ms - self._last_timestamp_ms) / 1000, 1e-3)
            head_motion = min(10.0, ((face_center[0] - self._last_face_center[0]) ** 2 +
                                      (face_center[1] - self._last_face_center[1]) ** 2) ** 0.5 / elapsed)
        self._last_face_center = face_center
        self._last_timestamp_ms = timestamp_ms
        if overlay:
            self._draw_overlay(frame, landmarks, mouth)
        if mouth is None:
            return FaceObservation(face_detected=True, head_motion=head_motion,
                                   tracking_quality=tracking_quality), frame
        return FaceObservation(
            face_detected=True,
            mouth_detected=True,
            mouth_x=mouth.x,
            mouth_y=mouth.y,
            mouth_openness=mouth.openness,
            mouth_width=mouth.width,
            mouth_region=mouth.region,
            head_motion=head_motion,
            tracking_quality=tracking_quality,
            frame_aspect_ratio=frame.shape[1] / frame.shape[0],
        ), frame

    @staticmethod
    def _draw_overlay(frame: np.ndarray, landmarks: Any, mouth: Any) -> None:
        height, width = frame.shape[:2]
        # Sparse face anchors keep the preview readable; the lips get a full outline.
        for index in (1, 4, 33, 133, 168, 263, 362, 234, 454, 152):
            if index < len(landmarks):
                point = landmarks[index]
                cv2.circle(frame, (int(point.x * width), int(point.y * height)), 2, (100, 220, 255), -1)
        if len(landmarks) > 291:
            lip_indices = (61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91, 61)
            points = np.array(
                [(int(landmarks[index].x * width), int(landmarks[index].y * height)) for index in lip_indices],
                dtype=np.int32,
            )
            cv2.polylines(frame, [points], False, (70, 235, 155), 2, cv2.LINE_AA)
        if mouth is not None:
            cv2.circle(frame, (int(mouth.x * width), int(mouth.y * height)), 4, (0, 255, 255), -1)

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        self._mp = None
        self.models_loaded = False
        self._last_face_center = None
        self._last_timestamp_ms = None
