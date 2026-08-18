# Conversion Mode

Conversion Mode creates local-event reels with restrained movie-trailer text
overlays. It never inserts standalone graphic cards.

## Open the editor

Load a movie project, then choose **Open Conversion Mode** from the Mood Montage
screen, or visit `/projects/<project-id>/conversion`.

## What it stores

- Film title and year
- Event date and time
- Venue and city
- Persistent FFS mark preference
- Ordered film and venue slots
- Per-slot source start, duration, top copy, and bottom copy
- Optional local venue-video paths
- Final CTA slot

Venue slots fall back to labeled movie footage until their local media paths
point to real files. This makes it possible to lock timing and copy before a
venue shoot, then replace the placeholders without rebuilding the reel.

## Rendering

- 1080 × 1920 H.264 video at 30 fps
- AAC stereo silent track for social-platform music
- DIN Condensed Bold headline overlays
- Avenir Next information overlays
- Approved persistent FFS square mark
- All information directly over footage

## API

- `GET /api/projects/<project-id>/conversion`
- `PUT /api/projects/<project-id>/conversion`
- `POST /api/projects/<project-id>/conversion/export`

The export is added to the normal project export registry and written to the
engine's `outputs/` folder.
