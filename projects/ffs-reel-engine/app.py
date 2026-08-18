from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from dotenv import load_dotenv

from src.engine import EngineError, ReelEngine


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
engine = ReelEngine(ROOT)


@app.get("/")
def index():
    return render_template("index.html", initial_project_id=None)


@app.get("/projects/<project_id>/montage")
def mood_montage_editor(project_id: str):
    engine.load(project_id)
    return render_template("index.html", initial_project_id=project_id)


@app.get("/projects/<project_id>/workspace")
def unified_workspace(project_id: str):
    """Unified project shell; existing recipe editors remain available as tools."""
    engine.load(project_id)
    return render_template("workspace.html", project_id=project_id)


@app.get("/projects/<project_id>/scenes")
def scene_review(project_id: str):
    engine.load(project_id)
    return render_template("scenes.html", project_id=project_id)


@app.get("/projects/<project_id>/storyboards/<storyboard_id>")
def storyboard_editor(project_id: str, storyboard_id: str):
    engine.get_editorial_storyboard(project_id, storyboard_id)
    return render_template("storyboard.html", project_id=project_id,
                           storyboard_id=storyboard_id)


@app.get("/projects/<project_id>/conversion")
def conversion_editor(project_id: str):
    engine.get_conversion_reel(project_id)
    return render_template("conversion.html", project_id=project_id)


@app.post("/api/projects")
def create_project():
    data = request.get_json(force=True)
    return jsonify(engine.create_project(data.get("title", "Untitled film")))


@app.get("/api/projects/<project_id>")
def get_project(project_id: str):
    return jsonify(engine.load(project_id))


@app.post("/api/projects/<project_id>/ingest")
def ingest(project_id: str):
    data = request.get_json(force=True)
    return jsonify(engine.ingest_movie(project_id, data.get("movie_path", "")))


@app.post("/api/projects/<project_id>/shots")
def shots(project_id: str):
    return jsonify(engine.discover_shots(project_id))


@app.get("/api/projects/<project_id>/index")
def index_status(project_id: str):
    return jsonify(engine.index_status(project_id))


@app.post("/api/projects/<project_id>/transcription/start")
def start_transcription(project_id: str):
    return jsonify(engine.start_transcription(project_id))


@app.get("/api/projects/<project_id>/transcription")
def transcription_status(project_id: str):
    return jsonify(engine.transcription_status(project_id))


@app.post("/api/projects/<project_id>/transcription/cancel")
def cancel_transcription(project_id: str):
    return jsonify(engine.cancel_transcription(project_id))


@app.post("/api/projects/<project_id>/scenes/generate")
def generate_scenes(project_id: str):
    return jsonify(engine.generate_scene_map(project_id))


@app.get("/api/projects/<project_id>/scenes")
def scenes(project_id: str):
    return jsonify(engine.scenes(project_id))


@app.post("/api/projects/<project_id>/scenes/enrich")
def enrich_scenes(project_id: str):
    return jsonify(engine.enrich_scene_index(project_id))


@app.get("/api/projects/<project_id>/scenes/search")
def search_scenes(project_id: str):
    return jsonify(engine.search_scene_index(project_id, request.args.get("q", "")))


@app.post("/api/projects/<project_id>/scenes/semantic-index")
def semantic_index(project_id: str):
    return jsonify(engine.build_semantic_scene_index(project_id))


@app.get("/api/projects/<project_id>/scenes/semantic-search")
def semantic_search(project_id: str):
    return jsonify(engine.semantic_scene_search(project_id, request.args.get("q", "")))


@app.post("/api/projects/<project_id>/evidence")
def evidence_board(project_id: str):
    data = request.get_json(force=True)
    return jsonify(engine.evidence_board(project_id, data.get("topic", "")))


@app.post("/api/projects/<project_id>/evidence/ai-research")
def ai_evidence_research(project_id: str):
    data = request.get_json(force=True)
    return jsonify(engine.research_evidence(project_id, data.get("topic", "")))


@app.get("/api/projects/<project_id>/evidence/latest")
def latest_evidence_research(project_id: str):
    return jsonify(engine.latest_evidence_research(project_id))


@app.post("/api/projects/<project_id>/evidence/<research_id>/visual-analysis")
def visual_evidence_analysis(project_id: str, research_id: str):
    return jsonify(engine.analyze_evidence_visuals(project_id, research_id))


@app.get(
    "/api/projects/<project_id>/evidence/frame/<research_id>/<analysis_id>/<filename>"
)
def visual_evidence_frame(project_id: str, research_id: str,
                          analysis_id: str, filename: str):
    return send_file(engine.evidence_frame_path(
        project_id, research_id, analysis_id, filename
    ), conditional=True)


@app.get("/api/editorial/status")
def editorial_status():
    return jsonify(engine.editorial_status())


@app.post("/api/projects/<project_id>/evidence/editorial-rerank")
def editorial_rerank(project_id: str):
    data = request.get_json(force=True)
    return jsonify(engine.editorial_rerank(project_id, data.get("topic", "")))


@app.post("/api/projects/<project_id>/concepts")
def concepts(project_id: str):
    data = request.get_json(force=True)
    if not data.get("research_id"):
        return jsonify(engine.generate_editorial_concepts(
            project_id, data.get("topic", ""), data.get("evidence_ids", [])
        ))
    return jsonify(engine.generate_editorial_concepts(
        project_id, data.get("topic", ""), data.get("evidence_ids", []),
        data.get("research_id"),
    ))


@app.post("/api/projects/<project_id>/storyboards")
def create_storyboard(project_id: str):
    return jsonify(engine.create_editorial_storyboard(project_id, request.get_json(force=True)))


@app.get("/api/projects/<project_id>/storyboards/<storyboard_id>")
def get_storyboard(project_id: str, storyboard_id: str):
    return jsonify(engine.get_editorial_storyboard(project_id, storyboard_id))


@app.patch("/api/projects/<project_id>/storyboards/<storyboard_id>")
def patch_storyboard(project_id: str, storyboard_id: str):
    return jsonify(engine.update_editorial_storyboard(
        project_id, storyboard_id, request.get_json(force=True)
    ))


@app.post("/api/projects/<project_id>/storyboards/<storyboard_id>/cards/<card_id>/refine")
def refine_storyboard_clip(project_id: str, storyboard_id: str, card_id: str):
    return jsonify(engine.refine_storyboard_clip(project_id, storyboard_id, card_id))


@app.post("/api/projects/<project_id>/storyboards/<storyboard_id>/export")
def export_storyboard(project_id: str, storyboard_id: str):
    return jsonify(engine.export_editorial_storyboard(project_id, storyboard_id))


@app.get("/api/projects/<project_id>/conversion")
def get_conversion(project_id: str):
    return jsonify(engine.get_conversion_reel(project_id))


@app.put("/api/projects/<project_id>/conversion")
def save_conversion(project_id: str):
    return jsonify(engine.save_conversion_reel(project_id, request.get_json(force=True)))


@app.post("/api/projects/<project_id>/conversion/export")
def export_conversion(project_id: str):
    return jsonify(engine.export_conversion_reel(project_id))


@app.patch("/api/projects/<project_id>/scenes/<int:scene_id>")
def review_scene(project_id: str, scene_id: int):
    return jsonify(engine.review_scene(project_id, scene_id, request.get_json(force=True)))


@app.post("/api/projects/<project_id>/candidates")
def candidates(project_id: str):
    return jsonify(engine.generate_candidates(project_id))


@app.get("/api/projects/<project_id>/montage")
def get_mood_montage(project_id: str):
    return jsonify(engine.get_mood_montage(project_id))


@app.post("/api/projects/<project_id>/montage/balanced-draft")
def balanced_mood_montage(project_id: str):
    return jsonify(engine.build_balanced_mood_montage(
        project_id, request.get_json(force=True)
    ))


@app.post("/api/projects/<project_id>/montage/mood-draft")
def mood_aware_montage(project_id: str):
    return jsonify(engine.build_mood_aware_montage(
        project_id, request.get_json(force=True)
    ))


@app.post("/api/projects/<project_id>/montage/visual-index")
def visual_montage_index(project_id: str):
    return jsonify(engine.build_visual_montage_index(
        project_id, request.get_json(force=True)
    ))


@app.patch("/api/projects/<project_id>/montage")
def save_mood_montage(project_id: str):
    return jsonify(engine.save_mood_montage(project_id, request.get_json(force=True)))


@app.post("/api/projects/<project_id>/export")
def export(project_id: str):
    data = request.get_json(force=True)
    return jsonify(engine.export_montage(project_id, data))


@app.get("/api/media/<project_id>")
def media(project_id: str):
    project = engine.load(project_id)
    return send_file(project["movie"]["path"], conditional=True)


@app.get("/api/output/<name>")
def output(name: str):
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
        return jsonify({"error": "Invalid output name"}), 400
    path = ROOT / "outputs" / name
    if not path.is_file():
        return jsonify({"error": "Output file not found. Render or copy this export into the current workspace."}), 404
    return send_file(path, conditional=True)


@app.get("/assets/<path:name>")
def asset(name: str):
    return send_from_directory(ROOT / "assets", name)


@app.get("/api/projects/<project_id>/thumbnail/<name>")
def thumbnail(project_id: str, name: str):
    if not re.fullmatch(
            r"(?:shot-[0-9]{3}|indexed-[0-9]{6}|runtime-[0-9]{10}|mood-[0-9a-f]{8}-[0-9]{4})\.jpg", name):
        return jsonify({"error": "Invalid thumbnail name"}), 400
    return send_file(engine.project_dir(project_id) / "thumbnails" / name)


@app.errorhandler(EngineError)
def engine_error(error: EngineError):
    return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(__import__("os").environ.get("REEL_ENGINE_PORT", "8777")), debug=False)
