import { inspectGeoJson } from '../sandbox/geojson.ts';
import { validateStudyMetadata, type GeographicRole, type StudyMetadata } from '../data/studyMetadata.ts';

export type IntakeIssue = { code: string; message: string; severity: 'error' | 'review' };
export type IntakeEvidence = { field: string; sourceUrl: string; note: string };
export type IntakeManifest = {
  schemaVersion: 'terrain-lab-intake-source/v1';
  discoveryDoi: string;
  publication: {
    id: string; title: string; authors: string[]; publicationYear: number; doi: string;
    sourceUrl: string; discipline: string; studyArea: { name: string; sourceUrl: string };
    permissions: string; uncertainties: string[];
  };
  dataset: {
    id: string; title: string; role: GeographicRole; sourceUrl: string;
    localPath: string; temporalCoverage: { startYear: number; endYear: number };
    provenance: string; permissions: string; limitations: string[];
    subject: string; excludedRoles: GeographicRole[];
  };
  files: {
    archivePath: string; archiveSha256: string; preparedPath: string; preparedSha256: string;
    nestedCrsMembers: string[]; sourcePrjSha256: string; sourceCrsLabel: string;
    preparedCrs: 'EPSG:4326'; expectedFeatureCount: number;
    expectedBounds: [[number, number], [number, number]];
  };
  sensitivity: { status: 'reviewed-public-infrastructure' | 'restricted' | 'unknown'; rationale: string; sourceUrl: string };
  evidence: IntakeEvidence[];
};

export type IntakeInputs = {
  discoveryRecord: unknown;
  archiveSha256: string;
  preparedSha256: string;
  sourcePrjSha256: string;
  sourcePrjText: string;
  preparedGeoJson: unknown;
};

export type IntakeCandidate = {
  schemaVersion: 'terrain-lab-intake-candidate/v1';
  reviewStatus: 'pending-human-review';
  publicationStatus: 'not-published-by-intake';
  machineChecksPassed: boolean;
  proposedStudy: StudyMetadata | null;
  geographicEvidence: {
    sourceArchive: { path: string; sha256: string; crs: string; prjSha256: string };
    preparedGeoJson: { path: string; sha256: string; crs: string; featureCount: number | null;
      bounds: [[number, number], [number, number]] | null; geometryTypes: string[];
      temporalCoverage: { startYear: number; endYear: number } | null };
    subject: string; excludedRoles: GeographicRole[];
    sensitivity: IntakeManifest['sensitivity'];
  } | null;
  evidence: IntakeEvidence[];
  issues: IntakeIssue[];
};

const requiredEvidence = [
  'publication.bibliography', 'publication.studyArea', 'publication.permissions',
  'dataset.association', 'dataset.role', 'dataset.permissions', 'dataset.temporalCoverage',
  'dataset.sourceCrs', 'dataset.preparedCrs', 'dataset.extent', 'dataset.sensitivity',
] as const;

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function url(value: unknown): boolean {
  if (typeof value !== 'string') return false;
  try { return ['http:', 'https:'].includes(new URL(value).protocol); } catch { return false; }
}
function hex(value: unknown): boolean { return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value); }
function issue(issues: IntakeIssue[], code: string, message: string, severity: IntakeIssue['severity'] = 'error'): void {
  issues.push({ code, message, severity });
}
function sameBounds(actual: [[number, number], [number, number]], expected: [[number, number], [number, number]]): boolean {
  return Array.isArray(expected) && expected.length === 2 && expected.every(pair => Array.isArray(pair) && pair.length === 2 && pair.every(Number.isFinite)) &&
    actual.every((pair, i) => pair.every((value, j) => Math.abs(value - expected[i][j]) <= 1e-6));
}
function normalizedTitle(value: string): string { return value.trim().replace(/[.\s]+$/g, '').replace(/\s+/g, ' ').toLowerCase(); }

export function buildIntakeCandidate(rawManifest: unknown, inputs: IntakeInputs): IntakeCandidate {
  const issues: IntakeIssue[] = [];
  const empty: IntakeCandidate = {
    schemaVersion: 'terrain-lab-intake-candidate/v1', reviewStatus: 'pending-human-review',
    publicationStatus: 'not-published-by-intake', machineChecksPassed: false, proposedStudy: null,
    geographicEvidence: null, evidence: [], issues,
  };
  if (!object(rawManifest) || rawManifest.schemaVersion !== 'terrain-lab-intake-source/v1' ||
      !object(rawManifest.publication) || !object(rawManifest.dataset) || !object(rawManifest.files) ||
      !object(rawManifest.sensitivity) || !Array.isArray(rawManifest.evidence)) {
    issue(issues, 'INVALID_MANIFEST', 'The intake source must have v1 publication, dataset, files, sensitivity, and evidence objects.');
    return empty;
  }
  const manifest = rawManifest as IntakeManifest;
  const { publication, dataset, files, sensitivity } = manifest;
  const evidence = manifest.evidence.filter(item => object(item) && typeof item.field === 'string' &&
    url(item.sourceUrl) && typeof item.note === 'string' && item.note.trim()) as IntakeEvidence[];
  if (evidence.length !== manifest.evidence.length) issue(issues, 'INVALID_EVIDENCE', 'Every evidence item needs a field, HTTP(S) source URL, and note.');
  for (const field of requiredEvidence) if (!evidence.some(item => item.field === field)) {
    issue(issues, 'MISSING_EVIDENCE', `No direct source reference for ${field}.`);
  }
  if (!url(publication.sourceUrl) || !url(publication.studyArea?.sourceUrl) || !url(dataset.sourceUrl) || !url(sensitivity.sourceUrl)) {
    issue(issues, 'INVALID_SOURCE_URL', 'Publication, study area, dataset, and sensitivity need HTTP(S) source URLs.');
  }
  if (!object(inputs.discoveryRecord) || String(inputs.discoveryRecord.doi).toLowerCase() !== publication.doi?.toLowerCase() ||
      String(inputs.discoveryRecord.doi).toLowerCase() !== manifest.discoveryDoi?.toLowerCase() ||
      typeof inputs.discoveryRecord.title !== 'string' || typeof publication.title !== 'string' ||
      normalizedTitle(inputs.discoveryRecord.title) !== normalizedTitle(publication.title) ||
      Number(String(inputs.discoveryRecord.date).slice(0, 4)) !== publication.publicationYear) {
    issue(issues, 'DISCOVERY_MISMATCH', 'The discovery candidate DOI, title, or year does not match the proposed publication.');
  }
  if (dataset.role !== 'observed-geography' || typeof dataset.subject !== 'string' || !dataset.subject.trim() ||
      !Array.isArray(dataset.excludedRoles) || new Set([dataset.role, ...dataset.excludedRoles]).size !== 4 ||
      dataset.excludedRoles.includes(dataset.role)) {
    issue(issues, 'ROLE_CLASSIFICATION', 'This USPVDB pilot must classify solar infrastructure as observed geography and exclude the other three roles.');
  }
  if (sensitivity.status !== 'reviewed-public-infrastructure' || !sensitivity.rationale?.trim()) {
    issue(issues, 'SENSITIVE_LOCATION_REVIEW', 'An explicit public-infrastructure sensitivity review is required before this example can pass.');
  }
  for (const [name, expected, actual] of [
    ['original archive', files.archiveSha256, inputs.archiveSha256],
    ['prepared GeoJSON', files.preparedSha256, inputs.preparedSha256],
    ['source .prj', files.sourcePrjSha256, inputs.sourcePrjSha256],
  ] as const) {
    if (!hex(expected) || expected.toLowerCase() !== actual.toLowerCase()) issue(issues, 'CHECKSUM_MISMATCH', `${name} checksum does not match its declared value.`);
  }
  if (!Array.isArray(files.nestedCrsMembers) || !files.nestedCrsMembers.length ||
      files.preparedCrs !== 'EPSG:4326' || !/Albers/i.test(inputs.sourcePrjText) ||
      !/North_American_1983/i.test(inputs.sourcePrjText) || !/Meter/i.test(inputs.sourcePrjText)) {
    issue(issues, 'CRS_MISMATCH', 'The source .prj must declare NAD83 Albers in meters and the prepared data must be documented as EPSG:4326.');
  }
  let inspection: ReturnType<typeof inspectGeoJson> | null = null;
  let measuredYears: { startYear: number; endYear: number } | null = null;
  try { inspection = inspectGeoJson(inputs.preparedGeoJson); }
  catch (error) { issue(issues, 'INVALID_GEOJSON', error instanceof Error ? error.message : 'Invalid GeoJSON.'); }
  if (inspection) {
    if (inspection.featureCount !== files.expectedFeatureCount || !inspection.bounds ||
        !sameBounds(inspection.bounds, files.expectedBounds) ||
        inspection.kinds.some(kind => !['Polygon', 'MultiPolygon'].includes(kind))) {
      issue(issues, 'GEOGRAPHIC_EXTENT', 'Prepared feature count, geometry types, or WGS84 extent differs from the source manifest.');
    }
    let firstYear = Infinity, lastYear = -Infinity;
    for (const feature of inspection.data.features) {
      const properties = feature.properties as Record<string, unknown> | null;
      const year = properties?.p_year;
      if (typeof year !== 'number' || !Number.isInteger(year)) {
        issue(issues, 'TEMPORAL_COVERAGE', 'A prepared feature lacks a numeric facility operation year.');
        break;
      }
      firstYear = Math.min(firstYear, year); lastYear = Math.max(lastYear, year);
      if (properties?.terrainLabStudyId !== publication.id || properties?.terrainLabDatasetId !== dataset.id ||
          properties?.terrainLabRole !== 'observed solar infrastructure; not tortoise observations') {
        issue(issues, 'FEATURE_PROVENANCE', 'A prepared feature lacks the expected study, dataset, or subject classification.');
        break;
      }
    }
    if (Number.isFinite(firstYear) && Number.isFinite(lastYear)) {
      measuredYears = { startYear: firstYear, endYear: lastYear };
      if (dataset.temporalCoverage?.startYear !== firstYear || dataset.temporalCoverage?.endYear !== lastYear) {
        issue(issues, 'TEMPORAL_COVERAGE', 'Dataset temporal coverage differs from prepared feature operation years.');
      }
    }
  }
  const proposedStudy = {
    schemaVersion: 'terrain-lab-study/v1', id: publication.id, title: publication.title,
    authors: publication.authors, publicationYear: publication.publicationYear,
    doi: publication.doi, sourceUrl: publication.sourceUrl, discipline: publication.discipline,
    studyArea: publication.studyArea, provenanceUrl: dataset.sourceUrl,
    permissions: publication.permissions, uncertainties: publication.uncertainties,
    datasets: [{ id: dataset.id, title: dataset.title, role: dataset.role, availability: 'local',
      sourceUrl: dataset.sourceUrl, format: 'GeoJSON', localPath: dataset.localPath,
      temporalCoverage: dataset.temporalCoverage, provenance: dataset.provenance,
      permissions: dataset.permissions, limitations: dataset.limitations }],
  } satisfies StudyMetadata;
  try { validateStudyMetadata(proposedStudy); }
  catch (error) { issue(issues, 'STUDY_SCHEMA', error instanceof Error ? error.message : 'Invalid study metadata.'); }
  issue(issues, 'HUMAN_REVIEW_REQUIRED', 'Source claims and geographic meaning require a human reviewer before catalog promotion.', 'review');
  return {
    ...empty, proposedStudy, evidence,
    machineChecksPassed: !issues.some(item => item.severity === 'error'),
    geographicEvidence: {
      sourceArchive: { path: files.archivePath, sha256: inputs.archiveSha256,
        crs: files.sourceCrsLabel, prjSha256: inputs.sourcePrjSha256 },
      preparedGeoJson: { path: files.preparedPath, sha256: inputs.preparedSha256,
        crs: files.preparedCrs, featureCount: inspection?.featureCount ?? null,
        bounds: inspection?.bounds ?? null, geometryTypes: inspection?.kinds ?? [],
        temporalCoverage: measuredYears },
      subject: dataset.subject, excludedRoles: dataset.excludedRoles, sensitivity,
    },
  };
}

export function renderIntakeReview(candidate: IntakeCandidate): string {
  const study = candidate.proposedStudy;
  const geo = candidate.geographicEvidence;
  const cell = (value: string): string => value.replace(/\|/g, '\\|').replace(/\s+/g, ' ').trim();
  return [
    `# Intake review: ${study?.title ?? 'invalid proposal'}`,
    '',
    `**Status:** ${candidate.reviewStatus}; ${candidate.publicationStatus}.`,
    `**Machine checks:** ${candidate.machineChecksPassed ? 'passed' : 'failed'}. Human review is required in either case.`,
    '',
    '## Proposed publication and geography',
    '',
    `- Publication: ${study?.authors.join(', ') ?? 'unavailable'} (${study?.publicationYear ?? 'unknown'}), DOI ${study?.doi ?? 'unavailable'}.`,
    `- Study area: ${study?.studyArea?.name ?? 'unavailable'}. No footprint polygon is proposed.`,
    `- Dataset: ${study?.datasets[0]?.title ?? 'unavailable'}; role **${study?.datasets[0]?.role ?? 'unavailable'}**.`,
    `- Dataset availability: ${study?.datasets[0]?.availability ?? 'unavailable'}; source ${study?.datasets[0]?.sourceUrl ?? 'unavailable'}.`,
    `- Excluded roles: ${geo?.excludedRoles.join(', ') ?? 'unavailable'}.`,
    `- Subject: ${geo?.subject ?? 'unavailable'}.`,
    `- Sensitivity review: ${geo?.sensitivity.status ?? 'unavailable'} — ${geo?.sensitivity.rationale ?? 'unavailable'}`,
    `- Article permissions: ${study?.permissions ?? 'unavailable'}`,
    `- Dataset permissions: ${study?.datasets[0]?.permissions ?? 'unavailable'}`,
    '',
    '## Machine-checked local files',
    '',
    `- Original archive: \`${geo?.sourceArchive.path ?? 'unavailable'}\`; SHA-256 \`${geo?.sourceArchive.sha256 ?? 'unavailable'}\`.`,
    `- Source CRS: ${geo?.sourceArchive.crs ?? 'unavailable'}; .prj SHA-256 \`${geo?.sourceArchive.prjSha256 ?? 'unavailable'}\`.`,
    `- Prepared data: \`${geo?.preparedGeoJson.path ?? 'unavailable'}\`; SHA-256 \`${geo?.preparedGeoJson.sha256 ?? 'unavailable'}\`.`,
    `- Prepared CRS and extent: ${geo?.preparedGeoJson.crs ?? 'unavailable'}; ${JSON.stringify(geo?.preparedGeoJson.bounds ?? null)}.`,
    `- Features and geometry: ${geo?.preparedGeoJson.featureCount ?? 'unknown'}; ${geo?.preparedGeoJson.geometryTypes.join(', ') ?? 'unavailable'}.`,
    `- Facility operation years: ${geo?.preparedGeoJson.temporalCoverage ? `${geo.preparedGeoJson.temporalCoverage.startYear}–${geo.preparedGeoJson.temporalCoverage.endYear}` : 'unavailable'}.`,
    '',
    '## Source references to review',
    '',
    '| Claim | Source | Why it was included |',
    '| --- | --- | --- |',
    ...candidate.evidence.map(item => `| ${cell(item.field)} | ${cell(item.sourceUrl)} | ${cell(item.note)} |`),
    '',
    '## Uncertainties and validation items',
    '',
    ...(study?.uncertainties.map(item => `- ${item}`) ?? ['- Proposal unavailable.']),
    ...(study?.datasets[0]?.limitations.map(item => `- Dataset limit: ${item}`) ?? []),
    ...candidate.issues.map(item => `- **${item.severity.toUpperCase()} ${item.code}:** ${item.message}`),
    '',
    '## Human approval checklist',
    '',
    '- [ ] Confirm the publication citation, study-area wording, and dataset association at the linked sources.',
    '- [ ] Confirm the pinned dataset version, reuse terms, attribution, and sensitive-location decision.',
    '- [ ] Confirm CRS, conversion, geographic extent, temporal meaning, and geographic-role classification.',
    '- [ ] Resolve uncertainties and errors; document reviewer, date, and decision in a separate promotion change.',
    '',
    '**Decision:** Pending. This report is not publication approval.',
    '',
  ].join('\n');
}
