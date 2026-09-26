from __future__ import annotations
import math
import re
from pathlib import Path
import cv2
import numpy as np


def tokens(mood: str | list[str]) -> set[str]:
    return set(re.findall(r'[\w-]+', ' '.join(mood).lower() if isinstance(mood, list) else mood.lower()))


def score(shot: dict, mood: set[str], cfg: dict, treatment: str = 'atmosphere') -> float:
    weights = cfg['ranking']
    energetic = bool(mood & {'fast', 'energetic', 'frenetic', 'chaotic', 'restless', 'movement'})
    quiet = bool(mood & {'quiet', 'dreamy', 'melancholy', 'romantic', 'lonely', 'longing'})
    motion_target = 0.65 if energetic else 0.15 if quiet else 0.35
    if treatment == 'energy':
        motion_target = min(1, motion_target + 0.2)
    base = (weights['visual_interest'] * shot['visual_interest'] + weights['composition'] * shot['composition_score']
            + weights['motion'] * (2.0 if energetic else 1.0) * (1 - abs(shot['motion_score'] - motion_target))
            + weights['faces'] * shot['face_fraction'])
    if mood & {'night', 'nocturnal', 'dark', 'neon'}:
        base += 0.5 * shot['darkness']
    if mood & {'neon', 'colorful', 'dreamy'}:
        base += 0.4 * shot['colorfulness']
    if mood & {'romantic', 'faces', 'emotional', 'longing'} or treatment == 'emotion':
        base += 0.25 * shot['face_fraction']
    if mood & {'quiet', 'melancholy', 'lonely'}:
        base += 0.25 * shot['stability']
    semantic = set(shot.get('semantic_tags', []) + shot.get('mood_tags', []))
    base += 0.5 * len(mood & semantic)
    return base + 0.15 * min(1, shot['duration'] / 3)


def similarity(a: dict, b: dict, cfg: dict) -> float:
    temporal = math.exp(-abs(a['start'] - b['start']) / cfg['ranking']['timestamp_separation'])
    color = 1 - min(1, math.dist(a['mean_color'], b['mean_color']) / 0.9)
    composition = 1 - min(1, math.dist(a['primary_subject'], b['primary_subject']))
    motion = 1 - abs(a['motion_score'] - b['motion_score'])
    tags_a, tags_b = set(a.get('semantic_tags', [])), set(b.get('semantic_tags', []))
    semantic = len(tags_a & tags_b) / max(1, len(tags_a | tags_b))
    visual = color
    if 'visual_descriptor' in a and 'visual_descriptor' in b:
        visual = float(np.minimum(a['visual_descriptor'], b['visual_descriptor']).sum())
    return 0.35 * temporal + 0.35 * visual + 0.1 * color + 0.1 * composition + 0.05 * motion + 0.05 * semantic


def eligible(shots: list[dict], film_duration: float, spoilers: str, cfg: dict, exclusions: list) -> list[dict]:
    cutoff = film_duration * cfg['spoilers'].get(f'{spoilers}_max_fraction', 1)
    return [s for s in shots if s['duration'] >= 0.35 and s['end'] <= cutoff
            and not any(s['start'] < b and s['end'] > a for a, b in exclusions)
            and not (spoilers == 'low' and s.get('spoiler_score', 0) > 0.3)]


def add_visual_descriptors(shots: list[dict], project: Path) -> None:
    """Read tiny cached thumbnails, never the movie, to compare visual appearance."""
    for shot in shots:
        if 'visual_descriptor' in shot:
            continue
        frame = cv2.imread(str(project / shot['thumbnail']))
        if frame is None:
            raise ValueError(f"Missing thumbnail for shot {shot['shot_id']}; rerun analyze")
        hsv = cv2.cvtColor(cv2.resize(frame, (96, 54)), cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]).ravel()
        shot['visual_descriptor'] = (hist / max(1, hist.sum())).tolist()
