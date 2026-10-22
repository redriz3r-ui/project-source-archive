import { PMTiles, TileType, type Header, type RangeResponse, type Source } from 'pmtiles';

const MAX_RANGE_BYTES = 4 * 1024 * 1024;

export type ArchiveKind = 'vector' | 'raster';
export type PmtilesLayerConfig = {
  id: string;
  url: string;
  name: string;
  kind: ArchiveKind;
  tileType: string;
  sourceLayer: string | null;
  attribution: string;
  requiredAttribution: string;
  bounds: [number, number, number, number];
  minZoom: number;
  maxZoom: number;
  tileSize: 256 | 512;
  visible: boolean;
  opacity: number;
};
export type ArchiveInspection = {
  archive: PMTiles;
  source: StrictRangeSource;
  url: string;
  kind: ArchiveKind;
  tileType: string;
  name: string;
  description: string;
  attribution: string;
  sourceLayers: string[];
  bounds: [number, number, number, number];
  minZoom: number;
  maxZoom: number;
  tileSize: 256 | 512;
  addressedTiles: number;
};

export function parseArchiveUrl(input: string): string {
  const trimmed = input.trim().replace(/^pmtiles:\/\//i, '');
  if (!trimmed || trimmed.length > 4096) throw new Error('Enter a hosted PMTiles URL.');
  let url: URL;
  try { url = new URL(trimmed); } catch { throw new Error('Enter a valid absolute HTTPS URL.'); }
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) {
    throw new Error('Use HTTPS for hosted archives. HTTP is allowed only on localhost.');
  }
  if (url.username || url.password) throw new Error('Put archives at a URL without embedded username or password.');
  if (url.hash) throw new Error('Remove the URL fragment after #; it is not sent to the archive host.');
  return url.toString();
}

function responseMessage(response: Response): string {
  if (response.status === 404) return 'Archive not found (HTTP 404). Check the URL.';
  if (response.status === 401 || response.status === 403) return `Archive access denied (HTTP ${response.status}). Use a public URL or a valid signed URL.`;
  if (response.status === 416) return 'The host rejected a byte range request (HTTP 416). Check its Range support.';
  return `Archive request failed (HTTP ${response.status}).`;
}

export class StrictRangeSource implements Source {
  private lastError = 0;
  onFailure?: (message: string) => void;
  readonly url: string;

  constructor(url: string) { this.url = url; }
  getKey(): string { return this.url; }

  async getBytes(offset: number, length: number, signal?: AbortSignal, etag?: string): Promise<RangeResponse> {
    if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(length) || length < 1 || length > MAX_RANGE_BYTES) {
      throw new Error('The archive requested an invalid or oversized byte range.');
    }
    try {
      const response = await fetch(this.url, {
        headers: { Range: `bytes=${offset}-${offset + length - 1}` }, signal, credentials: 'omit',
      });
      if (response.status === 200) {
        await response.body?.cancel();
        throw new Error('The host returned the whole archive. It must support HTTP 206 byte range responses.');
      }
      if (response.status !== 206) {
        await response.body?.cancel();
        throw new Error(responseMessage(response));
      }
      const range = response.headers.get('Content-Range');
      if (range) {
        const match = /^bytes (\d+)-(\d+)\/(\d+|\*)$/i.exec(range);
        if (!match || Number(match[1]) !== offset || Number(match[2]) < offset || Number(match[2]) - offset + 1 > length) {
          await response.body?.cancel();
          throw new Error('The host returned an incorrect Content-Range for this archive.');
        }
      }
      const declaredLength = Number(response.headers.get('Content-Length'));
      if (declaredLength > length) {
        await response.body?.cancel();
        throw new Error('The host sent more bytes than requested; check its Range configuration.');
      }
      if (etag && response.headers.get('ETag') && response.headers.get('ETag') !== etag) {
        await response.body?.cancel();
        throw new Error('The archive changed while tiles were loading. Inspect it again.');
      }
      if (!response.body) throw new Error('The host returned no archive bytes.');
      const reader = response.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > length) {
          await reader.cancel();
          throw new Error('The host sent more bytes than requested; check its Range configuration.');
        }
        chunks.push(part.value);
      }
      const bytes = new Uint8Array(size);
      let cursor = 0;
      for (const chunk of chunks) { bytes.set(chunk, cursor); cursor += chunk.byteLength; }
      return {
        data: bytes.buffer,
        etag: response.headers.get('ETag') || undefined,
        cacheControl: response.headers.get('Cache-Control') || undefined,
        expires: response.headers.get('Expires') || undefined,
      };
    } catch (error) {
      if (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw error;
      const message = error instanceof TypeError ? 'The archive could not be reached. Check CORS, network access, and the URL.' :
        error instanceof Error ? error.message : 'The archive request failed.';
      if (Date.now() - this.lastError > 5000) { this.lastError = Date.now(); this.onFailure?.(message); }
      throw new Error(message);
    }
  }
}

function tileKind(header: Header): { kind: ArchiveKind; label: string } {
  switch (header.tileType) {
    case TileType.Mvt: return { kind: 'vector', label: 'MVT vector' };
    case TileType.Mlt: return { kind: 'vector', label: 'MLT vector' };
    case TileType.Png: return { kind: 'raster', label: 'PNG raster' };
    case TileType.Jpeg: return { kind: 'raster', label: 'JPEG raster' };
    case TileType.Webp: return { kind: 'raster', label: 'WebP raster' };
    case TileType.Avif: return { kind: 'raster', label: 'AVIF raster' };
    default: throw new Error('This archive has an unsupported tile type. Use MVT, MLT, PNG, JPEG, WebP, or AVIF tiles.');
  }
}

export async function inspectArchive(input: string): Promise<ArchiveInspection> {
  const url = parseArchiveUrl(input);
  const source = new StrictRangeSource(url);
  const archive = new PMTiles(source);
  let header: Header;
  try { header = await archive.getHeader(); }
  catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (/magic number|spec version/i.test(message)) throw new Error('This is not a supported PMTiles v3 archive.');
    throw error;
  }
  if (header.specVersion !== 3) throw new Error(`PMTiles version ${header.specVersion} is unsupported; use a v3 archive.`);
  const { kind, label } = tileKind(header);
  if (header.minZoom > header.maxZoom || header.maxZoom > 24) throw new Error('The archive has invalid zoom metadata.');
  if (![header.minLon, header.minLat, header.maxLon, header.maxLat].every(Number.isFinite) ||
      header.minLon < -180 || header.maxLon > 180 || header.minLat < -90 || header.maxLat > 90 ||
      header.minLon >= header.maxLon || header.minLat >= header.maxLat) throw new Error('The archive has invalid geographic bounds.');
  if (header.jsonMetadataLength > MAX_RANGE_BYTES) throw new Error('The archive metadata is too large to inspect safely.');
  const raw = header.jsonMetadataLength ? await archive.getMetadata() : {};
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('The archive has invalid JSON metadata.');
  const metadata = raw as Record<string, unknown>;
  const sourceLayers = Array.isArray(metadata.vector_layers) ? [...new Set(metadata.vector_layers.flatMap(item => {
    if (!item || typeof item !== 'object') return [];
    const id = (item as Record<string, unknown>).id;
    return typeof id === 'string' && id.trim() ? [id.trim()] : [];
  }))] : [];
  const filename = decodeURIComponent(new URL(url).pathname.split('/').pop() || 'PMTiles layer');
  return {
    archive, source, url, kind, tileType: label,
    name: typeof metadata.name === 'string' && metadata.name.trim() ? metadata.name.trim().slice(0, 100) : filename,
    description: typeof metadata.description === 'string' ? metadata.description.slice(0, 180) : '',
    attribution: typeof metadata.attribution === 'string' ? metadata.attribution.trim() : '',
    sourceLayers, bounds: [header.minLon, header.minLat, header.maxLon, header.maxLat],
    minZoom: header.minZoom, maxZoom: header.maxZoom,
    tileSize: metadata.tile_size === 512 || metadata.tileSize === 512 ? 512 : 256,
    addressedTiles: header.numAddressedTiles,
  };
}
