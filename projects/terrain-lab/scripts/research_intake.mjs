import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildIntakeCandidate, renderIntakeReview } from '../src/research/intake.ts';
import { buildShapefileIntakeCandidate, renderShapefileIntakeReview } from '../src/research/shapefileIntake.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
const option = name => {
  const at = args.indexOf(name);
  return at < 0 ? undefined : args[at + 1];
};
const manifestName = option('--manifest') ?? 'research/intake/fleckenstein-2025.source.json';
const discoveryName = option('--discovery') ?? 'research/discovery/desert_tortoise_papers.json';
const outputName = option('--output');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const md5 = bytes => createHash('md5').update(bytes).digest('hex');

function projectPath(name, prefix = root) {
  if (typeof name !== 'string' || !name || isAbsolute(name)) throw new Error('Paths must be relative to the project.');
  const full = resolve(root, name);
  const within = relative(prefix, full);
  if (within.startsWith('..') || isAbsolute(within) || within === '') throw new Error(`Path must be inside ${prefix}.`);
  return full;
}

try {
  const manifest = JSON.parse(readFileSync(projectPath(manifestName), 'utf8'));
  const discovery = JSON.parse(readFileSync(projectPath(discoveryName), 'utf8'));
  if (!manifest?.files) throw new Error('Intake manifest is missing file paths.');
  const discoveryRecord = discovery.papers?.find(item => item.doi?.toLowerCase() === manifest.discoveryDoi?.toLowerCase());
  let candidate;
  let review;
  if (manifest.files.kind === 'shapefile-components') {
    const sourceRoot = resolve(root, 'research/intake/sources');
    const sourceFiles = Object.fromEntries(manifest.files.sourceFiles.map(file => {
      const bytes = readFileSync(projectPath(file.path, sourceRoot));
      return [file.path, { sha256: hash(bytes), md5: md5(bytes) }];
    }));
    const prj = readFileSync(projectPath(manifest.files.sourcePrjPath, sourceRoot), 'utf8');
    const prepared = readFileSync(projectPath(manifest.files.preparedPath, sourceRoot));
    candidate = buildShapefileIntakeCandidate(manifest, {
      discoveryRecord, sourceFiles, sourcePrjText: prj,
      preparedSha256: hash(prepared), preparedGeoJson: JSON.parse(prepared.toString('utf8')),
    });
    review = renderShapefileIntakeReview(candidate);
  } else {
    if (!Array.isArray(manifest.files.nestedCrsMembers)) throw new Error('Intake manifest lacks nested CRS members.');
    const dataRoot = resolve(root, 'public/data');
    const archivePath = projectPath(manifest.files.archivePath, dataRoot);
    const preparedPath = projectPath(manifest.files.preparedPath, dataRoot);
    const archive = readFileSync(archivePath);
    const prepared = readFileSync(preparedPath);
    const prj = execFileSync('python3', [fileURLToPath(new URL('./read_nested_zip_member.py', import.meta.url)),
      archivePath, ...manifest.files.nestedCrsMembers], { maxBuffer: 1024 * 1024 });
    candidate = buildIntakeCandidate(manifest, {
      discoveryRecord, archiveSha256: hash(archive), preparedSha256: hash(prepared), sourcePrjSha256: hash(prj),
      sourcePrjText: prj.toString('utf8'), preparedGeoJson: JSON.parse(prepared.toString('utf8')),
    });
    review = renderIntakeReview(candidate);
  }
  const serialized = `${JSON.stringify(candidate, null, 2)}\n`;
  if (outputName) {
    const target = projectPath(outputName, resolve(root, 'research/intake/candidates'));
    if (!target.endsWith('.json')) throw new Error('Candidate output must be a .json file.');
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, serialized);
    writeFileSync(target.replace(/\.json$/, '.review.md'), review);
    process.stderr.write(`Wrote review candidate: ${outputName}\n`);
  } else process.stdout.write(serialized);
  if (!candidate.machineChecksPassed) process.exitCode = 1;
} catch (error) {
  process.stderr.write(`Research intake failed: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
