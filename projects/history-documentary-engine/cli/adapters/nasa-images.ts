import type {ArchiveAdapter, ArchiveCandidate} from '../adapters';

type NasaItem = {href?: string; data?: Array<{nasa_id?: string; title?: string; date_created?: string; center?: string; description?: string}>; links?: Array<{href?: string; rel?: string; render?: string}>};
const tokens = (text: string) => new Set(text.toLowerCase().match(/[a-z0-9]+/g) ?? []);

export class NasaImagesAdapter implements ArchiveAdapter {
  async search(query: string, limit = 5): Promise<ArchiveCandidate[]> {
    const broadQuery = query.split('|')[0].trim();
    const response = await fetch(`https://images-api.nasa.gov/search?${new URLSearchParams({q: broadQuery, media_type: 'image', page_size: String(Math.max(20, limit * 4))})}`, {headers: {'User-Agent': 'HistoryDocumentaryEngine/0.1'}});
    if (!response.ok) throw new Error(`NASA Images search failed: ${response.status}`);
    const data = await response.json() as {collection?: {items?: NasaItem[]}};
    const queryTokens = tokens(query);
    return (data.collection?.items ?? []).flatMap((item) => {
      const metadata = item.data?.[0];
      const imageUrl = item.links?.find((link) => link.render === 'image')?.href;
      if (!metadata?.nasa_id || !imageUrl) return [];
      const score = [...tokens(`${metadata.title ?? ''} ${metadata.description ?? ''}`)].filter((token) => queryTokens.has(token)).length * 10;
      return [{itemUrl: `https://images.nasa.gov/details/${encodeURIComponent(metadata.nasa_id)}`, imageUrl, title: metadata.title ?? metadata.nasa_id, date: metadata.date_created?.slice(0, 10), credit: metadata.center ? `NASA/${metadata.center}` : 'NASA', rightsStatus: 'NO_KNOWN_RESTRICTIONS' as const, rightsText: 'NASA content; subject to NASA Media Usage Guidelines and any item-specific notices', score}];
    }).sort((a, b) => b.score - a.score).slice(0, limit);
  }
}
