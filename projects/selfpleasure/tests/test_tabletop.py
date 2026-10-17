"""Tabletop safety contracts, exercised entirely with injected devices."""

import asyncio
from dataclasses import asdict
import time

from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraStatus
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.hand_response import (
    HandResponseController, HandResponseMode, HandResponseRule, HandResponseState,
)
from app.vision.hand_tracking import HandTracking
from app.vision.stroke_contract import STROKE_SCHEMA_VERSION, StrokeDirection, StrokeObservation
from app.vision.stroke_estimator import StrokeEstimator
from tests.test_hand_response import Recorder, observation, started, updated
from tests.test_hand_session import InertRealDevice


def test_single_dropped_frame_does_not_erase_stroke_but_sustained_loss_does():
    estimator = StrokeEstimator()
    def sample(frame, position, timestamp_ms):
        tracking = HandTracking(state="TRACKED" if position is not None else "TRACKING_LOST",
                                travel_position=position,
                                tracking_confidence=0.9 if position is not None else 0)
        return estimator.update(tracking, timestamp_ms * 1_000_000, frame)

    sample(1, 0.1, 1000)
    sample(2, 0.19, 1050)
    sample(3, 0.25, 1100)
    before = estimator._active_id
    missing, events = sample(4, None, 1150)
    assert before is not None
    assert estimator.recovering is True
    assert missing.hand_position is None and events == ()
    sample(5, 0.30, 1200)
    assert estimator.recovering is False
    assert estimator._active_id == before
    sample(6, None, 1250)
    _, events = sample(7, None, 1310)
    assert [event.kind.value for event in events] == ["tracking_lost"]
    assert estimator._active_id is None


def test_uncertain_frame_stops_active_output_without_rearming_from_replay():
    async def exercise():
        devices = DeviceRegistry()
        device = Recorder()
        devices.add(device)
        devices.select(device.info.identifier)
        safety = SafetyController(devices)
        controller = HandResponseController(devices, safety, lambda: True)
        rule = HandResponseRule(duration=0.08, cooldown=0.08,
                                mode=HandResponseMode.FOLLOW_MOVEMENT)
        await controller.handle_event(observation(1))
        await controller.arm(rule, tabletop=True)
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(observation(3))
        movement = updated(3, 1)
        await controller.handle_event(movement)
        await asyncio.sleep(0.01)
        assert device.last_intensity > 0
        uncertain = StrokeObservation(STROKE_SCHEMA_VERSION, time.monotonic_ns(), 4,
                                      None, StrokeDirection.UNKNOWN, 0, 0, 0, 1)
        await controller.handle_event(Event("stroke_observation", {
            "stroke": asdict(uncertain), "tracking_state": "RECOVERING"}))
        assert device.last_intensity == 0
        assert controller.state == HandResponseState.COOLDOWN
        await asyncio.sleep(0.09)
        await controller.handle_event(observation(5))
        await controller.handle_event(movement)
        assert len(device.commands) == 1
        assert device.last_intensity == 0
        await controller.disarm("user_stop")
        assert controller.snapshot()["disarm_reason"] == "Stopped by user"
        await controller.shutdown()
    asyncio.run(exercise())


def test_tabletop_api_is_locked_by_default_and_requires_real_feature():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        body = {"feature_index": 2, "off_body_confirmed": True,
                "manual_preflight_confirmed": True, "physical_power_off_ready": True}
        current = web.app.state.services
        device = InertRealDevice()
        current.devices.add(device)
        current.devices.select(device.info.identifier)
        current.intiface.state.connected = True
        current.camera.status = CameraStatus.RUNNING
        current.camera.mode = "hand"
        current.hand_response._tracking_ns = time.monotonic_ns()
        assert web.post("/api/tabletop/arm", json={**body, "off_body_confirmed": False}).status_code == 409
        assert web.post("/api/tabletop/arm", json=body).status_code == 409
        assert current.hand_response.state == HandResponseState.DISARMED
        assert device.last_intensity == 0

    with TestClient(create_app(Settings(real_device_output_enabled=True)),
                    base_url="http://127.0.0.1:8000") as web:
        current = web.app.state.services
        device = InertRealDevice()
        current.devices.add(device)
        current.devices.select(device.info.identifier)
        current.intiface.state.connected = True
        current.camera.status = CameraStatus.RUNNING
        current.camera.mode = "hand"
        current.hand_response._tracking_ns = time.monotonic_ns()
        assert web.post("/api/tabletop/arm", json={**body, "feature_index": 0}).status_code == 409
        armed = web.post("/api/tabletop/arm", json=body)
        assert armed.status_code == 200
        assert armed.json()["tabletop"] is True
        assert armed.json()["rule"]["duration"] == 0.08
        assert device.last_intensity == 0
        assert web.post("/api/control/stop").status_code == 200
        assert current.hand_response.state == HandResponseState.DISARMED


def test_failed_real_stop_latches_output_off_for_process():
    class FailingStop(InertRealDevice):
        async def stop(self):
            raise RuntimeError("injected stop failure")

    async def exercise():
        devices = DeviceRegistry()
        device = FailingStop()
        devices.add(device)
        devices.select(device.info.identifier)
        safety = SafetyController(devices, Settings(real_device_output_enabled=True))
        assert safety.real_device_output_enabled
        await safety.stop("user_stop")
        assert not safety.real_device_output_enabled
        assert "stop failed" in (safety.last_error or "").lower()
    asyncio.run(exercise())
