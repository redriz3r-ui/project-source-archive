import asyncio
import time

import pytest

from app.devices.simulated import SimulatedDevice
from app.devices.registry import DeviceRegistry
from app.config import Settings
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.automation import AutomationRule, AutomationState
from app.triggers.patterns import Pattern
from app.triggers.session import SessionPhase, SessionSettings, step_for


def setup(device, *, command_timeout=2.0):
    registry = DeviceRegistry()
    registry.add(device)
    registry.select(device.info.identifier)
    safety = SafetyController(registry, Settings(command_timeout_seconds=command_timeout))
    from app.triggers.automation import AutomationController
    return AutomationController(registry, safety, lambda: True, lambda: True), device, None, safety


def test_session_plan_is_finite_and_never_exceeds_chosen_intensity():
    settings = SessionSettings(1, 2, 1, True)
    steps = [step_for(settings, index) for index in range(5)]
    assert [step.phase if step else None for step in steps] == [
        SessionPhase.OPENING, SessionPhase.MIDDLE, SessionPhase.MIDDLE,
        SessionPhase.BUILDUP, None,
    ]
    assert [step.pattern for step in steps if step] == [
        Pattern.GENTLE_PULSE, Pattern.RHYTHMIC_PULSE,
        Pattern.RHYTHMIC_PULSE, Pattern.GRADUAL_RAMP,
    ]
    assert all(0 < step.intensity_fraction <= 1 for step in steps if step)
    assert step_for(SessionSettings(1, 1, 2, False), 2) is None


@pytest.mark.parametrize("settings", [
    SessionSettings(0, 1, 1, True),
    SessionSettings(1, 21, 1, True),
    SessionSettings(20, 20, 1, True),
    SessionSettings(True, 1, 1, True),
])
def test_session_rejects_unbounded_or_invalid_counts(settings):
    with pytest.raises(ValueError):
        settings.validate()


class RecordingDevice(SimulatedDevice):
    def __init__(self):
        super().__init__()
        self.commands = []

    async def vibrate_feature(self, feature_index, intensity):
        self.commands.append((feature_index, intensity))
        await super().vibrate_feature(feature_index, intensity)


def test_guided_session_completes_and_disarms_without_more_output():
    async def exercise():
        controller, device, _, _ = setup(RecordingDevice())
        await controller.arm(
            AutomationRule(intensity=0.2, duration=0.16, cooldown=0.5),
            SessionSettings(1, 1, 1, True),
        )
        deadline = time.monotonic() + 5
        while controller.state != AutomationState.DISARMED and time.monotonic() < deadline:
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.9, "observed_at": time.monotonic(),
            }))
            await asyncio.sleep(0.04)
        assert controller.state == AutomationState.DISARMED
        assert controller.snapshot()["session"]["phase"] == SessionPhase.COMPLETE
        assert controller.snapshot()["session"]["completed_pulses"] == 3
        assert device.last_intensity == 0
        values = [intensity for _, intensity in device.commands]
        assert values and max(values) <= 0.2
        assert any(0 < value <= 0.1 for value in values)
        assert any(value > 0.1 for value in values)
        count = len(device.commands)
        await controller.handle_event(Event("interaction_continued", {
            "confidence": 0.9, "observed_at": time.monotonic(),
        }))
        await asyncio.sleep(0.1)
        assert len(device.commands) == count
        await controller.shutdown()
    asyncio.run(exercise())


def test_session_interruption_and_emergency_stop_cannot_resume():
    async def exercise():
        controller, device, _, _ = setup(RecordingDevice())
        await controller.arm(
            AutomationRule(duration=0.3), SessionSettings(1, 1, 1, True),
        )
        for _ in range(3):
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.9, "observed_at": time.monotonic(),
            }))
            await asyncio.sleep(0.04)
        await controller.handle_event(Event("tracking_lost"))
        assert controller.state == AutomationState.DISARMED
        assert device.last_intensity == 0
        assert controller.snapshot()["session"]["enabled"] is False
        await controller.arm(
            AutomationRule(duration=0.3), SessionSettings(1, 1, 1, True),
        )
        await controller.emergency_stop()
        count = len(device.commands)
        for _ in range(4):
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.9, "observed_at": time.monotonic(),
            }))
        assert controller.state == AutomationState.EMERGENCY_STOP
        assert device.last_intensity == 0
        assert len(device.commands) == count
        await controller.shutdown()
    asyncio.run(exercise())


def test_delayed_session_command_fails_closed_without_advancing():
    class SlowDevice(RecordingDevice):
        async def vibrate_feature(self, feature_index, intensity):
            await asyncio.sleep(0.2)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise():
        controller, device, _, _ = setup(SlowDevice(), command_timeout=0.05)
        await controller.arm(
            AutomationRule(duration=0.3), SessionSettings(1, 1, 1, True),
        )
        for _ in range(3):
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.9, "observed_at": time.monotonic(),
            }))
            await asyncio.sleep(0.04)
        await asyncio.sleep(0.2)
        assert controller.state == AutomationState.ERROR
        assert device.last_intensity == 0
        assert controller.snapshot()["session"]["completed_pulses"] == 0
        await controller.shutdown()
    asyncio.run(exercise())
