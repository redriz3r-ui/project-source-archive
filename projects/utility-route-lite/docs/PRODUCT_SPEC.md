# Utility Route Lite v1.0 — product charter

Status: proposed specification, 2026-10-16. No application implementation or QGIS runtime verification exists in this repository yet.

## Launch promise and audience

> Produce a connected, inspectable *proposed* route through an existing utility pathway network, subject to declared connectivity rules.

The primary users are GIS technicians preparing pathway options and utility designers checking proposed corridors. A reviewer must be able to see why an edge was eligible, which source features were used, where a connection was assumed, and what remains unverified. The plugin is one open-source QGIS 4.2+ / Qt6 plugin, with five Processing algorithms and one interactive Route Reviewer dock panel. Each capability can be run without completing a prescribed end-to-end workflow. Processing algorithms must be usable from the Toolbox, models, and Python; shared services should support both algorithms and the dock.

The product works locally. It needs no network service, database server, API key, telemetry, or Python package beyond QGIS's installed runtime and the Python standard library. Only synthetic or explicitly authorized datasets may be used for development and demos. Source utility layers are read-only inputs.

## Six capabilities

| Capability and interface | Required inputs | Outputs and independent use | v1.0 acceptance criteria |
| --- | --- | --- | --- |
| **Network Builder** — Processing | Existing line layer; declared source CRS; connection policy; optional explicit junction/transition data; eligibility fields and rule profile | Reusable 2D graph with stable source layer, feature, and part references, preserved line vertex sequences, edge lengths in meters, rule/provenance record, and build diagnostics. Can build without a route request. | Exact eligible endpoints connect under the selected policy; an X crossing, T touch at an interior point, and near miss do not create an undeclared junction; explicit transitions connect only as declared. Invalid CRS/geometry and unsupported rules are reported, with no silent repair or source writes. Repeated builds from identical inputs yield equivalent stable IDs and graph results. |
| **Smart Router** — Processing | Built graph or source network plus build parameters; start/end points with CRS; eligibility/profile; metric snap tolerance | One proposed route geometry, ordered source-edge/segment references, distance in meters, connection assumptions, or a structured no-route reason. Can run without the dock. | Finds the shortest **eligible distance** route on a synthetic graph, including direction and forbidden-transition cases; preserves full source shape and deterministic ties. Same-edge start/end and permitted mid-edge snaps work without connecting otherwise separate edges. Disconnected, outside-tolerance, unknown or blocked constraints fail clearly. Cost-based alternatives are absent from v1.0. |
| **Network Inspector** — Processing | Source lines or a built graph; CRS; same connection policy and eligibility profile | QA issue layer/table and summary of components, dangles, crossings without junctions, near misses, invalid geometry, unknown fields/rules, and policy used. Can inspect before routing. | Flags a geometric crossing as unconnected; identifies disconnected components and near misses without changing them; issue references point to source features and locations; same input/policy gives reproducible counts. Findings distinguish observed geometry from asserted asset connectivity. |
| **Route Reviewer** — interactive dock | A proposed route and its segment/QA/provenance results; optional source layers for highlighting | Map preview, segment list, assumptions and issues, and review state saved with a proposed-route result. Can open an existing route independently of a new routing run. | Reviewer can select a segment and locate its source feature, inspect policy/eligibility and warnings, mark accepted-as-proposed or rejected with an optional note, and reopen the result with state intact. A review action never certifies construction or edits the source. Unload/reload removes and restores dock actions cleanly. |
| **Batch Route Generator** — Processing | CSV or point-pair layer with unique route IDs, start/end coordinates and explicit CRS; built graph/source network; profile | Successful proposed routes plus per-row failure table and counts. Can run without the reviewer. | One synthetic fixture with two valid pairs and one disconnected pair produces exactly two routes and one failure; malformed/duplicate IDs and coordinates produce row-specific errors; valid rows continue; order is deterministic; cancellation is honored; graph is not rebuilt per row. |
| **Route Packager** — Processing | Selected proposed routes, segments, QA, review state, provenance/config, destination and overwrite choice | Portable 2D GeoPackage (`proposed_routes`, `route_segments`, `qa_issues`), `route_summary.csv`, `routing_config.json`, and local `report.html` in a directory or ZIP. Can package previously saved results. | QGIS can reload exported geometry, CRS, references, distances, QA and review state without loss; metadata states policy and unverified assumptions. HTML/CSV user text is escaped, output paths validated, and failed export leaves no misleading completed bundle or source mutation. |

The exact public schemas, rule-profile vocabulary, stable-ID derivation, and algorithm parameter names are to be frozen in `docs/DATA_CONTRACT.md` at the architecture stage. The acceptance tests above must be translated into fixtures and executable checks there.

## Routing boundary and correctness rules

1. Routing is on **2D representations of existing linear utility corridors**. It does not design new corridor geometry. Preserve each source line's full 2D shape in route output and retain stable source references. Multipart lines must be handled as referenced parts or rejected explicitly; they may not be merged silently.
2. **Geometric endpoint connectivity** means two permitted line endpoints coincide under a documented equality/precision policy. It is only a graph hypothesis. **Verified asset connectivity** requires separate, authoritative junction/transition evidence; geometry alone cannot establish physical fiber, splice, conduit, pipe, or electrical continuity. Every result labels the policy and its verification level.
3. The supported policy choices are `GEOMETRIC_ENDPOINT_ONLY` and `EXPLICIT_JUNCTIONS`. The latter allows transitions only where declared junction/transition records permit them. In either policy, X crossings and interior touches do not automatically connect. Near misses are QA findings, not repairs. Endpoint equality and explicit transitions may still be filtered by edge eligibility and direction.
4. A start/end point may attach to a nearby **eligible edge** within a user-declared tolerance measured in meters. This temporary attachment permits a partial edge route and same-edge routing; it does not merge nearby network edges or create a junction at a crossing. Invalid snaps return a reason.
5. v1.0 minimizes the sum of **eligible 2D edge distance in meters**. It never treats degrees or unspecified map units as meters. The QGIS adapter must declare CRS and use validated `QgsDistanceArea` measurement or a validated transformation, recording method/ellipsoid as appropriate. Unknown, blocked, unsupported, or ambiguous eligibility cannot silently become permitted; strict routing fails closed and reports the cause.
6. Z and M are not routing dimensions. Their presence must be detected and disclosed; 2D outputs and distance calculations must be identified as such. No vertical separation, depth, clearance, 3D crossing or measure-based transition is inferred. Inputs whose Z/M meaning is essential for connectivity are outside v1.0 support.

Cost weighting, alternative paths, capacity, congestion, construction constraints, and optimized engineering design are **optional v1.1** work unless separately implemented, documented, and tested before release. They are not implied by the v1.0 shortest-distance result.

## User journeys

1. **One route:** choose existing line layer, CRS, connection policy and eligibility; build or reuse graph; choose endpoints; receive a proposed route or a specific failure; inspect route distance, source segments and assumptions.
2. **Inspect:** run Network Inspector on a network before choosing endpoints; locate disconnected components, false crossings and near misses; resolve data issues outside the plugin under the data owner's process, then rerun.
3. **Review:** open a saved proposed route in the dock, step through source segments and QA flags, record accepted-as-proposed or rejected, and save review state with the route. Acceptance is a user workflow label, not engineering approval.
4. **Batch:** supply an authorized pair table with CRS and unique IDs; generate many proposed routes from one graph; collect both successful routes and row-level failures without losing valid work.
5. **Export:** select saved routes and create a portable, inspectable bundle; reload its GeoPackage and report to verify geometry, references, policy, warnings and review state.

## Threat model and safeguards

| Hazard | Required response |
| --- | --- |
| False physical connection from crossing, endpoint coincidence, snapping, missing junction record or stale source | Never node crossings automatically; disclose geometric-only assumptions; explicit transitions must be evidenced; record source identity and rule profile; show no-route/QA rather than invent a transition. |
| Wrong route from CRS, unit, Z/M, invalid geometry, ambiguous direction or unknown eligibility | Validate inputs, measure in meters, retain diagnostics, fail closed for unsupported/unknown constraints, and test adversarial fixtures. |
| Disclosure of sensitive utility layouts through network calls, telemetry or sample data | No network dependency or telemetry; demo/CI use synthetic or authorized datasets; exports go only to user-selected local destinations. |
| Corruption of authoritative data or misleading artifact after partial failure | Do not write source layers; use separate outputs and staging for export; require explicit overwrite choice and clear failure status. |
| Injection or path manipulation from user-controlled names/attributes | Escape HTML and spreadsheet formula-leading CSV values, validate destinations, avoid remote report assets, and reject traversal/unexpected paths. |
| License or package risk from third-party reuse | Prefer original implementation and QGIS APIs; audit file-specific licenses and attribution before importing code; inspect final ZIP and security scan. |

## Explicit non-goals

- No ArcMap extension or ArcGIS Pro adapter in v1.0.
- No fiber strand-level trace, splice/circuit continuity model, electrical load analysis, or proof of asset continuity.
- No engineering seal, construction-grade validity, permitting approval, or marketing claim of engineering certification.
- No authoritative edits, automatic topology repair, invented crossings/transitions, or installation of mandatory external services.
- No live asset synchronization, telemetry, or hosting requirement.

## GO / NO-GO release checklist

All items require recorded evidence; an unverified item means **NO-GO for v1.0**.

- [ ] Architecture/data contract and independent prior-art/license review are complete; any borrowed code has compatible licensing and attribution.
- [ ] One installable QGIS 4.2+ / Qt6 plugin registers five functioning Processing algorithms and one reviewer dock; clean unload/reload works.
- [ ] All six capability acceptance criteria above pass on synthetic fixtures, including false crossings, forbidden transitions, same-edge snaps, disconnection, partial batch failure and export round-trip.
- [ ] Distances are verified in meters across projected and geographic CRS cases; source geometry and references survive routing and packaging; Z/M disclosures are visible.
- [ ] No source-layer writes, telemetry, undeclared external dependencies, silent repairs or unsupported-constraint fall-through are found in code review and tests.
- [ ] Independent graph, shortest-path, full-repository, license/security and package audits have no unresolved blocking findings.
- [ ] A fresh QGIS 4.2+ profile installs the exact release ZIP and completes the six-tool workflow; platform limits are disclosed and actual commands/results logged. If QGIS is unavailable, mark integration **UNVERIFIED** and keep the v1.0 gate closed.
- [ ] Documentation, license, valid plugin metadata and source links, package contents, version/checksum and user-facing proposal warnings are verified against the final ZIP and current QGIS publishing rules.

## Ordered delivery backlog

1. Architecture and data contract.
2. Independent prior-art, license and feasibility review.
3. Plugin scaffold and packaging skeleton.
4. Synthetic fixtures and test harness.
5. Network Builder.
6. Network Inspector and graph QA audit.
7. Smart Router and shortest-path audit.
8. Route Reviewer.
9. Batch Route Generator.
10. Route Packager.
11. Six-capability integration and end-to-end workflow.
12. Independent audits, repairs, documentation and CI hardening.
13. Exact-ZIP packaging, clean-install and security/license release gate.
14. Release decision and publication only after GO evidence.

## Research basis (checked 2026-10-16)

- [QGIS migration guidance](https://plugins.qgis.org/docs/migrate-qgis4) says QGIS 4 compatibility uses metadata version ranges, `supportsQt6` is obsolete, and Qt6/PyQGIS code must be tested.
- [QGIS Processing plugin cookbook](https://doc.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/processing.html) describes a registered provider and `hasProcessingProvider=yes`; [PyQGIS provider API](https://www.qgis.org/pyqgis/master/core/QgsProcessingProvider.html) and [algorithm API](https://www.qgis.org/pyqgis/master/core/QgsProcessingAlgorithm.html) support this interface. Final method choices still need verification in the installed QGIS 4.2 runtime.
- [QgsDistanceArea API](https://www.qgis.org/pyqgis/master/core/QgsDistanceArea.html) requires source CRS and exposes measurement units; this informs the meter-validation requirement.
- [QNEAT](https://github.com/root676/QNEAT) demonstrates QGIS 4 Processing routing; [Network Topology](https://github.com/Oksion/network-topology-qgis) demonstrates QA but explicitly splits crossings, which is unsafe as a default utility-connectivity rule. [FiberQ](https://github.com/vukovicvl/fiberq) demonstrates fiber-oriented interchange; [On-the-Fly Shortest Path](https://github.com/fryktoria/On-the-Fly-Shortest-Path) demonstrates map-based route inspection. These are conceptual references only pending the independent code/license audit.
- [QGIS publishing requirements](https://plugins.qgis.org/docs/publish) and [approval process](https://plugins.qgis.org/docs/approval) inform the package, metadata and security gates.
