import test from 'node:test';import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';import {validatePackage} from '../../site/assets/library/contract.mjs';
import * as op from '../../site/assets/library/operations.mjs';import {planRestore} from '../../site/assets/library/archive.mjs';import {readerProjection} from '../../site/assets/library/reader.mjs';
const snapshot=()=>({version:1,records:packageFixture()});
const apply=(s,p)=>{for(const d of p.deletes)s.records[d.kind]=s.records[d.kind].filter(r=>r.id!==d.id);for(const w of p.writes){s.records[w.kind]=s.records[w.kind].filter(r=>r.id!==w.id);s.records[w.kind].push(w.value);}return s;};
test('review2 malformed formulas quiz and unknown teaching fields rejected before saving',()=>{
 for(const change of [l=>l.formulas=[{latex:'x',refs:[]}],l=>delete l.quiz.options[0].explanation,l=>l.unexpectedPayload={text:'unknown'}]){const p=packageFixture();change(p.revisions[0].lesson);assert.throws(()=>validatePackage(p),e=>e.code==='INVALID_PACKAGE');}
});
test('review2 camelCase credentials are excluded from any provenance depth',()=>{
 const p=packageFixture();p.revisions[0].provenance.accessToken='synthetic-test-token';assert.throws(()=>validatePackage(p),e=>e.code==='INVALID_PACKAGE');
});
test('review2 restore planning validates final merged state',async()=>{
 const s=snapshot(),incoming=packageFixture();incoming.revisions[0].lesson.formulas=[{latex:'x',refs:[]}];await assert.rejects(()=>planRestore(s,incoming),e=>e.code==='INVALID_PACKAGE');
});
test('review3 new revision owns evidence and remains export-restorable',()=>{
 const s=snapshot(),r={...structuredClone(s.records.revisions[0]),id:'rev-new'};apply(s,op.addRevision(s,{termId:'sample',revision:r}));assert.doesNotThrow(()=>validatePackage(s.records));const saved=s.records.revisions.find(v=>v.id==='rev-new');assert.ok(saved.evidenceIds.every(id=>s.records.evidence.find(e=>e.id===id).revisionId==='rev-new'));
});
test('review4 conflict remaps personal embedded targets and preserves official namespace',async()=>{
 const s=snapshot(),p=packageFixture();p.terms[0].zh='样本的另一含义';const revision=structuredClone(p.revisions[0]);revision.id='rev-other';revision.termId='other';revision.lesson.term.id='other';revision.lesson.term.zh='另一个术语';revision.evidenceIds=['ev-other'];revision.lesson.glossary=[{id:'g-personal',term:'个人样本',explanation:'说明',aliases:[],target:'sample',targetSpace:'personal',refs:[]},{id:'g-official',term:'官方样本',explanation:'说明',aliases:[],target:'sample',targetSpace:'official',refs:[]}];revision.lesson.relations=[{target:'sample',targetSpace:'personal',type:'next',reason:'学习顺序',refs:[]}];p.terms.push({...structuredClone(p.terms[0]),id:'other',zh:'另一个术语',currentRevisionId:revision.id});p.revisions.push(revision);p.evidence.push({...structuredClone(p.evidence[0]),id:'ev-other',revisionId:revision.id});
 const plan=await planRestore(s,p),other=plan.writes.find(w=>w.kind==='revisions'&&w.value.termId==='other').value,branched=plan.writes.find(w=>w.kind==='terms'&&w.id!=='other').id;
 assert.equal(other.lesson.glossary[0].target,branched);assert.equal(other.lesson.glossary[1].target,'sample');assert.equal(other.lesson.relations[0].target,branched);assert.equal(plan.writes.find(w=>w.kind==='revisions'&&w.value.termId===branched).value.lesson.term.id,branched);
});
test('review5 source deletion resolves local source IDs within their own revision',()=>{
 const s=snapshot(),r=structuredClone(s.records.revisions[0]),text=s.records.evidence[0].data.text;r.id='rev-second';r.sourceIds=['source-demo','source-B'];r.sourceMap={s1:'source-B',s2:'source-demo'};r.evidenceIds=['ev-A2','ev-B'];r.lesson.blocks[0].paragraphs[0].refs=[{source_id:'s1',start:0,end:10,excerpt:text.slice(0,10)},{source_id:'s2',start:0,end:10,excerpt:text.slice(0,10)}];s.records.revisions.push(r);s.records.sources.push({...s.records.sources[0],id:'source-B'});s.records.evidence.push({...structuredClone(s.records.evidence[0]),id:'ev-A2',revisionId:r.id},{...structuredClone(s.records.evidence[0]),id:'ev-B',sourceId:'source-B',revisionId:r.id});
 apply(s,op.deleteOriginal(s,{sourceId:'source-demo',removeExtracted:true}));const refs=s.records.revisions.find(v=>v.id===r.id).lesson.blocks[0].paragraphs[0].refs;assert.equal(refs[0].excerpt,text.slice(0,10));assert.equal(refs[1].excerpt,undefined);
});
test('review6 reader projection discloses removed evidence and saved scope',()=>{
 const s=snapshot(),r=s.records.revisions[0];r.provenance.removedEvidence=true;r.lesson.limitations=[{text:'本定义来自框架论述，量化指标尚待验证。',refs:[]}];const view=readerProjection(r,s.records.sources,s.records.works);assert.equal(view.evidenceRemoved,true);assert.ok(view.limitations[0].includes('量化指标'));
});
test('review7 editing and relocation preserve note identity and prior anchor',()=>{
 const s=snapshot();apply(s,op.addAnnotation(s,{termId:'sample',revisionId:'rev-demo',blockId:'plain_explanation',text:'错字'}));const before=structuredClone(s.records.annotations[0]);assert.equal(typeof op.updateAnnotation,'function');apply(s,op.updateAnnotation(s,{annotationId:before.id,text:'已改正',revisionId:'rev-demo',blockId:'detailed_explanation'}));const note=s.records.annotations[0];assert.equal(note.id,before.id);assert.equal(note.text,'已改正');assert.equal(note.blockId,'detailed_explanation');assert.equal(note.anchorHistory[0].blockId,'plain_explanation');
});
