import base64
import tempfile
import unittest
from pathlib import Path

from led_agent.canvas import Canvas
from led_agent.compiler import compile_prompt
from led_agent.presets import PresetStore
from led_agent.protocol_v2 import decode_rle, encode_rle, frame_message, scene_message


class ProtocolTests(unittest.TestCase):
    def test_frame_rle_round_trip(self):
        canvas = Canvas()
        canvas.clear("#010203")
        canvas.set(4, 5, "#ff00aa", blend="replace")
        encoded = encode_rle(canvas.pixels)
        self.assertEqual(decode_rle(encoded), bytes(canvas.pixels))
        self.assertLess(len(encoded), len(canvas.pixels))

    def test_frame_message_is_bounded(self):
        canvas = Canvas()
        canvas.clear("#123456")
        message = frame_message(canvas, "frame-1")
        self.assertEqual(message["encoding"], "rgb-rle-base64")
        self.assertEqual(decode_rle(base64.b64decode(message["data"])), bytes(canvas.pixels))

    def test_scene_message_validates(self):
        message = scene_message(compile_prompt("ocean waves"), "scene-1")
        self.assertEqual(message["v"], 2)
        self.assertEqual(message["cmd"], "scene")

    def test_preset_store_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "presets.json")
            scene = compile_prompt("fireflies")
            store.save_scene("quiet", scene)
            self.assertEqual(store.get_scene("quiet"), scene)
            store.save_playlist("evening", ["quiet"])
            self.assertEqual(store.load()["playlists"]["evening"], ["quiet"])
            combined=store.get_playlist_scene("evening")
            self.assertEqual(combined["name"],"evening")
            self.assertEqual(len(combined["steps"]),len(scene["steps"]))


if __name__ == "__main__":
    unittest.main()
