import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9292',port='8768',width='1440',term='sem'}=args(),ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx;
try{
 await page.send('Network.setCacheDisabled',{cacheDisabled:false});
 await page.send('Network.emulateNetworkConditions',{offline:false,latency:350,downloadThroughput:-1,uploadThroughput:-1});
 await page.send('Page.navigate',{url:`http://127.0.0.1:${port}/psy-stats/index.html?topic=${term==='sem'?'structural-equation-modeling':'foundations'}`});
 await until("document.readyState==='complete'&&!!window.PsychSoftNavigation");await wait(200);
 await run(`window.__resourceStart=performance.getEntriesByType('resource').length;window.__originalDocument=document;document.querySelector('.term-card[data-id="${term}"] a[data-expand-card]').click()`);
 await until(`location.pathname.endsWith('/${term}.html')&&!PsychSoftMotion.running&&PsychSoftNavigation.metrics.length>0`);
 await run('document.fonts.ready');await wait(500);
 const data=await run(`(()=>{const image=document.querySelector('.term-content picture img'),m=PsychSoftNavigation.metrics.at(-1),imageURL=image?.currentSrc;return {port:${JSON.stringify(port)},width:innerWidth,term:${JSON.stringify(term)},metric:m,sameDocument:document===__originalDocument,image:{url:imageURL,complete:image?.complete,width:image?.naturalWidth},resources:performance.getEntriesByType('resource').slice(__resourceStart).filter(r=>r.name===imageURL||/KaTeX_.*woff2/.test(r.name)).map(r=>({url:r.name,start:r.startTime,end:r.responseEnd,relativeEnd:r.responseEnd-m.committed})),overflow:document.documentElement.scrollWidth>innerWidth}})()`);
 await mkdir('logs/complete-nav',{recursive:true});const file=`logs/complete-nav/network-readiness-${port}-${term}-${width}-${Date.now()}.json`;await writeFile(file,JSON.stringify(data,null,2));console.log(file,JSON.stringify(data));
 assert.equal(data.sameDocument,true);assert.equal(data.overflow,false);assert.equal(data.image.complete,true);assert.ok(data.image.width>0);
 assert.ok(data.resources.some(r=>r.url===data.image.url),'Expected actual first picture resource');
 assert.ok(data.resources.every(r=>r.end<=data.metric.committed+2),'First picture and formula fonts must finish before commit, including under network latency');
}finally{await ctx.close();}
