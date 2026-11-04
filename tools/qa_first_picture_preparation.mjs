import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {args,isolatedPage} from './native-cdp.mjs';
const {cdp='9291'}=args();
const results=[];
for(const width of [1440,390])for(const term of ['variable','sem']){
 const ctx=await isolatedPage(cdp,width),{run,page,until}=ctx;
 try{
  const topic=term==='sem'?'structural-equation-modeling':'foundations';
  await page.send('Page.navigate',{url:`http://127.0.0.1:8766/psy-stats/index.html?topic=${topic}`});
  await until("document.readyState==='complete'&&!!document.querySelector('main')");
  await run(`(()=>{window.__pictureStart=performance.now();const a=[...document.querySelectorAll('a[href]')].find(a=>a.href.includes('/terms/${term}.html')&&!a.closest('[hidden]'));if(!a)throw Error('Visible card not found');a.click()})()`);
  await until(`location.pathname.endsWith('/${term}.html')&&!document.documentElement.dataset.psychTransition`);
  const row=await run(`(()=>{const image=document.querySelector('main picture img');return {currentSrc:image.currentSrc,complete:image.complete,naturalWidth:image.naturalWidth,fontStatus:document.fonts.status,metric:window.PsychNativeMetrics.at(-1),fonts:performance.getEntriesByType('resource').filter(r=>r.startTime>=__pictureStart&&r.name.includes('/katex/fonts/')).map(r=>({name:r.name,responseEnd:r.responseEnd})),images:performance.getEntriesByType('resource').filter(r=>r.startTime>=__pictureStart&&r.name.includes('/examples/${term}')).map(r=>({name:r.name,responseEnd:r.responseEnd}))}})()`);
  const variant=term+(width<600?'-mobile':'')+'.svg';
  assert.equal(row.images.length,1,'Only the matching picture variant is requested');
  assert.ok(row.images[0].name.includes('/'+variant+'?v='));
  assert.ok(row.currentSrc.includes('/'+variant+'?v='));
  assert.ok(row.complete&&row.naturalWidth>0);
  assert.ok(row.images[0].responseEnd<=row.metric.prepared,'Image fetched before transition commit');
  assert.equal(row.fonts.length,term==='sem'?3:0,'Only the fonts used on this page are prepared');
  assert.ok(row.fonts.every(font=>font.responseEnd<=row.metric.prepared),'Formula fonts fetched before transition commit');
  assert.equal(row.fontStatus,'loaded');
  results.push({width,term,...row});
 }finally{await ctx.close();}
}
await mkdir('logs/complete-nav',{recursive:true});
const path=`logs/complete-nav/picture-preparation-${Date.now()}.json`;
await writeFile(path,JSON.stringify({results},null,2));console.log(path);
