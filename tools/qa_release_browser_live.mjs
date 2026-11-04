// Real browser -> HTTPS API -> bounded supplier -> ZIP -> local library.
// Only starts a fresh task when this QA owner's task list has none for the case.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {isolatedPage,args,wait} from './native-cdp.mjs';
const o=args(),width=Number(o.width||1440),root='.superpowers/sdd/2026-10-24-online-release-readiness',meta=JSON.parse(await readFile(root+'/live-https/active.json','utf8')),b=await isolatedPage(9296,width),events=[],errors=[];
const term='频数分布',api=meta.origin+'/psy-stats/api/term-explainer/';let last;
const get=path=>b.run(`fetch(${JSON.stringify(api)}+${JSON.stringify(path)},{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('API '+r.status);return r.json()})`);
const click=text=>b.run(`(()=>{const n=[...document.querySelectorAll('button')].find(n=>n.textContent===${JSON.stringify(text)});if(!n)throw Error('Missing action');n.click()})()`);
async function until(expression,seconds=45){for(let i=0;i<seconds*5;i++){if(await b.run(expression))return;await wait(200);}throw Error('Timeout: '+expression);}
async function answer(job,value){return b.run(`(async()=>{const root=${JSON.stringify(api)},session=await(await fetch(root+'session',{cache:'no-store'})).json();const r=await fetch(root+'jobs/'+${JSON.stringify(job.id)}+'/answers',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({version:${job.version},answer:${JSON.stringify(value)}})});if(!r.ok)throw Error(await r.text());return r.json()})()`);}
try{
 b.page.events.set('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails?.text||'browser-exception'));
 await b.page.send('Security.enable');await b.page.send('Security.setIgnoreCertificateErrors',{ignore:true});
 await b.page.send('Page.navigate',{url:meta.origin+'/psy-stats/library/index.html#view=generate'});
 await until(`!!document.querySelector('.generation-login input')`);
 await b.run(`(()=>{const f=document.querySelector('.generation-login');f.querySelector('input').value=${JSON.stringify(meta.invitation)};f.requestSubmit()})()`);
 await until(`!!document.querySelector('form.generation-form')`);
 let jobs=await get('jobs');jobs=jobs.jobs||jobs;last=jobs.find(j=>j.termName===term);
 if(!last){
  await b.run(`(()=>{const f=document.querySelector('form.generation-form');f.querySelector('input:not([type])').value=${JSON.stringify(term)};f.querySelector('textarea').value='理解如何把一组问卷观测记录按类别或区间汇总，读出分布。统计学中的 Frequency distribution。';[...f.querySelectorAll('input[type=checkbox]')].at(-1).checked=true;f.requestSubmit()})()`);
  await until(`!!document.querySelector('.generation-detail small')`);jobs=await get('jobs');jobs=jobs.jobs||jobs;last=jobs.find(j=>j.termName===term);assert.ok(last);
 }
 let clarified=false,left=false,hinted=false;
 for(let i=0;i<1200;i++){
  last=await get('jobs/'+last.id);
  const stage=last.state+':'+last.stage;
  if(events.at(-1)?.stage!==stage){events.push({stage,elapsedSeconds:i*2});console.log(JSON.stringify({job:last.id,stage}));}
  if(last.state==='waiting_input'){
   const q=last.question;
   if(o['source-hint']&&!hinted&&['concept','sources','scope'].includes(q.kind)){
    hinted=true;await answer(last,{question_id:q.id,action:'clarify',explanation:o['source-hint']});
   }else if(q.kind==='literature')await answer(last,{question_id:q.id,action:'continue',allow_network:true});
   else if(q.kind==='concept'){
    const valid=(q.candidates||[]).filter(c=>{try{return /(^|\.)(openstax\.org|onlinestatbook\.com|psu\.edu|nist\.gov|libretexts\.org|statlect\.com|britannica\.com|who\.int|un\.org)$/.test(new URL(c.url).hostname)&&/frequen|频数/i.test(c.title+' '+c.url+' '+(c.search_snippet||''))}catch{return false}});
    if(!valid.length){await writeFile(root+'/live-candidate-review.json',JSON.stringify({job:last.id,question:q},null,2));throw Error('No preapproved source-identity match; candidates saved for agent inspection');}
    await answer(last,{question_id:q.id,candidate_id:valid[0].id});
   }else throw Error('Evidence needs additional substantive review; saved task remains intact');
  }else if(['complete','failed','needs_reconciliation','cancelled','expired'].includes(last.state))break;
  if(!left&&last.state==='running'){
   left=true;await b.run(`location.hash='view=guide'`);await wait(200);await b.run(`location.hash='view=generate'`);await until(`!!document.querySelector('form.generation-form')`);
  }
  await wait(2000);
 }
 assert.equal(last.state,'complete',JSON.stringify({state:last.state,progress:last.progress}));
 await b.page.send('Page.reload',{ignoreCache:false});await until(`!!document.querySelector('form.generation-form')`);
 await b.run(`(()=>{const n=[...document.querySelectorAll('.generation-page button')].find(n=>n.textContent.includes(${JSON.stringify(term)})&&n.textContent.includes('已生成'));if(!n)throw Error('Completed task not restored');n.click()})()`);
 await until(`document.querySelector('.generation-detail h3')?.textContent==='已生成，可领取'`);
 await click('查看生成的科普');await until(`!!document.querySelector('.generation-preview .personal-reader h1')`);
 assert.equal(await b.run(`document.querySelector('.generation-preview .personal-reader h1').textContent`),term);
 await click('核对并保存到我的知识库');await until(`!!document.querySelector('dialog[open]')`);await click('导入并保存');await until(`!document.querySelector('dialog[open]')`);
 await b.run(`location.hash='view=list'`);await until(`!!document.querySelector('.library-card')`);
 await b.run(`document.querySelector('.library-card').click()`);await until(`!!document.querySelector('.personal-reader h1')`);
 for(let i=0;i<4;i++){await b.run(`document.querySelectorAll('.quiz-option')[${i}].click()`);assert.ok((await b.run(`document.querySelector('#quiz-feedback').textContent`)).length>10);}
 assert.ok(await b.run(`document.documentElement.scrollWidth<=innerWidth+1`));
 await mkdir(root+'/browser',{recursive:true});const shot=await b.page.send('Page.captureScreenshot',{format:'png'});await writeFile(root+'/browser/live-reader-'+width+'.png',Buffer.from(shot.data,'base64'));
 const report={status:'passed',job:last.id,width,realBrowser:true,realAPI:true,realSupplier:true,noUploadedLiterature:true,backgroundNavigation:left,refreshRestored:true,localSaved:true,quizOptions:4,events,errors};
 await writeFile(root+'/browser/live-'+width+'.json',JSON.stringify(report,null,2));assert.equal(errors.length,0,JSON.stringify(errors));console.log(JSON.stringify(report));
}catch(e){await writeFile(root+'/live-browser-failure.json',JSON.stringify({message:e.message,job:last,events,errors},null,2));throw e;}finally{await b.close();}
