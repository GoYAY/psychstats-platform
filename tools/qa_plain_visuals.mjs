import assert from 'node:assert/strict';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [port='9273']=process.argv.slice(2),root=resolve('site/dist');
const tabs=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(tabs.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let id=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const checks=[],clipped=[];
try{
 await send('Page.enable');await send('Runtime.enable');
 for(const width of [1280,390]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
  for(const slug of ['parameter-and-statistic','independence','data-cleaning','central-tendency-and-dispersion','skewness','degrees-of-freedom','population-and-sample','missing-data','correlation-coefficient','sem','box-plot','reverse-scoring','r-squared','confidence-interval','factor-extraction','hlm','null-hypothesis','significance-level','cluster-analysis','reliability','validity','model-identification','continuous-variable','probability-density','equivalence-testing','likelihood','maximum-likelihood','p-value','missing-data-mechanism','extreme-value','outlier','model-fit','type-i-and-type-ii-errors']){
   await send('Page.navigate',{url:pathToFileURL(resolve(root,'terms',slug+'.html')).href});await wait(150);
   const state=await run(`(()=>{const f=document.querySelector('.plain-example-visual');if(!f)return {missing:true};window.scrollTo({top:scrollY+f.getBoundingClientRect().top-(document.querySelector('.site-head')?.getBoundingClientRect().height||0)-20,behavior:'instant'});return {missing:false,overflow:document.documentElement.scrollWidth>innerWidth+1,broken:[...f.querySelectorAll('img')].some(i=>i.complete&&!i.naturalWidth),count:document.querySelectorAll('.plain-example-visual').length,notes:f.querySelectorAll('dt').length}})()`);
   assert.ok(!state.missing,slug);assert.ok(!state.overflow,slug+' page overflow');assert.ok(!state.broken,slug+' broken image');assert.equal(state.count,1);
   assert.equal(state.notes,0);assert.equal(await run(`document.querySelectorAll('.figure-narrative').length`),2);assert.equal(await run(`document.querySelectorAll('.figure-caution').length`),1);
   checks.push({width,slug,...state});
   if(['parameter-and-statistic','independence','data-cleaning','central-tendency-and-dispersion','skewness','degrees-of-freedom','sem','continuous-variable','probability-density','equivalence-testing','likelihood','validity'].includes(slug)){
    const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(resolve('logs',`plain-${slug}-${width}.png`),Buffer.from(shot.data,'base64'));
   }
  }
 }
 const files=[...(await readdir(resolve(root,'assets/examples'))).filter(f=>f.endsWith('.svg')).map(f=>'examples/'+f),...(await readdir(resolve(root,'assets/diagrams'))).filter(f=>f.endsWith('-glass.svg')).map(f=>'diagrams/'+f)];
 // Test painted glyph extents. SVG getBBox includes unused font ascent/descent\n // and falsely reports adjacent Chinese lines as touching; Canvas actualBoundingBox\n // measures their ink while preserving anchor and SVG transforms.
 for(const file of files){
  const svg=await readFile(resolve(root,'assets',file),'utf8');
  const errors=await run(`(()=>{document.body.innerHTML=${JSON.stringify(svg)};const svg=document.querySelector('svg'),w=svg.viewBox.baseVal.width,h=svg.viewBox.baseVal.height;const texts=[...svg.querySelectorAll('text')].map(t=>{const style=getComputedStyle(t),ctx=document.createElement('canvas').getContext('2d');ctx.font=style.font;ctx.textAlign=style.textAnchor==='middle'?'center':style.textAnchor==='end'?'right':'left';const metrics=ctx.measureText(t.textContent),b={x:(t.x.baseVal[0]?.value||0)-metrics.actualBoundingBoxLeft,y:(t.y.baseVal[0]?.value||0)-metrics.actualBoundingBoxAscent,width:metrics.actualBoundingBoxLeft+metrics.actualBoundingBoxRight,height:metrics.actualBoundingBoxAscent+metrics.actualBoundingBoxDescent},m=svg.getScreenCTM().inverse().multiply(t.getScreenCTM()),pts=[[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(m)),xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);return {text:t.textContent,b:{x:Math.min(...xs),y:Math.min(...ys),width:Math.max(...xs)-Math.min(...xs),height:Math.max(...ys)-Math.min(...ys)}}});const bad=texts.filter(o=>o.b.x < -1 || o.b.x+o.b.width>w+1 || o.b.y<0 || o.b.y+o.b.height>h+1).map(o=>o.text);const intersect=(a,b)=>Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>2&&Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>2;for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++)if(intersect(texts[i].b,texts[j].b))bad.push('重叠:'+texts[i].text+'/'+texts[j].text);const nodes=[...svg.querySelectorAll('[data-network-node]')].map(e=>e.getBBox());for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++)if(intersect(nodes[i],nodes[j]))bad.push('节点重叠');return bad})()`);
  if(errors.length)clipped.push({file,errors});
 }
 await writeFile(resolve('logs/plain-visual-browser.json'),JSON.stringify({checks,svgCount:files.length,clipped},null,2));
 console.log(JSON.stringify({pageChecks:checks.length,svgCount:files.length,clipped}));
 assert.equal(clipped.length,0,'SVG text must stay inside diagram');
}finally{ws.close()}
