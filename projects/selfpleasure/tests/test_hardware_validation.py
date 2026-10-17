"""Offline scoring fixtures only: no webcam, Intiface connection, or output."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.diagnostics import LatencyRecorder, TraceStage
from app.diagnostics.collect_hardware_validation import collect, new_records
from app.diagnostics.hardware_validation import score_hardware_cohort, score_hardware_session


BASE = 1_000_000_000_000
MS = 1_000_000
SECOND = 1_000_000_000


def synthetic_session() -> dict:
    labels = []
    detections = []
    episodes = []
    for index in range(60):
        boundary = BASE + index * 2 * SECOND
        labels.append({"id": index + 1, "boundary_ns": boundary,
                       "scenario": ("slow", "normal", "fast")[index // 20]})
        detections.append({"stroke_id": index + 1,
                           "frame_captured_ns": boundary + 30 * MS,
                           "classifier_ns": boundary + 50 * MS,
                           "command_submitted_ns": boundary + 60 * MS,
                           "command_ack_ns": boundary + 70 * MS})
        episodes.append({"onset_ns": boundary + 120 * MS,
                         "off_ns": boundary + 200 * MS})
    stops = []
    for index, scenario in enumerate(("marker_occlusion", "camera_stop",
                                      "intiface_disconnect", "disarm", "emergency_stop")):
        boundary = labels[index]["boundary_ns"]
        stops.append({"scenario": scenario, "request_ns": boundary + 140 * MS,
                      "observation_end_ns": boundary + 300 * MS,
                      "output_active_at_request": True})
    return {
        "schema_version": 1, "source": "synthetic", "held_out": True,
        "session_id": "fixture-1",
        "clock_domain": "host_monotonic_ns", "max_clock_alignment_error_ms": 2,
        "sensor_method": "external_accelerometer",
        "device": {"identifier": "intiface-1", "model": "Synthetic Device", "selected_vibration_feature": 2,
                   "advertised_vibration_features": [2]},
        "labels": labels, "detections": detections,
        "physical_episodes": episodes,
        "negative_intervals": [
            {"scenario": "pause", "start_ns": BASE + 120 * SECOND,
             "end_ns": BASE + 3720 * SECOND},
            {"scenario": "marker_occlusion", "start_ns": BASE + 4000 * SECOND,
             "end_ns": BASE + 4001 * SECOND},
        ],
        "stop_checks": stops,
    }


def test_synthetic_metrics_are_computed_but_release_gates_never_pass():
    report = score_hardware_session(synthetic_session())
    assert report["labeled_strokes"] == 60
    assert report["exactly_one_responses"] == 60
    assert report["detection_precision"] == 1
    assert report["detection_recall"] == 1
    assert report["physical_onset_from_boundary"]["p95_ms"] == 120
    assert report["physical_stop_delay"]["p95_ms"] == 60
    assert report["camera_boundary_to_frame"]["median_ms"] == 30
    assert report["classifier_frame_to_decision"]["median_ms"] == 20
    assert report["trigger_decision_to_command"]["median_ms"] == 10
    assert report["command_ack"]["median_ms"] == 10
    assert report["device_command_to_physical"]["median_ms"] == 60
    assert report["release_gate_status"] == "NOT_EVALUATED"
    assert report["session_gate_status"] == "NOT_EVALUATED"
    assert set(report["gates"].values()) == {"NOT_EVALUATED"}


def test_missing_data_and_manual_reaction_timing_cannot_pass():
    document = synthetic_session()
    document["source"] = "real_device"
    document["labels"] = document["labels"][:4]
    document["sensor_method"] = "human_keypress"
    document["max_clock_alignment_error_ms"] = 20
    document["device"]["selected_vibration_feature"] = 7
    report = score_hardware_session(document)
    assert report["release_gate_status"] == "NOT_EVALUATED"
    assert report["feature_verified"] is False
    assert len(report["gate_preconditions_unmet"]) >= 4


def test_real_held_out_fixture_shows_misses_duplicates_false_onsets_and_stop_failures():
    document = synthetic_session()
    document["source"] = "real_device"  # Synthetic fixture checks formulas, not real evidence.
    document["physical_episodes"].pop(10)
    duplicate = {"onset_ns": BASE + 220 * MS, "off_ns": BASE + 250 * MS}
    document["physical_episodes"].append(duplicate)
    negative = document["negative_intervals"][0]["start_ns"]
    document["physical_episodes"].append({"onset_ns": negative + SECOND,
                                          "off_ns": negative + SECOND + 50 * MS})
    document["physical_episodes"].append({"onset_ns": negative + 3 * SECOND,
                                          "off_ns": negative + 3 * SECOND + 50 * MS})
    report = score_hardware_session(document)
    assert report["missed_responses"] == 1
    assert report["duplicate_responses"] == 1
    assert report["false_activation_episodes"] == 2
    assert report["unsafe_restarts"] == 1
    assert report["session_gate_status"] == "FAIL"
    assert report["release_gate_status"] == "NOT_EVALUATED"
    assert report["gates"]["no_unsafe_restart"] == "FAIL"
    assert report["gates"]["false_activations_per_hour"] == "FAIL"


def test_slow_physical_onset_fails_250_ms_gate_without_hiding_latency():
    document = synthetic_session()
    document["source"] = "real_device"
    for index in range(10, 60):
        document["physical_episodes"][index]["onset_ns"] += 200 * MS
        document["physical_episodes"][index]["off_ns"] += 200 * MS
    report = score_hardware_session(document)
    assert report["physical_onset_from_boundary"]["p95_ms"] == 320
    assert report["gates"]["physical_onset_p95"] == "FAIL"


def test_release_requires_three_distinct_complete_real_sessions():
    documents = [synthetic_session() for _ in range(3)]
    assert score_hardware_cohort(documents)["release_gate_status"] == "NOT_EVALUATED"
    for index, document in enumerate(documents):
        document["source"] = "real_device"  # Formula fixture; not actual evidence.
        document["session_id"] = f"fixture-{index}"
        document["tester_id"] = f"fixture-tester-{index % 2}"
        document["camera_position"] = ("front", "side")[index % 2]
        document["lighting_condition"] = ("daylight", "lamplight")[index % 2]
    assert score_hardware_cohort(documents[:2])["release_gate_status"] == "NOT_EVALUATED"
    assert score_hardware_cohort(documents)["release_gate_status"] == "PASS"
    assert score_hardware_cohort(documents)["compatibility"][0]["availability"] == "SUPPORTED"
    documents[2]["physical_episodes"].append({
        "onset_ns": documents[2]["negative_intervals"][0]["start_ns"] + SECOND,
        "off_ns": documents[2]["negative_intervals"][0]["start_ns"] + SECOND + 50 * MS,
    })
    documents[2]["physical_episodes"].append({
        "onset_ns": documents[2]["negative_intervals"][0]["start_ns"] + 3 * SECOND,
        "off_ns": documents[2]["negative_intervals"][0]["start_ns"] + 3 * SECOND + 50 * MS,
    })
    assert score_hardware_cohort(documents)["release_gate_status"] == "FAIL"


def test_one_tester_or_one_camera_condition_never_meets_release_gate():
    documents = [synthetic_session() for _ in range(3)]
    for index, document in enumerate(documents):
        document.update(source="real_device", session_id=f"fixture-{index}",
                        tester_id="same-tester", camera_position="front",
                        lighting_condition="daylight")
    report = score_hardware_cohort(documents)
    assert report["release_gate_status"] == "NOT_EVALUATED"
    entry = report["compatibility"][0]
    assert entry["availability"] == "NOT_ENABLED"
    assert len(entry["blockers"]) == 3


def test_physical_onset_in_negative_interval_is_false_even_after_matched_command():
    document = synthetic_session()
    document["negative_intervals"].append({"scenario": "pause",
                                           "start_ns": BASE + 100 * MS,
                                           "end_ns": BASE + 300 * MS})
    assert score_hardware_session(document)["false_activation_episodes"] == 1


def test_invalid_clocks_and_event_order_are_rejected():
    document = synthetic_session()
    document["clock_domain"] = "sensor_device_clock"
    with pytest.raises(ValueError, match="host monotonic"):
        score_hardware_session(document)
    document = synthetic_session()
    document["detections"][0]["classifier_ns"] = document["detections"][0]["frame_captured_ns"] - 1
    with pytest.raises(ValueError, match="precedes frame"):
        score_hardware_session(document)
    document = deepcopy(synthetic_session())
    document["physical_episodes"][0]["off_ns"] = document["physical_episodes"][0]["onset_ns"] - 1
    with pytest.raises(ValueError, match="precedes onset"):
        score_hardware_session(document)
    document = deepcopy(synthetic_session())
    document["negative_intervals"].append({
        "scenario": "pause", "start_ns": BASE + 120 * SECOND + 2,
        "end_ns": BASE + 130 * SECOND,
    })
    with pytest.raises(ValueError, match="must not overlap"):
        score_hardware_session(document)


def test_numeric_trace_export_is_read_only_and_contains_no_frames():
    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8000") as web:
        services = web.app.state.services
        simulator = web.post("/api/devices/simulated").json()
        selected = services.devices.get(simulator["id"])
        services.latency.start()
        services.latency.mark(7, TraceStage.FRAME_CAPTURED, 123)
        exported = web.get("/api/diagnostics/latency/traces")
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        assert exported.json() == {
            "clock_domain": "host_monotonic_ns", "numeric_only": True,
            "traces": [{"frame_id": 7, "timestamps_ns": {"frame_captured": 123}}],
            "stop_traces": [],
        }
        assert selected.stop_count == 0
        assert selected.last_intensity == 0


def test_stop_trace_uses_monotonic_numeric_clock_and_requires_opt_in():
    ticks = iter((100, 175))
    recorder = LatencyRecorder(clock=lambda: next(ticks))
    assert recorder.begin_stop("emergency_stop") is None
    recorder.start()
    token = recorder.begin_stop("emergency_stop")
    recorder.complete_stop(token)
    assert recorder.stop_traces() == ({
        "stop_id": token, "reason": "emergency_stop",
        "requested_ns": 100, "completed_ns": 175,
    },)
    with pytest.raises(ValueError, match="Unknown stop reason"):
        recorder.begin_stop("personal image")


def test_opt_in_collector_filters_to_numeric_records_and_deduplicates(tmp_path):
    seen = {"frames": set(), "stops": set(), "events": set()}
    traces = {"traces": [{"frame_id": 2, "timestamps_ns": {
        "frame_captured": 100, "raw_image": "private"}}],
        "stop_traces": [{"stop_id": 1, "reason": "disarm", "requested_ns": 200,
                         "completed_ns": None}]}
    events = [{"kind": "stroke_completed", "frame_id": 2, "timestamp_ns": 150,
               "stroke_id": 3, "hand_position": 0.6, "image": "private"}]
    records = new_records(traces, events, seen)
    assert len(records) == 3
    assert "private" not in str(records)
    assert new_records(traces, events, seen) == []
    traces["traces"][0]["timestamps_ns"]["command_submitted"] = 175
    traces["stop_traces"][0]["completed_ns"] = 250
    assert len(new_records(traces, events, seen)) == 2
    with pytest.raises(ValueError):
        collect(8000, 0.25, tmp_path)
    assert list(tmp_path.iterdir()) == []
