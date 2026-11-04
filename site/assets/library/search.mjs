import {COLLECTIONS} from './contract.mjs';
const lower=v=>String(v||'').toLocaleLowerCase();
function documentFor(index,term){
 const r=index.records,revision=r.revisions.get(term.currentRevisionId);if(term.trashed)return null;
 const sourceIds=revision?.sourceIds||[],sources=sourceIds.map(id=>r.sources.get(id)).filter(Boolean);
 const chunks=(revision?.lesson.blocks||[]).flatMap(b=>b.paragraphs.map((p,i)=>({blockId:b.id,paragraph:i,text:p.text})));
 for(const e of r.evidence.values())if(e.revisionId===revision?.id&&e.status!=='deleted')chunks.push({blockId:'source:'+e.sourceId,text:e.data.text,evidence:true,sourceId:e.sourceId});
 return {termId:term.id,revisionId:revision?.id||null,zh:term.zh,en:term.en,aliases:term.aliases||[],tags:term.tags||[],originalMissing:sources.some(s=>s.originalStatus!=='saved'),chunks};
}
export function buildIndex(records){const index={records:Object.fromEntries(COLLECTIONS.map(k=>[k,new Map((records[k]||[]).map(r=>[r.id,r]))])),documents:new Map(),lastUpdated:0};for(const term of index.records.terms.values()){const doc=documentFor(index,term);if(doc)index.documents.set(term.id,doc);}return index;}
export function updateIndex(index,changes){
 const affected=new Set();for(const c of [...changes.deletes||[],...changes.writes||[]]){const old=index.records[c.kind]?.get(c.id);for(const v of [old,c.value].filter(Boolean)){if(c.kind==='terms')affected.add(v.id);if(c.kind==='revisions')affected.add(v.termId);if(c.kind==='evidence')for(const t of index.records.terms.values())if(index.records.revisions.get(t.currentRevisionId)?.id===v.revisionId)affected.add(t.id);if(c.kind==='sources')for(const t of index.records.terms.values())if(index.records.revisions.get(t.currentRevisionId)?.sourceIds.includes(v.id))affected.add(t.id);}}
 for(const d of changes.deletes||[])index.records[d.kind]?.delete(d.id);for(const w of changes.writes||[])index.records[w.kind]?.set(w.id,w.value);
 for(const t of index.records.terms.values())if((changes.writes||[]).some(w=>w.kind==='revisions'&&w.value.termId===t.id))affected.add(t.id);
 for(const id of affected){const term=index.records.terms.get(id),doc=term&&documentFor(index,term);if(doc)index.documents.set(id,doc);else index.documents.delete(id);}index.lastUpdated=affected.size;return index;
}
export function search(index,query,{tag=null,limit=30,includeEvidence=false}={}){
 query=String(query||'').trim();if(!query)return [];const needle=lower(query),hits=[];
 for(const d of index.documents.values()){if(tag&&!d.tags.includes(tag))continue;const labels=[d.zh,d.en,...d.aliases].filter(Boolean),exact=labels.some(v=>lower(v)===needle),label=labels.find(v=>lower(v).includes(needle));
  if(label){const start=lower(label).indexOf(needle);hits.push({...d,chunks:undefined,text:label,blockId:null,start,end:start+query.length,score:exact?100:60});}
  for(const chunk of d.chunks){if(chunk.evidence&&!includeEvidence)continue;const start=lower(chunk.text).indexOf(needle);if(start>=0)hits.push({termId:d.termId,revisionId:d.revisionId,zh:d.zh,originalMissing:d.originalMissing,...chunk,start,end:start+query.length,score:chunk.evidence?10:20});}
 }return hits.sort((a,b)=>b.score-a.score||a.termId.localeCompare(b.termId)||String(a.blockId).localeCompare(String(b.blockId))).slice(0,Math.max(0,Math.min(limit,1000)));
}
export function selectContext(index,query,{limit=5,maxChars=6000}={}){
 const out=[];let remaining=Math.max(0,Math.min(maxChars,6000));for(const hit of search(index,query,{includeEvidence:true,limit:1000})){if(out.length>=Math.min(limit,5)||!remaining)break;const start=Math.max(0,hit.start-180),text=hit.text.slice(start,start+Math.min(remaining,1600));out.push({...hit,text,start:Math.max(0,hit.start-start),end:Math.min(text.length,hit.end-start)});remaining-=text.length;}return out;
}
