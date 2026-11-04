import test from 'node:test';import assert from 'node:assert/strict';
import {relationsFor,validateEdges} from '../../site/assets/library/graph.mjs';
const ref=id=>({space:'personal',id});
const edge=(a,b,type='prerequisites')=>({id:a+'-'+b,from:ref(a),to:ref(b),type,status:'suggested',reason:'学习关系'});
test('reverse prerequisite wording and statuses preserve direction',()=>{
 const r=relationsFor(ref('b'),[edge('a','b')]);assert.equal(r.incoming[0].label,'作为其前置知识');assert.equal(r.incoming[0].status,'suggested');assert.equal(r.incoming[0].target.id,'a');
 assert.equal(relationsFor(ref('a'),[{...edge('a','b'),status:'dismissed'}]).outgoing.length,0);
});
test('cycles warn for prerequisites only, shared papers do not create edges',()=>{
 assert.ok(validateEdges([edge('a','b'),edge('b','a')],[ref('a'),ref('b')]).some(i=>i.code==='PREREQUISITE_CYCLE'));
 assert.equal(validateEdges([edge('a','b','contrasts'),edge('b','a','contrasts')],[ref('a'),ref('b')]).length,0);
 assert.deepEqual(relationsFor(ref('a'),[]),{outgoing:[],incoming:[]});
});
test('hidden relations remain inspectable for restoration with their original direction',()=>{
 const hidden={...edge('a','b'),status:'dismissed'};
 assert.equal(relationsFor(ref('b'),[hidden]).incoming.length,0);
 const restoredView=relationsFor(ref('b'),[hidden],{includeDismissed:true});
 assert.equal(restoredView.incoming.length,1);
 assert.equal(restoredView.incoming[0].status,'dismissed');
 assert.equal(restoredView.incoming[0].target.id,'a');
 assert.equal(restoredView.incoming[0].label,'作为其前置知识');
});
