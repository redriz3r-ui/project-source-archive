import {z} from 'zod';

export const wikiParagraphSchema=z.object({id:z.string(),text:z.string().min(1),sentences:z.array(z.string().min(1)).min(1),wordCount:z.number().int().positive(),linkedTitles:z.array(z.string()).default([])});
export const wikiSectionSchema=z.object({id:z.string(),index:z.number().int().nonnegative(),level:z.number().int().min(1).max(6),title:z.string().min(1),anchor:z.string(),parentId:z.string().nullable(),paragraphs:z.array(wikiParagraphSchema),wordCount:z.number().int().nonnegative()});
export const wikiArticleSchema=z.object({
  schemaVersion:z.literal(1),source:z.literal('Wikipedia'),language:z.literal('en'),title:z.string().min(1),pageId:z.number().int().positive(),revisionId:z.number().int().positive(),
  canonicalUrl:z.string().url(),license:z.literal('CC BY-SA 4.0'),retrievedAt:z.string(),lead:z.array(wikiParagraphSchema).min(1),sections:z.array(wikiSectionSchema),
  images:z.array(z.object({filename:z.string().min(1)})),links:z.array(z.object({title:z.string().min(1),exists:z.boolean()})),
  totals:z.object({words:z.number().int().positive(),paragraphs:z.number().int().positive(),sections:z.number().int().nonnegative(),estimatedReadingMinutes:z.number().positive()}),contentHash:z.string().length(64),
});
export type WikiArticle=z.infer<typeof wikiArticleSchema>;

export const narrativeDirectorPacketSchema=z.object({
  schemaVersion:z.literal(1),task:z.literal('NARRATIVE_DIRECTOR'),article:z.object({title:z.string(),canonicalUrl:z.string().url(),revisionId:z.number().int(),license:z.string()}),
  objective:z.string(),constraints:z.array(z.string()),sectionOrder:z.array(z.object({sectionId:z.string(),title:z.string(),paragraphIds:z.array(z.string()),wordCount:z.number()})),
  evidence:z.array(z.object({paragraphId:z.string(),sectionId:z.string(),text:z.string()})),outputContract:z.object({format:z.literal('JSON'),schema:z.record(z.string(),z.unknown())}),
});

export const visualDirectorPacketSchema=z.object({
  schemaVersion:z.literal(1),task:z.literal('VISUAL_DIRECTOR'),status:z.literal('WAITING_FOR_APPROVED_NARRATIVE'),articleTitle:z.string(),
  objective:z.string(),constraints:z.array(z.string()),availableArticleImages:z.array(z.string()),requiredInputs:z.array(z.string()),
});
