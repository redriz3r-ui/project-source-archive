# Independent Gate A re-audit

2026-10-17. **Verdict: FAIL. Network Inspector and Smart Router are not authorized to advance.**

## 1. Executive summary

The reported 44 focused tests were independently reproduced: **44 passed, zero failures, errors or skips**, all using the installed QGIS 4.2.3 bundled Python. The original builder and adapter were reconstructed from saved diffs and matched the original audit's SHA-256 manifest. Their original eight core failures and one QGIS fingerprint failure recur. The fixes are real, but they do not fully satisfy the Builder contract.

Nine additional adversarial tests produced **three passes, five failures and one error**. Remaining blocking defects concern metric validation, cancellation, and output ownership. A valid full projected-meter WKT is also rejected by the new pure-core check. A concurrent output created after the destination precheck is silently overwritten by the Processing algorithm. Ordinary false crossings remain disconnected, authorized junctions remain represented, and protected-source reads preserved source bytes in the tested QGIS case.

The 50,000-edge build was independently repeated in forward and reverse input order, checking every edge's shape, source identity, status, length and ID, every node ID, all endpoint references, and digest equality. Both builds passed these checks. This does not close the failing negative cases.

Application code was not edited. Before/after manifests in [evidence/gate-a-reaudit](evidence/gate-a-reaudit/) match. New files are audit tests, evidence, this report and the BUILD_STATUS update. No repository commits were created; this workspace has no `.git` directory.

## 2. Ten-finding remediation matrix

The authoritative original findings remain in [GRAPH_REVIEW.md](GRAPH_REVIEW.md). The implementation claims were checked against [GATE_A_REMEDIATION.md](GATE_A_REMEDIATION.md), DATA_CONTRACT, ACCEPTANCE_MATRIX, current source and tests. “Closed for original defect” below does not mean the overall gate passes.

| Original finding | Defect / invariant | Corrective implementation and independent evidence | Re-audit disposition |
| --- | --- | --- | --- |
| GA-01 HIGH | False dimensional flags admitted XYZ as XY without consent; dimensions must be preserved or explicitly reduced. | `core/builder.py:226` validates Boolean flags and uniform arity; default rejects dimensional input, opt-in retains original vertices and emits warning. Original stacked-line test fails reconstructed baseline and passes current. Pure XYZ/XYM/XYZM and QGIS Z/M/ZM tests pass. | Closed for original defect. Explicit opt-in still means a 2D proposal, not physical connectivity verification. |
| GA-02 HIGH | Adapter erased numeric selected values before source fingerprinting. | `qgis_adapters/builder.py:69` preserves supported values/nulls; `core/builder.py:87` tags field types. Numeric 7→8 mutation fails on baseline and passes current QGIS. Typed scalar distinctions and changed-attribute fingerprint/unchanged-edge-ID tests pass. | Closed for original defect. Unsupported date/binary/custom values are explicitly rejected. |
| GA-03 HIGH | Equivalent source-vertex anchor representations generated different stable IDs. | `core/builder.py:332` canonicalizes an interior fraction-1 anchor to following segment/fraction 0.0. Original reproducer fails baseline and passes current; feature-order and JSON round-trip checks pass. | Closed for original defect. Raw junction-document hash can differ while normalized node/edge IDs agree, as documented. |
| GA-04 HIGH | Any declared junction at XY hid unrelated crossings. | `core/builder.py:359` records transformed pair/location authorization; QA checks that pair. Original nonmember test fails baseline and passes current. Transformed junction-coordinate regression also fails baseline and passes current. | Closed for original defect. Ordinary crossing and nonmember topology remain separate. |
| GA-05 HIGH | Ambiguous self-intersection junction accepted despite contract rejection. | `core/builder.py:324` searches other source segments and rejects a second location. Original bow-tie test fails baseline and passes current. | Topological defect closed; new scan contributes to remaining GA-07 cancellation defect (RA-02). |
| GA-06 HIGH | Geographic degrees labeled meters in pure core. | `core/builder.py:167` adds a CRS check only when no transform callback exists. Original EPSG:4326 test now passes, but transform-only input bypasses the check (RA-01). Regex also rejects valid repository WKT2. | **OPEN — HIGH.** Original example fixed, underlying metric boundary incomplete; new valid-input regression confirmed. |
| GA-07 HIGH | Eager consumption, late resource checks and P×E scan; cancellation must stop promptly and remain CANCELED. | Streaming adapter, running core limits and per-part edge indexing fix original pre-cancel/scaling cases. 50k identity/reorder/ingestion-cancel checks pass. However junction scan ignores cancellation and measurement callback cancellation is relabeled INVALID_CRS (RA-02). Output race also remains (RA-03). | **OPEN — HIGH.** Improvements verified, expensive-stage cancellation and safe publication incomplete. |
| GA-08 MEDIUM | Closed nonzero part accepted as self-loop contrary to current policy. | `core/builder.py:258` rejects equal transformed start/end. Original closed-triangle test fails baseline and passes current. | Closed for original defect. |
| GA-09 MEDIUM | Shared intermediate vertices escaped crossing QA. | `core/builder.py:543` classifies contacts against whole-part endpoints and deduplicates warnings. Original shared-vertex test and extra T-at-vertex test pass; both fail baseline. | Closed for original defect. No invented transitions observed in these cases. |
| GA-10 LOW | No node/edge hash collision abort. | `core/builder.py:391` and `:403` check identity reuse. Injected collision test fails baseline and passes current, including edge-only collision injection. | Collision behavior fixed. New `ID_COLLISION` public error is absent from frozen registry/decisions (RA-05); contract reconciliation remains. |

Baseline reconstruction: the new-file sections of `prompt06-plugin.diff`, followed by `prompt06-final-adjustments.diff`, recreate `core/builder.py`, `core/serialization.py`, both new package initializers and `qgis_adapters/builder.py`. All five match `gate-a/application-before.json`: [verification](evidence/gate-a-reaudit/baseline-reconstruction.json). Other files in the temporary test tree are copied from current workspace; this is a verified baseline of the affected core/adapter, not a claim of a historical full checkout. Original independent tests and extra regression tests run against these reconstructed modules. The current application was never replaced. Historical example JSON is known to have been refreshed by earlier remediation runs; this re-audit backs up/restores those files and bases historical conclusions on reconstruction and preserved logs.

## 3. Independent execution evidence

[Environment capture](evidence/gate-a-reaudit/environment.txt): QGIS **4.2.3-Belém do Pará**, Qt **6.11.1**, Python **3.12.11**, interpreter `/Applications/QGIS-final-4_2_3.app/Contents/MacOS/python3.12`. System discovery used Python **3.13.0**. The captured builder path is the actual workspace module; current source hashes are in [application-before.json](evidence/gate-a-reaudit/application-before.json). Each suite ran in a separate process. `qgis_builder.py` builds/extracts the current allowlisted plugin ZIP before importing its algorithm; this checks the packaged builder source as well.

Environment variables are captured verbatim in the environment log. Their effective values are: `PYTHONHOME=<bundle>/Contents/Resources`; `PYTHONPATH` contains repository root plus bundled Python 3.12, lib-dynload, site-packages and QGIS plugins; `QGIS_PREFIX_PATH=<bundle>/Contents/Resources/qgis`; `QT_PLUGIN_PATH=<bundle>/Contents/PlugIns`; `QT_QPA_PLATFORM=offscreen`; `PROJ_DATA=<bundle>/Contents/Resources/qgis/proj`; `GDAL_DATA=<bundle>/Contents/Resources/qgis/gdal`; `PYTHONDONTWRITEBYTECODE=1`. The audit runner sets these explicitly, matching the existing macOS runner.

Commands actually executed:

- `python3 tests/audit/run_reaudit.py`
- `python3 tests/audit/run_reaudit.py --baseline-only`
- `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/audit/test_reaudit_adversarial.py`
- `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/audit/qgis_reaudit_adversarial.py`
- `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/audit/reaudit_scale.py`

The first two commands orchestrate subprocesses; their exact argument arrays, working directories and exit codes, including actual temporary paths, are in [commands.json](evidence/gate-a-reaudit/commands.json) and [commands-baseline.json](evidence/gate-a-reaudit/commands-baseline.json). For focused suites the command is the captured absolute QGIS Python interpreter followed by the absolute file below and `-v`. System/QGIS discovery uses that interpreter followed by `-m unittest discover -s tests -p test_*.py -v`. Tests were never altered to suppress a failure.

| Executed suite | Tests | Pass | Fail | Error records | Skip | Log |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `tests/test_builder_core.py` (QGIS Python) | 16 | 16 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/existing-core.txt) |
| `tests/audit/test_graph_gate.py` (QGIS Python) | 9 | 9 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/independent-core.txt) |
| `tests/test_gate_a_regressions.py` (QGIS Python) | 8 | 8 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/new-core.txt) |
| `tests/qgis_builder.py` | 4 | 4 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/existing-qgis.txt) |
| `tests/audit/qgis_graph_gate.py` | 3 | 3 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/independent-qgis.txt) |
| `tests/audit/qgis_remediation.py` | 2 | 2 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/new-qgis.txt) |
| `tests/test_crs_contract.py` (QGIS Python) | 2 | 2 | 0 | 0 | 0 | [log](evidence/gate-a-reaudit/crs-qgis.txt) |
| **Reported focused set reproduced** | **44** | **44** | **0** | **0** | **0** | |
| Additional `test_reaudit_adversarial.py` | 6 | 1 | 4 | 1 | 0 | [log](evidence/gate-a-reaudit/adversarial-core.txt) |
| Additional `qgis_reaudit_adversarial.py` | 3 | 2 | 1 | 0 | 0 | [log](evidence/gate-a-reaudit/adversarial-qgis.txt) |
| Full discovery, system Python | 35 | 32 | 0 | 18 | 1 | [log](evidence/gate-a-reaudit/full-discovery-system.txt) |
| Full discovery, QGIS Python | 35 | 33 | 0 | 18 | 0 | [log](evidence/gate-a-reaudit/full-discovery-qgis.txt) |
| Reconstructed original: independent core | 9 | 1 | 8 | 0 | 0 | [log](evidence/gate-a-reaudit/original-independent-core.txt) |
| Reconstructed original: independent QGIS | 3 | 2 | 1 | 0 | 0 | [log](evidence/gate-a-reaudit/original-independent-qgis.txt) |
| Reconstructed original: added developer regressions | 8 | 3 | 5 | 0 | 0 | [log](evidence/gate-a-reaudit/original-new-regressions.txt) |
| Reconstructed original: fixture adapter suite | 2 | 0 | 0 | 18 | 0 | [log](evidence/gate-a-reaudit/original-fixture-adapter.txt) |

The 18 discovery errors are 17 failing subtests in one method plus one benchmark method; they are not 18 distinct test methods. Thus the discovery count cannot be calculated as `35 - 18`. Full discovery is **not passing**. New audit tests in `tests/audit/` are explicitly invoked because root unittest discovery does not recurse into that directory as a package.

## 4. Adversarial results and remaining defects

### RA-01 — HIGH: metric validation bypass; MEDIUM valid-WKT regression (GA-06)

Evidence: `utility_route_lite/core/builder.py:167` guards CRS validation with `transform is None`; line 171 defaults missing `measure` to planar Euclidean length irrespective of the supplied callback's output CRS. `test_transform_alone_cannot_authorize_degree_lengths` supplies identical EPSG:4326 CRSs, an identity transform and no measurement callback. Expected `INVALID_CRS`. Actual successful graph with `length_m=0.0010000000000047748` for a 0.001-degree longitude segment at latitude 37. The docstring requires an adapter to supply **both** transform and measurement in this situation; the implementation does not enforce it. This is a core-boundary issue; current QGIS adapter supplies both callbacks and rejects geographic target CRS.

The new regex at `core/builder.py:83` stops at the first `]`, including the nested `ORDER[1]` inside an AXIS. Consequently `test_valid_full_meter_wkt_in_pure_mode` raises `INVALID_CRS` on the repository's own `scripts/epsg3857.wkt`. A separate QGIS test independently confirms that WKT is valid EPSG:3857 with meter units. Expected: accept valid declared metric context, or explicitly require a validated adapter/context through an approved interface. Actual behavior depends on shorthand versus full WKT despite the public WKT contract.

Minimum fix: make metric-context validation independent of the mere presence of a transform callback; never choose Euclidean meter measurement without validated meter coordinates. Replace ad-hoc WKT substring inference with an explicit trusted adapter/context design or a clearly documented restrictive contract, with architect decision if the interface changes. Preserve rejection of geographic/foot coordinates and add valid full WKT tests. Rerun both new reproductions.

### RA-02 — HIGH: expensive-stage cancellation remains incomplete (GA-07)

Evidence: `core/builder.py:324` scans all other segments for each explicit member without checking feedback. `test_junction_scan_stops_promptly_on_cancel` uses a 10,000-segment part and sets the feedback flag when the first `_point_on_segment` call occurs. The real geometric predicate still runs. Actual: **9,999 predicate calls** before CANCELED reaches the next checked boundary. Expected: bounded prompt interruption, as in other loops; the test allows 1,024 calls. The flaw scales up to the retained vertex limit and repeated members. It is a Python loop and not covered by the documented native-call limitation.

Also `core/builder.py:377` catches every measurement exception and wraps it as `INVALID_CRS`. `test_measurement_cancellation_keeps_canceled_code` injects `BuildError('CANCELED', ...)` from the measurement callback. Expected CANCELED; actual INVALID_CRS. No successful graph is returned, but cancellation is misreported as bad CRS and programmatic cancellation handling breaks.

Minimum fix: poll cancellation inside member-segment validation and other long Python loops, propagate BuildError/CANCELED without relabeling, and bound adapter-side vertex/part ingestion before constructing an oversized feature snapshot. Add per-stage cancellation/error-code checks; preserve no-publication rollback checks. Existing pre-cancel and ordinary mid-ingestion tests remain valid but cannot establish all-stage cancellation.

### RA-03 — HIGH: publication overwrites a concurrently created destination

Evidence: `utility_route_lite/processing/algorithms.py:123` checks existence once, then lines 128 and 132 use overwriting `os.replace`. `qgis_reaudit_adversarial.py::test_output_created_after_precheck_is_not_overwritten` uses the real Processing algorithm, real synthetic input and real writers. A wrapper around the first real replace creates a sentinel file at the graph destination, simulating another writer after the precheck. Expected: explicit refusal, sentinel preserved, no partial new QA output. Actual: algorithm returns success and replaces the sentinel with graph JSON. The test touches only a temporary directory.

This violates the Builder's own no-overwrite behavior and the source/output protection invariant. It is not a claim that an ordinary run edited the source layer: the protected-source test passed. Minimum fix: use exclusive destination ownership/no-clobber publication, roll back only artifacts owned by the operation, and stage on the correct destination filesystem. Define how the two-output commit handles failure and cancellation. A precheck followed by `os.replace` is not exclusive ownership. Preserve existing cancellation rollback tests and add the concurrent-destination test. Process-crash atomicity across two arbitrary output paths remains a separate unverified limitation; no crash was injected here.

### RA-04 — MEDIUM: malformed junction part index resolves to a real part

Evidence: `core/builder.py:311` passes `source_part_index` directly to a Python dict key lookup without type validation. `False` equals integer zero. `test_junction_invalid_part_index_is_not_boolean` replaces a valid member's index 0 with JSON false; expected `INVALID_JUNCTION`, actual successful junction graph. Validate exact nonnegative integer part indices, excluding bool/fractional numbers, before lookup. Audit malformed scalar/list member fields for typed errors rather than unintended Python exceptions. This issue existed before remediation and was not part of the original ten numbered examples.

### RA-05 — MEDIUM: new collision error has no frozen contract entry

Collision abort works, but it now raises `ID_COLLISION` (`core/builder.py:392`, `:404`). This code is absent from DATA_CONTRACT's build errors, `docs/contract/v1.json`, and numbered decisions. Static inspection confirmed the mismatch; no extra runtime test was needed beyond the collision injection tests that exercise the emitted code. Minimum fix: use an appropriate existing stable code or record architect approval, registry update and compatibility tests for the addition. This does not negate the functional collision fix.

### Required scenarios A–H

| Scenario | Independent result |
| --- | --- |
| A: X crossing without junction | PASS in core and QGIS: separate components, no cross transition, reviewable crossing QA. |
| B: authorized directed junction | PASS for declared-junction fixture: virtual splits, one declared directed transition, no invented reverse declaration. Full route traversal remains outside Builder. |
| C: reordered input | PASS for small crossing/junction/prohibited/duplicate/multipart fixtures and full 50k chain; graph content/digests and stable IDs unchanged. |
| D: Z/M | PASS for original contradiction rejection, mixed arity, explicit Z/M/ZM consent and source ordinate retention. No ordinary silent dimensional reduction observed. |
| E: cancellation | PASS for pre-cancel, ingestion and rollback after first published output; FAIL for junction scan responsiveness and measurement-cancellation classification (RA-02). |
| F: duplicates/ambiguity | Duplicate key, zero-length, overlap and bow-tie tests pass expected rejection/warning semantics. Boolean junction index still accepted (RA-04). Geometric endpoint coalescence is policy-defined, never verified asset connectivity. |
| G: serialized reconstruction | PASS for complete `json.loads(pretty_json(graph))` equality and recomputed graph digest on five fixtures. This is data/semantic preservation, not an implemented production graph reader or hostile-file validator; that reader is still absent. |
| H: protected input | PASS: a synthetic GeoPackage made mode 0444 retained its SHA-256 after QGIS source reading/building; the full bent vertex sequence was preserved. Existing memory-layer before/after checks also pass. Output ownership fails separately (RA-03). |

## 5. 50,000-edge assessment

Command: `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/audit/reaudit_scale.py`. [Complete evidence](evidence/gate-a-reaudit/scale-50k.txt).

Both runs consumed 50,000 synthetic input features and returned exactly 50,000 physical edges, 50,001 nodes and one weak component. Every edge was checked against its source-indexed two-vertex geometry, unit length, OPEN/BOTH status, part index and independently calculated SHA-256 edge ID. Every node ID was independently recalculated from the documented geometric identity tuple. Endpoint references and absence of explicit transitions were checked. Reversing all input features preserved source/profile/graph digests and the complete sets of node/edge IDs. Graph digest in both runs: `c2e0fa3f8a60773d9baf5edd6a4bac7b7b9320ed9839be9fd8f79ee8d87100d5`.

Forward build: **3.872 s**, process peak RSS **667,156,480 bytes**. Reverse build: **4.542 s**, lifetime process peak RSS **736,444,416 bytes**. RSS is cumulative peak for the QGIS-loaded audit process, including fixture and validation structures; it is not directly comparable to the developer's separate system-Python measurements. The graphs were released between runs. A second synthetic input stream canceled at item 500 returned CANCELED and consumed exactly 500 of the 50,000 items.

This confirms the chain case, ID/fingerprint reproducibility and bounded ingestion cancellation. It does not verify 50k Processing/GeoPackage export, dense spatial candidate sets, many explicit junctions, 250k maximum memory, or prompt cancellation in the failing member-validation loop. One connected component alone was not used as the correctness oracle.

## 6. Classification of all 18 discovery errors

All exceptions originate at `tests/fixture_adapter.py:13`, an unconditional `NotImplementedError` with no call into Builder or downstream services. The [Prompt 05 handoff](../HANDOFF_05.md) records the same 18 errors before Builder implementation. The current fixture suite also produces all 18 against the reconstructed original Builder. There is no versioned checkout of the historical test file, so its past byte identity cannot be proven; the historical handoff, source control-flow and baseline rerun substantiate the common unimplemented-adapter cause. No error in this set is a remediation-induced application failure, and no shared algorithm defect is demonstrated by a function that never calls an algorithm.

However, describing all errors as purely downstream is incorrect. Two cases test Builder-only rejection. The other cases mix Builder observations with later tools. Each error is classified below. All require the test seam to be connected eventually; this audit does not implement it.

| Error case | Builder assertion hidden by adapter | Later-stage assertion / classification |
| --- | --- | --- |
| crossing_unconnected | Components and crossing QA | Router NO_ROUTE; mixed Builder verification gap + downstream blocker |
| declared_junction | Build/verification metadata | Route geometry/length/source parts; mixed |
| prohibited_turn | Build and transition structure | Router NO_ROUTE/forbidden traversal; mixed |
| tiny_endpoint_gap | Components and NEAR_MISS | Router NO_ROUTE; mixed |
| disconnected_components | Components and component QA | Router NO_ROUTE; mixed |
| duplicate_source_id | DUPLICATE_SOURCE_KEY | **Builder-only test wiring gap**; equivalent core rejection separately passes |
| duplicate_geometry | OVERLAP/build | Router AMBIGUOUS_SNAP; mixed |
| zero_length_edge | INVALID_GEOMETRY and QA normalization | **Builder-only test wiring gap**; core exception code separately passes, normalized adapter QA observation not exercised |
| multipart_refs | Build/components | Route-selected part and length; mixed |
| blocked_shortcut | Build/status | Router excludes shortcut and chooses detour; mixed |
| same_bent_line_interior | Build/source shape | Router partial-edge route; mixed |
| outside_snap_tolerance | Build | Router snap rejection; mixed |
| geographic_metric | Build/metric measurement | Route output length/source part; mixed |
| reverse_direction | Build/direction metadata | Reverse route geometry; mixed |
| same_start_end | Build | Router SAME_LOCATION; mixed |
| batch_one_bad_record | Build | Batch per-row success/failure; mixed |
| csv_html_escaping | Build | Router/export escaping; mixed |
| benchmark_1000 | Edge/component counts | Route length/success; mixed |

System discovery's single skip is a **test-environment limitation** (no PyQGIS in ordinary Python). It disappears in the verified QGIS Python run; the 18 adapter errors remain. They are not installation failures.

In principle, an independent Builder-only harness can close Builder coverage while preserving later-stage red tests. Here it does not justify PASS because RA-01, RA-02 and RA-03 are independently reproduced Builder correctness blockers. Before a future approval, map every Builder acceptance row to executed evidence, including invalid-junction variants, geometry errors, source preservation and output behavior; do not claim the mixed fixture suite is green or entirely outside the gate.

## 7. Remaining risks and minimum corrective handoff

Sol must address RA-01 through RA-03 before re-audit: establish a reliable metric boundary, complete cancellation/error propagation, and make output publication respect exclusive ownership. Correct strict member-index typing (RA-04) and reconcile the collision error contract (RA-05). Keep every passing test and the new failing adversarial assertions; rerun both QGIS integration and the original failures after repair. Further downstream implementation is not the remedy for these issues.

Remaining limits include untested maximum-size/dense-junction behavior, native-call cancellation latency, crash consistency across two output files, absent production graph-reader validation and GUI installation. All data in this audit is synthetic; geometric/declared connectivity remains unverified physical asset connectivity. No engineering certification is implied.

## 8. Explicit verdict and handoff

**Gate A: FAIL.** Existing tests and the original reproduction cases pass after remediation, but the full Network Builder contract is not independently verified because blocking metric, cancellation and output-publication defects remain. BUILD_STATUS records this independent verdict. Network Inspector and Smart Router remain blocked; no later development stage is approved.

Added: `tests/audit/run_reaudit.py`, `tests/audit/test_reaudit_adversarial.py`, `tests/audit/qgis_reaudit_adversarial.py`, `tests/audit/reaudit_scale.py`, this report and evidence under `docs/audits/evidence/gate-a-reaudit/`. Updated: `docs/BUILD_STATUS.md`. Application source unchanged, verified by hashes. Next action: bounded corrective work by Sol, followed by another independent Gate A run.
