from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .detection import build_windows, detect_candidates
from .media import extract_clips
from .providers import provider_for
from .ranking import rank_candidates
from .report import write_outputs
from .transcription import transcribe_candidates


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Find clip-worthy moments from livestream chat bursts")
    p.add_argument("vod_url", help="Twitch, Kick, or YouTube VOD/live URL")
    p.add_argument("--output", "-o", default="runs/latest", help="Output directory")
    p.add_argument("--config", help="JSON config path")
    p.add_argument("--chat-file", help="Use an existing chat JSON export")
    p.add_argument("--video-file", help="Use an existing video file")
    p.add_argument("--reuse", action="store_true", help="Reuse source video and chat.json in output")
    p.add_argument("--skip-video", action="store_true", help="Analyze chat and report only")
    p.add_argument("--skip-transcription", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    config = Config.load(args.config)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    provider = provider_for(args.vod_url)
    (output / "run.json").write_text(json.dumps({"url": args.vod_url, "provider": provider.name, "config": config.to_dict()}, indent=2), encoding="utf-8")
    try:
        chat_path = Path(args.chat_file) if args.chat_file else output / "chat.json"
        if not args.chat_file and (not chat_path.exists() or not args.reuse):
            chat_path = provider.download_chat(args.vod_url, output)
        messages = provider.parse_chat(chat_path)
        windows = build_windows(messages, config)
        candidates = detect_candidates(windows, config)
        video = Path(args.video_file) if args.video_file else next(iter(output.glob("source.*")), None)
        if not args.skip_video:
            if not args.video_file and (video is None or not video.exists() or not args.reuse):
                video = provider.download_video(args.vod_url, output, config.video_quality)
            if video is None or not video.exists():
                raise ValueError(f"Video file does not exist: {video}")
            extract_clips(video, candidates, output)
            if config.transcribe and not args.skip_transcription:
                transcribe_candidates(candidates, output, config.whisper_model)
        rank_candidates(candidates)
        write_outputs(output, args.vod_url, provider.name, windows, candidates)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Found {len(candidates)} candidates. Open {output / 'report.html'}")
    return 0
