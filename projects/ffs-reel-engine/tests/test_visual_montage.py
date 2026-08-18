import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import app as app_module
import src.engine as engine_module
import src.visual_montage as visual_module
from src.engine import ReelEngine
from src.visual_montage import (
    detect_targeted_shots, extract_visual_samples, search_visual_montage,
)


PROJECT_ID = "visual-film-123456"


def project_data(movie_path: str) -> dict:
    return {
        "id": PROJECT_ID, "title": "Visual Film", "recipe": "mood_montage",
        "movie": {"path": movie_path, "duration": 600.0,
                  "fingerprint": "visual-fingerprint"},
        "transcript": [], "candidates": [], "exports": [],
    }


class VisualMontageTests(unittest.TestCase):
    def test_targeted_detection_discovers_cuts_and_splits_long_misses(self):
        movie = Path("/tmp/movie.mp4")
        outputs = [
            SimpleNamespace(returncode=0, stderr="pts_time:2.0\npts_time:5.0\n", stdout=""),
            SimpleNamespace(returncode=0, stderr="", stdout=""),
        ]
        with patch.object(visual_module.subprocess, "run", side_effect=outputs):
            shots, regions = detect_targeted_shots(
                movie, [{"start": 100, "end": 110}, {"start": 200, "end": 220}],
                duration=600,
            )
        self.assertEqual(2, len(regions))
        self.assertTrue(any(abs(item["shot_start"] - 102) < .01 for item in shots))
        fallback = [item for item in shots if item["boundary_method"] == "dense_fallback"]
        self.assertEqual(4, len(fallback))
        self.assertEqual((200, 205), (fallback[0]["shot_start"], fallback[0]["shot_end"]))

    def test_extract_visual_samples_covers_full_runtime_and_reuses_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")
            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                Path(command[-1]).write_bytes(b"jpeg")
                return SimpleNamespace(returncode=0, stderr="", stdout="")

            with patch.object(visual_module.subprocess, "run", side_effect=fake_run):
                samples = extract_visual_samples(
                    movie, root / "frames", duration=600, sample_count=24
                )
                repeated = extract_visual_samples(
                    movie, root / "frames", duration=600, sample_count=24
                )

            self.assertEqual(24, len(samples))
            self.assertEqual(12.5, samples[0]["timestamp"])
            self.assertEqual(587.5, samples[-1]["timestamp"])
            self.assertEqual(24, len(calls))
            self.assertEqual(samples, repeated)

    def test_visual_search_ranks_frame_descriptions_by_local_embedding(self):
        one = np.array([1.0, 0.0], dtype=np.float32)
        two = np.array([0.0, 1.0], dtype=np.float32)
        index = {"status": "complete", "samples": [
            {"sample_id": 1, "timestamp": 100, "summary": "building facade",
             "embedding": base64.b64encode(one.tobytes()).decode()},
            {"sample_id": 2, "timestamp": 200, "summary": "close conversation",
             "embedding": base64.b64encode(two.tobytes()).decode()},
        ]}
        model = SimpleNamespace(encode_query=lambda *args, **kwargs: one)
        with patch.object(visual_module, "_model", return_value=model):
            results = search_visual_montage(index, "architecture")
        self.assertEqual(1, results[0]["sample_id"])
        self.assertEqual("building facade", results[0]["excerpt"])
        self.assertEqual(1.0, results[0]["score"])

    def test_visual_index_route_persists_metadata_without_returning_embeddings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "movie.mp4"
            movie.write_bytes(b"movie")
            engine = ReelEngine(root)
            engine._save(project_data(str(movie)))
            built = {
                "status": "complete", "created_at": "now", "sample_count": 72,
                "visual_model": "visual-test", "embedding_model": "embed-test",
                "source_fingerprint": "visual-fingerprint",
                "samples": [{"sample_id": 1, "embedding": "secret-vector"}],
            }
            with patch.object(engine_module, "build_visual_montage_index",
                              return_value=built), \
                 patch.object(app_module, "engine", engine):
                with app_module.app.test_client() as client:
                    response = client.post(
                        f"/api/projects/{PROJECT_ID}/montage/visual-index",
                        json={"sample_count": 72},
                    )
                    montage = client.get(f"/api/projects/{PROJECT_ID}/montage")

            self.assertEqual(200, response.status_code, response.get_json())
            self.assertNotIn("samples", response.get_json())
            self.assertEqual(72, montage.get_json()["visual_index"]["sample_count"])
            saved = engine.load(PROJECT_ID)["visual_montage_index"]
            self.assertEqual("secret-vector", saved["samples"][0]["embedding"])


if __name__ == "__main__":
    unittest.main()
