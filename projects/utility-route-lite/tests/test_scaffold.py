"""Pure-Python checks for the installable shell package."""

import ast
import configparser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from scripts.build_zip import INCLUDED, PLUGIN, ROOT, build_zip


class ScaffoldTests(unittest.TestCase):
    def test_all_python_files_parse(self):
        for path in PLUGIN.rglob("*.py"):
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_zip_has_single_plugin_root_and_only_allowlisted_files(self):
        with TemporaryDirectory() as temporary:
            output = build_zip(Path(temporary) / "plugin.zip")
            with ZipFile(output) as archive:
                expected = {f"utility_route_lite/{relative}" for relative in INCLUDED}
                expected.add("utility_route_lite/LICENSE")
                self.assertEqual(set(archive.namelist()), expected)
                self.assertTrue(all(name.startswith("utility_route_lite/") for name in archive.namelist()))
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("utility_route_lite/LICENSE"), (ROOT / "LICENSE").read_bytes())

    def test_metadata_declares_qgis_4_provider_and_unfinished_state(self):
        metadata = configparser.ConfigParser()
        metadata.read(PLUGIN / "metadata.txt")
        general = metadata["general"]
        self.assertEqual(general["hasProcessingProvider"], "yes")
        self.assertEqual(general["qgisMinimumVersion"], "4.2")
        self.assertEqual(general["qgisMaximumVersion"], "4.99")
        self.assertNotIn("supportsQt6", general)
        self.assertIn("NOT IMPLEMENTED", general["description"])


if __name__ == "__main__":
    unittest.main()
