import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
import src.concept_generator as concept_generator
import src.storyboard as storyboard_module
from src.engine import ReelEngine


PROJECT_ID = "test-film-123456"
RESEARCH_ID = "research-1234abcd"
TOPIC = "intimacy through conversation"
BOARD = {
    "topic": TOPIC,
    "research_summary": "The exchanges move from play toward mutual disclosure.",
    "thesis_direction": "Conversation makes intimacy feel like a negotiated risk.",
    "selected_ids": [501, 502, 503],
    "evidence": [
        {
            "id": 501, "passage_id": 501, "scene_id": 77,
            "title": "Question game", "evidence_start": 100.0,
            "evidence_end": 130.0, "excerpt": "Transcript evidence one.",
            "editorial_role": "setup", "reason": "The rules make disclosure safer.",
            "supported_claim": "Play creates permission for honesty.", "warning": "",
        },
        {
            "id": 502, "passage_id": 502, "scene_id": 88,
            "title": "Imaginary call", "evidence_start": 200.0,
            "evidence_end": 230.0, "excerpt": "Transcript evidence two.",
            "editorial_role": "development", "reason": "Role-play makes desire indirect.",
            "supported_claim": "Performance creates emotional cover.", "warning": "",
        },
        {
            "id": 503, "passage_id": 503, "scene_id": 99,
            "title": "Admission", "evidence_start": 300.0,
            "evidence_end": 330.0, "excerpt": "Transcript evidence three.",
            "editorial_role": "payoff", "reason": "The earlier play becomes direct.",
            "supported_claim": "Accumulated talk enables vulnerability.",
            "warning": "Do not overstate what the transcript proves.",
        },
    ],
}


def reel_concept(format_name: str) -> concept_generator.ReelConcept:
    return concept_generator.ReelConcept(
        title=f"A {format_name} concept", format=format_name,
        hook="Conversation is the romance.",
        thesis="Questions create room for reciprocal vulnerability.",
        tone="warm and precise", evidence_ids=[501, 502], estimated_duration=29,
        warnings=[], beats=[
            concept_generator.ConceptBeat(
                order=1, card_type="hook", evidence_id=0,
                text="Conversation is the romance.", duration_seconds=2,
            ),
            concept_generator.ConceptBeat(
                order=2, card_type="clip", evidence_id=501,
                text="The question game", anchor_quote="Transcript evidence one",
                duration_seconds=6,
            ),
            concept_generator.ConceptBeat(
                order=3, card_type="observation", evidence_id=0,
                text="Rules make honesty safer.", duration_seconds=4,
            ),
            concept_generator.ConceptBeat(
                order=4, card_type="clip", evidence_id=502,
                text="The imaginary call", anchor_quote="Transcript evidence two",
                duration_seconds=7,
            ),
            concept_generator.ConceptBeat(
                order=5, card_type="interpretation", evidence_id=0,
                text="Talk becomes a shared risk.", duration_seconds=7,
            ),
            concept_generator.ConceptBeat(
                order=6, card_type="end_card", evidence_id=0,
                text="Fresno Film Society", duration_seconds=3,
            ),
        ],
    )


class CapturingResponses:
    def __init__(self, calls: list[dict]):
        self.calls = calls

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=concept_generator.ConceptSet(concepts=[
            reel_concept("analytical_argument"), reel_concept("detail_missed"),
            reel_concept("poetic_ffs"),
        ]))


class CapturingOpenAI:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.responses = CapturingResponses(self.calls)


def saved_engine(root: Path, board: dict = BOARD) -> ReelEngine:
    engine = ReelEngine(root)
    engine._save({
        "id": PROJECT_ID, "title": "Test Film", "movie": {"duration": 500.0},
        "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
        "evidence_researches": [{"id": RESEARCH_ID, "created_at": "now", "board": board}],
    })
    # This fixture intentionally uses the legacy, pre-binding record shape. Its
    # evidence remains recoverable because it is byte-for-byte identical to the
    # current local semantic passages.
    with engine.film_index(PROJECT_ID).connect() as db:
        for item in BOARD["evidence"]:
            db.execute(
                "INSERT OR IGNORE INTO scenes(id,start,end,title) VALUES(?,?,?,?)",
                (item["scene_id"], item["evidence_start"], item["evidence_end"], item["title"]),
            )
            db.execute(
                "INSERT OR REPLACE INTO semantic_passages"
                "(id,scene_id,start,end,text,embedding) VALUES(?,?,?,?,?,?)",
                (item["id"], item["scene_id"], item["evidence_start"],
                 item["evidence_end"], item["excerpt"], b"\x00\x00\x00\x00"),
            )
    return engine


class ResearchDownstreamTests(unittest.TestCase):
    def setUp(self):
        CapturingOpenAI.calls.clear()

    def test_concepts_use_exact_saved_board_and_preserve_research_judgment(self):
        with tempfile.TemporaryDirectory() as temp:
            board = json.loads(json.dumps(BOARD))
            board["evidence"][0].update({
                "visual_summary": "The characters share a balanced two-shot.",
                "visual_observations": [{
                    "kind": "composition",
                    "statement": "Both figures occupy the same frame.",
                    "frame_numbers": [1], "confidence": "high",
                    "editorial_relevance": "The composition makes conversation spatially mutual.",
                }],
                "visual_caution": "Still frames cannot establish camera movement.",
            })
            engine = saved_engine(Path(temp), board)
            with patch.object(app_module, "engine", engine), \
                 patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
                 patch.object(concept_generator, "OpenAI", CapturingOpenAI), \
                 patch.object(
                     concept_generator, "build_evidence_board",
                     side_effect=AssertionError("local board must not be rebuilt"),
                 ):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/concepts",
                        json={"topic": TOPIC, "research_id": RESEARCH_ID,
                              "evidence_ids": [501, 502, 503]},
                    )

            self.assertEqual(200, response.status_code, response.get_json())
            self.assertEqual(RESEARCH_ID, response.get_json()["research_id"])
            prompt = json.loads(CapturingOpenAI.calls[0]["input"])
            self.assertEqual(BOARD["research_summary"], prompt["research_summary"])
            self.assertEqual(BOARD["thesis_direction"], prompt["thesis_direction"])
            self.assertEqual("setup", prompt["evidence"][0]["editorial_role"])
            self.assertEqual(
                "Play creates permission for honesty.",
                prompt["evidence"][0]["supported_claim"],
            )
            self.assertEqual(
                "The characters share a balanced two-shot.",
                prompt["evidence"][0]["visual_summary"],
            )
            self.assertEqual(
                "Both figures occupy the same frame.",
                prompt["evidence"][0]["visual_observations"][0]["statement"],
            )
            self.assertIn("Visual claims are allowed only", CapturingOpenAI.calls[0]["instructions"])

    def test_storyboard_uses_saved_passage_bounds_and_real_scene_id(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_engine(Path(temp))
            concept = reel_concept("analytical_argument").model_dump()
            with patch.object(app_module, "engine", engine), \
                 patch.object(
                     storyboard_module, "build_evidence_board",
                     side_effect=AssertionError("local board must not be rebuilt"),
                 ):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/storyboards",
                        json={
                            "topic": TOPIC, "research_id": RESEARCH_ID,
                            "concept": concept,
                            "evidence": [{"id": 501, "evidence_start": 0, "evidence_end": 500}],
                        },
                    )

            self.assertEqual(200, response.status_code, response.get_json())
            story = response.get_json()["storyboard"]
            self.assertEqual(RESEARCH_ID, story["research_id"])
            clip = next(card for card in story["cards"] if card.get("evidence_id") == 501)
            self.assertEqual(77, clip["scene_id"])
            self.assertEqual((100.0, 106.0), (clip["source_start"], clip["source_end"]))
            persisted = engine.load(PROJECT_ID)["editorial_storyboards"][0]
            self.assertEqual(RESEARCH_ID, persisted["research_id"])

    def test_unknown_mismatched_and_stale_researches_return_clear_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_engine(Path(temp))
            with patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    unknown = client.post(
                        f"/api/projects/{PROJECT_ID}/concepts",
                        json={"topic": TOPIC, "research_id": "research-deadbeef",
                              "evidence_ids": [501, 502, 503]},
                    )
                    mismatch = client.post(
                        f"/api/projects/{PROJECT_ID}/storyboards",
                        json={"topic": "a different idea", "research_id": RESEARCH_ID,
                              "concept": reel_concept("analytical_argument").model_dump()},
                    )
                    invalid_evidence = client.post(
                        f"/api/projects/{PROJECT_ID}/concepts",
                        json={"topic": TOPIC, "research_id": RESEARCH_ID,
                              "evidence_ids": [501, 502, 999]},
                    )
            self.assertEqual(400, unknown.status_code)
            self.assertIn("not found", unknown.get_json()["error"])
            self.assertEqual(400, mismatch.status_code)
            self.assertIn("does not match", mismatch.get_json()["error"])
            self.assertEqual(400, invalid_evidence.status_code)
            self.assertIn("does not belong", invalid_evidence.get_json()["error"])

            stale = dict(BOARD)
            stale["evidence"] = []
            stale_engine = saved_engine(Path(temp), stale)
            with patch.object(app_module, "engine", stale_engine):
                with app_module.app.test_client() as client:
                    stale_response = client.post(
                        f"/api/projects/{PROJECT_ID}/concepts",
                        json={"topic": TOPIC, "research_id": RESEARCH_ID,
                              "evidence_ids": [501, 502, 503]},
                    )
            self.assertEqual(400, stale_response.status_code)
            self.assertIn("no longer usable", stale_response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
