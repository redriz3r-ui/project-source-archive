import type {ProductionBrief} from './brief';

export type DirectedShot = {
  id: string;
  passageId: string;
  shotIndex: number;
  narration: string;
  visual: Exclude<ProductionBrief['script'][number]['visual'], 'AUTO'>;
  purpose: 'HOOK' | 'ORIENT' | 'EVIDENCE' | 'EXPLAIN' | 'EMPHASIS' | 'TRANSITION' | 'RESOLUTION';
  motion: 'NONE' | 'PUSH_IN' | 'PULL_OUT' | 'PAN_LEFT' | 'PAN_RIGHT' | 'FLOAT' | 'REVEAL';
  transition: 'CUT' | 'DISSOLVE' | 'WIPE' | 'FLASH';
  chapter?: string;
  sourceIds: string[];
  claimIds: string[];
  asset?: string;
  archiveQuery?: string;
  credit?: string;
  map?: ProductionBrief['script'][number]['map'];
};

const wordCount = (text: string) => text.split(/\s+/).filter(Boolean).length;
const splitSentences = (text: string) => {
  const parts=text.match(/[^.!?]+(?:[.!?]+[”"]?|$)/g)?.map((part) => part.trim()).filter(Boolean) ?? [text];
  const merged:string[]=[];
  for(let index=0;index<parts.length;index++){
    if(wordCount(parts[index])<4&&index+1<parts.length)merged.push(`${parts[index]} ${parts[++index]}`);
    else if(wordCount(parts[index])<4&&merged.length)merged[merged.length-1]+=` ${parts[index]}`;
    else merged.push(parts[index]);
  }
  return merged;
};

const splitForCadence = (text: string): string[] => {
  const sentences = splitSentences(text);
  return sentences.flatMap((sentence) => {
    if (wordCount(sentence) <= 10) return [sentence];
    const sentenceWords = sentence.split(/\s+/);
    const chunkSize = Math.ceil(sentenceWords.length / Math.ceil(sentenceWords.length / 10));
    return Array.from({length: Math.ceil(sentenceWords.length / chunkSize)}, (_, index) => sentenceWords.slice(index * chunkSize, (index + 1) * chunkSize).join(' '));
  });
};

const inferVisual = (text: string, index: number): DirectedShot['visual'] => {
  if (/\b(map|route|border|crossed|moved|journey|region|territory|river|railway|orbit|latitude|longitude|from .+ to)\b/i.test(text)) return 'MAP';
  if (/[“"][^”"]{12,}[”"]/.test(text)) return 'QUOTE_CARD';
  if (/\b(report|document|letter|law|decree|transcript|telegram|newspaper|record)\b/i.test(text)) return 'DOCUMENT_EXCERPT';
  if (/\b\d[\d,.]*(?:\s*[-–]\s*|\s+)(?:percent|%|million|thousand|people|homes|miles|years|days|hours|minutes|feet)\b/i.test(text)) return 'STATISTIC';
  if (/\b(?:1[5-9]|20)\d{2}\b/.test(text)) return 'DATE_CARD';
  if (/\b(because|therefore|meant that|led to|resulted|worked by|how it)\b/i.test(text)) return 'DIAGRAM';
  if (/\b(called|known as|named|symbol|device|object|product|person|president|armstrong|aldrin|eagle|module|camera|experiment)\b/i.test(text)) return 'LABELED_CUTOUT';
  return index % 3 === 0 ? 'ARCHIVE_PHOTO' : index % 3 === 1 ? 'KEN_BURNS' : 'ILLUSTRATION';
};

export const directBrief = (brief: ProductionBrief): DirectedShot[] => {
  const shots: DirectedShot[] = [];
  let previousChapter: string | undefined;
  brief.script.forEach((passage, passageIndex) => {
    if (brief.storyMode === 'EXPLAINED' && passage.chapter && passage.chapter !== previousChapter) {
      shots.push({id: `${passage.id}-chapter`, passageId: passage.id, shotIndex: 0, narration: '', visual: 'CHAPTER_CARD', purpose: 'TRANSITION', motion: 'REVEAL', transition: passageIndex ? 'WIPE' : 'CUT', chapter: passage.chapter, sourceIds: [], claimIds: []});
      previousChapter = passage.chapter;
    }
    splitForCadence(passage.narration).forEach((narration, shotIndex) => {
      const isFirst = passageIndex === 0 && shotIndex === 0;
      const isLast = passageIndex === brief.script.length - 1 && shotIndex === splitForCadence(passage.narration).length - 1;
      shots.push({
        id: `${passage.id}-shot-${shotIndex + 1}`, passageId: passage.id, shotIndex: shotIndex + 1, narration,
        visual: passage.visual === 'AUTO' ? inferVisual(narration, shots.length) : passage.visual,
        purpose: isFirst ? 'HOOK' : isLast ? 'RESOLUTION' : /\d|according|record|report/i.test(narration) ? 'EVIDENCE' : 'EXPLAIN',
        motion: (['PUSH_IN', 'PAN_RIGHT', 'FLOAT', 'PAN_LEFT'] as const)[shots.length % 4],
        transition: shots.length % 7 === 0 ? 'DISSOLVE' : 'CUT', chapter: passage.chapter,
        sourceIds: passage.sourceIds, claimIds: passage.claimIds, asset: passage.asset, archiveQuery: passage.archiveQuery, credit: passage.credit, map: passage.map,
      });
    });
  });
  return shots;
};

export const estimateShotSeconds = (narration: string) => narration ? Math.min(6, Math.max(3, wordCount(narration) / 2.7 + .7)) : 2.4;
