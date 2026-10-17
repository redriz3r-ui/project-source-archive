# Privacy policy — development build

SelfPleasure processes webcam frames in application memory on the user's Mac.
Frames are not saved, uploaded, or sent to an inference service by default.
The camera starts only after a user action and stops when the session finishes,
the application shuts down, or a managed Hand Stroke session lease expires.
The local dashboard listens on `127.0.0.1`; Intiface communication uses the
local WebSocket at `127.0.0.1:12345`. The app has no telemetry or analytics.

Calibration settings and trigger rules are saved locally. Evaluation is
optional: starting collection requires consent, and saving a session requires
separate consent. Saved evaluation sessions contain timestamps, labels, and
numeric tracking observations—not webcam frames. They can be reviewed and
deleted in the app. Latency diagnostics are RAM-only unless a user explicitly
runs the numeric hardware-validation collector. These records may still reveal
sensitive behavior, so treat them as private.

Normal operation makes no cloud requests. The optional one-time model download
used during source setup contacts Google's model storage, verifies a pinned
SHA-256 digest, and saves the models locally; a distributable app would bundle
the models instead. Intiface Central and the connected device have their own
software, network, and privacy behavior outside this application's control.

The source build stores local calibration/rule files beside the project and
opt-in evaluation files under `evaluation-data/`; `.gitignore` excludes them.
The internal macOS bundle instead uses
`~/Library/Application Support/SelfPleasure/` for writable data. Deleting
saved sessions in the UI removes those files. For full data removal, see
[uninstall guidance](uninstall.md). No claim is made about data
retained by the browser, macOS, Intiface, backups, or external tools.

This policy must be rechecked against the actual Developer-ID-signed build before release,
including packaged paths, model bundling, permissions, and network behavior.
