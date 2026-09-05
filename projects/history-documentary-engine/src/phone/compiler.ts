import {phoneFastBlueprintSchema,type CompiledEvent,type CompiledPhoneFast,type PhoneFastBlueprint,type VisualEventType} from './schema';
const words=(s:string)=>s.trim().split(/\s+/).length;
const eventTypes=(purpose:string,hasTwo:boolean,hasValue:boolean,index:number):VisualEventType[]=>{
  if(purpose==='HOOK')return ['PHOTO_REVEAL','LABEL'];
  if(purpose==='QUESTION')return ['HARD_CUT_BLACK',hasTwo?'SIDE_BY_SIDE':'PHOTO_REVEAL'];
  if(purpose==='REVEAL')return hasValue?['STAT_BUILD','DOCUMENT_HIGHLIGHT']:['HEADLINE','DOCUMENT_HIGHLIGHT'];
  if(purpose==='PAYOFF')return ['QUOTE_REVEAL','VISUAL_CALLBACK'];
  return hasTwo?['SIDE_BY_SIDE','ARROW']:[index%2?'CUTOUT':'PHOTO_REVEAL',index%3?'TIMELINE':'CALENDAR_ADVANCE'];
};
export const compilePhoneFast=(input:PhoneFastBlueprint):CompiledPhoneFast=>{
  const blueprint=phoneFastBlueprintSchema.parse(input);const fps=blueprint.fps;let cursor=0;const events:CompiledEvent[]=[];
  for(const chapter of blueprint.microchapters)for(const [index,beat] of chapter.beats.entries()){
    const types=eventTypes(beat.purpose,beat.assetIds.length>1,Boolean(beat.value),index);const beatSeconds=beat.durationSeconds?Math.max(3.4,beat.durationSeconds+.18):Math.max(3.4,Math.min(5.8,words(beat.narration)/2.8+.8));const frames=Math.round(beatSeconds*fps);const first=Math.floor(frames/2);
    types.forEach((type,eventIndex)=>{const assetIds=type==='HARD_CUT_BLACK'?[]:type==='SIDE_BY_SIDE'?beat.assetIds.slice(0,2):beat.assetIds.length?[beat.assetIds[eventIndex%beat.assetIds.length]]:[];events.push({id:`${beat.id}-${eventIndex+1}`,type,startFrame:cursor+(eventIndex?first:0),durationFrames:eventIndex?frames-first:first,assetIds,text:beat.narration,value:beat.value,label:beat.label,captionStyle:beat.captionStyle,microchapterId:chapter.id,beatId:beat.id});});cursor+=frames;
  }
  return {blueprint,events,durationInFrames:cursor};
};
