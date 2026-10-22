import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const cli = fileURLToPath(new URL('./point_distance_cli.mjs', import.meta.url));
const directory = mkdtempSync(join(tmpdir(), 'terrain-lab-distance-'));
const input = join(directory, 'points.geojson');
const run = (...args) => spawnSync(process.execPath, ['--experimental-strip-types', cli, ...args], { encoding: 'utf8' });

try {
  writeFileSync(input, JSON.stringify({ type: 'FeatureCollection', features: [
    { type: 'Feature', properties: { name: 'A' }, geometry: { type: 'Point', coordinates: [0, 0] } },
    { type: 'Feature', properties: { name: 'B' }, geometry: { type: 'Point', coordinates: [1, 0] } },
  ] }));

  const success = run(input, '0', '1');
  assert.equal(success.status, 0, success.stderr);
  const result = JSON.parse(success.stdout);
  assert.ok(Math.abs(result.feature.properties.value - 111_195) < 500);
  assert.equal(result.feature.properties.unit, 'meters');
  assert.deepEqual(result.feature.geometry.coordinates, [[0, 0], [1, 0]]);

  const badIndex = run(input, '0', '2');
  assert.equal(badIndex.status, 1);
  assert.match(badIndex.stderr, /Feature index is out of range/);
  assert.equal(badIndex.stdout, '');

  const badFile = join(directory, 'invalid.geojson');
  writeFileSync(badFile, '{invalid');
  const invalid = run(badFile, '0', '1');
  assert.equal(invalid.status, 1);
  assert.match(invalid.stderr, /does not contain valid JSON/);
  assert.equal(invalid.stdout, '');

  console.log('Point distance CLI checks passed: JSON result and failure exits.');
} finally {
  rmSync(directory, { recursive: true, force: true });
}
