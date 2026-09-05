import assert from 'node:assert/strict';
import {applyRestrictedPatch,buildContextBrief,propagateInvalidation,runCached,validateClaimGrounding} from '../src/intelligence/engine';
import {jordanBriefInput,jordanClaims,jordanPassages} from '../src/intelligence/jordanFixture';
import {contextBriefSchema,retrievalReceiptSchema} from '../src/intelligence/schema';
import {artifactRegistryDescriptor} from '../src/intelligence/registry';
import {jordanPhoneProof} from '../src/phone/jordanProof';
import {validatePhoneFast} from '../src/phone/validator';

const first=buildContextBrief(jordanBriefInput);const second=buildContextBrief(jordanBriefInput);
contextBriefSchema.parse(first.brief);retrievalReceiptSchema.parse(first.receipt);assert.deepEqual(first,second,'brief and receipt must be deterministic');
assert.equal(artifactRegistryDescriptor.length,10,'all intelligence artifact contracts must be registered');
assert.ok(first.brief.text.length<=jordanBriefInput.budget.maxCharacters,'brief must obey the character budget');assert.ok(first.brief.claimIds.length<=jordanBriefInput.budget.maxClaims);assert.ok(first.brief.passageIds.length<=jordanBriefInput.budget.maxPassages);
assert.deepEqual(first.receipt.claimIds,first.brief.claimIds,'receipt must exactly record supplied claims');assert.deepEqual(first.receipt.passageIds,first.brief.passageIds,'receipt must exactly record supplied passages');
assert.equal(validateClaimGrounding(first.brief.claimIds,jordanClaims,jordanPassages).status,'PASS');assert.equal(validateClaimGrounding(['unknown-claim'],jordanClaims,jordanPassages).status,'FAIL');assert.equal(validateClaimGrounding(['cl-rumor'],jordanClaims,jordanPassages).status,'FAIL');
const dependencies=[{schemaVersion:1 as const,artifactId:'beat',dependsOn:['cl-streak'],status:'VALID' as const},{schemaVersion:1 as const,artifactId:'events',dependsOn:['beat'],status:'VALID' as const}];const propagated=propagateInvalidation(dependencies,['cl-streak']);assert.ok(propagated.every(record=>record.status==='STALE'),'invalidation must propagate through dependencies');
const beat={id:'p5',purpose:'REVEAL',text:'Old text',claimIds:['cl-streak']};const basePatch={schemaVersion:1 as const,targetId:'p5',allowedPaths:['/text'],protectedPaths:['/claimIds','/purpose']};const patched=applyRestrictedPatch(beat,{...basePatch,operations:[{op:'replace',path:'/text',value:'Better text'}]});assert.equal(patched.text,'Better text');assert.deepEqual(patched.claimIds,beat.claimIds,'targeted patch must preserve grounded claim IDs');assert.throws(()=>applyRestrictedPatch(beat,{...basePatch,operations:[{op:'replace',path:'/claimIds',value:['cl-rumor']}]}),/protected/);
let calls=0;const initial=runCached('beat',first.brief,[],()=>{calls++;return beat;});const repeat=runCached('beat',first.brief,initial.cache,()=>{calls++;return beat;});assert.equal(initial.executed,true);assert.equal(repeat.executed,false);assert.equal(calls,1,'unchanged cached rerun must not execute producer');
assert.equal(validatePhoneFast(jordanPhoneProof).status,'PASS','intelligence layer must not regress PHONE_FAST');
console.log('Intelligence tests passed: bounded deterministic briefs, exact receipts, grounding, invalidation, caching, and restricted patches.');
