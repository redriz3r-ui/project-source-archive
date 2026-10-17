"""Run with the QGIS-bundled Python via scripts/run_qgis_scaffold_macos.sh."""

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from qgis.PyQt.QtWidgets import QMainWindow
from qgis.core import QgsApplication, QgsProcessingException


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_zip import build_zip  # noqa: E402


class FakeInterface:
    def __init__(self):
        self.window = QMainWindow()
        self.menu_actions = []
        self.docks = []

    def mainWindow(self):  # noqa: N802
        return self.window

    def addPluginToMenu(self, name, action):  # noqa: N802
        self.menu_actions.append((name, action))

    def removePluginMenu(self, name, action):  # noqa: N802
        self.menu_actions.remove((name, action))

    def addDockWidget(self, area, dock):  # noqa: N802
        self.docks.append(dock)
        self.window.addDockWidget(area, dock)

    def removeDockWidget(self, dock):  # noqa: N802
        self.docks.remove(dock)
        self.window.removeDockWidget(dock)


class QgisScaffoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
        cls.profile = TemporaryDirectory()
        cls.app = QgsApplication([], True, cls.profile.name)
        cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.app.exitQgis()
        cls.profile.cleanup()

    def test_zip_load_register_stubs_dock_and_unload(self):
        with TemporaryDirectory() as temporary:
            zip_path = build_zip(Path(temporary) / "plugin.zip")
            with ZipFile(zip_path) as archive:
                archive.extractall(temporary)
            sys.path.insert(0, temporary)
            try:
                from utility_route_lite import classFactory

                iface = FakeInterface()
                plugin = classFactory(iface)
                plugin.initGui()
                registry = QgsApplication.processingRegistry()
                expected = {"build_network", "inspect_network", "find_route", "batch_routes", "export_bundle"}
                provider = registry.providerById("utilityroutelite")
                self.assertIsNotNone(provider)
                self.assertEqual({algorithm.name() for algorithm in provider.algorithms()}, expected)
                self.assertEqual(len(iface.menu_actions), 1)
                contract = json.loads((ROOT / "docs/contract/v1.json").read_text(encoding="utf-8"))
                for name in expected:
                    algorithm = registry.algorithmById(f"utilityroutelite:{name}")
                    self.assertIsNotNone(algorithm)
                    if name != "build_network":
                        self.assertIn("NOT IMPLEMENTED", algorithm.shortHelpString())
                    specification = contract["algorithms"][algorithm.id()]
                    input_names = set(specification["required_inputs"] + specification["optional_inputs"])
                    declared_parameters = {parameter.name() for parameter in algorithm.parameterDefinitions()}
                    self.assertEqual(declared_parameters - set(specification["outputs"]), input_names)
                    output_names = {output.name() for output in algorithm.outputDefinitions()}
                    self.assertTrue(set(specification["outputs"]) <= declared_parameters | output_names)
                    if name != "build_network":
                        with self.assertRaisesRegex(QgsProcessingException, "NOT IMPLEMENTED"):
                            algorithm.processAlgorithm({}, None, None)
                plugin.show_reviewer()
                self.assertEqual(len(iface.docks), 1)
                self.assertIn("NOT IMPLEMENTED", iface.docks[0].windowTitle())
                plugin.unload()
                self.assertIsNone(registry.providerById("utilityroutelite"))
                self.assertEqual(iface.menu_actions, [])
                self.assertEqual(iface.docks, [])
            finally:
                sys.path.remove(temporary)
                for key in list(sys.modules):
                    if key == "utility_route_lite" or key.startswith("utility_route_lite."):
                        del sys.modules[key]


if __name__ == "__main__":
    unittest.main()
