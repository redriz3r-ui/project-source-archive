import asyncio
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraService
from app.config import Settings
from app.vision.calibration import Calibration, CalibrationStore
from app.vision.benchmark import evaluate_cases
from app.vision.interaction import InteractionEstimator, InteractionState
from app.vision.object_tracker import ObjectObservation, OpenCVObjectTracker
from app.vision.service import FaceObservation


FACE = FaceObservation(
    face_detected=True, mouth_detected=True, mouth_x=0.5, mouth_y=0.5,
    mouth_openness=0.2, mouth_width=0.12,
    mouth_region=(0.44, 0.47, 0.12, 0.06), tracking_quality=0.95,
)


def object_at(x: float, y: float = 0.5) -> ObjectObservation:
    return ObjectObservation(True, x, y, (x - 0.02, y - 0.02, 0.04, 0.04), 0.9, source="marker")


def test_sustained_motion_enters_active_then_ended() -> None:
    estimator = InteractionEstimator()
    config = Calibration()
    assert estimator.update(FaceObservation(), ObjectObservation(), 0, config).state == InteractionState.NO_FACE
    assert estimator.update(FACE, ObjectObservation(), 0.1, config).state == InteractionState.NO_OBJECT
    states = []
    for index, x in enumerate((0.90, 0.82, 0.75, 0.70, 0.66, 0.63, 0.60, 0.63, 0.60, 0.64, 0.60, 0.63)):
        states.append(estimator.update(FACE, object_at(x), 0.2 + index * 0.1, config).state)
    assert InteractionState.OBJECT_VISIBLE in states
    assert InteractionState.OBJECT_APPROACHING in states
    assert InteractionState.POSSIBLE_INTERACTION in states
    assert states[-1] == InteractionState.INTERACTION_ACTIVE
    for index, x in enumerate((0.72, 0.76, 0.80, 0.84)):
        ended = estimator.update(FACE, object_at(x), 1.4 + index * 0.1, config)
    assert ended.state == InteractionState.INTERACTION_ENDED
    assert 0 <= ended.confidence <= 1


def test_brief_pass_does_not_become_active() -> None:
    estimator = InteractionEstimator()
    states = []
    for index, x in enumerate((0.9, 0.65, 0.62, 0.9, 0.9)):
        states.append(estimator.update(FACE, object_at(x), index * 0.1, Calibration()).state)
    assert InteractionState.POSSIBLE_INTERACTION in states
    assert InteractionState.INTERACTION_ACTIVE not in states


def test_face_loss_object_occlusion_and_recovery() -> None:
    estimator = InteractionEstimator()
    config = Calibration()
    estimator.update(FACE, object_at(0.62), 0, config)
    assert estimator.update(FaceObservation(), object_at(0.62), 0.1, config).state == InteractionState.TRACKING_LOST
    assert estimator.update(FaceObservation(), object_at(0.62), 0.8, config).state == InteractionState.NO_FACE
    assert estimator.update(FACE, object_at(0.62), 0.9, config).state == InteractionState.POSSIBLE_INTERACTION
    assert estimator.update(FACE, ObjectObservation(), 1.0, config).state == InteractionState.TRACKING_LOST
    assert estimator.update(FACE, object_at(0.62), 1.1, config).state == InteractionState.POSSIBLE_INTERACTION


def test_rapid_movement_is_tracking_lost() -> None:
    estimator = InteractionEstimator()
    estimator.update(FACE, object_at(0.62), 0, Calibration())
    assert estimator.update(FACE, object_at(0.9), 0.01, Calibration()).state == InteractionState.TRACKING_LOST


def test_vertical_geometry_uses_frame_aspect_ratio() -> None:
    estimator = InteractionEstimator()
    face = FaceObservation(
        face_detected=True, mouth_detected=True, mouth_x=0.5, mouth_y=0.5,
        mouth_width=0.12, mouth_openness=0.2, tracking_quality=0.95,
        frame_aspect_ratio=4 / 3,
    )
    result = estimator.update(face, object_at(0.5, 0.74), 0, Calibration())
    assert result.distance_mouth_widths == 1.5
    assert result.state == InteractionState.POSSIBLE_INTERACTION


def test_alternating_near_motion_stays_active_and_withdrawal_ends_immediately() -> None:
    estimator = InteractionEstimator()
    config = Calibration()
    states = [estimator.update(FACE, object_at(x), index * 0.1, config).state
              for index, x in enumerate((0.9, 0.8, 0.7, 0.64, 0.60, 0.64,
                                         0.60, 0.64, 0.60, 0.64, 0.60, 0.64,
                                         0.60, 0.64, 0.60, 0.64, 0.60, 0.64))]
    assert states[-6:] == [InteractionState.INTERACTION_ACTIVE] * 6
    assert estimator.update(FACE, object_at(0.72), 1.8, config).state == InteractionState.INTERACTION_ENDED


def test_offline_benchmark_is_labeled_and_has_no_hardware_dependency() -> None:
    result = evaluate_cases()
    assert result.frames == 92
    assert result.true_positive + result.false_negative == 25
    assert result.true_negative + result.false_positive == 67
    assert result.recall is not None and result.false_positive_rate is not None


def test_marker_calibration_and_detection_are_local(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path / "config.local.json")
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    cv2.rectangle(frame, (45, 35), (85, 75), (0, 0, 255), -1)
    config = store.calibrate_marker(frame, 65 / 160, 55 / 120)
    assert config.marker_hue is not None
    observation = OpenCVObjectTracker(store).process(frame)
    assert observation.detected
    assert observation.source == "marker"
    assert abs(observation.x - 65 / 160) < 0.04
    contents = (tmp_path / "config.local.json").read_text()
    assert "marker_hue" in contents and "image" not in contents
    assert store.as_dict()["marker_hue"] == config.marker_hue
    assert CalibrationStore(tmp_path / "config.local.json").as_dict()["marker_hue"] == config.marker_hue


def test_manual_roi_mode_tracks_selected_rectangle(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path / "config.local.json")
    store.update(mode="roi", manual_roi=(0.2, 0.2, 0.25, 0.25))
    rng = np.random.default_rng(4)
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[40:90, 40:90] = rng.integers(0, 255, (50, 50, 3), dtype=np.uint8)
    tracker = OpenCVObjectTracker(store)
    first = tracker.process(frame)
    second = tracker.process(frame)
    assert first.detected and second.detected
    assert first.source == second.source == "roi"


class FakeSource:
    def open(self):
        pass

    def read(self):
        return np.zeros((120, 160, 3), dtype=np.uint8)

    def close(self):
        pass


class FakeFaceVision:
    def open(self):
        pass

    def process(self, frame, timestamp_ms, overlay):
        return FACE, frame

    def close(self):
        pass


class FakeObjectDetector:
    def process(self, frame):
        return object_at(0.65)


def test_camera_events_do_not_activate_devices(tmp_path: Path) -> None:
    camera = CameraService(
        Settings(camera_target_fps=24), source_factory=FakeSource,
        vision_factory=FakeFaceVision,
        calibration=CalibrationStore(tmp_path / "config.local.json"),
        object_detector_factory=lambda _: FakeObjectDetector(),
    )
    with TestClient(create_app(Settings(), camera=camera), base_url="http://127.0.0.1:8000") as web:
        web.post("/api/devices/simulated")
        simulator = web.app.state.services.devices.get("simulator-1")
        assert web.post("/api/camera/start").status_code == 202
        deadline = time.monotonic() + 2
        while not camera.events_after() and time.monotonic() < deadline:
            time.sleep(0.01)
        events = web.get("/api/interaction/events").json()
        assert events and events[0]["state"] == "POSSIBLE_INTERACTION"
        assert simulator.last_intensity == 0
        assert web.post("/api/camera/stop").status_code == 200
    assert simulator.last_intensity == 0


def test_calibration_api_saves_only_numeric_parameters(tmp_path: Path) -> None:
    class ColoredSource(FakeSource):
        def read(self):
            frame = super().read()
            cv2.rectangle(frame, (40, 30), (80, 70), (0, 0, 255), -1)
            return frame

    path = tmp_path / "config.local.json"
    camera = CameraService(
        Settings(camera_target_fps=24), source_factory=ColoredSource,
        vision_factory=FakeFaceVision,
        calibration=CalibrationStore(path),
    )
    with TestClient(create_app(Settings(), camera=camera), base_url="http://127.0.0.1:8000") as web:
        assert web.post("/api/camera/start").status_code == 202
        assert camera.wait_for_frame(0, 2) is not None
        assert web.post("/api/calibration/mouth").status_code == 200
        marker = web.post("/api/calibration/marker", json={"x": 0.62, "y": 0.42})
        assert marker.status_code == 200
        assert marker.json()["marker_hue"] is not None
        settings = web.post("/api/calibration/settings", json={
            "mode": "marker", "near_distance_mouth_widths": 2.5, "sensitivity": 0.35,
        })
        assert settings.status_code == 200
        assert web.post("/api/calibration/roi", json={
            "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.3,
        }).status_code == 200
        assert web.post("/api/calibration/roi", json={
            "x": 0.9, "y": 0.9, "width": 0.3, "height": 0.3,
        }).status_code == 422
        assert web.get("/api/calibration").json()["mode"] == "roi"
        assert web.post("/api/camera/stop").status_code == 200
    saved = path.read_text()
    assert "manual_roi" in saved and "marker_hue" in saved
    assert "frame" not in saved and "image" not in saved
