import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9259),root=process.argv[3],width=Number(process.argv[4]||1280);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value};
const check=(v,m)=>{if(!v)throw Error(m)};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function key(k,shift=false){const codes={Enter:13,' ':32,Tab:9,Escape:27};await send('Input.dispatchKeyEvent',{type:'keyDown',key:k,code:k===' '?'Space':k,windowsVirtualKeyCode:codes[k],modifiers:shift?8:0,...(['Enter',' '].includes(k)?{text:k==='Enter'?'\r':' '}:{})});await send('Input.dispatchKeyEvent',{type:'keyUp',key:k,windowsVirtualKeyCode:codes[k],modifiers:shift?8:0})}
async function hover(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center',behavior:'instant'})`);const p=await evaluate(`(()=>{const b=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2}})()`);await send('Input.dispatchMouseEvent',{type:'mouseMoved',...p})}
try{
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');
 await send('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:width<600});
 await send('Page.navigate',{url:pathToFileURL(root+'/terms/sem.html').href});await sleep(450);
 await hover('.formula-key[data-symbol="fs-0"]');
 const clickPoint=await evaluate(`(()=>{const b=document.querySelector('.formula-key[data-symbol="fs-0"]').getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2}})()`);
 for(let i=0;i<2;i++){await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...clickPoint});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...clickPoint})}
 await sleep(200);
 check(await evaluate(`(()=>{const k=document.querySelector('.formula-key[data-symbol="fs-0"]'),row=k.closest('li');return k.getAttribute('aria-pressed')==='false'&&getComputedStyle(row).boxShadow==='none'&&getComputedStyle(k).boxShadow==='none'})()`),'unpin must remove left stripe and shadow even while hovered/focused');
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:900});await sleep(200);
 check(await evaluate(`!document.querySelector('.formula-key[data-symbol="fs-0"]').classList.contains('is-active')`),'pointer focus must not keep hover fill after unpin and leave');
 await evaluate(`document.activeElement.blur()`);
 await hover('.formula-key[data-symbol="fs-0"]');
 await key('Enter');
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="fs-0"]').getAttribute('aria-pressed')==='true'`),'hover + Enter must pin without click');
 await hover('.formula-key[data-symbol="fs-1"]');
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="fs-0"]').classList.contains('is-active')&&document.querySelector('.formula-key[data-symbol="fs-1"]').classList.contains('is-active')`),'hover must not erase existing pin');
 await key('Enter');
 check(await evaluate(`document.querySelectorAll('.formula-key[aria-pressed="true"]').length===2`),'multiple symbols must stay pinned');
 await key('Tab');
 check(await evaluate(`document.activeElement.dataset.symbol==='fs-2'`),'hover + Tab must move to next explanation');
 await key(' ',false);
 check(await evaluate(`document.querySelectorAll('.formula-key[aria-pressed="true"]').length===3`),'space must add a third pin');
 await key('Tab',true);
 // Meaning links are real, keyboard-accessible siblings, not nested buttons.
 while(await evaluate(`document.activeElement.tagName==='A'&&!!document.activeElement.closest('.formula-row')`))await key('Tab',true);
 check(await evaluate(`document.activeElement.dataset.symbol==='fs-1'`),'Shift+Tab follows visual order');
 await key('Enter');
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="fs-1"]').getAttribute('aria-pressed')==='false'&&document.querySelectorAll('.formula-key[aria-pressed="true"]').length===2`),'toggle must remove only its own pin');
 await key('Escape');
 check(await evaluate(`document.querySelectorAll('.formula-key[aria-pressed="true"]').length===0`),'Escape clears pins');
 await evaluate(`document.activeElement.blur()`);
 await hover('.katex-html .fs-0');await key('Enter');
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="fs-0"]').getAttribute('aria-pressed')==='true'`),'formula glyph hover keyboard must work without click');
 await evaluate(`document.querySelectorAll('.formula-key')[document.querySelectorAll('.formula-key').length-1].focus()`);
 await key('Tab');
 check(await evaluate(`!document.activeElement.classList.contains('formula-key')`),'Tab at last key must exit, not trap');
 await evaluate(`document.querySelector('#q').focus()`);await key(' ');
 check(await evaluate(`document.querySelector('#q').value===' '`),'formula shortcuts must not hijack text input');
 await evaluate(`document.querySelector('#q').blur()`);
 await hover('.formula-key[data-symbol="fs-0"]');await key('Escape');
 await evaluate(`document.querySelector('.formula-key[data-symbol="fs-0"]').focus()`);
 await hover('.formula-key[data-symbol="fs-1"]');await key('Enter');
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="fs-0"]').getAttribute('aria-pressed')==='true'&&document.querySelector('.formula-key[data-symbol="fs-1"]').getAttribute('aria-pressed')==='false'`),'focused button must own Enter even when another symbol is hovered');
 await key(' ');
 check(await evaluate(`document.querySelectorAll('.formula-key[aria-pressed="true"]').length===0`),'focused button must own Space even when another symbol is hovered');
 await key('Escape');await evaluate(`document.activeElement.blur()`);
 const style=await evaluate(`(()=>{const q=document.querySelector('.real-question'),r=document.querySelector('.report-example'),c=document.querySelector('.quiz-card');return{background:getComputedStyle(q).backgroundColor,report:!!r,reportText:r?.textContent,width:document.documentElement.scrollWidth,quote:!!q.querySelector('.question-quote'),bold:!!document.querySelector('.output-interpretation .key-point'),quiz:getComputedStyle(c).backgroundColor}})()`);
 check(style.width<=width&&style.quote&&style.background!=='rgb(255, 255, 255)'&&style.background!==style.quiz,'distinct tinted question card');
 check(style.report&&style.reportText.includes('0.997')&&style.reportText.includes('−0.009')&&style.bold,'SEM report and emphasized output');
 for(const selector of ['.real-question','.formula','.report-example','.quiz-card']){await evaluate(`window.scrollTo({top:window.scrollY+document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().top-document.querySelector('.site-head').offsetHeight-20,behavior:'instant'})`);await sleep(90);const s=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/reading-v2-${width}-${selector.slice(1)}.png`,Buffer.from(s.data,'base64'))}
 await writeFile(`logs/reading-v2-qa-${width}.json`,JSON.stringify({passed:true,width,style},null,2));console.log(JSON.stringify({passed:true,width,style}));
}finally{ws.close()}
