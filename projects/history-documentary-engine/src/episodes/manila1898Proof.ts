import catalog from '../../public/wiki-tests/battle-of-manila-1898/rights-cleared-media-catalog.json';
import {phoneFastBlueprintSchema} from '../phone/schema';
const lines=[
 ['b01','HOOK','On August thirteenth, Spain and America fought for Manila.','op-01'],
 ['b02','HOOK','But the ending had already been arranged.','op-01'],
 ['b03','REVEAL','Their commanders had secretly planned a mock battle.','op-02'],
 ['b04','REVEAL','It would transfer Manila from Spain to the United States.','op-02'],
 ['b05','QUESTION','But one army was deliberately excluded.','op-03'],
 ['b06','ESCALATION','Filipino revolutionaries had already seized most of the islands.','op-03'],
 ['b07','ESCALATION','Around forty thousand fighters under Aguinaldo surrounded the capital.','op-03'],
 ['b08','ESCALATION','Spain feared surrendering Manila directly to them.','op-04'],
 ['b09','REVEAL','So Spanish and American officers designed an American victory.','op-04'],
 ['b10','ESCALATION','The staged attack would look real, then end quickly.','op-04'],
 ['b11','REVEAL','The night before, America delivered the crucial order.','op-05'],
 ['b12','REVEAL',"Aguinaldo's troops were not to enter Manila.",'op-05'],
 ['b13','ESCALATION','The Filipino forces advanced anyway.','op-06'],
 ['b14','ESCALATION','They believed the assault was genuine.','op-06'],
 ['b15','PAYOFF','By evening, America controlled the city.','op-07'],
 ['b16','PAYOFF','The Filipinos remained outside—and their alliance began collapsing.','op-07'],
] as const;
const assets=catalog.assets.filter(asset=>!['asset-008','asset-009','asset-011'].includes(asset.id)).map(asset=>({id:asset.id,src:asset.src,sourceUrl:asset.itemUrl,credit:asset.credit||'Wikimedia Commons',date:asset.date||'1898',depicts:[asset.title],roles:['CHARACTER','ACTION','EVIDENCE'] as const,treatments:['FULL_FRAME','DETAIL','SIDE_BY_SIDE','STAT_OVERLAY'] as const,storyMoments:['proof'],rightsStatus:asset.rightsStatus,maxFullFrameUses:4,maxTotalUses:12}));
const forVisual=(visual:string)=>catalog.assets.filter(asset=>asset.beatIds.includes(visual)&&assets.some(approved=>approved.id===asset.id));
const labels:Record<string,string>={b01:'MANILA · AUGUST 13, 1898',b03:'THE MOCK BATTLE',b07:'≈40,000 FILIPINO FIGHTERS',b11:'THE EXCLUSION ORDER',b15:'MANILA CHANGES HANDS'};
const styles=['IMPACT','STANDARD','KEYWORD','QUESTION'] as const;
export const manila1898Proof=phoneFastBlueprintSchema.parse({schemaVersion:2,id:'manila-1898-wikipedia-proof',title:'Locked Out of Their Own Victory',openingQuestion:'How were Filipino revolutionaries excluded from Manila’s surrender?',resolution:'America took Manila through a staged surrender while Filipino forces remained outside, beginning the collapse of their wartime alliance.',soundtrackSrc:'projects/episode-2/audio/score.wav',fps:30,pacing:{profile:'PHONE_FAST',targetEventSeconds:2.3,maxUnchangedSeconds:3,maxSentenceWords:14,maxRevealGapSeconds:10,microchapterSeconds:{min:48,max:78}},assets,microchapters:[{id:'proof',title:'The Victory They Could Not Enter',hook:'The battle’s ending was arranged.',question:'Who was excluded?',escalation:['Filipino forces surrounded Manila.','America ordered them outside.'],reveal:'The battle transferred Manila to America.',payoff:'The alliance began collapsing.',beats:lines.map(([id,purpose,narration,visual],index)=>{const matches=forVisual(visual);return {id,purpose,narration,audioSrc:`wiki-tests/battle-of-manila-1898/audio/${id}.wav`,assetIds:[matches[index%matches.length]?.id??assets[index%assets.length].id,matches[(index+1)%matches.length]?.id??assets[(index+3)%assets.length].id],value:id==='b07'?'≈40,000':undefined,label:labels[id],captionStyle:styles[index%styles.length]};})}],retentionMap:[{atSeconds:0,device:'CONTRADICTION',text:'The ending was arranged'},{atSeconds:8,device:'OPEN_LOOP',text:'One army was excluded'},{atSeconds:16,device:'ESCALATION',text:'Filipinos surrounded Manila'},{atSeconds:24,device:'REVERSAL',text:'Spain feared surrendering to them'},{atSeconds:32,device:'REVERSAL',text:'America delivered the order'},{atSeconds:40,device:'ESCALATION',text:'They advanced anyway'},{atSeconds:48,device:'PAYOFF',text:'America took the city'}],music:[{atSeconds:0,mode:'TENSION'},{atSeconds:16,mode:'MOMENTUM'},{atSeconds:31,mode:'SILENCE'},{atSeconds:38,mode:'MOMENTUM'},{atSeconds:48,mode:'PAYOFF'}]});
