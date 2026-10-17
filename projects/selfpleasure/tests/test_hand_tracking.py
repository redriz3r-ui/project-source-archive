"""Hand-mode geometry, mocked camera lifecycle, and no-device isolation."""

import asyncio
import math
import time
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraService, CameraStatus
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.safety.controller import SafetyController
from app.vision.hand_tracking import (
    HandCalibration, HandCalibrationStore, estimate_hand_axis, project_on_axis,
)


def landmarks(x: float, y: float, valid: int = 5):
    points = [SimpleNamespace(x=math.nan, y=math.nan) for _ in range(21)]
    for index in (0, 5, 9, 13, 17)[:valid]:
        points[index] = SimpleNamespace(x=x, y=y)
    return points


def axis(marker_anchor=False):
    return HandCalibration(base=(0.3, 0.5), endpoint=(0.7, 0.5),
                           marker_anchor=marker_anchor)


def test_axis_projection_is_relative_and_aspect_correct() -> None:
    position, lateral = project_on_axis((0.5, 0.5), axis().base, axis().endpoint, 4 / 3)
    assert position == pytest.approx(0.5)
    assert lateral == pytest.approx(0)
    assert project_on_axis((0.9, 0.5), axis().base, axis().endpoint, 4 / 3)[0] == 1
    assert project_on_axis((0.3, 0.6), axis().base, axis().endpoint, 4 / 3)[1] > 0


def test_camera_translation_is_compensated_by_marker_but_drift_is_rejected() -> None:
    initial = estimate_hand_axis([landmarks(0.5, 0.5)], axis(True), 4 / 3, (0.3, 0.5))
    shifted = estimate_hand_axis([landmarks(0.54, 0.53)], axis(True), 4 / 3, (0.34, 0.53))
    assert initial.state == shifted.state == "TRACKED"
    assert shifted.travel_position == pytest.approx(initial.travel_position)
    fixed_shifted = estimate_hand_axis([landmarks(0.54, 0.53)], axis(), 4 / 3)
    assert fixed_shifted.travel_position != pytest.approx(initial.travel_position)
    drifted = estimate_hand_axis([landmarks(0.5, 0.5)], axis(True), 4 / 3, (0.52, 0.5))
    assert drifted.state == "OBJECT_DRIFT"
    assert drifted.travel_position is None
    assert estimate_hand_axis([landmarks(0.5, 0.5)], axis(True), 4 / 3).state == "TRACKING_LOST"


def test_partial_occlusion_two_hands_and_marker_loss() -> None:
    partial = estimate_hand_axis([landmarks(0.5, 0.5, valid=2)], axis(), 4 / 3)
    assert partial.state == "TRACKED"
    assert partial.tracking_confidence < 0.5
    assert estimate_hand_axis([landmarks(0.5, 0.5, valid=1)], axis(), 4 / 3).state == "TRACKING_LOST"
    assert estimate_hand_axis([landmarks(0.45, 0.5), landmarks(0.55, 0.5)],
                              axis(), 4 / 3).state == "MULTIPLE_HANDS"
    assert estimate_hand_axis([], axis(), 4 / 3).state == "TRACKING_LOST"


def test_hand_calibration_is_numeric_only_and_validated(tmp_path) -> None:
    store = HandCalibrationStore(tmp_path / "hand.json")
    with pytest.raises(ValueError):
        store.update(base=(0.5, 0.5), endpoint=(0.51, 0.5))
    with pytest.raises(ValueError):
        store.update(base=(0.1, float("nan")))
    saved = store.update(base=(0.3, 0.5), endpoint=(0.7, 0.5), marker_anchor=True)
    assert saved.marker_anchor
    assert HandCalibrationStore(store.path).snapshot() == saved
    assert set(__import__("json").loads(store.path.read_text())) == {
        "base", "endpoint", "marker_anchor",
    }


class MockSource:
    def __init__(self, fail=False):
        self.fail = fail
        self.reads = 0
        self.closed = False

    def open(self):
        pass

    def read(self):
        self.reads += 1
        return None if self.fail else np.zeros((120, 160, 3), dtype=np.uint8)

    def close(self):
        self.closed = True


class MockHandVision:
    def __init__(self):
        self.calls = 0
        self.closed = False

    def open(self):
        pass

    def process(self, frame, timestamp_ms):
        self.calls += 1
        return [landmarks(0.5, 0.5)]

    def close(self):
        self.closed = True


def wait_for(camera, predicate):
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert predicate()


def test_mock_hand_camera_requires_no_face_and_emits_no_device_events(tmp_path) -> None:
    source = MockSource()
    hand = MockHandVision()
    store = HandCalibrationStore(tmp_path / "hand.json")
    store.update(base=(0.3, 0.5), endpoint=(0.7, 0.5))
    camera = CameraService(
        Settings(camera_target_fps=20), source_factory=lambda: source,
        vision_factory=lambda: (_ for _ in ()).throw(AssertionError("face must not load")),
        hand_vision_factory=lambda: hand, hand_calibration=store,
    )
    events = []
    camera.set_event_sink(events.append)
    assert camera.status == CameraStatus.INACTIVE
    assert source.reads == 0
    camera.set_mode("hand")
    camera.start()
    wait_for(camera, lambda: camera.snapshot()["hand"]["state"] == "TRACKED")
    assert camera.snapshot()["face_detected"] is False
    assert camera.snapshot()["hand"]["travel_position"] == pytest.approx(0.5)
    assert camera.wait_for_frame(0, 1)[1].startswith(b"\xff\xd8")
    assert source.reads == hand.calls  # one worker, current frame only; no inference queue
    assert {event.topic for event in events} == {"stroke_observation"}
    asyncio.run(camera.stop())
    assert source.closed and hand.closed
    assert events[-1].topic == "camera_stopped"
    assert not any(event.topic.startswith("interaction_") for event in events)


def test_hand_camera_error_does_not_touch_device(tmp_path) -> None:
    source = MockSource(fail=True)
    camera = CameraService(source_factory=lambda: source,
                           hand_vision_factory=MockHandVision,
                           hand_calibration=HandCalibrationStore(tmp_path / "hand.json"))
    device = SimulatedDevice()
    registry = DeviceRegistry()
    registry.add(device)
    safety = SafetyController(registry)
    camera.set_mode("hand")
    camera.start()
    wait_for(camera, lambda: camera.status == CameraStatus.ERROR)
    assert safety.activation_enabled is False
    assert device.last_intensity == 0 and device.stop_count == 0
    asyncio.run(camera.stop())


def test_hand_api_is_opt_in_and_rejects_automation_arm(tmp_path) -> None:
    source = MockSource()
    camera = CameraService(source_factory=lambda: source,
                           hand_vision_factory=MockHandVision,
                           hand_calibration=HandCalibrationStore(tmp_path / "hand.json"))
    with TestClient(create_app(Settings(), camera=camera), base_url="http://127.0.0.1:8000") as web:
        assert web.get("/hand").status_code == 200
        assert web.get("/api/camera/status").json()["status"] == "inactive"
        assert source.reads == 0
        assert web.post("/api/camera/mode", json={"mode": "hand"}).json()["mode"] == "hand"
        assert web.post("/api/camera/start").status_code == 202
        wait_for(camera, lambda: camera.status == CameraStatus.RUNNING)
        assert web.post("/api/camera/mode", json={"mode": "oral"}).status_code == 409
        calibrated = web.post("/api/hand/calibration", json={
            "base_x": 0.3, "base_y": 0.5, "endpoint_x": 0.7, "endpoint_y": 0.5,
        })
        assert calibrated.status_code == 200
        assert web.get("/api/hand/calibration").json()["base"] == [0.3, 0.5]
        device_id = web.post("/api/devices/simulated").json()["id"]
        web.post("/api/devices/select", json={"device_id": device_id})
        assert web.post("/api/automation/arm", json={"feature_index": 0}).status_code == 409
        assert web.get("/api/automation/status").json()["state"] == "DISARMED"
        assert web.post("/api/camera/stop").status_code == 200
    assert source.closed
