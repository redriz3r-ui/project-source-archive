"""Validate the frozen public registry and its architecture documentation.

This is documentation tooling, not plugin implementation. It needs only the
Python standard library and makes no network requests.
"""

import argparse
import json
from pathlib import Path
import re


EXPECTED_ALGORITHMS = (
    "utilityroutelite:build_network",
    "utilityroutelite:inspect_network",
    "utilityroutelite:find_route",
    "utilityroutelite:batch_routes",
    "utilityroutelite:export_bundle",
)
EXPECTED_LAYERS = ("proposed_routes", "route_segments", "qa_issues")
VALID_TYPES = {"TEXT", "REAL", "INTEGER"}


def validate_contract(contract):
    """Return problems instead of hiding incomplete or internally inconsistent IDs."""
    problems = []
    if contract.get("schema_version") != "1.0.0":
        problems.append("schema_version must be 1.0.0")
    if contract.get("provider_id") != "utilityroutelite":
        problems.append("provider_id changed")
    ids = contract.get("algorithm_ids", [])
    if tuple(ids) != EXPECTED_ALGORITHMS:
        problems.append("algorithm_ids changed or reordered")
    algorithms = contract.get("algorithms", {})
    if set(algorithms) != set(EXPECTED_ALGORITHMS):
        problems.append("algorithm definition set differs from public IDs")
    for algorithm_id, definition in algorithms.items():
        if not algorithm_id.startswith(contract.get("provider_id", "") + ":"):
            problems.append(f"wrong provider prefix: {algorithm_id}")
        inputs = definition.get("required_inputs", []) + definition.get("optional_inputs", [])
        outputs = definition.get("outputs", [])
        if len(inputs) != len(set(inputs)) or len(outputs) != len(set(outputs)):
            problems.append(f"duplicate parameter in {algorithm_id}")
        if not outputs:
            problems.append(f"missing output in {algorithm_id}")
        if not all(re.fullmatch(r"[A-Z][A-Z0-9_]*", name) for name in inputs + outputs):
            problems.append(f"invalid parameter spelling in {algorithm_id}")
    if set(contract.get("gpkg_layers", {})) != set(EXPECTED_LAYERS):
        problems.append("GeoPackage layer set changed")
    for layer_name, layer in contract.get("gpkg_layers", {}).items():
        fields = layer.get("fields", [])
        names = [field.get("name") for field in fields]
        if not names or len(names) != len(set(names)):
            problems.append(f"missing/duplicate field in {layer_name}")
        if "schema_version" not in names:
            problems.append(f"missing schema_version in {layer_name}")
        for field in fields:
            if field.get("type") not in VALID_TYPES or not isinstance(field.get("nullable"), bool):
                problems.append(f"invalid field type/nullability in {layer_name}.{field.get('name')}")
    required_fields = {
        "proposed_routes": {"route_id", "graph_digest", "length_m", "review_state"},
        "route_segments": {"route_id", "segment_seq", "edge_id", "source_feature_key", "source_part_index", "from_fraction", "to_fraction"},
        "qa_issues": {"issue_id", "severity", "code", "message"},
    }
    for name, required in required_fields.items():
        missing = required - {field.get("name") for field in contract.get("gpkg_layers", {}).get(name, {}).get("fields", [])}
        if missing:
            problems.append(f"missing required {name} fields: {sorted(missing)}")
    for name, fields in contract.get("csv_files", {}).items():
        if not fields or len(fields) != len(set(fields)):
            problems.append(f"missing/duplicate CSV fields: {name}")
    if set(contract.get("bundle_files", [])) != {"utility_routes.gpkg", "route_summary.csv", "routing_config.json", "report.html"}:
        problems.append("bundle file set changed")
    for enum_name, values in contract.get("enums", {}).items():
        if not values or len(values) != len(set(values)):
            problems.append(f"missing/duplicate values in enum {enum_name}")
    for name in ("connection_policy", "connection_verification", "edge_status", "direction", "review_decision", "request_status"):
        if name not in contract.get("enums", {}):
            problems.append(f"missing enum {name}")
    if not {"NO_ROUTE", "FORBIDDEN_TRANSITION", "STALE_REVIEW", "CANCELED"} <= set(contract.get("error_codes", [])):
        problems.append("critical error code missing")
    if not {"UNDECLARED_CROSSING", "INTERIOR_TOUCH", "Z_M_IGNORED", "INVALID_GEOMETRY"} <= set(contract.get("qa_issue_codes", [])):
        problems.append("critical QA issue code missing")
    if not {"analysis_complete", "counts", "connection_policy"} <= set(contract.get("summary_json_fields", [])):
        problems.append("Inspector summary field missing")
    for file_name, fields in contract.get("json_files", {}).items():
        if "schema_version" not in fields or len(fields) != len(set(fields)):
            problems.append(f"invalid JSON file fields: {file_name}")
    for object_name, fields in contract.get("json_objects", {}).items():
        if not fields or len(fields) != len(set(fields)):
            problems.append(f"missing/duplicate JSON object fields: {object_name}")
    for object_name, required in {
        "rule_profile": {"connection_policy", "eligibility", "direction", "strict"},
        "graph_edge": {"edge_id", "source_feature_key", "vertices_xy", "length_m"},
        "route_segment": {"edge_id", "source_feature_key", "from_fraction", "to_fraction", "vertices_xy"},
        "junction_transition": {"from_member_id", "to_member_id", "from_side", "to_side"},
    }.items():
        missing = required - set(contract.get("json_objects", {}).get(object_name, []))
        if missing:
            problems.append(f"missing required {object_name} fields: {sorted(missing)}")
    limits = contract.get("limits", {})
    if not limits or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in limits.values()):
        problems.append("limits must be positive integers")
    return problems


def validate_docs(root, contract):
    problems = []
    architecture = (root / "docs" / "ARCHITECTURE.md").read_text()
    data = (root / "docs" / "DATA_CONTRACT.md").read_text()
    acceptance = (root / "docs" / "ACCEPTANCE_MATRIX.md").read_text()
    for algorithm_id in EXPECTED_ALGORITHMS:
        if algorithm_id not in architecture or algorithm_id not in data:
            problems.append(f"algorithm not documented in both contracts: {algorithm_id}")
    for name, layer in contract["gpkg_layers"].items():
        if name not in data:
            problems.append(f"GeoPackage layer undocumented: {name}")
        for field in layer["fields"]:
            if field["name"] not in data:
                problems.append(f"GeoPackage field undocumented: {field['name']}")
    for object_name, fields in contract.get("json_objects", {}).items():
        for field in fields:
            if field not in data:
                problems.append(f"JSON object field undocumented: {object_name}.{field}")
    for policy in contract["enums"]["connection_policy"]:
        if policy not in architecture or policy not in data:
            problems.append(f"policy missing from prose: {policy}")
    for token in ("X crossing", "forbidden transition", "same-edge", "GeoPackage", "Not Run"):
        if token.lower() not in acceptance.lower():
            problems.append(f"acceptance matrix lacks {token}")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    contract = json.loads((args.root / "docs" / "contract" / "v1.json").read_text())
    problems = validate_contract(contract) + validate_docs(args.root, contract)
    for problem in problems:
        print("FAIL:", problem)
    if problems:
        raise SystemExit(1)
    print("PASS: frozen contract registry and documentation are internally consistent")


if __name__ == "__main__":
    main()
