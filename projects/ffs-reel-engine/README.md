# FFS Reel Engine

A local-first content engine for turning a movie you are licensed to use into
reviewable Fresno Film Society Instagram Reel drafts.

The first recipe is **Mood Montage**: import a movie, choose Balanced or build a
reusable 72-frame visual overview, replace or arrange shots, adjust per-shot
timing/framing/audio, add optional FFS cards, and export a post-ready 9:16
montage. Romantic, Melancholic, Dreamy, Energetic, City, Architecture, Night,
Nature, Dialogue-driven, and Custom styles search saved descriptions of sampled
movie frames. A mood first uses the overview to route its search, then reopens
the strongest regions, detects their cuts, describes up to 96 shot-level frames,
and saves a reusable mood-specific index. Balanced remains a zero-index
full-runtime fallback.

## Run

Requirements: Apple Silicon Mac, FFmpeg, and FFprobe. The project-local Python
environment includes Flask and MLX Whisper.

```bash
.venv/bin/python app.py
```

Open <http://127.0.0.1:8777>. Movie files remain in their original location;
the project stores a link to the file rather than copying the feature.

To build or resume the existing *Before Sunrise* transcript index directly:

```bash
.venv/bin/python transcribe_project.py before-sunrise-df826b
```

The job saves every completed ten-minute chunk. Press Control+C to request a
safe pause; running the same command resumes from saved progress.

## OpenAI editorial research

Movie processing, transcription, embeddings, and clip export stay local.
For an editorial idea, OpenAI can direct a bounded research pass over the local
index: it develops search angles, requests relevant transcript passages and
scene context, and assembles a saved evidence board. The initial research sends
only the topic and text excerpts returned by those local search tools.

Afterward, **Analyze evidence frames** is an optional visual pass. It extracts
three compressed still frames from each already-selected evidence moment and
sends only those frames, their timestamps, and the associated evidence text to
OpenAI. It never sends the movie file or arbitrary full-film footage. The
resulting visible observations remain attached to their exact evidence IDs and
are saved locally with the research board.

Mood Montage has a separate one-time **visual overview**. It samples 72
representative still frames across the full runtime and sends those compressed
JPEGs to the configured OpenAI vision model in small resumable batches. OpenAI
returns concrete visual descriptions; the app embeds and searches those
descriptions locally afterward. The overview is only a routing map. The first
time a particular mood is built, the engine detects cuts inside eight promising
regions, extracts up to 96 shot-level frames, and visually catalogs those frames
in resumable OpenAI batches. Rebuilding the same mood reuses that dense local
index. The movie file and video clips are never uploaded.

1. Open `.env` in this project.
2. Add a project-scoped API key after `OPENAI_API_KEY=`.
3. Optionally change `OPENAI_EDITORIAL_MODEL`.
   `OPENAI_VISUAL_MODEL` can separately override the visual-analysis model.
4. Restart the Flask server.

Never put the API key in browser JavaScript or commit `.env`.

## Current milestone

- local movie ingestion without transcription
- true visual cut detection with timestamped shot thumbnails
- selectable, reorderable montage cards with editable timing
- saved Mood Montage drafts with full-runtime Balanced selection or visual-index
  Romantic, Melancholic, Dreamy, Energetic, City, Architecture, Night, Nature,
  Dialogue-driven, and Custom selection
- explainable visual matches, full-film diversity scoring, and refresh restoration
- per-shot full-frame/crop, horizontal focus, movie-audio, and preview controls
- optional FFS opening/end cards and a finished 9:16 browser preview
- technical media inspection
- shared horizontal framing control
- muted 1080×1920 H.264/AAC export
- semantic full-film evidence retrieval
- OpenAI-directed transcript research with server-validated, persistent evidence boards
- opt-in representative-frame analysis for grounded composition, blocking, gesture,
  lighting/color, setting/object, and camera-viewpoint observations
- three-concept generation that keeps the selected research evidence authoritative
- persistent editable editorial storyboards with transcript-anchored clip in/out points, preview, trim, audio, focus, reorder, and delete controls
- on-demand local word-level dialogue alignment with silence-aware clip-boundary snapping
- transcript-timed dialogue captions with a storyboard-level on/off control and live clip preview
- local 1080×1920 editorial Reel export with FFS text cards, ordered hard cuts, per-clip audio/framing, burned captions, full-Reel preview, and download

The transcript and semantic index power the editorial-analysis workflow. Mood
Montage uses its own reusable visual-frame catalog instead. Balanced remains
available without either index. The visual catalog samples the feature rather
than examining every frame, so the detected-shot browser and editable draft
remain the final human review layer.
