import {readFile,stat,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';
import {pathsFor} from './pipeline';
import {reconcileUsage,visualPlanSchema,writeNarrativeRequest,writeVisualRequest} from './production';

const narrativeSchema=z.object({
  schemaVersion:z.literal(1),
  beats:z.array(z.object({
    id:z.string().min(1),
    purpose:z.string().min(1),
    text:z.string().min(1),
    paragraphIds:z.array(z.string().min(1)).min(1),
  })).min(3).max(12),
});

type FetchLike=typeof fetch;
type OllamaOptions={model?:string;baseUrl?:string;fetchImpl?:FetchLike;numCtx?:number;numPredict?:number;temperature?:number;system?:string};
const exists=(file:string)=>stat(file).then(()=>true,()=>false);
const readJson=async(file:string)=>JSON.parse(await readFile(file,'utf8'));
const writeJson=(file:string,value:unknown)=>writeFile(file,`${JSON.stringify(value,null,2)}\n`);
const words=(value:string)=>value.trim().split(/\s+/).filter(Boolean).length;

const narrativeJsonSchema={
  type:'object',
  additionalProperties:false,
  properties:{
    schemaVersion:{type:'integer',const:1},
    beats:{type:'array',minItems:3,maxItems:12,items:{
      type:'object',additionalProperties:false,
      properties:{
        id:{type:'string'},purpose:{type:'string'},text:{type:'string'},
        paragraphIds:{type:'array',minItems:1,items:{type:'string'}},
      },
      required:['id','purpose','text','paragraphIds'],
    }},
  },
  required:['schemaVersion','beats'],
};

const visualJsonSchema={
  type:'object',
  additionalProperties:false,
  properties:{
    schemaVersion:{type:'integer',const:1},
    assets:{type:'array',minItems:1,items:{
      type:'object',additionalProperties:false,
      properties:{
        id:{type:'string'},filename:{type:'string'},
        alternates:{type:'array',maxItems:5,items:{type:'string'}},
        depiction:{type:'string'},date:{type:'string'},
        beatIds:{type:'array',minItems:1,items:{type:'string'}},
      },
      required:['id','filename','depiction','date','beatIds'],
    }},
  },
  required:['schemaVersion','assets'],
};

export const ollamaStructured=async(request:unknown,format:unknown,options:OllamaOptions={})=>{
  const model=options.model??process.env.LOCAL_DIRECTOR_MODEL??'qwen3:4b';
  const baseUrl=(options.baseUrl??process.env.OLLAMA_HOST??'http://127.0.0.1:11434').replace(/\/$/,'');
  const response=await (options.fetchImpl??fetch)(`${baseUrl}/api/chat`,{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({
      model,stream:false,think:false,keep_alive:0,format,
      options:{temperature:options.temperature??0,num_ctx:options.numCtx??4096,num_predict:options.numPredict??1400},
      messages:[
        {role:'system',content:options.system??'You are a careful documentary editor. Return only schema-valid JSON. Use only the supplied evidence and identifiers. Never invent facts, filenames, dates, or IDs.'},
        {role:'user',content:`Complete this production request. Obey every constraint. JSON schema is enforced.\n${JSON.stringify(request)}`},
      ],
    }),
    signal:AbortSignal.timeout(10*60*1000),
  });
  if(!response.ok)throw new Error(`Local director HTTP ${response.status}: ${(await response.text()).slice(0,300)}`);
  const envelope=await response.json() as any;
  if(!envelope?.message?.content)throw new Error('Local director returned no content');
  return {model,content:JSON.parse(envelope.message.content),promptTokens:Number(envelope.prompt_eval_count??0),outputTokens:Number(envelope.eval_count??0)};
};

const validateNarrative=(request:any,value:unknown)=>{
  const narrative=narrativeSchema.parse(value),allowed=new Set(request.evidence.map((item:any)=>item.id));
  const total=words(narrative.beats.map(beat=>beat.text).join(' '));
  if(total<request.constraints.minimumWords||total>request.constraints.maximumWords)throw new Error(`Local narrative word count ${total} is outside ${request.constraints.minimumWords}-${request.constraints.maximumWords}`);
  const ids=new Set<string>();
  for(const beat of narrative.beats){
    if(ids.has(beat.id))throw new Error(`Duplicate narrative beat id: ${beat.id}`);
    ids.add(beat.id);
    for(const paragraphId of beat.paragraphIds)if(!allowed.has(paragraphId))throw new Error(`Narrative cited unavailable paragraph: ${paragraphId}`);
  }
  return narrative;
};

const validateVisual=(request:any,value:unknown)=>{
  const plan=visualPlanSchema.parse(value),allowedFiles=new Set<string>(request.source.availableImages),beatIds=new Set<string>(request.beats.map((beat:any)=>beat.id)),coverage=new Map<string,number>(),reuse=new Map<string,number>();
  for(const asset of plan.assets){
    if(!allowedFiles.has(asset.filename))throw new Error(`Visual plan invented unavailable filename: ${asset.filename}`);
    for(const alternate of asset.alternates??[])if(!allowedFiles.has(alternate))throw new Error(`Visual plan invented unavailable alternate: ${alternate}`);
    for(const beatId of asset.beatIds){
      if(!beatIds.has(beatId))throw new Error(`Visual plan cited unavailable beat: ${beatId}`);
      coverage.set(beatId,(coverage.get(beatId)??0)+1);
      reuse.set(asset.id,(reuse.get(asset.id)??0)+1);
    }
  }
  for(const beatId of beatIds)if((coverage.get(beatId)??0)<request.constraints.minimumAssetsPerBeat)throw new Error(`Visual coverage below minimum for ${beatId}`);
  if(Math.max(0,...reuse.values())>request.constraints.maximumReuse)throw new Error('Visual plan exceeds maximum asset reuse');
  return plan;
};

export const runLocalDirector=async(engineRoot:string,slug:string,options:OllamaOptions={})=>{
  const project=pathsFor(engineRoot,slug).project,narrativeFile=path.join(project,'approved-narrative.json'),visualFile=path.join(project,'approved-visual-plan.json'),manifestFile=path.join(project,'president-manifest.json'),completed:string[]=[];
  if(await exists(manifestFile))return {episode:slug,stage:'local-director',status:'CACHED',provider:'ollama',model:options.model??process.env.LOCAL_DIRECTOR_MODEL??'qwen3:4b',completed};
  if(!await exists(narrativeFile)){
    const requestFile=path.join(project,'narrative-director-request.json');
    if(!await exists(requestFile))await writeNarrativeRequest(engineRoot,slug);
    const request=await readJson(requestFile),result=await ollamaStructured(request,narrativeJsonSchema,options),narrative=validateNarrative(request,result.content);
    await writeJson(narrativeFile,narrative);await reconcileUsage(engineRoot,slug,'narrative',narrative);completed.push('narrative');
  }
  if(!await exists(visualFile)){
    const requestFile=path.join(project,'visual-director-request.json');
    if(!await exists(requestFile))await writeVisualRequest(engineRoot,slug);
    const request=await readJson(requestFile),result=await ollamaStructured(request,visualJsonSchema,options),plan=validateVisual(request,result.content);
    await writeJson(visualFile,plan);await reconcileUsage(engineRoot,slug,'visual_search',plan);completed.push('visual_search');
  }
  return {episode:slug,stage:'local-director',status:'PASS',provider:'ollama',model:options.model??process.env.LOCAL_DIRECTOR_MODEL??'qwen3:4b',completed};
};
