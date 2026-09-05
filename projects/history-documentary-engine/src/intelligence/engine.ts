import {createHash} from 'node:crypto';
import type {CacheRecord,ClaimRecord,ContextBrief,DecisionRecord,DependencyRecord,EvidencePassage,PatchRequest,RetrievalReceipt,SourceRecord} from './schema';
import {contextBriefSchema,patchRequestSchema,retrievalReceiptSchema} from './schema';

const canonical=(value:unknown):string=>{
  if(Array.isArray(value))return `[${value.map(canonical).join(',')}]`;
  if(value&&typeof value==='object')return `{${Object.entries(value as Record<string,unknown>).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${JSON.stringify(k)}:${canonical(v)}`).join(',')}}`;
  return JSON.stringify(value);
};
export const contentHash=(value:unknown)=>createHash('sha256').update(typeof value==='string'?value:canonical(value)).digest('hex');
const terms=(text:string)=>new Set(text.toLowerCase().match(/[a-z0-9]+/g)??[]);
const overlap=(query:Set<string>,text:string)=>[...terms(text)].filter(term=>query.has(term)).length;
const createdAt='2026-08-26T00:00:00.000Z';

export type BriefInput={id:string;taskType:string;query:string;budget:{maxCharacters:number;maxClaims:number;maxPassages:number};sources:SourceRecord[];passages:EvidencePassage[];claims:ClaimRecord[];decisions:DecisionRecord[]};
export const buildContextBrief=(input:BriefInput):{brief:ContextBrief;receipt:RetrievalReceipt}=>{
  const queryTerms=terms(input.query);
  const livePassages=input.passages.filter(p=>!p.invalidated).map(p=>({...p,score:overlap(queryTerms,p.text)})).filter(p=>p.score>0).sort((a,b)=>b.score-a.score||a.id.localeCompare(b.id));
  const liveIds=new Set(livePassages.map(p=>p.id));
  const rankedClaims=input.claims.filter(c=>c.status==='APPROVED'&&c.evidencePassageIds.some(id=>liveIds.has(id))).map(c=>({...c,score:overlap(queryTerms,c.statement)})).sort((a,b)=>b.score-a.score||a.id.localeCompare(b.id)).slice(0,input.budget.maxClaims);
  const lines=[...input.decisions].sort((a,b)=>a.id.localeCompare(b.id)).map(d=>`[${d.id}] ${d.kind}: ${d.value}`);const selectedClaims:typeof rankedClaims=[];const selectedPassages:typeof livePassages=[];
  for(const claim of rankedClaims){if(selectedClaims.length>=input.budget.maxClaims||selectedPassages.length>=input.budget.maxPassages)break;const passage=livePassages.find(p=>claim.evidencePassageIds.includes(p.id)&&!selectedPassages.some(selected=>selected.id===p.id));if(!passage)continue;const pair=[`[${claim.id}] ${claim.statement}`,`[${passage.id}] ${passage.text}`];if([...lines,...pair].join('\n').length>input.budget.maxCharacters)continue;selectedClaims.push(claim);selectedPassages.push(passage);lines.push(...pair);}
  const text=lines.join('\n');const passageIds=selectedPassages.map(p=>p.id);const validClaimIds=selectedClaims.map(c=>c.id);
  const base={schemaVersion:1 as const,id:input.id,taskType:input.taskType,query:input.query,budget:input.budget,claimIds:validClaimIds,passageIds,decisionIds:input.decisions.map(d=>d.id).sort(),text};
  const brief=contextBriefSchema.parse({...base,inputHash:contentHash(base)});
  const corpusHash=contentHash({sources:input.sources,passages:input.passages,claims:input.claims});
  const receipt=retrievalReceiptSchema.parse({schemaVersion:1,id:`receipt-${input.id}`,briefId:brief.id,query:brief.query,retriever:{id:'lexical-bounded',version:'1',configHash:contentHash(input.budget)},corpusHash,claimIds:brief.claimIds,passageIds:brief.passageIds,characterCount:brief.text.length,createdAt});
  return {brief,receipt};
};

export const validateClaimGrounding=(claimIds:string[],claims:ClaimRecord[],passages:EvidencePassage[])=>{
  const livePassages=new Set(passages.filter(p=>!p.invalidated).map(p=>p.id));const errors:string[]=[];
  for(const id of claimIds){const claim=claims.find(c=>c.id===id);if(!claim)errors.push(`Unknown claim: ${id}`);else if(claim.status!=='APPROVED')errors.push(`Claim is not approved: ${id}`);else if(!claim.evidencePassageIds.some(p=>livePassages.has(p)))errors.push(`Claim has no live evidence: ${id}`);}
  return {status:errors.length?'FAIL' as const:'PASS' as const,errors};
};

export const propagateInvalidation=(dependencies:DependencyRecord[],invalidatedIds:string[])=>{
  const stale=new Set(invalidatedIds);let changed=true;
  while(changed){changed=false;for(const record of dependencies)if(record.dependsOn.some(id=>stale.has(id))&&!stale.has(record.artifactId)){stale.add(record.artifactId);changed=true;}}
  return dependencies.map(record=>stale.has(record.artifactId)?{...record,status:'STALE' as const,reason:'Upstream artifact invalidated'}:record);
};

const decode=(part:string)=>part.replace(/~1/g,'/').replace(/~0/g,'~');
const pathAllowed=(path:string,allowed:string[])=>allowed.some(prefix=>path===prefix||path.startsWith(`${prefix}/`));
export const applyRestrictedPatch=<T extends object>(document:T,input:PatchRequest):T=>{
  const request=patchRequestSchema.parse(input);const clone=structuredClone(document) as Record<string,unknown>;
  for(const operation of request.operations){if(pathAllowed(operation.path,request.protectedPaths))throw new Error(`Patch path is protected: ${operation.path}`);if(!pathAllowed(operation.path,request.allowedPaths))throw new Error(`Patch path not allowed: ${operation.path}`);const parts=operation.path.split('/').slice(1).map(decode);if(!parts.length)throw new Error('Root patch is not allowed');let target:Record<string,unknown>|unknown[]=clone;for(const part of parts.slice(0,-1)){const next=Array.isArray(target)?target[Number(part)]:(target as Record<string,unknown>)[part];if(!next||typeof next!=='object')throw new Error(`Patch path does not exist: ${operation.path}`);target=next as Record<string,unknown>|unknown[];}const key=parts.at(-1)!;if(operation.op==='remove'){if(Array.isArray(target))target.splice(Number(key),1);else delete (target as Record<string,unknown>)[key];}else if(Array.isArray(target)){if(operation.op==='add'&&key==='-')target.push(operation.value);else target[Number(key)]=operation.value;}else (target as Record<string,unknown>)[key]=operation.value;}
  return clone as T;
};

export const runCached=<T>(artifactId:string,input:unknown,cache:CacheRecord[],producer:()=>T):{output:T|undefined;cache:CacheRecord[];executed:boolean}=>{
  const inputHash=contentHash(input);const hit=cache.find(record=>record.artifactId===artifactId&&record.inputHash===inputHash);
  if(hit)return {output:undefined,cache,executed:false};
  const output=producer();const record:CacheRecord={schemaVersion:1,key:`${artifactId}:${inputHash}`,inputHash,outputHash:contentHash(output),artifactId,createdAt};return {output,cache:[...cache.filter(r=>r.artifactId!==artifactId),record],executed:true};
};
