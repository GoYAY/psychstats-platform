import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
const [port='9290',base='http://127.0.0.1:8765/psy-stats/',mode='all',widthArg='1440']=process.argv.slice(2);
const width=Number(widthArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(resolve=>ws.onopen=resolve);
let seq=0,contextId=null;const tasks=new Map(),errors=[],documents=[],requests=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);
  if(m.method==='Runtime.executionContextCreated'&&m.params.context.auxData?.isDefault)contextId=m.params.context.id;
  if(m.method==='Runtime.exceptionThrown'&&m.params.exceptionDetails.executionContextId===contextId)errors.push(m.params.exceptionDetails);
  if(m.method==='Network.requestWillBeSent'&&m.params.type==='Document')documents.push(m.params.request.url);
  if(m.method==='Network.requestWillBeSent')requests.push({url:m.params.request.url,type:m.params.type});
  const task=tasks.get(m.id);if(task){tasks.delete(m.id);m.error?task.reject(m.error):task.resolve(m.result);}
};
const send=(method,params={})=>new Promise((resolve,reject)=>{tasks.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}));});
const run=async expression=>{const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!result.exceptionDetails,result.exceptionDetails?.exception?.description);return result.result.value;};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(expression){for(let i=0;i<100;i++){if(await run(expression))return;await wait(100);}throw Error('Timeout: '+expression);}
async function open(path){const url=new URL(path,base).href;await send('Page.navigate',{url});await until(`location.href===${JSON.stringify(url)}&&document.readyState==="complete"`);await wait(200);}
async function click(selector){await run(`document.querySelector(${JSON.stringify(selector)}).click()`);await wait(600);}
async function nav(path,options={}){assert.equal(await run(`PsychSoftNavigation.navigate(${JSON.stringify(new URL(path,base).href)},${JSON.stringify(options)})`),true);}
const results=[],injections=[];
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
 await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 errors.length=0;await open('index.html'); const before=documents.length;
 await run('window.__documentProbe="retained";window.__headerProbe=document.querySelector(".site-head")');
 await run('document.querySelector(".term-card:not([hidden]) a[data-expand-card]").focus()');
 await run(`window.__qaFrames=[];window.__qaSampling=true;(()=>{let last=0;function frame(time){if(last&&window.PsychSoftMotion?.running){window.__qaFrames.push(time-last);if(__qaFrames.length>300)__qaFrames.shift()}last=time;if(__qaSampling)requestAnimationFrame(frame)}requestAnimationFrame(frame)})()`);
 await click('.term-card:not([hidden]) a[data-expand-card]');
 assert.equal(await run('window.__documentProbe'),'retained','Term card must preserve the document');
 assert.equal(documents.length,before,'No top-level Document request on normal navigation');
 assert.equal(await run('window.__headerProbe===document.querySelector(".site-head")'),true);
 results.push({case:'document-retained',documentRequests:documents.length-before});
 await click('[data-collapse-term]');
 assert.ok(await run('document.activeElement.matches(".term-card a[data-expand-card]")'),'Return restores keyboard focus to the originating card');
 if(mode==='baseline') {console.log(JSON.stringify(results));}
 else if(mode==='continuity-topic') {
  await open('index.html?topic=foundations');
  for(const topic of ['hypothesis-testing','favorites','foundations']){
   const data=await run(`new Promise(resolve=>{const a=[],start=performance.now();function sample(t){const live=document.querySelector('body>main .topic-intro h2').getBoundingClientRect();const links=[...document.querySelectorAll('body>main .topic-nav a')].map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y}));const copies=[...document.querySelectorAll('.soft-outgoing-layer .topic-intro h2')].map(e=>({y:e.getBoundingClientRect().y}));a.push({links,liveY:live.y,copies});if(t-start<400)requestAnimationFrame(sample);else resolve(a)}sample(start);document.querySelector('[data-topic-link="${topic}"]').click()})`);
   const copy=data.find(s=>s.copies.length);
   assert.ok(copy&&copy.copies.every(c=>Math.abs(c.y-copy.liveY)<1),'Topic animation copy must align with its live heading');
   assert.ok(data.every(s=>s.links.every((link,i)=>Math.abs(link.x-data[0].links[i].x)<1&&Math.abs(link.y-data[0].links[i].y)<1)),'Topic selectors stay fixed across short and long topic content');
  }
  assert.deepEqual(errors,[]);console.log('topic heading and selector continuity passed');
 }
 else if(mode==='continuity-header') {
  await send('Emulation.setDeviceMetricsOverride',{width,height:1080,deviceScaleFactor:1,mobile:width<600});
  for(const from of ['practice.html','index.html?topic=favorites','symbols.html']){
   await nav(from);
   const data=await run(`new Promise(resolve=>{const a=[],start=performance.now();function sample(t){const links=[...document.querySelectorAll('.site-head nav a')].map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y}));const p=document.querySelector('.nav-motion-indicator').getBoundingClientRect();a.push({links,pill:{x:p.x,y:p.y}});if(t-start<650)requestAnimationFrame(sample);else resolve(a)}sample(start);void PsychSoftNavigation.navigate(new URL('paths.html',PsychSoftNavigation.siteRoot).href)})`);
   assert.ok(data.every(s=>s.links.every((link,i)=>Math.abs(link.x-data[0].links[i].x)<1&&Math.abs(link.y-data[0].links[i].y)<1)),'Header labels stay fixed when entering learning paths');
   const direction=Math.sign(data.at(-1).pill.x-data[0].pill.x);
   assert.ok(data.slice(1).every((s,i)=>(s.pill.x-data[i].pill.x)*direction>=-1),'Header shadow moves continuously toward learning paths');
  }
  assert.deepEqual(errors,[]);console.log('learning paths header continuity passed');
 }
 else if(mode==='geometry') {
  await nav('terms/simple-linear-regression.html');
  await run(`void PsychSoftNavigation.navigate(new URL('terms/intercept.html',PsychSoftNavigation.siteRoot).href,{motion:'slide'})`);await wait(100);
  const mid=await run(`document.querySelector('.sequence-next').getBoundingClientRect().toJSON()`);
  await wait(500);const end=await run(`document.querySelector('.sequence-next').getBoundingClientRect().toJSON()`);
  assert.ok(Math.abs(mid.y-end.y)<2&&Math.abs(mid.x-end.x)<2,'Desktop fixed term controls stay anchored during page motion');
  assert.ok(await run(`!!document.querySelector('body>main .term-sequence')&&!document.querySelector('.soft-sequence-portal')`));
  assert.deepEqual(errors,[]);console.log('fixed navigation geometry passed');
 }
 else if(mode==='stability') {
  await open('index.html?topic=foundations');
  const samples=await run(`new Promise(resolve=>{const out=[];const start=performance.now();function frame(t){const c=document.querySelector('.term-card:not([hidden])');if(c)out.push({id:c.dataset.id,height:c.getBoundingClientRect().height});if(t-start<500)requestAnimationFrame(frame);else resolve(out)}requestAnimationFrame(frame);document.querySelector('[data-topic-link="group-comparisons"]').click()})`);
  const heights=samples.filter(s=>s.id===samples.at(-1).id).map(s=>s.height);
  assert.ok(Math.max(...heights)-Math.min(...heights)<1,'Visible cards must not jump between placeholder and real height');
  await nav('paths.html');await run(`void PsychSoftNavigation.navigate(new URL('datasets.html',PsychSoftNavigation.siteRoot).href)`);await wait(80);
  assert.ok(await run(`document.querySelector('.nav-motion-indicator').getAnimations().some(a=>a.playState==='running')`),'Header shadow continues to move with live labels');
  await wait(500);assert.deepEqual(errors,[]);console.log('stable card geometry and live navigation passed');
 }
 else if(mode==='rapid') {
  await nav('sources.html');await nav('index.html');
  await run(`window.__motionOriginal=PsychSoftMotion.transition;window.__raceOnce=true;PsychSoftMotion.transition=options=>{const result=__motionOriginal(options);if(__raceOnce){__raceOnce=false;queueMicrotask(()=>{window.__raceB=PsychSoftNavigation.navigate(new URL('datasets.html',PsychSoftNavigation.siteRoot).href)})}return result};window.__raceA=PsychSoftNavigation.navigate(new URL('sources.html',PsychSoftNavigation.siteRoot).href);void 0`);
  await until('!!window.__raceB');await run('window.__raceB');assert.equal(await run('window.__raceA'),false);await wait(300);
  assert.ok(await run('location.pathname.endsWith("/datasets.html")&&!document.querySelector(".soft-outgoing-layer")&&!PsychSoftMotion.running'));
  assert.deepEqual(errors,[]);console.log('rapid animation cancellation passed');
 }
 else if(mode==='header-labels') {
  await nav('paths.html');await run(`void PsychSoftNavigation.navigate(new URL('datasets.html',PsychSoftNavigation.siteRoot).href)`);await wait(100);
  assert.ok(await run(`(()=>{const link=document.querySelector('.site-head nav a[aria-current="page"]'),pill=document.querySelector('.nav-motion-indicator');return Number(getComputedStyle(link).zIndex)>Number(getComputedStyle(pill).zIndex)&&link.getBoundingClientRect().width<150})()`),'Navigation labels stay above the moving shadow');
  await wait(500);assert.deepEqual(errors,[]);console.log('header labels passed');
 }
 else if(mode==='cursor') {
  const injected=await send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__matchMedia=window.matchMedia;window.matchMedia=q=>q.includes('(hover: hover)')?{matches:true}:__matchMedia(q)`});
  injections.push(injected.identifier);
  await open('index.html');await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:200,y:240});
  assert.ok(await run('!!document.querySelector(".cursor-dot:not([hidden])")'));
  await run(`void PsychSoftNavigation.navigate(new URL('datasets.html',PsychSoftNavigation.siteRoot).href)`);await wait(100);
  const before=await run(`document.querySelector('.cursor-dot').getBoundingClientRect().x`);
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:260,y:260});await wait(20);
  const after=await run(`document.querySelector('.cursor-dot').getBoundingClientRect().x`);
  assert.ok(after-before>50,'Cursor continues to follow the mouse while the page emerges');
  await wait(500);await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:injected.identifier});assert.deepEqual(errors,[]);console.log('live cursor passed');
 }
 else if(mode==='reduce-change') {
  await nav('index.html');
  await run(`window.__pending=PsychSoftNavigation.navigate(new URL('sources.html?reduce-change',PsychSoftNavigation.siteRoot).href);void 0`);
  await until('PsychSoftMotion.running');await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await run('window.__pending');assert.ok(await run('location.pathname.endsWith("/sources.html")'),'Changing motion preference still commits the prepared destination');
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});console.log('mid-flight reduce change passed');
 }
 else if(mode==='legacy') {
  await nav('terms/variable.html');
  const injected=await send('Page.addScriptToEvaluateOnNewDocument',{source:`document.addEventListener('DOMContentLoaded',()=>{window.__legacyAtBoot=document.documentElement.classList.contains('term-transition-pending')},{once:true})`});
  injections.push(injected.identifier);
  await run(`sessionStorage.setItem('psychstats.card-transition.v1',JSON.stringify({href:location.href,time:Date.now(),width:innerWidth,height:innerHeight,direction:'expand',html:'<main><p>obsolete snapshot</p></main>',styles:[]}))`);
  await send('Page.reload');await until('document.readyState==="complete"&&typeof window.__legacyAtBoot==="boolean"');
  assert.equal(await run('window.__legacyAtBoot'),false,'HTTP ignores obsolete multi-document snapshots');
  await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:injected.identifier});console.log('legacy HTTP snapshot ignored');
 }
 else if(mode==='visual') {
  await mkdir('logs',{recursive:true});
  for(const [selector,file] of [['.term-card:not([hidden]) a[data-expand-card]','soft-expand-mid.png'],['[data-collapse-term]','soft-collapse-mid.png']]){
   await run(`document.querySelector(${JSON.stringify(selector)}).click();void 0`);await wait(120);
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/'+file,Buffer.from(shot.data,'base64'));await wait(500);
  }
  await nav('paths.html');await run(`document.querySelector('.site-head nav a[href="${new URL('datasets.html',base).href}"]').click();void 0`);await wait(100);
  const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/soft-header-mid.png',Buffer.from(shot.data,'base64'));await wait(500);
  assert.deepEqual(errors,[]);console.log('visual snapshots captured');
 }
 else if(mode==='deep') {
  await open('terms/sem.html');const count=documents.length;await run('window.__deepProbe=true');
  await click(`.site-head nav a[href="${new URL('symbols.html',base).href}"]`);
  assert.ok(await run('!!document.querySelector("#symbol-query")'));
  await nav('analysis.html');await click('.analysis-card[data-analysis-id="sem"]');
  assert.ok(await run('!!document.querySelector("[data-analysis-field]")'));
  const paths=await run(`(async()=>{const nodes=[...document.querySelectorAll('main img[src],main a[download]')];const bad=[];for(const node of nodes){const url=new URL(node.src||node.href);if(url.origin===location.origin){if(!url.pathname.startsWith(new URL(PsychSoftNavigation.siteRoot).pathname)||!(await fetch(url.href,{method:'HEAD'})).ok)bad.push(url.href)}}return bad})()`);
  assert.deepEqual(paths,[]);assert.equal(documents.length,count);assert.equal(await run('window.__deepProbe'),true);
  assert.deepEqual(errors,[]);console.log('deep entry and resource paths passed');
 }
 else if(mode==='parse') {
  await run('window.__parseCount=0;window.__parseOriginal=DOMParser.prototype.parseFromString;DOMParser.prototype.parseFromString=function(...args){window.__parseCount++;return __parseOriginal.apply(this,args)}');
  await nav('sources.html?single-parse');
  assert.equal(await run('window.__parseCount'),1,'Cold navigation parses each HTML document only once');
  console.log('single parse passed');
 }
 else if(mode==='fallback') {
  await run('document.startViewTransition=undefined');await nav('index.html');
  await click('[data-topic-link="regression"]');
  assert.ok(await run('!!document.querySelector("body>main")&&document.querySelector("#topic-intro").dataset.topic==="regression"'),'Topic fallback retains a live main');
  assert.deepEqual(errors,[]);console.log('fallback topic passed');
 }
 else if(mode==='failures') {
  for(const fault of ['version','non-html','missing-main','module','redirect','404']){
   await open('index.html');const count=documents.length;
   const path=fault==='module'?'symbols.html?qa=module':fault==='404'?'terms/qa-missing.html':'sources.html?qa='+fault;
   await run(`window.__failureProbe=true;window.addEventListener('psych-navigation-error',event=>sessionStorage.setItem('qa.failure',JSON.stringify({reason:event.detail.message,visible:getComputedStyle(document.querySelector('body>main')).visibility})),{once:true});
    window.__originalFetch=fetch;window.fetch=async(...args)=>{const response=await __originalFetch(...args);if(!String(args[0]).includes('qa='))return response;let html=await response.text(),type='text/html';const fault=${JSON.stringify(fault)};
    if(fault==='version')html=html.replace(/name="psych-runtime" content="[^"]+"/,'name="psych-runtime" content="outdated"');
    if(fault==='non-html')type='text/plain';
    if(fault==='missing-main')html=html.replace('<main>','<section>').replace('</main>','</section>');
    if(fault==='module')html=html.replace(/assets\\/symbols\\.js\\?v=[a-z0-9]+/g,'assets/symbols.js?v=blocked');
    const altered=new Response(html,{status:response.status,headers:{'content-type':type}});Object.defineProperty(altered,'url',{value:fault==='redirect'?'https://outside.test/a.html':response.url});return altered;};void 0`);
   if(fault==='module')await send('Network.setBlockedURLs',{urls:['*symbols.js?v=blocked*']});
   await run(`void PsychSoftNavigation.navigate(${JSON.stringify(new URL(path,base).href)})`);
   await until(`!window.__failureProbe&&location.href===${JSON.stringify(new URL(path,base).href)}&&document.readyState==='complete'`);
   assert.equal(documents.length-count,1,'Failure falls back once: '+fault);
   const feedback=await run('JSON.parse(sessionStorage.getItem("qa.failure"))');assert.equal(feedback.visible,'visible');
   await send('Network.setBlockedURLs',{urls:[]});results.push({case:fault,fallbackDocuments:documents.length-count,feedback});
  }
  await mkdir('logs',{recursive:true});await writeFile('logs/soft-navigation-failures.json',JSON.stringify({base,results,errors},null,2));
  console.log(JSON.stringify({base,results,errors},null,2));
 }
 else {
  const stableDocumentCount=documents.length;
  // Every header page remains in this document, including modules not initially loaded.
  for(const file of ['paths.html','practice.html','datasets.html','symbols.html','analysis.html','sources.html','index.html']){
    await click(`.site-head nav a[href="${new URL(file,base).href}"]`);
    assert.equal(await run('location.pathname'),new URL(file,base).pathname);
    assert.equal(await run('window.__documentProbe'),'retained');
    assert.equal(await run('document.querySelectorAll(".nav-motion-indicator").length'),1);
  }
  results.push({case:'seven-header-pages',documentRequests:documents.length-stableDocumentCount});
  const sharedScripts=requests.filter(item=>item.type==='Script'&&/\/(?:site|page-runtime|favorites|cursor|soft-navigation)\.js\?/.test(item.url));
  assert.equal(new Set(sharedScripts.map(item=>item.url)).size,sharedScripts.length,'Common scripts load once');
  // Repeat visits don't multiply favorite subscriptions or click handlers.
  for(let i=0;i<3;i++){
    await nav('index.html');
    const previous=await run('PsychFavorites.has("variable")');
    await click('[data-favorite="variable"]');
    assert.equal(await run('PsychFavorites.has("variable")'),!previous);
    await nav('terms/variable.html');await click('[data-collapse-term]');
  }
  results.push({case:'favorite-single-toggle',visits:3});
  await nav('terms/sem.html');
  await run(`(()=>{const f=document.querySelector('.formula'),keys=f.querySelectorAll('.formula-key');keys[0].click();keys[1].click()})()`);
  assert.equal(await run('document.querySelectorAll(".formula-row.is-pinned").length'),2);
  await run('document.querySelector(".formula-key").click()');
  assert.equal(await run('document.querySelectorAll(".formula-row.is-pinned").length'),1);
  assert.equal(await run('document.querySelectorAll(".formula-row.is-active").length'),1);
  await run(`(()=>{const key=document.querySelectorAll('.formula-key')[2],symbol=document.querySelector('.katex-html .'+key.dataset.symbol);symbol.dispatchEvent(new PointerEvent('pointerenter'));document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));symbol.dispatchEvent(new PointerEvent('pointerleave'))})()`);
  assert.equal(await run('document.querySelectorAll(".formula-row.is-pinned").length'),2,'Hover enables Enter without first clicking');
  results.push({case:'formula-multi-highlight'});
  await nav('symbols.html');
  await run(`document.querySelector('#symbol-query').value='df';document.querySelector('#symbol-query').dispatchEvent(new Event('input'))`);
  assert.ok(await run('document.querySelectorAll("[data-symbol-row]:not([hidden])").length>0'));
  assert.ok(await run('document.querySelectorAll("[data-symbol-row]:not([hidden])").length<document.querySelectorAll("[data-symbol-row]").length'));
  results.push({case:'first-symbol-module'});
  await nav('analysis.html');
  await run(`document.querySelector('#analysis-filter').value='回归';document.querySelector('#analysis-filter').dispatchEvent(new Event('input'))`);
  await click('.analysis-card[data-analysis-id="logistic"]');
  assert.ok(await run('!!document.querySelector("[data-analysis-field]")'));
  await click('[data-collapse-analysis]');
  assert.equal(await run('document.querySelector("#analysis-filter").value'),'回归');
  results.push({case:'analysis-module-and-filter-return'});
  await nav('practice.html');await click('[data-choice="0"]');
  const session=await run('PsychPractice.captureState()');
  await click('.practice-open-link');
  assert.ok(await run('!!document.querySelector("[data-return-practice]")'));
  await click('[data-return-practice]');
  assert.deepEqual(await run('PsychPractice.captureState()'),session);
  await click('.practice-open-link');await click('.sequence-next');
  assert.equal(await run('!!document.querySelector("[data-return-practice]")'),false);
  results.push({case:'practice-session-and-temporary-return'});
  await nav('index.html');
  await run(`document.querySelector('#level-filter').value='intermediate';document.querySelector('#level-filter').dispatchEvent(new Event('change'))`);
  await click('[data-topic-link="regression"]');
  await run(`document.querySelector('#level-filter').value='advanced';document.querySelector('#level-filter').dispatchEvent(new Event('change'));window.scrollTo(0,350)`);
  await run('history.back()');await wait(650);
  assert.equal(await run('document.querySelector("#level-filter").value'),'intermediate');
  assert.equal(await run('document.querySelector("#topic-intro").dataset.topic'),'foundations');
  await run('history.forward()');await wait(650);
  assert.equal(await run('document.querySelector("#level-filter").value'),'advanced','Forward restores edits made before browser Back');
  await run('history.back()');await wait(650);
  results.push({case:'topic-history-and-filters'});
  await nav('terms/normal-distribution.html');
  await run(`const q=document.querySelector('#q');q.value='直方图';q.dispatchEvent(new Event('input'))`);await wait(120);
  assert.ok(await run('[...document.querySelectorAll("#search-results a")].some(a=>a.href.endsWith("/terms/histogram.html"))'));
  await run(`document.querySelector('#search-scope').value='page';document.querySelector('#search-scope').dispatchEvent(new Event('change'))`);
  assert.ok(await run('document.querySelectorAll(".search-hit").length>0'));
  await nav('terms/central-tendency-and-dispersion.html#mean');
  assert.equal(await run('location.hash'),'#mean');assert.ok(await run('!!document.querySelector("#mean")'));
  results.push({case:'global-search-page-search-cross-page-hash'});
  // A delayed response cannot cover a faster subsequent selection.
  await run(`window.__realFetch=window.fetch;window.fetch=async(...args)=>{if(String(args[0]).includes('sources.html?slow'))await new Promise(r=>setTimeout(r,500));return __realFetch(...args)};window.__slow=PsychSoftNavigation.navigate(new URL('sources.html?slow',PsychSoftNavigation.siteRoot).href);void 0`);
  await nav('datasets.html?fast');await wait(550);
  assert.equal(await run('location.pathname'),new URL('datasets.html',base).pathname);
  assert.equal(await run('window.__slow'),false);await run('window.fetch=window.__realFetch');
  results.push({case:'late-response-cancelled'});
  // Loading retains the old main and only starts animation when content is ready.
  await run(`window.fetch=async(...args)=>{if(String(args[0]).includes('paths.html?delayed'))await new Promise(r=>setTimeout(r,350));return __realFetch(...args)};window.__delayed=PsychSoftNavigation.navigate(new URL('paths.html?delayed',PsychSoftNavigation.siteRoot).href);void 0`);
  await wait(80);assert.ok(await run('location.pathname.endsWith("/datasets.html")&&getComputedStyle(document.querySelector("body>main")).visibility==="visible"'));
  await run('window.__delayed');await run('window.fetch=window.__realFetch');results.push({case:'old-content-visible-while-fetching'});
  // Both progressively enhanced and fallback animations have usable final pages.
  await run('window.__startViewTransition=document.startViewTransition;document.startViewTransition=undefined');
  await nav('index.html');await click('[data-topic-link="regression"]');
  assert.ok(await run('!!document.querySelector("body>main")&&document.querySelector("#topic-intro").dataset.topic==="regression"'),'Topic fallback retains a live main');
  await click('.term-card:not([hidden]) a[data-expand-card]');await click('[data-collapse-term]');
  await nav('terms/variable.html');await click('.sequence-next');
  assert.equal(await run('!!document.querySelector(".soft-outgoing-layer")'),false);
  await run('document.startViewTransition=window.__startViewTransition');
  results.push({case:'no-view-transition-fallback'});
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await nav('index.html');await click('.term-card:not([hidden]) a[data-expand-card]');
  assert.equal(await run('PsychSoftMotion.running'),false);
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});results.push({case:'reduced-motion'});
  await nav('paths.html');
  await run(`document.querySelector('.site-head nav a[href="${new URL('datasets.html',base).href}"]').click();void 0`);await wait(90);
  assert.ok(await run('document.querySelector(".nav-motion-indicator").getAnimations().some(a=>a.playState==="running")'),'Header shadow moves independently of the content layers');
  await wait(500);results.push({case:'header-shadow-visual-motion'});
  // A short hover warms exactly the selected candidate; warm navigation skips Fetch.
  await run(`const link=document.createElement('a');link.href=new URL('sources.html?hover',PsychSoftNavigation.siteRoot);link.id='qa-hover';link.textContent='QA';document.querySelector('main').appendChild(link);link.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));`);
  await wait(230);assert.ok(await run('!!PsychSoftNavigation.cache.get(new URL("sources.html?hover",PsychSoftNavigation.siteRoot).href)'));
  const fetchCount=requests.filter(item=>item.type==='Fetch').length;
  await nav('sources.html?hover');assert.equal(requests.filter(item=>item.type==='Fetch').length,fetchCount,'Warm cache makes no HTML request');
  assert.ok(await run('PsychSoftNavigation.cache.size<=12'));
  await run(`window.__realConnection=navigator.connection;Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'2g'}})`);
  await nav('terms/sem.html?no-prefetch');const disabledCount=requests.filter(item=>item.type==='Fetch').length;
  await wait(900);assert.equal(requests.filter(item=>item.type==='Fetch').length,disabledCount,'Save-data disables adjacent prefetch');
  await run(`Object.defineProperty(navigator,'connection',{configurable:true,value:window.__realConnection})`);
  results.push({case:'hover-cache-and-disabled-prefetch'});
  await nav('sources.html?timing');const cold=await run('PsychSoftNavigation.metrics.at(-1)');
  await nav('datasets.html');await nav('sources.html?timing');const warm=await run('PsychSoftNavigation.metrics.at(-1)');
  results.push({case:'controlled-cache-timing',coldPrepareMs:cold.loaded-cold.started,warmPrepareMs:warm.loaded-warm.started,coldCached:cold.cached,warmCached:warm.cached});
  // Real DOM events retain Ctrl/new-tab/download/external/hash browser semantics,
  // while our test listener prevents any download or external navigation.
  assert.equal(await run(`(()=>{const failures=[];for(const spec of [{href:'terms/variable.html',ctrlKey:true},{href:'terms/variable.html',target:'_blank'},{href:'assets/data/search-index.json',download:true},{href:'https://outside.test/'},{href:'#formula'}]){const a=document.createElement('a');a.href=new URL(spec.href,location.href).href;if(spec.target)a.target=spec.target;if(spec.download)a.download='';a.addEventListener('click',e=>{if(e.defaultPrevented)failures.push(spec);e.preventDefault()});document.querySelector('main').appendChild(a);a.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,button:0,ctrlKey:!!spec.ctrlKey}));a.remove()}return failures.length})()`),0);
  results.push({case:'native-link-semantics'});
  assert.equal(documents.length,stableDocumentCount,'Every normal navigation is same-document');
  assert.equal(await run('document.documentElement.scrollWidth<=innerWidth'),true,'Responsive layout does not overflow');
  assert.equal(await run('!!document.querySelector(".soft-outgoing-layer,.term-transition-scene")'),false);
  assert.deepEqual(errors,[]);
  results.push({case:'metrics',metrics:await run('window.PsychSoftNavigation?.metrics || []')});
  const timing=await run('({longTasks:PsychSoftNavigation.longTasks,frames:window.__qaFrames})');
  await run('window.__qaSampling=false');
  await mkdir('logs',{recursive:true});await writeFile(`logs/soft-navigation-qa-${width}-${new URL(base).pathname.includes('psy-stats')?'subpath':'root'}-${Date.now()}.json`,JSON.stringify({base,width,results,errors,timing},null,2));
  const sorted=timing.frames.toSorted((a,b)=>a-b),summary={samples:sorted.length,p50:sorted[Math.floor(sorted.length*.5)],p95:sorted[Math.floor(sorted.length*.95)],max:sorted.at(-1),longTasks:timing.longTasks};
  console.log(JSON.stringify({base,width,results:results.filter(item=>item.case!=='metrics'),errors,timing:summary},null,2));
 }
}finally{for(const identifier of injections)await send('Page.removeScriptToEvaluateOnNewDocument',{identifier}).catch(()=>{});ws.close();}
