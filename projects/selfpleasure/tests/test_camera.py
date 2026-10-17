import asyncio
import time
from types import SimpleNamespace

import numpy as np
from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraService, CameraStatus
from app.config import Settings
from app.devices import DeviceRegistry, SimulatedDevice
from app.safety import SafetyController
from app.vision.geometry import mouth_geometry
from app.vision.service import FaceObservation


def landmarks(scale: float = 1.0, shift_x: float = 0.0):
    points = [SimpleNamespace(x=0.0, y=0.0) for _ in range(292)]
    points[61] = SimpleNamespace(x=shift_x + 0.4 * scale, y=0.5)
    points[291] = SimpleNamespace(x=shift_x + 0.6 * scale, y=0.5)
    points[13] = SimpleNamespace(x=shift_x + 0.5 * scale, y=0.5 - 0.02 * scale)
    points[14] = SimpleNamespace(x=shift_x + 0.5 * scale, y=0.5 + 0.02 * scale)
    return points


def test_mouth_geometry_is_scale_and_position_robust() -> None:
    first = mouth_geometry(landmarks())
    second = mouth_geometry(landmarks(scale=0.5, shift_x=0.2))
    assert first is not None and second is not None
    assert abs(first.openness - 0.2) < 1e-6
    assert abs(first.openness - second.openness) < 1e-6
    assert abs(first.x - 0.5) < 1e-6
    assert abs(second.x - 0.45) < 1e-6
    assert mouth_geometry(landmarks()[:20]) is None


def test_mouth_openness_is_stable_under_head_roll() -> None:
    points = landmarks()
    rotated = [SimpleNamespace(x=0.5 - (point.y - 0.5), y=0.5 + (point.x - 0.5)) for point in points]
    original = mouth_geometry(points)
    rolled = mouth_geometry(rotated)
    assert original is not None and rolled is not None
    assert abs(original.openness - rolled.openness) < 1e-6


class MockCameraSource:
    def __init__(self, fails: bool = False) -> None:
        self.fails = fails
        self.opened = False
        self.closed = False
        self.read_count = 0

    def open(self) -> None:
        self.opened = True

    def read(self):
        self.read_count += 1
        if self.fails:
            return None
        return np.zeros((120, 160, 3), dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


class MockVision:
    def __init__(self) -> None:
        self.closed = False

    def open(self) -> None:
        pass

    def process(self, frame, timestamp_ms, overlay):
        return FaceObservation(True, True, 0.5, 0.55, 0.2), frame

    def close(self) -> None:
        self.closed = True


def wait_for_status(camera: CameraService, wanted: CameraStatus) -> None:
    deadline = time.monotonic() + 2
    while camera.status != wanted and time.monotonic() < deadline:
        time.sleep(0.01)
    assert camera.status == wanted


def test_mock_camera_streams_in_memory_then_stops() -> None:
    source = MockCameraSource()
    vision = MockVision()
    camera = CameraService(
        Settings(camera_target_fps=20),
        source_factory=lambda: source,
        vision_factory=lambda: vision,
    )
    assert camera.status == CameraStatus.INACTIVE
    assert source.opened is False
    camera.start()
    wait_for_status(camera, CameraStatus.RUNNING)
    result = camera.wait_for_frame(0, 2)
    assert result is not None and result[1].startswith(b"\xff\xd8")
    state = camera.snapshot()
    assert state["face_detected"] is True
    assert state["mouth_detected"] is True
    assert state["mouth_openness"] == 0.2
    camera.set_overlay(False)
    assert camera.snapshot()["overlay_enabled"] is False
    asyncio.run(camera.stop())
    assert source.closed and vision.closed
    assert camera.snapshot()["status"] == CameraStatus.INACTIVE
    assert camera.wait_for_frame(result[0], 0) is None


def test_camera_failure_isolated_from_device_control() -> None:
    source = MockCameraSource(fails=True)
    camera = CameraService(source_factory=lambda: source, vision_factory=MockVision)
    registry = DeviceRegistry()
    device = SimulatedDevice()
    registry.add(device)
    safety = SafetyController(registry)
    camera.start()
    wait_for_status(camera, CameraStatus.ERROR)
    assert camera.snapshot()["error"] == "Webcam stopped returning frames"
    assert safety.activation_enabled is False
    assert device.stop_count == 0
    asyncio.run(camera.stop())
    assert source.closed


def test_camera_api_requires_explicit_start_with_injected_source() -> None:
    source = MockCameraSource()
    camera = CameraService(
        source_factory=lambda: source,
        vision_factory=MockVision,
    )
    with TestClient(create_app(Settings(), camera=camera), base_url="http://127.0.0.1:8000") as web:
        assert web.get("/camera").status_code == 200
        assert web.get("/api/camera/status").json()["status"] == "inactive"
        assert web.get("/api/camera/stream").status_code == 409
        assert source.opened is False
        assert web.post("/api/camera/start").status_code == 202
        wait_for_status(camera, CameraStatus.RUNNING)
        assert web.post("/api/camera/overlay", json={"enabled": False}).json()["overlay_enabled"] is False
        assert web.post("/api/camera/stop").json()["status"] == "inactive"
    assert source.closed
