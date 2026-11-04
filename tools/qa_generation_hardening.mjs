// Isolated local browser only: real rendering/import/navigation, no model or server mutations.
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage} from './native-cdp.mjs';
const out='.superpowers/sdd/2026-10-26-generation-hardening';
await mkdir(out,{recursive:true});
for(const width of [1440,390]){
 const b=await isolatedPage(9325,width),errors=[];const deadline=setTimeout(()=>{console.error('Browser QA timed out');process.exit(2);},90000);
 b.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails?.text));
 try{
  await b.page.send('Page.navigate',{url:'http://127.0.0.1:8783/psy-stats/library/index.html#view=list'});
  await b.until(`!!document.querySelector('.library-import input[type=file]')`);
  await b.until(`!!document.querySelector('.library-grid')`);
  assert.equal(await b.run(`[...document.querySelectorAll('nav[aria-label="主导航"] a')].filter(a=>a.textContent==='我的知识库').length`),1);
  assert.equal(await b.run(`document.querySelectorAll('script[data-library-module]').length`),1);
  const {root}=await b.page.send('DOM.getDocument',{depth:0});
  const {nodeId}=await b.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'.library-import input[type=file]'});
  await b.page.send('DOM.setFileInputFiles',{nodeId,files:[resolve(out,'sjt-revision-v1/lesson.zip')]});
  await b.until(`!!document.querySelector('dialog[open]')`);
  await b.run(`[...document.querySelectorAll('dialog[open] button')].find(n=>n.textContent==='导入并保存').click()`);
  await b.until(`!document.querySelector('dialog[open]')`);
  await b.until(`!!document.querySelector('.library-card')`);
  await b.run(`document.querySelector('.library-card').click()`);
  await b.until(`!!document.querySelector('.personal-reader figure img')&&!!document.querySelector('.reading-toc nav')`);
  const initial=await b.run(`JSON.stringify({en:document.querySelector('.personal-english').textContent,ids:[...document.querySelectorAll('.reading-toc a')].map(a=>a.dataset.section),overflow:document.documentElement.scrollWidth>innerWidth,asideOverflow:getComputedStyle(document.querySelector('.library-aside')).overflowY,figure:document.querySelector('.personal-reader figure').id})`);
  const result=JSON.parse(initial);assert.match(result.en,/situational/i);assert.ok(result.ids.includes('visual')&&result.ids.includes('quiz')&&result.ids.includes('sources'));assert.equal(result.overflow,false);assert.equal(result.asideOverflow,'visible');
  await b.run(`document.querySelector('.quiz-option[data-option=a]').click();window.__originalReader=document.querySelector('.personal-reader');`);
  await b.run(`document.querySelector('.reading-toc a[data-section=visual]').click()`);
  assert.equal(await b.run(`window.__originalReader===document.querySelector('.personal-reader')`),true);
  assert.equal(await b.run(`document.querySelector('.quiz-option[data-option=a]').getAttribute('aria-pressed')`),'true');
  if(width<1000)await b.run(`document.querySelector('.reading-toc').open=true`);
  await b.run(`document.querySelector('.personal-reader').scrollIntoView({block:'start'})`);
  const screenshot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(`${out}/reader-${width}.png`,Buffer.from(screenshot.data,'base64'));
  assert.deepEqual(errors,[]);await writeFile(`${out}/browser-${width}.json`,JSON.stringify({...result,width,errors,readerPreserved:true,quizPreserved:true,modelCalls:0},null,2));console.log(JSON.stringify({width,status:'passed',...result}));
 }catch(error){console.error('BROWSER_STATE',await b.run(`JSON.stringify({status:document.querySelector('.library-status')?.textContent,dialog:document.querySelector('dialog')?.textContent,errors:[...document.querySelectorAll('[role=alert]')].map(n=>n.textContent)})`));throw error;}
 finally{clearTimeout(deadline);await b.close();}
}
