"""Version 2 scene contract and strict validation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

WIDTH, HEIGHT = 53, 11
EFFECTS = {
    "rain", "snow", "fire", "plasma", "noise", "stars", "fireflies",
    "particles", "comet", "waves", "scanner", "city", "text", "icon",
    "heart", "eyes", "lightning", "spectrum",
}
TRANSITIONS = {"cut", "fade", "wipe", "dissolve", "glitch"}
BLENDS = {"replace", "alpha", "add", "max"}

PALETTES = {
    "cyberpunk": ["#050018", "#7020ff", "#00cfff", "#ff3cac"],
    "sunset": ["#170021", "#ff3158", "#ff8c42", "#ffd166"],
    "ocean": ["#001b3a", "#0066cc", "#00d4ff", "#b8f3ff"],
    "fire": ["#080000", "#8c1200", "#ff5a00", "#ffe066"],
    "forest": ["#001308", "#006b3c", "#3dcc74", "#d8ff96"],
    "mono": ["#000000", "#ffffff"],
}


class SceneError(ValueError):
    pass


def parse_color(value: Any) -> tuple[int, int, int]:
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    if isinstance(value, (list, tuple)) and len(value) == 3:
        parts = tuple(int(v) for v in value)
        if all(0 <= v <= 255 for v in parts):
            return parts
    raise SceneError(f"invalid RGB color: {value!r}")


def validate_scene(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SceneError("scene must be an object")
    scene = deepcopy(value)
    if scene.get("v") != 2:
        raise SceneError("scene version must be 2")
    scene.setdefault("name", "untitled")
    scene.setdefault("brightness", 0.2)
    scene.setdefault("priority", 0)
    scene.setdefault("loop", True)
    scene.setdefault("transition", {"type": "cut", "duration": 0})
    scene.setdefault("background", "#000000")
    scene.setdefault("steps", [])
    if not isinstance(scene["name"], str) or not scene["name"].strip():
        raise SceneError("scene name must be non-empty")
    if not 0 <= float(scene["brightness"]) <= 1:
        raise SceneError("brightness must be from 0 to 1")
    if not -100 <= int(scene["priority"]) <= 100:
        raise SceneError("priority must be from -100 to 100")
    parse_color(scene["background"])
    transition = scene["transition"]
    if transition.get("type") not in TRANSITIONS:
        raise SceneError("unknown transition")
    if not 0 <= float(transition.get("duration", 0)) <= 10:
        raise SceneError("transition duration must be from 0 to 10 seconds")
    if not isinstance(scene["steps"], list) or not 1 <= len(scene["steps"]) <= 32:
        raise SceneError("scene needs 1 to 32 steps")
    for index, step in enumerate(scene["steps"]):
        _validate_step(step, index)
    expires = scene.get("expires_in")
    if expires is not None and not 1 <= float(expires) <= 86400:
        raise SceneError("expires_in must be from 1 second to 24 hours")
    return scene


def _validate_step(step: Any, index: int) -> None:
    if not isinstance(step, dict):
        raise SceneError(f"step {index} must be an object")
    step.setdefault("duration", 10)
    step.setdefault("layers", [])
    if not 0.05 <= float(step["duration"]) <= 86400:
        raise SceneError(f"step {index} duration is out of range")
    if not isinstance(step["layers"], list) or not 1 <= len(step["layers"]) <= 16:
        raise SceneError(f"step {index} needs 1 to 16 layers")
    for layer_index, layer in enumerate(step["layers"]):
        if not isinstance(layer, dict):
            raise SceneError(f"step {index} layer {layer_index} must be an object")
        effect = layer.get("effect")
        if effect not in EFFECTS:
            raise SceneError(f"unknown effect: {effect!r}")
        layer.setdefault("blend", "alpha")
        layer.setdefault("opacity", 1.0)
        layer.setdefault("speed", 1.0)
        layer.setdefault("intensity", 0.5)
        if layer["blend"] not in BLENDS:
            raise SceneError(f"unknown blend mode: {layer['blend']!r}")
        if not 0 <= float(layer["opacity"]) <= 1:
            raise SceneError("opacity must be from 0 to 1")
        if not 0.05 <= float(layer["speed"]) <= 8:
            raise SceneError("speed must be from 0.05 to 8")
        if not 0 <= float(layer["intensity"]) <= 1:
            raise SceneError("intensity must be from 0 to 1")
        palette = layer.get("palette", "cyberpunk")
        if isinstance(palette, str):
            if palette not in PALETTES:
                raise SceneError(f"unknown palette: {palette!r}")
        elif isinstance(palette, list) and 1 <= len(palette) <= 16:
            for color in palette:
                parse_color(color)
        else:
            raise SceneError("palette must be a known name or color list")
        if effect == "text" and not str(layer.get("text", ""))[:120]:
            raise SceneError("text effect requires text")


def palette_colors(layer: dict[str, Any]) -> list[tuple[int, int, int]]:
    palette = layer.get("palette", "cyberpunk")
    values = PALETTES[palette] if isinstance(palette, str) else palette
    return [parse_color(value) for value in values]

