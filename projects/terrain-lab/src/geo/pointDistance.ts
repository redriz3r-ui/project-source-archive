import type { LineString, Point } from 'geojson';
import { assertSource, distanceLabel, type AnalysisResult, type SourceFeature } from './analysisCommon.ts';

const pointTypes = new Set(['Point']);

export async function computePointDistance(first: SourceFeature, second?: SourceFeature): Promise<AnalysisResult> {
  if (!first) throw new Error('Choose a first point.');
  if (!second) throw new Error('Choose a second point.');
  if (first.key === second.key) throw new Error('Choose two different points.');
  const a = assertSource(first, pointTypes).geometry as Point;
  const b = assertSource(second, pointTypes).geometry as Point;
  const { distance } = await import('@turf/distance');
  const value = distance(a, b, { units: 'kilometers' }) * 1000;
  const geometry: LineString = { type: 'LineString', coordinates: [a.coordinates.slice(0, 2), b.coordinates.slice(0, 2)] };
  if (!Number.isFinite(value)) throw new Error('The calculation did not produce a valid result.');
  const sourceLabel = `${first.label} → ${second.label}`;
  return { id: crypto.randomUUID(), title: 'Point distance', valueLabel: distanceLabel(value), sourceLabel, feature: {
    type: 'Feature', geometry, properties: {
      classification: 'computed geometry', observed: false, operation: 'distance', value,
      unit: 'meters', source: sourceLabel, method: 'Turf.js geodesic calculation on WGS84 coordinates',
      computedAt: new Date().toISOString(),
    },
  } };
}
