import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';
import {LibraryOfCongressAdapter} from './adapters/library-of-congress';
import type {ArchiveCandidate} from './adapters';
import {WikimediaCommonsAdapter} from './adapters/wikimedia-commons';
import {InternetArchiveAdapter} from './adapters/internet-archive';
import {NasaImagesAdapter} from './adapters/nasa-images';

const safeName = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 70);
const genericSearchWords = new Set('central event hook context escalation aftermath significance historical history first from with that this into'.split(' '));
const relevantToQuery = (query: string, candidate: ArchiveCandidate) => {
  const queryTokens = new Set((query.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((word) => !genericSearchWords.has(word) && (word.length > 3 || /^\d+$/.test(word))));
  const titleTokens = new Set(candidate.title.toLowerCase().match(/[a-z0-9]+/g) ?? []);
  return [...queryTokens].some((word) => titleTokens.has(word));
};
export const searchLoc = async (query: string, limit: number) => new LibraryOfCongressAdapter().search(query, limit);
const searchProvidersOnce = async (query: string, limit: number) => {
  const providers = [new LibraryOfCongressAdapter(), new WikimediaCommonsAdapter(), new InternetArchiveAdapter(), new NasaImagesAdapter()];
  const candidates: ArchiveCandidate[] = [];
  const errors: string[] = [];
  const results = await Promise.allSettled(providers.map((provider) => provider.search(query, limit)));
  results.forEach((result, index) => result.status === 'fulfilled' ? candidates.push(...result.value) : errors.push(`${providers[index].constructor.name}: ${result.reason instanceof Error ? result.reason.message : result.reason}`));
  return {candidates: candidates.filter((candidate) => relevantToQuery(query, candidate)).sort((a, b) => {
    const rights = (candidate: ArchiveCandidate) => candidate.rightsStatus === 'NO_KNOWN_RESTRICTIONS' ? 2 : candidate.rightsStatus === 'LICENSED' ? 1 : 0;
    return rights(b) - rights(a) || b.score - a.score;
  }).slice(0, limit * 2), errors};
};

const searchProviders = async (query: string, limit: number) => {
  const variants = query.split('|').map((item) => item.trim()).filter(Boolean);
  const results = await Promise.all(variants.map((variant) => searchProvidersOnce(variant, limit)));
  const seen = new Set<string>();
  return {
    candidates: results.flatMap((result) => result.candidates).filter((candidate) => {
      if (seen.has(candidate.itemUrl)) return false;
      seen.add(candidate.itemUrl);
      return true;
    }).slice(0, Math.max(limit * 3, 6)),
    errors: results.flatMap((result) => result.errors),
  };
};

export const collectLocCandidates = async (manifestFile: string, download: boolean) => {
  const manifest = parseManifest(JSON.parse(await readFile(manifestFile, 'utf8')));
  const projectDir = path.dirname(path.resolve(manifestFile));
  const candidateDir = path.join(projectDir, 'archive-candidates');
  const report: Array<{sceneId: string; query: string; candidates: ArchiveCandidate[]; errors: string[]}> = [];
  const queryCache = new Map<string, Awaited<ReturnType<typeof searchProviders>>>();
  if (download) await mkdir(candidateDir, {recursive: true});

  for (const scene of manifest.scenes) {
    if (scene.type !== 'ARCHIVE_PHOTO' && scene.type !== 'KEN_BURNS') continue;
    const query = scene.payload.archiveQuery;
    if (!query) continue;
    const cached = queryCache.get(query) ?? await searchProviders(query, 3);
    queryCache.set(query, cached);
    const candidates = cached.candidates.map((candidate) => ({...candidate}));
    const errors = [...cached.errors];
    report.push({sceneId: scene.id, query, candidates, errors});
    if (download) {
      for (const [index, candidate] of candidates.entries()) {
        if (candidate.rightsStatus !== 'NO_KNOWN_RESTRICTIONS' && candidate.rightsStatus !== 'LICENSED') continue;
        const response = await fetch(candidate.imageUrl, {headers: {'User-Agent': 'HistoryDocumentaryEngine/0.1'}});
        const contentLength = Number(response.headers.get('content-length') ?? 0);
        if (!response.ok || contentLength > 25_000_000) { errors.push(`Candidate download skipped (${response.status}, ${contentLength} bytes): ${candidate.itemUrl}`); continue; }
        const imageData = await response.arrayBuffer();
        if (imageData.byteLength > 25_000_000) { errors.push(`Candidate body too large (${imageData.byteLength} bytes): ${candidate.itemUrl}`); continue; }
        await writeFile(path.join(candidateDir, `${safeName(scene.id)}-${index + 1}.jpg`), Buffer.from(imageData));
      }
    }
  }
  const reportFile = path.join(projectDir, 'archive-candidates.json');
  await writeFile(reportFile, `${JSON.stringify({provider: 'Library of Congress + Wikimedia Commons + Internet Archive + NASA Images', generatedAt: new Date().toISOString(), manifest: manifest.id, scenes: report}, null, 2)}\n`);
  return {reportFile, sceneCount: report.length, candidateCount: report.reduce((sum, entry) => sum + entry.candidates.length, 0)};
};

type CandidateReport = {
  provider: string;
  generatedAt: string;
  manifest: string;
  scenes: Array<{sceneId: string; query: string; candidates: ArchiveCandidate[]}>;
};

export const promoteLocCandidates = async (manifestFile: string) => {
  const absoluteManifest = path.resolve(manifestFile);
  const projectDir = path.dirname(absoluteManifest);
  const reportFile = path.join(projectDir, 'archive-candidates.json');
  const originalText = await readFile(absoluteManifest, 'utf8');
  const manifest = parseManifest(JSON.parse(originalText));
  const report = JSON.parse(await readFile(reportFile, 'utf8')) as CandidateReport;
  if (report.manifest !== manifest.id) throw new Error(`Candidate report is for ${report.manifest}, not ${manifest.id}`);

  const usedItems = new Set<string>();
  const promotions: Array<{sceneId: string; itemUrl: string; title: string; localAsset: string}> = [];
  const skipped: Array<{sceneId: string; reason: string}> = [];
  const assetDir = path.join(projectDir, 'archive-assets');
  await mkdir(assetDir, {recursive: true});

  for (const entry of report.scenes) {
    const scene = manifest.scenes.find((candidateScene) => candidateScene.id === entry.sceneId);
    if (!scene || (scene.type !== 'ARCHIVE_PHOTO' && scene.type !== 'KEN_BURNS')) continue;
    const anchorYears = `${manifest.title} ${manifest.topic} ${scene.narration ?? ''}`.match(/\b(?:1[5-9]|20)\d{2}\b/g)?.map(Number) ?? [];
    const dateFits = (item: ArchiveCandidate) => {
      const itemYear = item.date?.match(/\b(?:1[5-9]|20)\d{2}\b/)?.[0];
      if (!itemYear || anchorYears.length === 0) return true;
      return Number(itemYear) >= Math.min(...anchorYears) - 50 && Number(itemYear) <= Math.max(...anchorYears) + 5;
    };
    const eligible = [...entry.candidates]
      .filter((item) => (item.rightsStatus === 'NO_KNOWN_RESTRICTIONS' || item.rightsStatus === 'LICENSED') && !usedItems.has(item.itemUrl) && dateFits(item))
      .sort((a, b) => b.score - a.score);
    if (!eligible.length) {
      skipped.push({sceneId: entry.sceneId, reason: 'No unused rights-cleared, date-compatible candidate'});
      continue;
    }
    let candidate: ArchiveCandidate | undefined;
    let imageData: ArrayBuffer | undefined;
    for (const item of eligible) {
      const attempt = await fetch(item.imageUrl, {headers: {'User-Agent': 'HistoryDocumentaryEngine/0.1'}}).catch(() => null);
      const contentLength = Number(attempt?.headers.get('content-length') ?? 0);
      if (attempt?.ok && contentLength <= 25_000_000) {
        const data = await attempt.arrayBuffer();
        if (data.byteLength <= 25_000_000) { candidate = item; imageData = data; break; }
      }
    }
    if (!candidate || !imageData) { skipped.push({sceneId: entry.sceneId, reason: 'Rights-cleared candidates could not be downloaded'}); continue; }
    const localFile = path.join(assetDir, `${safeName(scene.id)}.jpg`);
    await writeFile(localFile, Buffer.from(imageData));
    const publicPath = path.relative(path.resolve('public'), localFile).split(path.sep).join('/');
    scene.payload.src = publicPath;
    scene.payload.archiveItemUrl = candidate.itemUrl;
    scene.payload.rightsStatus = candidate.rightsStatus;
    scene.payload.credit = `${candidate.credit} — ${candidate.title}`;
    const sourceId = `loc-${candidate.itemUrl.match(/item\/(\d+)/)?.[1] ?? safeName(candidate.title)}`;
    if (!manifest.sources.some((source) => source.id === sourceId)) manifest.sources.push({
      id: sourceId,
      title: candidate.title,
      url: candidate.itemUrl,
      publisher: candidate.credit,
      accessedAt: new Date().toISOString().slice(0, 10),
      rights: candidate.rightsText,
    });
    if (!scene.sourceIds.includes(sourceId)) scene.sourceIds.push(sourceId);
    usedItems.add(candidate.itemUrl);
    promotions.push({sceneId: scene.id, itemUrl: candidate.itemUrl, title: candidate.title, localAsset: publicPath});
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupFile = path.join(projectDir, `manifest.before-archive-${timestamp}.json`);
  await writeFile(backupFile, originalText);
  await writeFile(absoluteManifest, `${JSON.stringify(parseManifest(manifest), null, 2)}\n`);
  const promotionReport = path.join(projectDir, 'archive-promotions.json');
  await writeFile(promotionReport, `${JSON.stringify({generatedAt: new Date().toISOString(), backupFile: path.basename(backupFile), promotions, skipped}, null, 2)}\n`);
  return {backupFile, promotionReport, promotions, skipped};
};
