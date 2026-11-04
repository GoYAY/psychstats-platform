import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const [port='9291',experiment='baseline']=process.argv.slice(2);
function connect(url){const ws=new WebSocket(url),tasks=new Map(),events=new Map();let id=0;ws.onmessage=e=>{const m=JSON.parse(e.data),task=tasks.get(m.id);if(task){tasks.delete(m.id);m.error?task.reject(m.error):task.resolve(m.result);}else if(events.has(m.method))events.get(m.method)(m.params);};return {ws,events,ready:new Promise(r=>ws.onopen=r),send:(method,params={})=>new Promise((resolve,reject)=>{tasks.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));})};}
const version=await(await fetch(`http://127.0.0.1:${port}/json/version`)).json(),browser=connect(version.webSocketDebuggerUrl);await browser.ready;
const results=[];const wait=ms=>new Promise(r=>setTimeout(r,ms));
try{for(const kind of ['old','next','next','old']){
 const {browserContextId}=await browser.send('Target.createBrowserContext',{disposeOnDetach:true});
 try{
  const {targetId}=await browser.send('Target.createTarget',{url:'about:blank',browserContextId});
  const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json(),page=connect(pages.find(p=>p.id===targetId).webSocketDebuggerUrl);await page.ready;
  const run=async expression=>{const r=await page.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value;};
  async function until(expression){for(let i=0;i<200;i++){if(await run(expression))return;await wait(50);}throw Error(expression);}
  await page.send('Page.enable');await page.send('Network.enable');await page.send('Network.setCacheDisabled',{cacheDisabled:true});await page.send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  await page.send('Page.navigate',{url:`http://127.0.0.1:${kind==='old'?8765:8766}/psy-stats/${kind==='old'?'index.html':''}`});await until('document.readyState===\"complete\"&&!!document.querySelector(\".topic-nav\")');await wait(350);
  const initial=await run('({duration:performance.getEntriesByType(\"navigation\")[0].duration,bytes:performance.getEntriesByType(\"navigation\")[0].transferSize+performance.getEntriesByType(\"resource\").reduce((sum,r)=>sum+r.transferSize,0),nodes:document.querySelectorAll(\"*\").length})');
  if(experiment==='fonts')await run(`Promise.all(['16px KaTeX_Main','bold 16px KaTeX_Main','italic bold 16px KaTeX_Math'].map(font=>document.fonts.load(font)))`);
  if(experiment==='sections')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content > section {content-visibility:auto;contain-intrinsic-size:auto 250px;}';document.head.append(style)})()`);
  if(experiment==='short')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content > section:nth-of-type(n+4) {display:none;}';document.head.append(style)})()`);
  if(experiment==='sections-large')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content > section {content-visibility:auto;contain-intrinsic-size:auto 1000px;}';document.head.append(style)})()`);
  if(experiment==='font-family')await run(`(()=>{const style=document.createElement('style');style.textContent='body {--font-display:Arial,sans-serif;--font-body:Arial,sans-serif;}';document.head.append(style)})()`);
  if(experiment==='font-direct')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content,.term-content p,.term-content li,.term-content h1,.term-content h2,.term-content h3,.term-content a,.term-content button,.term-content strong {font-family:"Microsoft YaHei",sans-serif !important;}';document.head.append(style)})()`);
  await page.send('Profiler.enable');await page.send('Profiler.start');
  const traced=[];page.events.set('Tracing.dataCollected',p=>traced.push(...p.value));if(experiment==='trace')await page.send('Tracing.start',{categories:'devtools.timeline,disabled-by-default-devtools.timeline,blink,loading',transferMode:'ReportEvents'});
  await run(`window.__frames=[];window.__long=[];window.__keep=true;window.__bounds=[];window.__rect=Element.prototype.getBoundingClientRect;Element.prototype.getBoundingClientRect=function(){const t=performance.now(),b=__rect.apply(this,arguments),ms=performance.now()-t;if(ms>5)__bounds.push({ms,tag:this.tagName,className:this.className});return b};new PerformanceObserver(l=>__long.push(...l.getEntries().map(e=>({duration:e.duration,start:e.startTime})))).observe({type:'longtask',buffered:false});(()=>{let last=0;function tick(t){if(last)__frames.push(t-last);last=t;if(__keep)requestAnimationFrame(tick)}requestAnimationFrame(tick)})();window.__start=performance.now();`);
  if(kind==='old')await run(`PsychSoftNavigation.navigate(new URL('terms/sem.html',location.href).href)`);
  else {await run(`(()=>{const a=document.createElement('a');a.href='/psy-stats/terms/sem/';document.body.append(a);a.click();a.remove()})()`);await until(`!!document.querySelector('.term-content[data-term-id=sem]')&&!document.documentElement.classList.contains('next-moving')&&(window.PsychNextMetrics||[]).length>0`);}
  await wait(50);const data=await run('({elapsed:performance.now()-__start,long:__long,bounds:__bounds,frames:__frames,metrics:window.PsychNextMetrics||[]})');
  const {profile}=await page.send('Profiler.stop');await writeFile(`logs/cold-profile-${kind}-${results.length}.json`,JSON.stringify(profile));
  if(experiment==='trace'){const ended=new Promise(r=>page.events.set('Tracing.tracingComplete',r));await page.send('Tracing.end');await ended;await writeFile(`logs/cold-trace-${kind}-${results.length}.json`,JSON.stringify(traced));console.log(JSON.stringify(traced.filter(e=>e.ph==='X'&&e.dur>20000).map(e=>({name:e.name,duration:e.dur/1000,args:e.args}))));}
  const frames=data.frames.sort((a,b)=>a-b);data.frames={count:frames.length,max:frames.at(-1),p95:frames[Math.floor(frames.length*.95)],over33:frames.filter(x=>x>33).length};results.push({kind,initial,...data});page.ws.close();
 }finally{await browser.send('Target.disposeBrowserContext',{browserContextId});}
}await writeFile(`logs/next-cold-context-${experiment}.json`,JSON.stringify(results,null,2));console.log(JSON.stringify(results));}finally{browser.ws.close();}
