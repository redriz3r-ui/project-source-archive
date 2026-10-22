import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { computePointDistance } from '../src/geo/pointDistance.ts';
import { POINT_DISTANCE_CONTRACT_VERSION, POINT_DISTANCE_OPERATION_ID, runPointDistanceRequest,
  validatePointDistanceRequest, validatePointDistanceResponse } from '../src/geo/pointDistanceContract.ts';

assert.equal(globalThis.document, undefined);
assert.equal(globalThis.window, undefined);
const descriptor = JSON.parse(await readFile(new URL('../public/operations/point-distance.v1.json', import.meta.url), 'utf8'));
const catalog = JSON.parse(await readFile(new URL('../public/operations/index.json', import.meta.url), 'utf8'));
assert.ok(catalog.operations.some(operation => operation.id === POINT_DISTANCE_OPERATION_ID &&
  operation.contractVersion === POINT_DISTANCE_CONTRACT_VERSION &&
  operation.descriptor === '/operations/point-distance.v1.json'));
assert.equal(descriptor.id, POINT_DISTANCE_OPERATION_ID);
assert.equal(descriptor.contractVersion, POINT_DISTANCE_CONTRACT_VERSION);
assert.equal(descriptor.requestSchema.properties.operationId.const, POINT_DISTANCE_OPERATION_ID);
assert.equal(descriptor.responseSchema.properties.provenance.oneOf.length, 2);
assert.deepEqual(descriptor.errorSchema.properties.error.properties.code.enum,
  ['INVALID_REQUEST', 'UNSUPPORTED_VERSION', 'UNSUPPORTED_OPERATION', 'INVALID_GEOMETRY', 'INVALID_PARAMETERS', 'COMPUTATION_FAILED']);

const source = (key, coordinates) => ({ key, label: key, feature: {
  type: 'Feature', geometry: { type: 'Point', coordinates }, properties: { title: key },
} });
const first = source('first', [0, 0]);
const second = source('second', [1, 0]);
const request = { contractVersion: POINT_DISTANCE_CONTRACT_VERSION, operationId: POINT_DISTANCE_OPERATION_ID,
  inputs: { first, second }, sourceReference: 'https://example.org/caller-data' };
assert.deepEqual(validatePointDistanceRequest(request), request);
const response = await runPointDistanceRequest(request);
assert.equal(response.ok, true);
validatePointDistanceResponse(response);
assert.deepEqual(response.provenance, { verification: 'caller-supplied', inputKeys: ['first', 'second'],
  sourceReference: 'https://example.org/caller-data' });
assert.equal(response.result.feature.properties.value > 111_000, true);
assert.equal(response.result.feature.properties.unit, 'meters');
assert.deepEqual(response.result.feature.geometry.coordinates, [[0, 0], [1, 0]]);
const direct = await computePointDistance(first, second);
assert.equal(response.result.feature.properties.value, direct.feature.properties.value);
assert.deepEqual(response.result.feature.geometry, direct.feature.geometry);
assert.equal(response.result.valueLabel, direct.valueLabel);
assert.equal(response.result.sourceLabel, direct.sourceLabel);
const claimedStudy = await runPointDistanceRequest({ ...request, inputs: { first: { ...first,
  feature: { ...first.feature, properties: { studyId: 'nussear-2009-desert-tortoise-habitat' } } }, second } });
assert.equal(claimedStudy.ok, true);
assert.equal(claimedStudy.provenance.verification, 'caller-supplied');
const nullProperties = await runPointDistanceRequest({ ...request, inputs: { first: { ...first,
  feature: { ...first.feature, properties: null } }, second } });
assert.equal(nullProperties.ok, true);
const absentProperties = await runPointDistanceRequest({ ...request, inputs: { first: { ...first,
  feature: { type: 'Feature', geometry: first.feature.geometry } }, second } });
assert.equal(absentProperties.ok, true);

const failure = async (input, code, evidence) => {
  const result = await runPointDistanceRequest(input, evidence);
  assert.equal(result.ok, false);
  assert.equal(result.error.code, code);
  validatePointDistanceResponse(result);
};
await failure({ ...request, contractVersion: 'terrain-lab-operation/v2' }, 'UNSUPPORTED_VERSION');
await failure({ ...request, operationId: 'area' }, 'UNSUPPORTED_OPERATION');
await failure({ ...request, inputs: { first } }, 'INVALID_REQUEST');
await failure({ ...request, inputs: { first, second: { ...second, key: first.key } } }, 'INVALID_PARAMETERS');
await failure({ ...request, inputs: { first: source('bad', [181, 0]), second } }, 'INVALID_GEOMETRY');
await failure({ ...request, inputs: { first: source('bad', [0, NaN]), second } }, 'INVALID_GEOMETRY');
await failure({ ...request, inputs: { first: { ...first, feature: { ...first.feature,
  geometry: { type: 'LineString', coordinates: [[0, 0], [1, 0]] } } }, second } }, 'INVALID_GEOMETRY');
await failure({ ...request, sourceReference: '' }, 'INVALID_REQUEST');
await failure({ ...request, provenance: { verification: 'registered-dataset' } }, 'INVALID_REQUEST');
await failure(request, 'INVALID_REQUEST', { studyId: 'fake' });

const invalidOutput = structuredClone(response);
invalidOutput.result.feature.properties.unit = 'kilometers';
assert.throws(() => validatePointDistanceResponse(invalidOutput), /Invalid point-distance result/);
assert.throws(() => validatePointDistanceResponse({ ...response, extra: true }), /envelope/);
assert.throws(() => validatePointDistanceResponse({ ...response, provenance: {
  ...response.provenance, verification: 'registered-dataset' } }), /registered-dataset provenance/);
console.log('Point-distance contract passed: descriptor, runtime schemas, provenance, errors, and core parity.');
