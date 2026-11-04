// Deployment regression: existing generated ZIP, local IndexedDB only; all API
// traffic blocked before page load. Never enable generation or send source files.
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,args,wait} from './native-cdp.mjs';
const o=args(),width=Number(o.width||1440),cpu=Number(o.cpu||1),base='https://cdst.site/psy-stats-test/',output=o.output||'.superpowers/sdd/2026-10-25-deployment-followup/browser';
assert.ok(o.zip,'Supply the existing frequency-example ZIP; no model will run');
const overallDeadline=setTimeout(()=>{console.error('QA overall deadline reached; no generation was enabled');process.exit(2);},120000);
const b=await isolatedPage(Number(o.port||9296),width),requests=[],errors=[],responses=[];
const send=b.page.send;
b.page.send=(method,params={})=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP command timed out: '+method)),20000);send(method,params).then(v=>{clearTimeout(timer);resolve(v)},e=>{clearTimeout(timer);reject(e)});});
async function until(expression){const end=Date.now()+60000;while(Date.now()<end){if(await b.run(expression))return;await wait(100);}throw Error('Timeout without renavigation: '+expression);}
try{
 await b.page.send('Page.bringToFront');await b.page.send('Emulation.setCPUThrottlingRate',{rate:cpu});
 if(width<600)await b.page.send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
 await b.page.send('Network.setBlockedURLs',{urls:['*://cdst.site/psy-stats-test/api/*']});
 b.page.events.set('Network.requestWillBeSent',e=>requests.push({url:e.request.url,method:e.request.method}));
 b.page.events.set('Network.responseReceived',e=>responses.push({url:e.response.url,status:e.response.status,disk:e.response.fromDiskCache===true,sw:e.response.fromServiceWorker===true}));
 b.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.exception?.description||e.exceptionDetails.text));
 await b.page.send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__tasks=[];window.__shifts=[];new PerformanceObserver(l=>window.__tasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__shifts.push(...l.getEntries().filter(e=>!e.hadRecentInput).map(e=>e.value))).observe({type:'layout-shift',buffered:true});`});
 await b.page.send('Page.navigate',{url:base+'library/index.html#view=list'});
 await until(`document.querySelector('[data-library-status]')?.textContent.includes('请定期导出完整备份')`);
 const startup=await b.run(`({navigation:performance.getEntriesByType('navigation').map(n=>({ttfb:n.responseStart-n.requestStart,dcl:n.domContentLoadedEventEnd})),tasks:window.__tasks.slice()})`);
 const {root}=await b.page.send('DOM.getDocument'),{nodeId}=await b.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
 await b.page.send('DOM.setFileInputFiles',{nodeId,files:[path.resolve(o.zip)]});await until(`!!document.querySelector('dialog[open]')`);
 await b.run(`[...document.querySelectorAll('dialog button')].find(e=>e.textContent==='导入并保存').click()`);await until(`!document.querySelector('dialog[open]')&&!!document.querySelector('.library-card')`);
 await b.run(`document.querySelector('.library-card').click()`);await until(`!!document.querySelector('.personal-reader figure img')`);
 assert.equal(await b.run(`document.querySelector('.personal-reader h1').textContent`),'频数分布');
 const chart=`document.querySelector('[data-personal-chart]')`,shadow=`${chart}.querySelector('[data-chart-interactive]').shadowRoot`;
 await b.run(`${chart}.scrollIntoView({block:'center',behavior:'instant'})`);await until(`${chart}?.dataset.chartEnhanced==='true'`);await wait(200);
 const cold=await b.run(`({tasks:window.__tasks.slice(),cls:window.__shifts.reduce((a,b)=>a+b,0),measures:performance.getEntriesByType('measure').filter(e=>e.name.startsWith('psych-chart')).map(e=>({name:e.name,start:e.startTime,duration:e.duration}))})`);
 assert.equal(await b.run(`${shadow}.querySelectorAll('g[class^="bar-series"] rect').length`),4);
 const before=requests.length;
 const interaction=await b.run(`(async()=>{const caption=${chart}.parentElement.querySelector('figcaption'),y=caption.getBoundingClientRect().top+scrollY,times=[],start=performance.now();for(let i=0;i<30;i++){const t=performance.now();${shadow}.querySelector('[data-category="'+(i%4)+'"]').click();await new Promise(requestAnimationFrame);times.push(performance.now()-t)}times.sort((a,b)=>a-b);return{p95:times[28],max:Math.max(...times),captionShift:caption.getBoundingClientRect().top+scrollY-y,longTasks:window.__tasks.filter(t=>t.start>=start)}})()`);
 assert.equal(interaction.captionShift,0);assert.equal(requests.length,before,'Instant interactions must not send network requests');
 await b.run(`${shadow}.querySelector('[data-category="2"]').click()`);await until(`${shadow}.querySelector('[data-selection]').dataset.selection==='满意'`);
 await b.run(`${shadow}.querySelector('[data-category="3"]').focus()`);await b.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await b.page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await until(`${shadow}.querySelector('[data-selection]').dataset.selection==='非常满意'`);
 await b.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await until(`${shadow}.querySelector('[data-selection]').dataset.selection===''`);
 if(width<600){const rect=await b.run(`(()=>{const r=${shadow}.querySelector('[data-category="2"]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);await b.page.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[rect]});await b.page.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});}else await b.run(`${shadow}.querySelector('[data-category="2"]').click()`);
 await until(`${shadow}.querySelector('[data-selection]').dataset.selection==='满意'`);
 assert.equal(await b.run(`(()=>{const host=${chart}.querySelector('[data-chart-interactive]'),r=host.getBoundingClientRect(),t=${shadow}.querySelector('.readout').getBoundingClientRect();return t.left>=r.left&&t.right<=r.right+1})()`),true,'Tooltip stays inside chart');
 for(let i=0;i<4;i++){await b.run(`document.querySelectorAll('.quiz-option')[${i}].click()`);assert.ok((await b.run(`document.querySelector('#quiz-feedback').textContent`)).length>10);}
 await b.run(`location.hash='view=list'`);await until(`!!document.querySelector('.library-card')`);await b.run(`document.querySelector('.library-card').click()`);await until(`!!document.querySelector('[data-personal-chart]')`);await b.run(`${chart}.scrollIntoView({block:'center',behavior:'instant'})`);await until(`${chart}?.dataset.chartEnhanced==='true'`);
 assert.equal(await b.run(`${shadow}.querySelector('[data-selection]').dataset.selection`),'满意');
 const warm=await b.run(`performance.getEntriesByName('psych-chart-mount').map(e=>e.duration)`);
 assert.equal(await b.run(`document.documentElement.scrollWidth<=innerWidth+1`),true);
 const apiTraffic=requests.filter(r=>r.url.startsWith(base+'api/')),mutations=requests.filter(r=>!['GET','HEAD'].includes(r.method));assert.equal(apiTraffic.length,0);assert.equal(mutations.length,0);assert.equal(errors.length,0,errors.join('\n'));
 const optional=responses.filter(r=>/\/assets\/charts-[^/]+\//.test(r.url));assert.ok(optional.length>0,'Actually load interactive chart resources');
 const report={status:'functional-pass-performance-reported-separately',target:base,width,cpu,browser:b.version.Browser,conditions:'fresh isolated Edge context; HTTP cache disabled; no renavigation retries; shared browser process; not real phone/display frame validation',apiBlocked:true,apiRequests:0,mutationRequests:0,newModelCalls:0,startup,cold,interaction,warmMountDurations:warm,selectionReturn:true,keyboard:true,touch:width<600,quizOptions:4,optionalResources:optional,errors};
 await mkdir(output,{recursive:true});await writeFile(`${output}/deployed-chart-${width}.json`,JSON.stringify(report,null,2));const shot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(`${output}/deployed-chart-${width}.png`,Buffer.from(shot.data,'base64'));
 console.log(JSON.stringify(report));
}catch(error){await mkdir(output,{recursive:true});await writeFile(`${output}/failure-${width}.json`,JSON.stringify({message:error.message,requests,errors},null,2));throw error;}finally{
 // An unresponsive renderer must not leave this QA process waiting indefinitely.
 const guard=setTimeout(()=>process.exit(2),3500);let disposed=false;
 await Promise.race([b.close().then(()=>{disposed=true;}),wait(3000)]);if(disposed){clearTimeout(guard);clearTimeout(overallDeadline);}
}
