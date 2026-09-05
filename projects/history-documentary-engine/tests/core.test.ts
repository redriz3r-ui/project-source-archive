import assert from 'node:assert/strict';
import {findConflicts, researchReportSchema} from '../cli/research';
import {productionBriefSchema} from '../cli/brief';
import {planDocumentary} from '../cli/planner';
import {parseManifest} from '../src/manifest/schema';
import mapManifest from '../public/projects/maplibre-proof/manifest.json';
import {directBrief} from '../cli/visual-director';
import {createDirectorState, directorStateSchema} from '../cli/director';
import {continueEpisode} from '../cli/resume';
import {compilePhoneFast} from '../src/phone/compiler';
import {jordanPhoneProof} from '../src/phone/jordanProof';
import {assessLegacyManifest,validatePhoneFast} from '../src/phone/validator';
import {planPhoneMigration} from '../src/phone/migration';
import jordanLegacy from '../public/projects/episode-2/manifest.json';

const claims = [
  {id: 'a', text: 'The official report recorded 120 homes destroyed in the district.', evidence: 'Evidence A', sourceIds: ['s1'], confidence: 'HIGH' as const, numbers: ['120'], conflictIds: [] as string[]},
  {id: 'b', text: 'The official report recorded 220 homes destroyed in the district.', evidence: 'Evidence B', sourceIds: ['s2'], confidence: 'HIGH' as const, numbers: ['220'], conflictIds: [] as string[]},
];
assert.equal(findConflicts(claims).length, 1, 'numeric contradictions with matching predicates must be flagged');
assert.deepEqual(claims.map((claim) => claim.conflictIds.length), [1, 1]);

researchReportSchema.parse({schemaVersion: 1, title: 'Test', topic: 'Test', researchedAt: new Date().toISOString(), sources: [
  {id: 's1', title: 'Primary', url: 'https://example.gov/a', publisher: 'Archive', accessedAt: '2026-08-25', authority: 'PRIMARY'},
  {id: 's2', title: 'Secondary', url: 'https://example.edu/b', publisher: 'University', accessedAt: '2026-08-25', authority: 'AUTHORITATIVE_SECONDARY'},
], claims, conflicts: findConflicts(claims), warnings: [], status: 'REVIEW_REQUIRED'});

const visualTypes = ['DOCUMENT_EXCERPT', 'QUOTE_CARD', 'STATISTIC', 'DATE_CARD'] as const;
const brief = productionBriefSchema.parse({title: 'Scene Proof', topic: 'Renderer contracts', sources: [{id: 's1', title: 'Source', url: 'https://example.gov/source'}], script: visualTypes.map((visual, index) => ({id: `beat-${index}`, narration: index === 1 ? 'The witness said “This is a sufficiently long historical quotation.”' : `In 1927 the report recorded 120 people for scene ${index}.`, visual, sourceIds: ['s1'], claimIds: [`claim-${index}`]}))});
const manifest = planDocumentary(brief);
assert.deepEqual(manifest.scenes.slice(1).map((scene) => scene.type), visualTypes);
parseManifest(manifest);
parseManifest(mapManifest);

const explained = productionBriefSchema.parse({title: 'Five Lost Inventions Explained', topic: 'Lost inventions', storyMode: 'EXPLAINED', sources: [{id: 's1', title: 'Source', url: 'https://example.gov/source'}], script: [{id: 'one', chapter: 'The first machine', narration: 'The machine crossed the region in 1912. It disappeared because its maker destroyed the plans.', sourceIds: ['s1'], claimIds: ['c1']}, {id: 'two', chapter: 'The second machine', narration: 'The official report recorded 120 people at the demonstration.', sourceIds: ['s1'], claimIds: ['c2']}]});
const directed = directBrief(explained);
assert.equal(directed.filter((shot) => shot.visual === 'CHAPTER_CARD').length, 2, 'explained mode should insert chapter cards');
assert.ok(directed.filter((shot) => shot.narration).length >= 3, 'passages should expand into sentence-level shots');
const explainedManifest = planDocumentary(explained);
assert.ok(new Set(explainedManifest.scenes.map((scene) => scene.type)).size >= 4, 'director should create visual variety');
assert.ok(explainedManifest.scenes.every((scene) => scene.direction), 'every planned scene should include direction metadata');

const completeGrammar = ['ARCHIVE_PHOTO', 'KEN_BURNS', 'MAP', 'DOCUMENT_EXCERPT', 'QUOTE_CARD', 'STATISTIC', 'DATE_CARD', 'LABELED_CUTOUT', 'DIAGRAM', 'CHAPTER_CARD', 'ILLUSTRATION'] as const;
const grammarBrief = productionBriefSchema.parse({title: 'Visual Grammar Proof', topic: 'Renderer coverage', sources: [{id: 's1', title: 'Source', url: 'https://example.gov/source'}], script: completeGrammar.map((visual, index) => ({id: `grammar-${index}`, narration: visual === 'QUOTE_CARD' ? 'A witness said “This historical quotation is long enough.”' : `Supported visual grammar statement number ${index + 1}.`, visual, sourceIds: ['s1'], claimIds: [`claim-${index}`]}))});
const grammarManifest = planDocumentary(grammarBrief);
for (const type of completeGrammar) assert.ok(grammarManifest.scenes.some((scene) => scene.type === type), `${type} should be planned and parseable`);
const director = createDirectorState('episode-1', '2026-08-25T00:00:00.000Z');
directorStateSchema.parse(director);
assert.equal(director.activeCheckpoint, 'TOPIC_PROMISE');
assert.equal(director.checkpoints.length, 7);
assert.equal(director.checkpoints[0].options.length, 3);
assert.equal(director.checkpoints.filter((checkpoint) => checkpoint.status === 'AWAITING_CHOICE').length, 1);
const phoneReport=validatePhoneFast(jordanPhoneProof);
assert.equal(phoneReport.status,'PASS',phoneReport.errors.join('; '));
assert.deepEqual(compilePhoneFast(jordanPhoneProof),compilePhoneFast(jordanPhoneProof),'phone-fast compilation must be deterministic');
const retentionFailure=validatePhoneFast({...jordanPhoneProof,retentionMap:[{atSeconds:3,device:'OPEN_LOOP',text:'late'},{atSeconds:30,device:'PAYOFF',text:'later'}]});
assert.equal(retentionFailure.status,'FAIL');
const missingReveal={...jordanPhoneProof,microchapters:jordanPhoneProof.microchapters.map((chapter)=>({...chapter,beats:chapter.beats.map((beat)=>beat.purpose==='REVEAL'?{...beat,purpose:'ESCALATION' as const}:beat)}))};
assert.match(validatePhoneFast(missingReveal).errors.join('; '),/REVEAL/,'a phone-fast story must contain an explicit reveal');
const reuseFailure={...jordanPhoneProof,assets:jordanPhoneProof.assets.map((asset)=>asset.id==='retirement'?{...asset,maxTotalUses:1}:asset)};
assert.match(validatePhoneFast(reuseFailure).errors.join('; '),/uses exceed/,'asset reuse limits must be enforced');
const pacingFailure={...jordanPhoneProof,pacing:{...jordanPhoneProof.pacing,maxUnchangedSeconds:2}};
assert.match(validatePhoneFast(pacingFailure).errors.join('; '),/unchanged-frame limit/,'visual events longer than the pacing ceiling must fail');
const cropClone={...jordanPhoneProof,assets:jordanPhoneProof.assets.map((a,i)=>i===1||i===2?{...a,src:jordanPhoneProof.assets[0].src}:a)};
assert.match(validatePhoneFast(cropClone).errors.join('; '),/distinct source files/,'different IDs/crops of one file must not count as distinct assets');
assert.equal(assessLegacyManifest(parseManifest(jordanLegacy)).status,'FAIL','legacy repetitive Jordan cut must fail creative validation');
const migration=planPhoneMigration(parseManifest(jordanLegacy));
assert.equal(migration.writePolicy,'NEW_FILE_ONLY');
assert.ok(migration.assets.length>0&&migration.gaps.length>=4,'migration must preserve sources and expose creative gaps without overwriting v1');
continueEpisode('episode-1',{dryRun:true}).then((resume) => {
  assert.equal(resume.ledger.currentStage,'FINAL_PUBLICATION');
  assert.match(resume.ledger.lastRun?.result ?? '',/SKIPPED/);
  console.log('Core tests passed: conflicts, evidence schema, visual directing, scene registry contracts, persistent director workflow, and resumable ledger.');
});
