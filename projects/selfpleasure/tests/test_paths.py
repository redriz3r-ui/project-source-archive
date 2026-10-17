"""Packaged models are read-only; user data must never target the app bundle."""

from pathlib import Path
import sys

from app.paths import PROJECT_ROOT, private_data_path, resource_path


def test_source_paths_remain_local_to_project():
    assert resource_path(".models", "hand_landmarker.task") == PROJECT_ROOT / ".models" / "hand_landmarker.task"
    assert private_data_path("evaluation-data") == PROJECT_ROOT / "evaluation-data"


def test_frozen_paths_separate_resources_and_private_data(monkeypatch, tmp_path):
    bundle = tmp_path / "SelfPleasure.app" / "Contents" / "Frameworks"
    home = tmp_path / "home"
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert resource_path(".models", "hand_landmarker.task") == bundle / ".models" / "hand_landmarker.task"
    assert private_data_path("evaluation-data") == home / "Library" / "Application Support" / "SelfPleasure" / "evaluation-data"
