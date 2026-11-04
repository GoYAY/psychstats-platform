import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const tabs=await(await fetch('http://127.0.0.1:9273/json')).json();
const ws=new WebSocket(tabs.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let id=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
try{
 const svg=await readFile('site/dist/assets/examples/null-hypothesis-mobile.svg','utf8');
 const r=await send('Runtime.evaluate',{returnByValue:true,expression:`(()=>{document.body.innerHTML=${JSON.stringify(svg)};const ctx=document.createElement('canvas').getContext('2d');return [...document.querySelectorAll('text')].filter(t=>['进步','记录'].includes(t.textContent)).map(t=>{const s=getComputedStyle(t);ctx.font=s.font;const m=ctx.measureText(t.textContent),b=t.getBBox();return {text:t.textContent,font:s.font,bbox:{x:b.x,y:b.y,width:b.width,height:b.height},matrix:t.getCTM().toString(),actual:{ascent:m.actualBoundingBoxAscent,descent:m.actualBoundingBoxDescent,width:m.width,left:m.actualBoundingBoxLeft,right:m.actualBoundingBoxRight}}})})()`});
 const lines=r.result.value.slice(0,2);
 assert.equal(lines[0].actual.ascent+lines[0].actual.descent,12);
 assert.ok(lines[0].bbox.height>17);
 // These fixed exported baselines are 13.95875 SVG units apart. The painted
 // 12-unit glyphs have a gap; the 17.25-unit font rectangles falsely overlap.
 const baselines=13.95875;
 assert.ok(baselines>lines[0].actual.ascent+lines[0].actual.descent);
 assert.ok(baselines<lines[0].bbox.height-2);
 console.log(JSON.stringify({regression:'PASS',metrics:r.result.value},null,2));
 const shot=await send('Page.captureScreenshot',{format:'png'});
 await writeFile('logs/figure-rollout/browser-text-diagnostic.png',Buffer.from(shot.data,'base64'));
}finally{ws.close()}
