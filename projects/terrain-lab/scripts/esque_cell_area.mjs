import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { esqueStudy } from '../src/data/esqueStudy.ts';
import { POLYGON_AREA_CONTRACT_VERSION, POLYGON_AREA_OPERATION_ID, runPolygonAreaRequest } from '../src/geo/polygonAreaContract.ts';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';

const manifest = JSON.parse(await readFile(new URL('../research/intake/esque-2023-joshua-tree.source.json', import.meta.url), 'utf8'));
const dataset = esqueStudy.datasets.find(item => item.id === 'hybrid-presence-grid-cells');
const bundleSha256 = 'a42b0349759cac0a3c68762dd531807efa2416708f8a04de9fdbe1efc811a0f7';
const preparedSha256 = '96e23e42f471fb3d7f6cb90de798ebb426b9a16c8246a6c93e5e330feb715166';
const cellId = 680349;
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const md5 = bytes => createHash('md5').update(bytes).digest('hex');

export async function analyzeJoshuaCellArea() {
  if (dataset?.role !== 'observed-geography' || dataset.availability !== 'local')
    throw new Error('The registered USGS grid dataset is unavailable.');
  const bundle = await readFile(new URL('../research/intake/sources/esque-2023-joshua-tree/Hybrid_Presence_Cells_source_bundle.zip', import.meta.url));
  if (sha256(bundle) !== bundleSha256) throw new Error('Original-source bundle SHA-256 mismatch.');
  for (const source of manifest.files.sourceFiles) {
    const bytes = await readFile(new URL(`../${source.path}`, import.meta.url));
    if (sha256(bytes) !== source.sha256 || md5(bytes) !== source.sourceMd5)
      throw new Error(`Original USGS component checksum mismatch: ${source.path}.`);
  }
  const prepared = await readFile(new URL(`../public${dataset.localPath}`, import.meta.url));
  if (sha256(prepared) !== preparedSha256) throw new Error('Prepared WGS84 GeoJSON SHA-256 mismatch.');
  const collection = inspectGeoJson(JSON.parse(prepared.toString('utf8'))).data;
  const matches = collection.features.filter(feature => feature.properties?.ID === cellId);
  if (matches.length !== 1) throw new Error(`Expected exactly one mapped cell ${cellId}.`);
  const source = matches[0];
  if (source.geometry?.type !== 'Polygon' || source.id !== cellId ||
      source.properties?.Final_Stat !== 'P' || source.properties?.State !== 'NV' ||
      source.properties?.terrainLabStudyId !== esqueStudy.id ||
      source.properties?.terrainLabDatasetId !== dataset.id ||
      source.properties?.terrainLabRole !== 'observed-geography')
    throw new Error('Selected cell does not match the registered USGS data.');
  const execution = await runPolygonAreaRequest({
    contractVersion: POLYGON_AREA_CONTRACT_VERSION, operationId: POLYGON_AREA_OPERATION_ID,
    units: 'square-meters', input: { key: `joshua-tree-cell:${cellId}`,
      label: `Mapped Joshua tree hybrid-presence cell ${cellId}`, feature: source },
  }, {
    studyId: esqueStudy.id, datasetId: dataset.id, sourceUrl: dataset.sourceUrl,
    sourceFeatureId: String(cellId), sourceArchiveSha256: bundleSha256,
    preparedGeoJsonSha256: preparedSha256,
  });
  if (!execution.ok) throw new Error(execution.error.message);
  const derived = { ...execution.result.feature, properties: {
    ...execution.result.feature.properties,
    contractVersion: execution.contractVersion,
    sourceVerification: execution.provenance.verification,
    studyId: esqueStudy.id, datasetId: dataset.id, sourceFeatureId: cellId,
    sourceUrl: dataset.sourceUrl, sourceArchiveSha256: bundleSha256,
    preparedGeoJsonSha256: preparedSha256,
    interpretation: 'Geodesic area of one mapped presence grid cell. It is not tree-crown area, total occupied range, a population estimate, or a test of the paper’s climate findings.',
  } };
  const output = { type: 'FeatureCollection', features: [source, derived] };
  inspectGeoJson(output);
  return output;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(new URL(`file://${process.argv[1]}`))) {
  try {
    const args = process.argv.slice(2);
    if (args.length !== 0 && (args.length !== 2 || args[0] !== '--output' || !args[1]))
      throw new Error('Usage: npm run research:joshua-area -- [--output FILE.geojson]');
    const output = await analyzeJoshuaCellArea();
    const json = `${JSON.stringify(output, null, 2)}\n`;
    if (args.length) await writeFile(args[1], json);
    else process.stdout.write(json);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
