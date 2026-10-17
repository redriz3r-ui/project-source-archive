import asyncio
from types import SimpleNamespace

import pytest
from buttplug import OutputType
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.devices import DeviceRegistry, SimulatedDevice
from app.devices.models import DeviceStatus
from app.devices.buttplug_client import IntifaceGateway, RealDevice
from app.safety import SafetyController


class FakeButtplugDevice:
    def __init__(self, outputs=("Vibrate",)) -> None:
        self.index = 7
        self.name = "Test Stimulator"
        self.features = {0: SimpleNamespace(outputs={output: object() for output in outputs})}
        self.outputs = outputs
        self.commands = []
        self.stop_count = 0

    def has_output(self, output_type) -> bool:
        return output_type.value in self.outputs

    async def run_output(self, command) -> None:
        self.commands.append(command)

    async def stop(self) -> None:
        self.stop_count += 1


class FakeButtplugClient:
    def __init__(self, name: str, device: FakeButtplugDevice | None = None) -> None:
        self.name = name
        self.connected = False
        self.devices = {device.index: device} if device else {}
        self.on_device_added = None
        self.on_device_removed = None
        self.on_server_disconnect = None

    async def connect(self, url: str) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def start_scanning(self) -> None:
        pass

    async def stop_scanning(self) -> None:
        pass


def test_stop_all_attempts_other_devices_when_one_stop_stalls() -> None:
    class SlowDevice(SimulatedDevice):
        async def stop(self) -> None:
            await asyncio.sleep(0.2)

    async def scenario() -> None:
        registry = DeviceRegistry()
        registry.add(SlowDevice("simulator-slow"))
        fast = SimulatedDevice("simulator-fast")
        registry.add(fast)
        task = asyncio.create_task(registry.stop_all())
        await asyncio.sleep(0.02)
        assert fast.stop_count == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_gateway_discovers_real_device_and_reports_actual_outputs() -> None:
    device = FakeButtplugDevice(("Rotate",))
    client = FakeButtplugClient("SelfPleasure", device)
    registry = DeviceRegistry()
    gateway = IntifaceGateway("ws://127.0.0.1:12345", registry, lambda _: client)

    async def scenario() -> None:
        await gateway.connect()
        info = registry.list()[0]
        assert info.name == "Test Stimulator"
        assert info.capabilities == ("Rotate",)
        with pytest.raises(ValueError, match="no vibration"):
            await registry.get(info.identifier).vibrate(0.2)
        registry.select(info.identifier)
        with pytest.raises(RuntimeError, match="no vibration"):
            SafetyController(registry, Settings(real_device_output_enabled=True)).enable_activation()
        assert device.commands == []
        await gateway.shutdown()

    asyncio.run(scenario())


def test_automation_commands_only_explicit_vibration_feature() -> None:
    class Feature:
        outputs = {"Vibrate": object()}

        def __init__(self):
            self.commands = []

        def has_output(self, output_type):
            return output_type is OutputType.VIBRATE

        async def run_output(self, command):
            self.commands.append(command)

    async def scenario():
        native = FakeButtplugDevice()
        native.features = {0: Feature(), 1: Feature()}
        device = RealDevice(native)
        assert device.vibration_features == (0, 1)
        await device.vibrate_feature(1, 0.2)
        assert native.features[0].commands == []
        assert len(native.features[1].commands) == 1
        assert native.features[1].commands[0].value == 0.2
        await device.stop()
        registry = DeviceRegistry()
        registry.add(device)
        registry.select(device.info.identifier)
        safety = SafetyController(registry, Settings(real_device_output_enabled=True))
        safety.enable_activation()
        with pytest.raises(ValueError, match="Select one vibration feature"):
            await safety.start_test(0.2, 0.01)
        await safety.start_test(0.2, 0.01, feature_index=1)
        await asyncio.sleep(0.05)
        assert native.features[0].commands == []
        assert len(native.features[1].commands) == 2

    asyncio.run(scenario())


def test_real_stop_attempts_device_and_vibration_feature_independently() -> None:
    class Feature:
        outputs = {"Vibrate": object()}

        def __init__(self) -> None:
            self.stops = 0

        def has_output(self, output) -> bool:
            return output is OutputType.VIBRATE

        async def stop(self) -> None:
            self.stops += 1

    class Native(FakeButtplugDevice):
        async def stop(self) -> None:
            self.stop_count += 1
            raise ConnectionError("Injected device-level stop failure")

    async def scenario() -> None:
        native = Native()
        feature = Feature()
        native.features = {2: feature}
        wrapped = RealDevice(native)
        with pytest.raises(RuntimeError, match="stop commands failed"):
            await wrapped.stop()
        assert native.stop_count == 1
        assert feature.stops == 1
        assert wrapped.info.status == DeviceStatus.STOP_UNCONFIRMED

    asyncio.run(scenario())


def test_real_stop_still_attempts_device_scope_if_feature_inspection_fails() -> None:
    class BrokenFeature:
        outputs = {"Vibrate": object()}

        def has_output(self, output) -> bool:
            raise RuntimeError("Injected feature inspection failure")

    async def scenario() -> None:
        native = FakeButtplugDevice()
        native.features = {2: BrokenFeature()}
        wrapped = RealDevice(native)
        with pytest.raises(RuntimeError, match="stop commands failed"):
            await wrapped.stop()
        assert native.stop_count == 1
        assert wrapped.info.status == DeviceStatus.STOP_UNCONFIRMED

    asyncio.run(scenario())


def test_short_manual_test_reports_stop_failure_without_claiming_idle() -> None:
    class Feature:
        outputs = {"Vibrate": object()}

        def __init__(self) -> None:
            self.stops = 0

        def has_output(self, output) -> bool:
            return output is OutputType.VIBRATE

        async def run_output(self, command) -> None:
            assert command.value == 0.2

        async def stop(self) -> None:
            self.stops += 1

    class Native(FakeButtplugDevice):
        async def stop(self) -> None:
            self.stop_count += 1
            raise ConnectionError("Injected stop failure")

    async def scenario() -> None:
        native = Native()
        feature = Feature()
        native.features = {2: feature}
        registry = DeviceRegistry()
        wrapped = RealDevice(native)
        registry.add(wrapped)
        registry.select(wrapped.info.identifier)
        safety = SafetyController(registry, Settings(real_device_output_enabled=True))
        safety.enable_activation()
        await safety.start_test(0.2, 0.1, feature_index=2)
        await asyncio.sleep(0.15)
        assert native.stop_count >= 1
        assert feature.stops >= 1
        assert wrapped.info.status == DeviceStatus.STOP_UNCONFIRMED
        assert "stop failed" in (safety.last_error or "").lower()

    asyncio.run(scenario())


def test_default_safety_lockout_blocks_real_manual_and_pattern_output() -> None:
    async def scenario() -> None:
        native = FakeButtplugDevice()
        native.features = {0: SimpleNamespace(
            outputs={"Vibrate": object()},
            has_output=lambda output: output is OutputType.VIBRATE,
            run_output=lambda command: (_ for _ in ()).throw(
                AssertionError("Real output must remain locked")),
        )}
        registry = DeviceRegistry()
        registry.add(RealDevice(native))
        registry.select("intiface-7")
        safety = SafetyController(registry)
        with pytest.raises(RuntimeError, match="locked"):
            safety.enable_activation()
        with pytest.raises(RuntimeError, match="locked"):
            await safety.start_automation_pattern(0, "SHORT_PULSE", 0.2, 0.1,
                                                  lambda: True)
        assert native.commands == []

    asyncio.run(scenario())


def test_off_body_bench_unlocks_only_bounded_manual_output() -> None:
    class Feature:
        outputs = {"Vibrate": object()}

        def __init__(self) -> None:
            self.commands = []
            self.stops = 0

        def has_output(self, output_type) -> bool:
            return output_type is OutputType.VIBRATE

        async def run_output(self, command) -> None:
            self.commands.append(command)

        async def stop(self) -> None:
            self.stops += 1

    async def scenario() -> None:
        native = FakeButtplugDevice()
        feature = Feature()
        native.features = {2: feature}
        registry = DeviceRegistry()
        device = RealDevice(native)
        registry.add(device)
        registry.select(device.info.identifier)
        safety = SafetyController(registry, Settings(
            real_device_manual_bench_enabled=True,
            max_intensity=0.2, max_duration_seconds=0.5))
        with pytest.raises(RuntimeError, match="off-body"):
            safety.enable_activation()
        safety.enable_activation(off_body_confirmed=True)
        with pytest.raises(RuntimeError, match="off-body"):
            await safety.start_test(0.2, 0.05, feature_index=2)
        with pytest.raises(ValueError, match="Intensity"):
            await safety.start_test(0.21, 0.05, feature_index=2,
                                    off_body_confirmed=True)
        with pytest.raises(ValueError, match="Duration"):
            await safety.start_test(0.2, 0.51, feature_index=2,
                                    off_body_confirmed=True)
        await safety.start_test(0.2, 0.05, feature_index=2,
                                off_body_confirmed=True)
        await asyncio.sleep(0.09)
        assert [command.value for command in feature.commands] == [0.2]
        assert native.stop_count >= 1
        assert feature.stops >= 1
        with pytest.raises(RuntimeError, match="locked"):
            await safety.start_automation_pattern(2, "SHORT_PULSE", 0.2, 0.1,
                                                  lambda: True)

    asyncio.run(scenario())


def test_bench_api_requires_confirmation_and_preserves_automation_lock() -> None:
    class Feature:
        outputs = {"Vibrate": object()}

        def has_output(self, output_type) -> bool:
            return output_type is OutputType.VIBRATE

        async def run_output(self, command) -> None:
            pass

        async def stop(self) -> None:
            pass

    bench_settings = Settings(real_device_manual_bench_enabled=True,
                              max_intensity=0.2, max_duration_seconds=0.5)
    with TestClient(create_app(bench_settings), base_url="http://127.0.0.1:8000") as web:
        native = FakeButtplugDevice()
        native.features = {2: Feature()}
        web.app.state.services.devices.add(RealDevice(native))
        assert web.post("/api/devices/select", json={"device_id": "intiface-7"}).status_code == 200
        status = web.get("/api/status").json()
        assert status["real_device_output_enabled"] is False
        assert status["real_device_manual_bench_enabled"] is True
        assert web.post("/api/control/enable").status_code == 409
        assert web.post("/api/control/enable", json={"off_body_confirmed": True}).status_code == 200
        test = {"intensity": 0.2, "duration": 0.5, "feature_index": 2}
        assert web.post("/api/control/test", json=test).status_code == 409
        assert web.post("/api/control/test", json={**test, "duration": 0.6,
                                                   "off_body_confirmed": True}).status_code == 422
        assert web.post("/api/control/test", json={**test,
                                                   "off_body_confirmed": True}).status_code == 202
        assert web.post("/api/emergency-stop").status_code == 200


def test_manual_test_stops_after_duration_and_consumes_enable() -> None:
    async def scenario() -> None:
        registry = DeviceRegistry()
        simulated = SimulatedDevice()
        registry.add(simulated)
        registry.select(simulated.identifier)
        safety = SafetyController(registry, Settings())
        safety.enable_activation()
        await safety.start_test(0.2, 0.01)
        assert safety.activation_enabled is False
        await asyncio.sleep(0.05)
        assert simulated.last_intensity == 0.0
        assert simulated.stop_count >= 1
        with pytest.raises(RuntimeError, match="Enable one test"):
            await safety.start_test(0.2, 0.01)

    asyncio.run(scenario())


def test_command_timeout_attempts_stop() -> None:
    class HangingDevice(SimulatedDevice):
        async def vibrate(self, intensity: float) -> None:
            await asyncio.sleep(1)

    async def scenario() -> None:
        registry = DeviceRegistry()
        device = HangingDevice()
        registry.add(device)
        registry.select(device.identifier)
        safety = SafetyController(registry, Settings(command_timeout_seconds=0.01))
        safety.enable_activation()
        await safety.start_test(0.2, 0.1)
        await asyncio.sleep(0.05)
        assert device.stop_count >= 1
        assert safety.last_error is not None

    asyncio.run(scenario())


def test_manual_deadline_includes_command_delay() -> None:
    class DelayedDevice(SimulatedDevice):
        async def vibrate(self, intensity: float) -> None:
            await asyncio.sleep(0.10)
            await super().vibrate(intensity)

    async def scenario() -> None:
        registry = DeviceRegistry()
        device = DelayedDevice()
        registry.add(device)
        registry.select(device.identifier)
        safety = SafetyController(registry, Settings(command_timeout_seconds=0.5))
        safety.enable_activation()
        await safety.start_test(0.2, 0.18)
        await asyncio.sleep(0.23)
        assert not safety.running
        assert device.last_intensity == 0
        assert device.stop_count >= 1

    asyncio.run(scenario())


def test_manual_deadline_stops_a_stalled_output_command() -> None:
    class StalledDevice(SimulatedDevice):
        async def vibrate(self, intensity: float) -> None:
            await asyncio.sleep(1)
            await super().vibrate(intensity)

    async def scenario() -> None:
        registry = DeviceRegistry()
        device = StalledDevice()
        registry.add(device)
        registry.select(device.identifier)
        safety = SafetyController(registry, Settings(command_timeout_seconds=1.5))
        safety.enable_activation()
        await safety.start_test(0.2, 0.05)
        await asyncio.sleep(0.12)
        assert not safety.running
        assert device.last_intensity == 0
        assert device.stop_count >= 1

    asyncio.run(scenario())


def test_prior_manual_deadline_cannot_stop_a_later_test() -> None:
    class FirstCommandFails(SimulatedDevice):
        attempts = 0

        async def vibrate(self, intensity: float) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError("Injected first-command failure")
            await super().vibrate(intensity)

    async def scenario() -> None:
        registry = DeviceRegistry()
        device = FirstCommandFails()
        registry.add(device)
        registry.select(device.identifier)
        safety = SafetyController(registry)
        safety.enable_activation()
        await safety.start_test(0.2, 0.15)
        await asyncio.sleep(0.02)
        assert not safety.running
        safety.enable_activation()
        await safety.start_test(0.2, 0.25)
        await asyncio.sleep(0.16)
        assert safety.running
        assert device.last_intensity == 0.2
        await safety.emergency_stop()
        assert device.last_intensity == 0

    asyncio.run(scenario())


def test_cancelled_test_and_emergency_stop() -> None:
    async def scenario() -> None:
        registry = DeviceRegistry()
        device = SimulatedDevice()
        registry.add(device)
        registry.select(device.identifier)
        safety = SafetyController(registry)
        safety.enable_activation()
        await safety.start_test(0.2, 3)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="already running"):
            safety.enable_activation()
        await safety.emergency_stop()
        assert not safety.running
        assert device.last_intensity == 0
        assert safety.emergency_stop_latched
        with pytest.raises(RuntimeError, match="Enable one test"):
            await safety.start_test()

    asyncio.run(scenario())


def test_device_disconnect_cancels_test_and_clears_selection() -> None:
    async def scenario() -> None:
        device = FakeButtplugDevice()
        client = FakeButtplugClient("SelfPleasure", device)
        registry = DeviceRegistry()
        safety = SafetyController(registry, Settings(real_device_output_enabled=True))
        gateway = IntifaceGateway(
            "ws://127.0.0.1:12345", registry, lambda _: client,
            on_disconnect=safety.device_lost,
            on_device_removed=safety.device_lost,
        )
        await gateway.connect()
        registry.select("intiface-7")
        safety.enable_activation()
        await safety.start_test(0.2, 3)
        await asyncio.sleep(0)
        client.on_server_disconnect()
        await asyncio.sleep(0.01)
        assert not gateway.state.connected
        assert registry.selected_id is None
        assert not safety.activation_enabled
        assert not safety.running
        await gateway.shutdown()

    asyncio.run(scenario())


def test_api_manual_control_with_injected_client() -> None:
    device = FakeButtplugDevice()
    client = FakeButtplugClient("SelfPleasure", device)
    with TestClient(
        create_app(Settings(real_device_output_enabled=True), client_factory=lambda _: client),
        base_url="http://127.0.0.1:8000",
    ) as web:
        assert web.post("/api/intiface/connect").status_code == 200
        listed = web.get("/api/devices").json()
        assert listed[0]["can_vibrate"] is True
        assert web.post("/api/devices/select", json={"device_id": "intiface-7"}).status_code == 200
        assert web.post("/api/control/test", json={"intensity": 0.2, "duration": 1}).status_code == 409
        assert web.post("/api/control/enable").status_code == 200
        assert web.post("/api/control/test", json={"intensity": 0.8, "duration": 1}).status_code == 422
        assert web.post("/api/control/test", json={"intensity": 0.2, "duration": 6}).status_code == 422
        assert web.post("/api/control/test", json={"intensity": 0.2, "duration": 1}).status_code == 202
        assert web.post("/api/emergency-stop").status_code == 200
        assert web.get("/devices").status_code == 200
    assert all(command.output_type is OutputType.VIBRATE for command in device.commands)
    assert device.stop_count >= 1
