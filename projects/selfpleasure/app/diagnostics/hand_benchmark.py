"""Measure Hand Stroke camera loop with generated frames and the real local model."""

import argparse
import asyncio
import json
import time

import numpy as np

from app.camera.service import CameraService, CameraStatus
from app.config import Settings
from app.vision.hand_tracking import HandCalibration


class _GeneratedSource:
    def __init__(self) -> None:
        self.reads = 0

    def open(self) -> None:
        pass

    def read(self) -> np.ndarray:
        self.reads += 1
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def close(self) -> None:
        pass


class _EmptyCalibration:
    def snapshot(self) -> HandCalibration:
        return HandCalibration()


async def measure(seconds: float = 3.0) -> dict[str, object]:
    if not 1 <= seconds <= 30:
        raise ValueError("seconds must be between 1 and 30")
    source = _GeneratedSource()
    camera = CameraService(Settings(camera_target_fps=24), source_factory=lambda: source,
                           hand_calibration=_EmptyCalibration())
    camera.set_mode("hand")
    started = time.monotonic()
    try:
        camera.start()
        deadline = started + 10
        while camera.status == CameraStatus.STARTING and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        if camera.status != CameraStatus.RUNNING:
            raise RuntimeError(f"Hand camera could not start: {camera.error}")
        measuring_from = time.monotonic()
        initial_reads = source.reads
        await asyncio.sleep(seconds)
        elapsed = time.monotonic() - measuring_from
        reads = source.reads - initial_reads
        snapshot = camera.snapshot()
        if snapshot["status"] != CameraStatus.RUNNING:
            raise RuntimeError(f"Hand camera stopped: {snapshot['error']}")
        return {
            "source": "generated blank frames, not a real webcam",
            "model": "installed local MediaPipe Hand Landmarker",
            "resolution": "640x480",
            "target_fps": 24,
            "measured_frames": reads,
            "elapsed_seconds": round(elapsed, 3),
            "measured_pipeline_fps": round(reads / elapsed, 2),
            "displayed_smoothed_fps": snapshot["fps"],
            "real_webcam_fps_measured": False,
            "device_commands_sent": False,
        }
    finally:
        await camera.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=3.0)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.seconds)), indent=2))


if __name__ == "__main__":
    main()
