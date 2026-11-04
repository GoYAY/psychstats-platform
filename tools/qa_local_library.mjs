import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {dirname,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {isolatedPage,args,connect} from './native-cdp.mjs';
const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const options=args(),scenario=options.scenario||'assets',url=options.url||'http://127.0.0.1:8773/psy-stats/qa/library-host.html',port=Number(options.cdp||9296);
const log=resolve(ROOT,'logs/local-library');await mkdir(log,{recursive:true});

function privatePackage(name){
 const script=`import json,zipfile,base64,hashlib,sys\nwith zipfile.ZipFile(sys.argv[1]) as z:\n m=json.loads(z.read('manifest.json'))\n for f in m['files']:\n  b=z.read(f['path']);assert len(b)==f['size'] and hashlib.sha256(b).hexdigest()==f['hash']\n print(json.dumps({'package':json.loads(z.read('library.json')),'files':m['files'],'svg':[{'path':f['path'],'mime':f['mime'],'bytes':base64.b64encode(z.read(f['path'])).decode()} for f in m['files'] if f['mime']=='image/svg+xml']}))`;
 return JSON.parse(execFileSync(resolve(ROOT,'.venv/Scripts/python.exe'),['-X','utf8','-c',script,resolve(log,'private-fixtures',name+'.zip')],{encoding:'utf8',maxBuffer:16*1024*1024}));
}

async function assets(browser){
 await browser.run(`(async()=>{globalThis.qaSafe=await import('/psy-stats/assets/library/safe-assets.mjs');globalThis.qaContract=await import('/psy-stats/assets/library/contract.mjs');return true;})()`);
 const rows=[];
 for(const name of ['dtp','cognitive-drift','human-ai-entanglement']){
  const bundle=privatePackage(name);
  const result=await browser.run(`(async()=>{const b=${JSON.stringify(bundle)};const files=new Map(b.files.map(f=>[f.path,f]));for(const f of b.svg){const bytes=Uint8Array.from(atob(f.bytes),c=>c.charCodeAt(0));const actual=await qaSafe.safeAsset(bytes,{mime:f.mime,path:f.path});if(actual.hash!==files.get(f.path).hash)throw Error('Byte hash differs');}const p=qaContract.validatePackage(b.package,files,{catalogue:[]});return {case:${JSON.stringify(name)},terms:p.terms.length,sources:p.sources.length,assets:p.assets.length};})()`);
  assert.equal(result.terms,1);rows.push(result);
 }
 const malicious=[
  '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
  '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.com/a.svg#x"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg"><style>text{fill:url(https://example.com/a)}</style></svg>',
  '<?xml-stylesheet type="text/css" href="https://example.com/private.css"?><svg xmlns="http://www.w3.org/2000/svg"/>'
 ];
 for(let i=0;i<malicious.length;i++){
  const rejected=await browser.run(`(async()=>{try{await qaSafe.safeAsset(new TextEncoder().encode(${JSON.stringify(malicious[i])}),{mime:'image/svg+xml',path:'assets/unsafe.svg'});return false;}catch(e){return e.code==='UNSAFE_ASSET';}})()`);
  assert.equal(rejected,true,'SVG rejected at malicious input '+i);
 }
 return {scenario:'assets',privateCases:rows,rejectedSVG:malicious.length};
}

async function store(browser){
 return browser.run(`(async()=>{
  const {openLibrary,databaseName}=await import('/psy-stats/assets/library/store.mjs');
  const context={environment:'qa-store-'+Date.now(),libraryId:'one',owner:null};
  const one=await openLibrary(context),two=await openLibrary(context);const before=await one.snapshot();
  if(before.version!==0||before.records.terms.length)throw Error('New library not empty');
  const plan=id=>({writes:[{kind:'terms',id,value:{id,zh:'测试术语',en:'Test',aliases:[],tags:[],anchor:{},currentRevisionId:null,trashed:false}}],deletes:[],blobRefs:[],impact:[]});
  const results=await Promise.allSettled([one.commit(plan('first'),{expectedVersion:0}),two.commit(plan('second'),{expectedVersion:0})]);
  if(results.filter(r=>r.status==='fulfilled').length!==1||results.find(r=>r.status==='rejected').reason.code!=='CONFLICT')throw Error('Stale save overwritten newer version');
  const saved=await one.snapshot();if(saved.version!==1||saved.records.terms.length!==1)throw Error('Conflict changed contents');
  const abort=new AbortController();abort.abort();let cancelled=false;try{await one.commit(plan('cancelled'),{expectedVersion:1,signal:abort.signal});}catch(e){cancelled=e.code==='CANCELLED';}if(!cancelled)throw Error('Abort ignored');
  one.close();two.close();const reopened=await openLibrary(context);if((await reopened.snapshot()).records.terms.length!==1)throw Error('Reopen lost data');
  const isolated=await openLibrary({...context,environment:context.environment+'-other'});if((await isolated.snapshot()).records.terms.length)throw Error('Environment leaked');isolated.close();
  const blob=new Blob(['abc']),hash='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';await reopened.stageBlob(hash,blob,{});
  let hidden=false;try{await reopened.getBlob(hash);}catch(e){hidden=e.code==='MISSING_ORIGINAL';}if(!hidden)throw Error('Uncommitted blob visible');
  await reopened.commit({writes:[{kind:'assets',id:'asset',value:{id:'asset',blobHash:hash}}],deletes:[],blobRefs:[hash],impact:[]},{expectedVersion:1});
  if(await (await reopened.getBlob(hash)).text()!=='abc')throw Error('Saved bytes changed');
  let failWrite=false,abortWrite=false;const factory={open(...args){const request=indexedDB.open(...args);request.addEventListener('success',()=>{const db=request.result,transaction=db.transaction.bind(db);db.transaction=(names,mode,...rest)=>{if(failWrite&&mode==='readwrite')throw new DOMException('Full','QuotaExceededError');const tx=transaction(names,mode,...rest);if(abortWrite&&mode==='readwrite'){const original=tx.objectStore.bind(tx);tx.objectStore=name=>{const store=original(name);if(name==='records'){const put=store.put.bind(store);store.put=(...values)=>{const r=put(...values);r.addEventListener('success',()=>tx.abort(),{once:true});return r;};}return store;};}return tx;};});return request;}};
  const faulty=await openLibrary(context,{factory});failWrite=true;let full=false;try{await faulty.commit(plan('full'),{expectedVersion:2});}catch(e){full=e.code==='QUOTA';}failWrite=false;if(!full||(await reopened.snapshot()).version!==2)throw Error('Quota was reported as successful save');
  abortWrite=true;let rolledBack=false;try{await faulty.commit(plan('abort-mid-write'),{expectedVersion:2});}catch(e){rolledBack=e.code==='CANCELLED';}abortWrite=false;if(!rolledBack||(await reopened.snapshot()).records.terms.length!==1)throw Error('Aborted transaction published a partial write');faulty.close();
  const blockedContext={...context,environment:context.environment+'-blocked'},raw=await new Promise((resolve,reject)=>{const r=indexedDB.open(databaseName(blockedContext.environment),1);r.onsuccess=()=>resolve(r.result);r.onerror=reject;});raw.onversionchange=()=>{};
  let blocked=false;try{await openLibrary(blockedContext,{factory:{open:(name,version)=>indexedDB.open(name,version+1)}});}catch(e){blocked=e.code==='BLOCKED';}finally{raw.close();}if(!blocked)throw Error('Blocked upgrade not reported');
  reopened.close();sessionStorage.setItem('qaStoreContext',JSON.stringify(context));return {scenario:'store',version:2,concurrentOneWinner:true,cancelled:true,reopen:true,isolated:true,quota:true,midTransactionRollback:true,upgradeBlocked:true,stagingHidden:true};
 })()`);
}

async function backup(browser){
 await browser.run(`(async()=>{globalThis.qaArchive=await import('/psy-stats/assets/library/archive.mjs');const s=await import('/psy-stats/assets/library/store.mjs');globalThis.backupContext={environment:'qa-backup-'+Date.now(),libraryId:'main',owner:null};globalThis.backupStore=await s.openLibrary(backupContext);return true;})()`);
 for(const name of ['dtp','cognitive-drift','human-ai-entanglement']){
  const base64=(await readFile(resolve(log,'private-fixtures',name+'.zip'))).toString('base64');
  await browser.run(`(async()=>{const bytes=Uint8Array.from(atob(${JSON.stringify(base64)}),c=>c.charCodeAt(0));const inspected=await qaArchive.inspectBackup(new Blob([bytes]),{stageBlob:backupStore.stageBlob,discardStaged:backupStore.discardStaged});const before=await backupStore.snapshot(),plan=await qaArchive.planRestore(before,inspected.validated);await backupStore.commit(plan,{expectedVersion:before.version});await backupStore.discardStaged();return true;})()`);
 }
 return browser.run(`(async()=>{
  const before=await backupStore.snapshot();if(before.records.terms.length!==3||before.records.works.length!==5)throw Error('Three cases were merged or duplicated');
  const originalCount=new Set(before.records.sources.map(s=>s.blobHash).filter(Boolean)).size;if(originalCount!==4)throw Error('Shared original PDF not deduplicated');
  const blob=await qaArchive.exportBackup(before,backupStore.getBlob,{});globalThis.savedBackupBlob=blob;
  const {openLibrary}=await import('/psy-stats/assets/library/store.mjs');const restored=await openLibrary({...backupContext,libraryId:'restored'});
  const inspected=await qaArchive.inspectBackup(blob,{stageBlob:restored.stageBlob,discardStaged:restored.discardStaged});const initial=await restored.snapshot();await restored.commit(await qaArchive.planRestore(initial,inspected.validated),{expectedVersion:initial.version});
  const state=await restored.snapshot();for(const kind of Object.keys(before.records))if(state.records[kind].length!==before.records[kind].length)throw Error('Roundtrip lost '+kind);
  const canonical=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
  if(canonical(before.records)!==canonical(state.records))throw Error('Roundtrip changed record contents');
  const {sha256}=await import('/psy-stats/assets/library/safe-assets.mjs');for(const hash of new Set([...state.records.sources,...state.records.assets].map(r=>r.blobHash).filter(Boolean)))if(await sha256(new Uint8Array(await(await restored.getBlob(hash)).arrayBuffer()))!==hash)throw Error('Restored byte content hash differs');
  const repeated=await qaArchive.planRestore(state,inspected.validated);if(repeated.writes.length)throw Error('Repeated import created duplicates');await restored.commit(repeated,{expectedVersion:state.version});
  const controller=new AbortController();let cancelled=false;try{await qaArchive.inspectBackup(blob,{stageBlob:restored.stageBlob,discardStaged:restored.discardStaged,signal:controller.signal,onProgress:p=>{if(p.files>=1)controller.abort();}});}catch(e){cancelled=e.code==='CANCELLED';}if(!cancelled||(await restored.snapshot()).version!==state.version)throw Error('Cancelled import changed active library');
  const exportAgain=await qaArchive.exportBackup(state,restored.getBlob,{});const checked=await qaArchive.inspectBackup(exportAgain,{stageBlob:restored.stageBlob,discardStaged:restored.discardStaged});if((await qaArchive.planRestore(state,checked.validated)).writes.length)throw Error('Second backup changed records');
  const raw=new Uint8Array(await blob.arrayBuffer()),badCRC=raw.slice(),central=raw.findIndex((v,i)=>v===0x50&&raw[i+1]===0x4b&&raw[i+2]===1&&raw[i+3]===2);new DataView(badCRC.buffer).setUint32(central+16,0,true);
  const overLimit=raw.slice();new DataView(overLimit.buffer).setUint32(central+24,134217729,true);
  const fflate=await import('/psy-stats/assets/vendor/fflate/fflate.mjs'),small={schemaVersion:1,packageId:'bad-package',terms:[],revisions:[],works:[],sources:[],evidence:[],edges:[],annotations:[],assets:[]};const encoded=fflate.strToU8(JSON.stringify(small));
  const badHash=fflate.zipSync({'library.json':encoded,'manifest.json':fflate.strToU8(JSON.stringify({schemaVersion:1,kind:'personal-library-backup',packageId:small.packageId,files:[{path:'library.json',size:encoded.length,mime:'application/json',hash:'0'.repeat(64)}]}))});
  for(const [bytes,expected] of [[badCRC,'INVALID_PACKAGE'],[overLimit,'LIMIT'],[badHash,'INVALID_PACKAGE']]){
   let rejected=false;try{await qaArchive.inspectBackup(new Blob([bytes]),{stageBlob:restored.stageBlob,discardStaged:restored.discardStaged});}catch(e){rejected=e.code===expected;}if(!rejected||(await restored.snapshot()).version!==state.version)throw Error('Corrupt/oversized import changed active data');
  }
  for(const a of state.records.assets)if((await restored.getBlob(a.blobHash)).type!==a.mime)throw Error('Restored figure MIME type lost');
  const hashesBefore=before.records.assets.map(a=>a.blobHash).sort().join(','),hashesAfter=state.records.assets.map(a=>a.blobHash).sort().join(',');if(hashesBefore!==hashesAfter)throw Error('Figures changed');
  await restored.discardStaged();restored.close();backupStore.close();return {scenario:'backup',terms:3,works:5,originalFiles:originalCount,roundtrip:true,repeatedNoOp:true,cancelPreserves:true,crcRejected:true,oversizedRejected:true,manifestHashRejected:true,assetHashesPreserved:true,bytes:blob.size};
 })()`);
}

async function markdown(browser){
 await backup(browser);
 const result=await browser.run(`(async()=>{
  const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{projectMarkdown,importMarkdown}=await import('/psy-stats/assets/library/markdown.mjs');const store=await openLibrary(backupContext),snapshot=await store.snapshot(),before=JSON.stringify(snapshot);
  const projection=await projectMarkdown(snapshot,{includeOriginals:false}),paths=new Set(projection.files.map(f=>f.path));let links=0;
  for(const file of projection.files.filter(f=>f.bytes)){
   const text=new TextDecoder().decode(file.bytes);if(text.includes('sustained, reciprocal coupling'))throw Error('Evidence quote leaked');
   for(const match of text.matchAll(/\\]\\(([^)]+)\\)/g)){if(match[1].startsWith('https:'))continue;const resolved=decodeURIComponent(new URL(match[1],'https://local.invalid/'+file.path).pathname).slice(1);if(!paths.has(resolved))throw Error('Missing relative target: '+resolved);links++;}
  }
  if(projection.files.filter(f=>f.path.startsWith('术语/')).length!==3||projection.files.some(f=>f.path.startsWith('原件/')))throw Error('Reading projection scope wrong');
  const reading=await qaArchive.exportReading(snapshot,store.getBlob,{});let readingRejected=false;try{await qaArchive.inspectBackup(reading,{stageBlob:store.stageBlob,discardStaged:store.discardStaged});}catch(e){readingRejected=e.code==='READING_EXPORT';}if(!readingRejected)throw Error('Reading archive masqueraded as complete backup');
  const original=projection.files.find(f=>f.path.startsWith('术语/')),note=await importMarkdown(new TextDecoder().decode(original.bytes)+'\\n个人补充内容',{fileName:'edited.md',baseRevisionId:null});if(note.origin!=='external-markdown'||JSON.stringify(await store.snapshot())!==before)throw Error('External Markdown replaced a lesson');
  const bytes=new Uint8Array(await reading.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));store.close();return {scenario:'markdown',terms:3,relativeLinks:links,externalNoteSeparate:true,noEvidence:true,readingNotRestore:true,obsidianAppTested:false,archiveBase64:btoa(binary)};
 })()`);
 await writeFile(resolve(log,'private-fixtures/reading-export.zip'),Buffer.from(result.archiveBase64,'base64'));delete result.archiveBase64;return result;
}

async function reader(browser){
 await backup(browser);
 await browser.run(`(async()=>{const s=await import('/psy-stats/assets/library/store.mjs');globalThis.readerStore=await s.openLibrary(backupContext);globalThis.readerState=await readerStore.snapshot();globalThis.readerModule=await import('/psy-stats/assets/library/reader.mjs');return true;})()`);
 const rows=[];
 for(const width of [1440,390,320]){
  await browser.page.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<650});
  for(const term of ['dominant-trait-profile','cognitive-drift','human-ai-entanglement']){
   const result=await browser.run(`(async()=>{const records=readerState.records,t=records.terms.find(t=>t.id===${JSON.stringify(term)}),revision=records.revisions.find(r=>r.id===t.currentRevisionId),root=document.querySelector('main');globalThis.readerController=readerModule.mountReader(root,{revision,sources:records.sources,works:records.works,resolveAsset:role=>{const a=records.assets.find(a=>revision.assetIds.includes(a.id)&&a.role===role);return a?readerStore.getBlob(a.blobHash):null;}});await readerController.ready;const options=[...root.querySelectorAll('.quiz-option')],quiz=revision.lesson.quiz;for(const b of options){b.click();if(!root.querySelector('#quiz-feedback').textContent.includes(quiz.options.find(o=>o.id===b.dataset.option).explanation))throw Error('Option feedback wrong');}if(root.querySelectorAll('#real_question [data-note],#quiz [data-note],#formulas [data-note],#academic_expression [data-note],figcaption [data-note]').length)throw Error('Nonprose help');const first=root.querySelector('[data-note]'),panel=root.querySelector('#term-popover');if(first){first.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));if(!panel.hidden)throw Error('Hover opened help');first.click();if(panel.hidden)throw Error('Click failed');document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));if(!panel.hidden)throw Error('Escape failed');first.focus();first.click();first.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));if(!panel.contains(document.activeElement))throw Error('Keyboard entry failed');readerController.dispose();first.click();if(!panel.hidden)throw Error('Disposed listener survived');}if(document.documentElement.scrollWidth>innerWidth)throw Error('Reader overflow');if(root.innerHTML.includes('source_id')||root.innerHTML.includes('span_id')||root.innerHTML.includes('rawSource'))throw Error('Evidence in DOM');return {term:${JSON.stringify(term)},width:innerWidth,options:options.length,helpers:root.querySelectorAll('[data-note]').length,sources:root.querySelectorAll('.personal-sources li').length};})()`);
   rows.push(result);
  }
  const shot=await browser.page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(resolve(log,'reader-'+width+'.png'),Buffer.from(shot.data,'base64'));
 }
 const late=await browser.run(`(async()=>{const root=document.querySelector('main'),revision=readerState.records.revisions[0],before=root.innerHTML;let release;const asset=new Promise(r=>release=r),controller=readerModule.mountReader(root,{revision,resolveAsset:()=>asset});controller.dispose();release(null);const done=await controller.ready;if(done!==false||root.innerHTML!==before)throw Error('Late async wrote disposed page');readerStore.close();return true;})()`);
 return {scenario:'reader',cases:rows,lateResourceIgnored:late,disposedListeners:true};
}

async function graph(browser){
 await backup(browser);
 return browser.run(`(async()=>{const {relationsFor}=await import('/psy-stats/assets/library/graph.mjs'),{openLibrary}=await import('/psy-stats/assets/library/store.mjs'),store=await openLibrary(backupContext),s=await store.snapshot();const ent=relationsFor({space:'personal',id:'human-ai-entanglement'},s.records.edges);if(!ent.outgoing.some(e=>e.to.id==='cognitive-drift'&&e.type==='next'))throw Error('Positive relation missing');if(s.records.edges.some(e=>e.from.id==='dominant-trait-profile'&&e.to.id==='cognitive-drift'))throw Error('False cross-topic relation');const official=s.records.edges.find(e=>e.to.space==='official');if(official&&!relationsFor(official.to,s.records.edges).incoming.some(e=>e.id===official.id))throw Error('Official reverse view missing');const catalogue=await(await fetch('/psy-stats/assets/library/catalogue.json')).json();if(catalogue.terms.some(t=>['dominant-trait-profile','cognitive-drift','human-ai-entanglement'].includes(t.id)))throw Error('Private catalogue leak');store.close();return {scenario:'graph',positiveRelation:true,unrelatedControl:true,officialReverse:!!official,officialTerms:catalogue.terms.length};})()`);
}

async function searchQA(browser){
 await backup(browser);
 return browser.run(`(async()=>{
 const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),op=await import('/psy-stats/assets/library/operations.mjs'),s=await openLibrary(backupContext),before=await s.snapshot();
 const worker=new Worker('/psy-stats/assets/library/search.worker.mjs',{type:'module'});let serial=0;const ask=(type,payload)=>new Promise((resolve,reject)=>{const id=++serial;worker.onmessage=e=>e.data.id===id&&(e.data.error?reject(Error(e.data.error.message)):resolve(e.data.result));worker.postMessage({id,type,...payload});});
 await ask('build',{records:before.records});const hits=await ask('search',{query:'认知漂移'});if(!hits.some(h=>h.termId==='cognitive-drift'&&h.score===100))throw Error('Exact search missing');
 const revision=before.records.revisions.find(r=>r.termId==='cognitive-drift'),note=op.addAnnotation(before,{termId:revision.termId,revisionId:revision.id,blockId:'plain_explanation',text:'跨轮变化的观察笔记'});await s.commit(note,{expectedVersion:before.version});let stale=false;try{await s.commit(note,{expectedVersion:before.version});}catch(e){stale=e.code==='CONFLICT';}if(!stale)throw Error('Stale annotation overwrote state');
 let current=await s.snapshot();const recycled=op.trashTerm(current,'cognitive-drift');await s.commit(recycled,{expectedVersion:current.version});await ask('update',{changes:recycled});if((await ask('search',{query:'认知漂移'})).some(h=>h.termId==='cognitive-drift'))throw Error('Trash in search');current=await s.snapshot();await s.commit(op.restoreTerm(current,'cognitive-drift'),{expectedVersion:current.version});
 const lean=await s.read(['terms','sources']);if(lean.records.evidence.length||lean.records.revisions.length||lean.records.terms.length!==3)throw Error('Lean read cloned evidence');if(!(await s.getRecord('revisions',revision.id)))throw Error('Individual revision missing');
 current=await s.snapshot();const originalSource=current.records.sources.find(src=>src.blobHash&&current.records.sources.filter(other=>other.blobHash===src.blobHash).length>1);if(!originalSource)throw Error('Shared source fixture missing');const deletion=op.deleteOriginal(current,{sourceId:originalSource.id,removeExtracted:true});await s.commit(deletion,{expectedVersion:current.version});await s.discardStaged();
 const deleted=await s.snapshot(),archive=await qaArchive.exportBackup(deleted,s.getBlob,{}),inspection=await qaArchive.inspectBackup(archive,{stageBlob:s.stageBlob,discardStaged:s.discardStaged});if(inspection.validated.evidence.some(e=>e.sourceId===originalSource.id&&e.data.text))throw Error('Removed excerpt restored');
 worker.terminate();await s.discardStaged();s.close();return {scenario:'search',workerHits:hits.length,staleAnnotationConflict:true,trashExcluded:true,restored:true,leanRead:true,sharedSourceImpacts:deletion.impact.length,deletedEvidenceRoundtrip:true};})()`);
}

async function ui(browser){
 const errors=[];browser.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.exception?.description||e.exceptionDetails.text));
 await browser.page.send('Page.navigate',{url:'http://127.0.0.1:8773/psy-stats/index.html'});await browser.until('!!window.PsychSoftNavigation');
 assert.equal(await browser.run('new Set([...document.querySelectorAll(".site-head nav a")].map(a=>Math.round(a.getBoundingClientRect().top))).size'),1,'Desktop primary navigation remains one row');
 await browser.run(`globalThis.uiDocument=document;document.querySelector('.site-head nav a[href$="library/index.html"]').click();true`);
 await browser.until('!!document.querySelector(".library-empty")');
 assert.equal(await browser.run('document===uiDocument'),true);
 assert.equal(await browser.run('document.querySelectorAll(".library-card").length'),0);
 for(const name of ['dtp','cognitive-drift','human-ai-entanglement']){
  const {root}=await browser.page.send('DOM.getDocument');const {nodeId}=await browser.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
  await browser.page.send('DOM.setFileInputFiles',{nodeId,files:[resolve(log,'private-fixtures',name+'.zip')]});
  await browser.until('!!document.querySelector("dialog[open]")');
  await browser.run(`[...document.querySelectorAll('dialog button')].find(b=>b.textContent==='导入并保存').click();true`);
  await browser.until(`!document.querySelector('dialog')&&document.querySelectorAll('.library-card').length===${['dtp','cognitive-drift','human-ai-entanglement'].indexOf(name)+1}`);
 }
 await browser.run(`document.querySelector('a[href="#term=human-ai-entanglement"]').click();true`);await browser.until('!!document.querySelector(".personal-reader")');
 await browser.run(`const field=document.querySelector('.library-notes textarea');field.value='本机保存的验证笔记';document.querySelector('.library-notes form').requestSubmit();true`);
 await browser.until('!!document.querySelector(".library-note")');
 await browser.run(`globalThis.qaReaderNode=document.querySelector('.personal-reader');document.querySelector('.quiz-option').click();document.querySelector('.library-aside a[href*="block=plain_explanation"]').click();true`);
 await browser.until('location.hash.includes("block=plain_explanation")');
 await new Promise(r=>setTimeout(r,800));
 assert.equal(await browser.run('document.querySelector(".personal-reader")===qaReaderNode'),true,'Section navigation reuses the mounted reader');
 assert.equal(await browser.run('document.querySelectorAll(".quiz-option[aria-pressed=true]").length'),1,'Section navigation preserves reader interaction');
 const sizes=[];for(const width of [1440,390,320]){
  await browser.page.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<650});
  assert.equal(await browser.run('document.documentElement.scrollWidth<=innerWidth'),true);
  const shot=await browser.page.send('Page.captureScreenshot',{format:'png'});await writeFile(resolve(log,'ui-'+width+'.png'),Buffer.from(shot.data,'base64'));sizes.push(width);
 }
 await browser.page.send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 for(let i=0;i<10;i++){
  await browser.run(`document.querySelector('.site-head nav a[href$="paths.html"]').click();true`);await browser.until('!document.querySelector("[data-library-root]")');
  await browser.run(`document.querySelector('.site-head nav a[href$="library/index.html"]').click();true`);await browser.until('document.querySelectorAll(".library-card").length===3');
 }
 assert.equal(await browser.run('document===uiDocument'),true);assert.equal(await browser.run('document.querySelectorAll("#term-popover").length'),0);
 if(errors.length)throw Error(errors.join('\n'));
 return {scenario:'ui',casesImported:3,emptyLibraryInitially:true,softNavigation:true,noteSaved:true,widths:sizes,tenReentries:true,consoleErrors:errors.length};
}

async function offline(browser){
 await ui(browser);
 await browser.run(`location.hash='view=backup';true`);await browser.until('[...document.querySelectorAll("button")].some(b=>b.textContent==="启用离线阅读")');
 await browser.run(`[...document.querySelectorAll('button')].find(b=>b.textContent==='启用离线阅读').click();true`);
 await browser.until('document.querySelector("[data-library-status]").textContent.includes("离线阅读已就绪")');
 // The SPA originally created its document outside library/. A real reload
 // enters the narrow scope; changing history.pushState alone cannot do that.
 await browser.run('globalThis.qaOldDocument=document;true');await browser.page.send('Page.reload');await browser.until('!globalThis.qaOldDocument&&!!document.querySelector("[data-library-root]")&&!!navigator.serviceWorker.controller');
 const resources=await browser.run(`(async()=>{const keys=await caches.keys();const all=[];for(const key of keys){const c=await caches.open(key);all.push(...(await c.keys()).map(r=>new URL(r.url).pathname));}return all;})()`);
 assert.ok(resources.every(p=>p.startsWith('/psy-stats/assets/')||p.startsWith('/psy-stats/library/')));assert.ok(!resources.some(p=>p.endsWith('.pdf')||p.includes('private-fixtures')));
 await browser.page.send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 await browser.run('globalThis.qaOldDocument=document;true');await browser.page.send('Page.reload');await browser.until('!globalThis.qaOldDocument&&!!document.querySelector(".library-tabs")');
 await browser.run(`location.hash='term=dominant-trait-profile';true`);await browser.until('document.querySelector(".personal-reader h1")?.textContent.includes("优势特质")');
 assert.ok(await browser.run('document.querySelectorAll(".katex").length>0'));assert.equal(await browser.run('document.querySelector(".personal-reader figure img").naturalWidth>0'),true);
 await browser.run(`location.hash='term=cognitive-drift';true`);await browser.until('document.querySelector(".personal-reader h1")?.textContent==="认知漂移"');
 await browser.run(`document.querySelector('.quiz-option').click();true`);assert.ok(await browser.run('document.querySelector("#quiz-feedback").textContent.length>5'));
 const unknown=await browser.run(`fetch('/psy-stats/terms/nonexistent-offline.html').then(()=>false,()=>true)`);assert.equal(unknown,true);
 await browser.run(`(async()=>{const script=document.querySelector('script[data-library-module]'),app=await import(new URL(script.dataset.libraryModule,script.src)),{openLibrary}=await import(new URL('store.mjs',new URL(script.dataset.libraryModule,script.src))),op=await import(new URL('operations.mjs',new URL(script.dataset.libraryModule,script.src))),context=await app.libraryContext('http://127.0.0.1:8773/psy-stats/','local-library-preview'),s=await openLibrary(context),snapshot=await s.snapshot();snapshot.libraryId=context.libraryId;await s.commit(op.purgeLibrary(snapshot,{confirmLibraryId:context.libraryId}),{expectedVersion:snapshot.version});await s.discardStaged();s.close();return true;})()`);
 await browser.run('globalThis.qaOldDocument=document;true');await browser.page.send('Page.reload');await browser.until('!globalThis.qaOldDocument&&!!document.querySelector(".library-tabs")');
 assert.equal(await browser.run('document.querySelectorAll(".personal-reader").length'),0);
 await browser.page.send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
 return {scenario:'offline',cachedResources:resources.length,coldOffline:true,termsRead:2,formulas:true,figures:true,quiz:true,unknownOfficialNotFabricated:true,privateFilesNotCached:true,purgeNotRecoveredFromStaticCache:true};
}

async function performanceQA(browser){
 const runs=[];
 for(const [name,server] of [['baseline',8774],['library-preview',8773]]){
  await browser.page.send('Page.navigate',{url:'http://127.0.0.1:'+server+'/psy-stats/index.html'});await browser.until('!!window.PsychSoftNavigation');await new Promise(r=>setTimeout(r,250));
  const initial=await browser.run(`(async()=>({resources:performance.getEntriesByType('resource').map(r=>r.name),databases:(await indexedDB.databases()).map(d=>d.name),heap:performance.memory?.usedJSHeapSize||null,longTasks:window.PsychSoftNavigation.longTasks}))()`);
  assert.equal(initial.resources.filter(u=>/\/assets\/library(?:-[a-f0-9]{16})?\//.test(u)).length,0,'Public page requested heavy library modules');
  assert.equal(initial.databases.filter(n=>n.startsWith('psych-term-library')).length,0,'Public page opened personal storage');
  const timings=[];
  for(const path of ['paths.html','datasets.html','practice.html','symbols.html','index.html']){
   await browser.run(`globalThis.qaStart=performance.now();document.querySelector('.site-head nav a[href$="${path}"]').click();true`);
   await browser.until(`location.pathname.endsWith('/${path}')&&!window.PsychSoftMotion?.running`);
   timings.push({path,elapsedMs:await browser.run('Math.round(performance.now()-qaStart)')});
  }
  runs.push({name,initialResources:initial.resources.length,libraryHeavyRequests:0,libraryDatabases:0,initialHeapBytes:initial.heap,longTasks:initial.longTasks,timings});
 }
 return {scenario:'performance',headless:true,actualDisplayFramesTested:false,onlineTested:false,runs};
}
async function allQA(){
 const results=[];for(const name of ['assets','store','backup','markdown','reader','graph','search','offline','performance','review-search','review-notes','review-integrity']){
  const raw=execFileSync(process.execPath,[resolve(ROOT,'tools/qa_local_library.mjs'),'--scenario',name,'--cdp',String(port)],{encoding:'utf8',maxBuffer:4*1024*1024});results.push(JSON.parse(raw));
 }return {scenario:'all',results};
}

async function reviewSearch(browser){
 await ui(browser);await browser.run(`globalThis.qaWorkerCount=0;globalThis.Worker=class extends Worker{constructor(...args){super(...args);qaWorkerCount++;}};const input=document.querySelector('#library-search');input.value='认知漂移';input.dispatchEvent(new Event('input',{bubbles:true}));true`);await browser.until('!!document.querySelector(".library-card mark")');
 await browser.run(`document.querySelector('.library-card[href*="term=cognitive-drift"]').click();true`);await browser.until('document.querySelector(".personal-reader h1")?.textContent==="认知漂移"');
 await browser.run(`[...document.querySelectorAll('button')].find(b=>b.textContent==='移入回收区').click();true`);await browser.until('!!document.querySelector("#library-search")');await new Promise(r=>setTimeout(r,400));
 assert.equal(await browser.run('document.querySelectorAll(".library-card[href*=cognitive-drift]").length'),0,'Trashed private data removed from existing search index');
 assert.equal(await browser.run('qaWorkerCount'),1,'Own saves update only affected index entries without rebuilding the worker');
 await browser.run(`location.hash='view=backup';true`);await browser.until('[...document.querySelectorAll("button")].some(b=>b.textContent==="删除全部本机知识")');await browser.run(`[...document.querySelectorAll('button')].find(b=>b.textContent==='删除全部本机知识').click();true`);await browser.until('!!document.querySelector("dialog[open]")');await browser.run(`[...document.querySelectorAll('dialog button')].find(b=>b.textContent==='继续确认').click();true`);await browser.until('!!document.querySelector("dialog input")');await browser.run(`document.querySelector('dialog input').value='personal';[...document.querySelectorAll('dialog button')].find(b=>b.textContent==='完整删除').click();true`);await browser.until('!document.querySelector("dialog")');await browser.run(`location.hash='view=list';true`);await browser.until('!!document.querySelector("#library-search")');await new Promise(r=>setTimeout(r,300));assert.equal(await browser.run('document.querySelectorAll(".library-card").length'),0,'Full deletion clears search and in-memory results');
 return {scenario:'review-search',staleDeletedSearchCleared:true};
}
async function reviewNotes(browser){
 await ui(browser);await browser.run(`document.querySelector('a[href="#term=human-ai-entanglement"]').click();true`);await browser.until('!!document.querySelector("[data-annotation-editor]")');
 const id=await browser.run(`document.querySelector('[data-annotation-editor]').dataset.annotationEditor`);await browser.run(`const d=document.querySelector('[data-annotation-editor]');d.open=true;d.querySelector('textarea').value='更正后的批注';d.querySelector('select').value='detailed_explanation';d.querySelector('form').requestSubmit();true`);await browser.until('document.querySelector(".library-note p")?.textContent==="更正后的批注"');assert.equal(await browser.run('document.querySelector("[data-annotation-editor]").dataset.annotationEditor'),id);
 return {scenario:'review-notes',editing:true,relocation:true,identityPreserved:true};
}
async function reviewIntegrity(browser){
 await backup(browser);
 return browser.run(`(async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),op=await import('/psy-stats/assets/library/operations.mjs'),s=await openLibrary(backupContext);let state=await s.snapshot();const old=state.records.revisions.find(r=>r.termId==='cognitive-drift');const added=op.addAnnotation(state,{termId:old.termId,revisionId:old.id,blockId:'plain_explanation',text:'保留旧定位的批注'});await s.commit(added,{expectedVersion:state.version});state=await s.snapshot();const revision=structuredClone(old);revision.id='review-independent-revision';revision.lesson.blocks=revision.lesson.blocks.filter(b=>b.id!=='plain_explanation');await s.commit(op.addRevision(state,{termId:old.termId,revision}),{expectedVersion:state.version});state=await s.snapshot();const note=state.records.annotations[0];if(note.anchorStatus!=='needs-location')throw Error('Removed block note lost relocation status');await s.commit(op.updateAnnotation(state,{annotationId:note.id,text:'修订后重新定位',revisionId:revision.id,blockId:'detailed_explanation'}),{expectedVersion:state.version});state=await s.snapshot();const sourceId=revision.sourceIds[0];await s.commit(op.deleteOriginal(state,{sourceId,removeExtracted:true}),{expectedVersion:state.version});state=await s.snapshot();const backup=await qaArchive.exportBackup(state,s.getBlob,{}),restore=await openLibrary({...backupContext,libraryId:'review-restored'}),inspected=await qaArchive.inspectBackup(backup,{stageBlob:restore.stageBlob,discardStaged:restore.discardStaged});await restore.commit(await qaArchive.planRestore(await restore.snapshot(),inspected.validated),{expectedVersion:0});const restored=await restore.snapshot();if(!restored.records.revisions.some(r=>r.id===revision.id)||restored.records.annotations[0].anchorHistory[0].revisionId!==old.id)throw Error('Version or original note anchor lost during restore');const saved=restored.records.revisions.find(r=>r.id===revision.id),{mountReader}=await import('/psy-stats/assets/library/reader.mjs'),reader=mountReader(document.querySelector('main'),{revision:saved,sources:restored.records.sources,works:restored.records.works});await reader.ready;if(!document.querySelector('.personal-evidence-scope')?.textContent.includes('提取片段已删除'))throw Error('Evidence removal not disclosed');reader.dispose();
 const fflate=await import('/psy-stats/assets/vendor/fflate/fflate.mjs'),{sha256}=await import('/psy-stats/assets/library/safe-assets.mjs'),bad={schemaVersion:1,packageId:'bad-teaching',...state.records};bad.revisions=structuredClone(state.records.revisions);bad.revisions[0].lesson.formulas=[{latex:'x',refs:[]}];const bytes=fflate.strToU8(JSON.stringify(bad)),hash=await sha256(bytes),broken=fflate.zipSync({'library.json':bytes,'manifest.json':fflate.strToU8(JSON.stringify({schemaVersion:1,kind:'personal-library-backup',packageId:bad.packageId,files:[{path:'library.json',size:bytes.length,mime:'application/json',hash}]}))});const version=(await restore.snapshot()).version;let rejected=false;try{await qaArchive.inspectBackup(new Blob([broken]),{stageBlob:restore.stageBlob,discardStaged:restore.discardStaged});}catch(e){rejected=e.code==='INVALID_PACKAGE';}if(!rejected||(await restore.snapshot()).version!==version)throw Error('Malformed teaching changed active library');await s.discardStaged();await restore.discardStaged();s.close();restore.close();return {scenario:'review-integrity',newRevisionRoundtrip:true,noteRelocationRoundtrip:true,deletedEvidenceVisible:true,malformedPackageAtomic:true};})()`);
}
async function demoExport(browser){await backup(browser);const encoded=await browser.run(`(async()=>{const data=new Uint8Array(await savedBackupBlob.arrayBuffer());let out='';for(let i=0;i<data.length;i+=8192)out+=String.fromCharCode(...data.subarray(i,i+8192));return btoa(out);})()`);const target=resolve(log,'private-fixtures/three-case-library.zip');await writeFile(target,Buffer.from(encoded,'base64'));return {scenario:'case-export',terms:3,private:true,file:target,bytes:Buffer.from(encoded,'base64').length};}

const browser=await isolatedPage(port,1440);
try{
 await browser.page.send('Page.navigate',{url});await browser.until('document.readyState==="complete"');
 const result=await ({assets,store,backup,markdown,reader,graph,search:searchQA,ui,offline,performance:performanceQA,all:allQA,'case-export':demoExport,'review-search':reviewSearch,'review-notes':reviewNotes,'review-integrity':reviewIntegrity}[scenario]?.(browser)||Promise.reject(Error('Unknown scenario: '+scenario)));
 if(scenario==='store'){
  const context=await browser.run('JSON.parse(sessionStorage.getItem("qaStoreContext"))');
  const info=await browser.page.send('Target.getTargetInfo');
  const {targetId}=await browser.page.send('Target.createTarget',{url:'about:blank',browserContextId:info.targetInfo.browserContextId});
  const list=await(await fetch('http://127.0.0.1:'+port+'/json')).json();const other=connect(list.find(t=>t.id===targetId).webSocketDebuggerUrl);await other.ready;
  try{
   await other.send('Page.enable');await other.send('Runtime.enable');await other.send('Page.navigate',{url});
   const evaluate=async expression=>{const r=await other.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value;};
   const setup=`(async()=>{const m=await import('/psy-stats/assets/library/store.mjs');globalThis.tabStore=await m.openLibrary(${JSON.stringify(context)});return (await tabStore.snapshot()).version;})()`;
   assert.equal(await browser.run(setup),2);assert.equal(await evaluate(setup),2);
   const save=id=>`(async()=>{try{await tabStore.commit({writes:[{kind:'terms',id:'${id}',value:{id:'${id}',zh:'标签页修改',aliases:[],tags:[]}}],deletes:[],blobRefs:[],impact:[]},{expectedVersion:2});return 'saved';}catch(e){return e.code;}})()`;
   const outcomes=await Promise.all([browser.run(save('tab-one')),evaluate(save('tab-two'))]);assert.deepEqual(outcomes.sort(),['CONFLICT','saved']);
   await evaluate('tabStore.close()');await browser.run('tabStore.close()');result.realTabsOneWinner=true;result.version=3;
  }finally{other.ws.close();await browser.page.send('Target.closeTarget',{targetId});}
  await browser.page.send('Page.reload');await browser.until('document.readyState==="complete"');
  const restored=await browser.run(`(async()=>{const m=await import('/psy-stats/assets/library/store.mjs'),s=await m.openLibrary(JSON.parse(sessionStorage.getItem('qaStoreContext')));const state=await s.snapshot();s.close();return {version:state.version,count:state.records.terms.length};})()`);
  assert.equal(restored.version,3);assert.equal(restored.count,2);result.reloadPersistence=true;
 }
 await writeFile(resolve(log,scenario+'-qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
