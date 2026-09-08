import tempfile
import unittest
from pathlib import Path

from led_agent.compiler import compile_prompt
from led_agent.web_preview import build_preview


class WebPreviewTests(unittest.TestCase):
    def test_preview_embeds_production_frames_and_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            path=build_preview(compile_prompt("ocean waves"),Path(directory)/"preview.html",fps=4,seconds=1)
            text=path.read_text()
            self.assertIn('canvas width="53" height="11"',text)
            self.assertIn('id="toggle"',text)
            self.assertIn('const frames=[',text)


if __name__=="__main__": unittest.main()
