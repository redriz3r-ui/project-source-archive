"""Device-neutral contracts keep visual recognition away from hardware APIs."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class DeviceStatus(StrEnum):
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    ACTIVE = "active"
    STOP_UNCONFIRMED = "stop_unconfirmed"


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    identifier: str
    name: str
    simulated: bool
    capabilities: tuple[str, ...]
    status: DeviceStatus


class ControllableDevice(Protocol):
    @property
    def info(self) -> DeviceInfo: ...

    async def stop(self) -> None: ...

    async def vibrate(self, intensity: float) -> None: ...
