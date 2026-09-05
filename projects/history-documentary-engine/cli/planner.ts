import type {ProductionBrief} from './brief';
import {parseManifest, type DocumentaryManifest, type Scene} from '../src/manifest/schema';
import {directBrief, estimateShotSeconds} from './visual-director';

const slugify = (value: string) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export const planDocumentary = (brief: ProductionBrief): DocumentaryManifest => {
  const fps = 30;
  let cursor = 0;
  const scenes: Scene[] = [{
    id: 'opening', type: 'TITLE_CARD', startFrame: cursor, durationFrames: fps * 3,
    sourceIds: [], claimIds: [], reviewStatus: 'DRAFT', payload: {eyebrow: brief.storyMode === 'EXPLAINED' ? 'EVERY STORY EXPLAINED' : 'A SHORT HISTORY', title: brief.title, subtitle: brief.topic},
    direction: {passageId: 'opening', shotIndex: 0, purpose: 'HOOK', motion: 'REVEAL', transition: 'CUT'},
  }];
  cursor += fps * 3;

  for (const shot of directBrief(brief)) {
    const durationFrames = Math.round(estimateShotSeconds(shot.narration) * fps);
    const direction = {passageId: shot.passageId, shotIndex: shot.shotIndex, purpose: shot.purpose, motion: shot.motion, transition: shot.transition};
    const common = {id: shot.id, startFrame: cursor, durationFrames, caption: shot.narration || undefined, narration: shot.narration || undefined, sourceIds: shot.sourceIds, claimIds: shot.claimIds, reviewStatus: shot.narration ? 'SOURCED' as const : 'DRAFT' as const, direction};
    const source = brief.sources.find((item) => shot.sourceIds.includes(item.id));
    const type = shot.visual;
    if (type === 'CHAPTER_CARD') {
      scenes.push({...common, type, payload: {index: scenes.filter((scene) => scene.type === 'CHAPTER_CARD').length + 1, title: shot.chapter ?? 'Next chapter', kicker: brief.title}});
    } else if (type === 'MAP') {
      const isLunar = /\b(moon|lunar|apollo|latitude|longitude|orbit)\b/i.test(`${brief.topic} ${shot.narration}`);
      const map = shot.map ?? (isLunar
        ? {label: /latitude|longitude/i.test(shot.narration) ? 'Landing coordinates' : 'The path to the Moon', region: brief.topic, points: [{name: 'Earth', x: .2, y: .66}, {name: /latitude|longitude/i.test(shot.narration) ? 'Sea of Tranquility' : 'Apollo 11', x: .52, y: .42}, {name: 'Moon', x: .82, y: .3}], route: [.2, .66, .38, .54, .52, .42, .7, .34, .82, .3]}
        : {label: 'Geographic context', region: brief.topic, points: [{name: 'Origin', x: .24, y: .62}, {name: 'Destination', x: .76, y: .4}], route: [.24, .62, .48, .52, .76, .4]});
      scenes.push({...common, type, payload: {renderer: 'offline-svg', ...map}});
    } else if (type === 'DOCUMENT_EXCERPT') {
      scenes.push({...common, type, payload: {heading: 'From the historical record', excerpt: shot.narration, document: source?.title}});
    } else if (type === 'QUOTE_CARD') {
      scenes.push({...common, type, payload: {quote: shot.narration.match(/[“"]([^”"]+)[”"]/)?.[1] ?? shot.narration, attribution: source?.publisher ?? 'Historical source'}});
    } else if (type === 'STATISTIC') {
      const value = shot.narration.match(/\b\d[\d,.]*(?:\s+million|\s+thousand|\s*%|\s+percent)?/i)?.[0] ?? '—';
      scenes.push({...common, type, payload: {value, label: shot.narration}});
    } else if (type === 'DATE_CARD') {
      scenes.push({...common, type, payload: {date: shot.narration.match(/\b(?:1[5-9]|20)\d{2}\b/)?.[0] ?? 'DATE', headline: shot.narration}});
    } else if (type === 'DIAGRAM') {
      const parts = shot.narration.split(/\b(?:because|therefore|which|and|but)\b/i).map((part) => part.trim()).filter(Boolean);
      scenes.push({...common, type, payload: {title: shot.chapter ?? 'How it connects', nodes: (parts.length > 1 ? parts : [shot.narration, 'Historical consequence']).slice(0, 3).map((label) => ({label})), relation: 'CAUSE → EFFECT'}});
    } else {
      const src = shot.asset ?? `projects/${slugify(brief.title)}/generated/${shot.id}.svg`;
      const baseImage = {src, archiveQuery: shot.archiveQuery, rightsStatus: shot.asset ? undefined : 'PLACEHOLDER' as const, alt: `Visual for: ${shot.narration.slice(0, 90)}`, credit: shot.credit ?? (type === 'ILLUSTRATION' ? 'Original procedural illustration' : 'PLACEHOLDER — archive asset required')};
      if (type === 'LABELED_CUTOUT') scenes.push({...common, type, payload: {...baseImage, label: shot.chapter ?? brief.topic, detail: shot.narration}});
      else if (type === 'ILLUSTRATION') scenes.push({...common, type, payload: {...baseImage, prompt: `Editorial historical illustration: ${shot.narration}`, provider: 'mock-svg'}});
      else if (type === 'ARCHIVE_PHOTO') scenes.push({...common, type, payload: baseImage});
      else scenes.push({...common, type: 'KEN_BURNS', payload: {...baseImage, zoomFrom: 1, zoomTo: 1.13, panX: -18, panY: -10}});
    }
    cursor += durationFrames;
  }

  return parseManifest({
    schemaVersion: 1, id: slugify(brief.title), title: brief.title, topic: brief.topic, storyMode: brief.storyMode,
    format: {width: 1280, height: 720, fps}, theme: {ink: '#171713', paper: '#e7dfcb', accent: '#f05a3d'},
    sources: brief.sources, adapters: {archive: 'stub', map: 'offline-svg', narration: 'stub'}, scenes,
  });
};
