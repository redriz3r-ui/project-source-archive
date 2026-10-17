"""One-shot manual control, command limits, watchdog, and emergency stop."""

import asyncio
import math
import time
from collections.abc import Callable

from app.config import Settings
from app.diagnostics import LatencyRecorder, TraceStage
from app.devices.models import ControllableDevice
from app.devices.registry import DeviceRegistry
from app.triggers.patterns import Pattern, PatternStep, build_pattern


class SafetyController:
    def __init__(self, devices: DeviceRegistry, settings: Settings = Settings(),
                 latency: LatencyRecorder | None = None) -> None:
        self._devices = devices
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._manual_deadline_task: asyncio.Task[None] | None = None
        self._automation_deadline_task: asyncio.Task[None] | None = None
        self._active_device: ControllableDevice | None = None
        self._lock = asyncio.Lock()
        self._stop_lock = asyncio.Lock()
        self._stopping = False
        self._real_output_fault_latched = False
        self.activation_enabled = False
        self.emergency_stop_latched = False
        self.last_error: str | None = None
        self._generation = 0
        self.evaluation_mode = False
        self._latency = latency

    def enter_evaluation_mode(self) -> None:
        if self.evaluation_mode:
            raise RuntimeError("Evaluation is already active")
        if self.running or self.activation_enabled or self._stopping:
            raise RuntimeError("Stop and disable device control before evaluation")
        self.evaluation_mode = True

    def exit_evaluation_mode(self) -> None:
        self.evaluation_mode = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def max_intensity(self) -> float:
        return self._settings.max_intensity

    @property
    def max_duration_seconds(self) -> float:
        return self._settings.max_duration_seconds

    @property
    def real_device_output_enabled(self) -> bool:
        return self._settings.real_device_output_enabled and not self._real_output_fault_latched

    @property
    def real_device_manual_bench_enabled(self) -> bool:
        return self._settings.real_device_manual_bench_enabled and not self._real_output_fault_latched

    def _record_output_fault(self, device: ControllableDevice, message: str) -> None:
        self.last_error = message
        if not device.info.simulated:
            self._real_output_fault_latched = True

    def _require_real_output_allowed(self, device: ControllableDevice,
                                     *, automation: bool = False) -> None:
        allowed = (self.real_device_output_enabled or
                   (self.real_device_manual_bench_enabled and not automation))
        if not device.info.simulated and not allowed:
            raise RuntimeError("Real-device output is locked after a failed physical stop; use the simulator")

    def enable_activation(self, *, off_body_confirmed: bool = False) -> None:
        if self.evaluation_mode:
            raise RuntimeError("Device activation is disabled during evaluation")
        if self._stopping:
            raise RuntimeError("Stop is still in progress")
        if self.running:
            raise RuntimeError("A test is already running")
        selected = self._devices.get(self._devices.selected_id) if self._devices.selected_id else None
        if selected is None:
            raise RuntimeError("Select a device before enabling a test")
        self._require_real_output_allowed(selected)
        if (not selected.info.simulated and self.real_device_manual_bench_enabled
                and not self.real_device_output_enabled and not off_body_confirmed):
            raise RuntimeError("Confirm the device is off-body before enabling a bench test")
        if not any(capability.lower() == "vibrate" for capability in selected.info.capabilities):
            raise RuntimeError("Selected device has no vibration output")
        self.emergency_stop_latched = False
        self.activation_enabled = True
        self.last_error = None

    async def start_test(self, intensity: float = 0.2, duration: float = 1.0,
                         feature_index: int | None = None,
                         *, off_body_confirmed: bool = False) -> None:
        if not math.isfinite(intensity) or not 0 < intensity <= self._settings.max_intensity:
            raise ValueError(f"Intensity must be above 0 and at most {self._settings.max_intensity:.0%}")
        if not math.isfinite(duration) or not 0 < duration <= self._settings.max_duration_seconds:
            raise ValueError(f"Duration must be above 0 and at most {self._settings.max_duration_seconds:g} seconds")
        async with self._lock:
            if self.evaluation_mode:
                raise RuntimeError("Device activation is disabled during evaluation")
            if self.running:
                raise RuntimeError("A test is already running")
            if self._stopping:
                raise RuntimeError("Stop is still in progress")
            if self.emergency_stop_latched or not self.activation_enabled:
                raise RuntimeError("Enable one test before starting it")
            identifier = self._devices.selected_id
            device = self._devices.get(identifier) if identifier else None
            if device is None:
                raise RuntimeError("Selected device is disconnected")
            self._require_real_output_allowed(device)
            if (not device.info.simulated and self.real_device_manual_bench_enabled
                    and not self.real_device_output_enabled and not off_body_confirmed):
                raise RuntimeError("Confirm the device is off-body before starting a bench test")
            if not any(capability.lower() == "vibrate" for capability in device.info.capabilities):
                raise ValueError("Selected device has no vibration output")
            features = tuple(getattr(device, "vibration_features", ()))
            if feature_index is None and len(features) == 1:
                feature_index = features[0]
            elif feature_index is None and len(features) > 1:
                raise ValueError("Select one vibration feature before testing")
            if feature_index is not None and feature_index not in features:
                raise ValueError("Selected vibration feature is unavailable")
            self.activation_enabled = False  # Each test consumes one deliberate enable action.
            self._active_device = device
            self.last_error = None
            if self._manual_deadline_task is not None:
                self._manual_deadline_task.cancel()
            self._generation += 1
            generation = self._generation
            deadline = time.monotonic() + duration
            self._task = asyncio.create_task(self._run_test(
                device, intensity, deadline, feature_index))
            self._manual_deadline_task = asyncio.create_task(
                self._enforce_manual_deadline(deadline, generation))

    async def _enforce_manual_deadline(self, deadline: float, generation: int) -> None:
        """Attempt a stop even when the manual command task is delayed."""
        try:
            await asyncio.sleep(max(0.0, deadline - time.monotonic()))
            if generation == self._generation and self.running:
                await self.stop("deadline")
        except asyncio.CancelledError:
            raise

    async def start_automation_pattern(
        self, feature_index: int, pattern: Pattern | str, intensity: float,
        duration: float, authorized: Callable[[], bool],
        trace_id: int | None = None,
        command_ack: Callable[[int], None] | None = None,
    ) -> None:
        steps = build_pattern(pattern, intensity, duration, self._settings.max_intensity)
        if not math.isfinite(intensity) or not 0 < intensity <= self._settings.max_intensity:
            raise ValueError("Automation intensity exceeds the safety limit")
        if not math.isfinite(duration) or not 0 < duration <= min(2.0, self._settings.max_duration_seconds):
            raise ValueError("Automation duration exceeds the safety limit")
        async with self._lock:
            if self.evaluation_mode:
                raise RuntimeError("Device activation is disabled during evaluation")
            if not authorized():
                raise RuntimeError("Automation is no longer armed")
            if self.running or self._stopping or self.activation_enabled or self.emergency_stop_latched:
                raise RuntimeError("Device control is already occupied or disarmed")
            device = self._devices.get(self._devices.selected_id) if self._devices.selected_id else None
            if device is None or feature_index not in getattr(device, "vibration_features", ()):
                raise RuntimeError("Selected vibration feature is unavailable")
            self._require_real_output_allowed(device, automation=True)
            if self._manual_deadline_task is not None:
                self._manual_deadline_task.cancel()
                self._manual_deadline_task = None
            self._generation += 1
            self._active_device = device
            self.last_error = None
            generation = self._generation
            deadline = time.monotonic() + duration
            self._task = asyncio.create_task(self._run_pattern(
                device, feature_index, steps, deadline, generation, authorized, trace_id,
                command_ack,
            ))
            if self._automation_deadline_task is not None:
                self._automation_deadline_task.cancel()
            self._automation_deadline_task = asyncio.create_task(
                self._enforce_automation_deadline(deadline, generation))

    async def _enforce_automation_deadline(self, deadline: float, generation: int) -> None:
        """Independent lease expiry for camera-driven output commands."""
        try:
            await asyncio.sleep(max(0.0, deadline - time.monotonic()))
            if generation == self._generation and self.running:
                await self.stop("deadline")
        except asyncio.CancelledError:
            raise

    async def _run_pattern(self, device: ControllableDevice, feature_index: int,
                           steps: tuple[PatternStep, ...], deadline: float,
                           generation: int, authorized: Callable[[], bool],
                           trace_id: int | None,
                           command_ack: Callable[[int], None] | None) -> None:
        first_positive = True
        try:
            for step in steps:
                if generation != self._generation or not authorized():
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if step.intensity == 0:
                    command = device.stop()
                    timeout = min(self._settings.stop_timeout_seconds, remaining)
                else:
                    command = device.vibrate_feature(feature_index, step.intensity)
                    timeout = min(self._settings.command_timeout_seconds, remaining)
                first_command = first_positive and step.intensity > 0
                timed = bool(first_command and
                             trace_id is not None and self._latency is not None)
                if timed:
                    self._latency.mark(trace_id, TraceStage.COMMAND_SUBMITTED)
                try:
                    await asyncio.wait_for(command, timeout=timeout)
                except BaseException:
                    if timed:
                        self._latency.mark(trace_id, TraceStage.COMMAND_FAILED)
                    raise
                if timed:
                    self._latency.mark(trace_id, TraceStage.COMMAND_COMPLETED)
                if first_command:
                    first_positive = False
                    if command_ack is not None:
                        command_ack(time.monotonic_ns())
                if generation != self._generation or not authorized():
                    break
                # Leave a tiny scheduling margin for the normal trailing stop.
                # The independent deadline still stops a delayed command.
                await asyncio.sleep(min(step.duration, max(0.0, deadline - time.monotonic() - 0.005)))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._record_output_fault(device, str(exc) or type(exc).__name__)
        finally:
            try:
                await asyncio.wait_for(device.stop(), timeout=self._settings.stop_timeout_seconds)
            except Exception as exc:
                self._record_output_fault(device, f"Device stop failed: {exc}")
            self._active_device = None

    async def _run_test(self, device: ControllableDevice, intensity: float, deadline: float,
                        feature_index: int | None = None) -> None:
        try:
            command = (device.vibrate(intensity) if feature_index is None else
                       device.vibrate_feature(feature_index, intensity))
            await asyncio.wait_for(command, timeout=self._settings.command_timeout_seconds)
            await asyncio.sleep(max(0.0, deadline - time.monotonic()))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._record_output_fault(device, str(exc) or type(exc).__name__)
        finally:
            try:
                await asyncio.wait_for(device.stop(), timeout=self._settings.stop_timeout_seconds)
            except Exception as exc:
                self._record_output_fault(device, f"Device stop failed: {exc}")
            self._active_device = None

    async def _stop_active(self) -> None:
        task = self._task
        if task and not task.done():
            task.cancel()
        # Issue stop without waiting for an in-flight command to finish.
        device = self._active_device
        if device is not None:
            try:
                await asyncio.wait_for(device.stop(), timeout=self._settings.stop_timeout_seconds)
            except Exception as exc:
                self._record_output_fault(device, f"Device stop failed: {exc}")
        if task:
            try:
                await asyncio.wait_for(task, timeout=self._settings.stop_timeout_seconds)
            except (asyncio.CancelledError, TimeoutError):
                pass

    async def stop(self, reason: str = "unspecified") -> None:
        async with self._stop_lock:
            stop_trace = self._latency.begin_stop(reason) if self._latency is not None else None
            self._generation += 1
            self.activation_enabled = False
            self._stopping = True
            deadline_task = self._manual_deadline_task
            self._manual_deadline_task = None
            if deadline_task is not None and deadline_task is not asyncio.current_task():
                deadline_task.cancel()
            automation_deadline = self._automation_deadline_task
            self._automation_deadline_task = None
            if automation_deadline is not None and automation_deadline is not asyncio.current_task():
                automation_deadline.cancel()
            try:
                await self._stop_active()
                try:
                    await asyncio.wait_for(self._devices.stop_all(), timeout=self._settings.stop_timeout_seconds)
                except Exception as exc:
                    self.last_error = f"Device stop failed: {exc}"
                    if any(not device.simulated for device in self._devices.list()):
                        self._real_output_fault_latched = True
            finally:
                self._stopping = False
                if self._latency is not None:
                    self._latency.complete_stop(stop_trace)

    async def emergency_stop(self, reason: str = "emergency_stop") -> None:
        self.activation_enabled = False
        self.emergency_stop_latched = True
        await self.stop(reason)

    def device_lost(self, identifier: str | None = None) -> None:
        if identifier is None or identifier == self._devices.selected_id:
            self.activation_enabled = False
            self.last_error = "Selected device or Intiface disconnected"
            if self._task and not self._task.done():
                self._task.get_loop().call_soon_threadsafe(self._task.cancel)

    async def shutdown(self) -> None:
        await self.emergency_stop("shutdown")
