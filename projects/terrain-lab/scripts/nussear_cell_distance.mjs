import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { fromFile } from 'geotiff';
import { POINT_DISTANCE_CONTRACT_VERSION, POINT_DISTANCE_OPERATION_ID, runPointDistanceRequest } from '../src/geo/pointDistanceContract.ts';
import { webMercatorToWgs84 } from '../src/geo/webMercator.ts';
import { inspectGeoJson } from '../src/sandbox/geojson.ts';
import { nussearStudy } from '../src/data/nussearStudy.ts';

const root = new URL('../public/', import.meta.url);
const dataset = nussearStudy.datasets.find(item => item.id === 'habitat-model');
const rasterUrl = new URL(`.${dataset.localPath}`, root);
const archiveUrl = new URL('./data/nussear-2009/ofr20091102_dt_Habitat_Model.zip', root);
const archiveSha256 = 'c33d3088e9a5b1c2c653e215b3780657bba5a81d72d98638e126871068dc9ee0';
const rasterSha256 = '42d62244565576c5be0bb1b3cda569240674220bf5ac758a3df2fae0660e6644';

function cellIndex(raw, name) {
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || raw === undefined || String(value) !== raw || value < 0)
    throw new Error(`${name} must be a nonnegative integer.`);
  return value;
}

export async function analyzeCells(indices) {
  if (!Array.isArray(indices) || indices.length !== 4) throw new Error('Provide first-row first-column second-row second-column.');
  const [firstRow, firstColumn, secondRow, secondColumn] = indices.map((raw, index) => cellIndex(raw, ['first-row', 'first-column', 'second-row', 'second-column'][index]));
  if (firstRow === secondRow && firstColumn === secondColumn) throw new Error('Choose two different raster cells.');

  const archiveHash = createHash('sha256').update(await readFile(archiveUrl)).digest('hex');
  if (archiveHash !== archiveSha256) throw new Error('The preserved USGS source archive checksum does not match the registered study.');
  const rasterHash = createHash('sha256').update(await readFile(rasterUrl)).digest('hex');
  if (rasterHash !== rasterSha256) throw new Error('The registered display raster checksum does not match the verified analysis input.');
  const tiff = await fromFile(fileURLToPath(rasterUrl));
  try {
    const image = await tiff.getImage();
    const width = image.getWidth(), height = image.getHeight();
    if (width !== 589 || height !== 738 || image.getGeoKeys().ProjectedCSTypeGeoKey !== 3857 || image.getGeoKeys().GTRasterTypeGeoKey !== 1)
      throw new Error('The registered raster dimensions, CRS, or pixel interpretation changed.');
    const [west, south, east, north] = image.getBoundingBox();
    const [stepX, stepY] = image.getResolution();
    if (![west, south, east, north, stepX, stepY].every(Number.isFinite) || west >= east || south >= north || stepX <= 0 || stepY >= 0)
      throw new Error('The raster has invalid georeferencing.');
    if (image.getGDALNoData() !== -9999) throw new Error('The registered raster NoData value changed.');

    const point = async (row, column) => {
      if (row >= height || column >= width) throw new Error(`Cell (${row}, ${column}) is outside the ${height} × ${width} raster.`);
      const data = await image.readRasters({ window: [column, row, column + 1, row + 1], samples: [0] });
      const value = data[0][0];
      if (!Number.isFinite(value) || value === -9999) throw new Error(`Cell (${row}, ${column}) has no model value.`);
      if (value < 0 || value > 1 || Math.abs(value * 10 - Math.round(value * 10)) > 1e-5)
        throw new Error(`Cell (${row}, ${column}) is outside the published 0–1 binned model values.`);
      const coordinates = webMercatorToWgs84(west + (column + 0.5) * stepX, north + (row + 0.5) * stepY);
      if (coordinates[0] < -119.15 || coordinates[0] > -112.61 || coordinates[1] < 32.42 || coordinates[1] > 39.07)
        throw new Error(`Cell (${row}, ${column}) falls outside the verified raster envelope.`);
      const label = `Model cell (${row}, ${column})`;
      return { key: `${row}:${column}`, label, feature: { type: 'Feature', geometry: { type: 'Point', coordinates }, properties: {
        classification: 'model prediction cell center', observed: false, studyId: nussearStudy.id, datasetId: dataset.id,
        row, column, modelValue: Math.round(value * 10) / 10, modelValueUnit: 'binned habitat potential',
        sourceRaster: dataset.localPath, sourceUrl: dataset.sourceUrl,
      } } };
    };
    const first = await point(firstRow, firstColumn);
    const second = await point(secondRow, secondColumn);
    const execution = await runPointDistanceRequest({ contractVersion: POINT_DISTANCE_CONTRACT_VERSION,
      operationId: POINT_DISTANCE_OPERATION_ID, inputs: { first, second } }, {
      studyId: nussearStudy.id, datasetId: dataset.id, sourceUrl: dataset.sourceUrl,
      sourceArchiveSha256: archiveSha256, sourceRasterSha256: rasterSha256,
    });
    if (!execution.ok) throw new Error(execution.error.message);
    const result = execution.result;
    const line = { ...result.feature, properties: { ...result.feature.properties,
      contractVersion: execution.contractVersion, sourceVerification: execution.provenance.verification,
      studyId: nussearStudy.id, datasetId: dataset.id, sourceRaster: dataset.localPath,
      sourceUrl: dataset.sourceUrl, sourceArchiveSha256: archiveSha256,
      sourceRasterSha256: rasterSha256,
      inputCells: [[firstRow, firstColumn], [secondRow, secondColumn]],
      inputModelValues: [first.feature.properties.modelValue, second.feature.properties.modelValue],
      interpretation: 'Straight-line center-to-center distance only; no habitat connectivity or animal movement inference.',
    } };
    const output = { type: 'FeatureCollection', features: [first.feature, second.feature, line] };
    inspectGeoJson(output);
    return output;
  } finally { await tiff.close(); }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(new URL(`file://${process.argv[1]}`))) {
  try {
    const args = process.argv.slice(2);
    const outputFlag = args.indexOf('--output');
    let outputPath;
    if (outputFlag !== -1) {
      if (!args[outputFlag + 1]) throw new Error('--output requires a file path.');
      outputPath = args[outputFlag + 1];
      args.splice(outputFlag, 2);
    }
    const output = await analyzeCells(args);
    const json = `${JSON.stringify(output, null, 2)}\n`;
    if (outputPath) await writeFile(outputPath, json);
    else process.stdout.write(json);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
