from __future__ import annotations

import base64
import json
import math
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from openai import (
    APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field

from .editorial_rerank import DEFAULT_MODEL
from .semantic_search import MODEL_NAME, _model


DEFAULT_SAMPLE_COUNT = 72
BATCH_SIZE = 12
MAX_IMAGE_BYTES = 1_500_000


class VisualSampleDescription(BaseModel):
    sample_id: int = Field(ge=1)
    summary: str = Field(min_length=5, max_length=260)
    tags: list[str] = Field(min_length=2, max_length=12)
    setting: str = Field(min_length=2, max_length=100)
    lighting_color: str = Field(min_length=2, max_length=140)
    composition: str = Field(min_length=2, max_length=140)
    people_activity: str = Field(min_length=2, max_length=140)
    energy: str = Field(min_length=2, max_length=100)


class VisualSampleBatch(BaseModel):
    samples: list[VisualSampleDescription] = Field(min_length=1, max_length=BATCH_SIZE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _api_error(exc: Exception) -> ValueError:
    if isinstance(exc, AuthenticationError):
        return ValueError("OpenAI rejected the API key. Check .env and restart the server.")
    if isinstance(exc, RateLimitError):
        return ValueError("OpenAI rate limit or account quota reached. Check API billing and try again.")
    if isinstance(exc, APITimeoutError):
        return ValueError("Visual movie indexing took too long. Run it again to resume.")
    if isinstance(exc, APIConnectionError):
        return ValueError("Could not connect to OpenAI. Run visual indexing again to resume.")
    if isinstance(exc, APIError):
        return ValueError(f"OpenAI could not describe the movie frames: {exc.message}")
    return ValueError("OpenAI could not describe the movie frames.")


def _data_url(path: Path) -> str:
    data = path.read_bytes()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("A visual-index frame is empty or unexpectedly large.")
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def extract_visual_samples(movie_path: Path, destination: Path, *, duration: float,
                           sample_count: int = DEFAULT_SAMPLE_COUNT) -> list[dict]:
    if not movie_path.is_file() or not math.isfinite(duration) or duration <= 0:
        raise ValueError("The local movie is unavailable for visual indexing.")
    sample_count = min(120, max(24, int(sample_count)))
    destination.mkdir(parents=True, exist_ok=True)
    samples = []
    for index in range(sample_count):
        timestamp = duration * (index + 0.5) / sample_count
        filename = f"visual-sample-{index + 1:04d}.jpg"
        path = destination / filename
        if not path.is_file():
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", f"{timestamp:.3f}", "-i", str(movie_path), "-frames:v", "1",
                "-vf", "scale='min(640,iw)':-2", "-q:v", "4", "-y", str(path),
            ], capture_output=True, text=True)
            if result.returncode or not path.is_file():
                raise ValueError(f"Could not extract visual sample {index + 1}.")
        samples.append({
            "sample_id": index + 1, "timestamp": round(timestamp, 3),
            "filename": filename, "path": str(path),
        })
    return samples


def _instructions() -> str:
    return """You are building a searchable visual catalog for a film editor.
Describe only what is visibly present in each supplied frame. Do not use outside knowledge of the
film, infer dialogue, identify actors, or claim emotions as fact. Make the summary and tags useful
for visual searches such as architecture, city streets, night, warm interiors, crowds, solitude,
romantic proximity, movement, nature, color palettes, and composition. Distinguish visible people
and activity from interpretations. Return exactly one record for every supplied sample_id."""


def _content(samples: list[dict]) -> list[dict]:
    content = [{
        "type": "input_text",
        "text": json.dumps({"samples": [{
            "sample_id": item["sample_id"], "timestamp": item["timestamp"]
        } for item in samples]}),
    }]
    for item in samples:
        content.extend([
            {"type": "input_text", "text": (
                f"sample_id={item['sample_id']}; timestamp={item['timestamp']:.3f} seconds"
            )},
            {"type": "input_image", "image_url": _data_url(Path(item["path"])),
             "detail": "low"},
        ])
    return content


def _load_cache(path: Path) -> dict[int, dict]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
        return {int(item["sample_id"]): item for item in raw if isinstance(item, dict)}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def _save_cache(path: Path, values: dict[int, dict]) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps([values[key] for key in sorted(values)], indent=2) + "\n")
    temp.replace(path)


def describe_visual_samples(samples: list[dict], destination: Path) -> list[dict]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenAI is not configured. Add OPENAI_API_KEY to .env and restart.")
    model = os.getenv("OPENAI_VISUAL_MODEL", "").strip() \
        or os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL)
    cache_path = destination / "descriptions.json"
    cached = _load_cache(cache_path)
    client = OpenAI(api_key=key, timeout=180.0)
    for offset in range(0, len(samples), BATCH_SIZE):
        batch = samples[offset:offset + BATCH_SIZE]
        missing = [item for item in batch if item["sample_id"] not in cached]
        if not missing:
            continue
        try:
            response = client.responses.parse(
                model=model, instructions=_instructions(),
                input=[{"role": "user", "content": _content(missing)}],
                text_format=VisualSampleBatch, store=False, max_output_tokens=5000,
            )
        except (AuthenticationError, RateLimitError, APITimeoutError,
                APIConnectionError, APIError) as exc:
            raise _api_error(exc) from exc
        parsed = response.output_parsed
        expected = {item["sample_id"] for item in missing}
        if parsed is None or {item.sample_id for item in parsed.samples} != expected:
            raise ValueError("OpenAI's visual catalog did not match the supplied movie frames.")
        for description in parsed.samples:
            cached[description.sample_id] = description.model_dump()
        _save_cache(cache_path, cached)
    return [cached[item["sample_id"]] for item in samples]


def build_visual_montage_index(movie_path: Path, destination: Path, *, duration: float,
                               source_fingerprint: str | None,
                               sample_count: int = DEFAULT_SAMPLE_COUNT) -> dict:
    samples = extract_visual_samples(
        movie_path, destination, duration=duration, sample_count=sample_count
    )
    descriptions = describe_visual_samples(samples, destination)
    return _searchable_index(samples, descriptions, source_fingerprint=source_fingerprint)


def _searchable_index(samples: list[dict], descriptions: list[dict], *,
                      source_fingerprint: str | None) -> dict:
    search_texts = []
    for description in descriptions:
        search_texts.append(". ".join([
            description["summary"], "Tags: " + ", ".join(description["tags"]),
            "Setting: " + description["setting"],
            "Lighting and color: " + description["lighting_color"],
            "Composition: " + description["composition"],
            "People and activity: " + description["people_activity"],
            "Energy: " + description["energy"],
        ]))
    vectors = _model().encode_document(
        search_texts, normalize_embeddings=True, show_progress_bar=False
    ).astype(np.float32)
    output = []
    for sample, description, text, vector in zip(samples, descriptions, search_texts, vectors):
        preserved = {key: sample[key] for key in (
            "shot_start", "shot_end", "region_start", "region_end"
        ) if key in sample}
        output.append({
            "sample_id": sample["sample_id"], "timestamp": sample["timestamp"],
            "filename": sample["filename"], **preserved, **description, "search_text": text,
            "embedding": base64.b64encode(vector.tobytes()).decode("ascii"),
        })
    return {
        "status": "complete", "created_at": _now(), "source_fingerprint": source_fingerprint,
        "sample_count": len(output), "visual_model": os.getenv("OPENAI_VISUAL_MODEL", "").strip()
        or os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL),
        "embedding_model": MODEL_NAME, "samples": output,
    }


def _merge_regions(regions: list[dict], duration: float) -> list[dict]:
    normalized = sorted((
        max(0.0, float(item["start"])), min(duration, float(item["end"]))
    ) for item in regions if float(item["end"]) > float(item["start"]))
    merged: list[list[float]] = []
    for start, end in normalized:
        if merged and start <= merged[-1][1] + 1.0:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [{"start": round(start, 3), "end": round(end, 3)} for start, end in merged]


def detect_targeted_shots(movie_path: Path, regions: list[dict], *, duration: float,
                          threshold: float = 0.24, max_shots: int = 96) -> tuple[list[dict], list[dict]]:
    """Detect cuts only inside mood-routed regions and split detector misses."""
    merged = _merge_regions(regions, duration)
    detected = []
    for region in merged:
        region_start, region_end = float(region["start"]), float(region["end"])
        span = region_end - region_start
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "info", "-threads", "2",
            "-filter_threads", "2", "-ss", f"{region_start:.3f}", "-t", f"{span:.3f}",
            "-i", str(movie_path), "-an",
            "-vf", f"scale=320:-2,select='gt(scene,{threshold:.3f})',showinfo",
            "-fps_mode", "vfr", "-f", "null", "-",
        ], capture_output=True, text=True)
        if result.returncode:
            raise ValueError("Targeted visual shot detection failed.")
        boundaries = [region_start]
        for match in re.finditer(r"pts_time:([0-9.]+)", result.stderr):
            value = float(match.group(1))
            absolute = region_start + value if value <= span + 1.0 else value
            absolute = min(region_end, max(region_start, absolute))
            if absolute - boundaries[-1] >= 0.65:
                boundaries.append(absolute)
        if region_end - boundaries[-1] >= 0.4:
            boundaries.append(region_end)
        for start, end in zip(boundaries, boundaries[1:]):
            if end - start > 12.0:
                cursor = start
                while cursor < end - 0.6:
                    chunk_end = min(end, cursor + 5.0)
                    detected.append({
                        "shot_start": cursor, "shot_end": chunk_end,
                        "region_start": region_start, "region_end": region_end,
                        "boundary_method": "dense_fallback",
                    })
                    cursor = chunk_end
            elif end - start >= 0.65:
                detected.append({
                    "shot_start": start, "shot_end": end,
                    "region_start": region_start, "region_end": region_end,
                    "boundary_method": "targeted_scene_cut",
                })
    if not detected:
        raise ValueError("The targeted regions contained no usable shots.")
    max_shots = min(144, max(24, int(max_shots)))
    if len(detected) > max_shots:
        selected = []
        used: set[int] = set()
        for bucket in range(max_shots):
            target = duration * (bucket + 0.5) / max_shots
            available = [index for index in range(len(detected)) if index not in used]
            index = min(available, key=lambda candidate: abs(
                (detected[candidate]["shot_start"] + detected[candidate]["shot_end"]) / 2
                - target
            ))
            used.add(index)
            selected.append(detected[index])
        detected = sorted(selected, key=lambda item: item["shot_start"])
    return detected, merged


def extract_targeted_shot_frames(movie_path: Path, shots: list[dict],
                                 destination: Path) -> list[dict]:
    destination.mkdir(parents=True, exist_ok=True)
    samples = []
    for number, shot in enumerate(shots, start=1):
        start, end = float(shot["shot_start"]), float(shot["shot_end"])
        timestamp = start + min(max(0.2, (end - start) * 0.45), 1.5)
        filename = f"dense-shot-{number:04d}.jpg"
        path = destination / filename
        if not path.is_file():
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
                "-i", str(movie_path), "-frames:v", "1", "-vf", "scale='min(640,iw)':-2",
                "-q:v", "4", "-y", str(path),
            ], capture_output=True, text=True)
            if result.returncode or not path.is_file():
                continue
        samples.append({
            "sample_id": number, "timestamp": round(timestamp, 3), "filename": filename,
            "path": str(path), "shot_start": round(start, 3), "shot_end": round(end, 3),
            "region_start": round(float(shot["region_start"]), 3),
            "region_end": round(float(shot["region_end"]), 3),
        })
    if not samples:
        raise ValueError("Could not extract frames from the targeted shots.")
    return samples


def build_targeted_mood_index(movie_path: Path, destination: Path, *, duration: float,
                              source_fingerprint: str | None, regions: list[dict],
                              prompt: str, max_shots: int = 96) -> dict:
    shots, merged_regions = detect_targeted_shots(
        movie_path, regions, duration=duration, max_shots=max_shots
    )
    samples = extract_targeted_shot_frames(movie_path, shots, destination)
    descriptions = describe_visual_samples(samples, destination)
    result = _searchable_index(
        samples, descriptions, source_fingerprint=source_fingerprint
    )
    result.update({
        "type": "targeted_mood", "prompt": " ".join(str(prompt).split())[:300],
        "regions": merged_regions, "detected_shot_count": len(shots),
        "asset_dir": str(destination),
    })
    return result


def search_visual_montage(index: dict, query: str, *, limit: int = 24) -> list[dict]:
    if not isinstance(index, dict) or index.get("status") != "complete":
        raise ValueError("Build the visual movie index before using a visual Mood Style.")
    samples = index.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("The saved visual movie index is empty.")
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Describe the visual mood you want to find.")
    query_vector = _model().encode_query(query, normalize_embeddings=True)
    scored = []
    for sample in samples:
        try:
            vector = np.frombuffer(base64.b64decode(sample["embedding"]), dtype=np.float32)
            score = float(np.dot(query_vector, vector))
        except (KeyError, TypeError, ValueError):
            continue
        scored.append({**sample, "score": round(score, 4),
                       "evidence_start": float(sample.get("shot_start", sample["timestamp"] - 1.5)),
                       "evidence_end": float(sample.get("shot_end", sample["timestamp"] + 1.5)),
                       "excerpt": sample["summary"], "id": int(sample["sample_id"])})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:max(1, min(60, int(limit)))]


__all__ = [
    "build_targeted_mood_index", "build_visual_montage_index", "describe_visual_samples",
    "detect_targeted_shots", "extract_targeted_shot_frames", "extract_visual_samples",
    "search_visual_montage",
]
