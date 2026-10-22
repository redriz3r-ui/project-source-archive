import * as maplibregl from 'maplibre-gl';
import type { Map as MapLibreMap } from 'maplibre-gl';
import { places, studyBounds, type Place } from '../data/places';

export type Basemap = 'satellite' | 'elevation' | 'hillshade';
export type MapStatus = { level: 'loading' | 'ready' | 'warning'; message: string };
export type StudyLayer = 'sites' | 'highway' | 'railway' | 'solar';
export type CameraScene = { center: [number, number]; zoom: number; bearing: number; pitch: number };

const OPENFREEMAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';
const EOX_TILES = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg';
const DEM_TILEJSON = 'https://tiles.mapterhorn.com/tilejson.json';
const BASEMAP_FADE_MS = 650;
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const reliefColors: unknown[] = [
  'interpolate', ['linear'], ['elevation'],
  400, '#283c43', 700, '#4b746c', 1000, '#9ea987',
  1300, '#cdb98b', 1600, '#c4a078', 2000, '#927b6d',
  2500, '#d4d1c3', 3200, '#f5f4ea'
];

export class AtlasMap {
  readonly map: MapLibreMap;
  private basemap: Basemap = 'satellite';
  private roadsVisible = true;
  private terrainVisible = true;
  private styleReady = false;
  private imageFailures = 0;
  private demFailures = 0;
  private orbitFrame = 0;
  private orbitTime = 0;
  private renderedBasemap: Basemap | null = null;
  private basemapToken = 0;
  private basemapCleanup = 0;
  private studyVisibility: Record<StudyLayer, boolean> = { sites: true, highway: true, railway: true, solar: false };
  private placeMarkers: HTMLElement[] = [];
  private onStatus: (status: MapStatus) => void;
  private onFallback: () => void;
  private onOrbitChange: (orbiting: boolean) => void;

  constructor(container: HTMLElement, onStatus: (status: MapStatus) => void, onFallback: () => void, onOrbitChange: (orbiting: boolean) => void = () => {}) {
    this.onStatus = onStatus;
    this.onFallback = onFallback;
    this.onOrbitChange = onOrbitChange;
    this.map = new maplibregl.Map({
      container,
      style: OPENFREEMAP_STYLE,
      center: [-115.31, 35.57],
      zoom: 9.35,
      pitch: 52,
      bearing: -17,
      maxPitch: 85,
      maxZoom: 16,
      minZoom: 6,
      renderWorldCopies: false,
      attributionControl: false
    });

    this.map.addControl(new maplibregl.NavigationControl({ showZoom: true, showCompass: true, visualizePitch: true }), 'top-right');
    this.map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 120 }), 'bottom-right');
    this.map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
    this.map.on('load', () => this.installLayers());
    this.map.on('error', (event) => this.handleError(String(event.error?.message ?? 'Map service error')));
    this.map.on('dragstart', () => this.stopOrbit());
    this.map.on('wheel', () => this.stopOrbit());
    this.map.on('zoomend', () => this.updatePlaceMarkerDensity());
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.stopOrbit(); });
  }

  private installLayers(): void {
    const map = this.map;
    const road = map.getStyle().layers?.find((layer) => {
      const sourceLayer = 'source-layer' in layer ? layer['source-layer'] : undefined;
      return sourceLayer === 'transportation';
    });
    const before = road?.id ?? map.getStyle().layers?.find((layer) => layer.type === 'symbol')?.id;

    map.addSource('atlas-satellite', {
      type: 'raster', tiles: [EOX_TILES], tileSize: 256, maxzoom: 13,
      attribution: '<a href="https://cloudless.eox.at/" target="_blank" rel="noopener">EOxCloudless</a> by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2020)'
    });
    map.addSource('atlas-dem', {
      type: 'raster-dem', url: DEM_TILEJSON,
      attribution: '<a href="https://mapterhorn.com/attribution/" target="_blank" rel="noopener">Mapterhorn elevation sources</a>'
    });
    map.addSource('atlas-terrain-dem', {
      type: 'raster-dem', url: DEM_TILEJSON,
      attribution: '<a href="https://mapterhorn.com/attribution/" target="_blank" rel="noopener">Mapterhorn elevation sources</a>'
    });

    map.addLayer({ id: 'atlas-satellite-layer', type: 'raster', source: 'atlas-satellite', paint: { 'raster-opacity': 1, 'raster-opacity-transition': { duration: BASEMAP_FADE_MS }, 'raster-fade-duration': 250 } }, before);
    map.addLayer({ id: 'atlas-relief-layer', type: 'color-relief', source: 'atlas-dem', layout: { visibility: 'none' }, paint: { 'color-relief-color': reliefColors as any, 'color-relief-opacity': 0, 'color-relief-opacity-transition': { duration: BASEMAP_FADE_MS } } }, before);
    map.addLayer({ id: 'atlas-gray-relief-layer', type: 'color-relief', source: 'atlas-dem', layout: { visibility: 'none' }, paint: { 'color-relief-color': ['interpolate', ['linear'], ['elevation'], 400, '#404a43', 1000, '#92978d', 1800, '#b9b8a8', 2800, '#efeee4'] as any, 'color-relief-opacity': 0, 'color-relief-opacity-transition': { duration: BASEMAP_FADE_MS } } }, before);
    map.addLayer({ id: 'atlas-hillshade-layer', type: 'hillshade', source: 'atlas-dem', layout: { visibility: 'none' }, paint: { 'hillshade-illumination-direction': 325, 'hillshade-shadow-color': '#293b3a', 'hillshade-highlight-color': '#f1ebcf', 'hillshade-accent-color': '#8a8e79', 'hillshade-exaggeration': 0, 'hillshade-exaggeration-transition': { duration: BASEMAP_FADE_MS } } }, before);
    map.setTerrain({ source: 'atlas-terrain-dem', exaggeration: 1.25 });
    this.styleReady = true;
    this.applyBasemap();
    this.addPlaceMarkers();
    this.installStudyLayers();
    this.onStatus({ level: 'ready', message: 'LIVE TERRAIN · IVANPAH REGION' });
  }

  private addPlaceMarkers(): void {
    for (const place of places) {
      const marker = document.createElement('button');
      marker.className = 'place-marker';
      marker.type = 'button';
      marker.setAttribute('aria-label', `Fly to ${place.name}`);
      marker.innerHTML = `<span class="place-marker__dot"></span><span class="place-marker__name">${place.name}</span>`;
      marker.addEventListener('click', () => this.flyTo(place));
      new maplibregl.Marker({ element: marker, anchor: 'center' }).setLngLat(place.coordinates).addTo(this.map);
      this.placeMarkers.push(marker);
    }
    this.updatePlaceMarkerDensity();
  }

  private updatePlaceMarkerDensity(): void {
    const compact = this.map.getZoom() < 10.3;
    this.placeMarkers.forEach(marker => marker.classList.toggle('is-compact', compact));
  }

  private installStudyLayers(): void {
    const add = (id: StudyLayer, file: string) => this.map.addSource(`study-${id}`, { type: 'geojson', data: `/data/${file}` });
    add('sites', 'study-sites.geojson');
    add('highway', 'interstate-15.geojson');
    add('railway', 'railways.geojson');
    add('solar', 'solar-row.geojson');
    this.map.addLayer({ id: 'study-solar-fill', type: 'fill', source: 'study-solar', paint: { 'fill-color': '#eab361', 'fill-opacity': 0.3 } });
    this.map.addLayer({ id: 'study-solar-outline', type: 'line', source: 'study-solar', paint: { 'line-color': '#f8c873', 'line-width': 2 } });
    this.map.addLayer({ id: 'study-highway-line', type: 'line', source: 'study-highway', paint: { 'line-color': '#ff8e78', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 2, 12, 5], 'line-opacity': 0.95 } });
    this.map.addLayer({ id: 'study-railway-line', type: 'line', source: 'study-railway', paint: { 'line-color': '#e9d580', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 2, 12, 4], 'line-dasharray': [1.5, 1] } });
    this.map.addLayer({ id: 'study-site-halo', type: 'circle', source: 'study-sites', paint: { 'circle-radius': ['case', ['==', ['get', 'kind'], 'broader-area'], 15, 11], 'circle-color': '#172920', 'circle-opacity': 0.8, 'circle-stroke-color': ['case', ['==', ['get', 'kind'], 'broader-area'], '#ffd184', '#a9ecb9'], 'circle-stroke-width': 2.5 } });
    this.map.addLayer({ id: 'study-site-core', type: 'circle', source: 'study-sites', paint: { 'circle-radius': ['case', ['==', ['get', 'kind'], 'broader-area'], 5, 3.5], 'circle-color': ['case', ['==', ['get', 'kind'], 'broader-area'], '#ffd184', '#a9ecb9'] } });
    this.map.on('click', 'study-site-halo', (event) => {
      const feature = event.features?.[0];
      if (!feature || feature.geometry.type !== 'Point') return;
      const props = feature.properties as { name: string; n: number; kind: string };
      const label = props.name.replace(/([a-z])([A-Z])/g, '$1 $2');
      const kind = props.kind === 'broader-area' ? 'Broader Piute sampling area' : 'Named survey location · approximate 1 km² plot';
      new maplibregl.Popup({ offset: 16 }).setLngLat(feature.geometry.coordinates as [number, number])
        .setHTML(`<strong>${label}</strong><br>${kind}<br>${props.n} genotyped tortoises<br><small>Mean coordinate from USGS records; no plot outline inferred.</small>`).addTo(this.map);
    });
    this.map.on('mouseenter', 'study-site-halo', () => { this.map.getCanvas().style.cursor = 'pointer'; });
    this.map.on('mouseleave', 'study-site-halo', () => { this.map.getCanvas().style.cursor = ''; });
    this.applyStudyVisibility();
  }

  private applyStudyVisibility(): void {
    if (!this.styleReady || !this.map.getLayer('study-site-halo')) return;
    const visibility = (ids: string[], show: boolean) => ids.forEach(id => this.map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none'));
    visibility(['study-site-halo', 'study-site-core'], this.studyVisibility.sites);
    visibility(['study-highway-line'], this.studyVisibility.highway);
    visibility(['study-railway-line'], this.studyVisibility.railway);
    visibility(['study-solar-fill', 'study-solar-outline'], this.studyVisibility.solar);
    this.placeMarkers.forEach(marker => marker.classList.toggle('is-muted', this.studyVisibility.sites));
  }

  setStudyLayer(layer: StudyLayer, visible: boolean): void {
    this.studyVisibility[layer] = visible;
    this.applyStudyVisibility();
  }

  getStudyLayer(layer: StudyLayer): boolean { return this.studyVisibility[layer]; }

  private handleError(message: string): void {
    if (/eox|s2cloudless|satellite/i.test(message)) {
      this.imageFailures++;
      if (this.imageFailures >= 3 && this.basemap === 'satellite') {
        this.setBasemap('hillshade');
        this.onFallback();
        this.onStatus({ level: 'warning', message: 'IMAGERY UNAVAILABLE · HILLSHADE SHOWN' });
      }
    } else if (/mapterhorn|terrain|dem/i.test(message)) {
      this.demFailures++;
      if (this.demFailures >= 3) {
        this.map.setTerrain(null);
        this.onStatus({ level: 'warning', message: 'ELEVATION SERVICE UNAVAILABLE · FLAT MAP SHOWN' });
      }
    } else if (!this.styleReady) {
      this.onStatus({ level: 'warning', message: 'BASE MAP UNAVAILABLE · CHECK NETWORK' });
    }
  }

  setBasemap(value: Basemap): void {
    if (value === this.basemap && this.renderedBasemap === value) return;
    this.basemap = value;
    this.applyBasemap();
  }

  getBasemap(): Basemap { return this.basemap; }

  private applyBasemap(): void {
    if (!this.styleReady) return;
    const map = this.map;
    const ids = ['atlas-satellite-layer', 'atlas-relief-layer', 'atlas-gray-relief-layer', 'atlas-hillshade-layer'];
    const target = this.basemap;
    const show = (id: string, visible: boolean) => map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    const paint = (duration: number) => {
      for (const id of ids) {
        const property = id === 'atlas-satellite-layer' ? 'raster-opacity'
          : id === 'atlas-hillshade-layer' ? 'hillshade-exaggeration' : 'color-relief-opacity';
        const active = id === 'atlas-satellite-layer' && target === 'satellite'
          || id === 'atlas-relief-layer' && target === 'elevation'
          || (id === 'atlas-gray-relief-layer' || id === 'atlas-hillshade-layer') && target === 'hillshade';
        map.setPaintProperty(id, `${property}-transition` as any, { duration });
        map.setPaintProperty(id, property as any, active ? (id === 'atlas-hillshade-layer' ? 0.62 : 1) : 0);
      }
    };
    if (!this.renderedBasemap || reducedMotion()) {
      ids.forEach(id => show(id, id === 'atlas-satellite-layer' && target === 'satellite'
        || id === 'atlas-relief-layer' && target === 'elevation'
        || (id === 'atlas-gray-relief-layer' || id === 'atlas-hillshade-layer') && target === 'hillshade'));
      paint(0);
      this.renderedBasemap = target;
      return;
    }
    const token = ++this.basemapToken;
    window.clearTimeout(this.basemapCleanup);
    const targetIds = target === 'satellite' ? ['atlas-satellite-layer'] : target === 'elevation' ? ['atlas-relief-layer'] : ['atlas-gray-relief-layer', 'atlas-hillshade-layer'];
    targetIds.forEach(id => show(id, true));
    const source = target === 'satellite' ? 'atlas-satellite' : 'atlas-dem';
    const begin = () => {
      if (token !== this.basemapToken) return;
      paint(BASEMAP_FADE_MS);
      this.basemapCleanup = window.setTimeout(() => {
        if (token !== this.basemapToken) return;
        ids.forEach(id => show(id, targetIds.includes(id)));
        this.renderedBasemap = target;
      }, BASEMAP_FADE_MS + 80);
    };
    if (map.isSourceLoaded(source)) begin();
    else {
      const onSource = () => {
        if (!map.isSourceLoaded(source)) return;
        map.off('sourcedata', onSource);
        window.clearTimeout(timeout);
        begin();
      };
      map.on('sourcedata', onSource);
      const timeout = window.setTimeout(() => { map.off('sourcedata', onSource); begin(); }, 1800);
    }
  }

  setRoadsVisible(visible: boolean): void {
    this.roadsVisible = visible;
    if (!this.styleReady) return;
    for (const layer of this.map.getStyle().layers ?? []) {
      const sourceLayer = 'source-layer' in layer ? layer['source-layer'] : undefined;
      if (layer.type === 'symbol' || sourceLayer === 'transportation') {
        this.map.setLayoutProperty(layer.id, 'visibility', visible ? 'visible' : 'none');
      }
    }
  }

  getRoadsVisible(): boolean { return this.roadsVisible; }

  setTerrainVisible(visible: boolean): void {
    this.terrainVisible = visible;
    if (!this.styleReady) return;
    this.map.setTerrain(visible ? { source: 'atlas-terrain-dem', exaggeration: 1.25 } : null);
  }

  getTerrainVisible(): boolean { return this.terrainVisible; }

  flyTo(place: Place): void {
    this.moveToScene({ center: place.coordinates, zoom: place.zoom, bearing: place.bearing, pitch: place.pitch });
  }

  moveToScene(scene: CameraScene): void {
    this.stopOrbit();
    const offset: [number, number] = window.innerWidth <= 760 ? [0, -95] : [15, -18];
    const current = this.map.getCenter();
    const eastKm = (current.lng - scene.center[0]) * 91;
    const northKm = (current.lat - scene.center[1]) * 111;
    const distanceKm = Math.hypot(eastKm, northKm);
    const common = { center: scene.center, zoom: scene.zoom, bearing: scene.bearing, pitch: scene.pitch, offset, essential: true };
    if (reducedMotion()) this.map.jumpTo(common);
    else if (distanceKm > 45) this.map.flyTo({ ...common, speed: 0.65, curve: 1.15, maxDuration: 3400 });
    else this.map.easeTo({ ...common, duration: 2300, easing: t => t * t * (3 - 2 * t) });
  }

  overview(): void {
    this.stopOrbit();
    const mobile = window.innerWidth <= 760;
    this.map.fitBounds(studyBounds, { padding: mobile ? { top: 115, bottom: 280, left: 22, right: 22 } : { top: 80, bottom: 100, left: 195, right: 170 }, pitch: 49, bearing: -17, duration: reducedMotion() ? 0 : 2400, essential: true });
  }

  startOrbit(): void {
    if (this.orbitFrame) return;
    this.orbitTime = performance.now();
    this.onOrbitChange(true);
    const tick = (now: number) => {
      const elapsed = now - this.orbitTime;
      if (elapsed >= 32) {
        this.orbitTime = now;
        this.map.setBearing(this.map.getBearing() + Math.min(elapsed, 80) * 0.003);
      }
      this.orbitFrame = requestAnimationFrame(tick);
    };
    this.orbitFrame = requestAnimationFrame(tick);
  }

  stopOrbit(): void {
    const wasOrbiting = !!this.orbitFrame;
    if (this.orbitFrame) cancelAnimationFrame(this.orbitFrame);
    this.orbitFrame = 0;
    if (wasOrbiting) this.onOrbitChange(false);
  }

  isOrbiting(): boolean { return this.orbitFrame !== 0; }
}
