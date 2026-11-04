import {fail,safeId,text,validateStoredRecords} from './contract.mjs';
import {refKey} from './graph-identity.mjs';
import {declaredFrameworkRefs} from './framework-boundaries.mjs';
export function planFrameworkCommand(snapshot,c,{catalogue=[],officialGraph={terms:[],edges:[],frameworks:[]}}={}){
 const records=snapshot.records,plan={writes:[],deletes:[],blobRefs:[],impact:[]},now=c.updatedAt||new Date().toISOString();
 const put=(kind,value)=>plan.writes.push({kind,id:value.id,value:structuredClone(value)}),remove=(kind,id)=>plan.deletes.push({kind,id});
 const available=new Set([...catalogue,...officialGraph.terms||[]].map(t=>'official:'+t.id));for(const t of records.terms)if(!t.trashed)available.add('personal:'+t.id);for(const r of [...records.contexts||[],...records.graphViews.flatMap(v=>v.contextRefs)])available.add('pending:'+r.id);
 const check=r=>{if(!r||!available.has(refKey(r)))fail('INVALID_PACKAGE','所选术语已回收、尚未保存或不在已发布目录。');};
 let f=records.frameworks.find(f=>f.id===c.id);if(c.kind!=='create'&&!f)fail('INVALID_PACKAGE','框架不存在，请重新读取。');f=f?structuredClone(f):null;
 if(c.kind==='create'){
  safeId(c.id);if(records.frameworks.some(f=>f.id===c.id))fail('CONFLICT','已有这个框架编号。');text(c.title,{max:120});for(const r of c.members||[])check(r);
  f={id:c.id,title:c.title.trim(),description:c.description||'',members:[...new Map((c.members||[]).map(r=>[refKey(r),r])).values()],origin:c.origin||'user',provenance:c.provenance||null,locks:{title:!c.origin||c.origin==='user',members:(!c.origin||c.origin==='user')&&!!c.members?.length},legacyTemplate:null,createdAt:now,updatedAt:now,revision:0};
 }else if(c.kind==='delete'){
  remove('frameworks',f.id);const known=new Set((records.contexts||[]).map(c=>c.id));for(const v of records.graphViews)if(v.frameworkId===f.id){for(const c of v.contextRefs)if(!known.has(c.id)){put('contexts',c);known.add(c.id);}remove('graphViews',v.id);}
 }else{
  f.updatedAt=now;f.revision++;
  if(c.kind==='rename'){text(c.title,{max:120});f.title=c.title.trim();f.locks.title=true;if(c.description!==undefined)f.description=c.description;}
  else if(c.kind==='setLocks')f.locks={...f.locks,...c.locks};
  else if(c.kind==='addMember'){check(c.ref);if(!f.members.some(r=>refKey(r)===refKey(c.ref)))f.members.push(c.ref);f.locks.members=true;}
  else if(c.kind==='removeMember'){f.members=f.members.filter(r=>refKey(r)!==refKey(c.ref));f.locks.members=true;f.excludedMembers??=[];if(!f.excludedMembers.some(row=>refKey(row.ref)===refKey(c.ref)))f.excludedMembers.push({ref:structuredClone(c.ref),reason:'已手动移出框架，模型不自动加回'});}
  else if(c.kind==='createNote'){
   safeId(c.termId);text(c.name,{max:120});text(c.definition||'',{empty:true,max:1500});if(records.terms.some(t=>t.id===c.termId))fail('CONFLICT','个人术语编号重复。');
   put('terms',{id:c.termId,zh:c.name.trim(),en:'',aliases:[],anchor:{id:c.termId,zh:c.name.trim(),en:'',aliases:[],definition:c.definition||''},tags:['个人笔记'],currentRevisionId:null,trashed:false});f.members.push({space:'personal',id:c.termId});f.locks.members=true;
  }else if(c.kind==='materializeLegacy'){
   const needed=f.legacyTemplate==='combined'?['factor-analysis','multilevel-longitudinal']:['factor-analysis','multilevel-longitudinal'].includes(f.legacyTemplate)?[f.legacyTemplate]:[];
   if(needed.some(id=>!(officialGraph.frameworks||[]).some(g=>g.id===id)))fail('RESOURCE_UNAVAILABLE','官方框架尚未读取或缓存，旧布局与备份保留。');
   const views=records.graphViews.filter(v=>v.frameworkId===f.id),members=new Map(f.members.map(r=>[refKey(r),r]));
   for(const ref of declaredFrameworkRefs(records,f,views))members.set(refKey(ref),ref);
   for(const template of officialGraph.frameworks||[])if(needed.includes(template.id))for(const id of [...template.core,...template.oneHop])members.set('official:'+id,{space:'official',id});
   f.members=[...members.values()];f.legacyTemplate=null;
  }else fail('INVALID_PACKAGE','未知框架操作。');
  if(f.provenance&&['addMember','removeMember','createNote'].includes(c.kind)){f.origin='user';const kept=new Set(f.members.map(refKey));f.provenance.memberReasons=f.provenance.memberReasons.filter(r=>kept.has(refKey(r.ref)));}
 }
 if(c.kind!=='delete'){
  if(f.memberDetails){const details=new Map(f.memberDetails.map(r=>[refKey(r.ref),r]));f.memberDetails=f.members.map(ref=>details.get(refKey(ref))||{ref:structuredClone(ref),role:'existing',reason:'手动加入的成员'});}
  if(f.excludedMembers)f.excludedMembers=f.excludedMembers.filter(r=>!f.members.some(m=>refKey(m)===refKey(r.ref)));
  put('frameworks',f);
 }
 const next=structuredClone(records),inverse={records:[]};for(const row of [...plan.deletes,...plan.writes]){const old=(next[row.kind]||[]).find(r=>r.id===row.id)||null;inverse.records.push({kind:row.kind,id:row.id,before:old,after:'value'in row?row.value:null});next[row.kind]=(next[row.kind]||[]).filter(r=>r.id!==row.id);if('value'in row)next[row.kind].push(row.value);}
 validateStoredRecords(next);return {plan,inverse};
}
