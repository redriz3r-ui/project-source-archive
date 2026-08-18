from __future__ import annotations

import json
import os
from typing import Any

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from .editorial_rerank import DEFAULT_MODEL
from .film_index import FilmIndex
from .semantic_search import semantic_search


MAX_RESEARCH_ROUNDS = 8
MAX_TOOL_EXECUTIONS = 14
MAX_SEARCH_EXECUTIONS = 7
MAX_CONTEXT_EXECUTIONS = 8
MAX_SEARCH_RESULTS = 8
MAX_CONTEXT_UNITS = 160
MAX_CONTEXT_CHARS = 16_000

_ROLES = {"hook", "setup", "development", "contrast", "payoff", "support"}

_RESEARCH_TOOLS = [
    {
        "type": "function",
        "name": "semantic_scene_search",
        "description": (
            "Search the local full-film transcript by meaning. Returns stable semantic passage IDs, "
            "scene IDs, exact local timestamps, transcript text, and similarity scores."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 3, "maxLength": 240},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_RESULTS},
            },
            "required": ["query", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_scene_context",
        "description": (
            "Read transcript context around one stable semantic passage returned by search. "
            "Call this before selecting a passage as final evidence."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "passage_id": {"type": "integer", "minimum": 1},
            },
            "required": ["passage_id"],
            "additionalProperties": False,
        },
    },
]


def _final_tool(limit: int, inspected_ids: list[int]) -> dict:
    minimum_items = min(3, limit)
    allowed_ids = sorted({int(passage_id) for passage_id in inspected_ids})
    if len(allowed_ids) < minimum_items:
        raise ValueError(
            f"OpenAI inspected only {len(allowed_ids)} local passage(s); "
            f"at least {minimum_items} distinct passages are required. Try the research again."
        )
    passage_id_schema = {"type": "integer", "enum": allowed_ids}
    return {
        "type": "function",
        "name": "submit_evidence_board",
        "description": "Submit the final evidence board using only inspected local semantic passages.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "research_summary": {"type": "string", "minLength": 3, "maxLength": 500},
                "thesis_direction": {"type": "string", "minLength": 3, "maxLength": 320},
                "selected_ids": {
                    "type": "array", "minItems": minimum_items, "maxItems": limit,
                    "items": passage_id_schema,
                },
                "evidence": {
                    "type": "array", "minItems": minimum_items, "maxItems": limit,
                    "items": {
                        "type": "object",
                        "properties": {
                            "passage_id": passage_id_schema,
                            "editorial_role": {
                                "type": "string",
                                "enum": ["hook", "setup", "development", "contrast",
                                         "payoff", "support"],
                            },
                            "reason": {"type": "string", "minLength": 3, "maxLength": 280},
                            "supported_claim": {
                                "type": "string", "minLength": 3, "maxLength": 280,
                            },
                            "warning": {"type": "string", "maxLength": 220},
                        },
                        "required": ["passage_id", "editorial_role", "reason",
                                     "supported_claim", "warning"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["research_summary", "thesis_direction", "selected_ids", "evidence"],
            "additionalProperties": False,
        },
    }


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _arguments(item: Any) -> dict:
    value = _field(item, "arguments", "{}")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _api_error(exc: Exception) -> ValueError:
    if isinstance(exc, AuthenticationError):
        return ValueError("OpenAI rejected the API key. Check .env and restart the server.")
    if isinstance(exc, RateLimitError):
        return ValueError("OpenAI rate limit or account quota reached. Check API billing and try again.")
    if isinstance(exc, APIConnectionError):
        return ValueError("Could not connect to OpenAI. Check the internet connection and try again.")
    if isinstance(exc, APIError):
        return ValueError(f"OpenAI could not research the film evidence: {exc.message}")
    return ValueError("OpenAI could not research the film evidence.")


def _passage_catalog(index: FilmIndex) -> tuple[dict[int, dict], dict[tuple, int]]:
    passages = {}
    exact = {}
    for raw in index.semantic_passages():
        item = {
            "id": int(raw["id"]), "scene_id": int(raw["scene_id"]),
            "start": float(raw["start"]), "end": float(raw["end"]),
            "text": str(raw["text"]),
        }
        passages[item["id"]] = item
        exact[(item["scene_id"], item["start"], item["end"], item["text"])] = item["id"]
    return passages, exact


def _resolve_search_passage(result: dict, passages: dict[int, dict],
                            exact: dict[tuple, int]) -> dict | None:
    proposed = result.get("passage_id")
    if proposed is not None and int(proposed) in passages:
        return passages[int(proposed)]
    scene_id = int(result["id"])
    start = float(result["evidence_start"])
    end = float(result["evidence_end"])
    text = str(result["excerpt"])
    passage_id = exact.get((scene_id, start, end, text))
    if passage_id is None:
        passage_id = next((pid for pid, passage in passages.items()
                           if passage["scene_id"] == scene_id
                           and abs(passage["start"] - start) < 0.001
                           and abs(passage["end"] - end) < 0.001
                           and passage["text"] == text), None)
    return passages.get(passage_id) if passage_id is not None else None


def _search_tool(index: FilmIndex, query: str, requested_limit: int,
                 passages: dict[int, dict], exact: dict[tuple, int], scenes: dict[int, dict],
                 discovered: dict[int, dict]) -> dict:
    query = " ".join(str(query).split()).strip()[:240]
    if len(query) < 3:
        return {"error": "Search query must contain at least three characters."}
    count = min(MAX_SEARCH_RESULTS, max(1, int(requested_limit)))
    results = []
    for result in semantic_search(index, query, limit=count):
        passage = _resolve_search_passage(result, passages, exact)
        if passage is None:
            continue
        scene = scenes.get(passage["scene_id"], {})
        hit = {
            "passage_id": passage["id"], "scene_id": passage["scene_id"],
            "title": str(scene.get("title") or result.get("title") or "Untitled scene"),
            "start": passage["start"], "end": passage["end"], "text": passage["text"],
            "semantic_score": round(float(result.get("score", 0.0)), 4),
            "query": query,
        }
        prior = discovered.get(passage["id"])
        if prior is None or hit["semantic_score"] > prior["semantic_score"]:
            discovered[passage["id"]] = dict(hit)
        discovered[passage["id"]].setdefault("queries", [])
        if query not in discovered[passage["id"]]["queries"]:
            discovered[passage["id"]]["queries"].append(query)
        results.append(hit)
    return {"query": query, "results": results}


def _context_units(index: FilmIndex, scene: dict, passage: dict) -> list[dict]:
    units = [unit for unit in index.normalized_transcript()
             if float(unit["start"]) < float(scene["end"])
             and float(unit["end"]) > float(scene["start"])]
    if not units:
        return []
    anchors = [position for position, unit in enumerate(units)
               if float(unit["start"]) < passage["end"]
               and float(unit["end"]) > passage["start"]]
    center = anchors[0] if anchors else len(units) // 2
    begin = max(0, center - MAX_CONTEXT_UNITS // 3)
    selected = units[begin:begin + MAX_CONTEXT_UNITS]
    output = []
    chars = 0
    for unit in selected:
        text = str(unit.get("text", "")).strip()
        if not text:
            continue
        if chars + len(text) > MAX_CONTEXT_CHARS:
            break
        output.append({"start": float(unit["start"]), "end": float(unit["end"]), "text": text})
        chars += len(text)
    return output


def _context_tool(index: FilmIndex, passage_id: int, passages: dict[int, dict],
                  scenes: dict[int, dict], discovered: dict[int, dict],
                  inspected: dict[int, dict]) -> dict:
    if passage_id not in discovered or passage_id not in passages:
        return {"error": "Read context only for a passage_id returned by semantic_scene_search."}
    passage = passages[passage_id]
    scene = scenes.get(passage["scene_id"])
    if scene is None:
        return {"error": "The local scene for this passage no longer exists."}
    context = {
        "passage": {
            "passage_id": passage["id"], "scene_id": passage["scene_id"],
            "start": passage["start"], "end": passage["end"], "text": passage["text"],
        },
        "scene": {
            "scene_id": int(scene["id"]), "title": str(scene.get("title") or "Untitled scene"),
            "start": float(scene["start"]), "end": float(scene["end"]),
        },
        "transcript_units": _context_units(index, scene, passage),
    }
    inspected[passage_id] = context
    return context


def _research_instructions() -> str:
    return """You are the evidence researcher for Fresno Film Society.
Research the user's film-analysis topic by calling semantic_scene_search with several precise,
meaningfully different queries. Read scene context for promising stable passage_ids before selecting them.
Use only local transcript evidence returned by tools. Do not rely on outside knowledge, and never invent
visual details, dialogue, scene IDs, passage IDs, or timestamps. Seek distinct moments that can form a
short argument rather than redundant lines from one exchange. Tool results contain transcript text only;
the movie itself is never available to you."""


def _validate_final(arguments: dict, *, limit: int, inspected: dict[int, dict],
                    discovered: dict[int, dict], scenes: dict[int, dict]
                    ) -> tuple[str, str, list[int], list[dict]]:
    research_summary = " ".join(str(arguments.get("research_summary", "")).split()).strip()[:500]
    thesis = " ".join(str(arguments.get("thesis_direction", "")).split()).strip()[:320]
    raw_items = arguments.get("evidence")
    raw_selected = arguments.get("selected_ids")
    if (len(research_summary) < 3 or len(thesis) < 3
            or not isinstance(raw_items, list) or not isinstance(raw_selected, list)):
        raise ValueError("OpenAI returned an incomplete evidence board.")
    try:
        selected_ids = [int(item) for item in raw_selected]
    except (TypeError, ValueError) as exc:
        raise ValueError("OpenAI returned invalid selected evidence IDs.") from exc
    item_ids = [int(item.get("passage_id", -1)) for item in raw_items if isinstance(item, dict)]
    minimum_items = min(3, limit)
    if (len(selected_ids) < minimum_items or len(selected_ids) > limit or selected_ids != item_ids
            or len(set(selected_ids)) != len(selected_ids)):
        raise ValueError("OpenAI's selected evidence IDs did not pass validation.")

    evidence = []
    for raw, passage_id in zip(raw_items, selected_ids):
        if passage_id not in inspected or passage_id not in discovered:
            raise ValueError("OpenAI selected evidence it did not inspect through local tools.")
        context = inspected[passage_id]
        passage = context["passage"]
        scene = scenes[passage["scene_id"]]
        role = str(raw.get("editorial_role", ""))
        reason = " ".join(str(raw.get("reason", "")).split()).strip()[:280]
        claim = " ".join(str(raw.get("supported_claim", "")).split()).strip()[:280]
        warning = " ".join(str(raw.get("warning", "")).split()).strip()[:220]
        if role not in _ROLES or len(reason) < 3 or len(claim) < 3:
            raise ValueError("OpenAI returned invalid editorial evidence details.")
        hit = discovered[passage_id]
        evidence.append({
            "id": passage_id, "passage_id": passage_id,
            "scene_id": int(passage["scene_id"]),
            "title": str(scene.get("title") or "Untitled scene"),
            "start": float(scene["start"]), "end": float(scene["end"]),
            "evidence_start": float(passage["start"]),
            "evidence_end": float(passage["end"]),
            "excerpt": str(passage["text"]), "text": str(passage["text"]),
            "semantic_score": float(hit["semantic_score"]),
            "queries": list(hit.get("queries", [])),
            "editorial_role": role, "reason": reason,
            "supported_claim": claim, "warning": warning,
            "match_type": "ai_research",
        })
    return research_summary, thesis, selected_ids, evidence


def research_evidence(index: FilmIndex, topic: str, limit: int = 6) -> dict:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OpenAI is not configured yet. Add OPENAI_API_KEY to .env and restart.")
    topic = " ".join(str(topic).split()).strip()
    if len(topic) < 3:
        raise ValueError("Describe an editorial topic with at least three characters.")
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("Evidence limit must be a number.") from exc
    if not 1 <= limit <= 12:
        raise ValueError("Evidence limit must be between 1 and 12.")

    passages, exact = _passage_catalog(index)
    if not passages:
        raise ValueError("Build the local semantic index before researching evidence.")
    scenes = {int(scene["id"]): scene for scene in index.scenes()}
    discovered: dict[int, dict] = {}
    inspected: dict[int, dict] = {}
    queries: list[str] = []
    conversation: list[Any] = [{
        "role": "user",
        "content": json.dumps({"topic": topic, "desired_evidence_count": limit}),
    }]
    model = os.getenv("OPENAI_EDITORIAL_MODEL", DEFAULT_MODEL)
    client = OpenAI(api_key=key)
    executions = searches = contexts = rounds = 0
    minimum_inspected = min(3, limit)

    try:
        for _ in range(MAX_RESEARCH_ROUNDS):
            rounds += 1
            response = client.responses.create(
                model=model, instructions=_research_instructions(), input=conversation,
                tools=_RESEARCH_TOOLS, parallel_tool_calls=False,
                store=False, max_output_tokens=2200,
            )
            output = list(getattr(response, "output", []) or [])
            conversation.extend(output)
            calls = [item for item in output if _field(item, "type") == "function_call"]
            if not calls:
                if len(inspected) < minimum_inspected:
                    conversation.append({
                        "role": "user",
                        "content": (
                            "You have not inspected enough distinct local evidence yet. Continue "
                            "researching with the available tools: search again if needed, then read "
                            f"scene context until at least {minimum_inspected} distinct passage_ids "
                            "have been inspected."
                        ),
                    })
                    continue
                break
            tool_outputs = []
            for call in calls:
                name = str(_field(call, "name", ""))
                call_id = str(_field(call, "call_id", ""))
                args = _arguments(call)
                if executions >= MAX_TOOL_EXECUTIONS:
                    result = {"error": "The local research tool execution cap was reached."}
                elif name == "semantic_scene_search":
                    if searches >= MAX_SEARCH_EXECUTIONS:
                        result = {"error": "The semantic search cap was reached."}
                    else:
                        executions += 1
                        searches += 1
                        query = str(args.get("query", ""))
                        if query and query not in queries:
                            queries.append(query)
                        result = _search_tool(
                            index, query, args.get("limit", MAX_SEARCH_RESULTS),
                            passages, exact, scenes, discovered,
                        )
                elif name == "read_scene_context":
                    if contexts >= MAX_CONTEXT_EXECUTIONS:
                        result = {"error": "The scene-context cap was reached."}
                    else:
                        executions += 1
                        contexts += 1
                        try:
                            passage_id = int(args.get("passage_id", -1))
                        except (TypeError, ValueError):
                            passage_id = -1
                        result = _context_tool(
                            index, passage_id, passages, scenes, discovered, inspected
                        )
                else:
                    result = {"error": "Unknown local research tool."}
                tool_outputs.append({
                    "type": "function_call_output", "call_id": call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                })
            conversation.extend(tool_outputs)

        if len(inspected) < minimum_inspected:
            raise ValueError(
                f"OpenAI inspected only {len(inspected)} local passage(s); "
                f"at least {minimum_inspected} distinct passages are required. "
                "Try the research again."
            )
        conversation.append({
            "role": "user",
            "content": (
                "Research is complete. Submit the evidence board now. Select only inspected passage_ids. "
                f"Choose 4–6 distinct moments when that many strong inspected passages are available; "
                f"you must choose at least {min(3, limit)} and no more than {limit}."
            ),
        })
        final_tool = _final_tool(limit, list(inspected))
        final_response = client.responses.create(
            model=model, instructions=_research_instructions(), input=conversation,
            tools=[final_tool],
            tool_choice={"type": "function", "name": "submit_evidence_board"},
            parallel_tool_calls=False, store=False, max_output_tokens=3000,
        )
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
        raise _api_error(exc) from exc

    submissions = [item for item in (getattr(final_response, "output", []) or [])
                   if _field(item, "type") == "function_call"
                   and _field(item, "name") == "submit_evidence_board"]
    if len(submissions) != 1:
        raise ValueError("OpenAI returned no usable structured evidence board.")
    research_summary, thesis, selected_ids, evidence = _validate_final(
        _arguments(submissions[0]), limit=limit, inspected=inspected,
        discovered=discovered, scenes=scenes,
    )
    return {
        "topic": topic, "model": model, "research_summary": research_summary,
        "thesis_direction": thesis,
        "selected_ids": selected_ids, "evidence": evidence,
        "candidate_count": len(discovered),
        "searches": list(queries), "queries": list(queries),
        "research": {
            "rounds": rounds, "tool_calls": executions,
            "search_calls": searches, "context_calls": contexts, "queries": queries,
        },
    }


__all__ = ["research_evidence"]
