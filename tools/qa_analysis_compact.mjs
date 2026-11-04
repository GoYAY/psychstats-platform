// Verify the compact reading flow in a real browser, including TOC interaction.
import assert from 'node:assert/strict';
import {readdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [port,rootArg,scope='all']=process.argv.slice(2),root=resolve(rootArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);
let seq=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
const files=(await readdir(root+'/analyses')).filter(f=>f.endsWith('.html')&&(scope==='all'||['mediation.html','moderation.html'].includes(f)));
const checks=[],failures=[];
try{
 await send('Page.enable');
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 for(const width of [1440,390])for(const file of files){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
  const url=pathToFileURL(root+'/analyses/'+file).href;
  await send('Page.navigate',{url});
  for(let i=0;i<100;i++){if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;await new Promise(r=>setTimeout(r,50));}
  const result=await run(`(async()=>{
   const bad=[],paper=document.querySelector('.paper-results'),toc=document.querySelector('.analysis-toc'),output=document.getElementById('analysis-output');
   const primary=paper?.querySelector('.paper-primary');
   if(primary?.querySelectorAll('figure,table').length!==1)bad.push('primary display count');
   if(paper?.querySelector('details[open]'))bad.push('supplement expanded by default');
   if(output?.compareDocumentPosition(paper)!==Node.DOCUMENT_POSITION_FOLLOWING)bad.push('paper before actual output');
   const links=[...toc.querySelectorAll('a')];
   if(links.length!==6||links.some(a=>!document.querySelector(a.hash)))bad.push('directory targets');
   const main=document.querySelector('.analysis-detail'),m=main.getBoundingClientRect(),n=toc.getBoundingClientRect();
   if(innerWidth>=1180&&(n.width>170||m.right>n.left||m.width<750||getComputedStyle(toc).position!=='sticky'))bad.push('desktop reading width or navigation overlap');
   document.querySelectorAll('.paper-primary img').forEach(i=>i.loading='eager');
   await Promise.all([...document.querySelectorAll('.paper-primary img')].map(i=>i.decode()));
   if(document.documentElement.scrollWidth>innerWidth+1)bad.push('page overflow');
   const mapping=document.querySelector('#analysis-design .analysis-variable-map');
   const rows=[...mapping?.querySelectorAll('tbody tr')||[]];
   if(!rows.length||rows.some(r=>r.cells.length!==3||[...r.cells].some(c=>!c.textContent.trim())))bad.push('missing variable correspondence');
   if(mapping&&mapping.scrollWidth>mapping.clientWidth+1)bad.push('variable correspondence overflows');
   const diagnoses=[...document.querySelectorAll('#analysis-diagnostics .analysis-diagnosis')];
   if(diagnoses.length<2||diagnoses.some(d=>d.closest('details')||!d.querySelector('h3')?.textContent.trim()||!d.querySelector('p')?.textContent.trim()))bad.push('diagnostics hidden or missing');
   links.find(a=>a.hash==='#paper-results').click();
   await new Promise(r=>setTimeout(r,200));
   if(location.hash!=='#paper-results'||toc.querySelector('[aria-current="location"]')?.hash!=='#paper-results')bad.push('navigation did not select section');
   const count=primary?.querySelectorAll('figure,table').length;
   return {bad,variableRows:rows.length,diagnosticCount:diagnoses.length,primaryDisplays:count,mainWidth:m.width,tocWidth:n.width,hash:location.hash,active:toc.querySelector('[aria-current="location"]')?.hash,paperTop:paper.getBoundingClientRect().top};
  })()`);
  checks.push({file,width,...result});if(result.bad.length)failures.push({file,width,...result});
  if(['mediation.html','moderation.html'].includes(file)){
   const shot=await send('Page.captureScreenshot',{format:'png'});
   await writeFile(`logs/paper-results/compact-${file.slice(0,-5)}-${width}.png`,Buffer.from(shot.data,'base64'));
  }
 }
 await writeFile('logs/paper-results/compact-browser-qa.json',JSON.stringify({checks,failures},null,2));
 assert.equal(failures.length,0,JSON.stringify(failures.slice(0,3)));console.log('Compact analysis:',checks.length,'desktop/mobile checks passed');
}finally{ws.close()}
