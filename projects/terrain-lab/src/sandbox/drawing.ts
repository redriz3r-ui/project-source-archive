import type { Geoman, DrawModeName, EditModeName, PartialLayerStyle } from '@geoman-io/maplibre-geoman-free';
import type { Map as MapLibreMap } from 'maplibre-gl';
import type { GeoJsonData } from './map';

export const drawTools = [
  { id: 'marker', label: 'Marker', hint: 'Click to place a point' },
  { id: 'line', label: 'Line', hint: 'Click vertices; double-click to finish' },
  { id: 'polygon', label: 'Polygon', hint: 'Click vertices; click first point to finish' },
  { id: 'rectangle', label: 'Rectangle', hint: 'Click two opposite corners' },
  { id: 'circle', label: 'Circle', hint: 'Click center, then radius' },
  { id: 'ellipse', label: 'Ellipse', hint: 'Click center, then two axes' },
  { id: 'circle_marker', label: 'Circle marker', hint: 'Click to place a symbol' },
  { id: 'text_marker', label: 'Text marker', hint: 'Click, type, then click away' },
] as const satisfies ReadonlyArray<{ id: DrawModeName; label: string; hint: string }>;

export const editTools = [
  { id: 'change', label: 'Edit vertices', hint: 'Drag vertices to reshape a feature' },
  { id: 'drag', label: 'Move', hint: 'Drag a feature to reposition it' },
  { id: 'rotate', label: 'Rotate', hint: 'Select and rotate a feature' },
  { id: 'cut', label: 'Cut', hint: 'Draw a cut through a polygon' },
  { id: 'delete', label: 'Remove', hint: 'Click a drawn feature to remove it' },
] as const satisfies ReadonlyArray<{ id: EditModeName; label: string; hint: string }>;

export type ActiveTool = { kind: 'draw'; id: DrawModeName } | { kind: 'edit'; id: EditModeName } | null;

export class DrawingWorkspace {
  private geoman: Geoman | null = null;
  private loading: Promise<void> | null = null;
  private ready = false;
  private onChange: () => void;
  private map: MapLibreMap;

  constructor(map: MapLibreMap, onChange: () => void) {
    this.map = map;
    this.onChange = onChange;
  }

  async initialize(): Promise<void> {
    if (this.ready) return;
    if (this.loading) return this.loading;
    this.loading = this.load();
    try { await this.loading; } finally { this.loading = null; }
  }

  private async load(): Promise<void> {
    const [{ Geoman }] = await Promise.all([
      import('@geoman-io/maplibre-geoman-free'),
      import('@geoman-io/maplibre-geoman-free/dist/maplibre-geoman.css'),
    ]);
    const labelStyle: PartialLayerStyle[] = [{
      type: 'symbol',
      layout: { 'text-field': ['get', '__gm_text'], 'text-justify': 'center', 'text-font': ['Noto Sans Regular'] },
      paint: { 'text-color': '#e9f7e6', 'text-halo-color': '#173331', 'text-halo-width': 2 },
    }];
    const geoman = new Geoman(this.map, {
      settings: { useControlsUi: false },
      layerStyles: { text_marker: { gm_main: labelStyle, gm_temporary: labelStyle } },
    });
    this.geoman = geoman;
    geoman.setGlobalEventsListener(event => {
      if (event.name === 'gm:create' || event.name === 'gm:remove' || event.name.includes('modetoggled') || event.name.endsWith('end')) {
        queueMicrotask(this.onChange);
      }
    });
    const instance = await geoman.waitForGeomanLoaded();
    if (!instance || !geoman.loaded) throw new Error('Drawing tools could not initialize.');
    this.ready = true;
    this.onChange();
  }

  isReady(): boolean { return this.ready; }

  activeTool(): ActiveTool {
    if (!this.geoman || !this.ready) return null;
    const draw = this.geoman.getActiveDrawModes()[0];
    if (draw) return { kind: 'draw', id: draw };
    const edit = this.geoman.getActiveEditModes()[0];
    return edit ? { kind: 'edit', id: edit } : null;
  }

  async select(tool: ActiveTool): Promise<void> {
    if (!this.ready) await this.initialize();
    const geoman = this.geoman!;
    const active = this.activeTool();
    await geoman.disableAllModes();
    if (!tool || (active?.kind === tool.kind && active.id === tool.id)) {
      this.onChange();
      return;
    }
    if (tool.kind === 'draw') await geoman.enableDraw(tool.id);
    else await geoman.enableMode('edit', tool.id);
    this.onChange();
  }

  async stop(): Promise<void> {
    if (!this.ready) return;
    await this.geoman!.disableAllModes();
    this.onChange();
  }

  data(): GeoJsonData {
    if (!this.ready) return { type: 'FeatureCollection', features: [] };
    return this.geoman!.features.exportGeoJson() as unknown as GeoJsonData;
  }

  async clear(): Promise<void> {
    if (!this.ready) return;
    await this.geoman!.disableAllModes();
    await this.geoman!.features.deleteAll();
    this.onChange();
  }
}
