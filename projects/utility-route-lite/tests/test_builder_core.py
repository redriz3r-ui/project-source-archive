"""Network Builder tests over invented linear fixtures, without QGIS."""

import json
from pathlib import Path
import unittest

from utility_route_lite.core.builder import BuildError, build_graph
from utility_route_lite.core.serialization import pretty_json


FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "v1"


def graph_for(name):
    case = json.loads((FIXTURES / f"{name}.json").read_text())
    return build_graph(case["source"]["features"], source_crs_wkt=case["source_crs"],
                       network_crs_wkt=case["network_crs"], layer_key=case["source_layer_key"],
                       feature_key_field="asset_key", profile=case["rule_profile"],
                       junctions=case.get("junction_document"), junction_transform=lambda xy: xy)


class BuilderCoreTests(unittest.TestCase):
    def test_false_crossing_is_disconnected(self):
        graph = graph_for("crossing_unconnected")
        self.assertEqual(graph["build_summary"]["component_count"], 2)
        self.assertEqual(len(graph["edges"]), 2)
        self.assertEqual(graph["transitions"], [])
        self.assertIn("UNDECLARED_CROSSING", {issue["code"] for issue in graph["qa_issues"]})
        self.assertEqual(graph["build_summary"]["connection_verification"], "NOT_ASSET_VERIFIED")

    def test_exact_endpoint_is_one_geometric_node(self):
        case = json.loads((FIXTURES / "tiny_endpoint_gap.json").read_text())
        case["source"]["features"][1]["geometry"]["coordinates"][0] = [5, 0]
        graph = build_graph(case["source"]["features"], source_crs_wkt=case["source_crs"],
                            network_crs_wkt=case["network_crs"], layer_key=case["source_layer_key"],
                            feature_key_field="asset_key", profile=case["rule_profile"])
        self.assertEqual(graph["build_summary"]["component_count"], 1)
        self.assertEqual(len([node for node in graph["nodes"] if node["xy"] == [5, 0]]), 1)
        self.assertEqual(graph["build_summary"]["connection_verification"], "NOT_ASSET_VERIFIED")
        self.assertEqual([part["original_vertices"] for part in graph["source_parts"]],
                         [[[0, 0], [5, 0]], [[5, 0], [10, 0]]])
        self.assertEqual(graph["graph_digest"], build_graph(case["source"]["features"],
            source_crs_wkt=case["source_crs"], network_crs_wkt=case["network_crs"],
            layer_key=case["source_layer_key"], feature_key_field="asset_key",
            profile=case["rule_profile"])["graph_digest"])

    def test_t_touch_at_interior_does_not_connect(self):
        case = json.loads((FIXTURES / "crossing_unconnected.json").read_text())
        case["source"]["features"][1]["geometry"]["coordinates"] = [[5, 0], [5, 5]]
        graph = build_graph(case["source"]["features"], source_crs_wkt=case["source_crs"],
                            network_crs_wkt=case["network_crs"], layer_key=case["source_layer_key"],
                            feature_key_field="asset_key", profile=case["rule_profile"])
        self.assertEqual(graph["build_summary"]["component_count"], 2)
        self.assertIn("INTERIOR_TOUCH", {issue["code"] for issue in graph["qa_issues"]})

    def test_explicit_junction_splits_only_members_and_one_direction(self):
        graph = graph_for("declared_junction")
        self.assertEqual(len(graph["edges"]), 4)
        self.assertEqual(graph["build_summary"]["component_count"], 1)
        declared = [transition for transition in graph["transitions"] if transition["declared"]]
        self.assertEqual(len(declared), 1)
        self.assertTrue(declared[0]["from_traversal_id"].endswith(":F"))
        self.assertTrue(declared[0]["to_traversal_id"].endswith(":F"))
        self.assertEqual({(e["source_feature_key"], e["source_part_index"]) for e in graph["edges"]}, {("h", 0), ("v", 0)})

    def test_declared_endpoint_to_interior_transition(self):
        case = json.loads((FIXTURES / "declared_junction.json").read_text())
        case["source"]["features"][0]["geometry"]["coordinates"] = [[0, 0], [5, 0]]
        case["junction_document"]["junctions"][0]["members"][0]["segment_fraction"] = 1.0
        graph = build_graph(case["source"]["features"], source_crs_wkt=case["source_crs"],
                            network_crs_wkt=case["network_crs"], layer_key=case["source_layer_key"],
                            feature_key_field="asset_key", profile=case["rule_profile"],
                            junctions=case["junction_document"], junction_transform=lambda xy: xy)
        self.assertEqual(len(graph["edges"]), 3)
        self.assertEqual(graph["build_summary"]["component_count"], 1)
        self.assertEqual(len([t for t in graph["transitions"] if t["declared"]]), 1)

    def test_prohibited_turn_is_not_invented(self):
        graph = graph_for("prohibited_turn")
        declared = [transition for transition in graph["transitions"] if transition["declared"]]
        self.assertEqual(len(declared), 1)
        self.assertTrue(declared[0]["to_traversal_id"].endswith(":R"))
        self.assertNotIn(declared[0]["to_traversal_id"][:-1] + "F", [t["to_traversal_id"] for t in declared])

    def test_gap_does_not_move_endpoint(self):
        graph = graph_for("tiny_endpoint_gap")
        self.assertEqual(graph["build_summary"]["component_count"], 2)
        self.assertIn("NEAR_MISS", {issue["code"] for issue in graph["qa_issues"]})
        self.assertIn([5.01, 0.0], [node["xy"] for node in graph["nodes"]])

    def test_duplicate_geometry_is_reported_without_merging_edges(self):
        graph = graph_for("duplicate_geometry")
        self.assertEqual(len(graph["edges"]), 2)
        self.assertIn("OVERLAP", {issue["code"] for issue in graph["qa_issues"]})
        self.assertNotEqual(graph["edges"][0]["edge_id"], graph["edges"][1]["edge_id"])

    def test_unknown_status_fails_closed(self):
        case = json.loads((FIXTURES / "crossing_unconnected.json").read_text())
        case["source"]["features"][0]["properties"]["status"] = "mystery"
        graph = build_graph(case["source"]["features"], source_crs_wkt=case["source_crs"],
                            network_crs_wkt=case["network_crs"], layer_key=case["source_layer_key"],
                            feature_key_field="asset_key", profile=case["rule_profile"])
        self.assertEqual(next(e for e in graph["edges"] if e["source_feature_key"] == "h")["edge_status"], "UNKNOWN")
        self.assertIn("UNKNOWN_ELIGIBILITY", {issue["code"] for issue in graph["qa_issues"]})

    def test_bad_junction_coordinate_is_rejected(self):
        case = json.loads((FIXTURES / "declared_junction.json").read_text())
        case["junction_document"]["junctions"][0]["xy"] = [5.01, 0]
        with self.assertRaises(BuildError) as raised:
            build_graph(case["source"]["features"], source_crs_wkt=case["source_crs"],
                        network_crs_wkt=case["network_crs"], layer_key=case["source_layer_key"],
                        feature_key_field="asset_key", profile=case["rule_profile"],
                        junctions=case["junction_document"], junction_transform=lambda xy: xy)
        self.assertEqual(raised.exception.code, "INVALID_JUNCTION")

    def test_multipart_reference_and_deterministic_output(self):
        graph = graph_for("multipart_refs")
        self.assertEqual([p["source_part_index"] for p in graph["source_parts"]], [0, 1])
        self.assertEqual(graph["build_summary"]["component_count"], 2)
        self.assertEqual(pretty_json(graph), pretty_json(graph_for("multipart_refs")))

    def test_1000_edge_benchmark_graph_is_one_component(self):
        graph = graph_for("benchmark_1000")
        self.assertEqual(len(graph["edges"]), 1000)
        self.assertEqual(graph["build_summary"]["component_count"], 1)
        self.assertEqual(sum(edge["length_m"] for edge in graph["edges"]), 1000)

    def test_graph_has_frozen_required_fields_and_source_edge_map(self):
        graph = graph_for("declared_junction")
        registry = json.loads((FIXTURES.parents[2] / "docs" / "contract" / "v1.json").read_text())
        self.assertTrue(set(registry["json_files"]["network_graph.json"]) <= set(graph))
        self.assertTrue(set(registry["json_objects"]["graph_edge"]) <= set(graph["edges"][0]))
        self.assertEqual(sum(len(row["edge_ids"]) for row in graph["build_summary"]["source_to_edges"]), len(graph["edges"]))

    def test_blocked_shortcut_remains_blocked(self):
        graph = graph_for("blocked_shortcut")
        self.assertEqual(next(e for e in graph["edges"] if e["source_feature_key"] == "short")["edge_status"], "BLOCKED")

    def test_bad_source_inputs_fail_with_stable_codes(self):
        for name, code in (("duplicate_source_id", "DUPLICATE_SOURCE_KEY"), ("zero_length_edge", "INVALID_GEOMETRY")):
            with self.subTest(name=name):
                with self.assertRaises(BuildError) as raised:
                    graph_for(name)
                self.assertEqual(raised.exception.code, code)

    def test_z_requires_opt_in_and_preserves_original_ordinates(self):
        case = json.loads((FIXTURES / "crossing_unconnected.json").read_text())
        case["source"]["features"] = [{"geometry": {"type": "LineString", "coordinates": [[0, 0, 7], [1, 0, 8]]},
                                        "properties": {"asset_key": "z", "status": "open", "direction": "both"}}]
        kwargs = {"source_crs_wkt": case["source_crs"], "network_crs_wkt": case["network_crs"],
                  "layer_key": case["source_layer_key"], "feature_key_field": "asset_key"}
        with self.assertRaises(BuildError) as raised:
            build_graph(case["source"]["features"], profile=case["rule_profile"], **kwargs)
        self.assertEqual(raised.exception.code, "UNSUPPORTED_DIMENSION")
        case["rule_profile"]["allow_2d_projection"] = True
        graph = build_graph(case["source"]["features"], profile=case["rule_profile"], **kwargs)
        self.assertEqual(graph["source_parts"][0]["original_vertices"], [[0, 0, 7], [1, 0, 8]])
        self.assertIn("Z_M_IGNORED", {issue["code"] for issue in graph["qa_issues"]})


if __name__ == "__main__":
    unittest.main()
