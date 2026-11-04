import {openLibrary} from './store.mjs';
import {mountWorks} from './works.mjs';
import {sha256} from './safe-assets.mjs';
import {safeId,fail} from './contract.mjs';
import {mountReader} from './reader.mjs';
import {relationsFor,validateEdges} from './graph.mjs';
import {termURL} from './catalogue.mjs';
import * as operations from './operations.mjs';
import {startFrameworkOrganizer} from './framework-autogroup.mjs';
import {rememberCanvas,returnCanvas} from './canvas-session.mjs';
import {planGraphInverse} from './graph-commands.mjs';

export function parseLibraryRoute(hash){
 const p=new URLSearchParams(String(hash||'').replace(/^#/,'')),id=p.get('term');
 if(id){try{safeId(id);return {view:'term',id,block:p.get('block')||null};}catch{return {view:'list'};}}
 return {view:['works','network','trash','backup','guide','generate'].includes(p.get('view'))?p.get('view'):'list'};
}
export async function libraryContext(siteRoot,environment){return {environment:environment+'-'+(await sha256(new TextEncoder().encode(new URL(siteRoot).pathname))).slice(0,24),libraryId:'personal',owner:null};}
const lean=['terms','sources','works','edges','annotations','assets'];
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(label,fn)=>{const b=el('button',label);b.type='button';b.addEventListener('click',fn);return b;};
const option=(value,label)=>{const o=el('option',label);o.value=value;return o;};
export function mountLibrary({main,siteRoot,environment='local-library-preview',signal,state={},chartHost=null}){
 state={...state,network:returnCanvas(new URL(siteRoot).href,location.hash)||state.network};
 const readingStates=new Map(Object.entries(state.readers||{}).slice(-100));let readerKey=null;
 const rememberReader=()=>{if(reader&&readerKey){readingStates.delete(readerKey);readingStates.set(readerKey,reader.capture());while(readingStates.size>100)readingStates.delete(readingStates.keys().next().value);}return Object.fromEntries(readingStates);};
 const root=main.querySelector('[data-library-root]'),status=main.querySelector('[data-library-status]'),local=new AbortController(),urls=new Set();
 let generation,works,worksState=state.works||{},store,context,organizer,publicContext,viewAbort=new AbortController(),reader,network,networkState=state.network||{},networkReturn=false,worker,workerReady,indexEpoch=0,workerSerial=0,sequence=0,disposed=false,busy=false,pendingDialog,unsubscribe,snapshot,catalogue=[],lastSearch=state.search||'',tag=state.tag||'',activeTermId=null,lastHidden=null;
 const callbacks=new Map();
 const message=(text,error=false)=>{if(disposed)return;status.textContent=text;status.setAttribute('role',error?'alert':'status');};
 const listen=(target,type,fn,options={})=>target.addEventListener(type,fn,{...options,signal:local.signal});
 const dispose=()=>{if(disposed)return;disposed=true;generation?.dispose();works?.dispose();organizer?.dispose();local.abort();viewAbort.abort();reader?.dispose();network?.dispose();worker?.terminate();for(const callback of callbacks.values())callback.reject(Error('页面已离开'));callbacks.clear();pendingDialog?.close();pendingDialog?.remove();unsubscribe?.();signal?.removeEventListener('abort',dispose);for(const url of urls)URL.revokeObjectURL(url);if(store)store.discardStaged().catch(()=>{}).finally(()=>store.close());};
 signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();
 const alive=token=>!disposed&&!local.signal.aborted&&(token===undefined||token===sequence);
 const download=(blob,name)=>{if(!alive())return;const url=URL.createObjectURL(blob);urls.add(url);const a=el('a');a.href=url;a.download=name;main.append(a);a.click();a.remove();setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);},60000);};
 const guarded=fn=>async()=>{if(busy){message('当前操作尚未完成，请先完成或取消。');return;}busy=true;try{await fn();}catch(e){if(alive())message(e.message||'操作失败，已有资料保持不变。',true);}finally{busy=false;}};
 async function confirmAction(title,description,{inputLabel=null,extra=null,confirmText='确认',canConfirm=()=>true}={}){
  if(!alive())return null;const dialog=el('dialog',null,'library-dialog'),heading=el('h2',title),copy=el('p',description),form=el('form');form.method='dialog';dialog.append(heading,copy);let input;
  if(inputLabel){const label=el('label',inputLabel);input=el('input');input.autocomplete='off';label.append(input);dialog.append(label);}if(extra)dialog.append(extra);
  const actions=el('div',null,'library-actions'),cancel=button('取消',()=>dialog.close('cancel')),yes=button(confirmText,()=>{if(canConfirm())dialog.close('yes');});const validate=()=>{yes.disabled=!canConfirm();};dialog.addEventListener('change',validate);dialog.addEventListener('input',validate);validate();actions.append(cancel,yes);dialog.append(actions);main.append(dialog);pendingDialog=dialog;
  return new Promise(resolve=>{const finish=()=>{const result=dialog.returnValue==='yes'?{value:input?.value||''}:null;dialog.remove();if(pendingDialog===dialog)pendingDialog=null;resolve(result);};dialog.addEventListener('close',finish,{once:true});dialog.showModal();cancel.focus();});
 }
 const cancelled=()=>Object.assign(Error('旧检索已取消，资料已更新。'),{code:'CANCELLED'});
 function invalidateIndex(){indexEpoch++;worker?.terminate();worker=null;workerReady=null;for(const callback of callbacks.values())callback.reject(cancelled());callbacks.clear();}
 function updateSavedIndex(changes){if(!changes||changes.deletes.some(d=>d.kind==='terms')){invalidateIndex();return;}if(!workerReady)return;indexEpoch++;const active=worker;workerReady=workerReady.then(()=>{if(!alive()||active!==worker)throw cancelled();return ask('update',{changes});}).catch(e=>{if(active===worker)invalidateIndex();throw e;});workerReady.catch(()=>{});}
 async function save(plan,version=snapshot.version){const next=await store.commit(plan,{expectedVersion:version,signal:local.signal});if(!alive())return;message('已保存到本浏览器。');return next;}
 async function refresh(){if(!alive())return;const value=await store.read(lean);if(!alive())return;snapshot=value;await render();}
 async function exportGraph(){const current=await store.read(['graphViews']);if(!current.records.graphViews.length)return undefined;const r=await fetch(new URL('./official-graph.json',import.meta.url),{signal:local.signal});if(!r.ok)throw Error('官方知识关系尚未缓存，请联网后再导出完整阅读网络。');return r.json();}
 async function changeRelation(edge,status){
  const version=snapshot.version,s=await store.snapshot(),current=s.records.edges.find(e=>e.id===edge.id);
  if(!current||current.status!==edge.status)fail('CONFLICT','此关联已更新，请重新读取后再操作。');
  if(current.status==='dismissed'&&status!=='dismissed'){
   const issues=validateEdges(s.records.edges.map(e=>e.id===edge.id?{...e,status}:e),[...s.records.terms.map(t=>({space:'personal',id:t.id})),...catalogue.map(t=>({space:'official',id:t.id}))]);
   if(issues.length)fail('INVALID_PACKAGE',issues[0].message||'关联目标无效，请核对后再恢复。');
  }
  await save(operations.setEdgeStatus(s,{edgeId:edge.id,status}),version);
  if(!alive())return;lastHidden=status==='dismissed'?{id:edge.id,status:edge.status}:null;await refresh();
 }
 function relationNode(edge){
  const row=el('div',null,'library-relation'),target=edge.target,term=target.space==='personal'?snapshot.records.terms.find(t=>t.id===target.id):catalogue.find(t=>t.id===target.id);row.dataset.edgeId=edge.id;
  const href=termURL(target,catalogue,snapshot.records.terms,siteRoot),label=el(href?'a':'span',term?.zh||target.id);if(href)label.href=href;row.append(el('small',edge.label),label,el('p',edge.reason));
  row.append(el('small',edge.status==='dismissed'?'已隐藏 · 依据保留，可恢复':edge.status==='confirmed'?'已确认 · '+(edge.origin==='user'?'个人判断':'文献关联建议经确认'):'关联建议 · 待确认'));
  if(edge.status==='dismissed'){
   row.append(button('恢复关联',guarded(()=>changeRelation(edge,'suggested'))),button('恢复并确认',guarded(()=>changeRelation(edge,'confirmed'))));
  }else{
   row.append(button(edge.status==='confirmed'?'撤回确认':'确认关联',guarded(()=>changeRelation(edge,edge.status==='confirmed'?'suggested':'confirmed'))));
   row.append(button('隐藏关联',guarded(()=>changeRelation(edge,'dismissed'))));
  }return row;
 }
 function hiddenRelations(ref){
  const edges=ref?(()=>{const r=relationsFor(ref,snapshot.records.edges,{includeDismissed:true});return [...r.outgoing,...r.incoming].filter(e=>e.status==='dismissed');})():snapshot.records.edges.filter(e=>e.status==='dismissed').map(e=>{const row=relationsFor(e.from,[e],{includeDismissed:true}).outgoing[0],from=snapshot.records.terms.find(t=>t.id===e.from.id);return {...row,label:(from?.zh||e.from.id)+' · '+row.label};});
  if(!edges.length)return null;const panel=el('details',null,'library-hidden-relations');panel.append(el('summary','已隐藏关联 · '+edges.length));for(const edge of edges)panel.append(relationNode(edge));return panel;
 }
 function ensureWorker(){if(workerReady)return workerReady;const epoch=indexEpoch,active=new Worker(new URL('search.worker.mjs',import.meta.url),{type:'module'});worker=active;active.onmessage=e=>{if(active!==worker)return;const callback=callbacks.get(e.data.id);if(!callback)return;callbacks.delete(e.data.id);e.data.error?callback.reject(Error(e.data.error.message)):callback.resolve(e.data.result);};active.onerror=()=>{for(const callback of callbacks.values())callback.reject(Error('本地检索未能启动，请重新进入知识库。'));callbacks.clear();};workerReady=(async()=>{const state=await store.snapshot();if(!alive()||epoch!==indexEpoch||worker!==active)throw cancelled();await ask('build',{records:state.records});})().catch(e=>{if(epoch===indexEpoch){active.terminate();worker=null;workerReady=null;}throw e;});return workerReady;}
 function ask(type,payload){return new Promise((resolve,reject)=>{if(!worker||!alive()){reject(cancelled());return;}const id=++workerSerial;callbacks.set(id,{resolve,reject});worker.postMessage({id,type,...payload});});}
 async function searchList(container,query,token){
  if(!query){container.replaceChildren(...cards(snapshot.records.terms.filter(t=>!t.trashed&&(!tag||t.tags.includes(tag)))));return;}
  const epoch=indexEpoch;await ensureWorker();if(epoch!==indexEpoch)throw cancelled();const hits=await ask('search',{query,options:{tag:tag||null,limit:30}});if(!alive(token)||lastSearch!==query||epoch!==indexEpoch)return;
  const rows=hits.map(h=>{const a=el('a',null,'library-card');a.href='#term='+encodeURIComponent(h.termId)+(h.blockId&&!h.blockId.startsWith('source:')?'&block='+encodeURIComponent(h.blockId):'');a.append(el('h2',h.zh));const text=el('p');text.append(document.createTextNode(h.text.slice(Math.max(0,h.start-40),h.start)),el('mark',h.text.slice(h.start,h.end)),document.createTextNode(h.text.slice(h.end,h.end+85)));a.append(text);return a;});container.replaceChildren(...(rows.length?rows:[el('p','没有找到匹配内容，可以换用别名或缩短搜索词。','library-empty')]));
 }
 function cards(terms){return terms.map(t=>{const a=el('a',null,'library-card');a.href='#term='+encodeURIComponent(t.id);a.append(el('h2',t.zh),el('p',t.en,'library-card-en'),el('small',(t.tags||[]).join(' · ')||'个人术语'));return a;});}
 function noteEditor(note,revision,version){
  const details=el('details');details.dataset.annotationEditor=note.id;details.append(el('summary',note.anchorStatus==='needs-location'?'编辑并重新定位':'编辑批注'));const form=el('form'),label=el('label','修改批注'),field=el('textarea');field.rows=3;field.required=true;field.value=note.text;label.append(field);const anchorLabel=el('label','保存到当前修订的小节'),anchor=el('select');anchor.append(option('','整篇科普'));for(const b of revision.lesson.blocks)anchor.append(option(b.id,b.heading));anchor.value=revision.lesson.blocks.some(b=>b.id===note.blockId)?note.blockId:'';anchorLabel.append(anchor);const submit=el('button','保存批注修改');submit.type='submit';form.append(label,anchorLabel,submit);form.addEventListener('submit',e=>{e.preventDefault();guarded(async()=>{const s=await store.snapshot();await save(operations.updateAnnotation(s,{annotationId:note.id,text:field.value,revisionId:revision.id,blockId:anchor.value||null}),version);await refresh();})()},{signal:viewAbort.signal});details.append(form);return details;
 }
 async function importPackage(file,{generated=false}={}){
  const base=await store.snapshot(),{inspectBackup,planRestore}=await import('./archive.mjs');message('正在本机校验备份与文件指纹…');
  try{const inspected=await inspectBackup(file,{stageBlob:store.stageBlob,discardStaged:store.discardStaged,signal:local.signal,onProgress:p=>message('本机校验中 · 已检查 '+(p.files||0)+' 个文件')});if(!alive())return;
   const plan=await planRestore(base,inspected.validated),yes=await confirmAction('确认导入','包含 '+inspected.validated.terms.length+' 个术语、'+inspected.validated.works.length+' 篇文献；新增或保留分支记录 '+plan.writes.length+' 条。同名条目不会自动合并。',{confirmText:'导入并保存'});
   if(!yes){message('已取消导入，原知识库保持不变。');return;}await save(plan,base.version);await refresh();organizer?.schedule();
  }finally{await store.discardStaged();}
 }
 let lastVisualInverse=null;
 async function updatePackage(file){
  const base=await store.snapshot(),{inspectBackup}=await import('./archive.mjs'),{inspectVisualUpdates,planVisualUpdate,describeVisualChange}=await import('./visual-updates.mjs');message('正在本机核对已有修订与更新图示…');
  try{const inspected=await inspectBackup(file,{stageBlob:store.stageBlob,discardStaged:store.discardStaged,signal:local.signal}),report=inspectVisualUpdates(base,inspected.validated),choices=[...report.updates];
   for(const conflict of report.conflicts)for(const termId of conflict.identityCandidates){const term=base.records.terms.find(t=>t.id===termId);choices.push({termId,incomingRevisionId:conflict.incomingRevisionId,currentRevisionId:term.currentRevisionId,bodyChanged:true,branch:true});}
   if(!choices.length){message(report.conflicts.length?'来源或身份有冲突，未改动现有科普。':report.unchanged.length?'图示与当前修订一致，无需重复更新。':'没有匹配的已有术语，请使用导入功能。',!!report.conflicts.length);return;}
   const extra=el('div'),chooseLabel=el('label','选择已有术语与新修订'),choose=el('select'),ambiguous=choices.some(item=>item.branch);if(ambiguous)choose.append(option('','请选择要更新的分支（不会自动选择）'));
   for(const [i,item] of choices.entries())choose.append(option(String(i),(base.records.terms.find(t=>t.id===item.termId)?.zh||item.termId)+' · '+item.termId));chooseLabel.append(choose);const bodyLabel=el('label','已阅读下方变化，我同意一并采用正文、公式或题目的修订'),bodyCheck=el('input'),preview=el('section');preview.dataset.visualChangePreview='';preview.className='visual-change-preview';bodyCheck.type='checkbox';bodyLabel.prepend(bodyCheck);extra.append(chooseLabel,preview,bodyLabel);
   const selectedChoice=()=>choose.value===''?null:choices[Number(choose.value)];let changed=false;
   function refreshPreview(){preview.replaceChildren();bodyCheck.checked=false;const choice=selectedChoice();changed=false;if(!choice){bodyLabel.hidden=true;preview.append(el('p','先选择明确的目标分支，再核对当前与新修订。'));return;}const d=describeVisualChange(base,inspected.validated,choice);preview.append(el('p','术语身份：'+d.termId),el('p','当前修订：'+d.currentRevisionId),el('p','将采用：'+d.incomingRevisionId));changed=d.changes.length>0;bodyLabel.hidden=!changed;if(!changed)preview.append(el('p','教学正文未变化，仅更新图示或图注。'));for(const change of d.changes){const section=el('details');section.append(el('summary',change.title+' · 内容变化'));if(change.before===change.after)section.append(el('p','文字相同，结构或引用标记已更新。'));else section.append(el('strong','当前内容'),el('pre',change.before||'（无）'),el('strong','新修订内容'),el('pre',change.after||'（无）'));preview.append(section);}}
   choose.addEventListener('change',refreshPreview);refreshPreview();
   const yes=await confirmAction('更新已有科普','保留旧修订、原件、标签与批注。请核对目标身份和内容差异；旧批注仍绑定原修订。'+report.unchanged.length+' 个术语无需更新。',{extra,confirmText:'确认采用此修订',canConfirm:()=>!!selectedChoice()&&(!changed||bodyCheck.checked)});if(!yes){message('已取消更新，当前科普保持不变。');return;}
   const choice=choices[Number(choose.value)],planned=await planVisualUpdate(base,inspected.validated,{...choice,expectedCurrentRevisionId:choice.currentRevisionId,allowBodyChange:bodyCheck.checked});await save(planned.plan,base.version);lastVisualInverse=planned.inverse;await refresh();message('已采用更新图示；旧修订、原件与批注均保留。可撤销本次更新。');
  }finally{await store.discardStaged();}
 }
 async function render(){
  const token=++sequence;generation?.dispose();generation=null;if(works){worksState=works.capture();works.dispose();works=null;}if(network){networkState=network.capture();network.dispose();network=null;}rememberReader();viewAbort.abort();viewAbort=new AbortController();reader?.dispose();reader=null;readerKey=null;const route=parseLibraryRoute(location.hash),records=snapshot.records,content=el('div',null,'library-content');main.classList.toggle('library-network-page',route.view==='network');
  const nav=el('nav',null,'library-tabs');nav.setAttribute('aria-label','知识库分区');for(const [view,label] of [['list','术语'],['works','文献'],['network','知识关系'],['trash','回收区'],['backup','备份与设置'],['guide','使用指南'],...(main.dataset.generationApi?[['generate','生成科普']]:[])]){const a=el('a',label);a.href=view==='list'?'#view=list':'#view='+view;if(route.view===view||route.view==='term'&&view==='list')a.setAttribute('aria-current','page');nav.append(a);}content.append(nav);
  if(lastHidden){const previous=lastHidden,edge=records.edges.find(e=>e.id===previous.id&&e.status==='dismissed');if(edge){const undo=el('div',null,'library-relation-undo');undo.setAttribute('role','status');undo.append(el('span','关联已隐藏，仍可恢复。'),button('撤销隐藏',guarded(()=>changeRelation(edge,previous.status))));content.append(undo);}else lastHidden=null;}
  if(lastVisualInverse){const undo=el('div',null,'library-relation-undo'),action=button('撤销本次图示更新',guarded(async()=>{const s=await store.snapshot(),planned=planGraphInverse(s,lastVisualInverse);await save(planned.plan,s.version);lastVisualInverse=null;await refresh();}));action.dataset.visualUpdateUndo='';undo.append(el('span','图示已更新，旧修订和批注保留。'),action);content.append(undo);}
  if(route.view==='list'){
   const controls=el('div',null,'library-controls'),label=el('label','查找我的术语'),input=el('input');input.id='library-search';input.type='search';input.value=lastSearch;input.placeholder='名称、别名或正文';label.append(input);const tagLabel=el('label','标签'),tags=el('select');tags.append(option('','全部标签'));for(const t of [...new Set(records.terms.flatMap(t=>t.tags))])tags.append(option(t,t));tags.value=tag;tagLabel.append(tags);controls.append(label,tagLabel);content.append(controls);
   const grid=el('div',null,'library-grid');content.append(grid);const active=records.terms.filter(t=>!t.trashed);if(!active.length)grid.append(el('p','还没有个人术语。点击“导入科普包”，保存你的第一份科普、图示与文献。','library-empty'));else grid.append(...cards(active.filter(t=>!tag||t.tags.includes(tag))));
   let timer;input.addEventListener('input',()=>{clearTimeout(timer);lastSearch=input.value.trim();timer=setTimeout(()=>searchList(grid,lastSearch,token).catch(e=>{if(e.code!=='CANCELLED')message(e.message,true);}),160);},{signal:viewAbort.signal});tags.addEventListener('change',()=>{tag=tags.value;searchList(grid,lastSearch,token).catch(e=>{if(e.code!=='CANCELLED')message(e.message,true);});},{signal:viewAbort.signal});viewAbort.signal.addEventListener('abort',()=>clearTimeout(timer),{once:true});
   if(lastSearch)queueMicrotask(()=>searchList(grid,lastSearch,token).catch(e=>{if(e.code!=='CANCELLED')message(e.message,true);}));
  }else if(route.view==='term'){
   const term=records.terms.find(t=>t.id===route.id&&!t.trashed);if(!term)content.append(el('p','该术语不在当前库中，或已进入回收区。','library-empty'));else{
    const back=el('a',networkReturn?'← 返回知识画布':'← 我的术语');back.href=networkReturn?'#view=network&framework='+encodeURIComponent(networkState.frameworkId||''):'#view=list';content.append(back);const revision=term.currentRevisionId?await store.getRecord('revisions',term.currentRevisionId):null;if(!alive(token))return;
    if(!revision)content.append(el('h2',term.zh),el('small','个人笔记 · 待补充完整科普'),el('p',term.anchor?.definition||'尚未填写释义。'));else{
     const layout=el('div',null,'library-reading-layout'),article=el('div'),aside=el('aside',null,'library-aside');layout.append(article,aside);content.append(layout);
     readerKey=revision.id;const current=mountReader(article,{revision,chartHost,state:readingStates.get(readerKey)||{},sources:records.sources,works:records.works,signal:viewAbort.signal,catalogue:[...catalogue,...records.terms.filter(t=>!t.trashed).map(t=>({...t,space:'personal',published:true,url:new URL('library/index.html#term='+encodeURIComponent(t.id),siteRoot).href}))],resolveAsset:async role=>{const a=records.assets.find(a=>revision.assetIds.includes(a.id)&&a.role===role)||records.assets.find(a=>revision.assetIds.includes(a.id));return a?store.getBlob(a.blobHash):null;}});reader=current;await current.ready;if(!alive(token))return;
     const review=revision.lesson.provenance?.human_scientific_review||revision.provenance?.human_scientific_review;aside.append(el('small',review==='passed'?'已人工审阅':'个人生成内容 · 待科学审阅'));
     const {mountReadingNavigation}=await import('./reading-layout.mjs');if(!alive(token))return;mountReadingNavigation(aside,article,{lesson:revision.lesson,signal:viewAbort.signal,hrefFor:id=>'#term='+encodeURIComponent(term.id)+'&block='+encodeURIComponent(id)});
     aside.append(el('h2','知识关联'));const related=relationsFor({space:'personal',id:term.id},records.edges);for(const e of [...related.outgoing,...related.incoming])aside.append(relationNode(e));if(!related.outgoing.length&&!related.incoming.length)aside.append(el('p','尚无已保存的关联。'));
     const hidden=hiddenRelations({space:'personal',id:term.id});if(hidden)aside.append(hidden);
     const notes=el('section',null,'library-notes');notes.append(el('h2','我的批注'));for(const n of records.annotations.filter(n=>n.termId===term.id)){const note=el('div',null,'library-note');note.append(el('p',n.text),el('small',n.anchorStatus==='needs-location'?'保留于旧修订 · 待重新定位':n.revisionId===revision.id?'本修订批注':'旧修订批注'));note.append(noteEditor(n,revision,snapshot.version));notes.append(note);}const form=el('form'),label=el('label','批注内容'),text=el('textarea');text.required=true;text.rows=3;label.append(text);const blockLabel=el('label','关联小节'),block=el('select');block.append(option('','整篇科普'));for(const b of revision.lesson.blocks)block.append(option(b.id,b.heading));blockLabel.append(block);const submit=el('button','保存批注');submit.type='submit';form.append(label,blockLabel,submit);const viewedVersion=snapshot.version;form.addEventListener('submit',e=>{e.preventDefault();guarded(async()=>{const state=await store.snapshot();await save(operations.addAnnotation(state,{termId:term.id,revisionId:revision.id,blockId:block.value||null,text:text.value}),viewedVersion);await refresh();})();},{signal:viewAbort.signal});notes.append(form);article.append(notes);
     const versions=await store.read(['revisions']);if(!alive(token))return;const history=el('details');history.append(el('summary','已保存修订 · '+versions.records.revisions.filter(r=>r.termId===term.id).length));for(const old of versions.records.revisions.filter(r=>r.termId===term.id))history.append(el('p',old.id+(old.id===revision.id?'（当前）':'（历史，完整备份中保留）')));article.append(history);
    }
    const meta=el('details');meta.append(el('summary','别名与标签'));const form=el('form'),aliases=el('input'),tags=el('input');aliases.value=term.aliases.join('，');tags.value=term.tags.join('，');for(const [name,input] of [['别名（逗号分隔）',aliases],['标签（逗号分隔）',tags]]){const l=el('label',name);l.append(input);form.append(l);}const submit=el('button','保存设置');submit.type='submit';form.append(submit);form.addEventListener('submit',e=>{e.preventDefault();guarded(async()=>{const s=await store.snapshot(),split=v=>v.split(/[,，]/).map(x=>x.trim()).filter(Boolean);await save(operations.updateTermMeta(s,{termId:term.id,aliases:split(aliases.value),tags:split(tags.value)}));await refresh();})();},{signal:viewAbort.signal});meta.append(form);content.append(meta,button('移入回收区',guarded(async()=>{const s=await store.snapshot();await save(operations.trashTerm(s,term.id));location.hash='view=list';})));
   }
  }else if(route.view==='works'){
   const files=new Set(records.sources.map(s=>s.blobHash).filter(Boolean));content.append(el('p',records.works.length+' 篇文献 · '+files.size+' 份不同原件','library-description'));
   const workState=await store.read(['revisions']);if(!alive(token))return;const area=el('section');content.append(area);
   works=mountWorks(area,{records:{...records,revisions:workState.records.revisions},signal:viewAbort.signal,state:worksState,
    onDownload:source=>guarded(async()=>download(await store.getBlob(source.blobHash),source.fileName||'文献.pdf'))(),
    onDelete:source=>guarded(async()=>{const s=await store.snapshot(),impact=operations.deleteOriginal(s,{sourceId:source.id,removeExtracted:false}).impact,extra=el('label','同时删除本来源的提取片段'),check=el('input');check.type='checkbox';extra.prepend(check);const shared=s.records.sources.filter(v=>v.id!==source.id&&v.blobHash&&v.blobHash===source.blobHash).length;const yes=await confirmAction('删除原件','影响 '+impact.length+' 份科普修订；保留书目。'+(shared?'另有 '+shared+' 条来源仍引用相同文件，文件将为它们保留。':'')+'旧导出备份不受影响。',{extra,confirmText:'确认删除'});if(yes){await save(operations.deleteOriginal(s,{sourceId:source.id,removeExtracted:check.checked}));await store.discardStaged();await refresh();}})()
   });
  }else if(route.view==='network'){
   networkReturn=false;const area=el('div');content.append(area);root.replaceChildren(content);
   const {mountNetwork}=await import('./network-page.mjs');if(!alive(token))return;
   network=mountNetwork(area,{store,catalogue,siteRoot,signal:viewAbort.signal,state:networkState,organizer,onMessage:message,onRead:(node,captured)=>{networkState=captured;if(node.ref.space==='personal'){networkReturn=true;location.hash='term='+encodeURIComponent(node.ref.id);}else if(node.readingURL){rememberCanvas(new URL(siteRoot).href,captured);const target=new URL(node.readingURL,siteRoot);target.searchParams.set('from-library',captured.frameworkId);const link=el('a');link.href=target.href;main.append(link);link.click();link.remove();}}});await network.ready;if(!alive(token))return;
  }else if(route.view==='generate'){
   if(!main.dataset.generationApi){content.append(el('p','当前站点尚未启用在线生成；已有科普仍可导入和阅读。'));}else{
    const [{createGenerationClient},{mountGeneration}]=await Promise.all([import('./generation-client.mjs'),import('./generation-page.mjs')]);if(!alive(token))return;
    const client=createGenerationClient({apiRoot:new URL(main.dataset.generationApi,siteRoot),signal:viewAbort.signal});generation=mountGeneration({root:content,client,store,catalogue,chartHost,signal:viewAbort.signal,onImport:file=>importPackage(file,{generated:true})});
   }
  }else if(route.view==='guide'){
   const {mountGuide}=await import('./guide.mjs');if(!alive(token))return;mountGuide(content,{onlineGeneration:!!main.dataset.generationApi});
  }else if(route.view==='trash'){
   for(const t of records.terms.filter(t=>t.trashed)){const row=el('div',null,'library-work');row.append(el('h2',t.zh),button('恢复',guarded(async()=>{const s=await store.snapshot();await save(operations.restoreTerm(s,t.id));await refresh();})),button('永久删除',guarded(async()=>{const yes=await confirmAction('永久删除术语','将删除此术语的修订与批注；其他术语仍引用的文献会保留。旧备份不受影响。',{confirmText:'永久删除'});if(yes){const s=await store.snapshot();await save(operations.purgeTerm(s,t.id));await store.discardStaged();await refresh();}})));content.append(row);}if(!records.terms.some(t=>t.trashed))content.append(el('p','回收区为空。','library-empty'));
  }else{
   content.append(el('h2','保存一份可迁移的知识库'),el('p','本机保存属于当前浏览器和当前网站地址。清理网站数据、更换浏览器或设备后，需要用完整备份恢复。','library-description'));
   const controls=el('div',null,'library-actions');controls.append(button('私人完整备份（含原文）',guarded(async()=>{message('正在本机生成完整备份…');const {exportBackup}=await import('./archive.mjs');download(await exportBackup(await store.snapshot(),store.getBlob,{signal:local.signal,catalogue}),'我的知识库-完整备份.zip');message('已生成完整备份并交给浏览器下载；请确认文件已保存。');})));
   const originals=el('input');originals.type='checkbox';const l=el('label','阅读导出附带原件');l.prepend(originals);controls.append(l,button('Markdown 阅读导出',guarded(async()=>{const {exportReading}=await import('./archive.mjs');download(await exportReading(await store.snapshot(),store.getBlob,{includeOriginals:originals.checked,signal:local.signal,catalogue,officialGraph:await exportGraph()}),'我的知识库-阅读导出.zip');message('已生成阅读导出；它不含私有证据，不能代替完整备份。');})));content.append(controls);
   const md=el('input');md.type='file';md.accept='.md,text/markdown';const mdLabel=el('label','导入外部 Markdown 为个人笔记');mdLabel.append(md);md.addEventListener('change',()=>guarded(async()=>{if(!md.files[0])return;if(md.files[0].size>2*1024*1024)fail('LIMIT','笔记超过2 MiB，请分为较小文件。');const {importMarkdown}=await import('./markdown.mjs'),note=await importMarkdown(await md.files[0].text(),{fileName:md.files[0].name}),s=await store.snapshot();await save({writes:[{kind:'annotations',id:note.id,value:note}],deletes:[],blobRefs:[],impact:[]},s.version);await refresh();})(),{signal:viewAbort.signal});content.append(mdLabel);for(const n of records.annotations.filter(n=>!n.termId)){const box=el('details');box.append(el('summary',n.fileName||'外部笔记'),el('pre',n.text,'library-external-note'));content.append(box);}
   content.append(button('请求浏览器保留本机资料',guarded(async()=>{const allowed=await navigator.storage?.persist?.();message(allowed?'浏览器已同意持久保存；仍建议定期导出备份。':'浏览器未授予持久保存，请定期导出备份。');})));
   content.append(button('启用离线阅读',guarded(async()=>{message('正在校验并缓存离线阅读资源…');const {prepareOffline}=await import('./offline.mjs'),scope=new URL('library/',siteRoot),response=await fetch(new URL('offline-manifest.json',scope),{signal:local.signal});if(!response.ok)throw Error('离线清单未能读取');const result=await prepareOffline({scope,manifest:await response.json(),signal:local.signal});message(result.message,result.state!=='ready');})));
   const deletion=el('div',null,'library-danger');deletion.append(el('h2','完整删除本库'),el('p','只删除当前环境的本机知识库，不删除官方收藏或旧导出文件。'),button('删除全部本机知识',guarded(async()=>{const first=await confirmAction('删除全部本机知识','此操作会删除当前库的所有术语、批注、证据和未共享原件。',{confirmText:'继续确认'});if(!first)return;const second=await confirmAction('再次确认','输入 personal 确认完整删除本库。',{inputLabel:'本库标识',confirmText:'完整删除'});if(!second)return;const s=await store.snapshot();s.libraryId=context.libraryId;await save(operations.purgeLibrary(s,{confirmLibraryId:second.value}));await store.discardStaged();await refresh();})));content.append(deletion);
  }
  if(!alive(token))return;root.replaceChildren(content);activeTermId=route.view==='term'?route.id:null;if(route.block)requestAnimationFrame(()=>{if(alive(token))document.getElementById(route.block)?.scrollIntoView({block:'start'});});
 }
 const ready=(async()=>{
  if(disposed)return false;context=await libraryContext(siteRoot,environment);if(disposed)return false;store=await openLibrary(context);if(disposed){store.close();return false;}
  const response=await fetch(new URL('catalogue.json',import.meta.url),{signal:local.signal});if(!response.ok)throw Error('官方目录未能读取');catalogue=(await response.json()).terms.map(t=>({...t,space:'official'}));
  let onlineTransport=null;if(main.dataset.generationApi){const [{createGenerationClient},{createOnlineFrameworkTransport}]=await Promise.all([import('./generation-client.mjs'),import('./online-framework-transport.mjs')]);if(disposed)return false;onlineTransport=createOnlineFrameworkTransport(createGenerationClient({apiRoot:new URL(main.dataset.generationApi,siteRoot),signal:local.signal}));}
  organizer=startFrameworkOrganizer({store,transport:onlineTransport,signal:local.signal,getPublicContext:async()=>{if(!publicContext){const response=await fetch(new URL('official-graph.json',import.meta.url),{signal:local.signal});if(!response.ok)throw Error('官方定义暂未缓存，私人资料仍可阅读。');publicContext=await response.json();}return {catalogue,officialGraph:publicContext};},onState:value=>{network?.updateOrganizer(value);if(value.message)message(value.message,value.status==='failed');},onApplied:()=>network?.refreshModel()});await organizer.ready;
  const input=main.querySelector('[data-library-import]');listen(input,'change',()=>{const file=input.files[0];input.value='';if(file)guarded(()=>importPackage(file))();});
  const updateInput=main.querySelector('[data-library-update]');if(updateInput)listen(updateInput,'change',()=>{const file=updateInput.files[0];updateInput.value='';if(file)guarded(()=>updatePackage(file))();});
  listen(window,'hashchange',()=>{const route=parseLibraryRoute(location.hash);if(route.view==='term'&&route.id===activeTermId){if(route.block)document.getElementById(route.block)?.scrollIntoView({block:'start'});return;}refresh().catch(e=>{if(e.code!=='CANCELLED')message(e.message,true);});});
  unsubscribe=store.subscribe(event=>{if(!alive())return;updateSavedIndex(event.changes);root.querySelector('.library-grid')?.replaceChildren(el('p','资料已更新，请重新搜索或读取。'));message('本库已更新。未保存的输入会保留；需要时点击“重新读取”。');});
  listen(main.querySelector('[data-library-refresh]'),'click',()=>guarded(async()=>{invalidateIndex();await refresh();message('已读取最新保存版本。');})());
  await refresh();message('资料仅保存在本浏览器。请定期导出完整备份。');return true;
 })().catch(e=>{if(alive())message(e.message,true);throw e;});
 return {ready,dispose,capture:()=>({hash:location.hash,search:lastSearch,tag,readers:rememberReader(),works:works?.capture()||worksState,network:network?.capture()||networkState})};
}
