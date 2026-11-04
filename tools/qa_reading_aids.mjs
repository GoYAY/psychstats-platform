import {readdir,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9258),root=process.argv[3],width=Number(process.argv[4]||1280);
const targets=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data),h=pending.get(m.id);if(h){pending.delete(m.id);m.error?h.reject(m.error):h.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function check(ok,message){if(!ok)throw Error(message);}
async function open(slug){
 const url=pathToFileURL(root+'/terms/'+slug+'.html').href;
 await send('Page.navigate',{url});
 for(let i=0;i<30;i++){await wait(60);if(await evaluate(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;}
 await evaluate('document.fonts.ready.then(()=>true)');
}
async function shot(slug,selector){
 await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});window.scrollTo({top:window.scrollY+el.getBoundingClientRect().top-document.querySelector('.site-head').offsetHeight-22,behavior:'instant'})})()`);
 await wait(120);const result=await send('Page.captureScreenshot',{format:'png'});
 await writeFile(`logs/reading-aids-${width}-${slug}-${selector.replace(/[^a-z-]/g,'')}.png`,Buffer.from(result.data,'base64'));
}
const tested=[];
try{
 await send('Page.enable');await send('Runtime.enable');
 await send('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:width<600});
 const slugs=(await readdir(root+'/terms')).filter(n=>n.endsWith('.html')).map(n=>n.slice(0,-5));
 for(const slug of slugs){
  await open(slug);
  const state=await evaluate(`(()=>{
   const q=document.querySelector('.real-question'),card=document.querySelector('.quiz-card'),p=document.querySelector('#agent-prompt'),f=document.querySelector('.formula'),h=document.querySelector('.explanation-part h3'),b=document.querySelector('.key-point'),r=document.querySelector('.explanation-part p');
   const keys=[...document.querySelectorAll('.formula-key')],symbols=[...document.querySelectorAll('.katex-html .formula-symbol')];
   const allMappings=keys.every(k=>symbols.some(s=>s.classList.contains(k.dataset.symbol)));
   let interactions=true;
   for(const s of symbols){s.dispatchEvent(new PointerEvent('pointerenter'));const id=[...s.classList].find(c=>/^fs-\\d+$/.test(c));if(!document.querySelector('.formula-key[data-symbol="'+id+'"]')?.classList.contains('is-active'))interactions=false;s.dispatchEvent(new PointerEvent('pointerleave'));}
   if(keys[0]){keys[0].focus();interactions=interactions&&symbols.some(s=>s.classList.contains(keys[0].dataset.symbol)&&s.classList.contains('is-focused'));keys[0].click();interactions=interactions&&keys[0].getAttribute('aria-pressed')==='true';keys[0].dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));interactions=interactions&&keys[0].getAttribute('aria-pressed')==='false';keys[0].blur();}
   const report=document.querySelector('.report-example'),output=document.querySelector('.output-interpretation');
   return {slug:${JSON.stringify(slug)},width:document.documentElement.scrollWidth,questionBorder:getComputedStyle(q).borderTopWidth,questionShadow:getComputedStyle(q).boxShadow,questionBackground:getComputedStyle(q).backgroundColor,questionQuote:!!q.querySelector('.question-quote'),report:!!report,reportEmphasis:!!report?.querySelector('.key-point'),outputEmphasis:!!output?.querySelector('.key-point'),reportBackground:report&&getComputedStyle(report).backgroundColor,quizBackground:card&&getComputedStyle(card).backgroundColor,quizShadow:card&&getComputedStyle(card).boxShadow,promptLines:p?Math.round(p.getBoundingClientRect().height/parseFloat(getComputedStyle(p).lineHeight)):0,promptFont:p&&getComputedStyle(p).fontSize,formulaKeys:keys.length,formulaSymbols:symbols.length,allMappings,interactions,bold:!!b,headingSize:h&&parseFloat(getComputedStyle(h).fontSize),boldSize:b&&parseFloat(getComputedStyle(b).fontSize),headingWeight:h&&getComputedStyle(h).fontWeight,boldWeight:b&&getComputedStyle(b).fontWeight,remainingWeight:r&&getComputedStyle(r).fontWeight,errors:[...document.querySelectorAll('.katex-error')].length};
  })()`);
  check(state.width<=width,'page overflow '+slug);
  check(state.questionBorder==='0px'&&state.questionShadow!=='none'&&state.questionBackground!=='rgb(255, 255, 255)'&&state.questionQuote,'question treatment '+slug);
  check(state.quizShadow!=='none'&&state.quizBackground!==state.questionBackground,'quiz treatment '+slug);
  check(state.bold&&state.headingSize>state.boldSize&&Number(state.headingWeight)>Number(state.boldWeight)&&Number(state.boldWeight)>Number(state.remainingWeight),'text hierarchy '+slug);
  if(width>=1100)check(state.promptLines<=4,'prompt exceeds four lines '+slug+' '+state.promptLines);
  if(state.promptLines)check(state.report&&state.reportEmphasis&&state.outputEmphasis&&state.reportBackground!==state.questionBackground&&state.reportBackground!==state.quizBackground,'report card/output emphasis '+slug);
  check(state.allMappings&&state.interactions&&state.errors===0,'formula mapping/interaction '+slug);
  tested.push(state);
  if(tested.length%30===0)console.log(JSON.stringify({progress:tested.length,width}));
 }
 for(const [slug,selectors]of [['simple-linear-regression',['.real-question','.detailed-explanation','.formula','.agent-brief','.quiz-card']],['standard-error',['.formula']],['cronbach-alpha',['.formula']]]){
  await open(slug);for(const selector of selectors)await shot(slug,selector);
 }
 // Real pointer and keyboard activation on a repeated coefficient target.
 await open('standard-error');
 check(await evaluate(`(()=>{const n=[...document.querySelectorAll('.katex-html .formula-symbol')].find(s=>s.textContent.trim()==='n');n.click();const id=[...n.classList].find(c=>/^fs-\\d+$/.test(c));return document.querySelector('.formula-key[data-symbol="'+id+'"]').getAttribute('aria-pressed')==='true'})()`),'radicand click must not select enclosing square root');
 check(await evaluate(`!document.querySelector('.formula-symbol .formula-symbol')`),'formula symbols must not nest interactive targets');
 check(await evaluate(`document.querySelector('.katex-html').getAttribute('aria-hidden')==='true'&&!document.querySelector('.katex-html [tabindex]')`),'MathML must remain the sole accessible formula representation');
 await evaluate(`document.querySelector('.formula-key').focus();document.querySelector('.formula-key').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`);
 for(const key of ['Enter',' ']){
  await send('Input.dispatchKeyEvent',{type:'keyDown',key,text:key==='Enter'?'\r':' ',code:key==='Enter'?'Enter':'Space',windowsVirtualKeyCode:key==='Enter'?13:32});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key,code:key==='Enter'?'Enter':'Space',windowsVirtualKeyCode:key==='Enter'?13:32});
  check(await evaluate(`document.querySelector('.formula-key').getAttribute('aria-pressed')==='${key==='Enter'?'true':'false'}'`),'native glossary keyboard activation '+key);
 }
 await open('simple-linear-regression');
 await evaluate(`document.querySelector('.formula').scrollIntoView({block:'center',behavior:'instant'})`);
 await evaluate(`(()=>{const k=[...document.querySelectorAll('.formula-key')].find(k=>k.closest('li').textContent.includes('斜率'));document.querySelector('.katex-html .'+k.dataset.symbol).scrollIntoView({block:'center',behavior:'instant'})})()`);
 const point=await evaluate(`(()=>{const k=[...document.querySelectorAll('.formula-key')].find(k=>k.closest('li').textContent.includes('斜率'));const s=document.querySelector('.katex-html .'+k.dataset.symbol);const b=s.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2,id:k.dataset.symbol}})()`);
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:point.x,y:point.y});
 check(point.y>=0&&point.y<950,'pointer target outside viewport');
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="${point.id}"]').classList.contains('is-active')`),'real pointer hover');
 await send('Input.dispatchMouseEvent',{type:'mousePressed',x:point.x,y:point.y,button:'left',clickCount:1});
 await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:point.x,y:point.y,button:'left',clickCount:1});
 check(await evaluate(`document.querySelector('.formula-key[data-symbol="${point.id}"]').getAttribute('aria-pressed')==='true'`),'real pointer click');
 await writeFile(`logs/reading-aids-qa-${width}.json`,JSON.stringify({passed:true,width,tested},null,2));
 console.log(JSON.stringify({passed:true,width,pages:tested.length,formulaPages:tested.filter(s=>s.formulaKeys).length,promptPages:tested.filter(s=>s.promptLines).length,maxPromptLines:Math.max(...tested.map(s=>s.promptLines))}));
}finally{socket.close();}
