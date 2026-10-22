const MERCATOR_LIMIT = 20037508.342789244;

export function webMercatorToWgs84(x: number, y: number): [number, number] {
  if (![x, y].every(Number.isFinite) || Math.abs(x) > MERCATOR_LIMIT || Math.abs(y) > MERCATOR_LIMIT)
    throw new Error('Web Mercator coordinates are outside the valid world extent.');
  return [x / MERCATOR_LIMIT * 180, Math.atan(Math.sinh(y / MERCATOR_LIMIT * Math.PI)) * 180 / Math.PI];
}
