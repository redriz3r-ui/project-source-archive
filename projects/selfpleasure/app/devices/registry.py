"""In-memory inventory independent of any transport implementation."""

import asyncio

from app.devices.models import ControllableDevice, DeviceInfo


class DeviceRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, ControllableDevice] = {}
        self.selected_id: str | None = None

    def add(self, device: ControllableDevice) -> DeviceInfo:
        self._devices[device.info.identifier] = device
        return device.info

    def list(self) -> tuple[DeviceInfo, ...]:
        return tuple(device.info for device in self._devices.values())

    def get(self, identifier: str) -> ControllableDevice | None:
        return self._devices.get(identifier)

    def select(self, identifier: str) -> DeviceInfo:
        device = self.get(identifier)
        if device is None:
            raise KeyError(identifier)
        self.selected_id = identifier
        return device.info

    def remove(self, identifier: str) -> None:
        self._devices.pop(identifier, None)
        if self.selected_id == identifier:
            self.selected_id = None

    def clear_real(self) -> None:
        for identifier, device in tuple(self._devices.items()):
            if not device.info.simulated:
                self.remove(identifier)

    async def stop_all(self) -> None:
        # A stalled device must not prevent a stop attempt reaching other devices.
        devices = tuple(self._devices.values())
        results = await asyncio.gather(*(device.stop() for device in devices),
                                       return_exceptions=True)
        first_error = next((result for result in results if isinstance(result, BaseException)), None)
        if first_error is not None:
            raise first_error
