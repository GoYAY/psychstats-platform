import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const port = Number(process.argv[2] || 9265), root = process.argv[3];
const width = Number(process.argv[4] || 1280);
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0;
const pending = new Map(), errors = [];
const film = [];
let filming = false, navigationTime = 0;
ws.onmessage = event => {
  const message = JSON.parse(event.data);
  if (filming && message.method === 'Page.frameNavigated') navigationTime = Date.now();
  if (message.method === 'Page.screencastFrame') {
    if (filming) film.push({data:message.params.data,time:Date.now(),navigationTime});
    send('Page.screencastFrameAck',{sessionId:message.params.sessionId});
    return;
  }
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
  const task = pending.get(message.id);
  if (!task) return;
  pending.delete(message.id);
  message.error ? task.reject(message.error) : task.resolve(message.result);
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  pending.set(++sequence, {resolve, reject});
  ws.send(JSON.stringify({id: sequence, method, params}));
});
const evaluate = async expression => {
  const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  assert.ok(!result.exceptionDetails, result.exceptionDetails?.exception?.description);
  return result.result.value;
};
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function open(page) {
  const url = new URL(page, pathToFileURL(root + '/')).href;
  await send('Page.navigate', {url});
  for (let i = 0; i < 60; i++) {
    await wait(30);
    if (await evaluate(`location.href === ${JSON.stringify(url)} && document.readyState === 'complete'`)) return;
  }
  throw Error('Page load timeout');
}
async function landed(path) {
  for (let i = 0; i < 60; i++) {
    await wait(30);
    try {
      if (await evaluate(`location.pathname.endsWith(${JSON.stringify(path)}) && document.readyState === 'complete'`)) {
        await wait(700); return;
      }
    } catch (_) { /* Execution context is replaced during native navigation. */ }
  }
  throw Error('Native navigation timeout: ' + path);
}
async function click(x, y) {
  await send('Input.dispatchMouseEvent', {type: 'mousePressed', x, y, button: 'left', clickCount: 1});
  await send('Input.dispatchMouseEvent', {type: 'mouseReleased', x, y, button: 'left', clickCount: 1});
}
async function point(selector) {
  return evaluate(`(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    element.scrollIntoView({block:'center',behavior:'instant'});
    const box = element.getBoundingClientRect();
    return {x:box.left+box.width/2, y:box.top+Math.min(18,box.height/2)};
  })()`);
}
async function verifyArrival(label, expectedTitle) {
  const frames = await evaluate('window.__expansionFrames');
  const expanded = frames.filter(frame => frame.panel);
  if (expanded.length < 3) console.log(JSON.stringify(await evaluate(`({before:window.__transitionBeforeScript,events:window.__transitionEvents,frames:window.__expansionFrames.slice(0,8)})`)));
  assert.ok(expanded.length >= 3, label + ': visible expansion frames, not a hard cut');
  assert.ok(Math.abs(expanded[0].panel.width - expanded.at(-1).panel.width) > 20 ||
            Math.abs(expanded[0].panel.height - expanded.at(-1).panel.height) > 20,
            label + ': panel expands from card dimensions to article dimensions');
  assert.ok(expanded.some(frame => frame.active), label + ': animation remains active after pageshow');
  const viewportWidth=await evaluate('document.documentElement.clientWidth');
  assert.ok(expanded.at(-1).panel.width >= viewportWidth-2,label+': opens the entire page, not a narrow article panel');
  assert.ok(expanded.every(frame => frame.shadow==='none' && frame.border===0),label+': no outlined or shadowed intermediate page');
  assert.ok(expanded.every(frame=>!frame.titleDescriptionOverlap),label+': moving title does not overlap the destination English name');
  assert.ok(await evaluate(`(() => {
    const title = document.querySelector('.term-content > header h1');
    return title.textContent === ${JSON.stringify(expectedTitle)} && getComputedStyle(title).visibility === 'visible'
      && !document.querySelector('.term-transition-scene') && !document.documentElement.classList.contains('term-transition-pending')
      && !sessionStorage.getItem('psychstats.card-transition.v1') && document.documentElement.scrollWidth <= innerWidth;
  })()`), label + ': final content visible, temporary state cleared, no overflow');
  return {label, frames: expanded.length, first: expanded[0], last: expanded.at(-1)};
}

try {
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.addScriptToEvaluateOnNewDocument', {source: `(() => {
    window.__expansionFrames=[];window.__transitionEvents=[];const start=performance.now();
    try{const raw=sessionStorage.getItem('psychstats.card-transition.v1');const o=raw?JSON.parse(raw):null;window.__transitionBeforeScript=o?{href:o.href,width:o.width,height:o.height,bytes:o.html.length}:null}catch(error){window.__transitionBeforeScript={error:error.message}}
    for(const name of ['DOMContentLoaded','pageshow'])addEventListener(name,()=>window.__transitionEvents.push({name,classes:document.documentElement.className,scene:!!document.querySelector('.term-transition-scene')}));
    function frame(){
      const panel=document.querySelector('.term-transition-panel');
      const box=panel?.getBoundingClientRect();
      const title=document.querySelector('.term-transition-title'),description=document.querySelector('.term-content > header > p');
      const t=title?.getBoundingClientRect(),d=description?.getBoundingClientRect();
      const descriptionVisible=description&&parseFloat(getComputedStyle(description).opacity)>.25&&parseFloat(getComputedStyle(description.closest('main')).opacity)>.4;
      window.__expansionFrames.push({time:Math.round(performance.now()-start),
        active:document.documentElement?.classList.contains('term-transition-active'),
        shadow:panel?getComputedStyle(panel).boxShadow:null,
        border:panel?parseFloat(getComputedStyle(panel).borderTopWidth):null,
        titleDescriptionOverlap:!!(t&&d&&descriptionVisible&&t.top<d.bottom&&t.bottom>d.top),
        panel:box?{width:box.width,height:box.height,x:box.x,y:box.y}:null});
      if(performance.now()-start<1000)requestAnimationFrame(frame);
    }requestAnimationFrame(frame);
  })();`});
  await send('Emulation.setDeviceMetricsOverride', {width,height:900,deviceScaleFactor:1,mobile:width<600});
  await open('index.html?topic=foundations');
  assert.ok(await evaluate(`document.title === '心理统计学术语图鉴-轻松掌握心理统计和r语言数据分析' && document.querySelector('.brand img').naturalWidth === 48`));
  const home = await evaluate(`(() => {const c=document.querySelector('.term-card:not([hidden])');return {id:c.dataset.id,title:c.querySelector('h2').textContent}})()`);
  const p = await point('.term-card:not([hidden]) h2');
  await send('Input.dispatchMouseEvent', {type:'mouseMoved',...p}); await wait(220);
  const actual = await point('.term-card:not([hidden]) h2');
  if(width===1280){filming=true;await send('Page.startScreencast',{format:'png',maxWidth:1280,maxHeight:900,everyNthFrame:1});}
  await click(actual.x,actual.y); await landed('/terms/' + home.id + '.html');
  const results = [await verifyArrival('Home card',home.title)];
  if(filming){
    await send('Page.stopScreencast');filming=false;
    const arrival=film.filter(frame=>frame.navigationTime);
    assert.ok(arrival.length>=3,'Animation screencast must contain intermediate frames');
    for(const time of [120,250,600]){
      const frame=arrival.reduce((best,current)=>Math.abs(current.time-current.navigationTime-time)<Math.abs(best.time-best.navigationTime-time)?current:best);
      await writeFile(`logs/card-expansion-v2-${width}-${time}ms.png`,Buffer.from(frame.data,'base64'));
    }
  }
  await evaluate(`(() => {const s=document.querySelector('#search-scope'),q=document.querySelector('#q');s.value='page';s.dispatchEvent(new Event('change'));q.value=${JSON.stringify(home.title)};q.dispatchEvent(new Event('input',{bubbles:true}))})()`);
  await wait(150);
  assert.ok(await evaluate(`!!document.querySelector('.term-content .search-hit')`),'Page search binds the real destination, not the temporary snapshot');
  await evaluate(`document.querySelector('#q').value='';document.querySelector('#q').dispatchEvent(new Event('input',{bubbles:true}))`);
  await evaluate(`document.querySelector('.quiz .opt').click()`);
  assert.ok(await evaluate(`!!document.querySelector('.quiz-result').textContent`),'Term quiz initialized after expansion');
  await evaluate('history.back()'); await landed('/index.html');
  assert.ok(await evaluate(`document.querySelector('#topic-intro').dataset.topic==='foundations' && !document.querySelector('.term-transition-scene') && window.__expansionFrames.every(f=>!f.panel)`),'Back restores source without replay');

  await open('practice.html');
  await evaluate(`document.querySelector('[data-choice]').click()`);
  await evaluate(`document.querySelector('.practice-reading').scrollIntoView({block:'start',behavior:'instant'})`);
  assert.ok(await evaluate(`!document.querySelector('.practice-full-link') && !!document.querySelector('.practice-open-link') && !!document.querySelector('.practice-reading a:not([data-expand-card])')`),'Header entry replaces footer and preserves concept links');
  const practice = await evaluate(`({id:window.PsychPracticeData[0].term_id,title:document.querySelector('.practice-reading h2').textContent})`);
  const blank = await evaluate(`(() => {const b=document.querySelector('.practice-reading').getBoundingClientRect(),h=document.querySelector('.site-head').getBoundingClientRect();return {x:b.right-8,y:Math.max(h.bottom+20,b.top+12)}})()`);
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',...blank});await wait(220);
  assert.ok(await evaluate(`getComputedStyle(document.querySelector('.practice-reading')).boxShadow!=='none' && Number(getComputedStyle(document.querySelector('.practice-expand-hint')).opacity)>.9`),'Hover lifts reading panel and reveals entry');
  await evaluate(`(() => {const range=document.createRange();range.selectNodeContents(document.querySelector('.practice-reading p'));const s=getSelection();s.removeAllRanges();s.addRange(range)})()`);
  // A synthetic click avoids clearing the selection before the handler can inspect it.
  await evaluate(`document.querySelector('.practice-reading').dispatchEvent(new MouseEvent('click',{bubbles:true,button:0}))`);
  assert.ok(await evaluate(`location.pathname.endsWith('/practice.html') && !sessionStorage.getItem('psychstats.card-transition.v1')`),'Selecting text does not navigate');
  await evaluate(`getSelection().removeAllRanges()`);
  await click(blank.x,blank.y); await landed('/terms/' + practice.id + '.html');
  results.push(await verifyArrival('Practice panel',practice.title));

  await open('practice.html'); await evaluate(`document.querySelector('[data-choice]').click();document.querySelector('.practice-open-link').scrollIntoView({block:'center',behavior:'instant'});document.querySelector('.practice-open-link').focus({preventScroll:true})`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await landed('/terms/' + practice.id + '.html');
  results.push(await verifyArrival('Keyboard entry',practice.title));

  await open('index.html');
  const formulaPoint=await point('.term-card[data-id="correlation-coefficient"] h2');
  await click(formulaPoint.x,formulaPoint.y);await landed('/terms/correlation-coefficient.html');
  results.push(await verifyArrival('Formula and R page','相关系数'));
  await evaluate(`document.querySelector('.formula-key').click();document.querySelector('[data-tab="your-data"]').click()`);
  assert.ok(await evaluate(`document.querySelector('.formula-key').getAttribute('aria-pressed')==='true' && document.querySelector('[data-panel="example"]').hidden && !document.querySelector('[data-panel="your-data"]').hidden`),'Formula pinning and R tabs work after transition');

  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await open('index.html');
  const reducedPoint=await point('.term-card:not([hidden]) h2');await click(reducedPoint.x,reducedPoint.y);
  await landed('/terms/'+home.id+'.html');
  assert.ok(await evaluate(`window.__expansionFrames.every(f=>!f.panel) && getComputedStyle(document.querySelector('h1')).visibility==='visible'`),'Reduced motion uses native navigation');
  await send('Emulation.setEmulatedMedia',{features:[]});
  assert.equal(errors.length,0,'No runtime exceptions: '+errors.join(','));
  await writeFile(`logs/card-expansion-${width}.json`,JSON.stringify({passed:true,width,results},null,2));
  console.log(JSON.stringify({passed:true,width,results}));
} finally {ws.close();}
