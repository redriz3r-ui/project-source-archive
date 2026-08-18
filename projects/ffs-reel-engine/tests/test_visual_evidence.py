import copy
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
import src.engine as engine_module
import src.visual_evidence as visual_module
from src.engine import ReelEngine


PROJECT_ID = "test-film-123456"
RESEARCH_ID = "research-1234abcd"
TOPIC = "intimacy through conversation"
BOARD = {
    "topic": TOPIC,
    "research_summary": "Three conversations make disclosure progressively more direct.",
    "thesis_direction": "Talk becomes a shared risk.",
    "selected_ids": [11, 12, 13],
    "evidence": [
        {
            "id": evidence_id, "passage_id": evidence_id, "scene_id": evidence_id,
            "title": f"Moment {evidence_id}", "evidence_start": start,
            "evidence_end": start + 20, "excerpt": f"Transcript evidence {evidence_id}.",
            "editorial_role": "support", "reason": "A useful moment.",
            "supported_claim": "The exchange makes disclosure more direct.", "warning": "",
        }
        for evidence_id, start in ((11, 10.0), (12, 50.0), (13, 90.0))
    ],
}


class FakeResponses:
    calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=visual_module.VisualAnalysisSet(evidence=[
            visual_module.EvidenceVisualAnalysis(
                evidence_id=evidence_id,
                visual_summary="The two figures share a balanced frame.",
                observations=[visual_module.VisualObservation(
                    kind="composition",
                    statement="Two figures occupy opposite sides of the frame.",
                    frame_numbers=[1, 2], confidence="high",
                    editorial_relevance="The shared frame visually connects the exchange.",
                )],
                caution="Still frames cannot establish camera movement.",
            )
            for evidence_id in (11, 12, 13)
        ]))


class FakeOpenAI:
    def __init__(self, **kwargs):
        self.responses = FakeResponses()


def saved_engine(root: Path) -> ReelEngine:
    movie = root / "movie.mp4"
    movie.write_bytes(b"fake movie")
    engine = ReelEngine(root)
    engine._save({
        "id": PROJECT_ID, "title": "Test Film",
        "movie": {"path": str(movie), "duration": 150.0, "fingerprint": "movie-fp"},
        "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
    })
    index = engine.film_index(PROJECT_ID)
    with index.connect() as db:
        for item in BOARD["evidence"]:
            db.execute(
                "INSERT INTO scenes(id,start,end,title) VALUES(?,?,?,?)",
                (item["scene_id"], item["evidence_start"], item["evidence_end"], item["title"]),
            )
            db.execute(
                "INSERT INTO semantic_passages(id,scene_id,start,end,text,embedding) "
                "VALUES(?,?,?,?,?,?)",
                (item["id"], item["scene_id"], item["evidence_start"],
                 item["evidence_end"], item["excerpt"], b"\x00\x00\x00\x00"),
            )
    project = engine.load(PROJECT_ID)
    project["evidence_researches"] = [{
        "id": RESEARCH_ID, "created_at": "now", "source_fingerprint": "movie-fp",
        "semantic_index_signature": index.semantic_index_signature(),
        "board": copy.deepcopy(BOARD),
    }]
    engine._save(project)
    return engine


class VisualEvidenceTests(unittest.TestCase):
    def setUp(self):
        FakeResponses.calls.clear()

    def test_frame_sampling_and_structured_visual_analysis(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")

            def fake_extract(_movie, _timestamp, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"jpeg data")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
                 patch.object(visual_module, "OpenAI", FakeOpenAI), \
                 patch.object(visual_module, "_extract_frame", fake_extract):
                result = visual_module.analyze_visual_evidence(
                    movie, BOARD, root / "frames", movie_duration=150,
                    analysis_id="visual-1234abcd",
                )

            self.assertEqual("visual-1234abcd", result["id"])
            self.assertEqual(9, result["frame_count"])
            self.assertEqual(3, result["observation_count"])
            self.assertEqual([13.6, 20.0, 26.4], [
                frame["timestamp"] for frame in result["evidence"][0]["visual_frames"]
            ])
            content = FakeResponses.calls[0]["input"][0]["content"]
            self.assertEqual(9, sum(item["type"] == "input_image" for item in content))
            self.assertTrue(all(
                item["image_url"].startswith("data:image/jpeg;base64,")
                for item in content if item["type"] == "input_image"
            ))

    def test_route_persists_visuals_and_serves_only_generated_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_engine(Path(temp))

            def fake_analysis(_movie, board, destination, **kwargs):
                analysis_id = kwargs["analysis_id"]
                evidence = []
                for item in board["evidence"]:
                    filename = f"evidence-{item['id']}-frame-1.jpg"
                    destination.mkdir(parents=True, exist_ok=True)
                    (destination / filename).write_bytes(b"frame")
                    evidence.append({
                        "evidence_id": item["id"],
                        "visual_summary": "A shared two-shot.",
                        "visual_observations": [{
                            "kind": "composition", "statement": "Both figures share the frame.",
                            "frame_numbers": [1], "confidence": "high",
                            "editorial_relevance": "Proximity supports the topic.",
                        }],
                        "visual_caution": "", "visual_frames": [{
                            "number": 1, "timestamp": item["evidence_start"] + 2,
                            "filename": filename,
                        }],
                    })
                return {
                    "id": analysis_id, "status": "complete", "model": "test-vision",
                    "created_at": "now", "frame_count": 3, "observation_count": 3,
                    "evidence": evidence,
                }

            with patch.object(app_module, "engine", engine), \
                 patch.object(engine_module, "analyze_visual_evidence", fake_analysis):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/evidence/{RESEARCH_ID}/visual-analysis",
                        json={},
                    )
                    self.assertEqual(200, response.status_code, response.get_json())
                    payload = response.get_json()
                    frame_url = payload["evidence"][0]["visual_frames"][0]["url"]
                    frame_response = client.get(frame_url)
                    invalid = client.get(
                        f"/api/projects/{PROJECT_ID}/evidence/frame/{RESEARCH_ID}/"
                        "visual-1234abcd/../../project.json"
                    )

            self.assertEqual(b"frame", frame_response.data)
            self.assertNotEqual(200, invalid.status_code)
            persisted = engine.load(PROJECT_ID)["evidence_researches"][0]["board"]
            self.assertEqual("complete", persisted["visual_analysis"]["status"])
            self.assertEqual("A shared two-shot.", persisted["evidence"][0]["visual_summary"])
            self.assertIn("/evidence/frame/", persisted["evidence"][0]["visual_frames"][0]["url"])

    def test_failed_visual_analysis_does_not_modify_saved_board(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_engine(Path(temp))
            before = engine.load(PROJECT_ID)["evidence_researches"][0]["board"]
            with patch.object(app_module, "engine", engine), \
                 patch.object(
                     engine_module, "analyze_visual_evidence",
                     side_effect=ValueError("vision unavailable"),
                 ):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/evidence/{RESEARCH_ID}/visual-analysis",
                        json={},
                    )
            self.assertEqual(400, response.status_code)
            self.assertEqual("vision unavailable", response.get_json()["error"])
            after = engine.load(PROJECT_ID)["evidence_researches"][0]["board"]
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
