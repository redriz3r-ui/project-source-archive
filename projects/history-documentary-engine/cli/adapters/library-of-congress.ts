import type {ArchiveAdapter, ArchiveCandidate} from '../adapters';

type LocResult = {
  id?: string;
  aka?: string[];
  url?: string;
  title?: string;
  date?: string;
  description?: string[];
  image_url?: string[];
  subject?: string[];
  unrestricted?: boolean;
  access_restricted?: boolean;
  digitized?: boolean;
};

const tokens = (value: string) => new Set(value.toLowerCase().match(/[a-z0-9]+/g) ?? []);
const overlap = (query: string, value: string) => {
  const queryTokens = tokens(query);
  return [...tokens(value)].filter((token) => queryTokens.has(token)).length;
};
const cleanImageUrl = (url: string) => url.replace(/#.*$/, '');
const bestJpeg = (urls: string[]) => [...urls].reverse().find((url) => /\.jpe?g(?:#|$)/i.test(url));
const fetchWithRetry = async (url: string, attempts = 3): Promise<Response> => {
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const response = await fetch(url);
      if (response.ok || response.status < 500) return response;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, attempt * 400));
  }
  throw lastError instanceof Error ? lastError : new Error(`Request failed: ${url}`);
};

export class LibraryOfCongressAdapter implements ArchiveAdapter {
  async search(query: string, limit = 5): Promise<ArchiveCandidate[]> {
    const params = new URLSearchParams({q: query, fo: 'json', at: 'results', c: String(Math.max(limit * 3, 15)), fa: 'digitized:true'});
    const response = await fetchWithRetry(`https://www.loc.gov/photos/?${params}`);
    if (!response.ok) throw new Error(`Library of Congress search failed: ${response.status}`);
    const data = await response.json() as {results?: LocResult[]};
    const ranked = (data.results ?? [])
      .filter((item) => item.digitized && !item.access_restricted && item.unrestricted && bestJpeg(item.image_url ?? []))
      .map((item) => ({item, score: overlap(query, `${item.title ?? ''} ${(item.subject ?? []).join(' ')} ${(item.description ?? []).join(' ')}`) * 10 + Math.min((item.image_url ?? []).length, 5)}))
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    return Promise.all(ranked.map(async ({item, score}) => {
      const itemUrl = (item.id ?? item.url ?? '').replace(/^http:/, 'https:');
      const rightsResponse = itemUrl ? await fetchWithRetry(`${itemUrl}?fo=json&at=item`).catch(() => null) : null;
      const rightsData = rightsResponse?.ok ? await rightsResponse.json().catch(() => ({})) as {item?: {rights_advisory?: string}} : {};
      const rightsAdvisory = rightsData.item?.rights_advisory ?? '';
      const noKnownRestrictions = /no known restrictions on publication/i.test(rightsAdvisory);
      return {
        itemUrl,
        imageUrl: cleanImageUrl(bestJpeg(item.image_url ?? [])!),
        title: item.title ?? 'Untitled Library of Congress item',
        date: item.date,
        credit: 'Library of Congress',
        rightsStatus: noKnownRestrictions ? 'NO_KNOWN_RESTRICTIONS' : 'REVIEW_REQUIRED',
        rightsText: rightsAdvisory || 'Rights advisory requires human review',
        score,
      } satisfies ArchiveCandidate;
    }));
  }
}
