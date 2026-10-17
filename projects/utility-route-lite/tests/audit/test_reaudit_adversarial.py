"""Independent contract assertions beyond the developer's remediation examples."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from utility_route_lite.core import builder
from utility_route_lite.core.serialization import digest,pretty_json

def fixture(name='crossing_unconnected'):
    return json.loads((ROOT/'examples/fixtures/v1'/f'{name}.json').read_text())
def build(c,**extra):
    return builder.build_graph(c['source']['features'],source_crs_wkt=c['source_crs'],network_crs_wkt=c['network_crs'],layer_key=c['source_layer_key'],feature_key_field='asset_key',profile=c['rule_profile'],junctions=c.get('junction_document'),junction_transform=lambda xy:xy,**extra)

class ReauditAdversarial(unittest.TestCase):
    def test_transform_alone_cannot_authorize_degree_lengths(self):
        c=fixture();c['source_crs']=c['network_crs']='EPSG:4326'
        c['source']['features']=c['source']['features'][:1]
        c['source']['features'][0]['geometry']['coordinates']=[[-122,37],[-121.999,37]]
        with self.assertRaises(builder.BuildError) as err:
            graph=build(c,transform=lambda xy:xy)
            print('OBSERVED geographic length_m:',graph['edges'][0]['length_m'])
        self.assertEqual(err.exception.code,'INVALID_CRS')

    def test_valid_full_meter_wkt_in_pure_mode(self):
        c=fixture();c['source_crs']=c['network_crs']=(ROOT/'scripts/epsg3857.wkt').read_text()
        graph=build(c)
        self.assertEqual(graph['build_summary']['component_count'],2)
        self.assertEqual(sorted(e['length_m'] for e in graph['edges']),[10.0,10.0])

    def test_measurement_cancellation_keeps_canceled_code(self):
        def canceled(vertices): raise builder.BuildError('CANCELED','callback canceled')
        with self.assertRaises(builder.BuildError) as err: build(fixture(),measure=canceled)
        self.assertEqual(err.exception.code,'CANCELED')

    def test_junction_scan_stops_promptly_on_cancel(self):
        c=fixture('declared_junction')
        c['source']['features'][0]['geometry']['coordinates']=[[i,0] for i in range(10001)]
        j=c['junction_document']['junctions'][0];j['xy']=[0.5,0]
        c['source']['features'][1]['geometry']['coordinates']=[[0.5,-1],[0.5,1]]
        class Feedback:
            canceled=False
            def isCanceled(self): return self.canceled
        feedback=Feedback(); calls=[]; original=builder._point_on_segment
        def cancel_in_scan(*args):
            calls.append(1);feedback.canceled=True
            return original(*args)
        with patch.object(builder,'_point_on_segment',side_effect=cancel_in_scan):
            with self.assertRaises(builder.BuildError) as err: build(c,feedback=feedback)
        self.assertEqual(err.exception.code,'CANCELED')
        print('OBSERVED segment checks after cancellation:',len(calls))
        self.assertLessEqual(len(calls),1024,'unbounded scan continued after cancellation')

    def test_junction_invalid_part_index_is_not_boolean(self):
        c=fixture('declared_junction');c['junction_document']['junctions'][0]['members'][0]['source_part_index']=False
        with self.assertRaises(builder.BuildError) as err: build(c)
        self.assertEqual(err.exception.code,'INVALID_JUNCTION')

    def test_controls_and_complete_json_roundtrip(self):
        for name in ('crossing_unconnected','declared_junction','prohibited_turn','duplicate_geometry','multipart_refs'):
            with self.subTest(case=name):
                c=fixture(name);g=build(c); roundtrip=json.loads(pretty_json(g))
                self.assertEqual(g,roundtrip)
                self.assertEqual(g['graph_digest'],digest([g['schema_version'],g['network_crs_wkt'],g['source_snapshot_sha256'],g['profile_hash'],g['junctions_sha256'],g['nodes'],g['edges'],g['transitions'],g['measurement']]))
                c['source']['features'].reverse();rev=build(c)
                self.assertEqual(g,rev)
        self.assertEqual(build(fixture())['build_summary']['component_count'],2)
        explicit=build(fixture('declared_junction'))
        self.assertEqual(len([t for t in explicit['transitions'] if t['declared']]),1)

if __name__=='__main__': unittest.main()
