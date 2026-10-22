import * as maplibregl from 'maplibre-gl';
import type { Map as MapLibreMap } from 'maplibre-gl';
import type { Protocol } from 'pmtiles';
import type { ArchiveInspection, PmtilesLayerConfig } from './pmtiles';

let pmtilesProtocol: Protocol | null = null;
export async function preparePmtiles(): Promise<void> {
  if (pmtilesProtocol) return;
  const { Protocol } = await import('pmtiles');
  const protocol = new Protocol({ metadata: false });
  maplibregl.addProtocol('pmtiles', protocol.tile as maplibregl.AddProtocolAction);
  pmtilesProtocol = protocol;
}

export type Basemap = 'satellite' | 'elevation' | 'hillshade';
export type Camera = { center: [number, number]; zoom: number; pitch: number; bearing: number };
export type Preset = Camera & { id: string; name: string; subtitle: string };
export type SandboxStatus = { level: 'ready' | 'loading' | 'warning'; message: string };
export type GeoJsonData = { type: 'FeatureCollection'; features: Record<string, unknown>[] };

export const presets: Preset[] = [
  { id: 'grand-canyon', name: 'Grand Canyon', subtitle: 'Layered canyon terrain', center: [-112.113, 36.107], zoom: 10.25, pitch: 63, bearing: -23 },
  { id: 'death-valley', name: 'Death Valley', subtitle: 'Basin and ranges', center: [-116.825, 36.532], zoom: 10.1, pitch: 62, bearing: 24 },
  { id: 'yosemite', name: 'Yosemite Valley', subtitle: 'Granite relief', center: [-119.593, 37.745], zoom: 11.2, pitch: 67, bearing: -28 },
];

const STYLE = 'https://tiles.openfreemap.org/styles/liberty';
const SATELLITE = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg';
const DEM = 'https://tiles.mapterhorn.com/tilejson.json';
const FADE = 600;
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const emptyCollection = (): GeoJsonData => ({ type: 'FeatureCollection', features: [] });
const escapeCredit = (value: string): string => value.replace(/[&<>"']/g, character =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);
const safeCredit = (value: string): string => {
  const body = new DOMParser().parseFromString(value, 'text/html').body;
  body.querySelectorAll('script,style').forEach(element => element.remove());
  return escapeCredit(body.textContent?.trim() ?? value);
};

const elevationColors: unknown[] = [
  'interpolate', ['linear'], ['elevation'],
  -100, '#254b54', 0, '#507779', 400, '#8b9b8d', 900, '#d0b898',
  1400, '#d4aa80', 2000, '#a98573', 2700, '#d2cec0', 3800, '#f0eee4',
];

export class SandboxMap {
  readonly map: MapLibreMap;
  private basemap: Basemap = 'satellite';
  private renderedBasemap: Basemap | null = null;
  private styleReady = false;
  private transitionToken = 0;
  private cleanupTimer = 0;
  private orbitFrame = 0;
  private orbitTime = 0;
  private terrainScale = 1.2;
  private imported: GeoJsonData = emptyCollection();
  private importedOpacity = 1;
  private importedPolygonStyle: 'default' | 'grid' = 'default';
  private importedPointMode: 'maplibre' | 'deck' = 'maplibre';
  private derived: GeoJsonData = emptyCollection();
  private pmtilesLayers: PmtilesLayerConfig[] = [];
  private tiffVisible = false;
  private tiffOpacity = 0.8;
  private sourceFailures = 0;
  private onStatus: (status: SandboxStatus) => void;
  private onCamera: (camera: Camera) => void;
  private onOrbit: (active: boolean) => void;
  private onPmtilesError: (id: string, message: string) => void;

  constructor(container: HTMLElement, callbacks: {
    status: (status: SandboxStatus) => void;
    camera: (camera: Camera) => void;
    orbit: (active: boolean) => void;
    pmtilesError: (id: string, message: string) => void;
  }) {
    this.onStatus = callbacks.status;
    this.onCamera = callbacks.camera;
    this.onOrbit = callbacks.orbit;
    this.onPmtilesError = callbacks.pmtilesError;
    const start = presets[0];
    this.map = new maplibregl.Map({
      container, style: STYLE, center: start.center, zoom: start.zoom,
      pitch: start.pitch, bearing: start.bearing, maxPitch: 85,
      minZoom: 3, maxZoom: 17, renderWorldCopies: false, attributionControl: false,
    });
    this.map.addControl(new maplibregl.NavigationControl({ showZoom: true, showCompass: true, visualizePitch: true }), 'top-right');
    this.map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 110 }), 'bottom-right');
    this.map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    this.map.on('load', () => this.installLayers());
    this.map.on('error', event => this.handleError(String(event.error?.message ?? 'Map service error')));
    this.map.on('dragstart', () => this.stopOrbit());
    this.map.on('wheel', () => this.stopOrbit());
    this.map.on('moveend', () => this.onCamera(this.getCamera()));
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.stopOrbit(); });
  }

  private installLayers(): void {
    const map = this.map;
    const before = map.getStyle().layers?.find(layer => layer.type === 'symbol')?.id;
    map.addSource('lab-satellite', { type: 'raster', tiles: [SATELLITE], tileSize: 256, maxzoom: 13,
      attribution: '<a href="https://cloudless.eox.at/" target="_blank" rel="noopener">EOxCloudless</a> modified Copernicus Sentinel data 2020' });
    map.addSource('lab-visual-dem', { type: 'raster-dem', url: DEM,
      attribution: '<a href="https://mapterhorn.com/attribution/" target="_blank" rel="noopener">Mapterhorn elevation sources</a>' });
    map.addSource('lab-terrain-dem', { type: 'raster-dem', url: DEM,
      attribution: '<a href="https://mapterhorn.com/attribution/" target="_blank" rel="noopener">Mapterhorn elevation sources</a>' });
    map.addLayer({ id: 'lab-satellite-layer', type: 'raster', source: 'lab-satellite', paint: {
      'raster-opacity': 1, 'raster-opacity-transition': { duration: FADE }, 'raster-fade-duration': 250,
    } }, before);
    map.addLayer({ id: 'lab-elevation-layer', type: 'color-relief', source: 'lab-visual-dem', layout: { visibility: 'none' }, paint: {
      'color-relief-color': elevationColors as any, 'color-relief-opacity': 0,
      'color-relief-opacity-transition': { duration: FADE },
    } }, before);
    map.addLayer({ id: 'lab-gray-layer', type: 'color-relief', source: 'lab-visual-dem', layout: { visibility: 'none' }, paint: {
      'color-relief-color': ['interpolate', ['linear'], ['elevation'], -100, '#405458', 500, '#8d9993', 1700, '#c7c4b8', 3500, '#f1f0e8'] as any,
      'color-relief-opacity': 0, 'color-relief-opacity-transition': { duration: FADE },
    } }, before);
    map.addLayer({ id: 'lab-shade-layer', type: 'hillshade', source: 'lab-visual-dem', layout: { visibility: 'none' }, paint: {
      'hillshade-illumination-direction': 320, 'hillshade-shadow-color': '#203b3b',
      'hillshade-highlight-color': '#f2ecdc', 'hillshade-accent-color': '#657575',
      'hillshade-exaggeration': 0, 'hillshade-exaggeration-transition': { duration: FADE },
    } }, before);
    map.setTerrain({ source: 'lab-terrain-dem', exaggeration: this.terrainScale });

    map.addSource('lab-import', { type: 'geojson', data: this.imported as any });
    map.addLayer({ id: 'lab-import-fill', type: 'fill', source: 'lab-import', paint: { 'fill-color': this.importedPolygonStyle === 'grid' ? '#88efb8' : '#f5a96e', 'fill-opacity': (this.importedPolygonStyle === 'grid' ? 0.68 : 0.3) * this.importedOpacity, 'fill-outline-color': this.importedPolygonStyle === 'grid' ? '#d4ffe2' : '#ffce9a' } });
    map.addLayer({ id: 'lab-import-line', type: 'line', source: 'lab-import', paint: { 'line-color': this.importedPolygonStyle === 'grid' ? '#b7ffce' : '#ffc18d', 'line-width': this.importedPolygonStyle === 'grid' ? 0.45 : 3, 'line-opacity': this.importedOpacity } });
    map.addLayer({ id: 'lab-import-points', type: 'circle', source: 'lab-import', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 6, 'circle-color': '#ffd39f', 'circle-stroke-width': 2, 'circle-stroke-color': '#172b2b', 'circle-opacity': 0.95 } });
    this.applyImportedPointMode();
    this.setOverlayOpacity(this.importedOpacity);
    map.addSource('lab-derived', { type: 'geojson', data: this.derived as any });
    map.addLayer({ id: 'lab-derived-fill', type: 'fill', source: 'lab-derived', paint: { 'fill-color': '#af9df4', 'fill-opacity': 0.25, 'fill-outline-color': '#ded4ff' } });
    map.addLayer({ id: 'lab-derived-line', type: 'line', source: 'lab-derived', paint: { 'line-color': '#dfd3ff', 'line-width': 3, 'line-dasharray': [2, 1] } });
    map.addLayer({ id: 'lab-derived-points', type: 'circle', source: 'lab-derived', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 7, 'circle-color': '#c9b9ff', 'circle-stroke-width': 2, 'circle-stroke-color': '#241d3f' } });
    this.styleReady = true;
    this.applyBasemap();
    this.onCamera(this.getCamera());
    this.onStatus({ level: 'ready', message: 'LIVE TERRAIN · READY TO EXPLORE' });
  }

  private handleError(message: string): void {
    if (/eox|s2cloudless|satellite/i.test(message) && this.basemap === 'satellite') {
      this.sourceFailures++;
      if (this.sourceFailures >= 3) {
        this.setBasemap('hillshade');
        this.onStatus({ level: 'warning', message: 'SATELLITE TILES UNAVAILABLE · HILLSHADE SHOWN' });
      }
    } else if (/mapterhorn|terrain|dem/i.test(message)) {
      this.onStatus({ level: 'warning', message: 'ELEVATION TILES UNAVAILABLE · CHECK CONNECTION' });
    } else if (!this.styleReady) {
      this.onStatus({ level: 'warning', message: 'BASE MAP UNAVAILABLE · CHECK CONNECTION' });
    }
  }

  getBasemap(): Basemap { return this.basemap; }
  setBasemap(value: Basemap): void {
    if (value === this.basemap && this.renderedBasemap === value) return;
    this.basemap = value;
    this.applyBasemap();
  }

  private applyBasemap(): void {
    if (!this.styleReady) return;
    const map = this.map;
    const target = this.basemap;
    const ids = ['lab-satellite-layer', 'lab-elevation-layer', 'lab-gray-layer', 'lab-shade-layer'];
    const active = target === 'satellite' ? ['lab-satellite-layer'] : target === 'elevation' ? ['lab-elevation-layer'] : ['lab-gray-layer', 'lab-shade-layer'];
    const show = (id: string, visible: boolean) => map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    const paint = (duration: number) => ids.forEach(id => {
      const property = id === 'lab-satellite-layer' ? 'raster-opacity' : id === 'lab-shade-layer' ? 'hillshade-exaggeration' : 'color-relief-opacity';
      map.setPaintProperty(id, `${property}-transition` as any, { duration });
      map.setPaintProperty(id, property as any, active.includes(id) ? (id === 'lab-shade-layer' ? 0.65 : 1) : 0);
    });
    if (!this.renderedBasemap || reduceMotion()) {
      ids.forEach(id => show(id, active.includes(id)));
      paint(0);
      this.renderedBasemap = target;
      return;
    }
    const token = ++this.transitionToken;
    window.clearTimeout(this.cleanupTimer);
    active.forEach(id => show(id, true));
    const source = target === 'satellite' ? 'lab-satellite' : 'lab-visual-dem';
    const begin = () => {
      if (token !== this.transitionToken) return;
      paint(FADE);
      this.cleanupTimer = window.setTimeout(() => {
        if (token !== this.transitionToken) return;
        ids.forEach(id => show(id, active.includes(id)));
        this.renderedBasemap = target;
      }, FADE + 70);
    };
    if (map.isSourceLoaded(source)) begin();
    else {
      const onData = () => {
        if (!map.isSourceLoaded(source)) return;
        map.off('sourcedata', onData);
        window.clearTimeout(timeout);
        begin();
      };
      map.on('sourcedata', onData);
      const timeout = window.setTimeout(() => { map.off('sourcedata', onData); begin(); }, 1800);
    }
  }

  getCamera(): Camera {
    const center = this.map.getCenter();
    return { center: [center.lng, center.lat], zoom: this.map.getZoom(), pitch: this.map.getPitch(), bearing: this.map.getBearing() };
  }

  goTo(camera: Camera): void {
    this.stopOrbit();
    const current = this.map.getCenter();
    const distance = Math.hypot((camera.center[0] - current.lng) * 90, (camera.center[1] - current.lat) * 111);
    const options = { center: camera.center, zoom: camera.zoom, pitch: camera.pitch, bearing: camera.bearing, essential: true };
    if (reduceMotion()) this.map.jumpTo(options);
    else if (distance > 70) this.map.flyTo({ ...options, speed: 0.7, curve: 1.2, maxDuration: 3600 });
    else this.map.easeTo({ ...options, duration: 2200, easing: t => t * t * (3 - 2 * t) });
  }

  setPitch(pitch: number): void { this.stopOrbit(); this.map.setPitch(pitch); }
  setTerrainScale(scale: number): void {
    this.terrainScale = scale;
    if (this.styleReady) this.map.setTerrain(scale > 0 ? { source: 'lab-terrain-dem', exaggeration: scale } : null);
  }
  getTerrainScale(): number { return this.terrainScale; }

  setImported(data: GeoJsonData): void {
    this.imported = data;
    if (this.styleReady) (this.map.getSource('lab-import') as maplibregl.GeoJSONSource).setData(data as any);
  }
  clearImported(): void { this.setImported(emptyCollection()); }
  getImported(): GeoJsonData { return this.imported; }
  setImportedPointMode(mode: 'maplibre' | 'deck'): void {
    this.importedPointMode = mode;
    this.applyImportedPointMode();
  }
  private applyImportedPointMode(): void {
    if (this.map.getLayer('lab-import-points'))
      this.map.setLayoutProperty('lab-import-points', 'visibility', this.importedPointMode === 'deck' ? 'none' : 'visible');
  }
  getPmtilesLayers(): PmtilesLayerConfig[] { return this.pmtilesLayers.map(layer => ({ ...layer })); }

  showGeoTiff(dataUrl: string, bounds: [number, number, number, number], attribution: string, tilesUrl?: string): void {
    if (!this.styleReady) throw new Error('Wait for the base map to finish loading.');
    this.removeGeoTiff();
    const [west, south, east, north] = bounds;
    this.map.addSource('lab-geotiff', tilesUrl ? { type: 'raster', tiles: [tilesUrl], tileSize: 256,
      minzoom: 3, maxzoom: 9, bounds, ...(attribution ? { attribution } : {}) } :
      { type: 'image', url: dataUrl, coordinates: [[west, north], [east, north], [east, south], [west, south]],
        ...(attribution ? { attribution } : {}) });
    this.map.addLayer({ id: 'lab-geotiff-layer', type: 'raster', source: 'lab-geotiff',
      paint: { 'raster-opacity': this.tiffOpacity, 'raster-fade-duration': 0 } }, 'lab-import-fill');
    this.tiffVisible = true;
  }
  setGeoTiffVisibility(visible: boolean): void {
    this.tiffVisible = visible;
    if (this.map.getLayer('lab-geotiff-layer')) this.map.setLayoutProperty('lab-geotiff-layer', 'visibility', visible ? 'visible' : 'none');
  }
  setGeoTiffOpacity(opacity: number): void {
    this.tiffOpacity = Math.max(0, Math.min(1, opacity));
    if (this.map.getLayer('lab-geotiff-layer')) this.map.setPaintProperty('lab-geotiff-layer', 'raster-opacity', this.tiffOpacity);
  }
  removeGeoTiff(): void {
    if (this.map.getLayer('lab-geotiff-layer')) this.map.removeLayer('lab-geotiff-layer');
    if (this.map.getSource('lab-geotiff')) this.map.removeSource('lab-geotiff');
    this.tiffVisible = false;
  }

  addPmtilesLayer(inspection: ArchiveInspection, sourceLayer: string | null, userAttribution: string, tileSize: 256 | 512): PmtilesLayerConfig {
    if (!this.styleReady) throw new Error('Wait for the base map to finish loading.');
    if (!pmtilesProtocol) throw new Error('Inspect the archive before adding it.');
    if (this.pmtilesLayers.length >= 3) throw new Error('Terrain Lab supports up to three hosted PMTiles layers at once.');
    if (inspection.kind === 'vector' && !sourceLayer) throw new Error('Choose or enter a vector source layer.');
    if (inspection.kind === 'vector' && inspection.sourceLayers.length && !inspection.sourceLayers.includes(sourceLayer!)) {
      throw new Error('That source layer is not listed in the archive metadata.');
    }
    if (this.pmtilesLayers.some(layer => layer.url === inspection.url)) {
      throw new Error('This archive is already on the map. Remove it before selecting another source layer.');
    }
    const attribution = [inspection.attribution, userAttribution.trim()].filter(Boolean).map(safeCredit).join(' · ');
    if (!attribution) throw new Error('Enter attribution for this archive before adding it.');
    const id = `lab-pmtiles-${crypto.randomUUID()}`;
    const config: PmtilesLayerConfig = {
      id, url: inspection.url, name: inspection.name, kind: inspection.kind, tileType: inspection.tileType,
      sourceLayer, attribution, requiredAttribution: inspection.attribution, bounds: inspection.bounds,
      minZoom: inspection.minZoom, maxZoom: inspection.maxZoom, tileSize, visible: true, opacity: 0.8,
    };
    const map = this.map;
    const sourceId = `${id}-source`;
    const before = 'lab-import-fill';
    inspection.source.onFailure = message => this.onPmtilesError(id, message);
    pmtilesProtocol.add(inspection.archive);
    try {
      if (config.kind === 'raster') {
        map.addSource(sourceId, { type: 'raster', url: `pmtiles://${config.url}`, tileSize,
          minzoom: config.minZoom, maxzoom: config.maxZoom, bounds: config.bounds, attribution });
        map.addLayer({ id: `${id}-raster`, source: sourceId, type: 'raster',
          paint: { 'raster-opacity': config.opacity, 'raster-fade-duration': 150 } }, before);
      } else {
        map.addSource(sourceId, { type: 'vector', url: `pmtiles://${config.url}`,
          minzoom: config.minZoom, maxzoom: config.maxZoom, bounds: config.bounds, attribution,
          ...(config.tileType === 'MLT vector' ? { encoding: 'mlt' as const } : {}) });
        const shared = { source: sourceId, 'source-layer': sourceLayer! };
        map.addLayer({ id: `${id}-fill`, ...shared, type: 'fill', filter: ['==', ['geometry-type'], 'Polygon'],
          paint: { 'fill-color': '#68d4ce', 'fill-opacity': config.opacity * 0.32, 'fill-outline-color': '#a4f0e2' } }, before);
        map.addLayer({ id: `${id}-line`, ...shared, type: 'line', filter: ['==', ['geometry-type'], 'LineString'],
          paint: { 'line-color': '#7fe4d9', 'line-width': 2.5, 'line-opacity': config.opacity } }, before);
        map.addLayer({ id: `${id}-point`, ...shared, type: 'circle', filter: ['==', ['geometry-type'], 'Point'],
          paint: { 'circle-color': '#9bece0', 'circle-radius': 5, 'circle-stroke-color': '#173a3a',
            'circle-stroke-width': 1.5, 'circle-opacity': config.opacity, 'circle-stroke-opacity': config.opacity } }, before);
      }
      this.pmtilesLayers.push(config);
      return { ...config };
    } catch (error) {
      for (const suffix of ['raster', 'fill', 'line', 'point']) if (map.getLayer(`${id}-${suffix}`)) map.removeLayer(`${id}-${suffix}`);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      if (!this.pmtilesLayers.some(layer => layer.url === inspection.url)) pmtilesProtocol.tiles.delete(inspection.url);
      throw error;
    }
  }

  setPmtilesVisibility(id: string, visible: boolean): void {
    const layer = this.pmtilesLayers.find(item => item.id === id);
    if (!layer) return;
    layer.visible = visible;
    for (const suffix of ['raster', 'fill', 'line', 'point']) {
      const layerId = `${id}-${suffix}`;
      if (this.map.getLayer(layerId)) this.map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
    }
  }

  setPmtilesOpacity(id: string, opacity: number): void {
    const layer = this.pmtilesLayers.find(item => item.id === id);
    if (!layer) return;
    layer.opacity = Math.max(0, Math.min(1, opacity));
    const paint: [string, string, number][] = layer.kind === 'raster' ? [['raster', 'raster-opacity', layer.opacity]] :
      [['fill', 'fill-opacity', layer.opacity * 0.32], ['line', 'line-opacity', layer.opacity],
        ['point', 'circle-opacity', layer.opacity], ['point', 'circle-stroke-opacity', layer.opacity]];
    for (const [suffix, property, value] of paint) this.map.setPaintProperty(`${id}-${suffix}`, property as any, value);
  }

  removePmtilesLayer(id: string): void {
    const index = this.pmtilesLayers.findIndex(item => item.id === id);
    if (index < 0) return;
    const [layer] = this.pmtilesLayers.splice(index, 1);
    for (const suffix of ['raster', 'fill', 'line', 'point']) if (this.map.getLayer(`${id}-${suffix}`)) this.map.removeLayer(`${id}-${suffix}`);
    this.map.removeSource(`${id}-source`);
    if (!this.pmtilesLayers.some(item => item.url === layer.url)) pmtilesProtocol?.tiles.delete(layer.url);
  }
  setDerived(data: GeoJsonData): void {
    this.derived = data;
    if (this.styleReady) (this.map.getSource('lab-derived') as maplibregl.GeoJSONSource).setData(data as any);
  }
  setImportedPolygonStyle(style: 'default' | 'grid'): void {
    this.importedPolygonStyle = style;
    if (!this.styleReady) return;
    this.map.setPaintProperty('lab-import-fill', 'fill-color', style === 'grid' ? '#88efb8' : '#f5a96e');
    this.map.setPaintProperty('lab-import-fill', 'fill-outline-color', style === 'grid' ? '#d4ffe2' : '#ffce9a');
    this.map.setPaintProperty('lab-import-line', 'line-color', style === 'grid' ? '#b7ffce' : '#ffc18d');
    this.map.setPaintProperty('lab-import-line', 'line-width', style === 'grid' ? 0.45 : 3);
    this.setOverlayOpacity(this.importedOpacity);
  }
  setOverlayOpacity(value: number): void {
    this.importedOpacity = Math.max(0, Math.min(1, value));
    if (!this.styleReady) return;
    this.map.setPaintProperty('lab-import-fill', 'fill-opacity', (this.importedPolygonStyle === 'grid' ? 0.68 : 0.3) * this.importedOpacity);
    this.map.setPaintProperty('lab-import-line', 'line-opacity', this.importedOpacity);
    this.map.setPaintProperty('lab-import-points', 'circle-opacity', this.importedOpacity);
    this.map.setPaintProperty('lab-import-points', 'circle-stroke-opacity', this.importedOpacity);
  }
  getImportedOpacity(): number { return this.importedOpacity; }
  fitBounds(bounds: [[number, number], [number, number]]): void {
    this.stopOrbit();
    this.map.fitBounds(bounds, { padding: window.innerWidth < 760 ? { top: 140, bottom: 260, left: 25, right: 25 } : { top: 100, bottom: 110, left: 230, right: 250 },
      duration: reduceMotion() ? 0 : 1800, pitch: Math.min(this.map.getPitch(), 55), essential: true });
  }

  startOrbit(): void {
    if (this.orbitFrame) return;
    this.orbitTime = performance.now();
    this.onOrbit(true);
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
    const wasActive = !!this.orbitFrame;
    if (this.orbitFrame) cancelAnimationFrame(this.orbitFrame);
    this.orbitFrame = 0;
    if (wasActive) this.onOrbit(false);
  }
  isOrbiting(): boolean { return this.orbitFrame !== 0; }
}
