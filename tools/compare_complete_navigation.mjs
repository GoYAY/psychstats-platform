import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
import {evaluateGate,presentationEvidence} from './complete-navigation-metrics.mjs';
const options=args(),bases={old:options.old||'http://127.0.0.1:8765/psy-stats/',new:options.new||'http://127.0.0.1:8766/psy-stats/',online:options.online||'https://cdst.site/psy-stats/'},port=options.cdp||'9291',width=Number(options.width||1440),samples=[],failures=[],stamp=Date.now();
await mkdir('logs/complete-nav',{recursive:true});
const manifest=JSON.parse(await readFile('site/next-preview/generated/manifest.json','utf8'));
async function round(version,roundIndex,prefetched){
 const ctx=await isolatedPage(port,width),{page,run}=ctx,until=x=>ctx.until(`Boolean(${x})`),base=bases[version],events=[],batch=[];let tracing=false;
 try{
  const response=await fetch(base+'index.html');if(!response.ok)throw Error('Missing target: '+base);
  await page.send('Network.setCacheDisabled',{cacheDisabled:false});
  await page.send('Page.navigate',{url:base+'index.html'});await until(`document.readyState==='complete'&&document.querySelector('.topic-nav')`);await wait(200);
  await run(`window.__nativeTimes=[];window.__domParses=0;const vt=document.startViewTransition?.bind(document);if(vt)document.startViewTransition=(...a)=>{const s={start:performance.now()};__nativeTimes.push(s);const t=vt(...a);t.ready.then(()=>s.ready=performance.now(),()=>s.failed=true);t.finished.then(()=>s.finished=performance.now(),()=>{});return t};const parse=DOMParser.prototype.parseFromString;DOMParser.prototype.parseFromString=function(...a){__domParses++;return parse.apply(this,a)};window.__long=[];new PerformanceObserver(l=>__long.push(...l.getEntries().map(e=>({start:e.startTime,ms:e.duration})))).observe({type:'longtask'});window.__same=document;window.__head=document.querySelector('.site-head');void 0;`);
  page.events.set('Tracing.dataCollected',e=>events.push(...e.value));await page.send('Tracing.start',{categories:'devtools.timeline,blink.user_timing,disabled-by-default-devtools.timeline.frame',transferMode:'ReportEvents'});tracing=true;
  async function settled(){await until(`!document.documentElement.dataset.psychTransition&&!document.documentElement.classList.contains('soft-motion-active')&&!document.querySelector('.next-load-status')`);await wait(80);}
  async function home(){await run(`(()=>{const a=document.querySelector('.site-head nav>a');a.click()})()`);await until(`!!document.querySelector('.topic-nav')`);await settled();}
  async function choose(topic){await run(`document.querySelector('[data-topic-link="${topic}"]').click()`);await until(`document.querySelector('[data-topic-link="${topic}"]')?.getAttribute('aria-current')==='page'`);await settled();}
  async function measure(scenario,temperature,href,click,target){
   if(prefetched&&temperature==='cold'&&scenario!=='topic'){await run(`${click.replace('.click()',`.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}))`)}`);await wait(300);}
   const id=`${version}-${roundIndex}-${prefetched}-${temperature}-${scenario}-${batch.length}`;
   await run(`(()=>{window.__sample={start:performance.now(),nativeStart:__nativeTimes.length,parses:__domParses,metricStart:(window.PsychNativeMetrics||window.PsychSoftNavigation?.metrics||[]).length,bytes:performance.getEntriesByType('resource').reduce((s,e)=>s+e.transferSize,0),before:document.querySelector('.site-head').getBoundingClientRect().toJSON(),topicBefore:document.querySelector('#topic-title')?.getBoundingClientRect().toJSON()};performance.mark(${JSON.stringify(id+'-start')});const observer=new MutationObserver(()=>{if(${target}){__sample.firstDOM=performance.now();observer.disconnect()}});observer.observe(document.querySelector('main').parentElement,{childList:true,subtree:true});})()`);
   await run(click);await until(target);await settled();await wait(80);
   const data=await run(`(()=>{const m=(window.PsychNativeMetrics||window.PsychSoftNavigation?.metrics||[]).slice(__sample.metricStart).at(-1),t=__nativeTimes.slice(__sample.nativeStart).at(-1),end=performance.now(),r=document.querySelector('.site-head').getBoundingClientRect().toJSON(),q=document.querySelector('#topic-title')?.getBoundingClientRect().toJSON();performance.mark(${JSON.stringify(id+'-end')});return {id:${JSON.stringify(id)},url:location.href,targetReadyMs:(t?.ready||__sample.firstDOM||end)-__sample.start,clientCommitMs:m?m.committed-(m.prepared||m.loaded||m.started):(__sample.firstDOM||end)-__sample.start,prepareMs:m?(m.prepared||m.loaded||m.started)-m.started:null,metric:m?{started:m.started,prepared:m.prepared,loaded:m.loaded,committed:m.committed,ready:m.ready,finished:m.finished}:null,firstDOM:__sample.firstDOM,native:t||null,domParses:__domParses-__sample.parses,sameDocument:__same===document,sameShell:__head===document.querySelector('.site-head'),anchorDrift:Math.max(Math.abs(r.x-__sample.before.x),Math.abs(r.y-__sample.before.y),${scenario==='topic'?'q&&__sample.topicBefore?Math.abs(q.y-__sample.topicBefore.y):0':'0'}),long:__long.filter(e=>e.start>=__sample.start&&e.start<=end),bytes:performance.getEntriesByType('resource').reduce((s,e)=>s+e.transferSize,0)-__sample.bytes,end}})()`);
   batch.push({...data,version,scenario,temperature,prefetched,round:roundIndex});console.log(JSON.stringify({version,scenario,temperature,prefetched,ready:Math.round(data.targetReadyMs),client:Math.round(data.clientCommitMs)}));
  }
  const repeats=roundIndex===0&&!prefetched?6:1;
  for(let i=0;i<repeats;i++){
   const temperature=i===0?'cold':'warm';
   await measure('paths',temperature,'paths.html',`document.querySelector('.site-head nav a[href*="paths"]').click()`,`!!document.querySelector('h1')?.textContent.includes('学习导图')`);await home();
   await measure('topic',temperature,'?topic=structural-equation-modeling',`document.querySelector('[data-topic-link="structural-equation-modeling"]').click()`,`document.querySelector('#topic-title')?.textContent.includes('结构方程')`);
   await measure('sem',temperature,'terms/sem.html',`document.querySelector('.term-card[data-id="sem"] a[data-expand-card]').click()`,`document.querySelector('.term-content')?.dataset.termId==='sem'`);await home();await choose('foundations');
   await measure('variable',temperature,'terms/variable.html',`document.querySelector('.term-card[data-id="variable"] a[data-expand-card]').click()`,`document.querySelector('.term-content')?.dataset.termId==='variable'`);await home();
  }
  const ended=new Promise(r=>page.events.set('Tracing.tracingComplete',r));await page.send('Tracing.end');await ended;tracing=false;
  const presentation=presentationEvidence(events);
  for(const s of batch){const start=events.find(e=>e.name===s.id+'-start')?.ts,end=events.find(e=>e.name===s.id+'-end')?.ts;s.layout=events.filter(e=>e.name==='Layout'&&e.ph==='X'&&e.ts>=start&&e.ts<=end).map(e=>({ms:e.dur/1000,relativeMs:(e.ts-start)/1000}));s.presentationStatus=presentation.status;}
  const traceFile=`logs/complete-nav/trace-${version}-${roundIndex}-${prefetched}-${stamp}.json`;await writeFile(traceFile,JSON.stringify(events));samples.push(...batch.map(s=>({...s,traceFile})));return presentation;
 }catch(error){failures.push({version,round:roundIndex,prefetched,error:error.message||JSON.stringify(error)});console.error(JSON.stringify(failures.at(-1)));}
 finally{if(tracing){const ended=new Promise(r=>page.events.set('Tracing.tracingComplete',r));await page.send('Tracing.end').catch(()=>{});await Promise.race([ended,wait(1000)]);}await ctx.close();}
}
for(let i=0;i<3;i++)for(const prefetched of [false,true])for(const version of i%2?['new','online','old']:['old','new','online'])await round(version,i,prefetched);
const gate=evaluateGate(samples);if(failures.length){gate.status='fail';gate.reasons.push('One or more target runs failed');}
const output=`logs/complete-nav/comparison-${stamp}.json`;await writeFile(output,JSON.stringify({buildHash:manifest.buildHash,conditions:{width,height:900,freshContextEachRound:true,coldRounds:3,warmVisits:5,cacheEnabled:true,trace:true,actualPresentation:'unmeasured',excludedWait:'Only setup/return legs outside measured marks; preparation and snapshot costs remain included.'},bases,samples,failures,gate},null,2));console.log(output,JSON.stringify(gate));
