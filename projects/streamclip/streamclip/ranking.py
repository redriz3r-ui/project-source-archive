from __future__ import annotations

import re

from .models import Candidate

HOOK_RE = re.compile(r"\b(?:wait|what|why|how|look|listen|bro|never|just|you won't|guess)\b", re.I)


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return []
    max_burst = max(c.burst_score for c in candidates) or 1.0
    for candidate in candidates:
        reasons = ["large normalized chat burst"]
        score = 55.0 * candidate.burst_score / max_burst
        score += min(15.0, candidate.reaction_density * 40)
        score += min(10.0, candidate.unique_chatters / max(candidate.peak_messages, 1) * 10)
        if candidate.transcript:
            words = candidate.transcript.split()
            if 20 <= len(words) <= 220:
                score += 10
                reasons.append("self-contained transcript length")
            if HOOK_RE.search(candidate.transcript[:180]):
                score += 10
                reasons.append("early verbal hook")
        else:
            reasons.append("untranscribed: ranking uses chat only")
        candidate.standalone_score = round(min(100.0, score), 1)
        candidate.reasons = reasons
    candidates.sort(key=lambda c: (c.standalone_score, c.burst_score), reverse=True)
    for rank, candidate in enumerate(candidates, 1):
        candidate.rank = rank
    return candidates

