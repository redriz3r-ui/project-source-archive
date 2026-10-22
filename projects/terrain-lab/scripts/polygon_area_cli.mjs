import { readFile } from 'node:fs/promises';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';
import { sourceFeatures } from '../src/sandbox/analysis.ts';
import { POLYGON_AREA_CONTRACT_VERSION, POLYGON_AREA_OPERATION_ID, runPolygonAreaRequest } from '../src/geo/polygonAreaContract.ts';

const usage = 'Usage: npm run area:cli -- <file.geojson> <feature-index>';

async function main() {
  const [file, indexArg, ...extra] = process.argv.slice(2);
  if (!file || indexArg === undefined || extra.length) throw new Error(usage);
  if (!/^(0|[1-9]\d*)$/.test(indexArg) || !Number.isSafeInteger(Number(indexArg)))
    throw new Error('Feature index must be a zero-based nonnegative integer.');
  let contents;
  try { contents = await readFile(file, 'utf8'); }
  catch (error) { throw new Error(`Cannot read GeoJSON file "${file}": ${error.message}`); }
  let input;
  try { input = JSON.parse(contents); }
  catch { throw new Error(`File "${file}" does not contain valid JSON.`); }
  const { data } = inspectGeoJson(input);
  const sources = sourceFeatures(data, { type: 'FeatureCollection', features: [] });
  const first = sources[Number(indexArg)];
  if (!first) throw new Error(`Feature index is out of range; this file has ${sources.length} features.`);
  const response = await runPolygonAreaRequest({ contractVersion: POLYGON_AREA_CONTRACT_VERSION,
    operationId: POLYGON_AREA_OPERATION_ID, units: 'square-meters', input: first });
  if (!response.ok) throw new Error(response.error.message);
  process.stdout.write(`${JSON.stringify(response)}\n`);
}

main().catch(error => {
  console.error(`Polygon area: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
