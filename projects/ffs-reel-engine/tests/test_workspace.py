from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as web
from src.engine import ReelEngine


class UnifiedWorkspaceRouteTests(unittest.TestCase):
    def test_workspace_renders_for_existing_project(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = ReelEngine(Path(directory))
            project = engine.create_project("Cinehan Nights")
            with patch.object(web, "engine", engine):
                response = web.app.test_client().get(
                    f"/projects/{project['id']}/workspace"
                )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Generate branded draft", response.data)
            self.assertIn(b"Your branded cut", response.data)

    def test_workspace_rejects_unknown_project(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(web, "engine", ReelEngine(Path(directory))):
                response = web.app.test_client().get(
                    "/projects/missing-project/workspace"
                )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.data)["error"], "Project not found.")

    def test_missing_historical_output_returns_404(self):
        response = web.app.test_client().get("/api/output/missing-preview.mp4")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Output file not found", json.loads(response.data)["error"])


if __name__ == "__main__":
    unittest.main()
