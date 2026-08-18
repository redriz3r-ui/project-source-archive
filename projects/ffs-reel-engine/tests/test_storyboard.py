import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.storyboard as storyboard
import app as app_module
from src.engine import ReelEngine


BOARD = {"evidence": [
    {"id": 10, "title": "Q&A", "evidence_start": 100.0, "evidence_end": 130.0},
    {"id": 29, "title": "Phone", "evidence_start": 200.0, "evidence_end": 240.0},
]}

CONCEPT = {
    "title": "Conversation Is the Romance", "format": "analytical_argument",
    "hook": "Conversation is the romance.", "thesis": "Questions create intimacy.",
    "tone": "clear", "evidence_ids": [10, 29], "estimated_duration": 28,
    "warnings": [], "beats": [
        {"order": 1, "card_type": "hook", "evidence_id": 0,
         "text": "Conversation is the romance.", "duration_seconds": 2},
        {"order": 2, "card_type": "clip", "evidence_id": 10,
         "text": "The question game", "duration_seconds": 6},
        {"order": 3, "card_type": "observation", "evidence_id": 0,
         "text": "Questions make disclosure safer.", "duration_seconds": 4},
        {"order": 4, "card_type": "clip", "evidence_id": 29,
         "text": "The imaginary call", "duration_seconds": 7},
        {"order": 5, "card_type": "end_card", "evidence_id": 0,
         "text": "Fresno Film Society", "duration_seconds": 3},
    ],
}


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.project = {"movie": {"duration": 300.0}, "editorial_storyboards": []}

    def create(self):
        with patch.object(storyboard, "build_evidence_board", return_value=BOARD):
            return storyboard.create_storyboard(self.project, None, "intimacy", CONCEPT)

    def test_concept_becomes_ordered_editable_cards(self):
        result = self.create()
        self.assertEqual(["hook", "clip", "observation", "clip", "end_card"],
                         [card["type"] for card in result["cards"]])
        self.assertEqual((100.0, 106.0),
                         (result["cards"][1]["source_start"], result["cards"][1]["source_end"]))
        self.assertEqual(1, result["revision"])
        self.assertEqual(result["id"], self.project["active_storyboard_id"])
        self.assertTrue(result["captions_enabled"])

    def test_clip_quote_aligns_inside_long_evidence_passage(self):
        class FakeIndex:
            @staticmethod
            def raw_transcript():
                return [
                    {"start": 100.0, "end": 102.0, "text": "Earlier dialogue."},
                    {"start": 117.0, "end": 117.2, "text": "Wait."},
                    {"start": 122.0, "end": 123.2,
                     "text": "I have to say something stupid."},
                ]

        concept = copy.deepcopy(CONCEPT)
        concept["beats"][1]["text"] = "Wait. I have to say something stupid."
        concept["beats"][1]["anchor_quote"] = "Wait. I have to say something stupid."
        with patch.object(storyboard, "build_evidence_board", return_value=BOARD):
            result = storyboard.create_storyboard(
                self.project, FakeIndex(), "intimacy", concept
            )
        clip = result["cards"][1]
        self.assertAlmostEqual(116.7, clip["source_start"], places=2)
        self.assertAlmostEqual(123.65, clip["source_end"], places=2)
        self.assertEqual(100.0, clip["evidence_start"])
        self.assertEqual("transcript_anchor", clip["alignment_method"])
        self.assertGreater(clip["duration"], 6.0)

    def test_update_reorders_edits_and_clamps_to_evidence(self):
        result = self.create()
        raw = copy.deepcopy(list(reversed(result["cards"])))
        clip = next(card for card in raw if card["type"] == "clip" and card["evidence_id"] == 10)
        clip.update({"source_start": 0, "source_end": 999, "crop_x": 2,
                     "original_audio": False})
        updated = storyboard.update_storyboard(
            self.project, result["id"], {
                "revision": 1, "title": "Edited", "cards": raw,
                "captions_enabled": False,
            }
        )
        saved_clip = next(card for card in updated["cards"] if card["id"] == clip["id"])
        self.assertEqual((100.0, 110.0),
                         (saved_clip["source_start"], saved_clip["source_end"]))
        self.assertEqual(1.0, saved_clip["crop_x"])
        self.assertFalse(saved_clip["original_audio"])
        self.assertEqual("manual_trim", saved_clip["alignment_method"])
        self.assertFalse(saved_clip["timing_refined"])
        self.assertEqual(2, updated["revision"])
        self.assertEqual("Edited", updated["title"])
        self.assertFalse(updated["captions_enabled"])

    def test_stale_revision_does_not_modify_storyboard(self):
        result = self.create()
        before = copy.deepcopy(result)
        with self.assertRaisesRegex(ValueError, "changed in another save"):
            storyboard.update_storyboard(
                self.project, result["id"], {"revision": 0, "cards": result["cards"]}
            )
        self.assertEqual(before, result)

    def test_flask_create_get_update_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = ReelEngine(Path(temp))
            engine._save({
                "id": "test-film-123456", "title": "Test Film", "movie": {"duration": 300.0},
                "recipe": "mood_montage", "transcript": [], "candidates": [], "exports": [],
            })
            with patch.object(app_module, "engine", engine), \
                 patch.object(storyboard, "build_evidence_board", return_value=BOARD):
                with app_module.app.test_client() as client:
                    created = client.post("/api/projects/test-film-123456/storyboards", json={
                        "topic": "intimacy", "concept": CONCEPT,
                    })
                    self.assertEqual(200, created.status_code)
                    payload = created.get_json()
                    story_id = payload["storyboard"]["id"]
                    fetched = client.get(f"/api/projects/test-film-123456/storyboards/{story_id}")
                    self.assertEqual(200, fetched.status_code)
                    cards = fetched.get_json()["storyboard"]["cards"]
                    cards[0]["text"] = "Edited hook"
                    updated = client.patch(
                        f"/api/projects/test-film-123456/storyboards/{story_id}",
                        json={"revision": 1, "title": "Edited", "cards": cards,
                              "captions_enabled": False},
                    )
                    self.assertEqual(200, updated.status_code)
                    self.assertEqual("Edited hook", updated.get_json()["storyboard"]["cards"][0]["text"])
                    self.assertFalse(updated.get_json()["storyboard"]["captions_enabled"])
                    reloaded = client.get(
                        f"/api/projects/test-film-123456/storyboards/{story_id}"
                    )
                    self.assertFalse(reloaded.get_json()["storyboard"]["captions_enabled"])
                    page = client.get(f"/projects/test-film-123456/storyboards/{story_id}")
                    self.assertEqual(200, page.status_code)
                    self.assertIn(b"Editorial Storyboard", page.data)
                    self.assertIn(b'id="preview-caption"', page.data)


if __name__ == "__main__":
    unittest.main()
