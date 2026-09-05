import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {copyFile, mkdir, readFile, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';
import {parseManifest} from '../src/manifest/schema';
import {loadDirectorState, setDirectorCheckpointOptions} from './director';
import {verifyRender} from './render';
import {validateProduction} from './validation';

const execFileAsync = promisify(execFile);
type Artifact = {path:string; hash:string; locked:boolean};
type Ledger = {
  schemaVersion:1; projectId:string; updatedAt:string;
  decisions:Record<string,string>; approvedStages:string[];
  artifacts:Record<string,Artifact>; currentStage:string; nextAction:string;
  exceptions:string[]; doNotRegenerate:string[];
  renderInputHash?:string; lastRun?:{at:string; result:string};
};

const hashFile = async (filename:string) => createHash('sha256').update(await readFile(filename)).digest('hex');
const exists = async (filename:string) => stat(filename).then(()=>true,()=>false);
const rel = (projectDir:string, filename:string) => path.relative(projectDir, filename);
const artifact = async (projectDir:string, filename:string, locked=true):Promise<Artifact> => ({path:rel(projectDir,filename),hash:await hashFile(filename),locked});
const ledgerFileFor = (projectDir:string) => path.join(projectDir,'production-ledger.json');

const decisionSnapshot = async (directorFile:string) => {
  const state = await loadDirectorState(directorFile);
  return Object.fromEntries(state.checkpoints.filter(c=>c.selectedOptionId).map(c=>[c.id,c.selectedOptionId!]));
};

const writeHandoff = async (projectDir:string, ledger:Ledger) => {
  const locked = Object.keys(ledger.artifacts).filter(key=>ledger.artifacts[key].locked).join(', ');
  const body = `# Episode handoff\n\n- Current stage: ${ledger.currentStage}\n- Next action: ${ledger.nextAction}\n- Locked artifacts: ${locked}\n- Do not regenerate: ${ledger.doNotRegenerate.join(', ')}\n- Exceptions: ${ledger.exceptions.length ? ledger.exceptions.join('; ') : 'none'}\n- Last result: ${ledger.lastRun?.result ?? 'ledger initialized'}\n`;
  await writeFile(path.join(projectDir,'HANDOFF.md'),body);
};

const bootstrapLedger = async (projectId:string, projectDir:string):Promise<Ledger> => {
  const files:Record<string,string> = {
    director:'director-state.json', research:'research-report.json', brief:'production-brief.json',
    manifest:'manifest.json', narration:'narration-report.json', captions:'caption-report.json', assets:'asset-source-report.json',
  };
  const artifacts:Record<string,Artifact> = {};
  for (const [name,file] of Object.entries(files)) {
    const absolute=path.join(projectDir,file);
    if (await exists(absolute)) artifacts[name]=await artifact(projectDir,absolute,true);
  }
  const hasManifest=Boolean(artifacts.manifest);
  return {
    schemaVersion:1,projectId,updatedAt:new Date().toISOString(),
    decisions:await decisionSnapshot(path.join(projectDir,'director-state.json')),
    approvedStages:hasManifest?['research','script-storyboard','archive-acquisition','narration','captions','rough-cut','archive-polish']:[],
    artifacts,currentStage:hasManifest?'RENDER_POLISHED_PREVIEW':'TOPIC_PROMISE',nextAction:hasManifest?'render-polished-preview':'await-director-choice',exceptions:[],
    doNotRegenerate:hasManifest?['research','production brief','approved script','narration audio','captions','downloaded archive assets']:[],
  };
};

const loadOrCreateLedger = async (projectId:string, projectDir:string) => {
  const filename=ledgerFileFor(projectDir);
  if (await exists(filename)) return JSON.parse(await readFile(filename,'utf8')) as Ledger;
  const ledger=await bootstrapLedger(projectId,projectDir);
  await writeFile(filename,`${JSON.stringify(ledger,null,2)}\n`);
  return ledger;
};

const renderFingerprint = async (projectDir:string) => {
  const inputs=['manifest.json','../../../src/Documentary.tsx','../../../src/scenes/KenBurns.tsx','../../../src/scenes/TitleCard.tsx','../../../src/captions/CaptionOverlay.tsx'];
  const hashes=[];
  for (const input of inputs) hashes.push(await hashFile(path.resolve(projectDir,input)));
  return createHash('sha256').update(hashes.join(':')).digest('hex');
};

const applyTargetedRevision = async (projectDir:string, sceneId:string, assetId:string) => {
  const manifestFile=path.join(projectDir,'manifest.json');
  const report=JSON.parse(await readFile(path.join(projectDir,'asset-source-report.json'),'utf8')) as {assets:Array<{id:string;localFile:string;title:string;itemUrl:string;institution:string;rightsStatus:string;rightsText:string}>};
  const selected=report.assets.find(a=>a.id===assetId);
  if (!selected) throw new Error(`Unknown asset ${assetId}`);
  const manifest=parseManifest(JSON.parse(await readFile(manifestFile,'utf8')));
  const scene=manifest.scenes.find(s=>s.id===sceneId);
  if (!scene || (scene.type!=='KEN_BURNS' && scene.type!=='ARCHIVE_PHOTO')) throw new Error(`Scene ${sceneId} is not an archive image scene`);
  const stamp=new Date().toISOString().replace(/[:.]/g,'-');
  await copyFile(manifestFile,path.join(projectDir,`manifest.before-scene-${sceneId}-${stamp}.json`));
  scene.payload={...scene.payload,src:`projects/${path.basename(projectDir)}/${selected.localFile}`,alt:selected.title,credit:`${selected.institution} · ${selected.title}`,archiveItemUrl:selected.itemUrl,rightsStatus:selected.rightsStatus as 'NO_KNOWN_RESTRICTIONS'};
  await writeFile(manifestFile,`${JSON.stringify(parseManifest(manifest),null,2)}\n`);
};

const finalOptions = [
  {id:'approve-publication',label:'Publish This Cut',consequence:'Lock the polished preview and proceed to the full-resolution master, thumbnail, and YouTube package.',recommended:true,evidenceUrls:['https://www.nps.gov/articles/000/the-battle-of-blair-mountain.htm']},
  {id:'targeted-final-notes',label:'Give Targeted Notes',consequence:'Name exact timestamps or scenes to revise; approved research, narration, and unrelated scenes remain locked.',recommended:false,evidenceUrls:['https://www.nps.gov/articles/000/the-battle-of-blair-mountain.htm']},
  {id:'hold-publication',label:'Hold the Episode',consequence:'Preserve every artifact and pause publication without regenerating completed work.',recommended:false,evidenceUrls:['https://www.nps.gov/articles/000/the-battle-of-blair-mountain.htm']},
];
const roughCutOptions = [
  {id:'approve-and-finish',label:'Approve and Finish',consequence:'Lock this researched cut and proceed later to the full-resolution master and publication package.',recommended:true,evidenceUrls:['https://www.nba.com/news/legendary-moments-michael-jordan-returns-nba-1995']},
  {id:'targeted-revision-notes',label:'Targeted Revision Notes',consequence:'Revise only named timestamps or scenes while preserving research, narration, and unrelated assets.',recommended:false,evidenceUrls:['https://www.mlb.com/milb/history/michael-jordan']},
  {id:'hold-production',label:'Hold Production',consequence:'Preserve every completed artifact and pause without regenerating work.',recommended:false,evidenceUrls:['https://www.mlb.com/milb/history/michael-jordan']},
];

const syncArtifacts = async (ledger:Ledger, projectDir:string) => {
  const files:Record<string,string>={director:'director-state.json',research:'research-report.json',brief:'production-brief.json',manifest:'manifest.json',narration:'narration-report.json',captions:'caption-report.json',assets:'asset-source-report.json',validation:'validation-report.json'};
  for(const [name,file] of Object.entries(files)){const absolute=path.join(projectDir,file);if(await exists(absolute))ledger.artifacts[name]=await artifact(projectDir,absolute,true);}
  ledger.approvedStages=['research','claims','script-storyboard','media-acquisition','narration','captions','validation'].filter(name=>({research:'research',claims:'research', 'script-storyboard':'brief','media-acquisition':'assets',narration:'narration',captions:'captions',validation:'validation'} as Record<string,string>)[name] in ledger.artifacts);
  ledger.doNotRegenerate=['research','verified claims','approved script/storyboard','narration audio','captions','downloaded media'];
};

export const continueEpisode = async (projectId:string, options:{dryRun?:boolean;sceneId?:string;assetId?:string}={}) => {
  const projectDir=path.resolve('public/projects',projectId);
  const ledger=await loadOrCreateLedger(projectId,projectDir);
  const manifestFile=path.join(projectDir,'manifest.json');
  if (!(await exists(manifestFile))) {
    const director=await loadDirectorState(path.join(projectDir,'director-state.json'));
    ledger.approvedStages=[];
    ledger.artifacts=ledger.artifacts.director?{director:ledger.artifacts.director}:{};
    ledger.doNotRegenerate=[];
    ledger.currentStage=director.activeCheckpoint;
    ledger.nextAction='await-director-choice';
    ledger.lastRun={at:new Date().toISOString(),result:`WAITING_FOR_DIRECTOR: ${director.activeCheckpoint}`};
    ledger.updatedAt=new Date().toISOString();
    await writeFile(ledgerFileFor(projectDir),`${JSON.stringify(ledger,null,2)}\n`);
    await writeHandoff(projectDir,ledger);
    return {ledger,ledgerFile:ledgerFileFor(projectDir),handoffFile:path.join(projectDir,'HANDOFF.md'),outputFile:path.join(projectDir,'renders',`${projectId}-polished-preview.mp4`)};
  }
  await syncArtifacts(ledger,projectDir);
  if (options.sceneId || options.assetId) {
    if (!options.sceneId || !options.assetId) throw new Error('Targeted revision requires both --revise-scene and --asset-id');
    await applyTargetedRevision(projectDir,options.sceneId,options.assetId);
    ledger.currentStage='RENDER_POLISHED_PREVIEW'; ledger.nextAction='render-polished-preview'; ledger.renderInputHash=undefined;
  }
  const fingerprint=await renderFingerprint(projectDir);
  const directorFile=path.join(projectDir,'director-state.json');
  const directorBefore=await loadDirectorState(directorFile);
  const reviewCheckpoint=directorBefore.activeCheckpoint==='ROUGH_CUT'?'ROUGH_CUT':'FINAL_PUBLICATION';
  const renderLabel=reviewCheckpoint==='ROUGH_CUT'?'rough-cut':'polished-preview';
  const outputFile=path.join(projectDir,'renders',`${projectId}-${renderLabel}.mp4`);
  const reportFile=path.join(projectDir,`${renderLabel}-report.json`);
  if (ledger.renderInputHash===fingerprint && await exists(outputFile) && await exists(reportFile)) {
    ledger.currentStage=reviewCheckpoint; ledger.nextAction='await-director-choice';
    ledger.lastRun={at:new Date().toISOString(),result:`SKIPPED: all approved inputs unchanged; ${renderLabel} already verified`};
  } else if (options.dryRun) {
    ledger.currentStage=`RENDER_${renderLabel.toUpperCase().replaceAll('-','_')}`; ledger.nextAction=`render-${renderLabel}`;
    ledger.lastRun={at:new Date().toISOString(),result:`DRY_RUN: render-${renderLabel} is the only incomplete action`};
  } else {
    await validateProduction(path.join(projectDir,'manifest.json'),{researchReport:path.join(projectDir,'research-report.json')});
    const manifest=parseManifest(JSON.parse(await readFile(path.join(projectDir,'manifest.json'),'utf8')));
    const propsFile=path.join(projectDir,'preview-props.json');
    await mkdir(path.dirname(outputFile),{recursive:true});
    await writeFile(propsFile,`${JSON.stringify({manifest},null,2)}\n`);
    await execFileAsync(path.resolve('node_modules/.bin/remotion'),['render','src/index.ts','HistoryDocumentary',outputFile,'--props',propsFile,'--codec','h264','--scale','0.5','--concurrency','1','--gl','angle','--overwrite'],{cwd:path.resolve('.'),maxBuffer:1024*1024*20});
    const verification=await verifyRender(outputFile,{width:640,height:360,requireAudio:true});
    const renderReport={schemaVersion:1,inputHash:fingerprint,outputFile,verified:true,...verification};
    await writeFile(reportFile,`${JSON.stringify(renderReport,null,2)}\n`);
    await writeFile(path.join(projectDir,'render-report.json'),`${JSON.stringify(renderReport,null,2)}\n`);
    const director=await loadDirectorState(directorFile);
    const checkpoint=director.checkpoints.find(c=>c.id===reviewCheckpoint);
    if (director.activeCheckpoint===reviewCheckpoint && checkpoint?.status==='LOCKED') await setDirectorCheckpointOptions(directorFile,reviewCheckpoint,reviewCheckpoint==='ROUGH_CUT'?roughCutOptions:finalOptions);
    ledger.artifacts.manifest=await artifact(projectDir,path.join(projectDir,'manifest.json'),true);
    ledger.artifacts.polishedPreview=await artifact(projectDir,outputFile,true);
    ledger.artifacts.previewReport=await artifact(projectDir,reportFile,true);
    ledger.renderInputHash=fingerprint; ledger.currentStage=reviewCheckpoint; ledger.nextAction='await-director-choice';
    ledger.lastRun={at:new Date().toISOString(),result:`RENDERED_AND_VERIFIED: ${verification.width}x${verification.height}, ${verification.durationSeconds.toFixed(1)}s, audio ${verification.audioCodec}`};
  }
  ledger.decisions=await decisionSnapshot(path.join(projectDir,'director-state.json'));
  ledger.updatedAt=new Date().toISOString();
  await writeFile(ledgerFileFor(projectDir),`${JSON.stringify(ledger,null,2)}\n`);
  await writeHandoff(projectDir,ledger);
  return {ledger,ledgerFile:ledgerFileFor(projectDir),handoffFile:path.join(projectDir,'HANDOFF.md'),outputFile};
};
