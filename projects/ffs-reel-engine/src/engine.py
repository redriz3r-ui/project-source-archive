from __future__ import annotations

import json
import hashlib
import os
import platform
import re
import subprocess
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .film_index import FilmIndex, source_fingerprint
from .transcription import TranscriptionJobs
from .scene_map import build_scene_map
from .scene_enrichment import enrich_scenes
from .semantic_search import build_semantic_index, semantic_search
from .evidence_builder import build_evidence_board
from .ai_evidence_research import research_evidence
from .editorial_rerank import api_status, editorial_rerank
from .concept_generator import generate_concepts
from .storyboard import create_storyboard, find_storyboard, update_storyboard
from .editorial_renderer import (
    EditorialRenderError, _render_text_card, render_editorial_storyboard,
)
from .captions import extract_clip_captions
from .visual_evidence import analyze_visual_evidence
from .visual_montage import (
    build_targeted_mood_index, build_visual_montage_index, search_visual_montage,
)
from .clip_refinement import refine_clip_alignment
from .conversion_renderer import (
    ConversionRenderError, default_conversion_config, normalize_conversion_config,
    render_conversion_reel,
)
from .mood_montage import (
    MOOD_RECIPES, apply_visual_style_bias, balanced_mood_draft, choose_diverse_mood_moments,
    mood_recipe, validate_mood_draft,
)


class EngineError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "movie"


def _normalized_topic(value: str) -> str:
    return " ".join(str(value).split()).strip()


def _seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def parse_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.splitlines()
        timing = next((line for line in lines if "-->" in line), None)
        if not timing:
            continue
        idx = lines.index(timing)
        start, end = [part.strip().split(" ")[0] for part in timing.split("-->")]
        caption = " ".join(lines[idx + 1 :])
        caption = re.sub(r"<[^>]+>", "", caption).strip()
        if caption:
            cues.append({"start": _seconds(start), "end": _seconds(end), "text": caption})
    if not cues:
        raise EngineError("No readable subtitle cues were found in the SRT file.")
    return cues


def _srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class ReelEngine:
    def __init__(self, root: Path):
        self.root = root
        self.projects = root / "work" / "projects"
        self.outputs = root / "outputs"
        self.projects.mkdir(parents=True, exist_ok=True)
        self.outputs.mkdir(parents=True, exist_ok=True)
        self._save_lock = threading.RLock()
        self.transcription_jobs = TranscriptionJobs()

    def _file(self, project_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9-]+", project_id):
            raise EngineError("Invalid project id.")
        return self.projects / project_id / "project.json"

    def project_dir(self, project_id: str) -> Path:
        return self._file(project_id).parent

    def film_index(self, project_id: str) -> FilmIndex:
        return FilmIndex(self.project_dir(project_id) / "index" / "film-index.sqlite3")

    def load(self, project_id: str) -> dict:
        with self._save_lock:
            path = self._file(project_id)
            if not path.exists():
                raise EngineError("Project not found.")
            return json.loads(path.read_text())

    def _save(self, project: dict) -> dict:
        with self._save_lock:
            project["updated_at"] = _now()
            path = self._file(project["id"])
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(project, indent=2) + "\n")
            temp.replace(path)
            return project

    @staticmethod
    def _source_fingerprint(project: dict, index: FilmIndex) -> str | None:
        movie = project.get("movie")
        if isinstance(movie, dict):
            fingerprint = movie.get("fingerprint")
            if isinstance(fingerprint, str) and fingerprint:
                return fingerprint
        metadata_fingerprint = index.stats()["metadata"].get("source_fingerprint")
        if isinstance(metadata_fingerprint, str) and metadata_fingerprint:
            return metadata_fingerprint
        if isinstance(movie, dict):
            path_value = movie.get("path")
            if isinstance(path_value, str):
                path = Path(path_value).expanduser()
                if path.is_file():
                    return source_fingerprint(path.resolve())
        return None

    def _research_binding(self, project: dict, index: FilmIndex) -> tuple[str | None, str]:
        return self._source_fingerprint(project, index), index.semantic_index_signature()

    @staticmethod
    def _clear_film_dependent_project_state(project: dict) -> None:
        project["transcript"] = []
        project["candidates"] = []
        for key in (
            "shot_index", "transcription", "subtitle_path", "evidence_researches",
            "editorial_storyboards", "active_storyboard_id", "mood_montage_draft",
            "visual_montage_index",
            "mood_visual_indexes",
            "conversion_reel",
        ):
            project.pop(key, None)

    def create_project(self, title: str) -> dict:
        title = str(title).strip() or "Untitled film"
        project_id = f"{_slug(title)}-{uuid.uuid4().hex[:6]}"
        return self._save({
            "schema_version": "0.1",
            "id": project_id,
            "title": title,
            "created_at": _now(),
            "recipe": "mood_montage",
            "movie": None,
            "transcript": [],
            "candidates": [],
            "exports": [],
        })

    def ingest_movie(self, project_id: str, movie_value: str) -> dict:
        movie = Path(movie_value).expanduser().resolve()
        if not movie.is_file():
            raise EngineError("Choose an existing local movie file.")
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of", "json", str(movie),
        ], capture_output=True, text=True)
        if probe.returncode:
            raise EngineError("FFprobe could not read the movie file.")
        info = json.loads(probe.stdout)
        video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
        if not video:
            raise EngineError("The selected file has no video stream.")
        fingerprint = source_fingerprint(movie)
        with self._save_lock:
            # Reload only after the potentially slow probe/fingerprint work so a
            # concurrent project edit cannot be overwritten by a stale snapshot.
            project = self.load(project_id)
            index = self.film_index(project_id)
            old_movie = project.get("movie")
            old_fingerprint = self._source_fingerprint(project, index)
            counts = index.stats()["counts"]
            source_changed = bool(old_fingerprint and old_fingerprint != fingerprint)
            if old_fingerprint is None and (isinstance(old_movie, dict) or any(counts.values())):
                old_path = str(old_movie.get("path") or "") if isinstance(old_movie, dict) else ""
                source_changed = old_path != str(movie) or any(counts.values())

            if source_changed:
                self.transcription_jobs.cancel(project_id)
                index.reset_for_source()
                self._clear_film_dependent_project_state(project)

            project["movie"] = {
                "path": str(movie), "filename": movie.name,
                "duration": float(info["format"]["duration"]),
                "width": video.get("width"), "height": video.get("height"),
                "codec": video.get("codec_name"), "fps": video.get("r_frame_rate"),
                "fingerprint": fingerprint,
            }
            metadata = {
                "source_path": str(movie), "source_fingerprint": fingerprint,
                "film_title": project["title"], "duration": project["movie"]["duration"],
            }
            if source_changed or not isinstance(old_movie, dict):
                metadata.update({
                    "shot_index_status": "pending", "transcript_status": "pending",
                    "scene_index_status": "pending", "semantic_index_status": "pending",
                })
            index.set_metadata(metadata)
            project["candidates"] = [] if source_changed else project.get("candidates", [])
            return self._save(project)

    def discover_shots(self, project_id: str, limit: int = 48) -> dict:
        project = self.load(project_id)
        if not project.get("movie"):
            raise EngineError("Load a movie first.")
        duration = float(project["movie"]["duration"])
        scan = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "info", "-threads", "2",
            "-filter_threads", "2", "-i", project["movie"]["path"], "-an",
            "-vf", "scale=320:-2,select='gt(scene,0.32)',showinfo",
            "-fps_mode", "vfr", "-f", "null", "-",
        ], capture_output=True, text=True)
        if scan.returncode:
            raise EngineError("Visual shot detection failed.")
        boundaries = [0.0]
        for match in re.finditer(r"pts_time:([0-9.]+)", scan.stderr):
            timestamp = float(match.group(1))
            # Suppress flashes, dissolves, and repeated detections within the
            # same transition while keeping genuine rapid cutting.
            if timestamp - boundaries[-1] >= 0.75:
                boundaries.append(timestamp)
        if duration - boundaries[-1] >= 0.4:
            boundaries.append(duration)
        detected = []
        for start, end in zip(boundaries, boundaries[1:]):
            shot_duration = end - start
            if shot_duration >= 0.65:
                detected.append({"start": start, "end": end, "shot_duration": shot_duration})
        if not detected:
            raise EngineError("No visual shot boundaries were detected.")
        count = min(limit, len(detected))
        # Select by elapsed runtime, not by shot-list index. Faster-cut sections
        # can contain many more shots and would otherwise dominate the browser.
        selected = []
        used: set[int] = set()
        for bucket in range(count):
            target = duration * (bucket + 0.5) / count
            ranked = sorted(
                range(len(detected)),
                key=lambda index: abs(
                    (float(detected[index]["start"]) + float(detected[index]["end"])) / 2 - target
                ),
            )
            index = next((candidate for candidate in ranked if candidate not in used), None)
            if index is not None:
                used.add(index)
                selected.append(detected[index])
        selected.sort(key=lambda shot: float(shot["start"]))
        thumb_dir = self.project_dir(project_id) / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        shots = []
        for index, detected_shot in enumerate(selected):
            start = float(detected_shot["start"])
            shot_duration = float(detected_shot["shot_duration"])
            timestamp = start + min(max(0.2, shot_duration * 0.45), 1.5)
            name = f"shot-{index:03d}.jpg"
            destination = thumb_dir / name
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
                "-i", project["movie"]["path"], "-frames:v", "1", "-vf", "scale=360:-2",
                "-q:v", "3", "-y", str(destination),
            ], capture_output=True, text=True)
            if result.returncode == 0:
                edit_duration = min(2.2, max(0.6, shot_duration - 0.1))
                shots.append({"id": f"shot-{index:03d}", "start": round(start, 3),
                              "duration": round(edit_duration, 3), "thumbnail": name,
                              "shot_end": round(float(detected_shot["end"]), 3),
                              "shot_duration": round(shot_duration, 3)})
        browser_starts = {round(float(shot["start"]), 3) for shot in selected}
        self.film_index(project_id).replace_shots(detected, 0.32, browser_starts)
        project["candidates"] = shots
        project["shot_index"] = {"method": "ffmpeg_scene_score", "threshold": 0.32,
                                 "detected_count": len(detected), "displayed_count": len(shots)}
        self._save(project)
        return {"shots": shots, **project["shot_index"]}

    def index_status(self, project_id: str) -> dict:
        self.load(project_id)
        return self.film_index(project_id).stats()

    def start_transcription(self, project_id: str) -> dict:
        project = self.load(project_id)
        if not project.get("movie"):
            raise EngineError("Load a movie before transcribing it.")
        return self.transcription_jobs.start(
            project_id, Path(project["movie"]["path"]), float(project["movie"]["duration"]),
            self.film_index(project_id), self.project_dir(project_id) / "transcription",
        )

    def transcription_status(self, project_id: str) -> dict:
        self.load(project_id)
        return self.transcription_jobs.status(project_id, self.film_index(project_id))

    def cancel_transcription(self, project_id: str) -> dict:
        self.load(project_id)
        return self.transcription_jobs.cancel(project_id)

    def generate_scene_map(self, project_id: str) -> dict:
        project = self.load(project_id)
        index = self.film_index(project_id)
        if index.stats()["metadata"].get("transcript_status") != "complete":
            raise EngineError("Complete the full-film transcript before grouping scenes.")
        try:
            return build_scene_map(index, float(project["movie"]["duration"]))
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    def scenes(self, project_id: str) -> dict:
        self.load(project_id)
        scenes = self.film_index(project_id).scenes()
        return {"scenes": scenes, "count": len(scenes)}

    def enrich_scene_index(self, project_id: str) -> dict:
        self.load(project_id)
        return enrich_scenes(self.film_index(project_id))

    def search_scene_index(self, project_id: str, query: str) -> dict:
        self.load(project_id)
        return {"query": query, "results": self.film_index(project_id).search_scenes(query)}

    def build_semantic_scene_index(self, project_id: str) -> dict:
        self.load(project_id)
        try:
            return build_semantic_index(self.film_index(project_id))
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    def semantic_scene_search(self, project_id: str, query: str) -> dict:
        self.load(project_id)
        try:
            return {"query": query, "results": semantic_search(self.film_index(project_id), query)}
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    def evidence_board(self, project_id: str, topic: str) -> dict:
        self.load(project_id)
        try:
            return build_evidence_board(self.film_index(project_id), topic)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    @staticmethod
    def _legacy_evidence_matches(index: FilmIndex, evidence: list[dict]) -> bool:
        """Verify an older unbound board against exact current passage content."""
        passages = {int(item["id"]): item for item in index.semantic_passages()}
        if not passages:
            return False
        for item in evidence:
            if not isinstance(item, dict):
                return False
            try:
                passage_id = int(item.get("passage_id", item["id"]))
                start = float(item["evidence_start"])
                end = float(item["evidence_end"])
            except (KeyError, TypeError, ValueError):
                return False
            passage = passages.get(passage_id)
            if passage is None:
                return False
            if abs(float(passage["start"]) - start) >= 0.001:
                return False
            if abs(float(passage["end"]) - end) >= 0.001:
                return False
            if "scene_id" in item:
                try:
                    if int(item["scene_id"]) != int(passage["scene_id"]):
                        return False
                except (TypeError, ValueError):
                    return False
            saved_text = item.get("excerpt", item.get("text"))
            if not isinstance(saved_text, str) or saved_text != str(passage["text"]):
                return False
        return True

    def _evidence_research(self, project: dict, research_id: str, topic: str) -> dict:
        if not isinstance(research_id, str) or not re.fullmatch(
                r"research-[0-9a-f]{8}", research_id):
            raise EngineError("Evidence research not found. Research the idea with OpenAI again.")
        researches = project.get("evidence_researches", [])
        if not isinstance(researches, list):
            raise EngineError(
                "Saved evidence research is no longer usable. Research the idea with OpenAI again."
            )
        record = next(
            (item for item in reversed(researches)
             if isinstance(item, dict) and item.get("id") == research_id),
            None,
        )
        if record is None:
            raise EngineError("Evidence research not found. Research the idea with OpenAI again.")
        board = record.get("board")
        evidence = board.get("evidence") if isinstance(board, dict) else None
        board_topic = _normalized_topic(board.get("topic", "")) if isinstance(board, dict) else ""
        if not board_topic or not isinstance(evidence, list) or not evidence:
            raise EngineError(
                "Saved evidence research is no longer usable. Research the idea with OpenAI again."
            )
        if _normalized_topic(topic).casefold() != board_topic.casefold():
            raise EngineError("The topic does not match the selected evidence research.")
        seen: set[int] = set()
        for item in evidence:
            try:
                evidence_id = int(item["id"])
                start = float(item["evidence_start"])
                end = float(item["evidence_end"])
            except (KeyError, TypeError, ValueError):
                raise EngineError(
                    "Saved evidence research is no longer usable. Research the idea with OpenAI again."
                ) from None
            if evidence_id in seen or end <= start:
                raise EngineError(
                    "Saved evidence research is no longer usable. Research the idea with OpenAI again."
                )
            seen.add(evidence_id)

        index = self.film_index(project["id"])
        current_source, current_signature = self._research_binding(project, index)
        has_source_binding = "source_fingerprint" in record
        has_index_binding = "semantic_index_signature" in record
        if has_source_binding and record.get("source_fingerprint") != current_source:
            raise EngineError(
                "Saved evidence research belongs to a different movie. Research the idea again."
            )
        if has_index_binding and record.get("semantic_index_signature") != current_signature:
            raise EngineError(
                "Saved evidence research belongs to an older film index. Research the idea again."
            )
        if (not has_source_binding or not has_index_binding) \
                and not self._legacy_evidence_matches(index, evidence):
            raise EngineError(
                "Saved evidence research is no longer usable. Research the idea with OpenAI again."
            )
        return board

    def research_evidence(self, project_id: str, topic: str) -> dict:
        project = self.load(project_id)
        index = self.film_index(project_id)
        binding_before = self._research_binding(project, index)
        try:
            board = research_evidence(index, topic)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc
        research_id = f"research-{uuid.uuid4().hex[:8]}"
        with self._save_lock:
            # The API call intentionally happens outside the lock. Merge its
            # result into the newest project snapshot only after it completes.
            project = self.load(project_id)
            binding_after = self._research_binding(project, index)
            if binding_after != binding_before:
                raise EngineError(
                    "The movie or semantic index changed during research. Research the idea again."
                )
            project.setdefault("evidence_researches", []).append({
                "id": research_id,
                "created_at": _now(),
                "source_fingerprint": binding_after[0],
                "semantic_index_signature": binding_after[1],
                "board": board,
            })
            self._save(project)
        return {**board, "research_id": research_id}

    def latest_evidence_research(self, project_id: str) -> dict:
        project = self.load(project_id)
        researches = project.get("evidence_researches", [])
        if not isinstance(researches, list):
            return {"available": False}
        for record in reversed(researches):
            if not isinstance(record, dict):
                continue
            research_id = record.get("id")
            board = record.get("board")
            topic = board.get("topic", "") if isinstance(board, dict) else ""
            try:
                valid_board = self._evidence_research(project, research_id, topic)
            except EngineError:
                continue
            return {"available": True, "research_id": research_id, **valid_board}
        return {"available": False}

    def analyze_evidence_visuals(self, project_id: str, research_id: str) -> dict:
        project = self.load(project_id)
        movie = project.get("movie")
        if not isinstance(movie, dict) or not movie.get("path"):
            raise EngineError("Load the local movie before analyzing visual evidence.")
        record = next(
            (item for item in reversed(project.get("evidence_researches", []))
             if isinstance(item, dict) and item.get("id") == research_id),
            None,
        )
        saved_board = record.get("board") if isinstance(record, dict) else None
        saved_topic = saved_board.get("topic", "") if isinstance(saved_board, dict) else ""
        board = self._evidence_research(project, research_id, str(saved_topic))
        binding_before = self._research_binding(project, self.film_index(project_id))
        analysis_id = f"visual-{uuid.uuid4().hex[:8]}"
        asset_dir = self.project_dir(project_id) / "visual-evidence" / research_id / analysis_id
        try:
            analysis = analyze_visual_evidence(
                Path(movie["path"]), board, asset_dir,
                movie_duration=float(movie["duration"]), analysis_id=analysis_id,
            )
        except (ValueError, TypeError, OSError) as exc:
            raise EngineError(str(exc)) from exc

        by_id = {int(item["evidence_id"]): item for item in analysis["evidence"]}
        with self._save_lock:
            project = self.load(project_id)
            index = self.film_index(project_id)
            if self._research_binding(project, index) != binding_before:
                raise EngineError(
                    "The movie or semantic index changed during visual analysis. Analyze again."
                )
            current_board = self._evidence_research(
                project, research_id, str(board.get("topic", ""))
            )
            current_ids = {int(item["id"]) for item in current_board["evidence"]}
            if set(by_id) != current_ids:
                raise EngineError(
                    "The evidence board changed during visual analysis. Analyze again."
                )
            for item in current_board["evidence"]:
                visual = by_id[int(item["id"])]
                item["visual_summary"] = visual["visual_summary"]
                item["visual_observations"] = visual["visual_observations"]
                item["visual_caution"] = visual["visual_caution"]
                item["visual_frames"] = [{
                    **frame,
                    "url": (
                        f"/api/projects/{project_id}/evidence/frame/{research_id}/"
                        f"{analysis_id}/{frame['filename']}"
                    ),
                } for frame in visual["visual_frames"]]
            current_board["visual_analysis"] = {
                key: value for key, value in analysis.items() if key != "evidence"
            }
            self._save(project)
        return {**current_board, "research_id": research_id}

    def evidence_frame_path(self, project_id: str, research_id: str,
                            analysis_id: str, filename: str) -> Path:
        self.load(project_id)
        if not re.fullmatch(r"research-[0-9a-f]{8}", research_id):
            raise EngineError("Visual evidence frame not found.")
        if not re.fullmatch(r"visual-[0-9a-f]{8}", analysis_id):
            raise EngineError("Visual evidence frame not found.")
        if not re.fullmatch(r"evidence-[0-9]+-frame-[1-3]\.jpg", filename):
            raise EngineError("Visual evidence frame not found.")
        path = (self.project_dir(project_id) / "visual-evidence" / research_id
                / analysis_id / filename)
        if not path.is_file():
            raise EngineError("Visual evidence frame not found.")
        return path

    def editorial_status(self) -> dict:
        return api_status()

    def editorial_rerank(self, project_id: str, topic: str) -> dict:
        self.load(project_id)
        try:
            return editorial_rerank(self.film_index(project_id), topic)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    def generate_editorial_concepts(self, project_id: str, topic: str,
                                     evidence_ids: list[int],
                                     research_id: str | None = None) -> dict:
        project = self.load(project_id)
        board = None
        if research_id:
            board = self._evidence_research(project, research_id, topic)
        try:
            if board is None:
                return generate_concepts(self.film_index(project_id), topic, evidence_ids)
            result = generate_concepts(self.film_index(project_id), topic, evidence_ids,
                                       evidence_board=board)
            return {**result, "research_id": research_id}
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    def create_editorial_storyboard(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        research_id = data.get("research_id")
        board = None
        if research_id:
            board = self._evidence_research(project, research_id, data.get("topic", ""))
        try:
            if board is None:
                storyboard = create_storyboard(
                    project, self.film_index(project_id), data.get("topic", ""),
                    data.get("concept", {}),
                )
            else:
                storyboard = create_storyboard(
                    project, self.film_index(project_id), data.get("topic", ""),
                    data.get("concept", {}), evidence_board=board,
                    research_id=research_id,
                )
        except (ValueError, TypeError) as exc:
            raise EngineError(str(exc)) from exc
        self._save(project)
        return {"storyboard": storyboard,
                "url": f"/projects/{project_id}/storyboards/{storyboard['id']}"}

    def get_editorial_storyboard(self, project_id: str, storyboard_id: str) -> dict:
        project = self.load(project_id)
        try:
            storyboard = find_storyboard(project, storyboard_id)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc
        clip_captions = self._editorial_preview_captions(project_id, storyboard)
        return {"storyboard": storyboard, "movie": project["movie"],
                "project_title": project["title"], "clip_captions": clip_captions}

    def _editorial_preview_captions(self, project_id: str, storyboard: dict) -> dict:
        transcript = self.film_index(project_id).raw_transcript()
        clip_captions = {}
        for card in storyboard.get("cards", []):
            if card.get("type") != "clip":
                continue
            try:
                clip_captions[card["id"]] = extract_clip_captions(
                    transcript, float(card["source_start"]), float(card["source_end"])
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise EngineError(f"Could not prepare preview captions for {card.get('id', 'clip card')}.") from exc
        return clip_captions

    def update_editorial_storyboard(self, project_id: str, storyboard_id: str,
                                    data: dict) -> dict:
        project = self.load(project_id)
        try:
            storyboard = update_storyboard(project, storyboard_id, data)
        except (ValueError, TypeError) as exc:
            raise EngineError(str(exc)) from exc
        clip_captions = self._editorial_preview_captions(project_id, storyboard)
        self._save(project)
        return {"storyboard": storyboard, "clip_captions": clip_captions}

    def refine_storyboard_clip(self, project_id: str, storyboard_id: str,
                               card_id: str) -> dict:
        if not isinstance(card_id, str) or not re.fullmatch(r"card-[0-9a-f]{8}", card_id):
            raise EngineError("Clip card not found.")
        project = self.load(project_id)
        try:
            storyboard = find_storyboard(project, storyboard_id)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc
        card = next((item for item in storyboard.get("cards", [])
                     if item.get("id") == card_id), None)
        if card is None:
            raise EngineError("Clip card not found.")
        if card.get("type") != "clip":
            raise EngineError("Only movie clip cards can be dialogue-refined.")
        movie = project.get("movie")
        if not isinstance(movie, dict) or not movie.get("path"):
            raise EngineError("The local movie file is no longer available.")
        revision_before = int(storyboard.get("revision", 1))
        try:
            refined = refine_clip_alignment(
                self.film_index(project_id), Path(movie["path"]), dict(card),
                self.project_dir(project_id) / "timing-refinement", self.root / "work",
            )
        except (ValueError, TypeError, OSError) as exc:
            raise EngineError(str(exc)) from exc

        with self._save_lock:
            project = self.load(project_id)
            try:
                storyboard = find_storyboard(project, storyboard_id)
            except ValueError as exc:
                raise EngineError(str(exc)) from exc
            if int(storyboard.get("revision", 1)) != revision_before:
                raise EngineError(
                    "The storyboard changed during timing refinement. Try the refinement again."
                )
            card = next((item for item in storyboard.get("cards", [])
                         if item.get("id") == card_id), None)
            if card is None or card.get("type") != "clip":
                raise EngineError("Clip card not found.")
            card.update(refined)
            storyboard["revision"] = revision_before + 1
            storyboard["updated_at"] = _now()
            self._save(project)
        return {
            "storyboard": storyboard,
            "clip_captions": self._editorial_preview_captions(project_id, storyboard),
            "refined_card_id": card_id,
        }

    def export_editorial_storyboard(self, project_id: str, storyboard_id: str) -> dict:
        project = self.load(project_id)
        try:
            storyboard = find_storyboard(project, storyboard_id)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc
        if not project.get("movie"):
            raise EngineError("Load a movie before exporting the editorial Reel.")
        cards = storyboard.get("cards")
        if not isinstance(cards, list) or not cards or len(cards) > 16:
            raise EngineError("The editorial storyboard must contain between 1 and 16 cards.")

        token = uuid.uuid4().hex[:8]
        work = self.project_dir(project_id) / f"editorial-render-{token}"
        work.mkdir(parents=True)
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", project["title"]).strip("-").lower()
        name = f"{safe_title}-editorial-reel-{token}.mp4"
        output = self.outputs / name
        try:
            render_details = render_editorial_storyboard(
                project, storyboard, work_dir=work, output_path=output,
                transcript_segments=self.film_index(project_id).raw_transcript(),
            )
        except EditorialRenderError as exc:
            raise EngineError(str(exc)) from exc
        if not isinstance(render_details, dict):
            raise EngineError("The editorial renderer returned invalid export details.")
        if not output.is_file():
            raise EngineError("The editorial renderer did not produce a Reel file.")

        record = {
            **render_details,
            "type": "editorial_storyboard",
            "filename": name,
            "path": str(output),
            "storyboard_id": storyboard["id"],
            "created_at": _now(),
        }
        project.setdefault("exports", []).append(record)
        storyboard["latest_export"] = record
        self._save(project)
        return record

    def get_conversion_reel(self, project_id: str) -> dict:
        project = self.load(project_id)
        if not project.get("movie"):
            raise EngineError("Load a movie before using Conversion Mode.")
        config = project.get("conversion_reel")
        if not isinstance(config, dict):
            config = default_conversion_config(project)
        return {"config": config, "project_title": project["title"],
                "movie": project["movie"]}

    def save_conversion_reel(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        if not project.get("movie"):
            raise EngineError("Load a movie before using Conversion Mode.")
        try:
            config = normalize_conversion_config(project, data)
        except ConversionRenderError as exc:
            raise EngineError(str(exc)) from exc
        previous = project.get("conversion_reel")
        if isinstance(previous, dict) and previous.get("latest_export"):
            config["latest_export"] = previous["latest_export"]
        project["conversion_reel"] = config
        self._save(project)
        return {"config": config}

    def export_conversion_reel(self, project_id: str) -> dict:
        project = self.load(project_id)
        if not project.get("movie"):
            raise EngineError("Load a movie before exporting Conversion Mode.")
        raw = project.get("conversion_reel")
        if not isinstance(raw, dict):
            raw = default_conversion_config(project)
        try:
            config = normalize_conversion_config(project, raw)
        except ConversionRenderError as exc:
            raise EngineError(str(exc)) from exc
        token = uuid.uuid4().hex[:8]
        work = self.project_dir(project_id) / f"conversion-render-{token}"
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", project["title"]).strip("-").lower()
        name = f"{safe_title}-conversion-reel-{token}.mp4"
        output = self.outputs / name
        try:
            details = render_conversion_reel(
                project, config, work, output, self.root / "assets" / "ffs-brand"
            )
        except ConversionRenderError as exc:
            raise EngineError(str(exc)) from exc
        if not output.is_file():
            raise EngineError("Conversion Mode did not produce a Reel file.")
        record = {
            **details, "type": "conversion_overlay", "filename": name,
            "path": str(output), "created_at": _now(),
        }
        project.setdefault("exports", []).append(record)
        config["latest_export"] = record
        project["conversion_reel"] = config
        self._save(project)
        return record

    def review_scene(self, project_id: str, scene_id: int, data: dict) -> dict:
        self.load(project_id)
        try:
            return self.film_index(project_id).update_scene_review(
                scene_id, status=data.get("status"), title=data.get("title")
            )
        except ValueError as exc:
            raise EngineError(str(exc)) from exc

    def get_mood_montage(self, project_id: str) -> dict:
        project = self.load(project_id)
        visual = project.get("visual_montage_index")
        return {
            "project": {
                "id": project["id"], "title": project["title"],
                "movie": project.get("movie"), "shot_index": project.get("shot_index"),
            },
            "shots": project.get("candidates", []),
            "draft": project.get("mood_montage_draft"),
            "mood_styles": [{"id": key, **value} for key, value in MOOD_RECIPES.items()],
            "visual_index": ({key: visual.get(key) for key in (
                "status", "created_at", "sample_count", "visual_model", "embedding_model"
            )} if isinstance(visual, dict) else {"status": "not_built"}),
        }

    def build_visual_montage_index(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        movie = project.get("movie")
        if not isinstance(movie, dict) or not movie.get("path"):
            raise EngineError("Load a local movie before building its visual index.")
        index = self.film_index(project_id)
        binding_before = self._source_fingerprint(project, index)
        token = (binding_before or "movie")[:16]
        try:
            sample_count = min(120, max(24, int(data.get("sample_count", 72))))
            destination = (self.project_dir(project_id) / "visual-montage" / token
                           / f"samples-{sample_count}")
            visual = build_visual_montage_index(
                Path(movie["path"]), destination, duration=float(movie["duration"]),
                source_fingerprint=binding_before,
                sample_count=sample_count,
            )
        except (ValueError, TypeError, OSError) as exc:
            raise EngineError(str(exc)) from exc
        with self._save_lock:
            project = self.load(project_id)
            if self._source_fingerprint(project, self.film_index(project_id)) != binding_before:
                raise EngineError("The linked movie changed during visual indexing. Build it again.")
            project["visual_montage_index"] = visual
            self._save(project)
        return {key: visual[key] for key in (
            "status", "created_at", "sample_count", "visual_model", "embedding_model"
        )}

    def _materialize_runtime_balanced_shots(self, project: dict, count: int) -> None:
        """Add thumbnail candidates selected from every indexed cut, not the legacy 48."""
        index_shots = self.film_index(project["id"]).shots()
        if not index_shots or not isinstance(project.get("movie"), dict):
            return
        movie_duration = float(project["movie"].get("duration", 0))
        if movie_duration <= 0:
            return
        eligible = [shot for shot in index_shots if float(shot.get("duration", 0)) >= 1.0]
        if len(eligible) < count:
            eligible = index_shots
        selected = []
        for bucket in range(min(count, len(eligible))):
            target = movie_duration * (bucket + 0.5) / count
            containing = [shot for shot in eligible
                          if float(shot["start"]) <= target < float(shot["end"])]
            shot = containing[0] if containing else min(eligible, key=lambda item: abs(
                (float(item["start"]) + float(item["end"])) / 2 - target
            ))
            shot_start = float(shot["start"])
            shot_end = float(shot["end"])
            sample_start = min(max(shot_start, target - 1.4), max(shot_start, shot_end - 0.7))
            selected.append({**shot, "sample_start": sample_start})

        candidates = project.setdefault("candidates", [])
        existing = {str(item.get("id")) for item in candidates if isinstance(item, dict)}
        thumb_dir = self.project_dir(project["id"]) / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        for shot in selected:
            sample_start = float(shot["sample_start"])
            sample_token = max(0, round(sample_start * 1000))
            candidate_id = f"runtime-shot-{sample_token:010d}"
            if candidate_id in existing:
                continue
            filename = f"runtime-{sample_token:010d}.jpg"
            destination = thumb_dir / filename
            if not destination.is_file():
                result = subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{sample_start + 0.35:.3f}",
                    "-i", project["movie"]["path"], "-frames:v", "1",
                    "-vf", "scale=360:-2", "-q:v", "3", "-y", str(destination),
                ], capture_output=True, text=True)
                if result.returncode:
                    continue
            source_end = min(float(shot["end"]), sample_start + 5.0)
            duration = source_end - sample_start
            candidates.append({
                "id": candidate_id,
                "start": round(sample_start, 3),
                "duration": round(min(2.8, max(0.6, duration - 0.1)), 3),
                "thumbnail": filename,
                "shot_end": round(source_end, 3),
                "shot_duration": round(duration, 3),
                "source": "runtime_balanced_sample",
            })
            existing.add(candidate_id)

    def build_balanced_mood_montage(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        try:
            requested_count = int(data.get("clip_count", 10))
            self._materialize_runtime_balanced_shots(project, requested_count)
            draft = balanced_mood_draft(
                project,
                clip_count=requested_count,
                target_duration=data.get("target_duration", 28),
                label=data.get("label", "Mood Montage"),
            )
        except (ValueError, TypeError) as exc:
            raise EngineError(str(exc)) from exc
        current = project.get("mood_montage_draft")
        if isinstance(current, dict):
            draft["revision"] = int(current.get("revision", 1)) + 1
        project["mood_montage_draft"] = draft
        self._save(project)
        return {"draft": draft}

    def _materialize_mood_shots(self, project: dict, moments: list[dict],
                                *, per_clip: float, mood_name: str) -> list[dict]:
        """Turn transcript-matched passages into editable shot-level candidates."""
        index_shots = self.film_index(project["id"]).shots()
        if not index_shots or not isinstance(project.get("movie"), dict):
            raise EngineError("Detect movie shots before building a mood-aware montage.")
        candidates = project.setdefault("candidates", [])
        by_id = {str(item.get("id")): item for item in candidates if isinstance(item, dict)}
        thumb_dir = self.project_dir(project["id"]) / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for moment in moments:
            evidence_start = float(moment["evidence_start"])
            evidence_end = float(moment["evidence_end"])
            target = (evidence_start + evidence_end) / 2
            overlaps = [shot for shot in index_shots
                        if float(shot["start"]) < evidence_end and float(shot["end"]) > evidence_start
                        and float(shot.get("duration", 0)) >= 0.7]
            options = overlaps or index_shots
            normal = [shot for shot in options if 1.0 <= float(shot.get("duration", 0)) <= 12.0]
            if normal:
                options = normal
            shot = min(options, key=lambda item: abs(
                (float(item["start"]) + float(item["end"])) / 2 - target
            ))
            shot_start, shot_end = float(shot["start"]), float(shot["end"])
            desired = min(5.0, max(0.6, per_clip))
            if shot_end - shot_start <= 12:
                sample_start = max(shot_start, min(target - desired / 2, shot_end - 0.6))
            else:
                # Old threshold-based indexes may contain a very long false "shot".
                # Sample around the matched passage instead of jumping to its beginning.
                sample_start = min(max(shot_start, target - desired / 2), shot_end - 0.6)
            sample_start = max(0.0, sample_start)
            source_end = min(shot_end, sample_start + 5.0)
            available = source_end - sample_start
            if available < 0.6:
                continue
            token = max(0, round(sample_start * 1000))
            candidate_id = f"runtime-shot-{token:010d}"
            filename = f"runtime-{token:010d}.jpg"
            destination = thumb_dir / filename
            if not destination.is_file():
                result = subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{min(source_end - 0.05, sample_start + 0.35):.3f}",
                    "-i", project["movie"]["path"], "-frames:v", "1",
                    "-vf", "scale=360:-2", "-q:v", "3", "-y", str(destination),
                ], capture_output=True, text=True)
                if result.returncode:
                    continue
            score = round(float(moment.get("mood_score", 0)), 4)
            visual_sample_id = int(moment.get("sample_id", moment.get("id", -1)))
            excerpt = " ".join(str(moment.get("excerpt", "")).split()).strip()[:500]
            candidate = by_id.get(candidate_id)
            mood_fields = {
                "selection_reason": (
                    f"{mood_name} visual match · "
                    f"{max(0, min(100, round(score * 100)))}% catalog similarity"
                ),
                "mood_excerpt": excerpt,
                "mood_score": score,
                "visual_sample_id": visual_sample_id,
                "source": "visual_mood_match",
            }
            if candidate is None:
                candidate = {
                    "id": candidate_id, "start": round(sample_start, 3),
                    "duration": round(min(desired, available), 3),
                    "thumbnail": filename, "shot_end": round(source_end, 3),
                    "shot_duration": round(available, 3), **mood_fields,
                }
                candidates.append(candidate)
                by_id[candidate_id] = candidate
            else:
                candidate.update(mood_fields)
            created.append(candidate)
        return created

    def _materialize_targeted_mood_shots(self, project: dict, moments: list[dict], *,
                                         per_clip: float, mood_name: str,
                                         index_id: str, asset_dir: Path) -> list[dict]:
        """Create candidates directly from mood-specific cut boundaries."""
        candidates = project.setdefault("candidates", [])
        by_id = {str(item.get("id")): item for item in candidates if isinstance(item, dict)}
        thumb_dir = self.project_dir(project["id"]) / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for moment in moments:
            start, end = float(moment["shot_start"]), float(moment["shot_end"])
            if end - start < 0.6:
                continue
            desired = min(5.0, max(0.6, per_clip))
            sample_start = min(max(start, float(moment["timestamp"]) - desired / 2), end - 0.6)
            sample_id = int(moment["sample_id"])
            candidate_id = f"mood-shot-{index_id}-{sample_id:04d}"
            filename = f"mood-{index_id}-{sample_id:04d}.jpg"
            destination = thumb_dir / filename
            source = asset_dir / str(moment["filename"])
            if not destination.is_file():
                if not source.is_file():
                    continue
                shutil.copyfile(source, destination)
            score = round(float(moment.get("mood_score", moment.get("score", 0))), 4)
            mood_fields = {
                "selection_reason": (
                    f"{mood_name} dense visual match · "
                    f"{max(0, min(100, round(score * 100)))}% catalog similarity"
                ),
                "mood_excerpt": " ".join(str(moment.get("summary", "")).split())[:500],
                "mood_score": score, "visual_sample_id": sample_id,
                "source": "targeted_visual_shot",
            }
            candidate = by_id.get(candidate_id)
            if candidate is None:
                candidate = {
                    "id": candidate_id, "start": round(sample_start, 3),
                    "duration": round(min(desired, end - sample_start), 3),
                    "thumbnail": filename, "shot_end": round(end, 3),
                    "shot_duration": round(end - sample_start, 3),
                    "detected_shot_start": round(start, 3), **mood_fields,
                }
                candidates.append(candidate)
                by_id[candidate_id] = candidate
            else:
                candidate.update(mood_fields)
            created.append(candidate)
        return created

    def _targeted_mood_index(self, project: dict, recipe: dict,
                             overview_searches: list[list[dict]]) -> tuple[dict, bool]:
        movie = project["movie"]
        duration = float(movie["duration"])
        fingerprint = self._source_fingerprint(project, self.film_index(project["id"]))
        prompt = " | ".join(recipe["queries"])
        digest = hashlib.sha256(
            f"{fingerprint}\0{recipe['id']}\0{prompt}".encode("utf-8")
        ).hexdigest()[:8]
        saved = project.get("mood_visual_indexes", {}).get(digest)
        if (isinstance(saved, dict) and saved.get("status") == "complete"
                and saved.get("source_fingerprint") == fingerprint):
            return saved, True
        anchor_count = 8
        anchors = choose_diverse_mood_moments(
            overview_searches, clip_count=anchor_count, movie_duration=duration
        )
        if len(anchors) < 3:
            raise ValueError("The overview could not find enough regions for a dense mood scan.")
        overview_count = max(24, int(project["visual_montage_index"].get("sample_count", 72)))
        radius = duration / overview_count * 0.55
        regions = [{
            "start": max(0.0, (item["evidence_start"] + item["evidence_end"]) / 2 - radius),
            "end": min(duration, (item["evidence_start"] + item["evidence_end"]) / 2 + radius),
        } for item in anchors]
        token = (fingerprint or "movie")[:16]
        destination = (self.project_dir(project["id"]) / "visual-montage" / token
                       / f"targeted-{digest}")
        targeted = build_targeted_mood_index(
            Path(movie["path"]), destination, duration=duration,
            source_fingerprint=fingerprint, regions=regions, prompt=prompt, max_shots=96,
        )
        targeted.update({
            "id": digest, "mood_style": recipe["id"], "mood_prompt": recipe["prompt"],
            "asset_dir": str(destination),
        })
        project.setdefault("mood_visual_indexes", {})[digest] = targeted
        return targeted, False

    def build_mood_aware_montage(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        try:
            requested_count = min(12, max(6, int(data.get("clip_count", 10))))
            target_duration = min(36.0, max(20.0, float(data.get("target_duration", 28))))
            recipe = mood_recipe(data.get("mood_style", "romantic"), data.get("mood_prompt", ""))
            if recipe["id"] == "balanced":
                return self.build_balanced_mood_montage(project_id, data)
            visual_index = project.get("visual_montage_index")
            current_fingerprint = self._source_fingerprint(project, self.film_index(project_id))
            if (not isinstance(visual_index, dict)
                    or visual_index.get("source_fingerprint") != current_fingerprint):
                raise ValueError(
                    "Build the visual movie index before using a visual Mood Style."
                )
            searches = [apply_visual_style_bias(
                search_visual_montage(visual_index, query, limit=36), recipe["id"]
            ) for query in recipe["queries"]]
            targeted_index, index_reused = self._targeted_mood_index(
                project, recipe, searches
            )
            searches = [apply_visual_style_bias(
                search_visual_montage(targeted_index, query, limit=48), recipe["id"]
            ) for query in recipe["queries"]]
            moments = choose_diverse_mood_moments(
                searches, clip_count=min(16, requested_count + 4),
                movie_duration=float(project.get("movie", {}).get("duration", 0)),
            )
            if len(moments) < 3:
                raise ValueError("The local film index could not find enough distinct mood matches.")
            candidates = self._materialize_targeted_mood_shots(
                project, moments, per_clip=target_duration / len(moments),
                mood_name=recipe["name"], index_id=targeted_index["id"],
                asset_dir=Path(targeted_index["asset_dir"]),
            )
            if len(candidates) < 3:
                raise ValueError("Could not turn enough mood matches into usable movie shots.")
            if len(candidates) > requested_count:
                candidates = sorted(
                    candidates, key=lambda item: float(item.get("mood_score", 0)), reverse=True
                )[:requested_count]
                candidates.sort(key=lambda item: float(item["start"]))
            clips = [{
                **candidate, "duration": min(5.0, target_duration / len(candidates)),
                "framing": "cinematic", "crop_x": 0.5,
                "original_audio": recipe["id"] == "dialogue",
            } for candidate in candidates]
            draft = validate_mood_draft(project, {
                "label": data.get("label") or f"{project['title']} · {recipe['name']}",
                "clips": clips, "mood_style": recipe["id"],
                "mood_prompt": recipe["prompt"], "selection_method": "targeted_visual_index",
                "mood_index_id": targeted_index["id"],
                "opening_card": False, "opening_text": project.get("title", ""),
                "end_card": True, "end_text": "FILM LIVES HERE",
            })
        except (ValueError, TypeError) as exc:
            raise EngineError(str(exc)) from exc
        current = project.get("mood_montage_draft")
        if isinstance(current, dict):
            draft["revision"] = int(current.get("revision", 1)) + 1
        project["mood_montage_draft"] = draft
        self._save(project)
        return {
            "draft": draft,
            "selection": {
                "method": "targeted_visual_index", "mood": recipe["name"],
                "queries": recipe["queries"], "matches": len(candidates),
                "index_reused": index_reused,
                "dense_samples": targeted_index["sample_count"],
                "regions": len(targeted_index["regions"]),
                "privacy": (
                    "The overview routed the search. Representative frames from the targeted "
                    "regions were sent to OpenAI once; this mood index is now cached locally."
                ),
            },
        }

    def save_mood_montage(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        current = project.get("mood_montage_draft")
        current_revision = int(current.get("revision", 1)) if isinstance(current, dict) else None
        try:
            draft = validate_mood_draft(
                project, data, current_revision=current_revision
            )
        except (ValueError, TypeError) as exc:
            raise EngineError(str(exc)) from exc
        if isinstance(current, dict) and current.get("latest_export"):
            draft["latest_export"] = current["latest_export"]
        project["mood_montage_draft"] = draft
        self._save(project)
        return {"draft": draft}

    def export_montage(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        saved_draft = project.get("mood_montage_draft")
        use_saved = bool(data.get("use_saved_draft")) and isinstance(saved_draft, dict)
        source = saved_draft if use_saved else data
        raw_clips = source.get("clips", [])
        if not isinstance(raw_clips, list) or not raw_clips:
            raise EngineError("Select at least one shot for the montage.")
        clips = raw_clips[:16]
        work = self.project_dir(project_id) / f"render-{uuid.uuid4().hex[:8]}"
        work.mkdir(parents=True)
        crop_x = min(1.0, max(0.0, float(source.get("crop_x", 0.5))))
        framing = str(source.get("framing", "cinematic"))
        original_audio = bool(source.get("original_audio", False))
        movie_audio_gain = min(2.0, max(0.0, float(source.get("movie_audio_gain", 1.0))))
        segments = []
        durations = []
        segment_number = 0
        if bool(source.get("opening_card", False)):
            segment = work / f"segment-{segment_number:03d}.mp4"
            try:
                duration = _render_text_card(
                    project, {
                        "type": "hook", "duration": 2.0,
                        "text": source.get("opening_text") or project["title"],
                    }, segment, work, segment_number + 1,
                )
            except EditorialRenderError as exc:
                raise EngineError(str(exc)) from exc
            segments.append(segment)
            durations.append(duration)
            segment_number += 1
        for index, raw in enumerate(clips):
            start = max(0.0, float(raw.get("start", 0)))
            duration = min(5.0, max(0.6, float(raw.get("duration", 2.2))))
            clip_crop_x = min(1.0, max(0.0, float(raw.get("crop_x", crop_x))))
            clip_framing = str(raw.get("framing", framing))
            clip_audio = bool(raw.get("original_audio", original_audio))
            segment = work / f"segment-{segment_number:03d}.mp4"
            if clip_framing == "crop":
                vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
                      f"crop=1080:1920:x=(in_w-out_w)*{clip_crop_x:.4f}:y=(in_h-out_h)/2,"
                      "setsar=1,eq=contrast=1.02:saturation=.96,format=yuv420p")
            else:
                vf = ("split=2[bg][fg];"
                      "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                      "crop=1080:1920,boxblur=28:5,hue=s=.35,"
                      "eq=brightness=-.18:contrast=.92[back];"
                      "[fg]scale=1080:-2:flags=lanczos,setsar=1,"
                      "eq=contrast=1.02:saturation=.96[front];"
                      "[back][front]overlay=(W-w)/2:(H-h)/2,format=yuv420p")
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
                       "-i", project["movie"]["path"]]
            if not clip_audio:
                command.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
            command.extend(["-t", f"{duration:.3f}", "-vf", vf])
            if clip_audio:
                command.extend(["-af", f"volume={movie_audio_gain:.3f}"])
            command.extend(["-map", "0:v:0", "-map",
                            "0:a:0" if clip_audio else "1:a:0", "-r", "30", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k",
                            "-ar", "48000", "-ac", "2", "-shortest", "-y", str(segment)])
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise EngineError(f"Could not render montage shot {index + 1}.")
            segments.append(segment)
            durations.append(duration)
            segment_number += 1
        if bool(source.get("end_card", False)):
            segment = work / f"segment-{segment_number:03d}.mp4"
            try:
                duration = _render_text_card(
                    project, {
                        "type": "end_card", "duration": 2.6,
                        "text": source.get("end_text") or "FILM LIVES HERE",
                    }, segment, work, segment_number + 1,
                )
            except EditorialRenderError as exc:
                raise EngineError(str(exc)) from exc
            segments.append(segment)
            durations.append(duration)
        concat = work / "concat.txt"
        concat.write_text("".join(f"file '{path}'\n" for path in segments))
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", project["title"]).strip("-").lower()
        name = f"{safe_title}-mood-montage-{uuid.uuid4().hex[:8]}.mp4"
        output = self.outputs / name
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "concat",
                                 "-safe", "0", "-i", str(concat), "-c", "copy",
                                 "-movflags", "+faststart", "-y", str(output)], capture_output=True, text=True)
        if result.returncode:
            raise EngineError("Could not assemble the montage.")
        record = {"filename": name, "path": str(output), "created_at": _now(),
                  "duration": round(sum(durations), 3),
                  "clip_count": len(clips),
                  "opening_card": bool(source.get("opening_card", False)),
                  "end_card": bool(source.get("end_card", False)),
                  "original_audio": any(bool(c.get("original_audio", original_audio)) for c in clips),
                  "movie_audio_gain": movie_audio_gain}
        project["exports"].append(record)
        if use_saved and isinstance(project.get("mood_montage_draft"), dict):
            project["mood_montage_draft"]["latest_export"] = record
        self._save(project)
        return record

    def ingest(self, project_id: str, movie_value: str, subtitle_value: str) -> dict:
        movie = Path(movie_value).expanduser().resolve()
        if not movie.is_file():
            raise EngineError("Choose an existing local movie file.")
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of", "json", str(movie),
        ], capture_output=True, text=True)
        if probe.returncode:
            raise EngineError("FFprobe could not read the movie file.")
        info = json.loads(probe.stdout)
        video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
        if not video:
            raise EngineError("The selected file has no video stream.")
        project = self.load(project_id)
        project["movie"] = {
            "path": str(movie), "filename": movie.name,
            "duration": float(info["format"]["duration"]),
            "width": video.get("width"), "height": video.get("height"),
            "codec": video.get("codec_name"), "fps": video.get("r_frame_rate"),
        }
        subtitle_value = str(subtitle_value or "").strip()
        if subtitle_value:
            subtitles = Path(subtitle_value).expanduser().resolve()
            if not subtitles.is_file() or subtitles.suffix.lower() != ".srt":
                raise EngineError("The optional subtitle path must point to an existing .srt file.")
            project["subtitle_path"] = str(subtitles)
            project["transcript"] = parse_srt(subtitles)
            project["transcription"] = {"method": "imported_srt", "status": "complete"}
        else:
            project_dir = self._file(project_id).parent
            audio = project_dir / "transcription-audio.wav"
            extracted = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(movie),
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(audio),
            ], capture_output=True, text=True)
            if extracted.returncode:
                raise EngineError("Could not extract audio for transcription.")
            # Apple Silicon uses MLX by default. Codex/headless environments can
            # opt into the slower CPU fallback with FFS_TRANSCRIBER=cpu.
            use_mlx = platform.machine() == "arm64" and os.environ.get("FFS_TRANSCRIBER") != "cpu"
            project["transcription"] = {"method": "mlx_whisper" if use_mlx else "whisper_cpu",
                                        "status": "running", "model": "small" if use_mlx else "base"}
            self._save(project)
            try:
                if use_mlx:
                    import mlx_whisper
                    result = mlx_whisper.transcribe(
                        str(audio), path_or_hf_repo="mlx-community/whisper-small-mlx",
                        language="en", word_timestamps=True,
                    )
                else:
                    import whisper
                    import torch
                    torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
                    model_dir = self.root / "work" / "models"
                    model_dir.mkdir(parents=True, exist_ok=True)
                    model = whisper.load_model("base", device="cpu", download_root=str(model_dir))
                    result = model.transcribe(str(audio), language="en", fp16=False, word_timestamps=True)
            except Exception as exc:
                raise EngineError(f"Automatic transcription failed: {exc}") from exc
            project["transcript"] = [
                {"start": round(float(segment["start"]), 3),
                 "end": round(float(segment["end"]), 3),
                 "text": str(segment.get("text", "")).strip()}
                for segment in result.get("segments", []) if str(segment.get("text", "")).strip()
            ]
            if not project["transcript"]:
                raise EngineError("The transcription engine did not detect any dialogue.")
            project["transcription"]["status"] = "complete"
            project["transcription"]["segment_count"] = len(project["transcript"])
        project["candidates"] = []
        return self._save(project)

    def generate_candidates(self, project_id: str) -> dict:
        project = self.load(project_id)
        cues = project.get("transcript", [])
        if not cues:
            raise EngineError("Ingest and transcribe a movie first.")
        windows = []
        for start_index in range(len(cues)):
            start = max(0.0, cues[start_index]["start"] - 0.35)
            end_index = start_index
            while end_index + 1 < len(cues) and cues[end_index]["end"] - start < 34:
                end_index += 1
                if cues[end_index]["end"] - start >= 22:
                    break
            end = min(project["movie"]["duration"], cues[end_index]["end"] + 0.45)
            duration = end - start
            if 18 <= duration <= 40:
                selected = cues[start_index : end_index + 1]
                words = sum(len(c["text"].split()) for c in selected)
                questions = sum(c["text"].count("?") for c in selected)
                score = words + questions * 10 + len(selected) * 2
                windows.append((score, start, end, selected))
        windows.sort(reverse=True, key=lambda row: row[0])
        chosen = []
        for score, start, end, selected in windows:
            if any(abs(start - item["in"]) < 90 for item in chosen):
                continue
            text = " ".join(c["text"] for c in selected)
            chosen.append({
                "id": f"candidate-{uuid.uuid4().hex[:8]}", "in": round(start, 3),
                "out": round(end, 3), "duration": round(end - start, 3),
                "title": text[:74] + ("…" if len(text) > 74 else ""),
                "transcript": selected, "score": score,
            })
            if len(chosen) == 3:
                break
        project["candidates"] = chosen
        self._save(project)
        return {"candidates": chosen}

    def export(self, project_id: str, data: dict) -> dict:
        project = self.load(project_id)
        if not project.get("movie"):
            raise EngineError("Ingest a movie first.")
        start = max(0.0, float(data.get("in", 0)))
        end = min(project["movie"]["duration"], float(data.get("out", start + 25)))
        if end - start < 3 or end - start > 60:
            raise EngineError("The selected scene must be between 3 and 60 seconds.")
        crop_x = min(1.0, max(0.0, float(data.get("crop_x", 0.5))))
        include_end = bool(data.get("end_card", True))
        event_date = str(data.get("event_date", "AUGUST 27, 2026"))[:80]
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", project["title"]).strip("-").lower()
        name = f"{safe_title}-{uuid.uuid4().hex[:8]}.mp4"
        output = self.outputs / name
        duration = end - start
        caption_file = self.projects / project_id / "scene-captions.srt"
        caption_blocks = []
        for cue in project.get("transcript", []):
            cue_start = max(start, float(cue["start"]))
            cue_end = min(end, float(cue["end"]))
            if cue_end <= cue_start:
                continue
            caption_blocks.append(
                f"{len(caption_blocks) + 1}\n{_srt_time(cue_start - start)} --> "
                f"{_srt_time(cue_end - start)}\n{cue['text']}\n"
            )
        caption_file.write_text("\n".join(caption_blocks), encoding="utf-8")
        subtitle_path = str(caption_file).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:x=(in_w-out_w)*{crop_x:.4f}:y=(in_h-out_h)/2,"
            "setsar=1,eq=contrast=1.02:saturation=.96,"
            f"subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=18,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,"
            "Outline=2,Shadow=0,MarginV=150,Alignment=2',format=yuv420p"
        )
        segment = self.projects / project_id / "scene.mp4"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
                   "-i", project["movie"]["path"], "-t", f"{duration:.3f}", "-vf", vf,
                   "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                   "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-y", str(segment)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise EngineError("Scene render failed: " + result.stderr.splitlines()[-1])
        if include_end:
            card = self.projects / project_id / "end-card.mp4"
            title = project["title"].upper().replace("'", "’").replace(":", "\\:")
            date = event_date.replace("'", "’").replace(":", "\\:")
            card_filter = (
                "drawbox=x=0:y=0:w=1080:h=1920:color=#F2EFE5:t=fill,"
                "drawbox=x=80:y=180:w=18:h=280:color=#C62828:t=fill,"
                "drawtext=fontfile='/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf':"
                "text='FRESNO FILM SOCIETY':fontcolor=#111111:fontsize=48:x=125:y=200,"
                f"drawtext=fontfile='/System/Library/Fonts/NewYork.ttf':text='{title}':"
                "fontcolor=#111111:fontsize=82:x=(w-text_w)/2:y=760,"
                f"drawtext=fontfile='/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf':text='{date}':"
                "fontcolor=#4A6070:fontsize=52:x=(w-text_w)/2:y=1020,format=yuv420p"
            )
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=#F2EFE5:s=1080x1920:r=30:d=2.8", "-f", "lavfi", "-i",
                            "anullsrc=r=48000:cl=stereo", "-vf", card_filter, "-t", "2.8",
                            "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-y", str(card)], check=True)
            concat = self.projects / project_id / "concat.txt"
            concat.write_text(f"file '{segment}'\nfile '{card}'\n")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                            "-i", str(concat), "-c", "copy", "-movflags", "+faststart", "-y", str(output)], check=True)
        else:
            segment.replace(output)
        record = {"filename": name, "path": str(output), "created_at": _now(), "in": start, "out": end}
        project["exports"].append(record)
        self._save(project)
        return record
