from __future__ import annotations

import bisect
import re

from .film_index import FilmIndex


def normalize_transcript(raw: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for segment in raw:
        text = re.sub(r"\s+", " ", str(segment["text"])).strip()
        if not text:
            continue
        flags = []
        words = text.split()
        if len(words) <= 2:
            flags.append("short_fragment")
        if len(words) >= 2 and words[0].lower() == words[1].lower():
            flags.append("possible_repetition")
        current = {"start": float(segment["start"]), "end": float(segment["end"]),
                   "text": text, "source_ids": [segment["id"]], "flags": flags}
        if normalized:
            previous = normalized[-1]
            gap = current["start"] - previous["end"]
            crosses_chunk = int(previous["end"] // 600) != int(current["start"] // 600)
            continuation = (not re.search(r"[.!?…][\"']?$", previous["text"])
                            and text[:1].islower() and gap <= 0.4)
            if continuation or (crosses_chunk and gap <= 0.25 and len(previous["text"].split()) < 18):
                previous["end"] = current["end"]
                previous["text"] += " " + current["text"]
                previous["source_ids"].extend(current["source_ids"])
                previous["flags"] = sorted(set(previous["flags"] + current["flags"] + ["merged"]))
                continue
        normalized.append(current)
    return normalized


def propose_scenes(index: FilmIndex, movie_duration: float) -> list[dict]:
    transcript = index.normalized_transcript()
    shots = index.shots()
    if not transcript:
        raise ValueError("The normalized transcript is empty.")
    shot_boundaries = sorted({float(shot["start"]) for shot in shots if float(shot["start"]) > 0})
    candidates: dict[float, dict] = {
        boundary: {"time": boundary, "score": 1.0, "reasons": ["detected visual transition"]}
        for boundary in shot_boundaries
    }

    def nearest_boundary(timestamp: float, tolerance: float = 12.0) -> float | None:
        if not shot_boundaries:
            return timestamp
        position = bisect.bisect_left(shot_boundaries, timestamp)
        options = shot_boundaries[max(0, position - 1): position + 1]
        nearest = min(options, key=lambda value: abs(value - timestamp)) if options else None
        return nearest if nearest is not None and abs(nearest - timestamp) <= tolerance else timestamp

    for previous, current in zip(transcript, transcript[1:]):
        gap = float(current["start"]) - float(previous["end"])
        if gap < 2.0:
            continue
        midpoint = float(previous["end"]) + gap / 2
        boundary = nearest_boundary(midpoint)
        if boundary is None:
            continue
        candidate = candidates.setdefault(boundary, {"time": boundary, "score": 0.0, "reasons": []})
        if gap >= 8:
            candidate["score"] += 5
            candidate["reasons"].append(f"{gap:.1f}s dialogue gap")
        elif gap >= 4:
            candidate["score"] += 3
            candidate["reasons"].append(f"{gap:.1f}s dialogue gap")
        else:
            candidate["score"] += 1
            candidate["reasons"].append(f"{gap:.1f}s dialogue gap")
        if re.search(r"[.!?…][\"']?$", str(previous["text"])):
            candidate["score"] += 0.5
            candidate["reasons"].append("dialogue unit ends")

    selected = []
    last = 0.0
    for candidate in sorted(candidates.values(), key=lambda item: item["time"]):
        if candidate["score"] >= 4 and candidate["time"] - last >= 45:
            selected.append(candidate)
            last = candidate["time"]

    # Prevent an uninterrupted dialogue-heavy passage from becoming one giant scene.
    final_boundaries = []
    start = 0.0
    all_candidates = sorted(candidates.values(), key=lambda item: item["time"])
    for target in selected + [{"time": movie_duration, "score": 0, "reasons": ["end of film"]}]:
        end = float(target["time"])
        while end - start > 360:
            eligible = [c for c in all_candidates if start + 120 <= c["time"] <= start + 360]
            split = max(eligible, key=lambda c: (c["score"], c["time"]), default=None)
            split_time = float(split["time"]) if split else start + 300
            final_boundaries.append({"time": split_time, "score": split["score"] if split else 0,
                                     "reasons": (split["reasons"] if split else ["maximum scene length"])})
            start = split_time
        if end < movie_duration:
            final_boundaries.append(target)
        start = end

    boundaries = [{"time": 0.0, "score": None, "reasons": ["start of film"]}] + final_boundaries
    if not boundaries or boundaries[-1]["time"] < movie_duration:
        boundaries.append({"time": movie_duration, "score": 0, "reasons": ["end of film"]})
    scenes = []
    for number, (left, right) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        start, end = float(left["time"]), float(right["time"])
        overlapping = [s for s in transcript if float(s["start"]) < end and float(s["end"]) > start]
        excerpt = " ".join(str(s["text"]) for s in overlapping[:5])[:600]
        scenes.append({"start": round(start, 3), "end": round(end, 3),
                       "title": f"Proposed Scene {number:02d}",
                       "summary": f"{len(overlapping)} dialogue units",
                       "dialogue_excerpt": excerpt,
                       "boundary_score": right.get("score"),
                       "boundary_reasons": right.get("reasons", [])})
    return scenes


def build_scene_map(index: FilmIndex, movie_duration: float) -> dict:
    normalized = normalize_transcript(index.raw_transcript())
    index.replace_normalized_transcript(normalized)
    scenes = propose_scenes(index, movie_duration)
    index.replace_scenes(scenes)
    return {"normalized_segments": len(normalized), "scenes": scenes}
