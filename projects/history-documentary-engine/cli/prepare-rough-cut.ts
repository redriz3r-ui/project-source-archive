import {copyFile, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';

const main = async () => {
  const manifestFile = path.resolve('public/projects/episode-1/manifest.json');
  const original = await readFile(manifestFile, 'utf8');
  const manifest = parseManifest(JSON.parse(original));
  let cursor = 0;
  for (const scene of manifest.scenes) {
    scene.startFrame = cursor;
    if (scene.type !== 'TITLE_CARD' && scene.durationFrames < Math.ceil(manifest.format.fps * 2.5)) scene.durationFrames = Math.ceil(manifest.format.fps * 2.5);
    cursor += scene.durationFrames;
  }
  const cueFrame = (passageId: string) => manifest.scenes.find((scene) => scene.direction?.passageId === passageId)?.startFrame ?? 0;
  manifest.soundtrack = {src:'projects/episode-1/audio/score.wav',provider:'house-style-original',title:'Restrained documentary pulse',license:'Original generated asset — CC0 dedication',baseVolume:.055,duckVolume:.018};
  manifest.soundEffects = [
    {id:'opening-impact',src:'projects/episode-1/audio/chapter-impact.wav',provider:'house-style-original',license:'Original generated asset — CC0 dedication',startFrame:0,volume:.07},
    {id:'march-transition',src:'projects/episode-1/audio/transition-whoosh.wav',provider:'house-style-original',license:'Original generated asset — CC0 dedication',startFrame:cueFrame('06-route'),volume:.055},
    {id:'battle-transition',src:'projects/episode-1/audio/chapter-impact.wav',provider:'house-style-original',license:'Original generated asset — CC0 dedication',startFrame:cueFrame('08-ridge'),volume:.065},
    {id:'federal-transition',src:'projects/episode-1/audio/transition-whoosh.wav',provider:'house-style-original',license:'Original generated asset — CC0 dedication',startFrame:cueFrame('10-federal'),volume:.05},
  ];
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  await copyFile(manifestFile, path.join(path.dirname(manifestFile), `manifest.before-rough-cut-${stamp}.json`));
  await writeFile(manifestFile, `${JSON.stringify(parseManifest(manifest), null, 2)}\n`);
  console.log(`Rough-cut timeline prepared: ${(cursor / manifest.format.fps).toFixed(1)} seconds, ${manifest.soundEffects.length} restrained cues`);
};

main().catch((error: unknown) => {console.error(error instanceof Error ? error.message : error); process.exitCode = 1;});
