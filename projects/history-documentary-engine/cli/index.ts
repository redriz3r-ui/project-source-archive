import {readFile, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest, type DocumentaryManifest} from '../src/manifest/schema';
import {productionBriefSchema} from './brief';
import {planDocumentary} from './planner';
import {collectLocCandidates, promoteLocCandidates, searchLoc} from './archive';
import {narrateManifest} from './narration';
import {getProductionStatus, runProduction} from './production';
import {captionManifest} from './captions';
import {renderManifest} from './render';
import {loadResearchReport, researchTopic} from './research';
import {validateProduction} from './validation';
import {materializeCreativeAssets} from './creative-assets';
import {chooseDirectorOption, createDirectorState, loadDirectorState, saveDirectorState, setDirectorCheckpointOptions} from './director';
import {continueEpisode} from './resume';
import {createAgenticLocalBrief,createLocalBrief} from './local-documentary';

const slugify = (value: string) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

const makeManifest = (title: string, topic: string): DocumentaryManifest => parseManifest({
  schemaVersion: 1,
  id: slugify(title),
  title,
  topic,
  format: {width: 1280, height: 720, fps: 30},
  theme: {ink: '#171713', paper: '#e7dfcb', accent: '#9f382d'},
  adapters: {archive: 'stub', map: 'offline-svg', narration: 'stub'},
  scenes: [
    {id: 'opening', type: 'TITLE_CARD', startFrame: 0, durationFrames: 120, payload: {eyebrow: 'A SHORT HISTORY', title, subtitle: topic}},
    {id: 'placeholder-archive', type: 'ARCHIVE_PHOTO', startFrame: 120, durationFrames: 150, caption: 'Replace this demo caption with a sourced historical claim.', payload: {src: 'assets/harbor-archive.svg', alt: 'Placeholder archival illustration', credit: 'Demo artwork — replace before publishing'}},
    {id: 'placeholder-map', type: 'MAP', startFrame: 270, durationFrames: 150, caption: 'Map data is illustrative until a cited source is added.', payload: {label: 'A Changing Landscape', year: 'DATE', region: topic, points: [{name: 'Origin', x: .22, y: .63}, {name: 'Destination', x: .78, y: .38}], route: [.22, .63, .44, .52, .6, .46, .78, .38]}},
  ],
});

const args = process.argv.slice(2);
const option = (name: string) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };

const main = async () => {
  const command = args[0] ?? 'generate';
  if (command === 'continue') {
    const projectId=args[1];
    if (!projectId) throw new Error('Usage: npm run documentary -- continue <project-id> [--dry-run] [--revise-scene <id> --asset-id <id>]');
    const result=await continueEpisode(projectId,{dryRun:args.includes('--dry-run'),sceneId:option('--revise-scene'),assetId:option('--asset-id')});
    console.log(`${result.ledger.lastRun?.result}. Stage: ${result.ledger.currentStage}; next: ${result.ledger.nextAction}`);
    return;
  }
  if (command === 'director-start') {
    const projectId = option('--project') ?? 'episode-1';
    const filename = await saveDirectorState(createDirectorState(projectId));
    console.log(`Director workflow ready at Topic and Audience Promise -> ${filename}`);
    return;
  }
  if (command === 'director-status') {
    const stateFile = args[1];
    if (!stateFile) throw new Error('Usage: npm run documentary -- director-status <director-state.json>');
    console.log(JSON.stringify(await loadDirectorState(stateFile), null, 2));
    return;
  }
  if (command === 'director-choose') {
    const stateFile = args[1];
    const choiceId = args[2];
    if (!stateFile || !choiceId) throw new Error('Usage: npm run documentary -- director-choose <director-state.json> <option-id>');
    const result = await chooseDirectorOption(stateFile, choiceId);
    console.log(`Choice saved; next checkpoint: ${result.state.activeCheckpoint}. Backup: ${result.backup}`);
    return;
  }
  if (command === 'director-options') {
    const stateFile = args[1];
    const optionsFile = args[2];
    if (!stateFile || !optionsFile) throw new Error('Usage: npm run documentary -- director-options <director-state.json> <options.json>');
    const input = JSON.parse(await readFile(optionsFile, 'utf8')) as {checkpointId: Parameters<typeof setDirectorCheckpointOptions>[1]; options: Parameters<typeof setDirectorCheckpointOptions>[2]};
    const result = await setDirectorCheckpointOptions(stateFile, input.checkpointId, input.options);
    console.log(`Options saved for ${input.checkpointId}. Backup: ${result.backup}`);
    return;
  }
  if (command === 'creative-assets') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- creative-assets <manifest.json>');
    const result = await materializeCreativeAssets(manifestFile);
    console.log(`Generated ${result.generatedScenes} original visuals and a licensed soundtrack -> ${result.reportFile}`);
    return;
  }
  if (command === 'run') {
    const briefFile = args[1];
    if (!briefFile) throw new Error('Usage: npm run documentary -- run <brief.json> [--render] [--no-archives] [--voice Samantha] [--rate 175] [--force-narration]');
    const result = await runProduction(briefFile, {voice: option('--voice') ?? 'Samantha', rate: Number(option('--rate') ?? 175), archives: !args.includes('--no-archives'), forceNarration: args.includes('--force-narration'), render: args.includes('--render'), researchReport: option('--research'), refreshPlan: args.includes('--refresh')});
    console.log(`Production ${result.state.status}: ${result.state.title} (${result.state.summary.durationSeconds.toFixed(1)}s) -> ${result.stateFile}`);
    return;
  }
  if (command === 'render-project') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- render-project <manifest.json>');
    const result = await renderManifest(manifestFile);
    console.log(`Verified MP4 (${result.verification.durationSeconds.toFixed(1)}s) -> ${result.outputFile}`);
    return;
  }
  if (command === 'research') {
    const title = option('--title');
    const topic = option('--topic') ?? title;
    if (!title || !topic) throw new Error('Usage: npm run documentary -- research --title "Title" [--topic "Historical topic"]');
    const result = await researchTopic(title, topic);
    console.log(`Research ${result.report.status}: ${result.report.claims.length} claims from ${result.report.sources.length - 1} authoritative sources -> ${result.briefFile}`);
    return;
  }
  if (command === 'create') {
    const title = option('--title');
    const topic = option('--topic') ?? title;
    if (!title || !topic) throw new Error('Usage: npm run documentary -- create --title "Title" [--topic "Historical topic"] [--voice Samantha] [--render]');
    const suppliedResearch=option('--research');
    const researched=suppliedResearch
      ? {report:await loadResearchReport(suppliedResearch),reportFile:path.resolve(suppliedResearch),briefFile:path.join(path.dirname(path.resolve(suppliedResearch)),'production-brief.json')}
      : await researchTopic(title, topic);
    if(researched.report.title!==title)throw new Error(`Research title “${researched.report.title}” does not match requested title “${title}”`);
    const local=args.includes('--local');
    const agentic=args.includes('--agentic');
    const briefFile=local?(agentic
      ?(await createAgenticLocalBrief(researched.report,path.dirname(researched.briefFile),option('--model'))).briefFile
      :(await createLocalBrief(researched.report,path.dirname(researched.briefFile),option('--model'))).briefFile):researched.briefFile;
    const result = await runProduction(briefFile, {voice: option('--voice') ?? 'Samantha', rate: Number(option('--rate') ?? 175), archives: !args.includes('--no-archives'), forceNarration: args.includes('--force-narration'), render: !local&&args.includes('--render'), researchReport: researched.reportFile, refreshPlan: args.includes('--refresh')});
    console.log(`Documentary ${result.state.status}: ${title} -> ${result.stateFile}`);
    if(local&&args.includes('--render'))console.log('Local workflow stopped before rendering. Inspect the manifest, then use render-project explicitly.');
    return;
  }
  if (command === 'validate-production') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- validate-production <manifest.json> [--research <report.json>] [--require-render]');
    const result = await validateProduction(manifestFile, {researchReport: option('--research'), requireRender: args.includes('--require-render')});
    console.log(`Validation ${result.report.status}: ${result.report.summary.passed} passed, ${result.report.summary.warnings} warnings, ${result.report.summary.errors} errors -> ${result.reportFile}`);
    if (result.report.status !== 'PASS') process.exitCode = 1;
    return;
  }
  if (command === 'status') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- status <manifest.json>');
    console.log(JSON.stringify(await getProductionStatus(manifestFile), null, 2));
    return;
  }
  if (command === 'caption') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- caption <manifest.json>');
    const result = await captionManifest(manifestFile);
    console.log(`Captioned ${result.scenes} scenes with ${result.totalCaptions} timed phrases -> ${result.reportFile}`);
    return;
  }
  if (command === 'archive-search') {
    const limitValue = option('--limit');
    const query = args.slice(1).filter((arg) => !arg.startsWith('--') && arg !== limitValue).join(' ');
    if (!query) throw new Error('Usage: npm run documentary -- archive-search "search terms" [--limit 5]');
    console.log(JSON.stringify(await searchLoc(query, Number(limitValue ?? 5)), null, 2));
    return;
  }
  if (command === 'archive-collect') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- archive-collect <manifest.json> [--download]');
    const result = await collectLocCandidates(manifestFile, args.includes('--download'));
    console.log(`Collected ${result.candidateCount} candidates for ${result.sceneCount} scenes -> ${result.reportFile}`);
    return;
  }
  if (command === 'archive-promote') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- archive-promote <manifest.json>');
    const result = await promoteLocCandidates(manifestFile);
    console.log(`Promoted ${result.promotions.length} scenes; skipped ${result.skipped.length}. Backup: ${result.backupFile}`);
    return;
  }
  if (command === 'narrate') {
    const manifestFile = args[1];
    if (!manifestFile) throw new Error('Usage: npm run documentary -- narrate <manifest.json> [--voice Samantha] [--rate 175]');
    const result = await narrateManifest(manifestFile, option('--voice') ?? 'Samantha', Number(option('--rate') ?? 175));
    console.log(`Narrated ${result.sceneCount} scenes (${result.totalDurationSeconds.toFixed(1)}s) -> ${result.reportFile}`);
    return;
  }
  if (command === 'produce') {
    const briefFile = args[1];
    if (!briefFile) throw new Error('Usage: npm run documentary -- produce <brief.json> [--voice Samantha] [--rate 175]');
    const brief = productionBriefSchema.parse(JSON.parse(await readFile(briefFile, 'utf8')));
    const manifest = planDocumentary(brief);
    const filename = path.resolve(option('--output') ?? path.join('public/projects', manifest.id, 'manifest.json'));
    await mkdir(path.dirname(filename), {recursive: true});
    await writeFile(filename, `${JSON.stringify(manifest, null, 2)}\n`);
    const result = await narrateManifest(filename, option('--voice') ?? 'Samantha', Number(option('--rate') ?? 175));
    console.log(`Produced ${manifest.title}: ${manifest.scenes.length} scenes, ${result.totalDurationSeconds.toFixed(1)}s -> ${filename}`);
    return;
  }
  if (command === 'plan') {
    const briefFile = args[1];
    if (!briefFile) throw new Error('Usage: npm run documentary -- plan <brief.json> [--output <manifest.json>]');
    const brief = productionBriefSchema.parse(JSON.parse(await readFile(briefFile, 'utf8')));
    const manifest = planDocumentary(brief);
    const filename = path.resolve(option('--output') ?? path.join('public/projects', manifest.id, 'manifest.json'));
    await mkdir(path.dirname(filename), {recursive: true});
    await writeFile(filename, `${JSON.stringify(manifest, null, 2)}\n`);
    const seconds = Math.ceil(Math.max(...manifest.scenes.map((scene) => scene.startFrame + scene.durationFrames)) / manifest.format.fps);
    console.log(`Planned ${manifest.scenes.length} scenes (${seconds}s) -> ${filename}`);
    return;
  }
  if (command === 'validate' || command === 'load') {
    const filename = args[1];
    if (!filename) throw new Error(`Usage: npm run documentary -- ${command} <manifest.json>`);
    const manifest = parseManifest(JSON.parse(await readFile(filename, 'utf8')));
    console.log(`${command === 'load' ? 'Loaded' : 'Valid'}: ${manifest.title} (${manifest.scenes.length} scenes)`);
    return;
  }
  if (command !== 'generate') throw new Error('Commands: continue, director-start, director-status, director-choose, director-options, create, research, validate-production, run, status, render-project, creative-assets, generate, plan, produce, narrate, caption, archive-search, archive-collect, archive-promote, validate, load');
  const title = option('--title') ?? 'An Untold History';
  const topic = option('--topic') ?? 'A short historical documentary';
  const manifest = makeManifest(title, topic);
  const outputDir = path.resolve('public/projects', manifest.id);
  await mkdir(outputDir, {recursive: true});
  const filename = path.join(outputDir, 'manifest.json');
  await writeFile(filename, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Created ${filename}`);
};

main().catch((error: unknown) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
