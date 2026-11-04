import test from 'node:test';import assert from 'node:assert/strict';
import {watchGeneration} from '../../site/assets/library/generation-client.mjs';
test('visual review failure keeps materials and offers a clear non-success message',async()=>{
 const {generationStatus}=await import('../../site/assets/library/generation-page.mjs');
 assert.equal(generationStatus({state:'failed',progress:{error_code:'visual_review_required'}}),'图示尚未通过核对，已有内容和资料已保存');
 assert.equal(generationStatus({state:'complete'}),'已生成，可领取');
});
test('partial supplementary uploads resume by fingerprint, not shifted position',async()=>{
 const {uploadPendingMaterials}=await import('../../site/assets/library/generation-page.mjs');
 const uploads=[{id:'one',sha256:'a',mime:'text/plain',bytes:5,uploaded:true},{id:'two',sha256:'b',mime:'text/plain',bytes:6,uploaded:false}];
 const client={get:async()=>({id:'j',version:4,uploads}),upload:async(job,id,file)=>{assert.equal(id,'two');assert.equal(await file.text(),'second');return {id:'j',version:5,uploads:uploads.map(d=>({...d,uploaded:true}))};}};
 const files=[new File(['first'],'one.txt'),new File(['second'],'two.txt')],descriptors=[{sha256:'a',mime:'text/plain',bytes:5},{sha256:'b',mime:'text/plain',bytes:6}];
 assert.equal((await uploadPendingMaterials(client,{id:'j'},files,descriptors)).version,5);
});
test('waiting for input stops polling without cancelling or creating another task',async()=>{
 let reads=0,cancelled=0;const states=[];const client={get:async()=>({id:'j',state:++reads===1?'running':'waiting_input'}),cancel:()=>cancelled++};
 await watchGeneration(client,'j',{onState:v=>states.push(v.state),interval:1});
 assert.deepEqual(states,['running','waiting_input']);assert.equal(cancelled,0);assert.equal(reads,2);
});
test('leaving the page ignores a late response without stopping the server job',async()=>{
 const controller=new AbortController();let finish;const request=new Promise(r=>finish=r),states=[];
 const pending=watchGeneration({get:()=>request},'j',{signal:controller.signal,onState:v=>states.push(v),interval:1});controller.abort();finish({state:'complete'});
 await pending;assert.equal(states.length,0);
});
