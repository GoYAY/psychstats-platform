import assert from 'node:assert/strict';
import {readFile,writeFile,stat,readdir} from 'node:fs/promises';
import {createServer} from 'node:http';
import {resolve,join,extname,relative} from 'node:path';
import {pathToFileURL} from 'node:url';
const [port,rootArg]=process.argv.slice(2),root=resolve(rootArg),errors=[],checks=[];
const expectedCases=(await readdir(join(root,'analyses'))).filter(p=>p.endsWith('.html')).length;
const server=createServer(async(req,res)=>{
 try{
  const path=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if(relative(root,path).startsWith('..'))throw Error('outside root');
  const body=await readFile(path);const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'};
  res.writeHead(200,{'Content-Type':(types[extname(path)]||'application/octet-stream')+'; charset=utf-8'});res.end(body);
 }catch{res.writeHead(404);res.end('not found')}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const bases=[pathToFileURL(root+'/').href,`http://127.0.0.1:${server.address().port}/`];
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const pending=new Map(),contexts=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.executionContextCreated')contexts.set(m.params.context.id,m.params.context);if(m.method==='Runtime.exceptionThrown')errors.push({...m.params.exceptionDetails,context:contexts.get(m.params.exceptionDetails.executionContextId)});if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression:`(()=>{return eval(${JSON.stringify(expression)})})()`,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function open(base,page){
 const url=new URL(page,base).href;await send('Page.navigate',{url});
 for(let attempt=0;attempt<100;attempt++){
  if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`)){await wait(120);return}
  await wait(50);
 }
 assert.fail('page load timed out: '+url);
}
async function fit(){assert.ok(await run('document.documentElement.scrollWidth <= innerWidth+1'),'page overflow')}
try{
 await send('Page.enable');await send('Runtime.enable');await send('Emulation.setFocusEmulationEnabled',{enabled:true});
 for(const base of bases)for(const width of[1440,1024,768,390]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
  await open(base,'analysis.html');await fit();
  assert.equal(await run('document.querySelectorAll(".analysis-card").length'),expectedCases);
  assert.equal(await run(`[...document.querySelectorAll('.site-head nav a')].find(a=>a.getAttribute('href')==='analysis.html').getAttribute('aria-current')`),'page');
  await run('const f=document.getElementById("analysis-filter");f.value="结构方程";f.dispatchEvent(new Event("input"))');
  assert.ok(await run('document.querySelectorAll(".analysis-card:not([hidden])").length')>0,'method filter');
  await run('const f=document.getElementById("analysis-filter");f.value="不存在的分析名称";f.dispatchEvent(new Event("input"))');
  assert.equal(await run('document.querySelectorAll(".analysis-card:not([hidden])").length'),0);
  await open(base,'analyses/sem.html');await fit();
  assert.ok(await run('document.querySelectorAll(".analysis-output table").length')>=2,'actual parameter and fit tables');
  await run('window.a=document.querySelectorAll("[data-analysis-field]")[0];window.b=document.querySelectorAll("[data-analysis-field]")[1];a.click();b.dispatchEvent(new PointerEvent("pointerenter",{pointerType:"mouse"}))');
  assert.equal(await run('document.querySelectorAll(".analysis-field.is-highlighted").length'),2,'pinned+hover union');
  await run('b.dispatchEvent(new PointerEvent("pointerleave"));a.click();a.blur()');
  assert.equal(await run('document.querySelectorAll(".analysis-meaning.is-highlighted").length'),0,'unpin fully clears');
  await run('a.scrollIntoView();a.focus()');await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  assert.equal(await run('a.getAttribute("aria-pressed")'),'true','keyboard pin');
  await run('document.querySelector("[data-analysis-clear]").click()');
  assert.equal(await run('document.querySelectorAll(".is-highlighted").length'),0,'clear all');
  for(const href of await run('[...document.querySelectorAll("a[download]")].map(a=>a.href)')){
   if(href.startsWith('file:'))await stat(decodeURIComponent(new URL(href).pathname).replace(/^\/(\w:)/,'$1'));
   else assert.equal((await fetch(href)).status,200,'download');
  }
  if(base.startsWith('file:')&&(width===1440||width===390)){
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/analysis-reader-${width}.png`,Buffer.from(shot.data,'base64'));
  }
  await open(base,'analyses/hierarchical.html');await fit();
  assert.ok(await run('document.querySelectorAll(".tree-branches path").length')>=140,'actual tree geometry');
  if(base.startsWith('file:')&&(width===1440||width===390)){
   await run('document.querySelector(".analysis-dendrogram").scrollIntoView({block:"center",behavior:"instant"})');
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/analysis-tree-${width}.png`,Buffer.from(shot.data,'base64'));
  }
  checks.push({protocol:new URL(base).protocol,width,status:'pass'});
 }
 await send('Emulation.setScriptExecutionDisabled',{value:true});await open(bases[0],'analyses/sem.html');
 assert.ok(await run('document.body.innerText.includes("研究结果怎么写")&&document.querySelectorAll(".analysis-meaning").length>0'),'no JS content');
 await send('Emulation.setScriptExecutionDisabled',{value:false});
 await open(bases[0],'index.html');await run('const q=document.getElementById("q");q.value="量表";q.dispatchEvent(new Event("input"))');await wait(500);
 assert.ok(await run(`[...document.querySelectorAll('#search-results a')].filter(a=>a.href.includes('analyses/')).length`)>0,'global search analysis');
 await open(bases[0],'paths.html');await run(`[...document.querySelectorAll('.site-head nav a')].find(a=>a.getAttribute('href')==='analysis.html').click()`);await wait(950);
 assert.ok(await run('location.pathname.endsWith("analysis.html")&&!!document.querySelector(".nav-motion-indicator")'),'nav entry and slider');
 await writeFile('logs/analysis-reader-browser-errors.json',JSON.stringify(errors,null,2));
 assert.deepEqual(errors,[],'browser exceptions');
 await writeFile('logs/analysis-reader-browser.json',JSON.stringify({checks,errors,no_js:'pass',downloads:'pass',global_search:'pass',navigation:'pass'},null,2));
 console.log('Analysis reader browser QA passed:',checks.length,'responsive/protocol combinations');
}finally{await send('Emulation.setScriptExecutionDisabled',{value:false}).catch(()=>{});ws.close();server.close()}
