import test from 'node:test';
import assert from 'node:assert/strict';
const module=await import('../../site/next-preview/lib/content-loader.mjs').catch(()=>({}));
const tick=()=>new Promise(r=>setTimeout(r,0));
test('loader merges duplicate requests and releases failed slots for retry',async()=>{
 assert.equal(typeof module.createContentLoader,'function');
 let calls=0;const loader=module.createContentLoader({fetcher:async()=>{calls++;if(calls===1)throw Error('offline');return {ok:true,json:async()=>({schemaVersion:1,key:'sem',payload:{html:'SEM'}})};}});
 const a=loader.load('sem'),b=loader.load('sem');await assert.rejects(a,/offline/);await assert.rejects(b,/offline/);assert.equal(calls,1);
 assert.deepEqual(await loader.load('sem'),{html:'SEM'});assert.equal(calls,2);await loader.load('sem');assert.equal(calls,2);
});
test('loader bounds concurrent work and explicit clicks queue instead of disappearing',async()=>{
 assert.equal(typeof module.createContentLoader,'function');
 const pending=[];let peak=0,active=0;
 const loader=module.createContentLoader({fetcher:url=>new Promise(resolve=>{active++;peak=Math.max(peak,active);pending.push(()=>{active--;const key=url.split('/').at(-1).replace('.json','');resolve({ok:true,json:async()=>({schemaVersion:1,key,payload:key==='index'?{topics:[],terms:[]}:{html:url}})});});})});
 const jobs=['sem','variable','paths','index'].map(k=>loader.load(k));await tick();assert.equal(pending.length,2);pending.shift()();await tick();assert.equal(pending.length,2);pending.shift()();await tick();while(pending.length)pending.shift()();await Promise.all(jobs);assert.equal(peak,2);
});
test('loader obeys slow-network prefetch and rejects malformed content',async()=>{
 assert.equal(typeof module.createContentLoader,'function');
 let calls=0;const loader=module.createContentLoader({fetcher:async()=>{calls++;return {ok:true,json:async()=>({schemaVersion:1,key:'sem',payload:{html:'<script>bad</script>'}})};}});
 await loader.prefetch('sem',{saveData:true});await loader.prefetch('sem',{effectiveType:'2g'});assert.equal(calls,0);
 await assert.rejects(loader.load('../escape'));await assert.rejects(loader.load('sem'),/content/i);
});
test('LRU eviction reloads the least recently used view',async()=>{
 assert.equal(typeof module.createContentLoader,'function');
 const calls=[];const loader=module.createContentLoader({maxEntries:2,fetcher:async url=>{const key=url.split('/').at(-1).replace('.json','');calls.push(key);return {ok:true,json:async()=>({schemaVersion:1,key,payload:{html:'ok'}})};}});
 await loader.load('sem');await loader.load('variable');await loader.load('sem');await loader.load('paths');await loader.load('variable');assert.deepEqual(calls,['sem','variable','paths','variable']);
});
test('initial static payload is available for history without refetch',async()=>{
 const loader=module.createContentLoader({fetcher:async()=>{throw Error('must not refetch initial page');}});assert.equal(typeof loader.seed,'function');loader.seed('sem',{html:'initial SEM'});assert.deepEqual(await loader.load('sem'),{html:'initial SEM'});
});
