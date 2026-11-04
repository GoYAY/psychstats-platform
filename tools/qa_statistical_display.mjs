import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {writeFile} from 'node:fs/promises';
const [port,rootArg]=process.argv.slice(2),root=resolve(rootArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);
let seq=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
let checks=0;
try{
 await send('Page.enable');
 for(const width of [1440,390])for(const file of ['linear-simple','sem','manova']){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
  const url=pathToFileURL(root+'/analyses/'+file+'.html').href;await send('Page.navigate',{url});
  let ready=false;for(let i=0;i<100;i++){if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`)){ready=true;break}await new Promise(r=>setTimeout(r,50));}assert.ok(ready);
  const issues=await run(`(()=>{
   const issues=[],note=document.querySelector('.analysis-reproduction-note'),body=document.querySelector('#analysis-design>p');
   if(!note||parseFloat(getComputedStyle(note.querySelector('p')).fontSize)>=parseFloat(getComputedStyle(body).fontSize))issues.push('reminder has body hierarchy');
   if(note?.closest('#analysis-design'))issues.push('reminder remains inside design');
   const significant=document.querySelector('.analysis-output .stat-significant');
   if(!significant||parseFloat(getComputedStyle(significant).fontWeight)<700)issues.push('significant value not visually bold');
   for(const cell of document.querySelectorAll('.analysis-output td')){
    const headers=[...cell.closest('table').querySelectorAll('thead th')],header=headers[cell.cellIndex]?.textContent||'';
    if(/^(p|pvalue|p[._]value|p_holm|Pr\\(.+\\)|Pr\\..+\\.)$/i.test(header)&&/[eE]-\\d+/.test(cell.textContent))issues.push('tiny p still scientific notation');
   }
   if(!document.querySelector('a[download][href$=".txt"]'))issues.push('raw output download missing');
   if(document.documentElement.scrollWidth>innerWidth+1)issues.push('page overflow');
   return issues;
  })()`);
  assert.deepEqual(issues,[],file+' at '+width);checks++;
  if(width===1440){await run(`document.querySelector(${JSON.stringify(file==='sem'?'.analysis-reproduction-note':'.analysis-output:has(table)')})?.scrollIntoView({block:'center',behavior:'instant'})`);const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/statistical-display-'+file+'.png',Buffer.from(shot.data,'base64'));}
 }
 console.log('Statistical display passed:',checks,'page/viewport checks');
}finally{ws.close()}
