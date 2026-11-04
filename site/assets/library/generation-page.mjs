import {watchGeneration} from './generation-client.mjs';
export async function uploadPendingMaterials(client,job,files,descriptors){
 let next=await client.get(job.id);
 for(const slot of (next.uploads||[]).filter(d=>!d.uploaded)){
  const at=descriptors.findIndex(d=>d.sha256===slot.sha256&&d.mime===slot.mime&&d.bytes===slot.bytes);
  if(at<0)throw Error('还需选择待上传的原文件：'+slot.name);
  next=await client.upload(job.id,slot.id,new Blob([files[at]],{type:slot.mime}));
 }
 return next;
}
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
const size=bytes=>bytes>=1048576?(bytes/1048576).toFixed(2)+' MB':Math.round(bytes/1024)+' KB';
const STATES={draft:'待提交资料',queued:'排队中',running:'处理中',waiting_input:'需要你确认',needs_reconciliation:'请求状态待核对',complete:'已生成，可领取',failed:'任务未完成',cancelled:'已取消',expired:'临时任务已过期'};
const STAGES={input:'检查输入',checking_sources:'检查资料',reading:'阅读与整理证据',confirmation:'等待确认',compiling:'编排科普',rendering:'绘制并核对图示',organizing:'整理知识关系',ready:'可领取'};
export function generationStatus(job){return job.question?.kind==='recovery'?'进度已保存，等待修复后继续':job.progress?.error_code==='visual_review_required'?'图示尚未通过核对，已有内容和资料已保存':STATES[job.state]||job.state;}
export function mountGeneration({root,client,store,catalogue=[],knownTerms=[],chartHost=null,onImport,signal}={}){
 const controller=new AbortController(),active=()=>!controller.signal.aborted,urls=new Set();let polling=null,selectedFiles=[],manualFiles=[],localFiles=new Map(),draftKey=null,currentJob=null,busy=false;
 let limits;const previewResources=[];const abort=()=>{for(const release of previewResources)release();controller.abort();polling?.abort();for(const u of urls)URL.revokeObjectURL(u);};signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
 const page=el('section',null,'generation-page'),notice=el('p','','generation-notice');notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
 const loginArea=el('div'),composer=el('div'),tasks=el('section'),detail=el('section',null,'generation-detail');page.append(el('h2','把一个陌生术语，变成读得懂的知识'),el('p','提供术语与相关材料，生成解释、图示和知识关联。内测期间不收款。','generation-intro'),notice,loginArea,composer,tasks,detail);root.append(page);
 const report=(message,error=false)=>{if(!active())return;notice.textContent=message;notice.dataset.error=String(error);};
 const run=fn=>async()=>{if(busy)return;busy=true;page.inert=true;page.setAttribute('aria-busy','true');try{await fn();}catch(e){if(active()&&e.name!=='AbortError'){if(e.status===401){composer.hidden=true;tasks.hidden=true;detail.hidden=true;login();}report(e.message,true);}}finally{busy=false;page.inert=false;page.removeAttribute('aria-busy');}};
 const button=(text,action)=>{const b=el('button',text);b.type='button';b.addEventListener('click',run(action),{signal:controller.signal});return b;};
 function download(blob){const url=URL.createObjectURL(blob);urls.add(url);const a=el('a');a.href=url;a.download='术语科普包.zip';a.click();}
 async function loadResult(job,label='正在下载科普包'){
  const line=el('p',label+'…','generation-download');line.setAttribute('role','status');line.setAttribute('aria-live','polite');detail.append(line);
  try{return await client.result(job.id,{onProgress:({received,total})=>{if(active())line.textContent=label+'… '+size(received)+(total?' / '+size(total):'');}});}
  finally{line.remove();}
 }
 async function showJob(job){
  if(!active())return;for(const release of previewResources.splice(0))release();currentJob=job;report(generationStatus(job)+' · '+(STAGES[job.stage]||'后台任务'));detail.replaceChildren();detail.append(el('h3',generationStatus(job)),el('p',STAGES[job.stage]||'后台任务'),el('small','任务 '+job.id));
  if(job.usage)detail.append(el('p','已记录 '+(job.usage.calls||0)+' 次请求 · 已确认 '+(job.usage.confirmed_tokens||0).toLocaleString()+' tokens'+(job.usage.pending_reserved_tokens?' · 尚未结算预算预留 '+job.usage.pending_reserved_tokens.toLocaleString()+' tokens':''),'generation-usage'));
  if(job.progress?.public_message&&!job.question)detail.append(el('p',job.progress.public_message));
  if(job.question?.kind==='recovery'){
   for(const text of job.question.messages||[])detail.append(el('p',text));
   detail.append(button('修复后从已保存进度继续',async()=>{const latest=await client.get(job.id);await follow(await client.resume(job.id,latest.version));}));
  }
  if(job.question&&job.question.kind!=='recovery'){for(const text of job.question.messages||[])detail.append(el('p',text));
   if(['literature','sources'].includes(job.question.kind))detail.append(button('暂时没有文献，授权检索来源',async()=>follow(await client.answer(job.id,job.version,{question_id:job.question.id,action:'continue',allow_network:true}))),button('暂不联网，保留待补资料',async()=>follow(await client.answer(job.id,job.version,{question_id:job.question.id,action:'continue',allow_network:false}))));
   for(const item of job.question.candidates||[])detail.append(button(item.title||item.id,async()=>follow(await client.answer(job.id,job.version,{question_id:job.question.id,candidate_id:item.id}))));
   const materialForm=el('div',null,'generation-form'),extra=inputField(materialForm,'补充文献（发送所选PDF或文本后继续当前任务）');extra.type='file';extra.multiple=true;extra.accept='.pdf,.txt,application/pdf,text/plain';
   materialForm.append(button('补充所选文献并继续',async()=>{
    const selected=[...extra.files];if(!selected.length)throw Error('请先选择要补充的材料。');const docs=await describeFiles(selected);
    let next=await client.get(job.id);if(next.state!=='waiting_input'||next.question?.id!==job.question.id)throw Error('当前确认问题已更新，请从任务列表重新打开。');
    next=await client.materials(job.id,next.version,docs);
    next=await uploadPendingMaterials(client,next,selected,docs);
    if(next.question?.id!==job.question.id)throw Error('当前确认问题已更新，请从任务列表重新打开。');
    await follow(await client.answer(job.id,next.version,{question_id:job.question.id,action:'resume_sources'}));
   }));detail.append(materialForm);
   if(['concept','scope','sources'].includes(job.question.kind)){const clarification=el('div',null,'generation-form'),text=inputField(clarification,'补充你想理解的含义或应用情境','textarea');text.maxLength=1200;clarification.append(button('补充问题并继续',async()=>follow(await client.answer(job.id,job.version,{question_id:job.question.id,action:'clarify',explanation:text.value}))));detail.append(clarification);}
  }
  if(['queued','running','waiting_input','needs_reconciliation','draft'].includes(job.state))detail.append(button('取消此任务',async()=>{const latest=await client.get(job.id);await follow(await client.cancel(job.id,latest.version));}));
  if(job.state==='draft'){
   const box=el('div',null,'generation-form'),files=inputField(box,'需要补传的原文件（已经上传的无需重复选择）');files.type='file';files.multiple=true;files.accept='.pdf,.txt';
   const missing=(job.uploads||[]).filter(d=>!d.uploaded);box.append(el('p',missing.length?'待补传：'+missing.map(d=>d.name).join('；'):'资料已上传完成，可以继续启动。'));
   box.append(button('继续上传并启动',async()=>{
    const chosen=[...files.files],descriptors=await describeFiles(chosen);let next=await client.get(job.id);
    for(const item of (next.uploads||[]).filter(d=>!d.uploaded)){
     const at=descriptors.findIndex(d=>d.sha256===item.sha256);if(at<0)throw Error('还需选择与原提交指纹一致的文件：'+item.name);
     next=await client.upload(job.id,item.id,new Blob([chosen[at]],{type:item.mime}));
    }
    await follow(await client.start(job.id,next.version));
   }));detail.append(box);
  }
  if(job.state==='needs_reconciliation')detail.append(el('p','此前请求的响应未确认，系统不会自动重复调用。请保留任务编号，由测试管理员核对。'));
  if(job.state==='complete'&&job.kind==='lesson'){
   detail.append(el('p','产物临时保留至 '+new Date(job.expiresAt*1000).toLocaleString()+'。建议保存到本机并导出备份。'));
   detail.append(button('查看生成的科普',async()=>{
    const blob=await loadResult(job),memory=new Map(),{inspectBackup}=await import('./archive.mjs'),{mountReader}=await import('./reader.mjs'),{mountReadingNavigation}=await import('./reading-layout.mjs');
    const inspected=await inspectBackup(blob,{signal:controller.signal,stageBlob:async(hash,data)=>{memory.set(hash,data);return hash;},discardStaged:async()=>memory.clear()});if(!active())return;
    const v=inspected.validated,revision=v.revisions[0],area=el('div',null,'generation-preview'),layout=el('div',null,'library-reading-layout'),article=el('div'),aside=el('aside',null,'library-aside');layout.append(article,aside);
    let navigation;const leave=()=>{reader.dispose();navigation?.dispose();memory.clear();area.remove();detail.classList.remove('is-preview');};
    area.append(button('← 返回生成任务',leave),layout);detail.append(area);detail.classList.add('is-preview');
    const reader=mountReader(article,{revision,sources:v.sources,works:v.works,catalogue,chartHost,signal:controller.signal,resolveAsset:async role=>{const a=v.assets.find(a=>revision.assetIds.includes(a.id)&&a.role===role)||v.assets.find(a=>revision.assetIds.includes(a.id));return a?memory.get(a.blobHash):null;}});
    previewResources.push(leave);await reader.ready;if(active()){navigation=mountReadingNavigation(aside,article,{lesson:revision.lesson,signal:controller.signal});area.scrollIntoView({block:'start'});}
   }),button('核对并保存到我的知识库',async()=>{const blob=await loadResult(job);await onImport(new File([blob],'generated-lesson.zip',{type:'application/zip'}));}),button('下载科普包',async()=>download(await loadResult(job))));
  }
 }
 async function follow(job){
  polling?.abort();polling=new AbortController();controller.signal.addEventListener('abort',()=>polling?.abort(),{once:true});await showJob(job);
  if(['queued','running'].includes(job.state))watchGeneration(client,job.id,{signal:polling.signal,onState:showJob}).catch(e=>{if(active()&&e.name!=='AbortError')report(e.message+' 任务仍可从列表继续查看。',true);});
 }
 async function list(){const value=await client.list();if(!active())return;tasks.replaceChildren(el('h3','我的生成任务'));if(!value.jobs.length)tasks.append(el('p','还没有生成任务。'));for(const job of value.jobs)tasks.append(button((job.termName||job.id)+' · '+(STATES[job.state]||job.state),async()=>follow(await client.get(job.id))));}
 function inputField(form,label,tag='input'){
  const holder=el('label',label),input=el(tag);holder.append(input);form.append(holder);return input;
 }
 async function describeFiles(files){
  if(files.length>limits.files)throw Error('文献数量超过当前内测限制。');let total=0;const docs=[];
  for(const file of files){total+=file.size;if(file.size>limits.fileBytes||total>limits.totalBytes)throw Error('文献大小超过当前内测限制。');const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),x=>x.toString(16).padStart(2,'0')).join('');docs.push({name:file.name,title:file.name,mime:file.name.toLowerCase().endsWith('.txt')?'text/plain':'application/pdf',bytes:file.size,sha256:hash});}return docs;
 }
 async function compose(session){
  limits=session.limits;
  if(!active())return;const rememberedName=composer.querySelector('input:not([type])')?.value||'',rememberedDefinition=composer.querySelector('textarea')?.value||'';composer.hidden=false;tasks.hidden=false;detail.hidden=false;composer.replaceChildren();loginArea.replaceChildren(button('退出内测会话',async()=>{try{await client.logout();}catch(e){if(e.status!==401)throw e;}polling?.abort();composer.replaceChildren();tasks.replaceChildren();detail.replaceChildren();login();report('已退出。已保存在本机的知识不变。');}));
  const form=el('form',null,'generation-form'),name=inputField(form,'术语名称'),definition=inputField(form,'希望理解的问题或文献阅读要求（可选）','textarea');name.required=true;name.maxLength=120;definition.maxLength=1500;definition.rows=3;name.value=rememberedName;definition.value=rememberedDefinition;
  const identityDetails=el('details');identityDetails.append(el('summary','补充已有英文名或定义（可选）'));const english=inputField(identityDetails,'英文名称（没有可留空，系统会据文献核对）');english.type='text';english.maxLength=160;const termDefinition=inputField(identityDetails,'你已知的术语定义（不是阅读要求）','textarea');termDefinition.maxLength=1500;form.append(identityDetails);
  const fileInput=inputField(form,'相关文献（可选，PDF / UTF-8文本）');fileInput.type='file';fileInput.multiple=true;fileInput.accept='.pdf,.txt,application/pdf,text/plain';
  manualFiles=[];localFiles.clear();selectedFiles=[];const selected=el('p','尚未选择文献。可以先提交，系统会提示补充来源。','generation-file-summary');form.append(selected);const syncFiles=()=>{selectedFiles=[...manualFiles,...localFiles.values()];draftKey=null;selected.textContent=selectedFiles.map(f=>f.name).join('；')||'尚未选择文献。';};
  fileInput.addEventListener('change',()=>{manualFiles=[...fileInput.files];syncFiles();},{signal:controller.signal});
  const localPapers=el('details');localPapers.append(el('summary','从已保存文献选择'));form.append(localPapers);
  const records=await store.read(['sources','works']);if(!active())return;const seen=new Set();
  for(const source of records.records.sources.filter(s=>s.blobHash&&s.originalStatus==='saved')){
   if(seen.has(source.blobHash))continue;seen.add(source.blobHash);const work=records.records.works.find(w=>w.id===source.workId),label=el('label',work?.title||source.fileName),check=el('input');check.type='checkbox';label.prepend(check);localPapers.append(label);let localFile;
   check.addEventListener('change',run(async()=>{if(check.checked){const blob=await store.getBlob(source.blobHash);localFile=new File([blob],source.fileName||'文献.pdf',{type:blob.type});localFiles.set(source.blobHash,localFile);}else localFiles.delete(source.blobHash);syncFiles();}),{signal:controller.signal});
  }
  if(!seen.size)localPapers.append(el('p','本机尚无已归档文献原件。'));
  const network=inputField(form,'允许检索来源及必要参考文献');network.type='checkbox';
  const consent=inputField(form,'同意发送所选材料及必要术语摘要，用于本次模型生成');consent.type='checkbox';consent.required=true;
  form.append(el('small','原件长期保存在你的浏览器；本次所选材料会临时发送至生成服务器及模型服务。任务临时材料按期限清理，未授权的整库资料和批注不发送。'));
  const submit=el('button','开始生成');submit.type='submit';submit.disabled=session.generationEnabled===false;if(submit.disabled)report('新生成暂未启用，仍可查看和领取已有任务。');form.append(submit);composer.append(form);
  form.addEventListener('input',e=>{if(e.target!==fileInput)draftKey=null;},{signal:controller.signal});
  form.addEventListener('submit',e=>{e.preventDefault();run(async()=>{
   if(session.generationEnabled===false)throw Error('新生成暂未启用，仍可查看和领取已有任务。');if(!consent.checked)throw Error('请先确认本次材料发送范围。');
   const docs=await describeFiles(selectedFiles);
   draftKey=draftKey||crypto.randomUUID();const termId='term-'+draftKey;const request={request_id:'request-'+draftKey,term:{id:termId,zh:name.value.trim(),en:english.value.trim(),aliases:[],definition:termDefinition.value.trim()},question:definition.value.trim(),sources:[],catalog:[],known_terms:knownTerms,literature_prompted:false,network_allowed:network.checked};
   report('正在提交本次选定材料…');let job=await client.create({kind:'lesson',request,documents:docs,model_allowed:true,network_allowed:network.checked},draftKey);
   if(job.state==='draft')for(let i=0;i<selectedFiles.length;i++){const d=job.uploads[i];if(!d.uploaded){const file=selectedFiles[i];job=await client.upload(job.id,d.id,new Blob([file],{type:docs[i].mime}));}}
   if(job.state==='draft')job=await client.start(job.id,job.version);
   report('任务已提交，可离开本页；稍后从任务列表继续查看。');await follow(job);await list();
  })();},{signal:controller.signal});
 }
 function login(){
  loginArea.replaceChildren();const form=el('form',null,'generation-login'),input=inputField(form,'内测邀请凭证');input.type='password';input.autocomplete='off';input.required=true;const submit=el('button','进入内测');submit.type='submit';form.append(submit);loginArea.append(form,el('small','邀请凭证仅供本人使用；持有同一凭证的设备可读取该凭证下尚未过期的任务。已归档知识仍保存在本浏览器。'));
  form.addEventListener('submit',e=>{e.preventDefault();run(async()=>{await client.login(input.value);input.value='';const s=await client.session();await compose(s);await list();report(s.generationEnabled===false?'内测会话已验证；新生成暂未启用，仍可领取已有结果。':'内测会话已验证。');})()},{signal:controller.signal});
 }
 const ready=(async()=>{let css=document.querySelector('link[data-generation-css]');if(!css){css=el('link');css.rel='stylesheet';css.href=new URL('generation.css',import.meta.url).href;css.dataset.generationCss='';document.head.append(css);}try{const s=await client.session();await compose(s);await list();}catch(e){if(!active())return;if(e.status===401){login();report('请使用管理员提供的内测邀请。');}else{login();report(e.message,true);}}})();
 return {ready,dispose:abort};
}
