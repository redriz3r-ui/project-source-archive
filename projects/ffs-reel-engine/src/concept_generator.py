from __future__ import annotations

import json
import os
import re
import unicodedata
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
from .evidence_builder import build_evidence_board
from .film_index import FilmIndex


class ConceptBeat(BaseModel):
    order: int = Field(ge=1, le=12)
    card_type: Literal["hook", "clip", "observation", "interpretation", "end_card"]
    evidence_id: int = Field(
        ge=0, description="Use 0 for text/end cards; otherwise use an supplied evidence candidate ID."
    )
    text: str = Field(min_length=1, max_length=240)
    anchor_quote: str | None = Field(
        default=None, max_length=240,
        description="For clip beats, a short verbatim quote copied from the supplied transcript."
    )
    duration_seconds: float = Field(ge=0.5, le=10)


class ReelConcept(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    format: Literal["analytical_argument", "detail_missed", "poetic_ffs"]
    hook: str = Field(min_length=3, max_length=180)
    thesis: str = Field(min_length=3, max_length=360)
    tone: str = Field(min_length=2, max_length=100)
    evidence_ids: list[int] = Field(min_length=2, max_length=4)
    beats: list[ConceptBeat] = Field(min_length=5, max_length=10)
    estimated_duration: float = Field(ge=20, le=45)
    warnings: list[str] = Field(max_length=5)


class ConceptSet(BaseModel):
    concepts: list[ReelConcept] = Field(min_length=3, max_length=3)


def _call_error(exc: Exception) -> ValueError:
    if isinstance(exc, AuthenticationError):
        return ValueError("OpenAI rejected the API key. Check .env and restart the server.")
    if isinstance(exc, RateLimitError):
        return ValueError("OpenAI rate limit or account quota reached. Check API billing and try again.")
    if isinstance(exc, APITimeoutError):
        return ValueError("Concept generation took too long. Try again.")
    if isinstance(exc, APIConnectionError):
        return ValueError("Could not connect to OpenAI. Check the internet connection and try again.")
    if isinstance(exc, APIError):
        return ValueError(f"OpenAI could not generate concepts: {exc.message}")
    return ValueError("OpenAI could not generate concepts.")


def _normalized_topic(value: str) -> str:
    return " ".join(str(value).split()).strip()


_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)


def _normalized_tokens(value: str | None) -> list[str]:
    if value is None:
        return []
    normalized = unicodedata.normalize("NFKC", str(value)).replace("’", "'").casefold()
    return _TOKEN_PATTERN.findall(normalized)


def _is_contiguous_verbatim_quote(quote: str | None, transcript: str | None) -> bool:
    quote_tokens = _normalized_tokens(quote)
    transcript_tokens = _normalized_tokens(transcript)
    if len(quote_tokens) < 2 or len(quote_tokens) > len(transcript_tokens):
        return False
    width = len(quote_tokens)
    return any(
        transcript_tokens[start:start + width] == quote_tokens
        for start in range(len(transcript_tokens) - width + 1)
    )


def _evidence_candidates(board: dict) -> dict[int, dict]:
    raw_evidence = board.get("evidence") if isinstance(board, dict) else None
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ValueError("The saved evidence research is no longer usable. Research the idea again.")
    candidates: dict[int, dict] = {}
    for raw in raw_evidence:
        if not isinstance(raw, dict):
            raise ValueError("The saved evidence research is no longer usable. Research the idea again.")
        try:
            evidence_id = int(raw["id"])
            float(raw["evidence_start"])
            float(raw["evidence_end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "The saved evidence research is no longer usable. Research the idea again."
            ) from None
        if evidence_id in candidates:
            raise ValueError("The saved evidence research contains duplicate evidence moments.")
        item = dict(raw)
        item["id"] = evidence_id
        candidates[evidence_id] = item
    return candidates


def generate_concepts(index: FilmIndex, topic: str, evidence_ids: list[int], *,
                      evidence_board: dict | None = None) -> dict:
    if not isinstance(evidence_ids, list):
        raise ValueError("Editorially rerank the evidence before generating concepts.")

    board = (build_evidence_board(index, topic, limit=12)
             if evidence_board is None else evidence_board)
    board_topic = _normalized_topic(board.get("topic", "")) if isinstance(board, dict) else ""
    requested_topic = _normalized_topic(topic)
    if not board_topic:
        raise ValueError("The saved evidence research has no topic. Research the idea again.")
    if evidence_board is not None and board_topic.casefold() != requested_topic.casefold():
        raise ValueError("The topic does not match the selected evidence research.")
    candidates = _evidence_candidates(board)
    selected_ids = []
    invalid_ids = []
    for raw_id in evidence_ids:
        try:
            evidence_id = int(raw_id)
        except (TypeError, ValueError):
            invalid_ids.append(raw_id)
            continue
        if evidence_id not in candidates:
            invalid_ids.append(raw_id)
        elif evidence_id not in selected_ids:
            selected_ids.append(evidence_id)
    if evidence_board is not None and invalid_ids:
        raise ValueError("Selected evidence does not belong to this OpenAI research board.")
    selected_ids = selected_ids[:6]
    if len(selected_ids) < 3:
        raise ValueError("At least three valid reranked evidence moments are required.")
    evidence = [{
        "candidate_id": item["id"],
        "scene_id": item.get("scene_id", item["id"]),
        "scene_title": item.get("title") or item.get("scene_title")
        or f"Scene {item.get('scene_id', item['id'])}",
        "start_seconds": item["evidence_start"], "end_seconds": item["evidence_end"],
        "transcript": item.get("excerpt", ""),
        "editorial_role": item.get("editorial_role", ""),
        "reason": item.get("reason", ""),
        "supported_claim": item.get("supported_claim", ""),
        "warning": item.get("warning", ""),
        "visual_summary": item.get("visual_summary", ""),
        "visual_observations": item.get("visual_observations", []),
        "visual_caution": item.get("visual_caution", ""),
    } for item in (candidates[item_id] for item_id in selected_ids)]

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenAI is not configured yet. Add OPENAI_API_KEY to .env and restart.")

    has_visual_evidence = any(item["visual_observations"] for item in evidence)
    visual_rule = (
        "Visual claims are allowed only when they are directly supported by the supplied "
        "visual_summary or visual_observations for that same candidate_id. Preserve visual "
        "cautions and distinguish visible facts from interpretation."
        if has_visual_evidence else
        "No visual evidence was supplied. Never claim camera movement, color, framing, acting, "
        "gesture, blocking, or other visual facts."
    )
    instructions = f"""You are an original social film programmer for Fresno Film Society.
Create exactly three distinct short-form editorial Reel concepts about the requested topic:
1) analytical_argument: a clear, defensible film-analysis argument;
2) detail_missed: an accessible, precise observation framed as something viewers may overlook;
3) poetic_ffs: evocative but still evidence-based, never vague or pretentious.
Use the supplied editorial role, reason, supported claim, and warning to preserve the researcher's
argument and cautions. Use only the supplied transcript and visual evidence. {visual_rule}
Do not quote or reference evidence not supplied. Every clip beat and evidence_id
must use a supplied candidate_id. Text cards use evidence_id 0. Target a practical 28–36 second Reel.
Each concept should use 2–4 evidence moments and follow HOOK → CLIP → OBSERVATION/INTERPRETATION →
CLIP → PAYOFF → FFS END CARD. For every clip beat, set anchor_quote to a short verbatim quotation
copied from that evidence transcript; this quote is used to locate the exact in point. Text/end cards
must use null for anchor_quote. Keep on-screen text concise and social-first, not academic."""
    model = os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL)
    try:
        response = OpenAI(api_key=key, timeout=180.0).responses.parse(
            model=model, instructions=instructions,
            input=json.dumps({
                "topic": board_topic,
                "research_summary": board.get("research_summary", ""),
                "thesis_direction": board.get("thesis_direction", ""),
                "evidence": evidence,
            }, ensure_ascii=False),
            text_format=ConceptSet, store=False, max_output_tokens=5000,
        )
    except (AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
        raise _call_error(exc) from exc
    result = response.output_parsed
    if result is None:
        raise ValueError("OpenAI returned no usable Reel concepts.")

    allowed = set(selected_ids)
    formats = {"analytical_argument", "detail_missed", "poetic_ffs"}
    concepts = []
    for concept in result.concepts:
        concept_ids = list(dict.fromkeys(item for item in concept.evidence_ids if item in allowed))
        beat_ids = {beat.evidence_id for beat in concept.beats if beat.evidence_id != 0}
        clip_beats = [beat for beat in concept.beats if beat.card_type == "clip"]
        clips_are_grounded = all(
            beat.evidence_id != 0
            and beat.evidence_id in allowed
            and _is_contiguous_verbatim_quote(
                beat.anchor_quote,
                candidates[beat.evidence_id].get("excerpt")
                or candidates[beat.evidence_id].get("text"),
            )
            for beat in clip_beats
        )
        if (len(concept_ids) < 2 or not beat_ids.issubset(allowed)
                or not beat_ids.issubset(set(concept_ids))
                or not clip_beats or not clips_are_grounded):
            continue
        data = concept.model_dump()
        data["evidence_ids"] = concept_ids
        data["beats"] = sorted(data["beats"], key=lambda beat: beat["order"])
        concepts.append(data)
    if len(concepts) != 3 or {concept["format"] for concept in concepts} != formats:
        raise ValueError("OpenAI's concept draft did not pass evidence validation. Try generating again.")
    return {"topic": board_topic, "model": model, "concepts": concepts,
            "evidence": evidence}
