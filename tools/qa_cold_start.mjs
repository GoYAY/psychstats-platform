// Read-only deployed/local QA. Existing package goes only to local IndexedDB.
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,args,wait} from './native-cdp.mjs';
import {summarizeCPUProfile} from './cold-start-profile.mjs';
const o=args(),base=new URL(o.url||'https://cdst.site/psy-stats-test/'),width=Number(o.width||390),cpu=Number(o.cpu||4);
assert.ok(base.origin==='https://cdst.site'&&base.pathname==='/psy-stats-test/'||base.hostname==='127.0.0.1','Only the test site or loopback');
assert.ok(!base.search&&!base.hash,'No credentials or query data');
const output=o.output||'.superpowers/sdd/2026-10-25-cold-start-optimization/baseline-online',sampling=o.profile!=='off',latency=Number(o.latency||0);
const deadline=setTimeout(()=>{console.error('Bounded profiling deadline reached');process.exit(2);},150000);
const b=await isolatedPage(Number(o.port||9296),width),send=b.page.send,requests=new Map(),errors=[],phases=[],trace=[];
b.page.send=(method,params={})=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP timeout: '+method)),20000);send(method,params).then(r=>{clearTimeout(timer);resolve(r)},e=>{clearTimeout(timer);reject(e)});});
async function until(expression){const end=Date.now()+50000;while(Date.now()<end){if(await b.run(expression))return;await wait(100);}throw Error('Bounded condition timeout: '+expression);}
async function phase(name,action){
 const start=name==='startup'?0:await b.run('performance.now()');if(sampling)await b.page.send('Profiler.start');
 try{await action();}finally{
  const profile=sampling?(await b.page.send('Profiler.stop')).profile:null,end=await b.run('performance.now()');
  phases.push({name,start,end,cpu:profile?summarizeCPUProfile(profile):null});
 }
}
try{
 await b.page.send('Page.bringToFront');await b.page.send('Emulation.setCPUThrottlingRate',{rate:cpu});
 await b.page.send('Profiler.enable');await b.page.send('Profiler.setSamplingInterval',{interval:1000});
 if(o.trace==='on'){
  b.page.events.set('Tracing.dataCollected',e=>{for(const item of e.value)if(item.ph==='X'&&item.dur>=5000)trace.push({name:item.name,start:item.ts/1000,duration:item.dur/1000,pid:item.pid,tid:item.tid,data:item.args?.data&&{url:item.args.data.url,scriptName:item.args.data.scriptName,functionName:item.args.data.functionName}});});
  await b.page.send('Tracing.start',{categories:'devtools.timeline,v8,disabled-by-default-v8.compile',transferMode:'ReportEvents'});
 }
 if(latency)await b.page.send('Network.emulateNetworkConditions',{offline:false,latency,downloadThroughput:-1,uploadThroughput:-1,connectionType:'wifi'});
 await b.page.send('Network.setBlockedURLs',{urls:['*://cdst.site/*/api/*','*://127.0.0.1:*/api/*','*://127.0.0.1:*/*/api/*']});
 b.page.events.set('Network.requestWillBeSent',e=>requests.set(e.requestId,{url:e.request.url,method:e.request.method,start:e.timestamp,initiator:e.initiator?.type}));
 b.page.events.set('Network.responseReceived',e=>Object.assign(requests.get(e.requestId)||{},{status:e.response.status,encoding:e.response.headers?.['content-encoding'],cache:e.response.fromDiskCache===true,sw:e.response.fromServiceWorker===true,timing:e.response.timing}));
 b.page.events.set('Network.loadingFinished',e=>Object.assign(requests.get(e.requestId)||{},{end:e.timestamp,encodedBytes:e.encodedDataLength}));
 b.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.exception?.description||e.exceptionDetails.text));
 await b.page.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__tasks=[];window.__shifts=[];new PerformanceObserver(l=>window.__tasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__shifts.push(...l.getEntries().filter(e=>!e.hadRecentInput).map(e=>e.value))).observe({type:'layout-shift',buffered:true});`});
 await phase('startup',async()=>{
  await b.page.send('Page.navigate',{url:new URL('library/index.html#view=list',base).href});
  await until(`document.querySelector('[data-library-status]')?.textContent.includes('请定期导出完整备份')`);
 });
 if(o.zip){
  await phase('package-parse',async()=>{
   const {root}=await b.page.send('DOM.getDocument'),{nodeId}=await b.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
   await b.page.send('DOM.setFileInputFiles',{nodeId,files:[path.resolve(o.zip)]});await until(`!!document.querySelector('dialog[open]')`);
  });
  await phase('package-save',async()=>{
   await b.run(`[...document.querySelectorAll('dialog button')].find(e=>e.textContent==='导入并保存').click()`);
   await until(`!document.querySelector('dialog[open]')&&!!document.querySelector('.library-card')`);
  });
  await phase('reader-and-chart',async()=>{
   await b.run(`document.querySelector('.library-card').click()`);await until(`!!document.querySelector('.personal-reader figure img')`);
   await b.run(`document.querySelector('[data-personal-chart]').scrollIntoView({block:'center',behavior:'instant'})`);
   await until(`document.querySelector('[data-personal-chart]')?.dataset.chartEnhanced==='true'`);
  });
 }
 const metrics=await b.run(`({url:location.href,navigation:performance.getEntriesByType('navigation').map(n=>({ttfb:n.responseStart-n.requestStart,dcl:n.domContentLoadedEventEnd})),resources:performance.getEntriesByType('resource').filter(r=>r.name.startsWith(location.origin)).map(r=>({url:r.name,start:r.startTime,duration:r.duration,responseStart:r.responseStart,transfer:r.transferSize,encoded:r.encodedBodySize,decoded:r.decodedBodySize})),tasks:window.__tasks,cls:window.__shifts.reduce((a,b)=>a+b,0),measures:performance.getEntriesByType('measure').filter(m=>m.name.startsWith('psych-chart')).map(m=>({name:m.name,start:m.startTime,duration:m.duration}))})`);
 const traffic=[...requests.values()].filter(r=>r.url.startsWith('http'));
 assert.equal(traffic.filter(r=>new URL(r.url).pathname.includes('/api/')).length,0);assert.equal(traffic.filter(r=>!['GET','HEAD'].includes(r.method)).length,0);assert.deepEqual(errors,[]);
 if(o.trace==='on'){const completed=new Promise(resolve=>b.page.events.set('Tracing.tracingComplete',resolve));await b.page.send('Tracing.end');await Promise.race([completed,wait(3000)]);}
 const result={browser:b.version.Browser,conditions:'isolated context; HTTP cache disabled; existing shared headless process; not real phone/display timing',sampling,emulatedLatencyMs:latency,width,cpu,apiRequests:0,mutationRequests:0,phases,metrics,requests:traffic,errors,trace:trace.sort((a,b)=>b.duration-a.duration).slice(0,150)};
 await mkdir(output,{recursive:true});await writeFile(output+'/profile-'+width+'.json',JSON.stringify(result,null,2));
 console.log(JSON.stringify({output,width,cpu,phases:phases.map(p=>({name:p.name,duration:p.end-p.start,cpuSampleMs:p.cpu?.sampledMs,idleMs:p.cpu?.idleMs,top:p.cpu?.functions.slice(0,6)})),tasks:metrics.tasks,measures:metrics.measures}));
}catch(e){await mkdir(output,{recursive:true});await writeFile(output+'/failure-'+width+'.json',JSON.stringify({error:e.message,phases,requests:[...requests.values()],errors},null,2));throw e;}
finally{await Promise.race([b.close(),wait(3000)]);clearTimeout(deadline);setTimeout(()=>process.exit(),100).unref();}
