import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { compute, sourceFeatures } from '../src/sandbox/analysis.ts';
import { POLYGON_AREA_CONTRACT_VERSION, POLYGON_AREA_OPERATION_ID, runPolygonAreaRequest,
  validatePolygonAreaRequest, validatePolygonAreaResponse } from '../src/geo/polygonAreaContract.ts';

assert.equal(globalThis.document, undefined);
assert.equal(globalThis.window, undefined);
const descriptor = JSON.parse(readFileSync(new URL('../public/operations/polygon-area.v1.json', import.meta.url)));
const catalog = JSON.parse(readFileSync(new URL('../public/operations/index.json', import.meta.url)));
assert.equal(descriptor.id, POLYGON_AREA_OPERATION_ID);
assert.equal(descriptor.contractVersion, POLYGON_AREA_CONTRACT_VERSION);
assert.ok(catalog.operations.some(operation => operation.id === descriptor.id &&
  operation.descriptor === '/operations/polygon-area.v1.json'));
const fixture = JSON.parse(readFileSync(new URL('./fixtures/polygon-area.geojson', import.meta.url)));
const sources = sourceFeatures(fixture, { type: 'FeatureCollection', features: [] });
const request = input => ({ contractVersion: POLYGON_AREA_CONTRACT_VERSION,
  operationId: POLYGON_AREA_OPERATION_ID, units: 'square-meters', input });
const rad = Math.PI / 180;
const square = 6_371_008.8 ** 2 * rad * Math.sin(rad);
const hole = 6_371_008.8 ** 2 * 0.5 * rad * (Math.sin(0.75 * rad) - Math.sin(0.25 * rad));
for (const [index, expected] of [square, square - hole, square * 2].entries()) {
  const input = request(sources[index]);
  assert.deepEqual(validatePolygonAreaRequest(input), input);
  const response = await runPolygonAreaRequest(input);
  assert.equal(response.ok, true);
  validatePolygonAreaResponse(response);
  assert.equal(response.provenance.verification, 'caller-supplied');
  assert.equal(response.provenance.inputKey, sources[index].key);
  assert.equal(response.result.feature.properties.unit, 'square meters');
  assert.deepEqual(response.result.feature.geometry, sources[index].feature.geometry);
  assert.ok(Math.abs(response.result.feature.properties.value - expected) / expected < 0.001);
  const browser = await compute('area', sources[index]);
  assert.equal(response.result.feature.properties.value, browser.feature.properties.value);
  assert.equal(response.result.valueLabel, browser.valueLabel);
}
const caller = await runPolygonAreaRequest({ ...request(sources[0]), sourceReference: 'example citation' });
assert.equal(caller.provenance.verification, 'caller-supplied');
assert.equal(caller.provenance.sourceReference, 'example citation');
const evidence = { studyId: 'registered-study', datasetId: 'registered-layer', sourceUrl: 'https://example.org/data',
  sourceFeatureId: '42', sourceArchiveSha256: 'a'.repeat(64), preparedGeoJsonSha256: 'b'.repeat(64) };
const verified = await runPolygonAreaRequest(request(sources[0]), evidence);
assert.equal(verified.ok, true);
assert.equal(verified.provenance.verification, 'registered-dataset');
assert.deepEqual(verified.provenance.sourceArchiveSha256, evidence.sourceArchiveSha256);
validatePolygonAreaResponse(verified);
const failure = async (change, code) => {
  const input = structuredClone(request(sources[0]));
  change(input);
  const response = await runPolygonAreaRequest(input);
  assert.equal(response.ok, false);
  assert.equal(response.error.code, code);
  validatePolygonAreaResponse(response);
};
await failure(input => { input.contractVersion = 'wrong'; }, 'UNSUPPORTED_VERSION');
await failure(input => { input.operationId = 'wrong'; }, 'UNSUPPORTED_OPERATION');
await failure(input => { input.units = 'hectares'; }, 'INVALID_PARAMETERS');
await failure(input => { input.input.feature.geometry.type = 'Point'; }, 'INVALID_GEOMETRY');
await failure(input => { input.input.feature.geometry.coordinates[0][0][1] = 91; }, 'INVALID_GEOMETRY');
await failure(input => { input.input.feature.geometry.coordinates[0].pop(); }, 'INVALID_GEOMETRY');
await failure(input => { input.input.key = ''; }, 'INVALID_REQUEST');
await failure(input => { input.provenance = { verification: 'registered-dataset' }; }, 'INVALID_REQUEST');
const run = (...args) => spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/polygon_area_cli.mjs', ...args], { encoding: 'utf8' });
const success = run('scripts/fixtures/polygon-area.geojson', '1');
assert.equal(success.status, 0, success.stderr);
const cli = JSON.parse(success.stdout);
assert.equal(cli.ok, true);
assert.ok(Math.abs(cli.result.feature.properties.value - (square - hole)) / square < 0.001);
assert.equal(cli.provenance.verification, 'caller-supplied');
const bad = run('scripts/fixtures/polygon-area.geojson', '7');
assert.equal(bad.status, 1);
assert.match(bad.stderr, /out of range/);
console.log('Polygon-area contract passed: independent fixtures, parity, validation, provenance, CLI, and no browser globals.');
