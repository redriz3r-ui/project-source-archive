"""Permanent Builder regressions supplementing the independent Gate A suite."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from utility_route_lite.core.serialization import digest as real_digest
from utility_route_lite.core.builder import BuildError, build_graph
from utility_route_lite.core.serialization import pretty_json

FIX = Path(__file__).resolve().parents[1] / 'examples/fixtures/v1'

def fixture(name='crossing_unconnected'):
    return json.loads((FIX / (name + '.json')).read_text())

def run(case, *, feedback=None):
    return build_graph(case['source']['features'], source_crs_wkt=case['source_crs'],
                       network_crs_wkt=case['network_crs'], layer_key=case['source_layer_key'],
                       feature_key_field='asset_key', profile=case['rule_profile'],
                       junctions=case.get('junction_document'), junction_transform=lambda xy: xy,
                       feedback=feedback)

class GateARegressionTests(unittest.TestCase):
    def test_order_serialization_and_attribute_identity(self):
        c = fixture('duplicate_geometry')
        a = run(c)
        c['source']['features'].reverse()
        b = run(c)
        self.assertEqual(a['graph_digest'], b['graph_digest'])
        self.assertEqual(pretty_json(a), pretty_json(b))
        self.assertEqual(json.loads(pretty_json(a)), a)
        c['source']['features'][0]['properties']['status'] = 'blocked'
        changed = run(c)
        self.assertNotEqual(a['source_snapshot_sha256'], changed['source_snapshot_sha256'])
        self.assertNotEqual(a['graph_digest'], changed['graph_digest'])
        self.assertEqual({e['edge_id'] for e in a['edges']}, {e['edge_id'] for e in changed['edges']})

    def test_typed_selected_attributes_are_distinct_and_unknown(self):
        c = fixture(); c['source']['features'] = c['source']['features'][:1]
        variants = [None, False, 0, 0.0, '0', 1, 1.0, '0x1.0000000000000p+0']
        hashes = []
        for raw in variants:
            c['source']['features'][0]['properties']['status'] = raw
            graph = run(c)
            hashes.append(graph['source_snapshot_sha256'])
            self.assertEqual(graph['edges'][0]['edge_status'], 'UNKNOWN')
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_explicit_dimension_modes_and_mixed_arity(self):
        for flags, vertices in [({'has_z':True, 'has_m':False}, [[0,0,2],[1,0,3]]),
                                ({'has_z':False, 'has_m':True}, [[0,0,2],[1,0,3]]),
                                ({'has_z':True, 'has_m':True}, [[0,0,2,4],[1,0,3,5]])]:
            with self.subTest(flags=flags):
                c = fixture(); c['source']['features'] = c['source']['features'][:1]
                f = c['source']['features'][0]; f['geometry']['coordinates'] = vertices; f.update(flags)
                with self.assertRaises(BuildError) as err: run(c)
                self.assertEqual(err.exception.code, 'UNSUPPORTED_DIMENSION')
                c['rule_profile']['allow_2d_projection'] = True
                g = run(c)
                self.assertEqual(g['source_parts'][0]['original_vertices'], vertices)
                self.assertIn('Z_M_IGNORED', {q['code'] for q in g['qa_issues']})
        c = fixture(); c['source']['features'] = c['source']['features'][:1]
        c['source']['features'][0]['geometry']['coordinates'] = [[0,0],[1,0,3]]
        with self.assertRaises(BuildError): run(c)

    def test_collision_abort_instead_of_node_or_edge_merge(self):
        c = fixture(); c['source']['features'] = c['source']['features'][:1]
        with patch('utility_route_lite.core.builder.digest', return_value='forced'):
            with self.assertRaises(BuildError) as err: run(c)
        self.assertEqual(err.exception.code, 'ID_COLLISION')
        c = fixture('duplicate_geometry')
        def collide_edges(payload):
            return 'forced' if isinstance(payload, list) and payload and payload[0] == 'edge' else real_digest(payload)
        with patch('utility_route_lite.core.builder.digest', side_effect=collide_edges):
            with self.assertRaises(BuildError) as err: run(c)
        self.assertEqual(err.exception.code, 'ID_COLLISION')

    def test_declared_junction_uses_network_crs_and_member_pair(self):
        c = fixture('declared_junction')
        # The junction source coordinate is displaced; the callback restores network XY.
        c['junction_document']['junctions'][0]['xy'] = [105, 100]
        def transformed():
            return build_graph(c['source']['features'], source_crs_wkt=c['source_crs'],
                network_crs_wkt=c['network_crs'], layer_key=c['source_layer_key'],
                feature_key_field='asset_key', profile=c['rule_profile'],
                junctions=c['junction_document'], junction_transform=lambda xy: [xy[0]-100,xy[1]-100])
        g = transformed()
        self.assertEqual(g['build_summary']['component_count'], 1)
        self.assertNotIn('UNDECLARED_CROSSING', {q['code'] for q in g['qa_issues']})

    def test_t_at_intermediate_vertex_stays_disconnected_and_warns(self):
        c = fixture()
        c['source']['features'][0]['geometry']['coordinates'] = [[0,0],[5,0],[10,0]]
        c['source']['features'][1]['geometry']['coordinates'] = [[5,0],[5,5]]
        g = run(c)
        self.assertEqual(g['build_summary']['component_count'],2)
        self.assertIn('INTERIOR_TOUCH',{q['code'] for q in g['qa_issues']})

    def test_cancellation_during_geometry_processing(self):
        c = fixture('benchmark_1000')
        class Feedback:
            calls = 0
            def isCanceled(self):
                self.calls += 1
                return self.calls > 200
        with self.assertRaises(BuildError) as err: run(c, feedback=Feedback())
        self.assertEqual(err.exception.code, 'CANCELED')

    def test_pure_mode_rejects_projected_foot_wkt(self):
        c = fixture(); c['source']['features'] = c['source']['features'][:1]
        c['source_crs'] = c['network_crs'] = 'PROJCRS["Foot",CS[Cartesian,2],AXIS["X",east,LENGTHUNIT["foot",0.3048]],AXIS["Y",north,LENGTHUNIT["foot",0.3048]]]'
        with self.assertRaises(BuildError) as err: run(c)
        self.assertEqual(err.exception.code, 'INVALID_CRS')

if __name__ == '__main__': unittest.main()
