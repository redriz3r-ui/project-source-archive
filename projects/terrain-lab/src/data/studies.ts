import { dutcherStudy } from './dutcherStudy.ts';
import { nussearStudy } from './nussearStudy.ts';
import { fleckensteinStudy } from './fleckensteinStudy.ts';
import { esqueStudy } from './esqueStudy.ts';
import { validateStudyMetadata, type StudyMetadata } from './studyMetadata.ts';

export const studies: readonly StudyMetadata[] = [dutcherStudy, nussearStudy, fleckensteinStudy, esqueStudy];

const ids = new Set<string>();
for (const study of studies) {
  validateStudyMetadata(study);
  if (ids.has(study.id)) throw new Error(`Duplicate study id: ${study.id}`);
  ids.add(study.id);
}

export { dutcherStudy };
