import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9260),root=process.argv[3],width=Number(process.argv[4]||1440);
const targets=await(await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws=new WebSocket(targets.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.onopen=r);let seq=0;const pending=new Map(),errors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++seq,{resolve,reject});ws.send(JSON.stringify({id:seq,method,params}))});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value};
const check=(v,m)=>{if(!v)throw Error(m)};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function open(path){const [file,query]=path.split('?');const target=pathToFileURL(root+'/'+file);if(query)target.search=query;const url=target.href;await send('Page.navigate',{url});for(let i=0;i<40;i++){await wait(60);if(await evaluate(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'`))return}throw Error('load timeout')}
async function query(value,scope='global'){await evaluate(`(()=>{const s=document.querySelector('#search-scope');s.value=${JSON.stringify(scope)};s.dispatchEvent(new Event('change'));const q=document.querySelector('#q');q.focus();q.value=${JSON.stringify(value)};q.dispatchEvent(new Event('input',{bubbles:true}))})()`);await wait(150)}
try{
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');
 await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
 await open('index.html?topic=regression');
 const cards=await evaluate(`[...document.querySelectorAll('[data-term]')].map(c=>({id:c.dataset.id,topic:c.dataset.topic}))`);
 await query('正态分布');
 check(await evaluate(`document.querySelector('#search-results a').getAttribute('href')==='terms/normal-distribution.html'`),'global search must ignore current topic');
 check(await evaluate(`document.querySelector('#topic-intro').dataset.topic==='regression'&&[...document.querySelectorAll('[data-term]:not([hidden])')].every(c=>c.dataset.topic==='regression')`),'global search must not rewrite topic browsing');
 await evaluate(`document.querySelector('[data-topic-link="foundations"]').click()`);
 for(let attempt=0;attempt<40;attempt++){
  if(await evaluate(`document.querySelector('#topic-intro').dataset.topic==='foundations'`))break;
  await wait(60);
 }
 await query('直方图','topic');
 check(await evaluate(`[...document.querySelectorAll('#search-results a')].some(a=>a.getAttribute('href')==='terms/normal-distribution.html')`),'topic search must find mentions in body');
 check(await evaluate(`[...document.querySelectorAll('#search-results a')].every(a=>a.textContent.includes('心理统计基础'))`),'topic search must stay scoped');
 await query('QQ图','topic');
 check(await evaluate(`[...document.querySelectorAll('#search-results a')].some(a=>a.getAttribute('href')==='terms/normal-distribution.html')`),'known alias must find body mentions');
 await open('terms/normal-distribution.html');
 check(await evaluate(`document.querySelector('.breadcrumb a:nth-of-type(2)').getAttribute('href')==='../index.html?topic=foundations'`),'breadcrumb restores correct topic');
 const links=await evaluate(`[...document.querySelectorAll('.detailed-explanation a')].map(a=>a.getAttribute('href'))`);
 for(const slug of ['histogram','qq-plot','skewness','extreme-value'])check(links.includes(slug+'.html'),'normal distribution missing concept link '+slug);
 await query('直方图');
 check(await evaluate(`document.querySelector('#search-results a').getAttribute('href')==='../terms/histogram.html'`),'term page global search must work');
 await query('标准差');
 check(await evaluate(`(()=>{const u=new URL(document.querySelector('#search-results a').href);return u.pathname.endsWith('/terms/central-tendency-and-dispersion.html')&&u.hash==='#standard-deviation'})()`),'core concept must link to its explanation anchor');
 await query('均值');
 await evaluate(`document.querySelector('#search-results a').click()`);await wait(650);
 check(await evaluate(`(()=>{const target=document.querySelector('#mean'),header=document.querySelector('.site-head');if(!target)return false;target.scrollIntoView({block:'start',behavior:'instant'});const h=target.querySelector('h3').getBoundingClientRect(),p=target.querySelector('p').getBoundingClientRect();return h.top>=header.getBoundingClientRect().bottom&&p.top<innerHeight})()`),'concept heading and first sentence must remain visible below sticky header');
 await open('terms/normal-distribution.html');
 await query('正态','page');
 check(await evaluate(`document.querySelectorAll('.search-hit').length>1`),'page search must highlight visible prose');
 const before=await evaluate(`document.querySelector('#search-status').textContent`);
 await evaluate(`document.querySelector('#find-next').click()`);
 check(await evaluate(`document.querySelector('#search-status').textContent!==${JSON.stringify(before)}&&document.querySelectorAll('.search-hit.is-current').length===1`),'page next result must update active highlight');
 await query('[不存在]+','page');
 check(await evaluate(`document.querySelector('#find-next').disabled&&document.querySelector('#search-status').textContent.includes('没有匹配')`),'page literal query and no-result guidance');
 await query('','page');
 check(await evaluate(`document.querySelectorAll('.search-hit').length===0`),'clear query removes highlights');
 await query('zz_no_such_term_94876');
 check(await evaluate(`!document.querySelector('#search-results a')&&document.querySelector('#search-status').textContent.includes('试试')`),'global empty state gives recovery help');
 await evaluate(`document.querySelector('#q').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`);
 check(await evaluate(`document.querySelector('#search-panel').hidden`),'Escape closes search');
 const idx=cards.findIndex(t=>t.id==='normal-distribution');
 for(const [direction,index] of [['previous',idx-1],['next',idx+1]])check(await evaluate(`document.querySelector('[data-direction="${direction}"]').getAttribute('href')===${JSON.stringify(cards[index].id+'.html')}`),'neighbor must match homepage card order');
 const boundary=cards.findIndex((t,i)=>i>0&&t.topic!==cards[i-1].topic);
 await open('terms/'+cards[boundary].id+'.html');
 check(await evaluate(`document.querySelector('[data-direction="previous"]').getAttribute('href')===${JSON.stringify(cards[boundary-1].id+'.html')}`),'cross-topic previous neighbor');
 await evaluate(`document.querySelector('.breadcrumb a:nth-of-type(2)').click()`);
 for(let attempt=0;attempt<40;attempt++){
  if(await evaluate(`document.querySelector('#topic-intro')?.dataset.topic===${JSON.stringify(cards[boundary].topic)}`))break;
  await wait(60);
 }
 check(await evaluate(`document.querySelector('#topic-intro').dataset.topic===${JSON.stringify(cards[boundary].topic)}`),'clicking breadcrumb shows own topic');
 await open('terms/sem.html');
 const layout=await evaluate(`(()=>{const a=document.querySelector('.term-content').getBoundingClientRect(),s=document.querySelector('.knowledge-sidebar').getBoundingClientRect(),prev=document.querySelector('[data-direction="previous"]').getBoundingClientRect(),next=document.querySelector('[data-direction="next"]').getBoundingClientRect();return{article:a.width,sidebar:s.width,scroll:document.documentElement.scrollWidth,prev:{x:prev.x,right:prev.right},next:{x:next.x,right:next.right},body:{x:a.x,right:a.right},navPosition:getComputedStyle(document.querySelector('[data-direction="previous"]')).position}})()`);
 check(layout.scroll<=width,'page must not overflow');
 if(width>=1200){check(layout.article>width/2&&layout.sidebar<=220&&layout.article>layout.sidebar*3,'desktop body must dominate sidebar');check(layout.prev.right<=layout.body.x&&layout.next.x>=layout.body.right,'side navigation must not cover prose')}
 else check(layout.navPosition!=='fixed','small-screen sequence navigation must be in document flow');
 const shot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/navigation-v4-${width}.png`,Buffer.from(shot.data,'base64'));
 check(errors.length===0,'JavaScript runtime errors '+errors.join(','));
 await writeFile(`logs/navigation-v4-${width}.json`,JSON.stringify({passed:true,width,layout},null,2));console.log(JSON.stringify({passed:true,width,layout}));
}finally{ws.close()}
