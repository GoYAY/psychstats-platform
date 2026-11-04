import {writeFile} from 'node:fs/promises';
const pages=await(await fetch('http://127.0.0.1:9290/json')).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const jobs=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(jobs.has(m.id)){const j=jobs.get(m.id);jobs.delete(m.id);m.error?j.reject(m.error):j.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{jobs.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description);return r.result.value};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const base='http://127.0.0.1:8765/psy-stats/';const results=[];
try{
await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
for(const width of [1440,1366,1200,390]){
 await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 await send('Page.navigate',{url:base+'index.html?topic=foundations'});await sleep(1000);
 for(const [from,to] of [['datasets.html','paths.html'],['symbols.html','paths.html'],['index.html','paths.html']]){
  await run(`PsychSoftNavigation.navigate(new URL(${JSON.stringify(from)},PsychSoftNavigation.siteRoot).href)`);await sleep(300);
  const data=await run(`new Promise(resolve=>{const out=[];const start=performance.now();function sample(t){const rect=sel=>document.querySelector(sel)?.getBoundingClientRect().toJSON();out.push({t:t-start,head:rect('.site-head'),nav:rect('.site-head nav'),pill:rect('.nav-motion-indicator'),search:rect('.header-search'),links:[...document.querySelectorAll('.site-head nav a')].map(a=>({name:a.textContent,rect:a.getBoundingClientRect().toJSON()})),client:document.documentElement.clientWidth});if(t-start<650)requestAnimationFrame(sample);else resolve(out)}sample(start);void PsychSoftNavigation.navigate(new URL(${JSON.stringify(to)},PsychSoftNavigation.siteRoot).href)})`);
  results.push({width,from,to,data});console.log(JSON.stringify({width,from,to,headHeights:[...new Set(data.map(s=>s.head.height))],navWidths:[...new Set(data.map(s=>s.nav.width))],client:[...new Set(data.map(s=>s.client))],pillEnds:[data[0].pill,data.at(-1).pill],pillY:[...new Set(data.map(s=>s.pill.y))]}));
 }
 await run(`PsychSoftNavigation.navigate(new URL('index.html?topic=foundations',PsychSoftNavigation.siteRoot).href)`);await sleep(300);
 for(const topic of ['hypothesis-testing','regression','favorites','foundations']){
  const data=await run(`new Promise(resolve=>{const out=[],start=performance.now();function sample(t){const rect=e=>e?.getBoundingClientRect().toJSON();out.push({t:t-start,head:rect(document.querySelector('.site-head')),topics:[...document.querySelectorAll('body>main .topic-nav a')].map(a=>({name:a.textContent,rect:rect(a)})),intro:rect(document.querySelector('body>main .topic-intro')),copies:[...document.querySelectorAll('.soft-outgoing-layer .topic-intro')].map(e=>({rect:rect(e),title:rect(e.querySelector('h2'))})),liveTitle:rect(document.querySelector('body>main .topic-intro h2')),client:document.documentElement.clientWidth});if(t-start<400)requestAnimationFrame(sample);else resolve(out)}sample(start);document.querySelector('[data-topic-link="${topic}"]').click()})`);
  results.push({width,topic,data});console.log(JSON.stringify({width,topic,client:[...new Set(data.map(s=>s.client))],introX:[...new Set(data.map(s=>s.intro.x))],topicsY:[...new Set(data.map(s=>s.topics[0].rect.y))],introTitleY:[...new Set(data.map(s=>s.liveTitle.y))],copyTitleY:[...new Set(data.flatMap(s=>s.copies.map(c=>c.title.y)))]}));
 }
}
await writeFile('logs/navigation-geometry-diagnosis.json',JSON.stringify(results,null,2));
}finally{ws.close()}
