import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { fleckensteinStudy } from '../src/data/fleckensteinStudy.ts';
import { POLYGON_AREA_CONTRACT_VERSION, POLYGON_AREA_OPERATION_ID, runPolygonAreaRequest } from '../src/geo/polygonAreaContract.ts';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';

const dataset = fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states');
const root = new URL('../public/', import.meta.url);
const archive = new URL('./data/fleckenstein-2025/uspvdb_v1_0_20231108.zip', root);
const prepared = new URL(`.${dataset.localPath}`, root);
const archiveSha256 = '8012ef258219fba003de7470a7eaac2cf426ce8131d5810469afc419d033dec4';
const preparedSha256 = '9c9b42452c30bc745be799396f0a97ad9c35e99ee4d6ac8ff6a08124fa3fd543';
const caseId = 400038;

async function verifiedFile(url, expected, label) {
  const bytes = await readFile(url);
  const actual = createHash('sha256').update(bytes).digest('hex');
  if (actual !== expected) throw new Error(`${label} SHA-256 does not match the registered source.`);
  return bytes;
}

export async function analyzeArrayArea() {
  if (dataset.role !== 'observed-geography' || dataset.availability !== 'local')
    throw new Error('The registered source dataset is not available as observed geography.');
  await verifiedFile(archive, archiveSha256, 'Original USGS archive');
  const bytes = await verifiedFile(prepared, preparedSha256, 'Prepared WGS84 GeoJSON');
  const collection = inspectGeoJson(JSON.parse(bytes.toString('utf8'))).data;
  const matches = collection.features.filter(feature => feature.properties?.case_id === caseId);
  if (matches.length !== 1) throw new Error(`Expected exactly one USPVDB feature with case_id ${caseId}.`);
  const source = matches[0];
  if (source.geometry?.type !== 'Polygon' || source.properties?.terrainLabStudyId !== fleckensteinStudy.id ||
    source.properties?.terrainLabDatasetId !== dataset.id || source.properties?.p_state !== 'CA' ||
    source.properties?.p_name !== 'CalRenew-1' || !Number.isFinite(source.properties?.p_area))
    throw new Error('The selected source feature does not match the verified research dataset.');
  const label = `${source.properties.p_name} · USPVDB case ${caseId}`;
  const execution = await runPolygonAreaRequest({
    contractVersion: POLYGON_AREA_CONTRACT_VERSION, operationId: POLYGON_AREA_OPERATION_ID,
    units: 'square-meters', input: { key: `uspvdb:${caseId}`, label, feature: source },
  }, {
    studyId: fleckensteinStudy.id, datasetId: dataset.id, sourceUrl: dataset.sourceUrl,
    sourceFeatureId: String(caseId), sourceArchiveSha256: archiveSha256,
    preparedGeoJsonSha256: preparedSha256,
  });
  if (!execution.ok) throw new Error(execution.error.message);
  const computed = execution.result.feature;
  const area = computed.properties.value;
  const sourceArea = source.properties.p_area;
  const derived = { ...computed, properties: { ...computed.properties,
    contractVersion: execution.contractVersion,
    sourceVerification: execution.provenance.verification,
    studyId: fleckensteinStudy.id, datasetId: dataset.id, sourceFeatureId: caseId,
    sourceUrl: dataset.sourceUrl, sourceArchiveSha256: archiveSha256,
    preparedGeoJsonSha256: preparedSha256,
    sourceAreaSquareMeters: sourceArea,
    differenceFromSourceAreaSquareMeters: area - sourceArea,
    interpretation: 'Geodesic area of this image-digitized solar-array polygon only. The source p_area is a comparison, not a validation of ecological findings, tortoise habitat, or full facility extent.',
  } };
  const output = { type: 'FeatureCollection', features: [source, derived] };
  inspectGeoJson(output);
  return output;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(new URL(`file://${process.argv[1]}`))) {
  try {
    const args = process.argv.slice(2);
    if (args.length !== 0 && (args.length !== 2 || args[0] !== '--output' || !args[1]))
      throw new Error('Usage: npm run research:area -- [--output FILE.geojson]');
    const output = await analyzeArrayArea();
    const json = `${JSON.stringify(output, null, 2)}\n`;
    if (args.length) await writeFile(args[1], json);
    else process.stdout.write(json);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
