"""Watchdog policy placeholder with conservative defaults."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WatchdogPolicy:
    maximum_activation_seconds: float = 10.0
    heartbeat_timeout_seconds: float = 2.0

