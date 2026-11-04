import {resolveTermRef} from './contract.mjs';
const normalize=v=>String(v||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');
export function matchSemanticTerm(candidate,{records,catalogue=[]}){
 const registry=[...records.terms.filter(t=>!t.trashed).map(t=>({...t,space:'personal'})),...catalogue.filter(t=>t.published!==false).map(t=>({...t,space:'official'}))];
 const contexts=new Map([...records.contexts||[],...(records.graphViews||[]).flatMap(v=>v.contextRefs)].map(c=>[c.id,c]));
 for(const c of contexts.values()){const g=records.revisions.find(r=>r.id===c.revisionId)?.lesson.glossary?.find(g=>g.id===c.glossaryId);if(c.name||g)registry.push({id:c.id,space:'pending',zh:c.name||g.term,aliases:c.aliases||g.aliases||[]});}
 const names=[candidate.name,...candidate.aliases||[]].filter(n=>typeof n==='string'&&n.trim()),matches=new Map();for(const name of names)for(const ref of resolveTermRef(name,registry).candidates)matches.set(ref.space+':'+ref.id,ref);const candidates=[...matches.values()],result={ref:candidates.length===1?candidates[0]:null,candidates};if(candidates.length)return result;
 const glossaryCandidates=[];for(const term of records.terms.filter(t=>!t.trashed)){const revision=records.revisions.find(r=>r.id===term.currentRevisionId);for(const g of revision?.lesson.glossary||[])if([g.term,...g.aliases||[]].some(n=>names.some(name=>normalize(n)===normalize(name))))glossaryCandidates.push({revisionId:revision.id,glossaryId:g.id});}
 return {...result,glossaryCandidates};
}
