import asyncio

import pytest

from app.devices import DeviceRegistry, SimulatedDevice
from app.events import Event, EventBus
from app.safety import SafetyController
from app.triggers import TriggerEngine, TriggerRule


def test_event_bus_delivers_events() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("interaction.detected", handler)
    event = Event("interaction.detected", {"confidence": 0.9})
    asyncio.run(bus.publish(event))
    assert received == [event]


def test_trigger_engine_fails_closed() -> None:
    engine = TriggerEngine((TriggerRule("interaction.detected", 0.8),))
    assert engine.matches(Event("interaction.detected", {"confidence": 1.0})) is False


def test_safety_gate_cannot_be_enabled_in_foundation() -> None:
    safety = SafetyController(DeviceRegistry())
    with pytest.raises(RuntimeError, match="Select a device"):
        safety.enable_activation()


def test_emergency_stop_reaches_simulator() -> None:
    registry = DeviceRegistry()
    simulator = SimulatedDevice()
    registry.add(simulator)
    safety = SafetyController(registry)

    asyncio.run(safety.emergency_stop())

    assert simulator.stop_count == 1
    assert safety.activation_enabled is False
    assert safety.emergency_stop_latched is True
