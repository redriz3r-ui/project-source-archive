import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
import src.engine as engine_module
from src.engine import ReelEngine
from src.mood_montage import (
    balanced_mood_draft, choose_diverse_mood_moments, mood_recipe,
    validate_mood_draft,
)


PROJECT_ID = "test-film-123456"


def project_data(movie_path: str = "/tmp/movie.mp4") -> dict:
    candidates = []
    for index in range(12):
        start = index * 50.0
        candidates.append({
            "id": f"shot-{index:03d}", "start": start, "shot_end": start + 4.0,
            "shot_duration": 4.0, "duration": 2.2,
            "thumbnail": f"shot-{index:03d}.jpg",
        })
    return {
        "id": PROJECT_ID, "title": "Test Film",
        "movie": {"path": movie_path, "duration": 600.0,
                  "fingerprint": "fixture-fingerprint"},
        "recipe": "mood_montage", "transcript": [], "candidates": candidates,
        "shot_index": {"detected_count": 100, "displayed_count": 12}, "exports": [],
    }


class MoodMontageTests(unittest.TestCase):
    def test_balanced_draft_spreads_shots_and_targets_reel_length(self):
        draft = balanced_mood_draft(
            project_data(), clip_count=8, target_duration=28, label="Night movement"
        )
        self.assertEqual(8, len(draft["clips"]))
        self.assertEqual("Night movement", draft["label"])
        self.assertLess(draft["clips"][0]["start"], 100)
        self.assertGreater(draft["clips"][-1]["start"], 450)
        self.assertAlmostEqual(28.0, sum(item["duration"] for item in draft["clips"]))
        self.assertTrue(draft["end_card"])
        self.assertTrue(all(item["framing"] == "cinematic" for item in draft["clips"]))

    def test_validation_clamps_each_clip_and_rejects_duplicate_shots(self):
        project = project_data()
        draft = validate_mood_draft(project, {
            "label": "Test", "clips": [{
                "id": "shot-000", "start": -50, "duration": 20,
                "framing": "crop", "crop_x": 2, "original_audio": True,
            }], "end_card": True, "movie_audio_gain": 1.5,
        })
        clip = draft["clips"][0]
        self.assertEqual((0.0, 4.0), (clip["start"], clip["duration"]))
        self.assertEqual(1.0, clip["crop_x"])
        self.assertTrue(clip["original_audio"])
        self.assertEqual(1.5, draft["movie_audio_gain"])
        with self.assertRaisesRegex(ValueError, "unknown or duplicate"):
            validate_mood_draft(project, {
                "clips": [{"id": "shot-001"}, {"id": "shot-001"}],
            })

    def test_balanced_draft_and_edits_persist_through_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = ReelEngine(Path(temp))
            engine._save(project_data())
            with patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    created = client.post(
                        f"/api/projects/{PROJECT_ID}/montage/balanced-draft",
                        json={"clip_count": 8, "target_duration": 26, "label": "Warm city"},
                    )
                    self.assertEqual(200, created.status_code, created.get_json())
                    draft = created.get_json()["draft"]
                    draft["clips"][0]["framing"] = "crop"
                    draft["clips"][0]["crop_x"] = .75
                    draft["clips"][0]["original_audio"] = True
                    saved = client.patch(
                        f"/api/projects/{PROJECT_ID}/montage", json=draft
                    )
                    restored = client.get(f"/api/projects/{PROJECT_ID}/montage")
                    page = client.get(f"/projects/{PROJECT_ID}/montage")

            self.assertEqual(200, saved.status_code, saved.get_json())
            self.assertEqual(2, saved.get_json()["draft"]["revision"])
            clip = restored.get_json()["draft"]["clips"][0]
            self.assertEqual("crop", clip["framing"])
            self.assertEqual(.75, clip["crop_x"])
            self.assertTrue(clip["original_audio"])
            self.assertIn(PROJECT_ID.encode(), page.data)
            self.assertIn(b"MOOD MONTAGE V4", page.data)
            self.assertIn(b"Use movie audio on all clips", page.data)
            self.assertIn(b"Movie audio level", page.data)

    def test_mood_recipes_and_diversity_use_meaning_without_losing_coverage(self):
        self.assertIn("romantic", " ".join(mood_recipe("romantic")["queries"]))
        self.assertEqual(["hesitant intimacy"], mood_recipe(
            "custom", "hesitant intimacy"
        )["queries"])
        with self.assertRaisesRegex(ValueError, "Describe the custom mood"):
            mood_recipe("custom")
        searches = [[
            {"id": 1, "evidence_start": 10, "evidence_end": 20,
             "score": .92, "excerpt": "first"},
            {"id": 2, "evidence_start": 25, "evidence_end": 35,
             "score": .91, "excerpt": "neighbor"},
            {"id": 3, "evidence_start": 300, "evidence_end": 310,
             "score": .86, "excerpt": "middle"},
            {"id": 4, "evidence_start": 570, "evidence_end": 580,
             "score": .84, "excerpt": "ending"},
        ]]
        chosen = choose_diverse_mood_moments(searches, clip_count=3, movie_duration=600)
        self.assertEqual(3, len(chosen))
        self.assertEqual(3, len({item["id"] for item in chosen}))
        self.assertLess(chosen[0]["evidence_start"], 50)
        self.assertGreater(chosen[-1]["evidence_start"], 500)

    def test_mood_aware_route_maps_visual_matches_to_detected_shots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")
            project = project_data(str(movie))
            project["visual_montage_index"] = {
                "status": "complete", "source_fingerprint": "fixture-fingerprint",
                "samples": [{"sample_id": 1}],
            }
            engine = ReelEngine(root)
            engine._save(project)
            asset_dir = root / "dense-assets"
            asset_dir.mkdir()
            for index in range(10):
                (asset_dir / f"dense-shot-{index + 1:04d}.jpg").write_bytes(b"image")
            detected = [{"id": index + 1, "start": index * 50.0,
                         "end": index * 50.0 + 8, "duration": 8.0}
                        for index in range(12)]
            fake_index = SimpleNamespace(shots=lambda: detected)

            def fake_search(_index, query, limit=24):
                self.assertTrue(query)
                return [{
                    "id": index + 1, "scene_id": index + 1,
                    "start": index * 50.0, "end": index * 50.0 + 8,
                    "sample_id": index + 1, "timestamp": index * 50.0 + 3,
                    "shot_start": index * 50.0, "shot_end": index * 50.0 + 8,
                    "filename": f"dense-shot-{index + 1:04d}.jpg",
                    "evidence_start": index * 50.0,
                    "evidence_end": index * 50.0 + 8,
                    "score": .92 - index * .02,
                    "excerpt": f"romantic passage {index}",
                } for index in range(10)]

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"image")
                return SimpleNamespace(returncode=0, stderr="", stdout="")

            targeted = {
                "id": "1234abcd", "status": "complete", "sample_count": 10,
                "regions": [{"start": 0, "end": 500}], "asset_dir": str(asset_dir),
            }
            with patch.object(engine, "film_index", return_value=fake_index), \
                 patch.object(engine, "_targeted_mood_index", return_value=(targeted, False)), \
                 patch.object(engine_module, "search_visual_montage", side_effect=fake_search), \
                 patch.object(engine_module.subprocess, "run", side_effect=fake_run), \
                 patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/montage/mood-draft",
                        json={"mood_style": "romantic", "clip_count": 6,
                              "target_duration": 24, "label": "Connection"},
                    )

            self.assertEqual(200, response.status_code, response.get_json())
            payload = response.get_json()
            draft = payload["draft"]
            self.assertEqual("romantic", draft["mood_style"])
            self.assertEqual("targeted_visual_index", draft["selection_method"])
            self.assertEqual(6, len(draft["clips"]))
            self.assertTrue(all(clip.get("selection_reason") for clip in draft["clips"]))
            self.assertTrue(all(not clip["original_audio"] for clip in draft["clips"]))
            self.assertIn("targeted regions", payload["selection"]["privacy"])
            self.assertFalse(payload["selection"]["index_reused"])
            restored = engine.load(PROJECT_ID)["mood_montage_draft"]
            self.assertEqual("romantic", restored["mood_style"])

    def test_export_uses_saved_per_clip_controls_and_ffs_cards(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")
            engine = ReelEngine(root)
            project = project_data(str(movie))
            project["mood_montage_draft"] = validate_mood_draft(project, {
                "label": "Test", "clips": [{
                    "id": "shot-000", "framing": "crop", "crop_x": .8,
                    "original_audio": True, "start": 0, "duration": 2.5,
                }], "opening_card": True, "opening_text": "One night",
                "end_card": True, "end_text": "FILM LIVES HERE",
                "movie_audio_gain": 1.35,
            })
            engine._save(project)
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                destination = Path(command[-1])
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"video")
                return SimpleNamespace(returncode=0, stderr="", stdout="")

            def fake_card(_project, card, destination, _work, _number):
                destination.write_bytes(b"card")
                return float(card["duration"])

            with patch.object(engine_module.subprocess, "run", fake_run), \
                 patch.object(engine_module, "_render_text_card", fake_card):
                record = engine.export_montage(PROJECT_ID, {"use_saved_draft": True})

            self.assertEqual(7.1, record["duration"])
            self.assertTrue(record["opening_card"])
            self.assertTrue(record["end_card"])
            clip_command = next(command for command in commands if "-ss" in command)
            self.assertIn("(in_w-out_w)*0.8000", clip_command[clip_command.index("-vf") + 1])
            self.assertNotIn("anullsrc=r=48000:cl=stereo", clip_command)
            self.assertEqual("volume=1.350", clip_command[clip_command.index("-af") + 1])
            self.assertEqual(1.35, record["movie_audio_gain"])
            persisted = engine.load(PROJECT_ID)["mood_montage_draft"]
            self.assertEqual(record, persisted["latest_export"])


if __name__ == "__main__":
    unittest.main()
