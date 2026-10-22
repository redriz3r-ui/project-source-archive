import { readFile } from 'node:fs/promises';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';
import { sourceFeatures } from '../src/sandbox/analysis.ts';
import { POINT_DISTANCE_CONTRACT_VERSION, POINT_DISTANCE_OPERATION_ID, runPointDistanceRequest } from '../src/geo/pointDistanceContract.ts';

const usage = 'Usage: npm run distance:cli -- <file.geojson> <first-index> <second-index>';

function parseIndex(value, label) {
  if (!/^(0|[1-9]\d*)$/.test(value) || !Number.isSafeInteger(Number(value))) {
    throw new Error(`${label} must be a zero-based feature index.`);
  }
  return Number(value);
}

async function main() {
  const [file, firstArg, secondArg, ...extra] = process.argv.slice(2);
  if (!file || firstArg === undefined || secondArg === undefined || extra.length) throw new Error(usage);
  const firstIndex = parseIndex(firstArg, 'First index');
  const secondIndex = parseIndex(secondArg, 'Second index');

  let contents;
  try { contents = await readFile(file, 'utf8'); }
  catch (error) { throw new Error(`Cannot read GeoJSON file "${file}": ${error.message}`); }

  let input;
  try { input = JSON.parse(contents); }
  catch { throw new Error(`File "${file}" does not contain valid JSON.`); }

  const { data } = inspectGeoJson(input);
  const sources = sourceFeatures(data, { type: 'FeatureCollection', features: [] });
  if (firstIndex >= sources.length || secondIndex >= sources.length) {
    throw new Error(`Feature index is out of range; this file has ${sources.length} features.`);
  }
  const response = await runPointDistanceRequest({ contractVersion: POINT_DISTANCE_CONTRACT_VERSION,
    operationId: POINT_DISTANCE_OPERATION_ID, inputs: { first: sources[firstIndex], second: sources[secondIndex] } });
  if (!response.ok) throw new Error(response.error.message);
  process.stdout.write(`${JSON.stringify(response.result)}\n`);
}

main().catch(error => {
  console.error(`Point distance: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
