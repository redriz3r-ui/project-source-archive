import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.editorial_renderer import EditorialRenderError, render_editorial_storyboard


def sample_storyboard():
    return {
        "cards": [
            {"type": "hook", "text": "Don’t miss this: 100% intimate.", "duration": 2.5},
            {
                "type": "clip", "text": "First clip", "source_start": 12.25,
                "source_end": 18.75, "crop_x": 0.75, "original_audio": True,
            },
            {"type": "observation", "text": "Notice what the question permits.", "duration": 3},
            {
                "type": "clip", "text": "Second clip", "source_start": 30,
                "source_end": 34, "crop_x": 0.1, "original_audio": False,
            },
            {"type": "interpretation", "text": "Language makes vulnerability safer.", "duration": 4},
            {"type": "end_card", "text": "FILM LIVES HERE", "duration": 3},
        ]
    }


class RecordingRunner:
    def __init__(self, fail_at=None):
        self.commands = []
        self.fail_at = fail_at

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if self.fail_at is not None and len(self.commands) == self.fail_at:
            return SimpleNamespace(returncode=1, stderr="simulated ffmpeg failure")
        return SimpleNamespace(returncode=0, stderr="")


class EditorialRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.movie = self.root / "source movie.mp4"
        self.movie.write_bytes(b"source-movie-must-remain-unchanged")
        self.project = {"title": "Before Sunrise", "movie": {"path": str(self.movie)}}
        self.work = self.root / "render work"
        self.output = self.root / "outputs" / "editorial-reel.mp4"

    def tearDown(self):
        self.temp.cleanup()

    def test_mixed_storyboard_uses_uniform_segment_contract_and_ordered_concat(self):
        runner = RecordingRunner()
        with patch("src.editorial_renderer._RUNNER", runner):
            result = render_editorial_storyboard(
                self.project, sample_storyboard(), self.work, self.output
            )

        self.assertEqual({
            "duration": 23.0, "card_count": 6, "clip_count": 2,
            "captions_enabled": True, "caption_cue_count": 0,
        }, result)
        self.assertEqual(7, len(runner.commands))
        segment_commands = runner.commands[:-1]
        for index, command in enumerate(segment_commands):
            self.assertEqual(
                str((self.work / f"segment-{index:03d}.mp4").resolve()), command[-1]
            )
            for pair in [
                ("-r", "30"), ("-c:v", "libx264"), ("-pix_fmt", "yuv420p"),
                ("-c:a", "aac"), ("-ar", "48000"), ("-ac", "2"),
            ]:
                position = command.index(pair[0])
                self.assertEqual(pair[1], command[position + 1])

        concat = self.work / "concat.txt"
        expected_order = [
            str((self.work / f"segment-{index:03d}.mp4").resolve()) for index in range(6)
        ]
        self.assertEqual(
            expected_order,
            [line.removeprefix("file '").removesuffix("'") for line in concat.read_text().splitlines()],
        )
        assembly = runner.commands[-1]
        self.assertEqual("copy", assembly[assembly.index("-c") + 1])
        self.assertEqual("+faststart", assembly[assembly.index("-movflags") + 1])
        self.assertEqual(str(self.output.resolve()), assembly[-1])
        self.assertEqual(b"source-movie-must-remain-unchanged", self.movie.read_bytes())

    def test_clips_keep_exact_range_crop_and_requested_audio_mode(self):
        runner = RecordingRunner()
        with patch("src.editorial_renderer._RUNNER", runner):
            render_editorial_storyboard(self.project, sample_storyboard(), self.work, self.output)

        original_audio = runner.commands[1]
        self.assertEqual("12.25", original_audio[original_audio.index("-ss") + 1])
        self.assertEqual("6.5", original_audio[original_audio.index("-t") + 1])
        self.assertIn("(in_w-out_w)*0.7500", original_audio[original_audio.index("-vf") + 1])
        self.assertEqual("0:a:0", original_audio[original_audio.index("-map", original_audio.index("-map") + 1) + 1])
        self.assertNotIn("anullsrc=r=48000:cl=stereo", original_audio)

        silent = runner.commands[3]
        self.assertEqual("30", silent[silent.index("-ss") + 1])
        self.assertEqual("4", silent[silent.index("-t") + 1])
        self.assertIn("(in_w-out_w)*0.1000", silent[silent.index("-vf") + 1])
        self.assertIn("anullsrc=r=48000:cl=stereo", silent)
        maps = [silent[index + 1] for index, value in enumerate(silent[:-1]) if value == "-map"]
        self.assertEqual(["0:v:0", "1:a:0"], maps)

    def test_editable_copy_is_kept_out_of_filter_commands_and_styles_are_distinct(self):
        runner = RecordingRunner()
        storyboard = sample_storyboard()
        risky_copy = storyboard["cards"][0]["text"]
        with patch("src.editorial_renderer._RUNNER", runner):
            render_editorial_storyboard(self.project, storyboard, self.work, self.output)

        command_text = " ".join(" ".join(command) for command in runner.commands)
        self.assertNotIn(risky_copy, command_text)
        rendered_copy = " ".join((self.work / "card-001-body.txt").read_text().split())
        self.assertEqual(risky_copy, rendered_copy)
        self.assertIn("Before Sunrise".upper(), (self.work / "card-006-title.txt").read_text())
        filters = [runner.commands[index][runner.commands[index].index("-vf") + 1]
                   for index in (0, 2, 4, 5)]
        self.assertEqual(4, len(set(filters)))
        for video_filter in filters:
            self.assertIn("textfile=", video_filter)
            self.assertIn("expansion=none", video_filter)

    def test_clip_captions_are_burned_and_reported_while_text_cards_stay_unchanged(self):
        runner = RecordingRunner()
        transcript = [
            {"start": 12.0, "end": 12.5, "text": "Begins before."},
            {"start": 13.0, "end": 14.0, "text": "A first caption."},
            {"start": 31.0, "end": 31.1, "text": "Brief second caption."},
            {"start": 40.0, "end": 41.0, "text": "Outside both clips."},
        ]
        with patch("src.editorial_renderer._RUNNER", runner):
            result = render_editorial_storyboard(
                self.project, sample_storyboard(), self.work, self.output,
                transcript_segments=transcript,
            )

        self.assertTrue(result["captions_enabled"])
        self.assertEqual(3, result["caption_cue_count"])
        for command_index in (1, 3):
            video_filter = runner.commands[command_index][runner.commands[command_index].index("-vf") + 1]
            self.assertIn("subtitles=filename=", video_filter)
            self.assertIn("captions.ass", video_filter)
        for command_index in (0, 2, 4, 5):
            video_filter = runner.commands[command_index][runner.commands[command_index].index("-vf") + 1]
            self.assertNotIn("subtitles=", video_filter)
        self.assertTrue((self.work / "card-002-captions.ass").is_file())
        self.assertTrue((self.work / "card-004-captions.ass").is_file())

    def test_storyboard_can_disable_captions(self):
        runner = RecordingRunner()
        storyboard = sample_storyboard()
        storyboard["captions_enabled"] = False
        transcript = [{"start": 13.0, "end": 14.0, "text": "Should not be burned."}]
        with patch("src.editorial_renderer._RUNNER", runner):
            result = render_editorial_storyboard(
                self.project, storyboard, self.work, self.output,
                transcript_segments=transcript,
            )

        self.assertFalse(result["captions_enabled"])
        self.assertEqual(0, result["caption_cue_count"])
        self.assertNotIn("subtitles=", " ".join(" ".join(command) for command in runner.commands))

    def test_invalid_timing_and_ffmpeg_failures_raise_module_error(self):
        invalid = sample_storyboard()
        invalid["cards"][1]["source_end"] = invalid["cards"][1]["source_start"]
        runner = RecordingRunner()
        with patch("src.editorial_renderer._RUNNER", runner):
            with self.assertRaisesRegex(EditorialRenderError, "end time after"):
                render_editorial_storyboard(self.project, invalid, self.work, self.output)

        failing = RecordingRunner(fail_at=1)
        with patch("src.editorial_renderer._RUNNER", failing):
            with self.assertRaisesRegex(EditorialRenderError, "simulated ffmpeg failure"):
                render_editorial_storyboard(
                    self.project, sample_storyboard(), self.work, self.output
                )
        self.assertEqual(b"source-movie-must-remain-unchanged", self.movie.read_bytes())


if __name__ == "__main__":
    unittest.main()
