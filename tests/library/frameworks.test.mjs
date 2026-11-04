import test from 'node:test';
import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';
import {upgradePackage,validatePackage} from '../../site/assets/library/contract.mjs';
import {buildGraph} from '../../site/assets/library/graph-model.mjs';
import {planGraphInverse} from '../../site/assets/library/graph-commands.mjs';
const api=await import('../../site/assets/library/framework-commands.mjs').catch(()=>({}));
const now='2026-10-20T00:00:00.000Z';
test('renamed imported legacy frame expands original official template without unrelated private terms',()=>{const s=state(),id='factor-analysis-imported';s.records.graphViews=[{id:'imported',title:'旧因素框架',frameworkId:id,mode:'free',nodes:[],groups:[],contextRefs:[],excludedRefs:[],viewport:{x:2,y:3,scale:1},updatedAt:now}];s.records.frameworks=[{id,title:'旧因素框架',description:'',members:[],origin:'legacy',provenance:null,locks:{title:false,members:false},legacyTemplate:'factor-analysis',createdAt:now,updatedAt:now,revision:0}];const before=structuredClone(s.records.graphViews),next=apply(s,command(s,{kind:'materializeLegacy',id}).plan);assert.deepEqual(next.records.frameworks[0].members.map(r=>r.id).sort(),['a','b']);assert.deepEqual(next.records.graphViews,before);});
test('deleting the sole frame retains globally resolvable background identities and their relations',()=>{let s=create(state());s.records.revisions[0].lesson.glossary=[{id:'g',term:'背景概念',explanation:'理解所需的已存释义。'}];s.records.graphViews=[{id:'v',title:'布局',frameworkId:'fw',mode:'free',nodes:[],groups:[],contextRefs:[{id:'context-one',revisionId:'rev-demo',glossaryId:'g'}],excludedRefs:[],viewport:{x:0,y:0,scale:1},updatedAt:now}];s.records.edges.push({id:'user-bg',from:{space:'personal',id:'sample'},to:{space:'pending',id:'context-one'},type:'next',reason:'个人学习关联',origin:'user',revisionId:null,refs:[],status:'confirmed'});s=apply(s,command(s,{kind:'delete',id:'fw'}).plan);assert.equal(s.records.graphViews.length,0);assert.equal(s.records.edges.length,1);assert.ok(s.records.contexts.some(c=>c.id==='context-one'));assert.doesNotThrow(()=>validatePackage({schemaVersion:3,packageId:'test',...s.records}));});
const ref=id=>({space:'official',id});
const official={terms:[{id:'a',zh:'甲',published:true},{id:'b',zh:'乙',published:true}],edges:[],frameworks:[{id:'factor-analysis',title:'因素',core:['a'],oneHop:['b'],edgeKeys:[]}]};
const state=()=>({version:1,records:upgradePackage(packageFixture())});
function apply(s,p){const n=structuredClone(s);for(const d of p.deletes)n.records[d.kind]=n.records[d.kind].filter(v=>v.id!==d.id);for(const w of p.writes)n.records[w.kind]=[...(n.records[w.kind]||[]).filter(v=>v.id!==w.id),w.value];n.version++;return n;}
function command(s,c){assert.equal(typeof api.planFrameworkCommand,'function','Framework command API missing');return api.planFrameworkCommand(s,{...c,updatedAt:now},{officialGraph:official,catalogue:official.terms});}
function create(s,id='fw'){return apply(s,command(s,{kind:'create',id,title:'自己的框架',members:[ref('a')]}).plan);}
test('v1 and v2 normalize into v4 without altering original records or views',()=>{
 for(const version of [1,2]){const p=packageFixture();p.schemaVersion=version;if(version===2)p.graphViews=[{id:'legacy',title:'旧框架',frameworkId:'factor-analysis',mode:'free',nodes:[],groups:[],contextRefs:[],excludedRefs:[],viewport:{x:11,y:22,scale:1},updatedAt:now}];const before=structuredClone(p),n=upgradePackage(p);assert.equal(n.schemaVersion,4);assert.deepEqual(p,before);assert.deepEqual(n.revisions,p.revisions);if(version===2){assert.deepEqual(n.graphViews,p.graphViews);assert.equal(n.frameworks[0].legacyTemplate,'factor-analysis');assert.equal(n.frameworks[0].id,'factor-analysis');}}
});
test('frameworks own exact members and do not sweep in unrelated private terms',()=>{
 const s=create(state());const model=buildGraph({records:s.records,catalogue:official.terms,officialGraph:official,view:{},framework:s.records.frameworks[0]});assert.deepEqual(model.nodes.map(n=>n.ref),[ref('a')]);
});
test('one term can belong to two frames; delete and inverse preserve source records',()=>{
 let s=create(create(state()),'fw-two');const before=structuredClone(s.records.terms),result=command(s,{kind:'delete',id:'fw'});s=apply(s,result.plan);assert.equal(s.records.frameworks.length,1);assert.deepEqual(s.records.terms,before);s=apply(s,planGraphInverse(s,result.inverse).plan);assert.equal(s.records.frameworks.length,2);
});
test('member edits and renaming lock manual decisions; notes do not fabricate revisions',()=>{
 let s=create(state());s=apply(s,command(s,{kind:'rename',id:'fw',title:'人工命名'}).plan);assert.equal(s.records.frameworks[0].locks.title,true);
 const revisions=s.records.revisions.length;s=apply(s,command(s,{kind:'createNote',id:'fw',termId:'note-one',name:'个人概念',definition:'暂存的理解'}).plan);assert.equal(s.records.revisions.length,revisions);assert.equal(s.records.terms.find(t=>t.id==='note-one').currentRevisionId,null);assert.equal(s.records.frameworks[0].locks.members,true);assert.ok(s.records.frameworks[0].members.some(r=>r.id==='note-one'));
});
test('a manually named new frame protects its title from automatic replacement',()=>{const s=create(state());assert.equal(s.records.frameworks[0].locks.title,true);});
test('manual changes preserve archived model provenance without attributing new members to it',()=>{let s=state();const provenance={taskId:'task-old',inputHash:'a'.repeat(64),model:'deepseek-flash',usage:{prompt_tokens:1,completion_tokens:2,total_tokens:3},calls:1,memberReasons:[{ref:ref('a'),reason:'已有定义的共同主题'}]};s=apply(s,command(s,{kind:'create',id:'fw',title:'模型框架',members:[ref('a')],origin:'model',provenance}).plan);s=apply(s,command(s,{kind:'addMember',id:'fw',ref:ref('b')}).plan);assert.equal(s.records.frameworks[0].provenance.taskId,'task-old');assert.equal(s.records.frameworks[0].provenance.memberReasons.length,1);assert.equal(s.records.frameworks[0].origin,'user');});
test('invalid and recycled member references are rejected and model origin needs real provenance',()=>{
 const s=create(state());s.records.terms[0].trashed=true;for(const r of [{space:'personal',id:'sample'},ref('missing')])assert.throws(()=>command(s,{kind:'addMember',id:'fw',ref:r}));
 const p=structuredClone(s.records);p.packageId='p';p.schemaVersion=3;p.frameworks[0].origin='model';p.frameworks[0].provenance=null;assert.throws(()=>validatePackage(p));
});
test('legacy templates materialize against actual graph without moving saved positions',()=>{
 const p=packageFixture();p.schemaVersion=2;p.graphViews=[{id:'legacy',title:'旧框架',frameworkId:'factor-analysis',mode:'free',nodes:[{ref:ref('a'),x:23,y:45,pinned:true,groups:[]}],groups:[],contextRefs:[],excludedRefs:[],viewport:{x:11,y:22,scale:1},updatedAt:now}];let s={version:1,records:upgradePackage(p)};const before=structuredClone(s.records.graphViews);s=apply(s,command(s,{kind:'materializeLegacy',id:'factor-analysis'}).plan);assert.deepEqual(s.records.frameworks[0].members,[ref('a'),ref('b')]);assert.equal(s.records.frameworks[0].legacyTemplate,null);assert.deepEqual(s.records.graphViews,before);
});
