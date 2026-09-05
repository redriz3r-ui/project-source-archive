import type {ArchiveAdapter, ArchiveCandidate} from '../adapters';

type IaDoc = {identifier?: string; title?: string; date?: string; licenseurl?: string};
type IaMetadata = {metadata?: {title?: string; date?: string; licenseurl?: string; creator?: string}; files?: Array<{name?: string; format?: string}>};

export class InternetArchiveAdapter implements ArchiveAdapter {
  async search(query: string, limit = 5): Promise<ArchiveCandidate[]> {
    const params = new URLSearchParams({q: `(${query}) AND mediatype:image`, fl: 'identifier,title,date,licenseurl', rows: String(Math.max(limit * 2, 10)), page: '1', output: 'json'});
    const response = await fetch(`https://archive.org/advancedsearch.php?${params}`, {headers: {'User-Agent': 'HistoryDocumentaryEngine/0.1'}});
    if (!response.ok) throw new Error(`Internet Archive search failed: ${response.status}`);
    const data = await response.json() as {response?: {docs?: IaDoc[]}};
    const found = await Promise.all((data.response?.docs ?? []).map(async (doc, index): Promise<ArchiveCandidate | null> => {
      if (!doc.identifier) return null;
      const metadataResponse = await fetch(`https://archive.org/metadata/${encodeURIComponent(doc.identifier)}`, {signal: AbortSignal.timeout(8000)}).catch(() => null);
      if (!metadataResponse?.ok) return null;
      const metadata = await metadataResponse.json() as IaMetadata;
      const file = metadata.files?.find((entry) => /JPEG|PNG/i.test(entry.format ?? '') && /\.(?:jpe?g|png)$/i.test(entry.name ?? ''));
      if (!file?.name) return null;
      const license = metadata.metadata?.licenseurl ?? doc.licenseurl ?? '';
      const cleared = /creativecommons\.org\/licenses\/(?:by|by-sa)\/|creativecommons\.org\/(?:publicdomain|public-domain)|public domain/i.test(license);
      const noRestrictions = /publicdomain|public-domain|public domain/i.test(license);
      return {itemUrl: `https://archive.org/details/${doc.identifier}`, imageUrl: `https://archive.org/download/${doc.identifier}/${encodeURIComponent(file.name)}`, title: metadata.metadata?.title ?? doc.title ?? doc.identifier, date: metadata.metadata?.date ?? doc.date, credit: metadata.metadata?.creator ?? 'Internet Archive', rightsStatus: noRestrictions ? 'NO_KNOWN_RESTRICTIONS' : cleared ? 'LICENSED' : 'REVIEW_REQUIRED', rightsText: license || 'License metadata missing', score: Math.max(1, limit * 2 - index)};
    }));
    return found.filter((candidate): candidate is ArchiveCandidate => Boolean(candidate)).slice(0, limit);
  }
}
