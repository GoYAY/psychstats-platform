// Isolated headless browser for local UI checks; never uses the user's profile.
import {spawn} from 'node:child_process';
import {resolve} from 'node:path';
const [port='9273',action='start']=process.argv.slice(2);
if(!/^\d{4,5}$/.test(port)) throw Error('Expected a local debugging port');
if(action==='close'){
 const version=await(await fetch(`http://127.0.0.1:${port}/json/version`)).json();
 const ws=new WebSocket(version.webSocketDebuggerUrl);
 await new Promise(r=>ws.onopen=r);
 ws.send(JSON.stringify({id:1,method:'Browser.close'}));
 await new Promise(r=>ws.onclose=r);
 console.log('Isolated QA browser closed');
}else{
 spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ['--headless=new','--disable-gpu',`--remote-debugging-port=${port}`,
   `--user-data-dir=${resolve('logs',`edge-qa-${port}`)}`,'--no-first-run','about:blank'],
  {detached:true,stdio:'ignore',windowsHide:true}).unref();
 for(let attempt=0;attempt<30;attempt++){
  try{const r=await fetch(`http://127.0.0.1:${port}/json/version`);if(r.ok){console.log('Isolated QA browser ready');break}}catch{}
  if(attempt===29)throw Error('Headless browser did not become ready');
  await new Promise(r=>setTimeout(r,200));
 }
}
