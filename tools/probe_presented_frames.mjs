import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {args,connect,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9293',term='sem',site='next',layout='native',target}=args();
async function attachedTestPage(){
 const targets=await(await fetch(`http://127.0.0.1:${cdp}/json`)).json(),item=targets.find(t=>t.id===target);
 assert.ok(item?.type==='page'&&/^(http:\/\/127\.0\.0\.1:8766\/|https:\/\/vibe-hub\.org\/)/.test(item.url),'Only explicit preview/reference test target may be reused');
 const page=connect(item.webSocketDebuggerUrl);await page.ready;for(const method of ['Page.enable','Runtime.enable','Network.enable'])await page.send(method);
 await page.send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
 const run=async expression=>{const r=await page.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value;};
 const until=async expression=>{for(let i=0;i<200;i++){if(await run(expression))return;await wait(50);}throw Error('Timeout: '+expression);};
 return {page,run,until,version:await(await fetch(`http://127.0.0.1:${cdp}/json/version`)).json(),close:async()=>page.ws.close()};
}
const ctx=target?await attachedTestPage():await isolatedPage(cdp),{page,run,until}=ctx,trace=[];
const base=site==='online-test'?'https://cdst.site/psy-stats-test/':site==='online'?'https://cdst.site/psy-stats/':site==='deployed-local'?'http://127.0.0.1:8765/psy-stats/':'http://127.0.0.1:8766/psy-stats/';
const home=site==='vibehub'?'https://vibe-hub.org/topics/technology':`${base}index.html?topic=${term==='sem'?'structural-equation-modeling':'foundations'}`;
const path=site==='vibehub'?'/hash':`${new URL(base).pathname}terms/${term}.html`;
let tracing=false;
try{
 await page.send('Network.setCacheDisabled',{cacheDisabled:false});
 await page.send('Page.navigate',{url:home});
 await page.send('Page.bringToFront');
 await until("document.readyState==='complete'&&!!document.querySelector('main')");await wait(250);
 const visibility=await run('document.visibilityState');if(visibility!=='visible')throw Error('Visible document required');
 if(layout==='visible')await run(`(()=>{const style=document.createElement('style');style.textContent='.term-content>section{content-visibility:visible!important}';document.head.append(style)})()`);
 if(layout==='freeze-tail')await run(`(()=>{const style=document.createElement('style');style.textContent='html[data-psych-transition=expand] .term-content>section:nth-of-type(n+4){content-visibility:hidden!important}';document.head.append(style)})()`);
 await run(`(()=>{const original=document.startViewTransition?.bind(document);if(original)document.startViewTransition=(...args)=>{const result=original(...args);result.ready.then(()=>performance.mark('presentation-native-ready'),()=>{});result.finished.then(()=>performance.mark('presentation-native-finished'),()=>{});return result}})()`);
 await run(`(()=>{window.__probeResources=performance.getEntriesByType('resource').length;if(window.PsychSoftMotion){const original=PsychSoftMotion.transition;PsychSoftMotion.transition=async function(...args){performance.mark('presentation-soft-start');const value=await original.apply(this,args);performance.mark('presentation-soft-finished');return value}}})()`);
 page.events.set('Tracing.dataCollected',e=>trace.push(...e.value));
 await page.send('Tracing.start',{categories:'devtools.timeline,blink.user_timing,benchmark,cc,viz,gpu,disabled-by-default-devtools.timeline.frame',transferMode:'ReportEvents'});tracing=true;
 await run(`(()=>{performance.mark('presentation-probe-start');const link=${site==='vibehub'?`[...document.querySelectorAll('main a[href]')].find(a=>new URL(a.href).pathname===${JSON.stringify(path)})`:`document.querySelector('.term-card[data-id="${term}"] a[data-expand-card]')`};if(!link)throw Error('Real visible destination link required');link.click()})()`);
 await until(`location.pathname===${JSON.stringify(path)}&&!document.documentElement.dataset.psychTransition&&!window.PsychSoftMotion?.running&&!document.querySelector('.next-load-status')`);await wait(600);
 await run("performance.mark('presentation-probe-end')");
 const ended=new Promise(resolve=>page.events.set('Tracing.tracingComplete',resolve));await page.send('Tracing.end');await ended;tracing=false;
 const start=trace.find(e=>e.name==='presentation-probe-start'),end=trace.find(e=>e.name==='presentation-probe-end');
 const events=trace.filter(e=>e.ts>=start.ts&&e.ts<=end.ts),names={};
 for(const e of events)if(/FramePresented|FrameSequence|PipelineReporter|Presentation|DrawAndSwap|Display::Draw|DroppedFrame/i.test(e.name))names[e.name]=(names[e.name]||0)+1;
 const data={browser:ctx.version.Browser,userAgent:ctx.version['User-Agent'],visibility,reusedTarget:!!target,site,layout,term,metrics:await run('(window.PsychNativeMetrics||window.PsychSoftNavigation?.metrics)?.at(-1)||null'),resources:await run(`performance.getEntriesByType('resource').slice(__probeResources).map(r=>({name:r.name,start:r.startTime,duration:r.duration,responseStart:r.responseStart,responseEnd:r.responseEnd,transferSize:r.transferSize,decodedBodySize:r.decodedBodySize,encodedBodySize:r.encodedBodySize,protocol:r.nextHopProtocol,initiatorType:r.initiatorType}))`),start,end,names,presentationEvents:events.filter(e=>/FramePresented|FrameSequence|Presentation|DroppedFrame/i.test(e.name)),traceEvents:trace};
 await mkdir('logs/complete-nav',{recursive:true});const file=`logs/complete-nav/presentation-probe-${site}-${term}-${Date.now()}.json`;await writeFile(file,JSON.stringify(data));console.log(JSON.stringify({file,browser:data.browser,visibility,names,metrics:data.metrics}));
}finally{if(tracing)await page.send('Tracing.end').catch(()=>{});await ctx.close();}
