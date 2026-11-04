import {fail,safeId,text} from './contract.mjs';
import {refKey} from './graph-identity.mjs';
export function upgradeSemanticRecords(records){const copy=structuredClone(records);for(const f of copy.frameworks||[]){f.scope??=f.description||'';f.memberDetails??=f.members.map(ref=>({ref:structuredClone(ref),role:'existing',reason:'既有成员，未补造模型归类依据'}));f.excludedMembers??=[];}for(const e of copy.edges||[]){e.basis??=e.origin==='user'&&e.revisionId===null?'manual':'literature';e.taskRecord??=null;}return copy;}
export function semanticFields(v,keys){if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==keys.length||keys.some(k=>!Object.hasOwn(v,k)))fail('INVALID_PACKAGE','语义记录字段缺失或未知。');}
export function validateTaskRecord(v){semanticFields(v,['taskId','inputHash','model','usage','calls']);safeId(v.taskId);text(v.model,{max:120});if(!/^[a-f0-9]{64}$/.test(v.inputHash)||v.calls!==1)fail('INVALID_PACKAGE','推断缺少可核对的单次任务来源。');semanticFields(v.usage,['prompt_tokens','completion_tokens','total_tokens']);for(const n of Object.values(v.usage))if(!Number.isSafeInteger(n)||n<0)fail('INVALID_PACKAGE','模型用量无效。');}
export function semanticText(v,{empty=false,max=1500}={}){text(v,{empty,max});if(/<\s*\/?\s*[a-zA-Z][^>]*>|javascript:/i.test(v)||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v))fail('INVALID_PACKAGE','简释包含不可执行内容。');}
export function validateSemanticContext(c,maps){
 safeId(c.id);if(Object.hasOwn(c,'revisionId')){semanticFields(c,['id','revisionId','glossaryId']);safeId(c.revisionId);safeId(c.glossaryId);if(!maps.revisions.get(c.revisionId)?.lesson.glossary?.some(g=>g.id===c.glossaryId))fail('INVALID_PACKAGE','背景概念缺少已保存的释义。');return c.revisionId+'|'+c.glossaryId;}
 semanticFields(c,['id','name','aliases','definition','basis','taskRecord']);semanticText(c.name,{max:120});semanticText(c.definition);if(!Array.isArray(c.aliases)||c.aliases.length>30||c.basis!=='inference')fail('INVALID_PACKAGE','独立简释来源无效。');for(const a of c.aliases)semanticText(a,{max:120});validateTaskRecord(c.taskRecord);return 'brief|'+c.id;
}
export function validateSemanticEdge(e,maps,contexts){
 if(!['literature','manual','inference'].includes(e.basis))fail('INVALID_PACKAGE','关系依据类型无效。');
 if(e.basis==='inference'){if(e.origin!=='model'||e.revisionId!==null||!Array.isArray(e.refs)||e.refs.length)fail('INVALID_PACKAGE','推断关系不能冒充原文证据。');validateTaskRecord(e.taskRecord);}
 else if(e.taskRecord!==null)fail('INVALID_PACKAGE','非推断关系不能附加推断任务。');
 if(e.basis==='manual'&&(e.origin!=='user'||e.revisionId!==null))fail('INVALID_PACKAGE','人工关系来源无效。');
 for(const r of [e.from,e.to]){refKey(r);if(e.basis!=='literature'&&(r.space==='personal'&&!maps.terms.has(r.id)||r.space==='pending'&&!contexts.has(r.id)))fail('INVALID_PACKAGE','关系目标已缺失。');}
}
export function validateMemberDetails(f){
 semanticText(f.scope,{empty:true});if(!Array.isArray(f.memberDetails)||!Array.isArray(f.excludedMembers)||f.excludedMembers.length>5000)fail('INVALID_PACKAGE','框架范围或排除决定无效。');
 const members=new Set(f.members.map(refKey)),seen=new Set();for(const row of f.memberDetails){semanticFields(row,['ref','role','reason']);const key=refKey(row.ref);if(!members.has(key)||seen.has(key)||!['core','supporting','existing'].includes(row.role))fail('INVALID_PACKAGE','成员角色身份无效。');seen.add(key);semanticText(row.reason);}
 if(seen.size!==members.size)fail('INVALID_PACKAGE','框架成员缺少角色说明。');seen.clear();for(const row of f.excludedMembers){semanticFields(row,['ref','reason']);const key=refKey(row.ref);if(seen.has(key)||members.has(key))fail('INVALID_PACKAGE','排除决定与框架成员冲突。');seen.add(key);semanticText(row.reason);}
}
