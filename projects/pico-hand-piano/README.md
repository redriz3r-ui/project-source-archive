# Saved Pico Hand Piano

Saved September 13, 2026. This is the working Summer Means New Love opening-lead version, frozen separately from ongoing experiments.

## Open it again

1. Connect the Pico WH to this Mac by USB, without holding BOOTSEL.
2. Close any other app connected to the Pico (or stop its Pico interpreter).
3. Double-click **Open Hand Piano.command**. If macOS asks to allow the file to open, use Finder’s Open action.
4. Click **Start** and hold your palm in front of both ultrasonic sensor eyes.

Move farther away to advance through the opening lead. Move closer to retrace it backward. Hold still to add no new notes. The app fills in any crossed note steps. Your movement sets the rhythm; this is the opening phrase rather than automatic full-song playback.

Range: **2–20 inches**. Sixteen note positions. Piano-like samples. Sound toggle, volume, and playback-speed controls. The servo stays still in piano mode.

Click **Stop**, or close the window, before disconnecting. The launcher uses the installed Thonny 3.14 Python runtime and its pyserial library; no cloud service or internet connection is required. The Pico already has MicroPython 1.29.0 for Pico W installed. No main.py or automatic startup program is needed.

## Files

- `hand_slider.py`: saved hand-controller app.
- `song_player.py`: forward/backward note playback.
- `opening_lead.json`: first-line melody transcribed from the supplied score screenshot, with ties merged.
- `song_piano/`: generated piano WAV files.
- `servo_test.py`, `distance_test.py`, `scan_test.py`: earlier finite MicroPython hardware tests; run only deliberately.
- `WIRING.md`: wiring reference.
- `manifest.json`: file hashes for snapshot verification.

The .command launcher is for this Mac. If Thonny’s location or Python version changes, its interpreter path may need updating.
