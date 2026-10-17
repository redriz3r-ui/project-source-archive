# Synthetic fixture suite v1

These fixtures are generated from simple invented coordinates and feature IDs. They contain no real utility locations or critical infrastructure data and may be redistributed with the project under GPL-3.0-or-later. `scripts/regenerate_fixtures.py` is the sole source; JSON files in `examples/fixtures/v1/` are committed-style generated artifacts, not hand-edited GIS data. Each case embeds its versioned expected results.

Run `python3 scripts/regenerate_fixtures.py` to regenerate the 17 small cases and `benchmark_1000.json`. The generator uses sorted JSON keys, fixed formatting, and no randomness or timestamps. To generate a larger scaling input without adding a large repository file, run `python3 scripts/regenerate_fixtures.py --scale 10000 --output /tmp/utility-route-fixtures` or substitute `50000`. The 1,000-edge case is a connected straight chain whose expected route is 1,000 meters. Scaling files are performance inputs, not benchmark speed claims.

The `source` member is a GeoJSON-style FeatureCollection inside a fixture envelope. Source and network CRS are explicitly declared beside it. Projected synthetic cases use EPSG:3857 with `ellipsoid: NONE` so their simple lengths are planar meters. Declared junctions carry full WKT2 from `scripts/epsg3857.wkt`, generated with the QGIS-bundled GDAL tool. The geographic case uses EPSG:4326 source, EPSG:32610 network, and WGS84 ellipsoidal length; its 88–90 meter oracle is deliberately a range to avoid asserting a universal byte-identical transform. The examples are input scenarios, not the `network_graph.json` public output schema.

| Case group | Expected behavior encoded in JSON |
| --- | --- |
| `crossing_unconnected`, `declared_junction`, `prohibited_turn` | A crossing stays disconnected; one declared directed turn works; an undeclared turn fails. |
| `tiny_endpoint_gap`, `disconnected_components` | Gap and separate components do not autojoin; near miss and component QA are required. |
| `duplicate_source_id`, `duplicate_geometry`, `zero_length_edge` | Duplicate key and degenerate part fail construction; overlap is reported and equal snap edges are ambiguous. |
| `multipart_refs`, `blocked_shortcut`, `same_bent_line_interior` | Part index and route segment order persist; blocked shortcut is bypassed; interior route keeps bend vertices. |
| `outside_snap_tolerance`, `geographic_metric`, `reverse_direction`, `same_start_end` | Strict snap, meter length, original line orientation, and same-location failure. |
| `batch_one_bad_record`, `csv_html_escaping` | One invalid row does not erase valid routes; output text is HTML escaped and spreadsheet formula text is neutralized. |

`tests/test_contract.py` checks generated file identity, schema codes and deterministic regeneration. `tests/test_crs_contract.py` checks the geographic oracle; its PyQGIS test skips under ordinary Python and runs under the QGIS bundle. Run `bash scripts/run_qgis_scaffold_macos.sh /Applications/QGIS-final-4_2_3.app tests/test_crs_contract.py` locally for that integration check.

`tests/test_graph_fixtures.py` is intentionally **red** until the core services exist. It compares observed build, QA, route, batch and export behavior with each case's expected results. `tests/fixture_adapter.py` is a test-only seam that currently raises `NotImplementedError`; implementers should connect it to real services without editing the expected results to fit broken behavior. Run the red suite with `python3 -m unittest discover -s tests -p 'test_graph_fixtures.py' -v`. The other tests can be run separately with `python3 -m unittest discover -s tests -p 'test_contract.py' -v` and `python3 -m unittest discover -s tests -p 'test_crs_contract.py' -v`.

The expected results reflect [the frozen data contract](../docs/DATA_CONTRACT.md) and [acceptance matrix](../docs/ACCEPTANCE_MATRIX.md). If a result conflicts with a frozen contract rule, record a decision in `docs/DECISIONS.md` before changing either. The fixture adapter's normalized observation keys are documented in its module header; they are test-only and do not extend the plugin's public API.
