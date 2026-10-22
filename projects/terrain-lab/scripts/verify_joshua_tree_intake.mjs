import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildShapefileIntakeCandidate, renderShapefileIntakeReview } from '../src/research/shapefileIntake.ts';
import { validateStudyMetadata } from '../src/data/studyMetadata.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = path => readFileSync(resolve(root, path));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const md5 = bytes => createHash('md5').update(bytes).digest('hex');
const manifest = JSON.parse(read('research/intake/esque-2023-joshua-tree.source.json'));
const discoveryRecord = JSON.parse(read('research/discovery/joshua_tree_papers.json')).papers[0];
const prepared = read(manifest.files.preparedPath);
assert.ok(prepared.byteLength < 3_000_000, 'The staged file must fit the existing mixed-GeoJSON browser limit.');
const inputs = {
  discoveryRecord,
  sourceFiles: Object.fromEntries(manifest.files.sourceFiles.map(file => {
    const bytes = read(file.path);
    return [file.path, { sha256: sha256(bytes), md5: md5(bytes) }];
  })),
  sourcePrjText: read(manifest.files.sourcePrjPath).toString('utf8'),
  preparedSha256: sha256(prepared),
  preparedGeoJson: JSON.parse(prepared.toString('utf8')),
};
const run = (changeManifest = () => {}, changeInputs = () => {}) => {
  const candidateManifest = structuredClone(manifest);
  const candidateInputs = { ...inputs };
  changeManifest(candidateManifest);
  changeInputs(candidateInputs);
  return buildShapefileIntakeCandidate(candidateManifest, candidateInputs);
};
const errors = candidate => candidate.issues.filter(issue => issue.severity === 'error').map(issue => issue.code);

const valid = run();
assert.equal(valid.machineChecksPassed, true);
assert.equal(valid.reviewStatus, 'pending-human-review');
assert.equal(valid.publicationStatus, 'not-published-by-intake');
assert.deepEqual(valid.issues.map(issue => issue.code), ['HUMAN_REVIEW_REQUIRED']);
validateStudyMetadata(valid.proposedStudy);
assert.equal(valid.proposedStudy.doi, discoveryRecord.doi);
assert.equal(valid.proposedStudy.datasets.length, 1);
assert.equal(valid.proposedStudy.datasets[0].role, 'observed-geography');
assert.equal(valid.proposedStudy.datasets[0].availability, 'external');
assert.equal(valid.proposedStudy.datasets[0].localPath, undefined);
assert.equal(valid.proposedStudy.studyArea.footprintDatasetId, undefined);
assert.equal(valid.proposedStudy.datasets[0].temporalCoverage, undefined);
assert.equal(valid.geographicEvidence.featureCount, 941);
assert.deepEqual(valid.geographicEvidence.bounds, manifest.files.expectedBounds);
assert.deepEqual(valid.geographicEvidence.geometryTypes, ['Polygon']);
assert.equal(valid.geographicEvidence.preparedSha256, manifest.files.preparedSha256);
for (const feature of inputs.preparedGeoJson.features) {
  assert.equal(feature.geometry.type, 'Polygon');
  for (const ring of feature.geometry.coordinates) {
    assert.ok(ring.length >= 4);
    assert.deepEqual(ring[0], ring.at(-1), 'Every prepared polygon ring must close.');
    assert.ok(ring.every(position => position.length === 2), 'Prepared positions must have WGS84 lon/lat only.');
  }
}
assert.match(renderShapefileIntakeReview(valid), /Decision:\*\* Pending/);

assert.ok(errors(run(source => { source.files.sourceFiles[0].sourceMd5 = '0'.repeat(32); })).includes('CHECKSUM_MISMATCH'));
assert.ok(errors(run(source => { source.files.preparedSha256 = '0'.repeat(64); })).includes('CHECKSUM_MISMATCH'));
assert.ok(errors(run(source => { source.publication.publicationYear = 2024; })).includes('DISCOVERY_MISMATCH'));
assert.ok(errors(run(source => { source.evidence = source.evidence.filter(item => item.field !== 'dataset.permissions'); })).includes('MISSING_EVIDENCE'));
assert.ok(errors(run(source => { source.dataset.role = 'model-prediction'; })).includes('ROLE_CLASSIFICATION'));
assert.ok(errors(run(source => { source.sensitivity.status = 'unknown'; })).includes('SENSITIVE_LOCATION_REVIEW'));
assert.ok(errors(run(source => { source.files.expectedBounds[0][0] += 0.01; })).includes('GEOGRAPHIC_EXTENT'));
assert.ok(errors(run(() => {}, evidence => { evidence.sourcePrjText = 'EPSG:3857'; })).includes('CRS_MISMATCH'));
assert.ok(errors(run(() => {}, evidence => {
  evidence.preparedGeoJson = structuredClone(inputs.preparedGeoJson);
  evidence.preparedGeoJson.features[0].properties.terrainLabDatasetId = 'wrong-dataset';
})).includes('FEATURE_PROVENANCE'));
assert.ok(errors(run(() => {}, evidence => {
  evidence.preparedGeoJson = structuredClone(inputs.preparedGeoJson);
  evidence.preparedGeoJson.features[1].id = evidence.preparedGeoJson.features[0].id;
  evidence.preparedGeoJson.features[1].properties.ID = evidence.preparedGeoJson.features[0].id;
})).includes('FEATURE_ID'));
assert.ok(errors(run(() => {}, evidence => {
  evidence.preparedGeoJson = structuredClone(inputs.preparedGeoJson);
  evidence.preparedGeoJson.features[0].geometry.coordinates[0][0][0] = 999;
})).includes('INVALID_GEOJSON'));

const cli = spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/research_intake.mjs',
  '--manifest', 'research/intake/esque-2023-joshua-tree.source.json',
  '--discovery', 'research/discovery/joshua_tree_papers.json'], { cwd: root, encoding: 'utf8' });
assert.equal(cli.status, 0, cli.stderr);
const cliResult = JSON.parse(cli.stdout);
assert.equal(cliResult.machineChecksPassed, true);
assert.equal(cliResult.reviewStatus, 'pending-human-review');
assert.equal(cliResult.geographicEvidence.featureCount, 941);
const forbidden = spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/research_intake.mjs',
  '--manifest', 'research/intake/esque-2023-joshua-tree.source.json',
  '--discovery', 'research/discovery/joshua_tree_papers.json',
  '--output', 'public/data/unreviewed.json'], { cwd: root, encoding: 'utf8' });
assert.equal(forbidden.status, 1);
assert.match(forbidden.stderr, /Path must be inside/);

console.log('Joshua tree intake checks passed: preserved files, CRS, geometry, extent, provenance, source claims, CLI, and review gate.');
