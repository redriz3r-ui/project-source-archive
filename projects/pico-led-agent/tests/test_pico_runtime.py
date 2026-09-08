import base64
import importlib.util
import sys
import unittest
from pathlib import Path

PICO = Path(__file__).parents[1] / "pico_v2"
sys.path.insert(0, str(PICO))
from display import VirtualDisplay
from runtime import Runtime

from led_agent.canvas import Canvas
from led_agent.compiler import compile_prompt
from led_agent.protocol_v2 import frame_message


class PicoRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.display = VirtualDisplay()
        self.runtime = Runtime(self.display, fps=20)

    def test_capabilities(self):
        result = self.runtime.handle({"v":2,"cmd":"capabilities","id":"x"},0)
        self.assertTrue(result["ok"])
        self.assertEqual((result["width"],result["height"]),(53,11))
        self.assertEqual(result["id"],"x")

    def test_scene_renders_autonomously(self):
        scene=compile_prompt("cyberpunk city and purple rain")
        self.assertTrue(self.runtime.handle({"v":2,"cmd":"scene","scene":scene},0)["ok"])
        self.assertTrue(self.runtime.tick(100))
        self.assertTrue(any(self.display.pixels))

    def test_frame_stream_decodes(self):
        canvas=Canvas(); canvas.clear("#123456"); canvas.set(2,3,"#ffffff",blend="replace")
        result=self.runtime.handle(frame_message(canvas),0)
        self.assertTrue(result["ok"])
        self.assertEqual(bytes(self.display.pixels),bytes(canvas.pixels))

    def test_priority_interrupt_and_resume(self):
        low=compile_prompt("ocean waves"); low["priority"]=0; low["loop"]=False
        high=compile_prompt("red scanner"); high["priority"]=10; high["loop"]=False
        high["steps"][0]["duration"]=.1
        self.runtime.submit(low,0); self.runtime.submit(high,50)
        self.assertEqual(self.runtime.active["priority"],10)
        self.runtime.tick(200)
        self.assertEqual(self.runtime.active["priority"],0)

    def test_bad_scene_returns_error(self):
        result=self.runtime.handle({"v":2,"cmd":"scene","scene":{"v":2,"steps":[]}},0)
        self.assertFalse(result["ok"])

    def test_text_step_renders_on_device_runtime(self):
        scene=compile_prompt("scroll HELLO in cyan")
        self.runtime.submit(scene,0)
        self.runtime.tick(100)
        self.assertTrue(any(self.display.pixels))

    def test_v1_commands_remain_compatible(self):
        result=self.runtime.handle({"v":1,"cmd":"play","animation":"rain","params":{}},0)
        self.assertTrue(result["ok"])
        self.assertEqual(self.runtime.active["name"],"v1 play")
        self.assertTrue(self.runtime.handle({"v":1,"cmd":"ping"},10)["ok"])

    def test_expired_scene_stops(self):
        scene=compile_prompt("fireflies"); scene["expires_in"]=.1; scene["loop"]=True
        self.runtime.submit(scene,0)
        self.runtime.tick(200)
        self.assertIsNone(self.runtime.active)

    def test_all_transitions_render_on_device_runtime(self):
        for kind in ("cut","fade","wipe","dissolve","glitch"):
            with self.subTest(kind=kind):
                scene=compile_prompt("rain then scroll HI")
                scene["steps"][0]["duration"]=.1
                scene["transition"]={"type":kind,"duration":.2}
                runtime=Runtime(VirtualDisplay(),fps=20); runtime.submit(scene,0)
                self.assertTrue(runtime.tick(150))

    def test_expired_interrupted_scene_is_not_resumed(self):
        low=compile_prompt("ocean waves"); low["priority"]=0; low["expires_in"]=.1
        high=compile_prompt("scanner once"); high["priority"]=10; high["loop"]=False
        high["steps"][0]["duration"]=.1
        self.runtime.submit(low,0); self.runtime.submit(high,10); self.runtime.tick(200)
        self.assertIsNone(self.runtime.active)


if __name__ == "__main__": unittest.main()
