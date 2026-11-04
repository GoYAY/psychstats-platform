// Real-browser checks for paper tables/figures on desktop and narrow screens.
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readdir,writeFile,readFile} from 'node:fs/promises';
const [port,rootArg]=process.argv.slice(2),root=resolve(rootArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);
let seq=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
const files=(await readdir(root+'/analyses')).filter(f=>f.endsWith('.html')).map(f=>'analyses/'+f);
for(const file of (await readdir(root+'/terms')).filter(f=>f.endsWith('.html'))){
 if((await readFile(root+'/terms/'+file,'utf8')).includes('class="paper-results"'))files.push('terms/'+file);
}
const failures=[];let checks=0;
try{
 await send('Page.enable');
 for(const width of [1440,390])for(const file of files){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
  const url=pathToFileURL(root+'/'+file).href;await send('Page.navigate',{url});
  for(let i=0;i<100;i++){if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;await new Promise(r=>setTimeout(r,50));}
  const issues=await run(`(async()=>{
   const issues=[],paper=document.querySelector('.paper-results');
   if(!paper)return ['missing paper results'];
   for(const img of paper.querySelectorAll('img')){img.loading='eager';try{await img.decode()}catch{issues.push('broken figure '+img.src)}if(!img.alt)issues.push('missing figure description');}
   await document.fonts.ready;
   if(!paper.querySelector('a[download][href*=".json"]'))issues.push('missing source data');
   for(const frame of document.querySelectorAll('.paper-figure,.paper-table-scroll,.analysis-detail .analysis-output,.analysis-detail .analysis-variable-map,.analysis-detail .analysis-dendrogram,.term-visual figure,.illustrated-example picture')){
    const b=frame.getBoundingClientRect(),p=frame.parentElement.getBoundingClientRect();
    if(b.width&&p.width-b.width<19)issues.push('missing horizontal figure/table gutter');
    if(b.width&&Math.abs((b.left-p.left)-(p.right-b.right))>2)issues.push('figure/table not centred');
   }
   for(const table of paper.querySelectorAll('table')){
    if(getComputedStyle(table).borderTopWidth!=='2px'||getComputedStyle(table).borderBottomWidth!=='2px')issues.push('three-line table boundary');
    const columns=[...table.querySelectorAll('thead th')];
    for(const row of table.querySelectorAll('tbody tr'))for(const [i,cell]of [...row.cells].entries()){
     if(getComputedStyle(cell).borderLeftWidth!=='0px')issues.push('vertical table border');
     if(cell.classList.contains('analysis-numeric')&&(getComputedStyle(cell).textAlign!=='right'||getComputedStyle(columns[i]).textAlign!=='right'))issues.push('numeric column alignment');
    }
   }
   if(document.documentElement.scrollWidth>innerWidth+1)issues.push('page overflow');
   return issues;
  })()`);
  if(issues.length)failures.push({file,width,issues});checks++;
  if(width===1440&&['analyses/mediation.html','analyses/moderation.html','analyses/conditional-mediation.html','terms/simple-linear-regression.html'].includes(file)){
   await run(`document.querySelector('.paper-results').scrollIntoView({block:'start',behavior:'instant'})`);
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile('logs/paper-results/browser-'+file.replaceAll('/','-')+'.png',Buffer.from(shot.data,'base64'));
  }
 }
 await writeFile('logs/paper-results/browser-qa.json',JSON.stringify({checks,failures},null,2));
 assert.deepEqual(failures,[]);console.log('Paper results:',checks,'desktop/mobile page checks passed');
}finally{ws.close()}
