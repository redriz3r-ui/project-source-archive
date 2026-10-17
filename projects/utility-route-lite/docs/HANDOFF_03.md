# Prompt 03 handoff — architecture and interfaces

Date: 2026-10-16. **Outcome:** the v1 public interface is specified and frozen at `schema_version=1.0.0`. This is a design milestone. No plugin implementation, Processing registration, GUI workflow or release ZIP exists yet.

## Files changed

- Added `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACT.md`, `docs/ACCEPTANCE_MATRIX.md`, `docs/contract/v1.json` and this handoff.
- Added `scripts/check_contract.py` and `tests/audit/test_contract_registry.py`. These are architecture validation tools, not product application code.
- Updated `docs/DECISIONS.md` with D-012 through D-017, `docs/BUILD_STATUS.md`, and the closing paragraph of `docs/audits/RISKS.md`. The prior-art report and its evidence were preserved.

## Commands actually run and evidence

| Command | Result |
| --- | --- |
| `rg --files ...`, `rg -n ...`, `cat docs/BUILD_STATUS.md docs/DECISIONS.md utility_route_lite_prompts/03_GPT6_freeze_interfaces_and_architecture.md` | Inspected current docs, the prior audit and later prompts before writing. No Git repository is present in this directory. |
| `python3 scripts/check_contract.py && python3 -m unittest discover -s tests/audit -p 'test_contract_registry.py' -v` (first run) | **Fail:** validator found missing literal `same-edge` in acceptance prose. The matrix was corrected. |
| Same command after correction | **Pass:** contract registry/prose consistent; four stdlib negative/positive tests passed. Rerun after later contract edits is recorded below. |
| `python3 -m json.tool docs/contract/v1.json >/dev/null` | **Pass:** machine registry parses as JSON. |
| `python3 scripts/check_contract.py > docs/audits/evidence/architecture-contract.txt 2>&1`, then the unittest command appended to that file | **Pass:** final registry/prose check and four tests; [saved output](audits/evidence/architecture-contract.txt). The JSON syntax check also passed after the final contract edit. |

The current PyQGIS availability evidence is Prompt 02's [eight passing synthetic API probes](audits/evidence/qgis-feasibility.txt) on QGIS 4.2.3 / Qt 6.11.1. Those were **not rerun for this documentation change**. QGIS plugin integration remains **UNVERIFIED**. To run the existing host probe locally: `bash scripts/run_qgis_audit_macos.sh /Applications/QGIS-final-4_2_3.app`. To check this contract: `python3 scripts/check_contract.py` and `python3 -m unittest discover -s tests/audit -p 'test_contract_registry.py' -v`.

## Limits and next action

This checker finds internal registry/documentation drift; it does not prove shortest-path semantics, safe topology, legal reuse, QGIS compatibility or successful installation. All product cases in [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md) remain **Not Run**. The strict exact-equality policy can disconnect near-matching data by design; that must appear as QA, not an automatic fix. Declared junctions are user assertions, not physical verification. The proposed GPL-3.0-or-later license still needs adoption at scaffold and file-specific review before importing third-party code.

Next implement the one-plugin scaffold, then synthetic fixtures and the six capabilities in [BUILD_STATUS.md](BUILD_STATUS.md) order. Tool implementers must preserve `docs/contract/v1.json`; any necessary interface revision goes through a numbered `docs/DECISIONS.md` entry, migration analysis, acceptance tests and architect review before code changes.
