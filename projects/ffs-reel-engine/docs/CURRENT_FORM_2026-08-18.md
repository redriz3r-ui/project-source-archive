# Reel Engine — Current Form Snapshot

Snapshot date: 2026-08-18

Snapshot branch: `snapshot/current-form-2026-08-18`

## Product today

The Reel Engine is a local-first Flask application that turns licensed film
media into vertical Fresno Film Society reel drafts. It currently exposes three
distinct workflows built on related media-processing and rendering primitives.

### Mood Montage

- One feature film per project
- Visual shot detection and representative thumbnails
- Balanced full-runtime selection and mood-specific visual search
- Editable shot order, timing, crop focus, audio, and packaging
- 1080 × 1920 H.264/AAC export

### Editorial Reel

- Transcript and semantic-index research
- Saved evidence boards and optional representative-frame analysis
- Generated concepts grounded in selected evidence
- Editable storyboard cards, dialogue timing refinement, and captions
- Local vertical export

### Conversion Mode

- Trailer-style text directly over footage
- Persistent approved FFS mark
- Editable top and bottom copy
- Film and venue slots with movie-footage placeholders
- Event title, year, date, time, venue, city, and final CTA
- Approved FFS brand assets and legal macOS font substitutes

## Current technical shape

- Python and Flask application in `app.py`
- Project orchestration in `src/engine.py`
- One `project["movie"]` source binding per project
- One project-local `FilmIndex` SQLite database
- FFmpeg/FFprobe media processing and rendering
- Local MLX Whisper transcription
- Optional OpenAI-assisted editorial and visual research
- JSON project persistence beneath ignored `work/projects/`
- Generated reels beneath ignored `outputs/`

## Current UI shape

The interface is segmented into Mood Montage, scene/evidence research,
Editorial Storyboard, and Conversion Mode pages. These workflows function, but
the product risks presenting recipes as different applications even though they
share the same core operations.

## Agreed product direction

**One media library → one analysis engine → one storyboard editor → multiple
recipes.**

The preferred editing model is a visual storyboard, not a traditional timeline.
Every storyboard card should use a shared structure containing:

- Source ID and source type
- In/out points and duration
- Vertical crop and focus
- Original audio and volume
- Captions
- Top and bottom text
- Speaker or film identification
- Persistent or per-card branding

Mood Montage, Film Introduction, Editorial, Event Promotion, and Event Recap
should become starting recipes that populate the same storyboard editor.

## Next stress test

The planned Cinehan Nights recap must support concurrent processing of:

1. *Manila in the Claws of Light*
2. *Perfumed Nightmare*
3. *Himala*
4. Event footage
5. Audience conversations and post-screening discussion

This requires a backward-compatible multi-source media library with independent
source indexes and processing status. It should not replace the singular
`movie` field abruptly or break existing single-film projects.

## Known limitations

- Project schema is fundamentally single-source.
- Visual and transcript indexes are bound to one feature film.
- Conversion Mode has its own editor instead of using the shared storyboard.
- Cross-source browsing and rendering are not implemented.
- Concurrent multi-film processing is not implemented.
- Event conversations lack a dedicated speaker/caption workflow.

## Verification state

- Full automated suite: 65 tests passing
- Conversion renderer produced a real 1080 × 1920, 18-second MP4
- Approved FFS logo assets live under `assets/ffs-brand/`
- Generated media, project data, `.env`, and `.venv` are excluded from Git

## Run locally

```bash
.venv/bin/python app.py
```

Open `http://127.0.0.1:8777`.
