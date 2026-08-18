from __future__ import annotations

import json
import re
from collections import Counter

from .film_index import FilmIndex


STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before",
    "being", "but", "can", "come", "could", "did", "does", "doing", "for", "from",
    "get", "going", "got", "had", "has", "have", "her", "here", "him", "his", "how",
    "into", "its", "just", "know", "like", "maybe", "more", "much", "not", "now",
    "one", "only", "out", "really", "right", "said", "see", "she", "some", "than",
    "that", "the", "their", "them", "then", "there", "they", "thing", "think", "this",
    "time", "too", "very", "want", "was", "way", "well", "were", "what", "when",
    "where", "which", "who", "why", "will", "with", "would", "yeah", "yes", "you",
    "your", "i'm", "it's", "don't", "that's",
}


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def enrich_scenes(index: FilmIndex) -> dict:
    scenes = index.scenes()
    transcript = index.normalized_transcript()
    documents = []
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        units = [u for u in transcript if float(u["start"]) < end and float(u["end"]) > start]
        intervals = _merge_intervals([
            (max(start, float(unit["start"])), min(end, float(unit["end"]))) for unit in units
        ])
        dialogue_seconds = sum(right - left for left, right in intervals)
        silence_gaps = []
        cursor = start
        for left, right in intervals:
            silence_gaps.append(max(0.0, left - cursor))
            cursor = max(cursor, right)
        silence_gaps.append(max(0.0, end - cursor))
        text = " ".join(str(unit["text"]) for unit in units)
        words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z']+", text)]
        keywords = [word for word, _ in Counter(
            word for word in words if len(word) >= 4 and word not in STOPWORDS
        ).most_common(10)]
        documents.append({
            "scene_id": scene["id"], "title": scene["title"], "transcript": text,
            "first_dialogue": float(units[0]["start"]) if units else None,
            "last_dialogue": float(units[-1]["end"]) if units else None,
            "dialogue_seconds": round(dialogue_seconds, 3),
            "dialogue_density": round(dialogue_seconds / max(0.001, end - start), 4),
            "longest_silence": round(max(silence_gaps, default=end - start), 3),
            "dialogue_units": len(units), "question_count": text.count("?"),
            "keywords": keywords,
        })
    index.replace_scene_documents(documents)
    return {"documents": len(documents)}

