import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';
import {MacOsSayNarrationAdapter} from './adapters/macos-say';

const safeName = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 70);

export const narrateManifest = async (manifestFile: string, voice: string, rate: number) => {
  const absoluteManifest = path.resolve(manifestFile);
  const projectDir = path.dirname(absoluteManifest);
  const originalText = await readFile(absoluteManifest, 'utf8');
  const manifest = parseManifest(JSON.parse(originalText));
  const audioDir = path.join(projectDir, 'audio');
  const tempDir = path.join(audioDir, '.source');
  await mkdir(tempDir, {recursive: true});
  const adapter = new MacOsSayNarrationAdapter(voice, rate);
  let cursor = 0;
  const generated: Array<{sceneId: string; durationSeconds: number; src: string}> = [];

  for (const scene of manifest.scenes) {
    scene.startFrame = cursor;
    if (!scene.narration) {
      cursor += scene.durationFrames;
      continue;
    }
    const filename = `${safeName(scene.id)}.wav`;
    const wavPath = path.join(audioDir, filename);
    const aiffPath = path.join(tempDir, `${safeName(scene.id)}.aiff`);
    const {durationSeconds} = await adapter.synthesize(scene.narration, aiffPath, wavPath);
    const relativeSrc = path.relative(path.resolve('public'), wavPath).split(path.sep).join('/');
    scene.audio = {src: relativeSrc, provider: adapter.provider, voice: adapter.voice, durationSeconds};
    scene.durationFrames = Math.ceil((durationSeconds + 0.65) * manifest.format.fps);
    generated.push({sceneId: scene.id, durationSeconds, src: relativeSrc});
    cursor += scene.durationFrames;
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupFile = path.join(projectDir, `manifest.before-narration-${timestamp}.json`);
  await writeFile(backupFile, originalText);
  await writeFile(absoluteManifest, `${JSON.stringify(parseManifest(manifest), null, 2)}\n`);
  const reportFile = path.join(projectDir, 'narration-report.json');
  await writeFile(reportFile, `${JSON.stringify({generatedAt: new Date().toISOString(), provider: adapter.provider, voice: adapter.voice, rate, backupFile: path.basename(backupFile), totalDurationSeconds: cursor / manifest.format.fps, scenes: generated}, null, 2)}\n`);
  return {backupFile, reportFile, sceneCount: generated.length, totalDurationSeconds: cursor / manifest.format.fps};
};
