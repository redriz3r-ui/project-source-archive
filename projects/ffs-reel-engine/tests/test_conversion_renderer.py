import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from src.conversion_renderer import (
    ConversionRenderError, default_conversion_config, normalize_conversion_config,
    render_conversion_reel,
)
from src.engine import ReelEngine


class RecordingRunner:
    def __init__(self):
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        return SimpleNamespace(returncode=0, stderr="")


class ConversionRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.movie = self.root / "movie.mp4"
        self.movie.write_bytes(b"movie")
        self.assets = self.root / "assets"
        self.assets.mkdir()
        (self.assets / "ffs-square.png").write_bytes(b"logo")
        self.project = {
            "title": "Before Sunrise",
            "movie": {"path": str(self.movie), "duration": 28.0},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_default_is_an_eighteen_second_trailer_overlay(self):
        config = default_conversion_config(self.project)
        self.assertEqual("conversion_overlay", config["mode"])
        self.assertEqual(6, len(config["slots"]))
        self.assertEqual(18, sum(slot["duration"] for slot in config["slots"]))
        self.assertEqual(2, sum(slot["kind"] == "venue" for slot in config["slots"]))
        self.assertTrue(config["persistent_logo"])
        self.assertTrue(all(slot["audio_mode"] == "silent" for slot in config["slots"]))

    def test_normalization_validates_slots_and_missing_venue_media(self):
        config = default_conversion_config(self.project)
        config["slots"][1]["media_path"] = str(self.root / "missing.mp4")
        with self.assertRaisesRegex(ConversionRenderError, "does not exist"):
            normalize_conversion_config(self.project, config)

    def test_render_uses_one_command_per_slot_then_ordered_concat(self):
        config = default_conversion_config(self.project)
        config["event"].update({
            "year": "1995", "date": "AUGUST 27", "time": "7:30 PM",
            "venue": "ISLA TEA LOUNGE", "city": "FRESNO",
        })
        runner = RecordingRunner()
        work = self.root / "work"
        output = self.root / "output.mp4"
        with patch("src.conversion_renderer._RUNNER", runner):
            result = render_conversion_reel(
                self.project, config, work, output, self.assets
            )
        self.assertEqual(18, result["duration"])
        self.assertEqual(6, result["slot_count"])
        self.assertEqual(2, result["venue_slot_count"])
        self.assertEqual(7, len(runner.commands))
        for command in runner.commands[:-1]:
            joined = " ".join(command)
            self.assertIn("textfile=", joined)
            self.assertIn("ffs-square.png", joined)
            self.assertNotIn("SPEND ONE NIGHT", joined)
        self.assertEqual("copy", runner.commands[-1][runner.commands[-1].index("-c") + 1])

    def test_original_and_reduced_audio_are_mapped_from_source(self):
        config = default_conversion_config(self.project)
        config["slots"][0]["audio_mode"] = "original"
        config["slots"][1]["audio_mode"] = "reduced"
        runner = RecordingRunner()
        with patch("src.conversion_renderer._RUNNER", runner):
            render_conversion_reel(
                self.project, config, self.root / "audio-work",
                self.root / "audio-output.mp4", self.assets,
            )
        first = " ".join(runner.commands[0])
        second = " ".join(runner.commands[1])
        self.assertIn("[0:a:0]volume=1.000", first)
        self.assertIn("[0:a:0]volume=0.250", second)
        self.assertIn("-map [audio]", first)

    def test_conversion_routes_create_edit_and_persist_configuration(self):
        engine = ReelEngine(self.root / "engine")
        project = engine.create_project("Before Sunrise")
        saved = engine.load(project["id"])
        saved["movie"] = {"path": str(self.movie), "duration": 28.0}
        engine._save(saved)
        with patch.object(app_module, "engine", engine):
            with app_module.app.test_client() as client:
                page = client.get(f"/projects/{project['id']}/conversion")
                self.assertEqual(200, page.status_code)
                self.assertIn(b"Conversion Mode", page.data)
                fetched = client.get(f"/api/projects/{project['id']}/conversion")
                self.assertEqual(200, fetched.status_code)
                config = fetched.get_json()["config"]
                config["event"].update({"date": "AUGUST 27", "time": "7:30 PM"})
                saved_response = client.put(
                    f"/api/projects/{project['id']}/conversion", json=config
                )
                self.assertEqual(200, saved_response.status_code)
                reloaded = client.get(f"/api/projects/{project['id']}/conversion")
                self.assertEqual("AUGUST 27", reloaded.get_json()["config"]["event"]["date"])


if __name__ == "__main__":
    unittest.main()
