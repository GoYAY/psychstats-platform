import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const [port,root]=process.argv.slice(2);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);
let sequence=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),t=pending.get(m.id);if(t){pending.delete(m.id);m.error?t.reject(m.error):t.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++sequence,{resolve,reject});ws.send(JSON.stringify({id:sequence,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function move(selector){
 const p=await run(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',...p});await wait(200);
 const state=await run(`(()=>{const d=document.querySelector('.cursor-dot'),r=d.getBoundingClientRect(),s=getComputedStyle(d),ring=getComputedStyle(d,'::before');return {hidden:d.hidden,x:r.x+r.width/2,y:r.y+r.height/2,width:r.width,bg:s.backgroundColor,scale:s.scale,ringScale:new DOMMatrixReadOnly(ring.transform).m11,ringBorder:ring.borderTopColor,ringBorderWidth:ring.borderTopWidth}})()`);
 if(!state.hidden){assert.ok(Math.abs(state.x-p.x)<1&&Math.abs(state.y-p.y)<1,'Cursor center stays under the pointer while scaling');assert.equal(state.bg,'rgba(0, 0, 0, 0)')}
 return state;
}
try{
 await send('Page.enable');await send('Runtime.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:pathToFileURL(root+'/index.html').href});await wait(700);
 const link=await move('.site-head nav a[href="paths.html"]');
 assert.ok(Math.abs(link.width*link.ringScale-21)<0.01,'Interactive ring has a 21px diameter');
 assert.equal(link.ringBorderWidth,'1px');
 const plain=await move('.hero h1');assert.equal(plain.width,15);assert.equal(plain.ringScale,1);assert.equal(plain.ringBorderWidth,'2px');
 const text=await move('#q');assert.ok(text.hidden,'Input keeps native cursor');
 await run(`const b=document.createElement('button');b.disabled=true;b.textContent='disabled';b.id='qa-disabled';b.style.cssText='position:fixed;top:200px;left:200px;z-index:99';document.body.appendChild(b)`);
 const disabled=await move('#qa-disabled');assert.ok(Number(disabled.scale)===1||disabled.ringScale===1);
 await send('Page.navigate',{url:pathToFileURL(root+'/terms/sem.html').href});await wait(700);
 const formula=await move('.formula-symbol');assert.ok(Math.abs(formula.width*formula.ringScale-21)<0.01);
 await send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
 await send('Page.navigate',{url:pathToFileURL(root+'/index.html').href});await wait(700);
 assert.ok(await run(`!document.querySelector('.cursor-dot')&&!document.documentElement.classList.contains('dot-cursor')`));
 console.log(JSON.stringify({passed:true,checks:['transparent','center-stable','interactive-scale','reset','input-native','disabled','formula','mobile-native']}));
}finally{ws.close()}
