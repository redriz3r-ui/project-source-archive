import 'maplibre-gl/dist/maplibre-gl.css';
import { Popup, setWorkerUrl } from 'maplibre-gl';
import type MaplibreInspect from '@maplibre/maplibre-gl-inspect';
import type { GeoJSONFeatureWithSourceLayer } from '@maplibre/maplibre-gl-inspect';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import './style.css';
import { SandboxMap, preparePmtiles, presets, type Basemap, type Camera } from './map';
import { inspectGeoJson } from './geojson';
import { DrawingWorkspace, drawTools, editTools, type ActiveTool } from './drawing';
import { compute, resultsGeoJson, sourceFeatures, supports, type AnalysisResult, type Operation } from './analysis';
import { POINT_DISTANCE_CONTRACT_VERSION, POINT_DISTANCE_OPERATION_ID, runPointDistanceRequest } from '../geo/pointDistanceContract';
import { POLYGON_AREA_CONTRACT_VERSION, POLYGON_AREA_OPERATION_ID, runPolygonAreaRequest } from '../geo/polygonAreaContract';
import type { ArchiveInspection } from './pmtiles';
import type { TiffSession, DecodedBand, TiffMetadata } from './geotiff';
import { nussearStudy } from '../data/nussearStudy';
import { fleckensteinStudy } from '../data/fleckensteinStudy';
import { esqueStudy } from '../data/esqueStudy';
import type { DeckPoints, PointDatum, PointStyle } from './deckPoints';
import type { DrawModeName, EditModeName } from '@geoman-io/maplibre-geoman-free';

const app = document.querySelector<HTMLDivElement>('#app')!;
setWorkerUrl(workerUrl);
app.innerHTML = `
  <div id="map" aria-label="Interactive three dimensional terrain map"></div>
  <div class="scrim"></div>
  <header class="masthead">
    <div class="brand"><span class="brand-mark" aria-hidden="true">△</span><span><strong>TERRAIN LAB</strong><small>AN OPEN GEOSPATIAL SANDBOX</small></span></div>
    <div class="head-actions"><span class="live"><i></i><span id="status">LOADING TERRAIN</span></span><a href="/" class="atlas-link">RESEARCH ATLAS <span aria-hidden="true">↗</span></a></div>
  </header>
  <aside id="workspace" class="workspace" aria-label="Sandbox controls">
    <div class="workspace-scroll">
      <div class="intro"><span class="eyebrow">01 / EXPLORE</span><h1>Shape the view.</h1><p>Move across real terrain. Change the surface, tune the camera, and place your own spatial data.</p></div>
      <section class="section"><div class="section-heading"><h2>Geographic scenes</h2><span>FLY TO</span></div><div id="presets" class="presets"></div></section>
      <section class="section"><div class="section-heading"><h2>Surface</h2><span>BASEMAP</span></div><div class="basemaps" role="group" aria-label="Terrain appearance">
        <button data-base="satellite" class="selected" aria-pressed="true"><span class="base-icon satellite-icon"></span><strong>Satellite</strong><small>Imagery</small></button>
        <button data-base="elevation" aria-pressed="false"><span class="base-icon elevation-icon"></span><strong>Elevation</strong><small>Color relief</small></button>
        <button data-base="hillshade" aria-pressed="false"><span class="base-icon hillshade-icon"></span><strong>Hillshade</strong><small>Shaded relief</small></button>
      </div><p class="hint">Elevation colors show terrain height in meters.</p></section>
      <section class="section"><div class="section-heading"><h2>Camera &amp; terrain</h2><span>ADJUST</span></div>
        <label class="slider-label" for="pitch"><span>Camera tilt</span><output id="pitch-value">63°</output></label><input id="pitch" type="range" min="0" max="80" value="63" step="1" />
        <label class="slider-label" for="terrain"><span>Terrain height</span><output id="terrain-value">1.2×</output></label><input id="terrain" type="range" min="0" max="3" value="1.2" step="0.1" />
        <button id="orbit" class="action-button" aria-pressed="false"><span class="action-symbol">◎</span><span>Orbit camera</span><span id="orbit-state" class="action-state">START</span></button>
      </section>
      <section class="section data-section"><div class="section-heading"><h2>Your layers</h2><span>GEOJSON</span></div>
        <p class="section-copy">Load WGS84 GeoJSON from your device. It stays in this browser session.</p>
        <input id="file" type="file" accept=".geojson,.json,application/geo+json,application/json" hidden />
        <button id="import" class="import-button">＋ &nbsp; Add GeoJSON layer</button>
        <div class="tiff-inspection"><strong>New study · Joshua tree distribution</strong>
          <p>Explore 941 USGS mapped hybrid-presence grid cells in Nevada, linked to Esque et al. (2023). These cells are observed geography, not individual trees, model predictions, or a study boundary.</p>
          <button id="esque-load" class="import-button">Explore Joshua tree grid cells</button>
          <button id="esque-area" class="import-button">Inspect one cell’s area</button>
          <p>The area result measures one mapped grid cell only. It does not measure tree cover or validate the paper’s climate findings.</p>
          <p><a href="https://doi.org/${esqueStudy.doi}" target="_blank" rel="noopener">Paper</a> · <a href="${esqueStudy.provenanceUrl}" target="_blank" rel="noopener">USGS source data</a> · <a href="/data/esque-2023-joshua-tree/PROVENANCE.md" target="_blank" rel="noopener">Provenance and limits</a></p>
        </div>
        <div class="tiff-inspection"><strong>Fleckenstein et al. (2025) · cited solar infrastructure</strong>
          <p>Explore 2023 USGS solar-array polygons in the seven states named by the study methods. These are infrastructure data, not tortoise observations, model predictions, or a study boundary.</p>
          <button id="fleckenstein-load" class="import-button">Explore USGS solar arrays</button>
          <button id="fleckenstein-area" class="import-button">Inspect example array area</button>
          <p>The example measures one USGS solar-array polygon (case 400038). It does not measure tortoise habitat or test the paper's ecological findings.</p>
          <p><a href="https://doi.org/${fleckensteinStudy.doi}" target="_blank" rel="noopener">Study</a> · <a href="${fleckensteinStudy.provenanceUrl}" target="_blank" rel="noopener">Original USGS release</a></p>
        </div>
        <div id="layer-card" class="layer-card" hidden><div class="layer-top"><span class="layer-dot"></span><div><strong id="layer-name"></strong><small id="layer-details"></small></div><button id="clear-layer" title="Remove imported layer" aria-label="Remove imported layer">×</button></div><small id="layer-origin" class="layer-origin"></small><p id="layer-limitations" class="hint" hidden></p><label class="import-credit-label" for="geojson-credit">Source credit or license, if required</label><input id="geojson-credit" class="import-credit-input" type="text" maxlength="500" placeholder="Enter attribution for this GeoJSON" /><label class="slider-label" for="opacity"><span>Layer opacity</span><output id="opacity-value">100%</output></label><input id="opacity" type="range" min="0" max="100" value="100" />
          <div id="point-display" class="point-display" hidden><div class="tool-label">IMPORTED POINTS</div><div class="point-modes" role="group" aria-label="Point renderer"><button id="points-maplibre" class="selected" aria-pressed="true">MapLibre</button><button id="points-deck" aria-pressed="false">deck.gl</button></div>
            <p id="point-status" class="point-status" role="status"></p><div id="deck-style" hidden><label class="point-color-label" for="deck-color">Point color <input id="deck-color" type="color" value="#ffc18d" /></label>
              <label class="slider-label" for="deck-radius"><span>Radius · screen pixels</span><output id="deck-radius-value">5 px</output></label><input id="deck-radius" type="range" min="1" max="20" value="5" />
              <label class="slider-label" for="deck-opacity"><span>Point opacity</span><output id="deck-opacity-value">85%</output></label><input id="deck-opacity" type="range" min="10" max="100" value="85" />
              <div class="point-legend"><i id="point-legend-symbol"></i><span id="point-legend-text">Imported point · 5 px radius · 85% opacity</span></div>
              <p class="hint">Screen overlay at geographic coordinates. These symbols are not draped over terrain and may appear above ridges.</p></div></div>
        </div>
      </section>
      <section class="section tiff-section"><div class="section-heading"><h2>GeoTIFF raster</h2><span>RAW VALUES</span></div>
        <p class="section-copy">Read a local GeoTIFF or hosted COG. Inspect its georeferencing before displaying one band.</p>
        <div class="tiff-inspection"><strong>Nussear et al. (${nussearStudy.publicationYear}) habitat model</strong>
          <p>Published binned habitat potential · model prediction, not observations or a study boundary. Display colors use a fixed 0–1 legend.</p>
          <button id="nussear-load" class="import-button">Explore published habitat model</button>
          <button id="nussear-distance" class="import-button">Inspect example cell distance</button>
          <p>The distance is a headless result between two selected model cell centers; it does not measure habitat connectivity.</p>
          <p><a href="https://doi.org/${nussearStudy.doi}" target="_blank" rel="noopener">Study</a> · <a href="${nussearStudy.datasets.find(item => item.id === 'habitat-model')!.sourceUrl}" target="_blank" rel="noopener">Original USGS ZIP</a></p>
        </div>
        <input id="tiff-file" type="file" accept=".tif,.tiff,image/tiff" hidden />
        <button id="tiff-local" class="import-button">＋ &nbsp; Choose local GeoTIFF</button>
        <label class="analysis-label" for="tiff-url">Remote COG URL</label><input id="tiff-url" type="url" placeholder="https://example.org/image.tif" spellcheck="false" autocomplete="off" />
        <button id="tiff-remote" class="import-button">Read remote metadata</button>
        <p id="tiff-status" class="tiff-status" role="status" aria-live="polite"></p>
        <div id="tiff-inspection" class="tiff-inspection" hidden>
          <strong id="tiff-name"></strong><small id="tiff-details"></small><p id="tiff-bounds"></p><p id="tiff-resolution"></p><p id="tiff-nodata"></p>
          <label class="analysis-label" for="tiff-band">Display band</label><select id="tiff-band"></select>
          <div class="tiff-range"><label for="tiff-min">Display min<input id="tiff-min" type="number" step="any" placeholder="Auto from sampled pixels" /></label><label for="tiff-max">Display max<input id="tiff-max" type="number" step="any" placeholder="Auto from sampled pixels" /></label></div>
          <label class="analysis-label" for="tiff-credit">Source credit, if required</label><input id="tiff-credit" type="text" maxlength="500" placeholder="Optional attribution" />
          <button id="tiff-render" class="analysis-run">Display selected band</button>
          <p class="tiff-note">Nearest-neighbor sampling preserves source values. Only the selected band is decoded.</p>
        </div>
        <div id="tiff-layer" class="tiff-layer" hidden><div class="tiff-layer-top"><strong id="tiff-layer-title"></strong><button id="tiff-remove" aria-label="Remove GeoTIFF overlay" title="Remove GeoTIFF overlay">×</button></div>
          <small id="tiff-layer-detail"></small><label class="pmtiles-visibility"><input id="tiff-visible" type="checkbox" checked /> Visible</label>
          <small id="tiff-study-detail" hidden></small>
          <label class="slider-label" for="tiff-opacity"><span>Opacity</span><output id="tiff-opacity-value">80%</output></label><input id="tiff-opacity" type="range" min="0" max="100" value="80" />
          <div class="tiff-legend"><span id="tiff-legend-title">Raw band values</span><div id="tiff-legend-ramp"></div><div class="tiff-legend-values"><span id="tiff-legend-min"></span><span id="tiff-legend-max"></span></div><small>NoData is transparent · color is a display choice, not a physical interpretation.</small></div>
        </div>
      </section>
      <section class="section pmtiles-section"><div class="section-heading"><h2>Hosted tiles</h2><span>PMTILES</span></div>
        <p class="section-copy">Add a public or signed PMTiles archive by URL. Only needed byte ranges are fetched.</p>
        <label class="analysis-label" for="pmtiles-url">Archive URL</label>
        <input id="pmtiles-url" type="url" placeholder="https://example.org/map.pmtiles" spellcheck="false" autocomplete="off" />
        <button id="pmtiles-inspect" class="import-button">Inspect archive</button>
        <p id="pmtiles-status" class="pmtiles-status" role="status" aria-live="polite"></p>
        <div id="pmtiles-inspection" class="pmtiles-inspection" hidden>
          <strong id="pmtiles-name"></strong><small id="pmtiles-details"></small><p id="pmtiles-description"></p>
          <div id="pmtiles-sources-wrap" hidden><label class="analysis-label" for="pmtiles-source-layer">Vector source layer</label><select id="pmtiles-source-layer"></select></div>
          <div id="pmtiles-manual-wrap" hidden><label class="analysis-label" for="pmtiles-manual-layer">Source layer ID</label><input id="pmtiles-manual-layer" type="text" placeholder="Exact ID from the archive" autocomplete="off" /><p class="pmtiles-note">No source layers were listed in metadata. Enter the exact ID used by the vector tiles.</p></div>
          <div id="pmtiles-size-wrap" hidden><label class="analysis-label" for="pmtiles-tile-size">Raster tile size</label><select id="pmtiles-tile-size"><option value="256">256 px</option><option value="512">512 px</option></select></div>
          <p id="pmtiles-required-credit" class="pmtiles-note"></p>
          <label class="analysis-label" for="pmtiles-extra-credit">Attribution <span id="pmtiles-credit-qualifier"></span></label><input id="pmtiles-extra-credit" type="text" maxlength="500" placeholder="Credit or license, if missing above" />
          <button id="pmtiles-add" class="analysis-run">Add to map</button>
        </div>
        <div id="pmtiles-layers" class="pmtiles-layers"></div>
        <p class="pmtiles-note">Hosts must allow CORS and HTTP Range requests. Scene export includes each full URL, including any query token.</p>
      </section>
      <section class="section inspect-section"><div class="section-heading"><h2>Inspect features</h2><span>VECTOR DATA</span></div>
        <p class="section-copy">Tap a visible feature to read its source and properties. Map navigation stays available.</p>
        <button id="inspect-toggle" class="action-button inspect-toggle" aria-pressed="false"><span class="action-symbol">⌕</span><span>Inspect map</span><span id="inspect-state" class="action-state">START</span></button>
        <p class="hint">Drawing and inspection use separate interaction modes.</p>
      </section>
      <section class="section draw-section"><div class="section-heading"><h2>Draw &amp; edit</h2><span id="draw-status">ON DEMAND</span></div>
        <p class="section-copy">Sketch new features over the terrain. Your drawings stay in this browser session.</p>
        <div class="tool-label">DRAW SHAPES</div><div id="draw-tools" class="tool-grid" role="group" aria-label="Drawing tools"></div>
        <div class="tool-label edit-label">EDIT DRAWINGS</div><div id="edit-tools" class="tool-grid" role="group" aria-label="Editing tools"></div>
        <p id="draw-count" class="draw-count">0 drawn features</p>
        <div class="data-actions"><button id="clear-drawings">Clear drawings</button><button id="export-drawings">Export GeoJSON</button></div>
        <button id="export" class="scene-export">Export complete scene ↗</button>
      </section>
      <section class="section analysis-section"><div class="section-heading"><h2>Spatial analysis</h2><span>COMPUTED</span></div>
        <p class="section-copy">Measure drawn or imported geometry. Calculations use WGS84 coordinates and represent horizontal distance or area, not 3D terrain surface.</p>
        <label class="analysis-label" for="analysis-operation">Operation</label>
        <select id="analysis-operation"><option value="length">Line length</option><option value="area">Polygon area</option><option value="distance">Point-to-point distance</option><option value="buffer">Buffer</option></select>
        <label class="analysis-label" for="analysis-first">Source feature</label><select id="analysis-first"></select>
        <div id="analysis-second-wrap" hidden><label class="analysis-label" for="analysis-second">Second point</label><select id="analysis-second"></select></div>
        <div id="analysis-radius-wrap" hidden><label class="analysis-label" for="analysis-radius">Buffer radius · meters</label><input id="analysis-radius" type="number" min="0.1" max="50000" step="any" value="1000" inputmode="decimal" /></div>
        <p id="analysis-help" class="analysis-help"></p><button id="analysis-run" class="analysis-run">Compute result</button>
        <div class="analysis-results-heading"><span><i></i> COMPUTED GEOMETRY</span><button id="analysis-export" disabled>Export results ↗</button></div>
        <div id="analysis-results" class="analysis-results"><p class="analysis-empty">No results yet.</p></div>
      </section>
      <div class="credits"><strong>REAL GEOGRAPHY</strong><p>MapLibre · OpenFreeMap · EOxCloudless Sentinel mosaic · Mapterhorn DEM. Imagery and elevation are separate visual sources. Scene presets are camera positions, not study data.</p></div>
    </div>
  </aside>
  <div class="map-hint">DRAG TO PAN <span>·</span> RIGHT DRAG TO ROTATE &amp; TILT <span>·</span> SCROLL TO ZOOM</div>
  <div id="import-credit-display" class="import-credit-display" hidden></div>
  <div id="camera-readout" class="camera-readout" aria-live="off"></div>
  <div id="active-tool" class="active-tool" hidden><span class="active-tool-icon">✎</span><span class="active-tool-text"><strong id="active-tool-label"></strong><small id="active-tool-hint"></small></span><button id="stop-tool">Done</button></div>
  <button id="mobile-toggle" class="mobile-toggle" aria-expanded="false" aria-controls="workspace">CONTROLS <span>⌃</span></button>
  <div id="toast" class="toast" role="status" aria-live="polite"></div>
`;

const $ = <T extends HTMLElement>(selector: string): T => app.querySelector<T>(selector)!;
const status = $('#status');
const toast = $('#toast');
let toastTimer = 0;
function announce(message: string): void {
  toast.textContent = message;
  toast.classList.add('show');
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove('show'), 4200);
}
function updateCamera(camera: Camera): void {
  $('#camera-readout').innerHTML = `<span>LAT ${camera.center[1].toFixed(4)}°</span><span>LON ${camera.center[0].toFixed(4)}°</span><span>ZOOM ${camera.zoom.toFixed(1)}</span><span>BEARING ${Math.round((camera.bearing + 360) % 360)}°</span>`;
  const pitch = $<HTMLInputElement>('#pitch');
  pitch.value = String(Math.round(camera.pitch));
  $('#pitch-value').textContent = `${Math.round(camera.pitch)}°`;
}
const lab = new SandboxMap($('#map'), {
  status: event => { status.textContent = event.message; status.parentElement?.classList.toggle('warning', event.level === 'warning'); syncBasemap(); },
  camera: updateCamera,
  orbit: active => { $('#orbit').setAttribute('aria-pressed', String(active)); $('#orbit').classList.toggle('active', active); $('#orbit-state').textContent = active ? 'STOP' : 'START'; },
  pmtilesError: (id, message) => showPmtilesError(id, message),
});

const drawing = new DrawingWorkspace(lab.map, syncDrawing);
const analysisResults: AnalysisResult[] = [];
let deckPoints: DeckPoints | null = null;
let pointMode: 'maplibre' | 'deck' = 'maplibre';
let importedPointCount = 0;
let inspectionActive = false;
const inspectionPopup = new Popup({ closeButton: true, closeOnClick: false, maxWidth: '340px', className: 'terrain-inspect-popup' });
function renderFeatureProperties(features: GeoJSONFeatureWithSourceLayer[]): HTMLElement {
  const content = document.createElement('div');
  content.className = 'inspect-popup-content';
  const seen = new Set<string>();
  const unique = features.filter(feature => {
    const signature = JSON.stringify([feature.source, feature.layer['source-layer'], feature.id, feature.geometry, feature.properties]);
    if (seen.has(signature)) return false;
    seen.add(signature);
    return true;
  });
  const heading = document.createElement('strong');
  heading.textContent = `${unique.length} visible ${unique.length === 1 ? 'feature' : 'features'}`;
  content.append(heading);
  const sorted = unique.sort((a, b) => Number(b.source.startsWith('lab-')) - Number(a.source.startsWith('lab-')));
  sorted.slice(0, 8).forEach((feature, index) => {
    const item = document.createElement('details');
    item.className = 'inspect-feature';
    item.open = index === 0;
    const title = document.createElement('summary');
    const source = feature.source.startsWith('lab-pmtiles-') ? 'PMTiles' : feature.source === 'lab-import' ? 'Imported GeoJSON' : feature.source === 'lab-derived' ? 'Computed geometry' : feature.source;
    title.textContent = `${source} · ${feature.layer['source-layer'] ?? feature.layer.id}`;
    item.append(title);
    const meta = document.createElement('p');
    meta.textContent = `${feature.geometry.type} · source ${feature.source}${feature.layer['source-layer'] ? ` · layer ${feature.layer['source-layer']}` : ''}`;
    item.append(meta);
    const properties = Object.entries(feature.properties ?? {});
    if (properties.length) {
      const table = document.createElement('dl');
      for (const [key, value] of properties.slice(0, 80)) {
        const label = document.createElement('dt'); label.textContent = key;
        const data = document.createElement('dd'); data.textContent = value == null ? 'null' : String(value);
        table.append(label, data);
      }
      item.append(table);
      if (properties.length > 80) {
        const more = document.createElement('p'); more.textContent = `${properties.length - 80} more properties omitted.`; item.append(more);
      }
    } else {
      const empty = document.createElement('p'); empty.textContent = 'No properties on this feature.'; item.append(empty);
    }
    content.append(item);
  });
  if (sorted.length > 8) {
    const more = document.createElement('p'); more.textContent = `${sorted.length - 8} more overlapping features. Zoom in to narrow the selection.`; content.append(more);
  }
  return content;
}
let inspector: MaplibreInspect | null = null;
function syncInspection(): void {
  const button = $<HTMLButtonElement>('#inspect-toggle');
  button.classList.toggle('active', inspectionActive);
  button.setAttribute('aria-pressed', String(inspectionActive));
  app.classList.toggle('inspection-active', inspectionActive);
  $('#inspect-state').textContent = inspectionActive ? 'STOP' : 'START';
  syncDrawing();
}
function stopInspection(): void {
  if (!inspectionActive) return;
  inspectionActive = false;
  inspectionPopup.remove();
  if (inspector) lab.map.removeControl(inspector);
  lab.map.getCanvas().style.cursor = '';
  syncInspection();
}
$('#draw-tools').innerHTML = drawTools.map(tool => `<button class="tool-button" data-draw="${tool.id}" aria-pressed="false" title="${tool.hint}">${tool.label}</button>`).join('');
$('#edit-tools').innerHTML = editTools.map(tool => `<button class="tool-button" data-edit="${tool.id}" aria-pressed="false" title="${tool.hint}">${tool.label}</button>`).join('');
function syncDrawing(): void {
  const active = drawing.activeTool();
  deckPoints?.setInteractive(!active && !inspectionActive);
  const count = drawing.data().features.length;
  $('#draw-count').textContent = `${count.toLocaleString()} drawn ${count === 1 ? 'feature' : 'features'}`;
  app.querySelectorAll<HTMLButtonElement>('[data-draw], [data-edit]').forEach(button => {
    const selected = !!active && button.dataset[active.kind] === active.id;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
    button.disabled = toolBusy;
  });
  const indicator = $('#active-tool');
  indicator.hidden = !active && !inspectionActive;
  if (inspectionActive) {
    $('#active-tool-label').textContent = 'Inspect · visible features';
    $('#active-tool-hint').textContent = 'Tap a feature to read its properties. Drag and zoom still work.';
  } else if (active) {
    const tool = active.kind === 'draw' ? drawTools.find(item => item.id === active.id) : editTools.find(item => item.id === active.id);
    $('#active-tool-label').textContent = `${active.kind === 'draw' ? 'Drawing' : 'Editing'} · ${tool?.label ?? active.id}`;
    $('#active-tool-hint').textContent = tool?.hint ?? 'Use the map to edit the feature';
  }
  refreshAnalysis();
}
let toolBusy = false;
async function selectTool(tool: ActiveTool): Promise<void> {
  if (toolBusy) return;
  toolBusy = true;
  try {
    lab.stopOrbit();
    if (tool) stopInspection();
    if (tool && !drawing.isReady()) $('#draw-status').textContent = 'LOADING';
    await drawing.select(tool);
    if (drawing.isReady()) $('#draw-status').textContent = 'READY';
    if (drawing.activeTool()) closeMobile();
  } catch (error) { $('#draw-status').textContent = 'UNAVAILABLE'; announce(error instanceof Error ? error.message : 'Could not start this tool'); }
  finally { toolBusy = false; syncDrawing(); }
}
app.querySelectorAll<HTMLButtonElement>('[data-draw]').forEach(button => button.addEventListener('click', () => {
  void selectTool({ kind: 'draw', id: button.dataset.draw as DrawModeName });
}));
app.querySelectorAll<HTMLButtonElement>('[data-edit]').forEach(button => button.addEventListener('click', () => {
  void selectTool({ kind: 'edit', id: button.dataset.edit as EditModeName });
}));
$('#stop-tool').addEventListener('click', () => { if (inspectionActive) stopInspection(); else void selectTool(null); });
$('#inspect-toggle').addEventListener('click', async () => {
  if (toolBusy) return;
  if (inspectionActive) { stopInspection(); return; }
  toolBusy = true;
  try {
    lab.stopOrbit();
    await drawing.stop();
    if (!inspector) {
      const { default: MaplibreInspect } = await import('@maplibre/maplibre-gl-inspect');
      inspector = new MaplibreInspect({
        popup: inspectionPopup, showInspectButton: false, showMapPopup: true,
        showMapPopupOnHover: false, showInspectMapPopupOnHover: false,
        useInspectStyle: false, selectThreshold: 6,
        sources: { 'lab-import': [] },
        renderPopup: renderFeatureProperties,
      });
    }
    lab.map.addControl(inspector, 'top-right');
    inspectionActive = true;
    closeMobile();
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not start inspection'); }
  finally { toolBusy = false; syncInspection(); }
});

function syncBasemap(): void {
  app.querySelectorAll<HTMLButtonElement>('[data-base]').forEach(button => {
    const active = button.dataset.base === lab.getBasemap();
    button.classList.toggle('selected', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

$('#presets').innerHTML = presets.map((preset, i) => `<button class="preset" data-preset="${preset.id}"><span class="preset-number">0${i + 1}</span><span class="preset-text"><strong>${preset.name}</strong><small>${preset.subtitle}</small></span><span class="preset-arrow">↗</span></button>`).join('');
app.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach(button => button.addEventListener('click', () => {
  const preset = presets.find(item => item.id === button.dataset.preset);
  if (preset) { void drawing.stop(); lab.goTo(preset); announce(`Flying to ${preset.name}`); closeMobile(); }
}));
app.querySelectorAll<HTMLButtonElement>('[data-base]').forEach(button => button.addEventListener('click', () => {
  lab.setBasemap(button.dataset.base as Basemap); syncBasemap();
}));

$<HTMLInputElement>('#pitch').addEventListener('input', event => {
  const value = Number((event.target as HTMLInputElement).value);
  $('#pitch-value').textContent = `${value}°`;
  lab.setPitch(value);
});
$<HTMLInputElement>('#terrain').addEventListener('input', event => {
  const value = Number((event.target as HTMLInputElement).value);
  $('#terrain-value').textContent = `${value.toFixed(1)}×`;
  lab.setTerrainScale(value);
});
$('#orbit').addEventListener('click', () => lab.isOrbiting() ? lab.stopOrbit() : lab.startOrbit());

const fileInput = $<HTMLInputElement>('#file');
let importedProvenance: { kind: 'local GeoJSON' | 'research model cells' | 'research solar arrays' | 'research solar array analysis' | 'research plant cells' | 'research plant cell analysis'; fileName: string; bytes: number; lastModified: string | null; crs: 'WGS84 longitude/latitude'; featureCount: number; coordinateCount: number; attribution: string; studyId?: string; datasetId?: string; sourceUrl?: string; analysisUrl?: string; originalArchivePath?: string; sourceSha256?: string; preparedSha256?: string; conversion?: string; limitations?: string[] } | null = null;
function syncImportedCredit(): void {
  const credit = $<HTMLInputElement>('#geojson-credit');
  credit.readOnly = importedProvenance?.kind === 'research solar arrays' || importedProvenance?.kind === 'research solar array analysis' || importedProvenance?.kind === 'research plant cells' || importedProvenance?.kind === 'research plant cell analysis';
  if (importedProvenance && !credit.readOnly) importedProvenance.attribution = credit.value.trim();
  const badge = $('#import-credit-display');
  badge.hidden = !importedProvenance;
  badge.textContent = importedProvenance ? `${importedProvenance.kind === 'research model cells' ? 'Research model cells' : importedProvenance.kind === 'research solar arrays' ? 'Research solar arrays' : importedProvenance.kind === 'research solar array analysis' ? 'Research array analysis' : importedProvenance.kind === 'research plant cells' ? 'Research plant cells' : importedProvenance.kind === 'research plant cell analysis' ? 'Research plant cell analysis' : 'Imported GeoJSON'} · ${importedProvenance.fileName}${importedProvenance.attribution ? ` · ${importedProvenance.attribution}` : ' · credit not supplied'}` : '';
  const limitations = $('#layer-limitations');
  limitations.hidden = importedProvenance?.kind !== 'research solar arrays' && importedProvenance?.kind !== 'research solar array analysis' && importedProvenance?.kind !== 'research plant cells' && importedProvenance?.kind !== 'research plant cell analysis';
  limitations.textContent = !limitations.hidden
    ? `Limitations: ${importedProvenance?.limitations?.slice(0, 3).join(' ') ?? ''}` : '';
}
$<HTMLInputElement>('#geojson-credit').addEventListener('input', syncImportedCredit);
const pointPopup = new Popup({ closeButton: true, maxWidth: '300px', className: 'terrain-inspect-popup' });
const pointStyle: PointStyle = { color: '#ffc18d', radius: 5, opacity: 0.85 };
function pickedPoint(point: PointDatum): void {
  if (inspectionActive || drawing.activeTool()) return;
  const content = document.createElement('div'); content.className = 'inspect-popup-content';
  const title = document.createElement('strong'); title.textContent = `Imported point · feature ${point.featureIndex + 1}`;
  const coords = document.createElement('p'); coords.textContent = `${point.position[1].toFixed(5)}° N, ${point.position[0].toFixed(5)}° E`;
  content.append(title, coords);
  const entries = Object.entries(point.properties);
  if (entries.length) {
    const table = document.createElement('dl');
    for (const [key, value] of entries.slice(0, 30)) {
      const label = document.createElement('dt'); label.textContent = key;
      const data = document.createElement('dd'); data.textContent = value == null ? 'null' : typeof value === 'object' ? JSON.stringify(value).slice(0, 200) : String(value).slice(0, 200);
      table.append(label, data);
    }
    content.append(table);
  }
  pointPopup.setLngLat(point.position).setDOMContent(content).addTo(lab.map);
}
function syncPointControls(): void {
  for (const mode of ['maplibre', 'deck'] as const) {
    const button = $<HTMLButtonElement>(`#points-${mode}`);
    button.classList.toggle('selected', pointMode === mode);
    button.setAttribute('aria-pressed', String(pointMode === mode));
  }
  $('#deck-style').hidden = pointMode !== 'deck';
  $('#point-display').hidden = importedPointCount === 0;
  $('#point-legend-symbol').setAttribute('style', `width:${Math.max(8, pointStyle.radius * 2)}px;height:${Math.max(8, pointStyle.radius * 2)}px;background:${pointStyle.color};opacity:${pointStyle.opacity}`);
  $('#point-legend-text').textContent = `Imported point · ${pointStyle.radius} px radius · ${Math.round(pointStyle.opacity * 100)}% opacity`;
}
let pointModeToken = 0;
async function setPointMode(mode: 'maplibre' | 'deck'): Promise<void> {
  const token = ++pointModeToken;
  if (mode === 'deck') {
    if (!importedPointCount) return;
    $('#point-status').textContent = 'Loading deck.gl…';
    try {
      const { DeckPoints } = await import('./deckPoints');
      if (token !== pointModeToken) return;
      if (!deckPoints) deckPoints = new DeckPoints(lab.map, pickedPoint, message => {
        void setPointMode('maplibre');
        $('#point-status').textContent = `deck.gl unavailable: ${message}. MapLibre points shown.`;
      });
      deckPoints.setData(lab.getImported());
      deckPoints.setStyle(pointStyle);
      deckPoints.setInteractive(!drawing.activeTool() && !inspectionActive);
      deckPoints.enable();
      if (token !== pointModeToken) { deckPoints.disable(); return; }
      pointMode = 'deck';
      lab.setImportedPointMode('deck');
      $('#point-status').textContent = `${importedPointCount.toLocaleString()} points · deck.gl screen overlay`;
    } catch (error) {
      deckPoints?.disable();
      pointMode = 'maplibre'; lab.setImportedPointMode('maplibre');
      $('#point-status').textContent = error instanceof Error ? error.message : 'deck.gl unavailable; MapLibre points shown.';
    }
  } else {
    deckPoints?.disable(); pointPopup.remove();
    pointMode = 'maplibre'; lab.setImportedPointMode('maplibre');
    $('#point-status').textContent = `${importedPointCount.toLocaleString()} points · MapLibre circles`;
  }
  syncPointControls();
}
$('#points-maplibre').addEventListener('click', () => { void setPointMode('maplibre'); });
$('#points-deck').addEventListener('click', () => { void setPointMode('deck'); });
for (const id of ['deck-color', 'deck-radius', 'deck-opacity']) {
  $<HTMLInputElement>(`#${id}`).addEventListener('input', () => {
    pointStyle.color = $<HTMLInputElement>('#deck-color').value;
    pointStyle.radius = Number($<HTMLInputElement>('#deck-radius').value);
    pointStyle.opacity = Number($<HTMLInputElement>('#deck-opacity').value) / 100;
    $('#deck-radius-value').textContent = `${pointStyle.radius} px`;
    $('#deck-opacity-value').textContent = `${Math.round(pointStyle.opacity * 100)}%`;
    deckPoints?.setStyle(pointStyle); syncPointControls();
  });
}
$('#import').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', async () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  try {
    if (file.size > 20_000_000) throw new Error('GeoJSON files must be under 20 MB. Split the collection before importing.');
    const inspection = inspectGeoJson(JSON.parse(await file.text()) as unknown);
    if (file.size > 3_000_000 && inspection.pointCount !== inspection.coordinateCount)
      throw new Error('Files over 3 MB must contain points only. Simplify mixed geometry before importing.');
    if (!inspection.coordinateCount) throw new Error('This GeoJSON contains no mappable coordinates.');
    ++pointModeToken;
    pointPopup.remove(); inspectionPopup.remove();
    importedPointCount = inspection.pointCount;
    importedProvenance = { kind: 'local GeoJSON', fileName: file.name, bytes: file.size,
      lastModified: Number.isFinite(file.lastModified) && file.lastModified > 0 ? new Date(file.lastModified).toISOString() : null,
      crs: 'WGS84 longitude/latitude', featureCount: inspection.featureCount,
      coordinateCount: inspection.coordinateCount, attribution: '' };
    $<HTMLInputElement>('#geojson-credit').value = '';
    $('#layer-origin').textContent = `Local source · ${file.size < 1_000_000 ? `${Math.max(1, Math.round(file.size / 1_000))} KB` : `${(file.size / 1_000_000).toFixed(2)} MB`} · WGS84`;
    syncImportedCredit();
    lab.setImportedPolygonStyle('default');
    lab.setImported(inspection.data);
    deckPoints?.setData(inspection.data);
    if (!importedPointCount) { pointMode = 'maplibre'; deckPoints?.disable(); lab.setImportedPointMode('maplibre'); }
    syncPointControls();
    refreshAnalysis();
    $('#layer-name').textContent = file.name;
    $('#layer-details').textContent = `${inspection.featureCount.toLocaleString()} features · ${inspection.kinds.join(', ')}`;
    $('#layer-card').hidden = false;
    if (inspection.bounds) {
      const [[west, south], [east, north]] = inspection.bounds;
      if (west === east && south === north) lab.goTo({ center: [west, south], zoom: 12, pitch: 55, bearing: 0 });
      else lab.fitBounds(inspection.bounds);
    }
    announce(`Loaded ${file.name}`);
    closeMobile();
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not read the GeoJSON file.'); }
  fileInput.value = '';
});
async function loadJoshuaCells(exampleArea: boolean): Promise<void> {
  try {
    const dataset = esqueStudy.datasets.find(item => item.id === 'hybrid-presence-grid-cells')!;
    const derivedDataset = esqueStudy.datasets.find(item => item.id === 'hybrid-cell-680349-area')!;
    const path = exampleArea ? derivedDataset.localPath! : dataset.localPath!;
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Could not load the Joshua tree data (${response.status}).`);
    const payload = await response.arrayBuffer();
    const inspection = inspectGeoJson(JSON.parse(new TextDecoder().decode(payload)) as unknown);
    const features = inspection.data.features as Array<{ type: string; id?: number; geometry: { type: string }; properties: Record<string, unknown> }>;
    const source = exampleArea ? features[0] : null;
    const area = exampleArea ? features[1] : null;
    if (exampleArea ? inspection.featureCount !== 2 || source?.id !== 680349 || source.geometry?.type !== 'Polygon' ||
        source.properties?.ID !== 680349 || source.properties?.terrainLabStudyId !== esqueStudy.id ||
        source.properties?.terrainLabDatasetId !== dataset.id || area?.geometry?.type !== 'Polygon' ||
        area.properties?.classification !== 'computed geometry' || area.properties?.observed !== false ||
        area.properties?.operation !== 'area' || area.properties?.unit !== 'square meters' ||
        area.properties?.studyId !== esqueStudy.id || area.properties?.datasetId !== dataset.id ||
        area.properties?.sourceFeatureId !== 680349 || area.properties?.sourceVerification !== 'registered-dataset' ||
        JSON.stringify(source.geometry) !== JSON.stringify(area.geometry) :
        inspection.featureCount !== 941 || inspection.kinds.some(kind => kind !== 'Polygon') ||
        features.some(feature => feature.properties?.terrainLabStudyId !== esqueStudy.id ||
          feature.properties?.terrainLabDatasetId !== dataset.id || feature.properties?.terrainLabRole !== 'observed-geography' ||
          feature.properties?.Final_Stat !== 'P' || feature.properties?.State !== 'NV'))
      throw new Error('The bundled Joshua tree layer has an unexpected structure.');
    const value = exampleArea ? Number(area!.properties.value) : null;
    if (exampleArea && (!Number.isFinite(value) || value! <= 0)) throw new Error('The grid-cell area is invalid.');
    ++pointModeToken;
    pointPopup.remove(); inspectionPopup.remove(); deckPoints?.disable(); importedPointCount = 0;
    pointMode = 'maplibre'; lab.setImportedPointMode('maplibre');
    analysisResults.length = 0;
    lab.setDerived(resultsGeoJson(analysisResults)); renderResults();
    importedProvenance = {
      kind: exampleArea ? 'research plant cell analysis' : 'research plant cells',
      fileName: exampleArea ? 'USGS hybrid-presence cell 680349 and derived area' : 'USGS hybrid-presence grid cells',
      bytes: payload.byteLength, lastModified: null, crs: 'WGS84 longitude/latitude',
      featureCount: exampleArea ? 1 : inspection.featureCount,
      coordinateCount: exampleArea ? inspectGeoJson({ type: 'FeatureCollection', features: [source] }).coordinateCount : inspection.coordinateCount,
      attribution: 'USGS, Distribution Data and Habitat Models for Joshua Trees (2025), DOI 10.5066/P9NZMDLL; CC0 1.0',
      studyId: esqueStudy.id, datasetId: dataset.id, sourceUrl: dataset.sourceUrl,
      analysisUrl: exampleArea ? derivedDataset.localPath : undefined,
      sourceSha256: 'a42b0349759cac0a3c68762dd531807efa2416708f8a04de9fdbe1efc811a0f7',
      preparedSha256: '96e23e42f471fb3d7f6cb90de798ebb426b9a16c8246a6c93e5e330feb715166',
      conversion: 'USGS NAD83 Albers shapefile transformed to WGS84 GeoJSON without simplifying geometry; source Z values omitted.',
      limitations: exampleArea ? derivedDataset.limitations : dataset.limitations,
    };
    $<HTMLInputElement>('#geojson-credit').value = importedProvenance.attribution;
    $('#layer-origin').textContent = `Esque et al. (2023) · USGS 2025 release · ${dataset.id}${exampleArea ? ` → ${derivedDataset.id}` : ''}`;
    syncImportedCredit();
    lab.setImportedPolygonStyle(exampleArea ? 'default' : 'grid');
    lab.setImported({ type: 'FeatureCollection', features: exampleArea ? [source!] : features });
    syncPointControls(); refreshAnalysis();
    $('#layer-name').textContent = exampleArea ? 'Mapped presence cell 680349' : 'Joshua tree hybrid-presence grid cells';
    $('#layer-details').textContent = exampleArea ? '1 observed grid cell · derived area shown separately' : '941 mapped presence cells · not individual trees';
    $('#layer-card').hidden = false;
    if (exampleArea) {
      const result: AnalysisResult = { id: crypto.randomUUID(), title: 'Polygon area',
        valueLabel: `${value!.toFixed(1)} m²`, sourceLabel: 'USGS mapped presence cell 680349',
        feature: area as unknown as AnalysisResult['feature'] };
      analysisResults.push(result);
      lab.setDerived(resultsGeoJson(analysisResults)); renderResults();
    }
    if (inspection.bounds) lab.fitBounds(inspection.bounds);
    announce(exampleArea ? `Loaded one USGS grid cell and headless area: ${value!.toFixed(1)} m²` : 'Loaded 941 USGS mapped presence cells. Turn on Inspect map to read attributes.');
    closeMobile();
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not load Joshua tree data.'); }
}
$('#esque-load').addEventListener('click', () => { void loadJoshuaCells(false); });
$('#esque-area').addEventListener('click', () => { void loadJoshuaCells(true); });
$('#fleckenstein-load').addEventListener('click', async () => {
  try {
    const dataset = fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states')!;
    const response = await fetch(dataset.localPath!);
    if (!response.ok) throw new Error(`Could not load the solar-array data (${response.status}).`);
    const payload = await response.arrayBuffer();
    const inspection = inspectGeoJson(JSON.parse(new TextDecoder().decode(payload)) as unknown);
    if (inspection.featureCount !== 872 || inspection.kinds.some(kind => kind !== 'Polygon' && kind !== 'MultiPolygon') ||
      inspection.data.features.some(feature => {
        const properties = feature.properties as Record<string, unknown> | null;
        return properties?.terrainLabStudyId !== fleckensteinStudy.id || properties?.terrainLabDatasetId !== dataset.id ||
          !['AZ', 'CA', 'CO', 'NM', 'NV', 'TX', 'UT'].includes(String(properties?.p_state));
      }))
      throw new Error('The bundled solar-array layer has an unexpected structure.');
    ++pointModeToken;
    pointPopup.remove(); inspectionPopup.remove(); deckPoints?.disable(); importedPointCount = 0;
    pointMode = 'maplibre'; lab.setImportedPointMode('maplibre');
    importedProvenance = {
      kind: 'research solar arrays', fileName: 'USPVDB v1.0 solar arrays', bytes: payload.byteLength, lastModified: null,
      crs: 'WGS84 longitude/latitude', featureCount: inspection.featureCount,
      coordinateCount: inspection.coordinateCount,
      attribution: 'USGS and Lawrence Berkeley National Laboratory, USPVDB v1.0 (2023), DOI 10.5066/P9IA3TUS',
      studyId: fleckensteinStudy.id, datasetId: dataset.id, sourceUrl: dataset.sourceUrl,
      originalArchivePath: '/data/fleckenstein-2025/uspvdb_v1_0_20231108.zip',
      sourceSha256: '8012ef258219fba003de7470a7eaac2cf426ce8131d5810469afc419d033dec4',
      preparedSha256: '9c9b42452c30bc745be799396f0a97ad9c35e99ee4d6ac8ff6a08124fa3fd543',
      conversion: 'Original USPVDB Albers/NAD83 shapefile filtered by p_state and transformed to WGS84 GeoJSON; geometry not simplified.',
      limitations: dataset.limitations,
    };
    $<HTMLInputElement>('#geojson-credit').value = importedProvenance.attribution;
    $('#layer-origin').textContent = `Fleckenstein et al. (2025) · dataset ${dataset.id} · USGS solar arrays · WGS84 display conversion`;
    syncImportedCredit(); lab.setImportedPolygonStyle('default'); lab.setImported(inspection.data); syncPointControls(); refreshAnalysis();
    $('#layer-name').textContent = 'USPVDB solar arrays · seven study states';
    $('#layer-details').textContent = `${inspection.featureCount} solar-array polygons · not tortoise locations or model output`;
    $('#layer-card').hidden = false;
    if (inspection.bounds) lab.fitBounds(inspection.bounds);
    announce('Loaded USGS solar-array polygons. Turn on Inspect map to read source attributes.');
    closeMobile();
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not load the solar-array data.'); }
});
$('#fleckenstein-area').addEventListener('click', async () => {
  try {
    const dataset = fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states')!;
    const derivedDataset = fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-case-400038-area')!;
    const response = await fetch(derivedDataset.localPath!);
    if (!response.ok) throw new Error(`Could not load the research area result (${response.status}).`);
    const payload = await response.arrayBuffer();
    const inspection = inspectGeoJson(JSON.parse(new TextDecoder().decode(payload)) as unknown);
    const [source, area] = inspection.data.features as Array<{ type: string; geometry: { type: string }; properties: Record<string, unknown> }>;
    if (inspection.featureCount !== 2 || source?.geometry?.type !== 'Polygon' || area?.geometry?.type !== 'Polygon' ||
      source.properties?.case_id !== 400038 || source.properties?.terrainLabStudyId !== fleckensteinStudy.id ||
      source.properties?.terrainLabDatasetId !== dataset.id || area.properties?.classification !== 'computed geometry' ||
      area.properties?.observed !== false || area.properties?.operation !== 'area' || area.properties?.unit !== 'square meters' ||
      area.properties?.studyId !== fleckensteinStudy.id || area.properties?.datasetId !== dataset.id ||
      area.properties?.sourceFeatureId !== 400038 || area.properties?.sourceVerification !== 'registered-dataset' ||
      JSON.stringify(source.geometry) !== JSON.stringify(area.geometry))
      throw new Error('The bundled research area result has an unexpected structure.');
    const value = Number(area.properties?.value);
    if (!Number.isFinite(value) || value <= 0) throw new Error('The research area is invalid.');
    ++pointModeToken;
    pointPopup.remove(); inspectionPopup.remove(); deckPoints?.disable(); importedPointCount = 0;
    pointMode = 'maplibre'; lab.setImportedPointMode('maplibre');
    importedProvenance = {
      kind: 'research solar array analysis', fileName: 'USPVDB case 400038 and derived area', bytes: payload.byteLength,
      lastModified: null, crs: 'WGS84 longitude/latitude', featureCount: 1,
      coordinateCount: inspectGeoJson({ type: 'FeatureCollection', features: [source] }).coordinateCount,
      attribution: 'USGS and Lawrence Berkeley National Laboratory, USPVDB v1.0 (2023), DOI 10.5066/P9IA3TUS',
      studyId: fleckensteinStudy.id, datasetId: dataset.id, sourceUrl: dataset.sourceUrl,
      analysisUrl: derivedDataset.localPath,
      originalArchivePath: '/data/fleckenstein-2025/uspvdb_v1_0_20231108.zip',
      sourceSha256: String(area.properties.sourceArchiveSha256),
      preparedSha256: String(area.properties.preparedGeoJsonSha256),
      conversion: 'Original USPVDB Albers/NAD83 polygon transformed to WGS84 GeoJSON; Turf geodesic area computed from the converted polygon.',
      limitations: derivedDataset.limitations,
    };
    $<HTMLInputElement>('#geojson-credit').value = importedProvenance.attribution;
    $('#layer-origin').textContent = `Fleckenstein et al. (2025) · ${dataset.id} → ${derivedDataset.id} · verified source checksums`;
    syncImportedCredit();
    lab.setImportedPolygonStyle('default');
    lab.setImported({ type: 'FeatureCollection', features: [source] });
    syncPointControls(); refreshAnalysis();
    $('#layer-name').textContent = 'CalRenew-1 · USPVDB case 400038';
    $('#layer-details').textContent = '1 source solar-array polygon · derived area shown separately';
    $('#layer-card').hidden = false;
    const result: AnalysisResult = { id: crypto.randomUUID(), title: 'Polygon area',
      valueLabel: `${value.toFixed(1)} m²`, sourceLabel: String(area.properties?.source ?? 'USPVDB case 400038'),
      feature: area as unknown as AnalysisResult['feature'] };
    const previous = analysisResults.findIndex(item => item.feature.properties?.studyId === fleckensteinStudy.id &&
      item.feature.properties?.sourceFeatureId === 400038 && item.feature.properties?.operation === 'area');
    if (previous !== -1) analysisResults.splice(previous, 1);
    analysisResults.push(result); lab.setDerived(resultsGeoJson(analysisResults)); renderResults();
    if (inspection.bounds) lab.fitBounds(inspection.bounds);
    announce(`Loaded USGS solar-array polygon and headless area: ${result.valueLabel}`);
    closeMobile();
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not load the research area result.'); }
});
$('#clear-layer').addEventListener('click', () => { ++pointModeToken; deckPoints?.disable(); pointPopup.remove(); inspectionPopup.remove(); importedPointCount = 0; importedProvenance = null; syncImportedCredit(); pointMode = 'maplibre'; lab.setImportedPointMode('maplibre'); lab.setImportedPolygonStyle('default'); lab.clearImported(); syncPointControls(); refreshAnalysis(); $('#layer-card').hidden = true; announce('Imported layer removed'); });
$<HTMLInputElement>('#opacity').addEventListener('input', event => {
  const value = Number((event.target as HTMLInputElement).value);
  $('#opacity-value').textContent = `${value}%`;
  lab.setOverlayOpacity(value / 100);
});
let inspectedTiff: TiffSession | null = null;
let decodedTiff: { band: number; data: DecodedBand } | null = null;
let tiffToken = 0;
type TiffStudyReference = { studyId: string; datasetId: string; publicationUrl: string; sourceUrl: string; originalArchivePath: string; displayTilesUrl: string };
let tiffStudy: TiffStudyReference | null = null;
let tiffScene: { metadata: TiffMetadata; study?: TiffStudyReference; processing: { band: number; overview: [number, number]; displayPixels: [number, number]; resampling: string; reprojection: string }; display: { minimum: number; maximum: number; palette: string; opacity: number; visible: boolean; attribution: string } } | null = null;
function setTiffStatus(message: string, error = false): void {
  const target = $('#tiff-status'); target.textContent = message; target.classList.toggle('error', error);
}
function tiffSourceName(metadata: TiffMetadata): string {
  return metadata.source.kind === 'local' ? metadata.source.name : new URL(metadata.source.url).pathname.split('/').pop() || new URL(metadata.source.url).host;
}
function showTiffMetadata(session: TiffSession): void {
  const info = session.metadata;
  inspectedTiff = session; decodedTiff = null;
  $('#tiff-inspection').hidden = false;
  $('#tiff-name').textContent = tiffSourceName(info);
  $('#tiff-details').textContent = `${info.width.toLocaleString()} × ${info.height.toLocaleString()} px · ${info.bands} ${info.bands === 1 ? 'band' : 'bands'} · ${info.crs}`;
  $('#tiff-bounds').textContent = `WGS84 bounds: ${info.boundsWgs84.map(value => value.toFixed(5)).join(', ')} (W, S, E, N)`;
  $('#tiff-resolution').textContent = `Native resolution: ${info.resolution[0].toPrecision(5)} × ${info.resolution[1].toPrecision(5)} ${info.resolutionUnit}/pixel · ${info.overviewSizes.length} image ${info.overviewSizes.length === 1 ? 'level' : 'levels'}`;
  $('#tiff-nodata').textContent = `NoData: ${info.noData === null ? 'not declared' : info.noData} · PixelIsArea`;
  const select = $<HTMLSelectElement>('#tiff-band');
  select.replaceChildren(...Array.from({ length: info.bands }, (_, index) => new Option(`Band ${index + 1}${info.bandDescriptions[index] ? ` · ${info.bandDescriptions[index]}` : ''}${info.bandUnits[index] ? ` (${info.bandUnits[index]})` : ''}`, String(index))));
  $<HTMLInputElement>('#tiff-min').value = '';
  $<HTMLInputElement>('#tiff-max').value = '';
  $<HTMLInputElement>('#tiff-min').disabled = !!tiffStudy;
  $<HTMLInputElement>('#tiff-max').disabled = !!tiffStudy;
  if (tiffStudy) { $<HTMLInputElement>('#tiff-min').value = '0'; $<HTMLInputElement>('#tiff-max').value = '1'; }
  $<HTMLInputElement>('#tiff-credit').value = info.copyright ?? '';
  setTiffStatus('Metadata ready. Choose a band and display its raw values.');
}
async function loadTiff(promise: Promise<TiffSession>, study: TiffStudyReference | null = null, display = false): Promise<void> {
  const token = ++tiffToken;
  inspectedTiff = null; decodedTiff = null; tiffStudy = null; $('#tiff-inspection').hidden = true;
  setTiffStatus('Reading GeoTIFF metadata…');
  try {
    const session = await promise;
    if (token !== tiffToken) return;
    tiffStudy = study;
    showTiffMetadata(session);
    if (study) $<HTMLInputElement>('#tiff-credit').value = 'Nussear et al. (2009), U.S. Geological Survey Open-File Report 2009-1102';
    if (display) $<HTMLButtonElement>('#tiff-render').click();
  }
  catch (error) { if (token === tiffToken) setTiffStatus(error instanceof Error ? error.message : 'Could not read this GeoTIFF.', true); }
}
const nussearHabitat = nussearStudy.datasets.find(item => item.id === 'habitat-model')!;
$('#nussear-load').addEventListener('click', () => void loadTiff((async () => {
  const response = await fetch(nussearHabitat.localPath!);
  if (!response.ok) throw new Error(`Could not load the bundled habitat model (${response.status}).`);
  const blob = await response.blob();
  const { inspectLocalTiff } = await import('./geotiff');
  const session = await inspectLocalTiff(new File([blob], 'Nussear 2009 habitat potential.tif', { type: 'image/tiff' }));
  const [west, south, east, north] = session.metadata.boundsWgs84;
  if (session.metadata.crs !== 'EPSG:3857' || Math.abs(west + 119.1488949) > 0.01 ||
      Math.abs(south - 32.422115) > 0.01 || Math.abs(east + 112.6122265) > 0.01 ||
      Math.abs(north - 39.0621884) > 0.01) throw new Error('The bundled habitat model has unexpected georeferencing.');
  return session;
})(), {
  studyId: nussearStudy.id, datasetId: nussearHabitat.id,
  publicationUrl: nussearStudy.sourceUrl!, sourceUrl: nussearHabitat.sourceUrl,
  originalArchivePath: '/data/nussear-2009/ofr20091102_dt_Habitat_Model.zip',
  displayTilesUrl: '/data/nussear-2009/tiles/{z}/{x}/{y}.png',
}, true));
const tiffFile = $<HTMLInputElement>('#tiff-file');
$('#tiff-local').addEventListener('click', () => tiffFile.click());
tiffFile.addEventListener('change', () => {
  const file = tiffFile.files?.[0];
  if (file) void loadTiff(import('./geotiff').then(module => module.inspectLocalTiff(file)));
  tiffFile.value = '';
});
$<HTMLInputElement>('#tiff-url').addEventListener('input', () => {
  ++tiffToken; inspectedTiff = null; decodedTiff = null; tiffStudy = null; $('#tiff-inspection').hidden = true; setTiffStatus('');
});
$('#tiff-remote').addEventListener('click', () => void loadTiff(import('./geotiff').then(module => module.inspectRemoteTiff($<HTMLInputElement>('#tiff-url').value))));
$<HTMLSelectElement>('#tiff-band').addEventListener('change', () => {
  ++tiffToken;
  decodedTiff = null; $<HTMLInputElement>('#tiff-min').value = ''; $<HTMLInputElement>('#tiff-max').value = '';
});
function escapeAttribution(value: string): string {
  return value.replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);
}
let tiffRendering = false;
$('#tiff-render').addEventListener('click', async () => {
  if (tiffRendering) return;
  const session = inspectedTiff;
  if (!session) { setTiffStatus('Read a GeoTIFF first.', true); return; }
  tiffRendering = true;
  const button = $<HTMLButtonElement>('#tiff-render'); button.disabled = true;
  const token = tiffToken;
  try {
    const { decodeTiffBand, renderTiffBand, paletteCss } = await import('./geotiff');
    const band = Number($<HTMLSelectElement>('#tiff-band').value);
    if (!Number.isInteger(band) || band < 0 || band >= session.metadata.bands) throw new Error('Choose a valid band.');
    setTiffStatus('Decoding a bounded overview and drawing the band…');
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    if (!decodedTiff || decodedTiff.band !== band) decodedTiff = { band, data: await decodeTiffBand(session, band) };
    if (token !== tiffToken) return;
    const decoded = decodedTiff.data;
    const lowInput = $<HTMLInputElement>('#tiff-min'); const highInput = $<HTMLInputElement>('#tiff-max');
    const low = lowInput.value.trim() ? Number(lowInput.value) : decoded.min === decoded.max ? decoded.min - 0.5 : decoded.min;
    const high = highInput.value.trim() ? Number(highInput.value) : decoded.min === decoded.max ? decoded.max + 0.5 : decoded.max;
    const dataUrl = tiffStudy ? '' : renderTiffBand(decoded, session.metadata, low, high);
    const credit = $<HTMLInputElement>('#tiff-credit').value.trim();
    lab.showGeoTiff(dataUrl, session.metadata.boundsWgs84, escapeAttribution(credit),
      tiffStudy?.displayTilesUrl);
    const opacity = Number($<HTMLInputElement>('#tiff-opacity').value) / 100;
    lab.setGeoTiffOpacity(opacity);
    $<HTMLInputElement>('#tiff-visible').checked = true;
    lowInput.value = String(low); highInput.value = String(high);
    const unit = session.metadata.bandUnits[band];
    $('#tiff-layer-title').textContent = `${tiffSourceName(session.metadata)} · band ${band + 1}`;
    $('#tiff-layer-detail').textContent = `Decoded ${decoded.overview[0]} × ${decoded.overview[1]} → displayed ${decoded.width} × ${decoded.height} px`;
    const studyDetail = $('#tiff-study-detail');
    studyDetail.hidden = !tiffStudy;
    if (tiffStudy) studyDetail.innerHTML = `Model prediction · <a href="https://doi.org/${nussearStudy.doi}" target="_blank" rel="noopener">${nussearStudy.id}</a> · ${tiffStudy.datasetId}. Raster cells are not tortoise observations or a study boundary.`;
    $('#tiff-legend-title').textContent = tiffStudy ? 'Binned habitat potential · model values' : `Raw band ${band + 1} values${unit ? ` · ${unit}` : ' · units unspecified'}`;
    $('#tiff-legend-ramp').setAttribute('style', `background:${paletteCss}`);
    $('#tiff-legend-min').textContent = low.toLocaleString(); $('#tiff-legend-max').textContent = high.toLocaleString();
    $('#tiff-layer').hidden = false;
    tiffScene = { metadata: session.metadata, ...(tiffStudy ? { study: tiffStudy } : {}), processing: { band: band + 1, overview: decoded.overview, displayPixels: [decoded.width, decoded.height], resampling: 'nearest neighbor', reprojection: tiffStudy ? 'published NAD83 / UTM zone 11N grid converted to EPSG:3857 and served as PNG tiles' : session.metadata.crs === 'EPSG:4326' ? 'latitude rows resampled to Web Mercator' : 'native Web Mercator' },
      display: { minimum: low, maximum: high, palette: 'Terrain Lab generic linear', opacity, visible: true, attribution: credit } };
    lab.fitBounds([[session.metadata.boundsWgs84[0], session.metadata.boundsWgs84[1]], [session.metadata.boundsWgs84[2], session.metadata.boundsWgs84[3]]]);
    setTiffStatus('Band displayed. Colors show raw values only.');
    closeMobile();
  } catch (error) { setTiffStatus(error instanceof Error ? error.message : 'Could not display this band.', true); }
  finally { tiffRendering = false; button.disabled = false; }
});
$<HTMLInputElement>('#tiff-visible').addEventListener('change', event => {
  const visible = (event.target as HTMLInputElement).checked; lab.setGeoTiffVisibility(visible); if (tiffScene) tiffScene.display.visible = visible;
});
$<HTMLInputElement>('#tiff-opacity').addEventListener('input', event => {
  const value = Number((event.target as HTMLInputElement).value); $('#tiff-opacity-value').textContent = `${value}%`;
  lab.setGeoTiffOpacity(value / 100); if (tiffScene) tiffScene.display.opacity = value / 100;
});
$('#tiff-remove').addEventListener('click', () => { ++tiffToken; lab.removeGeoTiff(); tiffScene = null; $('#tiff-layer').hidden = true; setTiffStatus('GeoTIFF overlay removed.'); });
let inspectedArchive: ArchiveInspection | null = null;
let inspectionToken = 0;
function setPmtilesStatus(message: string, error = false): void {
  const target = $('#pmtiles-status');
  target.textContent = message;
  target.classList.toggle('error', error);
}
function showPmtilesError(id: string, message: string): void {
  setPmtilesStatus(message, true);
  const card = app.querySelector<HTMLElement>(`[data-pmtiles-id="${CSS.escape(id)}"] .pmtiles-card-error`);
  if (card) card.textContent = message;
}
function plainCredit(value: string): string {
  return new DOMParser().parseFromString(value, 'text/html').body.textContent?.trim() ?? value;
}
function renderPmtilesLayers(): void {
  const container = $('#pmtiles-layers');
  container.replaceChildren();
  for (const layer of lab.getPmtilesLayers()) {
    const card = document.createElement('div'); card.className = 'pmtiles-card'; card.dataset.pmtilesId = layer.id;
    const heading = document.createElement('div'); heading.className = 'pmtiles-card-heading';
    const name = document.createElement('strong'); name.textContent = layer.name;
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.title = 'Remove PMTiles layer'; remove.setAttribute('aria-label', `Remove ${layer.name}`);
    remove.addEventListener('click', () => { lab.removePmtilesLayer(layer.id); renderPmtilesLayers(); setPmtilesStatus('Hosted layer removed.'); });
    heading.append(name, remove);
    const details = document.createElement('small'); details.textContent = `${layer.tileType}${layer.sourceLayer ? ` · ${layer.sourceLayer}` : ''} · ${new URL(layer.url).host}`;
    const visibility = document.createElement('label'); visibility.className = 'pmtiles-visibility';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = layer.visible;
    checkbox.addEventListener('change', () => lab.setPmtilesVisibility(layer.id, checkbox.checked));
    visibility.append(checkbox, document.createTextNode('Visible'));
    const opacityLabel = document.createElement('label'); opacityLabel.className = 'slider-label';
    const opacityId = `${layer.id}-opacity`; opacityLabel.htmlFor = opacityId;
    const opacityValue = document.createElement('output'); opacityValue.textContent = `${Math.round(layer.opacity * 100)}%`;
    opacityLabel.append(document.createTextNode('Opacity'), opacityValue);
    const opacity = document.createElement('input'); opacity.type = 'range'; opacity.id = opacityId; opacity.min = '0'; opacity.max = '100'; opacity.value = String(Math.round(layer.opacity * 100));
    opacity.addEventListener('input', () => { const value = Number(opacity.value); lab.setPmtilesOpacity(layer.id, value / 100); opacityValue.textContent = `${value}%`; });
    const view = document.createElement('button'); view.type = 'button'; view.className = 'pmtiles-view'; view.textContent = 'View extent ↗';
    view.addEventListener('click', () => { const [west, south, east, north] = layer.bounds; lab.fitBounds([[west, south], [east, north]]); closeMobile(); });
    const credit = document.createElement('small'); credit.className = 'pmtiles-card-credit'; credit.textContent = `Credit: ${plainCredit(layer.attribution)}`;
    const error = document.createElement('p'); error.className = 'pmtiles-card-error'; error.setAttribute('role', 'status');
    card.append(heading, details, visibility, opacityLabel, opacity, view, credit, error);
    container.append(card);
  }
}
$<HTMLInputElement>('#pmtiles-url').addEventListener('input', () => {
  inspectedArchive = null; inspectionToken++;
  $('#pmtiles-inspection').hidden = true;
  setPmtilesStatus('');
});
$('#pmtiles-inspect').addEventListener('click', async () => {
  const token = ++inspectionToken;
  inspectedArchive = null;
  $('#pmtiles-inspection').hidden = true;
  const button = $<HTMLButtonElement>('#pmtiles-inspect'); button.disabled = true;
  setPmtilesStatus('Reading archive header and metadata…');
  try {
    const [{ inspectArchive }] = await Promise.all([import('./pmtiles'), preparePmtiles()]);
    const inspection = await inspectArchive($<HTMLInputElement>('#pmtiles-url').value);
    if (token !== inspectionToken) return;
    inspectedArchive = inspection;
    $('#pmtiles-inspection').hidden = false;
    $('#pmtiles-name').textContent = inspection.name;
    $('#pmtiles-details').textContent = `${inspection.tileType} · zoom ${inspection.minZoom}–${inspection.maxZoom} · ${inspection.addressedTiles.toLocaleString()} addressed tiles`;
    $('#pmtiles-description').textContent = inspection.description;
    const vector = inspection.kind === 'vector';
    $('#pmtiles-sources-wrap').hidden = !vector || !inspection.sourceLayers.length;
    $('#pmtiles-manual-wrap').hidden = !vector || !!inspection.sourceLayers.length;
    $('#pmtiles-size-wrap').hidden = vector;
    const select = $<HTMLSelectElement>('#pmtiles-source-layer');
    select.replaceChildren(...inspection.sourceLayers.map(name => new Option(name, name)));
    $<HTMLSelectElement>('#pmtiles-tile-size').value = String(inspection.tileSize);
    $('#pmtiles-required-credit').textContent = inspection.attribution ? `Archive credit: ${plainCredit(inspection.attribution)}` : 'This archive does not include attribution metadata. Enter its required credit below.';
    $('#pmtiles-credit-qualifier').textContent = inspection.attribution ? '· additional, optional' : '· required';
    setPmtilesStatus('Archive ready. Choose a source layer if needed, then add it to the map.');
  } catch (error) {
    if (token === inspectionToken) setPmtilesStatus(error instanceof Error ? error.message : 'Could not inspect this archive.', true);
  } finally { if (token === inspectionToken) button.disabled = false; }
});
$('#pmtiles-add').addEventListener('click', () => {
  try {
    if (!inspectedArchive) throw new Error('Inspect an archive first.');
    const inspection = inspectedArchive;
    const sourceLayer = inspection.kind === 'vector' ? (inspection.sourceLayers.length ?
      $<HTMLSelectElement>('#pmtiles-source-layer').value : $<HTMLInputElement>('#pmtiles-manual-layer').value.trim()) : null;
    const size = Number($<HTMLSelectElement>('#pmtiles-tile-size').value) as 256 | 512;
    const layer = lab.addPmtilesLayer(inspection, sourceLayer, $<HTMLInputElement>('#pmtiles-extra-credit').value, size);
    renderPmtilesLayers();
    setPmtilesStatus(`${layer.name} added. Use View extent to navigate to its coverage.`);
    announce('PMTiles layer added');
  } catch (error) { setPmtilesStatus(error instanceof Error ? error.message : 'Could not add this layer.', true); }
});
$('#clear-drawings').addEventListener('click', async () => {
  await drawing.clear();
  announce('Drawings cleared');
});
function downloadJson(filename: string, data: unknown): void {
  const mime = filename.endsWith('.geojson') ? 'application/geo+json' : 'application/json';
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: mime }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 30000);
}
$('#export-drawings').addEventListener('click', () => {
  downloadJson('terrain-lab-drawings.geojson', drawing.data());
  announce('Drawn features exported as GeoJSON');
});
let analysisBusy = false;
function refreshAnalysis(): void {
  const operation = $<HTMLSelectElement>('#analysis-operation').value as Operation;
  const candidates = analysisSources().filter(source => supports(operation, source));
  const first = $<HTMLSelectElement>('#analysis-first');
  const second = $<HTMLSelectElement>('#analysis-second');
  const previousFirst = first.value;
  const previousSecond = second.value;
  const fill = (select: HTMLSelectElement, previous: string) => {
    select.replaceChildren(...candidates.map(source => new Option(source.label, source.key)));
    if (candidates.some(source => source.key === previous)) select.value = previous;
  };
  fill(first, previousFirst);
  fill(second, previousSecond);
  if (operation === 'distance' && candidates.length > 1 && second.value === first.value) second.selectedIndex = 1;
  $('#analysis-second-wrap').hidden = operation !== 'distance';
  $('#analysis-radius-wrap').hidden = operation !== 'buffer';
  const needed = operation === 'distance' ? 2 : 1;
  $('#analysis-run').toggleAttribute('disabled', analysisBusy || candidates.length < needed);
  $('#analysis-help').textContent = candidates.length < needed ?
    `Add ${needed === 2 ? 'two points' : operation === 'length' ? 'a line' : operation === 'area' ? 'a polygon' : 'a supported feature'} to calculate.` :
    operation === 'buffer' ? 'Radius: greater than 0 and up to 50,000 m. Output is an approximate geodesic polygon.' :
    `Result is a computed snapshot. Recalculate after editing source geometry.${lab.getImported().features.length > 500 ? ' Analysis lists the first 500 imported features to keep controls responsive.' : ''}`;
}
function analysisSources() {
  const imported = lab.getImported();
  return sourceFeatures({ type: 'FeatureCollection', features: imported.features.slice(0, 500) }, drawing.data());
}
function renderResults(): void {
  const container = $('#analysis-results');
  container.replaceChildren();
  if (!analysisResults.length) {
    const empty = document.createElement('p'); empty.className = 'analysis-empty'; empty.textContent = 'No results yet.'; container.append(empty);
  }
  for (const result of analysisResults) {
    const card = document.createElement('div'); card.className = 'analysis-result';
    const body = document.createElement('div');
    const title = document.createElement('strong'); title.textContent = `${result.title} · ${result.valueLabel}`;
    const source = document.createElement('small'); source.textContent = result.sourceLabel;
    body.append(title, source);
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.title = 'Remove computed result'; remove.setAttribute('aria-label', `Remove ${result.title} result`);
    remove.addEventListener('click', () => { analysisResults.splice(analysisResults.findIndex(item => item.id === result.id), 1); lab.setDerived(resultsGeoJson(analysisResults)); renderResults(); });
    card.append(body, remove); container.append(card);
  }
  $<HTMLButtonElement>('#analysis-export').disabled = !analysisResults.length;
}
$('#nussear-distance').addEventListener('click', async () => {
  try {
    const analysisUrl = '/data/nussear-2009/cell-distance.geojson';
    const response = await fetch(analysisUrl);
    if (!response.ok) throw new Error(`Could not load the research analysis (${response.status}).`);
    const inspection = inspectGeoJson(await response.json() as unknown);
    const [first, second, line] = inspection.data.features as Array<{ type: string; geometry: { type: string }; properties: Record<string, unknown> }>;
    if (inspection.featureCount !== 3 || first?.geometry?.type !== 'Point' || second?.geometry?.type !== 'Point' || line?.geometry?.type !== 'LineString' ||
      line.properties?.operation !== 'distance' || line.properties?.studyId !== nussearStudy.id || line.properties?.datasetId !== nussearHabitat.id ||
      first.properties?.classification !== 'model prediction cell center' || second.properties?.classification !== 'model prediction cell center')
      throw new Error('The bundled research analysis has an unexpected structure.');
    const value = Number(line.properties?.value);
    if (!Number.isFinite(value) || value <= 0) throw new Error('The research distance is invalid.');
    const points = { type: 'FeatureCollection' as const, features: [first, second] };
    ++pointModeToken;
    pointPopup.remove();
    importedPointCount = 2;
    importedProvenance = { kind: 'research model cells', fileName: 'Nussear model cell centers', bytes: 0, lastModified: null,
      crs: 'WGS84 longitude/latitude', featureCount: 2, coordinateCount: 2,
      attribution: 'Nussear et al. (2009), USGS Open-File Report 2009-1102', studyId: nussearStudy.id,
      datasetId: nussearHabitat.id, sourceUrl: nussearHabitat.sourceUrl, analysisUrl };
    $<HTMLInputElement>('#geojson-credit').value = importedProvenance.attribution;
    $('#layer-origin').textContent = 'Research model cells · EPSG:3857 cell centers transformed to WGS84';
    syncImportedCredit();
    pointMode = 'maplibre'; deckPoints?.disable(); lab.setImportedPointMode('maplibre');
    lab.setImportedPolygonStyle('default'); lab.setImported(points); deckPoints?.setData(points);
    syncPointControls(); refreshAnalysis();
    $('#layer-name').textContent = 'Nussear model cell centers';
    $('#layer-details').textContent = '2 selected model cells · predictions, not observations';
    $('#layer-card').hidden = false;
    const result: AnalysisResult = { id: crypto.randomUUID(), title: 'Point distance', valueLabel: `${(value / 1000).toFixed(3)} km`,
      sourceLabel: String(line.properties?.source ?? 'Nussear model cell centers'), feature: line as unknown as AnalysisResult['feature'] };
    const previous = analysisResults.findIndex(item => item.feature.properties?.studyId === nussearStudy.id &&
      item.feature.properties?.datasetId === nussearHabitat.id && item.feature.properties?.source === result.sourceLabel);
    if (previous !== -1) analysisResults.splice(previous, 1);
    analysisResults.push(result); lab.setDerived(resultsGeoJson(analysisResults)); renderResults();
    if (inspection.bounds) lab.fitBounds(inspection.bounds);
    announce(`Loaded model cells and headless distance: ${result.valueLabel}`);
    closeMobile();
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not load the research analysis.'); }
});
$<HTMLSelectElement>('#analysis-operation').addEventListener('change', refreshAnalysis);
$<HTMLSelectElement>('#analysis-first').addEventListener('change', refreshAnalysis);
$('#analysis-run').addEventListener('click', async () => {
  if (analysisBusy) return;
  analysisBusy = true;
  refreshAnalysis();
  try {
    const operation = $<HTMLSelectElement>('#analysis-operation').value as Operation;
    const candidates = analysisSources();
    const first = candidates.find(source => source.key === $<HTMLSelectElement>('#analysis-first').value);
    const second = candidates.find(source => source.key === $<HTMLSelectElement>('#analysis-second').value);
    if (!first) throw new Error('Choose a source feature.');
    const radiusInput = $<HTMLInputElement>('#analysis-radius');
    const radius = operation === 'buffer' && radiusInput.value.trim() !== '' ? Number(radiusInput.value) : undefined;
    let result: AnalysisResult;
    if (operation === 'distance') {
      const response = await runPointDistanceRequest({ contractVersion: POINT_DISTANCE_CONTRACT_VERSION,
        operationId: POINT_DISTANCE_OPERATION_ID, inputs: { first, second } });
      if (!response.ok) throw new Error(response.error.message);
      result = response.result;
    } else if (operation === 'area') {
      const response = await runPolygonAreaRequest({ contractVersion: POLYGON_AREA_CONTRACT_VERSION,
        operationId: POLYGON_AREA_OPERATION_ID, units: 'square-meters', input: first });
      if (!response.ok) throw new Error(response.error.message);
      result = response.result;
    } else result = await compute(operation, first, second, radius);
    analysisResults.push(result);
    lab.setDerived(resultsGeoJson(analysisResults));
    renderResults();
    announce(`${result.title}: ${result.valueLabel} · computed geometry`);
  } catch (error) { announce(error instanceof Error ? error.message : 'Could not calculate this geometry.'); }
  finally { analysisBusy = false; refreshAnalysis(); }
});
$('#analysis-export').addEventListener('click', () => { downloadJson('terrain-lab-computed-results.geojson', resultsGeoJson(analysisResults)); announce('Computed geometry exported as GeoJSON'); });
refreshAnalysis();
$('#export').addEventListener('click', () => {
  const scene = { format: 'terrain-lab-scene/v7', exportedAt: new Date().toISOString(), camera: lab.getCamera(),
    basemap: lab.getBasemap(), terrainExaggeration: lab.getTerrainScale(),
    importedGeoJson: lab.getImported(), importedProvenance, importedOpacity: lab.getImportedOpacity(),
    drawnGeoJson: drawing.data(), derivedGeoJson: resultsGeoJson(analysisResults),
    pmtilesLayers: lab.getPmtilesLayers(), geoTiffRaster: tiffScene,
    importedPointDisplay: { renderer: pointMode, pointCount: importedPointCount, deckStyle: { ...pointStyle }, terrainBehavior: 'screen overlay; not terrain draped' } };
  downloadJson('terrain-lab-scene.json', scene);
  announce('Scene exported as JSON');
});

const mobileToggle = $('#mobile-toggle');
function closeMobile(): void { app.classList.remove('mobile-open'); mobileToggle.setAttribute('aria-expanded', 'false'); }
mobileToggle.addEventListener('click', () => {
  const open = app.classList.toggle('mobile-open');
  mobileToggle.setAttribute('aria-expanded', String(open));
  if (open) $('.workspace-scroll').scrollTop = 0;
});
