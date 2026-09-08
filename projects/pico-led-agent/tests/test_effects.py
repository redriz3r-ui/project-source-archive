import unittest

from led_agent.canvas import Canvas
from led_agent.effects import REGISTRY, create_effect


class EffectCoverageTests(unittest.TestCase):
    def test_every_registered_effect_renders_safely(self):
        for name in REGISTRY:
            with self.subTest(effect=name):
                layer={"effect":name,"palette":"cyberpunk","speed":1,"intensity":.5,
                       "opacity":1,"blend":"alpha"}
                if name=="text": layer["text"]="TEST"
                canvas=Canvas(); create_effect(layer).render(canvas,1.2)
                self.assertEqual(len(canvas.pixels),53*11*3)

    def test_named_motion_effects_are_visually_distinct(self):
        signatures = {}
        for name in ("stars", "fireflies", "particles", "waves", "spectrum"):
            layer={"effect":name,"palette":"cyberpunk","speed":1,"intensity":.7,
                   "opacity":1,"blend":"alpha"}
            canvas=Canvas(); create_effect(layer).render(canvas,1.37)
            signatures[name]=bytes(canvas.pixels)
        self.assertEqual(len(set(signatures.values())),len(signatures))
