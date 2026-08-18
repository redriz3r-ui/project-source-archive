from __future__ import annotations

import base64
import json
import math
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field

from .editorial_rerank import DEFAULT_MODEL


FRAMES_PER_EVIDENCE = 3
MAX_EVIDENCE = 8
MAX_IMAGE_BYTES = 2_500_000


class VisualObservation(BaseModel):
    kind: Literal[
        "composition", "blocking_proximity", "gesture_expression",
        "lighting_color", "setting_object", "camera_viewpoint",
    ]
    statement: str = Field(min_length=3, max_length=240)
    frame_numbers: list[int] = Field(min_length=1, max_length=3)
    confidence: Literal["high", "medium", "low"]
    editorial_relevance: str = Field(min_length=3, max_length=240)


class EvidenceVisualAnalysis(BaseModel):
    evidence_id: int = Field(ge=1)
    visual_summary: str = Field(min_length=3, max_length=360)
    observations: list[VisualObservation] = Field(min_length=1, max_length=6)
    caution: str = Field(default="", max_length=240)


class VisualAnalysisSet(BaseModel):
    evidence: list[EvidenceVisualAnalysis] = Field(min_length=1, max_length=MAX_EVIDENCE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _api_error(exc: Exception) -> ValueError:
    if isinstance(exc, AuthenticationError):
        return ValueError("OpenAI rejected the API key. Check .env and restart the server.")
    if isinstance(exc, RateLimitError):
        return ValueError("OpenAI rate limit or account quota reached. Check API billing and try again.")
    if isinstance(exc, APITimeoutError):
        return ValueError("Visual evidence analysis took too long. Try again.")
    if isinstance(exc, APIConnectionError):
        return ValueError("Could not connect to OpenAI. Check the internet connection and try again.")
    if isinstance(exc, APIError):
        return ValueError(f"OpenAI could not analyze the evidence frames: {exc.message}")
    return ValueError("OpenAI could not analyze the evidence frames.")


def _frame_times(start: float, end: float, movie_duration: float) -> list[float]:
    if not all(math.isfinite(value) for value in (start, end, movie_duration)):
        raise ValueError("Evidence contains invalid timestamps.")
    if start < 0 or end <= start or movie_duration <= 0:
        raise ValueError("Evidence contains invalid timestamps.")
    start = min(start, movie_duration)
    end = min(end, movie_duration)
    if end <= start:
        raise ValueError("Evidence falls outside the movie duration.")
    span = end - start
    # Avoid the exact transcript boundaries, where a cut or subtitle transition
    # is more likely, while still representing the beginning/middle/end.
    fractions = (0.18, 0.50, 0.82)
    return [round(min(movie_duration - 0.04, max(0.0, start + span * fraction)), 3)
            for fraction in fractions]


def _extract_frame(movie_path: Path, timestamp: float, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
        "-i", str(movie_path), "-frames:v", "1",
        "-vf", "scale='min(960,iw)':-2", "-q:v", "3", "-y", str(destination),
    ], capture_output=True, text=True)
    if result.returncode or not destination.is_file():
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ValueError(f"Could not extract a visual evidence frame{suffix}")


def extract_evidence_frames(movie_path: Path, board: dict, destination: Path,
                            *, movie_duration: float) -> list[dict]:
    raw_evidence = board.get("evidence") if isinstance(board, dict) else None
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ValueError("The evidence board has no moments to analyze.")
    if len(raw_evidence) > MAX_EVIDENCE:
        raise ValueError(f"Visual analysis supports at most {MAX_EVIDENCE} evidence moments.")
    if not movie_path.is_file():
        raise ValueError("The local movie file is no longer available.")

    extracted = []
    for item in raw_evidence:
        try:
            evidence_id = int(item["id"])
            start = float(item["evidence_start"])
            end = float(item["evidence_end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("The evidence board contains invalid timestamps.") from None
        frames = []
        for number, timestamp in enumerate(_frame_times(start, end, movie_duration), start=1):
            filename = f"evidence-{evidence_id}-frame-{number}.jpg"
            path = destination / filename
            _extract_frame(movie_path, timestamp, path)
            frames.append({
                "number": number,
                "timestamp": timestamp,
                "filename": filename,
                "path": str(path),
            })
        extracted.append({
            "evidence_id": evidence_id,
            "title": str(item.get("title") or f"Evidence {evidence_id}"),
            "transcript": str(item.get("excerpt") or item.get("text") or ""),
            "supported_claim": str(item.get("supported_claim") or ""),
            "frames": frames,
        })
    return extracted


def _image_data_url(path: Path) -> str:
    data = path.read_bytes()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("A visual evidence frame is empty or unexpectedly large.")
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def _input_content(topic: str, groups: list[dict]) -> list[dict]:
    content: list[dict] = [{
        "type": "input_text",
        "text": json.dumps({
            "topic": topic,
            "evidence": [{
                "evidence_id": group["evidence_id"],
                "title": group["title"],
                "transcript": group["transcript"],
                "supported_claim": group["supported_claim"],
                "frame_timestamps": [frame["timestamp"] for frame in group["frames"]],
            } for group in groups],
        }, ensure_ascii=False),
    }]
    for group in groups:
        for frame in group["frames"]:
            content.append({
                "type": "input_text",
                "text": (
                    f"Evidence {group['evidence_id']}, frame {frame['number']}, "
                    f"movie timestamp {frame['timestamp']:.3f} seconds"
                ),
            })
            content.append({
                "type": "input_image",
                "image_url": _image_data_url(Path(frame["path"])),
                "detail": "low",
            })
    return content


def _instructions() -> str:
    return """You are the visual evidence analyst for Fresno Film Society.
Analyze only the supplied movie frames. They are grouped by evidence_id and ordered in time.
Describe concrete, visible facts: composition, character proximity/blocking, visible gesture or
expression, lighting/color, setting/objects, and camera viewpoint. You may compare supplied frames
within the same evidence moment, but a few stills cannot prove continuous action or camera movement.
Never identify a person unless the supplied text names them, never infer private thoughts or emotions
as fact, and never use outside knowledge of the film. Connect visible facts to the requested topic
carefully; editorial_relevance must distinguish observation from interpretation. Use a caution when
the frames cannot verify the transcript claim or when temporal context would be required. Return one
analysis for every supplied evidence_id and reference only frame numbers that exist for that evidence."""


def analyze_visual_evidence(movie_path: Path, board: dict, destination: Path,
                            *, movie_duration: float, analysis_id: str | None = None) -> dict:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenAI is not configured yet. Add OPENAI_API_KEY to .env and restart.")
    topic = " ".join(str(board.get("topic", "")).split()).strip()
    if len(topic) < 3:
        raise ValueError("The evidence board has no usable editorial topic.")

    groups = extract_evidence_frames(
        movie_path, board, destination, movie_duration=movie_duration
    )
    model = os.getenv("OPENAI_VISUAL_MODEL", "").strip() \
        or os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL)
    try:
        response = OpenAI(api_key=key, timeout=180.0).responses.parse(
            model=model,
            instructions=_instructions(),
            input=[{"role": "user", "content": _input_content(topic, groups)}],
            text_format=VisualAnalysisSet,
            store=False,
            max_output_tokens=5000,
        )
    except (AuthenticationError, RateLimitError, APITimeoutError,
            APIConnectionError, APIError) as exc:
        raise _api_error(exc) from exc
    parsed = response.output_parsed
    if parsed is None:
        raise ValueError("OpenAI returned no usable visual evidence analysis.")

    expected = [group["evidence_id"] for group in groups]
    analyses = {item.evidence_id: item for item in parsed.evidence}
    if len(analyses) != len(parsed.evidence) or set(analyses) != set(expected):
        raise ValueError("OpenAI's visual analysis did not match the selected evidence moments.")

    evidence_output = []
    total_observations = 0
    for group in groups:
        analysis = analyses[group["evidence_id"]]
        for observation in analysis.observations:
            if (len(set(observation.frame_numbers)) != len(observation.frame_numbers)
                    or any(number < 1 or number > FRAMES_PER_EVIDENCE
                           for number in observation.frame_numbers)):
                raise ValueError("OpenAI referenced an invalid visual evidence frame.")
        observations = [item.model_dump() for item in analysis.observations]
        total_observations += len(observations)
        evidence_output.append({
            "evidence_id": group["evidence_id"],
            "visual_summary": analysis.visual_summary.strip(),
            "visual_observations": observations,
            "visual_caution": analysis.caution.strip(),
            "visual_frames": [{
                "number": frame["number"],
                "timestamp": frame["timestamp"],
                "filename": frame["filename"],
            } for frame in group["frames"]],
        })

    analysis_id = analysis_id or f"visual-{uuid.uuid4().hex[:8]}"
    return {
        "id": analysis_id,
        "status": "complete",
        "model": model,
        "created_at": _now(),
        "frame_count": sum(len(group["frames"]) for group in groups),
        "observation_count": total_observations,
        "evidence": evidence_output,
    }


__all__ = ["analyze_visual_evidence", "extract_evidence_frames"]
