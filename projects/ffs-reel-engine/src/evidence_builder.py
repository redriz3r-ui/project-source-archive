from __future__ import annotations

from collections import defaultdict

from .film_index import FilmIndex
from .semantic_search import semantic_search


def _search_angles(topic: str) -> list[dict]:
    return [
        {"label": "Core idea", "query": topic},
        {"label": "Revelation", "query": f"characters reveal personal feelings through {topic}"},
        {"label": "Conversation", "query": f"conversation and dialogue demonstrating {topic}"},
        {"label": "Tension", "query": f"fear conflict hesitation or uncertainty surrounding {topic}"},
        {"label": "Development", "query": f"a relationship or character changes through {topic}"},
    ]


def build_evidence_board(index: FilmIndex, topic: str, limit: int = 8) -> dict:
    topic = " ".join(topic.split()).strip()
    if len(topic) < 3:
        raise ValueError("Describe an editorial idea with at least three characters.")

    angles = _search_angles(topic)
    matches: dict[int, list[dict]] = defaultdict(list)
    for angle in angles:
        for result in semantic_search(index, angle["query"], limit=10):
            matches[result["id"]].append({"angle": angle["label"], **result})

    candidates = []
    for scene_id, scene_matches in matches.items():
        scene_matches.sort(key=lambda item: item["score"], reverse=True)
        best = dict(scene_matches[0])
        scores = [item["score"] for item in scene_matches]
        coverage = len({item["angle"] for item in scene_matches})
        # Reward both a strong direct match and support across several editorial lenses.
        combined = 0.75 * max(scores) + 0.20 * (sum(scores[:3]) / min(3, len(scores)))
        combined += 0.01 * coverage
        best.update({
            "score": round(combined, 4),
            "semantic_score": round(max(scores), 4),
            "angles": list(dict.fromkeys(item["angle"] for item in scene_matches)),
            "match_type": "evidence",
        })
        candidates.append(best)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    chosen = []
    for candidate in candidates:
        # Keep the board useful as an editorial overview instead of filling it
        # with neighboring scenes from a single stretch of the film.
        if any(abs(candidate["evidence_start"] - item["evidence_start"]) < 120 for item in chosen):
            continue
        chosen.append(candidate)
        if len(chosen) == limit:
            break

    return {
        "topic": topic,
        "angles": angles,
        "evidence": chosen,
        "candidate_count": len(candidates),
    }
