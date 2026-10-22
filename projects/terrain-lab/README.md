# Terrain Lab — geospatial sandbox and reusable engine

**North star:** Terrain Lab is a geospatial sandbox and reusable engine. It aims to turn authorized geographic sources into validated spatial results that can be inspected on a map and reused outside the browser. Research publications are the first rigorous source-ingestion examples; automated paper parsing and natural-language execution are planned capabilities. See [the north-star decision guide](NORTH_STAR.md).

The project also includes a local, browser-based 3D terrain atlas for the geographic setting of Dutcher et al. (2020), *Genes in space: what Mojave desert tortoise genetics can tell us about landscape connectivity*. This is an interpretive research viewer, not a map of individual tortoises or modeled corridors.

## Run locally

Requirements: Node.js 20.19+ or 22.12+ is recommended by recent Vite releases; this project is tested with Node.js 22.11 and Vite 6.4.

```bash
npm install
npm run dev
```

Open the local URL Vite prints, normally `http://127.0.0.1:5173/`. A network connection is needed to fetch map tiles. To check the production build:

```bash
npm run build
npm run preview
```

## Independent terrain sandbox

### Reviewable research intake pilot

Run `npm run research:intake -- --output research/intake/candidates/fleckenstein-2025.candidate.json` to create an unpublished, machine-checked proposal from the existing Fleckenstein discovery record and preserved USGS dataset. A second, previously uncurated pilot [staged Esque et al. (2023) Joshua tree presence grid cells](research/intake/README.md#new-paper-pilot-esque-et-al-joshua-tree-presence-cells) from a later USGS data release. After source review and project-owner authorization for a local investor demo, that dataset was registered separately in the catalog and map. See the [intake workflow and limits](research/intake/README.md), [demo decision](research/intake/esque-2023-joshua-tree.demo-decision.md), and [layer provenance](public/data/esque-2023-joshua-tree/PROVENANCE.md). Run `npm run test:research-intake`, `npm run test:joshua-intake`, and `npm run test:joshua-layer` for offline checks.

### Point distance from the command line

With Node.js and the project dependencies installed, calculate the WGS84 geodesic distance between two Point features in a GeoJSON file. Indices are zero-based positions in its FeatureCollection:

```bash
npm run --silent distance:cli -- public/data/study-sites.geojson 0 1
```

The command prints one JSON result to standard output, with distance in meters and a connecting GeoJSON LineString. For a file result, redirect output with `> distance.json`. Invalid files, indices, or non-Point selections print an error to standard error and exit with status 1. Run `npm run test:distance-cli` to check the interface.

Run `npm run test:distance-parity` to compare this command with the browser-facing analysis call on `scripts/fixtures/point-distance.geojson`. The check compares distance within 0.000001 m, line coordinates within 0.000000001 degree, labels, and analytical properties; generated IDs and timestamps may differ. It also validates both result FeatureCollections with Terrain Lab's GeoJSON inspector.

Verified result: both paths returned 1958.052085770897 meters, the ordered line from `[-112.115, 36.105]` to `[-112.095, 36.112]`, and matching analytical metadata. In the browser, the result appeared as a dashed computed line and Inspect map displayed `lab-derived-line` with the same meter value. Only generated IDs and timestamps differed. The parity check runs without a browser; the MapLibre inspection was checked in the existing UI.

Open [`/sandbox.html`](http://127.0.0.1:5173/sandbox.html) on the same local server. This is a separate workspace built with the atlas's MapLibre and terrain stack; it does not load the Dutcher study layers or findings.

- Fly between Grand Canyon, Death Valley, and Yosemite Valley camera presets, or navigate freely with drag, right-drag, wheel, and the map controls.
- Switch among satellite imagery, elevation color relief, and hillshade. Adjust camera tilt and DEM exaggeration, and orbit the current view.
- Import a WGS84 GeoJSON FeatureCollection, Feature, or geometry from your device. Record its credit or license and set its MapLibre layer opacity.
- For imported Point and MultiPoint collections, switch between MapLibre circles and a lazily loaded deck.gl ScatterplotLayer. The deck mode has pixel radius, color, opacity, a legend, and click/tap property inspection.
- Inspect a local GeoTIFF or a range-enabled remote COG, then display one chosen band with a raw-value legend, visibility, opacity, and a user-set display range. The raster is draped on the real terrain; its pixel values do not change the terrain height.
- Inspect a hosted PMTiles URL, choose a vector source layer or raster tile size, and add up to three hosted tile layers. Each has visibility, opacity, and a **View extent** control. Archive attribution stays in the map control.
- Turn on **Inspect map** to tap visible vector features and read their source, source layer, geometry type, and properties. It works with imported GeoJSON, hosted PMTiles vectors, and the visible base map. The map keeps its terrain and imagery; selecting a Geoman drawing or editing tool turns inspection off, and starting inspection stops the active Geoman tool. On mobile, open **Controls** to turn Inspect off.
- Draw markers, circle markers, text markers, lines, polygons, rectangles, circles, and ellipses with [MapLibre Geoman Free](https://github.com/geoman-io/maplibre-geoman). Edit vertices, move, rotate, cut, or remove drawings. The active tool appears in a floating bar with a **Done** button; on mobile, choosing a tool closes the controls drawer so the map is available.
- Measure line length, polygon area, point distance, and buffers for drawn or imported features. Export or remove computed geometry separately.
- Export drawn features or computed results as GeoJSON, or export the current camera, surface settings, imported GeoJSON and point display choice, drawings, computed geometry, PMTiles configurations, and GeoTIFF source/processing/display record as a JSON scene file. The exported file is a record of the scene; scene reimport is not implemented.

GeoJSON is parsed locally in the browser and is not uploaded. Mixed geometry remains limited to 3 MB and 10,000 features. Point-only collections can be up to 20 MB, 150,000 features, and 200,000 coordinates; these are browser safety limits, not a performance guarantee. Coordinates must be longitude/latitude in WGS84. Spatial analysis lists the first 500 imported features for large collections so its selectors stay responsive. The importer records the local filename, byte size, file modification time, WGS84 assumption, feature/coordinate counts, and user-entered credit in scene export. The credit also appears as a small map badge. If the file needs attribution, enter it before sharing the view or scene. Hosted map tiles still require an internet connection and follow the attribution and usage terms below. Elevation colors represent height in meters, not habitat suitability.

Scene export version `terrain-lab-scene/v7` keeps **source data** (`importedGeoJson` plus `importedProvenance`, hosted PMTiles configurations, and the GeoTIFF source record), **user-drawn geometry** (`drawnGeoJson`), and **computed results** (`derivedGeoJson`) in separate fields. Camera, basemap, terrain exaggeration, imported opacity, deck point style, and raster display settings describe the view; they are not observations. The GeoTIFF record contains metadata and processing choices, but not raster bytes. Full remote URLs, including signed query tokens, are saved verbatim; review a scene JSON before sharing it. There is no scene reimport or persistence between browser sessions.

The optional integrations load on first use: Geoman and its CSS when drawing starts, MapLibre GL Inspect when Inspect starts, PMTiles when an archive is inspected, each Turf module when its calculation runs, geotiff.js when a TIFF is opened, and deck.gl when its renderer is selected. An unused tool does not initiate its library's data requests. The atlas at `/` has a separate bundle and does not load Terrain Lab datasets.

The point mode uses [deck.gl's MapLibreOverlay](https://deck.gl/docs/api-reference/maplibre/overview) in overlaid mode, with a ScatterplotLayer loaded only when selected. MapLibre remains the camera and interaction controller; its imported circle layer is hidden while deck.gl renders points, so symbols are not duplicated. The deck canvas is a screen overlay at geographic coordinates. **Points are not draped over MapLibre terrain** and can appear above terrain ridges at tilted views. The controls specify radius in screen pixels. MapLibre fill and line layers remain in place for smaller mixed imports. If WebGL2 is unavailable or deck initialization fails, the control reports the problem and leaves MapLibre points visible. Clicking a deck point opens its source properties; turn off Inspect map or drawing first for deck point picking. The separate Inspect map tool queries MapLibre-rendered vector layers, not deck's canvas. Scene export records the renderer and style, along with the original imported GeoJSON.

Geoman edits newly drawn features. The existing imported GeoJSON layer remains a separate display layer. The Free package does not include freehand or custom-shape drawing, or advanced edit tools such as scaling, copying, splitting, unions, and line simplification; those require Geoman Pro. Drawn circles and ellipses export as GeoJSON polygons with Geoman shape metadata. The sandbox does not silently convert imported features into editable drawings.

Feature inspection uses [MapLibre GL Inspect](https://github.com/maplibre/maplibre-gl-inspect) v1.9 with MapLibre GL JS v6. It queries rendered features only on click while Inspect is active. Its built-in toggle is hidden; Terrain Lab provides the single visible Inspect control. The plugin's alternate inspection style is disabled so it never replaces Terrain Lab's terrain, imagery, or user layers. Starting Inspect stops Geoman drawing, and starting a drawing tool stops Inspect. At most eight overlapping features and 80 properties per feature are shown in a dismissible popup; zoom in to narrow dense selections. Raster pixels and features outside the current viewport are not inspectable.

### GeoTIFF raster workflow

Terrain Lab uses [geotiff.js](https://github.com/geotiffjs/geotiff.js) v3, loaded only when a raster is opened. **Choose local GeoTIFF** reads a file in the browser without uploading it. **Remote COG URL** accepts HTTPS, or HTTP on localhost for development. The host must allow cross-origin requests and return `206 Partial Content` plus `Content-Range` to byte-range GETs. The remote reader refuses whole-file responses. A remote URL is a source reference; it is not bundled into scene export. Signed URL query tokens are saved verbatim in the scene record, so review that JSON before sharing.

The metadata panel reports dimensions, WGS84 bounds, CRS, native pixel resolution, band count, declared band descriptions/units, NoData, and image-level count. Choose a band, optionally set numeric display minimum/maximum, then display it. Auto limits come from the decoded sample after NoData masking. Nearest-neighbor sampling preserves source values; a generic linear palette colors them. For EPSG:4326, output rows are resampled onto a Web Mercator grid before MapLibre drapes the image. EPSG:3857 is displayed in its native map projection. The palette is **not** an elevation, habitat, or measurement-unit inference. NoData is transparent. Source credit can be entered for the map attribution control and is stored in scene export.

This first viewer supports north-up PixelIsArea GeoTIFFs in EPSG:4326 or EPSG:3857, within Web Mercator's latitude range. It rejects missing or other CRS codes, rotated/skewed transforms, non-origin tie points, PixelIsPoint grids, and files whose compression cannot be decoded by geotiff.js. Local files are capped at 256 MB; remote archives at 2 GB. It decodes only one band from an image level of at most 4 million pixels with tiles/strips of at most 1 million pixels, and renders at most 1024 pixels on the longest side. Large rasters need internal overviews and suitable tiling. External `.ovr` files, arbitrary CRS reprojection, multiband composites, and per-pixel value queries are not yet implemented. Scene export records source identity, metadata, selected overview, band, resampling/reprojection choice, palette, range, opacity, and visibility; it does not embed local raster bytes.

### Hosting PMTiles

Terrain Lab uses the [official Protomaps MapLibre protocol](https://docs.protomaps.com/pmtiles/maplibre) with PMTiles v3 archives. Paste an HTTPS archive URL in **Hosted tiles**, then inspect it. Inspection reads the header and JSON metadata through byte range requests; adding the layer starts viewport tile requests. The reader rejects a host that answers a range request with an entire file, and caps each byte request at 4 MiB. PMTiles metadata provides tile type, zoom range, bounds, source-layer IDs, and attribution when present. Vector archives without source-layer metadata require an exact ID entered by the user. Raster archives default to 256 px tiles; choose 512 px if the archive uses that size. This is a tile overlay, not a complete external map style.

The archive host must return HTTP `206 Partial Content` for `Range: bytes=...`, with correct byte ranges. If the host is on a different origin, its [CORS configuration](https://docs.protomaps.com/pmtiles/cloud-storage) must allow the Terrain Lab origin to make GET requests with `Range` and expose `ETag` when available. The reader validates `Content-Range` when CORS exposes it; some working public hosts do not expose that header. Serve the PMTiles file as stable bytes; avoid a proxy or CDN that rewrites or compresses the entire archive. A `200 OK` whole-file response, invalid exposed `Content-Range`, CORS failure, inaccessible file, or unsupported tile type produces an error in the layer form. Hosted archives are fetched from the user's browser, so any access control and usage terms belong to that host.

The form accepts HTTPS URLs, plus HTTP on localhost for development. It supports MVT and MLT vector tiles and PNG, JPEG, WebP, and AVIF raster tiles. AVIF display depends on browser support. PMTiles DEM tiles are not wired into the terrain control. Up to three hosted archives may be active, with one selected source layer per archive URL, to limit duplicate tile requests. Visibility and opacity do not modify archive data. Attributions embedded in archive metadata are retained as escaped text in the map control; when absent, the form requires a credit before adding the layer. Scene export stores full archive URLs, including signed query tokens; review that file before sharing it. Signed URLs may expire, and scene import is not implemented.

Public test archives from the [PMTiles project](https://github.com/protomaps/PMTiles) are [Firenze vector tiles (ODbL)](https://pmtiles.io/protomaps(vector)ODbL_firenze.pmtiles) and [Stamen Toner raster tiles (CC BY + ODbL)](https://pmtiles.io/stamen_toner(raster)CC-BY+ODbL_z3.pmtiles). The former includes vector source-layer metadata and OpenStreetMap credit. The latter lacks attribution metadata, so enter its Stamen and OpenStreetMap credits in the form.

## What works

- 3D terrain from real elevation tiles, with pan, orbit, zoom, and tilt.
- Keyless Sentinel-2 satellite mosaic, elevation color relief, and hillshade views.
- Optional map roads/labels and 3D terrain; map navigation remains available if a tile service fails.
- Smooth camera navigation among six geographic reference viewpoints. Viewpoint labels become compact dots at regional scale.
- Five guided chapters with composed valley, pass, and infrastructure views and verified overlay changes.
- Crossfades among satellite imagery, elevation color relief, and hillshade; the elevation view is explicitly labeled as terrain in meters, not habitat suitability.
- Aggregate markers for all eleven sampling locations, including a distinct Piute Valley area marker.
- Census I-15 and railway lines and one authorized BLM solar right-of-way polygon.
- Four study-figure interpretation tabs and an interactive findings panel.
- Responsive interface with a collapsible layer panel on narrow screens.

**Map controls:** drag to pan; right-drag or use the compass control to rotate/tilt; scroll or use +/- to zoom. The Orbit button rotates the camera until clicked again or the map is moved. Geographic view buttons and map labels move to reference points. Full extent returns to the regional view. Open **Layers** for overlays; the basemap switch remains visible when the drawer is closed. Camera animation respects reduced-motion preferences.

## Tile sources, license, and attribution

| Role | Source | Terms / attribution |
| --- | --- | --- |
| Satellite mosaic | [EOxCloudless 2020 WMTS](https://cloudless.eox.at/documentation/usage) | [Free noncommercial research/education use](https://cloudless.eox.at/documentation/license). Visible credit in the layer panel and MapLibre attribution: “EOxCloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2020).” Commercial use requires an appropriate EOX license. |
| Elevation DEM | [Mapterhorn Terrain TileJSON](https://mapterhorn.com/data-access/) | [Source credits](https://mapterhorn.com/attribution/) are exposed in the layer panel and MapLibre attribution. |
| Reference roads/labels | [OpenFreeMap Liberty style](https://openfreemap.org/) | [OpenFreeMap, OpenMapTiles, and OpenStreetMap attribution](https://github.com/hyperknot/openfreemap#attribution) appears in the map control. |

The app never requires a paid API key. These hosted services may change availability, coverage, or terms. The app falls back from unavailable satellite imagery to hillshade, and disables terrain if elevation tile requests fail repeatedly. The base style and fonts still require OpenFreeMap; if it is unavailable, the interface explains the network error. The shipped highway and rail GeoJSON is clipped to the atlas viewing envelope and simplified for responsive rendering.

MapLibre APIs follow its current [3D terrain](https://maplibre.org/maplibre-gl-js/docs/examples/3d-terrain/), [hybrid satellite terrain](https://maplibre.org/maplibre-gl-js/docs/examples/display-a-hybrid-satellite-map-with-terrain-elevation/), [color relief](https://maplibre.org/maplibre-gl-js/docs/examples/add-a-color-relief-layer/), and [Vite worker setup](https://maplibre.org/maplibre-gl-js/docs/) documentation. The color ramp reads DEM elevation in meters; it is **not** habitat suitability.

## Geographic data and scientific scope

The Dutcher publication now has a validated, reusable metadata record in `src/data/dutcherStudy.ts`, using the schema and runtime validator in `src/data/studyMetadata.ts`. It records citation, discipline, 2015–2017 sampling period, source links, dataset provenance, and limitations. Dataset roles distinguish a verified **study footprint**, **observed geography**, **derived output**, and **model prediction**. The named Ivanpah study area has a source, but no footprint dataset: the map extent and aggregate points are not a verified boundary. The USGS individual records are external observed data; the shipped site means are derived from them; contextual public GIS layers are identified separately; and the unrecovered habitat-resistance surface is marked as an unavailable model prediction. Run `npm run test:study` to validate the record and its shipped GeoJSON references.

The research catalog in `src/data/studies.ts` also registers [Nussear et al. (2009), USGS Open-File Report 2009-1102](https://pubs.usgs.gov/publication/ofr20091102) as `src/data/nussearStudy.ts`. Its verified study area is the Mojave and parts of the Sonoran Deserts in California, Nevada, Utah, and Arizona; no study-footprint polygon or tortoise observation coordinates are registered. The original **Habitat Model** ZIP is preserved with a checksum, and its binned ASCII grid has been converted with nearest-neighbor sampling to a bundled EPSG:3857 GeoTIFF and raster display tiles. Use **Explore published habitat model** in Terrain Lab's existing GeoTIFF panel to display it; the panel links the map layer to the publication and original ZIP, and scene export records the study and dataset IDs. The raster envelope is not a study boundary, and the values are model predictions, not observations or validation of the report. See [raster provenance](public/data/nussear-2009/PROVENANCE.md) for CRS, extent, processing, and reuse terms. The separate **Environmental Layers** ZIP has not been ingested. The Dutcher atlas continues to display only Dutcher material.

The catalog now also registers [Fleckenstein et al. (2025)](https://doi.org/10.7717/peerj.18568). **Explore USGS solar arrays** in the sandbox loads 872 polygons from the cited, archived 2023 USPVDB source through the existing MapLibre GeoJSON layer. Use **Inspect map** to see facility attributes and study/dataset links. The original archive, conversion, CRS, extent, CC0 reuse statement, uncertainty, and data-selection decision are in the [selection and provenance record](research/discovery/fleckenstein_2025_selection.md). These are solar infrastructure polygons, not tortoise observations, model predictions, or a verified study boundary. Run `npm run test:fleckenstein-layer` for the source and layer checks. The Dutcher atlas and Nussear layer remain available.

The catalog also registers [Esque et al. (2023)](https://doi.org/10.3389/fevo.2023.1266892) with 941 mapped Joshua tree hybrid-presence grid cells from a linked [2025 USGS release](https://doi.org/10.5066/P9NZMDLL). **Explore Joshua tree grid cells** loads them into the sandbox's existing MapLibre layer; **Inspect one cell's area** displays the observed source cell and a separately classified headless polygon-area result. The 158,110 m² calculation measures one mapped cell, not tree cover or habitat. The release's nominal 0.25 km² survey-grid description does not match the selected cells' approximately 0.157–0.158 km² source polygons; the reason is unresolved and documented in [provenance](public/data/esque-2023-joshua-tree/PROVENANCE.md). Run `npm run research:joshua-area` for browser-free GeoJSON and `npm run test:joshua-layer` for validation. The Dutcher, Nussear, and Fleckenstein views remain available.

### Headless solar-array area demo

Open the [live local demo report](public/reports/terrain-lab-demo-2026-10-21.html) from a running Terrain Lab preview at `/reports/terrain-lab-demo-2026-10-21.html`. It embeds the existing sandbox beside a walkthrough, measured result, verification status, provenance links, and scientific limits.

For a concise investor presentation, open the [22 October live demo](public/reports/terrain-lab-investor-demo-2026-10-22.html) at `/reports/terrain-lab-investor-demo-2026-10-22.html` in a running local preview. It begins with the Joshua tree paper-to-map case, lets viewers inspect its checked one-cell calculation, and can switch to the earlier solar-array example. The page distinguishes current capabilities from the product roadmap and surfaces the unresolved survey-grid area question.

**Inspect example array area** in the sandbox loads USPVDB case 400038 (CalRenew-1) as the source polygon and its separately classified area result through the existing MapLibre imported and derived layers. **Inspect map** shows their attributes; scene export retains source and computation provenance. The Turf geodesic area is **161,416.349 m²**. The USPVDB `p_area` attribute is **161,468 m²**, 51.651 m² higher; that comparison is a useful cross-check, but the source's area method and digitizing accuracy are not an independent ground truth. This measures one image-digitized solar panel array, not total developed land, tortoise habitat, ecological impact, or the paper's model.

From the repository root, run `npm run research:area` to print machine-readable GeoJSON without launching a browser. Run `npm run research:area -- --output public/data/fleckenstein-2025/case-400038-area.geojson` to regenerate the bundled demo. The command verifies SHA-256 hashes of the preserved original USGS archive and prepared WGS84 GeoJSON, checks the selected source feature, validates the polygon-area request, and writes one unchanged source feature plus one derived feature. Invalid input or missing/changed source data exits nonzero. `npm run test:research-area`, `npm run test:area-contract`, and `npm run test:analysis` verify the workflow, contract, independent geometric fixtures, CLI, and browser/headless parity. See [area provenance](public/data/fleckenstein-2025/AREA_PROVENANCE.md).

The [operation catalog](public/operations/index.json) exposes the versioned [polygon-area descriptor](public/operations/polygon-area.v1.json). Local applications can import `runPolygonAreaRequest` from `src/geo/polygonAreaContract.ts` with `{ contractVersion: 'terrain-lab-operation/v1', operationId: 'polygon-area', units: 'square-meters', input }`, where `input` is a keyed GeoJSON Polygon or MultiPolygon feature in WGS84 longitude/latitude. It returns a structured result or error. The browser area tool and headless workflow call this same adapter and Turf implementation. Unverified `sourceReference` text stays marked `caller-supplied`; only an internal workflow that checked the registered source files supplies the adapter's separate verified-evidence argument. A future HTTP or MCP transport can publish the static catalog and pass requests to this adapter; neither service exists yet, and no OGC conformance is claimed.

### Desert tortoise publication discovery

Python 3.10+ and a network connection are required to refresh the publication list; no Python packages need to be installed. The collector in `scripts/desert_tortoise_research.py` searches OpenAlex, Crossref, and Europe PMC for Mojave, Sonoran, and Sinaloan desert tortoise publications. From the project root, run:

```bash
npm run research:discover -- --since 2023-10-18 --limit 50 --output-prefix research/discovery/desert_tortoise_papers
```

The command writes `research/discovery/desert_tortoise_papers.csv`, `.json`, and `.md`, replacing the previous files with that prefix. Use `--email your-address@example.org` for API contact information, `--per-query` to search more candidates per term and source, or `--scrape-abstracts` to fill missing abstracts from permitted publisher metadata. The bundled snapshot was generated on 2026-10-18: 25 records, with no reported source errors. The collector merges matching DOIs even when titles differ, uses normalized titles when a DOI is missing, and keeps records with different DOIs separate. Invalid, future, and pre-cutoff publication dates are excluded. Partial API failures are reported in the JSON `source_errors` field and Markdown warning while successful results are retained; complete API failure exits with status 1. Run `npm run test:research-discovery` for offline checks of these behaviors and output consistency.

These files are **discovery records**, not registered studies or geographic datasets. API metadata and dates may be incomplete or wrong, and the searches are not a systematic review. An open-access paper or abstract does not establish the availability, license, coordinate system, accuracy, or sensitivity of its supporting spatial data. Verify the publisher record, dataset source, reuse terms, and any sensitive tortoise locations before registering a study or displaying a layer. The discovery command does not change the browser interface or automatically add papers to the research catalog.

The same panel's **Inspect example cell distance** control loads a saved result from the headless point-distance operation: two 0.9-valued prediction-grid cell centers and their 50.074 km straight-line separation. Model cells and computed geometry remain distinct in the map and scene export. Run `npm run research:distance -- 350 300 400 300` to print GeoJSON without a browser, or add `--output public/data/nussear-2009/cell-distance.geojson` to regenerate the bundled result. `npm run test:research-distance` checks the source values, an independently calculated expected distance, validation failures, and CLI execution. This geometry does not describe habitat connectivity or tortoise movement; see [analysis provenance](public/data/nussear-2009/PROVENANCE.md#example-headless-cell-distance-analysis).

### Point-distance operation contract

The first transport-independent contract is `terrain-lab-operation/v1`. Its static [operation catalog](public/operations/index.json) and [point-distance descriptor](public/operations/point-distance.v1.json) are machine-readable; a hosted Terrain Lab serves them at `/operations/index.json` and `/operations/point-distance.v1.json`. The descriptor specifies JSON request, success, and error schemas, WGS84 longitude/latitude inputs, numeric meters and GeoJSON LineString output, limits, and scientific caveats. There is no execution URL or network service. Applications running the project code can import `runPointDistanceRequest` from `src/geo/pointDistanceContract.ts`.

The adapter accepts `{ contractVersion, operationId, inputs: { first, second }, sourceReference? }`. Each input is a `SourceFeature` with a unique key, label, and GeoJSON Point feature. It returns `{ contractVersion, operationId, ok: true, result, provenance }` or `{ contractVersion, operationId, ok: false, error: { code, message } }`. `result` is the existing `AnalysisResult`, including the computed LineString and numeric meters. `validatePointDistanceRequest` and `validatePointDistanceResponse` are available for runtime checks. The adapter calls the existing Turf-backed `computePointDistance`; it does not recalculate the distance. The browser distance control and existing GeoJSON CLI use this adapter while retaining their previous result format. Run `npm run test:distance-contract` for descriptor, validation, provenance, and parity checks.

An external request can provide a `sourceReference`, but the response marks it `caller-supplied`; input feature properties cannot confer verified status. The optional second argument to the adapter is trusted registered-dataset evidence for internal callers only. The Nussear workflow supplies it **after** checking its registered raster and archive checksums, and its saved GeoJSON records `sourceVerification: registered-dataset`. A future HTTP handler or MCP tool should validate external JSON with this adapter and never copy a user-provided verification claim into that internal argument. The same descriptor could drive an HTTP operation listing or an MCP tool definition; neither transport exists yet. This static catalog is not an OGC conformance claim.

The six camera targets remain documented landscape reference points, separate from the eleven aggregate USGS sampling markers. The point called “Piute Valley” in the navigation row is a **Searchlight-edge viewpoint**; the amber Piute sampling symbol comes from the public genotype release. The default map extent is a viewing frame, not a research boundary. See [`public/PROVENANCE.md`](public/PROVENANCE.md) for dataset citations, accuracy, processing, and limitations.

The source data includes individual tortoise coordinates, but the atlas publishes only the mean location of each named sampling group. This supports viewing the study distribution without exposing exact individual locations or inventing plot outlines. The processing script is [`scripts/build_verified_layers.py`](scripts/build_verified_layers.py); run it with `pyproj` installed to rebuild the GeoJSON assets.

The Figure 2 interface compares uniform, highway, railway, and habitat-based resistance concepts without drawing an unverified raster. In the paper, habitat resistance was `1 − modeled habitat suitability`. The displayed elevation colors are terrain, never habitat suitability. The Figure 3 and 4 panels explain the three broad genetic groups and two spatial axes without inventing assignment percentages, group boundaries, axis scores, or tortoise paths.

The railway and highway parallel each other, so the paper does not definitively separate their effects. It also lacks preconstruction genetic measurements. The 60 km relatedness result does not trace a single animal's journey. The paper's Table 4 has an apparent mismatch between printed parameter counts and AIC values, so model weights should be rechecked before any quantitative reproduction.

The [USGS 2020 genotype data release](https://www.sciencebase.gov/catalog/item/5e38914ce4b0a79317df572d) has 299 rows, plot labels, NAD83 UTM coordinates, and 20 microsatellite marker pairs. It does not contain the published STRUCTURE assignment fractions or spatial PCA site scores. The habitat suitability and resistance rasters were not recovered. No relevant, verified urban footprint was added. The BLM solar polygon represents only one right-of-way, not the full Ivanpah solar development.

## Project structure

- `src/data/places.ts`: sourced map targets and view settings.
- `src/data/story.ts`: guided research narrative.
- `src/data/figures.ts`: figure interpretations, reported values, and sampling roster.
- `src/map/atlasMap.ts`: MapLibre sources, visual layers, terrain, camera, and service fallback.
- `public/data/*.geojson`: derived aggregate sampling points and public GIS overlays.
- `public/PROVENANCE.md`: source, accuracy, processing, and limitation register.
- `src/main.ts`: interface and interactions.
- `src/style.css`: presentation and responsive layout.

## Dutcher atlas research follow-ups

1. Recover the original habitat suitability and resistance rasters or document a defensible reconstruction.
2. Obtain numeric STRUCTURE assignments and spatial PCA scores from authors or reproducible analysis files.
3. Locate a validated urban-development footprint and complete solar footprints for the sampling period.
4. Resolve Table 4's AIC arithmetic and rerun model comparison before treating its ranking as reproduced.
