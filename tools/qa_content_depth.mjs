import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9257),root=process.argv[3],width=Number(process.argv[4]||1280);
const targets=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const h=pending.get(m.id);pending.delete(m.id);m.error?h.reject(m.error):h.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
const delay=()=>new Promise(r=>setTimeout(r,650));
async function open(path){await send('Page.navigate',{url:pathToFileURL(root+'/'+path).href});await delay();}
function check(ok,message){if(!ok)throw Error(message);}
const tested=[];
try {
await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:width<=600});
await open('index.html');
check(await evaluate(`PsychSiteData.search.length===167&&PsychSiteData.quizzes.length===167`),'search/quiz counts');
// Add a new learning node without disturbing the user's browser profile.
await evaluate(`document.querySelector('[data-topic-link="factor-analysis"]').click();document.querySelector('[data-favorite="cronbach-alpha"]').click();document.querySelector('[data-topic-link="favorites"]').click()`);
check(await evaluate(`!document.querySelector('[data-term][data-id="cronbach-alpha"]').hidden`),'new favorite is not visible');
await send('Page.reload');await delay();
check(await evaluate(`document.querySelector('[data-term][data-id="cronbach-alpha"] [data-favorite]').getAttribute('aria-pressed')==='true'`),'new favorite did not persist');
await evaluate(`document.querySelector('[data-favorite="cronbach-alpha"]').click()`);
for(const slug of ['cronbach-alpha','mcdonald-omega','measurement-invariance','equivalence-testing','reverse-scoring','robust-standard-errors','cross-validation','t-test','anova','standard-error','number-of-factors','moderation-effect']) {
 await open('terms/'+slug+'.html');
 const state=await evaluate(`(()=>{const a=document.querySelector('article.term-content'),r=document.querySelector('.r-practice'),img=document.querySelector('.term-visual img');return {questionFirst:a.querySelector('section').classList.contains('real-question'),pageWidth:document.documentElement.scrollWidth,formula:document.querySelectorAll('.formula .katex').length,report:!!r&&r.textContent.includes('研究结果怎么写'),img:!img||(img.complete&&img.naturalWidth>0),imageSource:img?.currentSrc}})()`);
 check(state.questionFirst&&state.pageWidth<=width&&state.img,'question/image/layout '+slug);
 if(['cronbach-alpha','mcdonald-omega','equivalence-testing','reverse-scoring','robust-standard-errors','cross-validation','t-test','anova','moderation-effect'].includes(slug))check(state.report,'report missing '+slug);
 const options=await evaluate(`(()=>{const q=document.querySelector('.quiz'),answer=Number(q.dataset.answer);return [...q.querySelectorAll('.opt')].map((b,i)=>{b.click();const f=b.parentElement.querySelector('.option-feedback');return {visible:!f.hidden,explanation:f.textContent.trim(),result:q.querySelector('.quiz-result').textContent,correct:i===answer}})})()`);
 check(options.length===4&&options.every(o=>o.visible&&o.explanation&&(o.correct?o.result.includes('正确'):o.result.includes('错误'))),'per-option feedback '+slug);
 if(['t-test','anova','standard-error','number-of-factors','measurement-invariance'].includes(slug)) {
   if(width<=600)check(state.imageSource.endsWith('-mobile.svg'),'mobile SVG not selected '+slug);
   await evaluate(`document.querySelector('.term-visual').scrollIntoView({block:'start'})`);await delay();
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/content-depth-${width}-${slug}.png`,Buffer.from(shot.data,'base64'));
 }
 tested.push({slug,...state});
}
await open('terms/cronbach-alpha.html');await evaluate(`document.querySelector('.r-practice').scrollIntoView({block:'start'})`);await delay();
const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/content-depth-${width}-r-report.png`,Buffer.from(shot.data,'base64'));
console.log(JSON.stringify({passed:true,width,tested}));
} finally {socket.close();}
