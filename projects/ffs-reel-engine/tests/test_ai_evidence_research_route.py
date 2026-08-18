import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
import src.engine as engine_module
from src.engine import ReelEngine


PROJECT_ID = "test-film-123456"
BOARD = {
    "topic": "intimacy grows through conversation",
    "thesis_direction": "Conversation lets vulnerability become reciprocal.",
    "evidence": [{
        "id": 10,
        "title": "Question game",
        "evidence_start": 100.0,
        "evidence_end": 125.0,
        "supported_claim": "Direct questions accelerate personal disclosure.",
    }],
}


def saved_project(root: Path) -> ReelEngine:
    engine = ReelEngine(root)
    engine._save({
        "id": PROJECT_ID,
        "title": "Test Film",
        "movie": {"duration": 300.0},
        "recipe": "mood_montage",
        "transcript": [],
        "candidates": [],
        "exports": [],
    })
    return engine


class AiEvidenceResearchRouteTests(unittest.TestCase):
    def test_route_researches_topic_against_project_index(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            calls = []

            def fake_research(index, topic):
                calls.append((index, topic))
                return BOARD

            with patch.object(app_module, "engine", engine), \
                 patch.object(engine_module, "research_evidence", fake_research):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/evidence/ai-research",
                        json={"topic": BOARD["topic"]},
                    )

            self.assertEqual(200, response.status_code)
            payload = response.get_json()
            self.assertEqual(BOARD["topic"], payload["topic"])
            self.assertEqual(BOARD["evidence"], payload["evidence"])
            self.assertRegex(payload["research_id"], r"^research-[0-9a-f]{8}$")
            self.assertEqual(1, len(calls))
            self.assertEqual(BOARD["topic"], calls[0][1])
            self.assertEqual(
                engine.film_index(PROJECT_ID).path,
                calls[0][0].path,
            )
            persisted = engine.load(PROJECT_ID)["evidence_researches"]
            self.assertEqual(1, len(persisted))
            self.assertEqual(payload["research_id"], persisted[0]["id"])
            self.assertEqual(BOARD, persisted[0]["board"])
            self.assertIn("created_at", persisted[0])

    def test_research_error_uses_engine_error_response(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            with patch.object(app_module, "engine", engine), \
                 patch.object(
                     engine_module,
                     "research_evidence",
                     side_effect=ValueError("OpenAI research could not be completed."),
                 ):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/evidence/ai-research",
                        json={"topic": "intimacy"},
                    )

            self.assertEqual(400, response.status_code)
            self.assertEqual(
                {"error": "OpenAI research could not be completed."},
                response.get_json(),
            )
            self.assertNotIn("evidence_researches", engine.load(PROJECT_ID))


if __name__ == "__main__":
    unittest.main()
