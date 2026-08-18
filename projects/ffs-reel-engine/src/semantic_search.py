from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np

from .film_index import FilmIndex


MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_CACHE = Path(__file__).resolve().parents[1] / "work" / "models" / "huggingface"
MAX_WORDS = 220
OVERLAP_WORDS = 40


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    try:
        return SentenceTransformer(
            MODEL_NAME, cache_folder=str(MODEL_CACHE), local_files_only=True
        )
    except OSError:
        # First run only: download into the project. Later loads stay offline.
        return SentenceTransformer(MODEL_NAME, cache_folder=str(MODEL_CACHE))


def _scene_passages(index: FilmIndex) -> list[dict]:
    units = index.normalized_transcript()
    passages = []
    for scene in index.scenes():
        scene_units = [u for u in units if u["start"] < scene["end"] and u["end"] > scene["start"]]
        current: list[dict] = []
        word_count = 0
        for unit in scene_units:
            words = str(unit["text"]).split()
            if current and word_count + len(words) > MAX_WORDS:
                passages.append({
                    "scene_id": scene["id"], "start": current[0]["start"],
                    "end": current[-1]["end"],
                    "text": " ".join(item["text"] for item in current),
                })
                overlap = []
                overlap_words = 0
                for item in reversed(current):
                    overlap.insert(0, item)
                    overlap_words += len(str(item["text"]).split())
                    if overlap_words >= OVERLAP_WORDS:
                        break
                current, word_count = overlap, overlap_words
            current.append(unit)
            word_count += len(words)
        if current:
            passages.append({
                "scene_id": scene["id"], "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": " ".join(item["text"] for item in current),
            })
    return [p for p in passages if p["text"].strip()]


def build_semantic_index(index: FilmIndex) -> dict:
    passages = _scene_passages(index)
    if not passages:
        raise ValueError("Enrich the transcript scene index before semantic indexing.")
    model = _model()
    vectors = model.encode_document(
        [p["text"] for p in passages], normalize_embeddings=True, show_progress_bar=False
    ).astype(np.float32)
    for passage, vector in zip(passages, vectors):
        passage["embedding"] = vector.tobytes()
    index.replace_semantic_passages(passages, model=MODEL_NAME, dimensions=vectors.shape[1])
    return {"passages": len(passages), "scenes": len({p["scene_id"] for p in passages}),
            "model": MODEL_NAME, "dimensions": int(vectors.shape[1])}


def semantic_search(index: FilmIndex, query: str, limit: int = 12) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    passages = index.semantic_passages()
    if not passages:
        raise ValueError("Build the semantic index first.")
    query_vector = _model().encode_query(query, normalize_embeddings=True)
    by_scene: dict[int, list[tuple[float, dict]]] = defaultdict(list)
    for passage in passages:
        vector = np.frombuffer(passage["embedding"], dtype=np.float32)
        by_scene[passage["scene_id"]].append((float(np.dot(query_vector, vector)), passage))
    scenes = {scene["id"]: scene for scene in index.scenes()}
    results = []
    for scene_id, matches in by_scene.items():
        matches.sort(key=lambda item: item[0], reverse=True)
        best_score, best = matches[0]
        scene = dict(scenes[scene_id])
        scene.update({
            "score": round(best_score, 4), "excerpt": best["text"],
            "evidence_start": best["start"], "evidence_end": best["end"],
            "match_type": "semantic",
        })
        results.append(scene)
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
