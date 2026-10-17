"""Deterministically regenerate synthetic, versioned source fixtures and oracles."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "fixtures" / "v1"
VERSION = "1.0.0"
EPSG3857_WKT = Path(__file__).with_name("epsg3857.wkt").read_text(encoding="utf-8").strip()


def line(key, coordinates, status="open", direction="both"):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": {"asset_key": key, "status": status, "direction": direction}}


def multi(key, parts):
    feature = line(key, [])
    feature["geometry"] = {"type": "MultiLineString", "coordinates": parts}
    return feature


def profile(policy="GEOMETRIC_ENDPOINT_ONLY", near=0.02):
    return {"schema_version": VERSION, "profile_id": "synthetic_v1", "connection_policy": policy,
            "eligibility": {"mode": "FIELD", "field": "status", "map": {"open": "OPEN", "blocked": "BLOCKED", "unknown": "UNKNOWN"}},
            "direction": {"mode": "FIELD", "field": "direction", "map": {"both": "BOTH", "forward": "FORWARD", "reverse": "REVERSE"}},
            "ellipsoid": "NONE", "allow_2d_projection": False, "qa_near_miss_m": near, "strict": True}


def request(start, end, tolerance=0):
    return {"route_id": "route_1", "start_xy": start, "end_xy": end,
            "request_crs": "EPSG:3857", "snap_tolerance_m": tolerance}


def fixture(case_id, features, expected, *, policy="GEOMETRIC_ENDPOINT_ONLY", near=0.02,
            route=None, junctions=None, source_crs="EPSG:3857", network_crs="EPSG:3857", batch=None,
            extra=None):
    result = {"schema_version": VERSION, "case_id": case_id, "synthetic": True,
              "source_layer_key": "synthetic_corridors", "source_crs": source_crs,
              "network_crs": network_crs, "rule_profile": profile(policy, near),
              "source": {"type": "FeatureCollection", "features": features},
              "expected": expected}
    if route is not None:
        result["request"] = route
    if junctions is not None:
        result["junction_document"] = junctions
    if batch is not None:
        result["batch_requests"] = batch
    if extra is not None:
        result["test_text"] = extra
    return result


def junction(transitions):
    return {"schema_version": VERSION, "junction_crs_wkt": EPSG3857_WKT, "junctions": [{
        "junction_id": "j_cross", "xy": [5, 0],
        "members": [
            {"member_id": "h", "source_layer_key": "synthetic_corridors", "source_feature_key": "h",
             "source_part_index": 0, "segment_index": 0, "segment_fraction": 0.5},
            {"member_id": "v", "source_layer_key": "synthetic_corridors", "source_feature_key": "v",
             "source_part_index": 0, "segment_index": 0, "segment_fraction": 0.5}],
        "transitions": transitions}]}


def transition(to_side="TO_END"):
    return {"from_member_id": "h", "from_side": "FROM_START", "to_member_id": "v", "to_side": to_side}


def cases():
    cross = [line("h", [[0, 0], [10, 0]]), line("v", [[5, -5], [5, 5]])]
    yield fixture("crossing_unconnected", cross,
                  {"build_status": "OK", "route_status": "FAILED", "failure_code": "NO_ROUTE",
                   "qa_codes_include": ["UNDECLARED_CROSSING"], "component_count": 2},
                  route=request([0, 0], [5, 5]))
    yield fixture("declared_junction", cross,
                  {"build_status": "OK", "route_status": "SUCCESS", "length_m": 10.0,
                   "source_parts": [["h", 0], ["v", 0]], "connection_verification": "DECLARED_TRANSITIONS_NOT_FIELD_VERIFIED"},
                  policy="EXPLICIT_JUNCTIONS", junctions=junction([transition()]),
                  route=request([0, 0], [5, 5]))
    yield fixture("prohibited_turn", cross,
                  {"build_status": "OK", "route_status": "FAILED", "failure_code": "NO_ROUTE",
                   "forbidden_transition": ["h", "FROM_START", "v", "TO_END"]},
                  policy="EXPLICIT_JUNCTIONS", junctions=junction([transition("TO_START")]),
                  route=request([0, 0], [5, 5]))
    yield fixture("tiny_endpoint_gap", [line("a", [[0, 0], [5, 0]]), line("b", [[5.01, 0], [10, 0]])],
                  {"build_status": "OK", "route_status": "FAILED", "failure_code": "NO_ROUTE",
                   "qa_codes_include": ["NEAR_MISS"], "component_count": 2},
                  route=request([0, 0], [10, 0]))
    yield fixture("disconnected_components", [line("a", [[0, 0], [2, 0]]), line("b", [[20, 0], [22, 0]])],
                  {"build_status": "OK", "route_status": "FAILED", "failure_code": "NO_ROUTE",
                   "qa_codes_include": ["DISCONNECTED_COMPONENT"], "component_count": 2},
                  route=request([0, 0], [22, 0]))
    yield fixture("duplicate_source_id", [line("dup", [[0, 0], [1, 0]]), line("dup", [[1, 0], [2, 0]])],
                  {"build_status": "FAILED", "build_error": "DUPLICATE_SOURCE_KEY"})
    yield fixture("duplicate_geometry", [line("a", [[0, 0], [2, 0]]), line("b", [[0, 0], [2, 0]])],
                  {"build_status": "OK", "qa_codes_include": ["OVERLAP"],
                   "route_status": "FAILED", "failure_code": "AMBIGUOUS_SNAP"},
                  route=request([1, 0], [2, 0]))
    yield fixture("zero_length_edge", [line("zero", [[1, 1], [1, 1]])],
                  {"build_status": "FAILED", "build_error": "INVALID_GEOMETRY",
                   "qa_codes_include": ["INVALID_GEOMETRY"]})
    yield fixture("multipart_refs", [multi("multi", [[[0, 0], [2, 0]], [[10, 0], [10, 4]]])],
                  {"build_status": "OK", "route_status": "SUCCESS", "length_m": 4.0,
                   "source_parts": [["multi", 1]], "component_count": 2},
                  route=request([10, 0], [10, 4]))
    yield fixture("blocked_shortcut", [line("short", [[0, 0], [10, 0]], status="blocked"),
                                       line("detour_a", [[0, 0], [0, 5]]),
                                       line("detour_b", [[0, 5], [10, 5]]),
                                       line("detour_c", [[10, 5], [10, 0]])],
                  {"build_status": "OK", "route_status": "SUCCESS", "length_m": 20.0,
                   "source_parts": [["detour_a", 0], ["detour_b", 0], ["detour_c", 0]],
                   "excluded_source_keys": ["short"]}, route=request([0, 0], [10, 0]))
    yield fixture("same_bent_line_interior", [line("bend", [[0, 0], [0, 5], [5, 5], [5, 0]])],
                  {"build_status": "OK", "route_status": "SUCCESS", "length_m": 11.0,
                   "source_parts": [["bend", 0]],
                   "route_vertices_xy": [[0, 2], [0, 5], [5, 5], [5, 2]]},
                  route=request([0, 2], [5, 2]))
    yield fixture("outside_snap_tolerance", [line("a", [[0, 0], [10, 0]])],
                  {"build_status": "OK", "route_status": "FAILED", "failure_code": "OUTSIDE_SNAP_TOLERANCE"},
                  route=request([0, 1.001], [10, 0], tolerance=1))
    geographic = fixture("geographic_metric", [line("geo", [[-122.0, 37.0], [-121.999, 37.0]])],
                         {"build_status": "OK", "route_status": "SUCCESS", "length_m_range": [88, 90],
                          "source_parts": [["geo", 0]], "measurement_unit": "m"},
                         source_crs="EPSG:4326", network_crs="EPSG:32610",
                         route={"route_id": "route_1", "start_xy": [-122.0, 37.0],
                                "end_xy": [-121.999, 37.0], "request_crs": "EPSG:4326", "snap_tolerance_m": 0})
    geographic["rule_profile"]["ellipsoid"] = "WGS84"
    yield geographic
    yield fixture("reverse_direction", [line("reverse", [[0, 0], [10, 0]], direction="reverse")],
                  {"build_status": "OK", "route_status": "SUCCESS", "length_m": 10.0,
                   "source_parts": [["reverse", 0]], "route_vertices_xy": [[10, 0], [0, 0]],
                   "directions": ["REVERSE"]}, route=request([10, 0], [0, 0]))
    yield fixture("same_start_end", [line("a", [[0, 0], [10, 0]])],
                  {"build_status": "OK", "route_status": "FAILED", "failure_code": "SAME_LOCATION"},
                  route=request([3, 0], [3, 0]))
    yield fixture("batch_one_bad_record", [line("a", [[0, 0], [10, 0]])],
                  {"build_status": "OK", "batch_statuses": ["SUCCESS", "FAILED", "SUCCESS"],
                   "batch_failure_codes": [None, "INVALID_PAIR", None], "batch_lengths_m": [10, None, 4]},
                  batch=[{"input_row": 1, "route_id": "r_1", "start_xy": [0, 0], "end_xy": [10, 0]},
                         {"input_row": 2, "route_id": "r_bad", "start_xy": "not-a-point", "end_xy": [5, 0]},
                         {"input_row": 3, "route_id": "r_3", "start_xy": [2, 0], "end_xy": [6, 0]}])
    yield fixture("csv_html_escaping", [line("safe", [[0, 0], [1, 0]])],
                  {"build_status": "OK", "route_status": "SUCCESS", "length_m": 1.0,
                   "html_must_contain": "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;",
                   "csv_cell_must_start": "'=HYPERLINK"}, route=request([0, 0], [1, 0]),
                  extra={"review_note": "=HYPERLINK(\"https://invalid.example\",\"x\") <script>alert('x')</script>"})


def benchmark(edge_count):
    if edge_count not in (1000, 10000, 50000):
        raise ValueError("supported edge counts: 1000, 10000, 50000")
    return fixture(f"benchmark_{edge_count}",
                   [line(f"edge_{i:05d}", [[i, 0], [i + 1, 0]]) for i in range(edge_count)],
                   {"build_status": "OK", "route_status": "SUCCESS", "length_m": float(edge_count),
                    "physical_edge_count": edge_count, "component_count": 1},
                   route=request([0, 0], [edge_count, 0]))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def regenerate(directory=OUT, include_benchmark=True):
    directory = Path(directory)
    items = list(cases())
    for item in items:
        write_json(directory / f"{item['case_id']}.json", item)
    if include_benchmark:
        write_json(directory / "benchmark_1000.json", benchmark(1000))
    write_json(directory / "manifest.json", {"schema_version": VERSION, "synthetic": True,
               "case_ids": [item["case_id"] for item in items], "benchmark_id": "benchmark_1000"})
    return len(items)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--scale", type=int, choices=(10000, 50000), help="generate only a large benchmark")
    args = parser.parse_args()
    if args.scale:
        target = args.output / f"benchmark_{args.scale}.json"
        write_json(target, benchmark(args.scale))
        print(target)
    else:
        print(f"generated {regenerate(args.output)} synthetic cases and one 1000-edge benchmark in {args.output}")
