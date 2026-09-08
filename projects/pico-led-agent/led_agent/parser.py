"""Small, predictable natural-language command interpreter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Command:
    cmd: str
    fields: dict[str, Any]

    def to_wire(self) -> dict[str, Any]:
        return {"v": 1, "cmd": self.cmd, **self.fields}


ANIMATIONS = {
    "eyes": ("eyes", "blinking eyes", "blink eyes", "robot eyes"),
    "rain": ("rain", "pixel rain", "raining"),
    "heart": ("heart", "pulse", "pulsing heart"),
    "twinkle": ("twinkle", "stars", "sparkle", "sparkles"),
}


def parse(text: str) -> Command:
    raw = text.strip()
    lowered = raw.lower()
    if not raw:
        raise ParseError("Type a command, such as 'show blinking eyes'.")

    scroll = re.search(r"\bscroll\s+(.+)$", raw, flags=re.IGNORECASE)
    if scroll:
        message = scroll.group(1).strip().strip("\"'")
        if not message:
            raise ParseError("Tell me what to scroll.")
        return Command("scroll", {"text": message[:80], "params": {"speed": 1.0}})

    brightness = re.search(r"\bbrightness(?:\s+(?:to|at))?\s+(\d+)\b", lowered)
    if brightness:
        value = int(brightness.group(1))
        if not 0 <= value <= 15:
            raise ParseError("Brightness must be from 0 to 15.")
        return Command("setting", {"name": "brightness", "value": value})

    speed = re.search(r"\bspeed(?:\s+(?:to|at))?\s+(\d+(?:\.\d+)?)\b", lowered)
    if speed:
        value = float(speed.group(1))
        if not 0.25 <= value <= 4.0:
            raise ParseError("Speed must be from 0.25 to 4.")
        return Command("setting", {"name": "speed", "value": value})

    if any(word in lowered for word in ("clear", "blank", "turn off", "all off")):
        return Command("clear", {})
    if re.search(r"\b(stop|pause)\b", lowered):
        return Command("stop", {})
    if re.search(r"\b(ping|status|hello pico)\b", lowered):
        return Command("ping", {})

    for animation, aliases in ANIMATIONS.items():
        if any(alias in lowered for alias in aliases):
            return Command("play", {"animation": animation, "params": {"speed": 1.0}})

    raise ParseError(
        "I don't know that one yet. Try eyes, rain, heart, twinkle, "
        "scroll HELLO, brightness 4, clear, or stop."
    )

