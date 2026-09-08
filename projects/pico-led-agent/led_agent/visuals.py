from __future__ import annotations

import time

EYES = [
    ["........", "........", ".##..##.", ".##..##.", "........", "........", "........", "........"],
    ["........", "........", "........", ".##..##.", "........", "........", "........", "........"],
    ["........"] * 8,
]
HEART = [
    ["........", ".##..##.", "#######.", "#######.", ".#####..", "..###...", "...#....", "........"]
]


def preview(command, stream):
    name = command.get("animation")
    if command["cmd"] == "play" and name in ("eyes", "heart"):
        frames = EYES if name == "eyes" else HEART
        for frame in frames:
            stream.write("\n" + "\n".join(row.replace(".", "·").replace("#", "█") for row in frame) + "\n")
            stream.flush()
            time.sleep(0.12)
    elif command["cmd"] == "play":
        stream.write(f"\n[animated preview: {name}]\n")
    elif command["cmd"] == "scroll":
        stream.write(f"\n[scrolling: {command['text']}]\n")

