"""Hand mirroring safety tests use injected simulators; never real hardware."""

import asyncio
from dataclasses import asdict
import time

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.devices.models import DeviceInfo
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.hand_response import (
    HandResponseController, HandResponseMode, HandResponseRule, HandResponseState,
    ResponseStyle, preview_hand_rule,
)
from app.vision.stroke_contract import (
    STROKE_SCHEMA_VERSION, StrokeDirection, StrokeEvent, StrokeEventKind,
    StrokeObservation,
)


class Recorder(SimulatedDevice):
    def __init__(self, delay: float = 0) -> None:
        super().__init__()
        self.delay = delay
        self.commands: list[tuple[int, float]] = []

    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.commands.append((feature_index, intensity))
        await super().vibrate_feature(feature_index, intensity)


class FakeRealVibrator(Recorder):
    @property
    def info(self):
        original = super().info
        return DeviceInfo("intiface-0", "Injected real-device double", False,
                          ("Vibrate", "Oscillate"), original.status)

    @property
    def vibration_features(self):
        return (2,)

    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        if feature_index != 2:
            raise ValueError("Unadvertised feature")
        if self.delay:
            await asyncio.sleep(self.delay)
        self.commands.append((feature_index, intensity))
        await self.vibrate(intensity)


def rig(delay: float = 0, timeout: float = 0.3):
    devices = DeviceRegistry()
    device = Recorder(delay)
    devices.add(device)
    devices.select(device.info.identifier)
    camera = {"running": True}
    safety = SafetyController(devices, Settings(command_timeout_seconds=timeout,
                                                 stop_timeout_seconds=0.15))
    controller = HandResponseController(devices, safety, lambda: camera["running"])
    return controller, device, devices, camera, safety


def real_rig(delay: float = 0, timeout: float = 0.3):
    devices = DeviceRegistry()
    device = FakeRealVibrator(delay)
    devices.add(device)
    devices.select(device.info.identifier)
    camera = {"running": True}
    connected = {"value": True}
    safety = SafetyController(devices, Settings(command_timeout_seconds=timeout,
                                                 stop_timeout_seconds=0.15,
                                                 real_device_output_enabled=True))
    controller = HandResponseController(
        devices, safety, lambda: camera["running"],
        intiface_connected=lambda: connected["value"],
    )
    return controller, device, devices, camera, connected


def observation(frame: int, *, at: int | None = None, confidence: float = 0.9,
                tracking_state: str = "TRACKED") -> Event:
    stroke = StrokeObservation(STROKE_SCHEMA_VERSION, at or time.monotonic_ns(), frame,
                               0.8, StrokeDirection.FORWARD, 0.7, 0.6, confidence, frame)
    return Event("stroke_observation", {"stroke": asdict(stroke), "tracking_state": tracking_state})


def stroke_event(frame: int, stroke_id: int, kind: StrokeEventKind, *, at: int | None = None,
                 speed: float = 0.7, confidence: float = 0.9) -> Event:
    stroke = StrokeEvent(STROKE_SCHEMA_VERSION, at or time.monotonic_ns(), frame,
                         0.8, StrokeDirection.FORWARD, speed, 0.6, confidence,
                         stroke_id, kind)
    return Event(kind.value, {"stroke": asdict(stroke)})


def completed(frame: int, stroke_id: int, *, at: int | None = None,
              speed: float = 0.7, confidence: float = 0.9) -> Event:
    return stroke_event(frame, stroke_id, StrokeEventKind.COMPLETED,
                        at=at, speed=speed, confidence=confidence)


def started(frame: int, stroke_id: int) -> Event:
    return stroke_event(frame, stroke_id, StrokeEventKind.STARTED)


def updated(frame: int, stroke_id: int, speed: float = 0.7) -> Event:
    return stroke_event(frame, stroke_id, StrokeEventKind.UPDATED, speed=speed)


async def ready(controller: HandResponseController, rule: HandResponseRule | None = None):
    await controller.handle_event(observation(1))
    await controller.arm(rule or HandResponseRule(duration=0.06, cooldown=0.25))


def test_one_stroke_one_bounded_response_and_duplicate_or_rapid_strokes_drop():
    async def exercise():
        controller, device, _, _, _ = rig()
        await ready(controller)
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await controller.handle_event(completed(2, 1))
        await controller.handle_event(observation(3))
        await controller.handle_event(started(3, 2))
        await controller.handle_event(completed(3, 2))
        await asyncio.sleep(0.11)
        snap = controller.snapshot()
        assert snap["stroke_count"] == 2
        assert snap["pending_response_count"] == 0
        assert snap["completed_response_count"] == 1
        assert snap["dropped_response_count"] == 2
        assert snap["simulator_latency_ms"] is not None
        assert device.commands == [(0, 0.2)]
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_deadline_stop_counts_acknowledged_simulator_response_without_error():
    async def exercise():
        controller, device, _, _, _ = rig()
        await ready(controller, HandResponseRule(duration=0.18, cooldown=0.25))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.02)
        assert device.commands == [(0, 0.2)]
        assert controller.state == HandResponseState.ACTIVE
        controller._active_until = time.monotonic() - 1  # Force the watchdog deadline branch.
        await asyncio.sleep(0.06)
        assert controller.state == HandResponseState.COOLDOWN
        assert controller.last_error is None
        assert controller.completed_response_count == 1
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_deadline_before_command_acknowledgement_fails_closed():
    async def exercise():
        controller, device, _, _, _ = rig(delay=0.12)
        await ready(controller, HandResponseRule(duration=0.18, cooldown=0.25))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        controller._active_until = time.monotonic() - 1
        await asyncio.sleep(0.06)
        assert controller.state == HandResponseState.ERROR
        assert controller.last_error == "Response ended before command acknowledgement"
        assert controller.completed_response_count == 0
        await asyncio.sleep(0.13)
        assert device.commands == []
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_ten_sequential_simulator_strokes_do_not_trip_deadline_error():
    async def exercise():
        controller, device, _, _, _ = rig()
        await ready(controller, HandResponseRule(duration=0.04, cooldown=0.25))
        frame = 1
        for stroke_id in range(1, 11):
            while controller.state != HandResponseState.ARMED:
                await asyncio.sleep(0.03)
                frame += 1
                await controller.handle_event(observation(frame))
            frame += 1
            await controller.handle_event(observation(frame))
            await controller.handle_event(started(frame, stroke_id))
            await controller.handle_event(completed(frame, stroke_id))
            assert controller.state == HandResponseState.ACTIVE
        while controller.state == HandResponseState.ACTIVE:
            await asyncio.sleep(0.03)
            frame += 1
            await controller.handle_event(observation(frame))
        assert controller.last_error is None
        assert controller.completed_response_count == 10
        assert len(device.commands) == 10
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_stale_out_of_order_occlusion_and_camera_loss_cannot_start_response():
    async def exercise():
        controller, device, _, camera, _ = rig()
        await ready(controller)
        await controller.handle_event(started(1, 1))
        await controller.handle_event(completed(2, 1, at=time.monotonic_ns() - 500_000_000))
        await controller.handle_event(observation(5))
        await controller.handle_event(completed(4, 2))
        await controller.handle_event(observation(6, tracking_state="OCCLUDED"))
        await controller.handle_event(completed(7, 3))
        assert controller.state == HandResponseState.DISARMED
        assert device.commands == []
        await controller.handle_event(observation(8))
        await controller.arm(HandResponseRule(duration=0.06))
        camera["running"] = False
        await asyncio.sleep(0.05)
        assert controller.state == HandResponseState.DISARMED
        await controller.handle_event(completed(9, 4))
        assert device.commands == []
        await controller.shutdown()
    asyncio.run(exercise())


@pytest.mark.parametrize("interruption", ["disarm", "emergency", "tracking", "camera", "disconnect", "shutdown"])
def test_interruption_prevents_delayed_or_queued_restart(interruption):
    async def exercise():
        controller, device, devices, camera, _ = rig(delay=0.12)
        await ready(controller, HandResponseRule(duration=0.25, cooldown=0.25))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.02)
        if interruption == "disarm":
            await controller.disarm()
        elif interruption == "emergency":
            await controller.emergency_stop()
        elif interruption == "tracking":
            await controller.handle_event(Event("stroke_tracking_lost"))
        elif interruption == "camera":
            camera["running"] = False
            await controller.handle_event(Event("camera_stopped"))
        elif interruption == "disconnect":
            devices.remove(device.info.identifier)
            controller.device_lost(device.info.identifier)
        else:
            await controller.shutdown()
        await asyncio.sleep(0.17)
        await controller.handle_event(completed(3, 2))
        assert device.commands == []
        assert device.last_intensity == 0
        assert controller.state in {HandResponseState.DISARMED, HandResponseState.ERROR,
                                    HandResponseState.EMERGENCY_STOP}
        await controller.shutdown()
    asyncio.run(exercise())


def test_delayed_command_timeout_fails_closed_and_motion_shaped_stays_bounded():
    async def exercise():
        controller, device, _, _, _ = rig(delay=0.12, timeout=0.04)
        await ready(controller, HandResponseRule(duration=0.2))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.11)
        assert controller.state == HandResponseState.ERROR
        assert device.commands == []
        await controller.shutdown()

        controller, device, _, _, _ = rig()
        await ready(controller, HandResponseRule(intensity=0.25, duration=0.06,
                                                  mode=HandResponseMode.MOTION_SHAPED))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1, speed=0.1))
        await asyncio.sleep(0.1)
        assert len(device.commands) == 1
        assert 0 < device.commands[0][1] <= 0.25
        await controller.shutdown()
    asyncio.run(exercise())


def test_second_response_needs_fresh_tracking_after_cooldown():
    async def exercise():
        controller, device, _, _, _ = rig()
        await ready(controller, HandResponseRule(duration=0.04, cooldown=0.25))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        for frame in range(3, 11):
            await asyncio.sleep(0.04)
            await controller.handle_event(observation(frame))
        assert controller.state == HandResponseState.ARMED
        await controller.handle_event(started(10, 2))
        await controller.handle_event(completed(10, 2))
        await asyncio.sleep(0.08)
        assert controller.completed_response_count == 2
        assert device.commands == [(0, 0.2), (0, 0.2)]
        await controller.shutdown()
    asyncio.run(exercise())


def test_api_refuses_real_devices_and_starts_disarmed():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        assert web.get("/api/hand/response/status").json()["state"] == "DISARMED"
        assert "Arm simulated responses" in web.get("/hand").text
        assert web.post("/api/hand/response/arm", json={}).status_code == 409
        device = web.post("/api/devices/simulated").json()
        web.post("/api/devices/select", json={"device_id": device["id"]})
        assert web.post("/api/hand/response/arm", json={}).status_code == 409
        assert web.post("/api/hand/response/arm", json={"intensity": 0.7}).status_code == 422


def test_real_device_and_unadvertised_feature_never_arm_and_prearm_stroke_drops():
    class InertReal(Recorder):
        @property
        def info(self):
            original = super().info
            return DeviceInfo(original.identifier, original.name, False,
                              original.capabilities, original.status)

    async def exercise():
        devices = DeviceRegistry()
        real = InertReal()
        devices.add(real)
        devices.select(real.info.identifier)
        safety = SafetyController(devices, Settings(real_device_output_enabled=True))
        controller = HandResponseController(devices, safety, lambda: True)
        await controller.handle_event(observation(1))
        with pytest.raises(RuntimeError, match="supervised pilot"):
            await controller.arm(HandResponseRule())
        assert real.commands == []
        await controller.shutdown()

        controller, device, _, _, _ = rig()
        await controller.handle_event(observation(1))
        with pytest.raises(RuntimeError, match="advertised"):
            await controller.arm(HandResponseRule(feature_index=7))
        await controller.handle_event(started(1, 1))
        await controller.arm(HandResponseRule(duration=0.06))
        await controller.handle_event(observation(2))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.08)
        assert device.commands == []
        await controller.shutdown()
    asyncio.run(exercise())


def test_supervised_real_pilot_requires_managed_arm_and_strict_selected_feature():
    async def exercise():
        controller, device, _, _, connected = real_rig()
        await controller.handle_event(observation(1))
        rule = HandResponseRule(feature_index=2, intensity=0.2, duration=0.06,
                                cooldown=0.5)
        with pytest.raises(RuntimeError, match="supervised pilot"):
            await controller.arm(rule, real_pilot=True)
        with pytest.raises(RuntimeError, match="supervised pilot"):
            await controller.arm(rule, session_managed=True)
        with pytest.raises(RuntimeError, match="advertised"):
            await controller.arm(HandResponseRule(feature_index=0, duration=0.06,
                                                  cooldown=0.5), session_managed=True,
                                 real_pilot=True)
        with pytest.raises(ValueError, match="Real pilot"):
            await controller.arm(HandResponseRule(feature_index=2, duration=0.18,
                                                  cooldown=0.5), session_managed=True,
                                 real_pilot=True)
        with pytest.raises(ValueError, match="Real pilot"):
            await controller.arm(HandResponseRule(feature_index=2, duration=0.06,
                                                  cooldown=0.5, mode=HandResponseMode.FOLLOW_MOVEMENT),
                                 session_managed=True, real_pilot=True)
        connected["value"] = False
        with pytest.raises(RuntimeError, match="connected"):
            await controller.arm(rule, session_managed=True, real_pilot=True)
        connected["value"] = True
        await controller.arm(rule, session_managed=True, real_pilot=True)
        assert controller.snapshot()["real_pilot"] is True
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.10)
        assert device.commands == [(2, 0.2)]
        assert device.last_intensity == 0
        await controller.disarm()
        assert controller.snapshot()["real_pilot"] is False
        await controller.shutdown()
    asyncio.run(exercise())


@pytest.mark.parametrize("interruption", ["emergency", "disconnect", "camera"])
def test_real_pilot_delayed_command_cannot_restart_after_stop(interruption):
    async def exercise():
        controller, device, devices, camera, connected = real_rig(delay=0.12)
        await controller.handle_event(observation(1))
        await controller.arm(HandResponseRule(feature_index=2, duration=0.12,
                                              cooldown=0.5), session_managed=True,
                             real_pilot=True)
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.02)
        if interruption == "emergency":
            await controller.emergency_stop()
        elif interruption == "disconnect":
            connected["value"] = False
            devices.remove(device.info.identifier)
            controller.device_lost(device.info.identifier)
        else:
            camera["running"] = False
            await controller.handle_event(Event("camera_stopped"))
        await asyncio.sleep(0.16)
        assert device.commands == []
        assert device.last_intensity == 0
        assert controller.state != HandResponseState.ACTIVE
        await controller.shutdown()
    asyncio.run(exercise())


def test_real_pilot_cancellation_resistant_command_gets_trailing_stop():
    class CancellationResistantReal(FakeRealVibrator):
        async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
            try:
                await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                await asyncio.sleep(0.06)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise():
        devices = DeviceRegistry()
        device = CancellationResistantReal()
        devices.add(device)
        devices.select(device.info.identifier)
        safety = SafetyController(devices, Settings(stop_timeout_seconds=0.15,
                                                     real_device_output_enabled=True))
        controller = HandResponseController(devices, safety, lambda: True,
                                            intiface_connected=lambda: True)
        await controller.handle_event(observation(1))
        await controller.arm(HandResponseRule(feature_index=2, duration=0.12,
                                              cooldown=0.5), session_managed=True,
                             real_pilot=True)
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(completed(2, 1))
        await asyncio.sleep(0.02)
        await controller.emergency_stop()
        await asyncio.sleep(0.1)
        assert controller.state == HandResponseState.EMERGENCY_STOP
        assert device.last_intensity == 0
        assert device.stop_count >= 2
        await controller.shutdown()
    asyncio.run(exercise())


def test_follow_movement_uses_short_rate_limited_pulses_from_fresh_updates():
    async def exercise():
        controller, device, _, _, _ = rig()
        await ready(controller, HandResponseRule(
            duration=0.06, cooldown=0.08, mode=HandResponseMode.FOLLOW_MOVEMENT,
            style=ResponseStyle.GENTLE,
        ))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(observation(3))
        await controller.handle_event(updated(3, 1))
        await controller.handle_event(updated(3, 1))  # Same update must not queue.
        await asyncio.sleep(0.24)
        await controller.handle_event(observation(4))
        await controller.handle_event(updated(4, 1, speed=1.2))
        await asyncio.sleep(0.09)
        assert len(device.commands) == 2
        assert all(feature == 0 and 0 < intensity <= 0.2
                   for feature, intensity in device.commands)
        assert controller.submitted_response_count == 2
        await controller.handle_event(observation(5))
        await controller.handle_event(completed(5, 1))
        await controller.handle_event(observation(6))
        await controller.handle_event(updated(6, 1))
        assert len(device.commands) == 2
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())


def test_pause_requires_explicit_rearm_and_stops_delayed_follow_pulse():
    async def exercise():
        controller, device, _, _, _ = rig(delay=0.12)
        await ready(controller, HandResponseRule(duration=0.12, cooldown=0.08,
                                                  mode=HandResponseMode.FOLLOW_MOVEMENT))
        await controller.handle_event(observation(2))
        await controller.handle_event(started(2, 1))
        await controller.handle_event(observation(3))
        await controller.handle_event(updated(3, 1))
        await asyncio.sleep(0.02)
        await controller.pause()
        await asyncio.sleep(0.15)
        await controller.handle_event(updated(3, 1))
        assert controller.state == HandResponseState.PAUSED
        assert device.commands == []
        assert device.last_intensity == 0
        await controller.handle_event(observation(4))
        await controller.arm(HandResponseRule(duration=0.06, cooldown=0.08,
                                               mode=HandResponseMode.FOLLOW_MOVEMENT))
        assert controller.state == HandResponseState.ARMED
        await controller.shutdown()
    asyncio.run(exercise())


def test_session_preview_is_pure_and_follow_limits_are_stricter():
    preview = preview_hand_rule(HandResponseRule(style=ResponseStyle.RAMP), 0.5, 5)
    assert preview["device_command_sent"] is False
    assert preview["style"] == "RAMP"
    assert len(preview["steps"]) == 4
    following = preview_hand_rule(HandResponseRule(duration=0.08, cooldown=0.08,
                              mode=HandResponseMode.FOLLOW_MOVEMENT), 0.5, 5)
    assert following["maximum_duration"] == 0.08
    assert len(following["steps"]) == 1
    with pytest.raises(ValueError):
        preview_hand_rule(HandResponseRule(duration=0.18, cooldown=0.08,
                          mode=HandResponseMode.FOLLOW_MOVEMENT), 0.5, 5)
