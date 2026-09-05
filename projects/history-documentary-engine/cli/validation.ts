import {access, readFile, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';
import {researchReportSchema} from './research';

type Check = {category: 'research' | 'editorial' | 'rights' | 'asset' | 'audio' | 'caption' | 'manifest' | 'pacing' | 'visual' | 'provenance' | 'render'; level: 'PASS' | 'WARNING' | 'ERROR'; message: string};
const exists = (filename: string) => access(filename).then(() => true).catch(() => false);

export const validateProduction = async (manifestFilename: string, options: {researchReport?: string; requireRender?: boolean} = {}) => {
  const manifestFile = path.resolve(manifestFilename);
  const projectDir = path.dirname(manifestFile);
  const manifest = parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
  const checks: Check[] = [];
  const add = (category: Check['category'], level: Check['level'], message: string) => checks.push({category, level, message});

  if (options.researchReport) {
    try {
      const research = researchReportSchema.parse(JSON.parse(await readFile(path.resolve(options.researchReport), 'utf8')));
      add('research', research.status === 'PASS' ? 'PASS' : 'ERROR', `Research status is ${research.status}; ${research.claims.length} claims and ${research.conflicts.length} conflicts`);
      if (research.claims.some((claim) => !claim.sourceIds.length || !claim.evidence)) add('research', 'ERROR', 'One or more claims lack evidence or sources');
      else add('research', 'PASS', 'Every research claim has evidence and at least one source');
      const knownClaims = new Set(research.claims.map((claim) => claim.id));
      const scenesWithoutClaims = manifest.scenes.filter((scene) => scene.narration && (!scene.claimIds.length || scene.claimIds.some((id) => !knownClaims.has(id))));
      add('editorial', scenesWithoutClaims.length ? 'ERROR' : 'PASS', scenesWithoutClaims.length ? `Missing or unknown claim citations in: ${scenesWithoutClaims.map((scene) => scene.id).join(', ')}` : 'Every narration beat cites specific evidence-ledger claim IDs');
    } catch (error) { add('research', 'ERROR', `Research report invalid: ${error instanceof Error ? error.message : error}`); }
  } else add('research', 'WARNING', 'No research report supplied to validator');

  const knownSources = new Set(manifest.sources.map((source) => source.id));
  const narrativeScenes = manifest.scenes.filter((scene) => scene.narration);
  add('editorial', narrativeScenes.length >= 6 ? 'PASS' : 'ERROR', `${narrativeScenes.length} narrated story beats (minimum 6)`);
  const uncited = narrativeScenes.filter((scene) => !scene.sourceIds.length || scene.sourceIds.some((id) => !knownSources.has(id)));
  add('editorial', uncited.length ? 'ERROR' : 'PASS', uncited.length ? `Uncited/unknown sources in: ${uncited.map((scene) => scene.id).join(', ')}` : 'All narration beats cite known sources');

  const missingDirection = manifest.scenes.filter((scene) => !scene.direction);
  add('provenance', missingDirection.length ? 'ERROR' : 'PASS', missingDirection.length ? `Missing visual direction/provenance: ${missingDirection.map((scene) => scene.id).join(', ')}` : 'Every shot records passage, purpose, motion, and transition');
  const weakProvenance = narrativeScenes.filter((scene) => !scene.claimIds.length || !scene.sourceIds.length || !scene.direction?.passageId);
  add('provenance', weakProvenance.length ? 'ERROR' : 'PASS', weakProvenance.length ? `Incomplete claim-to-shot provenance: ${weakProvenance.map((scene) => scene.id).join(', ')}` : 'Every narrated shot preserves claim and source lineage');

  const imageScenes = manifest.scenes.filter((scene) => scene.type === 'ARCHIVE_PHOTO' || scene.type === 'KEN_BURNS');
  const sourceReportFile = path.join(projectDir, 'asset-source-report.json');
  const sourceReport = await exists(sourceReportFile) ? JSON.parse(await readFile(sourceReportFile, 'utf8')) as {usages?: Array<{sceneId?:string;localFile:string;cropVariant:string;editorialPurpose?:string;fairUseRationale?:string}>} : null;
  const rightsProblems = imageScenes.filter((scene) => {
    if (scene.payload.rightsStatus === 'NO_KNOWN_RESTRICTIONS' || scene.payload.rightsStatus === 'LICENSED') return false;
    if (scene.payload.rightsStatus !== 'EDITORIAL_FAIR_USE') return true;
    const usage=sourceReport?.usages?.find((item)=>item.sceneId===scene.id);
    return !usage?.fairUseRationale || !usage.editorialPurpose;
  });
  add('rights', rightsProblems.length ? 'ERROR' : 'PASS', rightsProblems.length ? `Uncleared image scenes: ${rightsProblems.map((scene) => scene.id).join(', ')}` : 'All archive images have clear rights metadata');
  for (const scene of imageScenes) {
    const asset = path.resolve('public', scene.payload.src);
    if (!await exists(asset)) add('asset', 'ERROR', `${scene.id}: asset missing (${scene.payload.src})`);
    else add('asset', (await stat(asset)).size > 1000 ? 'PASS' : 'ERROR', `${scene.id}: asset exists (${(await stat(asset)).size} bytes)`);
  }
  const generatedImageScenes = manifest.scenes.filter((scene) => scene.type === 'ILLUSTRATION' || scene.type === 'LABELED_CUTOUT');
  for (const scene of generatedImageScenes) {
    const asset = path.resolve('public', scene.payload.src);
    if (!await exists(asset)) add('asset', 'ERROR', `${scene.id}: generated visual missing (${scene.payload.src})`);
    else add('asset', (await stat(asset)).size > 500 ? 'PASS' : 'ERROR', `${scene.id}: generated visual exists (${(await stat(asset)).size} bytes)`);
    add('rights', scene.payload.rightsStatus === 'LICENSED' && Boolean(scene.payload.credit) ? 'PASS' : 'ERROR', `${scene.id}: original visual rights and credit metadata`);
  }

  const shotSeconds = manifest.scenes.filter((scene) => scene.type !== 'TITLE_CARD' && scene.type !== 'CHAPTER_CARD').map((scene) => scene.durationFrames / manifest.format.fps);
  const overlong = manifest.scenes.filter((scene) => scene.type !== 'TITLE_CARD' && scene.type !== 'CHAPTER_CARD' && scene.durationFrames / manifest.format.fps > 7);
  const tooBrief = manifest.scenes.filter((scene) => scene.type !== 'TITLE_CARD' && scene.type !== 'CHAPTER_CARD' && scene.durationFrames / manifest.format.fps < 2);
  const averageShot = shotSeconds.reduce((sum, value) => sum + value, 0) / Math.max(1, shotSeconds.length);
  add('pacing', overlong.length ? 'ERROR' : 'PASS', overlong.length ? `Shots exceed 7s: ${overlong.map((scene) => scene.id).join(', ')}` : `All content shots meet the 2–7 second cadence target (average ${averageShot.toFixed(2)}s)`);
  add('pacing', tooBrief.length ? 'ERROR' : 'PASS', tooBrief.length ? `Shots are too brief to register visually: ${tooBrief.map((scene) => scene.id).join(', ')}` : 'Every content shot remains visible long enough to read');
  const visualTypes = new Set(manifest.scenes.map((scene) => scene.type));
  const visualTreatments = new Set(manifest.scenes.map((scene) => `${scene.type}:${scene.direction?.motion ?? 'NONE'}:${scene.type === 'KEN_BURNS' ? `${scene.payload.focalPoint?.x ?? .5},${scene.payload.focalPoint?.y ?? .5}` : 'default'}`));
  const requiredVariety = manifest.scenes.length >= 10 ? 5 : 3;
  add('visual', visualTreatments.size < requiredVariety ? 'ERROR' : 'PASS', `${visualTypes.size} scene types with ${visualTreatments.size} distinct editorial treatments (minimum ${requiredVariety})`);
  const visualSources = manifest.scenes.flatMap((scene) => scene.type === 'ARCHIVE_PHOTO' || scene.type === 'KEN_BURNS' || scene.type === 'ILLUSTRATION' || scene.type === 'LABELED_CUTOUT' ? [scene.payload.src] : []);
  const repeated = [...new Set(visualSources.filter((src, index) => visualSources.indexOf(src) !== index))];
  if (repeated.length) {
    if (!await exists(sourceReportFile)) add('visual', 'ERROR', 'Repeated visual assets lack an asset/source report');
    else {
      const usages = sourceReport?.usages ?? [];
      const undocumented = repeated.filter((src) => {
        const localFile = src.replace(new RegExp(`^projects/${path.basename(projectDir)}/`), '');
        const variants = usages.filter((usage) => usage.localFile === localFile).map((usage) => usage.cropVariant);
        return variants.length !== visualSources.filter((candidate) => candidate === src).length || new Set(variants).size !== variants.length;
      });
      add('visual', undocumented.length ? 'ERROR' : 'PASS', undocumented.length ? `Repeated assets lack distinct documented crops: ${undocumented.join(', ')}` : `${repeated.length} reused archive assets have distinct, documented editorial crops`);
    }
  } else add('visual', 'PASS', 'No visual asset is reused');

  const missingAudio = narrativeScenes.filter((scene) => !scene.audio);
  add('audio', missingAudio.length ? 'ERROR' : 'PASS', missingAudio.length ? `Missing narration audio: ${missingAudio.map((scene) => scene.id).join(', ')}` : 'Every narration beat has measured audio');
  for (const scene of narrativeScenes) if (scene.audio && !await exists(path.resolve('public', scene.audio.src))) add('audio', 'ERROR', `${scene.id}: audio file missing`);
  if (!manifest.soundtrack) add('audio', 'ERROR', 'Background music plan is missing');
  else {
    add('audio', await exists(path.resolve('public', manifest.soundtrack.src)) ? 'PASS' : 'ERROR', `Soundtrack asset: ${manifest.soundtrack.src}`);
    add('audio', manifest.soundtrack.duckVolume < manifest.soundtrack.baseVolume ? 'PASS' : 'ERROR', `Automatic narration ducking ${manifest.soundtrack.baseVolume} → ${manifest.soundtrack.duckVolume}`);
    add('rights', manifest.soundtrack.license.length > 3 ? 'PASS' : 'ERROR', `Soundtrack license: ${manifest.soundtrack.license}`);
  }
  add('audio', manifest.soundEffects.length ? 'PASS' : 'ERROR', `${manifest.soundEffects.length} planned transition/emphasis sound cues`);
  for (const cue of manifest.soundEffects) {
    if (!await exists(path.resolve('public', cue.src))) add('audio', 'ERROR', `${cue.id}: sound effect missing`);
    if (!cue.license) add('rights', 'ERROR', `${cue.id}: sound effect license missing`);
  }

  const captionProblems = narrativeScenes.filter((scene) => !scene.captions?.length || (scene.captions.at(-1)?.endFrame ?? 0) > scene.durationFrames);
  add('caption', captionProblems.length ? 'ERROR' : 'PASS', captionProblems.length ? `Caption coverage invalid: ${captionProblems.map((scene) => scene.id).join(', ')}` : 'Every narration beat has in-bounds timed captions');

  const sorted = [...manifest.scenes].sort((a, b) => a.startFrame - b.startFrame);
  const timelineProblems = sorted.filter((scene, index) => index > 0 && scene.startFrame !== sorted[index - 1].startFrame + sorted[index - 1].durationFrames);
  add('manifest', timelineProblems.length ? 'ERROR' : 'PASS', timelineProblems.length ? `Timeline gaps/overlaps before: ${timelineProblems.map((scene) => scene.id).join(', ')}` : 'Timeline is contiguous and non-overlapping');

  const renderReportFile = path.join(projectDir, 'render-report.json');
  if (options.requireRender) {
    if (!await exists(renderReportFile)) add('render', 'ERROR', 'Render report missing');
    else {
      const render = JSON.parse(await readFile(renderReportFile, 'utf8')) as {verified?: boolean; outputFile?: string};
      add('render', render.verified && render.outputFile && await exists(render.outputFile) ? 'PASS' : 'ERROR', render.verified ? 'Verified rendered media exists' : 'Rendered media is not verified');
    }
  }
  const errors = checks.filter((check) => check.level === 'ERROR');
  const report = {schemaVersion: 1, generatedAt: new Date().toISOString(), manifestFile, status: errors.length ? 'FAIL' : 'PASS', checks, summary: {passed: checks.filter((check) => check.level === 'PASS').length, warnings: checks.filter((check) => check.level === 'WARNING').length, errors: errors.length}};
  const reportFile = path.join(projectDir, 'validation-report.json');
  await writeFile(reportFile, `${JSON.stringify(report, null, 2)}\n`);
  return {report, reportFile};
};

export const assertValidationPassed = (result: Awaited<ReturnType<typeof validateProduction>>) => {
  if (result.report.status !== 'PASS') throw new Error(`Validation gate failed with ${result.report.summary.errors} error(s). See ${result.reportFile}`);
};
