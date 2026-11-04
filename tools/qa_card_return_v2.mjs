import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]),root=process.argv[3],width=Number(process.argv[4]||1280),mode=process.argv[5]||'all';
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const pending=new Map(),errors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function landed(path){for(let i=0;i<60;i++){await wait(30);try{if(await evaluate(`location.pathname.endsWith(${JSON.stringify(path)})&&document.readyState==='complete'`)){await wait(800);return}}catch(_){}}throw Error('Navigation timeout '+path)}
async function open(page){await send('Page.navigate',{url:new URL(page,pathToFileURL(root+'/')).href});await landed(page.split('?')[0]);}
async function click(selector){const point=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing entry '+${JSON.stringify(selector)});e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+Math.min(18,r.height/2)}})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1});await send('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1});}
const results=[];
try{
 await send('Page.enable');await send('Runtime.enable');
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:`window.__returnFrames=[];(()=>{const start=performance.now();function sample(){const p=document.querySelector('.term-transition-panel'),b=p?.getBoundingClientRect();window.__returnFrames.push({time:Math.round(performance.now()-start),width:b?.width,height:b?.height,x:b?.x,y:b?.y});if(performance.now()-start<1000)requestAnimationFrame(sample)}requestAnimationFrame(sample)})()`});
 await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 if(mode!=='practice'){
  await open('index.html?topic=regression');
  await click('.term-card[data-id="simple-linear-regression"] h2');await landed('/terms/simple-linear-regression.html');
  await click('.breadcrumb a:nth-of-type(2)');await landed('/index.html');
  const frames=await evaluate('window.__returnFrames.filter(f=>f.width)');
  assert.ok(frames.length>=3,'Topic return must animate rather than cut');
  assert.ok(frames[0].width>frames.at(-1).width+20||frames[0].height>frames.at(-1).height+20,'Page shrinks into the card');
  assert.ok(await evaluate(`(()=>{const c=document.querySelector('.term-card[data-id="simple-linear-regression"]'),r=c.getBoundingClientRect(),h=document.querySelector('.site-head').getBoundingClientRect();return !c.hidden&&r.top>=h.bottom&&r.bottom<=innerHeight&&document.querySelector('#topic-intro').dataset.topic==='regression'&&!document.querySelector('.term-content')&&!document.querySelector('.term-transition-scene')&&[...document.querySelector('#search-scope').options].some(o=>o.value==='topic')})()`),'Correct theme, visible card and homepage search scope restored');
  const card=await evaluate(`(()=>{const r=document.querySelector('.term-card[data-id="simple-linear-regression"]').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()`);
  assert.ok(Math.abs(frames.at(-1).x-card.x)<6&&Math.abs(frames.at(-1).y-card.y)<6,'Shrink ends on the actual card');
  results.push({case:'topic-return',frames:frames.length,first:frames[0],last:frames.at(-1),card});
 }
 if(mode!=='reverse'){
  await open('practice.html');
  await evaluate(`document.querySelector('[data-choice="0"]').click();document.querySelector('[data-next-question]').click();document.querySelector('[data-choice="1"]').click()`);
  const original=await evaluate(`({question:document.querySelector('.practice-question h2').textContent,selected:document.querySelector('[data-choice][aria-pressed="true"]').dataset.choice,score:document.querySelector('.practice-score').textContent,feedback:document.querySelector('.explain').textContent,term:window.PsychPractice.captureState?.().question_id})`);
  const target=await evaluate(`new URL(document.querySelector('.practice-open-link').href).pathname`);
  await click('.practice-open-link');await landed(target);
  assert.ok(await evaluate(`!!document.querySelector('[data-return-practice]')`),'Direct practice entry exposes a return pointer');
  await click('[data-return-practice]');await landed('/practice.html');
  const restored=await evaluate(`({question:document.querySelector('.practice-question h2').textContent,selected:document.querySelector('[data-choice][aria-pressed="true"]')?.dataset.choice,score:document.querySelector('.practice-score').textContent,feedback:document.querySelector('.explain').textContent,term:window.PsychPractice.captureState?.().question_id})`);
  assert.deepEqual(restored,original,'Return keeps the same question, selected option, explanation and first-attempt score');
  assert.ok(await evaluate(`!sessionStorage.getItem('psychstats.practice-return.v1')&&!sessionStorage.getItem('psychstats.practice-resume.v1')`),'Return consumes the temporary context');
  await click('.practice-open-link');await landed(target);
  await click('.sequence-next');await wait(800);
  assert.ok(await evaluate(`!document.querySelector('[data-return-practice]')&&!sessionStorage.getItem('psychstats.practice-return.v1')`),'Switching terms removes the pointer and does not pass it to the next term');
  await open('practice.html');await evaluate(`document.querySelector('[data-choice]').click()`);await click('.practice-open-link');await landed(await evaluate('location.pathname'));
  await click('.site-head nav a[href="../paths.html"]');await landed('/paths.html');
  assert.ok(await evaluate(`!sessionStorage.getItem('psychstats.practice-return.v1')`),'Other navigation also clears practice context');
  results.push({case:'practice-return',original,restored});
 }
 assert.equal(errors.length,0,'No runtime errors: '+errors.join(','));
 await writeFile(`logs/card-return-v2-${width}.json`,JSON.stringify({passed:true,width,results},null,2));
 console.log(JSON.stringify({passed:true,width,results}));
}finally{ws.close()}
