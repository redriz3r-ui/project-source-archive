# Prompt 04 handoff — plugin scaffold

## Changed files

- Added `utility_route_lite/__init__.py`, `plugin.py`, `processing/__init__.py`, `processing/provider.py`, `processing/algorithms.py`, `metadata.txt`, and original `icon.svg`.
- Added root `LICENSE` (standard GNU GPL version 3 license text), `pyproject.toml`, `README.md`, `scripts/build_zip.py`, `scripts/run_qgis_scaffold_macos.sh`, `tests/test_scaffold.py`, and `tests/qgis_smoke.py`.
- Updated `docs/BUILD_STATUS.md`. Built `dist/utility_route_lite-0.1.0.zip`.

The project license is GPL-3.0-or-later as declared in metadata and README. QGIS is GPL-2.0-or-later; the [prior-art audit](audits/PRIOR_ART.md) found this compatible. No third-party program source was imported. The icon is original. The packaged GPLv3 text covers the chosen license family; project grants say “or later.”

## Commands actually run and evidence

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -p 'test_*.py' -v` | PASS, 3 pure-Python tests (syntax, ZIP allowlist and metadata) |
| `python3 scripts/check_contract.py` | PASS, frozen contract registry/docs consistency |
| `bash scripts/run_qgis_scaffold_macos.sh` | PASS, 1 offscreen QGIS 4.2.3 test after the parameter comparison was added; ZIP extraction, classFactory, five exact algorithm IDs and parameters, explicit failures, dock, unload |
| `python3 scripts/build_zip.py` | PASS, created `dist/utility_route_lite-0.1.0.zip` |
| `unzip -l dist/utility_route_lite-0.1.0.zip` | PASS, eight entries under one `utility_route_lite/` directory; no docs/tests/cache/secrets |

The QGIS test uses bundled Python and an offscreen fake `iface`. QGIS Plugin Manager installation, GUI behavior in a live QGIS window, other 4.x versions, and any functional routing are **UNVERIFIED**. Metadata author/contact and real repository/tracker URLs require owner details before publication. All algorithm execution raises `QgsProcessingException` with `NOT IMPLEMENTED`; no source utility layers are written.

## Next action

Create synthetic fixtures from the acceptance matrix, then implement and independently test Network Builder and Inspector. Before release, install the built ZIP in a clean QGIS 4.2+ profile and validate the real menu/provider UI. Reproduce the local shell smoke with `bash scripts/run_qgis_scaffold_macos.sh [path-to-QGIS.app]`.
