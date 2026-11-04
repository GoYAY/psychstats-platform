import {fail,validateStoredRecords} from './contract.mjs';
import {upgradeSemanticRecords} from './semantic-schema.mjs';
import {refKey,edgeKey} from './graph-identity.mjs';
import {validateEdges} from './graph.mjs';
import {currentBatchInput,frameworkInputHash} from './framework-summary.mjs';
import {matchSemanticTerm} from './semantic-identity.mjs';
import {validateSemanticOutput} from './semantic-response.mjs';
import {planMembershipCleanup} from './framework-boundaries.mjs';
import {backgroundCandidates} from './background-candidates.mjs';
export async function planSemanticSuggestions(snapshot,result,{taskId,baseInput,baseInputHash,catalogue=[],officialGraph={terms:[],edges:[]}}={}){
 validateSemanticOutput(result,baseInput);if(result.inputHash!==baseInputHash||await frameworkInputHash(baseInput)!==baseInputHash)fail('INVALID_MODEL_RESULT','模型结果不属于本次输入。');
 const records=upgradeSemanticRecords(snapshot.records),plan={writes:[],deletes:[],blobRefs:[],impact:[]},inverse={records:[]},conflicts=[],review=[];
 if(await frameworkInputHash(currentBatchInput(records,baseInput,{catalogue,officialGraph}))!==baseInputHash)return {plan,inverse,conflicts:[{reason:'资料或框架已在整理期间改变，建议未覆盖当前版本。',groups:result.groups}],review};
 const taskRecord={taskId,inputHash:result.inputHash,model:result.model,usage:result.usage,calls:result.calls},mapping=new Map(),proposed=new Map(),pool=structuredClone(records),now=new Date().toISOString();
 const put=(kind,value)=>{if(plan.writes.some(w=>w.kind===kind&&w.id===value.id))fail('CONFLICT','本次结果重复写入同一身份。');plan.writes.push({kind,id:value.id,value});};
 const candidateKeys=new Set(baseInput.terms.map(t=>refKey(t.ref))),candidateMapping=new Map();
 for(const c of backgroundCandidates(records))if(candidateKeys.has(refKey(c.term.ref))){
  // A persisted contextual identity already denotes a specific meaning. Keep it.
  const existing=[...records.contexts,...records.graphViews.flatMap(v=>v.contextRefs)].some(v=>v.id===c.context.id);if(existing){if(!records.contexts.some(v=>v.id===c.context.id)){proposed.set(c.context.id,c.context);pool.contexts.push(c.context);}continue;}
  const match=matchSemanticTerm({name:c.term.name},{records:pool,catalogue:[...catalogue,...officialGraph.terms||[]]});
  if(match.ref){candidateMapping.set(c.context.id,match.ref);continue;}
  if(match.candidates.length>1){candidateMapping.set(c.context.id,null);conflicts.push({reason:'“'+c.term.name+'”存在多个已保存含义，未自动合并。'});continue;}
  if(!records.contexts.some(v=>v.id===c.context.id)){proposed.set(c.context.id,c.context);pool.contexts.push(c.context);}
 }
 for(const c of result.contexts){const matched=matchSemanticTerm(c,{records:pool,catalogue:[...catalogue,...officialGraph.terms||[]]});if(matched.ref){mapping.set(c.localId,matched.ref);continue;}if(matched.candidates.length||matched.glossaryCandidates?.length>1){mapping.set(c.localId,null);conflicts.push({reason:'“'+c.name+'”存在多个含义，需先确认身份。'});continue;}
  let value;if(matched.glossaryCandidates?.length===1){const source=matched.glossaryCandidates[0],id='context-'+(await frameworkInputHash(source)).slice(0,32);value={id,...source};}
  else value={id:'brief-'+(await frameworkInputHash({taskId,localId:c.localId})).slice(0,32),name:c.name,aliases:c.aliases,definition:c.definition,basis:'inference',taskRecord};
  if(records.contexts.some(v=>v.id===value.id))fail('CONFLICT','背景身份已存在，请重新读取。');mapping.set(c.localId,{space:'pending',id:value.id});proposed.set(value.id,value);pool.contexts.push(value);
 }
 const mapped=ref=>ref.space==='new'?mapping.get(ref.id):ref.space==='pending'&&candidateMapping.has(ref.id)?candidateMapping.get(ref.id):ref;
 for(const [i,g] of result.groups.entries()){
  const old=g.targetFrameworkId?records.frameworks.find(f=>f.id===g.targetFrameworkId):null,excluded=new Set((old?.excludedMembers||[]).map(r=>refKey(r.ref))),selected=new Map();
  for(const row of g.members){const ref=mapped(row.ref);if(!ref)continue;if(excluded.has(refKey(ref))){conflicts.push({reason:'已按你的排除决定保留未加入的成员。'});continue;}selected.set(refKey(ref),{ref:structuredClone(ref),role:row.role,reason:row.reason});}
  if(![...selected.values()].some(r=>r.ref.space!=='pending'||records.contexts.some(c=>c.id===r.ref.id))){conflicts.push({reason:'身份尚未确认，暂不建立这个框架。'});continue;}
  if(old?.locks.members&&[...selected.values()].some(r=>!old.members.some(m=>refKey(m)===refKey(r.ref)))){conflicts.push({reason:'框架成员已由你手动整理，新增建议待审阅。',group:g});continue;}
  const members=new Map((old?.members||[]).map(ref=>[refKey(ref),ref])),details=new Map((old?.memberDetails||[]).map(r=>[refKey(r.ref),r]));for(const [k,row] of selected){members.set(k,row.ref);if(!old?.locks.members)details.set(k,row);}
  const id=old?.id||'auto-'+result.inputHash.slice(0,16)+'-'+i;if(!old&&records.frameworks.some(f=>f.id===id))fail('CONFLICT','此模型任务已应用，不重复覆盖。');
  const memberReasons=[...selected.values()].map(({ref,reason})=>({ref,reason})),origin=old?.origin==='user'||members.size!==selected.size?'user':'model';
  put('frameworks',{id,title:old?.locks.title?old.title:g.title,description:old?.locks.title?old.description:g.description,scope:old?.locks.title?old.scope:g.scope,members:[...members.values()],memberDetails:[...members].map(([k,ref])=>details.get(k)||{ref,role:'existing',reason:'既有成员'}),excludedMembers:old?.excludedMembers||[],origin,provenance:{...taskRecord,memberReasons},locks:old?.locks||{title:false,members:false},legacyTemplate:null,createdAt:old?.createdAt||now,updatedAt:now,revision:(old?.revision??-1)+1});
 }
 const used=new Set(plan.writes.filter(w=>w.kind==='frameworks').flatMap(w=>w.value.members.filter(r=>r.space==='pending').map(r=>r.id)));
 for(const [id,c] of proposed)if(used.has(id))put('contexts',c);
 const activeContexts=new Set([...records.contexts.map(c=>c.id),...plan.writes.filter(w=>w.kind==='contexts').map(w=>w.id)]),existing=new Map([...officialGraph.edges||[],...records.edges].map(e=>[edgeKey(e),e]));
 for(const r of result.relations){const from=mapped(r.from),to=mapped(r.to);if(!from||!to||refKey(from)===refKey(to)||[from,to].some(ref=>ref.space==='pending'&&!activeContexts.has(ref.id)))continue;const edge={from,to,type:r.type},key=edgeKey(edge);if(existing.has(key))continue;const id='inferred-'+(await frameworkInputHash({taskId,key})).slice(0,32);const value={id,...edge,reason:r.reason,refs:[],origin:'model',basis:'inference',taskRecord,revisionId:null,status:'suggested'};put('edges',value);existing.set(key,value);}
 // A rejected relationship must not leave a just-created background node orphaned.
 const connected=new Set(plan.writes.filter(w=>w.kind==='edges').flatMap(w=>[w.value.from,w.value.to]).filter(r=>r.space==='pending').map(r=>r.id));
 const orphan=new Set(plan.writes.filter(w=>w.kind==='contexts'&&!connected.has(w.id)).map(w=>w.id));
 if(orphan.size){plan.writes=plan.writes.filter(w=>w.kind!=='contexts'||!orphan.has(w.id));for(const w of plan.writes.filter(w=>w.kind==='frameworks')){w.value.members=w.value.members.filter(r=>r.space!=='pending'||!orphan.has(r.id));w.value.memberDetails=w.value.memberDetails.filter(r=>r.ref.space!=='pending'||!orphan.has(r.ref.id));w.value.provenance.memberReasons=w.value.provenance.memberReasons.filter(r=>r.ref.space!=='pending'||!orphan.has(r.ref.id));}}
 for(const row of result.reviews)if(row.action==='remove')review.push({...row,locked:!!records.frameworks.find(f=>f.id===row.frameworkId)?.locks.members});
 const next=structuredClone(records);for(const w of plan.writes){const old=records[w.kind].find(v=>v.id===w.id)||null;inverse.records.push({kind:w.kind,id:w.id,before:structuredClone(old),after:structuredClone(w.value)});next[w.kind]=[...next[w.kind].filter(v=>v.id!==w.id),w.value];}
 validateStoredRecords(next);
 const registry=[...next.terms.filter(t=>!t.trashed).map(t=>({space:'personal',id:t.id})),...next.contexts.map(c=>({space:'pending',id:c.id})),...[...catalogue,...officialGraph.terms||[]].map(t=>({space:'official',id:t.id}))],available=new Set(registry.map(refKey));
 const candidates=[...existing.values()].filter(e=>e.status!=='dismissed'&&[e.from,e.to].every(r=>available.has(refKey(r))));if(validateEdges(candidates,registry).length)fail('INVALID_MODEL_RESULT','映射后的关系有重复或前置循环，尚未保存。');
 return {plan,inverse,conflicts,review};
}
export function planReviewDecision(snapshot,{frameworkId,ref,action,reason}){
 if(action==='remove')return planMembershipCleanup(snapshot,{frameworkId,removeRefs:[ref]});
 const old=snapshot.records.frameworks.find(f=>f.id===frameworkId);if(!old||!['keep','reconsider'].includes(action))fail('CONFLICT','审查对象已变化。');const value=structuredClone(old);value.revision++;value.updatedAt=new Date().toISOString();if(action==='keep')value.locks.members=true;else value.excludedMembers=(value.excludedMembers||[]).filter(row=>refKey(row.ref)!==refKey(ref));
 const next=structuredClone(snapshot.records);next.frameworks=next.frameworks.map(f=>f.id===frameworkId?value:f);validateStoredRecords(next);return {plan:{writes:[{kind:'frameworks',id:frameworkId,value}],deletes:[],blobRefs:[],impact:[]},inverse:{records:[{kind:'frameworks',id:frameworkId,before:structuredClone(old),after:structuredClone(value)}]}};
}
