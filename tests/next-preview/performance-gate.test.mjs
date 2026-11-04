import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../tools/complete-navigation-metrics.mjs').catch(()=>({}));
test('missing targets or metrics cannot turn into a passing performance gate',()=>{
 assert.equal(typeof api.evaluateGate,'function');assert.equal(api.evaluateGate([]).status,'fail');assert.equal(api.evaluateGate([{version:'new',scenario:'sem',temperature:'cold'}]).status,'fail');
});
test('RAF or DrawFrame events never stand in for confirmed presentation timestamps',()=>{
 assert.equal(typeof api.presentationEvidence,'function');assert.equal(api.presentationEvidence([{name:'DrawFrame',ts:100},{name:'BeginFrame',ts:200}]).status,'unmeasured');
});
