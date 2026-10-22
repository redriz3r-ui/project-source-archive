import type { Feature, Geometry } from 'geojson';

export type SourceFeature = { key: string; label: string; feature: Feature<Geometry> };
export type AnalysisResult = { id: string; title: string; valueLabel: string; sourceLabel: string; feature: Feature<Geometry> };

export const coordinate = (value: unknown): value is number[] => Array.isArray(value) && value.length >= 2 &&
  typeof value[0] === 'number' && typeof value[1] === 'number' && Number.isFinite(value[0]) && Number.isFinite(value[1]) &&
  value[0] >= -180 && value[0] <= 180 && value[1] >= -90 && value[1] <= 90;

function validGeometry(geometry: Geometry): boolean {
  const g = geometry as Geometry & { coordinates?: unknown };
  const line = (value: unknown): value is number[][] => Array.isArray(value) && value.length >= 2 && value.every(coordinate);
  const ring = (value: unknown): value is number[][] => Array.isArray(value) && value.length >= 4 && value.every(coordinate) &&
    value[0][0] === value[value.length - 1][0] && value[0][1] === value[value.length - 1][1];
  const polygon = (value: unknown): boolean => Array.isArray(value) && value.length > 0 && value.every(ring);
  switch (g.type) {
    case 'Point': return coordinate(g.coordinates);
    case 'MultiPoint': return Array.isArray(g.coordinates) && g.coordinates.length > 0 && g.coordinates.every(coordinate);
    case 'LineString': return line(g.coordinates);
    case 'MultiLineString': return Array.isArray(g.coordinates) && g.coordinates.length > 0 && g.coordinates.every(line);
    case 'Polygon': return polygon(g.coordinates);
    case 'MultiPolygon': return Array.isArray(g.coordinates) && g.coordinates.length > 0 && g.coordinates.every(polygon);
    default: return false;
  }
}

export function assertSource(source: SourceFeature, types: Set<string>): Feature<Geometry> {
  const feature = source.feature;
  const geometry = feature?.geometry;
  if (!geometry || !types.has(geometry.type)) throw new Error(`This operation does not support ${geometry?.type ?? 'empty'} geometry.`);
  if (!validGeometry(geometry)) throw new Error(`“${source.label}” has incomplete or invalid WGS84 geometry.`);
  return feature;
}

export const distanceLabel = (meters: number): string => meters < 1000 ? `${meters.toFixed(1)} m` : `${(meters / 1000).toFixed(3)} km`;
