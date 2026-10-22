export type TemporalCoverage = { startYear: number; endYear: number };
export type GeographicRole = 'study-footprint' | 'observed-geography' | 'derived-output' | 'model-prediction';
export type DatasetAvailability = 'local' | 'external' | 'not-recovered';

export type GeographicDataset = {
  id: string;
  title: string;
  role: GeographicRole;
  availability: DatasetAvailability;
  sourceUrl: string;
  format?: string;
  localPath?: string;
  temporalCoverage?: TemporalCoverage;
  provenance: string;
  permissions?: string;
  limitations: string[];
  derivedFrom?: string[];
};

export type StudyMetadata = {
  schemaVersion: 'terrain-lab-study/v1';
  id: string;
  title: string;
  authors: string[];
  publicationYear: number;
  doi?: string;
  sourceUrl?: string;
  discipline: string;
  studyArea?: { name: string; sourceUrl: string; footprintDatasetId?: string };
  temporalCoverage?: TemporalCoverage;
  provenanceUrl?: string;
  permissions?: string;
  datasets: GeographicDataset[];
  uncertainties: string[];
};

function record(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${path} must be an object.`);
  return value as Record<string, unknown>;
}

function keys(value: Record<string, unknown>, allowed: string[], path: string): void {
  const unknown = Object.keys(value).find(key => !allowed.includes(key));
  if (unknown) throw new Error(`${path}.${unknown} is not a study metadata field.`);
}

function text(value: unknown, path: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${path} must be a non-empty string.`);
  return value;
}

function url(value: unknown, path: string): void {
  const input = text(value, path);
  let parsed: URL;
  try { parsed = new URL(input); } catch { throw new Error(`${path} must be an HTTP(S) URL.`); }
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error(`${path} must be an HTTP(S) URL.`);
}

function strings(value: unknown, path: string, nonempty = false): void {
  if (!Array.isArray(value) || (nonempty && !value.length)) throw new Error(`${path} must be ${nonempty ? 'a non-empty' : 'an'} array.`);
  value.forEach((item, index) => text(item, `${path}[${index}]`));
}

function year(value: unknown, path: string): number {
  if (!Number.isInteger(value) || (value as number) < 1000 || (value as number) > 9999) throw new Error(`${path} must be a four-digit year.`);
  return value as number;
}

function coverage(value: unknown, path: string): void {
  const period = record(value, path);
  keys(period, ['startYear', 'endYear'], path);
  if (year(period.startYear, `${path}.startYear`) > year(period.endYear, `${path}.endYear`)) {
    throw new Error(`${path}.startYear must not follow endYear.`);
  }
}

export function validateStudyMetadata(value: unknown): asserts value is StudyMetadata {
  const study = record(value, 'study');
  keys(study, ['schemaVersion', 'id', 'title', 'authors', 'publicationYear', 'doi', 'sourceUrl', 'discipline',
    'studyArea', 'temporalCoverage', 'provenanceUrl', 'permissions', 'datasets', 'uncertainties'], 'study');
  if (study.schemaVersion !== 'terrain-lab-study/v1') throw new Error('study.schemaVersion must be terrain-lab-study/v1.');
  text(study.id, 'study.id');
  text(study.title, 'study.title');
  strings(study.authors, 'study.authors', true);
  year(study.publicationYear, 'study.publicationYear');
  if (study.doi === undefined && study.sourceUrl === undefined) throw new Error('study requires a DOI or source URL.');
  if (study.doi !== undefined && !/^10\.\d{4,9}\/\S+$/i.test(text(study.doi, 'study.doi'))) {
    throw new Error('study.doi must be a DOI such as 10.1000/example.');
  }
  if (study.sourceUrl !== undefined) url(study.sourceUrl, 'study.sourceUrl');
  text(study.discipline, 'study.discipline');
  if (study.temporalCoverage !== undefined) coverage(study.temporalCoverage, 'study.temporalCoverage');
  if (study.provenanceUrl !== undefined) text(study.provenanceUrl, 'study.provenanceUrl');
  if (study.permissions !== undefined) text(study.permissions, 'study.permissions');
  strings(study.uncertainties, 'study.uncertainties');

  let footprintId: string | undefined;
  if (study.studyArea !== undefined) {
    const area = record(study.studyArea, 'study.studyArea');
    keys(area, ['name', 'sourceUrl', 'footprintDatasetId'], 'study.studyArea');
    text(area.name, 'study.studyArea.name');
    url(area.sourceUrl, 'study.studyArea.sourceUrl');
    if (area.footprintDatasetId !== undefined) footprintId = text(area.footprintDatasetId, 'study.studyArea.footprintDatasetId');
  }

  if (!Array.isArray(study.datasets) || !study.datasets.length) throw new Error('study.datasets must be a non-empty array.');
  const ids = new Set<string>();
  for (const [index, raw] of study.datasets.entries()) {
    const path = `study.datasets[${index}]`;
    const dataset = record(raw, path);
    keys(dataset, ['id', 'title', 'role', 'availability', 'sourceUrl', 'format', 'localPath',
      'temporalCoverage', 'provenance', 'permissions', 'limitations', 'derivedFrom'], path);
    const id = text(dataset.id, `${path}.id`);
    if (ids.has(id)) throw new Error(`${path}.id duplicates ${id}.`);
    ids.add(id);
    text(dataset.title, `${path}.title`);
    if (!['study-footprint', 'observed-geography', 'derived-output', 'model-prediction'].includes(dataset.role as string)) {
      throw new Error(`${path}.role is invalid.`);
    }
    if (!['local', 'external', 'not-recovered'].includes(dataset.availability as string)) {
      throw new Error(`${path}.availability is invalid.`);
    }
    url(dataset.sourceUrl, `${path}.sourceUrl`);
    if (dataset.format !== undefined) text(dataset.format, `${path}.format`);
    if (dataset.availability === 'local') text(dataset.localPath, `${path}.localPath`);
    else if (dataset.localPath !== undefined) throw new Error(`${path}.localPath requires local availability.`);
    if (dataset.temporalCoverage !== undefined) coverage(dataset.temporalCoverage, `${path}.temporalCoverage`);
    text(dataset.provenance, `${path}.provenance`);
    if (dataset.permissions !== undefined) text(dataset.permissions, `${path}.permissions`);
    strings(dataset.limitations, `${path}.limitations`);
    if (dataset.derivedFrom !== undefined) strings(dataset.derivedFrom, `${path}.derivedFrom`, true);
    if (dataset.role === 'study-footprint' && (id !== footprintId || dataset.availability === 'not-recovered')) {
      throw new Error(`${path} must be referenced as an available study-area footprint.`);
    }
  }
  for (const [index, raw] of study.datasets.entries()) {
    const dataset = raw as GeographicDataset;
    for (const sourceId of dataset.derivedFrom ?? []) {
      if (!ids.has(sourceId) || sourceId === dataset.id) throw new Error(`study.datasets[${index}].derivedFrom references an invalid dataset.`);
    }
  }
  if (footprintId && !study.datasets.some((raw: GeographicDataset) => raw.id === footprintId && raw.role === 'study-footprint')) {
    throw new Error('study.studyArea.footprintDatasetId must reference a study-footprint dataset.');
  }
}
