import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const [port, root] = process.argv.slice(2);
const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.onopen = resolve);
let sequence = 0;
const pending = new Map();
const errors = [];
ws.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
  const task = pending.get(message.id);
  if (task) {
    pending.delete(message.id);
    message.error ? task.reject(message.error) : task.resolve(message.result);
  }
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  pending.set(++sequence, {resolve, reject});
  ws.send(JSON.stringify({id: sequence, method, params}));
});
const run = async expression => {
  const response = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
  assert.ok(!response.exceptionDetails, response.exceptionDetails?.exception?.description);
  return response.result.value;
};
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const results = [];
try {
  await send('Page.enable');
  await send('Runtime.enable');
  for (const width of [1280, 390]) {
    await send('Emulation.setDeviceMetricsOverride', {width, height: 900, deviceScaleFactor: 1, mobile: width < 600});
    await send('Page.navigate', {url: pathToFileURL(root + '/terms/latent-variable.html').href});
    await wait(700);
    assert.ok(await run(`!document.querySelector('.term-content').innerHTML.includes('潜<a ')`));
    assert.ok(await run(`[...document.querySelectorAll('.knowledge-sidebar a')].every(a=>getComputedStyle(a).textDecorationLine==='none')`), 'Knowledge links use the same no-underline style');
    const baseline = await run(`(() => {
      const a = [...document.querySelectorAll('.term-inline-link')].find(a => a.textContent === '载荷');
      a.scrollIntoView({block:'center',behavior:'instant'});
      const r = a.getBoundingClientRect(), s = getComputedStyle(a);
      window.qaLink = a;
      return {x:r.x,y:r.y,width:r.width,height:r.height,color:s.color,decoration:s.textDecorationLine,shadow:s.boxShadow,bg:s.backgroundColor,href:a.getAttribute('href')};
    })()`);
    assert.equal(baseline.href, 'factor-loading.html');
    assert.equal(baseline.decoration, 'none');
    assert.equal(baseline.shadow, 'none');
    await send('Input.dispatchMouseEvent', {type:'mouseMoved', x:baseline.x+baseline.width/2, y:baseline.y+baseline.height/2});
    await wait(220);
    const hover = await run(`(() => {const s=getComputedStyle(qaLink),r=qaLink.getBoundingClientRect();return {shadow:s.boxShadow,bg:s.backgroundColor,decoration:s.textDecorationLine,x:r.x,y:r.y,width:r.width,height:r.height}})()`);
    assert.notEqual(hover.shadow, 'none');
    assert.notEqual(hover.bg, 'rgba(0, 0, 0, 0)');
    assert.equal(hover.decoration, 'none');
    for (const key of ['x','y','width','height']) assert.equal(hover[key], baseline[key], 'Hover does not shift text');
    await send('Input.dispatchMouseEvent', {type:'mouseMoved',x:1,y:899});
    await send('Input.dispatchKeyEvent', {type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    await run('qaLink.focus()');
    await wait(220);
    assert.ok(await run(`qaLink.matches(':focus-visible')&&getComputedStyle(qaLink).boxShadow!=='none'&&getComputedStyle(qaLink).outlineStyle!=='none'`));
    if (width === 1280) {
      const shot = await send('Page.captureScreenshot', {format:'png'});
      await writeFile('logs/term-links-latent-hover.png', Buffer.from(shot.data, 'base64'));
    }
    if (width === 390) {
      await send('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[{x:baseline.x+baseline.width/2,y:baseline.y+baseline.height/2}]});
      await send('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
    } else {
      await send('Input.dispatchKeyEvent', {type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
      await send('Input.dispatchKeyEvent', {type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    }
    await wait(700);
    assert.ok(await run(`location.pathname.endsWith('/factor-loading.html')`));
    assert.ok(await run(`document.documentElement.scrollWidth<=innerWidth`));
    results.push({width, baseline, hover, navigation: width === 390 ? 'touch' : 'keyboard'});
  }
  assert.deepEqual(errors, []);
  await writeFile('logs/term-links-browser.json', JSON.stringify(results, null, 2));
  console.log(JSON.stringify({passed:true, widths:[1280,390], checks:['full-term','alias','hover','focus','stable-layout','keyboard-navigation','touch-navigation']}));
} finally {
  ws.close();
}
