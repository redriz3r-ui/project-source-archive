import {readFile} from 'node:fs/promises';
import {productionBriefSchema} from './brief';
import {researchReportSchema} from './research';

const main = async () => {
  const projectDir = 'public/projects/episode-1';
  const report = researchReportSchema.parse(JSON.parse(await readFile(`${projectDir}/research-report.json`, 'utf8')));
  const brief = productionBriefSchema.parse(JSON.parse(await readFile(`${projectDir}/production-brief.json`, 'utf8')));
  const authoritativeSources = report.sources.filter((source) => source.authority !== 'DISCOVERY_ONLY');
  const supportedClaims = report.claims.filter((claim) => claim.confidence !== 'LOW' && claim.conflictIds.length === 0);
  const referencedClaims = new Set(brief.script.flatMap((beat) => beat.claimIds));
  const errors: string[] = [];
  if (report.status !== 'PASS') errors.push(`Research status is ${report.status}`);
  if (authoritativeSources.length < 2) errors.push('Fewer than two authoritative sources');
  if (supportedClaims.length !== report.claims.length) errors.push('Unsupported or conflicting claims remain');
  if (!brief.script.every((beat) => beat.claimIds.length && beat.sourceIds.length)) errors.push('Every script beat must cite claims and sources');
  if (![...referencedClaims].every((id) => report.claims.some((claim) => claim.id === id))) errors.push('Script references an unknown claim');
  if (brief.script.some((beat) => beat.visual === 'ILLUSTRATION')) errors.push('Archive-only episode contains an illustration request');
  if (brief.script.length < 10 || brief.script.length > 16) errors.push('Storyboard must contain 10–16 deliberate sequences');
  if (errors.length) throw new Error(errors.join('; '));
  console.log(`Preproduction PASS: ${report.claims.length} claims, ${authoritativeSources.length} authoritative sources, ${brief.script.length} cited sequences, archive-only visual plan`);
};

main().catch((error: unknown) => {console.error(error instanceof Error ? error.message : error); process.exitCode = 1;});
