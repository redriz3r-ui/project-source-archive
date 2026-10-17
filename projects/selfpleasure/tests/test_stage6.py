from pathlib import Path
import stat

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.triggers.store import RuleStore


def rule_data(name="Short pulse", feature=0):
    return {
        "name": name, "trigger": "INTERACTION_ACTIVE", "action": "VIBRATE",
        "pattern": "SHORT_PULSE", "feature_index": feature,
        "intensity": 0.2, "duration": 2.0, "cooldown": 1.0,
        "minimum_confidence": 0.6,
    }


def test_local_rule_crud_and_single_enabled_rule(tmp_path: Path):
    path = tmp_path / "config.local.rules.json"
    with TestClient(create_app(Settings(), rules=RuleStore(path)), base_url="http://127.0.0.1:8000") as web:
        assert web.get("/rules").status_code == 200
        assert web.get("/api/rules").json() == []
        dashboard = web.get("/api/dashboard").json()
        assert dashboard["automation"]["state"] == "DISARMED"
        assert dashboard["camera"]["status"] == "inactive"
        first = web.post("/api/rules", json=rule_data()).json()
        second = web.post("/api/rules", json=rule_data("Alternative")).json()
        assert first["enabled"] is False
        assert web.post(f"/api/rules/{first['id']}/enabled", json={"enabled": True}).status_code == 200
        assert web.post(f"/api/rules/{second['id']}/enabled", json={"enabled": True}).status_code == 200
        listed = web.get("/api/rules").json()
        assert sum(rule["enabled"] for rule in listed) == 1
        assert next(rule for rule in listed if rule["enabled"])["id"] == second["id"]
        changed = web.put(f"/api/rules/{second['id']}", json=rule_data("Revised", 2)).json()
        assert changed["name"] == "Revised" and changed["feature_index"] == 2
        assert web.post("/api/automation/arm", json={"rule_id": second["id"]}).status_code == 409
        assert web.delete(f"/api/rules/{first['id']}").status_code == 200
        assert web.get("/api/rules").json()[0]["id"] == second["id"]
    assert RuleStore(path).enabled().id == second["id"]
    assert "camera" not in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_rules_validate_limits_and_unsupported_actions(tmp_path: Path):
    with TestClient(create_app(Settings(), rules=RuleStore(tmp_path / "rules.json")), base_url="http://127.0.0.1:8000") as web:
        invalid = rule_data()
        invalid["duration"] = 30
        assert web.post("/api/rules", json=invalid).status_code == 422
        invalid = rule_data()
        invalid["action"] = "ROTATE"
        assert web.post("/api/rules", json=invalid).status_code == 422
        assert web.get("/api/rules").json() == []


def test_camera_selection_requires_camera_stopped_and_local_origin(tmp_path: Path):
    with TestClient(create_app(Settings(), rules=RuleStore(tmp_path / "rules.json")), base_url="http://127.0.0.1:8000") as web:
        assert web.post("/api/camera/input", json={"index": 1}).json()["camera_index"] == 1
        assert web.get("/api/camera/status").json()["camera_index"] == 1
        assert web.post("/api/camera/input", json={"index": -1}).status_code == 422
        assert web.post("/api/camera/input", json={"index": 0}, headers={"Origin": "https://other.example"}).status_code == 403
        assert web.get("/api/rules", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        from app.camera import CameraStatus
        web.app.state.services.camera.status = CameraStatus.RUNNING
        assert web.post("/api/camera/input", json={"index": 2}).status_code == 409


def test_bad_local_rules_fail_closed_without_blocking_startup(tmp_path: Path):
    path = tmp_path / "config.local.rules.json"
    path.write_text("not json")
    store = RuleStore(path)
    assert store.list() == []
    assert store.load_error is not None
    with TestClient(create_app(Settings(), rules=store), base_url="http://127.0.0.1:8000") as web:
        assert web.get("/").status_code == 200
        assert web.get("/api/status").json()["rules_error"] is not None
        assert web.post("/api/automation/arm", json={"rule_id": "missing"}).status_code == 409
        assert web.post("/api/rules", json=rule_data()).status_code == 409
        assert path.read_text() == "not json"


def test_manual_commands_blocked_while_automation_armed(tmp_path: Path):
    from app.camera import CameraService, CameraStatus

    camera = CameraService(Settings())
    camera.status = CameraStatus.RUNNING  # No real camera opened by this API test.
    with TestClient(create_app(Settings(), camera=camera, rules=RuleStore(tmp_path / "rules.json")),
                    base_url="http://127.0.0.1:8000") as web:
        web.post("/api/devices/simulated")
        web.post("/api/devices/select", json={"device_id": "simulator-1"})
        simulator = web.app.state.services.devices.get("simulator-1")
        rule = web.post("/api/rules", json=rule_data()).json()
        web.post(f"/api/rules/{rule['id']}/enabled", json={"enabled": True})
        assert web.post("/api/automation/arm", json={"rule_id": rule["id"]}).status_code == 200
        assert web.post("/api/control/enable").status_code == 409
        assert web.post("/api/control/test", json={"intensity": 0.2, "duration": 1}).status_code == 409
        assert simulator.last_intensity == 0
        assert web.post("/api/emergency-stop").status_code == 200
        assert web.get("/api/automation/status").json()["state"] == "EMERGENCY_STOP"
        assert simulator.last_intensity == 0


def test_real_adapter_receives_no_camera_commands_while_disarmed():
    import asyncio
    import time
    from buttplug import OutputType
    from app.devices.buttplug_client import RealDevice
    from app.devices.registry import DeviceRegistry
    from app.events import Event
    from app.safety.controller import SafetyController
    from app.triggers.automation import AutomationController

    class Feature:
        outputs = {"Vibrate": object()}

        def __init__(self): self.commands = []
        def has_output(self, output): return output is OutputType.VIBRATE
        async def run_output(self, command): self.commands.append(command)

    class NativeDevice:
        index = 4
        name = "Fake real device"

        def __init__(self):
            self.features = {2: Feature()}
            self.stops = 0

        async def stop(self): self.stops += 1

    async def exercise():
        native = NativeDevice()
        registry = DeviceRegistry()
        registry.add(RealDevice(native))
        registry.select("intiface-4")
        safety = SafetyController(registry)
        controller = AutomationController(registry, safety, lambda: True, lambda: True)
        for _ in range(10):
            await controller.handle_event(Event("interaction_continued", {
                "confidence": 0.95, "observed_at": time.monotonic(),
            }))
        assert native.features[2].commands == []
        await controller.shutdown()

    asyncio.run(exercise())
