"""Atomic JSON persistence for named scenes and playlists."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .scene import validate_scene


class PresetStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {"v": 1, "scenes": {}, "playlists": {}}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("v") != 1 or not isinstance(value.get("scenes"), dict):
            raise ValueError("invalid preset store")
        value.setdefault("playlists", {})
        return value

    def save_scene(self, name: str, scene: dict) -> None:
        if not name.strip() or len(name) > 60:
            raise ValueError("preset name must be 1 to 60 characters")
        data = self.load()
        data["scenes"][name] = validate_scene(scene)
        self._write(data)

    def get_scene(self, name: str) -> dict:
        try:
            return self.load()["scenes"][name]
        except KeyError as exc:
            raise KeyError(f"unknown scene: {name}") from exc

    def save_playlist(self, name: str, scene_names: list[str]) -> None:
        data = self.load()
        missing = [item for item in scene_names if item not in data["scenes"]]
        if missing:
            raise ValueError("unknown scenes: " + ", ".join(missing))
        data["playlists"][name] = list(scene_names)
        self._write(data)

    def get_playlist_scene(self, name: str) -> dict:
        data=self.load()
        try: names=data["playlists"][name]
        except KeyError as exc: raise KeyError(f"unknown playlist: {name}") from exc
        if not names: raise ValueError("playlist is empty")
        scenes=[data["scenes"][item] for item in names]
        combined={"v":2,"name":name,"brightness":scenes[0].get("brightness",.2),
                  "priority":0,"loop":True,"background":scenes[0].get("background","#000000"),
                  "transition":scenes[0].get("transition",{"type":"fade","duration":.5}),
                  "steps":[step for scene in scenes for step in scene["steps"]]}
        return validate_scene(combined)

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
