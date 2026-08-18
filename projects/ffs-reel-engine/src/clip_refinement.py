from __future__ import annotations

import math
import os
import platform
import re
import subprocess
import uuid
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from .film_index import FilmIndex


WORD_MATCH_THRESHOLD = 0.78
MAX_SCAN_SECONDS = 120.0
WORD_PREROLL = 0.24
WORD_POSTROLL = 0.35


def _tokens(value: str) -> list[str]:
    value = str(value).casefold().replace("’", "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", value, re.UNICODE)


def _score(target: list[str], candidate: list[str]) -> float:
    if not target or not candidate:
        return 0.0
    target_text = " ".join(target)
    candidate_text = " ".join(candidate)
    overlap = sum((Counter(target) & Counter(candidate)).values())
    coverage = overlap / len(target)
    precision = overlap / len(candidate)
    sequence = SequenceMatcher(None, target_text, candidate_text).ratio()
    result = 0.55 * sequence + 0.30 * coverage + 0.15 * precision
    if target == candidate:
        result = 1.0
    return result


def _token_timeline(words: list[dict]) -> list[dict]:
    timeline = []
    for word in words:
        try:
            start = float(word["start"])
            end = float(word["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            continue
        for token in _tokens(word.get("text", word.get("word", ""))):
            timeline.append({"token": token, "start": start, "end": end})
    return timeline


def _match_anchor(words: list[dict], anchor_quote: str,
                  expected_start: float | None = None) -> dict | None:
    target = _tokens(anchor_quote)
    timeline = _token_timeline(words)
    if len(target) < 2 or len(timeline) < len(target):
        return None

    candidates = []
    for width in range(max(2, len(target) - 2), min(len(timeline), len(target) + 2) + 1):
        for left in range(len(timeline) - width + 1):
            right = left + width - 1
            candidate = [item["token"] for item in timeline[left:left + width]]
            score = _score(target, candidate)
            if score >= WORD_MATCH_THRESHOLD:
                candidates.append({
                    "score": score, "left": left, "right": right,
                    "start": timeline[left]["start"], "end": timeline[right]["end"],
                })
    if not candidates:
        return None
    candidates.sort(key=lambda item: (
        -item["score"],
        abs(item["start"] - expected_start) if expected_start is not None else item["start"],
    ))
    best = candidates[0]
    # Repeated short phrases are safe only when the segment-level anchor supplies
    # a clear expected location.
    rivals = [item for item in candidates[1:]
              if item["score"] >= best["score"] - 0.015
              and abs(item["start"] - best["start"]) > 0.5]
    if len(target) <= 4 and rivals and expected_start is None:
        return None
    return best


def _scan_window(card: dict) -> tuple[float, float]:
    lower = float(card["evidence_start"])
    upper = float(card["evidence_end"])
    expected_start = card.get("anchor_start")
    expected_end = card.get("anchor_end")
    if expected_start is not None and expected_end is not None:
        begin = max(lower, float(expected_start) - 10.0)
        end = min(upper, float(expected_end) + 10.0)
    else:
        begin, end = lower, upper
    if end - begin > MAX_SCAN_SECONDS:
        center = (begin + end) / 2
        begin = max(lower, center - MAX_SCAN_SECONDS / 2)
        end = min(upper, begin + MAX_SCAN_SECONDS)
    if end - begin < 1.0:
        raise ValueError("The evidence passage is too short for dialogue refinement.")
    return begin, end


def _extract_audio(movie_path: Path, start: float, end: float, destination: Path) -> None:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
        "-i", str(movie_path), "-t", f"{end - start:.3f}", "-vn", "-ac", "1",
        "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(destination),
    ], capture_output=True, text=True)
    if result.returncode or not destination.is_file():
        raise ValueError("Could not extract audio for dialogue timing refinement.")


def _transcribe_words(audio_path: Path, offset: float, model_root: Path) -> list[dict]:
    use_mlx = (
        platform.machine() == "arm64"
        and os.environ.get("FFS_TRANSCRIBER") != "cpu"
        and not os.environ.get("CODEX_SANDBOX")
    )
    if use_mlx:
        try:
            import mlx_whisper
            result = mlx_whisper.transcribe(
                str(audio_path), path_or_hf_repo="mlx-community/whisper-small-mlx",
                language="en", word_timestamps=True,
            )
            source = "mlx_whisper_refinement"
        except Exception:
            # Metal may be unavailable in a headless/sandboxed macOS process
            # even though this is an Apple-Silicon machine. The short clip can
            # still be refined safely with the already-supported CPU backend.
            use_mlx = False
    if not use_mlx:
        import torch
        import whisper
        torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
        model_dir = model_root / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model = whisper.load_model("base", device="cpu", download_root=str(model_dir))
        result = model.transcribe(
            str(audio_path), language="en", fp16=False, word_timestamps=True
        )
        source = "whisper_cpu_refinement"

    words = []
    for segment in result.get("segments", []) or []:
        for word in segment.get("words", []) or []:
            text = str(word.get("word", word.get("text", ""))).strip()
            if not text:
                continue
            words.append({
                "start": offset + float(word["start"]),
                "end": offset + float(word["end"]),
                "text": text,
                "confidence": word.get("probability", word.get("confidence")),
                "source": source,
            })
    if not words:
        raise ValueError("Whisper returned no word timestamps for this evidence moment.")
    return words


def _silences(audio_path: Path, offset: float) -> list[tuple[float, float]]:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "info", "-i", str(audio_path),
        "-af", "silencedetect=noise=-38dB:d=0.12", "-f", "null", "-",
    ], capture_output=True, text=True)
    if result.returncode:
        return []
    starts = [float(value) for value in re.findall(r"silence_start: ([0-9.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end: ([0-9.]+)", result.stderr)]
    pairs = []
    end_index = 0
    for start in starts:
        while end_index < len(ends) and ends[end_index] < start:
            end_index += 1
        if end_index < len(ends):
            pairs.append((offset + start, offset + ends[end_index]))
            end_index += 1
    return pairs


def _bounds(card: dict, anchor_start: float, anchor_end: float,
            silences: list[tuple[float, float]]) -> tuple[float, float, bool]:
    lower = float(card["evidence_start"])
    upper = float(card["evidence_end"])
    requested = min(10.0, max(0.5, float(card.get("duration", 6.0))))
    start = max(lower, anchor_start - WORD_PREROLL)
    end = min(upper, max(anchor_end + WORD_POSTROLL, start + requested))
    snapped = False

    start_candidates = [silence_end for _, silence_end in silences
                        if anchor_start - 1.5 <= silence_end <= anchor_start + 0.1]
    if start_candidates:
        start = max(lower, max(start_candidates) - 0.08)
        snapped = True

    end_candidates = [silence_start for silence_start, _ in silences
                      if max(anchor_end + 0.12, end - 1.0) <= silence_start <= end + 1.0]
    if end_candidates:
        end = min(upper, min(end_candidates) + 0.08)
        snapped = True

    end = max(end, anchor_end + 0.12)
    if end - start > 10.0:
        end = min(upper, start + 10.0)
    if end < anchor_end:
        end = anchor_end
        start = max(lower, end - 10.0)
    if end - start < 0.5:
        end = min(upper, start + 0.5)
    return round(start, 3), round(end, 3), snapped


def refine_clip_alignment(index: FilmIndex, movie_path: Path, card: dict,
                          work_dir: Path, model_root: Path) -> dict:
    if card.get("type") != "clip":
        raise ValueError("Only movie clip cards can be dialogue-refined.")
    anchor_quote = str(card.get("anchor_quote", "")).strip()
    if len(_tokens(anchor_quote)) < 2:
        raise ValueError("This clip has no reliable dialogue anchor to refine.")
    if not movie_path.is_file():
        raise ValueError("The local movie file is no longer available.")
    scan_start, scan_end = _scan_window(card)
    expected = float(card["anchor_start"]) if card.get("anchor_start") is not None else None

    cached = index.transcript_words(scan_start, scan_end)
    match = _match_anchor(cached, anchor_quote, expected)
    timing_source = "cached_word_timestamps"
    words = cached
    audio_path = work_dir / f"refine-{card['id']}-{uuid.uuid4().hex[:8]}.wav"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        if match is None:
            _extract_audio(movie_path, scan_start, scan_end, audio_path)
            words = _transcribe_words(audio_path, scan_start, model_root)
            index.add_transcript_words(words, source=str(words[0]["source"]))
            match = _match_anchor(words, anchor_quote, expected)
            timing_source = str(words[0]["source"])
        if match is None:
            raise ValueError(
                "Whisper could not locate the quoted dialogue precisely. Keep the current manual trim."
            )
        if not audio_path.is_file():
            _extract_audio(movie_path, scan_start, scan_end, audio_path)
        silence_ranges = _silences(audio_path, scan_start)
        start, end, snapped = _bounds(
            card, float(match["start"]), float(match["end"]), silence_ranges
        )
        return {
            "source_start": start,
            "source_end": end,
            "duration": round(end - start, 3),
            "anchor_start": round(float(match["start"]), 3),
            "anchor_end": round(float(match["end"]), 3),
            "alignment_method": "word_anchor_silence_snap" if snapped else "word_anchor",
            "alignment_score": round(float(match["score"]), 3),
            "timing_source": timing_source,
            "timing_refined": True,
        }
    finally:
        audio_path.unlink(missing_ok=True)


__all__ = ["refine_clip_alignment"]
