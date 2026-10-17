# Unresolved risks — charter baseline

2026-10-16. These are open until the named stage supplies evidence; this short log does not replace the later independent prior-art audit.

| Priority | Risk | Next evidence / owner stage |
| --- | --- | --- |
| Critical | Geometric crossings, touching or near misses may be mistaken for physical utility connectivity. | Architecture policy/schema, false-crossing fixtures, Network Builder and independent graph audit. |
| High | Missing asset junction/transition data can make a geometrically connected route misleading. | Explicit verification label, fail-closed unknowns, Inspector issues and reviewer warnings. |
| High | CRS, map-unit or Z/M mishandling can change the shortest route or reported length. | Meter-measurement tests in multiple CRSs and 2D disclosure at router/integration gates. |
| High | QGIS 4.2/Qt6 API behavior, packaging and fresh-profile installation are unverified here. | Scaffold runtime checks and final exact-ZIP clean install. |
| High | Third-party code/license obligations and upstream topology behavior are not yet audited file by file. | Independent prior-art/license review before any import. |
| Medium | User-controlled attributes or destination paths could create unsafe HTML/CSV or misleading partial exports. | Packager escaping/path/staging tests and final security review. |
