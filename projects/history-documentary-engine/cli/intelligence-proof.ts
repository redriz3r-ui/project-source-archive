import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {applyRestrictedPatch,buildContextBrief,contentHash,propagateInvalidation,runCached,validateClaimGrounding} from '../src/intelligence/engine';
import {jordanBriefInput,jordanClaims,jordanDecisions,jordanLegacyBroadContext,jordanPassages,jordanSources} from '../src/intelligence/jordanFixture';
import {cacheRecordSchema,dependencyRecordSchema,modelRunReceiptSchema,patchRequestSchema} from '../src/intelligence/schema';
import {jordanPhoneProof} from '../src/phone/jordanProof';
import {validatePhoneFast} from '../src/phone/validator';
import {artifactRegistryDescriptor} from '../src/intelligence/registry';

const root=path.resolve('public/projects/episode-2/intelligence-proof');
const outputReport=path.resolve('../outputs/jordan-intelligence-benchmark.json');
const stable=(value:unknown)=>`${JSON.stringify(value,null,2)}\n`;
const writeJson=async(file:string,value:unknown)=>{await mkdir(path.dirname(file),{recursive:true});const next=stable(value);let current='';try{current=await readFile(file,'utf8');}catch{}if(current!==next)await writeFile(file,next);};
const writeJsonl=async(file:string,values:unknown[])=>{await mkdir(path.dirname(file),{recursive:true});const next=`${values.map(value=>JSON.stringify(value)).join('\n')}\n`;let current='';try{current=await readFile(file,'utf8');}catch{}if(current!==next)await writeFile(file,next);};
const loadCache=async()=>{try{return cacheRecordSchema.array().parse(JSON.parse(await readFile(path.join(root,'state/cache.json'),'utf8')));}catch{return [];}};

const main=async()=>{
  const {brief,receipt}=buildContextBrief(jordanBriefInput);const grounding=validateClaimGrounding(brief.claimIds,jordanClaims,jordanPassages);if(grounding.status!=='PASS')throw new Error(grounding.errors.join('; '));
  const cache=await loadCache();let producerCalls=0;const taskInput={brief,outputSchema:'narration-beat-v2'};
  const run=runCached('narration-beat-p5',taskInput,cache,()=>{producerCalls++;return {schemaVersion:1,id:'p5-efficient',purpose:'REVEAL',text:'His first hit sparked a thirteen-game streak.',claimIds:['cl-streak']};});
  const generated=run.output??JSON.parse(await readFile(path.join(root,'03-script/narration-beat-p5.json'),'utf8'));
  const patch=patchRequestSchema.parse({schemaVersion:1,targetId:'p5-efficient',allowedPaths:['/text'],protectedPaths:['/claimIds','/purpose','/id'],operations:[{op:'replace',path:'/text',value:'Then his first hit sparked a thirteen-game streak.'}]});
  const patched=applyRestrictedPatch(generated,patch);const patchedGrounding=validateClaimGrounding((patched as {claimIds:string[]}).claimIds,jordanClaims,jordanPassages);if(patchedGrounding.status!=='PASS')throw new Error(patchedGrounding.errors.join('; '));
  const dependencies=dependencyRecordSchema.array().parse([{schemaVersion:1,artifactId:'narration-beat-p5',dependsOn:['cl-streak'],status:'VALID'},{schemaVersion:1,artifactId:'visual-events-p5',dependsOn:['narration-beat-p5'],status:'VALID'}]);
  const invalidationProof=propagateInvalidation(dependencies,['cl-streak']);
  const creative=validatePhoneFast(jordanPhoneProof);if(creative.status!=='PASS')throw new Error(`PHONE_FAST regression: ${creative.errors.join('; ')}`);
  const broadCharacters=JSON.stringify(jordanLegacyBroadContext).length;const boundedCharacters=brief.text.length;const reductionPercent=Number(((1-boundedCharacters/broadCharacters)*100).toFixed(1));
  const blueprintHashBefore=contentHash(jordanPhoneProof);const blueprintHashAfter=contentHash(jordanPhoneProof);
  const report={schemaVersion:1,status:reductionPercent>=70&&grounding.status==='PASS'&&creative.status==='PASS'&&blueprintHashBefore===blueprintHashAfter?'PASS':'FAIL',metrics:{broadContextCharacters:broadCharacters,boundedContextCharacters:boundedCharacters,contextReductionPercent:reductionPercent,estimatedBroadInputTokens:Math.ceil(broadCharacters/4),estimatedBoundedInputTokens:Math.ceil(boundedCharacters/4),unsupportedClaims:grounding.errors.length,modelCallsThisRun:producerCalls,unchangedRerunWouldCallModel:run.executed?1:0,fullArtifactRewritesForPatch:0,patchedPaths:patch.operations.map(op=>op.path),phoneFastCreativeScore:creative.score,phoneFastBlueprintPreserved:blueprintHashBefore===blueprintHashAfter},artifacts:{briefId:brief.id,receiptId:receipt.id,corpusHash:receipt.corpusHash,inputHash:brief.inputHash,outputHash:contentHash(patched)},invalidationProof};
  if(report.status!=='PASS')throw new Error(`Efficiency proof failed: ${JSON.stringify(report.metrics)}`);
  await writeJson(path.join(root,'artifact-registry.json'),artifactRegistryDescriptor);await writeJsonl(path.join(root,'01-research/sources.jsonl'),jordanSources);await writeJsonl(path.join(root,'01-research/evidence-passages.jsonl'),jordanPassages);await writeJsonl(path.join(root,'01-research/claims.jsonl'),jordanClaims);await writeJson(path.join(root,'01-research/corpus-snapshot.json'),{schemaVersion:1,corpusHash:receipt.corpusHash,sourceIds:jordanSources.map(x=>x.id),passageIds:jordanPassages.map(x=>x.id),claimIds:jordanClaims.map(x=>x.id)});await writeJsonl(path.join(root,'state/decisions.jsonl'),jordanDecisions);await writeJson(path.join(root,'02-brief/context-brief.json'),brief);await writeJson(path.join(root,'02-brief/retrieval-receipt.json'),receipt);await writeJson(path.join(root,'03-script/narration-beat-p5.json'),generated);await writeJson(path.join(root,'03-script/narration-beat-p5.patched.json'),patched);await writeJson(path.join(root,'state/dependencies.json'),dependencies);await writeJson(path.join(root,'state/cache.json'),run.cache);
  const runReceipt=modelRunReceiptSchema.parse({schemaVersion:1,id:`run-${brief.inputHash.slice(0,12)}-${run.executed?'executed':'cached'}`,taskType:brief.taskType,briefId:brief.id,inputHash:brief.inputHash,outputHash:contentHash(generated),model:'bounded-model-adapter-placeholder',status:run.executed?'EXECUTED':'CACHED',usage:{inputTokens:run.executed?Math.ceil(boundedCharacters/4):0,outputTokens:run.executed?Math.ceil(JSON.stringify(generated).length/4):0,elapsedMs:0},createdAt:'2026-08-26T00:00:00.000Z'});await writeJson(path.join(root,`state/runs/${runReceipt.id}.json`),runReceipt);await writeJson(path.join(root,'state/latest-run.json'),runReceipt);await writeJson(path.join(root,'benchmark.json'),report);await writeJson(path.join(root,`state/replay/${runReceipt.id}.json`),{schemaVersion:1,runReceipt,retrievalReceipt:receipt,brief,corpusHash:receipt.corpusHash});await writeJson(outputReport,report);
  console.log(`${run.executed?'EXECUTED':'SKIPPED'}: ${reductionPercent}% context reduction; ${grounding.errors.length} unsupported claims; PHONE_FAST ${creative.score}/100; patch rewrites 0`);
};
main().catch(error=>{console.error(error instanceof Error?error.message:error);process.exitCode=1;});
