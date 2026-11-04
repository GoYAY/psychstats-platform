import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';

const port = Number(process.argv[2] || 9264);
const root = process.argv[3];
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0;
const pending = new Map();
ws.onmessage = event => {
  const message = JSON.parse(event.data);
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
  const result = await send('Runtime.evaluate', {expression, returnByValue: true});
  assert.ok(!result.exceptionDetails, 'Browser evaluation must succeed');
  return result.result.value;
};

try {
  await send('Page.enable');
  for (const width of [1440, 1280, 390]) {
    await send('Emulation.setDeviceMetricsOverride', {width, height: 900, deviceScaleFactor: 1, mobile: width < 600});
    for (const page of ['index.html', 'terms/sem.html', 'practice.html']) {
      const url = pathToFileURL(`${root}/${page}`).href;
      await send('Page.navigate', {url});
      let ready = false;
      for (let attempt = 0; attempt < 50; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 60));
        ready = await evaluate(`location.href === ${JSON.stringify(url)} && document.readyState === 'complete'`);
        if (ready) break;
      }
      assert.ok(ready, `Page loaded: ${page}`);
      const state = await evaluate(`(() => {
        const brand = document.querySelector('.brand');
        const rect = brand.getBoundingClientRect();
        return {
          brand: brand.textContent,
          title: document.title,
          heading: document.querySelector('h1').textContent,
          draft: !!document.querySelector('.draft-badge, .preview-note'),
          overflow: document.documentElement.scrollWidth > innerWidth + 1,
          brandVisible: rect.left >= 0 && rect.right <= innerWidth
        };
      })()`);
      assert.equal(state.brand, '心理统计学术语图鉴');
      assert.ok(state.title.includes('心理统计学术语图鉴'));
      if (page === 'index.html') assert.equal(state.heading, '心理统计学术语图鉴');
      assert.equal(state.draft, false);
      assert.equal(state.overflow, false, `${width}px ${page}: no horizontal overflow`);
      assert.equal(state.brandVisible, true);
      console.log(`${width}px ${page}: identity, draft removal, and layout passed`);
    }
  }
} finally {
  ws.close();
}
