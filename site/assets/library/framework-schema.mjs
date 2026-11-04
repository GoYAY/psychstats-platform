import {fail,safeId,text} from './contract.mjs';
import {refKey} from './graph-identity.mjs';
import {validateMemberDetails} from './semantic-schema.mjs';
const templates=new Set(['all','human-ai','factor-analysis','multilevel-longitudinal','combined']);
export function legacyFrameworks(views){
 const frames=new Map();
 for(const v of views){let f=frames.get(v.frameworkId);if(!f){f={id:v.frameworkId,title:v.title,description:'旧画布保留的组织',members:[],origin:'legacy',provenance:null,locks:{title:false,members:false},legacyTemplate:templates.has(v.frameworkId)?v.frameworkId:null,createdAt:v.updatedAt,updatedAt:v.updatedAt,revision:0};frames.set(f.id,f);}
  const members=[...v.nodes.map(n=>n.ref),...v.groups.flatMap(g=>g.members),...v.contextRefs.map(c=>({space:'pending',id:c.id}))];
  for(const ref of members)if(!f.members.some(r=>refKey(r)===refKey(ref)))f.members.push(structuredClone(ref));
 }return [...frames.values()];
}
function object(value,keys){if(!value||Array.isArray(value)||typeof value!=='object'||Object.keys(value).some(k=>!keys.includes(k))||keys.some(k=>!(k in value)))fail('INVALID_PACKAGE','框架字段缺失或未知。');}
export function validateFrameworks(value,maps,contexts){
 for(const f of value.frameworks){
  object(f,['id','title','description','members','origin','provenance','locks','legacyTemplate','createdAt','updatedAt','revision','scope','memberDetails','excludedMembers']);safeId(f.id);text(f.title,{max:120});text(f.description,{empty:true,max:1500});validateMemberDetails(f);
  if(!['user','model','template','legacy'].includes(f.origin)||!Number.isInteger(f.revision)||f.revision<0)fail('INVALID_PACKAGE','框架来源或版本无效。');
  for(const date of [f.createdAt,f.updatedAt])if(typeof date!=='string'||!/^\d{4}-\d\d-\d\dT/.test(date)||!Number.isFinite(Date.parse(date)))fail('INVALID_PACKAGE','框架日期无效。');
  object(f.locks,['title','members']);if(Object.values(f.locks).some(v=>typeof v!=='boolean')||f.legacyTemplate!==null&&(f.origin!=='legacy'||!templates.has(f.legacyTemplate)))fail('INVALID_PACKAGE','框架锁定或迁移来源无效。');
  if(!Array.isArray(f.members)||f.members.length>5000)fail('INVALID_PACKAGE','框架成员列表无效。');const keys=new Set();
  for(const r of f.members){object(r,['space','id']);safeId(r.id);const key=refKey(r);if(!['personal','official','pending'].includes(r.space)||keys.has(key)||r.space==='personal'&&!maps.terms.has(r.id)||r.space==='pending'&&!contexts.has(r.id))fail('INVALID_PACKAGE','框架成员身份缺失或重复。');keys.add(key);}
  if(f.provenance===null){if(f.origin==='model')fail('INVALID_PACKAGE','模型框架缺少调用来源。');continue;}
  if(!['model','user'].includes(f.origin))fail('INVALID_PACKAGE','此来源不能附模型调用记录。');
  const p=f.provenance;object(p,['taskId','inputHash','model','usage','calls','memberReasons']);safeId(p.taskId);text(p.model,{max:120});
  if(!/^[a-f0-9]{64}$/.test(p.inputHash)||!Number.isInteger(p.calls)||p.calls<1||p.calls>3||!p.usage||typeof p.usage!=='object'||Array.isArray(p.usage)||!Array.isArray(p.memberReasons))fail('INVALID_PACKAGE','缺少真实模型整理记录。');
  for(const key of ['prompt_tokens','completion_tokens','total_tokens'])if(!Number.isInteger(p.usage[key])||p.usage[key]<0)fail('INVALID_PACKAGE','模型用量无效。');
  const reasons=new Set();for(const item of p.memberReasons){object(item,['ref','reason']);object(item.ref,['space','id']);text(item.reason,{max:1500});const key=refKey(item.ref);if(!keys.has(key)||reasons.has(key))fail('INVALID_PACKAGE','模型分组理由身份无效。');reasons.add(key);}
  if(f.origin==='model'&&reasons.size!==keys.size)fail('INVALID_PACKAGE','模型成员缺少分组理由。');
 }
}
