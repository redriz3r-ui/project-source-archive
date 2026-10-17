"""Original synthetic API probes, not Utility Route Lite acceptance tests.

The interior-vertex test deliberately records native graph behavior that the
product must NOT inherit. No upstream plugin source is imported or executed.
Run using scripts/run_qgis_audit_macos.sh, or QGIS's configured Python elsewhere.
Missing QGIS is an error, not a passing skipped test suite.
"""
import os
from pathlib import Path
import tempfile
import unittest

from qgis.PyQt.QtCore import QT_VERSION_STR, QMetaType
from qgis.analysis import (
    QgsGraphAnalyzer, QgsGraphBuilder, QgsNetworkDistanceStrategy,
    QgsVectorLayerDirector,
)
from qgis.core import (
    Qgis, QgsApplication, QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext, QgsDistanceArea, QgsFeature, QgsField,
    QgsGeometry, QgsPointXY, QgsProcessingAlgorithm, QgsProcessingProvider,
    QgsVectorFileWriter, QgsVectorLayer,
)
from qgis.gui import QgsDockWidget


class QgisFeasibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = tempfile.TemporaryDirectory(prefix="url-qgis-audit-")
        if os.environ.get("QGIS_PREFIX_PATH"):
            QgsApplication.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
        cls.app = QgsApplication([], False, cls.profile.name)
        cls.app.initQgis()
        print(f"Runtime: QGIS {Qgis.QGIS_VERSION}; Qt {QT_VERSION_STR}", flush=True)

    @classmethod
    def tearDownClass(cls):
        cls.app.exitQgis()
        cls.profile.cleanup()

    def layer(self, wkts, crs="EPSG:3857"):
        layer = QgsVectorLayer(f"LineString?crs={crs}", "synthetic-audit", "memory")
        self.assertTrue(layer.isValid())
        features = []
        for wkt in wkts:
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        self.assertTrue(layer.dataProvider().addFeatures(features)[0])
        return layer

    def graph(self, layer, points=()):
        director = QgsVectorLayerDirector(
            layer, -1, "", "", "", QgsVectorLayerDirector.Direction.DirectionBoth
        )
        director.addStrategy(QgsNetworkDistanceStrategy())
        builder = QgsGraphBuilder(layer.crs(), True, 0.0)
        tied = director.makeGraph(builder, list(points))
        return builder.graph(), tied

    def reachable(self, graph, start, end):
        a, b = graph.findVertex(QgsPointXY(*start)), graph.findVertex(QgsPointXY(*end))
        self.assertGreaterEqual(a, 0)
        self.assertGreaterEqual(b, 0)
        predecessors, _ = QgsGraphAnalyzer.dijkstra(graph, a, 0)
        return predecessors[b] != -1

    def test_runtime_and_interfaces(self):
        self.assertGreaterEqual(Qgis.QGIS_VERSION_INT, 40200)
        self.assertEqual(QT_VERSION_STR.split(".")[0], "6")
        for cls, methods in [
            (QgsProcessingAlgorithm, ["initAlgorithm", "processAlgorithm", "createInstance"]),
            (QgsProcessingProvider, ["loadAlgorithms", "id", "name"]),
            (QgsDockWidget, ["setWidget", "setUserVisible"]),
            (QgsVectorFileWriter, ["writeAsVectorFormatV3"]),
        ]:
            for method in methods:
                self.assertTrue(callable(getattr(cls, method)))
        self.assertEqual(QgsField("source_key", QMetaType.Type.QString).name(), "source_key")

    def test_native_crossing_without_shared_vertices_is_disconnected(self):
        layer = self.layer(["LINESTRING (-10 0,10 0)", "LINESTRING (0 -10,0 10)"])
        graph, _ = self.graph(layer)
        self.assertFalse(self.reachable(graph, (-10, 0), (0, 10)))

    def test_native_shared_interior_vertices_connect_without_asset_evidence(self):
        layer = self.layer([
            "LINESTRING (-10 0,0 0,10 0)", "LINESTRING (0 -10,0 0,0 10)"
        ])
        graph, _ = self.graph(layer)
        self.assertTrue(self.reachable(graph, (-10, 0), (0, 10)))

    def test_native_same_edge_ties(self):
        layer = self.layer(["LINESTRING (0 0,10 0)"])
        graph, tied = self.graph(layer, [QgsPointXY(2, 0), QgsPointXY(8, 0)])
        self.assertEqual([(p.x(), p.y()) for p in tied], [(2, 0), (8, 0)])
        self.assertTrue(self.reachable(graph, (2, 0), (8, 0)))

    def test_ellipsoidal_geographic_meters(self):
        measure = QgsDistanceArea()
        measure.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateTransformContext())
        self.assertTrue(measure.setEllipsoid("WGS84"))
        raw = measure.measureLine(QgsPointXY(0, 0), QgsPointXY(1, 0))
        meters = measure.convertLengthMeasurement(raw, Qgis.DistanceUnit.Meters)
        self.assertAlmostEqual(meters, 111319.490793, delta=0.01)

    def test_projected_feet_convert_to_meters(self):
        measure = QgsDistanceArea()
        measure.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:2263"), QgsCoordinateTransformContext())
        measure.setEllipsoid("NONE")
        raw = measure.measureLine(QgsPointXY(1000000, 200000), QgsPointXY(1001000, 200000))
        self.assertAlmostEqual(raw, 1000.0, places=6)
        self.assertNotEqual(measure.lengthUnits(), Qgis.DistanceUnit.Meters)
        meters = measure.convertLengthMeasurement(raw, Qgis.DistanceUnit.Meters)
        self.assertAlmostEqual(meters, 304.8006096, delta=0.001)

    def test_2d_conversion_discards_zm(self):
        geometry = QgsGeometry.fromWkt("LINESTRING ZM (0 0 7 11,1 1 9 13)")
        converted = QgsGeometry.fromPolylineXY(geometry.asPolyline())
        self.assertEqual(converted.wkbType(), Qgis.WkbType.LineString)
        self.assertEqual([(p.x(), p.y()) for p in converted.asPolyline()], [(0, 0), (1, 1)])

    def test_geopackage_roundtrip_retains_shape_crs_and_reference(self):
        layer = self.layer(["LINESTRING (0 0,3 4,6 0)"])
        self.assertTrue(layer.dataProvider().addAttributes([QgsField("source_key", QMetaType.Type.QString)]))
        layer.updateFields()
        feature = next(layer.getFeatures())
        self.assertTrue(layer.dataProvider().changeAttributeValues({feature.id(): {0: "synthetic-edge-1"}}))
        before = bytes(feature.geometry().asWkb())
        with tempfile.TemporaryDirectory(prefix="url-gpkg-audit-") as folder:
            path = str(Path(folder) / "probe.gpkg")
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = "proposed_routes"
            result = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, path, QgsCoordinateTransformContext(), options
            )
            self.assertEqual(result[0], QgsVectorFileWriter.WriterError.NoError, result)
            loaded = QgsVectorLayer(path + "|layername=proposed_routes", "reloaded", "ogr")
            self.assertTrue(loaded.isValid())
            self.assertEqual(loaded.featureCount(), 1)
            self.assertEqual(loaded.crs().authid(), "EPSG:3857")
            exported = next(loaded.getFeatures())
            self.assertEqual(bytes(exported.geometry().asWkb()), before)
            self.assertEqual(exported["source_key"], "synthetic-edge-1")
            del loaded


if __name__ == "__main__":
    unittest.main()
