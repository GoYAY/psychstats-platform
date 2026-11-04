import {writeFile} from 'node:fs/promises';
const pages=await(await fetch('http://127.0.0.1:9290/json')).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const jobs=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(jobs.has(m.id)){const j=jobs.get(m.id);jobs.delete(m.id);m.error?j.reject(m.error):j.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{jobs.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description);return r.result.value};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
const results=[];
try {
for(const base of (process.argv[2]==='local'?['http://127.0.0.1:8765/psy-stats/']:['http://127.0.0.1:8765/psy-stats/','https://cdst.site/psy-stats/'])){
 await send('Page.navigate',{url:base+'index.html?topic=foundations'});
 for(let i=0;i<200;i++){if(await run(`location.href.startsWith(${JSON.stringify(base)})&&document.readyState==='complete'&&!!window.PsychSoftMotion`))break;await sleep(100)}
 await sleep(800);
 const topics=await run(`Array.from(document.querySelectorAll('[data-topic-link]')).map(a=>({id:a.dataset.topicLink,title:a.textContent.trim()}))`);
 const version=await run(`document.querySelector('meta[name="psych-runtime"]').content`);
 for(const mode of ['native','no-snapshot']){
  await run(`window.__nativeVT=window.__nativeVT||document.startViewTransition;document.startViewTransition=${mode==='native'?'window.__nativeVT':'undefined'};window.__diag={frames:[],tasks:[],shifts:[],samples:[],active:false};new PerformanceObserver(l=>l.getEntries().forEach(e=>__diag.tasks.push({start:e.startTime,duration:e.duration}))).observe({type:'longtask',buffered:false});new PerformanceObserver(l=>l.getEntries().forEach(e=>__diag.shifts.push({value:e.value,recent:e.hadRecentInput,sources:e.sources.map(s=>({tag:s.node?.className,from:s.previousRect,to:s.currentRect}))}))).observe({type:'layout-shift',buffered:false});window.__diag.active=true;(()=>{let prev=performance.now();function sample(t){if(!__diag.active)return;__diag.frames.push(t-prev);prev=t;const c=document.querySelector('.term-card:not([hidden])');const g=document.querySelector('.term-grid');const m=document.querySelector('body>main');const style=getComputedStyle(document.documentElement,'::view-transition-new(psych-content)');__diag.samples.push({t,card:c?.getBoundingClientRect().toJSON(),grid:g?.getBoundingClientRect().toJSON(),main:m?.getBoundingClientRect().toJSON(),pseudo:{height:style.height,width:style.width,transform:style.transform},scrollY});requestAnimationFrame(sample)}requestAnimationFrame(sample)})()`);
  const begin=await run('performance.now()');
  const testedTopics=process.argv.includes('--all-topics')?topics.slice(1):topics.slice(1,5);
  for(const topic of testedTopics){
   await run(`document.querySelector('[data-topic-link="${topic.id}"]').click()`);await sleep(500);
  }
  await run('__diag.active=false');const d=await run('__diag');
  const sorted=d.frames.filter(x=>x>0).sort((a,b)=>a-b);
  const data={base,mode,version,topics:testedTopics,start:begin,frameMedian:sorted[Math.floor(sorted.length*.5)],frameP95:sorted[Math.floor(sorted.length*.95)],frameMax:Math.max(...sorted),over33:d.frames.filter(x=>x>33).length,longTasks:d.tasks,shifts:d.shifts,samples:d.samples};
  results.push(data);console.log(JSON.stringify({...data,samples:undefined,shifts:d.shifts.map(s=>({value:s.value,recent:s.recent,sources:s.sources.map(x=>x.tag)}))}));
 }
}
await writeFile(process.argv[3]||'logs/navigation-performance-diagnosis.json',JSON.stringify(results,null,2));
} finally {ws.close()}
