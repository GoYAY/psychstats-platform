import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9291',width='1440',base='http://127.0.0.1:8766/psy-stats/'}=args();
const ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx;
const failures=[],samples=[],errors=[];
page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
const pointerClick=async selector=>{
 const point=await run(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
 await page.send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
 await page.send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
};
try{
 await page.send('Page.navigate',{url:base});
 await until('document.readyState==="complete"&&!!document.querySelector(".topic-nav")');await wait(500);
 await run(`(()=>{const real=document.startViewTransition.bind(document);window.__navRecords=[];window.__pauseNav=true;document.startViewTransition=cb=>{const t=real(cb);window.__navReady=false;window.__navFinished=false;t.ready.then(()=>{if(__pauseNav)document.getAnimations().forEach(a=>a.pause());window.__navReady=true});t.finished.finally(()=>window.__navFinished=true);return t}})()`);
 for(const [label,selector,back] of [['forward','nav a[href*="paths"]',false],['return','nav a[href="/psy-stats/"]',false],['history',null,true]]){
  if(back)await run('history.back()');else await pointerClick(selector);
  await until('window.__navReady===true');
  const sample=await run(`(()=>{const p=document.querySelector('.nav-motion-indicator'),name=getComputedStyle(p).viewTransitionName,target=document.querySelector('.site-head nav [aria-current]'),r=target.getBoundingClientRect(),animations=document.getAnimations(),g=animations.find(a=>a.effect.pseudoElement==='::view-transition-group('+name+')'),last=g?.effect.getKeyframes().at(-1),m=last?new DOMMatrix(last.transform):null;return {name,elementAnimationCount:p.getAnimations().length,oldOpacity:getComputedStyle(document.documentElement,'::view-transition-old('+name+')').opacity,newOpacity:getComputedStyle(document.documentElement,'::view-transition-new('+name+')').opacity,endpoint:m?{x:m.e,y:m.f,width:parseFloat(last.width)*m.a}:null,target:{x:r.x,y:r.y,width:r.width},textNames:[...document.querySelectorAll('.site-head nav>a')].map(a=>getComputedStyle(a).viewTransitionName)}})()`);
  samples.push({label,...sample});
  if(sample.elementAnimationCount)failures.push(label+': duplicate component animation');
  if(sample.oldOpacity!=='0'||sample.newOpacity!=='1')failures.push(label+': old/new pill shadows both visible');
  if(!sample.endpoint||['x','y','width'].some(k=>Math.abs(sample.endpoint[k]-sample.target[k])>1))failures.push(label+': snapshot endpoint misses selected link');
  if(sample.textNames.some(n=>n==='none'))failures.push(label+': nav text shares root below pill snapshot');
  await run('document.getAnimations().forEach(a=>a.play())');await until('window.__navFinished===true');
  const aligned=await run(`(()=>{const p=document.querySelector('.nav-motion-indicator').getBoundingClientRect(),a=document.querySelector('nav [aria-current]').getBoundingClientRect();return ['x','y','width','height'].every(k=>Math.abs(p[k]-a[k])<1)})()`);
  assert.ok(aligned,label+': final pill aligns with selected link');
 }
 await run('window.__pauseNav=false');
 await pointerClick('nav a[href="/psy-stats/"]');await wait(80);await pointerClick('nav a[href*="paths"]');await wait(80);await pointerClick('nav a[href="/psy-stats/"]');
 await until('!document.documentElement.hasAttribute("data-psych-transition")');await wait(100);
 assert.equal(await run('!!document.querySelector(".topic-nav")'),true,'rapid clicks keep latest page');
 assert.ok(await run(`(()=>{const p=document.querySelector('.nav-motion-indicator').getBoundingClientRect(),a=document.querySelector('nav [aria-current]').getBoundingClientRect();return Math.abs(p.x-a.x)<1&&Math.abs(p.width-a.width)<1})()`),'rapid clicks keep pill aligned');
 assert.deepEqual(errors,[]);
 const file=`logs/native-nav-ghost-${width}-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;
 await writeFile(file,JSON.stringify({samples,failures,errors},null,2));console.log(file);
 assert.deepEqual(failures,[]);
}finally{await ctx.close();}
