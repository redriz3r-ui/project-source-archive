from __future__ import annotations

import math
from datetime import datetime, timezone


MAX_CLIPS = 16
MIN_CLIP_DURATION = 0.6
MAX_CLIP_DURATION = 5.0
FRAMINGS = {"cinematic", "crop"}


MOOD_RECIPES = {
    "balanced": {
        "name": "Balanced",
        "description": "Reliable coverage from the beginning, middle, and end of the film.",
        "queries": [],
    },
    "romantic": {
        "name": "Romantic",
        "description": "Visible closeness, shared looks, warm spaces, and gentle two-shots.",
        "queries": [
            "cinematic romantic closeness, two people together, shared looks, gentle proximity",
            "warm intimate two-shot, tender body language, soft light, affectionate connection",
            "visually romantic atmosphere, couple, quiet closeness, warm inviting composition",
        ],
    },
    "melancholic": {
        "name": "Melancholic",
        "description": "Isolation, distance, empty space, cool light, and quiet compositions.",
        "queries": [
            "melancholic cinematic image, solitary person, emotional distance, empty negative space",
            "quiet lonely setting, cool muted light, separation, still reflective composition",
            "departure, isolation, empty street or room, subdued color, visual longing",
        ],
    },
    "dreamy": {
        "name": "Dreamy",
        "description": "Soft light, night wandering, reflections, haze, and suspended time.",
        "queries": [
            "dreamlike cinematic frame, soft light, haze, reflections, visual wonder",
            "night wandering, glowing lights, gentle color, surreal suspended atmosphere",
            "poetic image, memory-like softness, unusual light, quiet visual possibility",
        ],
    },
    "energetic": {
        "name": "Energetic",
        "description": "Movement, crowds, bright contrast, laughter, and visual momentum.",
        "queries": [
            "energetic cinematic frame, movement, lively crowd, bright contrast, action",
            "playful people laughing, spontaneous activity, dynamic composition, momentum",
            "busy street, music, dancing, travel, motion, vivid high-energy atmosphere",
        ],
    },
    "dialogue": {
        "name": "Dialogue-driven",
        "description": "Expressive conversational two-shots and close-ups with movie audio.",
        "queries": [
            "cinematic conversation, expressive close-up, two people facing each other",
            "intimate dialogue two-shot, attentive faces, quiet conversational setting",
            "animated conversation, visible gestures, speaker and listener composition",
        ],
    },
    "city": {
        "name": "City",
        "description": "Streets, transit, cafés, public spaces, crowds, and urban movement.",
        "queries": [
            "cinematic city street, urban public space, pedestrians, storefronts and transit",
            "wandering through a city, street life, cafés, public square, urban movement",
            "city atmosphere, roads, signs, buildings, station, neighborhood exterior",
        ],
    },
    "architecture": {
        "name": "Architecture",
        "description": "Buildings, façades, stations, bridges, interiors, and structural space.",
        "queries": [
            "architecture-dominant cinematic shot, building façade, structural geometry",
            "urban architecture, bridge, station, church, historic building, public square",
            "architectural interior, columns, windows, corridors, stairs, designed space",
        ],
    },
    "night": {
        "name": "Night",
        "description": "Dark exteriors, streetlights, glowing windows, and nocturnal color.",
        "queries": [
            "night exterior, streetlights, dark sky, glowing windows, nocturnal city",
            "low-light cinematic scene, artificial lights, deep shadows, night atmosphere",
            "after-dark street, illuminated architecture, neon or warm pools of light",
        ],
    },
    "nature": {
        "name": "Nature",
        "description": "Trees, parks, water, sky, landscape, and outdoor calm.",
        "queries": [
            "nature landscape, trees, park, water, sky, vegetation, outdoor environment",
            "quiet natural setting, greenery, river, open landscape, scenic exterior",
            "cinematic nature composition, plants, sunrise, sunset, earth and sky",
        ],
    },
    "custom": {
        "name": "Custom prompt",
        "description": "Use your own emotional or thematic direction.",
        "queries": [],
    },
}


VISUAL_STYLE_SIGNALS = {
    "architecture": (
        {"architecture", "building", "façade", "facade", "bridge", "station",
         "church", "chapel", "corridor", "stair", "escalator", "interior",
         "structural", "geometry", "symmetry", "wide shot"},
        {"close-up", "medium close-up"},
    ),
    "city": (
        {"city", "urban", "street", "transit", "station", "storefront", "square",
         "courtyard", "alley", "passage", "café", "cafe", "pedestrian"}, set(),
    ),
    "night": (
        {"night", "streetlamp", "dark sky", "glowing", "nocturnal", "low light",
         "shadows", "illuminated", "neon"}, {"daylight", "daytime"},
    ),
    "nature": (
        {"nature", "tree", "park", "water", "river", "sky", "vegetation", "greenery",
         "landscape", "grass", "foliage"}, {"interior"},
    ),
    "romantic": (
        {"couple", "two people", "close proximity", "side by side", "face to face",
         "warm", "intimate", "together"}, set(),
    ),
    "melancholic": (
        {"alone", "lone", "solitary", "empty", "negative space", "muted", "quiet",
         "cool", "walking away"}, {"crowd", "lively"},
    ),
    "dreamy": (
        {"soft", "haze", "reflection", "glowing", "dreamlike", "night", "candlelight",
         "saturated", "silhouette"}, set(),
    ),
    "energetic": (
        {"movement", "crowd", "lively", "dynamic", "dancing", "walking", "gesture",
         "bright", "high contrast"}, {"still", "empty"},
    ),
}


def apply_visual_style_bias(results: list[dict], style: str) -> list[dict]:
    """Use validated catalog fields to keep a broad embedding from drifting off-style."""
    signals = VISUAL_STYLE_SIGNALS.get(style)
    if not signals:
        return results
    positive, negative = signals
    adjusted = []
    for raw in results:
        text = str(raw.get("search_text") or raw.get("excerpt") or "").lower()
        positive_hits = sum(term in text for term in positive)
        negative_hits = sum(term in text for term in negative)
        score = float(raw.get("score", 0)) + min(0.21, positive_hits * 0.035) \
            - min(0.14, negative_hits * 0.07)
        adjusted.append({**raw, "score": round(score, 4)})
    adjusted.sort(key=lambda item: float(item.get("score", 0)), reverse=True)
    return adjusted


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite(value, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result


def _candidate_map(project: dict) -> dict[str, dict]:
    candidates = project.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Detect movie shots before building a Mood Montage.")
    result = {}
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        result[item["id"]] = item
    if not result:
        raise ValueError("The saved shot browser is no longer usable. Detect shots again.")
    return result


def _validate_clip(raw: dict, candidate: dict) -> dict:
    shot_start = _finite(candidate["start"], "Shot start")
    shot_end = _finite(candidate.get("shot_end", shot_start + candidate["shot_duration"]),
                       "Shot end")
    requested_start = _finite(raw.get("start", shot_start), "Clip start")
    start = min(max(shot_start, requested_start), max(shot_start, shot_end - MIN_CLIP_DURATION))
    available = max(MIN_CLIP_DURATION, shot_end - start)
    duration = _finite(raw.get("duration", candidate.get("duration", 2.2)), "Clip duration")
    duration = min(MAX_CLIP_DURATION, available, max(MIN_CLIP_DURATION, duration))
    framing = str(raw.get("framing", "cinematic"))
    if framing not in FRAMINGS:
        raise ValueError("Clip framing must be cinematic or crop.")
    crop_x = min(1.0, max(0.0, _finite(raw.get("crop_x", 0.5), "Clip focus")))
    clip = {
        "id": candidate["id"],
        "start": round(start, 3),
        "duration": round(duration, 3),
        "thumbnail": str(candidate.get("thumbnail", "")),
        "shot_start": round(shot_start, 3),
        "shot_end": round(shot_end, 3),
        "shot_duration": round(shot_end - shot_start, 3),
        "framing": framing,
        "crop_x": round(crop_x, 3),
        "original_audio": bool(raw.get("original_audio", False)),
    }
    # These fields explain an automatic mood choice. They are always derived from
    # the local film index and cannot change the source bounds used for rendering.
    for key in ("selection_reason", "mood_excerpt", "mood_score", "scene_id",
                "visual_sample_id"):
        value = raw.get(key, candidate.get(key))
        if value is not None:
            if key == "mood_score":
                clip[key] = round(min(1.0, max(-1.0, _finite(value, "Mood score"))), 4)
            elif key in {"scene_id", "visual_sample_id"}:
                clip[key] = int(value)
            else:
                limit = 500 if key == "mood_excerpt" else 180
                clip[key] = " ".join(str(value).split()).strip()[:limit]
    return clip


def validate_mood_draft(project: dict, data: dict, *, current_revision: int | None = None) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Mood Montage data must be an object.")
    if current_revision is not None:
        try:
            supplied_revision = int(data.get("revision", -1))
        except (TypeError, ValueError):
            supplied_revision = -1
        if supplied_revision != current_revision:
            raise ValueError("This Mood Montage changed in another save. Refresh before editing again.")
    candidates = _candidate_map(project)
    raw_clips = data.get("clips")
    if not isinstance(raw_clips, list) or not 1 <= len(raw_clips) <= MAX_CLIPS:
        raise ValueError(f"A Mood Montage must contain between 1 and {MAX_CLIPS} shots.")
    clips = []
    seen = set()
    for raw in raw_clips:
        if not isinstance(raw, dict):
            raise ValueError("Every Mood Montage shot must be an object.")
        shot_id = str(raw.get("id", ""))
        if shot_id in seen or shot_id not in candidates:
            raise ValueError("The Mood Montage contains an unknown or duplicate shot.")
        seen.add(shot_id)
        clips.append(_validate_clip(raw, candidates[shot_id]))

    label = " ".join(str(data.get("label", "Mood Montage")).split()).strip()[:100]
    opening_text = " ".join(str(data.get("opening_text", project.get("title", ""))).split()).strip()[:180]
    end_text = " ".join(str(data.get("end_text", "FILM LIVES HERE")).split()).strip()[:180]
    revision = 1 if current_revision is None else current_revision + 1
    movie_audio_gain = min(2.0, max(0.0, _finite(
        data.get("movie_audio_gain", 1.0), "Movie audio level"
    )))
    return {
        "id": "mood-draft",
        "label": label or "Mood Montage",
        "clips": clips,
        "opening_card": bool(data.get("opening_card", False)),
        "opening_text": opening_text or str(project.get("title") or "FILM"),
        "end_card": bool(data.get("end_card", True)),
        "end_text": end_text or "FILM LIVES HERE",
        "mood_style": _mood_style(data.get("mood_style", "balanced")),
        "mood_prompt": _mood_prompt(data.get("mood_prompt", "")),
        "selection_method": str(data.get("selection_method", "manual"))[:60],
        "mood_index_id": str(data.get("mood_index_id", ""))[:32],
        "movie_audio_gain": round(movie_audio_gain, 3),
        "revision": revision,
        "updated_at": _now(),
    }


def _mood_style(value) -> str:
    style = str(value or "balanced").strip().lower()
    if style not in MOOD_RECIPES:
        raise ValueError("Choose a supported Mood Style.")
    return style


def _mood_prompt(value) -> str:
    return " ".join(str(value or "").split()).strip()[:300]


def mood_recipe(style: str, prompt: str = "") -> dict:
    """Return the local-AI search recipe for a named or custom mood."""
    style = _mood_style(style)
    prompt = _mood_prompt(prompt)
    if style == "custom" and not prompt:
        raise ValueError("Describe the custom mood you want the montage to find.")
    recipe = dict(MOOD_RECIPES[style])
    recipe["id"] = style
    recipe["prompt"] = prompt
    recipe["queries"] = ([prompt] if style == "custom" else list(recipe["queries"]))
    if prompt and style != "custom":
        recipe["queries"].insert(0, prompt)
    return recipe


def choose_diverse_mood_moments(results: list[dict], *, clip_count: int,
                                movie_duration: float) -> list[dict]:
    """Prefer strong semantic matches while avoiding one repetitive film section."""
    if movie_duration <= 0:
        raise ValueError("The linked movie has no usable duration.")
    clip_count = max(1, int(clip_count))
    merged: dict[tuple, dict] = {}
    for query_index, query_results in enumerate(results):
        for rank, raw in enumerate(query_results):
            start = _finite(raw.get("evidence_start", raw.get("start", 0)), "Evidence start")
            end = _finite(raw.get("evidence_end", raw.get("end", start)), "Evidence end")
            if end <= start:
                continue
            key = (int(raw.get("id", raw.get("scene_id", -1))), round(start, 2), round(end, 2))
            semantic = float(raw.get("score", 0))
            rank_bonus = max(0.0, 0.035 - rank * 0.002)
            candidate = merged.get(key)
            if candidate is None:
                merged[key] = {
                    **raw, "evidence_start": start, "evidence_end": end,
                    "mood_score": semantic + rank_bonus,
                    "query_matches": [query_index],
                }
            else:
                candidate["mood_score"] = max(candidate["mood_score"], semantic + rank_bonus)
                if query_index not in candidate["query_matches"]:
                    candidate["query_matches"].append(query_index)
                    candidate["mood_score"] += 0.025

    pool = list(merged.values())
    selected: list[dict] = []
    # Temporal MMR: meaning remains primary, but repeated neighboring scenes lose
    # enough score for another strong moment elsewhere in the movie to win.
    spacing = max(45.0, movie_duration / max(4.0, clip_count * 1.5))
    while pool and len(selected) < clip_count:
        used_scenes = {int(item.get("id", item.get("scene_id", -1))) for item in selected}
        fresh_scenes = [item for item in pool
                        if int(item.get("id", item.get("scene_id", -1))) not in used_scenes]
        choice_pool = fresh_scenes or pool

        def adjusted(item: dict) -> float:
            center = (item["evidence_start"] + item["evidence_end"]) / 2
            if not selected:
                novelty = 0.0
            else:
                nearest = min(abs(center - ((other["evidence_start"] + other["evidence_end"]) / 2))
                              for other in selected)
                novelty = -0.24 * math.exp(-nearest / spacing)
            return float(item["mood_score"]) + novelty

        winner = max(choice_pool, key=adjusted)
        pool.remove(winner)
        selected.append(winner)
    selected.sort(key=lambda item: item["evidence_start"])
    return selected


def balanced_mood_draft(project: dict, *, clip_count: int = 10,
                        target_duration: float = 28.0, label: str = "Mood Montage") -> dict:
    candidates = list(_candidate_map(project).values())
    clip_count = min(12, max(6, int(clip_count)))
    clip_count = min(clip_count, len(candidates))
    target_duration = min(36.0, max(20.0, _finite(target_duration, "Target duration")))
    movie_duration = float(project.get("movie", {}).get("duration", 0))
    if movie_duration <= 0:
        raise ValueError("The linked movie has no usable duration.")

    eligible = [item for item in candidates if float(item.get("shot_duration", 0)) >= 1.0]
    if len(eligible) < clip_count:
        eligible = candidates
    selected = []
    used = set()
    for bucket in range(clip_count):
        target = movie_duration * (bucket + 0.5) / clip_count
        options = [item for item in eligible if item["id"] not in used]
        if not options:
            break
        item = min(options, key=lambda shot: abs(
            (float(shot["start"]) + float(shot.get("shot_end", shot["start"]))) / 2 - target
        ))
        used.add(item["id"])
        selected.append(item)
    selected.sort(key=lambda item: float(item["start"]))
    per_clip = target_duration / max(1, len(selected))
    clips = [{
        **item,
        "duration": min(MAX_CLIP_DURATION, per_clip,
                        max(MIN_CLIP_DURATION, float(item.get("shot_duration", per_clip)) - 0.1)),
        "framing": "cinematic", "crop_x": 0.5, "original_audio": False,
    } for item in selected]
    return validate_mood_draft(project, {
        "label": label, "clips": clips,
        "mood_style": "balanced", "mood_prompt": "",
        "selection_method": "runtime_balanced",
        "opening_card": False, "opening_text": project.get("title", ""),
        "end_card": True, "end_text": "FILM LIVES HERE",
    })


__all__ = [
    "MOOD_RECIPES", "balanced_mood_draft", "choose_diverse_mood_moments",
    "apply_visual_style_bias", "mood_recipe", "validate_mood_draft",
]
