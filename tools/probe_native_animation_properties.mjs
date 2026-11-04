import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {args,isolatedPage} from './native-cdp.mjs';
const {cdp='9291'}=args(),ctx=await isolatedPage(cdp),{page,run,until}=ctx;
try{
 await page.send('Page.navigate',{url:'http://127.0.0.1:8766/psy-stats/index.html'});
 await until("document.readyState==='complete'&&!!document.querySelector('main')");
 await run(`(()=>{window.__animationProbe=[];window.__sourceBox=document.querySelector('.term-card[data-id="variable"]').getBoundingClientRect().toJSON();const start=document.startViewTransition.bind(document);document.startViewTransition=(...args)=>{const transition=start(...args);transition.ready.then(()=>queueMicrotask(()=>{__animationProbe.push(...document.getAnimations().map(a=>({name:a.animationName,pseudo:a.effect.pseudoElement,frames:a.effect.getKeyframes()})));window.__destinationBox=document.querySelector('.term-content>header').getBoundingClientRect().toJSON();document.getAnimations().forEach(a=>a.pause());window.__probeReady=true}));return transition};document.querySelector('.term-card[data-id="variable"] a[data-expand-card]').click()})()`);
 await until('window.__probeReady===true');
 assert.equal(await run("getComputedStyle(document.querySelector('.native-viewport>main')).backgroundColor"),'rgb(255, 255, 255)','Incoming reading snapshot needs an opaque paper surface');
 const groups=await run(`__animationProbe.filter(a=>a.name?.startsWith('-ua-view-transition-group-anim-'))`);
 assert.ok(groups.length>=2);
 assert.ok(groups.every(a=>a.frames.every(f=>!('width' in f)&&!('height' in f))),'Snapshot animations must not interpolate width/height');
 const samples=[];
 for(const time of [0,16,160,319]){
  await run(`document.getAnimations().forEach(a=>a.currentTime=${time})`);
  await run('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  samples.push(await run(`(()=>{const style=getComputedStyle(document.documentElement,'::view-transition-group(psych-morph)'),animation=document.getAnimations().find(a=>a.effect?.pseudoElement==='::view-transition-group(psych-morph)');return {time:${time},width:style.width,height:style.height,transform:style.transform,timing:animation?.effect.getComputedTiming(),animationTime:animation?.currentTime}})()`));
 }
 console.log(JSON.stringify(samples));
 assert.ok(samples.slice(1).every(s=>s.width===samples[1].width&&s.height===samples[1].height),'Active snapshot layout size remains constant while its transform changes');
 const bounds=s=>{assert.match(s.transform,/^matrix\(/);const m=s.transform.slice(7,-1).split(',').map(Number);return {x:m[4],y:m[5],width:Number.parseFloat(s.width)*m[0],height:Number.parseFloat(s.height)*m[3]}};
 const source=await run('__sourceBox'),destination=await run('__destinationBox'),first=bounds(samples[0]),last=bounds(samples.at(-1));
 assert.ok(Object.keys(first).every(key=>Math.abs(first[key]-source[key])<1),'Initial visible rectangle matches the actual source card');
 assert.ok(Object.keys(last).every(key=>Math.abs(last[key]-destination[key])<1),'Final visible rectangle matches the actual destination header');
 for(let i=1;i<samples.length;i++){const previous=bounds(samples[i-1]),next=bounds(samples[i]);assert.ok(next.x>=previous.x-1&&next.y<=previous.y+1,'The rectangle moves monotonically toward the destination');}
 assert.notEqual(samples[0].transform,samples.at(-1).transform);
 await run('document.getAnimations().forEach(a=>a.currentTime=160)');
 await mkdir('logs/complete-nav',{recursive:true});const shot=await page.send('Page.captureScreenshot',{format:'png'}),screenshot=`logs/complete-nav/compositor-expand-mid-${Date.now()}.png`;await writeFile(screenshot,Buffer.from(shot.data,'base64'));
 await run('document.getAnimations().forEach(a=>a.play())');
 await until("location.pathname.endsWith('/variable.html')&&!document.documentElement.dataset.psychTransition");
 const result=await run('__animationProbe');const path=`logs/complete-nav/animation-properties-${Date.now()}.json`;await writeFile(path,JSON.stringify({result,samples,source,destination,screenshot},null,2));console.log(path);console.log(JSON.stringify(result.map(a=>({name:a.name,pseudo:a.pseudo,keys:Object.keys(a.frames[0]||{})}))));
}finally{await ctx.close();}
