import unittest

from led_agent.compiler import compile_prompt
from led_agent.renderer import SceneRenderer
from led_agent.scene import SceneError, validate_scene
from led_agent.canvas import Canvas
from led_agent.transitions import apply_transition


class SceneTests(unittest.TestCase):
    def test_complex_prompt_compiles_to_sequence(self):
        scene = compile_prompt(
            "Make a dim cyberpunk city with flickering amber windows, slow purple rain, "
            "occasional blue lightning, then scroll ROB'S LAB in hot pink"
        )
        self.assertEqual(scene["v"], 2)
        self.assertEqual(len(scene["steps"]), 2)
        self.assertEqual([x["effect"] for x in scene["steps"][0]["layers"]],
                         ["city", "rain", "lightning"])
        self.assertEqual(scene["steps"][1]["layers"][0]["text"], "ROB'S LAB")
        self.assertLess(scene["brightness"], .2)
        layers=scene["steps"][0]["layers"]
        self.assertEqual(layers[0]["palette"][-1],"#ffb000")
        self.assertEqual(layers[1]["palette"][-1],"#7020ff")
        self.assertEqual(layers[2]["palette"][-1],"#00aaff")
        self.assertEqual(layers[2]["intensity"],.2)
        self.assertEqual(scene["steps"][1]["layers"][0]["palette"][-1],"#ff1493")

    def test_renderer_is_exact_hardware_size(self):
        renderer = SceneRenderer(compile_prompt("cyberpunk rain and city"))
        frame = renderer.render(1.25)
        self.assertEqual((frame.width, frame.height), (53, 11))
        self.assertEqual(len(frame.pixels), 53 * 11 * 3)
        self.assertTrue(any(frame.pixels))

    def test_unknown_effect_is_rejected(self):
        with self.assertRaises(SceneError):
            validate_scene({"v": 2, "steps": [{"layers": [{"effect": "nope"}]}]})

    def test_renderer_is_deterministic(self):
        scene = compile_prompt("stars and fireflies")
        self.assertEqual(SceneRenderer(scene).render(2).pixels,
                         SceneRenderer(scene).render(2).pixels)

    def test_all_transitions_preserve_canvas_shape(self):
        before, after = Canvas(), Canvas()
        before.clear("#ff0000"); after.clear("#0000ff")
        for kind in ("cut", "fade", "wipe", "dissolve", "glitch"):
            frame = apply_transition(before, after, .5, kind)
            self.assertEqual(len(frame.pixels), 53 * 11 * 3)

    def test_fade_interpolates(self):
        before, after = Canvas(), Canvas()
        before.clear("#000000"); after.clear("#ffffff")
        self.assertEqual(apply_transition(before, after, .5, "fade").get(0, 0), (127, 127, 127))

    def test_natural_priority_expiry_and_one_shot(self):
        scene=compile_prompt("urgent red scanner once for 2 minutes")
        self.assertEqual(scene["priority"],50)
        self.assertEqual(scene["expires_in"],120)
        self.assertFalse(scene["loop"])


if __name__ == "__main__":
    unittest.main()
