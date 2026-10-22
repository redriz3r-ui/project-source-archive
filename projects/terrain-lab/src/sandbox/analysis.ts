import type { Feature, Geometry, LineString } from 'geojson';
import type { GeoJsonData } from './map';
import { assertSource, coordinate, distanceLabel, type AnalysisResult, type SourceFeature } from '../geo/analysisCommon.ts';
import { computePointDistance } from '../geo/pointDistance.ts';
import { computePolygonArea } from '../geo/polygonArea.ts';

export type { AnalysisResult, SourceFeature } from '../geo/analysisCommon.ts';

export type Operation = 'length' | 'area' | 'distance' | 'buffer';

const supported = new Set(['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']);
const lineTypes = new Set(['LineString', 'MultiLineString']);
const polygonTypes = new Set(['Polygon', 'MultiPolygon']);
function vertexCount(value: unknown, limit = 2000): number {
  if (coordinate(value)) return 1;
  if (!Array.isArray(value)) return 0;
  let count = 0;
  for (const child of value) {
    count += vertexCount(child, limit - count);
    if (count > limit) return count;
  }
  return count;
}


export function sourceFeatures(imported: GeoJsonData, drawn: GeoJsonData): SourceFeature[] {
  return ([['imported', imported], ['drawn', drawn]] as const).flatMap(([origin, data]) => data.features.map((raw, index) => {
    const feature = raw as unknown as Feature<Geometry>;
    const name = feature.properties?.name ?? feature.properties?.title ?? feature.properties?.label;
    const label = typeof name === 'string' && name.trim() ? name.trim().slice(0, 70) : `${origin === 'drawn' ? 'Drawing' : 'Imported'} ${index + 1}`;
    return { key: `${origin}:${index}`, label: `${label} · ${feature.geometry?.type ?? 'empty'}`, feature };
  }));
}

export function supports(operation: Operation, source: SourceFeature): boolean {
  const type = source.feature.geometry?.type;
  return !!type && (operation === 'distance' ? type === 'Point' : operation === 'length' ? lineTypes.has(type) :
    operation === 'area' ? polygonTypes.has(type) : supported.has(type));
}

export async function compute(operation: Operation, first: SourceFeature, second?: SourceFeature, radiusMeters?: number): Promise<AnalysisResult> {
  if (operation === 'distance') return computePointDistance(first, second);
  if (operation === 'area') return computePolygonArea(first);
  let geometry: Geometry;
  let value: number;
  let valueLabel: string;
  let sourceLabel = first.label;
  if (operation === 'length') {
    const feature = assertSource(first, lineTypes);
    const { length } = await import('@turf/length');
    value = length(feature as Feature<LineString>, { units: 'kilometers' }) * 1000;
    valueLabel = distanceLabel(value);
    geometry = structuredClone(feature.geometry);
  } else {
    const feature = assertSource(first, supported);
    if (typeof radiusMeters !== 'number' || !Number.isFinite(radiusMeters) || radiusMeters <= 0 || radiusMeters > 50_000) {
      throw new Error('Enter a buffer radius greater than 0 and no more than 50,000 m.');
    }
    if (vertexCount((feature.geometry as Geometry & { coordinates: unknown }).coordinates) > 2000) {
      throw new Error('This feature is too detailed to buffer here. Simplify it to 2,000 vertices or fewer.');
    }
    const { buffer } = await import('@turf/buffer');
    const buffered = buffer(feature, radiusMeters, { units: 'meters', steps: 16 });
    if (!buffered || buffered.type !== 'Feature') throw new Error('A buffer could not be computed for this geometry.');
    geometry = buffered.geometry;
    value = radiusMeters;
    valueLabel = `Radius ${distanceLabel(radiusMeters)}`;
  }
  if (!Number.isFinite(value) || !geometry) throw new Error('The calculation did not produce a valid result.');
  const title = ({ length: 'Line length', area: 'Polygon area', distance: 'Point distance', buffer: 'Buffer' } as const)[operation];
  const id = crypto.randomUUID();
  return { id, title, valueLabel, sourceLabel, feature: {
    type: 'Feature', geometry, properties: {
      classification: 'computed geometry', observed: false, operation, value,
      unit: 'meters',
      source: sourceLabel, method: 'Turf.js geodesic calculation on WGS84 coordinates',
      computedAt: new Date().toISOString(), ...(operation === 'buffer' ? { radiusMeters } : {}),
    },
  } };
}

export function resultsGeoJson(results: AnalysisResult[]): GeoJsonData {
  return { type: 'FeatureCollection', features: results.map(result => result.feature as unknown as Record<string, unknown>) };
}
