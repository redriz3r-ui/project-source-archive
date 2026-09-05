import {z} from 'zod';

export const presidentAssetSchema=z.object({id:z.string(),src:z.string(),itemUrl:z.string().url(),credit:z.string(),rightsText:z.string(),depiction:z.string(),date:z.string(),source:z.string()});
export const presidentBeatSchema=z.object({id:z.string(),purpose:z.enum(['HOOK','RISE','INDEPENDENCE','ACHIEVEMENT','REVERSAL','ESCALATION','CONTROVERSY','FALL','RETURN','LEGACY_HANDOFF','ELECTION','CHALLENGE','POLICY','REFORMS','WAR','EXILE','DEATH_LEGACY','HANDOFF']),text:z.string().min(1),paragraphIds:z.array(z.string()).min(1),audioSrc:z.string(),durationSeconds:z.number().positive(),assetIds:z.array(z.string()).min(1),treatment:z.enum(['PUSH_IN','PAN_LEFT','PAN_RIGHT','PULL_OUT']).default('PUSH_IN')});
export const presidentSegmentSchema=z.object({schemaVersion:z.literal(1),articleRevisionId:z.number().int().positive(),cacheKey:z.string(),seriesTitle:z.string(),presidentNumber:z.number().int().positive(),presidentName:z.string(),term:z.string(),segmentTitle:z.string(),fps:z.number().int().positive(),soundtrackSrc:z.string(),assets:z.array(presidentAssetSchema),beats:z.array(presidentBeatSchema).min(1)});
export type PresidentSegment=z.infer<typeof presidentSegmentSchema>;
export const presidentDuration=(manifest:PresidentSegment)=>manifest.beats.reduce((sum,beat)=>sum+Math.ceil(beat.durationSeconds*manifest.fps),0);
