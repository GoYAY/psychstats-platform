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
const results=[];
try{
 await send('Page.enable');
 for(const width of [1440,390]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
  let baseline;
  for(const file of ['datasets.html','practice.html','symbols.html','analysis.html']){
   const url=pathToFileURL(root+'/'+file).href;await send('Page.navigate',{url});
   let ready=false;
   for(let i=0;i<100;i++){if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`)){ready=true;break}await new Promise(r=>setTimeout(r,50));}
   assert.ok(ready,'page load timed out');
   const heading=await run(`(()=>{const h=document.querySelector('main h1'),s=getComputedStyle(h),p=getComputedStyle(h.parentElement),b=h.getBoundingClientRect(),nav=document.querySelector('.site-head .wrap').getBoundingClientRect();return {font:s.fontSize,weight:s.fontWeight,family:s.fontFamily,line:s.lineHeight,spacing:s.letterSpacing,margin:s.margin,padding:p.padding,top:b.top,left:b.left-nav.left,overflow:document.documentElement.scrollWidth>innerWidth+1}})()`);
   if(!baseline)baseline=heading;
   assert.deepEqual(heading,baseline,width+' '+file+' differs from dataset page heading');
   results.push({file,width,...heading});
   if(width===1440&&['symbols.html','analysis.html'].includes(file)){const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/heading-'+file.slice(0,-5)+'.png',Buffer.from(shot.data,'base64'));}
  }
 }
 console.log('Page heading consistency passed:',results.length,'page/viewport checks');
 await writeFile('logs/page-heading-consistency.json',JSON.stringify(results,null,2));
}finally{ws.close()}
