// Final candidate navigation: distinguish cold startup from input/transition work.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,args,wait} from './native-cdp.mjs';
const o=args(),width=Number(o.width||390),cpu=Number(o.cpu||4),base=o.url||'http://127.0.0.1:8892/site/online-release-ready/',output=o.output||'.superpowers/sdd/2026-10-24-online-release-readiness/navigation',b=await isolatedPage(9296,width),rows=[];
try{
 await b.page.send('Page.bringToFront');await b.page.send('Emulation.setCPUThrottlingRate',{rate:cpu});
 await b.page.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__tasks=[];window.__cls=[];new PerformanceObserver(l=>window.__tasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__cls.push(...l.getEntries().filter(e=>!e.hadRecentInput).map(e=>e.value))).observe({type:'layout-shift',buffered:true});`});
 await b.page.send('Page.navigate',{url:new URL('index.html',base).href});await b.until(`!!document.querySelector('[data-topic-link]')&&document.readyState==='complete'`);await wait(1600);
 for(const [kind,selector,expected] of [
  ['topic','[data-topic-link="hypothesis-testing"]','index.html?topic=hypothesis-testing'],
  ['topic','[data-topic-link="foundations"]','index.html?topic=foundations'],
  ['top','nav[aria-label="主导航"] a[href$="paths.html"]','paths.html'],
  ['top','nav[aria-label="主导航"] a[href$="practice.html"]','practice.html'],
  ['top','nav[aria-label="主导航"] a[href$="datasets.html"]','datasets.html'],
  ['top','nav[aria-label="主导航"] a[href$="index.html"]','index.html'],
 ]){
  const start=await b.run(`performance.now()`);
  const samples=await b.run(`(async()=>{const node=document.querySelector(${JSON.stringify(selector)});if(!node)throw Error('Missing navigation '+${JSON.stringify(selector)});const frames=[];let running=true,last=performance.now();const tick=t=>{frames.push(t-last);last=t;if(running)requestAnimationFrame(tick)};requestAnimationFrame(tick);node.click();await new Promise(r=>setTimeout(r,1000));running=false;return frames;})()`);
  await b.until(`(location.pathname+location.search).endsWith(${JSON.stringify(expected)})`);
  const data=await b.run(`({tasks:window.__tasks.filter(t=>t.start>=${start}),overflow:document.documentElement.scrollWidth>innerWidth+1,cls:window.__cls.reduce((a,b)=>a+b,0),documents:performance.getEntriesByType('navigation').length})`);
  assert.equal(data.overflow,false);assert.equal(data.documents,1,'Navigation must retain the same document');samples.sort((a,b)=>a-b);
  rows.push({kind,expected,p95:samples[Math.floor(samples.length*.95)],maxFrame:Math.max(...samples),...data});await wait(400);
 }
 await mkdir(output,{recursive:true});const report={width,cpu,scope:'local Edge CPU simulation,not online or real phone',rows};await writeFile(`${output}/${width}.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await b.close();}
