import {execFile} from 'node:child_process';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';
import {parseManifest} from '../src/manifest/schema';
import {verifyRender} from './render';

const execFileAsync = promisify(execFile);
const main = async () => {
  const manifestFile = path.resolve('public/projects/episode-1/manifest.json');
  const projectDir = path.dirname(manifestFile);
  const manifest = parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
  const propsFile = path.join(projectDir, 'preview-props.json');
  const outputFile = path.join(projectDir, 'renders', 'episode-1-rough-cut.mp4');
  await mkdir(path.dirname(outputFile), {recursive:true});
  await writeFile(propsFile, `${JSON.stringify({manifest}, null, 2)}\n`);
  await execFileAsync(path.resolve('node_modules/.bin/remotion'), ['render','src/index.ts','HistoryDocumentary',outputFile,'--props',propsFile,'--codec','h264','--scale','0.5','--concurrency','1','--gl','angle','--overwrite'], {cwd:path.resolve('.'),maxBuffer:1024*1024*20});
  const verification = await verifyRender(outputFile,{width:640,height:360,requireAudio:true});
  await writeFile(path.join(projectDir,'preview-render-report.json'),`${JSON.stringify({schemaVersion:1,outputFile,verified:true,...verification},null,2)}\n`);
  console.log(`Preview verified: ${verification.width}x${verification.height}, ${verification.durationSeconds.toFixed(1)} seconds, audio ${verification.audioCodec}`);
};

main().catch((error:unknown)=>{console.error(error instanceof Error?error.message:error);process.exitCode=1;});
