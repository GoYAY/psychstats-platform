import test from 'node:test';import assert from 'node:assert/strict';import {packageFixture} from './helpers.mjs';
import {buildIndex,updateIndex,search,selectContext} from '../../site/assets/library/search.mjs';
test('exact aliases first, case insensitive and Chinese offsets point to original',()=>{
 const r=packageFixture();r.terms[0].aliases=['Sample Unit'];const index=buildIndex(r);
 assert.equal(search(index,'sample unit')[0].termId,'sample');const h=search(index,'实际观察')[0];assert.equal(h.text.slice(h.start,h.end),'实际观察');
});
test('incremental update touches one of 100 records and equals rebuild',()=>{
 const r=packageFixture(),terms=Array.from({length:100},(_,i)=>({...r.terms[0],id:'t'+i,zh:'术语'+i,currentRevisionId:null}));r.terms=terms;r.revisions=[];const index=buildIndex(r),changed={...terms[12],aliases:['新名']};
 updateIndex(index,{writes:[{kind:'terms',id:changed.id,value:changed}],deletes:[]});assert.equal(index.lastUpdated,1);
 assert.deepEqual(search(index,'新名'),search(buildIndex({...r,terms:terms.map(t=>t.id===changed.id?changed:t)}),'新名'));
});
test('context selection is bounded, missing originals explicit, trash excluded',()=>{
 const r=packageFixture();r.evidence[0].data.text='样本'.repeat(10000);const idx=buildIndex(r);const context=selectContext(idx,'样本',{limit:5,maxChars:6000});assert.ok(context.reduce((a,c)=>a+c.text.length,0)<=6000);assert.ok(context.some(c=>c.originalMissing));
 updateIndex(idx,{writes:[{kind:'terms',id:'sample',value:{...r.terms[0],trashed:true}}],deletes:[]});assert.equal(search(idx,'样本').length,0);
});
