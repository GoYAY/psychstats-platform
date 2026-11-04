import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const port=Number(process.argv[2]||9243),root=process.argv[3],width=Number(process.argv[4]||1280);
const targets=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let id=0;const pending=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){const h=pending.get(m.id);pending.delete(m.id);m.error?h.reject(m.error):h.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
const delay=()=>new Promise(r=>setTimeout(r,700));
async function open(path){const [file,query]=path.split('?');const u=pathToFileURL(root+'/'+file);if(query)u.search=query;await send('Page.navigate',{url:u.href});await delay();}
function check(ok,message){if(!ok)throw Error(message);}
const visible=()=>evaluate(`[...document.querySelectorAll('[data-term]:not([hidden])')].map(x=>x.dataset.id)`);
try {
await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:width<=600});
await open('index.html');
check(await evaluate(`(()=>{const a=document.querySelector('.site-head nav a[aria-current="page"]');if(!a)return false;const s=getComputedStyle(a),t=getComputedStyle(document.querySelector('[data-topic-link="foundations"]')),rgb=t.backgroundColor.match(/\\d+/g).map(Number);return a.textContent==='术语'&&s.borderWidth==='0px'&&s.boxShadow!=='none'&&rgb[2]>rgb[0]&&t.boxShadow.includes('0.16')})()`),'主导航高亮或淡蓝色主题阴影尚未实现');
check(await evaluate(`!!document.querySelector('[data-topic-link="favorites"]')`),'缺少第11个收藏主题');
await evaluate(`localStorage.removeItem('psych-favorites-v1')`);await send('Page.reload');await delay();
check(await evaluate(`document.querySelectorAll('[data-topic-link]').length===11`),'主题数量错误');
check(await evaluate(`document.querySelector('[data-topic-count="foundations"]').textContent==='17'`),'基础术语数量错误');
check(await evaluate(`[...document.querySelectorAll('[data-topic-count]:not([data-topic-count="favorites"])')].every(c=>Number(c.textContent)===document.querySelectorAll('[data-term][data-topic="'+c.dataset.topicCount+'"]').length)`),'主题计数与术语不一致');
const style=await evaluate(`(()=>{const a=document.querySelector('[data-topic-link="foundations"]'),b=document.querySelector('[data-topic-link="regression"]');return {active:getComputedStyle(a).boxShadow,border:getComputedStyle(a).borderWidth,inactive:getComputedStyle(b).boxShadow,title:getComputedStyle(document.querySelector('.hero h1')).fontSize,nav:getComputedStyle(a).fontSize}})()`);
check(style.border==='0px'&&style.active!=='none'&&style.inactive==='none'&&parseFloat(style.title)>parseFloat(style.nav)*2,'导航或标题视觉层级错误');
const origin=await evaluate('performance.timeOrigin');
await evaluate(`document.querySelector('[data-favorite="variable"]').click();document.querySelector('[data-topic-link="regression"]').click();document.querySelector('[data-favorite="simple-linear-regression"]').click();document.querySelector('[data-topic-link="favorites"]').click()`);
check(JSON.stringify(await visible())===JSON.stringify(['variable','simple-linear-regression']),'收藏集合错误或破坏学习顺序');
check(await evaluate(`performance.timeOrigin===${origin}&&document.querySelector('.hero h1').textContent==='心理统计学术语'`),'收藏切换替换了页面');
await evaluate(`document.querySelector('#r-filter').value='true';document.querySelector('#r-filter').dispatchEvent(new Event('change',{bubbles:true}))`);
check(JSON.stringify(await visible())===JSON.stringify(['simple-linear-regression']),'收藏R筛选错误');
await evaluate(`document.querySelector('#r-filter').value='';document.querySelector('#r-filter').dispatchEvent(new Event('change'));document.querySelector('#favorite-topic-filter').value='foundations';document.querySelector('#favorite-topic-filter').dispatchEvent(new Event('change'))`);
check(JSON.stringify(await visible())===JSON.stringify(['variable']),'收藏原主题筛选错误');
await send('Page.reload');await delay();check((await visible()).length===2,'刷新丢失收藏');
await open('terms/p-value.html');await evaluate(`document.querySelector('[data-favorite="p-value"]').click()`);
check(await evaluate(`document.querySelector('[data-favorite="p-value"]').getAttribute('aria-pressed')==='true'`),'详情收藏没有反馈');
await send('Page.reload');await delay();check(await evaluate(`document.querySelector('[data-favorite="p-value"]').getAttribute('aria-pressed')==='true'`),'详情刷新丢失收藏');
await open('index.html?topic=favorites');check((await visible()).includes('p-value'),'file协议详情和首页收藏不共享');
check(await evaluate(`document.querySelector('[data-topic-count="favorites"]').textContent==='3'`),'收藏计数没有更新');
await evaluate(`document.querySelectorAll('[data-favorite][aria-pressed="true"]').forEach(b=>b.click())`);
check((await visible()).length===0&&await evaluate(`!document.querySelector('#filter-empty').hidden`),'取消收藏或空状态错误');
await evaluate(`document.querySelector('[data-topic-link="foundations"]').click()`);
check(await evaluate(`document.querySelector('#favorite-topic-filter').closest('label').hidden`),'非收藏主题暴露额外筛选');
check(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),'页面横向溢出');
await new Promise(r=>setTimeout(r,2400));
const screenshot=await send('Page.captureScreenshot',{format:'png'});await writeFile(`logs/favorites-${width}.png`,Buffer.from(screenshot.data,'base64'));
for (const [page,label] of [['paths.html','学习路径'],['practice.html','练习'],['datasets.html','示例数据'],['sources.html','来源说明'],['terms/anova.html','术语']]) {
  await open(page);
  check(await evaluate(`(()=>{const links=[...document.querySelectorAll('.site-head nav a[aria-current="page"]')];return links.length===1&&links[0].textContent===${JSON.stringify(label)}&&getComputedStyle(links[0]).boxShadow!=='none'&&document.documentElement.scrollWidth<=innerWidth})()`),'大页面选中状态或布局错误：'+page);
}
console.log(JSON.stringify({passed:true,width,style,sharedFileStorage:true}));
} finally { socket.close(); }
