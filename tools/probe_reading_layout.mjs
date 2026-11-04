import {writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9291',phase='probe',width='1440',eager='no'}=args(),results=[];
for(const variant of ['baseline','candidate','candidate','baseline']){
 const ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx;
 try{
  await page.send('Page.navigate',{url:'http://127.0.0.1:8765/psy-stats/index.html'});
  await until('document.readyState==="complete"&&!!document.querySelector(".topic-nav")');await wait(350);
  // Only this isolated browser context changes; no product assets are edited.
  if(phase!=='probe')await run(`(()=>{const style=document.createElement('style');style.textContent=${JSON.stringify(variant==='baseline'?'.term-content>section{content-visibility:visible!important;contain-intrinsic-size:none!important}':'')};document.head.append(style)})()`);
  else if(variant==='candidate')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content>section{content-visibility:auto;contain-intrinsic-size:auto 600px}@media print{.term-content>section{content-visibility:visible;contain-intrinsic-size:none}}';document.head.append(style)})()`);
  if(eager==='yes'&&variant==='candidate')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content>section:nth-of-type(-n+3){content-visibility:visible!important;contain-intrinsic-size:none!important}';document.head.append(style)})()`);
  await run(`window.__long=[];window.__times=[];window.__sampling=true;new PerformanceObserver(l=>__long.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask'});requestAnimationFrame(function f(t){__times.push(t);if(__sampling)requestAnimationFrame(f)})`);
  const visits=[];
  for(const [slug,label] of [['sem','cold'],['sem','repeat']]){
   await run(`document.querySelector('[data-topic-link="structural-equation-modeling"]').click()`);await wait(350);
   await run(`window.__long=[];window.__times=[];window.__start=performance.now()`);
   await run(`document.querySelector('.term-card[data-id="${slug}"] a[data-expand-card]').click()`);
   await until(`document.querySelector('.term-content')?.dataset.termId==='${slug}'&&!PsychSoftMotion.running`);await wait(200);
   const sample=await run(`({label:${JSON.stringify(label)},long:__long,times:__times,metric:PsychSoftNavigation.metrics.at(-1),nodes:document.querySelectorAll('*').length,sections:document.querySelectorAll('.term-content>section').length})`);
   sample.maxFrame=Math.max(...sample.times.slice(1).map((t,i)=>t-sample.times[i]));delete sample.times;visits.push(sample);
   await run(`PsychSoftNavigation.navigate('http://127.0.0.1:8765/psy-stats/index.html')`);await wait(150);
  }
  results.push({variant,visits});console.log(JSON.stringify(results.at(-1)));
 }finally{await ctx.close()}
}
const log=`logs/reading-layout-${phase}-${width}-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;
await writeFile(log,JSON.stringify({width,results},null,2));console.log(log);
