# Verification record — September 23, 2026

The Phase 1 pipeline is implemented and exercised end to end. Quality features include sampled face/motion tracking, restrained crop paths, contact sheets, diversity-aware variants, editable plans, and locked-shot regeneration. Semantic-model integration is optional; no cloud model was needed for the tests.

## Automated checks

- **9 unit tests passed:** exact planned duration, distinct variants, excluded-range overlap, crop pan limits/dead zones, composition fallback, missed-first-face initialization, invalid/stale plans, small-library capacity, and single-frame flash rejection.
- **Synthetic new-film CLI integration passed:** ingest → analyze → generate three variants → MP4, with source paths containing spaces and an apostrophe. Ten known synthetic shots were detected.
- Verified H.264/yuv420p, exact output frame counts and dimensions, and complete FFmpeg decoding of all synthetic variants.
- Original-audio waveform test used a frequency-changing signal. Cross-correlation at the interior of each selected cut found **0, 0, 0 samples** of offset against decoded source audio. This tests these fixture cuts; it is not a blanket guarantee for every codec or unusual timestamp layout.
- Silent sources, muted output, every framing mode, preview, end cards, render-cache reuse, lock-aware regeneration, replacement, removal, duration edits, and reordering passed integration checks.
- Additional targeted checks passed for an anamorphic source (2:1 sample aspect ratio), music looping/trimming, and experimental dialogue-reduced encoding. The latter is an effect, not validated speech separation.
- Final rerun of the real film analysis reused **749 shots in 2.52 seconds** without changing any visual-checkpoint modification time.

Test commands:

```bash
python3 -m unittest discover -s tests -v
python3 tests/integration.py
```

Environment: Python 3.13, OpenCV 4.11.0, FFmpeg/ffprobe 7.1.1 on macOS; CPU encoding, no CUDA or large model.

## Production-film test

The user-provided local Chungking Express file was referenced in place. Its full 102.9-minute timeline was proxied and indexed. Improved flash rejection reduced the initial 752 detected shots to **749**, reusing visual measurements for unchanged boundaries. All existing reel source intervals were preserved when updating shot IDs.

| Reviewed export | Duration | Frames | Canvas | Audio |
|---|---:|---:|---|---|
| `reel_001.mp4` — Atmosphere | 23 seconds | 690 | 1080×1920, 30 fps | Muted |
| `reel_002.mp4` — Frenzy | 15 seconds | 450 | 1080×1920, 30 fps | Muted |
| `reel_003.mp4` — Longing | 25 seconds | 750 | 1080×1920, 30 fps | Muted |

Exports use original-source footage, H.264/yuv420p and fast-start MP4. Each export has a render sidecar, and `exports/verification.json` records the final full-decode check. Lightweight previews are also available.

The production plans received an **agent-directed editorial pass**, using the cached contact sheets. They are not presented as untouched automatic output. Initial face-heavy choices led to better generic appearance-similarity penalties and stronger environmental balance. The final three treatments emphasize city/sky/neon atmosphere, fast movement, and quieter faces/gestures respectively. They share only one shot between Atmosphere and Longing; Frenzy uses a different set.

Preview frames at 10%, 50%, and 90% of every selected clip were inspected. This exposed missed-face initialization and profile/occlusion problems; the engine initialization was repaired, and plan-level framing/offset overrides corrected the selected production shots. `thumbnails/reel_*_crop_review.jpg` records this sampled-frame review. This was not a claim of frame-by-frame human viewing of the whole film. Deliberate fit/letterbox shots retain important widescreen compositions.

`reel_004`–`reel_006` retain an additional **fully automatic** three-variant planning test: 8, 11, and 7 unique shots, with no shot shared between the variants. These are saved plans and contact sheets, not additional final exports. Earlier draft plans and the pre-refresh database are preserved in history folders.

## Practical limits

The automatic director and spoiler controls remain heuristics. No model infers plot, characters, or reliably identifies romance/night/interiors. The first production reels are muted to avoid dialogue and should be reviewed before release. There is no automatic music selection, beat matching, identity-aware continuous tracking, or graphical timeline editor. The README documents the functioning alternatives and extension interfaces.
