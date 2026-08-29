# StreamClip MVP

A local-first pipeline that turns a Twitch, Kick, or YouTube VOD into ranked short-form clip candidates:

`chat + video → normalized burst detection → merged events → 45–90s clips → transcription → ranking → HTML/CSV/JSON report`

The first milestone intentionally has no web UI or cloud services. Provider-specific behavior lives behind a small adapter, while detection, media handling, transcription, ranking, and reporting remain independent modules.

## Requirements

- Python 3.10+
- `ffmpeg` available on your PATH (only required for clip creation)
- Enough disk space for the source VOD and generated clips

On macOS, a typical setup is:

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[transcribe,dev]'
```

For chat-only analysis without Whisper, install the smaller set:

```bash
pip install -e '.[dev]'
```

## Run

```bash
python analyze.py 'https://www.twitch.tv/videos/VIDEO_ID'
```

Outputs go to `runs/latest/`:

- `report.html` — burst graph and ranked candidate table
- `candidates.csv` / `candidates.json` — top timestamps and scores
- `windows.json` — full binned timeline for later modeling
- `clips/` — generated MP4 candidates
- `chat.json` and `source.mp4` — downloaded inputs
- `run.json` — source, provider, and effective config

Useful development modes:

```bash
# Fast chat-only pass (no VOD download, clipping, or transcription)
python analyze.py URL --chat-file path/to/chat.json --skip-video

# Reuse already-downloaded inputs and skip Whisper
python analyze.py URL --output runs/kai-test --reuse --skip-transcription

# Custom thresholds
cp config.example.json config.json
python analyze.py URL --config config.json --output runs/kai-test
```

## Detection approach

Chat is divided into 5-second windows. Each window tracks message volume, unique chatters, reaction phrase density, and repeated-message ratio. Volume and unique-chat activity are normalized against a rolling five-minute baseline using median absolute deviation with a Poisson-like noise floor. This matters for Kai-like chats where raw volume is always high.

Windows exceeding the configured composite threshold are spikes. Spikes within `merge_gap_seconds` become a single event so one reaction does not yield several overlapping clips. The event peak anchors a configurable pre/post window, constrained to 45–90 seconds.

The MVP standalone score combines normalized burst strength, reaction density, chatter diversity, transcript length, and the presence of a simple early verbal hook. It is deliberately transparent and heuristic: posting outcomes can later replace these weights with a learned model.

## Provider boundaries

`streamclip/providers.py` contains Twitch, Kick, and YouTube adapters. The MVP uses `chat-downloader` for replay chat and `yt-dlp` for media, while keeping the provider interface replaceable.

For Twitch, the adapter automatically falls back to `TwitchDownloaderCLI` when `chat-downloader` is rejected by Twitch. Put `TwitchDownloaderCLI` on your PATH or point the app to it:

```bash
export STREAMCLIP_TWITCH_DOWNLOADER=/path/to/TwitchDownloaderCLI
python analyze.py 'https://www.twitch.tv/videos/VIDEO_ID' --skip-video
```

VOD replay chat availability varies by platform and stream. Kick support is best-effort because its endpoints change more often. Livestream URLs may remain incomplete until the broadcast and chat replay are finalized; a completed VOD is the reliable first target.

## Tests

```bash
pytest
```

The tests synthesize a high-volume baseline, inject adjacent anomalous bursts, and verify normalization, detection, merging, and empty-input behavior.

## Compare detections with public Twitch clips

With credentials from a registered Twitch developer application, public clip metadata can provide evaluation labels:

```bash
export TWITCH_CLIENT_ID=your_client_id
export TWITCH_CLIENT_SECRET=your_client_secret
python compare_twitch_clips.py \
  --vod-id 2855528442 --broadcaster-id 211234859 \
  --started-at 2026-08-24T22:13:14Z --duration 152929 \
  --candidates runs/adapt-alaska/candidates.json
```

The command obtains an app access token, pages through clips created during the broadcast, filters them to the requested VOD, and reports the nearest detected peak and timing distance. Keep the client secret out of config files and version control.

## Project structure

```text
analyze.py                 CLI compatibility entry point
streamclip/
  cli.py                   pipeline orchestration
  providers.py             Twitch/Kick/YouTube ingestion adapters
  detection.py             windows, rolling normalization, spike merging
  media.py                 ffmpeg candidate extraction
  transcription.py         optional faster-whisper integration
  ranking.py               transparent short-form heuristic
  report.py                HTML graph and CSV/JSON outputs
tests/                     burst detector tests and fixtures
config.example.json        tunable defaults
```

## Practical first Kai test

Start with `--skip-video` to validate chat acquisition and inspect the timestamp report. Then rerun the same output directory with `--reuse` to download/process media once the thresholds look useful. A 24-hour 1080p VOD is expensive in storage and processing time, so using a lower `video_quality` (for example 720p) is sensible during detector calibration.
