import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { fromFile } from 'geotiff';
import { dutcherStudy, studies } from '../src/data/studies.ts';
import { nussearStudy } from '../src/data/nussearStudy.ts';
import { fleckensteinStudy } from '../src/data/fleckensteinStudy.ts';
import { esqueStudy } from '../src/data/esqueStudy.ts';
import { validateStudyMetadata } from '../src/data/studyMetadata.ts';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
validateStudyMetadata(dutcherStudy);
assert.equal(dutcherStudy.datasets.find(item => item.id === 'aggregate-sites').role, 'derived-output');
assert.equal(dutcherStudy.datasets.find(item => item.id === 'habitat-resistance').availability, 'not-recovered');
assert.equal(dutcherStudy.studyArea.footprintDatasetId, undefined);
assert.equal(studies.length, 4);
assert.deepEqual(new Set(studies.map(study => study.id)), new Set([dutcherStudy.id, nussearStudy.id, fleckensteinStudy.id, esqueStudy.id]));
validateStudyMetadata(nussearStudy);
assert.equal(nussearStudy.studyArea.footprintDatasetId, undefined);
assert.equal(nussearStudy.temporalCoverage, undefined);
assert.equal(nussearStudy.datasets.find(item => item.id === 'presence-records').role, 'observed-geography');
assert.equal(nussearStudy.datasets.find(item => item.id === 'presence-records').availability, 'not-recovered');
assert.equal(nussearStudy.datasets.find(item => item.id === 'environmental-layers').role, 'derived-output');
assert.equal(nussearStudy.datasets.find(item => item.id === 'habitat-model').role, 'model-prediction');
assert.equal(nussearStudy.datasets.find(item => item.id === 'habitat-model').availability, 'local');
assert.deepEqual(nussearStudy.datasets.find(item => item.id === 'habitat-model').derivedFrom,
  ['presence-records', 'environmental-layers']);
assert.ok(nussearStudy.datasets.filter(item => item.id !== 'habitat-model').every(item => item.availability !== 'local' && item.localPath === undefined));
validateStudyMetadata(fleckensteinStudy);
assert.equal(fleckensteinStudy.studyArea.footprintDatasetId, undefined);
assert.equal(fleckensteinStudy.temporalCoverage, undefined);
assert.match(fleckensteinStudy.permissions, /CC BY 4\.0/);
assert.equal(fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states').role, 'observed-geography');
assert.equal(fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states').availability, 'local');
assert.deepEqual(fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states').temporalCoverage,
  { startYear: 1986, endYear: 2021 });
assert.match(fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-v1-study-states').permissions, /CC0 1\.0/);
assert.equal(fleckensteinStudy.datasets.find(item => item.id === 'gbif-occurrences').availability, 'not-recovered');
assert.match(fleckensteinStudy.datasets.find(item => item.id === 'gbif-occurrences').permissions, /CC BY-NC 4\.0/);
assert.equal(fleckensteinStudy.datasets.find(item => item.id === 'species-suitability-models').role, 'model-prediction');
const arrayArea = fleckensteinStudy.datasets.find(item => item.id === 'uspvdb-case-400038-area');
assert.equal(arrayArea.role, 'derived-output');
assert.equal(arrayArea.availability, 'local');
assert.deepEqual(arrayArea.derivedFrom, ['uspvdb-v1-study-states']);
assert.ok(fleckensteinStudy.datasets.filter(item => !['uspvdb-v1-study-states', 'uspvdb-case-400038-area'].includes(item.id)).every(item => item.localPath === undefined));
validateStudyMetadata(esqueStudy);
assert.equal(esqueStudy.studyArea.footprintDatasetId, undefined);
assert.equal(esqueStudy.temporalCoverage, undefined);
assert.equal(esqueStudy.datasets[0].role, 'observed-geography');
assert.equal(esqueStudy.datasets[0].temporalCoverage, undefined);
assert.equal(esqueStudy.datasets[1].role, 'derived-output');
assert.deepEqual(esqueStudy.datasets[1].derivedFrom, ['hybrid-presence-grid-cells']);
assert.match(esqueStudy.datasets[0].permissions, /CC0 1\.0/);

for (const dataset of studies.flatMap(study => study.datasets).filter(item => item.availability === 'local')) {
  const path = resolve(root, 'public', dataset.localPath.slice(1));
  assert.ok(existsSync(path), `${dataset.id} must reference a shipped file`);
  if (dataset.format === 'GeoJSON') assert.ok(inspectGeoJson(JSON.parse(readFileSync(path, 'utf8'))).featureCount > 0);
}

const sourceZip = readFileSync(resolve(root, 'public/data/nussear-2009/ofr20091102_dt_Habitat_Model.zip'));
assert.equal(createHash('sha256').update(sourceZip).digest('hex'), 'c33d3088e9a5b1c2c653e215b3780657bba5a81d72d98638e126871068dc9ee0');
const raster = await fromFile(resolve(root, 'public/data/nussear-2009/habitat-potential-3857.tif'));
const image = await raster.getImage();
assert.deepEqual([image.getWidth(), image.getHeight()], [589, 738]);
assert.equal(image.getGeoKeys().ProjectedCSTypeGeoKey, 3857);
assert.equal(image.getGDALNoData(), -9999);
const [west, south, east, north] = image.getBoundingBox();
assert.ok(Math.abs(west + 13263594.308153283) < 1 && Math.abs(south - 3818848.2170947837) < 1 &&
  Math.abs(east + 12535935.709060103) < 1 && Math.abs(north - 4730583.439727664) < 1);
const values = (await image.readRasters({ samples: [0] }))[0];
const observed = new Set();
for (const value of values) {
  if (value === -9999) continue;
  assert.ok(value >= 0 && value <= 1 && Math.abs(value * 10 - Math.round(value * 10)) < 0.00001,
    `unexpected binned model value ${value}`);
  observed.add(Math.round(value * 10));
}
assert.ok(observed.size >= 10, 'the model should retain its published binned values');
for (const tile of ['5/5/12.png', '9/95/200.png']) {
  const bytes = readFileSync(resolve(root, 'public/data/nussear-2009/tiles', tile));
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', `${tile} must be a PNG tile`);
}

const invalid = change => {
  const copy = structuredClone(dutcherStudy);
  change(copy);
  return () => validateStudyMetadata(copy);
};
assert.throws(invalid(study => { delete study.doi; delete study.sourceUrl; }), /requires a DOI or source URL/);
assert.throws(invalid(study => { study.temporalCoverage.startYear = 2018; }), /must not follow endYear/);
assert.throws(invalid(study => { study.datasets[0].role = 'study-footprint'; }), /available study-area footprint/);
assert.throws(invalid(study => { study.datasets[1].derivedFrom = ['missing']; }), /invalid dataset/);
assert.throws(invalid(study => { delete study.datasets[1].localPath; }), /localPath/);
assert.throws(invalid(study => { study.datasets[5].localPath = '/data/missing.geojson'; }), /requires local availability/);
const invalidFleckenstein = change => {
  const copy = structuredClone(fleckensteinStudy);
  change(copy);
  return () => validateStudyMetadata(copy);
};
assert.throws(invalidFleckenstein(study => { study.permissions = ''; }), /study.permissions must be a non-empty string/);
assert.throws(invalidFleckenstein(study => { study.datasets[0].permissions = ''; }), /permissions must be a non-empty string/);
assert.throws(invalidFleckenstein(study => { study.datasets[0].role = 'study-footprint'; }), /available study-area footprint/);

console.log('Study metadata checks passed: four catalog records, local research layers, and invalid classifications/references.');
