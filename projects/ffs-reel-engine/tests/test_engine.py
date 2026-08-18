import tempfile
import unittest
from pathlib import Path

from src.engine import ReelEngine, parse_srt
from src.film_index import FilmIndex
from src.scene_map import normalize_transcript


class EngineTests(unittest.TestCase):
    def test_transcript_normalization_merges_clear_continuation(self):
        normalized = normalize_transcript([
            {"id": 1, "start": 0.0, "end": 1.0, "text": "I always thought that if"},
            {"id": 2, "start": 1.1, "end": 2.0, "text": "none of your friends knew."},
            {"id": 3, "start": 4.0, "end": 5.0, "text": "A new thought."},
        ])
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["source_ids"], [1, 2])

    def test_parse_srt_and_create_project(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subtitle = root / "movie.srt"
            subtitle.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nHello there.\n\n"
                "2\n00:00:04,000 --> 00:00:06,500\nHow are you?\n"
            )
            cues = parse_srt(subtitle)
            self.assertEqual(len(cues), 2)
            self.assertEqual(cues[1]["start"], 4.0)
            project = ReelEngine(root).create_project("Before Sunrise")
            self.assertEqual(project["recipe"], "mood_montage")
            self.assertTrue((root / "work" / "projects" / project["id"] / "project.json").exists())

    def test_film_index_persists_all_shots_and_future_layers(self):
        with tempfile.TemporaryDirectory() as folder:
            index = FilmIndex(Path(folder) / "film-index.sqlite3")
            shots = [
                {"start": 0.0, "end": 2.0, "shot_duration": 2.0},
                {"start": 2.0, "end": 5.5, "shot_duration": 3.5},
                {"start": 5.5, "end": 8.0, "shot_duration": 2.5},
            ]
            index.replace_shots(shots, 0.32, {0.0, 5.5})
            stats = index.stats()
            self.assertEqual(stats["counts"]["shots"], 3)
            self.assertEqual(stats["counts"]["browser_shots"], 2)
            self.assertEqual(stats["counts"]["transcript_segments"], 0)
            self.assertEqual(stats["metadata"]["shot_index_status"], "complete")
            index.append_transcript(
                [{"start": 1.0, "end": 2.4, "text": "A saved line of dialogue."}], 600.0
            )
            resumed = index.stats()
            self.assertEqual(resumed["counts"]["transcript_segments"], 1)
            self.assertEqual(resumed["metadata"]["transcript_completed_through"], 600.0)
            self.assertEqual(index.transcript_completed_through(), 600.0)


if __name__ == "__main__":
    unittest.main()
