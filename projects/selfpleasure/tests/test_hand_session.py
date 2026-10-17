"""Session API and accessible surface tests; no hardware or camera opened."""

import asyncio
from html.parser import HTMLParser
import time

from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraStatus
from app.config import Settings
from app.devices.models import DeviceInfo
from app.devices.registry import DeviceRegistry
from app.devices.simulated import SimulatedDevice
from app.safety.controller import SafetyController
from app.triggers.hand_response import HandResponseController, HandResponseRule, HandResponseState
from app.vision.stroke_contract import STROKE_SCHEMA_VERSION, StrokeDirection, StrokeObservation
from app.events import Event
from dataclasses import asdict


class SessionHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.labels = []
        self.buttons = []
        self.status_live = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "label":
            self.labels.append(attrs.get("for"))
        if tag == "button":
            self.buttons.append((attrs.get("id"), attrs.get("type")))
        if attrs.get("role") == "status" and attrs.get("aria-live") == "polite":
            self.status_live += 1


class InertRealDevice(SimulatedDevice):
    @property
    def info(self):
        original = super().info
        return DeviceInfo("intiface-0", "Injected Petal", False,
                          ("Vibrate", "Oscillate"), original.status)

    @property
    def vibration_features(self):
        return (2,)

    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        raise AssertionError("This API test must not issue device output")


class RecordingRealDevice(InertRealDevice):
    async def vibrate_feature(self, feature_index: int, intensity: float) -> None:
        assert feature_index == 2
        self.last_intensity = intensity


def test_default_real_output_lockout_blocks_manual_preflight_and_hand_arm():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        current = web.app.state.services
        device = InertRealDevice()
        current.devices.add(device)
        current.devices.select(device.info.identifier)
        current.intiface.state.connected = True
        current.camera.status = CameraStatus.RUNNING
        current.camera.mode = "hand"
        current.hand_response._tracking_ns = time.monotonic_ns()
        assert web.get("/api/status").json()["real_device_output_enabled"] is False
        assert web.get("/api/hand/session/status").json()["real_pilot_available"] is False
        assert web.post("/api/control/enable").status_code == 409
        assert web.post("/api/hand/session/preflight-test", json={
            "feature_index": 2, "physical_power_off_ready": True}).status_code == 409
        assert web.post("/api/hand/session/arm", json={
            "feature_index": 2, "duration": 0.12, "cooldown": 0.5,
            "real_pilot": True, "manual_preflight_confirmed": True,
            "physical_power_off_ready": True}).status_code == 409
        assert device.last_intensity == 0


def test_session_page_has_keyboard_controls_status_and_emergency_stop():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        page = web.get("/hand/session")
        assert page.status_code == 200
        parser = SessionHTML()
        parser.feed(page.text)
        assert len(parser.ids) == len(set(parser.ids))
        assert {"session-emergency", "session-arm", "session-prepare", "session-preflight-test",
                "session-pause", "session-disarm", "session-finish", "session-preview-pattern"}.issubset({value for value, _ in parser.buttons})
        assert all(kind == "button" for _, kind in parser.buttons)
        assert "session-intensity" in parser.labels
        assert "session-feature" in parser.labels
        assert "session-device-select" in parser.labels
        assert "session-manual-check" in parser.labels
        assert "session-power-check" in parser.labels
        assert "session-base-x" in parser.labels  # Keyboard calibration alternative.
        assert parser.status_live >= 2
        assert 'aria-keyshortcuts="Escape"' in page.text
        assert "No footage or telemetry is saved by default" in page.text
        assert web.get("/").status_code == 200
        assert 'id="tabletop-arm"' in web.get("/").text
        assert web.get("/dashboard").status_code == 200
        assert web.post("/api/application/quit").status_code == 404


def test_desktop_quit_stops_output_and_camera_before_exit_callback():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        web.app.state.desktop_exit = lambda: None
        assert web.get("/api/status").json()["desktop_app"] is True
        result = web.post("/api/application/quit")
        assert result.status_code == 200
        assert result.json()["quitting"] is True
        assert web.app.state.services.hand_response.state == HandResponseState.DISARMED
        assert web.app.state.services.camera.status == "inactive"


def test_preflight_preview_and_finish_are_safe_and_origin_checked():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        status = web.get("/api/hand/session/status").json()
        assert status["response"]["state"] == "DISARMED"
        assert status["tracking_ready"] is False
        assert status["camera"]["status"] == "inactive"
        assert web.post("/api/hand/session/pause").status_code == 409
        simulator_id = web.post("/api/devices/simulated").json()["id"]
        web.post("/api/devices/select", json={"device_id": simulator_id})
        simulator = web.app.state.services.devices.get(simulator_id)
        preview = web.post("/api/hand/session/preview", json={
            "mode": "ONE_RESPONSE", "style": "GENTLE",
        })
        assert preview.status_code == 200
        assert preview.json()["device_command_sent"] is False
        assert simulator.stop_count == 0
        assert simulator.last_intensity == 0
        assert web.post("/api/hand/session/preview", json={
            "mode": "FOLLOW_MOVEMENT", "duration": 0.18, "cooldown": 0.08,
        }).status_code == 422
        assert web.post("/api/hand/session/arm", json={}).status_code == 409
        assert web.post("/api/hand/session/preview", json={},
                        headers={"Origin": "https://example.org"}).status_code == 403
        finished = web.post("/api/hand/session/finish")
        assert finished.status_code == 200
        assert finished.json()["camera"]["status"] == "inactive"
        assert simulator.last_intensity == 0


def test_real_pilot_api_requires_acknowledgements_feature_and_managed_session():
    with TestClient(create_app(Settings(real_device_output_enabled=True)), base_url="http://127.0.0.1:8000") as web:
        current = web.app.state.services
        device = InertRealDevice()
        current.devices.add(device)
        current.devices.select(device.info.identifier)
        current.intiface.state.connected = True
        current.camera.status = CameraStatus.RUNNING  # Mock state; no webcam opened.
        current.camera.mode = "hand"
        current.hand_response._tracking_ns = time.monotonic_ns()
        rule = {"feature_index": 2, "intensity": 0.2, "duration": 0.12,
                "cooldown": 0.5, "real_pilot": True}
        assert web.post("/api/hand/session/preview", json=rule).json()["device_command_sent"] is False
        assert web.post("/api/hand/session/preview", json={**rule,
            "intensity": 0.21}).status_code == 422
        assert web.post("/api/hand/response/arm", json={**rule,
            "manual_preflight_confirmed": True, "physical_power_off_ready": True}).status_code == 409
        assert web.post("/api/hand/session/arm", json=rule).status_code == 409
        assert web.post("/api/hand/session/arm", json={**rule,
            "manual_preflight_confirmed": "true", "physical_power_off_ready": True}).status_code == 422
        confirmed = {**rule, "manual_preflight_confirmed": True,
                     "physical_power_off_ready": True}
        assert web.post("/api/hand/session/arm", json={**confirmed, "feature_index": 0}).status_code == 409
        assert web.post("/api/hand/session/arm", json=confirmed).status_code == 200
        assert current.hand_response.snapshot()["real_pilot"] is True
        assert device.last_intensity == 0
        assert web.post("/api/emergency-stop").status_code == 200
        assert current.hand_response.state == HandResponseState.EMERGENCY_STOP
        assert device.last_intensity == 0


def test_short_real_preflight_requires_physical_fallback_and_selected_feature():
    with TestClient(create_app(Settings(real_device_output_enabled=True)), base_url="http://127.0.0.1:8000") as web:
        current = web.app.state.services
        device = RecordingRealDevice()
        current.devices.add(device)
        current.devices.select(device.info.identifier)
        current.intiface.state.connected = True
        path = "/api/hand/session/preflight-test"
        assert web.post(path, json={"feature_index": 2, "physical_power_off_ready": False}).status_code == 409
        assert web.post(path, json={"feature_index": 2, "physical_power_off_ready": "true"}).status_code == 422
        assert web.post(path, json={"feature_index": 0, "physical_power_off_ready": True}).status_code == 409
        assert web.post(path, json={"feature_index": 2, "physical_power_off_ready": True},
                        headers={"Origin": "https://example.org"}).status_code == 403
        assert device.last_intensity == 0
        result = web.post(path, json={"feature_index": 2, "physical_power_off_ready": True})
        assert result.status_code == 202
        assert result.json()["duration"] == 0.1
        assert result.json()["intensity"] == 0.2
        time.sleep(0.2)
        assert device.last_intensity == 0
        assert device.stop_count > 0
        assert web.post("/api/emergency-stop").status_code == 200
        assert current.hand_response.state == HandResponseState.EMERGENCY_STOP
        assert device.last_intensity == 0


def test_intiface_disconnect_disarms_real_pilot_before_transport_shutdown():
    with TestClient(create_app(Settings(real_device_output_enabled=True)), base_url="http://127.0.0.1:8000") as web:
        current = web.app.state.services
        device = InertRealDevice()
        current.devices.add(device)
        current.devices.select(device.info.identifier)
        current.intiface.state.connected = True
        current.camera.status = CameraStatus.RUNNING
        current.camera.mode = "hand"
        current.hand_response._tracking_ns = time.monotonic_ns()
        assert web.post("/api/hand/session/arm", json={
            "feature_index": 2, "duration": 0.12, "cooldown": 0.5,
            "real_pilot": True, "manual_preflight_confirmed": True,
            "physical_power_off_ready": True,
        }).status_code == 200
        assert web.post("/api/intiface/disconnect").status_code == 200
        assert current.hand_response.state == HandResponseState.DISARMED
        assert device.stop_count >= 1
        assert device.last_intensity == 0
        assert current.devices.get(device.info.identifier) is None


def test_session_lease_expiry_disarms_and_releases_camera_without_resume():
    async def exercise():
        registry = DeviceRegistry()
        device = SimulatedDevice()
        registry.add(device)
        registry.select(device.info.identifier)
        camera = {"running": True, "released": False}
        async def release_camera():
            camera["running"] = False
            camera["released"] = True
        safety = SafetyController(registry)
        controller = HandResponseController(registry, safety,
                                            lambda: camera["running"], release_camera)
        observation = StrokeObservation(STROKE_SCHEMA_VERSION, time.monotonic_ns(),
                                        1, 0.5, StrokeDirection.STILL, 0, 0, 0.9, None)
        await controller.handle_event(Event("stroke_observation", {
            "stroke": asdict(observation), "tracking_state": "TRACKED"}))
        await controller.arm(HandResponseRule(), session_managed=True)
        assert controller.snapshot()["session_managed"] is True
        controller.heartbeat()
        controller._session_lease_until = time.monotonic() - 0.01
        try:
            controller.heartbeat()
        except RuntimeError as exc:
            assert "expired" in str(exc)
        else:
            raise AssertionError("Expired heartbeat must not renew an armed session")
        await asyncio.sleep(0.07)
        assert controller.state == HandResponseState.DISARMED
        assert camera["released"] is True
        assert device.last_intensity == 0
        await controller.shutdown()
    asyncio.run(exercise())
