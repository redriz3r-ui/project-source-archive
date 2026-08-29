from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatMessage:
    timestamp: float
    author: str = ""
    text: str = ""


@dataclass
class ChatWindow:
    start: float
    end: float
    messages: int = 0
    unique_chatters: int = 0
    reaction_messages: int = 0
    repeated_ratio: float = 0.0
    volume_z: float = 0.0
    unique_z: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    rank: int
    peak_timestamp: float
    event_start: float
    event_end: float
    clip_start: float
    clip_end: float
    burst_score: float
    peak_messages: int
    unique_chatters: int
    reaction_density: float
    repeated_ratio: float
    transcript: str = ""
    standalone_score: float = 0.0
    clip_path: str = ""
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

