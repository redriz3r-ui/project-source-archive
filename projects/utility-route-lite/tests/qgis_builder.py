"""Integration tests for the installed QGIS 4 Network Builder algorithm."""

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProcessingContext, QgsProcessingFeedback, QgsVectorLayer,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "examples" / "fixtures" / "v1"
from scripts.build_zip import build_zip  # noqa: E402


def source_layer(case):
    is_multi = any(item["geometry"]["type"] == "MultiLineString" for item in case["source"]["features"])
    layer = QgsVectorLayer(("MultiLineString" if is_multi else "LineString") + f"?crs={case['source_crs']}&field=asset_key:string&field=status:string&field=direction:string",
                           "synthetic_corridors", "memory")
    assert layer.isValid()
    rows = []
    for item in case["source"]["features"]:
        feature = QgsFeature(layer.fields())
        feature.setAttributes([item["properties"][name] for name in ("asset_key", "status", "direction")])
        if is_multi:
            feature.setGeometry(QgsGeometry.fromMultiPolylineXY([
                [QgsPointXY(*xy) for xy in part] for part in item["geometry"]["coordinates"]]))
        else:
            feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*xy) for xy in item["geometry"]["coordinates"]]))
        rows.append(feature)
    assert layer.dataProvider().addFeatures(rows)[0]
    layer.updateExtents()
    return layer


class QgisBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = TemporaryDirectory()
        with ZipFile(build_zip(Path(cls.package.name) / "plugin.zip")) as archive:
            archive.extractall(cls.package.name)
        sys.path.insert(0, cls.package.name)
        QgsApplication.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
        cls.profile = TemporaryDirectory()
        cls.app = QgsApplication([], False, cls.profile.name)
        cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.app.exitQgis()
        cls.profile.cleanup()
        sys.path.remove(cls.package.name)
        cls.package.cleanup()

    def build(self, case_id):
        from utility_route_lite.processing.algorithms import BuildNetworkAlgorithm
        case = json.loads((FIXTURES / f"{case_id}.json").read_text())
        layer = source_layer(case)
        before = [(f.id(), f.geometry().asWkt(), f.attributes()) for f in layer.getFeatures()]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            rule_path = root / "profile.json"
            rule_path.write_text(json.dumps(case["rule_profile"]))
            junction_path = root / "junctions.json"
            if "junction_document" in case:
                junction_path.write_text(json.dumps(case["junction_document"]))
            params = {"SOURCE_LINES": layer, "SOURCE_CRS": QgsCoordinateReferenceSystem(case["source_crs"]),
                      "NETWORK_CRS": QgsCoordinateReferenceSystem(case["network_crs"]),
                      "LAYER_KEY": case["source_layer_key"], "FEATURE_KEY_FIELD": "asset_key",
                      "RULE_PROFILE": str(rule_path), "GRAPH_JSON": str(root / "network.json"),
                      "QA_GPKG": str(root / "qa.gpkg")}
            if junction_path.exists():
                params["JUNCTIONS_JSON"] = str(junction_path)
            algorithm = BuildNetworkAlgorithm()
            algorithm.initAlgorithm()
            outputs = algorithm.processAlgorithm(params, QgsProcessingContext(), QgsProcessingFeedback())
            self.assertTrue(Path(outputs["GRAPH_JSON"]).exists())
            self.assertTrue(Path(outputs["QA_GPKG"]).exists())
            qa_layer = QgsVectorLayer(outputs["QA_GPKG"] + "|layername=qa_issues", "qa", "ogr")
            self.assertTrue(qa_layer.isValid())
            graph = json.loads(Path(outputs["GRAPH_JSON"]).read_text())
            self.assertTrue(graph["network_crs_wkt"].startswith("PROJCRS["))
            self.assertEqual(qa_layer.featureCount(), len(graph["qa_issues"]))
            self.assertTrue({"issue_id", "severity", "code", "source_feature_key", "source_part_index"} <=
                            {field.name() for field in qa_layer.fields()})
            self.assertEqual(qa_layer.crs(), QgsCoordinateReferenceSystem(case["network_crs"]))
            after = [(f.id(), f.geometry().asWkt(), f.attributes()) for f in layer.getFeatures()]
            self.assertEqual(before, after)
            return graph

    def test_false_crossing_remains_disconnected_and_deterministic(self):
        first = self.build("crossing_unconnected")
        self.assertEqual(first["build_summary"]["component_count"], 2)
        self.assertEqual(first["transitions"], [])
        self.assertIn("UNDECLARED_CROSSING", {issue["code"] for issue in first["qa_issues"]})
        self.assertEqual(first, self.build("crossing_unconnected"))

    def test_declared_junction_only_adds_declared_transition(self):
        graph = self.build("declared_junction")
        self.assertEqual(len(graph["edges"]), 4)
        self.assertEqual(graph["build_summary"]["component_count"], 1)
        self.assertEqual(len([t for t in graph["transitions"] if t["declared"]]), 1)

    def test_multipart_keeps_part_indices(self):
        graph = self.build("multipart_refs")
        self.assertEqual([part["source_part_index"] for part in graph["source_parts"]], [0, 1])
        self.assertEqual(graph["build_summary"]["component_count"], 2)

    def test_geographic_source_has_meter_length(self):
        graph = self.build("geographic_metric")
        self.assertEqual(len(graph["edges"]), 1)
        self.assertGreaterEqual(graph["edges"][0]["length_m"], 88)
        self.assertLessEqual(graph["edges"][0]["length_m"], 90)
        self.assertEqual(graph["measurement"]["ellipsoid"], "WGS84")


if __name__ == "__main__":
    unittest.main()
