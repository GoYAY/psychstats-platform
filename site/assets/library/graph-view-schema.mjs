import {fail,safeId,text} from './contract.mjs';
import {refKey} from './graph-identity.mjs';
import {validateSemanticContext} from './semantic-schema.mjs';
const object=(v,keys)=>{if(!v||Array.isArray(v)||typeof v!=='object'||Object.keys(v).some(k=>!keys.includes(k))||keys.some(k=>!(k in v)))fail('INVALID_PACKAGE','画布字段缺失或未知。');};
const list=(v,max=5000)=>{if(!Array.isArray(v)||v.length>max)fail('INVALID_PACKAGE','画布列表无效。');return v;};
const coordinate=v=>{if(typeof v!=='number'||!Number.isFinite(v)||Math.abs(v)>1e6)fail('INVALID_PACKAGE','画布坐标无效。');};
export function validateGraphViews(value,maps){
 const contexts=new Map(),origins=new Map();
 for(const c of [...list(value.contexts||[]),...value.graphViews.flatMap(view=>list(view.contextRefs))]){
  const identity=validateSemanticContext(c,maps);
  if(contexts.has(c.id)&&contexts.get(c.id)!==identity||origins.has(identity)&&origins.get(identity)!==c.id)fail('INVALID_PACKAGE','背景概念身份冲突。');
  contexts.set(c.id,identity);origins.set(identity,c.id);
 }
 const ref=r=>{object(r,['space','id']);safeId(r.id);if(!['personal','official','pending'].includes(r.space)||r.space==='personal'&&!maps.terms.has(r.id)||r.space==='pending'&&!contexts.has(r.id))fail('INVALID_PACKAGE','画布节点缺少对应术语或背景释义。');return refKey(r);};
 for(const v of value.graphViews){
  object(v,['id','title','frameworkId','mode','nodes','groups','contextRefs','excludedRefs','viewport','updatedAt']);safeId(v.id);safeId(v.frameworkId);text(v.title,{max:120});
  if(!['structure','learning','free'].includes(v.mode)||typeof v.updatedAt!=='string'||!/^\d{4}-\d\d-\d\dT/.test(v.updatedAt)||!Number.isFinite(Date.parse(v.updatedAt)))fail('INVALID_PACKAGE','画布模式或日期无效。');
  object(v.viewport,['x','y','scale']);coordinate(v.viewport.x);coordinate(v.viewport.y);if(typeof v.viewport.scale!=='number'||!Number.isFinite(v.viewport.scale)||v.viewport.scale<.2||v.viewport.scale>2.5)fail('INVALID_PACKAGE','画布缩放无效。');
  const groupIds=new Set();for(const g of list(v.groups,100)){
   object(g,['id','title','origin','members','sourceRef']);safeId(g.id);text(g.title,{max:120});if(groupIds.has(g.id)||!['official','model','user'].includes(g.origin))fail('INVALID_PACKAGE','画布分组无效。');groupIds.add(g.id);
   object(g.sourceRef,['kind','id']);safeId(g.sourceRef.id);
   const expected={official:'official-framework',model:'revision',user:'user'}[g.origin];if(g.sourceRef.kind!==expected||expected==='revision'&&!maps.revisions.has(g.sourceRef.id)||expected==='official-framework'&&!['factor-analysis','multilevel-longitudinal'].includes(g.sourceRef.id))fail('INVALID_PACKAGE','分组来源无法解析。');
   const members=list(g.members).map(ref);if(new Set(members).size!==members.length)fail('INVALID_PACKAGE','分组成员重复。');
  }
  const keys=new Set();for(const n of list(v.nodes)){
   object(n,['ref','x','y','pinned','groups']);const key=ref(n.ref);if(keys.has(key))fail('INVALID_PACKAGE','画布节点重复。');keys.add(key);coordinate(n.x);coordinate(n.y);if(typeof n.pinned!=='boolean')fail('INVALID_PACKAGE','固定状态无效。');
   const groups=list(n.groups,100);if(new Set(groups).size!==groups.length||groups.some(id=>!groupIds.has(id)))fail('INVALID_PACKAGE','节点分组缺失或重复。');
  }
  const excluded=list(v.excludedRefs).map(ref);if(new Set(excluded).size!==excluded.length)fail('INVALID_PACKAGE','移出节点重复。');
 }
 return contexts;
}
