import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest, type Scene} from '../src/manifest/schema';
import {ProceduralIllustrationAdapter, ProceduralMusicAdapter, ProceduralSoundEffectAdapter} from './adapters/procedural-assets';

export const materializeCreativeAssets = async (manifestFilename: string) => {
  const manifestFile = path.resolve(manifestFilename);
  const projectDir = path.dirname(manifestFile);
  const original = await readFile(manifestFile, 'utf8');
  const manifest = parseManifest(JSON.parse(original));
  const generatedDir = path.join(projectDir, 'generated');
  const audioDir = path.join(projectDir, 'music');
  await mkdir(generatedDir, {recursive: true});
  await mkdir(audioDir, {recursive: true});
  const illustration = new ProceduralIllustrationAdapter();
  const generated: string[] = [];
  manifest.scenes = manifest.scenes.map((scene): Scene => {
    if ((scene.type === 'ARCHIVE_PHOTO' || scene.type === 'KEN_BURNS') && scene.payload.rightsStatus !== 'NO_KNOWN_RESTRICTIONS' && scene.payload.rightsStatus !== 'LICENSED') {
      return {...scene, type: 'ILLUSTRATION', payload: {src: `projects/${manifest.id}/generated/${scene.id}.svg`, alt: scene.payload.alt, credit: 'Original procedural illustration', rightsStatus: 'LICENSED', archiveQuery: scene.payload.archiveQuery, prompt: `Editorial historical illustration: ${scene.narration ?? scene.payload.alt}`, provider: illustration.provider}};
    }
    return scene;
  });
  for (const scene of manifest.scenes) {
    if (scene.type !== 'ILLUSTRATION' && scene.type !== 'LABELED_CUTOUT') continue;
    const output = path.join(generatedDir, `${scene.id}.svg`);
    const prompt = scene.type === 'ILLUSTRATION' ? scene.payload.prompt : scene.payload.detail ?? scene.payload.label;
    await illustration.generate(prompt, scene.narration ?? scene.payload.alt, output);
    scene.payload.src = path.relative(path.resolve('public'), output).split(path.sep).join('/');
    scene.payload.credit = 'Original procedural illustration';
    scene.payload.rightsStatus = 'LICENSED';
    generated.push(scene.id);
  }
  const durationSeconds = Math.max(...manifest.scenes.map((scene) => scene.startFrame + scene.durationFrames)) / manifest.format.fps;
  const music = new ProceduralMusicAdapter();
  const musicFile = path.join(audioDir, 'documentary-pulse.wav');
  const musicMeta = await music.generate(durationSeconds + 2, musicFile);
  manifest.soundtrack = {src: path.relative(path.resolve('public'), musicFile).split(path.sep).join('/'), provider: music.provider, title: musicMeta.title, license: musicMeta.license, baseVolume: .1, duckVolume: .035};
  const sfx = new ProceduralSoundEffectAdapter();
  const whooshFile = path.join(audioDir, 'transition-whoosh.wav');
  const impactFile = path.join(audioDir, 'chapter-impact.wav');
  const whooshMeta = await sfx.generate('WHOOSH', whooshFile);
  const impactMeta = await sfx.generate('IMPACT', impactFile);
  manifest.soundEffects = manifest.scenes.filter((scene, index) => index > 0 && (scene.direction?.transition !== 'CUT' || scene.type === 'STATISTIC' || scene.type === 'DATE_CARD' || scene.type === 'CHAPTER_CARD')).map((scene, index) => ({id: `cue-${index + 1}-${scene.id}`, src: path.relative(path.resolve('public'), scene.type === 'CHAPTER_CARD' || scene.type === 'STATISTIC' ? impactFile : whooshFile).split(path.sep).join('/'), provider: sfx.provider, license: scene.type === 'CHAPTER_CARD' || scene.type === 'STATISTIC' ? impactMeta.license : whooshMeta.license, startFrame: scene.startFrame, volume: .11}));
  const backupFile = path.join(projectDir, `manifest.before-creative-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
  await writeFile(backupFile, original);
  await writeFile(manifestFile, `${JSON.stringify(parseManifest(manifest), null, 2)}\n`);
  const reportFile = path.join(projectDir, 'creative-assets-report.json');
  await writeFile(reportFile, `${JSON.stringify({generatedAt: new Date().toISOString(), illustrationProvider: illustration.provider, generatedScenes: generated, soundtrack: manifest.soundtrack, soundEffects: manifest.soundEffects}, null, 2)}\n`);
  return {backupFile, reportFile, generatedScenes: generated.length, soundtrack: manifest.soundtrack};
};
