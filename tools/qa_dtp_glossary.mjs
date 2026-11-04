// Local-only interaction/privacy QA. No model or external navigation.
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {writeFile,mkdir} from 'node:fs/promises';
import {isolatedPage,wait} from './native-cdp.mjs';
const folder=resolve(process.env.DTP_QA_JOB||'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run','preview');
const out=resolve('logs/term-explainer/glossary-browser');await mkdir(out,{recursive:true});
const reports=[];
for(const width of [1440,390]){
 const browser=await isolatedPage(9278,width);const run=browser.run;
 const press=async(key,code,keyCode)=>{const text=key==='Enter'?'\r':key===' '?' ':'';await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:keyCode,...(text?{text,unmodifiedText:text}:{})});await browser.page.send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:keyCode});};
 try{
  if(width<600)await browser.page.send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
  await browser.page.send('Page.navigate',{url:pathToFileURL(resolve(folder,'index.html')).href});
  await browser.until('document.readyState==="complete" && !!document.querySelector("[data-note=tirt]")');
  await run('document.fonts.ready');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab'});
  await run(`scrollTo(0,0);document.querySelector('[data-note="se"]').focus()`);
  await run('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  assert.ok(await run(`document.getElementById('term-popover').hidden`),'Focus alone must not open a note');
  await press('Enter','Enter',13);
  assert.ok(await run(`!document.getElementById('term-popover').hidden && document.activeElement.getAttribute('aria-describedby')?.includes('term-popover-description')`),'Explicit keyboard activation must preserve its explanation while scrolling');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await run('document.activeElement.blur()');
  const point=async key=>{await run(`document.querySelector('[data-note="${key}"]').scrollIntoView({behavior:'instant',block:'center'})`);
   // Let the programmatic scroll event finish: scrolling intentionally dismisses
   // notes. A real hover starts after scrolling, not in the same rendering frame.
   await run('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
   return run(`(()=>{const r=document.querySelector('[data-note="${key}"]').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`);};
  const p=await point('tirt');
  if(width>=600){
   await browser.page.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});await browser.page.send('Input.dispatchMouseEvent',{type:'mouseMoved',...p});
   await wait(180);
   assert.ok(await run('document.getElementById("term-popover").hidden'),'Hover must show an affordance, not open the panel');
   const style=await run(`(()=>{const s=getComputedStyle(document.querySelector('[data-note=tirt]'));return {shadow:s.boxShadow,border:s.borderTopWidth}})()`);
   assert.notEqual(style.shadow,'none');assert.equal(style.border,'0px');
   await browser.page.send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});
   await browser.page.send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});
  }
  else{
   await browser.page.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[p]});
   await browser.page.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  }
  await browser.until('!document.getElementById("term-popover").hidden');
  await wait(180);
  const popup=await run(`(()=>{const e=document.getElementById('term-popover'),r=e.getBoundingClientRect();return {text:e.textContent,width:r.width,left:r.left,right:r.right,top:r.top,bottom:r.bottom}})()`);
  assert.match(popup.text,/用陈述之间的偏好/);assert.ok(popup.width<=322&&popup.left>=8&&popup.right<=width-8);
  if(width>=600){
   await browser.page.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:popup.left+30,y:popup.top+25});await wait(200);
   assert.ok(await run('!document.getElementById("term-popover").hidden'));
   const another=await run(`(()=>{const panel=document.getElementById('term-popover').getBoundingClientRect();for(const e of document.querySelectorAll('main [data-note]')){const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;if(e.dataset.note!=='tirt'&&r.top>0&&r.bottom<innerHeight&&!(x>=panel.left&&x<=panel.right&&y>=panel.top&&y<=panel.bottom))return {x,y};}return null})()`);
   assert.ok(another);await browser.page.send('Input.dispatchMouseEvent',{type:'mouseMoved',...another});await wait(180);
   assert.equal(await run('document.getElementById("term-popover-title").textContent'),'TIRT','Hovering another helper must not replace an explicitly opened note');
  }
  const shot=await browser.page.send('Page.captureScreenshot',{format:'png'});await writeFile(resolve(out,`${width}-popover.png`),Buffer.from(shot.data,'base64'));
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await browser.until('document.getElementById("term-popover").hidden');
  await run(`document.querySelector('[data-note="discrimination"]').focus()`);
  assert.ok(await run('document.getElementById("term-popover").hidden'));
  await press('Enter','Enter',13);
  await browser.until('!document.getElementById("term-popover").hidden');
  assert.ok(await run(`document.querySelector('[data-note="discrimination"]').tagName==='BUTTON' && document.getElementById('term-popover-link').hidden`));
  assert.equal(await run(`document.activeElement.getAttribute('aria-describedby')`),'term-popover-description term-popover-hint');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown'});
  assert.equal(await run('document.activeElement.id'),'term-popover');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  assert.ok(await run(`document.activeElement.dataset.note==='discrimination' && !document.activeElement.getAttribute('aria-describedby').includes('term-popover-description') && document.getElementById('term-popover').hidden`));
  await run(`document.querySelector('[data-note="se"]').focus()`);
  assert.ok(await run('document.getElementById("term-popover").hidden'));
  await press(' ','Space',32);
  await browser.until('!document.getElementById("term-popover-link").hidden');
  assert.equal(await run('document.getElementById("term-popover-link").getAttribute("href")'),'https://cdst.site/psy-stats/terms/standard-error.html');
  assert.equal(await run(`document.querySelector('[data-note="discrimination"]').getAttribute('aria-describedby')`),'term-popover-hint');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown'});
  assert.equal(await run('document.activeElement.id'),'term-popover-link');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',modifiers:8});
  assert.equal(await run('document.activeElement.dataset.note'),'se');
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown'});
  const nextControl=await run(`(()=>{const p=document.getElementById('term-popover'),all=[...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')].filter(e=>e.tabIndex>=0&&!e.disabled&&!p.contains(e)&&e.getClientRects().length);const n=all[all.indexOf(document.querySelector('[data-note="se"]'))+1];n.dataset.qaNext='true';return n.tagName})()`);
  assert.ok(nextControl);
  await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab'});
  assert.equal(await run('document.activeElement.dataset.qaNext'),'true');
  await run(`document.body.click()`);await browser.until('document.getElementById("term-popover").hidden');
  if(width<600){
   const linked=await point('se');
   await browser.page.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[linked]});
   await browser.page.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   await browser.until('!document.getElementById("term-popover").hidden');
   await wait(150);assert.ok(await run('location.protocol==="file:"'));
   await browser.page.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[linked]});
   await browser.page.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   await browser.until('document.getElementById("term-popover").hidden');
   await run('document.body.click()');
  }
  const metrics=await run(`({scrollWidth:document.documentElement.scrollWidth,
   sourceRows:document.querySelectorAll('#sources li').length,rawPassages:document.querySelectorAll('#sources blockquote,#sources details').length,
   hasRawExcerpt:document.documentElement.outerHTML.includes('Although much has been accomplished in the research on MFC-based scoring'),
   controls:document.querySelectorAll('[data-note]').length,nestedControls:document.querySelectorAll('.term-help .term-help').length,
   nonBodyControls:document.querySelectorAll('#formulas [data-note],#quiz [data-note],figcaption [data-note],#real_question [data-note],#academic_expression [data-note],#evidence-scope [data-note]').length,
   excessiveNotes:['block','pair','positive-keying','negative-keying','dtp-rule','matching','estimation','high-correlation'].filter(k=>k in JSON.parse(document.getElementById('term-notes').textContent))})`);
  assert.ok(metrics.scrollWidth<=width);assert.equal(metrics.sourceRows,Number(process.env.DTP_QA_SOURCE_COUNT||1));assert.equal(metrics.rawPassages,0);assert.equal(metrics.hasRawExcerpt,false);assert.equal(metrics.nestedControls,0);
  assert.equal(metrics.nonBodyControls,0);assert.deepEqual(metrics.excessiveNotes,[]);
  reports.push({width,popup,metrics,status:'pass',apiCalls:0});
 }finally{await browser.close();}
}
await writeFile(resolve(out,'report.json'),JSON.stringify(reports,null,2));
console.log('Click-only helper notes passed: hover shadow without border, no focus auto-open, Enter/Space, panel keyboard order, Escape, touch toggle, explicit selection/body scope, classic routes and source privacy.');
