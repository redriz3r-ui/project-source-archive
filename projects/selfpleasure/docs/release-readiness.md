# Stage 7 release-readiness audit — 2026-10-15

**Decision: DO NOT RELEASE.** A 0.1-second manual vibration preflight on the
JoyHub Petalwish 2 did not stop physically; the user had to reset the device.
The user pressed Emergency Stop before resetting it, and the physical output
continued after the app reported Emergency Stop. Real-device output is now
locked out by default across manual and
automated paths; the running app was emergency-stopped and disconnected from
Intiface. The failure has not been reproduced or explained, and no further
physical test should be attempted without a reviewed stop protocol.

## Evidence checked

- Python 3.13 on macOS ARM64; pinned direct dependencies install and `pip check`
  reports no broken requirements. Installed core versions: FastAPI 0.143.1,
  Uvicorn 0.53.0, Buttplug 1.0.0, MediaPipe 1.1.0, OpenCV contrib 5.0.0.93.
  The lock is not hash-pinned and transitive dependency/security/license review
  is incomplete. A newer MediaPipe release exists but was not silently adopted.
- Full automated suite and focused device/automation/hardware-validation fault
  tests pass. These use mocks/simulation, not physical onset or physical stop.
- Camera and device are off at startup. The HTTP host and Intiface URL are
  loopback restricted. State-changing browser requests reject foreign Origin
  headers and cross-site Fetch Metadata. The camera pipeline is local; no
  frame-saving or upload path was found in normal operation. Evaluation saves
  numeric data only after consent. The optional setup model downloader is an
  explicit external-network exception.
- Unmanaged Hand Stroke arming rejects real devices; the previously managed
  real pilot is now suspended. Feature selection is checked against
  advertised vibration indexes. Oscillation is not enabled automatically.
  Emergency Stop, tracking loss, camera stop, disarm, and
  shutdown attempt stop and revoke authorization. Software stop cannot
  guarantee physical cessation after host/Bluetooth failure.
- Audit fixes: all registered devices now receive concurrent stop attempts,
  and the real-device adapter attempts both device-level and advertised
  vibration-feature-level StopCmds. This redundant stop path has only been
  verified with injected devices; it has **not** been physically validated or
  used to remove the real-output lockout. The adapter reports
  `stop_unconfirmed` if either stop scope errors. The offline scorer also
  counts every physical onset in a negative interval.
  The scorer now requires per-device/feature variation in testers, camera
  positions, and lighting before its cohort gate can pass.
- An internal 211 MB ARM64 `.app` bundle was built with bundled local models,
  `NSCameraUsageDescription`, and an ad-hoc signature. It served the local
  dashboard with camera inactive, Intiface disconnected, and activation
  disabled, then closed via the UI's Quit endpoint. No camera permission or
  physical-device behavior was exercised in the bundle. This is not a
  distributable signed/notarized release.

## Open release blockers

1. Obtain a Developer ID Application signing identity and notarization
   credentials from the project owner. Never place them in source control.
2. Finish packaging validation. The internal bundle includes Python, model
   files, camera usage text, a Quit action, and separate Application Support
   data paths, but its camera permission, native libraries, signing
   entitlements, notarization, clean-machine install, and removal have not
   been validated. Ad-hoc signing is not Developer ID signing.
3. Investigate the observed failed physical stop during the 0.1-second manual
   preflight. Determine whether the stop command was sent, acknowledged, and
   honored by Intiface and the device. Injected tests do not close this issue.
4. Collect held-out, consenting, numeric-only real sessions with independent
   stroke-boundary and physical output sensors. The available pilot has one
   tester, one camera position, and daylight by a window, so it cannot satisfy
   the requested generalization gate. At least a second tester and different
   camera/lighting conditions are needed for each proposed device/feature.
5. Confirm the exact Intiface-advertised vibration feature of the reported
   Joy hub Petal. Publish measured stroke accuracy, onset/stop latency, and
   no-restart evidence for each configuration. No physical figures exist yet.
6. Run supervised first-run, arm/active, Pause, Emergency Stop, and uninstall
   usability tests with new users. Fix misunderstandings and retest. No such
   sessions have been conducted in this task.
7. Complete dependency/license/security review, package network verification,
   signing and notarization verification, and a clean-machine install test.

## Release rule

Do not publish or label a physical configuration supported until the Stage 5
gates pass on reviewed real evidence, all safety-critical defects are closed,
and a new user can set up and stop a session without developer help. A
passing synthetic fixture, command acknowledgement, or manual device pulse
is insufficient. The compatibility matrix remains unverified until then.

Commands used in this audit:

```bash
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_hardware_validation.py tests/test_hand_response.py tests/test_device_control.py tests/test_automation.py tests/test_patterns.py tests/test_session.py tests/test_hand_session.py
```
