import type { Point } from 'geojson';
import type { AnalysisResult, SourceFeature } from './analysisCommon.ts';
import { computePointDistance } from './pointDistance.ts';

export const POINT_DISTANCE_OPERATION_ID = 'point-distance';
export const POINT_DISTANCE_CONTRACT_VERSION = 'terrain-lab-operation/v1';

export type PointDistanceRequest = {
  contractVersion: typeof POINT_DISTANCE_CONTRACT_VERSION;
  operationId: typeof POINT_DISTANCE_OPERATION_ID;
  inputs: { first: SourceFeature; second: SourceFeature };
  sourceReference?: string;
};
export type RegisteredDatasetEvidence = {
  studyId: string;
  datasetId: string;
  sourceUrl: string;
  sourceArchiveSha256: string;
  sourceRasterSha256: string;
};
export type PointDistanceProvenance = { inputKeys: [string, string] } & (
  { verification: 'caller-supplied'; sourceReference?: string } |
  ({ verification: 'registered-dataset' } & RegisteredDatasetEvidence)
);
export type PointDistanceSuccess = {
  contractVersion: typeof POINT_DISTANCE_CONTRACT_VERSION;
  operationId: typeof POINT_DISTANCE_OPERATION_ID;
  ok: true;
  result: AnalysisResult;
  provenance: PointDistanceProvenance;
};
export type PointDistanceErrorCode = 'INVALID_REQUEST' | 'UNSUPPORTED_VERSION' | 'UNSUPPORTED_OPERATION' |
  'INVALID_GEOMETRY' | 'INVALID_PARAMETERS' | 'COMPUTATION_FAILED';
export type PointDistanceFailure = {
  contractVersion: typeof POINT_DISTANCE_CONTRACT_VERSION;
  operationId: typeof POINT_DISTANCE_OPERATION_ID;
  ok: false;
  error: { code: PointDistanceErrorCode; message: string };
};
export type PointDistanceResponse = PointDistanceSuccess | PointDistanceFailure;

class ContractError extends Error {
  readonly code: PointDistanceErrorCode;
  constructor(code: PointDistanceErrorCode, message: string) { super(message); this.code = code; }
}
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const nonempty = (value: unknown, max: number): value is string => typeof value === 'string' &&
  value.trim().length > 0 && value.length <= max;
const exactKeys = (value: Record<string, unknown>, allowed: string[]): boolean =>
  Object.keys(value).every(key => allowed.includes(key));
function onlyKeys(value: Record<string, unknown>, allowed: string[], path: string): void {
  const extra = Object.keys(value).find(key => !allowed.includes(key));
  if (extra) throw new ContractError('INVALID_REQUEST', `${path}.${extra} is not supported.`);
}
function source(value: unknown, path: string): SourceFeature {
  if (!object(value)) throw new ContractError('INVALID_REQUEST', `${path} must be a source feature object.`);
  onlyKeys(value, ['key', 'label', 'feature'], path);
  if (!nonempty(value.key, 120) || !nonempty(value.label, 200))
    throw new ContractError('INVALID_REQUEST', `${path} needs a nonempty key and label within the published limits.`);
  const feature = value.feature;
  if (!object(feature) || feature.type !== 'Feature' ||
    (feature.properties !== undefined && feature.properties !== null && !object(feature.properties)))
    throw new ContractError('INVALID_GEOMETRY', `${path}.feature must be a GeoJSON Feature with object or null properties.`);
  const geometry = feature.geometry;
  if (!object(geometry) || geometry.type !== 'Point')
    throw new ContractError('INVALID_GEOMETRY', `${path}.feature.geometry must be a Point.`);
  const coordinates = geometry.coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 2 || coordinates.length > 16 ||
    !coordinates.every(item => typeof item === 'number' && Number.isFinite(item)) ||
    coordinates[0] < -180 || coordinates[0] > 180 || coordinates[1] < -90 || coordinates[1] > 90)
    throw new ContractError('INVALID_GEOMETRY', `${path}.feature needs valid WGS84 longitude and latitude.`);
  let propertiesJson: string | undefined;
  try { propertiesJson = JSON.stringify(feature.properties ?? null); } catch { /* Non-JSON input. */ }
  if (!propertiesJson || new TextEncoder().encode(propertiesJson).length > 16_384)
    throw new ContractError('INVALID_REQUEST', `${path}.feature.properties must be JSON within 16,384 bytes.`);
  return value as SourceFeature;
}

export function validatePointDistanceRequest(value: unknown): PointDistanceRequest {
  if (!object(value)) throw new ContractError('INVALID_REQUEST', 'Request must be an object.');
  onlyKeys(value, ['contractVersion', 'operationId', 'inputs', 'sourceReference'], 'request');
  if (value.contractVersion !== POINT_DISTANCE_CONTRACT_VERSION)
    throw new ContractError('UNSUPPORTED_VERSION', `Use ${POINT_DISTANCE_CONTRACT_VERSION}.`);
  if (value.operationId !== POINT_DISTANCE_OPERATION_ID)
    throw new ContractError('UNSUPPORTED_OPERATION', `Use ${POINT_DISTANCE_OPERATION_ID}.`);
  if (!object(value.inputs)) throw new ContractError('INVALID_REQUEST', 'inputs must contain first and second source features.');
  onlyKeys(value.inputs, ['first', 'second'], 'inputs');
  const first = source(value.inputs.first, 'inputs.first');
  const second = source(value.inputs.second, 'inputs.second');
  if (first.key === second.key) throw new ContractError('INVALID_PARAMETERS', 'Choose two different point keys.');
  if (value.sourceReference !== undefined && !nonempty(value.sourceReference, 2048))
    throw new ContractError('INVALID_REQUEST', 'sourceReference must be a nonempty string of at most 2,048 characters.');
  return { contractVersion: POINT_DISTANCE_CONTRACT_VERSION, operationId: POINT_DISTANCE_OPERATION_ID,
    inputs: { first, second }, ...(value.sourceReference === undefined ? {} : { sourceReference: value.sourceReference as string }) };
}

function validEvidence(value: RegisteredDatasetEvidence): boolean {
  return object(value) && nonempty(value.studyId, 200) && nonempty(value.datasetId, 200) &&
    nonempty(value.sourceUrl, 2048) && /^https?:\/\//.test(value.sourceUrl) &&
    /^[a-f0-9]{64}$/.test(value.sourceArchiveSha256) && /^[a-f0-9]{64}$/.test(value.sourceRasterSha256);
}

export function validatePointDistanceResponse(value: unknown): asserts value is PointDistanceResponse {
  if (!object(value) || !exactKeys(value, value.ok === true ?
    ['contractVersion', 'operationId', 'ok', 'result', 'provenance'] : ['contractVersion', 'operationId', 'ok', 'error']) ||
    value.contractVersion !== POINT_DISTANCE_CONTRACT_VERSION ||
    value.operationId !== POINT_DISTANCE_OPERATION_ID || typeof value.ok !== 'boolean')
    throw new Error('Invalid point-distance response envelope.');
  if (!value.ok) {
    const error = value.error;
    if (!object(error) || !exactKeys(error, ['code', 'message']) ||
      !['INVALID_REQUEST', 'UNSUPPORTED_VERSION', 'UNSUPPORTED_OPERATION', 'INVALID_GEOMETRY',
      'INVALID_PARAMETERS', 'COMPUTATION_FAILED'].includes(String(error.code)) || !nonempty(error.message, 4096))
      throw new Error('Invalid point-distance error response.');
    return;
  }
  const result = value.result;
  const provenance = value.provenance;
  if (!object(result) || !nonempty(result.id, 200) || result.title !== 'Point distance' ||
    !nonempty(result.valueLabel, 200) || !nonempty(result.sourceLabel, 500) || !object(result.feature) ||
    result.feature.type !== 'Feature' || !object(result.feature.geometry) || result.feature.geometry.type !== 'LineString' ||
    !Array.isArray(result.feature.geometry.coordinates) || result.feature.geometry.coordinates.length !== 2 ||
    !result.feature.geometry.coordinates.every((pair: unknown) => Array.isArray(pair) && pair.length === 2 &&
      pair.every((item: unknown) => typeof item === 'number' && Number.isFinite(item)) &&
      pair[0] >= -180 && pair[0] <= 180 && pair[1] >= -90 && pair[1] <= 90) ||
    !object(result.feature.properties) || result.feature.properties.classification !== 'computed geometry' ||
    result.feature.properties.observed !== false || result.feature.properties.operation !== 'distance' ||
    typeof result.feature.properties.value !== 'number' || !Number.isFinite(result.feature.properties.value) ||
    result.feature.properties.value < 0 || result.feature.properties.unit !== 'meters' ||
    !nonempty(result.feature.properties.source, 500) || !nonempty(result.feature.properties.method, 500) ||
    typeof result.feature.properties.computedAt !== 'string' || !Number.isFinite(Date.parse(result.feature.properties.computedAt)))
    throw new Error('Invalid point-distance result.');
  if (!object(provenance) || !Array.isArray(provenance.inputKeys) || provenance.inputKeys.length !== 2 ||
    !provenance.inputKeys.every((key: unknown) => nonempty(key, 120)))
    throw new Error('Invalid point-distance provenance.');
  if (provenance.verification === 'registered-dataset') {
    if (!exactKeys(provenance, ['verification', 'inputKeys', 'studyId', 'datasetId', 'sourceUrl',
      'sourceArchiveSha256', 'sourceRasterSha256']) || !validEvidence(provenance as RegisteredDatasetEvidence))
      throw new Error('Invalid registered-dataset provenance.');
  } else if (provenance.verification === 'caller-supplied') {
    if (!exactKeys(provenance, ['verification', 'inputKeys', 'sourceReference']) ||
      (provenance.sourceReference !== undefined && !nonempty(provenance.sourceReference, 2048)))
      throw new Error('Invalid caller-supplied provenance.');
  } else throw new Error('Invalid provenance verification status.');
}

// The second argument is internal evidence, never a field in an external request.
// A caller must verify the registered source before supplying it here.
export async function runPointDistanceRequest(input: unknown, verified?: RegisteredDatasetEvidence): Promise<PointDistanceResponse> {
  let request: PointDistanceRequest;
  try { request = validatePointDistanceRequest(input); }
  catch (error) {
    const issue = error instanceof ContractError ? error : new ContractError('INVALID_REQUEST', 'Invalid request.');
    return { contractVersion: POINT_DISTANCE_CONTRACT_VERSION, operationId: POINT_DISTANCE_OPERATION_ID,
      ok: false, error: { code: issue.code, message: issue.message } };
  }
  try {
    if (verified && !validEvidence(verified)) throw new ContractError('INVALID_REQUEST', 'Invalid registered-dataset evidence.');
    const result = await computePointDistance(request.inputs.first, request.inputs.second);
    const inputKeys: [string, string] = [request.inputs.first.key, request.inputs.second.key];
    const provenance: PointDistanceProvenance = verified ? { verification: 'registered-dataset', inputKeys, ...verified } :
      { verification: 'caller-supplied', inputKeys, ...(request.sourceReference ? { sourceReference: request.sourceReference } : {}) };
    const response: PointDistanceSuccess = { contractVersion: POINT_DISTANCE_CONTRACT_VERSION,
      operationId: POINT_DISTANCE_OPERATION_ID, ok: true, result, provenance };
    validatePointDistanceResponse(response);
    return response;
  } catch (error) {
    return { contractVersion: POINT_DISTANCE_CONTRACT_VERSION, operationId: POINT_DISTANCE_OPERATION_ID,
      ok: false, error: { code: error instanceof ContractError ? error.code : 'COMPUTATION_FAILED',
        message: error instanceof ContractError ? error.message : 'Point distance could not be computed.' } };
  }
}
