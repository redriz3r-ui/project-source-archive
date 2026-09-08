import unittest

from led_agent.parser import ParseError, parse


class ParserTests(unittest.TestCase):
    def test_eyes(self):
        self.assertEqual(parse("show blinking eyes").to_wire()["animation"], "eyes")

    def test_rain(self):
        self.assertEqual(parse("make rain").to_wire()["animation"], "rain")

    def test_scroll_preserves_text(self):
        command = parse("please scroll HELLO Pico").to_wire()
        self.assertEqual(command["cmd"], "scroll")
        self.assertEqual(command["text"], "HELLO Pico")

    def test_brightness_range(self):
        self.assertEqual(parse("brightness 4").to_wire()["value"], 4)
        with self.assertRaises(ParseError):
            parse("brightness 20")

    def test_unknown(self):
        with self.assertRaises(ParseError):
            parse("make me a sandwich")


if __name__ == "__main__":
    unittest.main()
