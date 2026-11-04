import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {isolatedPage,args} from './native-cdp.mjs';

// These regressions exercise the shipped page in a disposable browser context.
// Breaks caught: body-layer cursor under a modal; irreversible relation decisions.
const options=args(),scenario=options.scenario||'cursor';
const url=options.url||'http://127.0.0.1:8773/psy-stats/library/index.html';
const browser=await isolatedPage(Number(options.cdp||9296),1440);
const reportDir=resolve('logs/local-library-interactions');
const fixture=resolve('logs/local-library/private-fixtures/three-case-library.zip');
async function clickText(text,scope='[data-library-root]'){
 await browser.run(`(()=>{const b=[...document.querySelectorAll(${JSON.stringify(scope+' button')})].find(b=>b.textContent===${JSON.stringify(text)});if(!b)throw Error('Missing action: '+${JSON.stringify(text)});b.click();return true;})()`);
}
async function openImport(){
 const {root}=await browser.page.send('DOM.getDocument');
 const {nodeId}=await browser.page.send('DOM.querySelector',{nodeId:root.nodeId,selector:'[data-library-import]'});
 await browser.page.send('DOM.setFileInputFiles',{nodeId,files:[fixture]});
 await browser.until('!!document.querySelector("dialog:modal")');
}
async function moveToModal(){
 const point=await browser.run(`(()=>{const r=document.querySelector('dialog button').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
 await browser.page.send('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
 await browser.until('!document.querySelector(".cursor-dot").hidden');
 return browser.run(`(()=>{const dot=document.querySelector('.cursor-dot'),r=dot.getBoundingClientRect();return {inModal:!!dot.closest('dialog:modal'),interactive:dot.classList.contains('is-interactive'),x:r.x+r.width/2,y:r.y+r.height/2,count:document.querySelectorAll('.cursor-dot').length};})()`);
}
async function cursor(){
 assert.equal(await browser.run(`matchMedia('(hover: hover) and (pointer: fine)').matches`),true,'Desktop pointer prerequisite');
 await openImport();const state=await moveToModal();
 assert.equal(state.inModal,true,'Custom ring must share the visible modal layer');
 assert.equal(state.interactive,true);assert.equal(state.count,1);
 const screenshot=await browser.page.send('Page.captureScreenshot',{format:'png'});
 await writeFile(resolve(reportDir,'modal-cursor.png'),Buffer.from(screenshot.data,'base64'));
 await clickText('取消','dialog');
 await browser.until('!document.querySelector("dialog")');
 await browser.until('document.querySelector(".cursor-dot")?.parentElement===document.body');
 await browser.page.send('Page.reload');await browser.until('document.querySelector("[data-library-status]")?.textContent.includes("资料仅保存在")');
 await openImport();await moveToModal();
 await browser.page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
 await browser.page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
 await browser.until('!document.querySelector("dialog")');
 await browser.until('document.querySelector(".cursor-dot")?.parentElement===document.body');
 await browser.page.send('Page.reload');await browser.until('document.querySelector("[data-library-status]")?.textContent.includes("资料仅保存在")');
 await openImport();await clickText('导入并保存','dialog');
 await browser.until('document.querySelectorAll(".library-card").length===3');
 await browser.until('document.querySelector(".cursor-dot")?.parentElement===document.body');
 assert.equal(await browser.run('document.querySelectorAll(".cursor-dot").length'),1);
 return {scenario,cancelRestores:true,escapeRestores:true,confirmRestores:true,interactiveRingInModal:true};
}
async function ensureTestFramework(){
 await browser.run(`(async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),{libraryContext}=await import('/psy-stats/assets/library/app.mjs'),{planFrameworkCommand}=await import('/psy-stats/assets/library/framework-commands.mjs');const s=await openLibrary(await libraryContext(new URL('/psy-stats/',location.href),'local-library-preview')),before=await s.snapshot();if(!before.records.frameworks.length){const p=planFrameworkCommand(before,{kind:'create',id:'relation-check',title:'交互测试框架',members:before.records.terms.filter(t=>!t.trashed).map(t=>({space:'personal',id:t.id}))});await s.commit(p.plan,{expectedVersion:before.version});}s.close();})()`);
}
async function relations(){
 await openImport();await clickText('导入并保存','dialog');
 await browser.until('document.querySelectorAll(".library-card").length===3');
 await browser.run(`location.hash='term=human-ai-entanglement';true`);
 await browser.until('!!document.querySelector(".library-aside .library-relation")');
 await clickText('确认关联','.library-aside');
 await browser.until('document.querySelector(".library-aside .library-relation")?.textContent.includes("已确认")');
 assert.equal(await browser.run(`[...document.querySelectorAll('.library-aside button')].some(b=>b.textContent==='撤回确认')`),true,'Confirmed relation must be reversible');
 await clickText('撤回确认','.library-aside');
 await browser.until(`[...document.querySelectorAll('.library-aside button')].some(b=>b.textContent==='确认关联')`);
 await clickText('隐藏关联','.library-aside');
 await browser.until('document.querySelectorAll(".library-aside > .library-relation").length===0');
 await clickText('撤销隐藏');
 await browser.until('document.querySelectorAll(".library-aside > .library-relation").length>0');
 await clickText('隐藏关联','.library-aside');
 await browser.until('!!document.querySelector(".library-hidden-relations")');
 await browser.page.send('Page.reload');
 await browser.until('!!document.querySelector(".library-hidden-relations")');
 assert.equal(await browser.run(`document.querySelector('.library-hidden-relations').textContent.includes('认知漂移')`),true,'Reload must retain a discoverable hidden target');
 await browser.run(`document.querySelector('.library-hidden-relations').open=true;true`);
 await clickText('恢复关联','.library-hidden-relations');
 await browser.until('document.querySelectorAll(".library-aside > .library-relation").length>0');
 await ensureTestFramework();await browser.run(`location.hash='view=network';true`);await browser.until('!!document.querySelector("[data-member-key]")');await browser.run(`document.querySelector('[data-member-key="personal:human-ai-entanglement"]').click()`);
 await browser.until('!!document.querySelector(".canvas-list button")');
 await browser.run(`(()=>{[...document.querySelectorAll('.canvas-list button')].find(b=>b.textContent.includes('纠缠')&&b.textContent.includes('认知漂移')).click();})()`);
 await clickText('移除关联','.canvas-side');
 await browser.until('!!document.querySelector(".canvas-removed-relations")');
 await browser.run(`document.querySelector('.canvas-removed-relations').open=true;document.querySelector('.canvas-removed-relations button').click();true`);
 await browser.until('!document.querySelector(".canvas-removed-relations")');
 return {scenario,unconfirm:true,undoHide:true,restoreAfterReload:true,networkRestore:true};
}
async function restoreCycle(){
 await openImport();await clickText('导入并保存','dialog');
 await browser.until('document.querySelectorAll(".library-card").length===3');
 // Isolated synthetic graph state: A requires B is hidden, B requires A active.
 await browser.run(`(async()=>{
  const script=document.querySelector('script[data-library-module]'),base=new URL('.',new URL(script.dataset.libraryModule,script.src)),app=await import(new URL('app.mjs',base)),{openLibrary}=await import(new URL('store.mjs',base)),context=await app.libraryContext(new URL('/psy-stats/',location.href),'local-library-preview'),s=await openLibrary(context),before=await s.snapshot();
  const edge=before.records.edges.find(e=>e.from.id==='human-ai-entanglement'&&e.to.id==='cognitive-drift'),target=before.records.terms.find(t=>t.id==='cognitive-drift');
  const hidden={...edge,type:'prerequisites',status:'dismissed'},reverse={...edge,id:'qa-cycle-reverse',from:edge.to,to:edge.from,type:'prerequisites',status:'confirmed',origin:'user',reason:'仅用于软件循环校验的合成关系',refs:[],revisionId:target.currentRevisionId};
  await s.commit({writes:[hidden,reverse].map(value=>({kind:'edges',id:value.id,value})),deletes:[],blobRefs:[],impact:[]},{expectedVersion:before.version});s.close();return true;
 })()`);
 await browser.page.send('Page.reload');await browser.until('!!document.querySelector(".library-content")');
 await ensureTestFramework();await browser.run(`location.hash='view=network';true`);await browser.until('!!document.querySelector("[data-member-key]")');await browser.run(`document.querySelector('[data-member-key="personal:human-ai-entanglement"]').click()`);
 await browser.until('!!document.querySelector(".canvas-removed-relations")');
 await browser.run(`document.querySelector('.canvas-removed-relations').open=true;document.querySelector('.canvas-removed-relations button').click();true`);
 await browser.until('document.querySelector(".canvas-notice").getAttribute("role")==="alert"||!document.querySelector(".canvas-removed-relations")');
 assert.equal(await browser.run(`document.querySelector('.canvas-notice').textContent.includes('循环')`),true,'Restoring a prerequisite must reject an active dependency cycle');
 assert.equal(await browser.run(`!!document.querySelector('.canvas-removed-relations')`),true,'Rejected restore preserves the hidden edge');
 return {scenario,cycleRestoreRejected:true,hiddenPreserved:true};
}
try{
 await mkdir(reportDir,{recursive:true});
 await browser.page.send('Page.navigate',{url});
 await browser.until('!!document.querySelector(".library-content")');
 const result=await ({cursor,relations,'restore-cycle':restoreCycle}[scenario]||(()=>{throw Error('Unknown scenario');}))();
 await writeFile(resolve(reportDir,scenario+'.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
