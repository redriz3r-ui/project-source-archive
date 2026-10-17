# SelfPleasure

SelfPleasure is an open-source, local-first application for consenting adults.
The local dashboard presents camera, device, detection, and rule controls in one
dashboard. The app always starts disarmed, with camera and Intiface disconnected.
Manual device control remains available separately.

**Release status:** development build, not consumer-ready. **Real-device
output is disabled by default after a 0.1-second manual preflight failed to
stop physically.** A temporary, off-body manual bench mode is described below;
it does not unlock camera automation. The Hand Stroke
simulator remains available. No physical hand-response configuration has passed
the supervised release gates. See the [Stage 7 audit](docs/release-readiness.md),
[compatibility matrix](docs/compatibility.md), and [privacy policy](docs/privacy-policy.md).

Two subsequent supervised, off-body 20% diagnostics on 2026-10-15 were observed
to stop physically, including one interrupted by Emergency Stop. An earlier
10% diagnostic produced no observable output. These tests do not explain the
original failure or verify physical stop reliability; normal-mode real-device
output and all real-device automation remain locked. Do not intentionally disconnect Intiface during an active
output test, since software may then be unable to issue a stop command.

Manual-test duration now uses an absolute deadline starting when the test is
scheduled, with a separate software deadline task that attempts to stop a
delayed command. This reduces a timing gap but is not a hardware-enforced
timer: a crash, transport failure, or device fault can still defeat software
stop. Keep the device's physical power control available.

## Requirements and setup

- macOS on Apple Silicon, Python 3.13
- Intiface Central with its WebSocket server started on `127.0.0.1:12345`
  only if testing a real device
- The built-in webcam and macOS camera permission for the app running Python

```bash
cd "/path/to/user/Documents/01 Active Projects/Software & Experiments/SelfPleasure"
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m app.vision.download_model
python -m app.vision.download_hand_model
```

This project uses the official [`buttplug` 1.0.0](https://github.com/buttplugio/buttplug-py)
Python client for protocol v4. The adapter uses its verified `ButtplugClient`,
`DeviceOutputCommand`, `OutputType.VIBRATE`, `device.has_output()`,
`device.run_output()`, and `device.stop()` APIs. The Face Landmarker model is
downloaded once from [Google's official model bundle](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/index),
verified by SHA-256, and kept in the ignored `.models/` directory. Camera
inference uses only local files and runs only after **Start Camera**.
The separate Hand Landmarker bundle is checksum-verified into the same ignored
`.models/` directory. Neither model is fetched while the app is running.

## Start the app

```bash
cd "/path/to/user/Documents/01 Active Projects/Software & Experiments/SelfPleasure"
source .venv/bin/activate
python -m app.main
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the one-page Hand
session: camera preview, calibration, device source and feature, simulator
response choices, session controls, and (when explicitly started in bench mode)
off-body manual tests. Source is a radio choice; the remaining options use
dropdowns. Older detailed pages remain at their existing URLs for diagnostics.
The app listens on loopback only.
It opens neither the camera nor Intiface on startup.

### Temporary off-body manual bench mode

For supervised diagnostics only, with the device off-body and its physical
power-off control within reach, stop the normal server and start:

```bash
python -m app.main --off-body-manual-bench
```

This flag applies only to the current server process. On the
[one-page session](http://127.0.0.1:8000/), choose **Intiface device**, connect
to local Intiface,
select the exact device and advertised vibration feature, and confirm the
off-body condition. Each test needs a separate **Enable one test** action.
The server caps real manual commands at 20% and 0.5 seconds and attempts a
stop at the deadline. The page keeps **Stop** and **Emergency Stop** available.
Check that output physically stopped after every test; if it did not, use the
device's power control immediately. A software acknowledgement is not proof
of a physical stop. Hand and oral real-device automation remain disabled in
this mode. Restart without the flag to restore the normal full lockout.

An **internal, ad-hoc-signed macOS app** can be built for packaging tests. It
bundles Python and the two local model files, so its user does not need Python
or Terminal to open the dashboard. It is **not** a notarized consumer release:

```bash
source .venv/bin/activate
python -m pip install -e ".[release]"
python -m app.vision.download_model
python -m app.vision.download_hand_model
PYINSTALLER_CONFIG_DIR="$(pwd)/build/pyinstaller-cache" \
  python -m PyInstaller --noconfirm packaging/SelfPleasure.spec
```

The development artifact is `dist/SelfPleasure.app`. Do not distribute it or
ask users to bypass Gatekeeper. A Developer ID identity, notarization profile,
clean-machine tests, and the physical safety gates are still missing. The
[first-run draft](docs/first-run.md) and [removal guide](docs/uninstall.md)
describe the intended flow and current data locations.

## Hand Stroke camera mode and supervised pilot

For a guided solo flow, open the [one-page session](http://127.0.0.1:8000/).
**Start hand camera** prepares local input without device output. Choose the
simulator and its vibration feature,
mark the prop's base and movement-axis end, and wait for **Tracking ready**.
One **Arm** click performs the no-output rule preview and then arms the
simulator feature. Real-device camera arming remains locked because the
physical stop failure is unresolved. Response choices are dropdowns on the
same page. Pause stops
output but keeps the camera on; Disarm stops output; Finish stops output and
releases the camera. Emergency Stop stays visible in the header and is also
available with Escape. The page clearly separates **armed** (may respond)
from **active** (a pulse is running). If the page disappears, a short server
lease disarms and closes the camera. It does not rearm or reconnect after a
fault. No footage or telemetry is saved by default.

Choose **Once after each completed stroke** for one bounded envelope per
accepted stroke, or **Follow movement** for short, rate-limited pulses from
fresh movement updates. The latter is not continuous output: busy or stale
updates are dropped. Choose Gentle, Crisp, or Ramp as the response feel. The
intensity slider sets a ceiling, not a guaranteed strength. Follow mode limits
each pulse to 0.12 seconds and requires at least 0.08 seconds between pulses;
the one-response mode retains its 0.5-second/0.25-second limits. See
[Stage 6 session notes](docs/hand-stroke-stage6.md) for the usability test
script and remaining validation work. **Follow movement remains simulator-only.**
The previous real-device pilot is suspended after the failed physical stop.
Its proposed limits were one crisp response per stroke, at most 20% for 0.12
seconds with at least 0.5 seconds between responses; these limits did not
guarantee a physical stop. No real device is approved for use until the stop
failure is understood and independently validated. Never assume a non-vibration
capability is interchangeable with vibration.

The Hand session's simulator deadline check now counts an acknowledged pulse
as completed when its deadline stop succeeds, instead of falsely entering
`ERROR` solely because the watchdog reached the deadline first. A command
that never acknowledges, a failed stop, or a tracking fault still blocks
further responses. Automated coverage includes ten sequential simulator
strokes and a forced deadline-stop race. This software fix does **not**
validate physical stop behavior or unlock real camera automation.

Open [http://127.0.0.1:8000/hand](http://127.0.0.1:8000/hand) and press
**Start Hand Camera**. This mode uses the installed MediaPipe 1.1.0 Hand
Landmarker in VIDEO mode on the current frame in the existing camera worker.
It never requires a face. The legacy hand-response controls below drive
**only a selected simulated device**. The separate managed Hand session offers
the bounded supervised real-device pilot described above. The
oral and Hand Stroke modes are separate; switching requires the camera to be
stopped. The app still starts with camera off and automation disarmed, and
oral automation cannot arm while Hand Stroke mode is running.

Use a harmless, mostly stationary prop. Click **Click base**, then the base
in the preview; click **Click axis end**, then a point farther along the
object's movement axis. Press **Save numeric axis**. The hand position shown
is its palm-center projection along that axis, clamped to 0–100%. It is not
a stroke event, penetration depth, or proof of contact. The optional colored
marker can anchor the base: put it on a **non-contact** portion, click the
base, press **Calibrate marker color at base**, check **Anchor base**, then
save. Marker anchoring compensates for modest image translation; missing
marker, large displacement, or two plausible hands produces a tracking-loss
state. Fixed-axis mode cannot compensate for camera/object movement. Axis
geometry is stored locally in ignored `config.local.hand-stroke.json`; no
frame or video is saved or uploaded.

The live preview shows the axis, detected hand landmarks, normalized position,
tracking-quality heuristic, loss state, and FPS. Toggle overlays if desired.
If the model is missing, run `python -m app.vision.download_hand_model` while
online, then restart the camera. The official model download is only a setup
step; normal operation is offline. See [Stage 2 notes](docs/hand-stroke-stage2.md)
for measured performance, failure cases, and what remains before mirroring.

### Stroke recognition and local evaluation (Stage 3)

Hand mode now emits versioned numeric `stroke_started`, `stroke_updated`,
`stroke_completed`, and `tracking_lost` events. A completed stroke means a
single sufficiently long, plausible-speed traversal along the calibrated
axis that reaches an endpoint or reverses consistently. A small shake,
partial movement, implausible jump, ambiguous second hand, missing marker,
low tracking quality, or out-of-frame hand must not produce a completed
stroke. The current stroke ID, direction, travel, and recent events appear
on the [Hand tracking page](http://127.0.0.1:8000/hand). The stroke event bus
uses separate topics from oral interaction. A separate hand-response subscriber
consumes only fresh, post-arm completed strokes. It does not use movement
updates as commands.

### Simulator-only one-to-one mapping (Stage 4)

On the [Hand tracking page](http://127.0.0.1:8000/hand), start the hand
camera, calibrate a harmless prop, and wait until tracking reads `TRACKED`.
Press **Create simulator**, then **Arm simulated responses**. One completed
stroke that *started after arming* sends one bounded pulse to the simulator's
selected vibration feature. The default is 20% intensity for 0.18 seconds,
with a 0.3-second cooldown. The server caps intensity at 30%, duration at
0.5 seconds, and cooldown at a minimum of 0.25 seconds for this rule. Busy,
duplicate, stale, out-of-order, and pre-arm strokes are dropped, not queued.
The optional experimental motion-shaped mode scales that **single** pulse's
intensity from completed-stroke speed and travel. Stage 6's separate Follow
Movement mode can use fresh `stroke_updated` events for short bounded pulses;
neither mode sends indefinite output.

The page shows strokes seen while armed, pending/completed and dropped
responses, and mean simulator event-to-command acknowledgement latency. This
latency is **not physical haptic onset**. Disarm, tracking loss, camera stop,
device loss, application shutdown, and Emergency Stop revoke authorization
and attempt to stop output. The independent safety watchdog remains active.
The application always starts disarmed; camera and simulator must be enabled
explicitly. Evaluation mode cannot run while hand responses are armed.
**This stage has not activated real hardware or validated one-to-one
performance with a physical device.**

### Supervised hardware validation preparation (Stage 5)

The [Stage 5 protocol](docs/hand-stroke-stage5.md) describes the read-only
Intiface feature check, user-present safety preflight, external non-intimate
sensor instrumentation, controlled test matrix, and proposed release gates.
The offline `python -m app.diagnostics.hardware_validation` scorer accepts
only numeric timestamps and never connects to a device. Raw in-memory
diagnostic timestamps can be read at `/api/diagnostics/latency/traces` after
explicitly starting diagnostics; the opt-in, read-only
`python -m app.diagnostics.collect_hardware_validation --consent` command can
save bounded numeric logs locally. Real-device Hand Stroke activation remains
disabled; physical timing and release gates are **not evaluated** until a
supervised real test is explicitly authorized and performed.

For real camera-only evaluation with a harmless prop, open
[Stroke evaluation](http://127.0.0.1:8000/hand/evaluate). Start Hand Camera,
calibrate the axis, explicitly consent to temporary numeric collection, then
press **Start evaluation**. Choose **Testing strokes** before deliberate
traversals and press **Mark one intended stroke** when each finishes. Choose
**No strokes** while testing rest, shakes, or false positives; use
**Uncertain** when the action cannot be labeled reliably. Press **Stop &
review** to see stroke-count accuracy, precision, recall, false detections
per negative-labeled hour, and signed detection latencies. Review the entire
numeric draft before separately consenting to save, or discard it. Saved
sessions are in ignored `evaluation-data/strokes/` and can be reviewed or
deleted from the page. Neither collection nor saving records images or video;
shutdown discards unsaved drafts.

Labels are timed by button presses, not synchronized ground-truth sensors;
the matching window is one second. Results are descriptive for that session
and cannot establish one-to-one accuracy without controlled real labels.
See [Stage 3 notes](docs/hand-stroke-stage3.md) for thresholds, measured
camera-loop FPS, tests, and known failure cases.

## Dashboard and rules

The dashboard shows an in-memory live preview, device connection and selected
output, detection state, enabled rule, and large Arm/Disarm/Emergency Stop
controls. **Device Control** connects and selects hardware and its vibration
feature; manual tests still require a separate one-shot enable. **Visual
Interaction** selects a camera input (index 0 is usually the built-in camera),
calibrates the mouth/marker or manual ROI, tunes the detection zone and
sensitivity, and toggles overlays. Camera input can only change while stopped.

On **Trigger Rules**, create a local rule, select its output feature and one
of four bounded patterns, set intensity, maximum pulse, cooldown, and minimum
heuristic score, then enable it. **Preview pattern** draws a timeline only;
it sends no device command and does not arm anything. The patterns are Short
Pulse (the original behavior), Gentle Pulse (three soft bursts), Rhythmic
Pulse (four separated bursts), and Gradual Ramp (four increasing steps). At
most one rule can be enabled. Enabling is **not** arming: the dashboard Arm
button also requires a running camera and a selected device with that
vibration feature. Only `INTERACTION_ACTIVE → VIBRATE` is supported; arbitrary
actions and unknown patterns are rejected.
Rules are stored in ignored `config.local.rules.json`; calibration remains in
ignored `config.local.json`. No frames or video are stored. If the rule file is
invalid, startup remains available but rules fail closed until that file is
repaired. Do not delete it without making a backup if its contents matter.

## Camera-to-device automation

Test with the simulator first. On **Trigger Rules**, select the simulator,
create and enable a bounded-pattern rule. On **Visual Interaction**, start the camera, calibrate the
mouth and object tracker, and verify that brief passes do not reach
`INTERACTION_ACTIVE`. Choose the specific vibration feature, leave intensity
at 20%, maximum activation at 2 seconds, and cooldown at 1 second. Press
**Arm Automation** only when ready. Sustained valid detections must survive an
additional three-event debounce before a pulse begins. Each pulse has a fixed
deadline; a separate watchdog stops it if valid updates cease for 350 ms or the
deadline passes. Another pulse needs fresh valid detections after cooldown.

The automation state machine is `DISARMED`, `ARMED`, `ACTIVE`, `COOLDOWN`,
`EMERGENCY_STOP`, or `ERROR`. Tracking loss and camera stop disarm; device
disconnect enters `ERROR`. Disarm, Stop, Emergency Stop, and app shutdown all
attempt to stop output. An error or disconnect never silently rearms the app.
The local endpoints are `GET /api/automation/status`,
`POST /api/automation/arm`, and `POST /api/automation/disarm`. The dashboard
arms the enabled rule by ID; the vision settings page can also arm a directly
configured rule. Server-side limits cap intensity at 50%, each pattern at 2 seconds, and
cooldown at no less than 0.5 seconds. The score is a heuristic, not a
probability of contact.

### Optional guided session (prototype)

On the dashboard, check **Guided session** before arming to run one finite
sequence using the enabled rule's selected device and vibration feature. Set
1–20 opening and middle pulses; optionally check **Include buildup phase**
and set 1–20 buildup pulses. The total is capped at 40. The opening uses Gentle
Pulse at half the rule intensity, the middle uses Rhythmic Pulse at three
quarters, and the optional buildup uses Gradual Ramp up to (never above) the
rule intensity. This is a predetermined pacing sequence, **not** an estimate
of arousal or an orgasm detector. It is off by default and settings are chosen
again each time the app starts.

Every pulse still requires fresh sustained interaction evidence, uses the
existing maximum 2-second activation and cooldown, and ends with a stop.
Interrupted pulses do not advance the sequence. The session automatically
disarms after its final pulse; ending the interaction stops output, while
tracking loss, camera stop, device loss, disarm, Emergency Stop, and shutdown
retain their existing fail-closed behavior. Test with the simulator first.
The session is an early experience prototype, not a validated route to a
particular outcome.

Each pattern is a fixed set of feature-specific vibration commands and stop
intervals within one deadline. Every step stays at or below the rule's
intensity limit. A generation guard prevents later pattern steps after a stop,
and the running task attempts a final stop even if cancelled or timed out.
The independent watchdog still requires fresh valid vision events; the next
pattern after cooldown requires a fresh three-event debounce. The preview API
is `GET /api/patterns/preview?pattern=GENTLE_PULSE&intensity=0.2&duration=1`.
It returns only numeric steps and never addresses hardware. Existing saved
`SHORT_PULSE` rules remain valid.

Only after the simulator behaves as expected, test a real device: verify it
is detected in Intiface Central, connect and select it in **Device Control**,
start and calibrate the camera, select the desired vibration feature, then arm
at or below the default 20%/2-second limits. Keep the device's physical power-off
control immediately accessible. First verify a brief pass does nothing;
then perform one sustained recognized interaction and confirm output stops on
ending it, hiding the marker, or pressing **Disarm**. Begin with Short Pulse,
then try one new pattern at a time. Press **Emergency Stop** if anything is
unexpected. Software cannot guarantee a stop after a computer crash,
Bluetooth failure, or a device command that completes after the connection
fails; the physical power control is the ultimate fallback. Never test while
you cannot immediately reach it.

## Face tracking and interaction calibration

1. Open [http://127.0.0.1:8000/camera](http://127.0.0.1:8000/camera).
2. Press **Start Camera**. macOS may ask the application that launched Python
   (usually Terminal) for camera access. Approve it. If you previously denied
   access, open **Apple menu → System Settings → Privacy & Security → Camera**
   and enable access for that application, then restart the app. See
   [Apple's camera access guide](https://support.apple.com/guide/mac-help/control-access-to-the-camera-on-mac-mchlf6d108da/mac).
3. Face the built-in webcam in even light. The page should show a mirrored live
   preview, **Face detected: Yes**, **Mouth detected: Yes**, mouth X/Y position
   as percentages of the image, a mouth openness ratio, and current FPS.
4. Open/close your mouth or move your head slightly. The position, mouth
   region, openness, and tracking quality should update. Toggle **Show tracking
   overlays** to inspect the visual overlay.
5. Use the calibration wizard on the page:
   - Capture your relaxed mouth as a baseline while your face is visible.
   - Put a distinctive colored marker on a **non-contact** portion of the
     handheld object (for example, its base). Click the marker in the mirrored
     preview. The app samples its color from the latest frame in memory.
   - If color tracking is unreliable, select **Manual object rectangle (CSRT)**
     and drag a rectangle around the object. Redraw it if tracking is lost.
   - Adjust the near zone in mouth widths and sensitivity. Press **Save
     calibration**. Try different camera positions and observe the state log.
6. Move the tracked object toward and away from your mouth. A brief pass may
   show `POSSIBLE_INTERACTION`; only sustained nearby movement can reach
   `INTERACTION_ACTIVE`. Moving the object away can yield
   `INTERACTION_ENDED`. Occlusion or unreliable tracking yields
   `TRACKING_LOST`.
7. Press **Stop Camera**. The worker releases the webcam and clears the preview.
   Quitting the app also stops capture.

The webcam defaults to device index 0, 640×480 pixels, and a 24 FPS target.
If index 0 is not the desired camera, choose another index in Vision Settings
while capture is stopped.
Actual FPS depends on the Mac and lighting. The mouth openness value is the
inner-lip gap divided by mouth width, so it is an estimate rather than a
calibrated physical measurement.

Calibration is stored in the ignored `config.local.json` file as numeric
thresholds, marker hue, and optional region coordinates. No camera frames or
screenshots are saved. The state-change event log is held in memory for the
current camera session and contains timestamps, normalized mouth/object
positions, state, and an estimated score. Consumers can read
`GET /api/interaction/events?after=<sequence>` or subscribe to
`GET /api/interaction/events/stream` (server-sent events). An in-process event
bus separately carries `interaction_started`, `interaction_continued`,
`interaction_ended`, `tracking_lost`, and `camera_stopped` signals to the
automation controller. The vision module has no Buttplug dependency.

States are `NO_FACE`, `NO_OBJECT`, `OBJECT_VISIBLE`, `OBJECT_APPROACHING`,
`POSSIBLE_INTERACTION`, `INTERACTION_ACTIVE`, `INTERACTION_ENDED`, and
`TRACKING_LOST`. The detection score and face tracking quality are heuristics,
not statistically calibrated probabilities. Neither proximity nor this state
machine proves oral contact or a particular physical action.

## Verify Intiface and make one short manual test

1. Open Intiface Central, start its server, and verify your device appears in
   its device list.
2. In SelfPleasure, open **Device Control** and press **Connect to Intiface**.
3. Press **Scan for devices** if the device is not listed. The scan takes about
   three seconds. Check connection status and the device's reported outputs.
4. Select the device. **Test Vibration** remains unavailable if Intiface does
   not report a `Vibrate` output.
5. Leave intensity at **20%** and duration at **1 second**. Press **Enable one
   test**, then **Test Vibration**. The enable action is consumed by that test.
6. The controller sends a stop command when the duration ends. Press **Stop**
   or **Emergency Stop** at any point to stop immediately. Emergency stop
   latches until you deliberately enable another test.

Use a simulated device through Trigger Rules or `POST /api/devices/simulated`
when hardware is unavailable. Then select it and follow the same enable/test
steps. The simulator never connects to hardware.

If the web page is unavailable, use a separate Terminal window to send an
independent stop command directly to Intiface Central:

```bash
cd "/path/to/user/Documents/01 Active Projects/Software & Experiments/SelfPleasure"
source .venv/bin/activate
python -m app.safety.emergency_stop
```

If Intiface itself disconnects, use its own emergency stop or the device's
physical power control. A networked stop cannot be confirmed after its
connection is lost.

## Limits and safety behavior

- A device must be selected and one test explicitly enabled before each run.
- Default intensity is 20%; the configured maximum is 50%.
- Default duration is 1 second; the configured maximum is 5 seconds.
- Intensity and duration are validated by the server as well as the UI.
- Overlapping tests are rejected. Stop and emergency stop cancel an active
  timer and issue stop commands. Command acknowledgement and stop attempts have
  timeouts. The test task also attempts `device.stop()` in `finally`.
- Device removal and server disconnect disarm and cancel the test. Application
  shutdown attempts to stop all registered devices and disconnects Intiface.
- Intiface connection is restricted to a loopback `ws://` address; the web
  server binds to `127.0.0.1` and rejects foreign origins for control requests.
- Webcam capture begins only after **Start Camera**. Frames and JPEG preview
  buffers stay in memory; no recording, screenshot, frame logging, or upload
  is performed. Stopping and application shutdown release the camera.
- Camera failures revoke automation authorization. Vision events are consumed
  only by the explicitly armed automation controller.

Settings are defined in `app/config.py`. Increase limits only after reviewing
the safety behavior and testing the specific hardware.

## Tests

```bash
cd "/path/to/user/Documents/01 Active Projects/Software & Experiments/SelfPleasure"
source .venv/bin/activate
python -m pytest
```

Tests inject a fake Buttplug client and mock camera source. They cover
capability gating, default disarming, command timeout, cancellation, emergency
stop, disconnection, mouth geometry, marker and ROI tracking, calibration,
temporal interaction trajectories, camera lifecycle, automation activation,
cooldown, tracking and camera loss, device disconnection, emergency stop,
delayed commands, shutdown, and the local API without activating hardware or
opening a real webcam. Stage 6 tests also cover rule CRUD/limits, local rule
persistence, invalid-file fail-closed behavior, camera selection, origin
rejection, and blocked manual commands while automation is armed.
Pattern tests cover each envelope, visual-only preview, timing bounds,
cancellation, tracking/camera loss, disconnect, emergency stop, delayed
commands, and a cancellation-resistant late command using simulated devices.
Evaluation tests cover explicit collection/save consent, unsaved-draft discard,
numeric-only storage, deletion, origin rejection, activation blocking,
camera-event capture with a mock source, and labeled scenarios for brief
passes, stationary holds, marker occlusion, head motion, and lighting loss.
Hand Stroke Stage 1 tests cover the device-independent versioned contract,
numeric-only bounded latency traces, opt-in diagnostic API, a no-hardware
synthetic pipeline benchmark, delayed-command timing, timeout, and emergency
stop during an in-flight simulated command.

## Hand Stroke diagnostic foundation

Stage 1 documented the camera-to-device path, added disabled-by-default
RAM-only timestamps, and defined versioned, device-neutral stroke
observations/events. Stages 2–4 added tracking, recognition, and a separate
initially simulator-only hand response rule without changing oral recognition. See
[Stage 1 architecture and baseline](docs/hand-stroke-stage1.md) for the
original measured simulator result and latency caveats. To repeat it:

```bash
python -m app.diagnostics.benchmark --samples 3
```

The API's `POST /api/diagnostics/latency/start` enables in-memory numeric
tracing for the current run; `GET /api/diagnostics/latency` reports aggregates;
`POST /api/diagnostics/latency/stop` disables tracing. It never starts the
camera, arms automation, or connects Intiface. Command completion is an API
acknowledgement, not measured physical device onset.

## Architecture

```text
camera -> face + object tracking -> temporal estimator -> local event bus
                                                        -> automation controller
                                                        -> safety controller

manual UI -> safety controller -> device registry -> simulator / Buttplug
```

- `app/main.py` starts the local FastAPI app.
- `app/camera/` owns explicit webcam start/stop, 640×480 capture, and in-memory
  preview buffers on a dedicated worker thread.
- `app/vision/` owns local Face Landmarker inference, mouth geometry, marker
  or CSRT object tracking, numeric calibration, temporal state estimation,
  optional overlays, and an offline numeric benchmark.
- `app/events.py` provides an asynchronous event bus.
- `app/triggers/` owns explicitly armed, bounded automation rules and the
  event-consuming state machine.
- `app/evaluation/` owns opt-in numeric drafts, local session files, and
  descriptive recognition metrics. It never imports device-control code.
- `app/diagnostics/` owns opt-in numeric timing traces and the simulator-only
  latency benchmark.
- `app/safety/` enforces one-shot manual arming, limits, timed stop, emergency
  stop, and shutdown cleanup.
- `app/devices/` adapts the installed Buttplug v4 client and provides the
  simulator behind a common device contract.
- `app/api/` and `app/web/` provide the local dashboard and Device, Vision,
  and Trigger Rules views without a frontend build system.
- `tests/` runs without hardware.

Limitations of this prototype include
false matches with similarly colored objects, marker occlusion, CSRT drift,
camera angle and lighting changes, and unknown object geometry: a marker on
the base does not reveal the location of the object's tip. The displayed
marker axis is only the visible marker's long axis; the object-to-mouth
bearing is a 2D image direction, not a 3D pose or contact measurement.
Pattern timing is best-effort on a general-purpose OS and depends on device
command latency; short steps can be skipped if the deadline or watchdog
expires. Real hardware was not exercised during pattern development. The
controller attempts a final stop after a late command, but software cannot
guarantee immediate physical shutdown if communication fails.

## Troubleshooting

- **Port 8000 already in use:** Stop the earlier SelfPleasure Terminal process
  with Ctrl-C, or use **Quit app** in the internal macOS bundle, then reopen.
  The app does not enable hot reload, so code and UI changes require a restart.
- **Camera permission denied:** In macOS System Settings → Privacy & Security
  → Camera, allow the app that launched Python (Terminal for the source build,
  SelfPleasure for the internal bundle), then restart
  SelfPleasure. Stop other apps using the camera. Try another input index only
  while the camera is stopped.
- **No face or marker:** Improve even lighting, keep the full face in frame,
  use a saturated marker color on a non-contact surface, and recalibrate.
  `TRACKING_LOST` revokes automation authorization; do not raise sensitivity
  merely to hide tracking failures.
- **No device listed:** Start the server in Intiface Central, confirm it sees
  the device, connect from Device Control, and scan. Intiface and SelfPleasure
  must remain on local loopback. Reconnects never automatically rearm.
- **Arm button unavailable:** Start the camera, select a device, create and
  enable a rule for one of its listed vibration feature indices, and confirm
  no manual test is enabled or running. The API returns the exact reason for
  rejected arm attempts.
- **Unexpected output or no confirmed stop:** Press Emergency Stop and use
  the device's physical power control. Software cannot guarantee a stop if
  the computer, Intiface, or Bluetooth link fails.

## Performance and validation limits

MediaPipe inference, CSRT tracking, JPEG encoding, and serving an MJPEG preview
are the likely CPU/bandwidth bottlenecks. Processing is limited to 640×480 with
a 24 FPS target; actual FPS is shown in the dashboard. The UI polls small
numeric status endpoints, while frames stay in memory. No recognition-accuracy
claim is made for live use: false-positive/negative rates have not been
measured against labeled, consented real-world sessions, and no sustained
multi-device reliability test has been completed. Keep real-device use
supervised with its physical stop control accessible.

## Advanced recognition: offline evaluation

Run the detector benchmark without opening a camera, connecting to Intiface,
or arming automation:

```bash
cd "/path/to/user/Documents/01 Active Projects/Software & Experiments/SelfPleasure"
source .venv/bin/activate
python -m app.vision.benchmark
```

The committed `tests/fixtures/recognition_cases.json` contains **hand-labeled,
synthetic numeric trajectories** of a harmless tracked prop near a face. Every
sample has an `active` intent label. The six scenarios cover sustained motion
and withdrawal, a brief pass, a stationary prop, vertical approach, tracking
interruption, and head/prop motion together. The labels do **not** establish
actual contact. No image, video, or personal biometric sample is included.
The benchmark accepts another local JSON file with the same schema as an
optional positional argument; it never saves the input or sends it anywhere.

On these 92 synthetic frames (25 labeled positive, 67 negative), the original
heuristic scored 14 true positives, 1 false positive, 66 true negatives, and
11 false negatives: precision 0.933, recall 0.560, frame false-positive rate
0.015. After correcting image aspect ratio in mouth-to-object distance,
checking adjacent-frame motion to avoid temporal aliasing, and ending on
clear withdrawal, it scored 25 true positives, 2 false positives, 65 true
negatives, and 0 false negatives: precision 0.926, recall 1.000, frame
false-positive rate 0.030. There were two early positive *episodes* on the
synthetic labels. Synthetic start/end latency was 0 seconds for the labeled
events, but the 100 ms sample period and subjective onset labels make that
figure unsuitable as a live latency claim. A 3-event automation debounce and
all existing safety limits remain separate from these detector metrics.

What this evaluation does **not** measure yet: actual Face Landmarker jitter
or occlusion confidence, marker identity accuracy under changing lighting,
CSRT drift, camera-to-camera geometry, real interaction start/end latency, or
real false activations per hour. A hidden marker still yields tracking loss;
the system must stop and require fresh evidence, never infer continued contact
from occlusion. The marker is on a non-contact part of the prop, so its center
does not locate the prop tip or prove any oral action. The score remains an
uncalibrated heuristic.

For an individual user, calibrate a neutral mouth pose, marker hue, camera
position, near-zone size, and sensitivity in **Vision Settings** while
automation is disarmed. Recheck with harmless pass, hold, withdrawal, head
movement, and marker-hiding scenarios. Do not raise sensitivity solely to
force an active state; it can increase false positives.

Approaches considered:

| Approach | Benefit | Main limitation / decision |
| --- | --- | --- |
| Current geometry + HSV marker + short temporal history | Runs locally now, needs no training data, and is interpretable | Sensitive to same-colored distractors, occlusion, and unknown prop geometry; retain for controlled testing |
| [MediaPipe Object Detector](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/ObjectDetector) with a small TFLite model | On-device object localization could reduce color dependence | Needs a suitable labeled model and still cannot prove contact; do not add yet |
| Small temporal classifier over numeric trajectories, using [Core ML](https://developer.apple.com/documentation/coreml) for local deployment if needed | Could learn motion patterns and smooth state decisions | Needs representative consented labels, held-out validation, and error analysis; do not train yet |

The recommendation is to retain the heuristic until opt-in, *real* labels show
whether its error rate is acceptable. A numeric-only evaluation mode is now
available as described below; it does not train a model or capture frames.
If a model is later justified, obtain a separate opt-in collection design and
split data by session/camera position before training so near-duplicate frames
cannot inflate results. No frame-capture or model-training mode exists.

## Opt-in local recognition evaluation

Open [http://127.0.0.1:8000/evaluate](http://127.0.0.1:8000/evaluate). This
mode is for a harmless marked prop and should not involve a physical device.
It requires the camera to be started explicitly and automation to be already
disarmed; it refuses to begin if a manual test is enabled or running. Once
evaluation begins, both manual activation and automation arming are blocked at
the API and safety-controller layers. Emergency Stop remains accessible as a
stop-only safety exception. Evaluation never sends an activation or pattern
command.

1. Start the camera and check face/marker tracking. Disarm automation before
   entering evaluation mode.
2. Check the first consent box and press **Start evaluation**. Numeric
   observations stay in memory. The initial label is **Uncertain**.
3. At the start of each test interval, press **No interaction**, **Intended
   interaction**, or **Uncertain**. Try a brief pass, stationary hold, marker
   hiding, head movement, and lighting changes. Use Uncertain when the intended
   state cannot be judged. Labels are timestamps of your button presses; they
   are not proof of physical contact.
4. Press **Stop & review**. Inspect precision, recall, false-positive episodes
   per hour of *negative-labeled camera time*, missed intended intervals,
   start/end latency, unresolved ends, and recent numeric observations. These
   are per-session descriptive metrics, not validated accuracy claims. Use
   **Review all numeric draft data** to inspect every sample before saving.
5. Either **Discard draft** (nothing is written) or check the separate local
   save consent box and press **Save numeric session**. Saved JSON sessions are
   in the ignored `evaluation-data/` directory with user-only file permissions.
   Review a session on the page or open its numeric JSON; delete it from the
   page when no longer needed. There is no automatic retention or upload.

The evaluation draft is discarded on app shutdown unless separately saved.
Collection stops at 30 minutes or 45,000 observations, and also pauses if the
camera stops or event processing fails; stop and review in that case. No JPEG,
video, screenshot, or image content is saved by this mode. Session files
contain timestamps, normalized mouth/object positions, tracking quality,
detector state/score, and manual labels; treat these numeric biometric traces
as private. The `GET /api/evaluation/sessions/{id}` route exposes them only
through the localhost application, and responses are marked `no-store`.

Precision and recall count labeled frames; Uncertain frames are excluded.
False-positive episodes per hour divides negative-labeled false-active runs by
observed negative camera time, with gaps over 250 ms excluded. Start latency
measures time from a positive label to the first active frame in that interval;
end latency measures from a positive-to-negative label change to the first
nonactive frame. A missed interval has no start-latency value. These numbers
are sensitive to human button timing, camera FPS, calibration, and label
quality. The report recommends more data for short sessions, heuristic
inspection when errors appear, or provisional retention when none appear. A
custom local model should be considered only if the same failure modes recur
across multiple held-out sessions; this mode does not claim a model is needed.
