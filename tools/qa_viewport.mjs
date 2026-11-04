// Chrome DevTools Protocol probe for a static page at a true mobile viewport.
import { writeFile } from 'node:fs/promises';
const port = Number(process.argv[2] || 9229);
const url = process.argv[3];
const width = Number(process.argv[4] || 375);
const screenshot = process.argv[5];
const screenshotTarget = process.argv[6] || '.term-visual';
if (!url) throw new Error('usage: node qa_viewport.mjs <port> <url> [width] [screenshot] [selector]');

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const target = targets.find(item => item.type === 'page' && item.url === 'about:blank') || targets.find(item => item.type === 'page');
if (!target) throw new Error('no Edge page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let nextId = 0;
const pending = new Map();
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  message.error ? reject(message.error) : resolve(message.result);
};
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width, height: 812, deviceScaleFactor: 1, mobile: true });
await send('Page.navigate', { url });
await new Promise(resolve => setTimeout(resolve, 1400));
const result = await send('Runtime.evaluate', {
  expression: `JSON.stringify({width: innerWidth, documentWidth: document.documentElement.scrollWidth, bodyWidth: document.body.scrollWidth, questionWidth: document.querySelector('.real-question')?.getBoundingClientRect().width, searchWidth: document.querySelector('.header-search')?.getBoundingClientRect().width, diagramViewport:document.querySelector('.diagram-scroll')?.clientWidth, diagramContent:document.querySelector('.diagram-scroll')?.scrollWidth, diagramLoaded:document.querySelector('.term-visual img')?.complete})`,
  returnByValue: true,
});
console.log(result.result.value);
if (screenshot) {
  await send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(screenshotTarget)})?.scrollIntoView({block:'start', behavior:'instant'})` });
  await send('Runtime.evaluate', { expression: "window.scrollBy({top: -(document.querySelector('.site-head')?.getBoundingClientRect().height || 0) - 16, behavior:'instant'})" });
  await new Promise(resolve => setTimeout(resolve, 150));
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(screenshot, Buffer.from(shot.data, 'base64'));
}
socket.close();
