import {z} from 'zod';

export const visualEventTypes=['PHOTO_REVEAL','CUTOUT','HEADLINE','DOCUMENT_HIGHLIGHT','LABEL','ARROW','TIMELINE','MAP_ROUTE','STAT_BUILD','SIDE_BY_SIDE','CALENDAR_ADVANCE','QUOTE_REVEAL','HARD_CUT_BLACK','VISUAL_CALLBACK'] as const;
export const treatmentTypes=['FULL_FRAME','CUTOUT','DETAIL','SIDE_BY_SIDE','DOCUMENT','STAT_OVERLAY'] as const;
export const assetSchema=z.object({
  id:z.string().min(1),src:z.string().min(1),sourceUrl:z.string().url(),credit:z.string().min(1),date:z.string().min(1),
  depicts:z.array(z.string()).min(1),roles:z.array(z.enum(['CHARACTER','ACTION','EVIDENCE','DOCUMENT','LOCATION'])).min(1),
  treatments:z.array(z.enum(treatmentTypes)).min(1),storyMoments:z.array(z.string()).min(1),
  rightsStatus:z.enum(['LICENSED','NO_KNOWN_RESTRICTIONS','EDITORIAL_FAIR_USE']),maxFullFrameUses:z.number().int().nonnegative(),maxTotalUses:z.number().int().positive(),
});
const beatSchema=z.object({id:z.string().min(1),purpose:z.enum(['HOOK','QUESTION','ESCALATION','REVEAL','PAYOFF']),narration:z.string().min(1),audioSrc:z.string().min(1),durationSeconds:z.number().positive().max(6).optional(),assetIds:z.array(z.string()).default([]),value:z.string().optional(),label:z.string().optional(),captionStyle:z.enum(['STANDARD','KEYWORD','QUESTION','IMPACT']).default('STANDARD')});
export const phoneFastBlueprintSchema=z.object({
  schemaVersion:z.literal(2),id:z.string().min(1),title:z.string().min(1),openingQuestion:z.string().min(1),resolution:z.string().min(1),soundtrackSrc:z.string().min(1),fps:z.number().positive().default(30),
  pacing:z.object({profile:z.literal('PHONE_FAST'),targetEventSeconds:z.number().max(3),maxUnchangedSeconds:z.number().max(3.5),maxSentenceWords:z.number().int().max(16),maxRevealGapSeconds:z.number().max(15),microchapterSeconds:z.object({min:z.number().positive(),max:z.number().positive()})}),
  assets:z.array(assetSchema).min(1),
  microchapters:z.array(z.object({id:z.string().min(1),title:z.string().min(1),hook:z.string().min(1),question:z.string().min(1),escalation:z.array(z.string()).min(1),reveal:z.string().min(1),payoff:z.string().min(1),beats:z.array(beatSchema).min(5)})).min(1),
  retentionMap:z.array(z.object({atSeconds:z.number().nonnegative(),device:z.enum(['CONTRADICTION','OPEN_LOOP','ESCALATION','REVERSAL','PAYOFF']),text:z.string().min(1)})).min(2),
  music:z.array(z.object({atSeconds:z.number().nonnegative(),mode:z.enum(['TENSION','MOMENTUM','SILENCE','PAYOFF'])})).min(2),
});
export type PhoneFastBlueprint=z.infer<typeof phoneFastBlueprintSchema>;
export type PhoneAsset=z.infer<typeof assetSchema>;
export type VisualEventType=(typeof visualEventTypes)[number];
export type CompiledEvent={id:string;type:VisualEventType;startFrame:number;durationFrames:number;assetIds:string[];text:string;value?:string;label?:string;captionStyle:'STANDARD'|'KEYWORD'|'QUESTION'|'IMPACT';microchapterId:string;beatId:string};
export type CompiledPhoneFast={blueprint:PhoneFastBlueprint;events:CompiledEvent[];durationInFrames:number};
