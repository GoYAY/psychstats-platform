import {fail,safeId,text,COLLECTIONS,validateStoredRecords} from './contract.mjs';
const plan=()=>({writes:[],deletes:[],blobRefs:[],impact:[]});
const get=(s,k,id)=>{const v=s.records[k].find(r=>r.id===id);if(!v)fail('INVALID_PACKAGE','找不到相应记录，请刷新后重试。');return v;};
const write=(p,kind,value)=>p.writes.push({kind,id:value.id,value:structuredClone(value)});
export function addAnnotation(s,{termId,revisionId,blockId,text:value}){const t=get(s,'terms',termId),r=get(s,'revisions',revisionId);if(r.termId!==t.id||blockId&&!r.lesson.blocks.some(b=>b.id===blockId))fail('INVALID_PACKAGE','批注定位与修订不一致。');text(value,{max:30000});const p=plan();write(p,'annotations',{id:'note-'+crypto.randomUUID(),termId,revisionId,blockId,text:value,origin:'user',anchorStatus:'located'});return p;}
export function updateAnnotation(s,{annotationId,text:value,revisionId,blockId}){const original=get(s,'annotations',annotationId),r=get(s,'revisions',revisionId);text(value,{max:30000});if(r.termId!==original.termId||blockId&&!r.lesson.blocks.some(b=>b.id===blockId))fail('INVALID_PACKAGE','请选择该术语有效的修订与小节。');const history=[...original.anchorHistory||[]];if(original.revisionId!==revisionId||original.blockId!==blockId)history.push({revisionId:original.revisionId,blockId:original.blockId});const p=plan();write(p,'annotations',{...original,text:value,revisionId,blockId,anchorStatus:'located',anchorHistory:history});return p;}
export function updateTermMeta(s,{termId,aliases,tags}){const t=get(s,'terms',termId),p=plan();for(const v of [aliases,tags])if(!Array.isArray(v)||v.length>100||v.some(x=>typeof x!=='string'||x.length>120))fail('INVALID_PACKAGE','别名和标签需为简短文字列表。');write(p,'terms',{...t,aliases:[...new Set(aliases)],tags:[...new Set(tags)]});return p;}
export function addRevision(s,{termId,revision}){
 const t=get(s,'terms',termId),p=plan();safeId(revision.id);if(s.records.revisions.some(r=>r.id===revision.id)||revision.termId!==termId)fail('CONFLICT','新修订需要独立编号和相同术语身份。');
 const newRevision=structuredClone(revision);newRevision.evidenceIds=revision.evidenceIds.map(id=>{const old=get(s,'evidence',id);if(!revision.sourceIds.includes(old.sourceId))fail('INVALID_PACKAGE','新修订的来源与证据不一致。');const item={...structuredClone(old),id:'ev-'+crypto.randomUUID(),revisionId:revision.id};write(p,'evidence',item);return item.id;});
 write(p,'revisions',newRevision);write(p,'terms',{...t,currentRevisionId:revision.id});
 for(const n of s.records.annotations.filter(n=>n.termId===termId&&n.blockId&&!revision.lesson.blocks.some(b=>b.id===n.blockId)))write(p,'annotations',{...n,anchorStatus:'needs-location'});
 const records=structuredClone(s.records);for(const w of p.writes){records[w.kind]=records[w.kind].filter(v=>v.id!==w.id);records[w.kind].push(w.value);}validateStoredRecords(records);return p;
}
export function setEdgeStatus(s,{edgeId,status}){if(!['suggested','confirmed','dismissed'].includes(status))fail('INVALID_PACKAGE','关联状态无效');const p=plan();write(p,'edges',{...get(s,'edges',edgeId),status});return p;}
const recycle=(s,id,trashed)=>{const p=plan();write(p,'terms',{...get(s,'terms',id),trashed});return p;};
export const trashTerm=(s,id)=>recycle(s,id,true),restoreTerm=(s,id)=>recycle(s,id,false);
export function deleteOriginal(s,{sourceId,removeExtracted}){
 if(typeof removeExtracted!=='boolean')fail('INVALID_PACKAGE','请明确选择是否同时删除提取片段。');const source=get(s,'sources',sourceId),p=plan();
 const affected=s.records.revisions.filter(r=>r.sourceIds.includes(sourceId));p.impact=affected.map(r=>({termId:r.termId,revisionId:r.id,removeExtracted}));
 write(p,'sources',{...source,blobHash:null,originalStatus:'deleted',...(removeExtracted?{extractedStatus:'deleted'}:{})});
 if(removeExtracted){
  for(const e of s.records.evidence.filter(e=>e.sourceId===sourceId))write(p,'evidence',{id:e.id,sourceId:e.sourceId,revisionId:e.revisionId,status:'deleted',originalLength:e.originalLength??e.data.text.length,data:{id:e.data.id,title:e.data.title||'',text:''}});
  const scrub=(v,sourceMap)=>{if(Array.isArray(v))return v.map(item=>scrub(item,sourceMap));if(!v||typeof v!=='object')return v;const out={};for(const [k,x] of Object.entries(v)){if(k==='refs'&&Array.isArray(x))out[k]=x.map(ref=>sourceMap[ref.source_id]===sourceId?{source_id:ref.source_id,start:ref.start,end:ref.end}:scrub(ref,sourceMap));else out[k]=scrub(x,sourceMap);}return out;};
  for(const r of affected)write(p,'revisions',{...r,lesson:scrub(r.lesson,r.sourceMap),provenance:{...r.provenance,removedEvidence:true}});
  for(const e of s.records.edges.filter(e=>affected.some(r=>r.id===e.revisionId)))write(p,'edges',{...e,refs:(e.refs||[]).map(ref=>affected.find(r=>r.id===e.revisionId).sourceMap[ref.source_id]===sourceId?{source_id:ref.source_id,start:ref.start,end:ref.end}:ref)});
 }return p;
}
export function purgeTerm(s,termId){
 get(s,'terms',termId);const p=plan(),revisions=s.records.revisions.filter(r=>r.termId===termId),ids=new Set(revisions.map(r=>r.id)),other=s.records.revisions.filter(r=>!ids.has(r.id));
 const contexts=new Set([...s.records.contexts||[],...(s.records.graphViews||[]).flatMap(v=>v.contextRefs)].filter(c=>ids.has(c.revisionId)).map(c=>c.id));
 for(const c of s.records.contexts||[])if(contexts.has(c.id))p.deletes.push({kind:'contexts',id:c.id});
 const affected=ref=>ref.space==='personal'&&ref.id===termId||ref.space==='pending'&&contexts.has(ref.id);
 for(const v of s.records.graphViews||[]){const groups=v.groups.filter(g=>g.sourceRef.kind!=='revision'||!ids.has(g.sourceRef.id)).map(g=>({...g,members:g.members.filter(r=>!affected(r))}));const kept=new Set(groups.map(g=>g.id));write(p,'graphViews',{...v,contextRefs:v.contextRefs.filter(c=>!ids.has(c.revisionId)),nodes:v.nodes.filter(n=>!affected(n.ref)).map(n=>({...n,groups:n.groups.filter(g=>kept.has(g))})),excludedRefs:v.excludedRefs.filter(r=>!affected(r)),groups});}
 for(const f of s.records.frameworks||[])if(f.members.some(affected)||(f.excludedMembers||[]).some(r=>affected(r.ref)))write(p,'frameworks',{...f,members:f.members.filter(r=>!affected(r)),...(f.memberDetails?{memberDetails:f.memberDetails.filter(r=>!affected(r.ref))}:{}),...(f.excludedMembers?{excludedMembers:f.excludedMembers.filter(r=>!affected(r.ref))}:{}),revision:f.revision+1,provenance:f.provenance?{...f.provenance,memberReasons:f.provenance.memberReasons.filter(r=>!affected(r.ref))}:null});
 for(const e of s.records.edges.filter(e=>[e.from,e.to].some(ref=>ref.space==='pending'&&contexts.has(ref.id))))p.deletes.push({kind:'edges',id:e.id});
 p.deletes.push({kind:'terms',id:termId},...revisions.map(r=>({kind:'revisions',id:r.id})),...s.records.evidence.filter(e=>ids.has(e.revisionId)).map(e=>({kind:'evidence',id:e.id})),...s.records.annotations.filter(n=>n.termId===termId).map(n=>({kind:'annotations',id:n.id})),...s.records.edges.filter(e=>ids.has(e.revisionId)||[e.from,e.to].some(r=>r.space==='personal'&&r.id===termId)).map(e=>({kind:'edges',id:e.id})));
 for(const kind of ['sources','assets']){const refs=new Set(other.flatMap(r=>r[kind==='sources'?'sourceIds':'assetIds']));const own=new Set(revisions.flatMap(r=>r[kind==='sources'?'sourceIds':'assetIds']));for(const id of own)if(!refs.has(id))p.deletes.push({kind,id});}return p;
}
export function purgeLibrary(s,{confirmLibraryId}){if(!s.libraryId||confirmLibraryId!==s.libraryId)fail('CONFLICT','完整删除需要再次输入本库标识确认。');const p=plan();for(const kind of COLLECTIONS)for(const record of s.records[kind]||[])p.deletes.push({kind,id:record.id});return p;}
