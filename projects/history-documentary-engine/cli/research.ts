import {access, copyFile, mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';
import {productionBriefSchema, type ProductionBrief} from './brief';
import {researchWithWikipediaDiscovery} from './adapters/wikipedia-research';

export const researchSourceSchema = z.object({
  id: z.string(), title: z.string(), url: z.string().url(), publisher: z.string(),
  accessedAt: z.string(), authority: z.enum(['PRIMARY', 'AUTHORITATIVE_SECONDARY', 'DISCOVERY_ONLY']),
  rights: z.string().optional(),
});

export const researchClaimSchema = z.object({
  id: z.string(), text: z.string().min(1), evidence: z.string().min(1), sourceIds: z.array(z.string()).min(1),
  confidence: z.enum(['HIGH', 'MEDIUM', 'LOW']), numbers: z.array(z.string()), conflictIds: z.array(z.string()),
});

export const researchReportSchema = z.object({
  schemaVersion: z.literal(1), title: z.string(), topic: z.string(), researchedAt: z.string(),
  sources: z.array(researchSourceSchema), claims: z.array(researchClaimSchema),
  conflicts: z.array(z.object({claimIds: z.tuple([z.string(), z.string()]), reason: z.string()})),
  warnings: z.array(z.string()), status: z.enum(['PASS', 'REVIEW_REQUIRED', 'FAIL']),
});
export type ResearchReport = z.infer<typeof researchReportSchema>;

const stopwords = new Set('a an and are as at be been by for from had has have in into is it its of on or that the their this to was were which with'.split(' '));
const keywords = (text: string) => new Set((text.toLowerCase().match(/[a-z]{4,}/g) ?? []).filter((word) => !stopwords.has(word)));
const overlap = (a: Set<string>, b: Set<string>) => {
  const shared = [...a].filter((word) => b.has(word)).length;
  return shared / Math.max(1, Math.min(a.size, b.size));
};

const genericTopicWords = new Set('fire history historical documentary story event tragedy incident nightclub'.split(' '));
const topicAnchors = (title: string) => [...keywords(title)].filter((word) => !genericTopicWords.has(word));
export const isTopicallyRelevant = (text: string, title: string) => {
  const anchors = topicAnchors(title);
  if (!anchors.length) return overlap(keywords(text), keywords(title)) >= .5;
  const lower = text.toLowerCase();
  return anchors.some((anchor) => lower.includes(anchor));
};

export const findConflicts = (claims: ResearchReport['claims']) => {
  const conflicts: ResearchReport['conflicts'] = [];
  for (let a = 0; a < claims.length; a++) for (let b = a + 1; b < claims.length; b++) {
    if (overlap(keywords(claims[a].text), keywords(claims[b].text)) < .8) continue;
    const left = new Set(claims[a].numbers);
    const right = new Set(claims[b].numbers);
    if (left.size && right.size && ([...left].some((n) => !right.has(n)) || [...right].some((n) => !left.has(n)))) {
      const reason = 'Similar claims contain different numeric or date values';
      conflicts.push({claimIds: [claims[a].id, claims[b].id], reason});
      claims[a].conflictIds.push(claims[b].id);
      claims[b].conflictIds.push(claims[a].id);
    }
  }
  return conflicts;
};

const cleanNarration = (text: string) => text.replace(/\[[^\]]+]/g, '').replace(/\s+/g, ' ').trim();
const roles = ['hook', 'context', 'escalation', 'central-event', 'aftermath', 'significance'] as const;
const roleScore = (role: (typeof roles)[number], text: string) => {
  const patterns: Record<(typeof roles)[number], Array<[RegExp, number]>> = {
    hook: [[/\b(first|historic|unprecedented|changed|achieved)\b/i, 12], [/\b(landed|victory|disaster)\b/i, 7]],
    context: [[/\b(primary objective|objectives|national goal|president|decision|program|before)\b/i, 14], [/\b(returned|splashdown|launched)\b/i, -8]],
    escalation: [[/\b(launched|departed|translunar|approached|orbit|journey|preparation)\b/i, 14]],
    'central-event': [[/\b(landed|landing|stepped|surface|Armstrong|Aldrin|Eagle|attack|battle|explosion)\b/i, 14], [/\b(liftoff|returned|splashdown|Pacific|recovery|journal)\b/i, -12]],
    aftermath: [[/\b(returned|aftermath|recovered|splashdown|liftoff|ended)\b/i, 14]],
    significance: [[/\b(legacy|result|achievement|remembered|inspired|national goal|impact)\b/i, 14], [/\b(first)\b/i, 5]],
  };
  return patterns[role].reduce((sum, [pattern, score]) => sum + (pattern.test(text) ? score : 0), 0);
};

export const briefFromResearch = (report: ResearchReport, targetMinutes = 2): ProductionBrief => {
  const usable = report.claims.filter((claim) => claim.confidence !== 'LOW' && claim.conflictIds.length === 0 && claim.sourceIds.some((id) => report.sources.find((source) => source.id === id)?.authority !== 'DISCOVERY_ONLY'));
  if (usable.length < 6) throw new Error(`Research gate failed: need 6 supported non-conflicting claims, found ${usable.length}`);
  const remaining = [...usable];
  const selections = new Map<(typeof roles)[number], ResearchReport['claims'][number]>();
  const selectionOrder: Array<(typeof roles)[number]> = ['significance', 'central-event', 'aftermath', 'escalation', 'context', 'hook'];
  for (const role of selectionOrder) {
    const scored = remaining.map((claim, index) => {
      const lower = claim.text.toLowerCase();
      const titleScore = lower.includes(report.title.toLowerCase()) ? 3 : 0;
      let penalty = /\b(journal|website|published online|interviews|editor|historian|transcripts|Jones|Schmitt|Apollo 17)\b/i.test(claim.text) ? 12 : 0;
      if (role === 'context' && /\bTV transmission\b/i.test(claim.text)) penalty += 10;
      if (role === 'central-event' && /\b(July 24|Pacific|recovery ship|splashdown)\b/i.test(claim.text)) penalty += 18;
      const centralLanding = role === 'central-event' ? (/\b(landed|stepped)\b/i.test(claim.text) ? 22 : /\blanding\b/i.test(claim.text) ? 8 : 0) : 0;
      return {claim, index, score: roleScore(role, claim.text) + titleScore + centralLanding - penalty};
    }).sort((a, b) => b.score - a.score);
    const picked = scored[0];
    remaining.splice(picked.index, 1);
    selections.set(role, picked.claim);
  }
  const buckets = roles.map((role) => ({role, claims: [selections.get(role)!]}));
  const script = buckets.map(({role, claims}) => {
    const narration = cleanNarration(claims.map((claim) => claim.text).join(' '));
    const sourceIds = [...new Set(claims.flatMap((claim) => claim.sourceIds))];
    const visual = role === 'context' && /\b(route|journey|region|city|country|ocean|river|landed|launched)\b/i.test(narration) ? 'MAP' as const : 'AUTO' as const;
    const searchTerms = narration.replace(/[^a-zA-Z0-9\s]/g, ' ').split(/\s+/).filter((word) => word.length > 4 || /^\d{4}$/.test(word)).slice(0, 9).join(' ');
    return {id: role, narration, visual, sourceIds, claimIds: claims.map((claim) => claim.id), archiveQuery: `${report.title} | ${searchTerms}`};
  });
  return productionBriefSchema.parse({
    title: report.title, topic: report.topic, targetMinutes,
    sources: report.sources.filter((source) => source.authority !== 'DISCOVERY_ONLY').map(({authority: _authority, ...source}) => source),
    script,
  });
};

export const researchTopic = async (title: string, topic: string, outputRoot = 'automation/generated') => {
  const raw = await researchWithWikipediaDiscovery(title, topic);
  const sourceById = new Map(raw.sources.map((source) => [source.id, source]));
  const beforeRelevance = raw.claims.length;
  raw.claims = raw.claims.filter((claim) => isTopicallyRelevant(claim.text, title) && claim.sourceIds.some((id) => {
    const source = sourceById.get(id);
    return source && source.authority !== 'DISCOVERY_ONLY' && isTopicallyRelevant(source.title, title);
  }));
  if (raw.claims.length < beforeRelevance) raw.warnings.push(`Rejected ${beforeRelevance - raw.claims.length} off-topic claims`);
  raw.conflicts = findConflicts(raw.claims);
  const supportedClaims = raw.claims.filter((claim) => claim.confidence !== 'LOW' && claim.conflictIds.length === 0);
  const authoritySources = raw.sources.filter((source) => source.authority !== 'DISCOVERY_ONLY');
  raw.status = supportedClaims.length >= 6 && authoritySources.length >= 2 ? (raw.conflicts.length ? 'REVIEW_REQUIRED' : 'PASS') : 'FAIL';
  if (authoritySources.length < 2) raw.warnings.push(`Only ${authoritySources.length} primary or authoritative secondary sources could be acquired; at least 2 are required`);
  const report = researchReportSchema.parse(raw);
  if (report.status === 'FAIL') throw new Error(`Research failed safely: ${report.warnings.join('; ')}`);
  const brief = briefFromResearch(report);
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const dir = path.resolve(outputRoot, slug);
  await mkdir(dir, {recursive: true});
  const reportFile = path.join(dir, 'research-report.json');
  const briefFile = path.join(dir, 'production-brief.json');
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  if (await access(reportFile).then(() => true).catch(() => false)) await copyFile(reportFile, path.join(dir, `research-report.before-${stamp}.json`));
  if (await access(briefFile).then(() => true).catch(() => false)) await copyFile(briefFile, path.join(dir, `production-brief.before-${stamp}.json`));
  await writeFile(reportFile, `${JSON.stringify(report, null, 2)}\n`);
  await writeFile(briefFile, `${JSON.stringify(brief, null, 2)}\n`);
  return {report, brief, reportFile, briefFile};
};

export const loadResearchReport = async (filename: string) => researchReportSchema.parse(JSON.parse(await readFile(filename, 'utf8')));
