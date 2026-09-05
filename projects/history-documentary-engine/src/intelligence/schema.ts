import {z} from 'zod';

const id=z.string().min(1);
export const sourceRecordSchema=z.object({schemaVersion:z.literal(1),id,title:z.string().min(1),url:z.string().url(),publisher:z.string().min(1),sourceType:z.enum(['PRIMARY','AUTHORITATIVE_SECONDARY','SECONDARY']),contentHash:z.string().min(8),reliabilityScore:z.number().min(0).max(100)});
export const evidencePassageSchema=z.object({schemaVersion:z.literal(1),id,sourceId:id,text:z.string().min(1),locator:z.string().min(1),questionIds:z.array(id),invalidated:z.boolean().default(false)});
export const claimRecordSchema=z.object({schemaVersion:z.literal(1),id,statement:z.string().min(1),evidencePassageIds:z.array(id).min(1),confidence:z.enum(['HIGH','MEDIUM','LOW']),status:z.enum(['APPROVED','REVIEW_REQUIRED','INVALIDATED'])});
export const decisionRecordSchema=z.object({schemaVersion:z.literal(1),id,kind:z.enum(['ANGLE','THESIS','TONE','AUDIENCE','REVISION']),value:z.string().min(1),createdAt:z.string().datetime()});
export const briefBudgetSchema=z.object({maxCharacters:z.number().int().positive(),maxClaims:z.number().int().positive(),maxPassages:z.number().int().positive()});
export const contextBriefSchema=z.object({schemaVersion:z.literal(1),id,taskType:z.string().min(1),query:z.string().min(1),budget:briefBudgetSchema,claimIds:z.array(id),passageIds:z.array(id),decisionIds:z.array(id),text:z.string(),inputHash:z.string().min(8)});
export const retrievalReceiptSchema=z.object({schemaVersion:z.literal(1),id,briefId:id,query:z.string(),retriever:z.object({id:z.string(),version:z.string(),configHash:z.string()}),corpusHash:z.string(),claimIds:z.array(id),passageIds:z.array(id),characterCount:z.number().int().nonnegative(),createdAt:z.string().datetime()});
export const modelRunReceiptSchema=z.object({schemaVersion:z.literal(1),id,taskType:z.string(),briefId:id,inputHash:z.string(),outputHash:z.string(),model:z.string(),status:z.enum(['EXECUTED','CACHED']),usage:z.object({inputTokens:z.number().int().nonnegative(),outputTokens:z.number().int().nonnegative(),elapsedMs:z.number().nonnegative()}),createdAt:z.string().datetime()});
export const dependencyRecordSchema=z.object({schemaVersion:z.literal(1),artifactId:id,dependsOn:z.array(id),status:z.enum(['VALID','STALE','BLOCKED']),reason:z.string().optional()});
export const cacheRecordSchema=z.object({schemaVersion:z.literal(1),key:z.string(),inputHash:z.string(),outputHash:z.string(),artifactId:id,createdAt:z.string().datetime()});
export const patchOperationSchema=z.object({op:z.enum(['add','replace','remove']),path:z.string().startsWith('/'),value:z.unknown().optional()});
export const patchRequestSchema=z.object({schemaVersion:z.literal(1),targetId:id,allowedPaths:z.array(z.string().startsWith('/')).min(1),protectedPaths:z.array(z.string().startsWith('/')).default([]),operations:z.array(patchOperationSchema).min(1)});

export type SourceRecord=z.infer<typeof sourceRecordSchema>;
export type EvidencePassage=z.infer<typeof evidencePassageSchema>;
export type ClaimRecord=z.infer<typeof claimRecordSchema>;
export type DecisionRecord=z.infer<typeof decisionRecordSchema>;
export type ContextBrief=z.infer<typeof contextBriefSchema>;
export type RetrievalReceipt=z.infer<typeof retrievalReceiptSchema>;
export type DependencyRecord=z.infer<typeof dependencyRecordSchema>;
export type CacheRecord=z.infer<typeof cacheRecordSchema>;
export type PatchRequest=z.infer<typeof patchRequestSchema>;

