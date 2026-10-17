"""Read-only bundled resources and private writable data live in different roots."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return root.joinpath(*parts)


def private_data_path(*parts: str) -> Path:
    root = (Path.home() / "Library" / "Application Support" / "SelfPleasure"
            if getattr(sys, "frozen", False) else PROJECT_ROOT)
    return root.joinpath(*parts)
