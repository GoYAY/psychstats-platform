import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/view-state.mjs').catch(()=>({}));
test('URL parsing preserves topic and hash only for supported routes',()=>{
 assert.equal(typeof api.parseView,'function');
 assert.deepEqual(api.parseView('http://localhost/psy-stats/terms/sem/#formula'),{key:'sem',topic:'foundations',hash:'#formula'});
 assert.deepEqual(api.parseView('http://localhost/psy-stats/?topic=favorites'),{key:'index',topic:'favorites',hash:''});
 assert.equal(api.parseView('http://localhost/psy-stats/terms/missing/'),null);
});
test('latest request token invalidates stale completion and popstate cancels pending',()=>{
 assert.equal(typeof api.createRequestGate,'function');const gate=api.createRequestGate(),a=gate.begin(),b=gate.begin();assert.equal(gate.isCurrent(a),false);assert.equal(gate.isCurrent(b),true);gate.invalidate();assert.equal(gate.isCurrent(b),false);
});
test('history merge keeps framework state and filters when replacing browser view',()=>{
 assert.equal(typeof api.mergeViewState,'function');assert.deepEqual(api.mergeViewState({__NA:true,psychFilters:{level:'basic'},other:2},{key:'sem'}),{__NA:true,psychFilters:{level:'basic'},other:2,psychView:{key:'sem'}});
});
test('external URL writes omit framework loop guards without dropping app history',()=>{
 assert.equal(typeof api.historyPayload,'function');assert.deepEqual(api.historyPayload({__NA:true,_N:true,__PRIVATE_NEXTJS_INTERNALS_TREE:[1],psychFilters:{level:'basic'},psychView:{key:'sem'}}),{__PRIVATE_NEXTJS_INTERNALS_TREE:[1],psychFilters:{level:'basic'},psychView:{key:'sem'}});
});
