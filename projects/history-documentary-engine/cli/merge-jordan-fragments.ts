import {execFile} from 'node:child_process';
import {copyFile, readFile, rename, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';
import {parseManifest} from '../src/manifest/schema';
const execFileAsync=promisify(execFile);
const projectDir=path.resolve('public/projects/episode-2');
const manifestFile=path.join(projectDir,'manifest.json');
const groups=[['06-season-shot-7','06-season-shot-8'],['08-practice-shot-1','08-practice-shot-2','08-practice-shot-3']];
const main=async()=>{
  const original=await readFile(manifestFile,'utf8');const manifest=parseManifest(JSON.parse(original));const removed=new Set<string>();
  for(const ids of groups){
    const scenes=ids.map(id=>manifest.scenes.find(s=>s.id===id)!);if(scenes.some(s=>!s?.audio))throw new Error(`Missing merge audio for ${ids.join(',')}`);
    const first=scenes[0];const target=path.resolve('public',first.audio!.src);const temp=`${target}.merged.wav`;
    const inputs=scenes.flatMap(s=>['-i',path.resolve('public',s.audio!.src)]);const pads=scenes.map((_,i)=>`[${i}:a]`).join('');
    await execFileAsync('ffmpeg',['-hide_banner','-loglevel','error','-y',...inputs,'-filter_complex',`${pads}concat=n=${scenes.length}:v=0:a=1[out]`,'-map','[out]',temp]);
    await rename(temp,target);const duration=scenes.reduce((sum,s)=>sum+s.audio!.durationSeconds,0);
    first.narration=scenes.map(s=>s.narration).join(' ').replace(/\s+([’”])/g,'$1').replace(/B\.\s+J\./g,'B.J.');first.caption=first.narration;
    first.audio={...first.audio!,durationSeconds:duration};first.durationFrames=Math.ceil((duration+.65)*manifest.format.fps);
    scenes.slice(1).forEach(s=>removed.add(s.id));
  }
  manifest.scenes=manifest.scenes.filter(s=>!removed.has(s.id));let cursor=0;for(const scene of manifest.scenes){scene.startFrame=cursor;cursor+=scene.durationFrames;}
  const stamp=new Date().toISOString().replace(/[:.]/g,'-');await copyFile(manifestFile,path.join(projectDir,`manifest.before-fragment-merge-${stamp}.json`));await writeFile(manifestFile,`${JSON.stringify(parseManifest(manifest),null,2)}\n`);
  const reportFile=path.join(projectDir,'asset-source-report.json');const report=JSON.parse(await readFile(reportFile,'utf8'));report.usages=report.usages.filter((u:{sceneId:string})=>!removed.has(u.sceneId));await writeFile(reportFile,`${JSON.stringify(report,null,2)}\n`);
  console.log(`Merged ${removed.size} narration fragments without regenerating approved audio`);
};main().catch(e=>{console.error(e instanceof Error?e.message:e);process.exitCode=1});
