import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [port,root,widthArg='1280',mode='all']=process.argv.slice(2),width=Number(widthArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const tasks=new Map(),errors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const t=tasks.get(m.id);if(t){tasks.delete(m.id);m.error?t.reject(m.error):t.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{tasks.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function open(page){await send('Page.navigate',{url:new URL(page,pathToFileURL(root+'/')).href});await wait(850)}
async function click(s){await run(`document.querySelector(${JSON.stringify(s)}).click()`);await wait(850)}
const sampler=`
window.__motionFrames=[];
addEventListener('pagehide',()=>{const m=document.querySelector('body>main');sessionStorage.setItem('qa.sourceOpacity',m?getComputedStyle(m).opacity:'1')});
window.__sampleMotion=()=>{
 window.__motionFrames=[];const start=performance.now();
 function f(){
  const m=document.querySelector('body>main'),t=document.querySelector('#topic-intro'),p=document.querySelector('.nav-motion-indicator'),a=document.querySelector('.sequence-previous');
  const incoming=document.querySelector('.topic-cover-next,.navigation-cover-next'),oldScene=document.querySelector('.term-transition-scene:not(.topic-cover-next):not(.navigation-cover-next)');
  const oldHost=oldScene?.querySelector('.term-transition-snapshot'),oldCard=oldHost?.shadowRoot?.querySelector('.term-card');
  const matrix=e=>e?new DOMMatrixReadOnly(getComputedStyle(e).transform):new DOMMatrixReadOnly();
  const alpha=incoming?Number(getComputedStyle(incoming).opacity):(m?Number(getComputedStyle(m).opacity):1),base=oldScene?Number(getComputedStyle(oldScene).opacity):0;
  const edge=oldCard?getComputedStyle(oldCard):null;
  window.__motionFrames.push({opacity:m?Number(getComputedStyle(m).opacity):1,topic:t?Number(getComputedStyle(t).opacity):1,x:matrix(m).m41,y:matrix(m).m42,scale:matrix(incoming||m).m11,topicX:matrix(incoming).m41,topicY:matrix(incoming).m42,topicScale:matrix(incoming).m11,incoming:alpha,coverage:alpha+(1-alpha)*base,old:!!oldHost?.shadowRoot?.querySelector('main'),oldX:matrix(oldScene).m41,duration:incoming?.getAnimations()[0]?.effect?.getTiming().duration,headerX:document.querySelector('.site-head').getBoundingClientRect().x,pageSnapshot:!!incoming?.classList.contains('navigation-cover-next')&&!!incoming.querySelector('.term-transition-snapshot')?.shadowRoot?.querySelector('main'),oldVisible:oldScene?getComputedStyle(oldScene).visibility==='visible':false,oldBorder:edge?edge.borderColor+'|'+edge.borderWidth+'|'+edge.boxShadow:null,pill:p?p.getBoundingClientRect().x:null,arrowY:a?a.getBoundingClientRect().top:null,active:document.documentElement.className,theme:t?.dataset.topic});
  if(performance.now()-start<700)requestAnimationFrame(f)
 }
 requestAnimationFrame(f)
};window.__sampleMotion();`;
const results=[];
try{
 await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:sampler});
 if(mode==='all'||mode==='borders'){
  await open('index.html');
  const edge=await run(`(()=>{const c=document.querySelector('.term-card:not([hidden])');c.querySelector('a[data-expand-card]').focus();const s=getComputedStyle(c);return s.borderColor+'|'+s.borderWidth+'|'+s.boxShadow})()`);
  await wait(200);
  const settledEdge=await run(`(()=>{const s=getComputedStyle(document.querySelector('.term-card:not([hidden])'));return s.borderColor+'|'+s.borderWidth+'|'+s.boxShadow})()`);
  await run('window.__sampleMotion()');await click('[data-topic-link="regression"]');
  const frames=await run('window.__motionFrames');
  assert.ok(frames.some(f=>f.oldVisible&&f.oldBorder),'Source cards are available during transition');
  assert.ok(frames.filter(f=>f.oldVisible&&f.oldBorder).every(f=>f.oldBorder===settledEdge),'Snapshot retains the real focused-card border and shadow without a style flash');
  results.push({case:'borders',edge:settledEdge});
 }
 if(mode==='all'||mode==='topics'){
  await open('index.html');await run('window.__sampleMotion()');await click('[data-topic-link="regression"]');
  let frames=await run('window.__motionFrames');assert.ok(frames.every(f=>f.topic===1&&f.opacity===1),'Theme never fades to white');
  assert.ok(frames.every(f=>Math.abs(f.topicY)<0.01&&Math.abs(f.topicX)<0.01),'Theme has no X/Y slide');
  assert.ok(frames.some(f=>f.topicScale<0.999&&f.incoming>0.02&&f.incoming<0.98&&f.old),'New theme emerges in depth over the old view');
  assert.ok(frames.every(f=>f.coverage>=0.999),'Theme never exposes a blank frame');
  assert.equal(await run('document.querySelector("#topic-intro").dataset.topic'),'regression');
  await run('window.__sampleMotion();document.querySelector("[data-topic-link=foundations]").click();document.querySelector("[data-topic-link=factor-analysis]").click();document.querySelector("[data-topic-link=regression]").click()');await wait(700);
  assert.ok(await run(`document.querySelector('#topic-intro').dataset.topic==='regression'&&[...document.querySelectorAll('.term-card:not([hidden])')].every(e=>e.dataset.topic==='regression')&&getComputedStyle(document.querySelector('#topic-intro')).opacity==='1'`),'Rapid input ends on latest topic without stale opacity');
  assert.ok(await run(`!document.querySelector('.topic-cover-scene')&&!document.querySelector('.topic-cover-surface')&&!document.documentElement.classList.contains('topic-cover-active')`),'Rapid input removes all temporary layers');
  await run('window.__sampleMotion()');await click('[data-topic-link="regression"]');assert.ok((await run('window.__motionFrames')).every(f=>f.topic===1),'Same topic does not replay');
  await run('window.__sampleMotion()');await click('.site-head nav a[href="index.html"]');
  assert.ok(await run(`document.querySelector('#topic-intro').dataset.topic==='regression'&&location.search==='?topic=regression'&&window.__motionFrames.every(f=>f.opacity===1)`),'Current terms navigation keeps the selected topic and does not replay');
  results.push({case:'topics',frames});
 }
 if(mode==='all'||mode==='pages'){
  await open('paths.html');
  await run(`document.querySelector('.site-head nav a[href="datasets.html"]').click()`);
  await wait(140);
  if(width===1280){const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/navigation-motion-header-mid.png',Buffer.from(shot.data,'base64'));}
  await wait(650);let frames=await run('window.__motionFrames');
  assert.equal(await run(`sessionStorage.getItem('qa.sourceOpacity')`),'1','Old page stays opaque until navigation');
  assert.ok(frames.every(f=>Math.abs(f.x)<0.01&&Math.abs(f.y)<0.01),'Main page has no X/Y slide');
  assert.ok(frames.some(f=>f.scale<0.999&&f.incoming>0.02&&f.incoming<0.98&&f.old),'New main page emerges in depth over the old view');
  assert.ok(frames.some(f=>f.pageSnapshot&&f.scale<0.999&&f.incoming>0.02&&f.incoming<0.98),'Header navigation uses the same snapshot-layer emergence as topics');
  assert.ok(frames.every(f=>f.coverage>=0.999),'Main navigation never exposes a blank frame');
  let positions=frames.filter(f=>f.pill!==null).map(f=>f.pill);assert.ok(positions.length>=4&&Math.max(...positions)-Math.min(...positions)>30,'One navigation shadow slides to the destination');
  assert.ok(await run(`location.pathname.endsWith('/datasets.html')&&document.querySelectorAll('.nav-motion-indicator').length===1&&getComputedStyle(document.querySelector('main')).opacity==='1'&&!document.documentElement.classList.contains('term-transition-pending')`));
  await run('history.back()');await wait(850);
  assert.ok(await run(`location.pathname.endsWith('/paths.html')&&getComputedStyle(document.querySelector('main')).opacity==='1'&&!sessionStorage.getItem('psychstats.card-transition.v1')`),'Browser Back restores a visible source page without replay');
  results.push({case:'pages',frames});
  for(const destination of ['practice.html','sources.html','index.html','paths.html','datasets.html','symbols.html','sources.html']){
   await click('.site-head nav a[href="'+destination+'"]');
   const samples=await run('window.__motionFrames');
   assert.ok(samples.some(f=>f.pageSnapshot&&f.incoming>0.02&&f.incoming<0.98&&f.scale<0.999),'Every header entry uses layered depth emergence: '+destination);
   const pillPositions=samples.filter(f=>f.pill!==null).map(f=>f.pill);
   assert.ok(pillPositions.length>=4&&Math.max(...pillPositions)-Math.min(...pillPositions)>20,'Navigation shadow moves to '+destination);
   assert.ok(samples.every(f=>f.coverage>=0.999&&Math.abs(f.topicX)<0.01&&Math.abs(f.topicY)<0.01),'No blank frame or X/Y drift: '+destination);
   assert.ok(await run(`location.pathname.endsWith(${JSON.stringify('/'+destination)})&&!document.querySelector('.navigation-cover-next')&&!document.documentElement.classList.contains('navigation-cover-active')&&getComputedStyle(document.querySelector('main')).visibility==='visible'`),'Navigation layers clean up: '+destination);
   results.push({case:'header-'+destination,frames:samples});
  }
 }
 if(mode==='all'||mode==='terms'){
  await open('terms/variable.html');await run('document.querySelector(".sequence-next").click()');await wait(140);
  if(width===1280){const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/navigation-motion-term-mid.png',Buffer.from(shot.data,'base64'));}
  await wait(750);let next=await run('window.__motionFrames');
  assert.ok(next.some(f=>f.pageSnapshot&&f.topicX>1&&f.topicScale<0.999&&f.incoming>0.02&&f.incoming<0.98),'Next term slides gently from the right and emerges in depth');
  await click('.sequence-previous');let previous=await run('window.__motionFrames');
  assert.ok(previous.some(f=>f.pageSnapshot&&f.topicX< -1&&f.topicScale<0.999&&f.incoming>0.02&&f.incoming<0.98),'Previous term slides gently from the left and emerges in depth');
  for(const frames of [next,previous]){
   assert.ok(frames.some(f=>f.duration===420),'Term transition lasts 420ms instead of the fast full-screen slide');
   assert.ok(frames.every(f=>Math.abs(f.topicX)<=32.01&&Math.abs(f.topicY)<0.01&&Math.abs(f.x)<0.01&&Math.abs(f.y)<0.01),'Only the incoming snapshot slides a short distance, without vertical drift');
   assert.ok(frames.every(f=>f.coverage>=0.999&&Math.abs(f.oldX)<0.01),'Opaque old content remains underneath, without blank frames');
   assert.ok(frames.every(f=>Math.abs(f.headerX)<0.01),'Header stays stationary');
  }
  assert.ok(await run(`document.documentElement.scrollWidth<=innerWidth&&getComputedStyle(document.querySelector('main')).transform==='none'&&getComputedStyle(document.querySelector('main')).visibility==='visible'&&!document.documentElement.classList.contains('navigation-cover-active')&&!document.querySelector('.term-transition-scene')&&!sessionStorage.getItem('psychstats.card-transition.v1')`),'Slide cleans up, restores live content and does not cause horizontal overflow');
  results.push({case:'terms',next,previous});
  await open('terms/variable.html');await run('document.querySelector(".sequence-next").click()');await wait(70);
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});await wait(250);
  assert.ok(await run(`getComputedStyle(document.querySelector('main')).visibility==='visible'&&!document.querySelector('.term-transition-scene')&&!document.documentElement.classList.contains('navigation-cover-active')`),'Motion preference changes cancel the transition without leaving content hidden');
  await send('Emulation.setEmulatedMedia',{features:[]});
 }
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 await open('index.html');await run('window.__sampleMotion()');await click('[data-topic-link="regression"]');assert.ok((await run('window.__motionFrames')).every(f=>f.topic===1),'Reduced-motion topics switch without animation');
 await click('.site-head nav a[href="paths.html"]');assert.ok((await run('window.__motionFrames')).every(f=>f.opacity===1),'Reduced-motion pages switch without animation');
 await open('terms/variable.html');await click('.sequence-next');assert.ok(await run(`!document.querySelector('.term-transition-scene')&&!sessionStorage.getItem('psychstats.card-transition.v1')&&getComputedStyle(document.querySelector('main')).visibility==='visible'`),'Reduced-motion term navigation stays immediate and visible');
 assert.equal(errors.length,0,JSON.stringify(errors));await writeFile(`logs/navigation-motion-${width}.json`,JSON.stringify({passed:true,width,results},null,2));console.log(JSON.stringify({passed:true,width,cases:results.map(r=>r.case)}));
}finally{await send('Emulation.setEmulatedMedia',{features:[]});ws.close()}
