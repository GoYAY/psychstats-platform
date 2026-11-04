import {refKey,edgeKey} from './graph-identity.mjs';
export const relationLabels={prerequisites:'需要先理解',components:'包含',contrasts:'对照理解',used_in:'应用于',next:'后续可学习'};
export function buildGraph({records,catalogue=[],officialGraph={terms:[],edges:[],frameworks:[]},view={},framework:customFramework=null}){
 const warnings=[],nodes=new Map(),wanted=new Map(),groups=[],privateTerms=new Map((records.terms||[]).map(t=>[t.id,t]));
 const official=new Map();for(const t of [...officialGraph.terms||[],...catalogue].filter(t=>t.published!==false)){const previous=official.get(t.id);official.set(t.id,{...previous,...t,definition:t.definition||previous?.definition||''});}
 const refs=ref=>wanted.set(refKey(ref),ref),frames=(officialGraph.frameworks||[]).filter(f=>view.frameworkId==='combined'||f.id===view.frameworkId);
 const contexts=new Map((records.contexts||[]).map(c=>[c.id,c]));for(const v of [...records.graphViews||[],view])for(const c of v.contextRefs||[])contexts.set(c.id,c);
 const framework=frames.length>0&&!customFramework;
 const strictLegacy=!customFramework&&!framework&&view.frameworkId&&view.frameworkId!=='all',savedFrame=strictLegacy?(records.frameworks||[]).find(f=>f.id===view.frameworkId):null;
 if(customFramework){for(const r of customFramework.members)refs(r);}
 else if(framework){for(const frame of frames){const members=[...new Set([...frame.core,...frame.oneHop])].map(id=>({space:'official',id}));for(const r of members)refs(r);groups.push({id:'framework-'+frame.id,title:frame.title,origin:'official',members,sourceRef:{kind:'official-framework',id:frame.id}});}}
 else {if(strictLegacy){for(const r of savedFrame?.members||[])refs(r);}else for(const t of privateTerms.values())if(!t.trashed)refs({space:'personal',id:t.id});for(const c of view.contextRefs||[])refs({space:'pending',id:c.id});}
 if(!customFramework)for(const n of view.nodes||[])refs(n.ref);
 for(const g of view.groups||[]){groups.push(structuredClone(g));if(!customFramework)for(const r of g.members)refs(r);}
 // Only direct targets of already selected personal concepts; never a citation/co-occurrence graph.
 if(!customFramework&&!strictLegacy)for(const e of records.edges||[])if(wanted.has(refKey(e.from))||wanted.has(refKey(e.to))){refs(e.from);refs(e.to);}
 const excluded=new Set((view.excludedRefs||[]).map(refKey)),excludedNodes=[];
 for(const [key,ref] of wanted){
  let label,kind,readingURL=null,explanation='';
  if(ref.space==='personal'){const t=privateTerms.get(ref.id);if(!t||t.trashed){warnings.push({code:'MISSING_PERSONAL',ref});continue;}label=t.zh;kind='personal';readingURL=t.currentRevisionId?'#term='+encodeURIComponent(t.id):null;explanation=t.anchor?.definition||'';}
  else if(ref.space==='official'){const t=official.get(ref.id);if(!t){warnings.push({code:'MISSING_OFFICIAL',ref});continue;}label=t.zh;kind='official';readingURL=t.path||null;explanation=t.definition||'';}
  else {const c=contexts.get(ref.id),revision=(records.revisions||[]).find(r=>r.id===c?.revisionId),g=c?.name?{term:c.name,explanation:c.definition}:revision?.lesson.glossary?.find(g=>g.id===c?.glossaryId);if(!g){warnings.push({code:'UNRESOLVED_CONTEXT',ref});continue;}label=g.term;kind='context';explanation=g.explanation;}
  nodes.set(key,{ref:{...ref},label,kind,explanation,readingURL,memberships:groups.filter(g=>g.members.some(r=>refKey(r)===key)).map(g=>g.id)});
 }
 for(const key of excluded)if(nodes.has(key)){excludedNodes.push(nodes.get(key));nodes.delete(key);}
 const allowedOfficial=new Set(frames.flatMap(f=>f.edgeKeys||[]));
 const candidates=[...(officialGraph.edges||[]).filter(e=>!framework||allowedOfficial.has(e.key||edgeKey(e))),...(records.edges||[])];
 const merged=new Map();
 for(const e of candidates){const key=edgeKey(e);if(!nodes.has(refKey(e.from))||!nodes.has(refKey(e.to)))continue;
  const previous=merged.get(key),rank=x=>x.status==='dismissed'?100:x.origin==='user'?50:x.origin==='model'?30:10;
  const sourceRecords=[...previous?.sourceRecords||[],...(e.origin==='official'?e.sourceRecords||[]:[{id:e.id,origin:e.origin,revisionId:e.revisionId}])];
  if(!previous||rank(e)>=rank(previous))merged.set(key,{...e,key,sourceRecords});else previous.sourceRecords=sourceRecords;
 }
 const edges=[...merged.values()].filter(e=>e.status!=='dismissed').sort((a,b)=>a.key.localeCompare(b.key));
 for(const g of groups)g.members=g.members.filter(r=>nodes.has(refKey(r)));
 return {nodes:[...nodes.values()].sort((a,b)=>refKey(a.ref).localeCompare(refKey(b.ref))),edges,groups,warnings,hiddenEdges:[...merged.values()].filter(e=>e.status==='dismissed'),excludedNodes};
}
