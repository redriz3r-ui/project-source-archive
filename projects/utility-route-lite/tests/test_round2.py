"""Small permanent regressions for the second Gate A correction round."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from utility_route_lite.core.builder import BuildError,build_graph
ROOT=Path(__file__).resolve().parents[1]

def case(name='crossing_unconnected'):
    return json.loads((ROOT/'examples/fixtures/v1'/f'{name}.json').read_text())
def build(c,**kwargs):
    return build_graph(c['source']['features'],source_crs_wkt=c['source_crs'],network_crs_wkt=c['network_crs'],layer_key=c['source_layer_key'],feature_key_field='asset_key',profile=c['rule_profile'],junctions=c.get('junction_document'),junction_transform=lambda xy:xy,**kwargs)
class Round2Tests(unittest.TestCase):
    def test_strict_junction_part_index_and_feature_key_types(self):
        for field,value in [('source_part_index',False),('source_part_index',0.0),('source_part_index',-1),('source_part_index',[]),('source_feature_key',{})]:
            with self.subTest(field=field,value=value):
                c=case('declared_junction');c['junction_document']['junctions'][0]['members'][0][field]=value
                with self.assertRaises(BuildError) as err: build(c)
                self.assertEqual(err.exception.code,'INVALID_JUNCTION')
    def test_transform_requires_measurement_even_for_metric_target(self):
        with self.assertRaises(BuildError) as err:build(case(),transform=lambda xy:xy)
        self.assertEqual(err.exception.code,'INVALID_CRS')
    def test_collision_error_is_in_registry_and_prose(self):
        with patch('utility_route_lite.core.builder.digest',return_value='forced'):
            with self.assertRaises(BuildError) as err:build(case())
        registry=json.loads((ROOT/'docs/contract/v1.json').read_text())
        self.assertIn(err.exception.code,registry['error_codes'])
        self.assertIn('`'+err.exception.code+'`',(ROOT/'docs/DATA_CONTRACT.md').read_text())
    def test_non_cancellation_measurement_error_still_has_typed_code(self):
        def bad_measure(v):raise ValueError('bad measurement')
        with self.assertRaises(BuildError) as err:build(case(),measure=bad_measure)
        self.assertEqual(err.exception.code,'INVALID_CRS')
if __name__=='__main__':unittest.main()
