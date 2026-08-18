import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
import src.engine as engine_module
from src.engine import ReelEngine
from src.film_index import source_fingerprint


PROJECT_ID = "test-film-123456"
TOPIC = "conversation creates intimacy"
BOARD = {
    "topic": TOPIC,
    "thesis_direction": "Talk makes vulnerability reciprocal.",
    "evidence": [{
        "id": 11, "passage_id": 11, "scene_id": 7,
        "title": "Question game", "evidence_start": 100.0,
        "evidence_end": 125.0, "excerpt": "An exact transcript passage.",
        "supported_claim": "Questions create permission for honesty.",
    }],
}


def saved_engine(root: Path, *, movie: dict | None = None) -> ReelEngine:
    engine = ReelEngine(root)
    engine._save({
        "id": PROJECT_ID, "title": "Test Film", "movie": movie,
        "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
    })
    return engine


def seed_passage(engine: ReelEngine, source: str = "source-a") -> None:
    index = engine.film_index(PROJECT_ID)
    with index.connect() as db:
        db.execute(
            "INSERT INTO scenes(id,start,end,title) VALUES(?,?,?,?)",
            (7, 90.0, 140.0, "Question game"),
        )
        db.execute(
            "INSERT INTO semantic_passages(id,scene_id,start,end,text,embedding) "
            "VALUES(?,?,?,?,?,?)",
            (11, 7, 100.0, 125.0, "An exact transcript passage.", b"\x00\x00\x00\x00"),
        )
    index.set_metadata({
        "source_fingerprint": source, "semantic_index_status": "complete",
        "semantic_model": "fixture", "semantic_dimensions": 1,
    })


class ResearchPersistenceTests(unittest.TestCase):
    def test_slow_research_merges_into_fresh_project_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_engine(Path(temp))

            def fake_research(_index, _topic):
                concurrent = engine.load(PROJECT_ID)
                concurrent["user_edit_during_research"] = "must survive"
                engine._save(concurrent)
                return BOARD

            with patch.object(engine_module, "research_evidence", fake_research):
                result = engine.research_evidence(PROJECT_ID, TOPIC)

            persisted = engine.load(PROJECT_ID)
            self.assertEqual("must survive", persisted["user_edit_during_research"])
            self.assertEqual(result["research_id"], persisted["evidence_researches"][0]["id"])
            record = persisted["evidence_researches"][0]
            self.assertIn("source_fingerprint", record)
            self.assertRegex(record["semantic_index_signature"], r"^[0-9a-f]{64}$")

    def test_ingesting_different_movie_resets_all_film_dependent_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.mp4"
            second = root / "second.mp4"
            first.write_bytes(b"first movie")
            second.write_bytes(b"different second movie")
            first_fingerprint = source_fingerprint(first)
            engine = saved_engine(root, movie={
                "path": str(first), "filename": first.name, "duration": 100.0,
                "fingerprint": first_fingerprint,
            })
            project = engine.load(PROJECT_ID)
            project.update({
                "transcript": [{"start": 1, "end": 2, "text": "old"}],
                "candidates": [{"id": "old-candidate"}],
                "shot_index": {"detected_count": 1},
                "transcription": {"status": "complete"},
                "evidence_researches": [{"id": "research-deadbeef", "board": BOARD}],
                "editorial_storyboards": [{"id": "story-old"}],
                "active_storyboard_id": "story-old",
            })
            engine._save(project)
            index = engine.film_index(PROJECT_ID)
            index.set_metadata({"source_fingerprint": first_fingerprint})
            index.replace_shots(
                [{"start": 0.0, "end": 2.0, "shot_duration": 2.0}], 0.32, {0.0}
            )
            index.append_transcript(
                [{"start": 0.5, "end": 1.5, "text": "old transcript"}], 2.0
            )

            probe = SimpleNamespace(
                returncode=0,
                stdout=json.dumps({
                    "format": {"duration": "120.0"},
                    "streams": [{
                        "codec_type": "video", "codec_name": "h264", "width": 1920,
                        "height": 1080, "r_frame_rate": "24/1",
                    }],
                }),
            )
            with patch.object(engine_module.subprocess, "run", return_value=probe):
                engine.ingest_movie(PROJECT_ID, str(second))

            reset_project = engine.load(PROJECT_ID)
            self.assertEqual([], reset_project["transcript"])
            self.assertEqual([], reset_project["candidates"])
            for stale_key in (
                "shot_index", "transcription", "evidence_researches",
                "editorial_storyboards", "active_storyboard_id",
            ):
                self.assertNotIn(stale_key, reset_project)
            stats = index.stats()
            self.assertTrue(all(count == 0 for count in stats["counts"].values()))
            self.assertEqual(source_fingerprint(second), stats["metadata"]["source_fingerprint"])
            self.assertEqual("pending", stats["metadata"]["semantic_index_status"])

    def test_latest_endpoint_skips_stale_binding_and_recovers_matching_legacy_board(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_engine(Path(temp), movie={"duration": 300.0, "fingerprint": "source-a"})
            seed_passage(engine)
            project = engine.load(PROJECT_ID)
            project["evidence_researches"] = [
                {"id": "research-11111111", "created_at": "older", "board": BOARD},
                {
                    "id": "research-22222222", "created_at": "newer",
                    "source_fingerprint": "different-source",
                    "semantic_index_signature": engine.film_index(
                        PROJECT_ID
                    ).semantic_index_signature(),
                    "board": BOARD,
                },
            ]
            engine._save(project)

            with patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    response = client.get(f"/api/projects/{PROJECT_ID}/evidence/latest")

            self.assertEqual(200, response.status_code)
            payload = response.get_json()
            self.assertTrue(payload["available"])
            self.assertEqual("research-11111111", payload["research_id"])
            self.assertEqual(BOARD["evidence"], payload["evidence"])

            project = engine.load(PROJECT_ID)
            project["evidence_researches"] = []
            engine._save(project)
            with patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    unavailable = client.get(
                        f"/api/projects/{PROJECT_ID}/evidence/latest"
                    ).get_json()
            self.assertEqual({"available": False}, unavailable)


if __name__ == "__main__":
    unittest.main()
