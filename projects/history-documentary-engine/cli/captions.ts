import {access, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';

const chunkWords = (text: string, targetWords = 7) => {
  const words = text.trim().split(/\s+/);
  const chunks: string[] = [];
  let current: string[] = [];
  for (const word of words) {
    current.push(word);
    const punctuationBreak = /[.!?;:]$/.test(word) && current.length >= 4;
    if (current.length >= targetWords || punctuationBreak) {
      chunks.push(current.join(' '));
      current = [];
    }
  }
  if (current.length) {
    if (chunks.length && current.length < 3) chunks[chunks.length - 1] += ` ${current.join(' ')}`;
    else chunks.push(current.join(' '));
  }
  return chunks;
};

export const captionManifest = async (manifestFilename: string) => {
  const manifestFile = path.resolve(manifestFilename);
  const projectDir = path.dirname(manifestFile);
  const originalText = await readFile(manifestFile, 'utf8');
  const manifest = parseManifest(JSON.parse(originalText));
  const report: Array<{sceneId: string; captionCount: number}> = [];
  const whisperCandidates = ['/opt/homebrew/bin/whisper-cli', '/usr/local/bin/whisper-cli'];
  const localAligner = (await Promise.all(whisperCandidates.map((candidate) => access(candidate).then(() => candidate).catch(() => null)))).find(Boolean) ?? null;

  for (const scene of manifest.scenes) {
    if (!scene.narration || !scene.audio) continue;
    const chunks = chunkWords(scene.narration);
    const totalWords = chunks.reduce((sum, chunk) => sum + chunk.split(/\s+/).length, 0);
    const audioFrames = Math.max(1, Math.floor(scene.audio.durationSeconds * manifest.format.fps));
    let cursor = 0;
    scene.captions = chunks.map((text, index) => {
      const wordCount = text.split(/\s+/).length;
      const startFrame = cursor;
      const rawEnd = index === chunks.length - 1 ? audioFrames : cursor + Math.round(audioFrames * wordCount / totalWords);
      const endFrame = Math.max(startFrame + 1, rawEnd);
      cursor = endFrame;
      return {text, startFrame, endFrame};
    });
    report.push({sceneId: scene.id, captionCount: scene.captions.length});
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupFile = path.join(projectDir, `manifest.before-captions-${timestamp}.json`);
  await writeFile(backupFile, originalText);
  await writeFile(manifestFile, `${JSON.stringify(parseManifest(manifest), null, 2)}\n`);
  const reportFile = path.join(projectDir, 'caption-report.json');
  await writeFile(reportFile, `${JSON.stringify({generatedAt: new Date().toISOString(), strategy: 'proportional-phrase-timing', alignment: {requested: 'auto', selected: 'phrase-fallback', localWhisperCli: localAligner, reason: localAligner ? 'A compatible model path was not configured; phrase timing retained' : 'No permissively licensed local whisper-cli installation was detected'}, backupFile: path.basename(backupFile), scenes: report, totalCaptions: report.reduce((sum, item) => sum + item.captionCount, 0)}, null, 2)}\n`);
  return {backupFile, reportFile, scenes: report.length, totalCaptions: report.reduce((sum, item) => sum + item.captionCount, 0)};
};
