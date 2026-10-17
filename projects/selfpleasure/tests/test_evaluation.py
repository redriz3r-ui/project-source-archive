import json
import stat
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.camera import CameraService, CameraStatus
from app.config import Settings
from app.evaluation.metrics import score_samples
from app.evaluation.service import EvaluationService
from app.events import Event
from app.vision.calibration import CalibrationStore
from app.vision.object_tracker import ObjectObservation
from app.vision.service import FaceObservation


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


def sample(index, label, state):
    return {"elapsed_s": index * 0.1, "label": label, "state": state}


def test_metrics_cover_brief_pass_stationary_occlusion_head_motion_and_lighting():
    negative = "NO_INTERACTION"
    positive = "INTENDED"
    uncertain = "UNCERTAIN"
    off = "OBJECT_VISIBLE"
    active = "INTERACTION_ACTIVE"
    states = [
        # Brief pass: one false active frame; stationary hold stays off.
        (negative, off), (negative, off), (negative, active), (negative, off),
        (negative, off), (negative, off), (negative, off), (negative, off), (negative, off),
        # Intended interval, delayed start; marker occlusion ends tracking.
        (positive, off), (positive, off), (positive, active), (positive, active),
        (positive, "TRACKING_LOST"), (negative, "TRACKING_LOST"), (negative, off),
        (negative, off),
        # Lighting loss marked uncertain, excluded from precision/recall.
        (uncertain, "NO_FACE"), (uncertain, active),
        # Head and prop moving together, intended interval recognized.
        (positive, off), (positive, active), (positive, active), (positive, active),
        (negative, active), (negative, off),
        # One intended interval entirely missed.
        (positive, off), (positive, off), (positive, off),
    ]
    report = score_samples([sample(i, label, state) for i, (label, state) in enumerate(states)])
    assert report["true_positive"] == 5
    assert report["false_positive"] == 2
    assert report["false_negative"] == 7
    assert report["precision"] == 0.714
    assert report["recall"] == 0.417
    assert report["false_positive_episodes"] == 2
    assert report["false_positive_episodes_per_hour"] > 0
    assert report["missed_interactions"] == 1
    assert report["start_latencies_s"] == [0.2, 0.1]
    assert report["end_latencies_s"] == [0.0, 0.1]
    assert report["uncertain_frames"] == 2


def test_numeric_draft_requires_two_consents_and_can_be_reviewed_deleted(tmp_path: Path):
    clock = Clock()
    evaluation = EvaluationService(tmp_path / "evaluation-data", clock=clock)
    with pytest.raises(ValueError):
        evaluation.start(False)
    evaluation.ingest(Event("vision_observation", {"observed_at": 100.0,
        "evaluation": {"state": "INTERACTION_ACTIVE", "mouth_x": 0.5}}))
    assert evaluation.snapshot()["sample_count"] == 0
    evaluation.start(True)
    clock.value = 100.1
    evaluation.set_label("NO_INTERACTION")
    clock.value = 100.2
    evaluation.ingest(Event("vision_observation", {"observed_at": 100.2,
        "evaluation": {"state": "OBJECT_VISIBLE", "mouth_x": 0.5, "object_x": 0.7,
                       "frame": "must-not-be-saved", "confidence": 0.4}}))
    assert not evaluation.directory.exists()
    evaluation.stop()
    with pytest.raises(ValueError):
        evaluation.save(False)
    assert not evaluation.directory.exists()
    saved = evaluation.save(True)
    path = evaluation.directory / f"{saved['id']}.json"
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    document = json.loads(path.read_text())
    assert document["samples"][0]["label"] == "NO_INTERACTION"
    assert document["samples"][0]["mouth_x"] == 0.5
    assert "frame" not in document["samples"][0]
    assert document["privacy"] == {"numeric_only": True, "frames_saved": False, "uploaded": False}
    assert evaluation.list_saved()[0]["id"] == saved["id"]
    assert evaluation.saved(saved["id"])["report"] == saved["report"]
    with pytest.raises(ValueError):
        evaluation.delete("../other")
    evaluation.delete(saved["id"])
    assert evaluation.list_saved() == []


def test_queued_frame_uses_label_at_capture_time_and_unsaved_draft_is_discarded(tmp_path: Path):
    clock = Clock()
    evaluation = EvaluationService(tmp_path / "evaluation-data", clock=clock)
    evaluation.start(True)
    clock.value = 100.1
    evaluation.set_label("NO_INTERACTION")
    clock.value = 100.3
    evaluation.set_label("INTENDED")
    evaluation.ingest(Event("interaction_started", {"observed_at": 100.2,
        "evaluation": {"state": "INTERACTION_ACTIVE"}}))
    assert evaluation.snapshot()["recent_samples"][0]["label"] == "NO_INTERACTION"
    evaluation.note_camera_stopped(99.0)  # Queued stop from a prior camera session.
    assert evaluation.snapshot()["recording"] is True
    evaluation.discard()
    assert evaluation.snapshot()["draft_id"] is None
    assert not evaluation.directory.exists()


def test_api_evaluation_blocks_all_activation_and_requires_consent(tmp_path: Path):
    camera = CameraService(Settings())
    camera.status = CameraStatus.RUNNING  # Fake status; no camera is opened.
    evaluation = EvaluationService(tmp_path / "evaluation-data")
    with TestClient(create_app(Settings(), camera=camera, evaluation=evaluation),
                    base_url="http://127.0.0.1:8000") as web:
        simulator = web.post("/api/devices/simulated").json()
        web.post("/api/devices/select", json={"device_id": simulator["id"]})
        device = web.app.state.services.devices.get(simulator["id"])
        assert web.get("/evaluate").status_code == 200
        assert web.post("/api/evaluation/start", json={"consent": False}).status_code == 422
        assert web.post("/api/evaluation/start", json={"consent": True},
                        headers={"Origin": "https://elsewhere.example"}).status_code == 403
        started = web.post("/api/evaluation/start", json={"consent": True})
        assert started.status_code == 200 and started.json()["active"]
        assert web.get("/api/status").json()["evaluation_active"] is True
        assert web.post("/api/evaluation/start", json={"consent": True}).status_code == 409
        assert web.post("/api/automation/arm", json={"feature_index": 0}).status_code == 409
        assert web.post("/api/control/enable").status_code == 409
        assert web.post("/api/control/test", json={"feature_index": 0}).status_code == 409
        assert web.post("/api/intiface/connect").status_code == 409
        assert web.post("/api/devices/select", json={"device_id": simulator["id"]}).status_code == 409
        assert device.last_intensity == 0 and device.stop_count == 0
        assert web.post("/api/evaluation/label", json={"label": "NO_INTERACTION"}).status_code == 200
        draft = web.get("/api/evaluation/draft")
        assert draft.status_code == 200 and draft.headers["cache-control"] == "no-store"
        assert web.post("/api/evaluation/stop").status_code == 200
        assert web.post("/api/evaluation/save", json={"consent": False}).status_code == 422
        saved = web.post("/api/evaluation/save", json={"consent": True})
        assert saved.status_code == 200
        identifier = saved.json()["id"]
        assert web.get(f"/api/evaluation/sessions/{identifier}").status_code == 200
        assert web.delete(f"/api/evaluation/sessions/{identifier}").json() == {"deleted": True}
        assert web.get("/api/evaluation/draft").status_code == 404
        assert device.last_intensity == 0 and device.stop_count == 0


def test_evaluation_rejects_armed_automation_then_can_start_after_disarm(tmp_path: Path):
    camera = CameraService(Settings())
    camera.status = CameraStatus.RUNNING
    evaluation = EvaluationService(tmp_path / "evaluation-data")
    with TestClient(create_app(Settings(), camera=camera, evaluation=evaluation),
                    base_url="http://127.0.0.1:8000") as web:
        simulator = web.post("/api/devices/simulated").json()
        web.post("/api/devices/select", json={"device_id": simulator["id"]})
        assert web.post("/api/automation/arm", json={"feature_index": 0}).status_code == 200
        assert web.post("/api/evaluation/start", json={"consent": True}).status_code == 409
        web.post("/api/automation/disarm")
        assert web.post("/api/evaluation/start", json={"consent": True}).status_code == 200
        assert web.post("/api/evaluation/discard").status_code == 200
        assert not evaluation.directory.exists()


def test_mock_camera_events_feed_numeric_evaluation_without_frames(tmp_path: Path):
    class Source:
        def open(self): pass
        def read(self): return np.zeros((120, 160, 3), dtype=np.uint8)
        def close(self): pass

    class Vision:
        def open(self): pass
        def process(self, frame, timestamp_ms, overlay):
            return FaceObservation(face_detected=True, mouth_detected=True, mouth_x=0.5,
                                   mouth_y=0.5, mouth_width=0.12, mouth_openness=0.2,
                                   tracking_quality=0.95), frame
        def close(self): pass

    class ObjectDetector:
        def process(self, frame):
            return ObjectObservation(True, 0.64, 0.5, tracking_quality=0.9, source="marker")

    camera = CameraService(Settings(camera_target_fps=20), source_factory=Source,
                           vision_factory=Vision,
                           calibration=CalibrationStore(tmp_path / "calibration.json"),
                           object_detector_factory=lambda _: ObjectDetector())
    evaluation = EvaluationService(tmp_path / "evaluation-data")
    with TestClient(create_app(Settings(), camera=camera, evaluation=evaluation),
                    base_url="http://127.0.0.1:8000") as web:
        assert web.post("/api/camera/start").status_code == 202
        deadline = time.monotonic() + 2
        while camera.status != CameraStatus.RUNNING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert web.post("/api/evaluation/start", json={"consent": True}).status_code == 200
        web.post("/api/evaluation/label", json={"label": "NO_INTERACTION"})
        deadline = time.monotonic() + 2
        while evaluation.snapshot()["sample_count"] < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert evaluation.snapshot()["sample_count"] >= 3
        sample_data = evaluation.snapshot()["recent_samples"][-1]
        assert sample_data["mouth_x"] == 0.5 and sample_data["object_x"] == 0.64
        assert "frame" not in sample_data and "image" not in sample_data
        assert web.post("/api/camera/stop").status_code == 200
        assert evaluation.snapshot()["recording"] is False
        web.post("/api/evaluation/stop")
        assert not evaluation.directory.exists()
