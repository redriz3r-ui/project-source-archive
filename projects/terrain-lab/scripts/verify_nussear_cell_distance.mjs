import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { analyzeCells } from './nussear_cell_distance.mjs';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';

assert.equal(globalThis.document, undefined);
assert.equal(globalThis.window, undefined);
const result = await analyzeCells(['350', '300', '400', '300']);
const [north, south, line] = result.features;
assert.equal(inspectGeoJson(result).featureCount, 3);
assert.deepEqual([north.properties.modelValue, south.properties.modelValue], [0.9, 0.9]);
assert.deepEqual([north.properties.row, north.properties.column, south.properties.row, south.properties.column], [350, 300, 400, 300]);
assert.ok(Math.abs(north.geometry.coordinates[0] - -115.81397323370514) < 1e-9);
assert.ok(Math.abs(north.geometry.coordinates[1] - 35.977828086504786) < 1e-9);
assert.ok(Math.abs(south.geometry.coordinates[1] - 35.52750683034502) < 1e-9);
assert.deepEqual(line.geometry.coordinates, [north.geometry.coordinates, south.geometry.coordinates]);
// Independently calculated as R * |latitude difference| for equal longitudes, R = 6,371,008.8 m.
assert.ok(Math.abs(line.properties.value - 50_073.50821) < 0.01);
assert.equal(line.properties.observed, false);
assert.equal(line.properties.contractVersion, 'terrain-lab-operation/v1');
assert.equal(line.properties.sourceVerification, 'registered-dataset');
assert.equal(line.properties.studyId, 'nussear-2009-desert-tortoise-habitat');
assert.equal(line.properties.sourceArchiveSha256, 'c33d3088e9a5b1c2c653e215b3780657bba5a81d72d98638e126871068dc9ee0');
assert.equal(line.properties.sourceRasterSha256, '42d62244565576c5be0bb1b3cda569240674220bf5ac758a3df2fae0660e6644');

const saved = JSON.parse(await readFile(new URL('../public/data/nussear-2009/cell-distance.geojson', import.meta.url), 'utf8'));
assert.deepEqual(saved.features.map(feature => feature.geometry), result.features.map(feature => feature.geometry));
assert.equal(saved.features[2].properties.value, result.features[2].properties.value);

await assert.rejects(() => analyzeCells(['350', '300', '350', '300']), /different raster cells/);
await assert.rejects(() => analyzeCells(['350', '300', '738', '300']), /outside/);
await assert.rejects(() => analyzeCells(['350', '300', 'bad', '300']), /nonnegative integer/);
await assert.rejects(() => analyzeCells(['350', '300']), /Provide/);
await assert.rejects(() => analyzeCells(['0', '0', '350', '300']), /no model value/);

const run = (...args) => spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/nussear_cell_distance.mjs', ...args], { encoding: 'utf8' });
const success = run('350', '300', '400', '300');
assert.equal(success.status, 0, success.stderr);
assert.equal(JSON.parse(success.stdout).features[2].properties.value, line.properties.value);
const failure = run('350', '300', '738', '300');
assert.equal(failure.status, 1);
assert.match(failure.stderr, /outside/);
console.log('Nussear research distance passed: source cells, independent expected distance, provenance, GeoJSON, and CLI status.');
