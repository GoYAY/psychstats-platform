import test from 'node:test';import assert from 'node:assert/strict';
import {parseLibraryRoute} from '../../site/assets/library/app.mjs';
import {savedViewOptions} from '../../site/assets/library/network-page.mjs';
const api=await import('../../site/assets/library/public-networks.mjs').catch(()=>({}));
const graph={terms:[],edges:[],frameworks:[{id:'regression',title:'回归框架',core:['a'],oneHop:['b'],edgeKeys:[]}]};
test('guide hash opens its own section instead of falling back to private terms',()=>{assert.equal(parseLibraryRoute('#view=guide').view,'guide');});
test('official frame choices are available without personal records and do not replace saved layouts',()=>{const records={frameworks:[{id:'mine',title:'自己的框架'}],graphViews:[]},before=structuredClone(records);const rows=savedViewOptions(records,graph);assert.deepEqual(rows.map(r=>r.id),['official:regression','mine']);assert.deepEqual(records,before);});
test('public frame projection marks core versus supporting terms without storing or exposing personal entries',()=>{assert.equal(typeof api.publicFramework,'function');const before=structuredClone(graph),f=api.publicFramework(graph,'official:regression');assert.equal(f.publicTemplate,'regression');assert.deepEqual(f.members,[{space:'official',id:'a'},{space:'official',id:'b'}]);assert.deepEqual(f.memberDetails.map(r=>r.role),['core','supporting']);assert.deepEqual(graph,before);assert.equal(api.publicFramework(graph,'official:missing'),null);assert.equal(api.publicFramework(graph,'mine'),null);});
