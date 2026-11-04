import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';
import {offlineStatus,validateOfflineResources,prepareOffline} from '../../site/assets/library/offline.mjs';
test('offline availability requires verified precache, not merely saved local data',()=>{assert.equal(offlineStatus().state,'not-prepared');});
test('offline scope and resources exclude private data and other public routes',()=>{
 const scope='https://example.com/psy/library/',manifest={version:'v1',resources:[{url:'index.html',hash:'a'.repeat(64)},{url:'../assets/library-abcd/app.mjs',hash:'b'.repeat(64)}]};
 assert.equal(validateOfflineResources(manifest,scope).length,2);
 for(const url of ['../index.html','https://outside.com/a','../api/chat','../originals/paper.pdf','index.html?token=secret'])assert.throws(()=>validateOfflineResources({...manifest,resources:[{url,hash:'a'.repeat(64)}]},scope));
 assert.throws(()=>validateOfflineResources(manifest,'https://example.com/psy/'));
});
test('failed worker update preserves previous cache and never activates partial cache',async()=>{
 const path='site/library/sw.js';assert.ok(fs.existsSync(path),'Narrow offline worker missing');const events=new Map(),old=new Map([['old',{complete:true}]]),deleted=[],scope='https://example.com/psy/library/';let skipped=false;
 const code=fs.readFileSync(path,'utf8').replaceAll('__BUILD_VERSION__','new-version');
 const self={registration:{scope},addEventListener:(type,fn)=>events.set(type,fn),skipWaiting:()=>{skipped=true;},clients:{claim:async()=>{}}};
 const caches={keys:async()=>['old'],open:async key=>({match:async()=>null,put:async()=>old.set(key,{complete:false})}),delete:async key=>{deleted.push(key);old.delete(key);}};
 vm.runInNewContext(code,{self,caches,URL,Response,Request,crypto,fetch:async url=>{if(String(url).endsWith('offline-manifest.json'))return Response.json({version:'new-version',resources:[{url:'index.html',hash:'a'.repeat(64)}]});throw Error('Connection interrupted');}});
 let completion;events.get('install')({waitUntil:p=>completion=p});await assert.rejects(completion);assert.equal(old.has('old'),true);assert.equal(skipped,false);assert.ok(deleted.some(k=>k.includes('new-version')));
});
test('an unrelated registration is not replaced',async()=>{
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator'),secure=Object.getOwnPropertyDescriptor(globalThis,'isSecureContext');let registrations=0;
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{serviceWorker:{getRegistrations:async()=>[{scope:'https://example.com/psy/library/',active:{scriptURL:'https://example.com/psy/library/other.js'}}],register:async()=>{registrations++;}}}});Object.defineProperty(globalThis,'isSecureContext',{configurable:true,value:true});
 try{const result=await prepareOffline({scope:'https://example.com/psy/library/',manifest:{version:'v',resources:[]}});assert.equal(result.state,'unavailable');assert.equal(registrations,0);}finally{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else delete globalThis.navigator;if(secure)Object.defineProperty(globalThis,'isSecureContext',secure);else delete globalThis.isSecureContext;}
});
