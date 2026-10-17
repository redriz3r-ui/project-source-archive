"""Validate linear parts and build a policy-controlled 2D pathway graph."""

import math
import re
import unicodedata
from collections import defaultdict

from .serialization import digest


VERSION = "1.0.0"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class BuildError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}: {message}")


def _finite_xy(value, code="INVALID_GEOMETRY"):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise BuildError(code, "expected a finite 2D coordinate")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise BuildError(code, "coordinate is not finite")
    return [float(v) if v != 0 else 0.0 for v in value]


def _id(value, kind):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise BuildError("UNSUPPORTED_RULE", f"invalid {kind}")
    return value


def _validate_profile(profile):
    expected = {"schema_version", "profile_id", "connection_policy", "eligibility", "direction",
                "ellipsoid", "allow_2d_projection", "qa_near_miss_m", "strict"}
    if not isinstance(profile, dict) or set(profile) != expected or profile.get("schema_version") != VERSION:
        raise BuildError("UNSUPPORTED_RULE", "rule profile keys/version do not match v1")
    _id(profile["profile_id"], "profile_id")
    if profile["connection_policy"] not in ("GEOMETRIC_ENDPOINT_ONLY", "EXPLICIT_JUNCTIONS"):
        raise BuildError("UNSUPPORTED_RULE", "unknown connection policy")
    if profile["ellipsoid"] not in ("NONE", "WGS84") or profile["strict"] is not True:
        raise BuildError("UNSUPPORTED_RULE", "unsupported measurement or non-strict mode")
    if not isinstance(profile["allow_2d_projection"], bool):
        raise BuildError("UNSUPPORTED_RULE", "allow_2d_projection must be boolean")
    near = profile["qa_near_miss_m"]
    if isinstance(near, bool) or not isinstance(near, (int, float)) or not math.isfinite(near) or near < 0:
        raise BuildError("UNSUPPORTED_RULE", "invalid near-miss threshold")
    for name, modes, labels in (("eligibility", ("FIELD", "ALL_OPEN"), {"OPEN", "BLOCKED", "UNKNOWN"}),
                                ("direction", ("FIELD", "ALL_BOTH"), {"FORWARD", "REVERSE", "BOTH", "UNKNOWN"})):
        rule = profile[name]
        if not isinstance(rule, dict) or rule.get("mode") not in modes:
            raise BuildError("UNSUPPORTED_RULE", f"invalid {name} rule")
        if rule["mode"] == "FIELD":
            if set(rule) != {"mode", "field", "map"} or not isinstance(rule["field"], str) or not rule["field"]:
                raise BuildError("UNSUPPORTED_RULE", f"invalid {name} field")
            if not isinstance(rule["map"], dict) or not rule["map"] or any(
                not isinstance(k, str) or not isinstance(v, str) or v not in labels for k, v in rule["map"].items()
            ):
                raise BuildError("UNSUPPORTED_RULE", f"invalid {name} map")
        elif set(rule) != {"mode"}:
            raise BuildError("UNSUPPORTED_RULE", f"unexpected {name} rule keys")


def _measure_planar(vertices):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(vertices, vertices[1:]))


def _check_canceled(feedback):
    if feedback is not None and feedback.isCanceled():
        raise BuildError("CANCELED", "build canceled")


def _metric_crs(crs):
    """Known synthetic CRS fast path; delegate all CRS parsing to QGIS."""
    if not isinstance(crs, str):
        return False
    if crs.strip().upper() == "EPSG:3857":
        return True
    try:
        from ..qgis_adapters.crs import is_projected_meters
    except ImportError:
        return False
    return is_projected_meters(crs)


def _fingerprint_value(value):
    """Keep field types distinct, including float versus a float-looking string."""
    if value is None:
        return ["null", None]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float) and math.isfinite(value):
        return ["float", value]
    if isinstance(value, str):
        return ["str", value]
    raise BuildError("UNSUPPORTED_RULE", "selected source attribute has unsupported or nonfinite type")


def _interpolate(a, b, fraction):
    if fraction == 0:
        return list(a)
    if fraction == 1:
        return list(b)
    return [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction]


def _clip(vertices, start, end):
    n = len(vertices) - 1
    def point(pos):
        if pos == n:
            return vertices[-1]
        index = int(pos)
        return _interpolate(vertices[index], vertices[index + 1], pos - index)
    result = [point(start)]
    result.extend(vertices[i] for i in range(math.floor(start) + 1, math.ceil(end)) if start < i < end)
    result.append(point(end))
    return result


def _segment_relation(a, b, c, d):
    """Return interior crossing, overlap, interior touch, or None for two segments."""
    ax, ay = a; bx, by = b; cx, cy = c; dx, dy = d
    rx, ry = bx - ax, by - ay; sx, sy = dx - cx, dy - cy
    cross = rx * sy - ry * sx
    qpx, qpy = cx - ax, cy - ay
    if cross == 0:
        if qpx * ry - qpy * rx != 0:
            return None
        axis = 0 if abs(rx) >= abs(ry) else 1
        lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
        hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
        return ("OVERLAP", None) if lo < hi else None
    t = (qpx * sy - qpy * sx) / cross
    u = (qpx * ry - qpy * rx) / cross
    if 0 <= t <= 1 and 0 <= u <= 1:
        if 0 < t < 1 and 0 < u < 1:
            return "UNDECLARED_CROSSING", _interpolate(a, b, t)
        if (0 < t < 1) != (0 < u < 1):
            return "INTERIOR_TOUCH", _interpolate(a, b, t)
        return "CONTACT", _interpolate(a, b, t)
    return None


def _point_on_segment(point, a, b):
    return ((point[0] - a[0]) * (b[1] - a[1]) == (point[1] - a[1]) * (b[0] - a[0])
            and min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= point[1] <= max(a[1], b[1]))


def build_graph(features, *, source_crs_wkt, network_crs_wkt, layer_key, feature_key_field,
                profile, junctions=None, transform=None, junction_transform=None, measure=None,
                qgis_version="PURE_PYTHON", feedback=None):
    """Build a graph from read-only feature snapshots; callbacks own CRS/metric work.

    Pure mode permits only identical declared metric CRS and explicit planar length.
    A QGIS adapter must provide transform and measure callbacks otherwise.
    """
    _validate_profile(profile)
    _id(layer_key, "layer_key")
    if not isinstance(feature_key_field, str) or not feature_key_field:
        raise BuildError("UNSUPPORTED_RULE", "feature key field required")
    if not source_crs_wkt or not network_crs_wkt:
        raise BuildError("INVALID_CRS", "declared source and network CRS required")
    if not _metric_crs(network_crs_wkt):
        raise BuildError("INVALID_CRS", "network CRS must be projected meters; full CRS validation requires QGIS")
    if transform is not None and measure is None:
        raise BuildError("INVALID_CRS", "transform callback requires a metric measurement callback")
    if transform is None:
        if source_crs_wkt != network_crs_wkt or profile["ellipsoid"] != "NONE":
            raise BuildError("INVALID_CRS", "pure mode needs identical metric CRS and planar measurement")
        transform = lambda xy: xy
    if measure is None:
        if profile["ellipsoid"] != "NONE":
            raise BuildError("INVALID_CRS", "ellipsoidal measurement requires a QGIS metric callback")
        measure = _measure_planar
    policy = profile["connection_policy"]
    if (policy == "EXPLICIT_JUNCTIONS") != (junctions is not None):
        raise BuildError("INVALID_JUNCTION", "junction document presence must match policy")
    _check_canceled(feedback)
    seen_keys = set(); parts = []; issue_inputs = []
    source_hash_rows = []
    vertex_count = 0
    for feature in features:
        _check_canceled(feedback)
        props = feature.get("properties")
        if not isinstance(props, dict):
            raise BuildError("INVALID_GEOMETRY", "feature properties missing")
        key = props.get(feature_key_field)
        if not isinstance(key, str) or not key.strip() or len(key.encode("utf-8")) > 128:
            raise BuildError("DUPLICATE_SOURCE_KEY", "missing or invalid persistent source key")
        if unicodedata.normalize("NFC", key) != key:
            raise BuildError("DUPLICATE_SOURCE_KEY", "source key must use Unicode NFC")
        if key in seen_keys:
            raise BuildError("DUPLICATE_SOURCE_KEY", f"duplicate source key {key!r}")
        seen_keys.add(key)
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "LineString":
            sequences = [geometry.get("coordinates")]
        elif geometry.get("type") == "MultiLineString":
            sequences = geometry.get("coordinates")
        else:
            raise BuildError("INVALID_GEOMETRY", f"unsupported geometry for {key!r}")
        if not isinstance(sequences, list) or not sequences:
            raise BuildError("INVALID_GEOMETRY", f"empty geometry for {key!r}")
        statuses = {}
        for name, default, unknown_code in (("eligibility", "OPEN", "UNKNOWN_ELIGIBILITY"),
                                             ("direction", "BOTH", "UNKNOWN_DIRECTION")):
            rule = profile[name]
            if rule["mode"] == "FIELD":
                raw = props.get(rule["field"])
                statuses[name] = rule["map"].get(raw, "UNKNOWN") if isinstance(raw, str) else "UNKNOWN"
                if statuses[name] == "UNKNOWN":
                    issue_inputs.append((unknown_code, None, key, None, None, "Unrecognized or missing rule value"))
            else:
                statuses[name] = default
                issue_inputs.append((("ELIGIBILITY_ASSUMED" if name == "eligibility" else "DIRECTION_ASSUMED"),
                                     None, key, None, None, "Explicit all-open/all-both assumption"))
        source_hash_rows.append([key, geometry, {name: _fingerprint_value(props.get(profile[name].get("field")))
                                                for name in ("eligibility", "direction")}])
        for part_index, raw_vertices in enumerate(sequences):
            _check_canceled(feedback)
            if not isinstance(raw_vertices, list) or len(raw_vertices) < 2:
                raise BuildError("INVALID_GEOMETRY", f"part {key}/{part_index} has fewer than two vertices")
            vertex_count += len(raw_vertices)
            if vertex_count > 2_000_000 or len(parts) >= 250_000:
                raise BuildError("LIMIT_EXCEEDED", "source vertex/part limit exceeded")
            for flag in ("has_z", "has_m"):
                if flag in feature and not isinstance(feature[flag], bool):
                    raise BuildError("UNSUPPORTED_DIMENSION", f"{flag} must be boolean")
            dimensions = {len(v) for v in raw_vertices if isinstance(v, (list, tuple))}
            if len(dimensions) != 1 or any(not isinstance(v, (list, tuple)) for v in raw_vertices):
                raise BuildError("UNSUPPORTED_DIMENSION", f"mixed coordinate dimensions in {key}/{part_index}")
            arity = next(iter(dimensions)) if dimensions else 0
            if arity not in (2, 3, 4):
                raise BuildError("INVALID_GEOMETRY", "invalid source ordinate count")
            has_z = feature.get("has_z", arity > 2)
            has_m = feature.get("has_m", False)
            if arity != 2 + int(has_z) + int(has_m):
                raise BuildError("UNSUPPORTED_DIMENSION", f"coordinate arity and Z/M flags disagree in {key}/{part_index}")
            if (has_z or has_m) and not profile["allow_2d_projection"]:
                raise BuildError("UNSUPPORTED_DIMENSION", f"Z/M part {key}/{part_index} needs opt-in")
            original = []
            vertices = []
            for vertex in raw_vertices:
                _check_canceled(feedback)
                if not isinstance(vertex, (list, tuple)) or len(vertex) not in (2, 3, 4):
                    raise BuildError("INVALID_GEOMETRY", "invalid source ordinate count")
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vertex):
                    raise BuildError("INVALID_GEOMETRY", "nonfinite source ordinate")
                original.append([float(v) if v != 0 else 0.0 for v in vertex])
                try:
                    vertices.append(_finite_xy(transform(original[-1][:2]), "TRANSFORM_FAILED"))
                except BuildError:
                    raise
                except Exception as exc:
                    raise BuildError("TRANSFORM_FAILED", str(exc)) from exc
            if any(a == b for a, b in zip(vertices, vertices[1:])):
                raise BuildError("INVALID_GEOMETRY", f"zero-length segment in {key}/{part_index}")
            if vertices[0] == vertices[-1]:
                raise BuildError("INVALID_GEOMETRY", f"closed self-loop in {key}/{part_index}")
            record = {"source_layer_key": layer_key, "source_feature_key": key, "source_part_index": part_index,
                      "original_vertices": original, "network_vertices_xy": vertices,
                      "has_z": has_z, "has_m": has_m}
            if feature.get("native_fid") is not None:
                record["source_native_fid"] = str(feature["native_fid"])
            parts.append((record, statuses))
            if has_z or has_m:
                issue_inputs.append(("Z_M_IGNORED", None, key, part_index, None, "Z/M ignored in 2D graph"))
    if not parts:
        raise BuildError("INVALID_GEOMETRY", "empty source layer")
    parts.sort(key=lambda p: (p[0]["source_feature_key"].encode(), p[0]["source_part_index"]))
    part_lookup = {(p["source_feature_key"], p["source_part_index"]): p for p, _ in parts}
    anchors = defaultdict(list)
    transition_rows = []
    endpoint_members = []
    used_member_positions = set()
    declared_pairs = set()
    if junctions is not None:
        if not isinstance(junctions, dict) or set(junctions) != {"schema_version", "junction_crs_wkt", "junctions"} or junctions["schema_version"] != VERSION:
            raise BuildError("INVALID_JUNCTION", "junction schema invalid")
        if not isinstance(junctions["junction_crs_wkt"], str) or not junctions["junction_crs_wkt"]:
            raise BuildError("INVALID_JUNCTION", "junction CRS missing")
        if junction_transform is None:
            if junctions["junction_crs_wkt"] != network_crs_wkt:
                raise BuildError("INVALID_CRS", "junction transform callback required")
            junction_transform = lambda xy: xy
        if not isinstance(junctions["junctions"], list):
            raise BuildError("INVALID_JUNCTION", "junctions must be an array")
        seen_junctions = set()
        for junction in junctions["junctions"]:
            _check_canceled(feedback)
            if not isinstance(junction, dict):
                raise BuildError("INVALID_JUNCTION", "junction must be an object")
            jid = _id(junction.get("junction_id"), "junction_id")
            if jid in seen_junctions:
                raise BuildError("INVALID_JUNCTION", "duplicate junction ID")
            seen_junctions.add(jid)
            if set(junction) != {"junction_id", "xy", "members", "transitions"}:
                raise BuildError("INVALID_JUNCTION", "unknown junction fields")
            declared_xy = _finite_xy(junction_transform(_finite_xy(junction["xy"], "INVALID_JUNCTION")), "INVALID_JUNCTION")
            members = {}
            if not isinstance(junction["members"], list) or len(junction["members"]) < 2:
                raise BuildError("INVALID_JUNCTION", "junction needs at least two members")
            for member in junction["members"]:
                _check_canceled(feedback)
                required = {"member_id", "source_layer_key", "source_feature_key", "source_part_index", "segment_index", "segment_fraction"}
                if not isinstance(member, dict) or set(member) != required:
                    raise BuildError("INVALID_JUNCTION", "member fields invalid")
                mid = _id(member["member_id"], "member_id")
                if mid in members or member["source_layer_key"] != layer_key:
                    raise BuildError("INVALID_JUNCTION", "duplicate member or wrong layer")
                if (type(member["source_part_index"]) is not int or member["source_part_index"] < 0
                        or not isinstance(member["source_feature_key"], str)):
                    raise BuildError("INVALID_JUNCTION", "member needs a string feature key and nonnegative integer part index")
                part = part_lookup.get((member["source_feature_key"], member["source_part_index"]))
                if part is None:
                    raise BuildError("INVALID_JUNCTION", "missing source part")
                index = member["segment_index"]; fraction = member["segment_fraction"]
                vertices = part["network_vertices_xy"]
                if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(vertices)-1:
                    raise BuildError("INVALID_JUNCTION", "invalid segment index")
                if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                    raise BuildError("INVALID_JUNCTION", "invalid segment fraction")
                position = index + fraction
                point = _interpolate(vertices[index], vertices[index+1], fraction)
                if point != declared_xy:
                    raise BuildError("INVALID_JUNCTION", "member does not exactly match junction coordinate")
                for other_index, (a, b) in enumerate(zip(vertices, vertices[1:])):
                    _check_canceled(feedback)
                    if other_index == index:
                        continue
                    if other_index in (index - 1, index + 1) and fraction in (0, 1):
                        if point == vertices[other_index] or point == vertices[other_index + 1]:
                            continue
                    if _point_on_segment(point, a, b):
                        raise BuildError("INVALID_JUNCTION", "ambiguous self-intersection at junction member")
                if fraction == 1 and index + 1 < len(vertices) - 1:
                    index += 1
                    fraction = 0.0
                else:
                    fraction = float(fraction)
                key = (member["source_feature_key"], member["source_part_index"])
                if (key, position) in used_member_positions:
                    raise BuildError("INVALID_JUNCTION", "duplicate anchor on a source part")
                used_member_positions.add((key, position))
                if position == 0:
                    endpoint_members.append((jid, mid, key, "START"))
                elif position == len(vertices) - 1:
                    endpoint_members.append((jid, mid, key, "END"))
                else:
                    anchor = {"segment_index": index, "segment_fraction": fraction, "junction_id": jid, "member_id": mid}
                    anchors[key].append((position, anchor, point))
                members[mid] = (key, position)
            if not isinstance(junction["transitions"], list) or not junction["transitions"]:
                raise BuildError("INVALID_JUNCTION", "junction needs a directed transition")
            for row in junction["transitions"]:
                _check_canceled(feedback)
                if not isinstance(row, dict) or set(row) != {"from_member_id", "from_side", "to_member_id", "to_side"}:
                    raise BuildError("INVALID_JUNCTION", "transition fields invalid")
                if any(not isinstance(value, str) for value in row.values()):
                    raise BuildError("INVALID_JUNCTION", "transition values must be strings")
                if row["from_member_id"] not in members or row["to_member_id"] not in members or row["from_member_id"] == row["to_member_id"]:
                    raise BuildError("INVALID_JUNCTION", "transition members invalid")
                if row["from_side"] not in ("FROM_START", "FROM_END") or row["to_side"] not in ("TO_START", "TO_END"):
                    raise BuildError("INVALID_JUNCTION", "transition side invalid")
                transition_rows.append((jid, row.copy()))
                pair = frozenset((members[row["from_member_id"]][0], members[row["to_member_id"]][0]))
                declared_pairs.add((tuple(declared_xy), pair))
    nodes = {}; edges = []; port_edges = {}; endpoint_edge_lookup = {}
    node_identities = {}; edge_identities = {}
    edges_by_part = defaultdict(list)
    for part, statuses in parts:
        _check_canceled(feedback)
        key = (part["source_feature_key"], part["source_part_index"])
        vertices = part["network_vertices_xy"]
        stops = [(0, "START", vertices[0]), *sorted(anchors.get(key, ()), key=lambda a: a[0]),
                 (len(vertices)-1, "END", vertices[-1])]
        for (start, start_anchor, start_xy), (end, end_anchor, end_xy) in zip(stops, stops[1:]):
            _check_canceled(feedback)
            if len(edges) >= 250_000:
                raise BuildError("LIMIT_EXCEEDED", "too many derived edges")
            clipped = _clip(vertices, start, end)
            try:
                length = float(measure(clipped))
            except BuildError:
                raise
            except Exception as exc:
                raise BuildError("INVALID_CRS", f"measurement failed: {exc}") from exc
            if not math.isfinite(length) or length <= 0:
                raise BuildError("INVALID_GEOMETRY", "edge has nonpositive measured length")
            node_ids = []
            for anchor, xy in ((start_anchor, start_xy), (end_anchor, end_xy)):
                if policy == "GEOMETRIC_ENDPOINT_ONLY":
                    group_key = [float(v).hex() for v in xy]
                    kind = "GEOMETRIC_ENDPOINT"
                else:
                    group_key = [layer_key, *key, anchor]
                    kind = "PART_PORT" if isinstance(anchor, str) else "INTRINSIC_SPLIT"
                node_identity = ["node", 1, network_crs_wkt, policy, group_key]
                node_id = "n_" + digest(node_identity)
                if node_id in node_identities and node_identities[node_id] != node_identity:
                    raise BuildError("ID_COLLISION", "distinct nodes have the same ID")
                node_identities[node_id] = node_identity
                if node_id not in nodes:
                    nodes[node_id] = {"node_id": node_id, "xy": xy, "kind": kind, "anchors": []}
                node_anchor = {"source_layer_key": layer_key, "source_feature_key": key[0],
                               "source_part_index": key[1], "anchor": anchor}
                if node_anchor not in nodes[node_id]["anchors"]:
                    nodes[node_id]["anchors"].append(node_anchor)
                node_ids.append(node_id)
            edge_identity = ["edge", 1, layer_key, key[0], key[1], start_anchor, end_anchor]
            edge_id = "e_" + digest(edge_identity)
            if edge_id in edge_identities:
                raise BuildError("ID_COLLISION", "duplicate or colliding edge ID")
            edge_identities[edge_id] = edge_identity
            edges.append({"edge_id": edge_id, "source_layer_key": layer_key, "source_feature_key": key[0],
                          "source_part_index": key[1], "from_node_id": node_ids[0], "to_node_id": node_ids[1],
                          "from_anchor": start_anchor, "to_anchor": end_anchor, "vertices_xy": clipped,
                          "length_m": length, "edge_status": statuses["eligibility"], "direction": statuses["direction"]})
            edges_by_part[key].append(edges[-1])
            if start_anchor == "START":
                endpoint_edge_lookup[(key, "START")] = edge_id
            if end_anchor == "END":
                endpoint_edge_lookup[(key, "END")] = edge_id
            for anchor, side, eid in ((start_anchor, "END", edge_id), (end_anchor, "START", edge_id)):
                if isinstance(anchor, dict):
                    port_edges[(anchor["junction_id"], anchor["member_id"], side)] = eid
    edge_by_id = {edge["edge_id"]: edge for edge in edges}
    for jid, mid, key, anchor in endpoint_members:
        _check_canceled(feedback)
        edge_id = endpoint_edge_lookup.get((key, anchor))
        if edge_id is None:
            raise BuildError("INVALID_JUNCTION", "endpoint member does not resolve to one adjacent edge")
        port_edges[(jid, mid, "END" if anchor == "START" else "START")] = edge_id
    transitions = []
    for jid, row in transition_rows:
        _check_canceled(feedback)
        incoming_side = "START" if row["from_side"] == "FROM_START" else "END"
        outgoing_side = "START" if row["to_side"] == "TO_START" else "END"
        incoming_id = port_edges.get((jid, row["from_member_id"], incoming_side))
        outgoing_id = port_edges.get((jid, row["to_member_id"], outgoing_side))
        if not incoming_id or not outgoing_id:
            raise BuildError("INVALID_JUNCTION", "transition side has no adjacent edge")
        incoming = edge_by_id[incoming_id]; outgoing = edge_by_id[outgoing_id]
        incoming_dir = "F" if incoming_side == "START" else "R"
        outgoing_dir = "R" if outgoing_side == "START" else "F"
        if incoming["edge_status"] != "OPEN" or outgoing["edge_status"] != "OPEN" or any(
            edge["direction"] not in ("BOTH", required)
            for edge, required in ((incoming, "FORWARD" if incoming_dir == "F" else "REVERSE"),
                                   (outgoing, "FORWARD" if outgoing_dir == "F" else "REVERSE"))
        ):
            raise BuildError("INVALID_JUNCTION", "transition conflicts with eligibility/direction")
        at_node_id = incoming["to_node_id"] if incoming_dir == "F" else incoming["from_node_id"]
        transitions.append({"from_traversal_id": incoming_id + ":" + incoming_dir,
                            "at_node_id": at_node_id, "to_traversal_id": outgoing_id + ":" + outgoing_dir,
                            "junction_id": jid, "declared": True})
    # Same-part continuation through split anchors is intrinsic and direction-aware.
    for key in sorted(anchors):
        _check_canceled(feedback)
        adjacent = sorted(edges_by_part[key],
                          key=lambda e: (0 if e["from_anchor"] == "START" else e["from_anchor"].get("segment_index", 0),
                                         0 if e["from_anchor"] == "START" else e["from_anchor"].get("segment_fraction", 0)))
        for left, right in zip(adjacent, adjacent[1:]):
            _check_canceled(feedback)
            if left["edge_status"] == right["edge_status"] == "OPEN":
                if left["direction"] in ("BOTH", "FORWARD") and right["direction"] in ("BOTH", "FORWARD"):
                    transitions.append({"from_traversal_id": left["edge_id"] + ":F", "at_node_id": left["to_node_id"],
                                        "to_traversal_id": right["edge_id"] + ":F", "junction_id": None, "declared": False})
                if left["direction"] in ("BOTH", "REVERSE") and right["direction"] in ("BOTH", "REVERSE"):
                    transitions.append({"from_traversal_id": right["edge_id"] + ":R", "at_node_id": right["from_node_id"],
                                        "to_traversal_id": left["edge_id"] + ":R", "junction_id": None, "declared": False})
    parent = {node_id: node_id for node_id in nodes}
    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    eligible_nodes = set()
    for edge in edges:
        _check_canceled(feedback)
        if edge["edge_status"] == "OPEN" and edge["direction"] != "UNKNOWN":
            eligible_nodes.update((edge["from_node_id"], edge["to_node_id"]))
            union(edge["from_node_id"], edge["to_node_id"])
    for transition in transitions:
        _check_canceled(feedback)
        if transition["declared"]:
            target_edge = edge_by_id[transition["to_traversal_id"].split(":")[0]]
            target_node = target_edge["from_node_id"] if transition["to_traversal_id"].endswith(":F") else target_edge["to_node_id"]
            eligible_nodes.update((transition["at_node_id"], target_node))
            union(transition["at_node_id"], target_node)
    roots = sorted({find(n) for n in eligible_nodes})
    component_ids = {root: "c_" + digest(["component", root]) for root in roots}
    node_components = {node_id: component_ids[find(node_id)] if node_id in eligible_nodes else None for node_id in nodes}
    degree = defaultdict(int)
    for edge in edges:
        _check_canceled(feedback)
        if edge["edge_status"] == "OPEN" and edge["direction"] != "UNKNOWN":
            degree[edge["from_node_id"]] += 1
            degree[edge["to_node_id"]] += 1
    for transition in transitions:
        _check_canceled(feedback)
        if transition["declared"]:
            degree[transition["at_node_id"]] += 1
            target = edge_by_id[transition["to_traversal_id"].split(":")[0]]
            target_node = target["from_node_id"] if transition["to_traversal_id"].endswith(":F") else target["to_node_id"]
            degree[target_node] += 1
    for node_id in sorted(nodes):
        _check_canceled(feedback)
        if degree[node_id] == 1:
            anchor = nodes[node_id]["anchors"][0]
            issue_inputs.append(("DANGLE", nodes[node_id]["xy"], anchor["source_feature_key"],
                                 anchor["source_part_index"], None, "Eligible network endpoint has one incident edge"))
    # Diagnostic relationships never modify topology.
    segments = []
    for part, _ in parts:
        _check_canceled(feedback)
        coords = part["network_vertices_xy"]
        for index, (a, b) in enumerate(zip(coords, coords[1:])):
            if index % 1024 == 0:
                _check_canceled(feedback)
            segments.append((part["source_feature_key"], part["source_part_index"], index, a, b))
    ordered_segments = sorted(segments, key=lambda s: (min(s[3][0], s[4][0]), s[0].encode(), s[1], s[2]))
    candidate_pairs = 0
    reported_relations = set()
    part_ends = {(p["source_feature_key"], p["source_part_index"]):
                 (p["network_vertices_xy"][0], p["network_vertices_xy"][-1]) for p, _ in parts}
    for i, left in enumerate(ordered_segments):
        if feedback and feedback.isCanceled():
            raise BuildError("CANCELED", "build canceled")
        max_x = max(left[3][0], left[4][0])
        for j in range(i + 1, len(ordered_segments)):
            if (j - i) % 1024 == 0:
                _check_canceled(feedback)
            right = ordered_segments[j]
            if min(right[3][0], right[4][0]) > max_x:
                break
            if left[:2] == right[:2] or max(left[3][1], left[4][1]) < min(right[3][1], right[4][1]) or max(right[3][1], right[4][1]) < min(left[3][1], left[4][1]):
                continue
            candidate_pairs += 1
            if candidate_pairs % 1024 == 0:
                _check_canceled(feedback)
            if candidate_pairs > 5_000_000:
                raise BuildError("LIMIT_EXCEEDED", "too many overlapping segment candidates for complete QA")
            relation = _segment_relation(left[3], left[4], right[3], right[4])
            if relation:
                code, xy = relation
                left_key, right_key = left[:2], right[:2]
                if xy is not None:
                    left_interior = xy not in part_ends[left_key]
                    right_interior = xy not in part_ends[right_key]
                    if not left_interior and not right_interior:
                        continue
                    code = "UNDECLARED_CROSSING" if left_interior and right_interior else "INTERIOR_TOUCH"
                if xy is not None and (tuple(xy), frozenset((left_key, right_key))) in declared_pairs:
                    continue
                relation_key = (code, tuple(xy) if xy is not None else None, left_key, right_key)
                if relation_key in reported_relations:
                    continue
                reported_relations.add(relation_key)
                issue_inputs.append((code, xy, left[0], left[1], None, f"{code} with {right[0]}/{right[1]}"))
    endpoints = [(p["source_feature_key"], p["source_part_index"], xy) for p, _ in parts
                 for xy in (p["network_vertices_xy"][0], p["network_vertices_xy"][-1])]
    near = profile["qa_near_miss_m"]
    if near > 0:
        planar_near = profile["ellipsoid"] == "NONE"
        endpoints.sort(key=lambda a: (a[2][0], a[2][1], a[0].encode(), a[1]))
        near_candidates = 0
        for i, a in enumerate(endpoints):
            if feedback and feedback.isCanceled():
                raise BuildError("CANCELED", "build canceled")
            for j in range(i + 1, len(endpoints)):
                if (j - i) % 1024 == 0:
                    _check_canceled(feedback)
                b = endpoints[j]
                if planar_near and b[2][0] - a[2][0] > near:
                    break
                if a[:2] == b[:2] or a[2] == b[2]:
                    continue
                if planar_near and abs(b[2][1] - a[2][1]) > near:
                    continue
                near_candidates += 1
                if near_candidates % 10000 == 0 and feedback and feedback.isCanceled():
                    raise BuildError("CANCELED", "build canceled")
                if near_candidates > 5_000_000:
                    raise BuildError("LIMIT_EXCEEDED", "too many endpoint candidates for complete metric QA")
                distance = measure([a[2], b[2]])
                if 0 < distance <= near:
                    issue_inputs.append(("NEAR_MISS", a[2], a[0], a[1], None, f"Endpoint within {near} m of {b[0]}/{b[1]}; not joined"))
    if len(roots) > 1:
        issue_inputs.append(("DISCONNECTED_COMPONENT", None, None, None, None, f"{len(roots)} eligible weak components"))
    qa_issues = []
    for ordinal, (code, xy, key, part_index, junction_id, message) in enumerate(sorted(issue_inputs, key=repr)):
        if ordinal % 1024 == 0:
            _check_canceled(feedback)
        qa_issues.append({"schema_version": VERSION, "issue_id": "i_" + digest([code, xy, key, part_index, junction_id, ordinal]),
                          "route_id": None, "severity": "WARNING", "code": code, "message": message,
                          "source_layer_key": layer_key if key is not None else None,
                          "source_feature_key": key, "source_part_index": part_index, "edge_id": None,
                          "junction_id": junction_id, "xy": xy})
    for node in nodes.values():
        node["anchors"].sort(key=lambda a: (a["source_feature_key"].encode(), a["source_part_index"], repr(a["anchor"])))
    source_parts = [p for p, _ in parts]
    _check_canceled(feedback)
    nodes_list = sorted(nodes.values(), key=lambda n: n["node_id"])
    edges.sort(key=lambda e: e["edge_id"])
    transitions.sort(key=lambda t: (t["from_traversal_id"], t["at_node_id"], t["to_traversal_id"]))
    measurement = {"ellipsoid": profile["ellipsoid"], "method": "PLANAR_LENGTH" if profile["ellipsoid"] == "NONE" else "QGIS_DISTANCE_AREA",
                   "qgis_version": qgis_version}
    profile_hash = digest(profile)
    junctions_hash = digest(junctions) if junctions is not None else None
    source_hash = digest([source_crs_wkt, layer_key, sorted(source_hash_rows, key=lambda r: r[0].encode())])
    graph = {"schema_version": VERSION, "kind": "NETWORK_GRAPH", "source_layer_key": layer_key,
             "source_crs_wkt": source_crs_wkt, "network_crs_wkt": network_crs_wkt,
             "source_snapshot_sha256": source_hash, "profile_hash": profile_hash, "rule_profile": profile,
             "junctions_sha256": junctions_hash, "measurement": measurement,
             "source_parts": source_parts, "nodes": nodes_list, "edges": edges, "transitions": transitions,
             "qa_issues": qa_issues}
    graph["graph_digest"] = digest([VERSION, network_crs_wkt, source_hash, profile_hash, junctions_hash,
                                     nodes_list, edges, transitions, measurement])
    # Supplemental build metadata: no new connectivity semantics or extra graph edges.
    source_to_edges = defaultdict(list)
    for edge in edges:
        _check_canceled(feedback)
        source_to_edges[(edge["source_feature_key"], edge["source_part_index"])].append(edge["edge_id"])
    graph["build_summary"] = {"connection_policy": policy,
                              "connection_verification": "NOT_ASSET_VERIFIED" if policy == "GEOMETRIC_ENDPOINT_ONLY" else "DECLARED_TRANSITIONS_NOT_FIELD_VERIFIED",
                              "physical_edge_count": len(edges), "node_count": len(nodes),
                              "component_count": len(roots), "node_component_ids": node_components,
                              "source_to_edges": [
                                  {"source_layer_key": layer_key, "source_feature_key": key,
                                   "source_part_index": part_index, "edge_ids": sorted(value)}
                                  for (key, part_index), value in sorted(source_to_edges.items(), key=lambda item: (item[0][0].encode(), item[0][1]))]}
    _check_canceled(feedback)
    return graph
