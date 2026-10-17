# Stage 6 — guided Hand Stroke session

Status: simulator by default, with a restricted **supervised real-device pilot**.
The Stage 5 physical hardware gates are still unmeasured, so real Hand Stroke
is not an approved everyday-use mode. A real pilot requires explicit selection
of the advertised vibration feature, confirmation of a successful short manual
test and physical power-off access, and a separate Arm action. Real pilot mode
uses only one crisp pulse per completed stroke, at most 20% for 0.12 seconds
with at least 0.5 seconds rest. Follow movement is unavailable on real devices.
It never infers arousal or promises an outcome.

## Flow and safety language

Open `/hand/session`. The page stays read-only on arrival: no camera,
Intiface connection, or output starts automatically. Preflight shows the
selected device, Intiface status, and camera state. **Use simulator** is an
explicit selection action. **Start camera** is a separate action; Hand mode
and the chosen camera number are set before capture begins. The preview is
in memory only. Advanced overlays are hidden by default.

The calibration step accepts clicks or keyboard-entered percentages for the
base and far end of the prop's movement axis. Tracking quality is shown as a
heuristic with plain-language advice. Uncertain tracking must prevent arming
and, if already armed, stop output. The user then chooses an intensity
ceiling, response feel, and response timing. **Preview response** is a pure
calculation and sends no command. The current settings must be previewed
before the page enables Arm, while the server independently validates all
settings and device capabilities.

The persistent header has Emergency Stop; Escape activates the same endpoint.
The primary status distinguishes:

- **DISARMED / PAUSED:** output off; no response is authorized.
- **ARMED:** tracking is valid and a response may occur, but output is off.
- **ACTIVE:** one bounded simulator pulse is running now.
- **COOLDOWN:** output off while the rate limit expires; some movement is
  intentionally skipped.
- **ERROR / EMERGENCY STOP:** output stopped; there is no automatic recovery.

Pause stops output but leaves the camera ready; a new deliberate Arm is
required. Disarm stops output and leaves the camera on. Finish stops output
and releases the camera. The session page sends a heartbeat only while the
current page deliberately armed the session; if heartbeats cease, the server
disarms and attempts to close the camera. Page exit also sends a best-effort
finish request. The independent safety watchdog and device stop behavior
remain in force. A computer crash or disconnected device may prevent software
stop; physical power-off remains the fallback.

**Once per stroke:** a fresh, completed traversal starts one bounded envelope
if not busy or cooling down. Gentle is separated softer bursts, Crisp is one
direct pulse, and Ramp builds within the envelope. This is not a guarantee
that every very fast stroke produces output.

**Follow movement:** a fresh, sufficiently confident movement update may
start a short pulse. The hand's measured speed shapes intensity below the
ceiling; Gentle softens it and Ramp further scales with travel. A pulse is
at most 0.12 seconds with at least 0.08 seconds of cooldown. No updates are
queued. The output stops when movement ceases, a stroke ends, tracking is
lost, the page lease expires, or the user stops the session. This is
rate-limited approximation, **not** continuous one-to-one physical mirroring.

## Supervised usability test still required

No supervised users have been observed in this stage. Before claiming that
the session experience is understandable, recruit consenting adults and test
with a harmless prop and simulator first. Do not record faces, footage, or
intimate actions. Ask permission before taking even anonymous task notes.
Use at least five participants unfamiliar with the interface, one at a time:

1. Ask them to open the page and explain whether the camera and output are
   on. Check that they notice the simulator default and that the real-device
   option is an unvalidated supervised pilot, not approved everyday use.
2. Ask them to select a simulator, start the camera, and calibrate by mouse
   and then by keyboard. Note every point where they are unsure what to do.
3. Ask them to preview Gentle/Once and explain whether Preview sends output.
4. Arm, move a harmless prop, and ask them to distinguish **ARMED** from
   **ACTIVE** and identify when output is off during cooldown.
5. Ask them to Pause, move again, and explain whether it resumed. Have them
   explicitly rearm, then use Emergency Stop by button and by Escape.
6. Simulate tracking loss and a dropped camera using test doubles only. Ask
   what they believe the output state is. Finish and confirm the camera is
   released.

Record task success, time to find Emergency Stop, incorrect armed/active
interpretations, keyboard-only blockers, and exact wording that confused
participants. Fix critical misunderstandings before any hardware pilot and
repeat the same tasks with new users. A useful gate is that every participant
can locate Emergency Stop quickly and correctly identify armed versus active
without coaching; this is a proposed usability criterion, not a measured
result. Stage 5 physical-response gates remain separate.
