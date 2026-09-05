export interface ArchiveAdapter {
  search(query: string, limit?: number): Promise<ArchiveCandidate[]>;
}

export interface ArchiveCandidate {
  itemUrl: string;
  imageUrl: string;
  title: string;
  date?: string;
  credit: string;
  rightsStatus: 'REVIEW_REQUIRED' | 'NO_KNOWN_RESTRICTIONS' | 'LICENSED';
  rightsText: string;
  score: number;
}

export interface NarrationAdapter {
  readonly provider: string;
  readonly voice: string;
  synthesize(text: string, sourcePath: string, outputPath: string): Promise<{durationSeconds: number}>;
}

export interface IllustrationAdapter {
  readonly provider: string;
  generate(prompt: string, title: string, outputPath: string): Promise<void>;
}

export interface MusicAdapter {
  readonly provider: string;
  generate(durationSeconds: number, outputPath: string): Promise<{title: string; license: string}>;
}

export interface SoundEffectAdapter {
  readonly provider: string;
  generate(kind: 'WHOOSH' | 'IMPACT', outputPath: string): Promise<{license: string}>;
}

export class StubArchiveAdapter implements ArchiveAdapter {
  async search(_query: string): Promise<ArchiveCandidate[]> {
    throw new Error('No archive provider configured. Add an adapter with licensing and attribution metadata.');
  }
}

export class StubNarrationAdapter implements NarrationAdapter {
  readonly provider = 'stub';
  readonly voice = 'none';
  async synthesize(_text: string, _sourcePath: string, _outputPath: string): Promise<{durationSeconds: number}> {
    throw new Error('No narration provider configured. Add a TTS adapter and credentials.');
  }
}
