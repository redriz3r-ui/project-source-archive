from __future__ import annotations

from pathlib import Path

from .models import Candidate


def transcribe_candidates(candidates: list[Candidate], output_dir: Path, model_name: str) -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Transcription requested but faster-whisper is not installed. Install with: pip install -e '.[transcribe]'") from exc
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    for candidate in candidates:
        if not candidate.clip_path:
            continue
        segments, _ = model.transcribe(str(output_dir / candidate.clip_path), vad_filter=True)
        candidate.transcript = " ".join(segment.text.strip() for segment in segments).strip()

