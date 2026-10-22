import GeoTIFF, { fromBlob, fromUrl, Pool } from 'geotiff';
import { webMercatorToWgs84 } from '../geo/webMercator';

const MAX_LOCAL_BYTES = 256 * 1024 * 1024;
const MAX_DECODE_PIXELS = 4_000_000;
const MAX_TILE_PIXELS = 1_048_576;
const MAX_TILE_BYTES = 16 * 1024 * 1024;
const MAX_DISPLAY_SIDE = 1024;
const MERCATOR_LIMIT = 20037508.342789244;
const LAT_LIMIT = 85.05112878;

export type TiffSource = { kind: 'local'; name: string; bytes: number } | { kind: 'remote'; url: string };
export type TiffMetadata = {
  source: TiffSource;
  width: number;
  height: number;
  bands: number;
  crs: 'EPSG:4326' | 'EPSG:3857';
  boundsNative: [number, number, number, number];
  boundsWgs84: [number, number, number, number];
  resolution: [number, number];
  resolutionUnit: 'degrees' | 'meters';
  pixelInterpretation: 'area';
  noData: number | null;
  bandUnits: Array<string | null>;
  bandDescriptions: Array<string | null>;
  copyright: string | null;
  overviewSizes: Array<[number, number]>;
};
export type TiffSession = { tiff: GeoTIFF; metadata: TiffMetadata; imageIndex: number };
export type DecodedBand = { values: ArrayLike<number>; width: number; height: number; min: number; max: number; overview: [number, number] };

function mercatorY(lat: number): number {
  const radians = lat * Math.PI / 180;
  return Math.log(Math.tan(Math.PI / 4 + radians / 2));
}
function latitudeAtMercatorY(y: number): number {
  return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI;
}

function validateRemoteUrl(input: string): string {
  const value = input.trim();
  if (!value || value.length > 4096) throw new Error('Enter a GeoTIFF URL.');
  let url: URL;
  try { url = new URL(value); } catch { throw new Error('Enter a valid HTTPS GeoTIFF URL.'); }
  if (url.username || url.password) throw new Error('Credentials in URLs are unsupported. Use a signed HTTPS URL if needed.');
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))) {
    throw new Error('Use HTTPS, or HTTP on localhost for development.');
  }
  return url.href;
}

async function checkRemoteRanges(url: string): Promise<void> {
  let response: Response;
  try { response = await fetch(url, { headers: { Range: 'bytes=0-16383' } }); }
  catch { throw new Error('The GeoTIFF host could not be reached from this browser. Check the URL and CORS policy.'); }
  const contentRange = response.headers.get('Content-Range');
  await response.body?.cancel();
  if (response.status !== 206 || !contentRange || !/^bytes 0-\d+\/\d+$/i.test(contentRange)) {
    throw new Error('This host must allow CORS and return HTTP 206 with Content-Range for byte requests.');
  }
  if (Number(contentRange.split('/')[1]) > 2_000_000_000) {
    throw new Error('Remote archives above 2 GB are outside this bounded browser workflow.');
  }
}

async function inspect(tiff: GeoTIFF, source: TiffSource): Promise<TiffSession> {
  const image = await tiff.getImage(0);
  const width = image.getWidth();
  const height = image.getHeight();
  const bands = image.getSamplesPerPixel();
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1) throw new Error('Invalid raster dimensions.');
  if (!Number.isSafeInteger(bands) || bands < 1 || bands > 16) throw new Error('Only rasters with 1–16 bands are supported.');
  const keys = image.getGeoKeys();
  const modelType = keys?.GTModelTypeGeoKey;
  const crs = modelType === 1 ? (keys?.ProjectedCSTypeGeoKey === 3857 ? 'EPSG:3857' : null) :
    modelType === 2 ? (keys?.GeographicTypeGeoKey === 4326 ? 'EPSG:4326' : null) :
    keys?.ProjectedCSTypeGeoKey === 3857 && !keys?.GeographicTypeGeoKey ? 'EPSG:3857' :
    keys?.GeographicTypeGeoKey === 4326 && !keys?.ProjectedCSTypeGeoKey ? 'EPSG:4326' : null;
  if (!crs) {
    const code = modelType === 1 ? keys?.ProjectedCSTypeGeoKey : modelType === 2 ? keys?.GeographicTypeGeoKey :
      keys?.ProjectedCSTypeGeoKey ?? keys?.GeographicTypeGeoKey;
    throw new Error(`CRS ${code ? `EPSG:${code}` : 'is missing'}; this viewer currently supports only EPSG:4326 and EPSG:3857.`);
  }
  if (keys?.GTRasterTypeGeoKey && keys.GTRasterTypeGeoKey !== 1) {
    throw new Error('PixelIsPoint rasters are not yet supported; their half-pixel offset must be handled explicitly.');
  }
  const tags = image.getFileDirectory();
  const transform = tags.getValue('ModelTransformation') as number[] | undefined;
  if (transform && (Math.abs(transform[1]) > 1e-10 || Math.abs(transform[4]) > 1e-10)) {
    throw new Error('Rotated or skewed GeoTIFF grids are not supported by this image overlay.');
  }
  const tiepoint = tags.getValue('ModelTiepoint') as number[] | undefined;
  if (tiepoint && (tiepoint.length !== 6 || tiepoint[0] !== 0 || tiepoint[1] !== 0)) {
    throw new Error('A non-origin tie point or multiple tie points require an affine transform this viewer cannot safely infer.');
  }
  let resolution: number[];
  let bbox: number[];
  try { resolution = image.getResolution(); bbox = image.getBoundingBox(); }
  catch { throw new Error('The file has no usable georeferencing transform.'); }
  if (resolution[0] <= 0 || resolution[1] >= 0 || ![...resolution.slice(0, 2), ...bbox].every(Number.isFinite)) {
    throw new Error('Only north-up rasters with positive eastward resolution are supported.');
  }
  const [west, south, east, north] = bbox;
  if (west >= east || south >= north) throw new Error('The GeoTIFF has invalid bounds.');
  let boundsWgs84: [number, number, number, number];
  if (crs === 'EPSG:4326') {
    if (west < -180 || east > 180 || south <= -LAT_LIMIT || north >= LAT_LIMIT) {
      throw new Error('WGS84 bounds must lie within the supported Web Mercator latitude and longitude range.');
    }
    boundsWgs84 = [west, south, east, north];
  } else {
    if (Math.max(Math.abs(west), Math.abs(east), Math.abs(south), Math.abs(north)) > MERCATOR_LIMIT) {
      throw new Error('EPSG:3857 bounds exceed the Web Mercator world extent.');
    }
    const [lonWest, latSouth] = webMercatorToWgs84(west, south);
    const [lonEast, latNorth] = webMercatorToWgs84(east, north);
    boundsWgs84 = [lonWest, latSouth, lonEast, latNorth];
  }
  const imageCount = await tiff.getImageCount();
  if (imageCount > 32) throw new Error('Files with more than 32 image directories are outside this bounded workflow.');
  const images = await Promise.all(Array.from({ length: imageCount }, (_, index) => tiff.getImage(index)));
  const overviewSizes = images.map(item => [item.getWidth(), item.getHeight()] as [number, number]);
  const targetRatio = Math.min(1, MAX_DISPLAY_SIDE / Math.max(width, height));
  const targetWidth = Math.max(1, Math.round(width * targetRatio));
  const targetHeight = Math.max(1, Math.round(height * targetRatio));
  const candidates = images.map((item, index) => ({ item, index })).filter(({ item, index }) => {
    const directory = item.getFileDirectory();
    const subfileType = directory.getValue('SubfileType');
    const newSubfileType = directory.getValue('NewSubfileType');
    return (index === 0 || subfileType === 2 || ((Number(newSubfileType) || 0) & 1) === 1) &&
    item.getWidth() * item.getHeight() <= MAX_DECODE_PIXELS &&
    item.getTileWidth() * item.getTileHeight() <= MAX_TILE_PIXELS &&
    item.getTileWidth() * item.getTileHeight() * item.getBytesPerPixel() <= MAX_TILE_BYTES &&
    item.getSamplesPerPixel() === bands &&
    Math.abs(item.getWidth() / item.getHeight() - width / height) / (width / height) < 0.01 &&
    item.getWidth() / width >= 1 / 128 && item.getHeight() / height >= 1 / 128;
  }).sort((a, b) => a.item.getWidth() * a.item.getHeight() - b.item.getWidth() * b.item.getHeight());
  const candidate = candidates.find(({ item }) => item.getWidth() >= targetWidth && item.getHeight() >= targetHeight) ?? candidates.at(-1);
  if (!candidate) throw new Error('This raster needs an overview of at most 4 million pixels, with tiles at most 1 million pixels and 16 MB decoded.');
  const bandUnits: Array<string | null> = [];
  const bandDescriptions: Array<string | null> = [];
  for (let index = 0; index < bands; index++) {
    const metadata = await image.getGDALMetadata(index);
    bandUnits.push(typeof metadata?.UNITTYPE === 'string' ? metadata.UNITTYPE : null);
    bandDescriptions.push(typeof metadata?.DESCRIPTION === 'string' ? metadata.DESCRIPTION : null);
  }
  const copyright = tags.getValue('Copyright' as any);
  const noData = image.getGDALNoData();
  return { tiff, imageIndex: candidate.index, metadata: {
    source, width, height, bands, crs, boundsNative: bbox as [number, number, number, number], boundsWgs84,
    resolution: [resolution[0], Math.abs(resolution[1])], resolutionUnit: crs === 'EPSG:4326' ? 'degrees' : 'meters',
    pixelInterpretation: 'area', noData: Number.isFinite(noData) ? noData : null, bandUnits, bandDescriptions,
    copyright: typeof copyright === 'string' && copyright.trim() ? copyright.trim() : null, overviewSizes,
  } };
}

export async function inspectLocalTiff(file: File): Promise<TiffSession> {
  if (file.size > MAX_LOCAL_BYTES) throw new Error('Local GeoTIFFs must be 256 MB or smaller.');
  if (!file.size) throw new Error('The file is empty.');
  try { return await inspect(await fromBlob(file), { kind: 'local', name: file.name, bytes: file.size }); }
  catch (error) {
    if (error instanceof Error && /byte order|magic|invalid tiff|unknown tiff/i.test(error.message)) {
      throw new Error('This is not a valid GeoTIFF or TIFF file.');
    }
    throw error instanceof Error ? error : new Error('Could not read this GeoTIFF.');
  }
}

export async function inspectRemoteTiff(input: string): Promise<TiffSession> {
  const url = validateRemoteUrl(input);
  await checkRemoteRanges(url);
  try {
    const tiff = await fromUrl(url, { allowFullFile: false, maxRanges: 0, blockSize: 65536, cacheSize: 32 } as any);
    return await inspect(tiff, { kind: 'remote', url });
  } catch (error) { throw error instanceof Error ? error : new Error('Could not read the remote GeoTIFF.'); }
}

export async function decodeTiffBand(session: TiffSession, band: number): Promise<DecodedBand> {
  if (!Number.isInteger(band) || band < 0 || band >= session.metadata.bands) throw new Error('Choose a valid band.');
  const image = await session.tiff.getImage(session.imageIndex);
  const ratio = Math.min(1, MAX_DISPLAY_SIDE / Math.max(image.getWidth(), image.getHeight()));
  const width = Math.max(1, Math.round(image.getWidth() * ratio));
  const height = Math.max(1, Math.round(image.getHeight() * ratio));
  const pool = new Pool(2);
  let rasters: Awaited<ReturnType<typeof image.readRasters>>;
  try { rasters = await image.readRasters({ samples: [band], width, height, resampleMethod: 'nearest', pool }); }
  finally { await pool.destroy(); }
  const values = rasters[0] as ArrayLike<number>;
  if (values.length !== width * height) throw new Error('Decoded band dimensions do not match the requested display size.');
  let min = Infinity;
  let max = -Infinity;
  const noData = session.metadata.noData;
  for (let index = 0; index < values.length; index++) {
    const value = values[index];
    if (!Number.isFinite(value) || (noData !== null && value === noData)) continue;
    min = Math.min(min, value); max = Math.max(max, value);
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) throw new Error('This band has no finite values after NoData masking.');
  return { values, width, height, min, max, overview: [image.getWidth(), image.getHeight()] };
}

const PALETTE: Array<[number, number, number]> = [[31, 56, 74], [54, 115, 126], [116, 176, 143], [218, 195, 116], [245, 229, 181]];
export const paletteCss = 'linear-gradient(90deg,#1f384a,#36737e,#74b08f,#dac374,#f5e5b5)';
export function renderTiffBand(band: DecodedBand, info: TiffMetadata, low: number, high: number): string {
  if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high) throw new Error('Display minimum must be below maximum.');
  const canvas = document.createElement('canvas'); canvas.width = band.width; canvas.height = band.height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas rendering is unavailable in this browser.');
  const output = context.createImageData(band.width, band.height);
  const [ , south, , north] = info.boundsWgs84;
  const mercSouth = mercatorY(south), mercNorth = mercatorY(north);
  for (let y = 0; y < band.height; y++) {
    const latitude = latitudeAtMercatorY(mercNorth - ((y + 0.5) / band.height) * (mercNorth - mercSouth));
    const sourceY = info.crs === 'EPSG:4326' ? Math.max(0, Math.min(band.height - 1, Math.floor((north - latitude) / (north - south) * band.height))) : y;
    for (let x = 0; x < band.width; x++) {
      const value = band.values[sourceY * band.width + x];
      const offset = (y * band.width + x) * 4;
      if (!Number.isFinite(value) || (info.noData !== null && value === info.noData)) continue;
      const scaled = Math.max(0, Math.min(1, (value - low) / (high - low))) * (PALETTE.length - 1);
      const before = Math.min(PALETTE.length - 2, Math.floor(scaled));
      const fraction = scaled - before;
      for (let channel = 0; channel < 3; channel++) output.data[offset + channel] = Math.round(PALETTE[before][channel] * (1 - fraction) + PALETTE[before + 1][channel] * fraction);
      output.data[offset + 3] = 255;
    }
  }
  context.putImageData(output, 0, 0);
  return canvas.toDataURL('image/png');
}
