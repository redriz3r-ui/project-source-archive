# Hand Stroke compatibility matrix

As of 2026-10-15, **no physical device is approved for Hand Stroke automation**.
The controller now locks out all real-device output by default after a failed
physical stop in a manual preflight. An Intiface device appearing in
Device Control, or passing a manual vibration test, is not evidence that its
stroke-triggered response and physical stop behavior meet the release gates.

| Device / output | Camera and conditions | Stroke accuracy | Physical onset latency | Physical stop delay | Hand Stroke availability |
| --- | --- | --- | --- | --- | --- |
| Built-in simulator / vibration feature 0 | Synthetic and injected tests | Not a real-session measure | Not a physical measure | Not a physical measure | Development only |
| JoyHub Petalwish 2 / Intiface vibration feature **2** | One MacBook webcam; daylight by window; one consenting adult available | Not measured | Not measured | **One 0.1-second preflight failed to stop; two later off-body tests stopped by user observation; physical delay not instrumented** | **Disabled / unsupported pending investigation** |
| Any other device or feature | Not tested | Not measured | Not measured | Not measured | **Not enabled / unverified** |

The device name and feature above were read from the local Intiface inventory.
The initial 0.1-second physical preflight failed to stop and required a physical
reset. On 2026-10-15, one supervised off-body 20%/0.5-second pulse physically
stopped, and a separate 20% pulse interrupted by Emergency Stop after about
0.2 seconds also physically stopped, according to the user's observation.
An earlier 10%/0.5-second off-body test produced no observable vibration.
These are individual observations, not instrumented stop-delay measurements or
proof of repeatable safety. Normal-mode real-device output and all camera
automation remain locked. A separate process-only off-body manual bench mode
allows capped diagnostics; it does not change support status. Do not use this
device for on-body automation while the failure remains unexplained.
Device indexes may change.
Never assume that a push/thrust capability is a vibration feature; the current
hand response only selects an advertised vibration feature and must not
silently switch outputs.

For each device **and selected output feature**, collect at least three distinct
held-out, numeric-only real sessions with at least two consenting testers,
two camera positions, and two lighting conditions. Each session must satisfy
the Stage 5 labeled-stroke, negative-observation, physical-sensor, and active
stop checks. Run the offline scorer, review provenance and sensor alignment,
then separately review any code/configuration change before enabling that
exact device and feature. A failed or incomplete configuration stays disabled;
it is not made supported by success on a different device or feature.

See [the Stage 5 protocol](hand-stroke-stage5.md) for collection and scoring.
The scorer reports per-device cohort gates and never commands hardware.
