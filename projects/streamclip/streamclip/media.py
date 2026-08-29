from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import Candidate


def extract_clips(video: Path, candidates: list[Candidate], output_dir: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to generate clips; install it and rerun with --reuse")
    clips = output_dir / "clips"
    clips.mkdir(exist_ok=True)
    for candidate in candidates:
        target = clips / f"candidate_{candidate.rank:02d}_{int(candidate.peak_timestamp):06d}.mp4"
        duration = candidate.clip_end - candidate.clip_start
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(candidate.clip_start),
               "-i", str(video), "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
               "-c:a", "aac", "-movflags", "+faststart", str(target)]
        subprocess.run(cmd, check=True)
        candidate.clip_path = str(target.relative_to(output_dir))

