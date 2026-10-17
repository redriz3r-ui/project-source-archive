import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.automation import AutomationController, AutomationRule, AutomationState
from app.triggers.patterns import Pattern, build_pattern
from app.triggers.store import RuleStore


class RecordingDevice(SimulatedDevice):
    def __init__(self):
        super().__init__()
        self.commands: list[tuple[str, float]] = []

    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        self.commands.append((f"feature-{feature_index}", intensity))
        await super().vibrate_feature(feature_index, intensity)

    async def stop(self) -> None:
        self.commands.append(("stop", 0.0))
        await super().stop()


def setup(device=None, *, command_timeout=0.5):
    registry = DeviceRegistry()
    device = device or RecordingDevice()
    registry.add(device)
    registry.select(device.info.identifier)
    camera = {"running": True}
    safety = SafetyController(registry, Settings(command_timeout_seconds=command_timeout))
    controller = AutomationController(registry, safety, lambda: camera["running"], lambda: True)
    return controller, device, camera, safety


async def activate(controller):
    for index in range(3):
        await controller.handle_event(Event(
            "interaction_started" if index == 0 else "interaction_continued",
            {"confidence": 0.9, "observed_at": time.monotonic()},
        ))
        await asyncio.sleep(0.04)


@pytest.mark.parametrize("pattern,positive_steps", [
    (Pattern.SHORT_PULSE, 1),
    (Pattern.GENTLE_PULSE, 3),
    (Pattern.RHYTHMIC_PULSE, 4),
    (Pattern.GRADUAL_RAMP, 4),
])
def test_patterns_are_bounded_and_execute_only_when_armed(pattern, positive_steps):
    async def exercise():
        controller, device, _, safety = setup()
        await activate(controller)
        assert device.commands == []
        await controller.arm(AutomationRule(pattern=pattern, intensity=0.2, duration=0.25))
        await activate(controller)
        assert controller.state == AutomationState.ACTIVE
        await asyncio.sleep(0.28)
        positive = [value for command, value in device.commands if command == "feature-0"]
        assert len(positive) == positive_steps
        assert all(0 < value <= 0.2 for value in positive)
        if pattern == Pattern.GRADUAL_RAMP:
            assert positive == sorted(positive)
        assert device.last_intensity == 0
        assert not safety.running
        await controller.shutdown()
    asyncio.run(exercise())


def test_pattern_preview_is_pure_and_limits_are_server_validated(tmp_path: Path):
    with TestClient(create_app(Settings(), rules=RuleStore(tmp_path / "rules.json")),
                    base_url="http://127.0.0.1:8000") as web:
        device = web.post("/api/devices/simulated").json()
        simulator = web.app.state.services.devices.get(device["id"])
        assert "Preview pattern" in web.get("/rules").text
        assert 'id="pattern"' in web.get("/dashboard").text
        for pattern in Pattern:
            result = web.get("/api/patterns/preview", params={
                "pattern": pattern, "intensity": 0.2, "duration": 1.0,
            })
            assert result.status_code == 200
            data = result.json()
            assert data["device_command_sent"] is False
            assert sum(step["duration"] for step in data["steps"]) == pytest.approx(1.0)
            assert max(step["intensity"] for step in data["steps"]) <= 0.2
        assert simulator.last_intensity == 0
        assert simulator.stop_count == 0
        assert web.get("/api/patterns/preview", params={"intensity": 0.8}).status_code == 422
        assert web.get("/api/patterns/preview", params={"duration": 9}).status_code == 422
        assert web.get("/api/patterns/preview", params={"pattern": "UNBOUNDED"}).status_code == 422


def test_store_accepts_patterns_but_rejects_unknown_and_keeps_old_rules(tmp_path: Path):
    store = RuleStore(tmp_path / "rules.json")
    fields = dict(name="Gentle", trigger="INTERACTION_ACTIVE", action="VIBRATE",
                  pattern="GENTLE_PULSE", feature_index=0, intensity=0.2,
                  duration=1.0, cooldown=1.0, minimum_confidence=0.6)
    saved = store.create(**fields)
    assert saved.automation_rule().pattern == Pattern.GENTLE_PULSE
    assert RuleStore(store.path).get(saved.id).pattern == "GENTLE_PULSE"
    with pytest.raises(ValueError):
        store.create(**{**fields, "pattern": "FOREVER"})
    old = store.create(**{**fields, "name": "Old", "pattern": "SHORT_PULSE"})
    assert old.automation_rule().pattern == Pattern.SHORT_PULSE


def test_disarm_and_tracking_loss_stop_mid_pattern_and_reject_late_events():
    async def exercise():
        for stop_kind in ("disarm", "tracking_lost", "camera_stopped"):
            controller, device, camera, _ = setup()
            await controller.arm(AutomationRule(pattern=Pattern.RHYTHMIC_PULSE, duration=1.0))
            await activate(controller)
            assert device.last_intensity > 0
            if stop_kind == "disarm":
                await controller.disarm()
            elif stop_kind == "tracking_lost":
                await controller.handle_event(Event("tracking_lost"))
            else:
                camera["running"] = False
                await controller.handle_event(Event("camera_stopped"))
            count = len(device.commands)
            await asyncio.sleep(0.2)
            assert device.last_intensity == 0
            assert not any(command.startswith("feature-") for command, _ in device.commands[count:])
            assert controller.state == AutomationState.DISARMED
            await controller.shutdown()
    asyncio.run(exercise())


def test_repeated_events_do_not_overlap_or_bypass_cooldown():
    async def exercise():
        controller, device, _, _ = setup()
        await controller.arm(AutomationRule(pattern=Pattern.RHYTHMIC_PULSE,
                                            duration=0.25, cooldown=0.5))
        await activate(controller)
        for _ in range(8):
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.9, "observed_at": time.monotonic(),
            }))
        await asyncio.sleep(0.3)
        first_count = sum(command.startswith("feature-") for command, _ in device.commands)
        assert first_count == 4
        assert controller.state == AutomationState.COOLDOWN
        await activate(controller)
        assert sum(command.startswith("feature-") for command, _ in device.commands) == first_count
        await controller.shutdown()
    asyncio.run(exercise())


def test_pattern_uses_only_explicitly_selected_feature():
    class TwoFeatureDevice(RecordingDevice):
        @property
        def vibration_features(self):
            return (0, 3)

        async def vibrate_feature(self, feature_index, intensity):
            self.commands.append((f"feature-{feature_index}", intensity))
            self.last_intensity = intensity

    async def exercise():
        controller, device, _, _ = setup(TwoFeatureDevice())
        await controller.arm(AutomationRule(feature_index=3,
                                            pattern=Pattern.GRADUAL_RAMP, duration=0.3))
        await activate(controller)
        await asyncio.sleep(0.32)
        assert {command for command, _ in device.commands if command.startswith("feature-")} == {"feature-3"}
        await controller.shutdown()
    asyncio.run(exercise())


def test_emergency_and_disconnect_races_do_not_resume_pattern():
    async def exercise():
        for emergency in (True, False):
            controller, device, _, _ = setup()
            await controller.arm(AutomationRule(pattern=Pattern.GRADUAL_RAMP, duration=1.0))
            await activate(controller)
            if emergency:
                await controller.emergency_stop()
                assert controller.state == AutomationState.EMERGENCY_STOP
            else:
                controller.device_lost(device.info.identifier)
                await asyncio.sleep(0.05)
                assert controller.state == AutomationState.ERROR
            count = len(device.commands)
            await asyncio.sleep(0.2)
            assert device.last_intensity == 0
            assert not any(command.startswith("feature-") for command, _ in device.commands[count:])
            await controller.shutdown()
    asyncio.run(exercise())


def test_delayed_command_timeout_stops_and_does_not_advance_pattern():
    class DelayedDevice(RecordingDevice):
        async def vibrate_feature(self, feature_index, intensity):
            await asyncio.sleep(0.2)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise():
        controller, device, _, safety = setup(DelayedDevice(), command_timeout=0.05)
        await controller.arm(AutomationRule(pattern=Pattern.RHYTHMIC_PULSE, duration=0.5))
        await activate(controller)
        await asyncio.sleep(0.15)
        assert controller.state == AutomationState.ERROR
        assert safety.last_error is not None
        assert device.last_intensity == 0
        assert not any(command.startswith("feature-") for command, _ in device.commands)
        await controller.shutdown()
    asyncio.run(exercise())


def test_cancellation_resistant_command_gets_a_final_stop():
    class LateDevice(RecordingDevice):
        async def vibrate_feature(self, feature_index, intensity):
            try:
                await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                await asyncio.sleep(0.08)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise():
        controller, device, _, _ = setup(LateDevice())
        await controller.arm(AutomationRule(pattern=Pattern.GRADUAL_RAMP, duration=1.0))
        await activate(controller)
        await controller.emergency_stop()
        await asyncio.sleep(0.12)
        assert controller.state == AutomationState.EMERGENCY_STOP
        assert device.last_intensity == 0
        assert device.commands[-1][0] == "stop"
        assert sum(command.startswith("feature-") for command, _ in device.commands) <= 1
        await controller.shutdown()
    asyncio.run(exercise())


def test_pattern_generator_rejects_nonfinite_and_excessive_values():
    for intensity, duration in ((0.6, 1), (0.2, 3), (float("nan"), 1), (0.2, float("inf"))):
        with pytest.raises(ValueError):
            build_pattern(Pattern.GENTLE_PULSE, intensity, duration)
