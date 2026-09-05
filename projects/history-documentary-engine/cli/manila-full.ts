import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {copyFile,mkdir,readFile,stat,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';
import {compilePhoneFast} from '../src/phone/compiler';
import {validatePhoneFast} from '../src/phone/validator';
import {manilaFull} from '../src/episodes/manilaFull';
import {verifyRender} from './render';

const execFileAsync=promisify(execFile);
const project=path.resolve('public/projects/bombing-of-manila-wwii');
const renderDir=path.join(project,'06-render');
const output=path.join(renderDir,'the-month-manila-died.mp4');
const publicOutput=path.resolve('../outputs/the-month-manila-died.mp4');
const cacheFile=path.join(renderDir,'full-cache.json');
const exists=(file:string)=>stat(file).then(()=>true,()=>false);

const inputs=['src/phone/schema.ts','src/phone/compiler.ts','src/phone/validator.ts','src/phone/PhoneFast.tsx','src/episodes/manilaFull.ts','src/episodes/manilaScript.ts',
  'public/projects/bombing-of-manila-wwii/01-research/corpus-snapshot.json','public/projects/bombing-of-manila-wwii/02-story/narrative-graph.json',
  'public/projects/bombing-of-manila-wwii/02-story/microchapters.json','public/projects/bombing-of-manila-wwii/04-assets/asset-inventory.json',
  'public/projects/bombing-of-manila-wwii/04-assets/rights-ledger.json','public/projects/bombing-of-manila-wwii/06-render/narration-report.json'];
const fingerprint=async()=>{const hash=createHash('sha256');for(const file of inputs)hash.update(await readFile(file));for(const asset of manilaFull.assets)hash.update(await readFile(path.resolve('public',asset.src)));for(const beat of manilaFull.microchapters.flatMap(x=>x.beats))hash.update(await readFile(path.resolve('public',beat.audioSrc)));hash.update(await readFile(path.resolve('public',manilaFull.soundtrackSrc)));return hash.digest('hex');};

const main=async()=>{
  await mkdir(renderDir,{recursive:true});await mkdir(path.dirname(publicOutput),{recursive:true});
  const compiled=compilePhoneFast(manilaFull);const validation=validatePhoneFast(manilaFull);
  await writeFile(path.join(renderDir,'full-blueprint.json'),`${JSON.stringify(manilaFull,null,2)}\n`);
  await writeFile(path.join(renderDir,'full-creative-validation.json'),`${JSON.stringify(validation,null,2)}\n`);
  if(validation.status!=='PASS')throw new Error(validation.errors.join('; '));
  const captions=manilaFull.microchapters.flatMap(ch=>ch.beats).map(beat=>{const events=compiled.events.filter(event=>event.beatId===beat.id);return {beatId:beat.id,startSeconds:Number((events[0].startFrame/manilaFull.fps).toFixed(3)),endSeconds:Number(((events.at(-1)!.startFrame+events.at(-1)!.durationFrames)/manilaFull.fps).toFixed(3)),text:beat.narration};});
  await writeFile(path.join(renderDir,'captions.json'),`${JSON.stringify({schemaVersion:1,language:'en',captions},null,2)}\n`);
  const hash=await fingerprint();
  if(await exists(cacheFile)&&await exists(output)){const cache=JSON.parse(await readFile(cacheFile,'utf8'));if(cache.fingerprint===hash&&cache.verified){await copyFile(output,publicOutput);console.log(`SKIPPED: cached verified MP4; creative ${validation.score}/100; ${cache.verification.durationSeconds.toFixed(1)}s`);return;}}
  const started=Date.now();
  await execFileAsync(path.resolve('node_modules/.bin/remotion'),['render','src/index.ts','ManilaFull',output,'--codec','h264','--concurrency','1','--gl','angle','--overwrite'],{cwd:path.resolve('.'),maxBuffer:1024*1024*40});
  const verification=await verifyRender(output,{width:1280,height:720,requireAudio:true});const expected=compiled.durationInFrames/manilaFull.fps;
  if(Math.abs(verification.durationSeconds-expected)>.35)throw new Error(`Duration mismatch: expected ${expected.toFixed(2)}, got ${verification.durationSeconds.toFixed(2)}`);
  if(verification.durationSeconds<480||verification.durationSeconds>600)throw new Error(`Episode duration ${verification.durationSeconds.toFixed(1)}s is outside 8–10 minutes`);
  const report={schemaVersion:1,verified:true,output,...verification,creativeScore:validation.score,distinctAuthenticAssets:validation.metrics.distinctAssets,elapsedSeconds:Number(((Date.now()-started)/1000).toFixed(1)),fingerprint:hash};
  await writeFile(path.join(renderDir,'full-render-report.json'),`${JSON.stringify(report,null,2)}\n`);await writeFile(cacheFile,`${JSON.stringify({fingerprint:hash,verified:true,verification},null,2)}\n`);await copyFile(output,publicOutput);
  console.log(`RENDERED: creative ${validation.score}/100; ${verification.width}x${verification.height}; ${verification.durationSeconds.toFixed(1)}s; ${report.distinctAuthenticAssets} authentic assets`);
};
main().catch(error=>{console.error(error instanceof Error?error.message:error);process.exitCode=1;});
