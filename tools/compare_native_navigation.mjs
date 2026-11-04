import {writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {phase='current-next',cdp='9291',trigger='direct',prefetch='no'}=args(),stamp=new Date().toISOString().replace(/[:.]/g,'-'),results=[];
for(const kind of ['old','next','next','old','old','next','next','old']){
 const ctx=await isolatedPage(cdp),{run,until,page}=ctx,base=`http://127.0.0.1:${kind==='old'?8765:8766}/psy-stats/`,home=base+(kind==='old'?'index.html':'');
 try{await page.send('Page.navigate',{url:home});await until('document.readyState==="complete"&&!!document.querySelector(".topic-nav")');await wait(350);
 const initial=await run('({duration:performance.getEntriesByType("navigation")[0].duration,bytes:performance.getEntriesByType("navigation")[0].transferSize+performance.getEntriesByType("resource").reduce((s,e)=>s+e.transferSize,0),nodes:document.querySelectorAll("*").length})');
 await run(`window.__long=[];window.__frameTimes=[];window.__running=true;new PerformanceObserver(l=>__long.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask'});(function frame(t){__frameTimes.push(t);if(__running)requestAnimationFrame(frame)})(performance.now());`);
 const visits=[];for(const [key,label] of [['sem','cold-sem'],['sem','repeat-sem'],['variable','variable']]){
 if(trigger==='card'){const topic=key==='sem'?'structural-equation-modeling':'foundations';await run(`document.querySelector('[data-topic-link="${topic}"]').click()`);await wait(400);await until(`!!document.querySelector('.term-card[data-id="${key}"]:not([hidden]) a[data-expand-card]')`);if(prefetch==='yes'){await run(`document.querySelector('.term-card[data-id="${key}"] a[data-expand-card]').dispatchEvent(new PointerEvent('pointerover',{bubbles:true}))`);await wait(250);}}
 await run('window.__long=[];window.__frameTimes=[];window.__metricStart=(window.PsychNativeMetrics||window.PsychNextMetrics||window.PsychSoftNavigation?.metrics||[]).length;window.__start=performance.now()');
 const href=kind==='old'?base+`terms/${key}.html`:`/psy-stats/terms/${key}/`;
 if(trigger==='card')await run(`document.querySelector('.term-card[data-id="${key}"] a[data-expand-card]').click()`);else await run(`(()=>{const a=document.createElement('a');a.href=${JSON.stringify(href)};document.body.append(a);a.click();a.remove()})()`);
 await until(`document.querySelector('.term-content')?.dataset.termId===${JSON.stringify(key)}&&!document.documentElement.classList.contains('next-moving')&&!document.documentElement.hasAttribute('data-psych-transition')&&!document.documentElement.classList.contains('soft-navigating')`);await wait(500);
 const data=await run(`({label:${JSON.stringify(label)},elapsed:performance.now()-__start,long:__long,frameTimes:__frameTimes,metrics:(window.PsychNativeMetrics||window.PsychNextMetrics||window.PsychSoftNavigation?.metrics||[]).slice(__metricStart),nodes:document.querySelectorAll('*').length})`);
 const intervals=data.frameTimes.slice(1).map((t,i)=>t-data.frameTimes[i]),sorted=[...intervals].sort((a,b)=>a-b);data.frames={count:sorted.length,max:sorted.at(-1),p95:sorted[Math.floor(sorted.length*.95)],over33:sorted.filter(x=>x>33).length};const m=data.metrics.at(-1);if(m?.ready){const animated=intervals.filter((_,i)=>data.frameTimes[i]>=m.ready&&data.frameTimes[i+1]<=m.finished);data.animationFrames={count:animated.length,max:Math.max(0,...animated),over33:animated.filter(x=>x>33).length};}delete data.frameTimes;visits.push(data);
 await run(`(()=>{const a=document.createElement('a');a.href=${JSON.stringify(kind==='old'?home:'/psy-stats/')};document.body.append(a);a.click();a.remove()})()`);await until('!!document.querySelector(".topic-nav")&&!document.documentElement.hasAttribute("data-psych-transition")');await wait(500);
 }
 results.push({kind,initial,visits});console.log(JSON.stringify({kind,visits:visits.map(v=>({label:v.label,max:v.frames.max,long:v.long,metrics:v.metrics}))}));
 }finally{await ctx.close();}
}
const file=`logs/native-navigation-${phase}-${stamp}.json`;await writeFile(file,JSON.stringify({phase,stamp,conditions:{viewport:'1440x900',cacheDisabled:true,freshContextPerRound:true,localHTTP:true,trigger,prefetch},results},null,2));console.log(file);
