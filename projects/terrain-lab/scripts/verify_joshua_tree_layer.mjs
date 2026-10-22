import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { esqueStudy } from '../src/data/esqueStudy.ts';
import { analyzeJoshuaCellArea } from './esque_cell_area.mjs';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const sourceDataset = esqueStudy.datasets.find(item => item.id === 'hybrid-presence-grid-cells');
const derivedDataset = esqueStudy.datasets.find(item => item.id === 'hybrid-cell-680349-area');
assert.ok(sourceDataset && derivedDataset);
const prepared = readFileSync(new URL(`../public${sourceDataset.localPath}`, import.meta.url));
assert.equal(createHash('sha256').update(prepared).digest('hex'),
  '96e23e42f471fb3d7f6cb90de798ebb426b9a16c8246a6c93e5e330feb715166');
const inspection = inspectGeoJson(JSON.parse(prepared.toString('utf8')));
assert.equal(inspection.featureCount, 941);
assert.deepEqual(inspection.kinds, ['Polygon']);
assert.deepEqual(inspection.bounds, [[-115.6371680202468, 37.234101992744485],
  [-115.28682511077108, 37.52676788214518]]);
assert.ok(prepared.byteLength < 3_000_000);
const ids = new Set();
for (const feature of inspection.data.features) {
  assert.equal(feature.geometry?.type, 'Polygon');
  assert.equal(feature.id, feature.properties?.ID);
  assert.ok(!ids.has(feature.id));
  ids.add(feature.id);
  assert.equal(feature.properties?.Final_Stat, 'P');
  assert.equal(feature.properties?.State, 'NV');
  assert.equal(feature.properties?.terrainLabStudyId, esqueStudy.id);
  assert.equal(feature.properties?.terrainLabDatasetId, sourceDataset.id);
  assert.equal(feature.properties?.terrainLabRole, 'observed-geography');
}
const output = await analyzeJoshuaCellArea();
assert.equal(inspectGeoJson(output).featureCount, 2);
const [source, derived] = output.features;
assert.deepEqual(source, inspection.data.features.find(feature => feature.id === 680349));
assert.deepEqual(derived.geometry, source.geometry);
assert.equal(derived.properties?.classification, 'computed geometry');
assert.equal(derived.properties?.observed, false);
assert.equal(derived.properties?.sourceVerification, 'registered-dataset');
assert.equal(derived.properties?.sourceFeatureId, 680349);
assert.equal(derived.properties?.studyId, esqueStudy.id);
assert.equal(derived.properties?.datasetId, sourceDataset.id);
assert.ok(Math.abs(derived.properties.value - 158110.06177397823) < 0.001);
// Independent planar area of this publisher shapefile cell is 158177.7134 m².
// The geodesic WGS84 result should stay within 0.1%, not match a different method exactly.
assert.ok(Math.abs(derived.properties.value - 158177.7134027913) / 158177.7134027913 < 0.001);
const saved = JSON.parse(readFileSync(new URL(`../public${derivedDataset.localPath}`, import.meta.url), 'utf8'));
assert.deepEqual(saved.features[0], source);
assert.deepEqual(saved.features[1].geometry, derived.geometry);
assert.equal(saved.features[1].properties.value, derived.properties.value);
const cli = spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/esque_cell_area.mjs'],
  { cwd: root, encoding: 'utf8' });
assert.equal(cli.status, 0, cli.stderr);
assert.equal(JSON.parse(cli.stdout).features[1].properties.value, derived.properties.value);
const invalid = spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/esque_cell_area.mjs', '--bad'],
  { cwd: root, encoding: 'utf8' });
assert.equal(invalid.status, 1);
assert.match(invalid.stderr, /Usage:/);
console.log('Joshua tree layer checks passed: 941 attributed cells, published geometry, independent area cross-check, saved result, and CLI.');
