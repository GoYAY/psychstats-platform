import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const [port,rootArg,widthArg='1440']=process.argv.slice(2),root=resolve(rootArg),width=Number(widthArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let id=0;const tasks=new Map(),errors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const t=tasks.get(m.id);if(t){tasks.delete(m.id);m.error?t.reject(m.error):t.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{tasks.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function landed(suffix){for(let i=0;i<100;i++){await wait(30);try{if(await run(`location.pathname.endsWith(${JSON.stringify(suffix)})&&document.readyState==='complete'`)){await wait(900);return}}catch(_){}}throw Error('Navigation timeout '+suffix)}
async function open(page){await send('Page.navigate',{url:pathToFileURL(root+'/'+page).href});await landed('/'+page);}
async function click(selector){const p=await run(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing '+${JSON.stringify(selector)});e.scrollIntoView({block:'center',behavior:'instant'});const b=e.getBoundingClientRect();return {x:b.left+b.width/2,y:b.top+b.height/2}})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await send('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});}
const results=[];
try{
 await send('Page.enable');await send('Runtime.enable');
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});
 await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:`(()=>{let token=0;function sample(){const mine=++token,start=performance.now();window.__analysisFrames=[];function frame(){if(mine!==token)return;const p=document.querySelector('.term-transition-panel'),b=p?.getBoundingClientRect();if(b)window.__analysisFrames.push({width:b.width,height:b.height,x:b.x,y:b.y,border:getComputedStyle(p).borderTopWidth,shadow:getComputedStyle(p).boxShadow});if(performance.now()-start<1200)requestAnimationFrame(frame)}requestAnimationFrame(frame)}sample();addEventListener('pageshow',e=>{if(e.persisted)sample()})})()`});
 for(const method of ['breadcrumb','browser-back','top-nav']){
  await open('analysis.html');
  assert.ok(await run(`!!document.querySelector('.analysis-card[data-analysis-id="logistic"][data-expand-card]')`),'Analysis cards expose expansion entry');
  await run(`document.querySelector('#analysis-filter').value='回归';document.querySelector('#analysis-filter').dispatchEvent(new Event('input',{bubbles:true}))`);
  await click('.analysis-card[data-analysis-id="logistic"] h3');await landed('/analyses/logistic.html');
  const forward=await run('window.__analysisFrames');
  assert.ok(forward.length>=3&&forward.at(-1).width>forward[0].width+20,'Card opens into full page');
  assert.ok(forward.every(f=>f.border==='0px'&&f.shadow==='none'),'No outlined intermediate page');
  if(method==='browser-back')await run('history.back()');
  else await click(method==='breadcrumb'?'[data-collapse-analysis]':'.site-head nav a[href="../analysis.html"]');
  await landed('/analysis.html');
  const backward=await run('window.__analysisFrames');
  assert.ok(backward.length>=3&&backward[0].width>backward.at(-1).width+20,'Details shrink into original card: '+method);
  assert.ok(await run(`document.querySelector('#analysis-filter').value==='回归'&&!document.querySelector('.analysis-card[data-analysis-id="logistic"]').hidden`),'Filter and originating card restored');
  const box=await run(`(()=>{const b=document.querySelector('.analysis-card[data-analysis-id="logistic"]').getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height}})()`);
  assert.ok(Math.abs(box.x-backward.at(-1).x)<8&&Math.abs(box.y-backward.at(-1).y)<8,'Return finishes at original card');
  assert.ok(await run(`!document.querySelector('.term-transition-scene')&&!document.documentElement.classList.contains('term-transition-pending')`),'Temporary layers cleared');
  results.push({method,forwardFrames:forward.length,backwardFrames:backward.length});
 }
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 await open('analysis.html');await click('.analysis-card[data-analysis-id="logistic"] h3');await landed('/analyses/logistic.html');
 assert.equal((await run('window.__analysisFrames')).length,0,'Reduced motion bypasses animation');
 await click('[data-collapse-analysis]');await landed('/analysis.html');
 assert.ok(await run(`!document.querySelector('.term-transition-scene')`));
 assert.equal(errors.length,0,errors.join('\n'));
 await writeFile(`logs/analysis-card-motion-${width}.json`,JSON.stringify({width,results,reducedMotion:true},null,2));
 console.log(JSON.stringify({passed:true,width,results,reducedMotion:true}));
}finally{ws.close()}
