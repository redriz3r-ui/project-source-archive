"""Bounded hand responses; real-device use requires an explicit pilot arm.

The camera publishes device-neutral events. This controller never consumes frames,
and the safety controller remains the sole owner of output commands.
"""

import asyncio
from collections import deque
from dataclasses import asdict, dataclass
from enum import StrEnum
import math
import time
from collections.abc import Callable

from app.devices.registry import DeviceRegistry
from app.events import Event
from app.safety.controller import SafetyController
from app.triggers.patterns import Pattern, build_pattern
from app.vision.stroke_contract import StrokeEvent, StrokeEventKind, StrokeObservation


class HandResponseState(StrEnum):
    DISARMED = "DISARMED"
    PAUSED = "PAUSED"
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ERROR = "ERROR"


class HandResponseMode(StrEnum):
    ONE_RESPONSE = "ONE_RESPONSE"
    MOTION_SHAPED = "MOTION_SHAPED"
    FOLLOW_MOVEMENT = "FOLLOW_MOVEMENT"


class ResponseStyle(StrEnum):
    GENTLE = "GENTLE"
    CRISP = "CRISP"
    RAMP = "RAMP"


@dataclass(frozen=True, slots=True)
class HandResponseRule:
    feature_index: int = 0
    intensity: float = 0.2
    duration: float = 0.18
    cooldown: float = 0.3
    minimum_confidence: float = 0.5
    mode: HandResponseMode = HandResponseMode.ONE_RESPONSE
    style: ResponseStyle = ResponseStyle.CRISP


def validate_hand_rule(rule: HandResponseRule, max_intensity: float,
                       max_duration: float) -> HandResponseRule:
    try:
        mode = HandResponseMode(rule.mode)
    except ValueError as exc:
        raise ValueError("Unsupported hand response mode") from exc
    try:
        style = ResponseStyle(rule.style)
    except ValueError as exc:
        raise ValueError("Unsupported response style") from exc
    if type(rule.feature_index) is not int or rule.feature_index < 0:
        raise ValueError("Select a vibration feature")
    if not all(math.isfinite(value) for value in
               (rule.intensity, rule.duration, rule.cooldown, rule.minimum_confidence)):
        raise ValueError("Hand response settings must be finite")
    duration_limit = 0.12 if mode == HandResponseMode.FOLLOW_MOVEMENT else 0.5
    cooldown_floor = 0.08 if mode == HandResponseMode.FOLLOW_MOVEMENT else 0.25
    if not (0 < rule.intensity <= min(max_intensity, 0.3)
            and 0 < rule.duration <= min(max_duration, duration_limit)
            and cooldown_floor <= rule.cooldown <= 5.0
            and 0.5 <= rule.minimum_confidence <= 1):
        raise ValueError("Hand response settings exceed conservative limits")
    return HandResponseRule(rule.feature_index, rule.intensity, rule.duration,
                            rule.cooldown, rule.minimum_confidence, mode, style)


def validate_real_pilot_rule(rule: HandResponseRule) -> None:
    if (rule.mode != HandResponseMode.ONE_RESPONSE
            or rule.style != ResponseStyle.CRISP
            or rule.intensity > 0.2 or rule.duration > 0.12
            or rule.cooldown < 0.5):
        raise ValueError("Real pilot permits only one crisp pulse per stroke, at most 20% for 0.12 seconds with 0.5 seconds rest")


def validate_tabletop_rule(rule: HandResponseRule) -> None:
    if (rule.mode != HandResponseMode.FOLLOW_MOVEMENT
            or rule.style != ResponseStyle.CRISP
            or rule.intensity > 0.2 or rule.duration > 0.08
            or rule.cooldown < 0.08):
        raise ValueError("Tabletop mode permits only fresh-movement crisp commands, at most 20% for 0.08 seconds with 0.08 seconds rest")


def preview_hand_rule(rule: HandResponseRule, max_intensity: float,
                      max_duration: float) -> dict[str, object]:
    """Pure response envelope preview; never touches a registry or device."""
    checked = validate_hand_rule(rule, max_intensity, max_duration)
    if checked.mode == HandResponseMode.FOLLOW_MOVEMENT:
        steps = build_pattern(Pattern.SHORT_PULSE, checked.intensity,
                              checked.duration, max_intensity)
        explanation = "Each fresh movement update may cause one short bounded pulse; busy updates are dropped."
    else:
        pattern = {ResponseStyle.GENTLE: Pattern.GENTLE_PULSE,
                   ResponseStyle.CRISP: Pattern.SHORT_PULSE,
                   ResponseStyle.RAMP: Pattern.GRADUAL_RAMP}[checked.style]
        steps = build_pattern(pattern, checked.intensity, checked.duration, max_intensity)
        explanation = "One completed stroke may cause this bounded envelope; rapid strokes during cooldown are dropped."
    return {"mode": checked.mode, "style": checked.style,
            "steps": [step.as_dict() for step in steps],
            "maximum_intensity": checked.intensity,
            "maximum_duration": checked.duration,
            "cooldown": checked.cooldown,
            "explanation": explanation, "device_command_sent": False}


class HandResponseController:
    """Never queues responses: busy, stale and duplicate completions are dropped."""

    MAX_EVENT_AGE_NS = 300_000_000
    # Longer than the vision drop-frame grace, but shorter than any sustained
    # loss.  Commands themselves are capped at 80 ms in tabletop mode.
    TRACKING_GAP_NS = 300_000_000
    TABLETOP_TRACKING_GAP_NS = 150_000_000

    def __init__(self, devices: DeviceRegistry, safety: SafetyController,
                 camera_running: Callable[[], bool],
                 on_session_expired: Callable[[], object] | None = None,
                 intiface_connected: Callable[[], bool] = lambda: False) -> None:
        self._devices = devices
        self._safety = safety
        self._camera_running = camera_running
        self._on_session_expired = on_session_expired
        self._intiface_connected = intiface_connected
        self._lock = asyncio.Lock()
        self._watchdog_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.state = HandResponseState.DISARMED
        self.rule = HandResponseRule()
        self.last_error: str | None = None
        self.last_disarm_reason: str = "Not started"
        self._selected_id: str | None = None
        self._armed_ns = 0
        self._tracking_ns = 0
        self._last_frame = 0
        self._last_stroke_id = 0
        self._last_response_frame = 0
        self._started_ids: set[int] = set()
        self._active_stroke_id: int | None = None
        self._active_frame_id: int | None = None
        self._active_command_acknowledged = False
        self._active_until = 0.0
        self._cooldown_until = 0.0
        self._session_managed = False
        self._real_pilot = False
        self._tabletop = False
        self._session_lease_until = 0.0
        self._epoch = 0
        self.stroke_count = 0
        self.completed_response_count = 0
        self.submitted_response_count = 0
        self.dropped_response_count = 0
        self._latencies_ms: deque[float] = deque(maxlen=64)

    def snapshot(self) -> dict[str, object]:
        latencies = tuple(self._latencies_ms)
        return {
            "state": self.state, "rule": asdict(self.rule),
            "selected_device": self._selected_id,
            "active_stroke_id": self._active_stroke_id,
            "active_frame_id": self._active_frame_id,
            "stroke_count": self.stroke_count,
            "pending_response_count": int(self.state == HandResponseState.ACTIVE),
            "completed_response_count": self.completed_response_count,
            "submitted_response_count": self.submitted_response_count,
            "dropped_response_count": self.dropped_response_count,
            "simulator_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "simulator_latency_samples": len(latencies),
            "error": self.last_error,
            "disarm_reason": self.last_disarm_reason,
            "simulator_only": not self._real_pilot,
            "real_pilot": self._real_pilot,
            "tabletop": self._tabletop,
            "session_managed": self._session_managed,
        }

    async def arm(self, rule: HandResponseRule, *, session_managed: bool = False,
                  real_pilot: bool = False, tabletop: bool = False) -> None:
        checked = validate_hand_rule(rule, self._safety.max_intensity,
                                     self._safety.max_duration_seconds)
        if tabletop:
            validate_tabletop_rule(checked)
        async with self._lock:
            if self.state not in {HandResponseState.DISARMED, HandResponseState.PAUSED, HandResponseState.ERROR,
                                  HandResponseState.EMERGENCY_STOP}:
                raise RuntimeError("Disarm hand responses before changing settings")
            if self._safety.evaluation_mode or self._safety.running or self._safety.activation_enabled:
                raise RuntimeError("Device control is unavailable")
            if not self._camera_running():
                raise RuntimeError("Start the hand camera before arming")
            tracking_gap = self.TABLETOP_TRACKING_GAP_NS if tabletop else self.TRACKING_GAP_NS
            if time.monotonic_ns() - self._tracking_ns > tracking_gap:
                raise RuntimeError("Wait for valid hand tracking before arming")
            device = self._devices.get(self._devices.selected_id) if self._devices.selected_id else None
            if device is None:
                raise RuntimeError("Select a device before arming")
            if not device.info.simulated:
                if not self._safety.real_device_output_enabled:
                    raise RuntimeError("Real-device output is locked after a failed physical stop")
                if not real_pilot or not session_managed or not self._intiface_connected():
                    raise RuntimeError("Real hand responses require an explicit connected supervised pilot")
                if not tabletop:
                    validate_real_pilot_rule(checked)
            elif real_pilot:
                raise RuntimeError("Select the real device before requesting a real pilot")
            if ("vibrate" not in {value.lower() for value in device.info.capabilities}
                    or checked.feature_index not in getattr(device, "vibration_features", ())):
                raise RuntimeError("Select an advertised vibration feature")
            self.rule = checked
            self._selected_id = device.info.identifier
            self._armed_ns = time.monotonic_ns()
            self._last_stroke_id = 0
            self._last_response_frame = 0
            self._started_ids.clear()
            self._last_frame = 0
            self._active_stroke_id = None
            self._active_frame_id = None
            self._active_command_acknowledged = False
            self._session_managed = session_managed
            self._real_pilot = real_pilot
            self._tabletop = tabletop
            self._session_lease_until = time.monotonic() + 1.5 if session_managed else 0.0
            self.stroke_count = 0
            self.completed_response_count = 0
            self.submitted_response_count = 0
            self.dropped_response_count = 0
            self._latencies_ms.clear()
            self.last_error = None
            self.last_disarm_reason = ""
            self._epoch += 1
            self._safety.emergency_stop_latched = False
            self.state = HandResponseState.ARMED
            self._loop = asyncio.get_running_loop()
            if self._watchdog_task is None or self._watchdog_task.done():
                self._watchdog_task = asyncio.create_task(self._watchdog())

    async def disarm(self, reason: str = "disarm") -> None:
        self._epoch += 1
        if self.state not in {HandResponseState.ERROR, HandResponseState.EMERGENCY_STOP}:
            self.state = HandResponseState.DISARMED
        self._selected_id = None
        self._active_stroke_id = None
        self._active_frame_id = None
        self._active_command_acknowledged = False
        self._started_ids.clear()
        self._tracking_ns = 0
        self._session_managed = False
        self._real_pilot = False
        self._tabletop = False
        self._session_lease_until = 0.0
        self.last_disarm_reason = {
            "user_stop": "Stopped by user",
            "disarm": "Stopped by user",
            "camera_stopped": "Camera stopped",
            "tracking_lost": "Tracking was lost or became uncertain",
            "camera_loss": "Fresh tracking did not arrive before the safety deadline",
            "device_lost": "Selected device disconnected",
            "session_expired": "Control heartbeat expired",
        }.get(reason, reason.replace("_", " ").capitalize())
        await self._safety.stop(reason)
        if self._safety.last_error is not None:
            self.state = HandResponseState.ERROR
            self.last_error = self._safety.last_error
            self.last_disarm_reason = self._safety.last_error

    def heartbeat(self) -> None:
        if (not self._session_managed or
                self.state not in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                   HandResponseState.COOLDOWN}):
            raise RuntimeError("No armed session needs a heartbeat")
        if time.monotonic() > self._session_lease_until:
            raise RuntimeError("Session heartbeat expired; disarm and arm explicitly")
        self._session_lease_until = time.monotonic() + 1.5

    async def pause(self) -> None:
        if self.state not in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                              HandResponseState.COOLDOWN}:
            raise RuntimeError("Arm the hand session before pausing")
        await self.disarm()
        if self.state == HandResponseState.DISARMED:
            self.state = HandResponseState.PAUSED

    async def emergency_stop(self) -> None:
        self._epoch += 1
        self.state = HandResponseState.EMERGENCY_STOP
        self._selected_id = None
        self._active_stroke_id = None
        self._active_frame_id = None
        self._active_command_acknowledged = False
        self._started_ids.clear()
        self._tracking_ns = 0
        self._session_managed = False
        self._real_pilot = False
        self._tabletop = False
        self._session_lease_until = 0.0
        self.last_disarm_reason = "Emergency Stop pressed"
        await self._safety.emergency_stop()
        if self._safety.last_error is not None:
            self.last_error = self._safety.last_error
            self.last_disarm_reason = f"Stop could not be confirmed: {self._safety.last_error}"

    async def fail(self, reason: str) -> None:
        if self.state == HandResponseState.EMERGENCY_STOP:
            return
        self._epoch += 1
        self.state = HandResponseState.ERROR
        self.last_error = reason
        self.last_disarm_reason = reason
        self._selected_id = None
        self._active_stroke_id = None
        self._active_frame_id = None
        self._active_command_acknowledged = False
        self._started_ids.clear()
        self._tracking_ns = 0
        self._session_managed = False
        self._real_pilot = False
        self._tabletop = False
        self._session_lease_until = 0.0
        await self._safety.stop("error")

    def device_lost(self, identifier: str | None = None) -> None:
        if self.state not in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                              HandResponseState.COOLDOWN}:
            return
        if identifier is not None and identifier != self._selected_id:
            return
        if identifier is None:
            selected = self._devices.get(self._selected_id) if self._selected_id else None
            if selected is not None and selected.info.simulated:
                return  # An unrelated Intiface disconnect cannot remove a simulator.
        self._epoch += 1
        self.state = HandResponseState.ERROR
        self.last_error = "Selected device disconnected"
        self.last_disarm_reason = self.last_error
        self._selected_id = None
        self._active_stroke_id = None
        self._active_frame_id = None
        self._active_command_acknowledged = False
        self._started_ids.clear()
        self._tracking_ns = 0
        self._session_managed = False
        self._real_pilot = False
        self._tabletop = False
        self._session_lease_until = 0.0
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._safety.stop("device_lost")))

    def _authorized(self, identifier: str, epoch: int) -> bool:
        device = self._devices.get(identifier)
        tracking_gap = self.TABLETOP_TRACKING_GAP_NS if self._tabletop else self.TRACKING_GAP_NS
        return (self._epoch == epoch
                and self.state in {HandResponseState.ARMED, HandResponseState.ACTIVE}
                and self._selected_id == identifier
                and self._devices.selected_id == identifier
                and device is not None
                and (device.info.simulated or (self._real_pilot and self._intiface_connected()
                                                and self._safety.real_device_output_enabled))
                and "vibrate" in {value.lower() for value in device.info.capabilities}
                and self.rule.feature_index in getattr(device, "vibration_features", ())
                and self._camera_running()
                and (not self._session_managed or time.monotonic() <= self._session_lease_until)
                and time.monotonic_ns() - self._tracking_ns <= tracking_gap)

    async def handle_event(self, event: Event) -> None:
        if event.topic == "camera_stopped" or event.topic == "stroke_tracking_lost":
            if self.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                              HandResponseState.COOLDOWN}:
                await self.disarm("camera_stopped" if event.topic == "camera_stopped"
                                  else "tracking_lost")
            return
        if event.topic not in {"stroke_observation", "stroke_started",
                               "stroke_updated", "stroke_completed"}:
            return
        payload = event.payload.get("stroke")
        if not isinstance(payload, dict):
            return
        now_ns = time.monotonic_ns()
        tracking_gap = self.TABLETOP_TRACKING_GAP_NS if self._tabletop else self.TRACKING_GAP_NS
        try:
            observation = (StrokeObservation(**payload) if event.topic == "stroke_observation"
                           else StrokeEvent(**payload))
        except (ValueError, TypeError):
            return
        if observation.timestamp_ns > now_ns + 50_000_000 or now_ns - observation.timestamp_ns > self.MAX_EVENT_AGE_NS:
            return
        if event.topic == "stroke_observation":
            if observation.frame_id <= self._last_frame:
                return
            self._last_frame = observation.frame_id
            tracking_state = event.payload.get("tracking_state")
            if tracking_state == "RECOVERING":
                # Keep the arm through brief detector jitter, but stop output
                # on the first uncertain frame. No stale update is authorized.
                if self.state == HandResponseState.ACTIVE:
                    await self._safety.stop("tracking_lost")
                    if self._safety.last_error is not None:
                        await self.fail(self._safety.last_error)
                        return
                    self._active_stroke_id = None
                    self._active_frame_id = None
                    self._active_command_acknowledged = False
                    self._cooldown_until = time.monotonic() + self.rule.cooldown
                    self.state = HandResponseState.COOLDOWN
                return
            if (tracking_state != "TRACKED"
                    or observation.tracking_confidence < self.rule.minimum_confidence):
                if self.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                  HandResponseState.COOLDOWN}:
                    await self.disarm("tracking_lost")
                self._tracking_ns = 0
                return
            self._tracking_ns = observation.timestamp_ns
            if (self.rule.mode == HandResponseMode.FOLLOW_MOVEMENT
                    and self.state == HandResponseState.ACTIVE
                    and observation.stroke_id == self._active_stroke_id
                    and observation.speed < 0.04):
                await self._safety.stop("unspecified")
                if self.state == HandResponseState.ACTIVE:
                    self._active_stroke_id = None
                    self._active_frame_id = None
                    self._cooldown_until = time.monotonic() + self.rule.cooldown
                    self.state = HandResponseState.COOLDOWN
            return
        if observation.stroke_id is None:
            return
        if self.state not in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                              HandResponseState.COOLDOWN}:
            return
        if observation.kind == StrokeEventKind.STARTED:
            if (observation.timestamp_ns >= self._armed_ns
                    and observation.frame_id == self._last_frame
                    and observation.tracking_confidence >= self.rule.minimum_confidence):
                self._started_ids.add(observation.stroke_id)
                if len(self._started_ids) > 32:
                    self._started_ids = set(sorted(self._started_ids)[-16:])
            return
        if observation.kind == StrokeEventKind.UPDATED:
            if self.rule.mode != HandResponseMode.FOLLOW_MOVEMENT:
                return
            async with self._lock:
                if (observation.stroke_id not in self._started_ids
                        or observation.stroke_id <= self._last_stroke_id
                        or observation.timestamp_ns < self._armed_ns
                        or observation.frame_id != self._last_frame
                        or observation.frame_id <= self._last_response_frame
                        or observation.tracking_confidence < self.rule.minimum_confidence
                        or observation.speed < 0.04 or observation.travel < 0.06
                        or now_ns - self._tracking_ns > tracking_gap):
                    return
                if self.state != HandResponseState.ARMED or self._safety.running:
                    return  # Never queue old movement samples behind an active pulse.
                await self._issue_response(observation)
            return
        if observation.kind != StrokeEventKind.COMPLETED:
            return
        async with self._lock:
            if observation.stroke_id <= self._last_stroke_id or observation.timestamp_ns < self._armed_ns:
                self.dropped_response_count += 1
                return
            self._last_stroke_id = observation.stroke_id
            self.stroke_count += 1
            if (observation.stroke_id not in self._started_ids
                    or observation.frame_id != self._last_frame
                    or observation.tracking_confidence < self.rule.minimum_confidence
                    or now_ns - self._tracking_ns > tracking_gap
                    or not self._camera_running()):
                self.dropped_response_count += 1
                return
            self._started_ids.discard(observation.stroke_id)
            if self.rule.mode == HandResponseMode.FOLLOW_MOVEMENT:
                if (self.state == HandResponseState.ACTIVE
                        and self._active_stroke_id == observation.stroke_id):
                    await self._safety.stop("unspecified")
                    if self.state == HandResponseState.ACTIVE:
                        self._active_stroke_id = None
                        self._active_frame_id = None
                        self._cooldown_until = time.monotonic() + self.rule.cooldown
                        self.state = HandResponseState.COOLDOWN
                return
            if self.state != HandResponseState.ARMED or self._safety.running:
                self.dropped_response_count += 1
                return
            await self._issue_response(observation)

    async def _issue_response(self, observation: StrokeEvent) -> None:
        """Submit one bounded envelope; caller holds the event lock."""
        identifier = self._selected_id
        if identifier is None or not self._authorized(identifier, self._epoch):
            self.dropped_response_count += 1
            return
        device = self._devices.get(identifier)
        if device is None or not (device.info.simulated or (self._real_pilot and self._intiface_connected())):
            await self.fail("Selected device disconnected")
            return
        epoch = self._epoch
        intensity = self.rule.intensity
        pattern = Pattern.SHORT_PULSE
        if self.rule.mode == HandResponseMode.FOLLOW_MOVEMENT:
            movement = min(1.0, max(0.0, observation.speed / 1.5))
            intensity *= 0.3 + 0.7 * movement
            if self.rule.style == ResponseStyle.GENTLE:
                intensity *= 0.6
            elif self.rule.style == ResponseStyle.RAMP:
                intensity *= 0.3 + 0.7 * min(1.0, observation.travel)
        else:
            pattern = {
                ResponseStyle.GENTLE: Pattern.GENTLE_PULSE,
                ResponseStyle.CRISP: Pattern.SHORT_PULSE,
                ResponseStyle.RAMP: Pattern.GRADUAL_RAMP,
            }[self.rule.style]
            if self.rule.mode == HandResponseMode.MOTION_SHAPED:
                shape = min(1.0, max(0.4, 0.4 + observation.speed * 0.3 + observation.travel * 0.2))
                intensity *= shape
        self._active_command_acknowledged = False
        self._last_response_frame = observation.frame_id
        self._active_stroke_id = observation.stroke_id
        self._active_frame_id = observation.frame_id
        try:
            await self._safety.start_automation_pattern(
                self.rule.feature_index, pattern, intensity,
                self.rule.duration, lambda: self._authorized(identifier, epoch),
                trace_id=observation.frame_id,
                command_ack=lambda ack_ns: self._note_ack(observation.stroke_id,
                                                           observation.timestamp_ns, ack_ns, epoch),
            )
        except Exception as exc:
            if self._epoch == epoch:
                await self.fail(str(exc) or type(exc).__name__)
            return
        if not self._authorized(identifier, epoch):
            await self._safety.stop("error")
            return
        self.submitted_response_count += 1
        self._active_until = time.monotonic() + self.rule.duration
        self.state = HandResponseState.ACTIVE

    def _note_ack(self, stroke_id: int, event_ns: int, ack_ns: int, epoch: int) -> None:
        if self._epoch == epoch and self._active_stroke_id == stroke_id and ack_ns >= event_ns:
            self._active_command_acknowledged = True
            self._latencies_ms.append((ack_ns - event_ns) / 1_000_000)

    async def _watchdog(self) -> None:
        while self.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                             HandResponseState.COOLDOWN}:
            await asyncio.sleep(0.025)
            if self.state not in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                  HandResponseState.COOLDOWN}:
                break
            if self._session_managed and time.monotonic() > self._session_lease_until:
                await self.disarm("session_expired")
                if self._on_session_expired is not None:
                    result = self._on_session_expired()
                    if asyncio.iscoroutine(result):
                        await result
                continue
            tracking_gap = self.TABLETOP_TRACKING_GAP_NS if self._tabletop else self.TRACKING_GAP_NS
            if not self._camera_running() or time.monotonic_ns() - self._tracking_ns > tracking_gap:
                await self.disarm("camera_loss")
                continue
            selected = self._devices.get(self._selected_id) if self._selected_id else None
            if (self._devices.selected_id != self._selected_id or selected is None
                    or not (selected.info.simulated or (self._real_pilot and self._intiface_connected()))
                    or self.rule.feature_index not in getattr(selected, "vibration_features", ())):
                await self.fail("Selected device disconnected")
                continue
            if self._safety.last_error is not None:
                await self.fail(self._safety.last_error)
                continue
            now = time.monotonic()
            if self.state == HandResponseState.ACTIVE and (now >= self._active_until or not self._safety.running):
                await self._safety.stop("deadline" if now >= self._active_until else "unspecified")
                if self.state == HandResponseState.ACTIVE:
                    if self._active_command_acknowledged and self._safety.last_error is None:
                        self.completed_response_count += 1
                    else:
                        await self.fail(self._safety.last_error or "Response ended before command acknowledgement")
                        continue
                    self._active_stroke_id = None
                    self._active_frame_id = None
                    self._active_command_acknowledged = False
                    self._cooldown_until = time.monotonic() + self.rule.cooldown
                    self.state = HandResponseState.COOLDOWN
            elif self.state == HandResponseState.COOLDOWN and now >= self._cooldown_until:
                self.state = HandResponseState.ARMED

    async def shutdown(self) -> None:
        await self.emergency_stop()
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
