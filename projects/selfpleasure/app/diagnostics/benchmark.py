"""Synthetic-camera, simulated-device latency baseline; never opens hardware."""

import argparse
import asyncio
import json
import time

import numpy as np

from app.camera.service import CameraService, CameraStatus
from app.config import Settings
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.diagnostics import LatencyRecorder, TraceStage
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.automation import AutomationController, AutomationRule
from app.vision.calibration import Calibration
from app.vision.object_tracker import ObjectObservation
from app.vision.service import FaceObservation


class _SyntheticSource:
    def open(self) -> None:
        pass

    def read(self) -> np.ndarray:
        return np.zeros((120, 160, 3), dtype=np.uint8)

    def close(self) -> None:
        pass


class _StubFaceVision:
    def open(self) -> None:
        pass

    def process(self, frame: np.ndarray, timestamp_ms: int, overlay: bool):
        return FaceObservation(
            face_detected=True, mouth_detected=True, mouth_x=0.5, mouth_y=0.5,
            mouth_openness=0.2, mouth_width=0.12,
            mouth_region=(0.44, 0.47, 0.12, 0.06), tracking_quality=0.95,
        ), frame

    def close(self) -> None:
        pass


class _SyntheticObject:
    def __init__(self) -> None:
        self.index = 0

    def process(self, frame: np.ndarray) -> ObjectObservation:
        x = max(0.62, 0.9 - self.index * 0.02) if self.index < 15 else (
            0.60 if self.index % 2 else 0.63
        )
        self.index += 1
        return ObjectObservation(True, x, 0.5, (x - 0.02, 0.48, 0.04, 0.04),
                                 0.9, source="synthetic")


class _FixedCalibration:
    def snapshot(self):
        return Calibration(), 0


async def measure(samples: int = 3, timeout_s: float = 8.0) -> dict[str, object]:
    """Measure app plumbing with synthetic vision and a simulated device only."""
    if type(samples) is not int or not 1 <= samples <= 10:
        raise ValueError("samples must be an integer from 1 to 10")
    recorder = LatencyRecorder(capacity=512)
    recorder.start()
    settings = Settings(camera_target_fps=24)
    registry = DeviceRegistry()
    simulator = SimulatedDevice()
    registry.add(simulator)
    registry.select(simulator.identifier)
    safety = SafetyController(registry, settings, latency=recorder)
    camera = CameraService(
        settings, source_factory=_SyntheticSource, vision_factory=_StubFaceVision,
        calibration=_FixedCalibration(), object_detector_factory=lambda _: _SyntheticObject(),
        latency=recorder,
    )
    controller = AutomationController(
        registry, safety, lambda: camera.status == CameraStatus.RUNNING,
        lambda: False, latency=recorder,
    )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=64)

    def on_camera_event(event: Event) -> None:
        def enqueue() -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                asyncio.create_task(controller.fail("Synthetic event queue overflow"))
        loop.call_soon_threadsafe(enqueue)

    async def consume() -> None:
        while True:
            await controller.handle_event(await queue.get())

    camera.set_event_sink(on_camera_event)
    consumer = asyncio.create_task(consume())
    try:
        camera.start()
        deadline = time.monotonic() + timeout_s
        while camera.status == CameraStatus.STARTING and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        if camera.status != CameraStatus.RUNNING:
            raise RuntimeError(f"Synthetic camera failed to start: {camera.error}")
        await controller.arm(AutomationRule(duration=0.15, cooldown=0.5))
        while time.monotonic() < deadline:
            if recorder.report()["stage_counts"][TraceStage.COMMAND_COMPLETED.value] >= samples:
                break
            await asyncio.sleep(0.02)
        else:
            raise TimeoutError("Synthetic benchmark did not collect the requested acknowledgements")
    finally:
        await controller.shutdown()
        await safety.shutdown()
        await camera.shutdown()
        camera.set_event_sink(None)
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass
        recorder.stop()
    return {
        "kind": "synthetic_oral_pipeline_baseline",
        "camera": "generated black frames with stub face and object observations",
        "device": "injected simulator; no Intiface connection",
        "hand_tracking_implemented": False,
        "stroke_decision_implemented": False,
        "physical_device_onset_measured": False,
        "report": recorder.report(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.samples)), indent=2))


if __name__ == "__main__":
    main()
