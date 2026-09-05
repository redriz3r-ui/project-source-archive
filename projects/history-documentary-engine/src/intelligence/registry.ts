import {cacheRecordSchema,claimRecordSchema,contextBriefSchema,decisionRecordSchema,dependencyRecordSchema,evidencePassageSchema,modelRunReceiptSchema,patchRequestSchema,retrievalReceiptSchema,sourceRecordSchema} from './schema';

export const intelligenceArtifactRegistry={
  'source-record-v1':sourceRecordSchema,
  'evidence-passage-v1':evidencePassageSchema,
  'claim-record-v1':claimRecordSchema,
  'decision-record-v1':decisionRecordSchema,
  'context-brief-v1':contextBriefSchema,
  'retrieval-receipt-v1':retrievalReceiptSchema,
  'model-run-receipt-v1':modelRunReceiptSchema,
  'dependency-record-v1':dependencyRecordSchema,
  'cache-record-v1':cacheRecordSchema,
  'restricted-patch-v1':patchRequestSchema,
} as const;

export const artifactRegistryDescriptor=Object.keys(intelligenceArtifactRegistry).sort().map(id=>({id,schemaVersion:1}));

