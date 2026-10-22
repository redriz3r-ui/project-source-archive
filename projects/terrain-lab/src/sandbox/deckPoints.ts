import { MapLibreOverlay } from '@deck.gl/maplibre';
import { ScatterplotLayer } from '@deck.gl/layers';
import type { Map as MapLibreMap } from 'maplibre-gl';
import type { GeoJsonData } from './map';
import { requireWebGl2 } from './pointCapability';

export type PointDatum = { position: [number, number]; featureIndex: number; properties: Record<string, unknown> };
export type PointStyle = { color: string; radius: number; opacity: number };

export function collectPoints(data: GeoJsonData): PointDatum[] {
  const points: PointDatum[] = [];
  data.features.forEach((raw, featureIndex) => {
    const geometry = raw.geometry as { type?: string; coordinates?: unknown } | null;
    const properties = raw.properties && typeof raw.properties === 'object' ? raw.properties as Record<string, unknown> : {};
    if (geometry?.type === 'Point') points.push({ position: geometry.coordinates as [number, number], featureIndex, properties });
    else if (geometry?.type === 'MultiPoint') for (const position of geometry.coordinates as [number, number][]) points.push({ position, featureIndex, properties });
  });
  return points;
}

function rgba(hex: string, opacity: number): [number, number, number, number] {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error('Choose a valid six-digit point color.');
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16), Math.round(opacity * 255)];
}

export class DeckPoints {
  private overlay: MapLibreOverlay | null = null;
  private points: PointDatum[] = [];
  private style: PointStyle = { color: '#ffc18d', radius: 5, opacity: 0.85 };
  private active = false;
  private interactive = true;

  constructor(private map: MapLibreMap, private onPick: (point: PointDatum) => void,
    private onFailure: (message: string) => void) {}

  setData(data: GeoJsonData): void { this.points = collectPoints(data); this.render(); }
  setStyle(style: PointStyle): void { this.style = style; this.render(); }
  setInteractive(value: boolean): void { if (this.interactive !== value) { this.interactive = value; this.render(); } }

  enable(): void {
    requireWebGl2();
    if (!this.overlay) {
      const overlay = new MapLibreOverlay({ interleaved: false, layers: [],
        onError: error => this.onFailure(error instanceof Error ? error.message : 'deck.gl rendering failed') });
      try { this.map.addControl(overlay); this.overlay = overlay; }
      catch (error) { try { this.map.removeControl(overlay); } catch { /* Control did not attach. */ } throw error; }
    }
    this.active = true;
    this.render();
  }

  disable(): void { this.active = false; this.overlay?.setProps({ layers: [] }); }
  destroy(): void { if (this.overlay) this.map.removeControl(this.overlay); this.overlay = null; this.active = false; }

  private render(): void {
    if (!this.overlay || !this.active) return;
    const { radius, opacity, color } = this.style;
    const layer = new ScatterplotLayer<PointDatum>({
      id: 'terrain-lab-imported-points', data: this.points, getPosition: point => point.position,
      radiusUnits: 'pixels', getRadius: radius, radiusMinPixels: 1, radiusMaxPixels: 40,
      getFillColor: rgba(color, opacity), getLineColor: [20, 38, 38, Math.round(opacity * 255)],
      lineWidthUnits: 'pixels', getLineWidth: 1, stroked: true,
      pickable: this.interactive,
      onClick: info => { if (info.object) this.onPick(info.object); },
    });
    this.overlay.setProps({ layers: [layer] });
  }
}
