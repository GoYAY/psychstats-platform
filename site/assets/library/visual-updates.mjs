import {fail,upgradePackage,validateStoredRecords} from './contract.mjs';
import {canonical,frameworkInputHash} from './framework-summary.mjs';
const normalize=v=>String(v||'').normalize('NFKC').trim().toLowerCase();
const workKey=w=>w?.doi?'doi:'+normalize(w.doi):w?'title:'+normalize(w.title):'';
const sourceKey=(s,records)=>workKey(records.works.find(w=>w.id===s?.workId))+'|'+(s?.scope||'');
function sourceChain(r,records){return [...new Set((r?.sourceIds||[]).map(id=>sourceKey(records.sources.find(s=>s.id===id),records)))].sort();}
function body(r,records,peer,peerRecords){const l=r?.lesson||{},normalizeTargets=(items,peerItems)=>items.map(original=>{const item=structuredClone(original);if(!item.target)return item;const other=peerItems.find(v=>v.target===item.target&&(!item.id||v.id===item.id));const space=item.targetSpace||r?.targetSpaces?.[item.target]||[...records.terms,...peerRecords.terms].some(t=>t.id===item.target)&&'personal'||other?.targetSpace||peer?.targetSpaces?.[item.target];if(space)item.targetSpace=space;return item;});return {blocks:l.blocks,formulas:l.formulas,quiz:l.quiz,glossary:normalizeTargets(l.glossary||[],peer?.lesson.glossary||[]),relations:normalizeTargets(l.relations||[],peer?.lesson.relations||[]),limitations:l.limitations||[]};}
function visual(r,records){return {visual:r?.lesson.visual||null,assets:(r?.assetIds||[]).map(id=>records.assets.find(a=>a.id===id)).filter(Boolean).map(a=>({role:a.role,hash:a.blobHash,alt:a.alt||''})).sort((a,b)=>a.role.localeCompare(b.role)||a.hash.localeCompare(b.hash))};}
const sameChain=(a,ar,b,br)=>canonical(sourceChain(a,ar))===canonical(sourceChain(b,br));
export function describeVisualChange(snapshot,incoming,{termId,incomingRevisionId}){
 const records=snapshot.records,term=records.terms.find(t=>t.id===termId),old=records.revisions.find(r=>r.id===term?.currentRevisionId),next=incoming.revisions.find(r=>r.id===incomingRevisionId);if(!term||!old||!next)fail('CONFLICT','修订预览目标已变化。');
 const before=body(old,records,next,incoming),after=body(next,incoming,old,records),changes=[];
 const text=block=>(block?.paragraphs||[]).map(p=>p.text).join('\n');
 for(const id of new Set([...(before.blocks||[]).map(b=>b.id),...(after.blocks||[]).map(b=>b.id)])){const a=before.blocks?.find(b=>b.id===id),b=after.blocks?.find(b=>b.id===id);if(canonical(a)!==canonical(b))changes.push({section:id,title:b?.heading||a?.heading||id,before:text(a),after:text(b)});}
 const readable={formulas:v=>(v||[]).map(f=>f.latex).join('\n'),quiz:v=>v?[v.question,...(v.options||[]).map(o=>o.text+'：'+o.explanation),'正确选项：'+v.correct_option].join('\n'):'',glossary:v=>(v||[]).map(g=>g.term+'：'+g.explanation+(g.target?' → '+g.target:'' )).join('\n'),relations:v=>(v||[]).map(r=>r.type+' → '+r.target+'：'+r.reason).join('\n'),limitations:v=>(v||[]).map(x=>typeof x==='string'?x:x.text||x.description||'说明已更新').join('\n')},titles={formulas:'公式',quiz:'理解检验',glossary:'辅助词释义',relations:'知识关系',limitations:'适用说明'};
 for(const [section,render] of Object.entries(readable))if(canonical(before[section])!==canonical(after[section]))changes.push({section,title:titles[section],before:render(before[section]),after:render(after[section])});
 return {termId,title:term.zh,currentRevisionId:old.id,incomingRevisionId:next.id,changes};
}
export function inspectVisualUpdates(snapshot,incoming){
 const records=snapshot.records,updates=[],unchanged=[],conflicts=[];
 for(const term of incoming.terms.filter(t=>!t.trashed&&t.currentRevisionId)){
  const revision=incoming.revisions.find(r=>r.id===term.currentRevisionId),exact=records.terms.find(t=>!t.trashed&&t.id===term.id),candidates=exact?[exact]:records.terms.filter(t=>!t.trashed&&[t.zh,t.en,...t.aliases||[]].some(n=>n&&[term.zh,term.en,...term.aliases||[]].some(v=>v&&normalize(v)===normalize(n))));
  if(!candidates.length)continue;
  const identityCandidates=candidates.filter(t=>sameChain(records.revisions.find(r=>r.id===t.currentRevisionId),records,revision,incoming)).map(t=>t.id);
  if(!exact||!identityCandidates.includes(exact.id)){conflicts.push({incomingRevisionId:revision.id,identityCandidates,reason:identityCandidates.length?'请明确选择要更新的已有术语分支。':'来源链不同，未自动更新。'});continue;}
  const old=records.revisions.find(r=>r.id===exact.currentRevisionId),before=visual(old,records),after=visual(revision,incoming),bodyChanged=canonical(body(old,records,revision,incoming))!==canonical(body(revision,incoming,old,records));
  if(canonical(before)===canonical(after)&&!bodyChanged){unchanged.push({termId:exact.id,currentRevisionId:old.id});continue;}
  updates.push({termId:exact.id,currentRevisionId:old?.id||null,incomingRevisionId:revision.id,assetHashes:after.assets.map(a=>a.hash),bodyChanged,identityCandidates:[exact.id]});
 }
 return {updates,unchanged,conflicts};
}
export async function planVisualUpdate(snapshot,incoming,{termId,incomingRevisionId,expectedCurrentRevisionId,allowBodyChange=false}){
 const records=snapshot.records;incoming=upgradePackage(incoming);validateStoredRecords(incoming);
 const oldTerm=records.terms.find(t=>t.id===termId&&!t.trashed),old=records.revisions.find(r=>r.id===oldTerm?.currentRevisionId),source=incoming.revisions.find(r=>r.id===incomingRevisionId),plan={writes:[],deletes:[],blobRefs:[],impact:[]},inverse={records:[]};
 if(!oldTerm||!old||!source||oldTerm.currentRevisionId!==expectedCurrentRevisionId)fail('CONFLICT','当前修订已变化或目标不存在，请重新读取更新预览。');
 if(!sameChain(old,records,source,incoming))fail('CONFLICT','来源链不一致，不能把它作为已有图示修订更新。');
 const bodyChanged=canonical(body(old,records,source,incoming))!==canonical(body(source,incoming,old,records));if(bodyChanged&&!allowBodyChange)fail('CONFLICT','新修订包含正文、公式或题目变化，请先明确允许该变化。');
 if(canonical(visual(old,records))===canonical(visual(source,incoming))&&!bodyChanged)return {plan,inverse,summary:{unchanged:true,termId}};
 const put=(kind,value)=>{const current=records[kind].find(v=>v.id===value.id);if(current){if(canonical(current)!==canonical(value))fail('CONFLICT','更新资源身份冲突，未覆盖已有资料。');return;}plan.writes.push({kind,id:value.id,value});};
 const sourceMap=new Map();for(const id of source.sourceIds){const input=incoming.sources.find(s=>s.id===id),targetSources=old.sourceIds.map(id=>records.sources.find(s=>s.id===id)).filter(s=>sourceKey(s,records)===sourceKey(input,incoming)),target=targetSources.find(s=>s.id===id)||targetSources.length===1&&targetSources[0];if(!target||target.extractedStatus==='deleted')fail('CONFLICT','来源匹配不唯一或该来源片段已删除，不能静默恢复。');sourceMap.set(id,target.id);}
 const digest=(await frameworkInputHash({termId,incomingRevisionId,lesson:source.lesson,assets:visual(source,incoming).assets})).slice(0,32),revision=structuredClone(source);revision.id='visual-revision-'+digest;revision.termId=termId;revision.lesson.term.id=termId;revision.sourceIds=[...new Set(source.sourceIds.map(id=>sourceMap.get(id)))];revision.sourceMap=Object.fromEntries(Object.entries(source.sourceMap).map(([local,id])=>[local,sourceMap.get(id)]));
 const assetMap=new Map();for(const id of source.assetIds){const a=incoming.assets.find(a=>a.id===id);if(!a)fail('INVALID_PACKAGE','更新图示文件缺失。');const existing=records.assets.find(v=>v.blobHash===a.blobHash&&v.role===a.role&&v.alt===a.alt&&v.mime===a.mime&&v.size===a.size);if(existing){assetMap.set(id,existing.id);continue;}const hash=(await frameworkInputHash(a)).slice(0,32),value={...a,id:'visual-asset-'+hash,path:'figures/visual-update-'+hash+'.'+a.path.split('.').pop()};put('assets',value);assetMap.set(id,value.id);}
 revision.assetIds=source.assetIds.map(id=>assetMap.get(id));revision.evidenceIds=[];
 for(const [i,id] of source.evidenceIds.entries()){const e=incoming.evidence.find(e=>e.id===id),sourceId=sourceMap.get(e?.sourceId);if(!e||!sourceId)fail('INVALID_PACKAGE','更新证据来源缺失。');const existing=records.evidence.filter(v=>v.sourceId===sourceId&&v.status!=='deleted');if(!existing.some(v=>canonical(v.data)===canonical(e.data)))fail('CONFLICT','更新要求不同或已删除的原文片段，请先核对资料。');const value={...structuredClone(e),id:'visual-evidence-'+digest+'-'+i,revisionId:revision.id,sourceId};put('evidence',value);revision.evidenceIds.push(value.id);}
 put('revisions',revision);const nextTerm={...structuredClone(oldTerm),currentRevisionId:revision.id};plan.writes.push({kind:'terms',id:termId,value:nextTerm});
 const next=structuredClone(records);for(const w of plan.writes){const before=records[w.kind].find(v=>v.id===w.id)||null;inverse.records.push({kind:w.kind,id:w.id,before:structuredClone(before),after:structuredClone(w.value)});next[w.kind]=[...next[w.kind].filter(v=>v.id!==w.id),w.value];}validateStoredRecords(next);plan.blobRefs=[...new Set(plan.writes.filter(w=>w.kind==='assets').map(w=>w.value.blobHash))];plan.impact=[{termId,fromRevisionId:old.id,toRevisionId:revision.id,bodyChanged}];
 return {plan,inverse,summary:{termId,fromRevisionId:old.id,toRevisionId:revision.id,incomingRevisionId,bodyChanged,addedAssets:plan.writes.filter(w=>w.kind==='assets').length}};
}
