"""Stage-1 hand-stroke contracts and simulator-only latency fault injection."""

import asyncio
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.diagnostics import LatencyRecorder, TraceStage
from app.diagnostics.benchmark import measure
from app.safety.controller import SafetyController
from app.vision.stroke_contract import (
    STROKE_SCHEMA_VERSION, StrokeDirection, StrokeEvent, StrokeEventKind,
    StrokeObservation,
)


def observation(**changes) -> StrokeObservation:
    fields = dict(schema_version=STROKE_SCHEMA_VERSION, timestamp_ns=123,
                  frame_id=7, hand_position=0.4, direction=StrokeDirection.FORWARD,
                  speed=0.8, travel=0.2, tracking_confidence=0.9, stroke_id=2)
    fields.update(changes)
    return StrokeObservation(**fields)


def test_stroke_contract_is_versioned_device_neutral_and_validated() -> None:
    item = observation()
    assert asdict(item)["hand_position"] == 0.4
    event = StrokeEvent(**asdict(item), kind=StrokeEventKind.STARTED)
    assert event.stroke_id == 2
    assert event.schema_version == 1
    StrokeEvent(**asdict(observation(hand_position=None, stroke_id=None,
                                     direction=StrokeDirection.UNKNOWN,
                                     tracking_confidence=0)),
                kind=StrokeEventKind.TRACKING_LOST)
    for change in (
        {"schema_version": 2}, {"timestamp_ns": -1}, {"frame_id": 0},
        {"hand_position": 1.01}, {"hand_position": float("nan")},
        {"speed": float("inf")}, {"travel": -0.1},
        {"tracking_confidence": 1.1}, {"stroke_id": 0},
        {"direction": "FORWARD"},
    ):
        with pytest.raises(ValueError):
            observation(**change)
    with pytest.raises(ValueError):
        StrokeEvent(**asdict(observation(hand_position=None)),
                    kind=StrokeEventKind.UPDATED)


def test_latency_recorder_is_opt_in_numeric_bounded_and_reports_intervals() -> None:
    recorder = LatencyRecorder(capacity=2)
    recorder.mark(1, TraceStage.FRAME_CAPTURED, 1)
    assert recorder.report()["trace_count"] == 0
    recorder.start()
    recorder.mark(1, TraceStage.FRAME_READ_STARTED, 500_000)
    recorder.mark(1, TraceStage.FRAME_CAPTURED, 1_000_000)
    recorder.mark(1, TraceStage.OBJECT_DETECTED, 4_000_000)
    recorder.mark(1, TraceStage.COMMAND_SUBMITTED, 6_000_000)
    recorder.mark(1, TraceStage.COMMAND_COMPLETED, 8_000_000)
    recorder.mark(2, TraceStage.FRAME_CAPTURED, 9_000_000)
    recorder.mark(2, TraceStage.HAND_DETECTED, 10_000_000)
    recorder.mark(2, TraceStage.STROKE_DECIDED, 11_000_000)
    report = recorder.report()
    assert report["intervals"]["capture_to_object_ms"]["median_ms"] == 3
    assert report["intervals"]["frame_read_ms"]["median_ms"] == 0.5
    assert report["intervals"]["command_ack_ms"]["median_ms"] == 2
    assert report["intervals"]["capture_to_hand_ms"]["median_ms"] == 1
    assert report["intervals"]["capture_to_stroke_decision_ms"]["median_ms"] == 2
    assert report["frames_saved"] is False
    assert recorder.traces()[0]["timestamps_ns"]["frame_captured"] == 1_000_000
    recorder.mark(3, TraceStage.FRAME_CAPTURED, 10_000_000)
    assert [trace["frame_id"] for trace in recorder.traces()] == [2, 3]
    recorder.stop()
    recorder.mark(4, TraceStage.FRAME_CAPTURED, 11_000_000)
    assert recorder.report()["trace_count"] == 2
    with pytest.raises(ValueError):
        recorder.mark(5, "webcam_image", 12)  # type: ignore[arg-type]


def test_diagnostic_api_keeps_safe_startup_and_does_not_control_device() -> None:
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        simulator_id = web.post("/api/devices/simulated").json()["id"]
        simulator = web.app.state.services.devices.get(simulator_id)
        before = web.get("/api/diagnostics/latency")
        assert before.status_code == 200
        assert before.headers["cache-control"] == "no-store"
        assert before.json()["enabled"] is False
        assert web.post("/api/diagnostics/latency/start").json()["enabled"] is True
        assert web.post("/api/diagnostics/latency/stop").json()["enabled"] is False
        assert web.get("/api/status").json()["camera"] == "inactive"
        assert web.get("/api/automation/status").json()["state"] == "DISARMED"
        assert simulator.last_intensity == 0


def test_synthetic_benchmark_has_no_hand_or_hardware_measurement() -> None:
    result = asyncio.run(measure(samples=1))
    report = result["report"]
    assert result["physical_device_onset_measured"] is False
    assert result["hand_tracking_implemented"] is False
    assert report["stage_counts"]["frame_captured"] > 0
    assert report["stage_counts"]["object_detected"] > 0
    assert report["stage_counts"]["oral_decided"] > 0
    assert report["stage_counts"]["command_completed"] >= 1
    assert report["stage_counts"]["hand_detected"] == 0
    assert report["intervals"]["capture_to_hand_ms"] is None


def test_delayed_simulator_command_is_measured_and_stopped() -> None:
    class DelayedDevice(SimulatedDevice):
        async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
            await asyncio.sleep(0.025)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise() -> None:
        device = DelayedDevice()
        registry = DeviceRegistry()
        registry.add(device)
        registry.select(device.identifier)
        recorder = LatencyRecorder()
        recorder.start()
        safety = SafetyController(registry, Settings(), latency=recorder)
        await safety.start_automation_pattern(0, "SHORT_PULSE", 0.2, 0.08,
                                              lambda: True, trace_id=1)
        assert safety._task is not None
        await safety._task
        assert device.last_intensity == 0
        assert recorder.report()["intervals"]["command_ack_ms"]["median_ms"] >= 20
        await safety.shutdown()

    asyncio.run(exercise())


def test_timeout_and_emergency_stop_faults_leave_simulator_off() -> None:
    class HangingDevice(SimulatedDevice):
        async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
            await asyncio.sleep(0.2)
            await super().vibrate_feature(feature_index, intensity)

    async def exercise() -> None:
        device = HangingDevice()
        registry = DeviceRegistry()
        registry.add(device)
        registry.select(device.identifier)
        recorder = LatencyRecorder()
        recorder.start()
        safety = SafetyController(
            registry, Settings(command_timeout_seconds=0.01), latency=recorder,
        )
        await safety.start_automation_pattern(0, "SHORT_PULSE", 0.2, 0.1,
                                              lambda: True, trace_id=1)
        assert safety._task is not None
        await safety._task
        report = recorder.report()
        assert report["stage_counts"]["command_failed"] == 1
        assert report["stage_counts"]["command_completed"] == 0
        assert device.last_intensity == 0
        assert device.stop_count > 0

        # Use a longer command deadline so the explicit stop races the delay.
        recorder.start()
        safety = SafetyController(registry, Settings(command_timeout_seconds=0.5),
                                  latency=recorder)
        await safety.start_automation_pattern(0, "SHORT_PULSE", 0.2, 0.3,
                                              lambda: True, trace_id=2)
        await asyncio.sleep(0.01)
        await safety.emergency_stop()
        await asyncio.sleep(0.22)
        assert safety.emergency_stop_latched
        assert device.last_intensity == 0
        assert recorder.report()["stage_counts"]["command_failed"] == 1
        await safety.shutdown()

    asyncio.run(exercise())
