# Prompt 06 handoff — Tool 01 Network Builder

## Changed files and actual diffs

Added pure-Python `utility_route_lite/core/builder.py` and `core/serialization.py`, PyQGIS `qgis_adapters/builder.py`, `tests/test_builder_core.py`, `tests/qgis_builder.py`, and [Tool 01 instructions](NETWORK_BUILDER.md). Updated the builder Processing algorithm and field selector in `processing/algorithms.py`, provider/metadata/README, ZIP allowlist, decisions/data contract, acceptance matrix, and build status. The built artifact is `dist/utility_route_lite-0.1.0.zip`.

This workspace has no Git repository, so Git cannot produce a change diff. The actual plugin file comparison against the saved Prompt 04 scaffold ZIP is [the primary unified diff](audits/evidence/prompt06-plugin.diff), followed by [final implementation adjustments](audits/evidence/prompt06-final-adjustments.diff) made before the final ZIP rebuild. Both were generated with `diff -ruN`; the first has 802 lines and the second 49. Documentation/test file additions are listed above and readable directly. No Git commit, screenshot or live Plugin Manager installation is claimed.

## Commands actually run and outputs

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -p 'test_builder_core.py' -v` | PASS, 16 tests; [full output](audits/evidence/prompt06-core-tests.txt). |
| `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/qgis_builder.py` | PASS, four offscreen QGIS 4.2.3 tests against an extracted plugin ZIP; [full output](audits/evidence/prompt06-qgis-tests.txt). |
| `python3 -m unittest discover -s tests -p 'test_scaffold.py' -v` | PASS, three syntax/metadata/package tests. |
| `bash scripts/run_qgis_scaffold_macos.sh` | PASS, one packaged provider/dock lifecycle test. |
| `python3 scripts/check_contract.py` | PASS, required frozen registry fields and documentation consistent. |
| `python3 scripts/build_zip.py` and `unzip -l dist/utility_route_lite-0.1.0.zip` | PASS, thirteen allowlisted files under one `utility_route_lite/` folder. |
| `python3 -c '...benchmark_1000...'` | PASS, 1,000 edges, one component, about 0.081 seconds in that local process; this is one observation, not a performance guarantee. |

The first QGIS junction integration run failed because `QgsCoordinateReferenceSystem(wkt)` did not parse the fixture WKT; using the verified `QgsCoordinateReferenceSystem.fromWkt` API fixed it. A later WKT2 assertion exposed QGIS's default `toWkt()` variant; the adapter now explicitly requests `Qgis.CrsWktVariant.Wkt2_2019`. Both checks passed on rerun.

## Correctness evidence and limitations

The false X crossing yields **two components, two unsplit edges and zero transitions** in pure core and QGIS tests. No router exists yet, so no route connection was created. A declared interior junction yields four split intervals and one declared directed transition. Tests also cover endpoint-to-interior declarations, forbidden turn omission, exact endpoint join, T touch isolation, near gap without movement, duplicate source key/geometry, zero-length rejection, multipart provenance, blocked/unknown status, Z opt-in, source immutability, QA GeoPackage fields and geographic WGS84 meter length. The graph includes original-to-derived edge rows and stable component IDs in `build_summary` under decision D-018.

QGIS integration was run on 4.2.3 only. Live Plugin Manager installation, 4.3+ compatibility, QGIS Z/M round-trip, combined multipart/geographic fixture, every negative junction variant, dense-network performance, and a graph reader round-trip remain **UNVERIFIED**. The Builder returns `LIMIT_EXCEEDED` when complete topology/near-miss QA would exceed five million candidate pairs. `build_summary` is additive diagnostic metadata and needs architect/reader compatibility review before release. Route Inspector, Smart Router, Reviewer, Batch and Packager remain unimplemented; the Prompt 05 end-to-end oracles remain red for those capabilities.

## Next action

Implement Network Inspector against the same graph/QA data, add missing negative junction and QGIS Z/M tests, and independently audit the Builder's dense-network and schema/reader behavior before any release GO decision.
