// Saved teaching definitions, never PDF excerpts or fabricated graph membership.
const normalize=v=>String(v||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');
export function glossaryContextId(revisionId,glossaryId){let a=2166136261,b=2246822507;for(const c of revisionId+'|'+glossaryId){a=Math.imul(a^c.charCodeAt(0),16777619);b=Math.imul(b^c.charCodeAt(0),3266489909);}return 'context-'+(a>>>0).toString(16).padStart(8,'0')+(b>>>0).toString(16).padStart(8,'0');}
export function backgroundCandidates(records){
 const contexts=[...records.contexts||[],...(records.graphViews||[]).flatMap(v=>v.contextRefs)],rows=new Map();
 for(const t of records.terms.filter(t=>!t.trashed)){const revision=records.revisions.find(r=>r.id===t.currentRevisionId);for(const g of revision?.lesson.glossary||[]){if(!g.explanation?.trim()||[t.zh,t.en,...t.aliases||[]].some(n=>n&&normalize(n)===normalize(g.term)))continue;const existing=contexts.find(c=>c.revisionId===revision.id&&c.glossaryId===g.id),context=existing||{id:glossaryContextId(revision.id,g.id),revisionId:revision.id,glossaryId:g.id},key='pending:'+context.id,collision=rows.get(key);if(collision&&(collision.context.revisionId!==revision.id||collision.context.glossaryId!==g.id))throw Error('背景候选身份冲突，请核对修订。');rows.set(key,{context,parentRef:{space:'personal',id:t.id},term:{ref:{space:'pending',id:context.id},name:g.term,definition:g.explanation,summary:'',revisionId:revision.id}});}}
 return [...rows.values()];
}
