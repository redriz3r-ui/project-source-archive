"""Temporary browser fixture for manually testing the storyboard UI."""
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import app as app_module
import src.storyboard as storyboard_module
from src.engine import ReelEngine


PROJECT_ID = "storyboard-ui-test"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
source = ReelEngine(SOURCE_ROOT).load("before-sunrise-df826b")
engine = ReelEngine(Path(mkdtemp(prefix="ffs-storyboard-ui-")))
project = {
    "id": PROJECT_ID, "title": "Before Sunrise", "movie": source["movie"],
    "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
}
engine._save(project)
board = {"evidence": [
    {"id": 10, "title": "Question game", "evidence_start": 1181.0, "evidence_end": 1220.0},
    {"id": 29, "title": "Imaginary phone call", "evidence_start": 4188.0, "evidence_end": 4230.0},
]}
concept = {
    "title": "Conversation Is the Romance", "format": "analytical_argument",
    "hook": "Before Sunrise makes conversation feel like physical intimacy.",
    "thesis": "Jesse and Céline use questions and performance to make disclosure safer.",
    "tone": "clear and intimate", "evidence_ids": [10, 29], "estimated_duration": 29,
    "warnings": [], "beats": [
        {"order": 1, "card_type": "hook", "evidence_id": 0,
         "text": "Conversation is the romance.", "duration_seconds": 2.5},
        {"order": 2, "card_type": "clip", "evidence_id": 10,
         "text": "The question game", "duration_seconds": 6},
        {"order": 3, "card_type": "observation", "evidence_id": 0,
         "text": "Questions turn vulnerability into play.", "duration_seconds": 4},
        {"order": 4, "card_type": "clip", "evidence_id": 29,
         "text": "The imaginary phone call", "duration_seconds": 7},
        {"order": 5, "card_type": "interpretation", "evidence_id": 0,
         "text": "They confess by pretending to speak to someone else.", "duration_seconds": 5},
        {"order": 6, "card_type": "end_card", "evidence_id": 0,
         "text": "Fresno Film Society", "duration_seconds": 3},
    ],
}
with patch.object(storyboard_module, "build_evidence_board", return_value=board):
    created = engine.create_editorial_storyboard(PROJECT_ID, {"topic": "intimacy", "concept": concept})

app_module.engine = engine
print(f"FIXTURE_URL=http://127.0.0.1:8778{created['url']}", flush=True)
app_module.app.run(host="127.0.0.1", port=8778, debug=False)
