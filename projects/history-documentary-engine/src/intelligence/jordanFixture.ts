import {contentHash,type BriefInput} from './engine';
import type {ClaimRecord,DecisionRecord,EvidencePassage,SourceRecord} from './schema';
import {jordanPhoneProof} from '../phone/jordanProof';

const source=(id:string,title:string,url:string,type:'PRIMARY'|'AUTHORITATIVE_SECONDARY'|'SECONDARY',score:number):SourceRecord=>({schemaVersion:1,id,title,url,publisher:new URL(url).hostname,sourceType:type,contentHash:contentHash({id,title,url}),reliabilityScore:score});
export const jordanSources:SourceRecord[]=[
  source('src-milb','Michael Jordan’s Minor League Career','https://www.mlb.com/milb/history/michael-jordan','AUTHORITATIVE_SECONDARY',92),
  source('src-si','Michael Jordan, Ballplayer','https://www.si.com/nba/2014/02/07/michael-jordan-ballplayer','SECONDARY',82),
  source('src-ajc','Michael Jordan Baseball Debut','https://www.ajc.com/sports/photos-michael-jordan-made-baseball-debut-years-ago/TqBppjW4KA6gjlKJ0J6BZK/','SECONDARY',78),
  source('src-fax','Michael Jordan I’m Back Fax','https://www.businessinsider.com/michael-jordan-im-back-fax-2015-3','SECONDARY',76),
];
const passage=(id:string,sourceId:string,text:string,questions:string[],invalidated=false):EvidencePassage=>({schemaVersion:1,id,sourceId,text,locator:`fixture:${id}`,questionIds:questions,invalidated});
export const jordanPassages:EvidencePassage[]=[
  passage('ev-age','src-milb','Michael Jordan was 31 years old during his 1994 season with the Birmingham Barons.',['difficulty','baseball']),
  passage('ev-years','src-si','Jordan had not played organized baseball since high school, approximately seventeen years earlier.',['difficulty']),
  passage('ev-debut','src-ajc','The Barons debut drew 10,359 fans and approximately 130 members of the press.',['pressure','debut']),
  passage('ev-hit','src-milb','After beginning hitless, Jordan recorded his first hit and followed it with a thirteen-game hitting streak.',['turning-point','streak']),
  passage('ev-average','src-milb','Jordan finished the Double-A season with a .202 batting average.',['results']),
  passage('ev-strike','src-si','The 1994 baseball strike interrupted the next stage of Jordan’s baseball development.',['ending']),
  passage('ev-return','src-fax','Jordan announced his return to basketball in March 1995 with the words “I’m back.”',['return','payoff']),
  passage('ev-noise','src-si','The national attention surrounding Jordan followed the team through its minor-league schedule.',['pressure']),
];
const claim=(id:string,statement:string,evidencePassageIds:string[],status:'APPROVED'|'REVIEW_REQUIRED'|'INVALIDATED'='APPROVED'):ClaimRecord=>({schemaVersion:1,id,statement,evidencePassageIds,confidence:status==='APPROVED'?'HIGH':'LOW',status});
export const jordanClaims:ClaimRecord[]=[
  claim('cl-age','Jordan was 31 during the 1994 Barons season.',['ev-age']),claim('cl-years','He had been away from organized baseball for about seventeen years.',['ev-years']),claim('cl-debut','His Barons debut drew 10,359 fans and about 130 reporters.',['ev-debut']),claim('cl-streak','His first hit began a thirteen-game hitting streak.',['ev-hit']),claim('cl-average','He finished the Double-A season batting .202.',['ev-average']),claim('cl-strike','The 1994 strike interrupted his baseball path.',['ev-strike']),claim('cl-return','He announced his basketball return with “I’m back.”',['ev-return']),claim('cl-rumor','A rumor definitively explains the retirement.',['ev-noise'],'INVALIDATED'),
];
export const jordanDecisions:DecisionRecord[]=[{schemaVersion:1,id:'decision-angle',kind:'ANGLE',value:'The greatest player becomes a rookie',createdAt:'2026-08-26T00:00:00.000Z'},{schemaVersion:1,id:'decision-tone',kind:'TONE',value:'PHONE_FAST; curious, tense, unsentimental',createdAt:'2026-08-26T00:00:00.000Z'}];
export const jordanBriefInput:BriefInput={id:'brief-jordan-streak',taskType:'WRITE_NARRATION_BEAT',query:'Jordan first hit thirteen game streak after early failure',budget:{maxCharacters:900,maxClaims:3,maxPassages:3},sources:jordanSources,passages:jordanPassages,claims:jordanClaims,decisions:jordanDecisions};
export const jordanLegacyBroadContext={task:'Rewrite the Jordan baseball microchapter',blueprint:jordanPhoneProof,sources:jordanSources,passages:jordanPassages,claims:jordanClaims,decisions:jordanDecisions,fullInstructions:'Review all research, all assets, the complete timeline, every narration beat, retention plan, music plan, and renderer settings before rewriting the single reveal beat.'};

