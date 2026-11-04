import {fail,RELATIONS,validateStoredRecords} from './contract.mjs';
import {edgeKey,refKey} from './graph-identity.mjs';
import {validateEdges} from './graph.mjs';
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const fingerprint=value=>{let a=2166136261,b=2246822507;for(const char of value){a=Math.imul(a^char.charCodeAt(0),16777619);b=Math.imul(b^char.charCodeAt(0),3266489909);}return (a>>>0).toString(16).padStart(8,'0')+(b>>>0).toString(16).padStart(8,'0');};
export const defaultGraphView=(id='all',frameworkId=id)=>({id,title:({all:'我的全部知识','human-ai':'人–AI交互框架','factor-analysis':'因素分析框架','multilevel-longitudinal':'多层与纵向模型框架',combined:'两套官方框架'})[frameworkId]||'我的画布',frameworkId,mode:'structure',nodes:[],groups:[],contextRefs:[],excludedRefs:[],viewport:{x:24,y:24,scale:1},updatedAt:'1970-01-01T00:00:00.000Z'});
function finish(snapshot,plan){
 const records=structuredClone(snapshot.records),inverse={records:[]};
 for(const item of [...plan.deletes,...plan.writes]){const old=(records[item.kind]||[]).find(v=>v.id===item.id)||null;inverse.records.push({kind:item.kind,id:item.id,before:structuredClone(old),after:'value' in item?structuredClone(item.value):null});records[item.kind]=(records[item.kind]||[]).filter(v=>v.id!==item.id);if('value' in item)records[item.kind].push(item.value);}
 validateStoredRecords(records);return {plan,inverse};
}
export function planGraphInverse(snapshot,inverse){
 const plan={writes:[],deletes:[],blobRefs:[],impact:[]};
 for(const row of inverse.records){const current=(snapshot.records[row.kind]||[]).find(r=>r.id===row.id)||null;if(!equal(current,row.after))fail('CONFLICT','资料已更新，不能用旧撤销记录覆盖；请重新读取。');if(row.before)plan.writes.push({kind:row.kind,id:row.id,value:structuredClone(row.before)});else plan.deletes.push({kind:row.kind,id:row.id});}
 return finish(snapshot,plan);
}
export function planGraphCommand(snapshot,command,{officialGraph={terms:[],edges:[]},catalogue=[]}={}){
 const plan={writes:[],deletes:[],blobRefs:[],impact:[]},records=snapshot.records;
 const put=(kind,value)=>{const found=plan.writes.find(w=>w.kind===kind&&w.id===value.id);if(found)found.value=structuredClone(value);else plan.writes.push({kind,id:value.id,value:structuredClone(value)});};
 const privateEdges=records.edges||[],all=[...officialGraph.edges||[],...privateEdges];
 const currentEdges=()=>{const local=new Map(privateEdges.map(e=>[e.id,e]));for(const w of plan.writes.filter(w=>w.kind==='edges'))local.set(w.id,w.value);const map=new Map(),rank=e=>e.status==='dismissed'?100:e.origin==='user'?50:e.origin==='model'?30:10;for(const edge of [...officialGraph.edges||[],...local.values()]){const key=edgeKey(edge),current=map.get(key);if(!current||rank(edge)>=rank(current))map.set(key,edge);}return [...map.values()];};
 const registry=[...(records.terms||[]).filter(t=>!t.trashed).map(t=>({space:'personal',id:t.id})),...catalogue.map(t=>({space:'official',id:t.id})),...(officialGraph.terms||[]).map(t=>({space:'official',id:t.id}))];
 const available=new Set([...registry.map(refKey),...[...records.contexts||[],...(records.graphViews||[]).flatMap(v=>v.contextRefs)].map(c=>'pending:'+c.id)]);
 const resolvable=edge=>[edge.from,edge.to].every(ref=>available.has(refKey(ref)));
 const validateCandidate=edge=>{if(!resolvable(edge))fail('INVALID_PACKAGE','所选关系的术语已回收、缺失或尚未加入背景概念，请先恢复或选择有效目标。');const active=currentEdges().filter(e=>e.status!=='dismissed'&&edgeKey(e)!==edgeKey(edge)&&resolvable(e));const issues=validateEdges([...active,edge],registry);if(issues.length)fail('INVALID_PACKAGE',issues[0].message||'关系有重复、缺失目标或自连，请检查。');};
 const setStatus=(edge,status)=>{
  if(!edge||!['suggested','confirmed','dismissed'].includes(status))fail('INVALID_PACKAGE','关联或状态无效。');
  if(status!=='dismissed')validateCandidate({...edge,status});
  const key=edgeKey(edge),matches=privateEdges.filter(e=>edgeKey(e)===key);
  if(matches.length){for(const e of matches)put('edges',{...e,status});}
  else {const id='canvas-edge-'+fingerprint(key),collision=privateEdges.find(e=>e.id===id&&edgeKey(e)!==key);if(collision)fail('CONFLICT','关系身份冲突，尚未保存。');put('edges',{id,from:edge.from,to:edge.to,type:edge.type,reason:'个人画布操作：'+edge.reason,refs:[],origin:'user',revisionId:null,status});}
 };
 const connect=({from,to,type,reason})=>{
  if(!RELATIONS.includes(type)||typeof reason!=='string'||!reason.trim())fail('INVALID_PACKAGE','请选择关系并填写判断依据。');
  const edge={id:'canvas-edge-'+fingerprint(type+'|'+refKey(from)+'|'+refKey(to)),from,to,type,reason,refs:[],origin:'user',revisionId:null,status:'confirmed'};
  if(currentEdges().some(e=>edgeKey(e)===edgeKey(edge)))fail('CONFLICT','已有此关系，请使用恢复或修改操作。');validateCandidate(edge);put('edges',edge);
 };
 if(command.kind==='connect')connect(command);
 else if(command.kind==='setStatus')setStatus(command.edge||all.find(e=>e.id===command.edgeId),command.status);
 else if(command.kind==='setType'){
  const edge=command.edge||all.find(e=>e.id===command.edgeId);if(!edge)fail('INVALID_PACKAGE','关系已不存在。');
  if(command.type!==edge.type){setStatus(edge,'dismissed');connect({...edge,type:command.type,reason:command.reason});}
 }else{
  const id=command.viewId||command.view?.id;if(!id)fail('INVALID_PACKAGE','需要画布视图。');const view=structuredClone((records.graphViews||[]).find(v=>v.id===id)||command.view||defaultGraphView(id));view.updatedAt=command.updatedAt||view.updatedAt;
  if(command.viewport)view.viewport=structuredClone(command.viewport);if(command.nodes)view.nodes=structuredClone(command.nodes);
  const node=ref=>{let n=view.nodes.find(n=>refKey(n.ref)===refKey(ref));if(!n){n={ref,x:0,y:0,pinned:false,groups:[]};view.nodes.push(n);}return n;};
  if(command.kind==='move'){const n=node(command.ref);n.x=command.x;n.y=command.y;n.pinned=true;}
  else if(command.kind==='setPinned')node(command.ref).pinned=command.pinned;
  else if(command.kind==='setViewport'){view.viewport=command.viewport;if(command.mode)view.mode=command.mode;if(command.nodes)view.nodes=structuredClone(command.nodes);}
  else if(command.kind==='setGroup'){const g=command.group;view.groups=view.groups.filter(x=>x.id!==g.id);if(!command.remove)view.groups.push(structuredClone(g));for(const n of view.nodes)n.groups=view.groups.filter(g=>g.members.some(r=>refKey(r)===refKey(n.ref))).map(g=>g.id);}
  else if(command.kind==='setVisibility'){const key=refKey(command.ref);view.excludedRefs=view.excludedRefs.filter(r=>refKey(r)!==key);if(!command.visible)view.excludedRefs.push(command.ref);}
  else if(command.kind==='addContext'){
   const revision=records.revisions.find(r=>r.id===command.revisionId),g=revision?.lesson.glossary?.find(g=>g.id===command.glossaryId);if(!g)fail('INVALID_PACKAGE','请选择已有修订中的辅助释义。');
   const existing=[...records.contexts||[],...(records.graphViews||[]).flatMap(v=>v.contextRefs)].find(c=>c.revisionId===revision.id&&c.glossaryId===g.id),context=existing||{id:'context-'+fingerprint(revision.id+'|'+g.id),revisionId:revision.id,glossaryId:g.id};
   if(!view.contextRefs.some(c=>c.id===context.id))view.contextRefs.push(context);view.excludedRefs=view.excludedRefs.filter(r=>r.space!=='pending'||r.id!==context.id);
  }else fail('INVALID_PACKAGE','未知画布操作。');
  put('graphViews',view);
 }
 return finish(snapshot,plan);
}
