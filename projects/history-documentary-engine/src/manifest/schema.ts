import {z} from 'zod';

const baseScene = z.object({
  id: z.string().min(1),
  startFrame: z.number().int().nonnegative(),
  durationFrames: z.number().int().positive(),
  caption: z.string().optional(),
  narration: z.string().optional(),
  sourceIds: z.array(z.string()).default([]),
  claimIds: z.array(z.string()).default([]),
  reviewStatus: z.enum(['DRAFT', 'SOURCED', 'APPROVED']).default('DRAFT'),
  direction: z.object({
    passageId: z.string().min(1),
    shotIndex: z.number().int().nonnegative(),
    purpose: z.enum(['HOOK', 'ORIENT', 'EVIDENCE', 'EXPLAIN', 'EMPHASIS', 'TRANSITION', 'RESOLUTION']),
    motion: z.enum(['NONE', 'PUSH_IN', 'PULL_OUT', 'PAN_LEFT', 'PAN_RIGHT', 'FLOAT', 'REVEAL']),
    transition: z.enum(['CUT', 'DISSOLVE', 'WIPE', 'FLASH']).default('CUT'),
  }).optional(),
  audio: z.object({
    src: z.string().min(1),
    provider: z.string().min(1),
    voice: z.string().min(1),
    durationSeconds: z.number().positive(),
  }).optional(),
  captions: z.array(z.object({
    text: z.string().min(1),
    startFrame: z.number().int().nonnegative(),
    endFrame: z.number().int().positive(),
  }).refine((caption) => caption.endFrame > caption.startFrame, 'caption end must follow start')).optional(),
});

const imagePayload = z.object({
  src: z.string().min(1),
  archiveQuery: z.string().optional(),
  archiveItemUrl: z.string().url().optional(),
  rightsStatus: z.enum(['PLACEHOLDER', 'REVIEW_REQUIRED', 'NO_KNOWN_RESTRICTIONS', 'LICENSED', 'EDITORIAL_FAIR_USE']).optional(),
  alt: z.string().min(1),
  credit: z.string().optional(),
  focalPoint: z.object({x: z.number().min(0).max(1), y: z.number().min(0).max(1)}).optional(),
});

export const sceneSchema = z.discriminatedUnion('type', [
  baseScene.extend({
    type: z.literal('TITLE_CARD'),
    payload: z.object({title: z.string(), subtitle: z.string().optional(), eyebrow: z.string().optional(), backgroundSrc: z.string().optional(), backgroundAlt: z.string().optional(), backgroundCredit: z.string().optional()}),
  }),
  baseScene.extend({type: z.literal('ARCHIVE_PHOTO'), payload: imagePayload}),
  baseScene.extend({type: z.literal('DOCUMENT_EXCERPT'), payload: z.object({heading: z.string(), excerpt: z.string(), document: z.string().optional(), date: z.string().optional()})}),
  baseScene.extend({type: z.literal('QUOTE_CARD'), payload: z.object({quote: z.string(), attribution: z.string(), date: z.string().optional()})}),
  baseScene.extend({type: z.literal('STATISTIC'), payload: z.object({value: z.string(), label: z.string(), context: z.string().optional()})}),
  baseScene.extend({type: z.literal('DATE_CARD'), payload: z.object({date: z.string(), headline: z.string(), context: z.string().optional()})}),
  baseScene.extend({type: z.literal('CHAPTER_CARD'), payload: z.object({index: z.number().int().positive(), title: z.string(), kicker: z.string().optional()})}),
  baseScene.extend({type: z.literal('LABELED_CUTOUT'), payload: imagePayload.extend({label: z.string(), detail: z.string().optional()})}),
  baseScene.extend({type: z.literal('ILLUSTRATION'), payload: imagePayload.extend({prompt: z.string(), provider: z.string().default('mock-svg')})}),
  baseScene.extend({type: z.literal('DIAGRAM'), payload: z.object({title: z.string(), nodes: z.array(z.object({label: z.string(), detail: z.string().optional()})).min(2), relation: z.string().optional()})}),
  baseScene.extend({
    type: z.literal('KEN_BURNS'),
    payload: imagePayload.extend({zoomFrom: z.number().positive().default(1), zoomTo: z.number().positive().default(1.12), panX: z.number().default(0), panY: z.number().default(0)}),
  }),
  baseScene.extend({
    type: z.literal('MAP'),
    payload: z.object({
      label: z.string(),
      year: z.string().optional(),
      region: z.string().optional(),
      renderer: z.enum(['offline-svg', 'maplibre']).default('offline-svg'),
      attribution: z.string().optional(),
      geojson: z.any().optional(),
      camera: z.object({
        from: z.tuple([z.number(), z.number(), z.number().positive()]),
        to: z.tuple([z.number(), z.number(), z.number().positive()]),
      }).optional(),
      points: z.array(z.object({name: z.string(), x: z.number().min(0).max(1), y: z.number().min(0).max(1)})).min(1),
      route: z.array(z.number().min(0).max(1)).refine((v) => v.length >= 4 && v.length % 2 === 0, 'route must contain x/y pairs').optional(),
    }),
  }),
]);

export const documentaryManifestSchema = z.object({
  schemaVersion: z.literal(1),
  id: z.string().min(1),
  title: z.string().min(1),
  topic: z.string().min(1),
  format: z.object({width: z.number().int().positive(), height: z.number().int().positive(), fps: z.number().positive()}),
  theme: z.object({ink: z.string(), paper: z.string(), accent: z.string()}),
  storyMode: z.enum(['NARRATIVE', 'EXPLAINED']).default('NARRATIVE'),
  soundtrack: z.object({src: z.string().min(1), provider: z.string().min(1), title: z.string().min(1), license: z.string().min(1), baseVolume: z.number().min(0).max(1), duckVolume: z.number().min(0).max(1)}).optional(),
  soundEffects: z.array(z.object({id: z.string().min(1), src: z.string().min(1), provider: z.string().min(1), license: z.string().min(1), startFrame: z.number().int().nonnegative(), volume: z.number().min(0).max(1)})).default([]),
  sources: z.array(z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    url: z.string().url(),
    publisher: z.string().optional(),
    accessedAt: z.string().optional(),
    rights: z.string().optional(),
  })).default([]),
  scenes: z.array(sceneSchema).min(1),
  adapters: z.object({archive: z.string(), map: z.string(), narration: z.string()}).optional(),
});

export type Scene = z.infer<typeof sceneSchema>;
export type DocumentaryManifest = z.infer<typeof documentaryManifestSchema>;

export const getDurationInFrames = (manifest: DocumentaryManifest) =>
  Math.max(...manifest.scenes.map((scene) => scene.startFrame + scene.durationFrames));

export const parseManifest = (input: unknown) => documentaryManifestSchema.parse(input);
