"""Test-only seam for the forthcoming graph services.

Implement this adapter when core services land. Return a normalized observation:
build_status, build_error, qa_codes, component_count, route_status,
failure_code, length_m, source_parts, route_vertices_xy, directions,
excluded_source_keys, connection_verification, batch_statuses,
batch_failure_codes, batch_lengths_m, rendered_html, escaped_csv_cell,
physical_edge_count. Only keys relevant to a fixture need values.
"""


def evaluate_fixture(case):
    raise NotImplementedError("RED TEST: wire this test adapter to implemented graph, QA, routing and export services")
