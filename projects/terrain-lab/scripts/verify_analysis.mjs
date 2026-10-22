import assert from 'node:assert/strict';
import { area } from '@turf/area';
import { compute, resultsGeoJson } from '../src/sandbox/analysis.ts';

const source = (key, geometry) => ({ key, label: key, feature: { type: 'Feature', geometry, properties: {} } });
const origin = source('origin', { type: 'Point', coordinates: [0, 0] });
const east = source('east', { type: 'Point', coordinates: [1, 0] });
const line = source('equator line', { type: 'LineString', coordinates: [[0, 0], [1, 0]] });
const square = source('small square', { type: 'Polygon', coordinates: [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]] });

const length = await compute('length', line);
const distance = await compute('distance', origin, east);
assert.ok(Math.abs(length.feature.properties.value - 111_195) < 500, '1° of equator is about 111.2 km');
assert.ok(Math.abs(distance.feature.properties.value - 111_195) < 500, 'point distance agrees with known equator distance');
assert.equal(distance.feature.geometry.type, 'LineString');
assert.deepEqual(distance.feature.geometry.coordinates, [[0, 0], [1, 0]], 'distance result connects the two source points');
assert.equal(distance.title, 'Point distance');
assert.equal(distance.valueLabel, '111.195 km');
assert.equal(distance.sourceLabel, 'origin → east');
assert.equal(distance.feature.properties.operation, 'distance');
assert.equal(distance.feature.properties.unit, 'meters');
assert.equal(distance.feature.properties.source, distance.sourceLabel);
assert.equal(distance.feature.properties.classification, 'computed geometry');
assert.equal(distance.feature.properties.observed, false);

const acrossDateLine = await compute('distance',
  source('west', { type: 'Point', coordinates: [179, 0] }),
  source('east', { type: 'Point', coordinates: [-179, 0] }));
assert.ok(Math.abs(acrossDateLine.feature.properties.value - 222_390) < 1000,
  'distance follows the short geodesic path across the antimeridian');
assert.deepEqual(acrossDateLine.feature.geometry.coordinates, [[179, 0], [-179, 0]]);

const elevated = await compute('distance',
  source('low', { type: 'Point', coordinates: [0, 0, 100] }),
  source('high', { type: 'Point', coordinates: [1, 0, 200] }));
assert.deepEqual(elevated.feature.geometry.coordinates, [[0, 0], [1, 0]],
  'distance output is a two-dimensional WGS84 line');
assert.ok(Math.abs(elevated.feature.properties.value - distance.feature.properties.value) < 0.001,
  'height does not affect the current distance calculation');

const polygonArea = await compute('area', square);
assert.ok(Math.abs(polygonArea.feature.properties.value - 1_236_000) < 30_000, '0.01° square near equator is about 1.24 km²');
const rectangle = (west, south, east, north) => [[west, south], [east, south], [east, north], [west, north], [west, south]];
const sphericalRectangleArea = (west, south, east, north) => {
  const radians = Math.PI / 180;
  return 6_371_008.8 ** 2 * (east - west) * radians * (Math.sin(north * radians) - Math.sin(south * radians));
};
const outer = rectangle(0, 0, 1, 1);
const hole = rectangle(0.25, 0.25, 0.75, 0.75);
const whole = await compute('area', source('whole', { type: 'Polygon', coordinates: [outer] }));
const perforated = await compute('area', source('with hole', { type: 'Polygon', coordinates: [outer, hole] }));
const expectedWhole = sphericalRectangleArea(0, 0, 1, 1);
const expectedHole = sphericalRectangleArea(0.25, 0.25, 0.75, 0.75);
assert.ok(Math.abs(whole.feature.properties.value - expectedWhole) / expectedWhole < 0.001);
assert.ok(Math.abs(perforated.feature.properties.value - (expectedWhole - expectedHole)) / expectedWhole < 0.001);
const secondPolygon = rectangle(2, 0, 3, 1);
const multi = await compute('area', source('two polygons', { type: 'MultiPolygon', coordinates: [[outer], [secondPolygon]] }));
assert.ok(Math.abs(multi.feature.properties.value - 2 * expectedWhole) / expectedWhole < 0.002);
assert.equal(perforated.feature.geometry.type, 'Polygon');
assert.deepEqual(perforated.feature.geometry.coordinates, [outer, hole]);
assert.equal(perforated.feature.properties.unit, 'square meters');
assert.equal(perforated.feature.properties.observed, false);

const buffered = await compute('buffer', origin, undefined, 1000);
assert.equal(buffered.feature.geometry.type, 'Polygon');
assert.ok(Math.abs(area(buffered.feature) - Math.PI * 1_000_000) < 120_000, '1 km buffer is approximately π km²');
assert.equal(buffered.feature.properties.classification, 'computed geometry');
assert.equal(buffered.feature.properties.observed, false);
assert.equal(resultsGeoJson([length, distance, polygonArea, buffered]).features.length, 4);

await assert.rejects(() => compute('length', origin), /does not support/);
await assert.rejects(() => compute('distance', origin, origin), /different points/);
await assert.rejects(() => compute('distance', origin), /second point/);
await assert.rejects(() => compute('distance', origin, line), /does not support LineString/);
await assert.rejects(() => compute('distance', source('invalid', { type: 'Point', coordinates: [181, 0] }), east), /invalid WGS84 geometry/);
await assert.rejects(() => compute('buffer', origin, undefined, 0), /radius/);
await assert.rejects(() => compute('buffer', origin, undefined, 50_001), /radius/);
await assert.rejects(() => compute('area', source('open ring', { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1]]] })), /invalid WGS84 geometry/);
await assert.rejects(() => compute('area', source('bad latitude', { type: 'Polygon', coordinates: [rectangle(0, 91, 1, 92)] })), /invalid WGS84 geometry/);

console.log('Spatial analysis checks passed: length, area, distance, buffer, metadata, and invalid inputs; distance contract and edge cases.');
