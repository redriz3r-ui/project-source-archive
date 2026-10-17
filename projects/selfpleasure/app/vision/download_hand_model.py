"""Fetch and checksum the official Hand Landmarker bundle once; inference is offline."""

import hashlib
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen

from app.vision.hand_tracking import DEFAULT_HAND_MODEL_PATH


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


def download_model(target: Path = DEFAULT_HAND_MODEL_PATH) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == MODEL_SHA256:
        return target
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            with urlopen(MODEL_URL, timeout=30) as source:
                shutil.copyfileobj(source, output)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != MODEL_SHA256:
            raise ValueError("Downloaded Hand Landmarker model checksum did not match")
        temporary.replace(target)
        return target
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    print(download_model())
