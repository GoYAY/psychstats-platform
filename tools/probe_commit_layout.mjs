import {mkdir,writeFile} from 'node:fs/promises';
import {args,isolatedPage,wait} from './native-cdp.mjs';
const {cdp='9292',term='sem'}=args(),ctx=await isolatedPage(cdp),{page,run,until}=ctx;
try{
 await page.send('Page.navigate',{url:`http://127.0.0.1:8766/psy-stats/index.html?topic=${term==='sem'?'structural-equation-modeling':'foundations'}`});
 await until("document.readyState==='complete'&&!!document.querySelector('main')");await wait(250);
 await run(`(()=>{window.__layoutReads=[];const instrument=(owner,key)=>{const original=owner[key];owner[key]=function(...args){const start=performance.now(),result=Reflect.apply(original,this,args),duration=performance.now()-start;if(duration>0.5)__layoutReads.push({method:key,start,duration,node:this.tagName?this.tagName+'.'+this.className:null,stack:new Error().stack});return result}};instrument(Element.prototype,'getBoundingClientRect');instrument(Document.prototype,'elementFromPoint');instrument(window,'scrollTo');instrument(Element.prototype,'scrollIntoView');document.querySelector('.term-card[data-id="${term}"] a[data-expand-card]').click()})()`);
 await until(`location.pathname.endsWith('/${term}.html')&&!document.documentElement.dataset.psychTransition&&!document.querySelector('.next-load-status')`);await wait(150);
 const data=await run(`({reads:__layoutReads,metrics:window.PsychNativeMetrics.at(-1),visibility:document.visibilityState})`);
 await mkdir('logs/complete-nav',{recursive:true});const file=`logs/complete-nav/commit-probe-${term}-${Date.now()}.json`;await writeFile(file,JSON.stringify(data,null,2));console.log(file);console.log(JSON.stringify(data));
}finally{await ctx.close();}
