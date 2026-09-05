import {mkdir, stat} from 'node:fs/promises';
import path from 'node:path';
import {MacOsSayNarrationAdapter} from './adapters/macos-say';
import {presidentGridEntries} from '../src/master/presidents';

const usable = async (file: string) => {
  try { return (await stat(file)).size > 1000; } catch { return false; }
};

const main = async () => {
  const directory = path.resolve('public/master/audio');
  await mkdir(directory, {recursive: true});
  const narrator = new MacOsSayNarrationAdapter('Daniel', 178);
  let generated = 0;
  for (const president of presidentGridEntries) {
    const base = `president-${String(president.number).padStart(2, '0')}`;
    const wav = path.join(directory, `${base}.wav`);
    if (await usable(wav)) continue;
    await narrator.synthesize(president.name, `${wav}.aiff`, wav);
    generated++;
  }
  console.log(JSON.stringify({status: 'PASS', announcements: presidentGridEntries.length, generated, provider: 'macOS', voice: 'Daniel', modelTokens: 0}));
};

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
