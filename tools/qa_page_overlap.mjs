import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9291',width='1440'}=args(),failures=[],samples=[];
for(const port of [8765,8766]){
 const ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx;
 try{
  await page.send('Page.navigate',{url:`http://127.0.0.1:${port}/psy-stats/${port===8765?'index.html':''}`});
  await until('document.readyState==="complete"&&!!document.querySelector(".topic-nav")');await wait(400);
  await run(port===8765?`(()=>{const real=Element.prototype.animate;Element.prototype.animate=function(...args){const a=real.apply(this,args);if(this.matches('body>main')&&document.documentElement.classList.contains('soft-kind-cover')){a.pause();window.__pageAnimation=a;window.__pageReady=true}return a}})()`:`(()=>{const real=document.startViewTransition.bind(document);document.startViewTransition=cb=>{const t=real(cb);t.ready.then(()=>{document.getAnimations().forEach(a=>a.pause());window.__pageReady=true});return t}})()`);
  for(const route of ['forward','return','history']){
   await run('window.__pageReady=false');
   if(route==='history')await run('history.back()');
   else await run(`document.querySelector(${JSON.stringify(route==='forward'?'.site-head nav a[href*="paths"]':`.site-head nav a[href${port===8765?'*="index.html"':'="/psy-stats/"'}]`)}).click()`);
   await until('window.__pageReady===true');
   for(const time of [0,45,100,199]){
    await run(`document.getAnimations().forEach(a=>a.currentTime=${time})`);
    const sample=await run(port===8765?`(()=>{const old=document.querySelector('.soft-outgoing-layer'),next=document.querySelector('body>main'),s=old&&getComputedStyle(old);return {oldVisible:!!old&&!old.hidden&&s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity)>0,newOpacity:Number(getComputedStyle(next).opacity),background:getComputedStyle(next).backgroundColor}})()`:`(()=>{const r=document.documentElement;return {oldVisible:getComputedStyle(r,'::view-transition-old(psych-body)').display!=='none'&&Number(getComputedStyle(r,'::view-transition-old(psych-body)').opacity)>0,newOpacity:Number(getComputedStyle(r,'::view-transition-new(psych-body)').opacity),background:getComputedStyle(document.querySelector('main')).backgroundColor}})()`);
    samples.push({port,route,time,...sample});
    if(sample.oldVisible)failures.push(`${port}/${route}/${time}: old正文 visible`);
    if(sample.newOpacity!==1)failures.push(`${port}/${route}/${time}: new正文 translucent`);
    if(sample.background!=='rgb(255, 255, 255)')failures.push(`${port}/${route}/${time}: transparent main`);
    if(route==='forward'&&time===45){const shot=await page.send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/page-overlap-mid-${port}-${width}.png`,Buffer.from(shot.data,'base64'));}
   }
   await run('document.getAnimations().forEach(a=>a.play())');
   await until(port===8765?'!window.PsychSoftMotion.running':'!document.documentElement.hasAttribute("data-psych-transition")');
  }
 }finally{await ctx.close()}
}
const log=`logs/page-overlap-${width}-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;
await writeFile(log,JSON.stringify({samples,failures},null,2));console.log(log);
assert.deepEqual(failures,[]);
