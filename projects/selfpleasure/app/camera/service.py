"""Single-owner webcam worker and in-memory MJPEG preview frames."""

import asyncio
from collections import deque
from dataclasses import asdict
import threading
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Protocol

import cv2
import numpy as np

from app.config import Settings
from app.diagnostics import LatencyRecorder, TraceStage
from app.vision.service import FaceObservation, VisionService
from app.vision.calibration import CalibrationStore
from app.vision.interaction import (
    InteractionEstimate, InteractionEstimator, InteractionEvent,
    state_change_event,
)
from app.vision.object_tracker import ObjectDetector, ObjectObservation, OpenCVObjectTracker
from app.vision.overlays import draw_interaction_overlay
from app.vision.hand_tracking import (
    HandCalibrationStore, HandLandmarkerService, HandTracking, estimate_hand_axis,
)
from app.vision.stroke_estimator import StrokeEstimator
from app.vision.stroke_contract import StrokeEvent, StrokeObservation
from app.events import Event
from app.vision.interaction import InteractionState


class CameraStatus(StrEnum):
    INACTIVE = "inactive"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class CameraSource(Protocol):
    def open(self) -> None: ...

    def read(self) -> np.ndarray | None: ...

    def close(self) -> None: ...


class OpenCVCameraSource:
    def __init__(self, index: int, width: int, height: int, fps: int) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        capture = cv2.VideoCapture(self.index, cv2.CAP_AVFOUNDATION)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("Could not open webcam. Check macOS camera permission and close other camera apps.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        self._capture = capture

    def read(self) -> np.ndarray | None:
        if self._capture is None:
            return None
        okay, frame = self._capture.read()
        return frame if okay else None

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class CameraService:
    def __init__(
        self,
        settings: Settings = Settings(),
        source_factory: Callable[[], CameraSource] | None = None,
        vision_factory: Callable[[], VisionService] = VisionService,
        calibration: CalibrationStore | None = None,
        object_detector_factory: Callable[[CalibrationStore], ObjectDetector] = OpenCVObjectTracker,
        latency: LatencyRecorder | None = None,
        hand_vision_factory: Callable[[], HandLandmarkerService] = HandLandmarkerService,
        hand_calibration: HandCalibrationStore | None = None,
    ) -> None:
        self.settings = settings
        self.camera_index = settings.camera_index
        self._source_factory = source_factory or (
            lambda: OpenCVCameraSource(
                self.camera_index, settings.camera_width,
                settings.camera_height, settings.camera_target_fps,
            )
        )
        self._vision_factory = vision_factory
        self._hand_vision_factory = hand_vision_factory
        self.hand_calibration = hand_calibration or HandCalibrationStore()
        self.mode = "oral"
        self.hand_tracking = HandTracking()
        self.stroke_observation: StrokeObservation | None = None
        self._stroke_estimator = StrokeEstimator()
        self._stroke_events: deque[StrokeEvent] = deque(maxlen=200)
        self._reset_stroke = False
        self.calibration = calibration or CalibrationStore()
        self._object_detector_factory = object_detector_factory
        self._object_detector = object_detector_factory(self.calibration)
        self._interaction = InteractionEstimator()
        self._events: deque[InteractionEvent] = deque(maxlen=100)
        self._event_sequence = 0
        self._reset_interaction = False
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.status = CameraStatus.INACTIVE
        self.error: str | None = None
        self.overlay_enabled = True
        self.observation = FaceObservation()
        self.object_observation = ObjectObservation()
        self.interaction_estimate = InteractionEstimate()
        self.fps = 0.0
        self.records_frames = False
        self.uploads_frames = False
        self._jpeg: bytes | None = None
        self._raw_frame: np.ndarray | None = None
        self._sequence = 0
        self._event_sink: Callable[[Event], None] | None = None
        self._latency = latency

    def set_latency_recorder(self, recorder: LatencyRecorder | None) -> None:
        self._latency = recorder

    def set_event_sink(self, sink: Callable[[Event], None] | None) -> None:
        self._event_sink = sink

    def start(self) -> None:
        with self._condition:
            if self.status in {CameraStatus.STARTING, CameraStatus.RUNNING, CameraStatus.STOPPING}:
                raise RuntimeError("Camera is already active")
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Previous camera worker is still stopping")
            self._stop_event.clear()
            self._jpeg = None
            self._raw_frame = None
            self._sequence += 1
            self.observation = FaceObservation()
            self.object_observation = ObjectObservation()
            self.interaction_estimate = InteractionEstimate()
            self.hand_tracking = HandTracking()
            self.stroke_observation = None
            self._stroke_estimator.reset()
            self._stroke_events.clear()
            self._interaction.reset()
            self._object_detector = self._object_detector_factory(self.calibration)
            self._events.clear()
            self._event_sequence = 0
            self.fps = 0.0
            self.error = None
            self.status = CameraStatus.STARTING
            self._thread = threading.Thread(target=self._run, name="selfpleasure-camera", daemon=True)
            self._thread.start()

    def set_overlay(self, enabled: bool) -> None:
        with self._condition:
            self.overlay_enabled = enabled

    def set_mode(self, mode: str) -> None:
        if mode not in {"oral", "hand"}:
            raise ValueError("Camera mode must be oral or hand")
        with self._condition:
            if self.status not in {CameraStatus.INACTIVE, CameraStatus.ERROR} or (
                self._thread is not None and self._thread.is_alive()
            ):
                raise RuntimeError("Stop the camera before changing modes")
            self.status = CameraStatus.INACTIVE
            self.mode = mode
            self.hand_tracking = HandTracking()
            self.stroke_observation = None

    def update_hand_calibration(self, **changes: object) -> dict[str, object]:
        with self._condition:
            config = self.hand_calibration.update(**changes)
            self._reset_stroke = True
        return asdict(config)

    def stroke_events(self) -> list[dict[str, object]]:
        with self._condition:
            return [asdict(event) for event in self._stroke_events]

    def set_camera_index(self, index: int) -> None:
        if not isinstance(index, int) or not 0 <= index <= 9:
            raise ValueError("Camera index must be between 0 and 9")
        with self._condition:
            if self.status != CameraStatus.INACTIVE:
                raise RuntimeError("Stop the camera before changing its input")
            self.camera_index = index

    def calibration_snapshot(self) -> dict[str, object]:
        return self.calibration.as_dict()

    def update_calibration(self, **changes: object) -> dict[str, object]:
        config = self.calibration.update(**changes)
        with self._condition:
            self._reset_interaction = True
        return asdict(config)

    def calibrate_mouth(self) -> dict[str, object]:
        with self._condition:
            face = self.observation
        if not face.mouth_detected or face.mouth_width is None or face.mouth_openness is None:
            raise RuntimeError("Keep your face visible before calibrating the mouth")
        return self.update_calibration(
            mouth_width_reference=face.mouth_width,
            neutral_mouth_openness=face.mouth_openness,
        )

    def calibrate_marker(self, x: float, y: float) -> dict[str, object]:
        with self._condition:
            frame = self._raw_frame.copy() if self._raw_frame is not None else None
        if frame is None:
            raise RuntimeError("Start the camera and show the marker before calibrating")
        config = self.calibration.calibrate_marker(frame, x, y)
        with self._condition:
            self._reset_interaction = True
        return asdict(config)

    def events_after(self, sequence: int = 0) -> list[dict[str, object]]:
        with self._condition:
            return [asdict(event) for event in self._events if event.sequence > sequence]

    def wait_for_event(self, sequence: int, timeout: float = 1.0) -> list[dict[str, object]]:
        with self._condition:
            self._condition.wait_for(
                lambda: self._event_sequence > sequence or self.status in {CameraStatus.INACTIVE, CameraStatus.ERROR},
                timeout=timeout,
            )
            return [asdict(event) for event in self._events if event.sequence > sequence]

    def snapshot(self) -> dict[str, object]:
        with self._condition:
            observation = self.observation
            obj = self.object_observation
            interaction = self.interaction_estimate
            return {
                "status": self.status,
                "mode": self.mode,
                "hand": asdict(self.hand_tracking),
                "stroke": asdict(self.stroke_observation) if self.stroke_observation else None,
                "stroke_event_count": len(self._stroke_events),
                "camera_index": self.camera_index,
                "error": self.error,
                "face_detected": observation.face_detected,
                "mouth_detected": observation.mouth_detected,
                "mouth_x": observation.mouth_x,
                "mouth_y": observation.mouth_y,
                "mouth_openness": observation.mouth_openness,
                "fps": round(self.fps, 1),
                "overlay_enabled": self.overlay_enabled,
                "mouth_region": observation.mouth_region,
                "mouth_width": observation.mouth_width,
                "head_motion": round(observation.head_motion, 3),
                "face_tracking_quality": round(observation.tracking_quality, 2),
                "object_detected": obj.detected,
                "object_x": obj.x,
                "object_y": obj.y,
                "object_region": obj.region,
                "object_tracking_quality": round(obj.tracking_quality, 2),
                "object_mode": obj.source,
                "marker_axis_degrees": obj.marker_axis_degrees,
                "interaction_state": interaction.state,
                "interaction_confidence": interaction.confidence,
                "distance_mouth_widths": interaction.distance_mouth_widths,
                "bearing_degrees": interaction.bearing_degrees,
                "evidence_frames": interaction.evidence_frames,
            }

    def wait_for_frame(self, after_sequence: int, timeout: float = 1.0) -> tuple[int, bytes] | None:
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    (self._jpeg is not None and self._sequence > after_sequence)
                    or self.status in {CameraStatus.INACTIVE, CameraStatus.ERROR, CameraStatus.STOPPING}
                ),
                timeout=timeout,
            )
            if self._jpeg is None or self.status not in {CameraStatus.RUNNING, CameraStatus.STARTING}:
                return None
            if self._sequence <= after_sequence:
                return None
            return self._sequence, self._jpeg

    def _run(self) -> None:
        source = None
        vision = None
        previous = None
        try:
            source = self._source_factory()
            mode = self.mode
            vision = self._hand_vision_factory() if mode == "hand" else self._vision_factory()
            vision.open()
            if self._stop_event.is_set():
                return
            source.open()
            if self._stop_event.is_set():
                return
            with self._condition:
                self.status = CameraStatus.RUNNING
                self._condition.notify_all()
            while not self._stop_event.is_set():
                started = time.monotonic()
                frame_id = self._sequence + 1
                latency = self._latency
                if latency is not None:
                    latency.mark(frame_id, TraceStage.FRAME_READ_STARTED)
                frame = source.read()
                if frame is None:
                    raise RuntimeError("Webcam stopped returning frames")
                captured_ns = time.monotonic_ns()
                if latency is not None:
                    latency.mark(frame_id, TraceStage.FRAME_CAPTURED, captured_ns)
                frame = cv2.resize(frame, (self.settings.camera_width, self.settings.camera_height))
                frame = cv2.flip(frame, 1)
                raw_frame = frame.copy()
                timestamp_ms = captured_ns // 1_000_000
                with self._condition:
                    overlay = self.overlay_enabled
                    reset_interaction = self._reset_interaction
                    self._reset_interaction = False
                    reset_stroke = self._reset_stroke
                    self._reset_stroke = False
                    hand_config = self.hand_calibration.snapshot() if mode == "hand" else None
                if reset_interaction:
                    self._interaction.reset()
                if reset_stroke:
                    self._stroke_estimator.reset()
                if mode == "hand":
                    hands = vision.process(frame, timestamp_ms)
                    if latency is not None:
                        latency.mark(frame_id, TraceStage.HAND_DETECTED)
                    assert hand_config is not None
                    marker = None
                    if hand_config.marker_anchor:
                        marker_config, _ = self.calibration.snapshot()
                        if marker_config.mode == "marker" and marker_config.marker_hue is not None:
                            tracked_marker = self._object_detector.process(raw_frame)
                            if tracked_marker.detected and tracked_marker.x is not None and tracked_marker.y is not None:
                                marker = (tracked_marker.x, tracked_marker.y)
                        if latency is not None:
                            latency.mark(frame_id, TraceStage.OBJECT_DETECTED)
                    hand_tracking = estimate_hand_axis(
                        hands, hand_config, frame.shape[1] / frame.shape[0], marker,
                    )
                    stroke_observation, stroke_events = self._stroke_estimator.update(
                        hand_tracking, captured_ns, frame_id,
                    )
                    if latency is not None:
                        latency.mark(frame_id, TraceStage.STROKE_DECIDED)
                    if overlay:
                        self._draw_hand_overlay(frame, hand_tracking, hands)
                    rendered = frame
                    observation = FaceObservation()
                    obj = ObjectObservation()
                    estimate = InteractionEstimate()
                    previous_state = estimate.state
                else:
                    observation, rendered = vision.process(frame, timestamp_ms, overlay)
                    if latency is not None:
                        latency.mark(frame_id, TraceStage.FACE_DETECTED)
                    obj = self._object_detector.process(raw_frame)
                    if latency is not None:
                        latency.mark(frame_id, TraceStage.OBJECT_DETECTED)
                    config, _ = self.calibration.snapshot()
                    previous_state = self._interaction.estimate.state
                    estimate = self._interaction.update(observation, obj, time.monotonic(), config)
                    if latency is not None:
                        latency.mark(frame_id, TraceStage.ORAL_DECIDED)
                    if overlay:
                        draw_interaction_overlay(rendered, observation, obj, estimate, config)
                okay, encoded = cv2.imencode(".jpg", rendered, [cv2.IMWRITE_JPEG_QUALITY, 78])
                if not okay:
                    raise RuntimeError("Could not encode preview frame")
                now = time.monotonic()
                instant_fps = 1 / max(now - previous, 1e-6) if previous else 0.0
                previous = now
                with self._condition:
                    self.observation = observation
                    self.object_observation = obj
                    self.interaction_estimate = estimate
                    if mode == "hand":
                        self.hand_tracking = hand_tracking
                        self.stroke_observation = stroke_observation
                        self._stroke_events.extend(stroke_events)
                    self._raw_frame = raw_frame
                    if estimate.state != previous_state:
                        self._event_sequence += 1
                        self._events.append(state_change_event(
                            self._event_sequence, previous_state, estimate, observation, obj,
                        ))
                    self.fps = (self.fps * 0.8 + instant_fps * 0.2) if self.fps else instant_fps
                    self._jpeg = encoded.tobytes()
                    self._sequence += 1
                    self._condition.notify_all()
                sink = self._event_sink
                if sink is not None and mode == "hand":
                    tracking_state = ("RECOVERING" if self._stroke_estimator.recovering
                                      else hand_tracking.state)
                    sink(Event("stroke_observation", {
                        "stroke": asdict(stroke_observation),
                        "tracking_state": tracking_state,
                        "observed_at": time.monotonic(),
                    }))
                    for stroke_event in stroke_events:
                        topic = ("stroke_tracking_lost" if stroke_event.kind.value == "tracking_lost"
                                 else stroke_event.kind.value)
                        sink(Event(topic, {
                            "stroke": asdict(stroke_event),
                            "observed_at": time.monotonic(),
                        }))
                if sink is not None and mode == "oral":
                    if estimate.state == InteractionState.INTERACTION_ACTIVE:
                        topic = ("interaction_continued" if previous_state == InteractionState.INTERACTION_ACTIVE
                                 else "interaction_started")
                    elif estimate.state in {InteractionState.TRACKING_LOST, InteractionState.NO_FACE,
                                            InteractionState.NO_OBJECT}:
                        topic = "tracking_lost"
                    elif estimate.state == InteractionState.INTERACTION_ENDED or previous_state == InteractionState.INTERACTION_ACTIVE:
                        topic = "interaction_ended"
                    else:
                        topic = "vision_observation"
                    sink(Event(topic, {
                        "state": estimate.state.value, "confidence": estimate.confidence,
                        "frame_id": frame_id,
                        "observed_at": time.monotonic(),
                        "evaluation": {
                            "face_detected": observation.face_detected,
                            "mouth_detected": observation.mouth_detected,
                            "mouth_x": observation.mouth_x,
                            "mouth_y": observation.mouth_y,
                            "mouth_width": observation.mouth_width,
                            "mouth_openness": observation.mouth_openness,
                            "head_motion": observation.head_motion,
                            "face_quality": observation.tracking_quality,
                            "object_detected": obj.detected,
                            "object_x": obj.x,
                            "object_y": obj.y,
                            "object_quality": obj.tracking_quality,
                            "object_source": obj.source,
                            "distance_mouth_widths": estimate.distance_mouth_widths,
                            "confidence": estimate.confidence,
                            "state": estimate.state.value,
                        },
                    }))
                    if latency is not None:
                        latency.mark(frame_id, TraceStage.EVENT_EMITTED)
                self._stop_event.wait(max(0.0, 1 / self.settings.camera_target_fps - (time.monotonic() - started)))
        except Exception as exc:
            with self._condition:
                self.error = str(exc)
                self.status = CameraStatus.ERROR
                self._condition.notify_all()
        finally:
            sink = self._event_sink
            if sink is not None:
                sink(Event("camera_stopped", {"observed_at": time.monotonic()}))
            cleanup_error = None
            for resource in (vision, source):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception as exc:
                        cleanup_error = cleanup_error or str(exc)
            with self._condition:
                if cleanup_error and self.error is None:
                    self.error = f"Camera cleanup failed: {cleanup_error}"
                    self.status = CameraStatus.ERROR
                elif self.status != CameraStatus.ERROR:
                    self.status = CameraStatus.INACTIVE
                self._jpeg = None
                self._raw_frame = None
                self.observation = FaceObservation()
                self.object_observation = ObjectObservation()
                self.interaction_estimate = InteractionEstimate()
                self.hand_tracking = HandTracking()
                self.stroke_observation = None
                self.fps = 0.0
                self._condition.notify_all()

    @staticmethod
    def _draw_hand_overlay(frame: np.ndarray, tracking: HandTracking,
                           hands: list[list[object]]) -> None:
        height, width = frame.shape[:2]
        for landmarks in hands:
            for point in landmarks:
                if 0 <= point.x <= 1 and 0 <= point.y <= 1:
                    cv2.circle(frame, (round(point.x * width), round(point.y * height)),
                               2, (190, 130, 255), -1)
        if tracking.base is not None and tracking.endpoint is not None:
            base = (round(tracking.base[0] * width), round(tracking.base[1] * height))
            endpoint = (round(tracking.endpoint[0] * width), round(tracking.endpoint[1] * height))
            cv2.line(frame, base, endpoint, (30, 210, 255), 3, cv2.LINE_AA)
            cv2.circle(frame, base, 7, (0, 180, 255), -1)
            cv2.circle(frame, endpoint, 7, (0, 255, 100), -1)
        if tracking.hand_x is not None and tracking.hand_y is not None:
            cv2.circle(frame, (round(tracking.hand_x * width), round(tracking.hand_y * height)),
                       9, (255, 100, 200), 2, cv2.LINE_AA)

    async def stop(self) -> None:
        with self._condition:
            if self.status == CameraStatus.INACTIVE:
                return
            self._stop_event.set()
            if self.status != CameraStatus.ERROR:
                self.status = CameraStatus.STOPPING
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            await asyncio.to_thread(thread.join, 5)
            if thread.is_alive():
                with self._condition:
                    self.error = "Camera did not stop within five seconds"
                    self.status = CameraStatus.ERROR
                return
        with self._condition:
            self.status = CameraStatus.INACTIVE
            self._jpeg = None
            self._raw_frame = None
            self.observation = FaceObservation()
            self.object_observation = ObjectObservation()
            self.interaction_estimate = InteractionEstimate()
            self.hand_tracking = HandTracking()
            self.stroke_observation = None
            self.fps = 0.0
            self._condition.notify_all()

    async def shutdown(self) -> None:
        await self.stop()
