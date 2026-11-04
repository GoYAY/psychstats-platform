// Controlled same-page baseline. Blocks only the optional bridge, never a product flag.
import {isolatedPage,args,wait} from './native-cdp.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const o=args(),base=o.url||'http://127.0.0.1:8892/site/instant-chart-preview/',rows=[];
for(const width of [1440,390])for(let round=0;round<3;round++)for(const enhanced of [false,true]){
 const b=await isolatedPage(9296,width);
 try{
  await b.page.send('Emulation.setCPUThrottlingRate',{rate:width===390?4:1});
  if(!enhanced)await b.page.send('Network.setBlockedURLs',{urls:['*assets/chart-runtime.js*']});
  await b.page.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__tasks=[];window.__shifts=[];new PerformanceObserver(l=>window.__tasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__shifts.push(...l.getEntries().filter(e=>!e.hadRecentInput).map(e=>e.value))).observe({type:'layout-shift',buffered:true});`});
  await b.page.send('Page.navigate',{url:new URL('terms/central-tendency-and-dispersion.html',base).href});
  await b.until(`document.readyState==='complete'&&!!document.querySelector('[data-instant-chart]')`);
  await b.run(`document.querySelector('[data-instant-chart]').scrollIntoView({block:'center',behavior:'instant'})`);
  if(enhanced)await b.until(`document.querySelector('[data-instant-chart]')?.dataset.chartEnhanced==='true'`);
  await wait(800);
  const result=await b.run(`({tasks:window.__tasks,cls:window.__shifts.reduce((a,b)=>a+b,0),measures:performance.getEntriesByType('measure').filter(e=>e.name.startsWith('psych-chart-')).map(e=>({name:e.name,start:e.startTime,duration:e.duration})),navigation:performance.getEntriesByType('navigation').map(n=>({dcl:n.domContentLoadedEventEnd,load:n.loadEventEnd}))})`);
  const row={width,cpu:width===390?4:1,round,enhanced,...result};
  if(enhanced){
   await b.run(`document.querySelector('[data-chart-interactive]').shadowRoot.querySelector('[data-category="0"]').click()`);
   const moduleRequests=await b.run(`performance.getEntriesByType('resource').filter(r=>r.name.includes('/widget-')).length`);
   await b.run(`[...document.querySelectorAll('nav[aria-label="主导航"] a')].find(a=>a.href.endsWith('/paths.html')).click()`);await b.until(`location.pathname.endsWith('/paths.html')&&!document.querySelector('[data-instant-chart]')`);
   await b.run('history.back()');await b.until(`location.pathname.endsWith('/central-tendency-and-dispersion.html')&&!!document.querySelector('[data-instant-chart]')`);await b.run(`document.querySelector('[data-instant-chart]').scrollIntoView({block:'center',behavior:'instant'})`);await b.until(`document.querySelector('[data-instant-chart]')?.dataset.chartEnhanced==='true'`);
   assert.equal(await b.run(`document.querySelector('[data-chart-interactive]').shadowRoot.querySelector('[data-selection]').dataset.selection`),'60');
   assert.equal(await b.run(`performance.getEntriesByType('resource').filter(r=>r.name.includes('/widget-')).length`),moduleRequests);
   row.remount=await b.run(`performance.getEntriesByName('psych-chart-mount').map(e=>e.duration)`);row.softReturnRestoresSelection=true;
  }
  rows.push(row);console.log(JSON.stringify({width,round,enhanced,maxTask:Math.max(0,...row.tasks.map(e=>e.duration)),measures:row.measures}));
 }catch(error){console.error(JSON.stringify({width,round,enhanced,diagnostic:await b.run(`({url:location.href,frame:document.querySelector('[data-instant-chart]')?.outerHTML.slice(0,1800),state:window.PsychPageRuntime?.capturePage(),measures:performance.getEntriesByType('measure').filter(e=>e.name.startsWith('psych-chart')).map(e=>({name:e.name,duration:e.duration}))})`)}));throw error;}finally{await b.close();}
}
const gate=rows.filter(r=>r.enhanced&&r.width===390).every(r=>r.tasks.filter(t=>r.measures.some(m=>t.start>=m.start&&t.start<m.start+m.duration)).length===0);
await writeFile('.superpowers/sdd/2026-10-23-shared-instant-chart-integration/controlled-performance.json',JSON.stringify({rows,chartWindowLongTaskGatePassed:gate,scope:'Fresh isolated browser contexts; local HTTP; not an iPhone or deployed-site result'},null,2));
console.log(JSON.stringify({chartWindowLongTaskGatePassed:gate}));
