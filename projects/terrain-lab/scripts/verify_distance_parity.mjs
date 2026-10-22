import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';
import { compute, resultsGeoJson, sourceFeatures } from '../src/sandbox/analysis.ts';
import { POINT_DISTANCE_CONTRACT_VERSION, POINT_DISTANCE_OPERATION_ID, runPointDistanceRequest } from '../src/geo/pointDistanceContract.ts';

const fixture = fileURLToPath(new URL('./fixtures/point-distance.geojson', import.meta.url));
const cli = fileURLToPath(new URL('./point_distance_cli.mjs', import.meta.url));
const { data } = inspectGeoJson(JSON.parse(readFileSync(fixture, 'utf8')));
const sources = sourceFeatures(data, { type: 'FeatureCollection', features: [] });

// This is the same adapter path the browser UI uses after choosing two imported features.
const browserExecution = await runPointDistanceRequest({ contractVersion: POINT_DISTANCE_CONTRACT_VERSION,
  operationId: POINT_DISTANCE_OPERATION_ID, inputs: { first: sources[0], second: sources[1] } });
assert.equal(browserExecution.ok, true);
const browserPath = browserExecution.result;
const directPath = await compute('distance', sources[0], sources[1]);
assert.equal(browserPath.feature.properties.value, directPath.feature.properties.value);
const headlessProcess = spawnSync(process.execPath,
  ['--experimental-strip-types', cli, fixture, '0', '1'], { encoding: 'utf8' });
assert.equal(headlessProcess.status, 0, headlessProcess.stderr);
const headlessPath = JSON.parse(headlessProcess.stdout);

assert.equal(browserPath.title, headlessPath.title);
assert.equal(browserPath.valueLabel, headlessPath.valueLabel);
assert.equal(browserPath.sourceLabel, headlessPath.sourceLabel);
assert.equal(browserExecution.provenance.verification, 'caller-supplied');
const browserFeature = browserPath.feature;
const headlessFeature = headlessPath.feature;
assert.equal(browserFeature.type, 'Feature');
assert.equal(headlessFeature.type, 'Feature');
assert.equal(browserFeature.geometry.type, 'LineString');
assert.equal(headlessFeature.geometry.type, 'LineString');
assert.deepEqual(browserFeature.geometry.coordinates, [[-112.115, 36.105], [-112.095, 36.112]],
  'The browser path must connect the selected fixture points in order');
assert.equal(browserFeature.geometry.coordinates.length, headlessFeature.geometry.coordinates.length);
for (let index = 0; index < browserFeature.geometry.coordinates.length; index++) {
  const browserCoordinate = browserFeature.geometry.coordinates[index];
  const headlessCoordinate = headlessFeature.geometry.coordinates[index];
  assert.equal(browserCoordinate.length, headlessCoordinate.length);
  for (let axis = 0; axis < browserCoordinate.length; axis++) {
    assert.ok(Math.abs(browserCoordinate[axis] - headlessCoordinate[axis]) <= 1e-9,
      `Coordinate ${index}, axis ${axis} differs across interfaces`);
  }
}
const { value: browserMeters, computedAt: browserTime, ...browserProperties } = browserFeature.properties;
const { value: headlessMeters, computedAt: headlessTime, ...headlessProperties } = headlessFeature.properties;
assert.ok(Math.abs(browserMeters - headlessMeters) <= 1e-6, 'Distance differs by more than 0.000001 m');
assert.ok(Math.abs(browserMeters - 1958.052086) <= 0.001, 'Distance differs from the fixture baseline');
assert.deepEqual(browserProperties, headlessProperties);
assert.ok(Number.isFinite(Date.parse(browserTime)) && Number.isFinite(Date.parse(headlessTime)));

// Both result geometries retain the GeoJSON shape consumed by Terrain Lab's derived MapLibre source.
for (const result of [browserPath, headlessPath]) {
  const collection = resultsGeoJson([result]);
  const inspection = inspectGeoJson(collection);
  assert.equal(inspection.featureCount, 1);
  assert.deepEqual(inspection.kinds, ['LineString']);
  assert.equal(inspection.coordinateCount, 2);
}

console.log(`Point distance parity passed: ${browserMeters.toFixed(6)} m; geometry and analytical metadata match.`);
