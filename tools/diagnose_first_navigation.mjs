import {writeFile} from 'node:fs/promises';
const pages=await(await fetch('http://127.0.0.1:9290/json')).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const jobs=new Map(),requests=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Network.requestWillBeSent')requests.push({time:m.params.timestamp,url:m.params.request.url,type:m.params.type,headers:m.params.request.headers});if(jobs.has(m.id)){const j=jobs.get(m.id);jobs.delete(m.id);m.error?j.reject(m.error):j.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{jobs.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description);return r.result.value};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function open(url){await send('Page.navigate',{url});for(let i=0;i<150;i++){if(await run(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))break;await sleep(100)}await sleep(1000)}
const results={};
try{
await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
await open('http://127.0.0.1:8765/psy-stats/index.html?topic=foundations');
await run(`window.__profile=[];window.__parse=DOMParser.prototype.parseFromString;DOMParser.prototype.parseFromString=function(...a){const t=performance.now();const result=__parse.apply(this,a);__profile.push({stage:'parseHTML',ms:performance.now()-t,bytes:a[0].length});return result};for(const name of ['preparePage','mountPage']){const original=PsychPageRuntime[name];PsychPageRuntime[name]=function(...args){const t=performance.now(),result=original.apply(this,args);if(result?.then)return result.then(v=>{__profile.push({stage:name,ms:performance.now()-t});return v});__profile.push({stage:name,ms:performance.now()-t});return result}}`);
const local=[];
for(const path of ['symbols.html','index.html','symbols.html','terms/sem.html','index.html','terms/sem.html']){
 const r=await run(`(async()=>{__profile.length=0;const result=await PsychSoftNavigation.navigate(new URL(${JSON.stringify(path)},PsychSoftNavigation.siteRoot).href);return {result,metric:PsychSoftNavigation.metrics.at(-1),stages:__profile.slice()}})()`);local.push({path,...r});await sleep(200);
}
results.local=local;console.log('LOCAL '+JSON.stringify(local));
const start=requests.length;await open('https://vibe-hub.org/topics/technology');await sleep(2500);
const before=requests.slice(start);
const info=await run(`({nextScripts:[...document.scripts].map(s=>s.src).filter(s=>s.includes('/_next/')).length,links:[...document.querySelectorAll('a[href]')].filter(a=>a.href.includes('terminal')||a.href.includes('browser-devtools')||a.href.endsWith('/react')).map(a=>({text:a.textContent.trim().slice(0,60),href:a.href})),mainNodes:document.querySelector('main')?.querySelectorAll('*').length})`);
const target=info.links.find(a=>/\/terminal(?:$|\?)/.test(a.href))||info.links[0];
if(!target)throw Error('No reference term link found');
await run(`window.__documentProbe='retained';window.__frames=[];window.__sampling=true;window.__clickTime=performance.now();(()=>{let last=performance.now();function frame(t){__frames.push(t-last);last=t;if(__sampling)requestAnimationFrame(frame)}requestAnimationFrame(frame)})()`);
const clickStart=requests.length;await run(`document.querySelector('a[href="'+new URL(${JSON.stringify(target.href)}).pathname+'"]').click()`);
for(let i=0;i<150;i++){if(await run(`location.href===${JSON.stringify(target.href)}`))break;await sleep(100)}await sleep(500);
const outcome=await run(`(__sampling=false,{probe:window.__documentProbe,url:location.href,elapsed:performance.now()-__clickTime,frames:__frames,mainNodes:document.querySelector('main')?.querySelectorAll('*').length})`);
results.vibe={info,target,before,after:requests.slice(clickStart),outcome};
console.log('VIBE '+JSON.stringify({info,target,beforeFetch:before.filter(r=>r.type==='Fetch'),after:results.vibe.after,outcome:{...outcome,frames:undefined,frameMax:Math.max(...outcome.frames),over33:outcome.frames.filter(t=>t>33).length}}));
await writeFile('logs/first-navigation-diagnosis.json',JSON.stringify(results,null,2));
}finally{ws.close()}
