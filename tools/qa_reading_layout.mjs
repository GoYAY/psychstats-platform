import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9291',width='1440'}=args(),ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx,results=[];
try{
 await page.send('Page.navigate',{url:'http://127.0.0.1:8765/psy-stats/index.html'});
 await until('document.readyState==="complete"&&!!document.querySelector(".topic-nav")');await wait(300);
 await run(`PsychSoftNavigation.navigate('http://127.0.0.1:8765/psy-stats/terms/sem.html')`);
 const initialText=await run('document.querySelector(".term-content").textContent');
 assert.ok(await run(`[...document.querySelectorAll('.term-content>section h2')].some(e=>!e.checkVisibility({contentVisibilityAuto:true}))`),'off-screen reading blocks must actually defer rendering');results.push('offscreen-deferred');
 // An off-screen code anchor must reveal its entire reading section.
 await run(`document.getElementById('r-example').scrollIntoView({block:'start',behavior:'instant'})`);await wait(500);
 assert.ok(await run(`(()=>{const r=document.getElementById('r-example').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0&&document.getElementById('r-example').checkVisibility({contentVisibilityAuto:true})})()`));
 const position=await run('scrollY'),anchorTop=await run('document.getElementById("r-example").getBoundingClientRect().top');await wait(400);assert.ok(Math.abs(await run('scrollY')-position)<2,'settled reading position does not jump');results.push('scroll-anchor-stable');
 // Back restores the same reading position after a different term was mounted.
 await run(`PsychSoftNavigation.navigate('http://127.0.0.1:8765/psy-stats/terms/variable.html')`);await run('history.back()');
 await until('document.querySelector(".term-content")?.dataset.termId==="sem"&&!PsychSoftMotion.running');await wait(400);
 assert.ok(Math.abs(await run('scrollY')-position)<2,'Back must restore the actual deep reading position');
 assert.ok(Math.abs(await run('document.getElementById("r-example").getBoundingClientRect().top')-anchorTop)<2,'Back restores the same content, not merely the same pixel offset');results.push('history-position');
 await run(`(()=>{const scope=document.getElementById('search-scope'),q=document.getElementById('q');scope.value='page';scope.dispatchEvent(new Event('change',{bubbles:true}));q.value='研究结果';q.dispatchEvent(new Event('input',{bubbles:true}))})()`);await wait(150);
 assert.ok(await run('document.querySelectorAll(".search-hit").length>0'),'page search finds deep retained text');
 await run(`document.getElementById('q').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}))`);await wait(300);
 assert.ok(await run(`(()=>{const r=document.querySelector('.search-hit.is-current').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0})()`));
 await run(`(()=>{const q=document.getElementById('q');q.value='';q.dispatchEvent(new Event('input',{bubbles:true}))})()`);await wait(120);
 assert.equal(await run('document.querySelector(".term-content").textContent'),initialText,'scientific text remains complete and unchanged');results.push('search-and-content');
 // Moving the outgoing article into the collapse layer must not change its
 // rendering mode or reflow all deferred reading blocks during the animation.
 await run(`(()=>{const real=Element.prototype.animate;window.__restoreAnimate=()=>Element.prototype.animate=real;Element.prototype.animate=function(...args){const a=real.apply(this,args);if(this.matches('.soft-outgoing-layer')&&document.documentElement.classList.contains('soft-kind-collapse')){a.pause();window.__collapseReady=true}return a};document.querySelector('[data-collapse-term]').click()})()`);
 await until('window.__collapseReady===true');
 assert.equal(await run(`getComputedStyle(document.querySelector('.soft-outgoing-layer .term-content>section:last-of-type')).contentVisibility`),'auto','outgoing reading blocks retain layout containment');
 await run('window.__restoreAnimate();document.getAnimations().forEach(a=>a.play())');await until('!PsychSoftMotion.running');
 await run(`PsychSoftNavigation.navigate('http://127.0.0.1:8765/psy-stats/terms/sem.html')`);results.push('collapse-layout-stable');
 await page.send('Emulation.setEmulatedMedia',{media:'print'});
 assert.ok(await run(`[...document.querySelectorAll('.term-content>section')].every(e=>getComputedStyle(e).contentVisibility==='visible')`),'print expands every block');results.push('print-complete');
 await page.send('Emulation.setEmulatedMedia',{media:''});
 await page.send('Page.navigate',{url:'http://127.0.0.1:8765/psy-stats/terms/sem.html#r-example'});
 await until('document.readyState==="complete"&&!!document.getElementById("r-example")');await wait(500);
 assert.ok(await run(`(()=>{const r=document.getElementById('r-example').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0})()`),'direct deep link remains visible');results.push('direct-hash');
 assert.ok(await run('document.documentElement.scrollWidth<=innerWidth'),'no horizontal overflow');
 const log=`logs/reading-layout-qa-${width}-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;await writeFile(log,JSON.stringify({width,results},null,2));console.log(log,results);
}finally{await ctx.close()}
