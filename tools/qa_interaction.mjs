// Read-only visual and interaction probe for the generated static pages.
import { writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const port = Number(process.argv[2] || 9230);
const root = process.argv[3];
const output = process.argv[4];
const width = Number(process.argv[5] || 1280);
if (!root) throw new Error('usage: node qa_interaction.mjs <port> <dist-directory> [screenshot-path]');

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const target = targets.find(item => item.type === 'page' && item.url === 'about:blank') || targets.find(item => item.type === 'page');
if (!target) throw new Error('no browser page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let nextId = 0;
const pending = new Map();
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') console.error('page-error', message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
  if (!message.id || !pending.has(message.id)) return;
  const handlers = pending.get(message.id);
  pending.delete(message.id);
  message.error ? handlers.reject(message.error) : handlers.resolve(message.result);
};
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
async function open(file) {
  const [pathname, query] = file.split('?');
  const url = pathToFileURL(`${root}/${pathname}`);
  if (query) url.search = query;
  await send('Page.navigate', { url: url.href });
  for (let attempt = 0; attempt < 30; attempt++) {
    if (await evaluate("document.readyState === 'complete' && !!window.PsychSiteData && !!window.PsychFilterMenu")) return;
    await new Promise(resolve => setTimeout(resolve, 150));
  }
  throw new Error(`page scripts did not initialize: ${file}`);
}
await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width <= 600 });
await open('index.html');
const initial = await evaluate(`JSON.stringify({
  page: getComputedStyle(document.body).backgroundColor,
  cursor: !!document.querySelector('.cursor-dot'),
  controls: document.querySelectorAll('.filter-trigger').length,
  ready: document.readyState,
  data: !!window.PsychSiteData,
  search: !!window.PsychSearch,
  filterMenu: !!window.PsychFilterMenu,
  cards: document.querySelectorAll('.term-card').length,
  card: getComputedStyle(document.querySelector('.term-card')).boxShadow
})`);
const menu = await evaluate(`(() => {
  const trigger = document.querySelector('.filter-trigger');
  trigger.click();
  const popup = trigger.nextElementSibling;
  return JSON.stringify({open:!popup.hidden, below:popup.getBoundingClientRect().top > trigger.getBoundingClientRect().bottom,
    options:popup.querySelectorAll('[role=option]').length});
})()`);
const keyboard = await evaluate(`(() => {
  const trigger = document.querySelector('.filter-trigger');
  trigger.focus();
  trigger.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown',bubbles:true,cancelable:true}));
  return JSON.stringify({focusedRole:document.activeElement.getAttribute('role'),
    focusedText:document.activeElement.textContent});
})()`);
const chosen = await evaluate(`(() => {
  const option = document.querySelector('.filter-options [role=option]:nth-child(2)');
  option.click();
  document.querySelector('[data-theme-choice=violet]').click();
  return JSON.stringify({filter:document.querySelector('#topic-filter').value,
    theme:document.documentElement.dataset.theme,
    stored:localStorage.getItem('psych-theme'),
    button:document.querySelector('[data-theme-choice=violet]').getAttribute('aria-pressed')});
})()`);
const lastMenu = await evaluate(`(() => {
  const trigger = [...document.querySelectorAll('.filter-trigger')].at(-1);
  trigger.click();
  const popup = trigger.nextElementSibling;
  const report = {viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
    below:popup.getBoundingClientRect().top > trigger.getBoundingClientRect().bottom,
    right:popup.getBoundingClientRect().right};
  trigger.click();
  return JSON.stringify(report);
})()`);
const cardRect = JSON.parse(await evaluate(`JSON.stringify((() => {
  const r = document.querySelector('.term-card:not([hidden])').getBoundingClientRect();
  return {x:r.x + r.width/2,y:r.y + r.height/2};
})())`));
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: cardRect.x, y: cardRect.y });
await new Promise(resolve => setTimeout(resolve, 250));
const hovered = await evaluate(`JSON.stringify({shadow:getComputedStyle(document.querySelector('.term-card:not([hidden])')).boxShadow,
  transform:getComputedStyle(document.querySelector('.term-card:not([hidden])')).transform,
  dotHidden:document.querySelector('.cursor-dot')?.hidden ?? null})`);
if (output) {
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(output, Buffer.from(shot.data, 'base64'));
}
await open('terms/anova.html');
const detail = await evaluate(`JSON.stringify({theme:document.documentElement.dataset.theme,
  englishColor:getComputedStyle(document.querySelector('.term-content > header p')).color,
  page:getComputedStyle(document.body).backgroundColor})`);
await open('practice.html?theme=violet');
await evaluate(`(() => {
  const link = document.createElement('a');
  link.href = 'terms/anova.html';
  link.textContent = '测试站内链接';
  document.body.appendChild(link);
  link.click();
})()`);
await new Promise(resolve => setTimeout(resolve, 500));
const dynamicLink = await evaluate(`JSON.stringify({url:location.href,theme:document.documentElement.dataset.theme})`);
console.log(JSON.stringify({initial:JSON.parse(initial),menu:JSON.parse(menu),keyboard:JSON.parse(keyboard),chosen:JSON.parse(chosen),lastMenu:JSON.parse(lastMenu),hovered:JSON.parse(hovered),detail:JSON.parse(detail),dynamicLink:JSON.parse(dynamicLink)}));
socket.close();
