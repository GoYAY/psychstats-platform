import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const port = Number(process.argv[2]), input = process.argv[3], output = process.argv[4];
const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.onopen = resolve);
let id = 0;
const tasks = new Map();
ws.onmessage = event => {
  const result = JSON.parse(event.data), task = tasks.get(result.id);
  if (!task) return;
  tasks.delete(result.id);
  result.error ? task.reject(result.error) : task.resolve(result.result);
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  tasks.set(++id, {resolve, reject});
  ws.send(JSON.stringify({id, method, params}));
});
try {
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {width:48,height:48,deviceScaleFactor:1,mobile:false});
  await send('Emulation.setDefaultBackgroundColorOverride', {color:{r:0,g:0,b:0,a:0}});
  await send('Page.navigate', {url:pathToFileURL(input).href});
  let loaded = false;
  for (let i=0;i<40;i++) {
    await new Promise(resolve => setTimeout(resolve,50));
    const result=await send('Runtime.evaluate',{expression:'document.readyState === "complete"',returnByValue:true});
    if(result.result.value){loaded=true;break;}
  }
  if(!loaded)throw Error('SVG load timeout');
  const png=await send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:48,height:48,scale:1}});
  await writeFile(output,Buffer.from(png.data,'base64'));
  console.log('Rendered approved SVG to transparent 48px PNG for ICO export');
} finally {ws.close();}
