# Hand Stroke Stage 2: local tracking, not mirroring

The camera service now has explicit `oral` and `hand` modes. Only the latter
opens MediaPipe Hand Landmarker; it does not load Face Landmarker or emit
`interaction_*` events. The automation controller's camera authorization
requires `oral` mode, so selecting Hand Stroke cannot route a detection to a
device. Manual device control remains a separate feature. The camera worker
performs a blocking `detect_for_video` on each newly read frame; there is no
application inference queue or saved footage. OpenCV/AVFoundation may still
buffer camera frames internally, so absolute sensor-to-preview latency is not
established by this stage.

The installed API inspected before implementation was MediaPipe **1.1.0**:
`HandLandmarkerOptions`, `HandLandmarker.create_from_options(options)`, and
`detect_for_video(mp.Image, timestamp_ms)` in `RunningMode.VIDEO`. The model
bundle is Google's official float16 Hand Landmarker task, downloaded into
ignored `.models/` and pinned by SHA-256. The local setup download is the
only network step; detection is fully local. No OpenCV fiducial marker was
added: the existing HSV color marker suffices for a first translation anchor,
while a fiducial would add calibration complexity without resolving hand
occlusion or depth ambiguity. Revisit it if labeled tests show color-marker
drift is a leading failure mode.

## Measured processing speed

On this Apple Silicon machine, two 3.001-second runs with **generated 640×480
black frames, the real installed hand model, preview encoding, and the camera
worker** processed 66 and 65 frames: **21.99 and 21.66 FPS** (UI smoothed
display: 22.0 and 21.7 FPS), against a 24 FPS target. A separate tight-loop model-only run processed 90
blank frames in 1.164 seconds (**77.34 inference calls/s**). Reproduce the
full-worker result with:

```bash
python -m app.diagnostics.hand_benchmark --seconds 3
```

These are actual local processing measurements, **not a real-webcam FPS
measurement** and not a measurement with a visible hand or colored marker.
Model tracking/re-detection, camera buffering, lighting, marker processing,
and a browser preview can change FPS. The Hand page displays current FPS so
the user can check their own webcam session. We did not open the personal
webcam or activate hardware during development.

## Geometry and observed limits

The saved numeric calibration is a base point and an axis endpoint in
mirrored-preview coordinates. With marker anchoring, the current colored
marker center translates the axis; the hand's median wrist/MCP center is
projected onto that translated axis using the frame aspect ratio. Small
camera/object translations preserve relative position. If the marker is
missing, translated over 15% of the normalized frame from calibration, or
moves the axis outside the preview, tracking fails closed. One visible palm
with two or more in-frame anchor landmarks is required. Two plausible hands
near the axis are marked ambiguous; one far-away extra hand is ignored.

The tests cover camera translation, large object drift, partial occlusion,
multiple hands, missing marker, no face, camera read failure, explicit mode
selection, and the inability to arm oral automation in Hand Stroke mode.
Known failure cases remain: a single colored marker cannot distinguish
camera motion from object translation or measure object rotation/depth;
similarly colored distractors can steal the marker; MediaPipe may infer
landmarks through occlusion; the palm center may not match the contact point;
and fixed-axis calibration drifts if the camera or prop moves. The displayed
quality is a geometric heuristic, not validated recognition accuracy. No
stroke classifier, temporal smoothing, event stream, or device mirroring is
present yet.
