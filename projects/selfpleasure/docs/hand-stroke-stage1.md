# Hand Stroke mode: Stage 1 baseline and integration contract

Hand Stroke is a **planned, separate mode**. This stage adds measurement and a
device-neutral contract, but no hand tracker, stroke classifier, stroke-to-output
mapping, mode switch, or real-device activation. The current oral-interaction
path, manual tests, patterns, watchdog, and emergency stop are unchanged.

## Existing camera-to-device path

```text
explicit camera start
  -> OpenCV read, resize/mirror (camera worker)
  -> MediaPipe Face Landmarker and mouth geometry
  -> OpenCV marker / ROI tracker
  -> temporal oral interaction estimator
  -> in-process event queue and event bus
  -> explicitly armed automation rule, 3-event debounce, cooldown
  -> safety controller, bounded pattern and watchdog
  -> selected feature on selected simulator / Buttplug device
```

The `frame_id` added to in-memory camera events correlates the worker's stages
with the accepted trigger and first positive output command. The diagnostic
recorder is disabled by default and keeps up to 512 frames' stage names and
`monotonic_ns` timestamps in RAM. It never accepts frames, images, landmarks,
device names, or arbitrary log text. It is not a per-user accuracy metric.
Only the first positive command of a pattern is timed: later pattern steps
still obey the existing deadline but are not included in the acknowledgement
interval. The report gives median, p95, maximum, and sample count. Start a
fresh capture with `POST /api/diagnostics/latency/start`; read
`GET /api/diagnostics/latency`; freeze it with
`POST /api/diagnostics/latency/stop`. No diagnostic records are written to
disk. Run diagnostics only while you intend to expose numeric timing data to
the local browser. The endpoint is loopback-only under the app's existing
host and browser-origin restrictions.

`frame_read_started` is immediately before the blocking `source.read()` call;
`frame_captured` means **`source.read()` has returned**, not sensor exposure.
`face_detected`, `object_detected`, and `oral_decided` mark completion of
their stages. `event_emitted` marks handoff to the main-loop queue after
preview encoding. `trigger_accepted` marks passage through the oral rule's
debounce and validity checks. `command_submitted` is immediately before the
first awaited device call; `command_completed` means that call returned.
It is **not** measured onset of physical motion. `command_failed` covers an
exception, timeout, or cancellation while awaiting that first command.
`hand_detected` and `stroke_decided` are reserved stage names; their counts
remain zero until the separate Hand Stroke pipeline is implemented.

The report also separates frame-read duration, oral-decision-to-event-emission
(including preview encoding), and event-emission-to-trigger-acceptance for the
frame that completes the debounce. It does **not** include the full
three-frame debounce interval in that last quantity. Latency sources not
isolated by the synthetic benchmark include camera exposure and
USB/AVFoundation buffering, MediaPipe's real inference,
OpenCV/CSRT tracker work, JPEG encoding, event-loop scheduling/backpressure,
debounce time across frames, Intiface WebSocket and Bluetooth transport,
device motor onset, and UI preview rendering. The instrumentation measures
capture-return-to-submission but not physical actuation. A bounded ring can
evict old frame traces during long sessions, and the first command timeout
may yield `command_failed` instead of an acknowledgement duration.

## Simulator baseline

Run, without a webcam or hardware connection:

```bash
python -m app.diagnostics.benchmark --samples 3
```

This drives generated black frames, stub face/object observations, the real
oral estimator/event bus/automation/safety path, and `SimulatedDevice`. It
explicitly arms **only that in-process simulator** and attempts shutdown in
`finally`. It does not open Intiface or test Hand Stroke mode. On one Apple
Silicon run, 55 captured synthetic frames yielded three simulated command
acknowledgements: median frame-read **0.042 ms** (p95 **0.066 ms**), median
capture-return-to-command-submission **3.486 ms** (p95 **3.713 ms**), and
median command acknowledgement **0.061 ms** (p95 **0.070 ms**). These are
one-run process measurements, not reliable hardware
latency estimates; repeat on the target machine and compare sample counts.
The benchmark returned zero hand detections and stroke decisions, as expected.

## Versioned vision-to-event boundary

`app/vision/stroke_contract.py` defines immutable, validated v1
`StrokeObservation` and `StrokeEvent`. They carry:

| Field | Meaning |
| --- | --- |
| `schema_version` | Exact contract version (`1`) |
| `timestamp_ns`, `frame_id` | Monotonic observation time and numeric trace correlation |
| `hand_position` | Optional calibrated 0–1 position along the fixed object's movement axis |
| `direction` | `FORWARD`, `REVERSE`, `STILL`, or `UNKNOWN` |
| `speed`, `travel` | Nonnegative axis lengths/second, and axis lengths since stroke start |
| `tracking_confidence` | Finite 0–1 heuristic quality, not a probability of contact |
| `stroke_id` | Positive ID for one stroke, absent only if not yet established/lost |
| `kind` (event) | `stroke_started`, `stroke_updated`, `stroke_completed`, or `tracking_lost` |

No Buttplug command, output feature, intensity, or device identifier exists
in the vision contract. The coordinate axis must be calibrated for the
stationary object; without reliable hand/object tracking, an observation
should carry unknown direction and low confidence, and a tracking-loss event
should revoke authorization. No stroke event currently enters the automation
controller.

## Exact next-stage integration points

1. Add a separate hand tracker under `app/vision/` with injectable detector
   and calibration. Run it after capture in `CameraService._run` only when a
   user-selected Hand Stroke mode is active. Mark `HAND_DETECTED` when the
   tracker completes; keep oral mode's estimator untouched.
2. Add a temporal stroke estimator that emits the v1 observations/events and
   marks `STROKE_DECIDED`. Test reversal, stationary hold, occlusion,
   distractors, handedness, and camera-position changes with numeric
   trajectories before any hardware path exists.
3. Route stroke events through the existing local event bus (`app/events.py`)
   with a distinct topic/handler. Add a mode-specific trigger/rule in
   `app/triggers/`—do not reinterpret oral `interaction_*` topics as strokes.
4. Add a bounded output mapper **after** the event boundary. The mapper must
   require explicit arm, fresh/high-quality tracking, selected device and
   selected output feature, per-command limits/deadlines, and all existing
   stop/disarm/watchdog paths. Simulator tests and measured latency precede
   any opt-in real-device verification.

Neither a simulator acknowledgement nor a webcam frame timestamp establishes
one-to-one physical mirroring. That claim requires measured end-to-end onset
and jitter, plus controlled false-activation and stop-latency validation on
specific hardware.
