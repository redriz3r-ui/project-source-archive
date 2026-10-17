"""Download the official Face Landmarker bundle once; inference stays offline."""

import hashlib
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen

from app.vision.service import DEFAULT_MODEL_PATH


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"


def download_model(target: Path = DEFAULT_MODEL_PATH) -> Path:
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
            raise ValueError("Downloaded Face Landmarker model checksum did not match")
        temporary.replace(target)
        return target
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    print(download_model())
