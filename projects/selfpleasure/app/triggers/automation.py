"""Explicitly armed, bounded camera-to-device automation."""

import asyncio
from dataclasses import asdict, dataclass
from enum import StrEnum
import math
import time
from collections.abc import Callable

from app.devices.registry import DeviceRegistry
from app.diagnostics import LatencyRecorder, TraceStage
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.patterns import Pattern
from app.triggers.session import SessionPhase, SessionSettings, step_for


class AutomationState(StrEnum):
    DISARMED = "DISARMED"
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class AutomationRule:
    feature_index: int = 0
    intensity: float = 0.2
    duration: float = 2.0
    cooldown: float = 1.0
    minimum_confidence: float = 0.6
    pattern: Pattern = Pattern.SHORT_PULSE


class AutomationController:
    def __init__(self, devices: DeviceRegistry, safety: SafetyController,
                 camera_running: Callable[[], bool], intiface_connected: Callable[[], bool],
                 latency: LatencyRecorder | None = None) -> None:
        self._devices = devices
        self._safety = safety
        self._camera_running = camera_running
        self._intiface_connected = intiface_connected
        self._latency = latency
        self._lock = asyncio.Lock()
        self._watchdog_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.state = AutomationState.DISARMED
        self.rule = AutomationRule()
        self.last_error: str | None = None
        self._selected_id: str | None = None
        self._valid_at = 0.0
        self._pulse_until = 0.0
        self._cooldown_until = 0.0
        self._evidence_count = 0
        self._evidence_started = 0.0
        self._session_settings: SessionSettings | None = None
        self._session_completed_pulses = 0
        self._session_finished = False

    def snapshot(self) -> dict[str, object]:
        session_step = (step_for(self._session_settings, self._session_completed_pulses)
                        if self._session_settings and not self._session_finished else None)
        return {
            "state": self.state, "rule": asdict(self.rule),
            "selected_device": self._selected_id, "error": self.last_error,
            "output_running": self._safety.running if self.state == AutomationState.ACTIVE else False,
            "session": {
                "enabled": self._session_settings is not None,
                "settings": asdict(self._session_settings) if self._session_settings else None,
                "phase": (SessionPhase.COMPLETE if self._session_finished else
                          session_step.phase if session_step else None),
                "completed_pulses": self._session_completed_pulses,
                "total_pulses": self._session_settings.total_pulses if self._session_settings else 0,
                "next_pattern": session_step.pattern if session_step else None,
                "next_intensity": round(self.rule.intensity * session_step.intensity_fraction, 4)
                if session_step else None,
            },
        }

    async def arm(self, rule: AutomationRule, session: SessionSettings | None = None) -> None:
        self._loop = asyncio.get_running_loop()
        if session is not None:
            session.validate()
        try:
            pattern = Pattern(rule.pattern)
        except ValueError as exc:
            raise ValueError("Unsupported vibration pattern") from exc
        if not all(math.isfinite(value) for value in
                   (rule.intensity, rule.duration, rule.cooldown, rule.minimum_confidence)):
            raise ValueError("Automation settings must be finite")
        if not (0 < rule.intensity <= min(self._safety.max_intensity, 0.5)
                and 0 < rule.duration <= min(self._safety.max_duration_seconds, 2.0)
                and 0.5 <= rule.cooldown <= 30
                and 0 <= rule.minimum_confidence <= 1):
            raise ValueError("Automation settings exceed conservative limits")
        async with self._lock:
            if self._safety.evaluation_mode:
                raise RuntimeError("Automation cannot arm during evaluation")
            if self.state not in {AutomationState.DISARMED, AutomationState.EMERGENCY_STOP,
                                  AutomationState.ERROR}:
                raise RuntimeError("Disarm before changing automation settings")
            if not self._camera_running():
                raise RuntimeError("Start the camera before arming automation")
            device = self._devices.get(self._devices.selected_id) if self._devices.selected_id else None
            if device is None:
                raise RuntimeError("Select a device before arming automation")
            if not device.info.simulated and not self._safety.real_device_output_enabled:
                raise RuntimeError("Real-device output is locked after a failed physical stop")
            if not device.info.simulated and not self._intiface_connected():
                raise RuntimeError("Intiface is disconnected")
            if rule.feature_index not in getattr(device, "vibration_features", ()):
                raise RuntimeError("Select a supported vibration feature")
            if self._safety.running or self._safety.activation_enabled:
                raise RuntimeError("Finish or disarm manual control before arming automation")
            self.rule = AutomationRule(
                feature_index=rule.feature_index, intensity=rule.intensity,
                duration=rule.duration, cooldown=rule.cooldown,
                minimum_confidence=rule.minimum_confidence, pattern=pattern,
            )
            self._selected_id = device.info.identifier
            self._valid_at = 0
            self._evidence_count = 0
            self._evidence_started = 0
            self._session_settings = session
            self._session_completed_pulses = 0
            self._session_finished = False
            self.last_error = None
            self._safety.emergency_stop_latched = False
            self.state = AutomationState.ARMED
            if self._watchdog_task is None or self._watchdog_task.done():
                self._watchdog_task = asyncio.create_task(self._watchdog())

    async def disarm(self) -> None:
        if self.state not in {AutomationState.EMERGENCY_STOP, AutomationState.ERROR}:
            self.state = AutomationState.DISARMED
        self._evidence_count = 0
        self._selected_id = None
        self._session_settings = None
        self._session_completed_pulses = 0
        self._session_finished = False
        await self._safety.stop()

    async def emergency_stop(self) -> None:
        self.state = AutomationState.EMERGENCY_STOP
        self._evidence_count = 0
        self._selected_id = None
        self._session_settings = None
        self._session_finished = False
        await self._safety.emergency_stop()

    async def fail(self, reason: str) -> None:
        if self.state == AutomationState.EMERGENCY_STOP:
            return
        self.state = AutomationState.ERROR
        self.last_error = reason
        self._selected_id = None
        self._session_settings = None
        self._session_finished = False
        await self._safety.stop()

    def device_lost(self, identifier: str | None = None) -> None:
        if identifier is not None and identifier != self._selected_id:
            return
        if self.state in {AutomationState.ARMED, AutomationState.ACTIVE, AutomationState.COOLDOWN}:
            self.state = AutomationState.ERROR
            self.last_error = "Selected device or Intiface disconnected"
            self._selected_id = None
            self._session_settings = None
            self._session_finished = False
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self._safety.stop()))

    async def handle_event(self, event: Event) -> None:
        if self.state not in {AutomationState.ARMED, AutomationState.ACTIVE, AutomationState.COOLDOWN}:
            return
        now = time.monotonic()
        if event.topic == "camera_stopped" or not self._camera_running():
            await self.disarm()
            return
        if event.topic == "tracking_lost":
            await self.disarm()
            return
        if event.topic not in {"interaction_started", "interaction_continued"}:
            self._evidence_count = 0
            if self.state == AutomationState.ACTIVE:
                await self._stop_to_cooldown(now)
            return
        observed_at = event.payload.get("observed_at", 0)
        confidence = event.payload.get("confidence", 0)
        if (not isinstance(observed_at, (float, int)) or now - observed_at > 0.4 or
                not isinstance(confidence, (float, int)) or confidence < self.rule.minimum_confidence):
            self._evidence_count = 0
            if self.state == AutomationState.ACTIVE:
                await self._stop_to_cooldown(now)
            return
        self._valid_at = now
        if self.state == AutomationState.ACTIVE:
            return
        if self.state == AutomationState.COOLDOWN:
            if now < self._cooldown_until:
                return
            self.state = AutomationState.ARMED
            self._evidence_count = 0
        if self._evidence_count == 0 or now - self._evidence_started > 0.35:
            self._evidence_started = now
            self._evidence_count = 0
        self._evidence_count += 1
        if self._evidence_count < 3 or now - self._evidence_started < 0.07:
            return
        self._evidence_count = 0
        if self._devices.selected_id != self._selected_id:
            await self.disarm()
            return
        device = self._devices.get(self._selected_id)
        if device is None or (not device.info.simulated and not self._intiface_connected()):
            self.device_lost()
            return
        try:
            trace_id = event.payload.get("frame_id")
            if type(trace_id) is not int or trace_id < 1:
                trace_id = None
            if trace_id is not None and self._latency is not None:
                self._latency.mark(trace_id, TraceStage.TRIGGER_ACCEPTED)
            session_step = (step_for(self._session_settings, self._session_completed_pulses)
                            if self._session_settings else None)
            pattern = session_step.pattern if session_step else self.rule.pattern
            intensity = (self.rule.intensity * session_step.intensity_fraction
                         if session_step else self.rule.intensity)
            await self._safety.start_automation_pattern(
                self.rule.feature_index, pattern, intensity, self.rule.duration,
                lambda: self.state in {AutomationState.ARMED, AutomationState.ACTIVE}
                and self._selected_id == device.info.identifier
                and self._devices.selected_id == device.info.identifier
                and self._camera_running()
                and (device.info.simulated or self._intiface_connected()),
                trace_id=trace_id,
            )
            if self.state != AutomationState.ARMED:
                await self._safety.stop()
                return
            self._pulse_until = time.monotonic() + self.rule.duration
            self.state = AutomationState.ACTIVE
        except Exception as exc:
            if self.state != AutomationState.ARMED:
                await self._safety.stop()
                return
            self.state = AutomationState.ERROR
            self.last_error = str(exc)
            await self._safety.stop()

    async def _stop_to_cooldown(self, now: float, completed: bool = False) -> None:
        await self._safety.stop()
        if self._safety.last_error is not None:
            self.last_error = self._safety.last_error
            self.state = AutomationState.ERROR
        elif self.state == AutomationState.ACTIVE:
            if completed and self._session_settings is not None:
                self._session_completed_pulses += 1
                if self._session_completed_pulses >= self._session_settings.total_pulses:
                    self._session_finished = True
                    self._selected_id = None
                    self._evidence_count = 0
                    self.state = AutomationState.DISARMED
                    return
            self._cooldown_until = now + self.rule.cooldown
            self.state = AutomationState.COOLDOWN

    async def _watchdog(self) -> None:
        while self.state in {AutomationState.ARMED, AutomationState.ACTIVE, AutomationState.COOLDOWN}:
            await asyncio.sleep(0.05)
            if self.state not in {AutomationState.ARMED, AutomationState.ACTIVE, AutomationState.COOLDOWN}:
                break
            now = time.monotonic()
            if not self._camera_running() or self._devices.selected_id != self._selected_id:
                await self.disarm()
                continue
            selected = self._devices.get(self._selected_id)
            if selected is None or (not selected.info.simulated and not self._intiface_connected()):
                self.device_lost()
                continue
            if self.state == AutomationState.ACTIVE:
                if now - self._valid_at > 0.35:
                    await self.disarm()
                elif self._safety.last_error is not None:
                    self.last_error = self._safety.last_error
                    self.state = AutomationState.ERROR
                    await self._safety.stop()
                elif now >= self._pulse_until or not self._safety.running:
                    await self._stop_to_cooldown(now, completed=True)
            elif self.state == AutomationState.COOLDOWN and now >= self._cooldown_until:
                self.state = AutomationState.ARMED

    async def shutdown(self) -> None:
        await self.emergency_stop()
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
