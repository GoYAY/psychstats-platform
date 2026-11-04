import {fail,RELATIONS} from './contract.mjs';
import {semanticFields as exact,semanticText as text,validateTaskRecord} from './semantic-schema.mjs';
import {refKey} from './graph-identity.mjs';
const list=(v,n)=>{if(!Array.isArray(v)||v.length>n)fail('INVALID_MODEL_RESULT','模型结果数量无效。');return v;};
export function modelRefKey(ref){if(ref?.space==='new'){exact(ref,['space','id']);if(!/^[A-Za-z0-9][A-Za-z0-9_:.-]{0,191}$/.test(ref.id))fail('INVALID_MODEL_RESULT','新词身份无效。');return 'new:'+ref.id;}exact(ref,['space','id']);return refKey(ref);}
export function validateSemanticOutput(result,input){
 exact(result,['schemaVersion','groups','contexts','relations','reviews','unassigned','inputHash','model','usage','calls']);if(result.schemaVersion!==2||input.schemaVersion!==2)fail('INVALID_MODEL_RESULT','旧整理结果不能作为新语义结果应用。');
 validateTaskRecord({taskId:'validation',inputHash:result.inputHash,model:result.model,usage:result.usage,calls:result.calls});
 const known=new Map(input.terms.map(t=>[refKey(t.ref),t])),newKeys=new Set(),frames=new Map(input.frameworks.map(f=>[f.id,f]));
 for(const c of list(result.contexts,20)){exact(c,['localId','name','aliases','definition','reason']);const key=modelRefKey({space:'new',id:c.localId});if(newKeys.has(key))fail('INVALID_MODEL_RESULT','新词重复。');newKeys.add(key);text(c.name,{max:120});text(c.definition);text(c.reason);for(const a of list(c.aliases,30))text(a,{max:120});}
 const covered=new Set(),groupedNew=new Set(),targets=new Set();
 for(const g of list(result.groups,30)){exact(g,['targetFrameworkId','title','description','scope','members']);text(g.title,{max:120});text(g.description,{empty:true});text(g.scope);if(g.targetFrameworkId!==null){if(!frames.has(g.targetFrameworkId)||targets.has(g.targetFrameworkId))fail('INVALID_MODEL_RESULT','框架目标无效。');targets.add(g.targetFrameworkId);}const seen=new Set();let anchor=false;
  for(const row of list(g.members,220)){exact(row,['ref','role','reason']);const k=modelRefKey(row.ref);text(row.reason);if(seen.has(k)||!known.has(k)&&!newKeys.has(k)||!['core','supporting'].includes(row.role))fail('INVALID_MODEL_RESULT','成员角色或身份无效。');seen.add(k);if(known.has(k)){const t=known.get(k);if(!t.definition.trim()&&!t.summary.trim())fail('INVALID_MODEL_RESULT','仅名称条目应未归类。');covered.add(k);anchor=true;}else groupedNew.add(k);}
  if(!anchor)fail('INVALID_MODEL_RESULT','框架缺少已有概念锚点。');
 }
 const linked=new Set(),edges=new Set(),adjacency=new Map();const addPre=r=>{if(r.type==='prerequisites'){const a=modelRefKey(r.from),b=modelRefKey(r.to);if(!adjacency.has(a))adjacency.set(a,new Set());adjacency.get(a).add(b);}};for(const r of input.relations)addPre(r);
 for(const r of list(result.relations,200)){exact(r,['from','to','type','reason']);const a=modelRefKey(r.from),b=modelRefKey(r.to);text(r.reason);if(a===b||!RELATIONS.includes(r.type)||![a,b].every(k=>known.has(k)||newKeys.has(k)))fail('INVALID_MODEL_RESULT','关系目标或类型无效。');const k=r.type+'|'+(r.type==='contrasts'?[a,b].sort():[a,b]).join('|');if(edges.has(k))fail('INVALID_MODEL_RESULT','关系重复。');edges.add(k);if(newKeys.has(a)&&known.has(b))linked.add(a);if(newKeys.has(b)&&known.has(a))linked.add(b);addPre(r);}
 if([...newKeys].some(k=>!groupedNew.has(k)||!linked.has(k)))fail('INVALID_MODEL_RESULT','新背景须入组且有与已有概念的具体关系。');
 const visiting=new Set(),done=new Set();function visit(k){if(visiting.has(k))fail('INVALID_MODEL_RESULT','前置知识形成循环。');if(done.has(k))return;visiting.add(k);for(const n of adjacency.get(k)||[])visit(n);visiting.delete(k);done.add(k);}for(const k of adjacency.keys())visit(k);
 const reviewed=new Set();for(const row of list(result.reviews,200)){exact(row,['frameworkId','ref','action','reason']);const k=modelRefKey(row.ref),f=frames.get(row.frameworkId),id=row.frameworkId+'|'+k;text(row.reason);if(!f||!f.members.some(r=>refKey(r)===k)||!known.has(k)||!['keep','remove'].includes(row.action)||reviewed.has(id))fail('INVALID_MODEL_RESULT','成员审查目标无效。');reviewed.add(id);}
 const unassigned=new Set();for(const ref of list(result.unassigned,200)){const k=modelRefKey(ref);if(!known.has(k)||covered.has(k)||unassigned.has(k))fail('INVALID_MODEL_RESULT','未归类名单无效。');unassigned.add(k);}if(covered.size+unassigned.size!==known.size)fail('INVALID_MODEL_RESULT','模型遗漏输入概念。');return result;
}
