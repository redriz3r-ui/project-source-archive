import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';
import { fleckensteinStudy } from '../src/data/fleckensteinStudy.ts';

const dataset = fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states');
assert.ok(dataset);
const archive = readFileSync(new URL('../public/data/fleckenstein-2025/uspvdb_v1_0_20231108.zip', import.meta.url));
assert.equal(createHash('sha256').update(archive).digest('hex'),
  '8012ef258219fba003de7470a7eaac2cf426ce8131d5810469afc419d033dec4');
const prepared = readFileSync(new URL(`../public${dataset.localPath}`, import.meta.url));
assert.equal(createHash('sha256').update(prepared).digest('hex'),
  '9c9b42452c30bc745be799396f0a97ad9c35e99ee4d6ac8ff6a08124fa3fd543');
const data = JSON.parse(prepared.toString('utf8'));
const inspection = inspectGeoJson(data);
assert.equal(inspection.featureCount, 872);
assert.deepEqual(new Set(inspection.kinds), new Set(['Polygon', 'MultiPolygon']));
assert.deepEqual(inspection.bounds, [
  [-124.10542662642925, 26.885386412346794],
  [-95.31047893592189, 41.77589331214717],
]);
const counts = new Map();
const ids = new Set();
const expectedProperties = [
  'case_id', 'multi_poly', 'eia_id', 'p_state', 'p_county', 'ylat', 'xlong', 'p_area',
  'p_img_date', 'p_dig_conf', 'p_name', 'p_year', 'p_pwr_reg', 'p_tech_pri',
  'p_tech_sec', 'p_axis', 'p_azimuth', 'p_tilt', 'p_battery', 'p_cap_ac',
  'p_cap_dc', 'p_type', 'p_agrivolt', 'p_zscore',
  'terrainLabStudyId', 'terrainLabDatasetId', 'terrainLabRole',
].sort();
for (const feature of inspection.data.features) {
  const properties = feature.properties;
  assert.deepEqual(Object.keys(properties).sort(), expectedProperties);
  assert.equal(properties?.terrainLabStudyId, fleckensteinStudy.id);
  assert.equal(properties?.terrainLabDatasetId, dataset.id);
  assert.equal(properties?.terrainLabRole, 'observed solar infrastructure; not tortoise observations');
  assert.equal(feature.id, properties?.case_id);
  assert.ok(!ids.has(feature.id));
  ids.add(feature.id);
  assert.ok(Number.isInteger(properties?.p_year) && properties.p_year >= 1986 && properties.p_year <= 2021);
  counts.set(properties?.p_state, (counts.get(properties?.p_state) ?? 0) + 1);
}
assert.deepEqual(Object.fromEntries([...counts].sort()), {
  AZ: 67, CA: 475, CO: 96, NM: 64, NV: 40, TX: 97, UT: 33,
});
console.log('Fleckenstein USPVDB layer checks passed: source checksum, 872 attributed polygons, states, years, and WGS84 extent.');
