from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict, deque

from .config import Config
from .models import Candidate, ChatMessage, ChatWindow

REACTION_RE = re.compile(r"\b(?:wtf|lmao+|lol+|no\s*way|clip|omg|w+|insane|crazy)\b", re.I)


def build_windows(messages: list[ChatMessage], config: Config) -> list[ChatWindow]:
    if not messages:
        return []
    buckets: dict[int, list[ChatMessage]] = defaultdict(list)
    size = config.window_seconds
    for msg in messages:
        buckets[int(msg.timestamp // size)].append(msg)
    last = max(buckets)
    windows = []
    history: deque[tuple[int, int]] = deque(maxlen=max(1, config.baseline_seconds // size))
    for index in range(last + 1):
        group = buckets.get(index, [])
        authors = {m.author for m in group if m.author}
        normalized = [m.text.strip().lower() for m in group if m.text.strip()]
        counts = Counter(normalized)
        repeated = sum(v for v in counts.values() if v > 1) / len(normalized) if normalized else 0.0
        reactions = sum(bool(REACTION_RE.search(m.text)) for m in group)
        volume_z = _robust_z(len(group), [x[0] for x in history], config.min_baseline_windows)
        unique_z = _robust_z(len(authors), [x[1] for x in history], config.min_baseline_windows)
        reaction_density = reactions / len(group) if group else 0.0
        score = max(0.0, volume_z) * 0.65 + max(0.0, unique_z) * 0.25 + reaction_density * 2.0 + repeated * 0.35
        windows.append(ChatWindow(index * size, (index + 1) * size, len(group), len(authors), reactions,
                                  repeated, volume_z, unique_z, score))
        history.append((len(group), len(authors)))
    return windows


def _robust_z(value: float, history: list[float], minimum: int) -> float:
    if len(history) < minimum:
        return 0.0
    median = statistics.median(history)
    deviations = [abs(x - median) for x in history]
    mad = statistics.median(deviations)
    # Poisson-like floor prevents a perfectly flat baseline from producing infinity.
    scale = max(1.4826 * mad, math.sqrt(max(median, 1.0)), 1.0)
    return (value - median) / scale


def detect_candidates(windows: list[ChatWindow], config: Config) -> list[Candidate]:
    spikes = [w for w in windows if w.score >= config.z_threshold]
    if not spikes:
        return []
    groups: list[list[ChatWindow]] = [[spikes[0]]]
    for window in spikes[1:]:
        if window.start - groups[-1][-1].end <= config.merge_gap_seconds:
            groups[-1].append(window)
        else:
            groups.append([window])
    candidates = []
    for group in groups:
        peak = max(group, key=lambda w: w.score)
        clip_start = max(0.0, peak.start - config.clip_pre_seconds)
        clip_end = peak.end + config.clip_post_seconds
        clip_end = max(clip_end, clip_start + config.min_clip_seconds)
        clip_end = min(clip_end, clip_start + config.max_clip_seconds)
        candidates.append(Candidate(
            rank=0, peak_timestamp=peak.start, event_start=group[0].start, event_end=group[-1].end,
            clip_start=clip_start, clip_end=clip_end, burst_score=round(peak.score, 3),
            peak_messages=peak.messages, unique_chatters=peak.unique_chatters,
            reaction_density=round(peak.reaction_messages / peak.messages, 3) if peak.messages else 0.0,
            repeated_ratio=round(peak.repeated_ratio, 3),
        ))
    candidates.sort(key=lambda c: c.burst_score, reverse=True)
    for rank, candidate in enumerate(candidates[:config.max_candidates], 1):
        candidate.rank = rank
    return candidates[:config.max_candidates]

