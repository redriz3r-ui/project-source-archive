"""Independent Gate A regressions. Failures deliberately retain contract expectations."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from utility_route_lite.core.builder import build_graph, BuildError
FIX = ROOT / 'examples/fixtures/v1'
EVIDENCE = ROOT / 'docs/audits/evidence/gate-a'

def case(name='crossing_unconnected'):
    return json.loads((FIX / (name + '.json')).read_text())

def build(c, name=None, features=None, feedback=None):
    g = build_graph(c['source']['features'] if features is None else features,
        source_crs_wkt=c['source_crs'], network_crs_wkt=c['network_crs'],
        layer_key=c['source_layer_key'], feature_key_field='asset_key', profile=c['rule_profile'],
        junctions=c.get('junction_document'), junction_transform=lambda xy: xy, feedback=feedback)
    if name:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / (name + '.json')).write_text(json.dumps(g, indent=2) + '\n')
    return g

class GateTests(unittest.TestCase):
    def test_nonmember_crossing_is_reported(self):
        c = case('declared_junction')
        extra = copy.deepcopy(c['source']['features'][0])
        extra['properties']['asset_key'] = 'other'
        extra['geometry']['coordinates'] = [[0, -5], [10, 5]]
        c['source']['features'].append(extra)
        g = build(c, 'nonmember_crossing')
        self.assertEqual(g['build_summary']['component_count'], 2)
        self.assertIn('UNDECLARED_CROSSING', {q['code'] for q in g['qa_issues']})

    def test_equivalent_vertex_anchor_has_stable_edge_ids(self):
        c = case('declared_junction')
        c['source']['features'][0]['geometry']['coordinates'] = [[0,0],[5,0],[10,0]]
        m = c['junction_document']['junctions'][0]['members'][0]
        m.update(segment_index=0, segment_fraction=1.0)
        a = build(c, 'anchor_left')
        m.update(segment_index=1, segment_fraction=0.0)
        b = build(c, 'anchor_right')
        self.assertEqual([e['edge_id'] for e in a['edges']], [e['edge_id'] for e in b['edges']])

    def test_geographic_core_cannot_label_degrees_meters(self):
        c = case(); c['source_crs'] = c['network_crs'] = 'EPSG:4326'
        c['source']['features'] = c['source']['features'][:1]
        c['source']['features'][0]['geometry']['coordinates'] = [[-122,37],[-121.999,37]]
        with self.assertRaises(BuildError):
            build(c, 'degrees_as_meters')

    def test_false_dimension_flags_cannot_silently_connect_stacked_lines(self):
        c = case()
        for f, coords in zip(c['source']['features'], ([[0,0,1],[5,0,1]], [[5,0,9],[10,0,9]])):
            f['geometry']['coordinates'] = coords
            f.update(has_z=False, has_m=False)
        with self.assertRaises(BuildError):
            build(c, 'stacked_flags')

    def test_cancel_before_consuming_generator(self):
        c = case(); consumed = []
        def source():
            for i in range(10000):
                consumed.append(i)
                yield c['source']['features'][0]
        class Canceled:
            def isCanceled(self): return True
        with self.assertRaises(BuildError) as raised:
            build(c, features=source(), feedback=Canceled())
        self.assertEqual(raised.exception.code, 'CANCELED')
        self.assertLessEqual(len(consumed), 1)

    def test_closed_self_loop_rejected(self):
        c = case(); c['source']['features'] = c['source']['features'][:1]
        c['source']['features'][0]['geometry']['coordinates'] = [[0,0],[1,0],[1,1],[0,0]]
        with self.assertRaises(BuildError): build(c, 'self_loop')

    def test_crossing_at_interior_vertices_is_reported(self):
        c = case()
        c['source']['features'][0]['geometry']['coordinates'] = [[0,0],[5,0],[10,0]]
        c['source']['features'][1]['geometry']['coordinates'] = [[5,-5],[5,0],[5,5]]
        g = build(c, 'vertex_crossing')
        self.assertEqual(g['build_summary']['component_count'], 2)
        self.assertIn('UNDECLARED_CROSSING', {q['code'] for q in g['qa_issues']})

    def test_ambiguous_self_intersection_anchor_rejected(self):
        c = case('declared_junction')
        c['source']['features'][0]['geometry']['coordinates'] = [[0,0],[10,10],[0,10],[10,0]]
        c['source']['features'][1]['geometry']['coordinates'] = [[5,5],[5,6]]
        j = c['junction_document']['junctions'][0]; j['xy'] = [5,5]
        j['members'][1]['segment_fraction'] = 0.0
        with self.assertRaises(BuildError): build(c, 'ambiguous_anchor')

    def test_controls(self):
        for name, count in [('crossing_unconnected',2),('tiny_endpoint_gap',2),('multipart_refs',2)]:
            with self.subTest(name=name):
                self.assertEqual(build(case(name))['build_summary']['component_count'], count)
        g = build(case('prohibited_turn'))
        self.assertEqual(len([t for t in g['transitions'] if t['declared']]),1)
        self.assertIn('OVERLAP', {q['code'] for q in build(case('duplicate_geometry'))['qa_issues']})

if __name__ == '__main__': unittest.main()
