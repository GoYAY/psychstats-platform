import {resolveTermRef,safeId} from './contract.mjs';
export function matchTerm(query,catalogue,personalTerms){return resolveTermRef(query,[...catalogue.filter(t=>t.published===true).map(t=>({...t,space:'official'})),...personalTerms.filter(t=>!t.trashed).map(t=>({...t,space:'personal'}))]);}
export function termURL(ref,catalogue,personalTerms,siteRoot){
 if(ref.space==='official'){const term=catalogue.find(t=>t.id===ref.id&&t.published===true);if(term&&/^terms\/[a-z0-9-]+\.html$/.test(term.path))return new URL(term.path,siteRoot).href;}
 if(ref.space==='personal'&&personalTerms.some(t=>t.id===ref.id&&!t.trashed))return new URL('library/index.html#term='+encodeURIComponent(safeId(ref.id)),siteRoot).href;return null;
}
export function reconcileCatalogue(oldCatalogue,newCatalogue,edges){
 const terms=newCatalogue.terms||[],candidates=[],unavailable=[];
 for(const edge of edges){for(const side of ['from','to']){const ref=edge[side];if(!ref)continue;if(ref.space==='official'&&!terms.some(t=>t.id===ref.id&&t.published))unavailable.push({edgeId:edge.id,ref});
  if(ref.space==='pending'&&terms.some(t=>t.id===ref.id&&t.published)&&!(edge.status==='dismissed'&&edge.catalogueVersion===newCatalogue.catalogueVersion))candidates.push({edgeId:edge.id,side,ref:{space:'official',id:ref.id},status:'suggested',catalogueVersion:newCatalogue.catalogueVersion});
 }}return {candidates,unavailable};
}
