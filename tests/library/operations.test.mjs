import test from 'node:test';import assert from 'node:assert/strict';import {packageFixture} from './helpers.mjs';
import {addAnnotation,addRevision,updateTermMeta,setEdgeStatus,trashTerm,restoreTerm,deleteOriginal,purgeTerm,purgeLibrary} from '../../site/assets/library/operations.mjs';
import {validatePackage} from '../../site/assets/library/contract.mjs';
const snap=()=>({version:2,libraryId:'main',records:packageFixture()});
const apply=(s,p)=>{for(const d of p.deletes)s.records[d.kind]=s.records[d.kind].filter(r=>r.id!==d.id);for(const w of p.writes){s.records[w.kind]=s.records[w.kind].filter(r=>r.id!==w.id);s.records[w.kind].push(w.value);}return s;};
test('annotations bind to exact revision and removed blocks remain relocatable',()=>{
 const s=snap(),note=addAnnotation(s,{termId:'sample',revisionId:'rev-demo',blockId:'plain_explanation',text:'个人思考'});apply(s,note);const revision={...structuredClone(s.records.revisions[0]),id:'rev-new'};revision.lesson.blocks=revision.lesson.blocks.filter(b=>b.id!=='plain_explanation');apply(s,addRevision(s,{termId:'sample',revision}));
 assert.equal(s.records.revisions.length,2);assert.equal(s.records.annotations[0].text,'个人思考');assert.equal(s.records.annotations[0].anchorStatus,'needs-location');assert.equal(s.records.annotations[0].revisionId,'rev-demo');
});
test('metadata and recycle preserve content; full purge requires explicit identity',()=>{
 const s=snap(),before=JSON.stringify(s.records.revisions);apply(s,updateTermMeta(s,{termId:'sample',aliases:['样本组'],tags:['学习']}));apply(s,trashTerm(s,'sample'));assert.equal(s.records.terms[0].trashed,true);apply(s,restoreTerm(s,'sample'));assert.equal(s.records.terms[0].trashed,false);assert.equal(JSON.stringify(s.records.revisions),before);assert.throws(()=>purgeLibrary(s,{confirmLibraryId:'wrong'}),e=>e.code==='CONFLICT');
});
test('source deletion requires explicit choice, impacts and tombstones restore safely',()=>{
 const s=snap();assert.throws(()=>deleteOriginal(s,{sourceId:'source-demo'}));const plan=deleteOriginal(s,{sourceId:'source-demo',removeExtracted:true});assert.ok(plan.impact.some(i=>i.termId==='sample'));apply(s,plan);assert.equal(s.records.evidence[0].data.text,'');assert.equal(s.records.sources[0].originalStatus,'deleted');assert.doesNotThrow(()=>validatePackage(s.records));
});
test('purge preserves shared original records and removes own dangling references',()=>{
 const s=snap();s.records.terms.push({...s.records.terms[0],id:'other',currentRevisionId:'rev-other'});s.records.revisions.push({...s.records.revisions[0],id:'rev-other',termId:'other',evidenceIds:['ev-other']});s.records.evidence.push({...s.records.evidence[0],id:'ev-other',revisionId:'rev-other'});
 apply(s,purgeTerm(s,'sample'));assert.equal(s.records.sources.length,1);assert.equal(s.records.evidence.length,1);assert.equal(s.records.revisions.length,1);assert.equal(s.records.terms[0].id,'other');
});
test('edge decisions persist separate from model text',()=>{
 const s=snap();s.records.edges=[{id:'e',status:'suggested',reason:'模型建议'}];const p=setEdgeStatus(s,{edgeId:'e',status:'dismissed'});assert.equal(p.writes[0].value.reason,'模型建议');assert.equal(p.writes[0].value.status,'dismissed');
});
