# Stage 5 — supervised hardware validation protocol

Status: **prepared, not executed**. The managed Hand session now has an
explicit, tightly bounded real-device pilot path; the earlier general
simulator-only hand guard remains on unmanaged endpoints. No physical response,
stop delay, or release gate has been measured. Do not start a hardware session
until the adult user is present, explicitly opts in, confirms a short manual
vibration/stop preflight, and can use the device's physical power-off control.
This protocol uses a harmless marked prop, not intimate footage.

## Preconditions and read-only feature check

1. Run the full test suite (`.venv/bin/python -m pytest -q`) and resolve any
   failures. Start the app with camera off and automation disarmed.
2. With the device physically accessible, start Intiface Central locally and
   confirm that it reports the expected device. Use `GET /api/status` and
   `GET /api/devices` (or the Device Settings page) to read the selected device
   ID and its **advertised vibration feature indexes**. Record the exact
   feature index in the session document. This step sends no output command.

   ```bash
   curl http://127.0.0.1:8000/api/status
   curl http://127.0.0.1:8000/api/devices
   ```
3. Use the existing manual control only for a separately authorized, brief
   20%/0.18-second preflight if the user deliberately enables and presses the
   test button. Keep physical power-off within reach. Verify the correct
   feature and that it physically stops. If it does not, end the session.
4. The managed Hand session's real pilot requires an explicit selected
   advertised vibration feature, two preflight confirmations, and a deliberate
   Arm. It is fixed to one crisp response per completed stroke at at most 20%
   for 0.12 seconds with at least 0.5 seconds rest. Follow movement and
   unmanaged Hand response endpoints continue to reject real-device output.
   Keep this a short, supervised validation trial—not an everyday session.

## Numeric timing instrumentation

The app's opt-in RAM-only diagnostics can be started with
`POST /api/diagnostics/latency/start`. `GET /api/diagnostics/latency/traces`
returns frame-ID-keyed monotonic nanosecond timestamps for frame capture,
stroke decision, trigger acceptance, command submission, and command
acknowledgement, plus numeric stop-request/completion traces with fixed
reason codes. `GET /api/hand/events` returns recent numeric stroke IDs,
frame IDs and timestamps. These rings are bounded and can overwrite old data;
the read-only logger below can collect them during any longer test after
explicit consent. It sends no device-control requests and stores only
allowlisted numeric records under ignored `evaluation-data/hardware/` with
owner-only file permissions. It emits an updated frame record when later
command timestamps arrive; retain the latest record for each frame ID when
joining data. No frames or video are returned by these endpoints. Command
acknowledgement is **not** proof of physical movement.

```bash
curl -X POST http://127.0.0.1:8000/api/diagnostics/latency/start
python -m app.diagnostics.collect_hardware_validation --consent --duration-seconds 3600
```

Review and delete the numeric JSONL file after use if it is not needed.
The scorer below accepts a reviewed, joined session JSON, not raw JSONL;
joining must preserve stroke IDs and frame IDs, combine the independent
boundary/sensor timestamps, and resolve any ambiguous associations.

For physical onset and cessation, attach a non-intimate accelerometer or
vibration sensor externally to the device housing, without interfering with
its controls or intended use. Timestamp sensor threshold crossings on the
same host monotonic clock as the app. If a separate acquisition clock is
unavoidable, align it with a measured maximum error of at most 5 ms before
importing data. Confirm sensor response to a known short manual pulse and
that it distinguishes true motor activity from hand movement of the housing.
For ground-truth stroke boundaries, use a separate position/optical gate on
the **harmless prop** rather than a human keypress: human reaction time cannot
establish a 250 ms onset target. Manually label intent and scenario after
each trial; mark uncertain trials separately and exclude them from gates.
Do not record or upload camera frames, audio, or intimate footage.

## Supervised test matrix

Run at most one selected vibration feature, initially 20% and 0.18 seconds.
Each activation must be one bounded command with the normal watchdog, and
the user must rearm explicitly after any failure or Emergency Stop. Do not
increase intensity to meet a timing gate. Start with the simulator, then
perform a small supervised real-device pilot only after its explicit enable
path has been implemented and reviewed. For each held-out session, collect:

- At least 20 labeled intentional traversals each at slow, normal, and fast
  speeds, with pauses. Record one numeric boundary per intended stroke.
- At least one hour of negative-labeled observation across rest, pauses,
  partial passes, marker occlusion, and normal prop handling. This is needed
  to make a “fewer than one false activation episode per hour” claim.
- While output is observably active, separately test marker occlusion,
  camera stop, Intiface disconnect, disarm, and Emergency Stop. Record the
  stop-request time, physical motor-off time, and a no-restart observation
  window. Test the device's physical power-off independently. Stop the
  session if any software stop fails or if output resumes without rearming.

Collect at least three distinct held-out real sessions with varied lighting
and camera position. Keep test and tuning sessions separate. Do not count
synthetic fixture results as measured real-device performance.

## Session format and report

Put local numeric session JSON under ignored `evaluation-data/hardware/` only
after explicit consent. Each file uses `schema_version: 1`,
`clock_domain: "host_monotonic_ns"`, `source: "real_device"`, a unique
`session_id`, pseudonymous `tester_id`, `camera_position`,
`lighting_condition`, `held_out: true`, the verified Intiface device ID,
exact `device.model` and selected feature, and the sensor alignment error. Arrays:

- `labels`: `{id, boundary_ns, scenario}` for slow/normal/fast strokes.
- `detections`: `{stroke_id, frame_captured_ns, classifier_ns,
  command_submitted_ns, command_ack_ns}`. The command fields may be null if
  the classifier emitted a stroke but the rule safely dropped it.
- `physical_episodes`: `{onset_ns, off_ns}` from the external sensor.
- `negative_intervals`: `{start_ns, end_ns, scenario}` for pause, occlusion,
  or other negative-labeled observation.
- `stop_checks`: `{scenario, request_ns, observation_end_ns,
  output_active_at_request}`. No deliberate rearm may occur inside this
  window.

Run the offline analyzer without connecting to Intiface:

```bash
cd "/path/to/user/Documents/01 Active Projects/Software & Experiments/SelfPleasure"
source .venv/bin/activate
python -m app.diagnostics.hardware_validation evaluation-data/hardware/session-1.json evaluation-data/hardware/session-2.json evaluation-data/hardware/session-3.json
```

It reports, per session, precision, recall, exactly-one/missed/duplicate
responses, false physical activations per negative-labeled hour, median and
95th-percentile physical onset and stop delay, and separate camera,
classifier, trigger/command, and device-command-to-physical components.
Unmatched or ambiguous physical episodes are surfaced. Release gates remain
`NOT_EVALUATED` until three distinct complete held-out real sessions per
device/feature exist, including at least two testers, two camera positions,
and two lighting conditions.
Each must meet: at least 95% exactly-one responses; at least 95% classifier
precision and recall; fewer than one false activation episode per hour;
physical onset p95 at most 250 ms from the independently measured boundary;
and no failed stop or unsafe restart. A missed stop, unsafe restart, or failed
gate means **not ready**; identify the failing stage and mark that camera/
device configuration unsupported until corrected and retested.

The scorer is descriptive, not a safety certification. Its assignment of
sensor onsets to recent commands is ambiguous if command windows overlap;
such a session cannot satisfy the gates. Labels, sensor thresholds, clock
alignment, and feature metadata must be audited before accepting a report.
