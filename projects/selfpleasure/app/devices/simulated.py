"""No-hardware device used by tests and early UI development."""

from app.devices.models import DeviceInfo, DeviceStatus


class SimulatedDevice:
    def __init__(self, identifier: str = "simulator-1") -> None:
        self.identifier = identifier
        self._status = DeviceStatus.IDLE
        self.stop_count = 0
        self.last_intensity = 0.0

    @property
    def info(self) -> DeviceInfo:
        return DeviceInfo(
            identifier=self.identifier,
            name="Simulated Vibrator",
            simulated=True,
            capabilities=("vibrate", "stop"),
            status=self._status,
        )

    async def stop(self) -> None:
        self._status = DeviceStatus.IDLE
        self.last_intensity = 0.0
        self.stop_count += 1

    async def vibrate(self, intensity: float) -> None:
        self.last_intensity = intensity
        self._status = DeviceStatus.ACTIVE

    @property
    def vibration_features(self) -> tuple[int, ...]:
        return (0,)

    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        if feature_index != 0:
            raise ValueError("Selected feature has no vibration output")
        await self.vibrate(intensity)
