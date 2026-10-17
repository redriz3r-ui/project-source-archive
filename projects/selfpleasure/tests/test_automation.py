import asyncio
import time

import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraService
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.automation import AutomationController, AutomationRule, AutomationState
from app.vision.calibration import CalibrationStore
from app.vision.object_tracker import ObjectObservation
from app.vision.service import FaceObservation


def setup(device=None, *, command_timeout=2.0):
    registry = DeviceRegistry()
    device = device or SimulatedDevice()
    registry.add(device)
    registry.select(device.info.identifier)
    camera = {"running": True}
    safety = SafetyController(registry, Settings(command_timeout_seconds=command_timeout))
    controller = AutomationController(
        registry, safety, lambda: camera["running"], lambda: True,
    )
    return controller, device, camera, safety


async def valid(controller, count=3):
    for index in range(count):
        await controller.handle_event(Event(
            "interaction_started" if index == 0 else "interaction_continued",
            {"confidence": 0.85, "observed_at": time.monotonic()},
        ))
        await asyncio.sleep(0.04)
    await asyncio.sleep(0.01)


def test_valid_activation_ends_and_cools_down():
    async def exercise():
        controller, device, _, safety = setup()
        assert controller.state == AutomationState.DISARMED
        await controller.arm(AutomationRule(duration=0.3, cooldown=0.5))
        await valid(controller)
        assert controller.state == AutomationState.ACTIVE
        assert device.last_intensity == 0.2
        await controller.handle_event(Event("interaction_ended"))
        assert controller.state == AutomationState.COOLDOWN
        assert device.last_intensity == 0
        await valid(controller)
        assert device.last_intensity == 0
        await controller.shutdown()
        assert not safety.running
    asyncio.run(exercise())


def test_tracking_loss_disarms_and_repeated_events_cannot_restart():
    async def exercise():
        controller, device, _, _ = setup()
        await controller.arm(AutomationRule(duration=0.3))
        await valid(controller)
        await controller.handle_event(Event("tracking_lost"))
        assert controller.state == AutomationState.DISARMED
        assert device.last_intensity == 0
        await valid(controller, 6)
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_camera_and_device_disconnect_fail_closed():
    async def exercise():
        controller, device, camera, _ = setup()
        await controller.arm(AutomationRule(duration=0.3))
        await valid(controller)
        camera["running"] = False
        await controller.handle_event(Event("camera_stopped"))
        assert controller.state == AutomationState.DISARMED
        assert device.last_intensity == 0
        camera["running"] = True
        await controller.arm(AutomationRule(duration=0.3))
        await valid(controller)
        controller.device_lost(device.info.identifier)
        await asyncio.sleep(0.05)
        assert controller.state == AutomationState.ERROR
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_emergency_stop_and_shutdown():
    async def exercise():
        controller, device, _, _ = setup()
        await controller.arm(AutomationRule(duration=0.3))
        await valid(controller)
        await controller.emergency_stop()
        assert controller.state == AutomationState.EMERGENCY_STOP
        assert device.last_intensity == 0
        await valid(controller)
        assert device.last_intensity == 0
        await controller.arm(AutomationRule(duration=0.3))  # explicit rearm only
        await valid(controller)
        await controller.shutdown()
        assert controller.state == AutomationState.EMERGENCY_STOP
        assert device.last_intensity == 0
    asyncio.run(exercise())


def test_watchdog_stops_when_updates_stall():
    async def exercise():
        controller, device, _, _ = setup()
        await controller.arm(AutomationRule(duration=1.0))
        await valid(controller)
        await asyncio.sleep(0.45)
        assert controller.state == AutomationState.DISARMED
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_delayed_command_times_out_and_errors():
    class DelayedDevice(SimulatedDevice):
        async def vibrate_feature(self, feature_index, intensity):
            await asyncio.sleep(0.2)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise():
        controller, device, _, _ = setup(DelayedDevice(), command_timeout=0.05)
        await controller.arm(AutomationRule(duration=0.3))
        await valid(controller)
        await asyncio.sleep(0.18)
        assert controller.state == AutomationState.ERROR
        assert device.last_intensity == 0
        assert device.stop_count >= 1
        await controller.shutdown()
    asyncio.run(exercise())


def test_no_activation_without_explicit_arm_or_valid_signal():
    async def exercise():
        controller, device, camera, _ = setup()
        await valid(controller)
        assert device.last_intensity == 0
        camera["running"] = False
        with pytest.raises(RuntimeError):
            await controller.arm(AutomationRule())
        camera["running"] = True
        await controller.arm(AutomationRule())
        for _ in range(4):
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.9, "observed_at": time.monotonic() - 2,
            }))
        assert controller.state == AutomationState.ARMED
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_emergency_stop_racing_activation_stays_off():
    async def exercise():
        controller, device, _, _ = setup()
        await controller.arm(AutomationRule(duration=0.3))
        await valid(controller, 2)
        signal = Event("interaction_continued", {
            "confidence": 0.9, "observed_at": time.monotonic(),
        })
        await asyncio.gather(controller.handle_event(signal), controller.emergency_stop())
        await asyncio.sleep(0.05)
        assert controller.state == AutomationState.EMERGENCY_STOP
        assert device.last_intensity == 0
        await controller.handle_event(signal)
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_camera_event_bus_drives_only_armed_simulator(tmp_path):
    face = FaceObservation(
        face_detected=True, mouth_detected=True, mouth_x=0.5, mouth_y=0.5,
        mouth_openness=0.2, mouth_width=0.12, mouth_region=(0.44, 0.47, 0.12, 0.06),
        tracking_quality=0.95,
    )

    class Source:
        def open(self): pass
        def read(self): return np.zeros((120, 160, 3), dtype=np.uint8)
        def close(self): pass

    class Vision:
        def open(self): pass
        def process(self, frame, timestamp_ms, overlay): return face, frame
        def close(self): pass

    class ObjectDetector:
        index = 0

        def process(self, frame):
            x = max(0.62, 0.9 - self.index * 0.02) if self.index < 15 else (0.60 if self.index % 2 else 0.63)
            self.index += 1
            return ObjectObservation(True, x, 0.5, (x - 0.02, 0.48, 0.04, 0.04), 0.9, source="marker")

    camera = CameraService(
        Settings(camera_target_fps=24), source_factory=Source, vision_factory=Vision,
        calibration=CalibrationStore(tmp_path / "config.local.json"),
        object_detector_factory=lambda _: ObjectDetector(),
    )
    with TestClient(create_app(Settings(), camera=camera), base_url="http://127.0.0.1:8000") as web:
        web.post("/api/devices/simulated")
        web.post("/api/devices/select", json={"device_id": "simulator-1"})
        device = web.app.state.services.devices.get("simulator-1")
        web.post("/api/camera/start")
        deadline = time.monotonic() + 2
        while camera.snapshot()["status"] != "running" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert device.last_intensity == 0
        response = web.post("/api/automation/arm", json={
            "feature_index": 0, "intensity": 0.2, "duration": 0.3, "cooldown": 0.5,
        })
        assert response.status_code == 200, response.text
        deadline = time.monotonic() + 3
        while device.last_intensity == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert device.last_intensity == 0.2, (camera.snapshot(), camera.events_after(), web.get("/api/automation/status").json())
        web.post("/api/camera/stop")
        assert device.last_intensity == 0
        assert web.get("/api/automation/status").json()["state"] == "DISARMED"
