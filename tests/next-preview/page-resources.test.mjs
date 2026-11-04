import test from 'node:test';
import assert from 'node:assert/strict';
const api=await import('../../site/next-preview/lib/page-resources.mjs').catch(()=>({}));
test('page resources share module preparation and release failure for retry',async()=>{
 assert.equal(typeof api.preparePageResources,'function');let calls=0;const importModule=async()=>{calls++;if(calls===1)throw Error('offline');return {};};
 await assert.rejects(api.preparePageResources({kind:'term'},{importModule}));
 await Promise.all([api.preparePageResources({kind:'term'},{importModule}),api.preparePageResources({kind:'term'},{importModule})]);assert.equal(calls,2);
});
test('cancelled preparation cannot commit late module results',async()=>{
 assert.equal(typeof api.preparePageResources,'function');let resolve;const abort=new AbortController();
 const job=api.preparePageResources({kind:'term'},{signal:abort.signal,importModule:()=>new Promise(r=>{resolve=r})});await new Promise(r=>setTimeout(r,0));abort.abort();resolve({});
 await assert.rejects(job,{name:'AbortError'});
});
test('only the explicit first-screen subset is prepared; failed resources retry and duplicate preparation shares work',async()=>{
 const record={kind:'term',resources:['offscreen-a','offscreen-b'],firstScreenResources:[{kind:'image',url:'hero.hash.webp'}]},seen=[];let fail=true;
 const loadResource=async resource=>{seen.push(resource.url);if(fail)throw Error('image unavailable')};
 await assert.rejects(api.preparePageResources(record,{loadResource}));fail=false;await Promise.all([api.preparePageResources(record,{loadResource}),api.preparePageResources(record,{loadResource})]);assert.deepEqual(seen,['hero.hash.webp','hero.hash.webp']);
});
test('picture preparation loads only the source matching the current viewport',async()=>{
 const record={kind:'term',firstScreenResources:[{kind:'image',url:'hero-desktop.svg',sources:[{media:'(max-width:650px)',url:'hero-mobile.svg'}]}]},seen=[];
 const loadResource=async resource=>seen.push(resource.url);
 await api.preparePageResources(record,{loadResource,matchesMedia:()=>true});
 await api.preparePageResources(record,{loadResource,matchesMedia:()=>false});
 assert.deepEqual(seen,['hero-mobile.svg','hero-desktop.svg']);
});
test('formula font readiness holds preparation until fonts load and releases cancellation',async()=>{
 let release,done=false,calls=0;const controller=new AbortController();
 const record={kind:'term',formulaFonts:[{font:'italic 700 16px "KaTeX_Math"',text:'ηαξζ'}]};
 const loadFont=()=>{calls++;return new Promise(resolve=>release=resolve)};
 const job=api.preparePageResources(record,{loadFont,signal:controller.signal}).then(()=>done=true);
 await new Promise(r=>setTimeout(r,0));assert.equal(calls,1,'declared fonts must start before readiness');assert.equal(done,false);
 controller.abort();release();await assert.rejects(job,{name:'AbortError'});
});
test('font failure allows retry and pages without formulas need no font preparation',async()=>{
 let calls=0;const record={kind:'term',formulaFonts:[{font:'16px "KaTeX_Main"',text:'='}]};
 const loadFont=async()=>{if(++calls===1)throw Error('font unavailable')};
 await assert.rejects(api.preparePageResources(record,{loadFont}));
 await api.preparePageResources(record,{loadFont});await api.preparePageResources(record,{loadFont});
 await api.preparePageResources({kind:'term'},{loadFont});assert.equal(calls,2);
});
