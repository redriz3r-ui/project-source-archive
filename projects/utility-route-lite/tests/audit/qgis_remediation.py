"""Installed QGIS 4.2 adapter and output cancellation regressions."""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsFeature,
    QgsGeometry, QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback,
    QgsVectorLayer, Qgis)
from utility_route_lite.core.builder import BuildError
from utility_route_lite.qgis_adapters.builder import graph_from_source
from utility_route_lite.processing.algorithms import BuildNetworkAlgorithm

class RemediationQgisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath(os.environ['QGIS_PREFIX_PATH'], True)
        cls.app = QgsApplication([], False); cls.app.initQgis()
        print('QGIS:', Qgis.QGIS_VERSION)
    @classmethod
    def tearDownClass(cls): cls.app.exitQgis()
    def setUp(self):
        self.profile = json.loads((ROOT/'examples/fixtures/v1/crossing_unconnected.json').read_text())['rule_profile']
        self.crs = QgsCoordinateReferenceSystem('EPSG:3857')
    def layer(self, wkt, dimension='LineString'):
        layer = QgsVectorLayer(f'{dimension}?crs=EPSG:3857&field=asset_key:string&field=status:string&field=direction:string','audit','memory')
        self.assertTrue(layer.isValid())
        feature = QgsFeature(layer.fields()); feature.setAttributes(['a','open','both'])
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        self.assertTrue(layer.dataProvider().addFeatures([feature])[0])
        return layer
    def graph(self, layer, feedback=None):
        return graph_from_source(layer,source_crs=self.crs,network_crs=self.crs,
            layer_key='audit',feature_key_field='asset_key',profile=self.profile,
            junctions=None,context=QgsProcessingContext(),feedback=feedback)
    def test_z_and_m_require_consent_and_preserve_source_ordinates(self):
        for dimension,wkt in [('LineStringZ','LINESTRING Z (0 0 2, 1 0 3)'),
                              ('LineStringM','LINESTRING M (0 0 2, 1 0 3)'),
                              ('LineStringZM','LINESTRING ZM (0 0 2 4, 1 0 3 5)')]:
            with self.subTest(dimension=dimension):
                layer = self.layer(wkt, dimension)
                with self.assertRaises(BuildError) as err: self.graph(layer)
                self.assertEqual(err.exception.code,'UNSUPPORTED_DIMENSION')
                self.profile['allow_2d_projection'] = True
                graph = self.graph(layer)
                self.assertEqual(len(graph['source_parts'][0]['original_vertices'][0]),4 if dimension=='LineStringZM' else 3)
                self.assertIn('Z_M_IGNORED',{q['code'] for q in graph['qa_issues']})
                self.profile['allow_2d_projection'] = False
    def test_canceled_build_publishes_no_outputs_or_source_edit(self):
        layer = self.layer('LINESTRING (0 0, 1 0)')
        before = [(f.geometry().asWkt(),f.attributes()) for f in layer.getFeatures()]
        with TemporaryDirectory() as temp:
            root=Path(temp); profile=root/'rules.json'; profile.write_text(json.dumps(self.profile))
            out_graph=root/'graph.json'; out_qa=root/'qa.gpkg'
            params={'SOURCE_LINES':layer,'SOURCE_CRS':self.crs,'NETWORK_CRS':self.crs,
                'LAYER_KEY':'audit','FEATURE_KEY_FIELD':'asset_key','RULE_PROFILE':str(profile),
                'GRAPH_JSON':str(out_graph),'QA_GPKG':str(out_qa)}
            alg=BuildNetworkAlgorithm(); alg.initAlgorithm()
            feedback=QgsProcessingFeedback()
            real_replace=os.link; calls=[]
            def cancel_after_first(source,destination):
                real_replace(source,destination); calls.append(str(destination))
                if len(calls)==1: feedback.cancel()
            with patch('utility_route_lite.processing.algorithms.os.link',side_effect=cancel_after_first):
                with self.assertRaises(QgsProcessingException) as err:
                    alg.processAlgorithm(params,QgsProcessingContext(),feedback)
            self.assertIn('CANCELED',str(err.exception))
            self.assertEqual(len(calls),1)
            self.assertFalse(out_graph.exists()); self.assertFalse(out_qa.exists())
        self.assertEqual(before,[(f.geometry().asWkt(),f.attributes()) for f in layer.getFeatures()])

if __name__=='__main__': unittest.main()
