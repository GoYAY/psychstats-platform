import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9241),root=process.argv[3],width=Number(process.argv[4]||1280);
const targets=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
const pending=new Map();let id=0;
socket.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const h=pending.get(m.id);pending.delete(m.id);m.error?h.reject(m.error):h.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value;}
async function open(path){await send('Page.navigate',{url:pathToFileURL(root+'/'+path).href});await new Promise(r=>setTimeout(r,1200));}
async function shot(name){const s=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(`logs/curriculum-${width}-${name}.png`,Buffer.from(s.data,'base64'));}
await send('Page.enable');await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<=600});
await open('index.html');
const home=JSON.parse(await evaluate(`JSON.stringify({topics:[...document.querySelectorAll('[data-topic-link]')].map(a=>a.dataset.topicLink),cards:[...document.querySelectorAll('[data-term]')].map(a=>a.dataset.id),navLeft:document.querySelector('.topic-nav').getBoundingClientRect().left,width:innerWidth,pageWidth:document.documentElement.scrollWidth})`));
await shot('home');
await open('topics/regression.html');
const topic=JSON.parse(await evaluate(`JSON.stringify((()=>{const select=document.querySelector('#level-filter');const levels=[...select.options].map(o=>o.textContent);select.value='basic';select.dispatchEvent(new Event('change',{bubbles:true}));const basics=[...document.querySelectorAll('[data-term]:not([hidden])')].map(c=>c.dataset.level);const r=document.querySelector('#r-filter');r.value='true';r.dispatchEvent(new Event('change',{bubbles:true}));const rVisible=[...document.querySelectorAll('[data-term]:not([hidden])')].map(c=>c.dataset.hasR);const trigger=[...document.querySelectorAll('.filter-trigger')].at(-1);trigger.click();const menu=trigger.nextElementSibling.getBoundingClientRect();return {levels,basics,rVisible,menuRight:menu.right,menuBelow:menu.top>=trigger.getBoundingClientRect().bottom,width:innerWidth,pageWidth:document.documentElement.scrollWidth,count:document.querySelector('#result-count').textContent};})())`));
await shot('topic');
await open('paths.html');
await evaluate(`document.querySelector('a[href="#direction-measurement"]').click()`);
await new Promise(r=>setTimeout(r,250));
const map=JSON.parse(await evaluate(`JSON.stringify({branches:document.querySelectorAll('.direction-map').length,open:document.querySelector('#direction-measurement').open,steps:document.querySelector('#direction-measurement .direction-stages').children.length,width:innerWidth,pageWidth:document.documentElement.scrollWidth})`));
await shot('map');
await evaluate(`document.querySelector('#direction-measurement a[href="#direction-mechanisms"]').click()`);
await new Promise(r=>setTimeout(r,250));
const cross=await evaluate(`document.querySelector('#direction-mechanisms').open`);
await open('paths.html');await shot('overview');
const result={home,topic,map,cross};
console.log(JSON.stringify(result));
if(home.navLeft<14||home.topics.length!==10||topic.basics.some(x=>x!=='basic')||topic.rVisible.some(x=>x!=='true')||!topic.menuBelow||topic.menuRight>width||map.branches!==6||!map.open||!cross||home.pageWidth>width||topic.pageWidth>width||map.pageWidth>width)throw Error('curriculum UI check failed');
socket.close();
