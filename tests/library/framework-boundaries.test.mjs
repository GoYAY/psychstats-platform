import test from 'node:test';
import assert from 'node:assert/strict';
import {packageFixture} from './helpers.mjs';
import {upgradePackage} from '../../site/assets/library/contract.mjs';
import {legacyFrameworks} from '../../site/assets/library/framework-schema.mjs';
import {buildGraph} from '../../site/assets/library/graph-model.mjs';
import {planFrameworkCommand} from '../../site/assets/library/framework-commands.mjs';
import {planGraphInverse} from '../../site/assets/library/graph-commands.mjs';
const api=await import('../../site/assets/library/framework-boundaries.mjs').catch(()=>({}));
const ref=id=>({space:'personal',id});
function fixture(){const records=upgradePackage(packageFixture());records.terms[0].zh='认知漂移';records.terms.push({...structuredClone(records.terms[0]),id:'dtp',zh:'DTP',currentRevisionId:null});
 const view={id:'human-ai',frameworkId:'human-ai',title:'人–AI交互',mode:'free',nodes:[],groups:[{id:'declared',title:'人–AI',origin:'user',members:[ref('sample')],sourceRef:{kind:'user',id:'local'}}],contextRefs:[],excludedRefs:[],viewport:{x:10,y:20,scale:1},updatedAt:'2026-10-21T00:00:00.000Z'};
 records.graphViews=[view];records.frameworks=legacyFrameworks([view]);records.edges=[{id:'cross',from:ref('dtp'),to:{space:'official',id:'standard-error'},type:'prerequisites',reason:'计分方法使用误差概念',origin:'user',status:'confirmed',revisionId:null,refs:[]}];return {version:1,records};}
test('legacy human AI does not expand to unrelated personal terms or their statistical prerequisites',()=>{const s=fixture(),g=buildGraph({records:s.records,view:s.records.graphViews[0],officialGraph:{terms:[{id:'standard-error',zh:'标准误'}],edges:[],frameworks:[]}});assert.deepEqual(g.nodes.map(n=>n.ref.id),['sample']);});
test('materializing a legacy human AI frame retains only declared members and saved geometry',()=>{const s=fixture(),before=structuredClone(s.records.graphViews),r=planFrameworkCommand(s,{kind:'materializeLegacy',id:'human-ai'});assert.deepEqual(r.plan.writes.find(w=>w.kind==='frameworks').value.members,[ref('sample')]);assert.deepEqual(s.records.graphViews,before);});
test('explicit manual membership remains even when its name is outside the typical domain',()=>{const s=fixture(),frame={...s.records.frameworks[0],members:[ref('dtp')],legacyTemplate:null,origin:'user'};assert.deepEqual(buildGraph({records:s.records,framework:frame}).nodes.map(n=>n.ref.id),['dtp']);});
test('legacy cleanup is a preview and removal changes only the framework with a reversible inverse',()=>{assert.equal(typeof api.inspectLegacyMembership,'function');const s=fixture();s.records.frameworks[0].members.push(ref('dtp'));const before=structuredClone(s),report=api.inspectLegacyMembership(s,'human-ai');assert.deepEqual(report.extra,[ref('dtp')]);const result=api.planMembershipCleanup(s,{frameworkId:'human-ai',removeRefs:[ref('dtp')]});assert.deepEqual(s,before);assert.deepEqual(result.plan.deletes,[]);assert.deepEqual(result.plan.writes.map(w=>w.kind),['frameworks']);const next=structuredClone(s);next.records.frameworks[0]=result.plan.writes[0].value;assert.deepEqual(planGraphInverse(next,result.inverse).plan.writes[0].value,s.records.frameworks[0]);});
test('membership without declared legacy provenance is uncertain and never silently removed',()=>{assert.equal(typeof api.inspectLegacyMembership,'function');const s=fixture();s.records.graphViews=[];const report=api.inspectLegacyMembership(s,'human-ai');assert.deepEqual(report.uncertain,[ref('sample')]);assert.deepEqual(report.extra,[]);});
