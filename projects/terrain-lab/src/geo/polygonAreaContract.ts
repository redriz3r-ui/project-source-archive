import type { AnalysisResult, SourceFeature } from './analysisCommon.ts';
import { assertSource } from './analysisCommon.ts';
import { computePolygonArea } from './polygonArea.ts';

export const POLYGON_AREA_OPERATION_ID = 'polygon-area';
export const POLYGON_AREA_CONTRACT_VERSION = 'terrain-lab-operation/v1';
export type PolygonAreaRequest = {
  contractVersion: typeof POLYGON_AREA_CONTRACT_VERSION;
  operationId: typeof POLYGON_AREA_OPERATION_ID;
  units: 'square-meters';
  input: SourceFeature;
  sourceReference?: string;
};
export type RegisteredPolygonDatasetEvidence = {
  studyId: string; datasetId: string; sourceUrl: string; sourceFeatureId: string;
  sourceArchiveSha256: string; preparedGeoJsonSha256: string;
};
export type PolygonAreaProvenance = { inputKey: string } & (
  { verification: 'caller-supplied'; sourceReference?: string } |
  ({ verification: 'registered-dataset' } & RegisteredPolygonDatasetEvidence)
);
export type PolygonAreaErrorCode = 'INVALID_REQUEST' | 'UNSUPPORTED_VERSION' | 'UNSUPPORTED_OPERATION' |
  'INVALID_GEOMETRY' | 'INVALID_PARAMETERS' | 'COMPUTATION_FAILED';
export type PolygonAreaResponse =
  { contractVersion: typeof POLYGON_AREA_CONTRACT_VERSION; operationId: typeof POLYGON_AREA_OPERATION_ID;
    ok: true; result: AnalysisResult; provenance: PolygonAreaProvenance } |
  { contractVersion: typeof POLYGON_AREA_CONTRACT_VERSION; operationId: typeof POLYGON_AREA_OPERATION_ID;
    ok: false; error: { code: PolygonAreaErrorCode; message: string } };

class ContractError extends Error {
  readonly code: PolygonAreaErrorCode;
  constructor(code: PolygonAreaErrorCode, message: string) { super(message); this.code = code; }
}
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const nonempty = (value: unknown, limit: number): value is string => typeof value === 'string' &&
  value.trim().length > 0 && value.length <= limit;
function onlyKeys(value: Record<string, unknown>, allowed: string[], path: string): void {
  const extra = Object.keys(value).find(key => !allowed.includes(key));
  if (extra) throw new ContractError('INVALID_REQUEST', `${path}.${extra} is not supported.`);
}
function validCoordinates(value: unknown, count: { value: number }): boolean {
  if (!Array.isArray(value)) return false;
  if (typeof value[0] === 'number') {
    count.value++;
    return count.value <= 20_000 && value.length >= 2 && value.length <= 16 &&
      value.every(item => typeof item === 'number' && Number.isFinite(item)) &&
      value[0] >= -180 && value[0] <= 180 && value[1] >= -90 && value[1] <= 90;
  }
  return value.length > 0 && value.every(item => validCoordinates(item, count));
}
function source(value: unknown): SourceFeature {
  if (!object(value)) throw new ContractError('INVALID_REQUEST', 'input must be a source feature object.');
  onlyKeys(value, ['key', 'label', 'feature'], 'input');
  if (!nonempty(value.key, 120) || !nonempty(value.label, 200))
    throw new ContractError('INVALID_REQUEST', 'input needs a nonempty key and label within the published limits.');
  if (!object(value.feature) || value.feature.type !== 'Feature' ||
    (value.feature.properties !== undefined && value.feature.properties !== null && !object(value.feature.properties)))
    throw new ContractError('INVALID_GEOMETRY', 'input.feature must be a GeoJSON Feature with object or null properties.');
  const geometry = value.feature.geometry;
  if (!object(geometry) || !['Polygon', 'MultiPolygon'].includes(String(geometry.type)) ||
    !validCoordinates(geometry.coordinates, { value: 0 }))
    throw new ContractError('INVALID_GEOMETRY', 'input.feature must contain a WGS84 Polygon or MultiPolygon with at most 20,000 coordinates.');
  let propertiesJson: string | undefined;
  try { propertiesJson = JSON.stringify(value.feature.properties ?? null); } catch { /* Non-JSON input. */ }
  if (!propertiesJson || new TextEncoder().encode(propertiesJson).length > 16_384)
    throw new ContractError('INVALID_REQUEST', 'input.feature.properties must be JSON within 16,384 bytes.');
  try { assertSource(value as SourceFeature, new Set(['Polygon', 'MultiPolygon'])); }
  catch { throw new ContractError('INVALID_GEOMETRY', 'input.feature has incomplete or invalid WGS84 polygon rings.'); }
  return value as SourceFeature;
}
export function validatePolygonAreaRequest(value: unknown): PolygonAreaRequest {
  if (!object(value)) throw new ContractError('INVALID_REQUEST', 'Request must be an object.');
  onlyKeys(value, ['contractVersion', 'operationId', 'units', 'input', 'sourceReference'], 'request');
  if (value.contractVersion !== POLYGON_AREA_CONTRACT_VERSION)
    throw new ContractError('UNSUPPORTED_VERSION', `Use ${POLYGON_AREA_CONTRACT_VERSION}.`);
  if (value.operationId !== POLYGON_AREA_OPERATION_ID)
    throw new ContractError('UNSUPPORTED_OPERATION', `Use ${POLYGON_AREA_OPERATION_ID}.`);
  if (value.units !== 'square-meters') throw new ContractError('INVALID_PARAMETERS', 'units must be square-meters.');
  const input = source(value.input);
  if (value.sourceReference !== undefined && !nonempty(value.sourceReference, 2048))
    throw new ContractError('INVALID_REQUEST', 'sourceReference must be a nonempty string of at most 2,048 characters.');
  return { contractVersion: POLYGON_AREA_CONTRACT_VERSION, operationId: POLYGON_AREA_OPERATION_ID,
    units: 'square-meters', input, ...(value.sourceReference === undefined ? {} : { sourceReference: value.sourceReference as string }) };
}
function validEvidence(value: RegisteredPolygonDatasetEvidence): boolean {
  return object(value) && nonempty(value.studyId, 200) && nonempty(value.datasetId, 200) &&
    nonempty(value.sourceUrl, 2048) && /^https?:\/\//.test(value.sourceUrl) &&
    nonempty(value.sourceFeatureId, 200) && /^[a-f0-9]{64}$/.test(value.sourceArchiveSha256) &&
    /^[a-f0-9]{64}$/.test(value.preparedGeoJsonSha256);
}
export function validatePolygonAreaResponse(value: unknown): asserts value is PolygonAreaResponse {
  if (!object(value) || value.contractVersion !== POLYGON_AREA_CONTRACT_VERSION ||
    value.operationId !== POLYGON_AREA_OPERATION_ID || typeof value.ok !== 'boolean')
    throw new Error('Invalid polygon-area response envelope.');
  if (!value.ok) {
    if (!object(value.error) || !['INVALID_REQUEST', 'UNSUPPORTED_VERSION', 'UNSUPPORTED_OPERATION',
      'INVALID_GEOMETRY', 'INVALID_PARAMETERS', 'COMPUTATION_FAILED'].includes(String(value.error.code)) ||
      !nonempty(value.error.message, 4096)) throw new Error('Invalid polygon-area error response.');
    return;
  }
  const result = value.result;
  if (!object(result) || !nonempty(result.id, 200) || result.title !== 'Polygon area' ||
    !nonempty(result.valueLabel, 200) || !nonempty(result.sourceLabel, 500) ||
    !object(result.feature) || result.feature.type !== 'Feature' || !object(result.feature.geometry) ||
    !['Polygon', 'MultiPolygon'].includes(String(result.feature.geometry.type)) ||
    !validCoordinates(result.feature.geometry.coordinates, { value: 0 }) ||
    !object(result.feature.properties) || result.feature.properties.classification !== 'computed geometry' ||
    result.feature.properties.observed !== false || result.feature.properties.operation !== 'area' ||
    typeof result.feature.properties.value !== 'number' || !Number.isFinite(result.feature.properties.value) ||
    result.feature.properties.value < 0 || result.feature.properties.unit !== 'square meters' ||
    !nonempty(result.feature.properties.source, 500) || !nonempty(result.feature.properties.method, 500) ||
    typeof result.feature.properties.computedAt !== 'string' || !Number.isFinite(Date.parse(result.feature.properties.computedAt)))
    throw new Error('Invalid polygon-area result.');
  const provenance = value.provenance;
  if (!object(provenance) || !nonempty(provenance.inputKey, 120)) throw new Error('Invalid polygon-area provenance.');
  if (provenance.verification === 'registered-dataset') {
    if (!validEvidence(provenance as RegisteredPolygonDatasetEvidence)) throw new Error('Invalid registered-dataset provenance.');
  } else if (provenance.verification === 'caller-supplied') {
    if (provenance.sourceReference !== undefined && !nonempty(provenance.sourceReference, 2048))
      throw new Error('Invalid caller-supplied provenance.');
  } else throw new Error('Invalid provenance verification status.');
}
// Only trusted internal workflows may supply registered-dataset evidence.
export async function runPolygonAreaRequest(input: unknown, verified?: RegisteredPolygonDatasetEvidence): Promise<PolygonAreaResponse> {
  let request: PolygonAreaRequest;
  try { request = validatePolygonAreaRequest(input); }
  catch (error) {
    const issue = error instanceof ContractError ? error : new ContractError('INVALID_REQUEST', 'Invalid request.');
    return { contractVersion: POLYGON_AREA_CONTRACT_VERSION, operationId: POLYGON_AREA_OPERATION_ID,
      ok: false, error: { code: issue.code, message: issue.message } };
  }
  try {
    if (verified && !validEvidence(verified)) throw new ContractError('INVALID_REQUEST', 'Invalid registered-dataset evidence.');
    const result = await computePolygonArea(request.input);
    const provenance: PolygonAreaProvenance = verified ?
      { verification: 'registered-dataset', inputKey: request.input.key, ...verified } :
      { verification: 'caller-supplied', inputKey: request.input.key,
        ...(request.sourceReference ? { sourceReference: request.sourceReference } : {}) };
    const response: PolygonAreaResponse = { contractVersion: POLYGON_AREA_CONTRACT_VERSION,
      operationId: POLYGON_AREA_OPERATION_ID, ok: true, result, provenance };
    validatePolygonAreaResponse(response);
    return response;
  } catch (error) {
    return { contractVersion: POLYGON_AREA_CONTRACT_VERSION, operationId: POLYGON_AREA_OPERATION_ID,
      ok: false, error: { code: error instanceof ContractError ? error.code : 'COMPUTATION_FAILED',
        message: error instanceof ContractError ? error.message : 'Polygon area could not be computed.' } };
  }
}
