import test from 'node:test';import assert from 'node:assert/strict';
const api=await import('../../site/assets/library/canvas-workspace.mjs').catch(()=>({}));
test('workspace fills the visual viewport below navigation without a spare footer gap',()=>{assert.equal(typeof api.workspaceHeight,'function');assert.equal(api.workspaceHeight({height:900,top:250}),650);assert.equal(api.workspaceHeight({height:600,top:210}),390);assert.equal(api.workspaceHeight({height:200,top:250}),160);});
