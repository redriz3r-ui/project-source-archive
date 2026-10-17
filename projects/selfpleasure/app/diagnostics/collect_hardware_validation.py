"""Opt-in local numeric trace collector; read-only and no device commands.

This captures diagnostic and stroke event rings before they roll over. The
external physical sensor and independently labeled boundaries remain separate.
"""

import argparse
import json
import os
from pathlib import Path
import time
from urllib.request import urlopen
from uuid import uuid4

from app.paths import private_data_path

DEFAULT_DIRECTORY = private_data_path("evaluation-data", "hardware")
MAX_DURATION_SECONDS = 7200
ALLOWED_STAGES = frozenset({
    "frame_read_started", "frame_captured", "hand_detected", "object_detected",
    "stroke_decided", "event_emitted", "trigger_accepted", "command_submitted",
    "command_completed", "command_failed",
})
ALLOWED_KINDS = frozenset({"stroke_started", "stroke_updated", "stroke_completed", "tracking_lost"})


def new_records(traces: dict, events: list[dict], seen: dict[str, set]) -> list[dict]:
    """Copy only allowlisted numeric/string fields; deduplicate rolling rings."""
    output = []
    for trace in traces.get("traces", []):
        frame_id = trace.get("frame_id")
        if type(frame_id) is not int or frame_id < 1:
            continue
        stamps = trace.get("timestamps_ns", {})
        if not isinstance(stamps, dict):
            continue
        allowed = {key: value for key, value in stamps.items()
                   if key in ALLOWED_STAGES and type(value) is int and value >= 0}
        # A frame can gain command timestamps after its first poll: emit updates.
        signature = (frame_id, tuple(sorted(allowed.items())))
        if signature not in seen["frames"]:
            seen["frames"].add(signature)
            output.append({"type": "frame_trace", "frame_id": frame_id,
                           "timestamps_ns": allowed})
    for stop in traces.get("stop_traces", []):
        stop_id = stop.get("stop_id")
        if type(stop_id) is not int or stop_id < 1:
            continue
        signature = (stop_id, stop.get("completed_ns"))
        if signature in seen["stops"]:
            continue
        seen["stops"].add(signature)
        if (type(stop.get("requested_ns")) is int and stop["requested_ns"] >= 0
                and (stop.get("completed_ns") is None or
                     type(stop["completed_ns"]) is int and stop["completed_ns"] >= 0)):
            output.append({"type": "stop_trace", "stop_id": stop_id,
                           "reason": str(stop.get("reason", "unknown"))[:32],
                           "requested_ns": stop["requested_ns"],
                           "completed_ns": stop.get("completed_ns")})
    for event in events:
        kind, frame_id, stroke_id = event.get("kind"), event.get("frame_id"), event.get("stroke_id")
        timestamp = event.get("timestamp_ns")
        if (kind not in ALLOWED_KINDS or type(frame_id) is not int or frame_id < 1
                or type(timestamp) is not int or timestamp < 0):
            continue
        signature = (frame_id, kind, stroke_id)
        if signature in seen["events"]:
            continue
        seen["events"].add(signature)
        item = {"type": "stroke_event", "kind": kind, "frame_id": frame_id,
                "timestamp_ns": timestamp,
                "stroke_id": stroke_id if type(stroke_id) is int and stroke_id > 0 else None}
        for key in ("hand_position", "speed", "travel", "tracking_confidence"):
            value = event.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                item[key] = value
        output.append(item)
    return output


def _read_local(path: str) -> object:
    with urlopen(f"http://127.0.0.1:8000{path}", timeout=2) as response:
        return json.load(response)


def collect(duration: float, interval: float, directory: Path = DEFAULT_DIRECTORY) -> Path:
    if not 0 < duration <= MAX_DURATION_SECONDS or not 0.1 <= interval <= 2:
        raise ValueError("Duration must be at most two hours; poll interval must be 0.1–2 seconds")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / f"numeric-traces-{uuid4().hex}.jsonl"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    seen: dict[str, set] = {"frames": set(), "stops": set(), "events": set()}
    deadline = time.monotonic() + duration
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            while time.monotonic() < deadline:
                traces = _read_local("/api/diagnostics/latency/traces")
                events = _read_local("/api/hand/events")
                for item in new_records(traces, events, seen):
                    stream.write(json.dumps(item, separators=(",", ":")) + "\n")
                stream.flush()
                time.sleep(interval)
    except KeyboardInterrupt:
        pass
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect local numeric diagnostics only")
    parser.add_argument("--consent", action="store_true", help="Explicit consent to save numeric logs")
    parser.add_argument("--duration-seconds", type=float, default=60)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    args = parser.parse_args()
    if not args.consent:
        parser.error("--consent is required before any file is created")
    path = collect(args.duration_seconds, args.poll_seconds)
    print(path)


if __name__ == "__main__":
    main()
