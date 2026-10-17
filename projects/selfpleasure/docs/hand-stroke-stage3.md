# Hand Stroke Stage 3: temporal recognition and evaluation

This is **camera-only recognition**. The hand estimator receives the Stage 2
axis-relative position and heuristic tracking quality; it imports no device
code. It emits versioned `StrokeObservation` and `StrokeEvent` values with
monotonic timestamps, frame IDs, calibrated position, direction, speed,
travel, quality, and unique stroke ID. The local event bus topics are
`stroke_observation`, `stroke_started`, `stroke_updated`, `stroke_completed`,
and `stroke_tracking_lost`. The last topic is deliberately distinct from the
oral mode's `tracking_lost`, although its contract event kind remains
`tracking_lost`. No stroke topic subscribes to automation or Buttplug.

## Traversal rule

A candidate starts only after **0.06 axis lengths** of directional movement
with average speed at least **0.04 axis lengths/s**. A raw jump above **3.0
axis lengths/s**, more than **250 ms** between observations, quality below
**0.5**, or any ambiguous/lost hand resets evidence and emits one tracking
loss event per interruption. Position uses a one-pole 0.55/0.45 smoother to
limit small shakes with roughly one frame of lag. A stroke completes once
it has traveled at least **0.25 axis lengths** within **8 seconds**, and
either reaches the far endpoint zone (within 0.12 of the end) or reverses
by at least 0.05 axis lengths for two frames. A partial reversal is discarded;
continuing in the same direction after endpoint completion cannot start a
duplicate stroke. Reversing for the return traversal gets a new stroke ID.
These are initial heuristic thresholds, not validated optimums. `started`
means a candidate traversal, not proof that a completed stroke will follow.

## Opt-in evaluation

The [local evaluation page](http://127.0.0.1:8000/hand/evaluate) requires
Hand Stroke camera mode, explicit numeric-collection consent, and disarmed
automation. The safety controller blocks manual and automated activation
while evaluation is active. The user labels `STROKES`, `NO_STROKES`, or
`UNCERTAIN` intervals and presses a separate button at each intended stroke
completion. The initial label is uncertain. Session drafts stay in memory,
pause on camera stop or event failure, and are discarded on shutdown. A
separate save consent writes JSON with user-only permissions to ignored
`evaluation-data/strokes/`; review and deletion are available in the UI.
There is a 30-minute/45,000-sample cap. Only timestamps, normalized numeric
observations, bounded state labels, and metrics are retained—no frames,
landmarks, screenshots, video, or uploads.

Reports match one detected completion to at most one manual mark within a
**±1-second window**, only during a `STROKES` interval. Unmatched detections
in labeled intervals are false positives; unmatched manual marks are misses;
uncertain intervals are excluded. Count accuracy is
`max(0, 1 - |detected − manual| / max(1, manual))`, with an empty/empty
session defined as 1. Precision and recall use matched/false/missed counts.
False detections per hour divide detections in `NO_STROKES` intervals by
observed negative-labeled camera time, capping each frame gap at 250 ms.
Latency is signed `detected timestamp − manual-button timestamp`; a negative
value can simply reflect reaction time. The report includes individual and
mean latency values, not a claim of physical actuation latency.

## Tests and measured status

Synthetic numeric tests cover slow and fast traversals, return strokes,
partial reversals, stationary shakes, interruption, low-confidence occlusion,
out-of-frame tracking, implausible jumps, and adequate/poor confidence as a
lighting proxy. A mock camera test changes frame brightness and verifies a
separate hand-tracking-loss event. Tests also cover one-to-one matching,
consent, numeric-only storage, review/deletion, origin rejection, and blocked
device actions during evaluation. They do **not** measure live accuracy.

After Stage 3 integration, the real installed model and camera worker
processed **66 generated blank 640×480 frames in 3.001 seconds: 21.99 FPS**
against a 24 FPS target (`python -m app.diagnostics.hand_benchmark --seconds
3`). This excludes a real webcam, visible hand, colored marker, and browser
display. Camera-only recognition therefore **has not yet met a measured
real-session count, precision, recall, false-detection, or latency target**.
Use the opt-in screen across several harmless-prop sessions before deciding
whether thresholds suffice. No one-to-one mirroring claim is justified.

Known failure modes: a single marker cannot distinguish camera translation
from prop drift/rotation; same-colored objects can steal the base anchor;
MediaPipe can hallucinate or swap hand landmarks during occlusion; hand
center differs from actual contact point; endpoint clicks and image geometry
vary by camera angle; and human button timing biases evaluation latency.
Tracking loss discards stroke evidence rather than inferring missing motion.
