import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
import src.engine as engine_module
from src.editorial_renderer import EditorialRenderError
from src.engine import ReelEngine


STORYBOARD_ID = "story-deadbeef"


def saved_project(root: Path) -> ReelEngine:
    engine = ReelEngine(root)
    movie = root / "movie.mp4"
    movie.write_bytes(b"fixture")
    engine._save({
        "id": "test-film-123456", "title": "Test Film",
        "movie": {"path": str(movie), "duration": 30.0},
        "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
        "editorial_storyboards": [{
            "id": STORYBOARD_ID, "title": "A saved argument", "status": "draft",
            "cards": [{"id": "card-12345678", "type": "hook",
                       "text": "A hook", "duration": 2.0}, {
                "id": "card-87654321", "type": "clip", "text": "A line",
                "duration": 3.0, "source_start": 5.0, "source_end": 8.0,
                "evidence_start": 0.0, "evidence_end": 30.0,
                "crop_x": 0.5, "original_audio": True,
            }],
        }],
    })
    engine.film_index("test-film-123456").append_transcript([
        {"start": 4.8, "end": 5.2, "text": "Begins before the clip."},
        {"start": 6.0, "end": 7.0, "text": "Caption me."},
        {"start": 9.0, "end": 10.0, "text": "Outside the clip."},
    ], 30.0)
    return engine


class EditorialExportRouteTests(unittest.TestCase):
    def test_export_route_renders_and_persists_record(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            calls = []

            def fake_renderer(project, storyboard, work_dir, output_path, *,
                              transcript_segments=None):
                calls.append((project, storyboard, work_dir, output_path, transcript_segments))
                output_path.write_bytes(b"rendered reel")
                return {"duration": 31.5, "card_count": len(storyboard["cards"]),
                        "captions_enabled": True, "caption_cue_count": 2}

            with patch.object(app_module, "engine", engine), \
                 patch.object(engine_module, "render_editorial_storyboard", fake_renderer):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/test-film-123456/storyboards/{STORYBOARD_ID}/export"
                    )

            self.assertEqual(200, response.status_code)
            record = response.get_json()
            self.assertEqual("editorial_storyboard", record["type"])
            self.assertEqual(STORYBOARD_ID, record["storyboard_id"])
            self.assertEqual(31.5, record["duration"])
            self.assertTrue((engine.outputs / record["filename"]).is_file())
            self.assertEqual(1, len(calls))
            self.assertIn("editorial-render-", calls[0][2].name)
            self.assertEqual("Caption me.", calls[0][4][1]["text"])

            persisted = engine.load("test-film-123456")
            self.assertEqual(record["filename"], persisted["exports"][0]["filename"])
            self.assertEqual(
                record["filename"],
                persisted["editorial_storyboards"][0]["latest_export"]["filename"],
            )

    def test_get_storyboard_returns_absolute_and_relative_preview_cues(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            with patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    response = client.get(
                        f"/api/projects/test-film-123456/storyboards/{STORYBOARD_ID}"
                    )

            self.assertEqual(200, response.status_code)
            cues = response.get_json()["clip_captions"]["card-87654321"]
            self.assertEqual(2, len(cues))
            self.assertEqual(0.0, cues[0]["start"])
            self.assertEqual(5.0, cues[0]["source_start"])
            self.assertEqual("Caption me.", cues[1]["text"])

    def test_timing_update_returns_refreshed_preview_cues(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            with patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    current = client.get(
                        f"/api/projects/test-film-123456/storyboards/{STORYBOARD_ID}"
                    ).get_json()["storyboard"]
                    clip = next(card for card in current["cards"] if card["type"] == "clip")
                    clip["source_end"] = 10.0
                    response = client.patch(
                        f"/api/projects/test-film-123456/storyboards/{STORYBOARD_ID}",
                        json={"revision": 1, "cards": current["cards"]},
                    )

            self.assertEqual(200, response.status_code)
            cues = response.get_json()["clip_captions"]["card-87654321"]
            self.assertEqual(3, len(cues))
            self.assertEqual("Outside the clip.", cues[-1]["text"])

    def test_renderer_error_is_reported_without_persisting_export(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            with patch.object(app_module, "engine", engine), \
                 patch.object(
                     engine_module, "render_editorial_storyboard",
                     side_effect=EditorialRenderError("Card 2 could not be rendered."),
                 ):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/test-film-123456/storyboards/{STORYBOARD_ID}/export"
                    )

            self.assertEqual(400, response.status_code)
            self.assertIn("Card 2", response.get_json()["error"])
            persisted = engine.load("test-film-123456")
            self.assertEqual([], persisted["exports"])
            self.assertNotIn("latest_export", persisted["editorial_storyboards"][0])

    def test_unknown_storyboard_does_not_call_renderer(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = saved_project(Path(temp))
            with patch.object(app_module, "engine", engine), \
                 patch.object(engine_module, "render_editorial_storyboard") as renderer:
                with app_module.app.test_client() as client:
                    response = client.post(
                        "/api/projects/test-film-123456/storyboards/story-cafebabe/export"
                    )
            self.assertEqual(400, response.status_code)
            renderer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
