import {fail,validateStoredRecords} from './contract.mjs';
import {refKey} from './graph-identity.mjs';
import {currentBatchInput,frameworkInputHash} from './framework-summary.mjs';
import {planSemanticSuggestions} from './semantic-suggestions.mjs';
export async function planFrameworkSuggestions(snapshot,result,{taskId,baseInput,baseInputHash,catalogue=[],officialGraph={terms:[],edges:[]}}={}){
 if(baseInput?.schemaVersion===2)return planSemanticSuggestions(snapshot,result,{taskId,baseInput,baseInputHash,catalogue,officialGraph});
 if(!result||!Array.isArray(result.groups)||!Array.isArray(result.unassigned)||result.groups.length>30||result.inputHash!==baseInputHash||await frameworkInputHash(baseInput)!==baseInputHash)fail('INVALID_MODEL_RESULT','模型结果与本次概念摘要不对应。');
 const known=new Map(baseInput.terms.map(t=>[refKey(t.ref),t])),frames=new Map(baseInput.frameworks.map(f=>[f.id,f])),covered=new Set(),targets=new Set();
 for(const group of result.groups){if(!group||Object.keys(group).sort().join('|')!==['targetFrameworkId','title','description','members'].sort().join('|')||!Array.isArray(group.members)||!group.members.length)fail('INVALID_MODEL_RESULT','模型分组字段不完整。');if(group.targetFrameworkId!==null&&(!frames.has(group.targetFrameworkId)||targets.has(group.targetFrameworkId)))fail('INVALID_MODEL_RESULT','模型指定了未知或重复框架。');if(group.targetFrameworkId!==null)targets.add(group.targetFrameworkId);const seen=new Set();for(const row of group.members){const key=refKey(row.ref||{});if(!known.has(key)||seen.has(key)||typeof row.reason!=='string'||!row.reason.trim())fail('INVALID_MODEL_RESULT','模型指定了未知、重复或无依据的概念。');seen.add(key);covered.add(key);}}
 const unassigned=new Set();for(const ref of result.unassigned){const key=refKey(ref);if(!known.has(key)||unassigned.has(key)||covered.has(key))fail('INVALID_MODEL_RESULT','未归类名单无效。');unassigned.add(key);}if(covered.size+unassigned.size!==known.size)fail('INVALID_MODEL_RESULT','模型遗漏了输入概念。');
 const current=currentBatchInput(snapshot.records,baseInput,{catalogue,officialGraph}),plan={writes:[],deletes:[],blobRefs:[],impact:[]},inverse={records:[]},conflicts=[];
 if(await frameworkInputHash(current)!==baseInputHash)return {plan,inverse,conflicts:[{reason:'资料或框架已在整理期间改变，建议未覆盖当前版本。',groups:result.groups}]};
 const now=new Date().toISOString();for(const [i,group] of result.groups.entries()){
  const old=group.targetFrameworkId?snapshot.records.frameworks.find(f=>f.id===group.targetFrameworkId):null,selected=new Map(group.members.map(r=>[refKey(r.ref),structuredClone(r)]));
  if(old?.locks.members&&group.members.some(r=>!old.members.some(m=>refKey(m)===refKey(r.ref)))){conflicts.push({reason:'框架成员已由你手动整理，新增建议待审阅。',group});continue;}
  const members=new Map((old?.members||[]).map(r=>[refKey(r),r]));for(const row of group.members)members.set(refKey(row.ref),row.ref);
  const id=old?.id||'auto-'+result.inputHash.slice(0,16)+'-'+i;if(!old&&snapshot.records.frameworks.some(f=>f.id===id))fail('CONFLICT','同一整理结果已保存，不重复覆盖。');
  const provenance={taskId,inputHash:result.inputHash,model:result.model,usage:result.usage,calls:result.calls,memberReasons:[...selected.values()]};
  const origin=old?.origin==='user'||members.size!==selected.size?'user':'model';
  const value={id,title:old?.locks.title?old.title:group.title,description:old?.locks.title?old.description:group.description,members:[...members.values()],origin,provenance,locks:old?.locks||{title:false,members:false},legacyTemplate:null,createdAt:old?.createdAt||now,updatedAt:now,revision:(old?.revision??-1)+1};
  plan.writes.push({kind:'frameworks',id,value});inverse.records.push({kind:'frameworks',id,before:structuredClone(old||null),after:structuredClone(value)});
 }
 const next=structuredClone(snapshot.records);for(const w of plan.writes)next.frameworks=[...next.frameworks.filter(f=>f.id!==w.id),w.value];validateStoredRecords(next);return {plan,inverse,conflicts};
}
