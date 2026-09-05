import type {ResearchReport} from '../research';

type SearchResponse = {query?: {search?: Array<{title: string}>}};
type ExtractResponse = {query?: {pages?: Record<string, {title?: string; extract?: string}>}};
type ParseResponse = {parse?: {externallinks?: string[]}};

const USER_AGENT = 'HistoryDocumentaryEngine/0.1 (local research tool)';
const fetchJson = async <T>(url: string): Promise<T> => {
  const response = await fetch(url, {headers: {'User-Agent': USER_AGENT}});
  if (!response.ok) throw new Error(`Research request failed (${response.status}): ${url}`);
  return response.json() as Promise<T>;
};
const endpoint = (params: Record<string, string>) => `https://en.wikipedia.org/w/api.php?${new URLSearchParams({format: 'json', origin: '*', ...params})}`;
const stripHtml = (html: string) => html.replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ').replace(/<nav[\s\S]*?<\/nav>/gi, ' ').replace(/<header[\s\S]*?<\/header>/gi, ' ').replace(/<footer[\s\S]*?<\/footer>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/&#(\d+);/g, (_match, code: string) => String.fromCodePoint(Number(code))).replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
const sentenceSplit = (text: string) => {
  const raw = text.split(/(?<=[.!?])\s+(?=[A-Z0-9])/).map((value) => value.trim());
  const merged: string[] = [];
  for (const part of raw) {
    if (merged.length && /\b[A-Z]\.$/.test(merged.at(-1)!)) merged[merged.length - 1] += ` ${part}`;
    else merged.push(part);
  }
  return merged.filter((value) => value.length >= 45 && value.length <= 420);
};
const authority = (url: string): 'PRIMARY' | 'AUTHORITATIVE_SECONDARY' | null => {
  const host = new URL(url).hostname.toLowerCase();
  if (host.endsWith('.gov') || host === 'loc.gov' || host.endsWith('.archives.gov')) return 'PRIMARY';
  if (host.endsWith('.edu') || /(^|\.)(si\.edu|history\.com|britannica\.com|ushmm\.org|iwm\.org\.uk|nationalarchives\.gov\.uk)$/.test(host)) return 'AUTHORITATIVE_SECONDARY';
  return null;
};
const significant = (title: string, topic: string) => new Set(`${title} ${topic}`.toLowerCase().match(/[a-z]{4,}/g) ?? []);
const junk = /\b(article contents|visit the|website about|skip to|share this|privacy policy|newsletter|related terms|related topics|explore more|page last updated|get more details|last updated)\b/i;
const sanitizeSentence = (sentence: string) => sentence
  .replace(/^.*?(?=The primary objective\b)/i, '')
  .replace(/^(?:Mission Highlights|Mission Objective|Launch|Orbit|Landing)\s+/i, '')
  .split(/\b(?:Get more details|Share Details|Last Updated|Related Terms)\b/i)[0]
  .replace(/\s+/g, ' ').trim();
const rankSentence = (sentence: string, title: string, terms: Set<string>) => {
  const lower = sentence.toLowerCase();
  let score = lower.includes(title.toLowerCase()) ? 12 : 0;
  for (const term of terms) if (lower.includes(term)) score += 2;
  if (/\b(launched|landed|returned|mission|objective|crew|surface|historic|first|aftermath|result|legacy)\b/i.test(sentence)) score += 3;
  if (/\b(18|19|20)\d{2}\b/.test(sentence)) score += 2;
  if (junk.test(sentence) || /[{}|]/.test(sentence)) score -= 100;
  return score;
};

export const researchWithWikipediaDiscovery = async (title: string, topic: string): Promise<ResearchReport> => {
  const accessedAt = new Date().toISOString().slice(0, 10);
  const search = await fetchJson<SearchResponse>(endpoint({action: 'query', list: 'search', srsearch: `${title} ${topic}`, srlimit: '1'}));
  const pageTitle = search.query?.search?.[0]?.title;
  if (!pageTitle) throw new Error(`No encyclopedia discovery page found for “${title}”`);
  const [extractData, parseData] = await Promise.all([
    fetchJson<ExtractResponse>(endpoint({action: 'query', prop: 'extracts', explaintext: '1', exsectionformat: 'plain', titles: pageTitle})),
    fetchJson<ParseResponse>(endpoint({action: 'parse', page: pageTitle, prop: 'externallinks'})),
  ]);
  const page = Object.values(extractData.query?.pages ?? {})[0];
  const discoveryUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(pageTitle.replace(/ /g, '_'))}`;
  const sources: ResearchReport['sources'] = [{id: 'discovery-wikipedia', title: page?.title ?? pageTitle, url: discoveryUrl, publisher: 'Wikipedia (discovery only)', accessedAt, authority: 'DISCOVERY_ONLY', rights: 'CC BY-SA; excluded from supported claim gate'}];
  const authoritativeLinks = [...new Set(parseData.parse?.externallinks ?? [])].filter((url) => { try { return Boolean(authority(url)); } catch { return false; } }).slice(0, 8);
  const documents: Array<{sourceId: string; text: string; topical: boolean}> = [];
  for (const [index, url] of authoritativeLinks.entries()) {
    try {
      const response = await fetch(url, {headers: {'User-Agent': USER_AGENT}, redirect: 'follow', signal: AbortSignal.timeout(12000)});
      if (!response.ok || !(response.headers.get('content-type') ?? '').includes('text/html')) continue;
      const html = await response.text();
      const text = stripHtml(html);
      if (text.length < 500) continue;
      const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
      const sourceId = `authority-${index + 1}`;
      const sourceTitle = stripHtml(titleMatch?.[1] ?? new URL(url).hostname);
      sources.push({id: sourceId, title: sourceTitle, url, publisher: new URL(url).hostname, accessedAt, authority: authority(url)!, rights: 'Text used as factual evidence; media rights evaluated separately'});
      documents.push({sourceId, text, topical: sourceTitle.toLowerCase().includes(title.toLowerCase())});
    } catch { /* inaccessible citations are recorded as a warning below */ }
    if (documents.length >= 4) break;
  }
  const terms = significant(title, topic);
  const candidateClaims = documents.flatMap((document) => {
    const semanticSentences = [
      ...(document.text.match(/\bThe primary objective.{30,500}?return to Earth[.!]?/gi) ?? []),
      ...(document.text.match(/\b(?:The result|The legacy|This marked|It was the first)[^.]{30,500}\./gi) ?? []),
    ];
    return [...sentenceSplit(document.text), ...semanticSentences].map(sanitizeSentence).filter((sentence) => sentence.length >= 45 && !/\b[A-Z]\.$/.test(sentence))
    .map((sentence) => ({sourceId: document.sourceId, sentence, score: rankSentence(sentence, title, terms) + (document.topical ? 5 : 0)}))
    .filter((claim) => claim.score >= 5);
  });
  const ranked = [...new Map(candidateClaims.sort((a, b) => b.score - a.score).map((claim) => [claim.sentence.toLowerCase(), claim])).values()];
  const perSource = new Map<string, number>();
  const unique = ranked.filter((claim) => {
    const count = perSource.get(claim.sourceId) ?? 0;
    if (count >= 20) return false;
    perSource.set(claim.sourceId, count + 1);
    return true;
  }).slice(0, 50);
  const claims: ResearchReport['claims'] = unique.map((claim, index) => ({
    id: `claim-${index + 1}`, text: claim.sentence, evidence: claim.sentence, sourceIds: [claim.sourceId],
    confidence: 'HIGH', numbers: claim.sentence.match(/\b(?:\d[\d,.]*|(?:1[5-9]|20)\d{2})\b/g) ?? [], conflictIds: [],
  }));
  const warnings: string[] = [];
  if (authoritativeLinks.length > documents.length) warnings.push(`${authoritativeLinks.length - documents.length} authoritative links could not be acquired as readable HTML`);
  if (claims.length < 6) warnings.push(`Only ${claims.length} supported claims were extracted; at least 6 are required`);
  return {schemaVersion: 1, title, topic, researchedAt: new Date().toISOString(), sources, claims, conflicts: [], warnings, status: 'FAIL'};
};
