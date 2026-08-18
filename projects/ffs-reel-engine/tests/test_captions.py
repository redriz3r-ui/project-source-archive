import tempfile
import unittest
from pathlib import Path

from src.captions import extract_clip_captions, write_ass_captions


class CaptionTests(unittest.TestCase):
    def test_clip_boundaries_short_extension_and_next_cue_limit(self):
        segments = [
            {"start": 8.0, "end": 9.0, "text": "outside before"},
            {"start": 9.8, "end": 10.1, "text": "starts before the clip"},
            {"start": 10.3, "end": 10.4, "text": "brief"},
            {"start": 10.6, "end": 11.2, "text": "ends after the clip"},
            {"start": 11.0, "end": 12.0, "text": "outside after"},
        ]
        cues = extract_clip_captions(segments, 10.0, 11.0)

        self.assertEqual(3, len(cues))
        self.assertEqual(
            (0.0, 0.3, 10.0, 10.3),
            tuple(cues[0][key] for key in ("start", "end", "source_start", "source_end")),
        )
        self.assertEqual(
            (0.3, 0.6, 10.3, 10.6),
            tuple(cues[1][key] for key in ("start", "end", "source_start", "source_end")),
        )
        self.assertEqual(
            (0.6, 1.0, 10.6, 11.0),
            tuple(cues[2][key] for key in ("start", "end", "source_start", "source_end")),
        )
        self.assertTrue(all(left["end"] <= right["start"] for left, right in zip(cues, cues[1:])))

    def test_isolated_short_cue_extends_and_long_copy_is_two_readable_lines(self):
        text = "This is a deliberately long subtitle line that would be difficult to read in a Reel without safe wrapping and limiting."
        cue = extract_clip_captions(
            [{"start": 20.1, "end": 20.2, "text": text}], 20.0, 21.0
        )[0]
        self.assertEqual((0.1, 0.85, 20.1, 20.85),
                         (cue["start"], cue["end"], cue["source_start"], cue["source_end"]))
        lines = cue["text"].splitlines()
        self.assertLessEqual(len(lines), 2)
        self.assertTrue(all(len(line) <= 34 for line in lines))
        self.assertTrue(lines[-1].endswith("…"))

    def test_ass_is_vertical_branded_safe_and_escapes_override_text(self):
        cue = {
            "start": 0.0, "end": 0.45,
            "text": "Never {\\an8} trust \\N input\nsecond line",
        }
        with tempfile.TemporaryDirectory() as temp:
            path = write_ass_captions([cue], Path(temp) / "captions.ass")
            content = path.read_text(encoding="utf-8")

        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1920", content)
        self.assertIn("Arial,64,&H00FFFFFF", content)
        self.assertIn(",3,4,0,2,70,70,320,1", content)
        self.assertIn("0:00:00.00,0:00:00.45", content)
        self.assertNotIn("{\\an8}", content)
        self.assertIn("｛＼an8｝", content)
        self.assertIn(r"\Nsecond line", content)

    def test_invalid_clip_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "end after start"):
            extract_clip_captions([], 10.0, 10.0)


if __name__ == "__main__":
    unittest.main()
