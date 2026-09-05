import {writeFile} from 'node:fs/promises';
import type {IllustrationAdapter, MusicAdapter, SoundEffectAdapter} from '../adapters';

const escapeXml = (value: string) => value.replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'}[character] ?? character));
const lines = (text: string, max = 31) => {
  const words = text.split(/\s+/);
  const result: string[] = [];
  let line = '';
  for (const word of words) {
    if (`${line} ${word}`.trim().length > max) { result.push(line); line = word; }
    else line = `${line} ${word}`.trim();
  }
  if (line) result.push(line);
  return result.slice(0, 5);
};

export class ProceduralIllustrationAdapter implements IllustrationAdapter {
  readonly provider = 'procedural-svg';
  async generate(prompt: string, title: string, outputPath: string) {
    const copy = lines(title || prompt);
    const hash = [...prompt].reduce((value, character) => ((value * 31 + character.charCodeAt(0)) >>> 0), 2166136261);
    const palettes = [['#101926', '#8f302d', '#f05a3d'], ['#17241d', '#875d32', '#e7b85c'], ['#23182d', '#3e648d', '#d35f6d'], ['#222019', '#4f6e69', '#d17b45']];
    const [dark, mid, accent] = palettes[hash % palettes.length];
    const flip = hash % 2 === 0;
    const orbX = 820 + hash % 330;
    const orbY = 145 + hash % 170;
    const mountain = 620 + hash % 210;
    const text = copy.map((line, index) => `<text x="88" y="${395 + index * 62}" font-family="Georgia" font-size="48" font-weight="700" fill="#f4ead2">${escapeXml(line)}</text>`).join('');
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><defs><linearGradient id="g" x2="${flip ? 1 : 0}" y2="1"><stop stop-color="${dark}"/><stop offset="1" stop-color="${mid}"/></linearGradient><filter id="n"><feTurbulence baseFrequency=".5" numOctaves="3"/><feBlend mode="soft-light" in="SourceGraphic"/></filter></defs><rect width="1280" height="720" fill="url(#g)"/><circle cx="${orbX}" cy="${orbY}" r="${130 + hash % 90}" fill="${accent}" opacity=".82"/><path d="M${mountain} 670 ${mountain + 190} ${100 + hash % 150}l${80 + hash % 70} ${120 + hash % 60} ${100 + hash % 80}-${90 + hash % 60} 150 540Z" fill="${dark}" opacity=".78"/><path d="M0 ${580 + hash % 70}Q280 ${470 + hash % 80} 560 650T1280 ${550 + hash % 80}V720H0Z" fill="#080a0d" opacity=".68"/><rect x="68" y="72" width="9" height="520" fill="${accent}"/>${text}<text x="90" y="110" font-family="Arial" font-size="18" font-weight="800" letter-spacing="5" fill="${accent}">VISUAL RECONSTRUCTION</text><rect width="1280" height="720" filter="url(#n)" opacity=".14"/></svg>`;
    await writeFile(outputPath, svg);
  }
}

export class ProceduralMusicAdapter implements MusicAdapter {
  readonly provider = 'procedural-ambient';
  async generate(durationSeconds: number, outputPath: string) {
    const sampleRate = 22050;
    const samples = Math.ceil(durationSeconds * sampleRate);
    const data = Buffer.alloc(samples * 2);
    for (let i = 0; i < samples; i++) {
      const t = i / sampleRate;
      const pulse = .55 + .45 * Math.sin(Math.PI * 2 * t / 4);
      const value = (Math.sin(Math.PI * 2 * 55 * t) * .34 + Math.sin(Math.PI * 2 * 82.5 * t) * .2 + Math.sin(Math.PI * 2 * 110 * t) * .1) * pulse;
      data.writeInt16LE(Math.round(value * 32767 * .18), i * 2);
    }
    const header = Buffer.alloc(44);
    header.write('RIFF', 0); header.writeUInt32LE(36 + data.length, 4); header.write('WAVEfmt ', 8); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(1, 22); header.writeUInt32LE(sampleRate, 24); header.writeUInt32LE(sampleRate * 2, 28); header.writeUInt16LE(2, 32); header.writeUInt16LE(16, 34); header.write('data', 36); header.writeUInt32LE(data.length, 40);
    await writeFile(outputPath, Buffer.concat([header, data]));
    return {title: 'Procedural documentary pulse', license: 'Original generated asset — CC0 dedication'};
  }
}

const wav = (samples: Int16Array, sampleRate: number) => {
  const data = Buffer.from(samples.buffer);
  const header = Buffer.alloc(44);
  header.write('RIFF', 0); header.writeUInt32LE(36 + data.length, 4); header.write('WAVEfmt ', 8); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(1, 22); header.writeUInt32LE(sampleRate, 24); header.writeUInt32LE(sampleRate * 2, 28); header.writeUInt16LE(2, 32); header.writeUInt16LE(16, 34); header.write('data', 36); header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
};

export class ProceduralSoundEffectAdapter implements SoundEffectAdapter {
  readonly provider = 'procedural-sfx';
  async generate(kind: 'WHOOSH' | 'IMPACT', outputPath: string) {
    const sampleRate = 22050;
    const duration = kind === 'WHOOSH' ? .42 : .24;
    const samples = new Int16Array(Math.ceil(sampleRate * duration));
    for (let i = 0; i < samples.length; i++) {
      const t = i / sampleRate;
      const envelope = Math.sin(Math.PI * i / samples.length) ** 2;
      const frequency = kind === 'WHOOSH' ? 130 + 700 * (i / samples.length) : 72;
      const signal = kind === 'WHOOSH' ? Math.sin(Math.PI * 2 * frequency * t) * envelope : Math.sin(Math.PI * 2 * frequency * t) * Math.exp(-t * 16);
      samples[i] = Math.round(signal * 32767 * .34);
    }
    await writeFile(outputPath, wav(samples, sampleRate));
    return {license: 'Original generated asset — CC0 dedication'};
  }
}
