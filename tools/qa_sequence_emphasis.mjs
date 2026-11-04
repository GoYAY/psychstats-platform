import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [port='9263', root, widthArg='1280'] = process.argv.slice(2);
const width=Number(widthArg), height=900;
const targets=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let id=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const check=(condition,message)=>{if(!condition)throw Error(message);};
const luminance=color=>{const channels=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>color.startsWith('color(srgb ')?v:v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);return channels[0]*0.2126+channels[1]*0.7152+channels[2]*0.0722;};
const state=()=>evaluate(`(()=>{const a=document.querySelector('.sequence-previous'),s=getComputedStyle(a),r=a.getBoundingClientRect(),icon=a.querySelector('.sequence-arrow');return{background:s.backgroundColor,border:s.borderTopWidth,borderStyle:s.borderTopStyle,borderColor:s.borderTopColor,color:s.color,outline:s.outlineStyle,focusVisible:a.matches(':focus-visible'),width:r.width,height:r.height,x:r.x,y:r.y,arrowWidth:icon.getBoundingClientRect().width,arrowSvg:!!icon.querySelector('svg')}})()`);
try {
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});
 const url=pathToFileURL(root+'/terms/sem.html').href;
 await send('Page.navigate',{url});
 for(let i=0;i<50;i++){await wait(60);if(await evaluate(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;}
 await evaluate('document.fonts.ready.then(()=>true)');
 await evaluate(`document.querySelector('.sequence-previous').scrollIntoView({block:'center',behavior:'instant'})`);
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1});await wait(200);
 const normal=await state();
 check(normal.border==='1px'&&normal.borderStyle==='solid','navigation card must have a permanent 1px solid border');
 check(normal.arrowSvg&&normal.arrowWidth>=27,'direction arrow must be a long nonshrinking line icon');
 const point={x:normal.x+normal.width/2,y:normal.y+normal.height/2};
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',...point});await wait(250);
 const hovered=await state();
 check(luminance(normal.background)-luminance(hovered.background)>=0.08,'hover fill must visibly darken');
 check(normal.borderColor!==hovered.borderColor,'hover border should strengthen');
 check(normal.width===hovered.width&&normal.height===hovered.height,'hover must not change card size');
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1});
 await evaluate(`document.querySelector('.sequence-previous').focus()`);
 // Trigger native keyboard modality, then focus the previous navigation link.
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
 await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
 await evaluate(`document.querySelector('.sequence-previous').focus()`);await wait(250);
 const focused=await state();
 check(focused.focusVisible&&focused.outline!=='none','keyboard focus must retain a visible outline');
 check(luminance(normal.background)-luminance(focused.background)>=0.08,'keyboard focus should get the darkened fill');
 const contrast=(luminance(focused.background)+0.05)/(luminance(focused.color)+0.05);
 check(contrast>=4.5,'darkened card label must retain readable contrast');
 await evaluate(`document.activeElement.blur()`);await wait(200);
 if(width<600){
  await send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
  const touch=await state();
  await evaluate(`document.querySelector('.sequence-previous').addEventListener('click',e=>e.preventDefault(),{once:true})`);
  await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:touch.x+touch.width/2,y:touch.y+touch.height/2}]});
  await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await wait(100);
  const pressed=await state();
  check(luminance(normal.background)-luminance(pressed.background)>=0.08,'touch press must visibly darken');
  await send('Emulation.setTouchEmulationEnabled',{enabled:false});await wait(200);
 }
 // Stress long adjacent labels without changing production content.
 const labels=await evaluate(`[...document.querySelectorAll('.sequence-link')].map(a=>a.lastElementChild.textContent)`);
 await evaluate(`for(const a of document.querySelectorAll('.sequence-link'))a.lastElementChild.textContent='Wilcoxon 符号秩检验与线性依赖解释';`);
 check(await evaluate(`document.documentElement.scrollWidth<=${width}&&[...document.querySelectorAll('.sequence-link')].every(a=>a.scrollWidth<=a.clientWidth+1&&a.getBoundingClientRect().height>=44)`),'long labels must wrap without horizontal overflow');
 await evaluate(`[...document.querySelectorAll('.sequence-link')].forEach((a,i)=>a.lastElementChild.textContent=${JSON.stringify(labels)}[i])`);
 const shot=await send('Page.captureScreenshot',{format:'png'});
 await writeFile(`logs/sequence-emphasis-${width}.png`,Buffer.from(shot.data,'base64'));
 await writeFile(`logs/sequence-emphasis-${width}.json`,JSON.stringify({passed:true,width,normal,hovered,focused,contrast},null,2));
 console.log(JSON.stringify({passed:true,width,arrowWidth:normal.arrowWidth,contrast}));
} finally { ws.close(); }
