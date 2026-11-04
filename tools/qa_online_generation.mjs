// Real loopback HTTPS API and browser; only supplier transport is substituted.
import assert from 'node:assert/strict';import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {isolatedPage,wait,args} from './native-cdp.mjs';
const options=args(),width=Number(options.width||1440),b=await isolatedPage(9296,width),meta=JSON.parse(await readFile(options.meta||'.superpowers/sdd/2026-10-22-online-generation-beta-implementation/https-qa/active.json','utf8')),errors=[],output=options.output||'logs/online-generation';
b.page.events.set('Runtime.exceptionThrown',event=>errors.push(event.exceptionDetails?.text||'browser-exception'));
const click=label=>b.run(`(()=>{const n=[...document.querySelectorAll('button')].find(n=>n.textContent===${JSON.stringify(label)});if(!n)throw Error('Missing action: '+${JSON.stringify(label)});n.click();})()`);
const paper='Intro\n总体是研究希望了解的目标对象集合。样本是实际获得观测的对象。\nApplication\n研究设计中说明研究对象和实际招募范围。';
async function until(expression,seconds=30){const deadline=Date.now()+seconds*1000;while(Date.now()<deadline){if(await b.run(expression))return;await wait(80);}throw Error('Timeout: '+expression+'; '+await b.run(`document.querySelector('.generation-notice')?.textContent`));}
try{
 await b.page.send('Security.enable');await b.page.send('Security.setIgnoreCertificateErrors',{ignore:true});
 await b.page.send('Page.navigate',{url:meta.origin+'/psy-stats/library/index.html#view=generate'});
 await until(`!!document.querySelector('.generation-login input[type=password]')`);
 await b.run(`(()=>{const f=document.querySelector('.generation-login');f.querySelector('input').value=${JSON.stringify(meta.invitation)};f.requestSubmit();})()`);
 await until(`!!document.querySelector('.generation-form input[type=file]')`);
 await mkdir(output,{recursive:true});
 const initialShot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(output+'/form-'+width+'.png',Buffer.from(initialShot.data,'base64'));
 assert.ok(await b.run(`document.documentElement.scrollWidth<=innerWidth+1`),'No horizontal overflow at '+width);
 await b.run(`(()=>{const f=document.querySelector('.generation-form');f.querySelector('input:not([type])').value='总体与样本';f.querySelector('textarea').value='想研究的人与实际调查到的人。';const input=f.querySelector('input[type=file]'),data=new DataTransfer();data.items.add(new File([${JSON.stringify(paper)}],'sample.txt',{type:'text/plain'}));input.files=data.files;input.dispatchEvent(new Event('change',{bubbles:true}));const checks=[...f.querySelectorAll('input[type=checkbox]')];checks.at(-1).checked=true;f.requestSubmit();})()`);
 await until(`document.querySelector('.generation-detail h3')?.textContent==='已生成，可领取'`,45);
 await click('查看生成的科普');await until(`!!document.querySelector('.generation-preview .personal-reader h1')`);
 assert.equal(await b.run(`document.querySelector('.generation-preview .personal-reader h1').textContent`),'总体与样本');
 const previewShot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(output+'/preview-'+width+'.png',Buffer.from(previewShot.data,'base64'));
 await click('核对并保存到我的知识库');await until(`!!document.querySelector('dialog[open]')`);
 await click('导入并保存');await until(`!document.querySelector('dialog[open]')`);
 await b.run(`location.hash='view=list'`);await until(`!!document.querySelector('.library-card')`);
 assert.equal(await b.run(`document.querySelector('.library-card h2').textContent`),'总体与样本');
 await b.run(`document.querySelector('.library-card').click()`);await until(`!!document.querySelector('.personal-reader')`);
 assert.equal(await b.run(`document.querySelector('.personal-reader h1').textContent`),'总体与样本');
 const roundtrip=await b.run(`(async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{libraryContext}=await import('/psy-stats/assets/library/app.mjs'),{exportBackup,inspectBackup,planRestore}=await import('/psy-stats/assets/library/archive.mjs');const store=await openLibrary(await libraryContext(new URL('/psy-stats/',location.origin),'local-library-preview'));try{const snapshot=await store.snapshot(),blobs=new Map(),blob=await exportBackup(snapshot,h=>store.getBlob(h));const inspected=await inspectBackup(blob,{stageBlob:async(h,b)=>{blobs.set(h,b);return h;},discardStaged:async()=>blobs.clear()});const restored=await planRestore(snapshot,inspected.validated);return {readings:inspected.validated.revisions[0].provenance.document_readings.length,termCount:inspected.validated.terms.length,newTermIds:restored.writes.filter(w=>w.kind==='terms'&&!snapshot.records.terms.some(t=>t.id===w.id)).length};}finally{store.close();}})()`);
 assert.equal(roundtrip.readings,1);assert.equal(roundtrip.termCount,1);assert.equal(roundtrip.newTermIds,0);
 await b.run(`location.hash='view=generate'`);await until(`!!document.querySelector('.generation-form details input[type=checkbox]')`);
 await b.run(`document.querySelector('.generation-form details input[type=checkbox]').click()`);
 await until(`document.querySelector('.generation-file-summary').textContent.includes('source-')||document.querySelector('.generation-file-summary').textContent.includes('sample')`);
 const localName=await b.run(`document.querySelector('.generation-file-summary').textContent`);
 await b.run(`(()=>{const i=document.querySelector('.generation-form input[type=file]'),d=new DataTransfer();d.items.add(new File(['# Intro\\nAnother source.'],'second.txt',{type:'text/plain'}));i.files=d.files;i.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 assert.ok(await b.run(`document.querySelector('.generation-file-summary').textContent.includes(${JSON.stringify(localName)}) && document.querySelector('.generation-file-summary').textContent.includes('second.txt')`),'Selecting disk files must retain checked archived papers');
 // A no-literature task must pause, then accept a real upload into that same job.
 await b.run(`location.hash='view=list'`);await until(`!!document.querySelector('.library-card')`);
 await b.run(`location.hash='view=generate'`);await until(`!!document.querySelector('.generation-form')`);
 await b.run(`(()=>{const f=document.querySelector('.generation-form');f.querySelector('input:not([type])').value='总体与样本';f.querySelector('textarea').value='想研究的人与实际调查到的人。';[...f.querySelectorAll('input[type=checkbox]')].at(-1).checked=true;f.requestSubmit();})()`);
 await until(`document.querySelector('.generation-detail h3')?.textContent==='需要你确认'`);
 const pausedId=await b.run(`document.querySelector('.generation-detail small').textContent`);
 await click('暂不联网，保留待补资料');await until(`!!document.querySelector('.generation-detail input[type=file]') && !document.querySelector('.generation-page').inert`);
 await b.run(`(()=>{const i=document.querySelector('.generation-detail input[type=file]'),d=new DataTransfer();d.items.add(new File([${JSON.stringify(paper)}],'supplement.txt',{type:'text/plain'}));i.files=d.files;})()`);
 await click('补充所选文献并继续');await until(`document.querySelector('.generation-detail h3')?.textContent==='已生成，可领取'`,45);
 assert.equal(await b.run(`document.querySelector('.generation-detail small').textContent`),pausedId,'Material supplementation resumes the same task');
 // Simulate a dropped start response before send, reload the form, resume draft.
 await b.run(`location.hash='view=list'`);await until(`!!document.querySelector('.library-card')`);
 await b.run(`(()=>{const original=window.fetch;let interrupted=false;window.fetch=async(...a)=>{if(!interrupted&&String(a[0]).endsWith('/start')){interrupted=true;window.fetch=original;return new Response(JSON.stringify({error:{code:'offline_test',message:'Offline fixture start interruption'}}),{status:503,headers:{'Content-Type':'application/json'}});}return original(...a);};})()`);
 await b.run(`location.hash='view=generate'`);await until(`!!document.querySelector('.generation-form')`);
 await b.run(`(()=>{const f=document.querySelector('.generation-form');f.querySelector('input:not([type])').value='总体与样本';f.querySelector('textarea').value='想研究的人与实际调查到的人。';const i=f.querySelector('input[type=file]'),d=new DataTransfer();d.items.add(new File([${JSON.stringify(paper)}],'resume.txt',{type:'text/plain'}));i.files=d.files;i.dispatchEvent(new Event('change',{bubbles:true}));[...f.querySelectorAll('input[type=checkbox]')].at(-1).checked=true;f.requestSubmit();})()`);
 await until(`document.querySelector('.generation-notice').textContent.includes('start interruption')`);
 await b.run(`location.hash='view=list'`);await until(`!!document.querySelector('.library-card')`);
 await b.run(`location.hash='view=generate'`);await until(`[...document.querySelectorAll('.generation-page button')].some(n=>n.textContent.includes('待提交资料'))`);
 await b.run(`[...document.querySelectorAll('.generation-page button')].find(n=>n.textContent.includes('待提交资料')).click()`);
 await until(`!![...document.querySelectorAll('button')].find(n=>n.textContent==='继续上传并启动')`);
 await click('继续上传并启动');await until(`document.querySelector('.generation-detail h3')?.textContent==='已生成，可领取'`,45);
 const rows=JSON.parse(await readFile(meta.run+'/events.json','utf8'));assert.ok(rows.length>=3);assert.equal(errors.length,0,JSON.stringify(errors));
 const result={width,status:'passed',https:true,realAPI:true,supplier:'offline-double',supplierStages:rows.length,preview:true,localSave:true,readBack:true,materialResume:true,draftResume:true,mixedFileSelection:true,backupRoundtrip:true,externalCalls:0};
 await mkdir(output,{recursive:true});await writeFile(output+'/browser-'+width+'.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await b.close();}
