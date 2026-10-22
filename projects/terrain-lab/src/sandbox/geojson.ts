import type { GeoJsonData } from './map';

export type Inspection = {
  data: GeoJsonData;
  bounds: [[number, number], [number, number]] | null;
  featureCount: number;
  coordinateCount: number;
  kinds: string[];
  pointCount: number;
};

const geometryTypes = new Set(['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon', 'GeometryCollection']);

export function inspectGeoJson(input: unknown): Inspection {
  if (!input || typeof input !== 'object') throw new Error('The file must contain a GeoJSON object.');
  const root = input as Record<string, unknown>;
  let features: unknown[];
  if (root.type === 'FeatureCollection' && Array.isArray(root.features)) features = root.features;
  else if (root.type === 'Feature') features = [root];
  else if (geometryTypes.has(String(root.type))) features = [{ type: 'Feature', geometry: root, properties: {} }];
  else throw new Error('Use a GeoJSON FeatureCollection, Feature, or geometry.');
  if (features.length > 150000) throw new Error('This file has more than 150,000 features. Split it before importing.');

  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity, coordinateCount = 0;
  const kinds = new Set<string>();
  const visitCoordinates = (value: unknown): void => {
    if (!Array.isArray(value)) throw new Error('A geometry has invalid coordinates.');
    if (typeof value[0] === 'number' && typeof value[1] === 'number') {
      const [lon, lat] = value;
      if (!Number.isFinite(lon) || !Number.isFinite(lat) || lon < -180 || lon > 180 || lat < -90 || lat > 90) {
        throw new Error('Coordinates must be WGS84 longitude and latitude in valid ranges.');
      }
      west = Math.min(west, lon); east = Math.max(east, lon);
      south = Math.min(south, lat); north = Math.max(north, lat);
      coordinateCount++;
      if (coordinateCount > 200000) throw new Error('This file has more than 200,000 coordinates. Split it before importing.');
      return;
    }
    for (const child of value) visitCoordinates(child);
  };
  const visitGeometry = (value: unknown): void => {
    if (value === null) return;
    if (!value || typeof value !== 'object') throw new Error('A feature has an invalid geometry.');
    const geometry = value as Record<string, unknown>;
    const kind = String(geometry.type);
    if (!geometryTypes.has(kind)) throw new Error(`Unsupported geometry: ${kind}.`);
    kinds.add(kind);
    if (kind === 'GeometryCollection') {
      if (!Array.isArray(geometry.geometries)) throw new Error('A geometry collection is missing geometries.');
      geometry.geometries.forEach(visitGeometry);
    } else visitCoordinates(geometry.coordinates);
  };
  let pointCount = 0;
  for (const feature of features) {
    if (!feature || typeof feature !== 'object' || (feature as Record<string, unknown>).type !== 'Feature') {
      throw new Error('Every collection member must be a GeoJSON Feature.');
    }
    const geometry = (feature as Record<string, unknown>).geometry;
    visitGeometry(geometry);
    if (geometry && typeof geometry === 'object') {
      const raw = geometry as Record<string, unknown>;
      if (raw.type === 'Point') pointCount++;
      else if (raw.type === 'MultiPoint' && Array.isArray(raw.coordinates)) pointCount += raw.coordinates.length;
    }
  }
  if (features.length > 10000 && (pointCount !== coordinateCount || pointCount === 0))
    throw new Error('The higher feature limit is for Point and MultiPoint collections only. Simplify mixed geometry to 10,000 features.');
  const bounds = coordinateCount ? [[west, south], [east, north]] as [[number, number], [number, number]] : null;
  return { data: { type: 'FeatureCollection', features: features as Record<string, unknown>[] }, bounds,
    featureCount: features.length, coordinateCount, kinds: [...kinds], pointCount };
}
