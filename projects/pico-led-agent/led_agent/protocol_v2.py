"""Wire helpers for v2 scene programs and compact RGB frames."""

from __future__ import annotations

import base64
import json
from typing import Iterable

from .canvas import Canvas
from .scene import HEIGHT, WIDTH, validate_scene

MAX_MESSAGE = 32_768


def scene_message(scene, request_id: str | None = None) -> dict:
    result = {"v": 2, "cmd": "scene", "scene": validate_scene(scene)}
    if request_id:
        result["id"] = request_id[:40]
    _check_size(result)
    return result


def capabilities_message() -> dict:
    return {"v": 2, "cmd": "capabilities"}


def frame_message(canvas: Canvas, request_id: str | None = None) -> dict:
    if (canvas.width, canvas.height) != (WIDTH, HEIGHT):
        raise ValueError(f"frame must be {WIDTH}x{HEIGHT}")
    encoded = encode_rle(canvas.pixels)
    result = {"v": 2, "cmd": "frame", "encoding": "rgb-rle-base64",
              "width": WIDTH, "height": HEIGHT,
              "data": base64.b64encode(encoded).decode("ascii")}
    if request_id:
        result["id"] = request_id[:40]
    _check_size(result)
    return result


def encode_rle(pixels: bytes | bytearray | Iterable[int]) -> bytes:
    raw = bytes(pixels)
    if len(raw) % 3:
        raise ValueError("RGB data length must be divisible by three")
    result = bytearray()
    i = 0
    while i < len(raw):
        rgb = raw[i:i + 3]
        count = 1
        while count < 255 and i + count * 3 < len(raw) and raw[i + count * 3:i + count * 3 + 3] == rgb:
            count += 1
        result.extend((count, *rgb))
        i += count * 3
    return bytes(result)


def decode_rle(data: bytes, expected_pixels=WIDTH * HEIGHT) -> bytes:
    if len(data) % 4:
        raise ValueError("invalid RGB RLE payload")
    result = bytearray()
    for i in range(0, len(data), 4):
        count, r, g, b = data[i:i + 4]
        if count == 0:
            raise ValueError("zero-length RLE run")
        result.extend(bytes((r, g, b)) * count)
        if len(result) > expected_pixels * 3:
            raise ValueError("RLE payload exceeds frame size")
    if len(result) != expected_pixels * 3:
        raise ValueError("RLE payload does not fill frame")
    return bytes(result)


def _check_size(message):
    size = len(json.dumps(message, separators=(",", ":")).encode())
    if size > MAX_MESSAGE:
        raise ValueError(f"message is too large ({size} bytes)")

