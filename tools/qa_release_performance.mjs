// Local measured windows, not a claim about deployed/iPhone frame rate.
import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {isolatedPage,args,wait} from './native-cdp.mjs';
const o=args(),width=Number(o.width||390),cpu=Number(o.cpu||4),base=o.url||'http://127.0.0.1:8892/site/online-release-preview/',output=o.output||'.superpowers/sdd/2026-10-24-online-release-readiness/performance',b=await isolatedPage(9296,width);
assert.ok(o.zip);const blocked=o.static==='true';
try{
 await b.page.send('Page.bringToFront');await b.page.send('Emulation.setCPUThrottlingRate',{rate:cpu});
 if(blocked)await b.page.send('Network.setBlockedURLs',{urls:['*/assets/charts-*/*.mjs']});
 await b.page.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__tasks=[];window.__shifts=[];new PerformanceObserver(l=>window.__tasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__shifts.push(...l.getEntries().filter(e=>!e.hadRecentInput).map(e=>e.value))).observe({type:'layout-shift',buffered:true});`});
 await b.page.send('Page.navigate',{url:new URL('library/index.html',base).href});await b.until(`document.querySelector('[data-library-status]')?.textContent.includes('请定期导出完整备份')`);
 const cold=await b.run(`({now:performance.now(),tasks:window.__tasks,cls:window.__shifts.reduce((a,b)=>a+b,0)})`);
 const {root}=await b.page.send('DOM.getDocument'),{nodeId}=await b.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
 await b.page.send('DOM.setFileInputFiles',{nodeId,files:[path.resolve(o.zip)]});await b.until(`!!document.querySelector('dialog[open]')`);await b.run(`[...document.querySelectorAll('dialog button')].find(e=>e.textContent==='导入并保存').click()`);await b.until(`!document.querySelector('dialog[open]')&&!!document.querySelector('.library-card')`);
 const profiling=o.profile==='true';
 if(profiling){await b.page.send('Profiler.enable');await b.page.send('Profiler.setSamplingInterval',{interval:1000});await b.page.send('Profiler.start');}
 const start=await b.run('performance.now()');await b.run(`document.querySelector('.library-card').click()`);await b.until(`!!document.querySelector('.personal-reader figure img')`);await b.run(`document.querySelector('[data-personal-chart]').scrollIntoView({block:'center',behavior:'instant'})`);
 if(!blocked)await b.until(`document.querySelector('[data-personal-chart]')?.dataset.chartEnhanced==='true'`);else await wait(1200);
 await wait(300);const end=await b.run('performance.now()');const profile=profiling?(await b.page.send('Profiler.stop')).profile:{nodes:[]};
 const sampled=profile.nodes.filter(n=>n.hitCount).sort((a,b)=>b.hitCount-a.hitCount).slice(0,18).map(n=>({function:n.callFrame.functionName,url:n.callFrame.url,hits:n.hitCount}));
 const result=await b.run(`({tasks:window.__tasks,cls:window.__shifts.reduce((a,b)=>a+b,0),measures:performance.getEntriesByType('measure').filter(e=>e.name.startsWith('psych-chart')).map(e=>({name:e.name,start:e.startTime,duration:e.duration})),visibility:document.visibilityState,overflow:document.documentElement.scrollWidth>innerWidth+1})`);
 const chartTasks=result.tasks.filter(t=>result.measures.some(m=>t.start<m.start+m.duration&&t.start+t.duration>m.start));
 const report={width,cpu,blocked,scope:'local Edge,simulated CPU/mobile,not real phone or online',cold,readerWindow:{start,end,tasks:result.tasks.filter(t=>t.start>=start&&t.start<end)},chartTasks,sampled,...result};
 await mkdir(output,{recursive:true});await writeFile(`${output}/${blocked?'static':'interactive'}-${width}.json`,JSON.stringify(report,null,2));console.log(JSON.stringify({width,blocked,coldMaxTask:Math.max(0,...cold.tasks.map(t=>t.duration)),chartTasks,measures:result.measures,sampled:sampled.slice(0,7)}));assert.equal(result.overflow,false);
}finally{await b.close();}
