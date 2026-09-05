import inventory from '../../public/projects/bombing-of-manila-wwii/04-assets/asset-inventory.json';
import narration from '../../public/projects/bombing-of-manila-wwii/06-render/narration-report.json';
import story from '../../public/projects/bombing-of-manila-wwii/02-story/microchapters.json';
import {phoneFastBlueprintSchema} from '../phone/schema';
import {manilaBeats} from './manilaScript';

if (inventory.assets.length < 16) throw new Error('Manila full episode requires at least 16 rights-cleared authentic assets');

const durationByBeat=new Map(narration.clips.map(clip=>[clip.beatId,clip.durationSeconds]));
const styles=['IMPACT','QUESTION','STANDARD','KEYWORD'] as const;
const values:Record<string,string>={
  'mc-01-b6':'≈100,000','mc-04-b1':'16–17,000','mc-08-b5':'7 DAYS','mc-09-b6':'600+ BLOCKS','mc-11-b1':'≈100,000',
};
const labels:Record<string,string>={
  'mc-01-b1':'FEBRUARY 3, 1945','mc-01-b3':'FEB 3 → MAR 3','mc-02-b4':'OPEN CITY','mc-03-b3':'ORDER: EVACUATE',
  'mc-03-b6':'IWABUCHI RESISTS','mc-05-b3':'FIRE SUPPORT RESTRICTED','mc-07-b4':'THE ARTILLERY DECISION',
  'mc-08-b2':'INTRAMUROS','mc-10-b6':'THE COLLECTIONS VANISH','mc-12-b1':'MARCH 3, 1945',
};

const assets=inventory.assets.map(asset=>({
  id:asset.id,src:asset.src,sourceUrl:asset.itemUrl,credit:asset.credit||'Wikimedia Commons / U.S. military archive',
  date:asset.date||'1945',depicts:asset.depicts.length?asset.depicts:[asset.title],roles:asset.roles,treatments:asset.treatments,
  storyMoments:story.chapters.map(chapter=>chapter.id),rightsStatus:asset.rightsStatus,maxFullFrameUses:8,maxTotalUses:24,
}));

const microchapters=story.chapters.map((chapter,chapterIndex)=>({
  id:chapter.id,title:chapter.title,hook:chapter.hook,question:chapter.question,escalation:chapter.escalation,reveal:chapter.reveal,payoff:chapter.payoff,
  beats:manilaBeats.filter(beat=>beat.chapterId===chapter.id).map((beat,beatIndex)=>{
    const globalIndex=manilaBeats.findIndex(candidate=>candidate.id===beat.id);
    return {id:beat.id,purpose:beat.purpose,narration:beat.text,audioSrc:`projects/bombing-of-manila-wwii/06-render/audio/${beat.id}.wav`,
      durationSeconds:durationByBeat.get(beat.id),assetIds:[assets[globalIndex%assets.length].id,assets[(globalIndex+5+chapterIndex)%assets.length].id],
      value:values[beat.id],label:labels[beat.id],captionStyle:styles[(beatIndex+chapterIndex)%styles.length]};
  }),
}));

const estimatedDuration=microchapters.flatMap(chapter=>chapter.beats).reduce((sum,beat)=>sum+Math.max(3.4,(beat.durationSeconds??3.4)+.18),0);
const devices=['CONTRADICTION','OPEN_LOOP','ESCALATION','REVERSAL','PAYOFF'] as const;
const retentionMap=Array.from({length:Math.floor(estimatedDuration/8)+1},(_,index)=>({
  atSeconds:index*8,device:devices[index%devices.length],text:microchapters[index%microchapters.length].title,
}));
const modes=['TENSION','MOMENTUM','SILENCE','PAYOFF'] as const;
const music=microchapters.map((chapter,index)=>({atSeconds:index*(estimatedDuration/microchapters.length),mode:modes[index%modes.length]}));

export const manilaFull=phoneFastBlueprintSchema.parse({
  schemaVersion:2,id:'the-month-manila-died',title:'The Month Manila Died',
  openingQuestion:'How did liberation leave Manila almost destroyed?',
  resolution:'Manila was liberated from occupation, but atrocities, demolition, urban combat, and American artillery devastated its people and physical memory.',
  soundtrackSrc:'projects/bombing-of-manila-wwii/06-render/score.wav',fps:30,
  pacing:{profile:'PHONE_FAST',targetEventSeconds:2.3,maxUnchangedSeconds:3,maxSentenceWords:14,maxRevealGapSeconds:10,microchapterSeconds:{min:30,max:50}},
  assets,microchapters,retentionMap,music,
});
