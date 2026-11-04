import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const [port='9291']=process.argv.slice(2),pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);let sequence=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++sequence,{resolve,reject});ws.send(JSON.stringify({id:sequence,method,params}));});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value;};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function until(expr){for(let i=0;i<200;i++){if(await run(expr))return;await wait(50);}throw Error(expr);}
const results=[];
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
 for(const round of [0,1])for(const kind of round===0?['old','next']:['next','old']){
  await send('Network.clearBrowserCache');await send('Network.setCacheDisabled',{cacheDisabled:false});
  const base=`http://127.0.0.1:${kind==='old'?8765:8766}/psy-stats/`;
  await send('Page.navigate',{url:base+(kind==='old'?'index.html':'')});await until('document.readyState===\"complete\"&&!!document.querySelector(\".topic-nav\")');await wait(500);
  const load=await run('({duration:performance.getEntriesByType(\"navigation\")[0].duration,resources:performance.getEntriesByType(\"resource\").map(r=>({name:r.name,bytes:r.transferSize})),nodes:document.querySelectorAll(\"*\").length})');
  await run(`window.__perf={frames:[],motionFrames:[],long:[],bounds:[]};window.__sampling=true;new PerformanceObserver(l=>__perf.long.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:false});(()=>{let last=0;function tick(t){if(last){__perf.frames.push(t-last);if(document.documentElement.classList.contains('next-moving')||window.PsychSoftMotion?.running)__perf.motionFrames.push(t-last)}last=t;if(__sampling)requestAnimationFrame(tick)}requestAnimationFrame(tick)})();window.__originalBounds=Element.prototype.getBoundingClientRect;Element.prototype.getBoundingClientRect=function(){const start=performance.now(),result=__originalBounds.apply(this,arguments),ms=performance.now()-start;if(ms>5)__perf.bounds.push({ms,tag:this.tagName,className:this.className});return result;};`);
  for(const [target,logical] of [['sem','SEM'],['index','index'],['sem','SEM-repeat'],['index','index-repeat'],['variable','variable'],['paths','paths']]){
   await run('__perf.frames=[];__perf.motionFrames=[];__perf.long=[];__perf.bounds=[];window.__started=performance.now()');
   if(kind==='old')await run(`PsychSoftNavigation.navigate(new URL(${JSON.stringify(target==='index'?'index.html':target==='paths'?'paths.html':`terms/${target}.html`)},location.href.includes('/terms/')?new URL('../',location.href):location.href).href)`);
   else {const href=target==='index'?'/psy-stats/':target==='paths'?'/psy-stats/paths/':`/psy-stats/terms/${target}/`;await run(`(()=>{const a=document.createElement('a');a.href=${JSON.stringify(href)};document.body.append(a);a.click();a.remove();})()`);await until(`location.pathname===${JSON.stringify(href)}&&!!document.querySelector(${JSON.stringify(target==='sem'||target==='variable'?'.term-content':target==='index'?'.topic-nav':'.learning-network')})&&!document.documentElement.classList.contains('next-moving')`);}
   await wait(50);const data=await run('({elapsed:performance.now()-__started,...__perf,metrics:window.PsychNextMetrics||[]})');
   for(const key of ['frames','motionFrames']){const a=data[key].sort((a,b)=>a-b);data[key]={count:a.length,max:a.at(-1)||0,p95:a[Math.floor(a.length*.95)]||0,over33:a.filter(x=>x>33).length};}
   results.push({round,kind,target:logical,...data,...(target==='sem'?{initialLoad:load}:{})});
  }
  await run('window.__sampling=false;Element.prototype.getBoundingClientRect=__originalBounds');
 }
 await writeFile('logs/next-navigation-comparison.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results.map(({round,kind,target,elapsed,long,frames,motionFrames,bounds})=>({round,kind,target,elapsed,long,frames,motionFrames,bounds}))));
}finally{ws.close();}
