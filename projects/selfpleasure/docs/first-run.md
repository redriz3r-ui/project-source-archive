# First-run guide (release candidate draft)

**No consumer release is available yet.** The current `.app` is an internal,
ad-hoc-signed development build. Do not ask users to bypass macOS security
warnings to run it. This guide describes the intended signed/notarized flow
and must be verified with new users on a clean Mac before publication.

1. Install Intiface Central separately if you plan to use a compatible
   physical device. Keep its server on the local computer. Nothing connects
   or activates automatically when SelfPleasure launches.
2. Drag the verified `SelfPleasure.app` into Applications and open it. The
   local dashboard opens in your browser. Confirm it says camera inactive
   and output disarmed. The app listens only on `127.0.0.1`.
3. Open **Hand session** for a simulator-only practice flow. Select the
   simulator, choose the webcam, and press **Start camera**. macOS should ask
   for camera access at this point, not on launch. If denied, use **System
   Settings → Privacy & Security → Camera** to permit SelfPleasure, then
   restart the app if necessary.
4. Mark the base and far end of a harmless, mostly still prop's movement axis.
   Wait for **Tracking ready**. Choose an intensity ceiling and response
   behavior; **Preview response** is visual only and does not command a device.
5. Press **Arm simulator** deliberately. **ARMED** means it may respond;
   **OUTPUT ACTIVE** means a bounded pulse is happening now. Tracking
   uncertainty stops authorization. **Pause** and **Disarm** stop output;
   neither resumes automatically. **Emergency Stop** remains in the header
   and responds to Escape.
6. Press **Finish** to stop output and release the camera. Press **Quit app**
   to close the local server. Physical power-off remains the fallback for any
   real device once a supervised hardware configuration is approved.

There is no approved real-device Hand Stroke configuration yet. The user must
never be invited to select an unverified device for this flow. Consult the
[compatibility matrix](compatibility.md) before any future hardware pilot.
