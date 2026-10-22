import 'maplibre-gl/dist/maplibre-gl.css';
import { setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import './style.css';
import { AtlasMap, type Basemap, type MapStatus, type StudyLayer } from './map/atlasMap';
import { places } from './data/places';
import { story } from './data/story';
import { figureHtml } from './data/figures';
import { dutcherStudy } from './data/studies';

setWorkerUrl(workerUrl);

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing app root');

app.innerHTML = `
  <main class="atlas">
    <div id="map" class="map" role="application" aria-label="Interactive three-dimensional map of the Ivanpah Valley study region"></div>
    <div class="vignette" aria-hidden="true"></div>

    <header class="masthead panel-glass">
      <div class="masthead__kicker"><span class="signal-dot"></span> FIELD ATLAS <span class="divider"></span> MOJAVE DESERT · CA / NV</div>
      <h1>Genes <em>in</em> Space<span class="period">.</span></h1>
      <p>Landscape connectivity through the lens of desert tortoise genetics</p>
      <button id="research-open" class="research-launch" type="button">Explore research figures ↗</button>
    </header>

    <section class="story panel-glass" aria-labelledby="story-title">
      <div class="story__topline"><span id="story-eyebrow">01 / Study geography</span><span id="story-count">01 — 05</span></div>
      <h2 id="story-title">Where were the tortoises studied?</h2>
      <p id="story-body"></p>
      <p id="story-detail" class="story__detail"></p>
      <button id="story-figure" class="story-figure" type="button">Open related figure ↗</button>
      <div class="story__footer">
        <button id="story-prev" class="icon-button" type="button" aria-label="Previous section">←</button>
        <div id="story-progress" class="story__progress" aria-label="Story progress"></div>
        <button id="story-next" class="icon-button" type="button" aria-label="Next section">→</button>
      </div>
    </section>

    <aside class="layer-panel panel-glass" aria-label="Map layers">
      <div class="panel-heading"><span>MAP VIEW</span><span class="tiny-line"></span><button id="layers-toggle" class="layers-toggle" type="button" aria-expanded="false" aria-label="Toggle map layers">Layers +</button></div>
      <div class="segmented" role="group" aria-label="Basemap mode">
        <button type="button" data-basemap="satellite" class="active">Satellite</button>
        <button type="button" data-basemap="elevation">Elevation</button>
        <button type="button" data-basemap="hillshade">Hillshade</button>
      </div>
      <p id="basemap-caption" class="basemap-caption">Satellite mosaic · 2020</p>
      <div class="layer-body">
      <label class="toggle-row"><span>Roads &amp; labels</span><input id="roads-toggle" type="checkbox" checked /><span class="switch"></span></label>
      <label class="toggle-row"><span>3D terrain</span><input id="terrain-toggle" type="checkbox" checked /><span class="switch"></span></label>
      <div class="study-layer-heading">VERIFIED STUDY OVERLAYS</div>
      <label class="toggle-row"><span><i class="legend-dot legend-dot--site"></i> Sampled locations</span><input data-study-layer="sites" type="checkbox" checked /><span class="switch"></span></label>
      <label class="toggle-row"><span><i class="legend-dot legend-dot--highway"></i> I-15</span><input data-study-layer="highway" type="checkbox" checked /><span class="switch"></span></label>
      <label class="toggle-row"><span><i class="legend-dot legend-dot--railway"></i> Railways</span><input data-study-layer="railway" type="checkbox" checked /><span class="switch"></span></label>
      <label class="toggle-row"><span><i class="legend-dot legend-dot--solar"></i> BLM solar ROW</span><input data-study-layer="solar" type="checkbox" /><span class="switch"></span></label>
      <div id="elevation-legend" class="elevation-legend" hidden>
        <div class="legend-title">ELEVATION <span>meters · DEM</span></div>
        <div class="legend-ramp"></div>
        <div class="legend-ticks"><span>400</span><span>1,300</span><span>2,200</span><span>3,200+</span></div>
      </div>
      <p class="layer-panel__hint">Drag to pan · right drag to tilt and rotate · scroll to zoom</p>
      <div id="source-credit" class="source-credit">Imagery: <a href="https://cloudless.eox.at/" target="_blank" rel="noopener">EOxCloudless</a> by EOX IT Services GmbH · modified Copernicus Sentinel data 2020</div>
      </div>
    </aside>

    <aside id="research-panel" class="research-panel panel-glass" aria-label="Study figures and findings" hidden>
      <div class="research-panel__header"><div><span class="research-kicker">DUTCHER ET AL. · ${dutcherStudy.publicationYear}</span><h2>Study evidence</h2></div><button id="research-close" type="button" aria-label="Close study figures">×</button></div>
      <div class="figure-tabs" role="tablist" aria-label="Study figures"><button type="button" data-figure="1">Fig 1</button><button type="button" data-figure="2">Fig 2</button><button type="button" data-figure="3">Fig 3</button><button type="button" data-figure="4">Fig 4</button><button type="button" data-figure="5">Findings</button></div>
      <div id="figure-content" class="figure-content" role="tabpanel"></div>
      <p class="research-source">Source: <a href="https://doi.org/${dutcherStudy.doi}" target="_blank" rel="noopener">Dutcher et al. (${dutcherStudy.publicationYear})</a> · <a href="https://www.sciencebase.gov/catalog/item/5e38914ce4b0a79317df572d" target="_blank" rel="noopener">USGS data release</a> · <a href="${dutcherStudy.provenanceUrl}" target="_blank">dataset methods</a></p>
    </aside>

    <nav class="place-nav panel-glass" aria-label="Explore geographic regions">
      <div class="place-nav__heading"><span>GEOGRAPHIC VIEWS <small>· reference places</small></span><button id="overview" type="button">Full extent ↗</button></div>
      <div id="place-list" class="place-nav__list"></div>
    </nav>

    <div class="map-actions" role="group" aria-label="Camera actions">
      <button id="orbit" type="button" title="Rotate the view">⟳ <span>Orbit</span></button>
      <button id="reset-view" type="button" title="Regional overview">⌖ <span>Overview</span></button>
    </div>

    <div id="map-status" class="map-status" role="status" aria-live="polite"><span class="signal-dot"></span><span>LOADING LIVE TERRAIN</span></div>
    <div class="data-notice"><span id="context-tag">OBSERVED</span><span id="map-context">Site means from USGS records · no individual locations</span></div>
    <div id="service-warning" class="service-warning" role="alert" hidden></div>
  </main>
`;

const $ = <T extends HTMLElement>(selector: string): T => {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`Missing element: ${selector}`);
  return element;
};

const status = $<HTMLDivElement>('#map-status');
const warning = $<HTMLDivElement>('#service-warning');
const basemapButtons = [...document.querySelectorAll<HTMLButtonElement>('[data-basemap]')];
const elevationLegend = $<HTMLDivElement>('#elevation-legend');
const sourceCredit = $<HTMLDivElement>('#source-credit');
const basemapCaption = $<HTMLParagraphElement>('#basemap-caption');
const layerPanel = $<HTMLElement>('.layer-panel');
const layersToggle = $<HTMLButtonElement>('#layers-toggle');

function setLayersCollapsed(collapsed: boolean): void {
  layerPanel.classList.toggle('is-collapsed', collapsed);
  $('.atlas').classList.toggle('layers-open', !collapsed);
  layersToggle.setAttribute('aria-expanded', String(!collapsed));
  layersToggle.textContent = collapsed ? 'Layers +' : 'Layers −';
}
setLayersCollapsed(true);
layersToggle.addEventListener('click', () => setLayersCollapsed(!layerPanel.classList.contains('is-collapsed')));

function updateStatus(state: MapStatus): void {
  status.dataset.level = state.level;
  status.querySelector('span:last-child')!.textContent = state.message;
  warning.hidden = state.level !== 'warning';
  if (state.level === 'warning') warning.textContent = state.message.replace(' · ', '. ') + '. Map navigation remains available where tiles have loaded.';
}

const orbitButton = $<HTMLButtonElement>('#orbit');
const atlas = new AtlasMap($('#map'), updateStatus, () => syncBasemap('hillshade'), orbiting => {
  orbitButton.classList.toggle('active', orbiting);
  orbitButton.setAttribute('aria-pressed', String(orbiting));
});

function syncBasemap(value: Basemap): void {
  for (const button of basemapButtons) {
    const active = button.dataset.basemap === value;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  }
  elevationLegend.hidden = value !== 'elevation';
  basemapCaption.textContent = value === 'satellite' ? 'Satellite mosaic · 2020'
    : value === 'elevation' ? 'Elevation in meters · not habitat'
      : 'Terrain shaded from real DEM';
  sourceCredit.innerHTML = value === 'satellite'
    ? 'Imagery: <a href="https://cloudless.eox.at/" target="_blank" rel="noopener">EOxCloudless</a> by EOX IT Services GmbH · modified Copernicus Sentinel data 2020'
    : 'Elevation: <a href="https://mapterhorn.com/attribution/" target="_blank" rel="noopener">Mapterhorn source credits</a>';
}

for (const button of basemapButtons) {
  button.addEventListener('click', () => {
    const value = button.dataset.basemap as Basemap;
    atlas.setBasemap(value);
    syncBasemap(value);
  });
}
syncBasemap('satellite');

$('#roads-toggle').addEventListener('change', (event) => atlas.setRoadsVisible((event.target as HTMLInputElement).checked));
$('#terrain-toggle').addEventListener('change', (event) => atlas.setTerrainVisible((event.target as HTMLInputElement).checked));
const studyChecks = [...document.querySelectorAll<HTMLInputElement>('[data-study-layer]')];
function setStudyLayers(layers: StudyLayer[]): void {
  for (const checkbox of studyChecks) {
    const layer = checkbox.dataset.studyLayer as StudyLayer;
    const visible = layers.includes(layer);
    checkbox.checked = visible;
    atlas.setStudyLayer(layer, visible);
  }
}
for (const checkbox of studyChecks) checkbox.addEventListener('change', () => atlas.setStudyLayer(checkbox.dataset.studyLayer as StudyLayer, checkbox.checked));
$('#overview').addEventListener('click', () => atlas.overview());
$('#reset-view').addEventListener('click', () => atlas.overview());

orbitButton.addEventListener('click', () => {
  if (atlas.isOrbiting()) atlas.stopOrbit(); else atlas.startOrbit();
});

const placeList = $<HTMLDivElement>('#place-list');
for (const place of places) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'place-link';
  button.innerHTML = `<span class="place-link__dot"></span><span><strong>${place.name}</strong><small>${place.subtitle}</small></span><span class="place-link__arrow">↗</span>`;
  button.title = place.note;
  button.addEventListener('click', () => {
    document.querySelectorAll('.place-link').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    atlas.flyTo(place);
    orbitButton.classList.remove('active');
  });
  placeList.append(button);
}

const researchPanel = $<HTMLElement>('#research-panel');
const figureContent = $<HTMLDivElement>('#figure-content');
const figureTabs = [...document.querySelectorAll<HTMLButtonElement>('[data-figure]')];
let activeFigure = 1;
function showFigure(figure: number): void {
  activeFigure = figure;
  researchPanel.hidden = false;
  setLayersCollapsed(true);
  figureContent.innerHTML = figureHtml[figure];
  for (const tab of figureTabs) {
    const selected = Number(tab.dataset.figure) === figure;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
  figureContent.scrollTop = 0;
  for (const button of figureContent.querySelectorAll<HTMLButtonElement>('[data-concept]')) {
    button.addEventListener('click', () => {
      const concept = button.dataset.concept;
      setStudyLayers(concept === 'highway' ? ['highway'] : concept === 'railway' ? ['railway'] : []);
      figureContent.querySelectorAll('[data-concept]').forEach(item => item.classList.toggle('active', item === button));
    });
  }
}
$('#research-open').addEventListener('click', () => showFigure(activeFigure));
$('#research-close').addEventListener('click', () => { researchPanel.hidden = true; });
$('#story-figure').addEventListener('click', () => showFigure(story[activeStory].figure));
for (const tab of figureTabs) tab.addEventListener('click', () => showFigure(Number(tab.dataset.figure)));
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') researchPanel.hidden = true; });

let activeStory = 0;
const progress = $<HTMLDivElement>('#story-progress');
story.forEach((_, index) => {
  const mark = document.createElement('button');
  mark.type = 'button';
  mark.setAttribute('aria-label', `Go to story section ${index + 1}`);
  mark.addEventListener('click', () => showStory(index));
  progress.append(mark);
});

function showStory(index: number): void {
  activeStory = Math.max(0, Math.min(story.length - 1, index));
  const section = story[activeStory];
  $('#story-eyebrow').textContent = section.eyebrow;
  $('#story-count').textContent = `${String(activeStory + 1).padStart(2, '0')} — ${String(story.length).padStart(2, '0')}`;
  $('#story-title').textContent = section.title;
  $('#story-body').textContent = section.body;
  $('#story-detail').textContent = section.detail;
  const context = section.id === 'where' || section.id === 'terrain'
    ? ['OBSERVED', 'Site means from USGS records · Piute is a broader area']
    : section.id === 'corridors' || section.id === 'uncertainty'
      ? ['PUBLIC GIS', 'Census corridors · BLM right-of-way · not modeled cost']
      : ['INFERENCE', 'Three reported groups · no invented boundaries'];
  $('#context-tag').textContent = context[0];
  $('#map-context').textContent = context[1];
  $('#story-figure').textContent = section.figure === 5 ? 'Explore findings ↗' : `Explore figure ${section.figure} ↗`;
  [...progress.children].forEach((mark, i) => mark.classList.toggle('active', i === activeStory));
  ($<HTMLButtonElement>('#story-prev')).disabled = activeStory === 0;
  ($<HTMLButtonElement>('#story-next')).disabled = activeStory === story.length - 1;
  setStudyLayers(section.layers);
  if (activeStory === 0 && index !== 0) atlas.overview();
  else if (index !== 0) atlas.moveToScene(section.scene);
  if (index !== 0 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    $('.story').animate([{ opacity: 0.72, transform: 'translateY(9px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 420, easing: 'ease-out' });
  }
}

$('#story-prev').addEventListener('click', () => showStory(activeStory - 1));
$('#story-next').addEventListener('click', () => showStory(activeStory + 1));
showStory(0);
