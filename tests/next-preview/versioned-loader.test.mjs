import test from 'node:test';
import assert from 'node:assert/strict';
import {createContentLoader} from '../../site/next-preview/lib/content-loader.mjs';
const manifest={schemaVersion:2,buildHash:'build-a',pages:Object.fromEntries(['index','paths','term:sem','term:variable','symbols'].map(key=>[key,{payloadURL:'/psy-stats/data/'+key.replace(':','-')+'.hash.json'}]))};
const response=(key,hash='build-a')=>({ok:true,json:async()=>({schemaVersion:2,key,buildHash:hash,payload:{kind:key,blocks:[{id:'body',role:'body',html:'<p>'+key+'</p>'}],...(key==='index'?{topics:[],terms:[]}: {})}})});
const tick=()=>new Promise(r=>setTimeout(r,0));
test('hashed manifest URL loads valid detail and mixed build never enters cache',async()=>{
 const seen=[];let wrong=true;
 const loader=createContentLoader({manifest,fetcher:async url=>{seen.push(url);return response('term:sem',wrong?'build-b':'build-a');}});
 await assert.rejects(loader.load('term:sem'),{name:'ContentVersionError'});
 wrong=false;const data=await loader.load('term:sem');assert.equal(data.blocks[0].html,'<p>term:sem</p>');await loader.load('term:sem');
 assert.deepEqual(seen,['/psy-stats/data/term-sem.hash.json','/psy-stats/data/term-sem.hash.json']);
});
test('explicit click overtakes queued prefetch and preserves two active slots',async()=>{
 const started=[],resolvers=[];
 const loader=createContentLoader({manifest,fetcher:url=>new Promise(resolve=>{const key=Object.keys(manifest.pages).find(k=>manifest.pages[k].payloadURL===url);started.push(key);resolvers.push(()=>resolve(response(key)));})});
 const a=loader.load('index'),b=loader.load('paths');await tick();
 const p=loader.prefetch('symbols',{}),click=loader.load('term:sem');resolvers.shift()();await tick();
 assert.deepEqual(started,['index','paths','term:sem']);resolvers.shift()();await tick();while(resolvers.length)resolvers.shift()();await Promise.all([a,b,p,click]);
});
test('unsafe blocks rejected; same-version seeded view and slow prefetch need no request',async()=>{
 let calls=0;const loader=createContentLoader({manifest,fetcher:async()=>{calls++;return {ok:true,json:async()=>({schemaVersion:2,key:'term:sem',buildHash:'build-a',payload:{blocks:[{html:'<p onclick="bad()">x</p>'}]}})};}});
 loader.seed('paths',{kind:'paths',blocks:[{id:'body',role:'body',html:'<p>paths</p>'}]});assert.equal((await loader.load('paths')).kind,'paths');
 await loader.prefetch('symbols',{saveData:true});await loader.prefetch('symbols',{effectiveType:'2g'});assert.equal(calls,0);
 await assert.rejects(loader.load('term:sem'),{name:'ContentLoadError'});
});
