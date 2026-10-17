"""CRS fixtures and PyQGIS metric-distance proof when QGIS is installed."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples" / "fixtures" / "v1" / "geographic_metric.json"

try:
    from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea, QgsPointXY, QgsProject
except ImportError:
    QgsApplication = None


class CrsContractTests(unittest.TestCase):
    def test_geographic_fixture_declares_metric_target_and_bound(self):
        case = json.loads(CASE.read_text())
        self.assertEqual(case["source_crs"], "EPSG:4326")
        self.assertEqual(case["network_crs"], "EPSG:32610")
        self.assertEqual(case["rule_profile"]["ellipsoid"], "WGS84")
        self.assertEqual(case["expected"]["measurement_unit"], "m")
        self.assertEqual(case["expected"]["length_m_range"], [88, 90])

    @unittest.skipIf(QgsApplication is None, "PyQGIS unavailable in this Python; run with QGIS bundled runtime")
    def test_qgis_transform_and_ellipsoidal_length_is_meters(self):
        if "QGIS_PREFIX_PATH" not in os.environ:
            self.skipTest("QGIS runtime environment not configured")
        QgsApplication.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
        with TemporaryDirectory() as profile:
            app = QgsApplication([], False, profile)
            app.initQgis()
            try:
                case = json.loads(CASE.read_text())
                source = QgsCoordinateReferenceSystem(case["source_crs"])
                target = QgsCoordinateReferenceSystem(case["network_crs"])
                self.assertTrue(source.isValid())
                self.assertTrue(target.isValid())
                self.assertTrue(target.isGeographic() is False)
                transform = QgsCoordinateTransform(source, target, QgsProject.instance().transformContext())
                points = [transform.transform(QgsPointXY(*xy)) for xy in case["source"]["features"][0]["geometry"]["coordinates"]]
                measure = QgsDistanceArea()
                measure.setSourceCrs(target, QgsProject.instance().transformContext())
                self.assertTrue(measure.setEllipsoid("WGS84"))
                length_m = measure.measureLine(points)
                lower, upper = case["expected"]["length_m_range"]
                self.assertLessEqual(lower, length_m)
                self.assertLessEqual(length_m, upper)
                self.assertGreater(length_m, 1)
            finally:
                app.exitQgis()


if __name__ == "__main__":
    unittest.main()
