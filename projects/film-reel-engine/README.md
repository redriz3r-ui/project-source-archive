# Film Reel Engine

A local-first Python pipeline that indexes a film once, saves an editable shot library, and renders vertical reels from reusable JSON edit decisions. FFmpeg handles media; OpenCV measures imagery and subject positions; the director chooses edits without manipulating video.

## Local interface

After installing the dependencies below, start the three-step interface from this folder:

```bash
python3 ui.py
```

It opens `http://127.0.0.1:8765/` in your browser. Choose a video (or paste its full path), click **Ingest video**, **Analyze video**, then **Generate reels**. The interface shows progress, existing projects, and playable exports. Leave the Terminal window running while using it; press Control-C to stop the server. It binds only to `127.0.0.1`, uses no external web assets, and sends no footage to a cloud service. The source file remains in place.

Under **Adjust shot analysis**, change cut threshold, minimum shot length, continuous-take segment length, sampling rate, sample cap, face tracking weight, or worker count. Click **Analyze video** to apply changes. These settings are stored per project in `analysis/ui_settings.json`; reanalysis may renumber shots, so create new reel plans after changing cut boundaries.

Under **Adjust shot selection**, change the weights for visual interest, composition, motion, faces, and variety. These affect which analyzed shots appear in new reels; they do not require reanalysis. The weights are stored per project in `analysis/ui_ranking.json`.

In **Generate a reel**, choose original audio, a local music file, silence, or experimental dialogue reduction, and adjust sound level from 0–200%. Original audio follows the selected source cuts and can jump between shots; music plays continuously over the reel. The music option does not mix in source audio. Choose a track you have rights to use.

The command-line workflow below remains available.

## Quick start

Requires Python 3.10+, FFmpeg/ffprobe with libx264, and the small Python dependencies below. No GPU, API key, cloud account, or large model is required.

```bash
# macOS, if FFmpeg is not installed:
brew install ffmpeg

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python reel.py ingest "/Movies/My Film.mp4"
python reel.py analyze
python reel.py generate --mood "dark, tense, mysterious" --duration 20 --aspect 9:16 --variants 3
```

`generate` writes plans, candidate/selection contact sheets, and rendered MP4s. Outputs are in `projects/<film-id>/exports/reel_001.mp4`, etc. Existing reel IDs are never reused by generation. The last ingested project is active; use `python reel.py status` to locate it. All paths with spaces must be shell-quoted.

Global options go **before** the command:

```bash
python reel.py --project <film-id> generate --mood "quiet romantic" --duration 25
python reel.py --config my-config.yaml --projects-dir /Volumes/Media/reel-projects ingest movie.mp4
```

The original is referenced in place and never changed. Keep it available for final renders. Source path, size, and modification time identify the project; a changed source gets a new project on ingest. This is a fast identity check, not a cryptographic content checksum.

## Preview and edit

```bash
python reel.py generate --mood "neon romantic" --duration 22 --variants 3 --plan-only
python reel.py preview reel_001
python reel.py render reel_001

python reel.py replace-shot reel_001 4 812
python reel.py remove-shot reel_001 2
python reel.py set-duration reel_001 1 2.5
python reel.py set-crop reel_001 1 smart_crop --center 0.7 0.5
python reel.py set-crop reel_001 2 blur_background
python reel.py lock-shot reel_001 1
python reel.py regenerate reel_001
python reel.py lock-shot reel_001 1 --unlock
python reel.py reorder reel_001 3 1 2
```

Positions are **1-based**; shot IDs refer to the film database. `reorder` must list every current position exactly once. Locks protect selections during `regenerate`; explicit manual editing still changes them. Regeneration preserves shot durations and locked entries, replaces unlocked choices, and does not scan the movie or render. Replacement fails if the new shot is too short. Removing a shot changes the reel duration. CLI edits save the previous plan in `reel_plans/history/`.

You can also edit `reel_plans/reel_001.json` directly. Each shot has `shot_id`, `source_in` (seconds **relative to the shot start**), `duration`, `crop_mode`, `locked`, and optionally normalized `crop_center: [x,y]`. The renderer validates boundaries, crop settings, source identity, and the shot-boundary signature. If reanalysis changes shot numbering, generate new plans. Arbitrary imported plans must carry the matching source fingerprint and database signature from a generated plan.

Durations are rounded to the nearest output frame. Preview and export use the same output frame rate. End-card time is included in the requested total. After manual edits, actual length is the sum of edited shot/card durations, not a time-stretch to `target_duration`.

## Architecture and data

| Module | Responsibility |
|---|---|
| `ingest.py` | ffprobe metadata, original reference, cached 640-pixel/12-fps proxy |
| `scene_detection.py` | Streaming color/pixel cut detector with minimum spacing and single-frame flash rejection |
| `shot_analysis.py` | Representative sampling, resumable per-shot checkpoints, feature aggregation |
| `frame_analysis.py` | Brightness, contrast, entropy, edges, quantized dominant colors, colorfulness |
| `motion_analysis.py` | Small-frame optical flow, global/residual movement, moving-subject estimate |
| `face_detection.py` | Lightweight OpenCV frontal-face cascade |
| `semantic.py` | Optional, content-addressed semantic-provider interface |
| `shot_ranker.py` | Mood-conditioned visual ranking and similarity penalties |
| `reel_director.py` | Paced, reproducible, distinct shot selections and non-destructive EDLs |
| `reframer.py` | Subject-weighted crop paths, dead zone, smoothing, pan limits, composition fallback |
| `renderer.py` | Original-source final renders, proxy previews, cached segments, verification |
| `editor.py` | Validated plan edits, revision backups, lock-aware regeneration |
| `thumbnails.py` | Labeled full-library, candidate, and selected-shot contact sheets |
| `end_cards.py` | Configurable text rendered with Pillow |

A project's `analysis/film.json`, `scenes.json`, `shots.json`, `frames/`, and `shot_cache/` are persistent. `scenes.json` currently contains **shots**, not inferred narrative scenes; `scene_id` is a shot identifier placeholder. `thumbnails/contact_*.jpg` shows the library, `reel_*_candidates_*.jpg` shows top candidates, and `reel_*_selected_*.jpg` follows the edit order. Every contact-sheet tile includes shot ID and source timestamp.

Analysis uses at most 40 samples per shot by default. Frames and optical-flow arrays stay small, and workers are capped at four (default one). `python reel.py analyze --workers 2` enables controlled parallel analysis; one worker is appropriate for constrained memory. Interrupting analysis preserves complete shot checkpoints; rerunning resumes. Cut detection itself restarts if interrupted before its final cache is written. Final databases and plans are written atomically.

Mood changes never trigger analysis. Proxy settings, analysis settings, and algorithm versions control cache invalidation. Visual checkpoints are keyed by source proxy and shot boundaries, so changing cut detection can reuse measurements for unchanged intervals even when shot IDs shift. Rendering has separate source/plan/filter/encoding cache keys, and sidecar JSON reports actual dimensions, duration, frames, source, and crop paths. `render_cache/` can be deleted when no render is running; the next render rebuilds needed clips. Generated full-quality clips can consume disk space. Use one writer per project at a time; simultaneous generation/editing in the same project is not supported.

## Framing

- `smart_crop`: face/moving-subject weighted crop, bounded by the image, with dead zone, temporal smoothing, and maximum normalized pan speed.
- `fit` / `letterbox`: preserve the full frame against black. These are intentionally aliases in this version.
- `blur_background`: preserve the full frame with an enlarged blurred background.
- `auto`: chooses a frame-preserving mode for detected separated/oversized faces or unstable subject estimates in a very narrow crop; otherwise uses smart crop.

`crop_center` fixes the virtual camera at a normalized center. Without an override, cached subject samples guide it. These are sampled detections, not identity-aware continuous face tracks. Fast motion, occlusions, profiles, and dark imagery can defeat the cascade. Review the previews; use a fixed center or frame-preserving mode when needed. The system cannot guarantee preservation of every important visual element.

Final default output is 1080×1920 H.264/yuv420p, 30 fps, with fast-start MP4 metadata. `--aspect` changes height relative to configured export width. `export.height` documents the default 9:16 canvas; requested aspect controls the actual height. Output dimensions are even. Encoding is CPU-only and uses a bounded thread count; GPU acceleration is not assumed. Preview is 360 pixels wide and uses the proxy.

## Audio

```bash
python reel.py generate --audio original --dialogue allow --mood "urban energy" --duration 15
python reel.py generate --audio muted --mood "quiet nocturnal" --duration 23
python reel.py generate --audio music --music "/Music/licensed track.wav" --duration 20
```

Muted is the default and produces a video without an audio stream. Original mode cuts the first audio stream at the exact source edit times. Each cut uses integer-frame video duration and stereo 48 kHz PCM audio; PCM is joined before a **single AAC encode**, avoiding per-cut AAC padding drift. Audio-free sources get silence when original audio is requested. Music mode loops/trims a user-provided track. It does not select, license, or beat-match music.

`dialogue_reduced` is an **experimental stereo center-cancellation effect**, not speech separation: it can remove centered music or fail to remove dialogue. `--dialogue avoid` is a planning intent, not a dialogue detector. Use muted audio to reliably avoid audible plot dialogue. Explicit `--audio original` takes priority and prints this limitation.

## Spoilers, semantics, and the director

`--spoilers low` excludes the last 20% of the film; medium excludes the last 5%; unrestricted removes this temporal cutoff. Explicitly excluded ranges always apply. Add `analysis/exclusions.json` in the project:

```json
{"excluded_ranges": [[4820, 5010], [6100, 6400]]}
```

Ranges use absolute source seconds. Any overlapping shot is excluded. Global exclusions can also be set in `config.yaml`. These controls **do not understand plot**; important spoilers can occur earlier. For release, review the selected footage and add exclusions as needed.

The default director is a local heuristic, not an Astra API call. It balances visual interest, faces, color, motion preferences, temporal spread, and visual/semantic similarity. Configurable mood pacing shapes longer opening/closing holds and quicker middle cuts. Variants apply different atmosphere/energy/emotion preferences and reuse penalties. With a small eligible library, some overlap is unavoidable. No character identity or narrative-scene clustering is currently available.

Astra or another creative agent can inspect the contact sheets and edit the same validated EDL; FFmpeg remains responsible for deterministic media operations. The production review can use this route without adding any API dependency. A built-in unattended model-backed director is a future extension.

Optional semantic analysis is configured with a trusted Python module:

```yaml
semantic:
  plugin: my_local_vision_provider
  version: '1'
```

That importable module implements `describe(image_path: str) -> dict` and may return `description`, `semantic_tags`, `mood_tags`, and `spoiler_score`. Results are cached by image SHA-256, provider name, and version. Change the provider version when its model or prompt changes. Exceptions are reported and completed visual checkpoints remain reusable. No default provider sends frames anywhere; install/enable your own local or external provider deliberately.

Brightness is labeled dark/bright; it is not claimed to establish actual day/night. Interior/exterior recognition, reliable emotional/narrative understanding, embeddings, beat detection, speech isolation, sophisticated saliency, and a visual timeline UI are deferred. The functional alternatives are visual mood heuristics, manual exclusions, contact sheets, and editable JSON/CLI controls.

## End cards and reusable test presets

In `config.yaml`:

```yaml
end_card:
  enabled: true
  duration: 2.5
  lines:
    - "YOUR FILM"
    - "FRIDAY NIGHT"
    - "YOUR VENUE"
```

Optional `font`, `background`, and `color` fields customize appearance. For unusual scripts supply a font that supports them. Text is drawn by Pillow, so punctuation is never interpreted as FFmpeg filter syntax.

The supplied presets are reusable requests, not film-specific code:

```bash
python reel.py generate --preset presets/atmosphere.json
python reel.py generate --preset presets/frenzy.json
python reel.py generate --preset presets/longing.json
```

Explicit command-line options override preset fields. Presets request 23, 15, and 25 seconds respectively, use low spoiler settings, and are muted for review.

## Verification

```bash
python -m unittest discover -s tests -v
python tests/integration.py
```

The integration test generates a new film with sharp cuts and moving shapes, exercises the actual CLI, and checks detection, three rendered variants, frame counts, complete decoding, original-audio waveform alignment, silent inputs, muted mode, every framing mode, end cards, preview, cache reuse, and manual edits/locks. It includes paths containing spaces and an apostrophe. No production film or network is needed. Temporary fixtures are removed on completion.

See `VALIDATION.md` for the actual run and production-film review results.
