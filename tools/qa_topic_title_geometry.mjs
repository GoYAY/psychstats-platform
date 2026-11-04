import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const [port='9291',base='http://127.0.0.1:8765/psy-stats/index.html']=process.argv.slice(2);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
let serial=0;const jobs=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data),job=jobs.get(m.id);if(job){jobs.delete(m.id);m.error?job.reject(m.error):job.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{jobs.set(++serial,{resolve,reject});ws.send(JSON.stringify({id:serial,method,params}));});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value;};
const results=[];const wait=ms=>new Promise(r=>setTimeout(r,ms));
try{
 await send('Page.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
 for(const width of [1440,390]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
  await send('Page.navigate',{url:base+'?topic=foundations'});await wait(1000);
  await run(`localStorage.setItem('psych-favorites-v1','[]');dispatchEvent(new StorageEvent('storage',{key:'psych-favorites-v1'}))`);
  for(const scroll of [0,120]){
   await run(`window.scrollTo({top:${scroll},behavior:'instant'})`);
   for(const topic of ['hypothesis-testing','regression','favorites','foundations']){
    const samples=await run(`new Promise(resolve=>{const samples=[],start=performance.now();function sample(t){const main=document.querySelector('main'),title=main.querySelector('#topic-title'),box=title.getBoundingClientRect();samples.push({t:t-start,x:box.x,y:box.y,copies:[...document.querySelectorAll('.soft-outgoing-layer .topic-intro h2,.next-outgoing .topic-intro h2')].map(e=>{const b=e.getBoundingClientRect();return{x:b.x,y:b.y}})});if(t-start<350)requestAnimationFrame(sample);else resolve(samples)}sample(start);document.querySelector('[data-topic-link="${topic}"]').click()})`);
    const spread=key=>Math.max(...samples.map(s=>s[key]))-Math.min(...samples.map(s=>s[key]));
    const maxCopyOffset=Math.max(0,...samples.flatMap(s=>s.copies.map(c=>Math.abs(c.y-s.y))));
    results.push({width,scroll,topic,xSpread:spread('x'),ySpread:spread('y'),maxCopyOffset,samples});
   }
  }
 }
 await writeFile(`logs/topic-title-geometry-${new URL(base).port}.json`,JSON.stringify(results,null,2));
 console.log(JSON.stringify(results.map(({samples,...r})=>r)));
 // The heading is the emergence anchor; surrounding content may still scale.
 assert.ok(results.every(r=>r.maxCopyOffset<1),'Transition title copy must align within 1px throughout the animation');
 assert.ok(results.every(r=>r.xSpread<1),'Short/empty topics must not shift the title horizontally');
 assert.ok(results.every(r=>r.ySpread<1),'Live topic title must not jump vertically');
}finally{ws.close();}
