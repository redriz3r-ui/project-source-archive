import type {ArchiveAdapter, ArchiveCandidate} from '../adapters';

type CommonsPage = {title?: string; imageinfo?: Array<{url?: string; thumburl?: string; descriptionurl?: string; extmetadata?: Record<string, {value?: string}>}>};
const plain = (value = '') => value.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').trim();

export class WikimediaCommonsAdapter implements ArchiveAdapter {
  async search(query: string, limit = 5): Promise<ArchiveCandidate[]> {
    const params = new URLSearchParams({action: 'query', format: 'json', origin: '*', generator: 'search', gsrsearch: `${query} filetype:bitmap`, gsrnamespace: '6', gsrlimit: String(Math.max(limit * 2, 10)), prop: 'imageinfo', iiprop: 'url|extmetadata', iiurlwidth: '1600'});
    const response = await fetch(`https://commons.wikimedia.org/w/api.php?${params}`, {headers: {'User-Agent': 'HistoryDocumentaryEngine/0.1'}});
    if (!response.ok) throw new Error(`Wikimedia Commons search failed: ${response.status}`);
    const data = await response.json() as {query?: {pages?: Record<string, CommonsPage>}};
    return Object.values(data.query?.pages ?? {}).flatMap((page, index) => {
      const info = page.imageinfo?.[0];
      if (!info?.url || !info.descriptionurl) return [];
      const meta = info.extmetadata ?? {};
      const license = plain(meta.LicenseShortName?.value);
      const rightsText = [license, plain(meta.UsageTerms?.value), plain(meta.AttributionRequired?.value) === 'true' ? 'Attribution required' : ''].filter(Boolean).join(' — ');
      const publicDomain = /public domain|cc0/i.test(license);
      const permissive = /^CC BY(?:-|$)/i.test(license);
      return [{itemUrl: info.descriptionurl, imageUrl: info.thumburl ?? info.url, title: (page.title ?? 'Wikimedia Commons file').replace(/^File:/, ''), date: plain(meta.DateTimeOriginal?.value || meta.DateTime?.value), credit: plain(meta.Credit?.value || meta.Artist?.value || 'Wikimedia Commons'), rightsStatus: publicDomain ? 'NO_KNOWN_RESTRICTIONS' as const : permissive ? 'LICENSED' as const : 'REVIEW_REQUIRED' as const, rightsText: rightsText || 'License metadata missing', score: Math.max(1, limit * 2 - index)}];
    }).filter((candidate) => /\.(?:jpe?g|png|webp)(?:\?|$)/i.test(candidate.imageUrl)).slice(0, limit);
  }
}
