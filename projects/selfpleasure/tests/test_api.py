from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings


def test_dashboard_and_safe_defaults() -> None:
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as client:
        home = client.get("/").text
        for control in ("tabletop-arm", "tabletop-stop", "tabletop-emergency",
                        "tabletop-preview", "tabletop-set-base", "tabletop-set-end",
                        "tabletop-save-axis", "tabletop-device", "tabletop-feature"):
            assert f'id="{control}"' in home
        for hidden_control in ("session-source-sim", "session-simulator", "session-mode",
                               "session-style", "session-preflight-test"):
            assert f'id="{hidden_control}"' not in home
        assert client.get("/dashboard").status_code == 200
        status = client.get("/api/status").json()

    assert status["application"] == "running"
    assert status["intiface"] == "not_connected"
    assert status["camera"] == "inactive"
    assert status["device"] is None
    assert status["activation_enabled"] is False
    assert status["real_device_manual_bench_enabled"] is False
    assert status["privacy"] == {"records_video": False, "uploads_video": False}


def test_simulator_can_be_initialized_and_emergency_stopped() -> None:
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as client:
        created = client.post("/api/devices/simulated")
        assert created.status_code == 201
        assert created.json()["name"] == "Simulated Vibrator"

        devices = client.get("/api/devices").json()
        assert devices[0]["simulated"] is True
        assert "vibrate" in devices[0]["capabilities"]

        stopped = client.post("/api/emergency-stop")
        assert stopped.json() == {"stopped": True, "activation_enabled": False}
        assert client.get("/api/status").json()["emergency_stop_latched"] is True


def test_guided_session_is_off_by_default_and_rejects_unbounded_plan() -> None:
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as client:
        assert 'id="guided-session"' in client.get("/dashboard").text
        snapshot = client.get("/api/automation/status").json()
        assert snapshot["state"] == "DISARMED"
        assert snapshot["session"]["enabled"] is False
        response = client.post("/api/automation/arm", json={
            "feature_index": 0,
            "session": {"opening_pulses": 20, "middle_pulses": 20,
                        "buildup_pulses": 1, "include_buildup": True},
        })
        assert response.status_code == 422
        assert client.get("/api/automation/status").json()["state"] == "DISARMED"
