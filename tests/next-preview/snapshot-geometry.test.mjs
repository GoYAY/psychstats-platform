import test from 'node:test';
import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/snapshot-geometry.mjs').catch(()=>({}));
test('snapshot geometry preserves endpoints through transform without animating layout dimensions',()=>{
 assert.equal(typeof api.compositorFrames,'function');
 const input=[{offset:0,width:'160px',height:'100px',transform:'matrix(1, 0, 0, 1, 100, 200)',backdropFilter:'none'},{offset:1,width:'640px',height:'400px',transform:'matrix(1, 0, 0, 1, 20, 30)',backdropFilter:'none'}];
 const result=api.compositorFrames(input);
 assert.equal(result[0].transform,'matrix(1, 0, 0, 1, 100, 200) scale(0.25, 0.25)');
 assert.equal(result[1].transform,'matrix(1, 0, 0, 1, 20, 30) scale(1, 1)');
 assert.ok(result.every(frame=>!('width' in frame)&&!('height' in frame)));
 assert.equal(input[0].width,'160px');assert.equal(result[0].offset,0);assert.equal(result[1].offset,1);
});
test('unknown or zero snapshot dimensions retain the native behavior',()=>{
 assert.equal(typeof api.compositorFrames,'function');
 assert.equal(api.compositorFrames([{width:'auto',height:'20px'},{width:'40px',height:'20px'}]),null);
 assert.equal(api.compositorFrames([{width:'20px',height:'20px'},{width:'0px',height:'20px'}]),null);
});
