import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
import src.clip_refinement as refinement
import src.engine as engine_module
from src.engine import ReelEngine
from src.film_index import FilmIndex


PROJECT_ID = "test-film-123456"
STORY_ID = "story-1234abcd"
CARD_ID = "card-1234abcd"


def clip_card() -> dict:
    return {
        "id": CARD_ID, "type": "clip", "text": "The admission",
        "duration": 6.0, "evidence_id": 10, "scene_id": 4,
        "scene_title": "Admission", "source_start": 18.0, "source_end": 24.0,
        "evidence_start": 10.0, "evidence_end": 40.0,
        "anchor_quote": "Wait, I have to say something stupid.",
        "anchor_start": 19.5, "anchor_end": 22.0,
        "alignment_method": "transcript_anchor", "alignment_score": 0.94,
        "original_audio": True, "crop_x": 0.5,
    }


class CachedIndex:
    def transcript_words(self, start, end):
        return [
            {"start": 20.0, "end": 20.2, "text": "Wait", "source": "full_transcript"},
            {"start": 20.2, "end": 20.35, "text": "I", "source": "full_transcript"},
            {"start": 20.35, "end": 20.55, "text": "have", "source": "full_transcript"},
            {"start": 20.55, "end": 20.7, "text": "to", "source": "full_transcript"},
            {"start": 20.7, "end": 21.0, "text": "say", "source": "full_transcript"},
            {"start": 21.0, "end": 21.35, "text": "something", "source": "full_transcript"},
            {"start": 21.35, "end": 21.75, "text": "stupid", "source": "full_transcript"},
        ]

    def add_transcript_words(self, words, source):
        raise AssertionError("cached words should avoid retranscription")


class ClipRefinementTests(unittest.TestCase):
    def test_word_anchor_uses_cached_words_and_snaps_to_nearby_silence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")

            def fake_audio(_movie, _start, _end, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"audio")

            with patch.object(refinement, "_extract_audio", fake_audio), \
                 patch.object(
                     refinement, "_silences",
                     return_value=[(19.1, 19.95), (25.5, 26.0)],
                 ), \
                 patch.object(
                     refinement, "_transcribe_words",
                     side_effect=AssertionError("cached words should avoid Whisper"),
                 ):
                result = refinement.refine_clip_alignment(
                    CachedIndex(), movie, clip_card(), root / "work", root
                )

            self.assertEqual("word_anchor_silence_snap", result["alignment_method"])
            self.assertEqual("cached_word_timestamps", result["timing_source"])
            self.assertEqual((20.0, 21.75), (result["anchor_start"], result["anchor_end"]))
            self.assertEqual(19.87, result["source_start"])
            self.assertEqual(25.58, result["source_end"])
            self.assertTrue(result["timing_refined"])

    def test_word_timestamp_table_persists_and_filters_ranges(self):
        with tempfile.TemporaryDirectory() as temp:
            index = FilmIndex(Path(temp) / "index.sqlite3")
            index.append_transcript(
                [{"start": 1.0, "end": 2.0, "text": "hello there"}], 2.0,
                [
                    {"start": 1.0, "end": 1.3, "text": "hello", "confidence": .9},
                    {"start": 1.4, "end": 1.8, "text": "there", "confidence": .8},
                ],
            )
            self.assertEqual(2, index.stats()["counts"]["transcript_words"])
            self.assertEqual(["there"], [item["text"] for item in index.transcript_words(1.35, 2.0)])
            index.reset_transcript()
            self.assertEqual(0, index.stats()["counts"]["transcript_words"])

    def test_refinement_route_updates_only_the_requested_clip_and_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")
            engine = ReelEngine(root)
            card = clip_card()
            engine._save({
                "id": PROJECT_ID, "title": "Test Film",
                "movie": {"path": str(movie), "duration": 100.0},
                "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
                "editorial_storyboards": [{
                    "id": STORY_ID, "title": "Test Story", "topic": "intimacy",
                    "format": "analytical_argument", "hook": "A hook", "thesis": "A thesis",
                    "tone": "clear", "warnings": [], "status": "draft",
                    "cards": [card], "captions_enabled": True, "revision": 3,
                    "created_at": "now", "updated_at": "now",
                }],
            })
            refined = {
                "source_start": 19.8, "source_end": 25.8, "duration": 6.0,
                "anchor_start": 20.0, "anchor_end": 21.75,
                "alignment_method": "word_anchor_silence_snap", "alignment_score": 1.0,
                "timing_source": "mlx_whisper_refinement", "timing_refined": True,
            }
            with patch.object(app_module, "engine", engine), \
                 patch.object(engine_module, "refine_clip_alignment", return_value=refined):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/storyboards/{STORY_ID}/cards/{CARD_ID}/refine",
                        json={},
                    )

            self.assertEqual(200, response.status_code, response.get_json())
            story = response.get_json()["storyboard"]
            self.assertEqual(4, story["revision"])
            self.assertEqual(19.8, story["cards"][0]["source_start"])
            self.assertEqual("word_anchor_silence_snap", story["cards"][0]["alignment_method"])
            persisted = engine.load(PROJECT_ID)["editorial_storyboards"][0]
            self.assertEqual(story, persisted)


if __name__ == "__main__":
    unittest.main()
