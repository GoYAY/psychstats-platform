import assert from 'node:assert/strict';
import test from 'node:test';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const policy = require('../../site/assets/navigation-policy.js');
const root = 'https://example.test/psy-stats/';
const current = root + 'index.html';
test('navigation respects browser semantics and site boundaries', () => {
  const click = {button:0};
  const link = {href:root+'terms/p-value.html'};
  assert.equal(policy.shouldHandle(link,click,current,root),true);
  for (const change of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1},{defaultPrevented:true}])
    assert.equal(policy.shouldHandle(link,{...click,...change},current,root),false);
  for (const change of [{download:true},{target:'_blank'},{href:'https://outside.test/a.html'},
    {href:current+'#heading'},{href:current+'?topic=regression'}, {href:root+'assets/a.csv'},
    {href:'https://example.test/outside/index.html'},{href:'file:///C:/index.html'}])
    assert.equal(policy.shouldHandle({...link,...change},click,current,root),false);
  assert.equal(policy.shouldHandle({href:root+'terms/p-value.html#formula'},click,current,root),true);
});
test('relative URLs resolve in target document directory', () => {
  assert.equal(policy.sameLibraryDocument(root+'library/index.html#term=a',root+'library/index.html#term=b',root),true);
  assert.equal(policy.sameLibraryDocument(root+'paths.html',root+'library/index.html#term=b',root),false);
  assert.equal(policy.shouldHandle({href:root+'library/index.html'},{button:0},current,root),true);
  assert.equal(policy.shouldHandle({href:root+'library/secret.html'},{button:0},current,root),false);
  assert.equal(policy.resolveURL('../assets/a.svg',root+'terms/a.html'),root+'assets/a.svg');
});
test('LRU stores at most twelve documents and touches on get', () => {
  const cache = policy.createCache(12);
  for(let i=0;i<12;i++) cache.set(String(i),i);
  assert.equal(cache.get('0'),0); cache.set('12',12);
  assert.equal(cache.size,12); assert.equal(cache.get('1'),undefined);
  assert.equal(cache.get('0'),0); cache.clear(); assert.equal(cache.size,0);
});
test('prefetch deduplicates and bounds concurrency at two', async () => {
  let active=0, peak=0; const seen=[], releases=[];
  const q=policy.createPrefetchQueue({allowed:()=>true,load:async url=>{
    seen.push(url); peak=Math.max(peak,++active);
    await new Promise(resolve=>releases.push(resolve)); active--;
  }});
  q.enqueue('a');q.enqueue('a');q.enqueue('b');q.enqueue('c');
  await new Promise(resolve=>setImmediate(resolve)); assert.equal(peak,2);
  releases.splice(0).forEach(fn=>fn()); await new Promise(resolve=>setImmediate(resolve));
  releases.splice(0).forEach(fn=>fn()); await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(seen,['a','b','c']);assert.equal(peak,2);
});
test('disabled network policy and cancelled pending jobs never load', async () => {
  let count=0;const q=policy.createPrefetchQueue({allowed:()=>false,load:()=>count++});
  q.enqueue('a'); await new Promise(resolve=>setImmediate(resolve));assert.equal(count,0);
});

test('visible destination overtakes queued background links without exceeding two active jobs',async()=>{
  const seen=[],releases=[];let active=0,peak=0;
  const q=policy.createPrefetchQueue({allowed:()=>true,maxConcurrent:2,load:async url=>{
    seen.push(url);peak=Math.max(peak,++active);await new Promise(resolve=>releases.push(resolve));active--;
  }});
  q.enqueue('busy-a');q.enqueue('busy-b');q.enqueue('background');q.enqueue('visible',10);
  await new Promise(resolve=>setImmediate(resolve));releases.shift()();
  await new Promise(resolve=>setImmediate(resolve));
  const actual=seen.slice();releases.splice(0).forEach(fn=>fn());await new Promise(resolve=>setImmediate(resolve));releases.splice(0).forEach(fn=>fn());
  assert.deepEqual(actual,['busy-a','busy-b','visible']);assert.equal(peak,2);
});

test('completed or failed prefetch can be retried after its consumer cache is evicted',async()=>{
  let calls=0;const q=policy.createPrefetchQueue({allowed:()=>true,load:async()=>{calls++;if(calls===1)throw Error('network');}});
  q.enqueue('same');await new Promise(resolve=>setImmediate(resolve));
  q.enqueue('same');await new Promise(resolve=>setImmediate(resolve));
  q.enqueue('same');await new Promise(resolve=>setImmediate(resolve));assert.equal(calls,3);
});

test('pending work is bounded and queued duplicate intent promotes one existing job',async()=>{
  const seen=[],releases=[];
  const q=policy.createPrefetchQueue({allowed:()=>true,maxConcurrent:1,maxPending:2,load:async url=>{
    seen.push(url);await new Promise(resolve=>releases.push(resolve));
  }});
  q.enqueue('active');q.enqueue('old');q.enqueue('promoted');q.enqueue('promoted',20);q.enqueue('dropped');
  await new Promise(resolve=>setImmediate(resolve));releases.shift()();
  await new Promise(resolve=>setImmediate(resolve));releases.shift()();
  await new Promise(resolve=>setImmediate(resolve));releases.shift()();
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(seen,['active','promoted','old']);
});
test('page runtime releases listeners, cleanup, and late callbacks', () => {
  const events=new EventTarget();let calls=0, disposed=0, ctx;
  const win={document:{readyState:'loading',addEventListener(){}},location:{href:current}};
  vm.runInNewContext(fs.readFileSync(new URL('../../site/assets/page-runtime.js',import.meta.url),'utf8'),
    {window:win,document:win.document,URL,AbortController,console});
  const runtime=win.PsychPageRuntime;
  runtime.register('probe',c=>{ctx=c;c.on(events,'probe',()=>calls++);c.deferCleanup(()=>disposed++);return {capture:()=>({value:7})};});
  runtime.mountPage({main:{},url:current,siteRoot:root,state:{}});
  events.dispatchEvent(new Event('probe')); assert.equal(calls,1);
  assert.equal(runtime.capturePage().probe.value,7);
  runtime.unmountPage();events.dispatchEvent(new Event('probe'));assert.equal(calls,1);
  assert.equal(ctx.alive(),false);assert.equal(ctx.signal.aborted,true);assert.equal(disposed,1);
  runtime.mountPage({main:{},url:current,siteRoot:root,state:{}});
  events.dispatchEvent(new Event('probe'));assert.equal(calls,2);
});
test('favorites unsubscribe releases an actual subscriber', () => {
  const storage=new Map(); const win={localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},addEventListener(){}};
  vm.runInNewContext(fs.readFileSync(new URL('../../site/assets/favorites.js',import.meta.url),'utf8'),{window:win,Set,JSON});
  let calls=0;const off=win.PsychFavorites.subscribe(()=>calls++);
  win.PsychFavorites.toggle('variable');off();off();win.PsychFavorites.toggle('variable');assert.equal(calls,1);
});
test('a failing mount also releases its partially bound listeners', () => {
  const events=new EventTarget();let calls=0;
  const win={document:{readyState:'loading',addEventListener(){}},location:{href:current}};
  vm.runInNewContext(fs.readFileSync(new URL('../../site/assets/page-runtime.js',import.meta.url),'utf8'),{window:win,document:win.document,URL,AbortController,console});
  win.PsychPageRuntime.register('broken',ctx=>{ctx.on(events,'probe',()=>calls++);throw Error('broken');});
  assert.throws(()=>win.PsychPageRuntime.mountPage({main:{},url:current,siteRoot:root}));
  events.dispatchEvent(new Event('probe'));assert.equal(calls,0);
});
