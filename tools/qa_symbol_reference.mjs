import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const port=process.argv[2]||'9273', root=resolve('site/dist');
const tabs=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);
let id=0; const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const checks=[];
async function navigate(file){await send('Page.navigate',{url:pathToFileURL(resolve(root,file)).href});await wait(200)}
try{
 await send('Page.enable');await send('Runtime.enable');
 for(const width of [1440,1280,1121,800,390,375]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
  await navigate('index.html');
  const cards=await run(`(()=>{const bad=[];document.querySelectorAll('[data-term]').forEach(card=>{card.hidden=false;const h=card.querySelector('h2'),s=card.querySelector('.term-symbols');if(!s)return;const hr=h.getBoundingClientRect(),sr=s.getBoundingClientRect();const range=document.createRange();range.selectNodeContents(h);const letters=range.getBoundingClientRect();if(letters.right>sr.left-1 && letters.top<sr.bottom && letters.bottom>sr.top)bad.push(card.dataset.id+' overlap');if(getComputedStyle(h).fontSize!==getComputedStyle(s.querySelector('a')).fontSize)bad.push(card.dataset.id+' font');});return {bad,badges:document.querySelectorAll('.term-symbol-badge').length,overflow:document.documentElement.scrollWidth>innerWidth+1}})()`);
  assert.deepEqual(cards.bad,[],`card geometry at ${width}`);assert.ok(!cards.overflow,`home overflow at ${width}`);assert.ok(cards.badges>25);
  assert.equal(await run(`getComputedStyle(document.querySelector('[data-id="degrees-of-freedom"] .stat-letter')).fontStyle`),'italic');
  assert.equal(await run(`getComputedStyle(document.querySelector('[data-id="significance-level"] .stat-roman')).fontStyle`),'normal');
  checks.push({width,page:'cards',...cards});
  await navigate('symbols.html');
  assert.ok(!await run('document.documentElement.scrollWidth>innerWidth+1'),`reference overflow ${width}`);
  const searches=[['df',['degrees-of-freedom','parameter-output','df-output']],['α',['significance-alpha','cronbach-alpha']],['ALPHA',['significance-alpha','cronbach-alpha']],['N',['total-sample-n']],['n',['subsample-n']],['Pr(>|t|)',['pr-t-output']],['zzzz不存在',[]]];
  for(const [query,expected] of searches){
   const ids=await run(`(()=>{const q=document.getElementById('symbol-query');q.value=${JSON.stringify(query)};q.dispatchEvent(new Event('input'));return [...document.querySelectorAll('[data-symbol-row]:not([hidden])')].map(r=>r.id)})()`);
   for(const key of expected)assert.ok(ids.includes(key),`${query} missing ${key}`);
   if(['N','n','zzzz不存在'].includes(query))assert.deepEqual(ids,expected);
  }
  await run(`document.getElementById('symbol-kind').value='output';document.getElementById('symbol-kind').dispatchEvent(new Event('change'));document.getElementById('symbol-clear').click()`);
  assert.equal(await run(`document.querySelectorAll('[data-symbol-row][hidden]').length`),0);
  await run(`document.getElementById('symbol-query').value='zzzz';document.getElementById('symbol-query').dispatchEvent(new Event('input'));location.hash='degrees-of-freedom'`);await wait(100);
  assert.ok(await run(`!document.getElementById('degrees-of-freedom').hidden && document.activeElement.id==='degrees-of-freedom'`));
  checks.push({width,page:'lookup',rows:await run(`document.querySelectorAll('[data-symbol-row]').length`)});
  if([1280,390].includes(width)){
   await run(`window.scrollTo({top:0,behavior:'instant'})`);
   const shot=await send('Page.captureScreenshot',{format:'png'});
   await writeFile(resolve('logs',`symbols-${width}.png`),Buffer.from(shot.data,'base64'));
  }
 }
 await navigate('index.html');
 await run(`document.querySelector('[data-id="population-and-sample"] .term-symbol-badge').focus()`);
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await wait(250);
 assert.ok(await run(`location.pathname.endsWith('/symbols.html') && location.hash==='#total-sample-n' && document.activeElement.id==='total-sample-n'`),'badge keyboard navigation must open the reference, not expand term');
 await writeFile(resolve('logs/symbol-reference-browser.json'),JSON.stringify(checks,null,2));
 console.log(JSON.stringify({checks:checks.length,badges:checks[0].badges,rows:checks[1].rows,passed:true}));
}finally{ws.close()}
