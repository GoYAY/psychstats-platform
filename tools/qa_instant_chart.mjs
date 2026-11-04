import {isolatedPage,wait,args} from './native-cdp.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const options=args(),width=Number(options.width||1440),cpu=Number(options.cpu||1),base=options.url||'http://127.0.0.1:8892/';
const output=options.output||'.superpowers/sdd/2026-10-23-shared-instant-chart-integration';
const b=await isolatedPage(9296,width),requests=[],errors=[];
try{
 b.page.events.set('Network.requestWillBeSent',e=>requests.push(e.request.url));
 b.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.exception?.description||e.exceptionDetails.text));
 await b.page.send('Emulation.setCPUThrottlingRate',{rate:cpu});
 if(width<600)await b.page.send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
 await b.page.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__tasks=[];window.__shifts=[];new PerformanceObserver(l=>window.__tasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__shifts.push(...l.getEntries().filter(e=>!e.hadRecentInput).map(e=>e.value))).observe({type:'layout-shift',buffered:true});`});
 if(!options['widget-only']){
  await b.page.send('Page.navigate',{url:new URL('terms/central-tendency-and-dispersion.html',base).href});
  const figure=`document.querySelector('.plain-example-visual.illustrated-example')`;
  await b.until(`!!${figure}?.querySelector('picture img')?.naturalWidth`);
  await b.run(`${figure}.scrollIntoView({block:'center',behavior:'instant'})`);
  await wait(700);
  assert.equal(await b.run(`document.querySelector('[data-instant-chart]')===null`),true,'Preserve the accepted separate distributions, not a grouped-category widget');
  assert.equal(requests.filter(u=>/\/assets\/charts-[^/]+\//.test(u)).length,0,'This static comparison must not load the optional chart runtime');
  const performance=await b.run(`({tasks:window.__tasks,cls:window.__shifts.reduce((a,b)=>a+b,0)})`);
  const geometry=await b.run(`(()=>{const f=${figure},i=f.querySelector('img'),r=f.getBoundingClientRect();return{source:i.currentSrc,naturalWidth:i.naturalWidth,naturalHeight:i.naturalHeight,width:r.width,height:r.height}})()`);
  assert.ok(new URL(geometry.source).pathname.endsWith(width<600?'central-tendency-and-dispersion-mobile.svg':'central-tendency-and-dispersion.svg'),'Use the accepted desktop/mobile distribution layout');
  assert.equal(await b.run('document.documentElement.scrollWidth<=innerWidth+1'),true);
  const shot=await b.page.send('Page.captureScreenshot',{format:'png'});await mkdir(output,{recursive:true});await writeFile(`${output}/official-${width}-${cpu}.png`,Buffer.from(shot.data,'base64'));
  assert.equal(errors.length,0,errors.join('\n'));
  const report={mode:'official-static-comparison',width,cpu,status:'functional-pass',optionalChartRequests:0,geometry,errors,performance};await writeFile(`${output}/official-${width}-${cpu}.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
  if(options.zip){
   await b.page.send('Page.navigate',{url:new URL('library/index.html#view=list',base).href});
   await b.until(`document.querySelector('[data-library-status]')?.textContent.includes('请定期导出完整备份')`);
   const {root}=await b.page.send('DOM.getDocument'),{nodeId}=await b.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
   await b.page.send('DOM.setFileInputFiles',{nodeId,files:[path.resolve(options.zip)]});await b.until(`!!document.querySelector('dialog[open]')`);
   await b.run(`[...document.querySelectorAll('dialog button')].find(e=>e.textContent==='导入并保存').click()`);await b.until(`!document.querySelector('dialog[open]')&&!!document.querySelector('.library-card')`);
   await b.run(`document.querySelector('.library-card').click()`);await b.until(`!!document.querySelector('.personal-reader figure img')`);
   assert.equal(await b.run(`document.querySelector('.personal-reader h1').textContent`),'频数分布');
   await b.run(`document.querySelector('[data-personal-chart]').scrollIntoView({block:'center',behavior:'instant'})`);
   await b.until(`document.querySelector('[data-personal-chart]')?.dataset.chartEnhanced==='true'`);
   const ps=`document.querySelector('[data-personal-chart] [data-chart-interactive]').shadowRoot`;
   await b.until(`${ps}.querySelectorAll('g[class^="bar-series"] rect').length===4`);
   await b.run(`${ps}.querySelector('[data-category="2"]').click()`);await b.until(`${ps}.querySelector('[data-selection]').textContent.includes('68')`);
   const personalRequests=requests.length,personalPerformance=await b.run(`(async()=>{const values=[],node=document.querySelector('[data-personal-chart]'),y=node.parentElement.querySelector('figcaption').getBoundingClientRect().top+scrollY;for(let i=0;i<30;i++){const t=performance.now();${ps}.querySelector('[data-category="'+(i%4)+'"]').click();await new Promise(requestAnimationFrame);values.push(performance.now()-t)}values.sort((a,b)=>a-b);return{p95:values[28],captionShift:node.parentElement.querySelector('figcaption').getBoundingClientRect().top+scrollY-y,tasks:window.__tasks}})()`);
   assert.equal(personalPerformance.captionShift,0);assert.equal(requests.length,personalRequests);
   assert.equal(await b.run(`(()=>{const root=document.querySelector('[data-personal-chart] [data-chart-interactive]'),r=root.getBoundingClientRect(),e=root.shadowRoot.querySelector('.readout').getBoundingClientRect();return e.left>=r.left&&e.right<=r.right})()`),true,'Personal long-label tooltip stays within chart bounds');
   assert.equal(await b.run(`(()=>{const root=document.querySelector('[data-personal-chart] [data-chart-interactive]'),r=root.getBoundingClientRect(),e=root.shadowRoot.querySelector('.explanation').getBoundingClientRect();return e.bottom<=r.bottom+1})()`),true,'Personal chart explanation must not be clipped by the static image height');
   for(let i=0;i<4;i++){await b.run(`document.querySelectorAll('.quiz-option')[${i}].click()`);assert.ok((await b.run(`document.querySelector('#quiz-feedback').textContent`)).length>10);}
   await b.run(`${ps}.querySelector('[data-category="2"]').click()`);
   await b.until(`${ps}.querySelector('[data-selection]').dataset.selection==='满意'`);
   await b.run(`location.hash='#view=list'`);await b.until(`!!document.querySelector('.library-card')`);await b.run(`document.querySelector('.library-card').click()`);await b.until(`!!document.querySelector('[data-personal-chart]')`);await b.run(`document.querySelector('[data-personal-chart]').scrollIntoView({block:'center',behavior:'instant'})`);await b.until(`document.querySelector('[data-personal-chart]')?.dataset.chartEnhanced==='true'`);
   assert.equal(await b.run(`${ps}.querySelector('[data-selection]').dataset.selection`),'满意','Returning to the same revision must restore chart selection');
   assert.equal(await b.run(`document.querySelector('.quiz-option[aria-pressed=true]')?.dataset.option`),'d');
   const rapid=await b.run(`(async()=>{const base=${JSON.stringify(base)},build=await(await fetch(new URL('library-build.json',base))).json(),library=new URL('assets/'+build.moduleDirectory+'/',base);const {openLibrary}=await import(new URL('store.mjs',library)),{libraryContext}=await import(new URL('app.mjs',library)),{mountReader}=await import(new URL('reader.mjs',library)),{enhanceChart}=await import(new URL('assets/'+build.chartCoreDirectory+'/loader.mjs',base));const store=await openLibrary(await libraryContext(new URL(base),'local-library-preview'));try{const snapshot=await store.snapshot(),revision=snapshot.records.revisions[0],readerCaptures=[],officialCaptures=[];let state={selected:'d',chart:{selectedCategory:'满意'}};for(let i=0;i<2;i++){const root=document.createElement('div');document.body.append(root);let release;const pending=new Promise(r=>release=r),reader=mountReader(root,{revision,resolveAsset:()=>pending,state});state=reader.capture();readerCaptures.push(state);reader.dispose();release(null);await reader.ready;root.remove();}const data={version:1,title:'原始图表',xLabel:'分值',yLabel:'人数',note:'教学',series:[{label:'班级',points:[{category:'60',value:0}]}]};let selected={selectedCategory:'60'};for(let i=0;i<2;i++){const root=document.createElement('div');root.style.cssText='position:fixed;top:-10000px;width:500px;height:460px';document.body.append(root);const chart=enhanceChart(root,{data,moduleURL:new URL('assets/'+build.chartDirectory+'/'+build.chartEntry,base).href,state:selected});selected=chart.capture();officialCaptures.push(selected);chart.dispose();await chart.ready;root.remove();}return{readerCaptures,officialCaptures};}finally{store.close();}})()`);
   assert.deepEqual(rapid.readerCaptures,[{selected:'d',chart:{selectedCategory:'满意'}},{selected:'d',chart:{selectedCategory:'满意'}}]);assert.deepEqual(rapid.officialCaptures,[{selectedCategory:'60'},{selectedCategory:'60'}]);
   await writeFile(`${output}/rapid-state-${width}-${cpu}.json`,JSON.stringify({status:'passed',...rapid},null,2));
   const roundtrip=await b.run(`(async()=>{const base=${JSON.stringify(base)},build=await(await fetch(new URL('library-build.json',base))).json(),moduleURL=new URL('assets/'+build.moduleDirectory+'/',base);const {openLibrary}=await import(new URL('store.mjs',moduleURL)),{libraryContext}=await import(new URL('app.mjs',moduleURL)),{exportBackup,inspectBackup,planRestore}=await import(new URL('archive.mjs',moduleURL));const store=await openLibrary(await libraryContext(new URL(base),'local-library-preview'));try{const snapshot=await store.snapshot(),blob=await exportBackup(snapshot,h=>store.getBlob(h)),staged=new Map(),v=await inspectBackup(blob,{stageBlob:async(h,b)=>{staged.set(h,b);return h},discardStaged:async()=>staged.clear()}),plan=await planRestore(snapshot,v.validated);const lesson=v.validated.revisions[0].lesson;return{terms:v.validated.terms.length,newTerms:plan.writes.filter(w=>w.kind==='terms'&&!snapshot.records.terms.some(t=>t.id===w.id)).length,values:lesson.visual.payload.series[0].y,categories:lesson.visual.payload.series[0].x}}finally{store.close()}})()`);
   assert.deepEqual(roundtrip.values,[12,23,68,17]);assert.equal(roundtrip.newTerms,0);
   await b.run(`document.querySelector('[data-personal-chart]').scrollIntoView({block:'center',behavior:'instant'})`);const shot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(`${output}/personal-${width}-${cpu}.png`,Buffer.from(shot.data,'base64'));
   const personal={mode:'real-model-zip-reader',width,cpu,status:'functional-pass-performance-pending',roundtrip,interactionRequests:0,performance:personalPerformance};await writeFile(`${output}/personal-${width}-${cpu}.json`,JSON.stringify(personal,null,2));console.log(JSON.stringify(personal));
   // Real SW preparation, then reopen the imported page with the network offline.
   const hash=await b.run('location.hash');await b.run(`location.hash='#view=backup'`);await b.until(`document.querySelector('.library-content')?.innerText.includes('启用离线阅读')`);
   await b.run(`[...document.querySelectorAll('.library-content button')].find(e=>e.textContent==='启用离线阅读').click()`);
   await b.until(`document.querySelector('[data-library-status]')?.textContent.includes('离线阅读已就绪')`);
   await b.page.send('Network.setCacheDisabled',{cacheDisabled:false});await b.page.send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
   await b.page.send('Page.navigate',{url:new URL('library/index.html'+hash,base).href});
   await b.until(`!!document.querySelector('.personal-reader figure img')`);await b.run(`document.querySelector('[data-personal-chart]').scrollIntoView({block:'center',behavior:'instant'})`);await b.until(`document.querySelector('[data-personal-chart]')?.dataset.chartEnhanced==='true'`);
   await writeFile(`${output}/offline-${width}-${cpu}.json`,JSON.stringify({status:'passed',realImport:true,realServiceWorker:true,offlineReopen:true},null,2));console.log('Offline reopen passed');
  }
 }else{
 await b.page.send('Page.navigate',{url:new URL('chart_widget/qa.html',base).href});
 await b.until('!!window.chartQA');
 assert.ok(await b.run('window.chartQA.ready'),await b.run('window.chartQA.error'));
 assert.equal(await b.run('window.chartQA.readyBars'),18,'Ready must mean actual bars are painted, not an empty React root');
 const shadow=`document.querySelector('#one').shadowRoot`;
 await b.until(`${shadow}?.querySelectorAll('g[class^="bar-series"] rect').length===18`);
 const y=await b.run(`document.querySelector('#after').getBoundingClientRect().y`),before=requests.length;
 await b.run(`${shadow}.querySelector('[data-category="0"]').click()`);
 await b.until(`${shadow}.querySelector('[data-selection]').dataset.selection==='60'`);
 assert.equal(await b.run(`(()=>{const bounds=document.querySelector('#one').getBoundingClientRect(),r=${shadow}.querySelector('.readout').getBoundingClientRect();return r.left>=bounds.left&&r.right<=bounds.right})()`),true,'Tooltip stays within chart bounds');
 assert.ok(await b.run(`${shadow}.querySelector('[data-selection]').textContent.includes('0')`));
 assert.equal(await b.run(`window.chartQA.two.capture().selectedCategory`),null);
 await b.run(`${shadow}.querySelector('[data-category="0"]').click()`);
 await b.until(`window.chartQA.one.capture().selectedCategory===null`);
 await b.run(`${shadow}.querySelector('[data-category="3"]').focus()`);
 await b.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
 await b.until(`${shadow}.activeElement.dataset.category==='4'`);
 await b.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await b.page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await b.until(`window.chartQA.one.capture().selectedCategory==='80'`);
 await b.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
 await b.until(`window.chartQA.one.capture().selectedCategory===null`);
 const rect=await b.run(`(()=>{const e=${shadow}.querySelector('[data-category="2"]'),r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);
 if(width<600){await b.page.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[rect]});await b.page.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await b.until(`window.chartQA.one.capture().selectedCategory==='70'`);}
 const performance=await b.run(`(async()=>{const samples=[];for(let i=0;i<30;i++){let start=performance.now();${shadow}.querySelector('[data-category="'+(i%9)+'"]').click();await new Promise(requestAnimationFrame);samples.push(performance.now()-start)}samples.sort((a,b)=>a-b);return{p95:samples[28],tasks:window.__tasks,cls:window.__shifts.reduce((a,b)=>a+b,0)}})()`);
 assert.equal(await b.run(`document.querySelector('#after').getBoundingClientRect().y`),y);
 assert.equal(requests.length,before,'Interactions must send zero requests');
 assert.equal(await b.run('document.documentElement.scrollWidth<=innerWidth+1'),true);
 const geometry=await b.run(`${shadow}.querySelector('svg').outerHTML`);await wait(400);assert.equal(await b.run(`${shadow}.querySelector('svg').outerHTML`),geometry,'No idle playback');
 await b.run(`window.chartQA.one.update({...window.chartQA.data,series:window.chartQA.data.series.map(s=>({...s,points:s.points.slice(0,2)}))})`);
 await b.until(`window.chartQA.one.capture().selectedCategory===null`);
 await b.run('window.chartQA.controller.abort();window.chartQA.one.dispose();window.chartQA.one.dispose()');
 assert.equal(await b.run(`${shadow}.querySelector('svg')===null`),true);
 assert.equal(errors.length,0,errors.join('\n'));
 const report={mode:'widget-only',width,cpu,status:'passed',interactionRequests:0,performance};
 await mkdir(output,{recursive:true});await writeFile(`${output}/widget-${width}-${cpu}.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }
}finally{await b.close();}
