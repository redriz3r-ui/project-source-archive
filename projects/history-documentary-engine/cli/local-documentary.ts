import {writeFile} from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';
import {productionBriefSchema,type ProductionBrief} from './brief';
import {type ResearchReport} from './research';
import {ollamaStructured} from '../src/presidential/local-director';

const visualTypes=['AUTO','ARCHIVE_PHOTO','KEN_BURNS','MAP','DOCUMENT_EXCERPT','QUOTE_CARD','STATISTIC','DATE_CARD','LABELED_CUTOUT','DIAGRAM','CHAPTER_CARD','ILLUSTRATION'] as const;
const localScriptSchema=z.object({
  script:z.array(z.object({
    id:z.string().min(1),
    narration:z.string().min(1),
    visual:z.enum(visualTypes),
    sourceIds:z.array(z.string().min(1)).min(1),
    claimIds:z.array(z.string().min(1)).min(1),
    archiveQuery:z.string().min(1),
  })).min(6).max(8),
});

const outputSchema={
  type:'object',additionalProperties:false,
  properties:{script:{type:'array',minItems:6,maxItems:8,items:{
    type:'object',additionalProperties:false,
    properties:{
      id:{type:'string'},narration:{type:'string'},visual:{type:'string',enum:visualTypes},
      sourceIds:{type:'array',minItems:1,items:{type:'string'}},
      claimIds:{type:'array',minItems:1,items:{type:'string'}},
      archiveQuery:{type:'string'},
    },required:['id','narration','visual','sourceIds','claimIds','archiveQuery'],
  }}},required:['script'],
};

const reviewSchema=z.object({
  action:z.enum(['APPROVE','REVISE']),
  issues:z.array(z.string()).max(4),
  script:localScriptSchema.shape.script,
});
const reviewOutputSchema={
  type:'object',additionalProperties:false,
  properties:{
    action:{type:'string',enum:['APPROVE','REVISE']},
    issues:{type:'array',maxItems:4,items:{type:'string'}},
    script:outputSchema.properties.script,
  },required:['action','issues','script'],
};

const wordCount=(text:string)=>text.trim().split(/\s+/).filter(Boolean).length;
export const validateLocalScript=(report:ResearchReport,value:unknown)=>{
  const result=localScriptSchema.parse(value),claims=new Map(report.claims.map(claim=>[claim.id,claim])),sources=new Set(report.sources.filter(source=>source.authority!=='DISCOVERY_ONLY').map(source=>source.id)),ids=new Set<string>();
  for(const [index,beat] of result.script.entries()){
    if(ids.has(beat.id))throw new Error(`Local script has duplicate beat id: ${beat.id}`);ids.add(beat.id);
    if(wordCount(beat.narration)<6||wordCount(beat.narration)>60)throw new Error(`Local script beat ${index+1} must contain 6-60 words`);
    const supportedSources=new Set<string>();
    for(const claimId of beat.claimIds){const claim=claims.get(claimId);if(!claim||claim.confidence==='LOW'||claim.conflictIds.length)throw new Error(`Local script cited unusable claim: ${claimId}`);for(const sourceId of claim.sourceIds)if(sources.has(sourceId))supportedSources.add(sourceId);}
    for(const sourceId of beat.sourceIds)if(!supportedSources.has(sourceId))throw new Error(`Local script source ${sourceId} does not support beat ${beat.id}`);
  }
  const total=wordCount(result.script.map(beat=>beat.narration).join(' '));
  if(total<100||total>280)throw new Error(`Local script total word count ${total} is outside 100-280`);
  return result.script;
};

export const createLocalBrief=async(report:ResearchReport,outputDir:string,model?:string):Promise<{brief:ProductionBrief;briefFile:string}>=>{
  const usableClaims=report.claims.filter(claim=>claim.confidence!=='LOW'&&!claim.conflictIds.length&&claim.sourceIds.some(id=>report.sources.some(source=>source.id===id&&source.authority!=='DISCOVERY_ONLY')));
  if(usableClaims.length<6)throw new Error(`Local director requires at least 6 supported claims; found ${usableClaims.length}`);
  const request={
    task:'GENERAL_HISTORY_DOCUMENTARY_SCRIPT',title:report.title,topic:report.topic,
    instructions:['Create a coherent six-to-eight beat historical documentary','Use only the supplied claims','Do not add facts, names, dates, numbers, quotations, causes, or conclusions absent from those claims','Every beat must cite the claim IDs and authoritative source IDs that support it','Prefer chronological order','Use respectful, non-sensational language for deaths or disasters','Archive queries must be short factual search phrases, not prose'],
    claims:usableClaims.map(({id,text,evidence,sourceIds,confidence})=>({id,text,evidence,sourceIds,confidence})),
    authoritativeSources:report.sources.filter(source=>source.authority!=='DISCOVERY_ONLY').map(({id,title,publisher,url})=>({id,title,publisher,url})),
  };
  let generated:Awaited<ReturnType<typeof ollamaStructured>>|undefined,script:ReturnType<typeof validateLocalScript>|undefined,lastError:unknown,currentRequest:unknown=request;
  for(let attempt=1;attempt<=3;attempt++){
    generated=await ollamaStructured(currentRequest,outputSchema,{model});
    try{script=validateLocalScript(report,generated.content);break;}catch(error){
      lastError=error;
      currentRequest={...request,correction:{attempt,validationError:error instanceof Error?error.message:String(error),previousOutput:generated.content,instruction:'Return the entire corrected JSON document. Preserve grounded IDs and fix every stated validation error.'}};
    }
  }
  if(!generated||!script)throw new Error(`Local director failed validation after 3 attempts: ${lastError instanceof Error?lastError.message:String(lastError)}`);
  const sourceIds=new Set(script.flatMap(beat=>beat.sourceIds));
  const brief=productionBriefSchema.parse({title:report.title,topic:report.topic,storyMode:'NARRATIVE',targetMinutes:2,sources:report.sources.filter(source=>sourceIds.has(source.id)).map(({authority:_authority,...source})=>source),script});
  const briefFile=path.join(outputDir,'production-brief.local.json');
  await writeFile(briefFile,`${JSON.stringify({...brief,localDirector:{provider:'ollama',model:generated.model,promptTokens:generated.promptTokens,outputTokens:generated.outputTokens,generatedAt:new Date().toISOString()}},null,2)}\n`);
  return {brief,briefFile};
};

export const createAgenticLocalBrief=async(report:ResearchReport,outputDir:string,model?:string):Promise<{brief:ProductionBrief;briefFile:string;logFile:string}>=>{
  const usableClaims=report.claims.filter(claim=>claim.confidence!=='LOW'&&!claim.conflictIds.length&&claim.sourceIds.some(id=>report.sources.some(source=>source.id===id&&source.authority!=='DISCOVERY_ONLY')));
  if(usableClaims.length<6)throw new Error(`Local agent requires at least 6 supported claims; found ${usableClaims.length}`);
  const sources=report.sources.filter(source=>source.authority!=='DISCOVERY_ONLY');
  const evidence={
    title:report.title,topic:report.topic,
    claims:usableClaims.map(({id,text,sourceIds,confidence})=>({id,text,sourceIds,confidence})),
    sources:sources.map(({id,title,publisher})=>({id,title,publisher})),
  };
  const constraints=['6-8 beats','100-280 total words','6-60 words per beat','use only supplied facts and IDs','cite supporting claim and source IDs on every beat','chronological, respectful, concise','short factual archive queries'];
  const log:{schemaVersion:number;provider:string;model:string;hardwareProfile:string;startedAt:string;steps:any[];totals:{promptTokens:number;outputTokens:number};status:string;finishedAt?:string}={schemaVersion:1,provider:'ollama',model:model??process.env.LOCAL_DIRECTOR_MODEL??'qwen3:4b',hardwareProfile:'4B model / 8 GB unified memory / 4096 context',startedAt:new Date().toISOString(),steps:[],totals:{promptTokens:0,outputTokens:0},status:'RUNNING'};
  let script:ReturnType<typeof validateLocalScript>|undefined,lastError='';
  for(let attempt=1;attempt<=2;attempt++){
    const request={agentRole:'DIRECTOR',tool:'SUBMIT_SCRIPT',evidence,constraints,correction:lastError||undefined};
    const result=await ollamaStructured(request,outputSchema,{model,numCtx:4096,numPredict:1200,temperature:.1,system:'You are the documentary director. Call the SUBMIT_SCRIPT tool by returning its exact JSON arguments. Work only from the compact evidence ledger. Do not expose reasoning.'});
    log.totals.promptTokens+=result.promptTokens;log.totals.outputTokens+=result.outputTokens;
    try{script=validateLocalScript(report,result.content);log.steps.push({step:log.steps.length+1,role:'DIRECTOR',tool:'SUBMIT_SCRIPT',attempt,status:'PASS',usage:{promptTokens:result.promptTokens,outputTokens:result.outputTokens},output:result.content});break;}
    catch(error){lastError=error instanceof Error?error.message:String(error);log.steps.push({step:log.steps.length+1,role:'DIRECTOR',tool:'SUBMIT_SCRIPT',attempt,status:'REJECTED',validationError:lastError,usage:{promptTokens:result.promptTokens,outputTokens:result.outputTokens}});}
  }
  if(!script)throw new Error(`Local agent director failed after 2 bounded attempts: ${lastError}`);
  const citedClaims=[...new Set(script.flatMap(beat=>beat.claimIds))].map(id=>usableClaims.find(claim=>claim.id===id)).filter(Boolean);
  const reviewRequest={agentRole:'CRITIC',tool:'REVIEW_SCRIPT',title:report.title,topic:report.topic,constraints,claims:citedClaims?.map(claim=>({id:claim!.id,text:claim!.text,sourceIds:claim!.sourceIds})),draft:{script},instructions:'Choose APPROVE when the draft is accurate, coherent, respectful, and constraint-compliant. Choose REVISE and return the full corrected script otherwise. Never add a fact absent from claims.'};
  const reviewed=await ollamaStructured(reviewRequest,reviewOutputSchema,{model,numCtx:4096,numPredict:1200,temperature:0,system:'You are an independent documentary fact and story critic. Return the REVIEW_SCRIPT tool arguments only. Check every sentence against supplied claims; silently approve or revise.'});
  log.totals.promptTokens+=reviewed.promptTokens;log.totals.outputTokens+=reviewed.outputTokens;
  const review=reviewSchema.parse(reviewed.content);
  script=validateLocalScript(report,{script:review.script});
  log.steps.push({step:log.steps.length+1,role:'CRITIC',tool:'REVIEW_SCRIPT',action:review.action,status:'PASS',issues:review.issues,usage:{promptTokens:reviewed.promptTokens,outputTokens:reviewed.outputTokens},output:{script:review.script}});
  const sourceIds=new Set(script.flatMap(beat=>beat.sourceIds));
  const brief=productionBriefSchema.parse({title:report.title,topic:report.topic,storyMode:'NARRATIVE',targetMinutes:2,sources:sources.filter(source=>sourceIds.has(source.id)).map(({authority:_authority,...source})=>source),script});
  log.status='COMPLETE';log.finishedAt=new Date().toISOString();
  const briefFile=path.join(outputDir,'production-brief.agent.json'),logFile=path.join(outputDir,'qwen-agent-log.json');
  await writeFile(briefFile,`${JSON.stringify({...brief,qwenAgent:{provider:'ollama',model:log.model,reviewAction:review.action,promptTokens:log.totals.promptTokens,outputTokens:log.totals.outputTokens,generatedAt:log.finishedAt}},null,2)}\n`);
  await writeFile(logFile,`${JSON.stringify(log,null,2)}\n`);
  return {brief,briefFile,logFile};
};
