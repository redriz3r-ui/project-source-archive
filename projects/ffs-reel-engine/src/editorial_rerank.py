from __future__ import annotations

import json
import os
from typing import Literal

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from .evidence_builder import build_evidence_board
from .film_index import FilmIndex


DEFAULT_MODEL = "gpt-5.6-terra"


class EvidenceAssessment(BaseModel):
    candidate_id: int
    keep: bool
    relevance: int = Field(ge=0, le=5)
    evidence_strength: int = Field(ge=0, le=5)
    editorial_usefulness: int = Field(ge=0, le=5)
    distinctiveness: int = Field(ge=0, le=5)
    clip_potential: int = Field(ge=0, le=5)
    editorial_role: Literal["hook", "setup", "development", "contrast", "payoff", "support"]
    reason: str = Field(min_length=3, max_length=280)
    supported_claim: str = Field(min_length=3, max_length=280)
    warning: str = Field(default="", max_length=220)


class EditorialJudgment(BaseModel):
    thesis_direction: str = Field(min_length=3, max_length=320)
    assessments: list[EvidenceAssessment]


def api_status() -> dict:
    return {
        "configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "model": os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL),
    }


def _prompt_payload(topic: str, candidates: list[dict]) -> str:
    evidence = [{
        "candidate_id": item["id"],
        "scene_title": item["title"],
        "start_seconds": item["evidence_start"],
        "end_seconds": item["evidence_end"],
        "transcript": item["excerpt"],
        "semantic_score": item["semantic_score"],
    } for item in candidates]
    return json.dumps({"topic": topic, "evidence_candidates": evidence}, ensure_ascii=False)


def editorial_rerank(index: FilmIndex, topic: str, limit: int = 6) -> dict:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenAI is not configured yet. Add OPENAI_API_KEY to the local .env file and restart the server.")

    local_board = build_evidence_board(index, topic, limit=12)
    candidates = local_board["evidence"]
    candidate_by_id = {item["id"]: item for item in candidates}
    instructions = """You are the editorial evidence judge for Fresno Film Society.
Evaluate only the supplied transcript evidence for the user's proposed film-analysis topic.
Do not use outside knowledge. Do not invent images, blocking, expressions, camera choices, or dialogue.
Judge whether each passage directly supports a distinct, defensible editorial point and would work as a short social-video clip.
Return exactly one assessment for every supplied candidate_id. Keep only strong evidence.
The supported_claim must be narrower than the evidence and plainly justified by its transcript.
Use warnings for transcript ambiguity or when visual confirmation would be required."""
    model = os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL)
    try:
        response = OpenAI(api_key=key).responses.parse(
            model=model,
            instructions=instructions,
            input=_prompt_payload(topic, candidates),
            text_format=EditorialJudgment,
            store=False,
            max_output_tokens=3500,
        )
    except AuthenticationError as exc:
        raise ValueError("OpenAI rejected the API key. Check the key in .env and restart the server.") from exc
    except RateLimitError as exc:
        raise ValueError("OpenAI rate limit or account quota reached. Check API billing and try again.") from exc
    except APIConnectionError as exc:
        raise ValueError("Could not connect to OpenAI. Check the internet connection and try again.") from exc
    except APIError as exc:
        raise ValueError(f"OpenAI could not complete the editorial review: {exc.message}") from exc

    judgment = response.output_parsed
    if judgment is None:
        raise ValueError("OpenAI returned no usable editorial judgment.")

    seen: set[int] = set()
    ranked = []
    for assessment in judgment.assessments:
        if assessment.candidate_id in seen or assessment.candidate_id not in candidate_by_id:
            continue
        seen.add(assessment.candidate_id)
        if not assessment.keep:
            continue
        item = dict(candidate_by_id[assessment.candidate_id])
        values = [assessment.relevance, assessment.evidence_strength,
                  assessment.editorial_usefulness, assessment.distinctiveness,
                  assessment.clip_potential]
        editorial_score = sum(values) / 25
        item.update({
            **assessment.model_dump(),
            "editorial_score": round(editorial_score, 4),
            "score": round(0.7 * editorial_score + 0.3 * item["semantic_score"], 4),
            "match_type": "editorial",
        })
        ranked.append(item)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {
        "topic": local_board["topic"], "model": model,
        "thesis_direction": judgment.thesis_direction,
        "candidate_count": len(candidates), "evidence": ranked[:limit],
    }
