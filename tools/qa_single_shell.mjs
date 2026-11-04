import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9242),root=process.argv[3],width=Number(process.argv[4]||1280);
const targets=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const h=pending.get(m.id);pending.delete(m.id);m.error?h.reject(m.error):h.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
const delay=()=>new Promise(r=>setTimeout(r,1400));
async function open(path){const [file,query]=path.split('?');const u=pathToFileURL(root+'/'+file);if(query)u.search=query;await send('Page.navigate',{url:u.href});await delay();}
async function snapshot(){return JSON.parse(await evaluate(`JSON.stringify({url:location.href,origin:performance.timeOrigin,heading:document.querySelector('.hero h1')?.textContent,topic:document.querySelector('#topic-title')?.textContent,selected:document.querySelector('[data-topic-link][aria-current]')?.dataset.topicLink,level:document.querySelector('#level-filter')?.value,count:document.querySelector('#result-count')?.textContent,theme:document.documentElement.dataset.theme,picker:document.querySelectorAll('[data-theme-choice]').length,topics:[...document.querySelectorAll('[data-term]:not([hidden])')].map(c=>c.dataset.topic),width:innerWidth,pageWidth:document.documentElement.scrollWidth})`));}
function check(ok,message){if(!ok)throw Error(message);}
await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<=600});
await open('index.html?theme=violet');
await evaluate(`localStorage.setItem('psych-theme','amber');`);
await send('Page.reload');await delay();
const initial=await snapshot();
await evaluate(`window.originalHero=document.querySelector('.hero');document.querySelector('#level-filter').value='basic';document.querySelector('#level-filter').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('[data-topic-link="foundations"]').click();`);
const repeated=await snapshot();
check(initial.origin===repeated.origin&&initial.url===repeated.url&&repeated.level==='basic','current topic click changed page or filters');
await evaluate(`document.querySelector('[data-topic-link="regression"]').click()`);
const regression=await snapshot();
check(regression.origin===initial.origin&&regression.heading==='心理统计学术语'&&regression.selected==='regression'&&regression.topics.length===18&&regression.topics.every(x=>x==='regression'),'topic switch replaced shell or leaked cards');
check(await evaluate(`window.originalHero===document.querySelector('.hero')`),'hero DOM replaced');
const image=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(`logs/single-shell-${width}.png`,Buffer.from(image.data,'base64'));
await evaluate('history.back()');await new Promise(r=>setTimeout(r,250));
const back=await snapshot();check(back.selected==='foundations'&&back.level==='basic','back did not restore topic/filter');
await evaluate('history.forward()');await new Promise(r=>setTimeout(r,250));
check((await snapshot()).selected==='regression','forward failed');
await send('Page.reload');await delay();
check((await snapshot()).selected==='regression','refresh lost selected topic');
await open('topics/foundations.html');
const alias=await snapshot();check(alias.url.includes('index.html?topic=foundations')&&alias.heading==='心理统计学术语','old URL showed duplicate shell');
check(initial.theme==='cobalt'&&initial.picker===0&&regression.pageWidth<=width&&initial.pageWidth<=width,'palette or layout incorrect');
console.log(JSON.stringify({width,initial,repeated,regression,back,alias,passed:true}));
socket.close();
