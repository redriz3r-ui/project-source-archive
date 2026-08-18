from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
from pathlib import Path

from .film_index import FilmIndex


class TranscriptionJobs:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str, movie: Path, duration: float, index: FilmIndex,
              work_dir: Path) -> dict:
        with self._lock:
            current = self._jobs.get(project_id)
            if current and current["state"] in {"queued", "running"}:
                return self.public(current)
            completed = min(duration, index.transcript_completed_through())
            job = {
                "project_id": project_id, "state": "queued", "percent": round(completed / duration * 100, 1),
                "message": "Preparing transcription", "completed_through": completed,
                "duration": duration, "started_at": time.time(), "updated_at": time.time(),
                "error": None, "cancel": threading.Event(),
            }
            self._jobs[project_id] = job
            thread = threading.Thread(
                target=self._run, args=(job, movie, index, work_dir), daemon=True,
                name=f"transcribe-{project_id}",
            )
            job["thread"] = thread
            thread.start()
            return self.public(job)

    def status(self, project_id: str, index: FilmIndex) -> dict:
        with self._lock:
            job = self._jobs.get(project_id)
            if job:
                return self.public(job)
        stats = index.stats()
        completed = float(stats["metadata"].get("transcript_completed_through", 0.0))
        duration = float(stats["metadata"].get("duration", 0.0))
        return {
            "project_id": project_id, "state": stats["metadata"].get("transcript_status", "pending"),
            "percent": round(completed / duration * 100, 1) if duration else 0,
            "completed_through": completed, "duration": duration,
            "segments": stats["counts"]["transcript_segments"], "message": "Saved transcript status",
            "error": stats["metadata"].get("transcript_error"),
        }

    def cancel(self, project_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(project_id)
            if not job or job["state"] not in {"queued", "running"}:
                return {"project_id": project_id, "state": "not_running"}
            job["cancel"].set()
            job["message"] = "Cancellation requested; finishing current chunk"
            return self.public(job)

    @staticmethod
    def public(job: dict) -> dict:
        return {key: value for key, value in job.items() if key not in {"cancel", "thread"}}

    def _update(self, job: dict, **values) -> None:
        with self._lock:
            job.update(values)
            job["updated_at"] = time.time()

    def _run(self, job: dict, movie: Path, index: FilmIndex, work_dir: Path) -> None:
        chunk_seconds = 600.0
        duration = float(job["duration"])
        start = float(job["completed_through"])
        work_dir.mkdir(parents=True, exist_ok=True)
        use_mlx = platform.machine() == "arm64" and os.environ.get("FFS_TRANSCRIBER") != "cpu"
        backend = "MLX Whisper (Apple Silicon)" if use_mlx else "Whisper CPU (2 threads)"
        try:
            self._update(job, state="running", message=f"Loading {backend}")
            index.set_transcript_status("running", transcript_backend=backend)
            cpu_model = None
            if not use_mlx:
                import torch
                import whisper
                torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
                model_dir = work_dir.parents[2] / "models"
                model_dir.mkdir(parents=True, exist_ok=True)
                cpu_model = whisper.load_model("base", device="cpu", download_root=str(model_dir))
            while start < duration:
                if job["cancel"].is_set():
                    index.set_transcript_status("paused", transcript_completed_through=start)
                    self._update(job, state="paused", message="Paused; completed work was saved")
                    return
                length = min(chunk_seconds, duration - start)
                chunk = work_dir / f"audio-{round(start):06d}.wav"
                self._update(
                    job, message=f"Extracting audio at {self._clock(start)}",
                    percent=round(start / duration * 100, 1), completed_through=start,
                )
                extraction = subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
                    "-i", str(movie), "-t", f"{length:.3f}", "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", "-y", str(chunk),
                ], capture_output=True, text=True)
                if extraction.returncode:
                    raise RuntimeError("Could not extract the next audio chunk")
                self._update(job, message=f"Transcribing {self._clock(start)}–{self._clock(start + length)}")
                if use_mlx:
                    import mlx_whisper
                    result = mlx_whisper.transcribe(
                        str(chunk), path_or_hf_repo="mlx-community/whisper-small-mlx",
                        language="en", word_timestamps=True,
                    )
                else:
                    result = cpu_model.transcribe(
                        str(chunk), language="en", fp16=False, word_timestamps=True
                    )
                segments = []
                words = []
                for segment in result.get("segments", []):
                    text = str(segment.get("text", "")).strip()
                    if text:
                        segments.append({"start": start + float(segment["start"]),
                                         "end": start + float(segment["end"]), "text": text})
                    for word in segment.get("words", []) or []:
                        word_text = str(word.get("word", word.get("text", ""))).strip()
                        if not word_text:
                            continue
                        words.append({
                            "start": start + float(word["start"]),
                            "end": start + float(word["end"]),
                            "text": word_text,
                            "confidence": word.get("probability", word.get("confidence")),
                            "source": "full_transcript",
                        })
                completed = min(duration, start + length)
                index.append_transcript(segments, completed, words)
                chunk.unlink(missing_ok=True)
                start = completed
                self._update(job, percent=round(start / duration * 100, 1), completed_through=start,
                             message=f"Saved transcript through {self._clock(start)}")
            index.set_transcript_status("complete", transcript_completed_through=duration)
            self._update(job, state="complete", percent=100.0,
                         message="Full-film transcript complete", completed_through=duration)
        except Exception as exc:
            index.set_transcript_status("failed", transcript_error=str(exc),
                                        transcript_completed_through=start)
            self._update(job, state="failed", error=str(exc), message="Transcription failed")

    @staticmethod
    def _clock(seconds: float) -> str:
        minutes, second = divmod(round(seconds), 60)
        hours, minute = divmod(minutes, 60)
        return f"{hours:02d}:{minute:02d}:{second:02d}"
