import {z} from 'zod';

export const productionBriefSchema = z.object({
  title: z.string().min(1),
  topic: z.string().min(1),
  storyMode: z.enum(['NARRATIVE', 'EXPLAINED']).default('NARRATIVE'),
  targetMinutes: z.number().positive().max(60).default(8),
  sources: z.array(z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    url: z.string().url(),
    publisher: z.string().optional(),
    accessedAt: z.string().optional(),
    rights: z.string().optional(),
  })).default([]),
  script: z.array(z.object({
    id: z.string().min(1),
    narration: z.string().min(1),
    chapter: z.string().optional(),
    visual: z.enum(['AUTO', 'ARCHIVE_PHOTO', 'KEN_BURNS', 'MAP', 'DOCUMENT_EXCERPT', 'QUOTE_CARD', 'STATISTIC', 'DATE_CARD', 'LABELED_CUTOUT', 'DIAGRAM', 'CHAPTER_CARD', 'ILLUSTRATION']).default('AUTO'),
    sourceIds: z.array(z.string()).min(1),
    claimIds: z.array(z.string()).default([]),
    asset: z.string().optional(),
    archiveQuery: z.string().optional(),
    credit: z.string().optional(),
    map: z.object({
      label: z.string(),
      year: z.string().optional(),
      region: z.string().optional(),
      points: z.array(z.object({name: z.string(), x: z.number().min(0).max(1), y: z.number().min(0).max(1)})).min(1),
      route: z.array(z.number()).optional(),
    }).optional(),
  })).min(1),
}).superRefine((brief, ctx) => {
  const known = new Set(brief.sources.map((source) => source.id));
  brief.script.forEach((beat, index) => beat.sourceIds.forEach((id) => {
    if (!known.has(id)) ctx.addIssue({code: 'custom', path: ['script', index, 'sourceIds'], message: `Unknown source id: ${id}`});
  }));
});

export type ProductionBrief = z.infer<typeof productionBriefSchema>;
