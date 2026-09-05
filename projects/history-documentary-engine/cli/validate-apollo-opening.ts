import {access, readFile, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {apolloOpeningCaptions, apolloOpeningShots} from '../src/prototypes/apolloOpeningPlan';
import {verifyRender} from './render';

type Check = {level: 'PASS' | 'ERROR'; message: string};
const projectDir = path.resolve('public/projects/apollo-11-opening');
const checks: Check[] = [];
const add = (pass: boolean, message: string) => checks.push({level: pass ? 'PASS' : 'ERROR', message});
const main = async () => {
const report = JSON.parse(await readFile(path.join(projectDir, 'asset-source-report.json'), 'utf8')) as {assets: Array<{localFile: string; itemUrl: string; institution: string; rightsStatus: string}>};

add(apolloOpeningShots.length >= 6 && apolloOpeningShots.length <= 10, `${apolloOpeningShots.length} deliberate shots`);
add(apolloOpeningShots[0].start === 0 && apolloOpeningShots.every((shot, index) => index === 0 || shot.start === apolloOpeningShots[index - 1].start + apolloOpeningShots[index - 1].duration), 'Shot timeline is contiguous');
add(apolloOpeningShots.at(-1)!.start + apolloOpeningShots.at(-1)!.duration === 900, 'Prototype duration is exactly 30 seconds');
add(apolloOpeningShots.every((shot) => shot.src.includes('/archive/') && !/generated|procedural|illustration/i.test(shot.src)), 'Every primary visual is an authentic archive asset');
const reportFiles = new Set(report.assets.map((asset) => `projects/apollo-11-opening/${asset.localFile}`));
add(apolloOpeningShots.every((shot) => reportFiles.has(shot.src)), 'Every used image appears in the source report');
add(apolloOpeningShots.every((shot) => shot.editorialPurpose.length > 20 && shot.assetRationale.length > 20), 'Every shot documents its editorial purpose and asset rationale');
add(report.assets.every((asset) => asset.itemUrl && asset.institution && asset.rightsStatus === 'NO_KNOWN_RESTRICTIONS'), 'Every asset records its item URL, institution, and rights status');
for (const asset of report.assets) {
  const filename = path.join(projectDir, asset.localFile);
  await access(filename);
  add((await stat(filename)).size > 50_000, `${asset.localFile} is a usable production asset`);
}
const reused = [...new Set(apolloOpeningShots.filter((shot, index, all) => all.findIndex((candidate) => candidate.src === shot.src) !== index).map((shot) => shot.src))];
add(reused.every((src) => {const variants = apolloOpeningShots.filter((shot) => shot.src === src); return variants.length === 2 && variants[0].objectPosition !== variants[1].objectPosition && variants[0].scaleFrom !== variants[1].scaleFrom && variants[1].credit.includes('DETAIL CROP');}), 'Repeated source images use documented, editorially distinct detail crops');
add(apolloOpeningCaptions.every((caption, index) => index === 0 || caption.start === apolloOpeningCaptions[index - 1].end), 'Narration captions are contiguous');
add(apolloOpeningCaptions.every((caption) => caption.text.length < 120), 'Captions contain concise spoken narration only');
add(apolloOpeningShots.every((shot) => shot.credit.length < 55), 'Credits contain attribution only');
add(!apolloOpeningShots.some((shot) => /before apollo|mission control could|landing was/i.test(shot.credit)), 'Credits do not repeat narration');
const outputFile = path.join(projectDir, 'apollo-11-opening-final.mp4');
try {
  const media = await verifyRender(outputFile, {width: 1280, height: 720, requireAudio: true});
  add(media.durationSeconds >= 29.9 && media.durationSeconds <= 30.2, `Verified final MP4 is ${media.durationSeconds.toFixed(2)} seconds with audio`);
} catch { add(false, 'Final 1280×720 MP4 is missing or invalid'); }

const errors = checks.filter((check) => check.level === 'ERROR').length;
await writeFile(path.join(projectDir, 'prototype-validation-report.json'), `${JSON.stringify({schemaVersion: 1, generatedAt: new Date().toISOString(), status: errors ? 'FAIL' : 'PASS', checks, summary: {passed: checks.length - errors, errors}}, null, 2)}\n`);
console.log(`Apollo opening validation ${errors ? 'FAIL' : 'PASS'}: ${checks.length - errors} passed, ${errors} errors`);
if (errors) process.exitCode = 1;
};

main().catch((error: unknown) => {console.error(error instanceof Error ? error.message : error); process.exitCode = 1;});
