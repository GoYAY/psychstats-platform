import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9240), root=process.argv[3];
const targets=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const h=pending.get(m.id);pending.delete(m.id);m.error?h.reject(m.error):h.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});socket.send(JSON.stringify({id:key,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value;}
async function open(path){await send('Page.navigate',{url:pathToFileURL(root+'/'+path).href});await new Promise(r=>setTimeout(r,1400));}
await send('Page.enable');
await open('terms/cfa.html');
console.log(await evaluate(`JSON.stringify((()=>{const q=document.querySelector('.quiz');const feedback=[...q.querySelectorAll('.opt')].map(b=>{b.click();return {selected:b.getAttribute('aria-pressed'),text:b.nextElementSibling.textContent,visible:!b.nextElementSibling.hidden,result:q.querySelector('.quiz-result').textContent}});document.querySelector('[data-tab="your-data"]').click();return {feedback,templateVisible:!document.querySelector('[data-panel="your-data"]').hidden,math:document.querySelectorAll('math').length,formulaWidth:document.querySelector('.formula-display')?.scrollWidth,viewport:innerWidth,pageWidth:document.documentElement.scrollWidth};})())`));
await open('practice.html');
console.log(await evaluate(`JSON.stringify((()=>{const app=document.querySelector('#practice-app');return {bank:window.PsychSiteData.quizzes.length,feedback:[0,1,2,3].map(i=>{window.PsychPractice.init(app);app.querySelectorAll('[data-choice]')[i].click();return app.querySelector('.explain').textContent;})};})())`));
socket.close();
