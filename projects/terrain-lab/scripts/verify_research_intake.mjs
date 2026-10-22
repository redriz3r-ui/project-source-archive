import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildIntakeCandidate, renderIntakeReview } from '../src/research/intake.ts';
import { validateStudyMetadata } from '../src/data/studyMetadata.ts';
import { fleckensteinStudy } from '../src/data/fleckensteinStudy.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const manifest = JSON.parse(readFileSync(resolve(root, 'research/intake/fleckenstein-2025.source.json'), 'utf8'));
const discovery = JSON.parse(readFileSync(resolve(root, 'research/discovery/desert_tortoise_papers.json'), 'utf8'))
  .papers.find(item => item.doi === manifest.discoveryDoi);
const archive = readFileSync(resolve(root, manifest.files.archivePath));
const prepared = readFileSync(resolve(root, manifest.files.preparedPath));
const prj = execFileSync('python3', [resolve(root, 'scripts/read_nested_zip_member.py'),
  resolve(root, manifest.files.archivePath), ...manifest.files.nestedCrsMembers]);
const hash = value => createHash('sha256').update(value).digest('hex');
const inputs = {
  discoveryRecord: discovery,
  archiveSha256: hash(archive), preparedSha256: hash(prepared), sourcePrjSha256: hash(prj),
  sourcePrjText: prj.toString('utf8'), preparedGeoJson: JSON.parse(prepared.toString('utf8')),
};
const run = (changeManifest = () => {}, changeInputs = () => {}) => {
  const source = structuredClone(manifest);
  const evidence = { ...inputs };
  changeManifest(source); changeInputs(evidence);
  return buildIntakeCandidate(source, evidence);
};

const valid = run();
assert.equal(valid.machineChecksPassed, true);
assert.equal(valid.reviewStatus, 'pending-human-review');
assert.equal(valid.publicationStatus, 'not-published-by-intake');
assert.deepEqual(valid.issues.map(item => item.code), ['HUMAN_REVIEW_REQUIRED']);
validateStudyMetadata(valid.proposedStudy);
assert.equal(valid.proposedStudy.id, fleckensteinStudy.id);
assert.equal(valid.proposedStudy.doi, fleckensteinStudy.doi);
assert.equal(valid.proposedStudy.datasets.length, 1);
assert.equal(valid.proposedStudy.datasets[0].role, 'observed-geography');
assert.equal(valid.proposedStudy.studyArea.footprintDatasetId, undefined);
assert.equal(valid.geographicEvidence.preparedGeoJson.featureCount, 872);
assert.deepEqual(valid.geographicEvidence.preparedGeoJson.temporalCoverage, { startYear: 1986, endYear: 2021 });
assert.deepEqual(valid.geographicEvidence.preparedGeoJson.bounds, manifest.files.expectedBounds);
assert.equal(valid.geographicEvidence.sourceArchive.prjSha256, manifest.files.sourcePrjSha256);
assert.deepEqual(valid.geographicEvidence.excludedRoles,
  ['study-footprint', 'derived-output', 'model-prediction']);
assert.match(renderIntakeReview(valid), /Human approval checklist/);
assert.match(renderIntakeReview(valid), /This report is not publication approval/);

const errorCodes = result => result.issues.filter(item => item.severity === 'error').map(item => item.code);
assert.ok(errorCodes(run(source => { source.files.archiveSha256 = '0'.repeat(64); })).includes('CHECKSUM_MISMATCH'));
assert.ok(errorCodes(run(source => { source.publication.publicationYear = 2024; })).includes('DISCOVERY_MISMATCH'));
assert.ok(errorCodes(run(source => { source.evidence = source.evidence.filter(item => item.field !== 'dataset.permissions'); })).includes('MISSING_EVIDENCE'));
assert.ok(errorCodes(run(source => { source.dataset.role = 'model-prediction'; })).includes('ROLE_CLASSIFICATION'));
assert.ok(errorCodes(run(source => { source.sensitivity.status = 'unknown'; })).includes('SENSITIVE_LOCATION_REVIEW'));
assert.ok(errorCodes(run(source => { source.files.expectedBounds[0][0] += 1; })).includes('GEOGRAPHIC_EXTENT'));
assert.ok(errorCodes(run(source => { source.dataset.temporalCoverage.endYear = 2020; })).includes('TEMPORAL_COVERAGE'));
assert.ok(errorCodes(run(() => {}, evidence => { evidence.sourcePrjText = 'EPSG:3857'; })).includes('CRS_MISMATCH'));
assert.ok(errorCodes(run(() => {}, evidence => {
  evidence.preparedGeoJson = { type: 'FeatureCollection', features: [{
    type: 'Feature', geometry: { type: 'Point', coordinates: [-120, 37] }, properties: {},
  }] };
})).includes('GEOGRAPHIC_EXTENT'));

const cli = spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/research_intake.mjs'],
  { cwd: root, encoding: 'utf8' });
assert.equal(cli.status, 0, cli.stderr);
const cliResult = JSON.parse(cli.stdout);
assert.equal(cliResult.machineChecksPassed, true);
assert.equal(cliResult.reviewStatus, 'pending-human-review');
assert.deepEqual(cliResult.geographicEvidence.preparedGeoJson.bounds, manifest.files.expectedBounds);
const forbidden = spawnSync(process.execPath, ['--experimental-strip-types', 'scripts/research_intake.mjs',
  '--output', 'public/data/unreviewed.json'], { cwd: root, encoding: 'utf8' });
assert.equal(forbidden.status, 1);
assert.match(forbidden.stderr, /Path must be inside/);

console.log('Research intake checks passed: candidate metadata, source files, CRS, extent, role, sensitivity, human-review gate, and CLI.');
