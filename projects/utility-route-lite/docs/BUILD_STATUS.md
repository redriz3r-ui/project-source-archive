# Utility Route Lite build status

Baseline: 2026-10-16. The original charter marked every delivery stage Not Started. Prompt 04 added an installable shell; Prompt 06 implements Network Builder. The remaining four algorithms and reviewer remain explicitly unimplemented. `Not Started` means no implementation-stage completion has been verified; it does not imply the charter is missing.

| Order | Stage | Status | Evidence needed to advance |
| --- | --- | --- | --- |
| 1 | Architecture and data contract | Specified / frozen; implementation unverified | [Architecture](ARCHITECTURE.md), [data contract](DATA_CONTRACT.md), [acceptance matrix](ACCEPTANCE_MATRIX.md), machine registry and [Prompt 03 handoff](HANDOFF_03.md) |
| 2 | Prior-art, license and feasibility review | Reviewed — revisions required | [Audit](audits/PRIOR_ART.md), [nine open risks](audits/RISKS.md), source manifest and eight passing QGIS 4.2.3 API probes; architecture blockers remain |
| 3 | Scaffold | Implemented; QGIS 4.2.3 offscreen smoke passed | ZIP package, provider/dock lifecycle and [Prompt 04 handoff](HANDOFF_04.md); clean Plugin Manager installation remains unverified |
| 4 | Synthetic fixtures | Generated; contract and CRS checks passed, functional oracles red by design | Seventeen versioned cases, 1,000-edge benchmark, 10k/50k generator, [Prompt 05 handoff](HANDOFF_05.md) |
| 5 | Network Builder | Independent re-audit FAILED — subsequent stages blocked | [Independent re-audit](audits/GRAPH_REVIEW_REAUDIT.md): 44 focused tests reproduced, but additional metric, cancellation and publication blockers remain. Full discovery still has 18 unwired fixture-adapter errors (including Builder-only cases). Prior baseline: 16 core tests, four QGIS integration tests, [Tool 01 guide](NETWORK_BUILDER.md) and [Prompt 06 handoff](HANDOFF_06.md) |
| 6 | Network Inspector | Not Started | Code, tests, docs and issue-layer QA |
| 7 | Smart Router | Not Started | Code, tests, docs and independent path audit |
| 8 | Route Reviewer | Not Started | Dock, state tests, GUI smoke evidence and docs |
| 9 | Batch Route Generator | Not Started | Code, partial-failure/cancellation tests and docs |
| 10 | Route Packager | Not Started | Code, export safety and QGIS round-trip tests |
| 11 | Integration | Not Started | Six-tool workflow and API documentation |
| 12 | Audits and repairs | Independent Gate A re-audit FAILED | [Re-audit verdict and corrective actions](audits/GRAPH_REVIEW_REAUDIT.md); Inspector and Router remain blocked |
| 13 | Packaging and release gate | Not Started | Exact ZIP, clean QGIS 4.2+ install and audit |
| 14 | Release | Not Started | Explicit GO decision, version/checksum and publication record |

For every later deliverable, record files changed, commands **actually run**, pass/fail evidence, limitations and next action. If QGIS is unavailable, run pure-Python tests where possible and mark QGIS integration **UNVERIFIED** with exact local verification commands. Do not convert a stage to Done from a textual claim alone.

Prompt 02 environment correction: QGIS was absent from PATH but is installed at `/Applications/QGIS-final-4_2_3.app`. The configured bundled runtime passed eight synthetic API tests; this does not verify product integration or GUI installation. See [the saved log](audits/evidence/qgis-feasibility.txt) and the audit handoff. Prompt 03 resolves the audit's five architecture questions as frozen **design decisions**. Prompt 04 verifies ZIP extraction, registration, stub failure, reviewer placeholder and unload using an offscreen fake QGIS interface; it does not verify Plugin Manager installation. Next: synthetic fixtures, graph/QA implementation and independent audit in the planned order.
