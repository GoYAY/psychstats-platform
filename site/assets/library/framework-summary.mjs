import {refKey,edgeKey} from './graph-identity.mjs';
import {fail} from './contract.mjs';
import {backgroundCandidates} from './background-candidates.mjs';
export const canonical=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
export async function frameworkInputHash(payload){const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(payload)));return [...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');}
export async function frameworkTermFingerprint(records,ref,context={}){const term=collectTerms(records,{...context,termKeys:[refKey(ref)]}).get(refKey(ref));return term?frameworkInputHash(term):null;}
function collectTerms(records,{catalogue=[],officialGraph={terms:[],edges:[]},termKeys=null,includeCandidates=true}={}){
 const terms=new Map(),scope=termKeys?new Set(termKeys):null,official=new Map([...catalogue,...officialGraph.terms||[]].map(t=>[t.id,t]));
 const put=t=>{if(scope&&!scope.has(refKey(t.ref)))return;if(!t.name?.trim())fail('INVALID_SUMMARY','术语缺少名称。');for(const k of ['definition','summary'])if(t[k].length>1500)fail('SUMMARY_LIMIT','“'+t.name+'”摘要过长，请先缩短该概念摘要；未自动删减。');terms.set(refKey(t.ref),t);};
 const block=(revision,id)=>(revision?.lesson.blocks||[]).find(b=>b.id===id)?.paragraphs.map(p=>p.text).join('\n')||'';
 for(const term of records.terms.filter(t=>!t.trashed)){const revision=records.revisions.find(r=>r.id===term.currentRevisionId);put({ref:{space:'personal',id:term.id},name:term.zh,definition:block(revision,'operational_definition')||term.anchor?.definition||'',summary:block(revision,'plain_explanation'),revisionId:revision?.id||null});}
 const contexts=new Map([...records.contexts||[],...(records.graphViews||[]).flatMap(v=>v.contextRefs)].map(c=>[c.id,c]));
 for(const frame of records.frameworks||[])for(const r of [...frame.members,...(frame.excludedMembers||[]).map(row=>row.ref)]){if(terms.has(refKey(r)))continue;if(r.space==='official'){const t=official.get(r.id);if(t)put({ref:{...r},name:t.zh,definition:t.definition||'',summary:'',revisionId:null});}else if(r.space==='pending'){const context=contexts.get(r.id),revision=records.revisions.find(v=>v.id===context?.revisionId),g=context?.name?{term:context.name,explanation:context.definition}:revision?.lesson.glossary?.find(g=>g.id===context?.glossaryId);if(g)put({ref:{...r},name:g.term,definition:g.explanation,summary:'',revisionId:revision?.id||null});}}
 if(includeCandidates){const candidates=backgroundCandidates(records),chosen=scope?candidates.filter(c=>scope.has(refKey(c.term.ref))):candidates.slice(0,20);for(const c of chosen)if(!terms.has(refKey(c.term.ref)))put(c.term);}
 return terms;
}
export function summarizeFrameworkInput(records,context={}){
 const terms=collectTerms(records,context),{officialGraph={terms:[],edges:[]},frameKeys=null}=context,frameScope=frameKeys?new Set(frameKeys):null;
 const frameworks=(records.frameworks||[]).filter(f=>!frameScope||frameScope.has(f.id)).map(f=>{const members=f.members.filter(r=>terms.has(refKey(r))),details=new Map((f.memberDetails||[]).map(row=>[refKey(row.ref),row]));return {id:f.id,title:f.title,description:f.description,scope:f.scope??f.description,members,memberDetails:members.map(ref=>details.get(refKey(ref))||{ref,role:'existing',reason:'既有成员'}),excludedMembers:f.excludedMembers||[],revision:f.revision,locks:{...f.locks}};});
 const merged=new Map();for(const e of [...officialGraph.edges||[],...records.edges||[]])merged.set(edgeKey(e),e);
 const relations=[];for(const e of merged.values()){if(e.status==='dismissed'||!terms.has(refKey(e.from))||!terms.has(refKey(e.to)))continue;relations.push({from:{...e.from},to:{...e.to},type:e.type,basis:e.basis||(e.origin==='official'?'official':e.origin==='user'?'manual':'literature')});}
 const result={schemaVersion:2,terms:[...terms.values()].sort((a,b)=>refKey(a.ref).localeCompare(refKey(b.ref))),frameworks,relations};
 if(result.terms.length>200||frameworks.length>60||relations.length>5000||new TextEncoder().encode(canonical(result)).length>512*1024)fail('SUMMARY_LIMIT','本次整理范围过大，请选择较小范围；资料未删减。');return result;
}
export async function nextFrameworkBatch(records,context={},processed={},force=false){
 const primary=collectTerms(records,{...context,includeCandidates:false}),candidates=backgroundCandidates(records).filter(c=>!primary.has(refKey(c.term.ref))),terms=new Map([...primary,...candidates.map(c=>[refKey(c.term.ref),c.term])]),fingerprints=Object.fromEntries(await Promise.all([...terms].map(async([key,t])=>[key,await frameworkInputHash(t)])));
 const changed=[...primary.keys()].filter(key=>force||processed[key]!==fingerprints[key]).sort(),candidateChanged=candidates.filter(c=>force||processed[refKey(c.term.ref)]!==fingerprints[refKey(c.term.ref)]),selected=[...changed.slice(0,160),...candidateChanged.slice(0,20).map(c=>refKey(c.term.ref))],remaining=changed.length+candidateChanged.length-selected.length,keys=new Set(selected),anchors=[];
 for(const c of candidateChanged.slice(0,20)){const parent=refKey(c.parentRef);if(!keys.has(parent)&&terms.has(parent)){keys.add(parent);anchors.push(parent);}}
 // Compact representative definitions retain context without repeating old prose.
 const frames=[...(records.frameworks||[])].sort((a,b)=>(b.updatedAt||'').localeCompare(a.updatedAt||'')).slice(0,60);
 for(const frame of frames){let n=0;for(const ref of frame.members){const key=refKey(ref);if(keys.size>=200)break;if(!keys.has(key)&&terms.has(key)&&processed[key]===fingerprints[key]){anchors.push(key);keys.add(key);if(anchors.length>=40)break;if(++n>=2)break;}}if(anchors.length>=40||keys.size>=200)break;}
 const input=summarizeFrameworkInput(records,{...context,termKeys:[...keys],frameKeys:frames.map(f=>f.id)});
 for(const term of input.terms)if(anchors.includes(refKey(term.ref)))term.summary='';
 return {input,fingerprints:Object.fromEntries(selected.map(k=>[k,fingerprints[k]])),remaining,changed:selected.length,anchors:anchors.length,referenceFrames:frames.length,totalFrames:(records.frameworks||[]).length,background:{sent:candidateChanged.slice(0,20).length,remaining:Math.max(0,candidateChanged.length-20),total:candidates.length}};
}
export function currentBatchInput(records,baseInput,context={}){
 const input=summarizeFrameworkInput(records,{...context,termKeys:baseInput.terms.map(t=>refKey(t.ref)),frameKeys:baseInput.frameworks.map(f=>f.id)}),old=new Map(baseInput.terms.map(t=>[refKey(t.ref),t]));
 for(const term of input.terms)if(old.get(refKey(term.ref))?.summary==='')term.summary='';
 return input;
}
