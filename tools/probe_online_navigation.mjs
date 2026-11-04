import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,wait,args} from './native-cdp.mjs';
const {cdp='9293',site='online'}=args();
const base=site==='online-test'?'https://cdst.site/psy-stats-test/':'https://cdst.site/psy-stats/';
const ctx=await isolatedPage(cdp),{page,run,until}=ctx;
const trace=[],failures=[],responses=[],actions=[];
let tracing=false;
page.events.set('Runtime.exceptionThrown',e=>failures.push({type:'exception',detail:e.exceptionDetails}));
page.events.set('Network.loadingFailed',e=>failures.push({type:'network',...e}));
page.events.set('Network.responseReceived',e=>responses.push({url:e.response.url,status:e.response.status,protocol:e.response.protocol,fromDiskCache:e.response.fromDiskCache,fromServiceWorker:e.response.fromServiceWorker}));
async function action(name,expression,ready){
 const before=await run("({resourceCount:performance.getEntriesByType('resource').length,time:performance.now(),url:location.href})");
 await run(`performance.mark(${JSON.stringify(name+'-start')});${expression}`);
 await until(ready+"&&!document.documentElement.dataset.psychTransition&&!window.PsychSoftMotion?.running&&!document.querySelector('.soft-navigation-status:not([hidden])')");
 await wait(1000);
 const after=await run(`(()=>{performance.mark(${JSON.stringify(name+'-end')});return {time:performance.now(),url:location.href,visibility:document.visibilityState,metric:window.PsychSoftNavigation?.metrics?.at(-1)||null,resources:performance.getEntriesByType('resource').slice(${before.resourceCount}).map(r=>({url:r.name,start:r.startTime,end:r.responseEnd,duration:r.duration,transferSize:r.transferSize,initiator:r.initiatorType})),heading:document.querySelector('main h1')?.textContent,topic:document.querySelector('[data-topic-link][aria-current="page"]')?.dataset.topicLink}})()`);
 if(after.visibility!=='visible')throw Error('Test window no longer visible');
 actions.push({name,before,after});
 console.log(JSON.stringify({name,url:after.url,metric:after.metric,resources:after.resources.length}));
}
try{
 await page.send('Network.setCacheDisabled',{cacheDisabled:false});
 await page.send('Page.navigate',{url:base+'index.html?topic=foundations'});
 await page.send('Page.bringToFront');
 await until("document.readyState==='complete'&&!!document.querySelector('.topic-nav')");
 await wait(500);
 if(await run('document.visibilityState')!=='visible')throw Error('Visible independent browser required');
 await run(`(()=>{const original=window.PsychSoftMotion?.transition;if(original)PsychSoftMotion.transition=async function(...a){performance.mark('online-soft-start');const value=await original.apply(this,a);performance.mark('online-soft-finished');return value}})()`);
 page.events.set('Tracing.dataCollected',e=>trace.push(...e.value));
 await page.send('Tracing.start',{categories:'devtools.timeline,blink.user_timing,benchmark,cc,viz,gpu,disabled-by-default-devtools.timeline.frame',transferMode:'ReportEvents'});tracing=true;
 await action('topic-out',`document.querySelector('[data-topic-link="hypothesis-testing"]').click()`,"document.querySelector('[data-topic-link=\"hypothesis-testing\"]')?.getAttribute('aria-current')==='page'");
 await action('topic-back',`document.querySelector('[data-topic-link="foundations"]').click()`,"document.querySelector('[data-topic-link=\"foundations\"]')?.getAttribute('aria-current')==='page'");
 await action('paths-cold',`[...document.querySelectorAll('.site-head nav a')].find(a=>new URL(a.href).pathname.endsWith('/paths.html')).click()`,"location.pathname.endsWith('/paths.html')&&!document.querySelector('.topic-nav')");
 await action('home-return',`[...document.querySelectorAll('.site-head nav a')].find(a=>new URL(a.href).pathname.endsWith('/index.html')).click()`,"location.pathname.endsWith('/index.html')&&!!document.querySelector('.topic-nav')");
 await action('variable-cold',`document.querySelector('.term-card[data-id="variable"] a[data-expand-card]').click()`,"location.pathname.endsWith('/terms/variable.html')&&!!document.querySelector('.term-content')");
 await action('variable-return',`history.back()`,"location.pathname.endsWith('/index.html')&&!!document.querySelector('.topic-nav')");
 await action('variable-warm',`document.querySelector('.term-card[data-id="variable"] a[data-expand-card]').click()`,"location.pathname.endsWith('/terms/variable.html')&&!!document.querySelector('.term-content')");
 const ended=new Promise(resolve=>page.events.set('Tracing.tracingComplete',resolve));await page.send('Tracing.end');await ended;tracing=false;
 const summaries=actions.map(a=>{
  const start=trace.find(e=>e.name===a.name+'-start'),end=trace.find(e=>e.name===a.name+'-end');
  const scoped=trace.filter(e=>e.pid===start?.pid&&e.tid===start?.tid&&e.ts>=start.ts&&e.ts<=end.ts);
  const duration=name=>scoped.filter(e=>e.name===name&&e.ph==='X').map(e=>e.dur/1000);
  return {name:a.name,pid:start?.pid,tid:start?.tid,layouts:duration('Layout'),paints:duration('Paint'),longTasks:scoped.filter(e=>e.ph==='X'&&e.name==='RunTask'&&e.dur>50000).map(e=>({start:e.ts,duration:e.dur/1000})),motionMarks:scoped.filter(e=>/^online-soft/.test(e.name)).map(e=>({name:e.name,ts:e.ts}))};
 });
 await mkdir('logs/complete-nav',{recursive:true});
 const file=`logs/complete-nav/${site}-browser-batch-${Date.now()}.json`;
 await writeFile(file,JSON.stringify({browser:ctx.version.Browser,base,network:'Actual online, no throttling, fresh isolated context with cache enabled',actions,summaries,failures,responses,traceEvents:trace}));
 console.log(JSON.stringify({file,summaries,failures}));
}finally{if(tracing)await page.send('Tracing.end').catch(()=>{});await ctx.close();}
