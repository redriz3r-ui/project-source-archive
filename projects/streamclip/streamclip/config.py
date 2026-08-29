from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Config:
    window_seconds: int = 5
    baseline_seconds: int = 300
    min_baseline_windows: int = 6
    z_threshold: float = 3.0
    merge_gap_seconds: int = 25
    max_candidates: int = 12
    clip_pre_seconds: int = 15
    clip_post_seconds: int = 45
    min_clip_seconds: int = 45
    max_clip_seconds: int = 90
    transcribe: bool = True
    whisper_model: str = "small"
    video_quality: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"

    @classmethod
    def load(cls, path: str | None) -> "Config":
        if not path:
            return cls()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        allowed = {f.name for f in fields(cls)}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")
        return cls(**raw)

    def to_dict(self) -> dict:
        return asdict(self)

