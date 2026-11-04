import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {isolatedPage,wait,args} from './native-cdp.mjs';
const {port='8769',width='390',cdp='9292'}=args(),base=`http://127.0.0.1:${port}/psy-stats/`,results=[];
const ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx;
try{
 await page.send('Network.setCacheDisabled',{cacheDisabled:false});
 await page.send('Page.navigate',{url:base+'index.html?topic=foundations'});
 await until("document.readyState==='complete'&&!!window.PsychSoftNavigation");
 await run("document.querySelector('.term-card[data-id=variable]').scrollIntoView({block:'center'})");await wait(2000);
 await run("document.querySelector('.term-card[data-id=normal-distribution]').scrollIntoView({block:'center'})");await wait(2000);
 const later=await run(`!!PsychSoftNavigation.cache.get(${JSON.stringify(base+'terms/normal-distribution.html')})`);
 results.push({case:'scroll reveals a later card after the initial two',pass:later});
}finally{await ctx.close();}
const cold=await isolatedPage(cdp,Number(width));
try{
 await cold.page.send('Network.setCacheDisabled',{cacheDisabled:false});
 await cold.page.send('Network.emulateNetworkConditions',{offline:false,latency:250,downloadThroughput:-1,uploadThroughput:-1});
 await cold.page.send('Page.addScriptToEvaluateOnNewDocument',{source:"Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'4g'}})"});
 await cold.page.send('Page.navigate',{url:base+'index.html?topic=foundations'});
 await cold.until("document.readyState==='complete'&&!!window.PsychSoftNavigation");await wait(200);
 await cold.run(`window.__requestStart=performance.now();PsychSoftNavigation.navigate(${JSON.stringify(base+'terms/sem.html')})`);
 await cold.until("location.pathname.endsWith('/terms/sem.html')&&!PsychSoftMotion.running&&document.querySelector('.soft-navigation-status').hidden");
 const evidence=await cold.run("({metric:PsychSoftNavigation.metrics.at(-1),resources:performance.getEntriesByType('resource').filter(r=>r.startTime>=__requestStart&&/sem.html|sem(?:-mobile)?\\.svg|woff/.test(r.name)).map(r=>({url:r.name,start:r.startTime,end:r.responseEnd}))})");
 const html=evidence.resources.find(r=>new URL(r.url).pathname.endsWith('/terms/sem.html'));
 const image=evidence.resources.find(r=>/sem(?:-mobile)?\.svg/.test(r.url));
 const fonts=evidence.resources.filter(r=>/woff/.test(r.url));
 results.push({case:'critical image starts before destination HTML finishes',pass:!!image&&image.start<html.end});
 results.push({case:'all required fonts start before destination HTML finishes',pass:fonts.length===3&&fonts.every(r=>r.start<html.end)});
 const file=`logs/complete-nav/prefetch-coverage-${port}-${width}-${Date.now()}.json`;
 await mkdir('logs/complete-nav',{recursive:true});await writeFile(file,JSON.stringify({base,width,latency:250,backgroundPrefetchDisabled:true,results,evidence},null,2));
 console.log(JSON.stringify({file,results,evidence}));assert.ok(results.every(r=>r.pass),'Prefetch coverage/parallel preparation failed');
}finally{await cold.close();}
