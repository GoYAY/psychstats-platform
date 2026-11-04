import {RELATIONS} from './contract.mjs';
import {refKey,edgeKey} from './graph-identity.mjs';
export function crossFrameworkRelations(ref,{records,officialGraph={edges:[]},framework}){const members=new Set((framework?.members||[]).map(refKey)),merged=new Map();for(const edge of [...officialGraph.edges||[],...records.edges||[]]){const k=edgeKey(edge),old=merged.get(k);if(old?.status==='dismissed'&&edge.origin!=='user')continue;merged.set(k,edge);}return [...merged.values()].filter(e=>e.status!=='dismissed'&&[e.from,e.to].some(r=>refKey(r)===refKey(ref))&&[e.from,e.to].some(r=>!members.has(refKey(r))));}
const same=(a,b)=>a.space===b.space&&a.id===b.id;
const forward={prerequisites:'前置知识',components:'组成部分',contrasts:'对照理解',used_in:'应用于',next:'后续学习'};
const backward={prerequisites:'作为其前置知识',components:'属于',contrasts:'对照理解',used_in:'由其应用',next:'可由此继续学习'};
export function relationsFor(ref,edges,{includeDismissed=false}={}){const active=edges.filter(e=>includeDismissed||e.status!=='dismissed');return {outgoing:active.filter(e=>same(e.from,ref)).map(e=>({...e,target:e.to,label:forward[e.type]})),incoming:active.filter(e=>same(e.to,ref)).map(e=>({...e,target:e.from,label:backward[e.type]}))};}
export function validateEdges(edges,registry=[]){
 const issues=[],active=edges.filter(e=>e.status!=='dismissed'),key=r=>r.space+':'+r.id;
 for(const e of active){if(!RELATIONS.includes(e.type))issues.push({code:'UNKNOWN_TYPE',edgeId:e.id});if(same(e.from,e.to))issues.push({code:'SELF_RELATION',edgeId:e.id});for(const r of [e.from,e.to])if(r.space!=='pending'&&!registry.some(v=>same(v,r)))issues.push({code:'MISSING_TARGET',edgeId:e.id,ref:r});}
 const adj=new Map();for(const e of active.filter(e=>e.type==='prerequisites')){const a=key(e.from),b=key(e.to);if(!adj.has(a))adj.set(a,[]);adj.get(a).push(b);}
 const done=new Set(),visiting=new Set();const visit=k=>{if(visiting.has(k))return true;if(done.has(k))return false;visiting.add(k);for(const n of adj.get(k)||[])if(visit(n))return true;visiting.delete(k);done.add(k);return false;};
 if([...adj.keys()].some(visit))issues.push({code:'PREREQUISITE_CYCLE',message:'前置知识形成循环，请检查方向。'});return issues;
}
