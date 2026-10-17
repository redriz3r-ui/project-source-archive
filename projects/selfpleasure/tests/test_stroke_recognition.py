"""Numeric stroke trajectories and opt-in, no-device session evaluation."""

import asyncio
import time

import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.evaluation.stroke import StrokeEvaluationService, score_stroke_session
from app.events import Event
from app.vision.hand_tracking import HandTracking
from app.vision.stroke_estimator import StrokeEstimator
from app.vision.stroke_contract import StrokeEventKind

from tests.test_hand_tracking import MockHandVision, MockSource, landmarks
from app.camera import CameraService, CameraStatus
from app.vision.hand_tracking import HandCalibrationStore


def tracked(position: float | None, confidence: float = 0.9,
            state: str = "TRACKED") -> HandTracking:
    return HandTracking(state=state, hand_detected=position is not None,
                        travel_position=position, tracking_confidence=confidence)


def run_positions(positions, dt=0.05, confidence=0.9):
    estimator = StrokeEstimator()
    events = []
    for index, position in enumerate(positions):
        _, emitted = estimator.update(tracked(position, confidence),
                                      1 + int(index * dt * 1e9), index + 1)
        events.extend(emitted)
    return events


@pytest.mark.parametrize("positions,dt", [
    ([0.1] * 3 + [0.1 + i * 0.006 for i in range(145)], 0.05),  # slow, ~0.12 axis/s
    ([0.08, 0.13, 0.23, 0.33, 0.43, 0.53, 0.63, 0.73, 0.83, 0.93] + [0.93] * 3, 0.05),
])
def test_slow_and_fast_complete_once_with_unique_id(positions, dt) -> None:
    events = run_positions(positions, dt)
    completed = [item for item in events if item.kind == StrokeEventKind.COMPLETED]
    started = [item for item in events if item.kind == StrokeEventKind.STARTED]
    assert len(started) == len(completed) == 1
    assert started[0].stroke_id == completed[0].stroke_id == 1
    assert completed[0].travel >= 0.25


def test_reversal_rule_completes_once_and_next_traversal_gets_new_id() -> None:
    positions = ([0.2, 0.2, 0.25, 0.33, 0.42, 0.5, 0.6, 0.69, 0.7, 0.66, 0.61, 0.55,
                  0.47, 0.38, 0.28, 0.18, 0.1, 0.07, 0.07])
    events = run_positions(positions)
    completed = [item for item in events if item.kind == StrokeEventKind.COMPLETED]
    assert len(completed) == 2
    assert [item.stroke_id for item in completed] == [1, 2]


def test_partial_stationary_and_small_shakes_never_complete() -> None:
    stationary = [0.5 + (0.008 if i % 2 else -0.008) for i in range(150)]
    partial = [0.1, 0.12, 0.17, 0.22, 0.27, 0.29, 0.25, 0.2, 0.15, 0.1]
    for positions in (stationary, partial):
        assert not any(event.kind == StrokeEventKind.COMPLETED
                       for event in run_positions(positions))


def test_interruption_occlusion_out_of_frame_and_implausible_jump_lose_tracking() -> None:
    estimator = StrokeEstimator()
    events = []
    sequence = [tracked(0.1), tracked(0.16), tracked(0.25),
                tracked(None, 0, "TRACKING_LOST"), tracked(None, 0, "TRACKING_LOST"),
                tracked(0.55), tracked(0.9)]
    for index, item in enumerate(sequence):
        _, emitted = estimator.update(item, 1 + index * 50_000_000, index + 1)
        events.extend(emitted)
    assert sum(event.kind == StrokeEventKind.TRACKING_LOST for event in events) == 2
    assert not any(event.kind == StrokeEventKind.COMPLETED for event in events)

    estimator = StrokeEstimator()
    estimator.update(tracked(0.1), 1, 1)
    _, emitted = estimator.update(tracked(0.9), 50_000_001, 2)
    assert emitted[0].kind == StrokeEventKind.TRACKING_LOST


def test_synthetic_lighting_quality_changes_are_fail_closed() -> None:
    trajectory = [0.1, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.95]
    for quality in (0.95, 0.6):  # proxy for adequate lighting, not image validation
        assert sum(event.kind == StrokeEventKind.COMPLETED for event in
                   run_positions(trajectory, confidence=quality)) == 1
    estimator = StrokeEstimator()
    emitted = []
    for index, position in enumerate(trajectory):
        quality = 0.3 if index >= 5 else 0.9  # dim/occluded tracking confidence collapse
        _, events = estimator.update(tracked(position, quality),
                                     1 + index * 50_000_000, index + 1)
        emitted.extend(events)
    assert any(event.kind == StrokeEventKind.TRACKING_LOST for event in emitted)
    assert not any(event.kind == StrokeEventKind.COMPLETED for event in emitted)


def test_stroke_session_metrics_match_one_to_one_and_exclude_uncertain() -> None:
    document = {
        "label_changes": [
            {"elapsed_s": 0.0, "label": "UNCERTAIN"},
            {"elapsed_s": 0.5, "label": "STROKES"},
            {"elapsed_s": 2.0, "label": "NO_STROKES"},
            {"elapsed_s": 4.0, "label": "UNCERTAIN"},
        ],
        "manual_strokes": [{"elapsed_s": 1.0}],
        "detected_strokes": [
            {"elapsed_s": 1.2, "stroke_id": 1},
            {"elapsed_s": 2.2, "stroke_id": 2},
            {"elapsed_s": 4.2, "stroke_id": 3},
        ],
        "samples": [
            {"elapsed_s": 2.0, "label": "NO_STROKES"},
            {"elapsed_s": 2.1, "label": "NO_STROKES"},
            {"elapsed_s": 2.2, "label": "NO_STROKES"},
        ],
    }
    report = score_stroke_session(document)
    assert report["matched_strokes"] == 1
    assert report["false_detections"] == 1
    assert report["precision"] == 0.5
    assert report["recall"] == 1
    assert report["stroke_count_accuracy"] == 0
    assert report["false_detections_per_hour"] == 18000
    assert report["detection_latencies_s"] == [0.2]


def test_stroke_evaluation_consent_review_save_delete_and_no_frames(tmp_path) -> None:
    now = [100.0]
    service = StrokeEvaluationService(tmp_path / "strokes", clock=lambda: now[0])
    with pytest.raises(ValueError):
        service.start(False)
    service.start(True)
    now[0] = 100.5
    service.label("STROKES")
    now[0] = 101.0
    service.mark_stroke()
    service.ingest(Event("stroke_observation", {
        "observed_at": 101.1,
        "tracking_state": "TRACKED",
        "stroke": {"frame_id": 4, "hand_position": 0.8, "speed": 0.5,
                   "travel": 0.6, "tracking_confidence": 0.9,
                   "stroke_id": 1, "direction": "FORWARD", "image": "must not persist"},
    }))
    service.ingest(Event("stroke_completed", {
        "observed_at": 101.2, "stroke": {"stroke_id": 1},
    }))
    assert service.snapshot()["sample_count"] == 1
    assert "image" not in service.draft_detail()["samples"][0]
    service.stop()
    assert service.snapshot()["report"]["recall"] == 1
    with pytest.raises(ValueError):
        service.save(False)
    saved = service.save(True)
    assert service.saved(saved["id"])["privacy"]["frames_saved"] is False
    assert len(service.list_saved()) == 1
    service.delete(saved["id"])
    assert service.list_saved() == []


def test_stroke_evaluation_api_forces_device_disarmed(tmp_path) -> None:
    source = MockSource()
    camera = CameraService(source_factory=lambda: source,
                           hand_vision_factory=MockHandVision,
                           hand_calibration=HandCalibrationStore(tmp_path / "hand.json"))
    evaluation = StrokeEvaluationService(tmp_path / "sessions")
    with TestClient(create_app(Settings(), camera=camera, stroke_evaluation=evaluation),
                    base_url="http://127.0.0.1:8000") as web:
        assert web.get("/hand/evaluate").status_code == 200
        assert web.post("/api/stroke-evaluation/start", json={"consent": True}).status_code == 409
        web.post("/api/camera/mode", json={"mode": "hand"})
        web.post("/api/camera/start")
        deadline = time.monotonic() + 2
        while camera.status != CameraStatus.RUNNING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert web.post("/api/stroke-evaluation/start", json={"consent": True}).status_code == 200
        assert web.post("/api/stroke-evaluation/label", json={"label": "STROKES"},
                        headers={"Origin": "http://outside.example"}).status_code == 403
        assert web.post("/api/devices/simulated").status_code == 409
        assert web.post("/api/automation/arm", json={"feature_index": 0}).status_code == 409
        assert web.post("/api/stroke-evaluation/label", json={"label": "STROKES"}).status_code == 200
        assert web.post("/api/stroke-evaluation/mark").status_code == 200
        draft = web.get("/api/stroke-evaluation/draft")
        assert draft.headers["cache-control"] == "no-store"
        assert draft.json()["privacy"]["frames_saved"] is False
        assert web.post("/api/stroke-evaluation/stop").status_code == 200
        assert web.post("/api/stroke-evaluation/discard").status_code == 200
        assert web.post("/api/camera/stop").status_code == 200
    assert source.closed


def test_hand_tracking_loss_uses_separate_topic_from_oral_automation(tmp_path) -> None:
    class ChangingLightSource(MockSource):
        def read(self):
            self.reads += 1
            value = 120 if self.reads == 1 else 10
            return np.full((120, 160, 3), value, dtype=np.uint8)

    class LightSensitiveHandVision(MockHandVision):
        def process(self, frame, timestamp_ms):
            self.calls += 1
            return [landmarks(0.5, 0.5)] if frame.mean() >= 50 else []

    store = HandCalibrationStore(tmp_path / "hand.json")
    store.update(base=(0.3, 0.5), endpoint=(0.7, 0.5))
    camera = CameraService(Settings(camera_target_fps=24), source_factory=ChangingLightSource,
                           hand_vision_factory=LightSensitiveHandVision, hand_calibration=store)
    topics = []
    camera.set_event_sink(lambda event: topics.append(event.topic))
    camera.set_mode("hand")
    camera.start()
    deadline = time.monotonic() + 2
    while "stroke_tracking_lost" not in topics and time.monotonic() < deadline:
        time.sleep(0.01)
    asyncio.run(camera.stop())
    assert "stroke_tracking_lost" in topics
    assert "tracking_lost" not in topics
    assert "interaction_started" not in topics
