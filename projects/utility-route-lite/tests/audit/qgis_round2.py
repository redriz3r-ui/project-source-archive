"""QGIS regressions for exclusive publication and native CRS validation."""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from qgis.core import QgsApplication,QgsCoordinateReferenceSystem,QgsFeature,QgsGeometry,QgsProcessingContext,QgsProcessingFeedback,QgsProcessingException,QgsVectorLayer
from utility_route_lite.processing.algorithms import BuildNetworkAlgorithm
from utility_route_lite.qgis_adapters.crs import is_projected_meters
class Round2Qgis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath(os.environ['QGIS_PREFIX_PATH'],True)
        cls.app=QgsApplication([],False);cls.app.initQgis()
    @classmethod
    def tearDownClass(cls):cls.app.exitQgis()
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.qa=self.root/'qa'/'issues.gpkg';self.graph=self.root/'graph'/'graph.json'
        self.qa.parent.mkdir();self.graph.parent.mkdir()
        self.layer=QgsVectorLayer('LineString?crs=EPSG:3857&field=asset_key:string&field=status:string&field=direction:string','synthetic','memory')
        f=QgsFeature(self.layer.fields());f.setAttributes(['a','open','both']);f.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0,1 0)'))
        self.assertTrue(self.layer.dataProvider().addFeatures([f])[0])
        rule=self.root/'rule.json';rule.write_text(json.dumps(json.loads((ROOT/'examples/fixtures/v1/crossing_unconnected.json').read_text())['rule_profile']))
        self.params={'SOURCE_LINES':self.layer,'SOURCE_CRS':QgsCoordinateReferenceSystem('EPSG:3857'),'NETWORK_CRS':QgsCoordinateReferenceSystem('EPSG:3857'),'LAYER_KEY':'audit','FEATURE_KEY_FIELD':'asset_key','RULE_PROFILE':str(rule),'GRAPH_JSON':str(self.graph),'QA_GPKG':str(self.qa)}
    def run_build(self):
        alg=BuildNetworkAlgorithm();alg.initAlgorithm()
        return alg.processAlgorithm(self.params,QgsProcessingContext(),QgsProcessingFeedback())
    def test_separate_parent_directories_publish_complete_files(self):
        result=self.run_build()
        self.assertTrue(self.qa.is_file());self.assertEqual(len(json.loads(self.graph.read_text())['edges']),1)
        self.assertEqual(result['GRAPH_JSON'],str(self.graph))
    def test_rollback_preserves_replaced_qa_and_concurrent_graph(self):
        real_link=os.link
        def concurrent(source,destination):
            real_link(source,destination)
            if Path(destination)==self.qa:
                self.qa.unlink();self.qa.write_bytes(b'external qa')
                self.graph.write_bytes(b'external graph')
        with patch('utility_route_lite.processing.algorithms.os.link',side_effect=concurrent):
            with self.assertRaises(QgsProcessingException) as err:self.run_build()
        self.assertIn('EXPORT_FAILED',str(err.exception))
        self.assertEqual(self.qa.read_bytes(),b'external qa');self.assertEqual(self.graph.read_bytes(),b'external graph')
    def test_dangling_symlink_is_not_clobbered(self):
        target=self.root/'missing';self.graph.symlink_to(target)
        with self.assertRaises(QgsProcessingException):self.run_build()
        self.assertTrue(self.graph.is_symlink());self.assertFalse(target.exists());self.assertFalse(self.qa.exists())
    def test_unavailable_hardlinks_fail_without_publication(self):
        with patch('utility_route_lite.processing.algorithms.os.link',side_effect=OSError('unsupported filesystem')):
            with self.assertRaises(QgsProcessingException) as err:self.run_build()
        self.assertIn('EXPORT_FAILED',str(err.exception));self.assertFalse(self.qa.exists());self.assertFalse(self.graph.exists())
    def test_native_crs_parser_validates_meter_foot_geographic_and_invalid(self):
        for authority,expected in [('EPSG:3857',True),('EPSG:32610',True),('EPSG:2263',False),('EPSG:4326',False)]:
            crs=QgsCoordinateReferenceSystem(authority);self.assertTrue(crs.isValid())
            self.assertEqual(is_projected_meters(crs.toWkt()),expected)
        self.assertFalse(is_projected_meters('not a CRS'))
if __name__=='__main__':unittest.main()
