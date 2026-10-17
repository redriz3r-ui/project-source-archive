"""Independent QGIS output ownership and protected-source checks."""
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from qgis.core import (QgsApplication,QgsCoordinateReferenceSystem,QgsFeature,QgsGeometry,QgsProcessingContext,QgsProcessingFeedback,QgsProcessingException,QgsVectorLayer,QgsVectorFileWriter,Qgis)
from utility_route_lite.processing.algorithms import BuildNetworkAlgorithm
from utility_route_lite.qgis_adapters.builder import graph_from_source
class QgisReaudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QgsApplication.setPrefixPath(os.environ['QGIS_PREFIX_PATH'],True)
        cls.app=QgsApplication([],False);cls.app.initQgis()
        print('QGIS',Qgis.QGIS_VERSION,'Python',sys.version)
    @classmethod
    def tearDownClass(cls): cls.app.exitQgis()
    def setUp(self):
        self.profile=json.loads((ROOT/'examples/fixtures/v1/crossing_unconnected.json').read_text())['rule_profile']
        self.crs=QgsCoordinateReferenceSystem('EPSG:3857')
        self.layer=QgsVectorLayer('LineString?crs=EPSG:3857&field=asset_key:string&field=status:string&field=direction:string','synthetic','memory')
        f=QgsFeature(self.layer.fields());f.setAttributes(['a','open','both']);f.setGeometry(QgsGeometry.fromWkt('LINESTRING(0 0, 5 1, 10 0)'))
        self.assertTrue(self.layer.dataProvider().addFeatures([f])[0])
    def test_output_created_after_precheck_is_not_overwritten(self):
        with TemporaryDirectory() as d:
            p=Path(d);rules=p/'rules.json';rules.write_text(json.dumps(self.profile))
            out_graph=p/'graph.json';out_qa=p/'qa.gpkg';sentinel=b'USER OWNED OUTPUT\n'
            args={'SOURCE_LINES':self.layer,'SOURCE_CRS':self.crs,'NETWORK_CRS':self.crs,'LAYER_KEY':'audit','FEATURE_KEY_FIELD':'asset_key','RULE_PROFILE':str(rules),'GRAPH_JSON':str(out_graph),'QA_GPKG':str(out_qa)}
            algorithm=BuildNetworkAlgorithm();algorithm.initAlgorithm()
            real_replace=os.link
            def concurrent_create(source,destination):
                real_replace(source,destination)
                if Path(destination)==out_qa: out_graph.write_bytes(sentinel)
            error=None
            with patch('utility_route_lite.processing.algorithms.os.link',side_effect=concurrent_create):
                try: algorithm.processAlgorithm(args,QgsProcessingContext(),QgsProcessingFeedback())
                except QgsProcessingException as e: error=str(e)
            print('OBSERVED concurrent destination:',{'exception':error,'sentinel_preserved':out_graph.read_bytes()==sentinel})
            self.assertEqual(out_graph.read_bytes(),sentinel,'pre-existing concurrent output was overwritten')
            self.assertIsNotNone(error)
            self.assertFalse(out_qa.exists())
    def test_readonly_geopackage_source_is_unchanged(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'protected.gpkg';context=QgsProcessingContext()
            opts=QgsVectorFileWriter.SaveVectorOptions();opts.driverName='GPKG';opts.layerName='corridors'
            result=QgsVectorFileWriter.writeAsVectorFormatV3(self.layer,str(path),context.transformContext(),opts)
            self.assertEqual(result[0],QgsVectorFileWriter.WriterError.NoError)
            path.chmod(0o444)
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            source=QgsVectorLayer(str(path)+'|layername=corridors','protected','ogr');self.assertTrue(source.isValid())
            graph=graph_from_source(source,source_crs=self.crs,network_crs=self.crs,layer_key='audit',feature_key_field='asset_key',profile=self.profile,junctions=None,context=context)
            self.assertEqual(graph['edges'][0]['vertices_xy'],[[0,0],[5,1],[10,0]])
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
            source=None;path.chmod(0o644)
    def test_repository_wkt_is_valid_projected_meter_crs(self):
        crs=QgsCoordinateReferenceSystem.fromWkt((ROOT/'scripts/epsg3857.wkt').read_text())
        self.assertTrue(crs.isValid());self.assertFalse(crs.isGeographic())
        self.assertEqual(crs.mapUnits(),Qgis.DistanceUnit.Meters)
        self.assertEqual(crs.authid(),'EPSG:3857')
if __name__=='__main__':unittest.main()
