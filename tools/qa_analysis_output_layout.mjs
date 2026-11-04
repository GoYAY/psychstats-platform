// Regression: real output must remain legible and headers align with their cells.
import assert from 'node:assert/strict';
import {readdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [port,rootArg,scope='focused']=process.argv.slice(2);
const root=resolve(rootArg);
const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);
let seq=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
const files=scope==='all'?(await readdir(root+'/analyses')).filter(f=>f.endsWith('.html')):['linear-simple.html','describe.html'];
const failures=[],checks=[];
try{
 await send('Page.enable');
 for(const width of [1440,390])for(const file of files){
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
  const url=pathToFileURL(root+'/analyses/'+file).href;
  await send('Page.navigate',{url});
  for(let i=0;i<100;i++){
   if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;
   await new Promise(r=>setTimeout(r,50));
  }
  const result=await run(`(()=>{
   document.querySelectorAll('details').forEach(d=>d.open=true);
   const bad=[];
   const rgb=s=>(s.match(/[\\d.]+/g)||[]).slice(0,3).map(Number);
   const luminance=s=>rgb(s).map(x=>{x/=255;return x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4}).reduce((a,x,i)=>a+x*[0.2126,0.7152,0.0722][i],0);
   for(const pre of document.querySelectorAll('.analysis-detail pre')){
    const content=pre.querySelector('code')||pre,style=getComputedStyle(content);
    let backdrop=pre,background=getComputedStyle(backdrop).backgroundColor;
    while((background==='transparent'||background==='rgba(0, 0, 0, 0)')&&backdrop.parentElement){backdrop=backdrop.parentElement;background=getComputedStyle(backdrop).backgroundColor;}
    const a=luminance(style.color),b=luminance(background),contrast=(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
    if(contrast<4.5||pre.getBoundingClientRect().height<20||!pre.innerText.trim())bad.push({kind:'unreadable output',contrast,color:style.color,background,text:pre.innerText.slice(0,90)});
   }
   for(const table of document.querySelectorAll('.analysis-output table:has(thead)')){
    const heads=[...table.querySelectorAll('thead th')];
    for(const row of table.querySelectorAll('tbody tr'))for(const [i,cell] of [...row.cells].entries()){
     const h=heads[i];if(!h){bad.push({kind:'missing header',i});continue}
     if(getComputedStyle(h).textAlign!==getComputedStyle(cell).textAlign)bad.push({kind:'header alignment',header:h.innerText,headerAlign:getComputedStyle(h).textAlign,cellAlign:getComputedStyle(cell).textAlign});
     if(Math.abs(h.getBoundingClientRect().x-cell.getBoundingClientRect().x)>1||Math.abs(h.getBoundingClientRect().width-cell.getBoundingClientRect().width)>1)bad.push({kind:'column geometry',header:h.innerText});
    }
   }
   const sources=[...document.querySelectorAll('[data-analysis-source]')];
   if(!sources.length)bad.push({kind:'missing output annotations'});
   for(const source of sources){
    const meaning=document.querySelector('[data-analysis-meaning="'+source.dataset.analysisSource+'"]');
    if(source.dataset.topic!==meaning?.dataset.topic)bad.push({kind:'mismatched topic',field:source.dataset.analysisSource});
    const expected=getComputedStyle(source).getPropertyValue('--topic-color').trim();
    if(!expected)bad.push({kind:'missing topic color',topic:source.dataset.topic});
    const probe=document.createElement('span');probe.style.color=expected;document.body.append(probe);
    if(getComputedStyle(source).color!==getComputedStyle(probe).color)bad.push({kind:'wrong field color',field:source.dataset.analysisSource});
    probe.remove();
    source.classList.add('is-highlighted');meaning?.classList.add('is-highlighted');
    if(meaning&&getComputedStyle(source).boxShadow!==getComputedStyle(meaning).boxShadow)bad.push({kind:'mismatched highlight shadow'});
    source.classList.remove('is-highlighted');meaning?.classList.remove('is-highlighted');
   }
   const locate=document.querySelector('[data-analysis-locate]');
   locate?.click();
   if(locate&&document.activeElement?.dataset.analysisSource!==locate.dataset.analysisLocate)bad.push({kind:'locate did not focus output'});
   if(document.querySelector('.analysis-diagnosis')?.closest('details'))bad.push({kind:'collapsed diagnosis'});
   if(document.documentElement.scrollWidth>innerWidth+1)bad.push({kind:'page overflow'});
   return {bad,outputs:document.querySelectorAll('.analysis-detail pre').length,tables:document.querySelectorAll('.analysis-output table').length};
  })()`);
  checks.push({file,width,...result});if(result.bad.length)failures.push({file,width,...result});
  if(scope==='focused'&&width===1440){
   await run(`document.querySelector(${JSON.stringify(file==='describe.html'?'.analysis-warning':'.analysis-output:has(thead)')})?.scrollIntoView({block:'center',behavior:'instant'})`);
   const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/output-layout-${file.slice(0,-5)}.png`,Buffer.from(shot.data,'base64'));
  }
 }
 await writeFile('logs/analysis-output-layout.json',JSON.stringify({checks,failures},null,2));
 assert.deepEqual(failures,[],JSON.stringify(failures.slice(0,2),null,2));
 console.log('Output layout passed:',checks.length,'page/viewport checks');
}finally{ws.close()}
