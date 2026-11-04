import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,wait,args} from './native-cdp.mjs';
const {port='8765',cdp='9292',width='390',latency='0',site='local'}=args(),base=site==='online-test'?'https://cdst.site/psy-stats-test/':`http://127.0.0.1:${port}/psy-stats/`;
const ctx=await isolatedPage(cdp,Number(width)),{page,run,until}=ctx;
const results=[],metrics=[];
function check(name,value){results.push({name,pass:!!value});}
async function settled(path){await until(`location.pathname.endsWith(${JSON.stringify(path)})&&!window.PsychSoftMotion?.running&&!document.querySelector('.soft-navigation-status:not([hidden])')`);}
async function focus(){return run(`(()=>{const e=document.activeElement;return {tag:e.tagName,outline:getComputedStyle(e).outlineStyle,outlineWidth:getComputedStyle(e).outlineWidth,cardTransform:e.closest('.term-card')&&getComputedStyle(e.closest('.term-card')).transform}})()`);}
try{
 await page.send('Network.setCacheDisabled',{cacheDisabled:false});
 if(Number(latency))await page.send('Network.emulateNetworkConditions',{offline:false,latency:Number(latency),downloadThroughput:-1,uploadThroughput:-1});
 await page.send('Page.navigate',{url:base+'index.html?topic=foundations'});
 await until("document.readyState==='complete'&&!!window.PsychSoftNavigation&&!!document.querySelector('.topic-nav')");
 check('initial page recoverable without download',await run('!!PsychSoftNavigation.cache.get(location.href)'));
 await run("document.querySelector('.term-card[data-id=variable]').scrollIntoView({block:'center'})");
 await wait(2500);
 check('visible term prefetched without mouse hover',await run(`!!PsychSoftNavigation.cache.get(${JSON.stringify(base+'terms/variable.html')})`));
 await run(`(()=>{const a=document.querySelector('.term-card[data-id="variable"] a[data-expand-card]');a.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'touch'}));a.click()})()`);
 await until("location.pathname.endsWith('/terms/variable.html')&&window.PsychSoftMotion?.running");
 check('ready page animation is not labelled preparation',await run("document.querySelector('.soft-navigation-status').hidden"));
 await settled('/terms/variable.html');metrics.push(await run('PsychSoftNavigation.metrics.at(-1)'));
 const heading=await focus();check('pointer entry heading has no ring',heading.outline==='none'||heading.outlineWidth==='0px');
 await run('history.back()');await settled('/index.html');metrics.push(await run('PsychSoftNavigation.metrics.at(-1)'));
 const card=await focus();check('pointer return card has no ring',card.outline==='none'||card.outlineWidth==='0px');
 check('pointer restored card does not remain raised',card.cardTransform==='none'||card.cardTransform==='matrix(1, 0, 0, 1, 0, 0)');
 check('initial history return cache hit',metrics.at(-1).cached);
 await run(`(()=>{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));document.querySelector('.term-card[data-id="variable"] a[data-expand-card]').click()})()`);
 await settled('/terms/variable.html');const keyboard=await focus();check('keyboard navigation retains visible focus',keyboard.outline!=='none'&&keyboard.outlineWidth!=='0px');
 const file=`logs/complete-nav/navigation-readiness-${site==='online-test'?'online-test':port}-${width}-${Date.now()}.json`;
 await mkdir('logs/complete-nav',{recursive:true});await writeFile(file,JSON.stringify({base,browser:ctx.version.Browser,width,latency:Number(latency),results,metrics,heading,card,keyboard},null,2));
 console.log(JSON.stringify({file,results,metrics,heading,card,keyboard}));assert.ok(results.every(r=>r.pass),'Readiness/focus regression failed');
}finally{await ctx.close();}
