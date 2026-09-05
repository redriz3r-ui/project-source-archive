import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import type {NarrationAdapter} from '../adapters';

const run = promisify(execFile);

export class MacOsSayNarrationAdapter implements NarrationAdapter {
  readonly provider = 'macos-say';
  constructor(readonly voice: string, private readonly rate: number) {}

  async synthesize(text: string, aiffPath: string, wavPath: string) {
    await run('/usr/bin/say', ['-v', this.voice, '-r', String(this.rate), '-o', aiffPath, text]);
    await run('/opt/homebrew/bin/ffmpeg', ['-y', '-loglevel', 'error', '-i', aiffPath, '-ar', '44100', '-ac', '1', '-c:a', 'pcm_s16le', wavPath]);
    const {stdout} = await run('/opt/homebrew/bin/ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', wavPath]);
    const durationSeconds = Number(stdout.trim());
    if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) throw new Error(`Could not measure narration duration: ${wavPath}`);
    return {durationSeconds};
  }
}
