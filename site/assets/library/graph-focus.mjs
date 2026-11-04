import {refKey} from './graph-identity.mjs';
export function representativeNode(model,framework={}){
 if(!model.nodes.length)return null;const degree=new Map(model.nodes.map(n=>[refKey(n.ref),0])),core=new Set((framework?.memberDetails||[]).filter(row=>row.role==='core').map(row=>refKey(row.ref)));
 for(const e of model.edges)if(degree.has(refKey(e.from))&&degree.has(refKey(e.to))){degree.set(refKey(e.from),degree.get(refKey(e.from))+1);degree.set(refKey(e.to),degree.get(refKey(e.to))+1);}
 const connected=model.nodes.filter(n=>degree.get(refKey(n.ref))>0),pool=connected.length?connected:model.nodes,ranked=pool.map((n,i)=>({n,i,key:refKey(n.ref)})).sort((a,b)=>Number(core.has(b.key))-Number(core.has(a.key))||Math.abs(degree.get(a.key)-3)-Math.abs(degree.get(b.key)-3)||a.i-b.i);return {...ranked[0].n.ref};
}
export function indexGraph(model){
 const nodes=new Map(model.nodes.map(n=>[refKey(n.ref),n])),incident=new Map([...nodes.keys()].map(k=>[k,[]]));
 for(const edge of model.edges){const a=refKey(edge.from),b=refKey(edge.to);if(!nodes.has(a)||!nodes.has(b))continue;incident.get(a).push(edge);if(a!==b)incident.get(b).push(edge);}
 return {nodes,incident,model};
}
export function focusGraph(index,{selectedKey=null,type=null}={}){
 const points=[...index.nodes.values()],selected=index.nodes.get(selectedKey);
 if(!selected)return {points,cards:[],edges:[],selectedKey:null,totalRelations:0,shownRelations:0};
 const all=index.incident.get(selectedKey)||[],edges=all.filter(e=>!type||e.type===type),keys=new Set([selectedKey]);
 for(const edge of edges){keys.add(refKey(edge.from));keys.add(refKey(edge.to));}
 const cards=[selected,...[...keys].filter(k=>k!==selectedKey).sort().map(k=>index.nodes.get(k))];
 return {points,cards,edges,selectedKey,totalRelations:all.length,shownRelations:edges.length};
}
export function focusLayout(projection,positions,offset={x:0,y:0}){
 const result=Object.fromEntries(Object.entries(positions).map(([k,p])=>[k,{...p}]));if(!projection.selectedKey)return result;
 const center=result[projection.selectedKey]||{x:0,y:0},neighbors=projection.cards.filter(n=>refKey(n.ref)!==projection.selectedKey),radius=Math.max(290,neighbors.length*270/(2*Math.PI));
 for(const [i,node] of neighbors.entries()){const angle=-Math.PI/2+i*Math.PI*2/Math.max(1,neighbors.length),key=refKey(node.ref);if(result[key]?.pinned)continue;result[key]={...result[key],ref:node.ref,x:center.x+Math.cos(angle)*radius,y:center.y+Math.sin(angle)*radius};}
 for(const node of projection.cards){const p=result[refKey(node.ref)];if(p){p.x+=offset.x;p.y+=offset.y;}}
 return result;
}
