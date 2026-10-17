# Prompt 05 handoff — synthetic fixtures

## Files changed

Added `scripts/regenerate_fixtures.py`, a static EPSG:3857 WKT2 definition in `scripts/epsg3857.wkt`; 17 versioned JSON cases, one 1,000-edge benchmark and a manifest in `examples/fixtures/v1/`; `examples/README.md`; `tests/test_contract.py`, `tests/test_graph_fixtures.py`, `tests/test_crs_contract.py`, and `tests/fixture_adapter.py`. Updated root `README.md`, `docs/BUILD_STATUS.md`, and `docs/ACCEPTANCE_MATRIX.md`. The QGIS runner accepts an optional second test-file argument. No plugin application code was changed.

## Commands actually run

| Command | Result |
| --- | --- |
| `python3 scripts/regenerate_fixtures.py` | PASS, generated 17 cases and 1,000-edge benchmark. |
| `PROJ_DATA=... /Applications/QGIS-final-4_2_3.app/Contents/MacOS/gdalsrsinfo -o wkt2 EPSG:3857 > scripts/epsg3857.wkt` | PASS, saved a full declared junction CRS WKT2 using local QGIS GDAL. |
| `python3 -m unittest discover -s tests -p 'test_contract.py' -v` | PASS, 4 tests including byte-identical regeneration and 10k/50k generator checks. |
| `python3 -m unittest discover -s tests -p 'test_crs_contract.py' -v` | PASS, 1 test; PyQGIS test skipped because ordinary Python has no `qgis` module. |
| `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/test_crs_contract.py` | PASS, 2 tests; geographic source transformed to EPSG:32610 and measured using `QgsDistanceArea` in the 88–90 m oracle. |
| `python3 -m unittest discover -s tests -p 'test_graph_fixtures.py' -v` | EXPECTED FAIL, 18 errors: 17 cases and benchmark reach `tests/fixture_adapter.py`, which raises `NotImplementedError` until core services are connected. |
| `python3 -m unittest discover -s tests -p 'test_scaffold.py' -v` | PASS, 3 existing shell/package tests. |
| `python3 scripts/check_contract.py` | PASS, frozen registry and documentation remain consistent. |
| `bash scripts/run_qgis_scaffold_macos.sh` | PASS, 1 existing QGIS shell lifecycle smoke test after runner change. |

The fixtures assert positive and negative results, including no crossing connection, one permitted directed junction, forbidden turn, near miss, disconnected components, duplicate key/geometry, degenerate part, multipart provenance, blocked detour, same-edge interior geometry, outside snap tolerance, geographic metric length, reverse traversal, same location, partial batch failure, and CSV/HTML escaping. They use only invented geometry and text. The larger 10k/50k scaling files are generated on demand and are not repository artifacts.

## Limits and next action

`test_graph_fixtures.py` has no green product result because Network Builder, Inspector, Router, Batch and Packager services do not yet exist. The QGIS CRS probe verifies the measurement API and this fixture's bound, not route implementation. Wire the test-only adapter to real services as each capability lands; preserve the frozen expected results unless an architectural decision documents a genuine contract correction. Start Network Builder next, using crossing/gap/duplicate/part fixtures as the first gate.
