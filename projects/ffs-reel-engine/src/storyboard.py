from __future__ import annotations

import re
import uuid
import math
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

from .concept_generator import ReelConcept
from .evidence_builder import build_evidence_board
from .film_index import FilmIndex


CARD_TYPES = {"hook", "clip", "observation", "interpretation", "end_card"}
ALIGNMENT_THRESHOLD = 0.74
CLIP_PREROLL = 0.3
CLIP_POSTROLL = 0.45


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _card_id() -> str:
    return f"card-{uuid.uuid4().hex[:8]}"


def _words(value: str) -> list[str]:
    value = str(value).lower().replace("’", "'")
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", value)


def _alignment_score(target: list[str], candidate: list[str]) -> float:
    if not target or not candidate:
        return 0.0
    target_text = " ".join(target)
    candidate_text = " ".join(candidate)
    overlap = sum((Counter(target) & Counter(candidate)).values())
    coverage = overlap / len(target)
    precision = overlap / len(candidate)
    sequence = SequenceMatcher(None, target_text, candidate_text).ratio()
    score = 0.55 * sequence + 0.30 * coverage + 0.15 * precision
    if target_text in candidate_text:
        score = max(score, 0.94)
    return score


def _clip_source_bounds(index: FilmIndex, item: dict, anchor_quote: str,
                        requested_duration: float, movie_duration: float) -> dict:
    """Locate a quoted clip beat inside its much longer semantic passage."""
    lower = max(0.0, float(item["evidence_start"]))
    upper = min(movie_duration, float(item["evidence_end"]))
    default_end = min(upper, lower + requested_duration)
    fallback = {
        "source_start": lower, "source_end": default_end,
        "alignment_method": "evidence_start", "alignment_score": 0.0,
        "anchor_quote": anchor_quote.strip(),
    }
    target = _words(anchor_quote)
    if len(target) < 2 or index is None:
        return fallback
    try:
        units = [unit for unit in index.raw_transcript()
                 if float(unit["start"]) < upper and float(unit["end"]) > lower]
    except (AttributeError, OSError, ValueError):
        return fallback
    if not units:
        return fallback

    matches = []
    for left in range(len(units)):
        candidate = []
        for right in range(left, min(len(units), left + 8)):
            candidate.extend(_words(units[right]["text"]))
            if len(candidate) < max(2, int(len(target) * 0.45)):
                continue
            if len(candidate) > len(target) * 2.5 + 6:
                break
            matches.append((_alignment_score(target, candidate), left, right))
    if not matches:
        return fallback
    matches.sort(reverse=True)
    score, left, right = matches[0]
    if score < ALIGNMENT_THRESHOLD:
        return fallback

    # A repeated short phrase is not a reliable temporal anchor.
    competing = [match for match in matches[1:]
                 if match[0] >= score - 0.02 and match[1] != left]
    if len(target) <= 4 and competing:
        fallback["alignment_method"] = "ambiguous_anchor"
        fallback["alignment_score"] = round(score, 3)
        return fallback

    anchor_start = max(lower, float(units[left]["start"]))
    anchor_end = min(upper, float(units[right]["end"]))
    start = max(lower, anchor_start - CLIP_PREROLL)
    end = min(upper, max(start + requested_duration, anchor_end + CLIP_POSTROLL))
    if end - start > 10.0:
        end = min(upper, start + 10.0)
    if end < anchor_end:
        end = anchor_end
        start = max(lower, end - 10.0)
    return {
        "source_start": start, "source_end": end,
        "alignment_method": "transcript_anchor", "alignment_score": round(score, 3),
        "anchor_quote": anchor_quote.strip(), "anchor_start": anchor_start,
        "anchor_end": anchor_end,
    }


def _evidence_map(board: dict) -> dict[int, dict]:
    raw_evidence = board.get("evidence") if isinstance(board, dict) else None
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ValueError("The saved evidence research is no longer usable. Research the idea again.")
    evidence: dict[int, dict] = {}
    for raw in raw_evidence:
        if not isinstance(raw, dict):
            raise ValueError("The saved evidence research is no longer usable. Research the idea again.")
        try:
            evidence_id = int(raw["id"])
            start = float(raw["evidence_start"])
            end = float(raw["evidence_end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "The saved evidence research is no longer usable. Research the idea again."
            ) from None
        if end <= start or evidence_id in evidence:
            raise ValueError("The saved evidence research contains invalid evidence moments.")
        item = dict(raw)
        item["id"] = evidence_id
        evidence[evidence_id] = item
    return evidence


def create_storyboard(project: dict, index: FilmIndex, topic: str,
                      concept_data: dict, *, evidence_board: dict | None = None,
                      research_id: str | None = None) -> dict:
    topic = " ".join(str(topic).split()).strip()
    if len(topic) < 3:
        raise ValueError("A valid editorial topic is required.")
    concept = ReelConcept.model_validate(concept_data)
    board = (build_evidence_board(index, topic, limit=12)
             if evidence_board is None else evidence_board)
    if evidence_board is not None:
        board_topic = " ".join(str(board.get("topic", "")).split()).strip()
        if not board_topic or board_topic.casefold() != topic.casefold():
            raise ValueError("The topic does not match the selected evidence research.")
    evidence = _evidence_map(board)
    if not set(concept.evidence_ids).issubset(evidence):
        raise ValueError("The concept references evidence outside the current evidence board.")

    cards = []
    for beat in sorted(concept.beats, key=lambda item: item.order):
        card = {
            "id": _card_id(), "type": beat.card_type, "text": beat.text.strip(),
            "duration": round(float(beat.duration_seconds), 2),
        }
        if beat.card_type == "clip":
            if beat.evidence_id not in evidence:
                raise ValueError("A clip card references unavailable evidence.")
            item = evidence[beat.evidence_id]
            movie_duration = float(project["movie"]["duration"])
            anchor_quote = beat.anchor_quote or beat.text
            bounds = _clip_source_bounds(
                index, item, anchor_quote, float(beat.duration_seconds), movie_duration
            )
            start = float(bounds.pop("source_start"))
            end = float(bounds.pop("source_end"))
            if end - start < 0.5:
                end = min(movie_duration, start + 0.5)
            card.update({
                "evidence_id": beat.evidence_id,
                "scene_id": item.get("scene_id", item["id"]),
                "scene_title": item.get("title") or item.get("scene_title")
                or f"Scene {item.get('scene_id', item['id'])}",
                "source_start": round(start, 3),
                "source_end": round(end, 3), "duration": round(end - start, 3),
                "evidence_start": round(float(item["evidence_start"]), 3),
                "evidence_end": round(float(item["evidence_end"]), 3),
                "original_audio": True, "crop_x": 0.5,
                **bounds,
            })
        cards.append(card)

    storyboard = {
        "id": f"story-{uuid.uuid4().hex[:8]}", "title": concept.title.strip(),
        "topic": topic, "format": concept.format, "hook": concept.hook.strip(),
        "thesis": concept.thesis.strip(), "tone": concept.tone.strip(),
        "warnings": concept.warnings, "status": "draft", "cards": cards,
        "captions_enabled": True,
        "revision": 1, "created_at": _now(), "updated_at": _now(),
    }
    if research_id is not None:
        storyboard["research_id"] = research_id
    project.setdefault("editorial_storyboards", []).append(storyboard)
    project["active_storyboard_id"] = storyboard["id"]
    return storyboard


def find_storyboard(project: dict, storyboard_id: str) -> dict:
    if not re.fullmatch(r"story-[a-f0-9]{8}", storyboard_id):
        raise ValueError("Invalid storyboard id.")
    storyboard = next((item for item in project.get("editorial_storyboards", [])
                       if item.get("id") == storyboard_id), None)
    if storyboard is None:
        raise ValueError("Storyboard not found.")
    storyboard.setdefault("captions_enabled", True)
    return storyboard


def update_storyboard(project: dict, storyboard_id: str, data: dict) -> dict:
    storyboard = find_storyboard(project, storyboard_id)
    if int(data.get("revision", -1)) != int(storyboard.get("revision", 1)):
        raise ValueError("This storyboard changed in another save. Refresh before editing again.")
    if "captions_enabled" in data and not isinstance(data["captions_enabled"], bool):
        raise ValueError("Caption preference must be true or false.")
    movie_duration = float(project["movie"]["duration"])
    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards or len(raw_cards) > 16:
        raise ValueError("A storyboard must contain between 1 and 16 cards.")
    existing = {card["id"]: card for card in storyboard["cards"]}
    cards = []
    seen = set()
    for raw in raw_cards:
        card_id = str(raw.get("id", ""))
        if card_id in seen or card_id not in existing:
            raise ValueError("Storyboard contains an unknown or duplicate card.")
        seen.add(card_id)
        original = existing[card_id]
        card_type = original["type"]
        if card_type not in CARD_TYPES or raw.get("type", card_type) != card_type:
            raise ValueError("Storyboard card types cannot be changed.")
        card = dict(original)
        card["text"] = str(raw.get("text", card["text"])).strip()[:240]
        duration = float(raw.get("duration", card["duration"]))
        if not math.isfinite(duration):
            raise ValueError("Card duration must be a finite number.")
        card["duration"] = round(min(10.0, max(0.5, duration)), 2)
        if card_type == "clip":
            requested_start = float(raw.get("source_start", card["source_start"]))
            requested_end = float(raw.get("source_end", card["source_end"]))
            timing_changed = (
                abs(requested_start - float(card["source_start"])) >= 0.001
                or abs(requested_end - float(card["source_end"])) >= 0.001
            )
            crop_x = float(raw.get("crop_x", card["crop_x"]))
            if not all(math.isfinite(value) for value in (requested_start, requested_end, crop_x)):
                raise ValueError("Clip timing and focus must use finite numbers.")
            lower = max(0.0, float(card["evidence_start"]))
            upper = min(movie_duration, float(card["evidence_end"]))
            start = min(upper - 0.5, max(lower, requested_start))
            end = min(upper, max(start + 0.5, requested_end))
            if end - start > 10:
                end = start + 10
            card.update({
                "source_start": round(start, 3), "source_end": round(end, 3),
                "duration": round(end - start, 3),
                "original_audio": bool(raw.get("original_audio", card["original_audio"])),
                "crop_x": round(min(1.0, max(0.0, crop_x)), 3),
            })
            if timing_changed:
                card["alignment_method"] = "manual_trim"
                card["timing_source"] = "editor"
                card["timing_refined"] = False
        cards.append(card)
    storyboard["cards"] = cards
    if "title" in data:
        title = str(data["title"]).strip()[:100]
        if title:
            storyboard["title"] = title
    if "captions_enabled" in data:
        storyboard["captions_enabled"] = data["captions_enabled"]
    storyboard["updated_at"] = _now()
    storyboard["revision"] = int(storyboard.get("revision", 1)) + 1
    project["active_storyboard_id"] = storyboard["id"]
    return storyboard
