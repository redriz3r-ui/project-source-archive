"""Buttplug v4 adapter. No connection or output happens at import/startup."""

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from buttplug import ButtplugClient, DeviceOutputCommand, OutputType

from app.devices.models import DeviceInfo, DeviceStatus
from app.devices.registry import DeviceRegistry


class ButtplugDeviceLike(Protocol):
    index: int
    name: str
    features: dict

    def has_output(self, output_type: OutputType) -> bool: ...

    async def run_output(self, command: DeviceOutputCommand) -> None: ...

    async def stop(self) -> None: ...

    def get_features_with_output(self, output_type: OutputType) -> list: ...


class ButtplugClientLike(Protocol):
    connected: bool
    devices: dict[int, ButtplugDeviceLike]
    on_device_added: Callable | None
    on_device_removed: Callable | None
    on_server_disconnect: Callable | None

    async def connect(self, url: str) -> None: ...

    async def disconnect(self) -> None: ...

    async def start_scanning(self) -> None: ...

    async def stop_scanning(self) -> None: ...


class RealDevice:
    def __init__(self, device: ButtplugDeviceLike) -> None:
        self._device = device
        self._status = DeviceStatus.IDLE

    @property
    def info(self) -> DeviceInfo:
        capabilities = tuple(sorted({
            output for feature in self._device.features.values()
            for output in (feature.outputs or {})
        }))
        return DeviceInfo(
            identifier=f"intiface-{self._device.index}",
            name=self._device.name,
            simulated=False,
            capabilities=capabilities,
            status=self._status,
        )

    async def vibrate(self, intensity: float) -> None:
        if not self._device.has_output(OutputType.VIBRATE):
            raise ValueError("Selected device has no vibration output")
        await self._device.run_output(DeviceOutputCommand(OutputType.VIBRATE, intensity))
        self._status = DeviceStatus.ACTIVE

    @property
    def vibration_features(self) -> tuple[int, ...]:
        return tuple(index for index, feature in self._device.features.items()
                     if feature.has_output(OutputType.VIBRATE))

    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        feature = self._device.features.get(feature_index)
        if feature is None or not feature.has_output(OutputType.VIBRATE):
            raise ValueError("Selected feature has no vibration output")
        await feature.run_output(DeviceOutputCommand(OutputType.VIBRATE, intensity))
        self._status = DeviceStatus.ACTIVE

    async def stop(self) -> None:
        # Both v4 stop scopes are available in the installed client. A device-
        # level StopCmd alone failed to produce a physical stop in one preflight;
        # attempt the vibration features independently as well. A protocol ACK
        # is still not proof that the hardware physically stopped.
        self._status = DeviceStatus.STOP_UNCONFIRMED
        commands = [self._device.stop()]
        errors: list[BaseException] = []
        for feature in self._device.features.values():
            try:
                supports_vibration = getattr(feature, "has_output", None)
                if callable(supports_vibration):
                    is_vibration = supports_vibration(OutputType.VIBRATE)
                else:
                    is_vibration = OutputType.VIBRATE.value in (getattr(feature, "outputs", None) or {})
                feature_stop = getattr(feature, "stop", None)
                if is_vibration and callable(feature_stop):
                    command = feature_stop()
                    if not inspect.isawaitable(command):
                        raise TypeError("Feature stop did not return an awaitable")
                    commands.append(command)
            except Exception as exc:
                errors.append(exc)
        results = await asyncio.gather(*commands, return_exceptions=True)
        errors.extend(result for result in results if isinstance(result, BaseException))
        if errors:
            raise RuntimeError("One or more Buttplug stop commands failed") from errors[0]
        self._status = DeviceStatus.IDLE


@dataclass(slots=True)
class IntifaceState:
    url: str
    connected: bool = False
    scanning: bool = False
    error: str | None = None


class IntifaceGateway:
    def __init__(
        self,
        url: str,
        registry: DeviceRegistry,
        client_factory: Callable[[str], ButtplugClientLike] = ButtplugClient,
        on_disconnect: Callable[[], None] | None = None,
        on_device_removed: Callable[[str], None] | None = None,
    ) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Intiface URL must use a local ws:// address")
        self.state = IntifaceState(url=url)
        self._registry = registry
        self._client_factory = client_factory
        self._client: ButtplugClientLike | None = None
        self._on_disconnect = on_disconnect
        self._on_device_removed = on_device_removed
        self._lock = asyncio.Lock()

    def _added(self, device: ButtplugDeviceLike) -> None:
        identifier = f"intiface-{device.index}"
        if self._registry.get(identifier) is None:
            self._registry.add(RealDevice(device))

    def _removed(self, device: ButtplugDeviceLike) -> None:
        identifier = f"intiface-{device.index}"
        if self._on_device_removed:
            self._on_device_removed(identifier)
        self._registry.remove(identifier)

    def _disconnected(self) -> None:
        self.state.connected = False
        self.state.scanning = False
        self.state.error = "Intiface connection lost"
        if self._on_disconnect:
            self._on_disconnect()
        self._registry.clear_real()

    async def connect(self) -> None:
        async with self._lock:
            if self._client and self._client.connected:
                return
            client = self._client_factory("SelfPleasure")
            client.on_device_added = self._added
            client.on_device_removed = self._removed
            client.on_server_disconnect = self._disconnected
            try:
                await asyncio.wait_for(client.connect(self.state.url), timeout=5)
            except Exception as exc:
                self.state.error = str(exc)
                self.state.connected = False
                raise
            self._client = client
            self.state.connected = True
            self.state.error = None
            for device in client.devices.values():
                self._added(device)

    async def scan(self, seconds: float) -> None:
        client = self._client
        if not client or not client.connected:
            raise ConnectionError("Connect to Intiface before scanning")
        await asyncio.wait_for(client.start_scanning(), timeout=5)
        self.state.scanning = True
        try:
            await asyncio.sleep(seconds)
        finally:
            self.state.scanning = False
            if client.connected and getattr(client, "scanning", True):
                await asyncio.wait_for(client.stop_scanning(), timeout=5)
            for device in client.devices.values():
                self._added(device)

    async def shutdown(self) -> None:
        async with self._lock:
            client = self._client
            self._client = None
            self.state.connected = False
            self.state.scanning = False
            try:
                if client and client.connected:
                    await asyncio.wait_for(client.disconnect(), timeout=5)
            finally:
                self._registry.clear_real()
