"""Deterministic natural-language to v2 scene compiler."""

from __future__ import annotations

import re
from typing import Protocol

from .scene import validate_scene

COLOR_WORDS = {
    "purple": "#7020ff", "violet": "#7020ff", "blue": "#00aaff",
    "cyan": "#00ddff", "pink": "#ff3cac", "hot pink": "#ff1493",
    "red": "#ff304f", "orange": "#ff7a18", "amber": "#ffb000",
    "yellow": "#ffe45e", "green": "#30e070", "white": "#ffffff",
}
EFFECT_ALIASES = {
    "skyline": "city", "city": "city", "rain": "rain", "snow": "snow",
    "fireplace": "fire", "fire": "fire", "plasma": "plasma", "noise": "noise",
    "stars": "stars", "starfield": "stars", "fireflies": "fireflies",
    "particles": "particles", "comet": "comet", "wave": "waves",
    "scanner": "scanner", "eyes": "eyes", "heart": "heart",
    "lightning": "lightning", "spectrum": "spectrum",
}


class SceneInterpreter(Protocol):
    """Extension point for deterministic, local-model, or remote-model compilers."""
    def compile(self, text: str) -> dict: ...


class DeterministicInterpreter:
    def compile(self, text: str) -> dict:
        return compile_prompt(text)


def compile_prompt(text: str) -> dict:
    raw, lowered = text.strip(), text.lower()
    if not raw:
        raise ValueError("describe a scene")
    palette = "cyberpunk"
    for name in ("sunset", "ocean", "fire", "forest", "cyberpunk"):
        if name in lowered:
            palette = name
            break
    brightness = .12 if any(w in lowered for w in ("dim", "subtle", "night")) else .28
    if "bright" in lowered:
        brightness = .5
    speed = .55 if "slow" in lowered else 1.7 if "fast" in lowered else 1.0
    priority = 50 if any(word in lowered for word in ("urgent", "alert", "interrupt")) else 0
    layers = []
    seen = set()
    positions = []
    for alias, effect in EFFECT_ALIASES.items():
        match = re.search(r"\b" + re.escape(alias) + r"\b", lowered)
        if match and effect not in seen:
            positions.append((match.start(), effect))
            seen.add(effect)
    for _, effect in sorted(positions):
        layer = {"effect": effect, "palette": palette, "speed": speed,
                 "intensity": .55, "opacity": 1, "blend": "alpha"}
        clause_start=max(lowered.rfind(",",0,_),lowered.rfind(";",0,_))+1
        clause_end=min([p for p in (lowered.find(",",_),lowered.find(";",_)) if p>=0] or [len(lowered)])
        clause=lowered[clause_start:clause_end]
        found=next((COLOR_WORDS[word] for word in sorted(COLOR_WORDS,key=len,reverse=True) if word in clause),None)
        if found: layer["palette"] = ["#000000", found]
        if effect=="lightning" and "occasional" in clause: layer["intensity"]=.2
        if effect=="city" and "flicker" in clause: layer["window_flicker"]=.3
        layers.append(layer)
    scroll = re.search(r"\bscroll\s+(.+?)(?:\s+in\s+(?:hot\s+)?(?:pink|red|blue|cyan|purple|green|white|amber))?(?:[,.]|$)", raw, re.I)
    steps = []
    if layers:
        steps.append({"duration": 12, "layers": layers})
    if scroll:
        phrase = scroll.group(1).strip(" '\"")[:120]
        text_color = next((COLOR_WORDS[k] for k in sorted(COLOR_WORDS,key=len,reverse=True) if f"in {k}" in lowered), "#ff3cac")
        steps.append({"duration": max(5, len(phrase) * .7), "layers": [{
            "effect": "text", "text": phrase, "palette": ["#000000", text_color],
            "speed": speed, "intensity": .5,
        }]})
    if not steps:
        steps = [{"duration": 10, "layers": [{"effect": "plasma", "palette": palette}]}]
    scene = {"v": 2, "name": _scene_name(lowered), "brightness": brightness,
             "priority": priority, "loop": not any(x in lowered for x in ("once", "one time", "one-time")), "background": "#010008",
             "transition": {"type": _transition(lowered), "duration": .6}, "steps": steps}
    expiry = re.search(r"\bfor\s+(\d+(?:\.\d+)?)\s*(seconds?|minutes?)\b", lowered)
    if expiry:
        value = float(expiry.group(1)) * (60 if expiry.group(2).startswith("minute") else 1)
        scene["expires_in"] = value
    return validate_scene(scene)


def _scene_name(text):
    words = re.findall(r"[a-z0-9]+", text)[:5]
    return " ".join(words) or "generated scene"


def _transition(text):
    return next((name for name in ("glitch", "dissolve", "wipe", "fade") if name in text), "fade")
