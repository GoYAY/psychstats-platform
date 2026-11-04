import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {isolatedPage,args} from './native-cdp.mjs';
const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'..'),o=args(),log=resolve(ROOT,'logs/operational-teaching-visuals');
await mkdir(log,{recursive:true});
const b=await isolatedPage(Number(o.cdp||9296),1440);
try{
 await b.page.send('Page.navigate',{url:o.url||'http://127.0.0.1:8773/psy-stats/qa/library-host.html'});
 await b.until('document.readyState === "complete"');
 const bytes=(await readFile(resolve(log,'private/human-ai-entanglement-operational-final.zip'))).toString('base64');
 await b.run(`(async()=>{const {openLibrary}=await import('/psy-stats/assets/library/store.mjs'),a=await import('/psy-stats/assets/library/archive.mjs');globalThis.s=await openLibrary({environment:'qa-visual-'+Date.now(),libraryId:'main',owner:null});const p=await a.inspectBackup(new Blob([Uint8Array.from(atob(${JSON.stringify(bytes)}),c=>c.charCodeAt(0))]),{stageBlob:s.stageBlob,discardStaged:s.discardStaged});const before=await s.snapshot();await s.commit(await a.planRestore(before,p.validated),{expectedVersion:before.version});globalThis.state=await s.snapshot();if(state.records.revisions.length!==2)throw Error('Old revision missing');globalThis.reader=await import('/psy-stats/assets/library/reader.mjs');return true;})()`);
 const rows=[];
 for(const width of [1440,390,320]){
  await b.page.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
  const row=await b.run(`(async()=>{const records=state.records,t=records.terms[0],r=records.revisions.find(x=>x.id===t.currentRevisionId),root=document.querySelector('main');if(globalThis.controller)controller.dispose();globalThis.controller=reader.mountReader(root,{revision:r,sources:records.sources,works:records.works,resolveAsset:role=>{const a=records.assets.find(a=>r.assetIds.includes(a.id)&&a.role===role);return a?s.getBlob(a.blobHash):null;}});await controller.ready;const img=root.querySelector('img');if(!img)throw Error('No image');await img.decode();if(r.lesson.visual.payload.layout!=='feedback_trace')throw Error('Old image selected');if(document.documentElement.scrollWidth>innerWidth)throw Error('Page overflow');for(const opt of root.querySelectorAll('.quiz-option')){opt.click();if(!root.querySelector('#quiz-feedback').textContent.includes(r.lesson.quiz.options.find(x=>x.id===opt.dataset.option).explanation))throw Error('Quiz feedback');}const helper=root.querySelector('[data-note]'),panel=root.querySelector('#term-popover');if(helper){helper.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));if(!panel.hidden)throw Error('Hover opened');helper.click();if(panel.hidden)throw Error('Click failed');document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));}if(root.innerHTML.includes('span_id')||root.innerHTML.includes('source_id'))throw Error('Private evidence in DOM');return {width:innerWidth,revisions:records.revisions.length,figureWidth:img.getBoundingClientRect().width,sources:root.querySelectorAll('.personal-sources li').length};})()`);
  assert.ok(row.figureWidth>200);rows.push(row);
  // Inspect the figure itself, not merely the document's introduction.
  for(let round=0;round<(width<600?3:1);round++){
   const visible=await b.run(`(()=>{const img=document.querySelector('main img'),r=img.getBoundingClientRect();window.scrollTo(0,scrollY+r.top+${round}*r.height/3-40);const after=img.getBoundingClientRect();return after.top<innerHeight&&after.bottom>0;})()`);
   assert.equal(visible,true,'Figure must intersect screenshot');
   const shot=await b.page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(resolve(log,`reader-${width}-round-${round+1}.png`),Buffer.from(shot.data,'base64'));
  }
 }
 await writeFile(resolve(log,'browser-review.json'),JSON.stringify({status:'passed',rows,modelCalls:0,scientificReview:'pending human'},null,2));console.log(JSON.stringify({status:'passed',rows}));
}finally{await b.close();}
