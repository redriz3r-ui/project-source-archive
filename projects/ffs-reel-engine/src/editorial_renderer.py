from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from .captions import extract_clip_captions, write_ass_captions


class EditorialRenderError(RuntimeError):
    """Raised when an editorial storyboard cannot be rendered safely."""


# Kept as a module attribute so tests and future background-job orchestration can
# replace the process runner without changing the public renderer interface.
_RUNNER = subprocess.run

_SANS_FONT = Path("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf")
_SERIF_FONT = Path("/System/Library/Fonts/NewYork.ttf")
_CARD_TYPES = {"hook", "clip", "observation", "interpretation", "end_card"}
_TEXT_TYPES = _CARD_TYPES - {"clip"}

_ENCODE_ARGS = [
    "-r", "30",
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "160k",
    "-ar", "48000",
    "-ac", "2",
]

_TEXT_STYLES = {
    "hook": {
        "background": "#15110E", "accent": "#C64D35", "copy": "#F2EFE5",
        "muted": "#C99A83", "label": "HOOK", "font_size": 88, "wrap": 25,
    },
    "observation": {
        "background": "#F2EFE5", "accent": "#C64D35", "copy": "#171411",
        "muted": "#725F54", "label": "OBSERVATION", "font_size": 76, "wrap": 29,
    },
    "interpretation": {
        "background": "#26343C", "accent": "#E1A16E", "copy": "#F5EFE5",
        "muted": "#BFC9C8", "label": "INTERPRETATION", "font_size": 76, "wrap": 29,
    },
}


def _number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise EditorialRenderError(f"{label} must be a number.") from exc
    if not math.isfinite(result):
        raise EditorialRenderError(f"{label} must be finite.")
    return result


def _seconds_arg(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _filter_path(path: Path) -> str:
    """Quote a path for an FFmpeg filter option, not for the shell."""
    value = str(path.resolve()).replace("\\", "\\\\")
    value = value.replace(":", "\\:").replace("'", "\\'")
    return f"'{value}'"


def _concat_path(path: Path) -> str:
    # FFmpeg's concat demuxer uses its own single-quote syntax.
    return str(path.resolve()).replace("'", "'\\''")


def _wrap_copy(value: Any, width: int) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return " "
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(
            " ".join(paragraph.split()), width=width, break_long_words=False,
            break_on_hyphens=False,
        ) or [""])
    return "\n".join(lines)


def _write_text(path: Path, value: Any, width: int) -> Path:
    path.write_text(_wrap_copy(value, width) + "\n", encoding="utf-8")
    return path


def _drawtext(*, font: Path, text_file: Path, color: str, size: int,
              x: str, y: str, line_spacing: int = 12) -> str:
    return (
        f"drawtext=fontfile={_filter_path(font)}:textfile={_filter_path(text_file)}:"
        f"expansion=none:fontcolor={color}:fontsize={size}:line_spacing={line_spacing}:"
        f"x={x}:y={y}"
    )


def _run(command: list[str], action: str) -> None:
    try:
        result = _RUNNER(command, capture_output=True, text=True)
    except OSError as exc:
        raise EditorialRenderError(f"{action} could not start: {exc}") from exc
    if result.returncode:
        stderr = str(getattr(result, "stderr", "") or "").strip().splitlines()
        detail = stderr[-1] if stderr else "FFmpeg returned an error."
        raise EditorialRenderError(f"{action} failed: {detail}")


def _clip_filter(crop_x: float, captions_path: Path | None = None) -> str:
    filters = [
        "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop=1080:1920:x=(in_w-out_w)*{crop_x:.4f}:y=(in_h-out_h)/2",
        "setsar=1",
    ]
    if captions_path is not None:
        filters.append(f"subtitles=filename={_filter_path(captions_path)}")
    filters.append("format=yuv420p")
    return ",".join(filters)


def _render_clip(movie_path: Path, card: dict, destination: Path, card_number: int,
                 captions_path: Path | None = None) -> float:
    start = _number(card.get("source_start"), f"Clip card {card_number} start")
    end = _number(card.get("source_end"), f"Clip card {card_number} end")
    if start < 0 or end <= start:
        raise EditorialRenderError(
            f"Clip card {card_number} must have an end time after its non-negative start time."
        )
    duration = end - start
    crop_x = _number(card.get("crop_x", 0.5), f"Clip card {card_number} crop focus")
    crop_x = min(1.0, max(0.0, crop_x))
    original_audio = bool(card.get("original_audio", True))

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", _seconds_arg(start), "-i", str(movie_path),
    ]
    if not original_audio:
        command.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
    command.extend([
        "-t", _seconds_arg(duration),
        "-vf", _clip_filter(crop_x, captions_path),
        "-map", "0:v:0", "-map", "0:a:0" if original_audio else "1:a:0",
        *_ENCODE_ARGS,
        "-shortest", "-movflags", "+faststart", "-y", str(destination),
    ])
    _run(command, f"Clip card {card_number}")
    return duration


def _standard_text_filter(card_type: str, assets: dict[str, Path]) -> str:
    style = _TEXT_STYLES[card_type]
    return ",".join([
        f"drawbox=x=72:y=112:w=12:h=218:color={style['accent']}:t=fill",
        _drawtext(
            font=_SANS_FONT, text_file=assets["label"], color=style["accent"],
            size=42, x="112", y="126", line_spacing=4,
        ),
        _drawtext(
            font=_SERIF_FONT, text_file=assets["body"], color=style["copy"],
            size=int(style["font_size"]), x="(w-text_w)/2", y="(h-text_h)/2",
            line_spacing=22,
        ),
        _drawtext(
            font=_SANS_FONT, text_file=assets["brand"], color=style["muted"],
            size=38, x="72", y="h-156", line_spacing=4,
        ),
        "format=yuv420p",
    ])


def _end_card_filter(assets: dict[str, Path]) -> str:
    return ",".join([
        "drawbox=x=72:y=154:w=16:h=292:color=#C64D35:t=fill",
        _drawtext(
            font=_SANS_FONT, text_file=assets["brand"], color="#171411",
            size=48, x="116", y="178", line_spacing=4,
        ),
        _drawtext(
            font=_SERIF_FONT, text_file=assets["title"], color="#171411",
            size=86, x="(w-text_w)/2", y="(h-text_h)/2-80", line_spacing=22,
        ),
        _drawtext(
            font=_SANS_FONT, text_file=assets["body"], color="#536873",
            size=46, x="(w-text_w)/2", y="h-430", line_spacing=10,
        ),
        "format=yuv420p",
    ])


def _render_text_card(project: dict, card: dict, destination: Path,
                      work_dir: Path, card_number: int) -> float:
    card_type = str(card.get("type", ""))
    duration = _number(card.get("duration"), f"{card_type} card {card_number} duration")
    if duration <= 0 or duration > 60:
        raise EditorialRenderError(
            f"{card_type} card {card_number} duration must be greater than 0 and at most 60 seconds."
        )

    prefix = f"card-{card_number:03d}"
    brand = _write_text(work_dir / f"{prefix}-brand.txt", "FRESNO FILM SOCIETY", 40)
    if card_type == "end_card":
        assets = {
            "brand": brand,
            "title": _write_text(
                work_dir / f"{prefix}-title.txt", str(project.get("title") or "FILM").upper(), 22,
            ),
            "body": _write_text(work_dir / f"{prefix}-body.txt", card.get("text"), 30),
        }
        background = "#F2EFE5"
        video_filter = _end_card_filter(assets)
    else:
        style = _TEXT_STYLES[card_type]
        assets = {
            "brand": brand,
            "label": _write_text(work_dir / f"{prefix}-label.txt", style["label"], 30),
            "body": _write_text(
                work_dir / f"{prefix}-body.txt", card.get("text"), int(style["wrap"]),
            ),
        }
        background = str(style["background"])
        video_filter = _standard_text_filter(card_type, assets)

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i",
        f"color=c={background}:s=1080x1920:r=30:d={_seconds_arg(duration)}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", _seconds_arg(duration), "-vf", video_filter,
        "-map", "0:v:0", "-map", "1:a:0",
        *_ENCODE_ARGS,
        "-shortest", "-movflags", "+faststart", "-y", str(destination),
    ]
    _run(command, f"{card_type.replace('_', ' ').title()} card {card_number}")
    return duration


def render_editorial_storyboard(project: dict, storyboard: dict, work_dir: Path,
                                output_path: Path, *,
                                transcript_segments: list[dict] | None = None) -> dict:
    """Render an ordered editorial storyboard as a vertical, hard-cut MP4.

    Movie/index/project data is read-only. Intermediate video and safe UTF-8 text
    assets are written only beneath ``work_dir``; the finished file is written to
    ``output_path``.
    """
    movie = project.get("movie") if isinstance(project, dict) else None
    movie_value = movie.get("path") if isinstance(movie, dict) else None
    if not movie_value:
        raise EditorialRenderError("The project does not reference a movie file.")
    movie_path = Path(str(movie_value)).expanduser().resolve()
    if not movie_path.is_file():
        raise EditorialRenderError("The project's movie file could not be found.")

    cards = storyboard.get("cards") if isinstance(storyboard, dict) else None
    if not isinstance(cards, list) or not cards:
        raise EditorialRenderError("The editorial storyboard has no cards to render.")
    for number, card in enumerate(cards, 1):
        if not isinstance(card, dict) or str(card.get("type", "")) not in _CARD_TYPES:
            raise EditorialRenderError(f"Storyboard card {number} has an unsupported type.")

    work_dir = Path(work_dir).expanduser().resolve()
    output_path = Path(output_path).expanduser().resolve()
    if output_path == movie_path:
        raise EditorialRenderError("The editorial export cannot overwrite the source movie.")
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EditorialRenderError(f"Could not prepare the editorial render folder: {exc}") from exc

    segments: list[Path] = []
    durations: list[float] = []
    clip_count = 0
    caption_cue_count = 0
    captions_enabled = bool(storyboard.get("captions_enabled", True))
    try:
        transcript = list(transcript_segments or [])
    except TypeError as exc:
        raise EditorialRenderError("Transcript segments must be an iterable of caption units.") from exc
    for number, card in enumerate(cards, 1):
        segment = work_dir / f"segment-{number - 1:03d}.mp4"
        if card["type"] == "clip":
            captions_path = None
            if captions_enabled and transcript:
                start = _number(card.get("source_start"), f"Clip card {number} start")
                end = _number(card.get("source_end"), f"Clip card {number} end")
                try:
                    cues = extract_clip_captions(transcript, start, end)
                except ValueError as exc:
                    raise EditorialRenderError(f"Clip card {number} captions are invalid: {exc}") from exc
                if cues:
                    captions_path = work_dir / f"card-{number:03d}-captions.ass"
                    try:
                        write_ass_captions(cues, captions_path)
                    except (OSError, TypeError, ValueError, KeyError) as exc:
                        raise EditorialRenderError(
                            f"Could not prepare captions for clip card {number}: {exc}"
                        ) from exc
                    caption_cue_count += len(cues)
            duration = _render_clip(movie_path, card, segment, number, captions_path)
            clip_count += 1
        else:
            duration = _render_text_card(project, card, segment, work_dir, number)
        segments.append(segment)
        durations.append(duration)

    concat_file = work_dir / "concat.txt"
    try:
        concat_file.write_text(
            "".join(f"file '{_concat_path(segment)}'\n" for segment in segments),
            encoding="utf-8",
        )
    except OSError as exc:
        raise EditorialRenderError(f"Could not write the editorial assembly list: {exc}") from exc

    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", "-movflags", "+faststart", "-y", str(output_path),
    ], "Editorial Reel assembly")

    return {
        "duration": round(sum(durations), 3),
        "card_count": len(cards),
        "clip_count": clip_count,
        "captions_enabled": captions_enabled,
        "caption_cue_count": caption_cue_count,
    }


__all__ = ["EditorialRenderError", "render_editorial_storyboard"]
