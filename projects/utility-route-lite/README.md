# Utility Route Lite

Utility Route Lite is a QGIS 4.2+ / Qt6 plugin for **proposed** routes through existing linear utility corridors. The experimental v0.1.0 package implements **Network Builder**. The remaining four Processing tasks and Route Reviewer display **NOT IMPLEMENTED**; the package cannot produce routes or review decisions yet.

The planned launch promise is: “Produce a connected, inspectable *proposed* route through an existing utility pathway network, subject to declared connectivity rules.” Geometric endpoint contact does not verify physical asset connectivity. Crossings do not imply junctions. The plugin will not edit source utility layers or certify an engineering design.

## Draft local installation

1. Use QGIS 4.2 or newer in the 4.x series. Build the ZIP with `python3 scripts/build_zip.py`.
2. In QGIS, choose **Plugins → Manage and Install Plugins → Install from ZIP**, and select `dist/utility_route_lite-0.1.0.zip`.
3. Enable Utility Route Lite. The Processing provider lists five tasks. Network Builder writes a graph JSON and QA GeoPackage from an existing read-only line source, a declared profile and explicit CRS values. The plugin menu opens the placeholder Route Reviewer dock.

This workflow is a draft. A clean installation through the QGIS Plugin Manager remains unverified. Do not publish this version as a functional routing plugin.

## Development checks

Run `python3 -m unittest discover -s tests -p 'test_builder_core.py'`, `python3 -m unittest discover -s tests -p 'test_scaffold.py'`, `python3 -m unittest discover -s tests -p 'test_contract.py'`, and `python3 -m unittest discover -s tests -p 'test_crs_contract.py'` for implemented Python and fixture checks. `test_graph_fixtures.py` remains red for routing, batch and export services; see [examples/README.md](examples/README.md). On macOS with QGIS 4.2.3 installed, run `bash scripts/run_qgis_scaffold_macos.sh` for provider/dock lifecycle and `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/qgis_builder.py` for Builder integration. Pass an alternate QGIS application path as the first argument if needed. The ZIP contains one `utility_route_lite/` folder and only plugin files and `LICENSE`.

No network service, database server, API key, telemetry, or third-party Python dependency is used by this shell. Runtime imports come from the QGIS-installed Python environment. The project declares GPL-3.0-or-later; the full GPLv3 text is in `LICENSE`. The icon is an original project asset. No third-party program source was imported.

The author and contact values in metadata are approval placeholders; real repository and tracker URLs are also required before publication. See `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACT.md`, and `docs/BUILD_STATUS.md` for the planned product and the frozen interface.
