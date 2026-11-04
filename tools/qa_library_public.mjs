import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,args,wait} from './native-cdp.mjs';
const opts=args(),b=await isolatedPage(9296),reports=[];
const url='http://127.0.0.1:8773/psy-stats/library/index.html';
try{
 await b.page.send('Page.navigate',{url:url+'#view=network'});await b.until('!!document.querySelector("[data-framework-select]")');
 await b.run(`window.publicSnapshot=async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{libraryContext}=await import('/psy-stats/assets/library/app.mjs');const store=await openLibrary(await libraryContext(new URL('/psy-stats/',location.origin),'local-library-preview'));try{return JSON.stringify(await store.snapshot());}finally{store.close();}};window.beforePublic=publicSnapshot();`);
 if(opts.scenario==='legacy'){
  await b.run(`(async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{libraryContext}=await import('/psy-stats/assets/library/app.mjs'),{defaultGraphView}=await import('/psy-stats/assets/library/graph-commands.mjs');const store=await openLibrary(await libraryContext(new URL('/psy-stats/',location.origin),'local-library-preview'));try{const s=await store.snapshot(),v=defaultGraphView('legacy-only','factor-analysis');await store.commit({writes:[{kind:'graphViews',id:v.id,value:v}],deletes:[],blobRefs:[],impact:[]},{expectedVersion:s.version});}finally{store.close();}window.beforePublic=await publicSnapshot();location.hash='view=network&framework=official:regression';})()`);
  await b.until(`document.querySelector('[data-framework-select]')?.value==='official:regression'`);
  assert.equal(await b.run('publicSnapshot()'),await b.run('beforePublic'),'Official browsing must not migrate legacy private views');
 }else if(opts.scenario!=='guide'){
  const ids=await b.run(`([...document.querySelector('[data-framework-select]').options].filter(o=>o.value.startsWith('official:')).map(o=>o.value))`);
  assert.equal(ids.length,10,'All ten public networks must be directly available');
  for(const id of ids){
   await b.run(`(()=>{const n=document.querySelector('[data-framework-select]');n.value=${JSON.stringify(id)};n.dispatchEvent(new Event('change'));})()`);
   await b.until(`new URLSearchParams(location.hash.slice(1)).get('framework')===${JSON.stringify(id)}&&!!document.querySelector('.canvas-node[aria-selected=true]')`);
   const count=await b.run(`document.querySelectorAll('[data-member-key]').length`);assert.ok(count>0,id);
   assert.ok(await b.run(`document.querySelectorAll('.canvas-edge').length>0`),id+' must demonstrate relationships');
   assert.ok(await b.run(`document.querySelector('[data-canvas-action=connect]').disabled`),'Public networks must not offer live relation editing');
   await b.run(`document.querySelector('[data-canvas-action=zoom-in]').click()`);await wait(80);
   assert.equal(await b.run('publicSnapshot()'),await b.run('beforePublic'),'Public viewing must not write personal records');reports.push({id,count});
   if(id==='official:regression')for(const width of [1440,390]){await b.page.send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});await wait(100);await mkdir('logs/library-public',{recursive:true});const shot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/library-public/network-${width}.png`,Buffer.from(shot.data,'base64'));}await b.page.send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  }
  await b.page.send('Page.reload');await b.until('!!document.querySelector("[data-framework-select]")');
 await b.run(`window.publicSnapshot=async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{libraryContext}=await import('/psy-stats/assets/library/app.mjs');const store=await openLibrary(await libraryContext(new URL('/psy-stats/',location.origin),'local-library-preview'));try{return JSON.stringify(await store.snapshot());}finally{store.close();}};window.beforePublic=publicSnapshot();`);
  assert.ok(await b.run(`new URLSearchParams(location.hash.slice(1)).get('framework').startsWith('official:')`));
  const publicSelected=await b.run(`document.querySelector('.canvas-node[aria-selected=true]').dataset.nodeKey`);
  await b.run(`document.querySelector('.canvas-detail button').click()`);await b.until('!!document.querySelector(".library-canvas-backlink")');await b.run(`document.querySelector('.library-canvas-backlink').click()`);
  await b.until(`document.querySelector('.canvas-node[aria-selected=true]')?.dataset.nodeKey===${JSON.stringify(publicSelected)}`);assert.ok(await b.run(`document.querySelector('[data-canvas-action=connect]').disabled`),'Public reading return retains read-only state');
  await b.run(`document.querySelector('[data-sidebar-tab=frameworks]').click();[...document.querySelectorAll('.framework-sidebar button')].find(n=>n.textContent==='创建个人副本（免费）').click()`);
  await b.until(`!!document.querySelector('[data-framework-select]')&&!document.querySelector('[data-framework-select]').value.startsWith('official:')`);
  assert.equal(await b.run(`document.querySelector('[data-canvas-action=connect]').disabled`),false,'Personal copy must be editable');
  assert.ok(await b.run(`document.querySelector('[data-framework-note]')`),'Personal copy permits manual additions');
  const saved=await b.run(`(async()=>{const s=JSON.parse(await publicSnapshot());return {frameworks:s.records.frameworks.length,views:s.records.graphViews.length,terms:s.records.terms.length};})()`);
  assert.deepEqual(saved,{frameworks:1,views:0,terms:0},'Copy creates one frame without importing fake personal lessons');
  const selected=await b.run(`document.querySelector('.canvas-node[aria-selected=true]').dataset.nodeKey`);
  await b.run(`document.querySelector('.canvas-node[aria-selected=true]').focus()`);await b.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight'});await b.page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight'});
  await b.until(`publicSnapshot().then(v=>JSON.parse(v).records.graphViews.length===1)`);
  await b.run(`document.querySelector('.canvas-detail button').click()`);await b.until('!!document.querySelector(".library-canvas-backlink")');await b.run(`document.querySelector('.library-canvas-backlink').click()`);await b.until(`document.querySelector('.canvas-node[aria-selected=true]')?.dataset.nodeKey===${JSON.stringify(selected)}`);
 }
 await b.run(`location.hash='view=guide'`);await b.until('!!document.querySelector(".library-guide")');
 assert.equal(await b.run(`document.querySelector('.library-tabs a[aria-current=page]').textContent`),'使用指南');
 const links=await b.run(`[...document.querySelectorAll('.library-guide [data-guide-page]')].map(a=>a.getAttribute('href'))`);
 assert.deepEqual(links,['#view=list','#view=works','#view=network','#view=trash','#view=backup']);
 for(const [width,height] of [[1440,900],[390,900],[844,390]]){
  await b.page.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});await wait(100);
  assert.ok(await b.run(`document.documentElement.scrollWidth<=innerWidth+1`),'Guide must not introduce horizontal overflow');
  const shot=await b.page.send('Page.captureScreenshot',{format:'png'});await mkdir('logs/library-public',{recursive:true});await writeFile(`logs/library-public/guide-${width}.png`,Buffer.from(shot.data,'base64'));
 }
 // Follow guide links through real mounted routes, including browser return.
 for(const href of links){await b.run(`document.querySelector('.library-guide a[href="${href}"]').click()`);await b.until(`!!document.querySelector('.library-tabs a[aria-current=page][href="${href}"]')`);await b.run(`history.back()`);await b.until('!!document.querySelector(".library-guide")');}
 await b.run(`document.querySelector('.guide-access a').click()`);await b.until('!!document.querySelector("[data-framework-select]")');assert.ok(await b.run(`document.querySelector('[data-framework-select]').value.startsWith('official:')`),'Official guide CTA must not reopen a personal frame');
 console.log(JSON.stringify({status:'passed',frameworks:reports,guideLinks:links.length,providerCalls:0}));
 await mkdir('logs/library-public',{recursive:true});await writeFile('logs/library-public/result.json',JSON.stringify({status:'passed',frameworks:reports,guideLinks:links.length,providerCalls:0},null,2));
}finally{await b.close();}
