from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any


class ConversionRenderError(RuntimeError):
    pass


_RUNNER = subprocess.run
_HEADLINE = Path("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf")
_INFO = Path("/System/Library/Fonts/Avenir Next.ttc")
_ENCODE = [
    "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
    "-ac", "2",
]


def _number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConversionRenderError(f"{label} must be a number.") from exc
    if not math.isfinite(result):
        raise ConversionRenderError(f"{label} must be finite.")
    return result


def _filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "\\\\")
    value = value.replace(":", "\\:").replace("'", "\\'")
    return f"'{value}'"


def _write_copy(path: Path, value: Any) -> Path:
    lines = []
    for line in str(value or "").replace("|", "\n").splitlines():
        lines.append(" ".join(line.split())[:72])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def _run(command: list[str], action: str) -> None:
    try:
        result = _RUNNER(command, capture_output=True, text=True)
    except OSError as exc:
        raise ConversionRenderError(f"{action} could not start: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or "FFmpeg returned an error.").strip().splitlines()[-1]
        raise ConversionRenderError(f"{action} failed: {detail}")


def default_conversion_config(project: dict) -> dict:
    duration = float(project.get("movie", {}).get("duration") or 30)
    starts = [0, 3, 5, 12, 20, 24]
    starts = [min(max(0.0, duration - 4), value) for value in starts]
    return {
        "mode": "conversion_overlay",
        "event": {
            "film_title": str(project.get("title") or "FILM").upper(),
            "year": "", "date": "", "time": "", "venue": "", "city": "FRESNO",
        },
        "persistent_logo": True,
        "slots": [
            {"kind": "film", "source_start": starts[0], "duration": 3,
             "audio_mode": "silent",
             "top_text": "FRESNO FILM SOCIETY PRESENTS",
             "bottom_text": "SPEND ONE NIGHT|IN VIENNA."},
            {"kind": "venue", "source_start": starts[1], "duration": 2,
             "audio_mode": "silent",
             "top_text": "ISLA EXTERIOR FOOTAGE · PLACEHOLDER", "bottom_text": "",
             "media_path": ""},
            {"kind": "film", "source_start": starts[2], "duration": 4,
             "audio_mode": "silent",
             "top_text": "", "bottom_text": "MEET JESSE|AND CÉLINE."},
            {"kind": "venue", "source_start": starts[3], "duration": 2,
             "audio_mode": "silent",
             "top_text": "ISLA TEA / ATMOSPHERE FOOTAGE · PLACEHOLDER",
             "bottom_text": "", "media_path": ""},
            {"kind": "film", "source_start": starts[4], "duration": 3,
             "audio_mode": "silent",
             "top_text": "", "bottom_text": "ONE NIGHT TOGETHER.|UNTIL DAWN."},
            {"kind": "film", "source_start": starts[5], "duration": 4,
             "audio_mode": "silent",
             "top_text": "", "bottom_text": "", "final_cta": True},
        ],
    }


def normalize_conversion_config(project: dict, raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ConversionRenderError("Conversion settings must be an object.")
    source_duration = _number(project.get("movie", {}).get("duration"), "Movie duration")
    event_raw = raw.get("event") if isinstance(raw.get("event"), dict) else {}
    event = {}
    for field in ("film_title", "year", "date", "time", "venue", "city"):
        event[field] = " ".join(str(event_raw.get(field, "")).split())[:100]
    slots_raw = raw.get("slots")
    if not isinstance(slots_raw, list) or not 1 <= len(slots_raw) <= 12:
        raise ConversionRenderError("Conversion Mode requires between 1 and 12 slots.")
    slots = []
    for index, item in enumerate(slots_raw, 1):
        if not isinstance(item, dict) or item.get("kind") not in {"film", "venue", "image"}:
            raise ConversionRenderError(f"Slot {index} must be a film, venue, or image slot.")
        duration = min(10.0, max(0.5, _number(item.get("duration"), f"Slot {index} duration")))
        start = max(0.0, _number(item.get("source_start", 0), f"Slot {index} start"))
        start = min(max(0.0, source_duration - duration), start)
        media_path = str(item.get("media_path") or "").strip()
        if item["kind"] == "image" and not media_path:
            raise ConversionRenderError(f"Slot {index} image path is required.")
        if media_path and not Path(media_path).expanduser().is_file():
            raise ConversionRenderError(f"Slot {index} venue footage does not exist.")
        audio_mode = str(item.get("audio_mode") or "silent")
        if audio_mode not in {"silent", "original", "reduced"}:
            raise ConversionRenderError(
                f"Slot {index} audio must be silent, original, or reduced."
            )
        if item["kind"] == "image":
            audio_mode = "silent"
        motion = str(item.get("motion") or "push_in")
        if motion not in {"push_in", "pull_out", "pan_left", "pan_right", "still"}:
            raise ConversionRenderError(f"Slot {index} has an unsupported photo motion.")
        slots.append({
            "kind": item["kind"], "source_start": round(start, 3),
            "duration": round(duration, 3), "media_path": media_path,
            "top_text": str(item.get("top_text") or "")[:240],
            "bottom_text": str(item.get("bottom_text") or "")[:240],
            "final_cta": bool(item.get("final_cta", False)),
            "audio_mode": audio_mode,
            "motion": motion,
        })
    return {
        "mode": "conversion_overlay", "event": event, "slots": slots,
        "persistent_logo": bool(raw.get("persistent_logo", True)),
    }


def _render_slot(movie: Path, slot: dict, event: dict, assets: Path, work: Path,
                 destination: Path, number: int, persistent_logo: bool) -> None:
    media = Path(slot["media_path"]).expanduser() if slot.get("media_path") else movie
    start = 0.0 if slot.get("media_path") else float(slot["source_start"])
    top = _write_copy(work / f"slot-{number:02d}-top.txt", slot.get("top_text"))
    bottom_value = slot.get("bottom_text")
    if slot.get("final_cta"):
        top = _write_copy(
            top, f"{event.get('film_title', '')} ({event.get('year', '')})".replace(" ()", "")
        )
        bottom_value = "|".join(filter(None, [
            " · ".join(filter(None, [event.get("date"), event.get("time")])),
            " · ".join(filter(None, [event.get("venue"), event.get("city")])),
        ]))
    bottom = _write_copy(work / f"slot-{number:02d}-bottom.txt", bottom_value)
    logo = assets / "ffs-square.png"
    is_image = slot.get("kind") == "image"
    inputs = (["-loop", "1", "-framerate", "30", "-i", str(media)] if is_image
              else ["-ss", f"{start:g}", "-i", str(media)])
    logo_filter = ""
    overlay_filter = ""
    if persistent_logo:
        inputs.extend(["-i", str(logo)])
        logo_filter = ";[1:v]scale=74:-1,format=rgba,lutrgb=r=255:g=255:b=255[logo]"
        overlay_filter = ";[base][logo]overlay=W-w-72:142:format=auto[v]"
        audio_input = 2
    else:
        overlay_filter = ";[base]format=yuv420p[v]"
        audio_input = 1
    inputs.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
    audio_mode = slot.get("audio_mode", "silent")
    audio_filter = ""
    audio_map = f"{audio_input}:a:0"
    if audio_mode in {"original", "reduced"}:
        gain = 1.0 if audio_mode == "original" else 0.25
        audio_filter = (
            f";[0:a:0]volume={gain:.3f},atrim=duration={float(slot['duration']):g},"
            "asetpts=PTS-STARTPTS[audio]"
        )
        audio_map = "[audio]"
    frames = max(1, round(float(slot["duration"]) * 30))
    motion = slot.get("motion", "push_in")
    if is_image:
        zoom = {"push_in": "min(zoom+0.0009,1.08)",
                "pull_out": "if(eq(on,1),1.08,max(zoom-0.0009,1.0))",
                "pan_left": "1.06", "pan_right": "1.06", "still": "1.0"}[motion]
        x = "iw/2-(iw/zoom/2)"
        if motion == "pan_left":
            x = f"(iw-iw/zoom)*(1-on/{frames})"
        elif motion == "pan_right":
            x = f"(iw-iw/zoom)*(on/{frames})"
        source_filter = (
            "[0:v]scale=1200:2134:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=1200:2134,"
            f"zoompan=z='{zoom}':x='{x}':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30,setsar=1,"
        )
    else:
        source_filter = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=1080:1920,setsar=1,"
        )
    filters = (
        source_filter +
        f"drawtext=fontfile={_filter_path(_INFO)}:textfile={_filter_path(top)}:"
        "expansion=none:fontcolor=0xF2EFE5:fontsize=31:line_spacing=4:x=72:y=150:"
        "borderw=2:bordercolor=black@0.55,"
        f"drawtext=fontfile={_filter_path(_HEADLINE)}:textfile={_filter_path(bottom)}:"
        "expansion=none:fontcolor=0xF2EFE5:fontsize=94:line_spacing=2:x=72:"
        "y=h-text_h-235:borderw=3:bordercolor=black@0.62[base]"
        f"{logo_filter}{overlay_filter}{audio_filter}"
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", *inputs,
               "-t", f"{slot['duration']:g}", "-filter_complex", filters,
               "-map", "[v]", "-map", audio_map, *_ENCODE,
               "-shortest", "-movflags", "+faststart", "-y", str(destination)]
    _run(command, f"Conversion slot {number}")


def render_conversion_reel(project: dict, config: dict, work_dir: Path,
                           output_path: Path, assets_dir: Path) -> dict:
    normalized = normalize_conversion_config(project, config)
    movie = Path(str(project.get("movie", {}).get("path") or "")).expanduser()
    if not movie.is_file():
        raise ConversionRenderError("The project movie is unavailable.")
    assets_dir = Path(assets_dir)
    if not (assets_dir / "ffs-square.png").is_file():
        raise ConversionRenderError("The approved FFS square logo is unavailable.")
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    segments = []
    for index, slot in enumerate(normalized["slots"], 1):
        segment = work_dir / f"segment-{index - 1:03d}.mp4"
        _render_slot(movie, slot, normalized["event"], assets_dir, work_dir,
                     segment, index, normalized["persistent_logo"])
        segments.append(segment)
    concat = work_dir / "concat.txt"
    concat.write_text("".join(f"file '{str(item.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for item in segments))
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "concat",
          "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags",
          "+faststart", "-y", str(output_path)], "Conversion Reel assembly")
    return {
        "duration": round(sum(float(slot["duration"]) for slot in normalized["slots"]), 3),
        "slot_count": len(normalized["slots"]), "mode": "conversion_overlay",
        "venue_slot_count": sum(slot["kind"] == "venue" for slot in normalized["slots"]),
        "image_slot_count": sum(slot["kind"] == "image" for slot in normalized["slots"]),
    }


__all__ = [
    "ConversionRenderError", "default_conversion_config", "normalize_conversion_config",
    "render_conversion_reel",
]
