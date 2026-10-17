"""Independent installed-runtime fingerprint and CRS boundary checks."""
import json
import os
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsProcessingContext, QgsVectorLayer, Qgis
from utility_route_lite.qgis_adapters.builder import graph_from_source
from utility_route_lite.core.builder import BuildError

class QgisGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath(os.environ['QGIS_PREFIX_PATH'], True)
        cls.app = QgsApplication([], False); cls.app.initQgis()
        print('ACTUAL QGIS:', Qgis.QGIS_VERSION)
    @classmethod
    def tearDownClass(cls): cls.app.exitQgis()
    def setUp(self):
        self.layer = QgsVectorLayer('LineString?crs=EPSG:3857&field=asset_key:string&field=status:integer&field=direction:string','audit','memory')
        f = QgsFeature(self.layer.fields()); f.setAttributes(['a',7,'both'])
        f.setGeometry(QgsGeometry.fromWkt('LINESTRING (0 0, 10 0)'))
        self.assertTrue(self.layer.dataProvider().addFeatures([f])[0])
        self.profile = json.loads((ROOT/'examples/fixtures/v1/crossing_unconnected.json').read_text())['rule_profile']
    def graph(self, source='EPSG:3857', target='EPSG:3857'):
        return graph_from_source(self.layer,source_crs=QgsCoordinateReferenceSystem(source),network_crs=QgsCoordinateReferenceSystem(target),layer_key='audit',feature_key_field='asset_key',profile=self.profile,junctions=None,context=QgsProcessingContext())
    def test_raw_selected_attribute_change_invalidates_fingerprint(self):
        a = self.graph()
        fid = next(self.layer.getFeatures()).id()
        self.assertTrue(self.layer.dataProvider().changeAttributeValues({fid:{1:8}}))
        b = self.graph()
        (ROOT/'docs/audits/evidence/gate-a/fingerprints.json').write_text(json.dumps({'value_7':a['source_snapshot_sha256'],'value_8':b['source_snapshot_sha256']},indent=2)+'\n')
        self.assertNotEqual(a['source_snapshot_sha256'], b['source_snapshot_sha256'])
    def test_inconsistent_declared_crs_rejected(self):
        with self.assertRaises(BuildError) as raised: self.graph(source='EPSG:4326')
        self.assertEqual(raised.exception.code,'INVALID_CRS')
    def test_geographic_target_rejected(self):
        with self.assertRaises(BuildError) as raised: self.graph(target='EPSG:4326')
        self.assertEqual(raised.exception.code,'INVALID_CRS')
if __name__ == '__main__': unittest.main()
