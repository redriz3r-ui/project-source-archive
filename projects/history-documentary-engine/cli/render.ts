import {execFile} from 'node:child_process';
import {access, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';
import {parseManifest} from '../src/manifest/schema';

const execFileAsync = promisify(execFile);

type Probe = {
  format?: {duration?: string};
  streams?: Array<{codec_type?: string; codec_name?: string; width?: number; height?: number}>;
};

export const verifyRender = async (outputFile: string, expected: {width: number; height: number; requireAudio: boolean}) => {
  await access(outputFile);
  const {stdout} = await execFileAsync('/opt/homebrew/bin/ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration,size:stream=codec_type,codec_name,width,height', '-of', 'json', outputFile,
  ]);
  const probe = JSON.parse(stdout) as Probe;
  const video = probe.streams?.find((stream) => stream.codec_type === 'video');
  const audio = probe.streams?.find((stream) => stream.codec_type === 'audio');
  const durationSeconds = Number(probe.format?.duration ?? 0);
  if (!video) throw new Error('Render verification failed: no video stream');
  if (video.width !== expected.width || video.height !== expected.height) throw new Error(`Render verification failed: expected ${expected.width}x${expected.height}, got ${video.width}x${video.height}`);
  if (expected.requireAudio && !audio) throw new Error('Render verification failed: no audio stream');
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) throw new Error('Render verification failed: invalid duration');
  return {durationSeconds, videoCodec: video.codec_name ?? 'unknown', audioCodec: audio?.codec_name ?? null, width: video.width, height: video.height};
};

export const renderManifest = async (manifestFilename: string) => {
  const manifestFile = path.resolve(manifestFilename);
  const manifest = parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
  const projectDir = path.dirname(manifestFile);
  const renderDir = path.join(projectDir, 'renders');
  const outputFile = path.join(renderDir, `${manifest.id}.mp4`);
  const propsFile = path.join(projectDir, 'render-props.json');
  const reportFile = path.join(projectDir, 'render-report.json');
  await mkdir(renderDir, {recursive: true});
  await writeFile(propsFile, `${JSON.stringify({manifest}, null, 2)}\n`);
  const startedAt = new Date().toISOString();
  await execFileAsync(path.resolve('node_modules/.bin/remotion'), [
    'render', 'src/index.ts', 'HistoryDocumentary', outputFile,
    '--props', propsFile, '--codec', 'h264', '--concurrency', '1', '--gl', 'angle', '--overwrite',
  ], {cwd: path.resolve('.'), maxBuffer: 1024 * 1024 * 20});
  const verification = await verifyRender(outputFile, {
    width: manifest.format.width,
    height: manifest.format.height,
    requireAudio: manifest.scenes.some((scene) => Boolean(scene.audio)),
  });
  const report = {schemaVersion: 1, manifestFile, outputFile, startedAt, completedAt: new Date().toISOString(), verified: true, ...verification};
  await writeFile(reportFile, `${JSON.stringify(report, null, 2)}\n`);
  return {outputFile, reportFile, verification};
};
