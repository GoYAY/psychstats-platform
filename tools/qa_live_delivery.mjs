// Inspect a real generated ZIP in an isolated browser. No model calls.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {isolatedPage,args,wait} from './native-cdp.mjs';
const o=args(),width=Number(o.width||1440),b=await isolatedPage(9296,width),output=o.output||'logs/online-generation';
assert.ok(o.zip&&o.expected,'Provide --zip and --expected');
const errors=[];b.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails?.text));
try{
 await b.page.send('Security.enable');await b.page.send('Security.setIgnoreCertificateErrors',{ignore:true});
 await b.page.send('Page.navigate',{url:new URL('library/index.html#view=list',o.url||'https://127.0.0.1:8874/psy-stats/').href});
 await b.until(`document.querySelector('[data-library-status]')?.textContent.includes('请定期导出完整备份')`);
 const {root}=await b.page.send('DOM.getDocument');
 const {nodeId}=await b.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
 await b.page.send('DOM.setFileInputFiles',{nodeId,files:[path.resolve(o.zip)]});
 await b.until(`!!document.querySelector('dialog[open]')`);
 await b.run(`[...document.querySelectorAll('dialog button')].find(n=>n.textContent==='导入并保存').click()`);
 await b.until(`!document.querySelector('dialog[open]')&&!!document.querySelector('.library-card')`);
 await b.run(`document.querySelector('.library-card').click()`);await b.until(`!!document.querySelector('.personal-reader img')`);
 assert.equal(await b.run(`document.querySelector('.personal-reader h1').textContent`),o.expected);
 assert.ok(await b.run(`document.documentElement.scrollWidth<=innerWidth+1`));
 const body=await b.run(`document.querySelector('.personal-reader').innerText`);assert.ok(body.includes('来源与核对'));
 const quizzes=await b.run(`document.querySelectorAll('.quiz-option').length`);assert.equal(quizzes,4);
 for(let i=0;i<4;i++){
  await b.run(`document.querySelectorAll('.quiz-option')[${i}].click()`);
  assert.ok((await b.run(`document.querySelector('#quiz-feedback').textContent`)).length>10);
 }
 const notes=await b.run(`document.querySelectorAll('.term-help').length`);
 if(notes){await b.run(`document.querySelector('.term-help').click()`);await b.until(`!document.querySelector('.term-popover').hidden`);await b.run(`document.querySelector('.term-help').click()`);}
 const roundtrip=await b.run(`(async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{libraryContext}=await import('/psy-stats/assets/library/app.mjs'),{exportBackup,inspectBackup,planRestore}=await import('/psy-stats/assets/library/archive.mjs');const s=await openLibrary(await libraryContext(new URL('/psy-stats/',location.origin),'local-library-preview'));try{const snapshot=await s.snapshot(),blob=await exportBackup(snapshot,h=>s.getBlob(h)),staged=new Map(),v=await inspectBackup(blob,{stageBlob:async(h,b)=>{staged.set(h,b);return h;},discardStaged:async()=>staged.clear()}),plan=await planRestore(snapshot,v.validated);return {terms:v.validated.terms.length,sources:v.validated.sources.length,readings:v.validated.revisions[0].provenance.document_readings?.length,newTerms:plan.writes.filter(w=>w.kind==='terms'&&!snapshot.records.terms.some(t=>t.id===w.id)).length};}finally{s.close();}})()`);
 assert.equal(roundtrip.terms,1);assert.equal(roundtrip.newTerms,0);
 await mkdir(output,{recursive:true});
 await b.run(`document.querySelector('.personal-reader figure').scrollIntoView({block:'center'})`);await wait(100);
 const shot=await b.page.send('Page.captureScreenshot',{format:'png'}),tag=path.basename(path.dirname(o.zip))+'-'+width;
 await writeFile(output+'/live-'+tag+'.png',Buffer.from(shot.data,'base64'));
 assert.equal(errors.length,0,JSON.stringify(errors));
 const report={status:'passed',width,term:o.expected,quizOptions:quizzes,glossaryTriggers:notes,roundtrip,externalCalls:0};
 await writeFile(output+'/live-'+tag+'.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}catch(error){
 console.error(JSON.stringify({diagnostic:await b.run(`({text:document.querySelector('main')?.innerText.slice(-1600),status:document.querySelector('[data-library-status]')?.textContent,files:document.querySelector('[data-library-import]')?.files?.length})`),exceptions:errors}));throw error;
}finally{await b.close();}
