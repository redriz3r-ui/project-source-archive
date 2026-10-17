"""Offline, numeric-only supervised hardware validation. Never connects to a device.

All timestamps must be nanoseconds on the *same host monotonic clock*. An
external sensor must be timestamped on the host or synchronized and aligned
before import. The JSON input contains no images or intimate descriptions.
"""

import argparse
import json
import math
from pathlib import Path
from statistics import median


SCHEMA_VERSION = 1
MATCH_WINDOW_NS = 1_000_000_000
REQUIRED_SCENARIOS = frozenset({
    "slow", "normal", "fast", "pause", "marker_occlusion",
    "camera_stop", "intiface_disconnect", "disarm", "emergency_stop",
})
SAFETY_SCENARIOS = frozenset({
    "marker_occlusion", "camera_stop", "intiface_disconnect",
    "disarm", "emergency_stop",
})


def _ns(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer nanosecond timestamp")
    return value


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 3)


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {"n": len(values), "median_ms": round(median(values), 3) if values else None,
            "p95_ms": _percentile(values, 0.95)}


def _pair_labels(labels: list[dict], detections: list[dict]) -> tuple[dict[int, int], int]:
    """Monotonic one-to-one matching, with a one-second diagnostic window."""
    available = set(range(len(detections)))
    pairs: dict[int, int] = {}
    for label_index, label in enumerate(labels):
        candidates = [(abs(detections[i]["classifier_ns"] - label["boundary_ns"]), i)
                      for i in available
                      if abs(detections[i]["classifier_ns"] - label["boundary_ns"]) <= MATCH_WINDOW_NS]
        if candidates:
            _, selected = min(candidates)
            pairs[label_index] = selected
            available.remove(selected)
    return pairs, len(available)


def score_hardware_session(document: dict[str, object]) -> dict[str, object]:
    """Describe measured performance and evaluate gates only on complete real data."""
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported hardware validation schema version")
    if document.get("clock_domain") != "host_monotonic_ns":
        raise ValueError("All measurements must use aligned host monotonic nanoseconds")
    alignment_error = document.get("max_clock_alignment_error_ms")
    if (not isinstance(alignment_error, (int, float)) or isinstance(alignment_error, bool)
            or not math.isfinite(alignment_error) or alignment_error < 0):
        raise ValueError("Record a finite clock alignment error in milliseconds")
    labels = document.get("labels", [])
    detections = document.get("detections", [])
    episodes = document.get("physical_episodes", [])
    negatives = document.get("negative_intervals", [])
    stops = document.get("stop_checks", [])
    if any(not isinstance(part, list) for part in (labels, detections, episodes, negatives, stops)):
        raise ValueError("Validation observations must be arrays")
    for label in labels:
        _ns(label["boundary_ns"], "label boundary")
        if type(label.get("id")) is not int or label["id"] < 1:
            raise ValueError("Every labeled stroke needs a positive ID")
        if label.get("scenario") not in {"slow", "normal", "fast"}:
            raise ValueError("Stroke scenario must be slow, normal, or fast")
    if len({label["id"] for label in labels}) != len(labels):
        raise ValueError("Labeled stroke IDs must be unique")
    device = document.get("device")
    if not isinstance(device, dict):
        raise ValueError("Record the selected Intiface device and feature")
    feature = device.get("selected_vibration_feature")
    advertised = device.get("advertised_vibration_features")
    feature_verified = (isinstance(device.get("identifier"), str)
                        and device["identifier"].startswith("intiface-")
                        and type(feature) is int and feature >= 0
                        and isinstance(advertised, list)
                        and all(type(value) is int and value >= 0 for value in advertised)
                        and feature in advertised)
    for detection in detections:
        if type(detection.get("stroke_id")) is not int or detection["stroke_id"] < 1:
            raise ValueError("Each detection needs a positive stroke ID")
        capture = _ns(detection["frame_captured_ns"], "frame capture")
        decision = _ns(detection["classifier_ns"], "classifier decision")
        if decision < capture:
            raise ValueError("Classifier decision precedes frame capture")
        submitted = detection.get("command_submitted_ns")
        acknowledged = detection.get("command_ack_ns")
        if submitted is not None:
            _ns(submitted, "command submission")
            if submitted < decision:
                raise ValueError("Command submission precedes classification")
        if acknowledged is not None:
            _ns(acknowledged, "command acknowledgement")
            if submitted is None or acknowledged < submitted:
                raise ValueError("Command acknowledgement precedes submission")
    for episode in episodes:
        onset = _ns(episode["onset_ns"], "physical onset")
        off = _ns(episode["off_ns"], "physical stop")
        if off < onset:
            raise ValueError("Physical stop precedes onset")
    for interval in negatives:
        if _ns(interval["end_ns"], "negative interval end") <= _ns(interval["start_ns"], "negative interval start"):
            raise ValueError("Negative interval must have positive duration")
        if interval.get("scenario") not in {"pause", "marker_occlusion", "normal", "fast", "slow"}:
            raise ValueError("Unknown negative interval scenario")
    ordered_negatives = sorted(negatives, key=lambda item: item["start_ns"])
    if any(left["end_ns"] > right["start_ns"]
           for left, right in zip(ordered_negatives, ordered_negatives[1:])):
        raise ValueError("Negative intervals must not overlap")
    if any(interval["start_ns"] <= label["boundary_ns"] < interval["end_ns"]
           for interval in negatives for label in labels):
        raise ValueError("A labeled stroke boundary cannot be inside a negative interval")
    for stop in stops:
        request = _ns(stop["request_ns"], "stop request")
        end = _ns(stop["observation_end_ns"], "stop observation end")
        if end <= request or stop.get("scenario") not in SAFETY_SCENARIOS:
            raise ValueError("Stop checks need a known scenario and observation window")
        if type(stop.get("output_active_at_request")) is not bool:
            raise ValueError("Record whether output was active at each stop request")

    labels = sorted(labels, key=lambda item: item["boundary_ns"])
    detections = sorted(detections, key=lambda item: item["classifier_ns"])
    episodes = sorted(episodes, key=lambda item: item["onset_ns"])
    overlapping_episodes = sum(left["off_ns"] > right["onset_ns"]
                               for left, right in zip(episodes, episodes[1:]))
    pairs, unmatched_detections = _pair_labels(labels, detections)
    detection_latencies: list[float] = []
    camera_latencies: list[float] = []
    classifier_processing: list[float] = []
    decision_to_submit: list[float] = []
    command_ack: list[float] = []
    boundary_to_physical: list[float] = []
    command_to_physical: list[float] = []
    responses_per_label = [0] * len(labels)
    episode_assignments: list[int | None] = []
    ambiguous_assignments = 0
    commands = [(index, detection["command_submitted_ns"])
                for index, detection in enumerate(detections)
                if detection.get("command_submitted_ns") is not None]
    for episode in episodes:
        candidates = [(index, submitted) for index, submitted in commands
                      if submitted <= episode["onset_ns"] <= submitted + MATCH_WINDOW_NS]
        if len(candidates) > 1:
            ambiguous_assignments += 1
        episode_assignments.append(max(candidates, key=lambda item: item[1])[0] if candidates else None)
    detection_to_label = {detection: label for label, detection in pairs.items()}
    for label_index, detection_index in pairs.items():
        label = labels[label_index]
        detection = detections[detection_index]
        boundary = label["boundary_ns"]
        decision = detection["classifier_ns"]
        capture = detection["frame_captured_ns"]
        detection_latencies.append((decision - boundary) / 1e6)
        camera_latencies.append((capture - boundary) / 1e6)
        classifier_processing.append((decision - capture) / 1e6)
        if detection.get("command_submitted_ns") is not None:
            decision_to_submit.append((detection["command_submitted_ns"] - decision) / 1e6)
        if detection.get("command_ack_ns") is not None:
            command_ack.append((detection["command_ack_ns"] - detection["command_submitted_ns"]) / 1e6)
    for episode, assigned in zip(episodes, episode_assignments):
        if assigned is None:
            continue
        command_to_physical.append((episode["onset_ns"] - detections[assigned]["command_submitted_ns"]) / 1e6)
        label_index = detection_to_label.get(assigned)
        if label_index is not None:
            responses_per_label[label_index] += 1
            boundary_to_physical.append((episode["onset_ns"] - labels[label_index]["boundary_ns"]) / 1e6)
    exact_responses = sum(count == 1 for count in responses_per_label)
    duplicate_responses = sum(max(0, count - 1) for count in responses_per_label)
    missed_responses = sum(count == 0 for count in responses_per_label)
    negative_seconds = sum((interval["end_ns"] - interval["start_ns"]) / 1e9 for interval in negatives)
    # Any physical onset in an explicitly negative interval is false, even if
    # its command happened to match a stroke labeled earlier in the session.
    false_onsets = sorted(episode["onset_ns"] for episode in episodes
                          if any(interval["start_ns"] <= episode["onset_ns"] < interval["end_ns"]
                                 for interval in negatives))
    false_episodes = 0
    last_false = None
    for onset in false_onsets:
        if last_false is None or onset - last_false > 1_000_000_000:
            false_episodes += 1
        last_false = onset
    stop_delays: list[float] = []
    unsafe_restarts = 0
    failed_stops = 0
    for stop in stops:
        request, end = stop["request_ns"], stop["observation_end_ns"]
        active = [episode for episode in episodes
                  if episode["onset_ns"] <= request < episode["off_ns"]]
        if stop["output_active_at_request"] and active:
            off = min(episode["off_ns"] for episode in active)
            if off <= end:
                stop_delays.append((off - request) / 1e6)
            else:
                failed_stops += 1
        elif stop["output_active_at_request"]:
            failed_stops += 1  # Claim of active output lacks sensor evidence.
        if any(request < episode["onset_ns"] < end for episode in episodes):
            unsafe_restarts += 1
    scenarios = {label["scenario"] for label in labels}
    scenarios.update(item["scenario"] for item in negatives)
    scenarios.update(item["scenario"] for item in stops)
    missing = sorted(REQUIRED_SCENARIOS - scenarios)
    precision = len(pairs) / len(detections) if detections else None
    recall = len(pairs) / len(labels) if labels else None
    exact_rate = exact_responses / len(labels) if labels else None
    false_rate = false_episodes * 3600 / negative_seconds if negative_seconds else None
    physical_p95 = _percentile(boundary_to_physical, 0.95)
    gates: dict[str, str] = {}
    sensor_method = document.get("sensor_method")
    preconditions = []
    if document.get("source") != "real_device" or document.get("held_out") is not True:
        preconditions.append("A held-out real-device session is required")
    if sensor_method not in {"external_accelerometer", "external_vibration_sensor"}:
        preconditions.append("Physical onset/stop needs an external sensor, not a human reaction key")
    if not feature_verified:
        preconditions.append("Verify the exact selected Intiface vibration feature")
    if alignment_error > 5:
        preconditions.append("Clock alignment error must be at most 5 ms")
    if missing:
        preconditions.append("Missing scenarios: " + ", ".join(missing))
    if len(labels) < 60 or any(sum(label["scenario"] == speed for label in labels) < 20
                               for speed in ("slow", "normal", "fast")):
        preconditions.append("Collect at least 20 labeled strokes at each speed")
    if negative_seconds < 3600:
        preconditions.append("Collect at least one hour of negative-labeled observation")
    if ambiguous_assignments:
        preconditions.append("Resolve ambiguous sensor-to-command assignments")
    if overlapping_episodes:
        preconditions.append("Resolve overlapping physical sensor episodes")
    missing_active_stops = sorted(name for name in SAFETY_SCENARIOS
                                  if not any(stop["scenario"] == name and stop["output_active_at_request"]
                                             for stop in stops))
    if missing_active_stops:
        preconditions.append("Missing active-output stop checks: " + ", ".join(missing_active_stops))
    sufficient = (document.get("source") == "real_device" and document.get("held_out") is True
                  and not preconditions)
    gate_conditions = {
        "exactly_one_response": exact_rate is not None and exact_rate >= 0.95,
        "detection_precision": precision is not None and precision >= 0.95,
        "detection_recall": recall is not None and recall >= 0.95,
        "false_activations_per_hour": false_rate is not None and false_rate < 1,
        "physical_onset_p95": physical_p95 is not None and physical_p95 <= 250,
        "no_unsafe_restart": unsafe_restarts == 0 and failed_stops == 0,
    }
    for name, passed in gate_conditions.items():
        gates[name] = "NOT_EVALUATED" if not sufficient else "PASS" if passed else "FAIL"
    return {
        "source": document.get("source"), "held_out": document.get("held_out"),
        "sensor_method": sensor_method,
        "device": document.get("device"),
        "feature_verified": feature_verified,
        "max_clock_alignment_error_ms": alignment_error,
        "labeled_strokes": len(labels), "detected_strokes": len(detections),
        "exactly_one_responses": exact_responses, "missed_responses": missed_responses,
        "duplicate_responses": duplicate_responses,
        "false_activation_episodes": false_episodes,
        "negative_labeled_seconds": round(negative_seconds, 3),
        "false_activation_episodes_per_hour": round(false_rate, 3) if false_rate is not None else None,
        "detection_precision": round(precision, 3) if precision is not None else None,
        "detection_recall": round(recall, 3) if recall is not None else None,
        "exactly_one_response_rate": round(exact_rate, 3) if exact_rate is not None else None,
        "physical_onset_from_boundary": _distribution(boundary_to_physical),
        "physical_stop_delay": _distribution(stop_delays),
        "camera_boundary_to_frame": _distribution(camera_latencies),
        "classifier_frame_to_decision": _distribution(classifier_processing),
        "classifier_boundary_to_decision": _distribution(detection_latencies),
        "trigger_decision_to_command": _distribution(decision_to_submit),
        "command_ack": _distribution(command_ack),
        "device_command_to_physical": _distribution(command_to_physical),
        "failed_stops": failed_stops, "unsafe_restarts": unsafe_restarts,
        "ambiguous_physical_assignments": ambiguous_assignments,
        "overlapping_physical_episodes": overlapping_episodes,
        "missing_scenarios": missing,
        "gate_preconditions_unmet": preconditions,
        "gates": gates,
        "session_gate_status": ("NOT_EVALUATED" if not sufficient else
                                "PASS" if all(value == "PASS" for value in gates.values()) else "FAIL"),
        "release_gate_status": "NOT_EVALUATED",
        "limitations": [
            "Physical sensor onsets are assigned to the most recent command in a one-second window.",
            "Overlapping command windows make assignments ambiguous and invalidate release gates.",
            "Human button timing alone cannot establish a 250 ms physical-onset gate.",
        ],
    }


def score_hardware_cohort(documents: list[dict[str, object]]) -> dict[str, object]:
    """Evaluate each physical device/feature independently across varied real sessions."""
    sessions = [score_hardware_session(document) for document in documents]
    groups: dict[tuple[str, int | None], list[tuple[dict, dict]]] = {}
    for document, session in zip(documents, sessions):
        device = document.get("device") or {}
        model = device.get("model") if isinstance(device, dict) else None
        feature = device.get("selected_vibration_feature") if isinstance(device, dict) else None
        key = (model if isinstance(model, str) and model.strip() else "Unspecified model",
               feature if type(feature) is int else None)
        groups.setdefault(key, []).append((document, session))
    compatibility = []
    for (model, feature), group in sorted(groups.items(), key=lambda item: str(item[0])):
        records = [document for document, _ in group]
        session_ids = [record.get("session_id") for record in records]
        testers = {record.get("tester_id") for record in records
                   if isinstance(record.get("tester_id"), str) and record["tester_id"].strip()}
        positions = {record.get("camera_position") for record in records
                     if isinstance(record.get("camera_position"), str) and record["camera_position"].strip()}
        lighting = {record.get("lighting_condition") for record in records
                    if isinstance(record.get("lighting_condition"), str) and record["lighting_condition"].strip()}
        blockers = []
        if model == "Unspecified model":
            blockers.append("Record the exact device model")
        valid_ids = all(isinstance(value, str) and bool(value.strip()) for value in session_ids)
        if len(records) < 3 or not valid_ids or len(set(session_ids)) != len(records):
            blockers.append("Three distinct held-out sessions per device/feature are required")
        if len(testers) < 2:
            blockers.append("At least two consenting testers are required")
        if len(positions) < 2:
            blockers.append("At least two camera positions are required")
        if len(lighting) < 2:
            blockers.append("At least two lighting conditions are required")
        if any(session["session_gate_status"] == "NOT_EVALUATED" for _, session in group):
            blockers.append("Every real session must have complete physical measurements")
        status = ("NOT_EVALUATED" if blockers else
                  "PASS" if all(session["session_gate_status"] == "PASS" for _, session in group)
                  else "FAIL")
        compatibility.append({
            "model": model, "feature_index": feature, "session_count": len(records),
            "distinct_testers": len(testers), "camera_positions": len(positions),
            "lighting_conditions": len(lighting), "release_gate_status": status,
            "availability": "SUPPORTED" if status == "PASS" else "NOT_ENABLED",
            "blockers": blockers,
        })
    status = ("NOT_EVALUATED" if not compatibility or any(
        entry["release_gate_status"] == "NOT_EVALUATED" for entry in compatibility) else
        "PASS" if all(entry["release_gate_status"] == "PASS" for entry in compatibility) else "FAIL")
    return {"release_gate_status": status, "session_count": len(sessions),
            "requires_distinct_held_out_real_sessions_per_device": 3,
            "compatibility": compatibility, "sessions": sessions}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score local numeric-only hardware validation data")
    parser.add_argument("sessions", type=Path, nargs="+",
                        help="JSON sessions with aligned host monotonic timestamps")
    args = parser.parse_args()
    documents = []
    for path in args.sessions:
        with path.open("r", encoding="utf-8") as stream:
            documents.append(json.load(stream))
    print(json.dumps(score_hardware_cohort(documents), indent=2))


if __name__ == "__main__":
    main()
