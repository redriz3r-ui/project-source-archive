import { inspectGeoJson } from '../sandbox/geojson.ts';
import { validateStudyMetadata, type GeographicRole, type StudyMetadata } from '../data/studyMetadata.ts';

type Issue = { code: string; message: string; severity: 'error' | 'review' };
type Evidence = { field: string; sourceUrl: string; note: string };
type SourceFile = { path: string; sha256: string; sourceMd5: string };

export type ShapefileIntakeManifest = {
  schemaVersion: 'terrain-lab-intake-source/v2';
  discoveryDoi: string;
  publication: {
    id: string; title: string; authors: string[]; publicationYear: number; doi: string;
    sourceUrl: string; discipline: string; studyArea: { name: string; sourceUrl: string };
    permissions: string; uncertainties: string[];
  };
  dataset: {
    id: string; title: string; role: GeographicRole; sourceUrl: string;
    provenance: string; permissions: string; limitations: string[];
    subject: string; excludedRoles: GeographicRole[];
  };
  files: {
    kind: 'shapefile-components'; sourceFiles: SourceFile[];
    sourcePrjPath: string; sourceCrsLabel: string; sourceCrsWktContains: string[];
    preparedPath: string; preparedSha256: string; preparedCrs: 'EPSG:4326';
    expectedFeatureCount: number; expectedBounds: [[number, number], [number, number]];
    expectedGeometryTypes: string[]; idProperty: string;
    expectedProperties: Record<string, string | number>;
  };
  sensitivity: { status: 'reviewed-public-plant-grid' | 'restricted' | 'unknown'; rationale: string; sourceUrl: string };
  evidence: Evidence[];
};

export type ShapefileIntakeInputs = {
  discoveryRecord: unknown;
  sourceFiles: Record<string, { sha256: string; md5: string }>;
  sourcePrjText: string;
  preparedSha256: string;
  preparedGeoJson: unknown;
};

export type ShapefileIntakeCandidate = {
  schemaVersion: 'terrain-lab-intake-candidate/v2';
  reviewStatus: 'pending-human-review';
  publicationStatus: 'not-published-by-intake';
  machineChecksPassed: boolean;
  proposedStudy: StudyMetadata | null;
  geographicEvidence: {
    sourceFiles: SourceFile[]; sourceCrs: string; preparedPath: string; preparedSha256: string;
    preparedCrs: string; featureCount: number | null;
    bounds: [[number, number], [number, number]] | null; geometryTypes: string[];
    subject: string; excludedRoles: GeographicRole[];
    sensitivity: ShapefileIntakeManifest['sensitivity'];
  } | null;
  evidence: Evidence[];
  issues: Issue[];
};

const requiredEvidence = [
  'publication.bibliography', 'publication.studyArea', 'publication.permissions',
  'dataset.association', 'dataset.role', 'dataset.permissions', 'dataset.temporalCoverage',
  'dataset.sourceCrs', 'dataset.preparedCrs', 'dataset.extent', 'dataset.sensitivity',
];
const roles: GeographicRole[] = ['study-footprint', 'observed-geography', 'derived-output', 'model-prediction'];
const isObject = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const isUrl = (value: unknown): boolean => {
  if (typeof value !== 'string') return false;
  try { return ['http:', 'https:'].includes(new URL(value).protocol); } catch { return false; }
};
const isHash = (value: unknown, size: number): boolean => typeof value === 'string' && new RegExp(`^[a-f0-9]{${size}}$`, 'i').test(value);
const titleKey = (value: string): string => value.trim().replace(/[.\s]+$/g, '').replace(/\s+/g, ' ').toLowerCase();
const sameBounds = (a: [[number, number], [number, number]], b: [[number, number], [number, number]]): boolean =>
  Array.isArray(b) && b.length === 2 && b.every((pair, i) => Array.isArray(pair) && pair.length === 2 && pair.every((v, j) => Number.isFinite(v) && Math.abs(v - a[i][j]) < 1e-6));

export function buildShapefileIntakeCandidate(raw: unknown, inputs: ShapefileIntakeInputs): ShapefileIntakeCandidate {
  const issues: Issue[] = [];
  const error = (code: string, message: string): void => { issues.push({ code, message, severity: 'error' }); };
  const empty: ShapefileIntakeCandidate = {
    schemaVersion: 'terrain-lab-intake-candidate/v2', reviewStatus: 'pending-human-review',
    publicationStatus: 'not-published-by-intake', machineChecksPassed: false,
    proposedStudy: null, geographicEvidence: null, evidence: [], issues,
  };
  if (!isObject(raw) || raw.schemaVersion !== 'terrain-lab-intake-source/v2' ||
      !isObject(raw.publication) || !isObject(raw.dataset) || !isObject(raw.files) ||
      !isObject(raw.sensitivity) || !Array.isArray(raw.evidence)) {
    error('INVALID_MANIFEST', 'A v2 publication, dataset, files, sensitivity, and evidence are required.');
    return empty;
  }
  const manifest = raw as ShapefileIntakeManifest;
  const { publication, dataset, files, sensitivity } = manifest;
  const evidence = manifest.evidence.filter(item => isObject(item) && typeof item.field === 'string' &&
    isUrl(item.sourceUrl) && typeof item.note === 'string' && item.note.trim()) as Evidence[];
  if (evidence.length !== manifest.evidence.length) error('INVALID_EVIDENCE', 'Each source reference needs a field, URL, and note.');
  for (const field of requiredEvidence) if (!evidence.some(item => item.field === field)) error('MISSING_EVIDENCE', `No source reference for ${field}.`);
  if (![publication.sourceUrl, publication.studyArea?.sourceUrl, dataset.sourceUrl, sensitivity.sourceUrl].every(isUrl))
    error('INVALID_SOURCE_URL', 'Publication, study area, dataset, and sensitivity need source URLs.');
  const discovery = inputs.discoveryRecord;
  if (!isObject(discovery) || String(discovery.doi).toLowerCase() !== publication.doi?.toLowerCase() ||
      String(discovery.doi).toLowerCase() !== manifest.discoveryDoi?.toLowerCase() ||
      typeof discovery.title !== 'string' || typeof publication.title !== 'string' ||
      titleKey(discovery.title) !== titleKey(publication.title) ||
      Number(String(discovery.date).slice(0, 4)) !== publication.publicationYear)
    error('DISCOVERY_MISMATCH', 'DOI, title, or year differs from the discovery record.');
  if (!roles.includes(dataset.role) || dataset.role !== 'observed-geography' ||
      !Array.isArray(dataset.excludedRoles) ||
      new Set([dataset.role, ...dataset.excludedRoles]).size !== roles.length ||
      !roles.every(role => role === dataset.role || dataset.excludedRoles.includes(role)) ||
      typeof dataset.subject !== 'string' || !dataset.subject.trim())
    error('ROLE_CLASSIFICATION', 'The mapped presence cells must be observed geography with the other three roles excluded.');
  if (sensitivity.status !== 'reviewed-public-plant-grid' || !sensitivity.rationale?.trim())
    error('SENSITIVE_LOCATION_REVIEW', 'A documented public plant-grid sensitivity review is required.');
  if (files.kind !== 'shapefile-components' || !Array.isArray(files.sourceFiles) || files.sourceFiles.length < 4 ||
      !['.shp', '.shx', '.dbf', '.prj'].every(ext => files.sourceFiles.some(file => file.path.endsWith(ext))))
    error('SOURCE_FILES', 'A complete shapefile source must list .shp, .shx, .dbf, and .prj.');
  for (const file of files.sourceFiles ?? []) {
    const actual = inputs.sourceFiles[file.path];
    if (!isHash(file.sha256, 64) || !isHash(file.sourceMd5, 32) ||
        file.sha256.toLowerCase() !== actual?.sha256.toLowerCase() ||
        file.sourceMd5.toLowerCase() !== actual?.md5.toLowerCase())
      error('CHECKSUM_MISMATCH', `Original component checksum mismatch: ${file.path}.`);
  }
  if (!files.sourceFiles?.some(file => file.path === files.sourcePrjPath) ||
      !Array.isArray(files.sourceCrsWktContains) || !files.sourceCrsWktContains.length ||
      files.sourceCrsWktContains.some(token => !inputs.sourcePrjText.includes(token)) ||
      files.preparedCrs !== 'EPSG:4326')
    error('CRS_MISMATCH', 'The original .prj or prepared WGS84 declaration does not match the source manifest.');
  if (!isHash(files.preparedSha256, 64) || files.preparedSha256.toLowerCase() !== inputs.preparedSha256.toLowerCase())
    error('CHECKSUM_MISMATCH', 'Prepared GeoJSON checksum mismatch.');
  let inspection: ReturnType<typeof inspectGeoJson> | null = null;
  try { inspection = inspectGeoJson(inputs.preparedGeoJson); }
  catch (cause) { error('INVALID_GEOJSON', cause instanceof Error ? cause.message : 'Invalid GeoJSON.'); }
  if (inspection) {
    if (inspection.featureCount !== files.expectedFeatureCount || !inspection.bounds ||
        !sameBounds(inspection.bounds, files.expectedBounds) ||
        !Array.isArray(files.expectedGeometryTypes) ||
        inspection.kinds.some(kind => !files.expectedGeometryTypes.includes(kind)))
      error('GEOGRAPHIC_EXTENT', 'Feature count, geometry type, or WGS84 bounds differ from the manifest.');
    const ids = new Set<unknown>();
    for (const feature of inspection.data.features) {
      const properties = feature.properties as Record<string, unknown> | null;
      const id = properties?.[files.idProperty];
      if (id === undefined || ids.has(id) || feature.id !== id) {
        error('FEATURE_ID', 'A feature has a missing, duplicate, or inconsistent source ID.');
        break;
      }
      ids.add(id);
      if (properties?.terrainLabStudyId !== publication.id || properties?.terrainLabDatasetId !== dataset.id ||
          Object.entries(files.expectedProperties).some(([key, value]) => properties?.[key] !== value)) {
        error('FEATURE_PROVENANCE', 'A feature lacks the expected source attributes or study/dataset classification.');
        break;
      }
    }
  }
  const proposedStudy = {
    schemaVersion: 'terrain-lab-study/v1', id: publication.id, title: publication.title,
    authors: publication.authors, publicationYear: publication.publicationYear, doi: publication.doi,
    sourceUrl: publication.sourceUrl, discipline: publication.discipline,
    studyArea: publication.studyArea, provenanceUrl: dataset.sourceUrl,
    permissions: publication.permissions, uncertainties: publication.uncertainties,
    datasets: [{ id: dataset.id, title: dataset.title, role: dataset.role,
      availability: 'external', sourceUrl: dataset.sourceUrl, format: 'GeoJSON proposal',
      provenance: dataset.provenance, permissions: dataset.permissions,
      limitations: dataset.limitations }],
  } satisfies StudyMetadata;
  try { validateStudyMetadata(proposedStudy); }
  catch (cause) { error('STUDY_SCHEMA', cause instanceof Error ? cause.message : 'Invalid study metadata.'); }
  issues.push({ code: 'HUMAN_REVIEW_REQUIRED', message: 'A person must approve source meaning, sensitivity, and publication before promotion.', severity: 'review' });
  return {
    ...empty, proposedStudy, evidence, machineChecksPassed: !issues.some(item => item.severity === 'error'),
    geographicEvidence: {
      sourceFiles: files.sourceFiles, sourceCrs: files.sourceCrsLabel,
      preparedPath: files.preparedPath, preparedSha256: inputs.preparedSha256,
      preparedCrs: files.preparedCrs, featureCount: inspection?.featureCount ?? null,
      bounds: inspection?.bounds ?? null, geometryTypes: inspection?.kinds ?? [],
      subject: dataset.subject, excludedRoles: dataset.excludedRoles, sensitivity,
    },
  };
}

export function renderShapefileIntakeReview(candidate: ShapefileIntakeCandidate): string {
  const study = candidate.proposedStudy;
  const geo = candidate.geographicEvidence;
  return [
    `# Intake review: ${study?.title ?? 'invalid proposal'}`, '',
    `**Status:** ${candidate.reviewStatus}; ${candidate.publicationStatus}.`,
    `**Machine checks:** ${candidate.machineChecksPassed ? 'passed' : 'failed'}.`, '',
    '## Proposed study and geographic meaning', '',
    `- Article: ${study?.authors.join(', ') ?? 'unavailable'} (${study?.publicationYear ?? 'unknown'}), DOI ${study?.doi ?? 'unavailable'}.`,
    `- Study area: ${study?.studyArea?.name ?? 'unavailable'}; no footprint polygon is proposed.`,
    `- Dataset: ${study?.datasets[0]?.title ?? 'unavailable'}; **${study?.datasets[0]?.role ?? 'unavailable'}**.`,
    `- Subject: ${geo?.subject ?? 'unavailable'}.`,
    `- Excluded roles: ${geo?.excludedRoles.join(', ') ?? 'unavailable'}.`,
    `- Sensitivity: ${geo?.sensitivity.status ?? 'unavailable'} — ${geo?.sensitivity.rationale ?? 'unavailable'}`, '',
    '## Machine-checked files', '',
    ...(geo?.sourceFiles.map(file => `- Original: \`${file.path}\`; SHA-256 \`${file.sha256}\`; publisher MD5 \`${file.sourceMd5}\`.`) ?? []),
    `- Source CRS: ${geo?.sourceCrs ?? 'unavailable'}.`,
    `- Prepared WGS84 GeoJSON: \`${geo?.preparedPath ?? 'unavailable'}\`; SHA-256 \`${geo?.preparedSha256 ?? 'unavailable'}\`.`,
    `- Features: ${geo?.featureCount ?? 'unknown'}; ${geo?.geometryTypes.join(', ') ?? 'unavailable'}; bounds ${JSON.stringify(geo?.bounds ?? null)}.`, '',
    '## Evidence to review', '',
    '| Claim | Source | Note |', '| --- | --- | --- |',
    ...candidate.evidence.map(item => `| ${item.field} | ${item.sourceUrl} | ${item.note.replace(/\|/g, '\\|')} |`), '',
    '## Uncertainties and limits', '',
    ...(study?.uncertainties.map(item => `- ${item}`) ?? []),
    ...(study?.datasets[0]?.limitations.map(item => `- ${item}`) ?? []),
    ...candidate.issues.map(item => `- **${item.severity.toUpperCase()} ${item.code}:** ${item.message}`), '',
    '## Review decision', '',
    '- [ ] Check the article and later USGS release directly; establish what data version the article used.',
    '- [ ] Confirm the cell classification, source CRS, conversion, extent, license, and location sensitivity.',
    '- [ ] Approve or reject catalog registration and public map publication; record reviewer and date.', '',
    '**Decision:** Pending. This report is not publication approval.', '',
  ].join('\n');
}
