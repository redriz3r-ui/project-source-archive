import assert from 'node:assert/strict';
import {researchReportSchema} from '../cli/research';
import {validateLocalScript} from '../cli/local-documentary';

const report=researchReportSchema.parse({
  schemaVersion:1,title:'Local Test',topic:'A documented historical event',researchedAt:'2026-09-05T00:00:00.000Z',
  sources:[{id:'source-1',title:'Official report',url:'https://example.gov/report',publisher:'Archive',accessedAt:'2026-09-05',authority:'PRIMARY'}],
  claims:Array.from({length:6},(_,index)=>({id:`claim-${index+1}`,text:`Supported historical claim ${index+1}.`,evidence:`The official evidence passage supports historical claim number ${index+1}.`,sourceIds:['source-1'],confidence:'HIGH',numbers:[String(index+1)],conflictIds:[]})),
  conflicts:[],warnings:[],status:'PASS',
});
const script={script:Array.from({length:6},(_,index)=>({id:`beat-${index+1}`,narration:`This carefully grounded documentary sentence explains supported historical claim number ${index+1} using only the official evidence supplied to the local model, carefully and clearly.`,visual:'AUTO',sourceIds:['source-1'],claimIds:[`claim-${index+1}`],archiveQuery:`historical event evidence ${index+1}`}))};
assert.equal(validateLocalScript(report,script).length,6);
assert.throws(()=>validateLocalScript(report,{script:script.script.map((beat,index)=>index?beat:{...beat,sourceIds:['invented-source']})}),/does not support/);
console.log('Local documentary tests passed: bounded script, claim grounding, and source grounding.');
