import assert from 'node:assert/strict';
import { computePointDistance } from '../src/geo/pointDistance.ts';

assert.equal(globalThis.document, undefined, 'test runs without a browser DOM');
assert.equal(globalThis.window, undefined, 'test runs without browser UI state');

const source = (key, coordinates) => ({ key, label: key, feature: {
  type: 'Feature', geometry: { type: 'Point', coordinates }, properties: {},
} });
const origin = source('origin', [0, 0]);
const east = source('east', [1, 0]);
const result = await computePointDistance(origin, east);

assert.ok(Math.abs(result.feature.properties.value - 111_195) < 500);
assert.equal(result.valueLabel, '111.195 km');
assert.equal(result.sourceLabel, 'origin → east');
assert.deepEqual(result.feature.geometry, { type: 'LineString', coordinates: [[0, 0], [1, 0]] });
assert.equal(result.feature.properties.operation, 'distance');
assert.equal(result.feature.properties.unit, 'meters');
assert.equal(result.feature.properties.observed, false);

const acrossDateLine = await computePointDistance(source('west', [179, 0]), source('east', [-179, 0]));
assert.ok(Math.abs(acrossDateLine.feature.properties.value - 222_390) < 1000);

await assert.rejects(() => computePointDistance(origin), /second point/);
await assert.rejects(() => computePointDistance(undefined, east), /first point/);
await assert.rejects(() => computePointDistance(origin, origin), /different points/);
await assert.rejects(() => computePointDistance(source('invalid', [181, 0]), east), /invalid WGS84 geometry/);
await assert.rejects(() => computePointDistance(origin, { ...east, feature: {
  ...east.feature, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 0]] },
} }), /does not support LineString/);

console.log('Headless point distance checks passed: result contract, antimeridian, and invalid inputs.');
