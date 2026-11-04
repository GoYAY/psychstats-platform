import test from 'node:test';
import assert from 'node:assert/strict';
const api=await import('../../site/experiments/critical-resources-bridge.mjs').catch(()=>({}));
test('legacy preparation cannot finish before declared image and formula fonts are ready',async()=>{
 assert.equal(typeof api.installCriticalPreparation,'function');
 let releaseImage,releaseFont,ready=false;const seen=[];
 const runtime={preparePage:async()=>{seen.push('module')}};
 api.installCriticalPreparation(runtime,{matchesMedia:()=>false,loadResource:r=>{seen.push(r.url);return new Promise(resolve=>releaseImage=resolve)},loadFont:r=>{seen.push(r.font);return new Promise(resolve=>releaseFont=resolve)}});
 const doc={querySelector:()=>({textContent:JSON.stringify({firstScreenResources:[{kind:'image',url:'../assets/diagram.svg',sources:[{media:'(max-width:600px)',url:'../assets/mobile.svg'}]}],formulaFonts:[{font:'16px "KaTeX_Main"',text:'x'}]})})};
 const promise=runtime.preparePage(doc,'https://example.test/psy-stats/terms/sem.html').then(()=>ready=true);
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.deepEqual(seen,['module','https://example.test/psy-stats/assets/diagram.svg','16px "KaTeX_Main"']);
 releaseImage();await new Promise(resolve=>setTimeout(resolve,0));assert.equal(ready,false);
 releaseFont();await promise;assert.equal(ready,true);
});
test('legacy pages without critical metadata still use their existing preparation',async()=>{
 assert.equal(typeof api.installCriticalPreparation,'function');let prepared=false;
 const runtime={preparePage:async()=>{prepared=true}};
 api.installCriticalPreparation(runtime,{loadResource:()=>{throw Error('unexpected download')}});
 await runtime.preparePage({querySelector:()=>null},'https://example.test/psy-stats/paths.html');assert.equal(prepared,true);
});

test('known resource hints start images and fonts without waiting for a destination HTML document',async()=>{
 const seen=[];const runtime={preparePage:async()=>{throw Error('HTML not available yet')}};
 api.installCriticalPreparation(runtime,{loadResource:async r=>seen.push(r.url),loadFont:async r=>seen.push(r.font)});
 assert.equal(typeof runtime.prepareCriticalResources,'function','No early resource preparation API');
 await runtime.prepareCriticalResources({firstScreenResources:[{kind:'image',url:'../assets/early.svg'}],formulaFonts:[{font:'16px "KaTeX_Main"',text:'y'}]},'https://example.test/psy-stats/terms/sem.html');
 assert.deepEqual(seen,['https://example.test/psy-stats/assets/early.svg','16px "KaTeX_Main"']);
});
