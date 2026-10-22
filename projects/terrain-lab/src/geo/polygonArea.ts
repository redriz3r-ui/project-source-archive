import type { Feature, Geometry, Polygon, MultiPolygon } from 'geojson';
import { assertSource, type AnalysisResult, type SourceFeature } from './analysisCommon.ts';

const polygonTypes = new Set(['Polygon', 'MultiPolygon']);

export async function computePolygonArea(first: SourceFeature): Promise<AnalysisResult> {
  const feature = assertSource(first, polygonTypes) as Feature<Polygon | MultiPolygon>;
  const { area } = await import('@turf/area');
  const value = area(feature);
  const geometry = structuredClone(feature.geometry) as Geometry;
  if (!Number.isFinite(value) || !geometry) throw new Error('The calculation did not produce a valid result.');
  const sourceLabel = first.label;
  const valueLabel = value < 1_000_000 ? `${value.toFixed(1)} m²` : `${(value / 1_000_000).toFixed(3)} km²`;
  return { id: crypto.randomUUID(), title: 'Polygon area', valueLabel, sourceLabel, feature: {
    type: 'Feature', geometry, properties: {
      classification: 'computed geometry', observed: false, operation: 'area', value,
      unit: 'square meters', source: sourceLabel,
      method: 'Turf.js geodesic calculation on WGS84 coordinates', computedAt: new Date().toISOString(),
    },
  } };
}
