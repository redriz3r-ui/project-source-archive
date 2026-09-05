import {access, copyFile, mkdir, readFile, rename, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';
import {productionBriefSchema} from './brief';
import {planDocumentary} from './planner';
import {collectLocCandidates, promoteLocCandidates} from './archive';
import {narrateManifest} from './narration';
import {captionManifest} from './captions';
import {renderManifest} from './render';
import {assertValidationPassed, validateProduction} from './validation';
import {materializeCreativeAssets} from './creative-assets';

type StageStatus = 'PENDING' | 'COMPLETE' | 'SKIPPED';
type ProductionState = {
  schemaVersion: 1;
  projectId: string;
  title: string;
  briefFile: string;
  manifestFile: string;
  updatedAt: string;
  status: 'IN_PROGRESS' | 'READY_TO_RENDER' | 'COMPLETE';
  stages: Record<'research' | 'planning' | 'archives' | 'narration' | 'captions' | 'validation' | 'render', StageStatus>;
  summary: {scenes: number; sourcedScenes: number; promotedAssets: number; narratedScenes: number; captionedScenes: number; durationSeconds: number};
};

const exists = async (filename: string) => access(filename).then(() => true).catch(() => false);

const inspectManifest = async (manifestFile: string) => {
  const manifest = parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
  const narratedScenes = manifest.scenes.filter((scene) => scene.narration).length;
  return {
    manifest,
    summary: {
      scenes: manifest.scenes.length,
      sourcedScenes: manifest.scenes.filter((scene) => scene.sourceIds.length > 0).length,
      promotedAssets: manifest.scenes.filter((scene) => (scene.type === 'ARCHIVE_PHOTO' || scene.type === 'KEN_BURNS') && scene.payload.archiveItemUrl).length,
      narratedScenes: manifest.scenes.filter((scene) => scene.audio).length,
      captionedScenes: manifest.scenes.filter((scene) => scene.captions?.length).length,
      durationSeconds: Math.max(...manifest.scenes.map((scene) => scene.startFrame + scene.durationFrames)) / manifest.format.fps,
    },
    narrationComplete: narratedScenes > 0 && manifest.scenes.filter((scene) => scene.narration && !scene.audio).length === 0,
    captionsComplete: narratedScenes > 0 && manifest.scenes.filter((scene) => scene.narration && scene.audio && !scene.captions?.length).length === 0,
  };
};

const writeState = async (projectDir: string, state: ProductionState) => {
  state.updatedAt = new Date().toISOString();
  await writeFile(path.join(projectDir, 'production-state.json'), `${JSON.stringify(state, null, 2)}\n`);
};

export const runProduction = async (briefFilename: string, options: {voice: string; rate: number; archives: boolean; forceNarration: boolean; render: boolean; researchReport?: string; refreshPlan?: boolean}) => {
  const absoluteBrief = path.resolve(briefFilename);
  const brief = productionBriefSchema.parse(JSON.parse(await readFile(absoluteBrief, 'utf8')));
  const planned = planDocumentary(brief);
  const projectDir = path.resolve('public/projects', planned.id);
  const manifestFile = path.join(projectDir, 'manifest.json');
  await mkdir(projectDir, {recursive: true});
  if (!await exists(manifestFile)) await writeFile(manifestFile, `${JSON.stringify(planned, null, 2)}\n`);
  else if (options.refreshPlan) {
    const previous = parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    await copyFile(manifestFile, path.join(projectDir, `manifest.before-replan-${stamp}.json`));
    for (const report of ['archive-candidates.json', 'archive-promotions.json', 'narration-report.json', 'caption-report.json', 'validation-report.json', 'render-report.json']) {
      const reportFile = path.join(projectDir, report);
      if (await exists(reportFile)) await rename(reportFile, path.join(projectDir, `${path.parse(report).name}.before-replan-${stamp}${path.extname(report)}`));
    }
    for (const scene of planned.scenes) {
      if (scene.type !== 'ARCHIVE_PHOTO' && scene.type !== 'KEN_BURNS') continue;
      const old = previous.scenes.find((candidate) => candidate.id === scene.id);
      if (!old || (old.type !== 'ARCHIVE_PHOTO' && old.type !== 'KEN_BURNS')) continue;
      if (old.payload.rightsStatus !== 'NO_KNOWN_RESTRICTIONS' && old.payload.rightsStatus !== 'LICENSED') continue;
      scene.payload = {...scene.payload, src: old.payload.src, archiveItemUrl: old.payload.archiveItemUrl, rightsStatus: old.payload.rightsStatus, credit: old.payload.credit};
      scene.sourceIds = [...new Set([...scene.sourceIds, ...old.sourceIds])];
    }
    for (const source of previous.sources) if (!planned.sources.some((candidate) => candidate.id === source.id)) planned.sources.push(source);
    await writeFile(manifestFile, `${JSON.stringify(parseManifest(planned), null, 2)}\n`);
  }

  const state: ProductionState = {
    schemaVersion: 1,
    projectId: planned.id,
    title: brief.title,
    briefFile: absoluteBrief,
    manifestFile,
    updatedAt: new Date().toISOString(),
    status: 'IN_PROGRESS',
    stages: {research: options.researchReport ? 'COMPLETE' : 'SKIPPED', planning: 'COMPLETE', archives: 'PENDING', narration: 'PENDING', captions: 'PENDING', validation: 'PENDING', render: 'PENDING'},
    summary: (await inspectManifest(manifestFile)).summary,
  };
  const oldState = path.join(projectDir, 'production-state.json');
  if (await exists(oldState)) await copyFile(oldState, path.join(projectDir, `production-state.before-${new Date().toISOString().replace(/[:.]/g, '-')}.json`));
  await writeState(projectDir, state);

  const hasArchiveQueries = (await inspectManifest(manifestFile)).manifest.scenes.some((scene) => (scene.type === 'ARCHIVE_PHOTO' || scene.type === 'KEN_BURNS') && scene.payload.archiveQuery);
  if (!options.archives || !hasArchiveQueries) {
    state.stages.archives = 'SKIPPED';
  } else {
    const candidateReport = path.join(projectDir, 'archive-candidates.json');
    const promotionReport = path.join(projectDir, 'archive-promotions.json');
    if (!await exists(candidateReport)) await collectLocCandidates(manifestFile, true);
    if (!await exists(promotionReport)) await promoteLocCandidates(manifestFile);
    state.stages.archives = 'COMPLETE';
  }
  state.summary = (await inspectManifest(manifestFile)).summary;
  await writeState(projectDir, state);

  const inspected = await inspectManifest(manifestFile);
  if (!inspected.narrationComplete || options.forceNarration) await narrateManifest(manifestFile, options.voice, options.rate);
  state.stages.narration = 'COMPLETE';
  state.summary = (await inspectManifest(manifestFile)).summary;
  await writeState(projectDir, state);

  await materializeCreativeAssets(manifestFile);

  if (!(await inspectManifest(manifestFile)).captionsComplete) await captionManifest(manifestFile);
  state.stages.captions = 'COMPLETE';
  state.summary = (await inspectManifest(manifestFile)).summary;
  await writeState(projectDir, state);

  parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
  const validation = await validateProduction(manifestFile, {researchReport: options.researchReport});
  assertValidationPassed(validation);
  state.stages.validation = 'COMPLETE';
  state.status = 'READY_TO_RENDER';
  state.summary = (await inspectManifest(manifestFile)).summary;
  await writeState(projectDir, state);
  if (options.render) {
    await renderManifest(manifestFile);
    const finalValidation = await validateProduction(manifestFile, {researchReport: options.researchReport, requireRender: true});
    assertValidationPassed(finalValidation);
    state.stages.render = 'COMPLETE';
    state.status = 'COMPLETE';
    await writeState(projectDir, state);
  }
  return {stateFile: path.join(projectDir, 'production-state.json'), state};
};

export const getProductionStatus = async (manifestFilename: string) => {
  const manifestFile = path.resolve(manifestFilename);
  const projectDir = path.dirname(manifestFile);
  const stateFile = path.join(projectDir, 'production-state.json');
  if (await exists(stateFile)) return JSON.parse(await readFile(stateFile, 'utf8')) as ProductionState;
  const inspected = await inspectManifest(manifestFile);
  return {manifestFile, status: 'UNTRACKED', summary: inspected.summary};
};
