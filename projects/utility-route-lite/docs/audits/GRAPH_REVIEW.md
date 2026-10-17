# Gate A — independent graph/topology review

Date: 2026-10-17. Scope: current on-disk Network Builder, its pure core, QGIS adapter, existing fixtures, serialized graph outputs and frozen contract. **Verdict: FAIL / NO-GO. Routing work is not authorized while the HIGH findings below remain unresolved.** Application code was not modified. This is a source/runtime audit, not field verification or engineering certification.

## Executed evidence

The installed runtime reports **QGIS 4.2.3-Belém do Pará**. Tests used synthetic data only. The following commands were actually executed from the repository root; saved stdout/stderr is linked. Independent regression failures intentionally retain the frozen contract expectations.

| Command | Actual result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s tests -p test_builder_core.py -v` | 16 passed | [existing core](evidence/gate-a/existing-core.txt) |
| `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/qgis_builder.py` | 4 passed | [existing QGIS](evidence/gate-a/existing-qgis.txt) |
| `python3 tests/audit/test_graph_gate.py -v` | 9 tests: 1 passed, 8 failed | [independent core](evidence/gate-a/core-regressions.txt) |
| `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/audit/qgis_graph_gate.py` | 3 tests: 2 passed, 1 failed | [independent QGIS](evidence/gate-a/qgis-regressions.txt) |
| `python3 tests/audit/graph_scaling_probe.py` | Three bounded sizes completed; edge/component assertions passed | [timings and peak RSS](evidence/gate-a/scaling.json) |

Test commands were redirected to the evidence files and followed by `cat` to inspect their contents. The enclosing shell's final `cat` exit status is not the unittest outcome: the logs explicitly report nine failing assertions across the two independent suites. No route solver was executed or implemented. Existing route-fixture adapter remains unimplemented; passing builder tests do not establish routing correctness. No Git commit was created: `.git` does not exist here.

## Findings and reproducible counterexamples

Line references below identify the reviewed, unchanged application snapshot. Reproduction test names are in `tests/audit/test_graph_gate.py` unless stated otherwise. The linked JSON files are actual generated graph outputs.

### GA-01 — HIGH: contradictory dimensional flags silently admit stacked XY connectivity

Evidence: `utility_route_lite/core/builder.py:184` trusts explicit `has_z=False`; lines 191–198 accept XYZ/XYZM coordinates and take XY; lines 211–212 warn only when flags are true. Geometric grouping at line 306 then joins equal XY endpoints.

Reproduce: `test_false_dimension_flags_cannot_silently_connect_stacked_lines`: two parts `[0,0,1]→[5,0,1]` and `[5,0,9]→[10,0,9]`, both flags false, `allow_2d_projection=false`. Expected `UNSUPPORTED_DIMENSION` or a typed inconsistent-dimensions error. Actual: one component, only DANGLE issues, no `Z_M_IGNORED`, original Z retained but silently disregarded for connectivity. [Output](evidence/gate-a/stacked_flags.json). Test ran and failed.

Scope: this is a reusable-core input-boundary defect. The current QGIS adapter derives flags from WKB and is not demonstrated to generate contradictory flags. Coincident XY endpoints under an explicitly selected geometric 2D policy are permitted and are never asset verification; the defect is bypassing mandatory dimensional consent.

Fix: validate flag types, coordinate arity and consistency for every part before transforming; reject inconsistent records. Cover XYZ, XYM, XYZM, mixed arity, explicit consent and default rejection through core and QGIS.

### GA-02 — HIGH: source fingerprint loses non-string selected attributes

Evidence: `utility_route_lite/qgis_adapters/builder.py:66` converts every selected non-string value to `None` before core hashing at `core/builder.py:180`. DATA_CONTRACT requires raw selected values in the snapshot fingerprint.

Reproduce: `tests/audit/qgis_graph_gate.py::test_raw_selected_attribute_change_invalidates_fingerprint` builds a memory line layer with integer status 7, changes it to 8 and rebuilds. Expected changed snapshot hash, even though both values are unmapped/UNKNOWN. Actual identical hash `bb1f8a4313821d12ccbc985d9ca5e9f9a5299331f7851e226b7b9b7a210bef7b`. [Evidence](evidence/gate-a/fingerprints.json). Test ran on QGIS 4.2.3 and failed. This can defeat future stale-review detection; it does not make UNKNOWN edges eligible.

Fix: separate lossless, typed fingerprint input from rule evaluation; preserve supported raw values and distinguish null, integer, float, bool and string. Reject unsupported QVariant types explicitly. Add mutation tests for every supported type; retain UNKNOWN behavior for unmatched rules.

### GA-03 — HIGH: equivalent source-vertex anchors change stable IDs

Evidence: `core/builder.py:262` computes the same position, but line 275 retains unnormalized segment index/fraction in the anchor; lines 311 and 319 hash that representation. DATA_CONTRACT line 36 requires source-vertex canonicalization.

Reproduce: `test_equivalent_vertex_anchor_has_stable_edge_ids`: split horizontal `[0,0],[5,0],[10,0]` at segment 0/fraction 1.0, then segment 1/fraction 0.0 with the same junction/member. Expected identical node/edge IDs and normalized anchors. Actual horizontal derived edge IDs differ. [First output](evidence/gate-a/anchor_left.json), [equivalent output](evidence/gate-a/anchor_right.json). Test ran and failed. The raw junction-document hash may legitimately differ; this assertion compares stable edge IDs, not raw document hashes.

Fix: define one canonical vertex representation and numeric fraction type before ID generation, duplicate detection, transitions and serialization. Cover all equivalent vertex encodings and reorderings. Any contract change requires an architect decision in `docs/DECISIONS.md`.

### GA-04 — HIGH: declared junction hides unrelated undeclared crossings

Evidence: `core/builder.py:438` suppresses any intersection whose XY equals any junction XY, without checking the two intersecting members or their anchors. It also compares raw junction CRS coordinates with network CRS coordinates.

Reproduce: `test_nonmember_crossing_is_reported`: add nonmember line `[0,-5]→[10,5]` to the declared horizontal/vertical junction at `[5,0]`. Expected undeclared-crossing QA for nonmember pairs and a separate component. Actual separate component is preserved, but every crossing warning is suppressed; only DANGLE/DISCONNECTED_COMPONENT remain. [Output](evidence/gate-a/nonmember_crossing.json). Test ran and failed. This is false QA assurance, not an observed invented graph transition.

Fix: classify intersections using transformed, validated member anchors and the actual pair involved. Do not let a colocated junction whitelist unrelated assets. Test mixed declared/nonmember crossings and different junction/network CRSs.

### GA-05 — HIGH: ambiguous self-intersection junction accepted

Evidence: `core/builder.py:263` validates only the selected segment; QA at line 428 skips all comparisons within a part. DATA_CONTRACT line 36 requires ambiguous self-intersections to fail `INVALID_JUNCTION`.

Reproduce: `test_ambiguous_self_intersection_anchor_rejected`: bow-tie `[0,0],[10,10],[0,10],[10,0]` with junction at `[5,5]` on segment 0, joined to `[5,5]→[5,6]`. Expected rejection because two source positions share the junction coordinate under the frozen policy. Actual split graph and declared transition accepted, one component, only DANGLE issues. [Output](evidence/gate-a/ambiguous_anchor.json). Test ran and failed. Explicit segment selection alone does not satisfy the frozen ambiguity rejection rule.

Fix: validate same-part repeated/intersecting positions before accepting junction members; reject ambiguous anchors with a located issue/error. Preserve valid ordinary bends and full source geometry.

### GA-06 — HIGH: pure core reports geographic degrees as meters

Evidence: `core/builder.py:128` checks only CRS-string equality and ellipsoid NONE; line 135 selects Euclidean measurement without verifying meter units. The docstring's metric precondition is not enforced.

Reproduce: `test_geographic_core_cannot_label_degrees_meters`: identical source/network `EPSG:4326`, coordinates `[-122,37]→[-121.999,37]`, planar NONE. Expected invalid CRS or validated metric adapter. Actual `length_m=0.0010000000000047748`. [Output](evidence/gate-a/degrees_as_meters.json). Test ran and failed.

Scope: QGIS adapter guards projected meter target and source-declaration consistency; both independent negative tests passed. Its existing geographic-source metric test also passed. Fix the public core boundary with an explicit validated metric context/callback contract; do not try to infer CRS validity from arbitrary string equality. Keep QGIS-dependent CRS parsing isolated.

### GA-07 — HIGH: eager allocation, late limits and uncancellable quadratic phase

Evidence: `core/builder.py:139` consumes the complete input before first cancellation at 145. Vertex/part limits occur at 213–216 after allocation; derived edge limit at 330 is also late. Adapter lines 43–69 materialize source snapshots first. Access to `anchors[key]` at 292 creates a key for every part; lines 360–363 rescan all edges for each part, including unsplit parts, with no cancellation check in that loop.

Reproduce: `test_cancel_before_consuming_generator` supplies an already-canceled feedback and a 10,000-item generator. Expected prompt cancellation before consuming input; actual all 10,000 items consumed before CANCELED. Test ran and failed. `graph_scaling_probe.py` measured 1k/2k/4k chains at 0.086/0.251/0.865 seconds and process-lifetime peak RSS about 33/46/69 MB on this machine. These are bounded single-run observations, not projected 50k or 250k performance claims. The P×E scan follows directly from the code. Massive/OOM tests were not run; maximum-size memory safety remains UNVERIFIED.

Fix: enforce running vertex/part/derived-edge budgets during ingestion/allocation; check cancellation before iteration and periodically within long loops; index edges by part once and visit only split parts for continuations. Add bounded-memory failure/cancellation tests and measured 10k/50k runs after correction. Review serialization copies and QA candidate limits too.

### GA-08 — MEDIUM: nonzero closed self-loop accepted despite explicit exclusion

Evidence: `core/builder.py:203` rejects adjacent duplicate vertices, and 300 rejects nonpositive length, but neither rejects equal part endpoints/self-loop IDs. ARCHITECTURE line 51 excludes self-loop edges.

Reproduce: `test_closed_self_loop_rejected`, triangle `[0,0],[1,0],[1,1],[0,0]`. Expected invalid geometry under current contract. Actual edge length 3.414213562373095, from/to node identical, zero QA issues. [Output](evidence/gate-a/self_loop.json). Test ran and failed.

Fix: enforce the frozen exclusion, or obtain an explicit architecture decision and define cycle semantics before allowing loops. Test closed parts under both policies and split intervals.

### GA-09 — MEDIUM: crossing at two interior source vertices is invisible to QA

Evidence: `core/builder.py:91`–111 classifies individual segment interiors; a shared segment endpoint on both sides produces no relation even when both positions are interior to their source parts.

Reproduce: `test_crossing_at_interior_vertices_is_reported`: horizontal and vertical source lines each contain `[5,0]` as an intermediate vertex. Expected undeclared-crossing issue and disconnected graph. Actual disconnected graph (correct), no crossing issue. [Output](evidence/gate-a/vertex_crossing.json). Test ran and failed.

Fix: classify contact relative to source-part positions rather than only individual segment endpoints; deduplicate pair/location issues deterministically. Add T-touch-at-vertex coverage.

### GA-10 — LOW: missing required collision detection (static finding)

Evidence: `core/builder.py:311`–319 reuses an existing node hash without checking the original grouping key, and edge dictionary construction at 332 can overwrite repeated edge IDs. DATA_CONTRACT line 10 requires detecting collisions and aborting. No real SHA-256 collision was generated or claimed; this is an unimplemented defensive contract requirement, not a practical demonstrated attack.

Fix: keep/check canonical identity payloads, reject duplicate IDs with different payloads, and verify with an injected hash-collision regression. That injection test was not run in this audit.

## Coverage and boundaries

| Counterexample | Actual observation |
| --- | --- |
| Non-node crossing | Existing core and QGIS tests pass: two components, no transitions, crossing QA |
| Stacked XY utilities | GA-01 fails core boundary; normal explicit dimensional consent remains required; geometry never proves asset connectivity |
| T without junction | Existing core test passes: separate components and INTERIOR_TOUCH |
| Overlapping polylines / duplicate geometry | Existing and independent controls retain separate edge IDs and OVERLAP QA; equal geometric endpoints may share nodes by declared policy |
| Multipart | Core and QGIS tests pass source-part references and disconnected counts |
| Duplicate endpoint coordinates | Existing exact-endpoint test passes expected geometric node coalescence and NOT_ASSET_VERIFIED declaration |
| Tiny gap | Existing and independent controls pass: near-miss warning, no movement or joining |
| Prohibited turn | Existing and independent checks retain only declared directional transition; no actual route solver tested |
| Duplicate ID / zero-length segment | Existing stable-error tests pass |
| Inconsistent CRS | QGIS negative controls pass; pure boundary fails GA-06 |
| Massive graph | Bounded scaling and pre-cancel probe executed; maximum-size/OOM behavior unverified (GA-07) |
| Determinism / shape preservation | Existing repeated-build and multipart checks pass; equivalent-anchor normalization fails GA-03 |

Components are weak connectivity diagnostics, not directed reachability. A shared component does not authorize forbidden turns; the future router must use incoming-traversal state and declared transitions. No ordinary non-node crossing was observed to become connected. GA-01 demonstrates one concrete unsafe connectivity path at the core input boundary. No source utility edit was observed in the existing QGIS tests, which compare source features before/after execution.

## Required remediation checklist for Sol

1. Fix GA-01 dimension validation and GA-06 metric-context validation before further graph consumers are built.
2. Fix GA-02 typed raw fingerprint preservation; add QGIS mutation regressions and check canonical serialization distinguishes supported types.
3. Fix GA-03 normalized anchors, GA-05 self-intersection rejection and GA-08 loop rejection; preserve stable references and original vertex sequences.
4. Fix GA-04 pair-specific declared-junction QA and GA-09 source-interior contact QA, including different CRS junction documents.
5. Fix GA-07 bounded ingestion, indexed continuations and cancellation; execute bounded resource tests and 10k/50k measurements.
6. Implement/test GA-10 collision handling. Keep existing tests and independent negative expectations intact.
7. Rerun all commands above, add the missing coverage, publish output/schema diffs and obtain an independent Gate A rerun. Record any proposed interface changes in `docs/DECISIONS.md` for architect resolution before implementation drift.

**Release/routing decision: NO-GO.** Seven HIGH and three MEDIUM/LOW findings are unresolved. No BLOCKER label is needed to close this gate: unresolved HIGH findings already prohibit routing under the project contract.

## Handoff

Files added: this review; `tests/audit/test_graph_gate.py`, `tests/audit/qgis_graph_gate.py`, `tests/audit/graph_scaling_probe.py`; logs, graph outputs, fingerprint evidence, bounded measurements and application checksum manifests under `docs/audits/evidence/gate-a/`. Updated `docs/BUILD_STATUS.md` to record the failed gate. Application source unchanged; before/after SHA-256 manifests are equal. Tests are separate audit files, not a separate commit (no Git repository exists).

Limitations: offscreen QGIS 4.2.3 only; no GUI interaction, real utility data, physical connectivity validation, route computation, 50k/250k memory stress or full product release audit. The targeted QGIS integration checks ran; broader QGIS integration remains unverified. Next action: Sol remediates the findings, then independent Gate A rerun before routing work.
