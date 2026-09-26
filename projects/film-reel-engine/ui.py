#!/usr/bin/env python3
"""Local browser interface for the three Film Reel Engine commands."""
from __future__ import annotations

import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
import yaml


ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
JOB = {"running": False, "action": None, "exit_code": None, "logs": [], "started_at": None}
ANALYSIS_FIELDS = {
    "cut_threshold": (float, 0.05, 0.90),
    "minimum_shot_seconds": (float, 0.1, 10),
    "continuous_segment_seconds": (float, 2, 60),
    "sample_fps": (float, 0.25, 8),
    "max_samples_per_shot": (int, 3, 120),
    "workers": (int, 1, 4),
    "face_weight": (float, 0, 1),
}
RANKING_FIELDS = {
    "visual_interest": (float, 0, 3),
    "composition": (float, 0, 3),
    "motion": (float, 0, 3),
    "faces": (float, 0, 3),
    "diversity": (float, 0, 4),
}


def json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def active_project() -> Path | None:
    name = json_file(PROJECTS / ".active.json").get("project")
    if not isinstance(name, str) or Path(name).name != name:
        return None
    path = PROJECTS / name
    return path if (path / "analysis/film.json").is_file() else None


def analysis_settings(project: Path) -> dict:
    base = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    values = {name: base["reframing" if name == "face_weight" else "analysis"][name]
              for name in ANALYSIS_FIELDS}
    values.update({name: value for name, value in json_file(project / "analysis/ui_settings.json").items()
                   if name in ANALYSIS_FIELDS})
    return values


def ranking_settings(project: Path) -> dict:
    base = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))["ranking"]
    values = {name: base[name] for name in RANKING_FIELDS}
    values.update({name: value for name, value in json_file(project / "analysis/ui_ranking.json").items()
                   if name in RANKING_FIELDS})
    return values


def validated_settings(data: dict, fields: dict = ANALYSIS_FIELDS) -> dict:
    values = {}
    for name, (kind, minimum, maximum) in fields.items():
        raw = data.get(name)
        try:
            value = kind(raw)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"Enter a valid {name.replace('_', ' ')}") from None
        if kind is int and (isinstance(raw, bool) or str(raw).strip() != str(value)):
            raise ValueError(f"{name.replace('_', ' ')} must be a whole number")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"{name.replace('_', ' ')} must be between {minimum} and {maximum}")
        values[name] = value
    if fields is ANALYSIS_FIELDS and values["minimum_shot_seconds"] >= values["continuous_segment_seconds"]:
        raise ValueError("Continuous segment length must exceed minimum shot length")
    return values


def project_config(project: Path, settings: dict | None = None, ranking: dict | None = None) -> Path:
    if settings is not None:
        path = project / "analysis/ui_settings.json"
        temp = path.with_suffix(".partial.json")
        temp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    if ranking is not None:
        path = project / "analysis/ui_ranking.json"
        temp = path.with_suffix(".partial.json")
        temp.write_text(json.dumps(ranking, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    values = analysis_settings(project)
    cfg = copy.deepcopy(yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")))
    for name, value in values.items():
        cfg["reframing" if name == "face_weight" else "analysis"][name] = value
    cfg["ranking"].update(ranking_settings(project))
    path = project / "analysis/ui_config.yaml"
    temp = path.with_suffix(".partial.yaml")
    temp.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    temp.replace(path)
    return path


def project_details(path: Path) -> dict:
    film = json_file(path / "analysis/film.json")
    shots_path = path / "analysis/shots.json"
    settings_path = path / "analysis/ui_settings.json"
    exports = []
    for video in sorted((path / "exports").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        exports.append({"name": video.name, "size": video.stat().st_size})
    return {
        "id": path.name,
        "source": film.get("source", ""),
        "duration": film.get("duration", 0),
        "shots": len(json_file(shots_path).get("shots", [])) if shots_path.exists() else None,
        "analysis_current": shots_path.exists() and (not settings_path.exists() or
                          shots_path.stat().st_mtime_ns >= settings_path.stat().st_mtime_ns),
        "has_audio": bool(film.get("audio_streams")),
        "analysis_settings": analysis_settings(path),
        "ranking_settings": ranking_settings(path),
        "exports": exports,
    }


def status() -> dict:
    current = active_project()
    options = [project_details(p) for p in PROJECTS.iterdir()
               if p.is_dir() and (p / "analysis/film.json").is_file()] if PROJECTS.exists() else []
    options.sort(key=lambda p: Path(p["source"]).name.lower())
    with LOCK:
        job = {**JOB, "logs": JOB["logs"][-80:].copy()}
    return {"active": project_details(current) if current else None, "projects": options, "job": job}


def run_job(action: str, args: list[str]) -> None:
    command = [sys.executable, "-u", str(ROOT / "reel.py"), *args]
    try:
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
            assert process.stdout is not None
            for line in process.stdout:
                with LOCK:
                    JOB["logs"].append(line.rstrip())
                    JOB["logs"] = JOB["logs"][-200:]
            code = process.wait()
    except OSError as exc:
        code = 1
        with LOCK:
            JOB["logs"].append(f"[ERROR] {exc}")
    with LOCK:
        JOB["exit_code"] = code
        JOB["running"] = False


class Handler(BaseHTTPRequestHandler):
    server_version = "FilmReelUI/1.0"

    def log_message(self, format: str, *args: object) -> None:
        if not self.path.startswith(("/api/status", "/media/")):
            super().log_message(format, *args)

    def reply(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/":
            data = (ROOT / "ui/index.html").read_text(encoding="utf-8").replace("__LOCAL_TOKEN__", TOKEN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/status":
            self.reply(200, status())
            return
        if self.path.startswith("/media/"):
            self.media()
            return
        self.reply(404, {"error": "Not found"})

    def media(self) -> None:
        from urllib.parse import parse_qs, urlsplit, unquote
        url = urlsplit(self.path)
        if parse_qs(url.query).get("token", [""])[0] != TOKEN:
            self.reply(403, {"error": "Forbidden"})
            return
        parts = [unquote(p) for p in url.path.split("/")[2:]]
        if len(parts) != 2 or any(Path(p).name != p for p in parts) or not parts[1].endswith(".mp4"):
            self.reply(404, {"error": "Not found"})
            return
        file = PROJECTS / parts[0] / "exports" / parts[1]
        if not file.is_file():
            self.reply(404, {"error": "Not found"})
            return
        size = file.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get("Range", "")
        if requested:
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", requested)
            if not match:
                self.reply(416, {"error": "Invalid range"})
                return
            start = int(match.group(1))
            end = min(size - 1, int(match.group(2))) if match.group(2) else size - 1
            if start > end or start >= size:
                self.reply(416, {"error": "Invalid range"})
                return
        self.send_response(206 if requested else 200)
        self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "video/mp4")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "private, no-store")
        if requested:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with file.open("rb") as source:
                source.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self) -> None:
        if self.headers.get("X-Reel-Token") != TOKEN:
            self.reply(403, {"error": "Forbidden"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16384:
                raise ValueError("Request is too large")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Invalid request")
            if self.path == "/api/pick":
                self.pick_file(data)
            elif self.path == "/api/start":
                self.start_job(data)
            elif self.path == "/api/select":
                self.select_project(data)
            elif self.path == "/api/reveal":
                self.reveal(data)
            else:
                self.reply(404, {"error": "Not found"})
        except (ValueError, OSError) as exc:
            self.reply(400, {"error": str(exc)})

    def pick_file(self, data: dict) -> None:
        if sys.platform != "darwin":
            raise ValueError("Paste the full file path into the field")
        prompt = "Choose an audio track" if data.get("kind") == "audio" else "Choose a video to edit"
        result = subprocess.run(["osascript", "-e", f'POSIX path of (choose file with prompt "{prompt}")'],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError("File selection canceled")
        self.reply(200, {"path": result.stdout.strip()})

    def start_job(self, data: dict) -> None:
        action = data.get("action")
        if action not in ("ingest", "analyze", "generate"):
            raise ValueError("Unknown action")
        with LOCK:
            if JOB["running"]:
                raise ValueError("Another step is still running")
        if action == "ingest":
            video = Path(str(data.get("path", ""))).expanduser().resolve()
            if not video.is_file():
                raise ValueError("Choose an existing video file")
            args = ["ingest", str(video)]
        else:
            project = active_project()
            if not project:
                raise ValueError("Choose a video first")
            if action == "analyze":
                settings = validated_settings(data.get("settings", analysis_settings(project)))
                args = ["--project", project.name, "--config", str(project_config(project, settings)), "analyze"]
            else:
                mood = str(data.get("mood", "")).strip()[:200]
                if not mood:
                    raise ValueError("Enter a mood")
                duration = float(data.get("duration", 20))
                variants = int(data.get("variants", 1))
                spoilers = data.get("spoilers", "low")
                if not 1 <= duration <= 600 or not 1 <= variants <= 20:
                    raise ValueError("Duration must be 1–600 seconds and variants 1–20")
                if spoilers not in ("low", "medium", "unrestricted"):
                    raise ValueError("Invalid spoiler setting")
                if not (project / "analysis/shots.json").is_file():
                    raise ValueError("Analyze the video first")
                audio = data.get("audio", "muted")
                if audio not in ("muted", "original", "music", "dialogue_reduced"):
                    raise ValueError("Choose a valid sound option")
                volume = float(data.get("audio_volume", 1))
                if not math.isfinite(volume) or not 0 <= volume <= 2:
                    raise ValueError("Sound level must be between 0 and 2")
                music = str(data.get("music", "")).strip()
                if audio == "music" and not Path(music).expanduser().is_file():
                    raise ValueError("Choose an existing music file")
                ranking = validated_settings(data.get("ranking", ranking_settings(project)), RANKING_FIELDS)
                args = ["--project", project.name, "--config", str(project_config(project, ranking=ranking)), "generate",
                        "--mood", mood, "--duration", str(duration), "--variants", str(variants),
                        "--spoilers", spoilers, "--audio", audio, "--audio-volume", str(volume)]
                if audio == "music":
                    args += ["--music", str(Path(music).expanduser().resolve())]
        with LOCK:
            JOB.update({"running": True, "action": action, "exit_code": None,
                        "logs": [f"Starting {action}…"], "started_at": time.time()})
        threading.Thread(target=run_job, args=(action, args), daemon=True).start()
        self.reply(202, {"started": action})

    def select_project(self, data: dict) -> None:
        name = str(data.get("project", ""))
        if Path(name).name != name or not (PROJECTS / name / "analysis/film.json").is_file():
            raise ValueError("Project not found")
        with LOCK:
            if JOB["running"]:
                raise ValueError("Wait for the current step to finish")
        (PROJECTS / ".active.json").write_text(json.dumps({"project": name}), encoding="utf-8")
        self.reply(200, {"selected": name})

    def reveal(self, data: dict) -> None:
        project = active_project()
        name = str(data.get("name", ""))
        if not project or Path(name).name != name or not name.endswith(".mp4"):
            raise ValueError("Video not found")
        video = project / "exports" / name
        if not video.is_file():
            raise ValueError("Video not found")
        subprocess.Popen(["open", "-R", str(video)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.reply(200, {"revealed": name})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    options = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", options.port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Film Reel Engine UI: {url}\nPress Control-C to stop.", flush=True)
    if not options.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
