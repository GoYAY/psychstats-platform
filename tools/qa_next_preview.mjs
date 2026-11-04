import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const [port='9290',base='http://127.0.0.1:8766/psy-stats/',widthArg='1440',mode='all']=process.argv.slice(2),width=Number(widthArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
let seq=0,contextId=null;const pending=new Map(),errors=[],docs=[],requests=[],otherErrors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.executionContextCreated'&&m.params.context.auxData?.isDefault)contextId=m.params.context.id;if(m.method==='Runtime.exceptionThrown')(m.params.exceptionDetails.executionContextId===contextId?errors:otherErrors).push(m.params.exceptionDetails);if(m.method==='Network.requestWillBeSent'){requests.push({url:m.params.request.url,type:m.params.type});if(m.params.type==='Document')docs.push(m.params.request.url);}const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}));});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value;};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function until(expression){for(let i=0;i<120;i++){if(await run(expression))return;await wait(100);}throw Error('Timed out: '+expression);}
async function open(route=''){await send('Page.navigate',{url:new URL(route,base).href});await until('document.readyState==="complete"&&!!document.querySelector("main")');await wait(500);}
async function click(selector){await run(`document.querySelector(${JSON.stringify(selector)}).click()`);await wait(750);}
const results=[];
// Clear only this task-owned browser's filter fixture before a scenario.
await send('Page.enable');await open();await run('sessionStorage.removeItem("next-topic-filters");const {psychFilters,...state}=history.state||{};history.replaceState(state,"")');
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 await open();await run('localStorage.setItem("psych-favorites-v1","[]");dispatchEvent(new StorageEvent("storage",{key:"psych-favorites-v1"}))');const before=docs.length;await run('window.__docProbe="keep";window.__headProbe=document.querySelector(".site-head");window.__frames=[];window.__long=[];new PerformanceObserver(l=>__long.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:"longtask",buffered:false});window.__sample=true;(()=>{let previous=0;function tick(t){if(previous)__frames.push(t-previous);previous=t;if(__sample)requestAnimationFrame(tick)}requestAnimationFrame(tick)})()');
 await click('.term-card[data-id="variable"] a[data-expand-card]');
 assert.ok(await run('location.pathname.endsWith("/terms/variable/")'),'Card opens migrated term');assert.equal(await run('window.__docProbe'),'keep');assert.equal(await run('window.__headProbe===document.querySelector(".site-head")'),true);assert.equal(docs.length,before);results.push({case:'same-document'});
 assert.ok(await run('(window.PsychNextMetrics||[]).some(m=>m.kind==="expand")'),'Card expansion animation must actually run, not only navigate');
 await click('[data-collapse-term]');assert.ok(await run('!!document.querySelector(".topic-nav")'),'Return reaches topic');results.push({case:'return'});
 if(mode==='history'){
  const setLevel=async value=>{await run(`(()=>{const s=document.getElementById('level-filter');s.value=${JSON.stringify(value)};s.dispatchEvent(new Event('change',{bubbles:true}))})()`);await wait(150);};
  await setLevel('basic');await click('[data-topic-link="structural-equation-modeling"]');await setLevel('advanced');await run('history.back()');await wait(400);
  assert.equal(await run('document.getElementById("level-filter").value'),'basic','Back restores filters belonging to that history entry');results.push({case:'history-filters'});
 }
 if(mode==='blocked-storage'){
  await run(`Storage.prototype.getItem=function(){throw Error('storage blocked')};Storage.prototype.setItem=function(){throw Error('storage blocked')}`);
  await click('.term-card[data-id="variable"] [data-favorite]');await click('.term-card[data-id="measurement-scales"] [data-favorite]');await click('[data-topic-link="favorites"]');
  assert.equal(await run('document.querySelectorAll(".term-card").length'),2,'Blocked storage keeps all favorites in page memory');results.push({case:'blocked-storage-favorites'});
 }
 if(mode==='same-route'){
  await click('[data-topic-link="structural-equation-modeling"]');await click('.site-head nav a[href="/psy-stats/"]');
  assert.equal(await run('document.getElementById("topic-title").textContent'),'心理统计基础','Header root resets topic on same pathname');
  assert.equal(await run('!!document.querySelector(".next-load-status:not([hidden])")'),false,'Same-path query navigation has no stuck load state');results.push({case:'same-route-query'});
 }
 if(mode==='geometry'){
  for(const topic of ['favorites','foundations','structural-equation-modeling']){
   const samples=await run(`new Promise(resolve=>{const a=[],start=performance.now();function tick(t){const h=document.querySelector('#topic-title').getBoundingClientRect();const nav=[...document.querySelectorAll('.site-head nav>a,.topic-nav>a')].map(e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y}});const copies=[...document.querySelectorAll('.next-outgoing .topic-intro h2')].map(e=>e.getBoundingClientRect().y);a.push({title:h.y,nav,copies});if(t-start<450)requestAnimationFrame(tick);else resolve(a)}tick(start);document.querySelector('[data-topic-link="${topic}"]').click()})`);
   assert.ok(samples.every(s=>s.nav.every((p,i)=>Math.abs(p.x-samples[0].nav[i].x)<1&&Math.abs(p.y-samples[0].nav[i].y)<1)),'Navigation labels must not jump across topic lengths');
   const copy=samples.find(s=>s.copies.length);assert.ok(copy&&copy.copies.every(y=>Math.abs(y-copy.title)<1),'Visible topic copy heading stays aligned');
  }
  await send('Emulation.setDeviceMetricsOverride',{width,height:1080,deviceScaleFactor:1,mobile:width<600});
  await click('[data-topic-link="favorites"]');
  const sample=await run(`new Promise(resolve=>{const a=[],start=performance.now();function tick(t){a.push([...document.querySelectorAll('.site-head nav>a')].map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));if(t-start<500)requestAnimationFrame(tick);else resolve(a)}tick(start);document.querySelector('.site-head nav a[href$="/paths/"]').click()})`);
  assert.ok(sample.every(s=>s.every((p,i)=>Math.abs(p.x-sample[0][i].x)<1&&Math.abs(p.y-sample[0][i].y)<1)),'Header stays fixed when scrollbars change');results.push({case:'geometry-continuity'});
 }
 if(mode==='rapid'){
  await run(`(()=>{function go(href){const a=document.createElement('a');a.href=href;document.body.append(a);a.click();a.remove()}go('/psy-stats/paths/');setTimeout(()=>go('/psy-stats/terms/sem/'),20);setTimeout(()=>go('/psy-stats/terms/variable/'),50)})()`);await wait(1000);
  assert.ok(await run('location.pathname.endsWith("/terms/variable/")&&document.querySelector(".term-content").dataset.termId==="variable"'));assert.equal(await run('document.querySelectorAll(".next-outgoing").length'),0);
  await click('[data-collapse-term]');await run(`document.querySelector('.term-card[data-id=variable] a').click()`);await wait(60);await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});await wait(450);assert.equal(await run('document.querySelectorAll(".next-outgoing").length'),0);await send('Emulation.setEmulatedMedia',{features:[]});results.push({case:'rapid-and-reduced'});
 }
 if(mode==='all'){
  await click('[data-topic-link="structural-equation-modeling"]');assert.equal(await run('document.querySelector("#topic-title").textContent'),'结构方程');
  await click('.term-card[data-id="sem"] a[data-expand-card]');assert.ok(await run('location.pathname.endsWith("/terms/sem/")'));assert.ok(await run('!!document.querySelector(".formula-key")'));
  await click('.formula-key');assert.equal(await run('document.querySelector(".formula-key").getAttribute("aria-pressed")'),'true');await click('.formula-key');assert.equal(await run('document.querySelector(".formula-row").classList.contains("is-pinned")'),false);
  await click('.quiz [data-idx="0"]');assert.equal(await run(`document.querySelector('.quiz [data-idx="0"]').nextElementSibling.hidden`),false);results.push({case:'formula-and-quiz'});
  await click('[data-favorite]');assert.equal(await run('JSON.parse(localStorage.getItem("psych-favorites-v1")||"[]").includes("sem")'),true);results.push({case:'term-favorite'});
  await run(`(()=>{const input=document.getElementById('q');input.focus();const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(input,'结构方程');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);await wait(400);assert.ok(await run('document.querySelectorAll("#search-results a").length>0'));
  await run(`(()=>{const scope=document.getElementById('search-scope');scope.value='page';scope.dispatchEvent(new Event('change',{bubbles:true}));const input=document.getElementById('q');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'潜变量');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);await wait(400);assert.ok(await run('document.querySelectorAll("mark.page-find-mark").length>0'));results.push({case:'global-and-page-search'});
  await run(`document.activeElement?.blur();document.getElementById('q').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`);
  await click('.site-head nav a[href$="/paths/"]');assert.ok(await run('document.querySelector("h1").textContent.includes("学习导图")'));await click('.site-head nav a[href="/psy-stats/"]');results.push({case:'header-paths'});
  await click('[data-topic-link="favorites"]');assert.ok(await run('!!document.querySelector(".term-card[data-id=sem]")'));
  await send('Page.reload');await until('document.readyState==="complete"&&document.querySelector("#topic-title")?.textContent==="收藏"');results.push({case:'favorites-query-refresh'});
  await run('history.back()');await wait(600);assert.equal(await run('document.querySelectorAll(".next-outgoing").length'),0);
 }
 assert.ok(await run('document.documentElement.scrollWidth<=innerWidth'),'No horizontal overflow');assert.deepEqual(errors,[]);
 const performance=await run('({frames:window.__frames||[],long:window.__long||[],metrics:window.PsychNextMetrics||[],outgoing:document.querySelectorAll(".next-outgoing").length})');assert.equal(performance.outgoing,0);
 const output={width,mode,results,performance,errors,otherErrors,documents:docs,requests};await writeFile(`logs/next-preview-qa-${width}-${mode}.json`,JSON.stringify(output,null,2));console.log(JSON.stringify({width,results,errors,metrics:performance.metrics,otherErrorContexts:otherErrors.map(e=>e.executionContextId)}));
}finally{await writeFile(`logs/next-preview-errors-${width}.json`,JSON.stringify(errors,null,2));const screenshot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/next-preview-${width}.png`,Buffer.from(screenshot.data,'base64'));ws.close();}
