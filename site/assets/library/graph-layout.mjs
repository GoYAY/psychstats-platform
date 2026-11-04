import {refKey} from './graph-identity.mjs';
// Bounded, deterministic placement. No DOM reads, clocks, timers or physics loop.
export function layoutGraph(model,{mode='structure',previousView={},nodeSize={}}={}){
 const nodes=[...model.nodes].sort((a,b)=>refKey(a.ref).localeCompare(refKey(b.ref))),keys=new Set(nodes.map(n=>refKey(n.ref))),adj=new Map(nodes.map(n=>[refKey(n.ref),[]])),warnings=[];
 const size=key=>nodeSize[key]||{width:200,height:86},positions={},old=new Map((previousView.nodes||[]).map(n=>[refKey(n.ref),n]));
 for(const e of model.edges){const a=refKey(e.from),b=refKey(e.to);if(a!==b&&keys.has(a)&&keys.has(b)){adj.get(a).push(b);adj.get(b).push(a);}}
 // Organization groups affect placement only. They never add semantic edges.
 for(const g of model.groups||[]){const members=g.members.map(refKey).filter(k=>keys.has(k));for(const key of members.slice(1)){adj.get(members[0]).push(key);adj.get(key).push(members[0]);}}
 const seen=new Set(),components=[];for(const node of nodes){const start=refKey(node.ref);if(seen.has(start))continue;const queue=[start],part=[];seen.add(start);for(let i=0;i<queue.length;i++){const key=queue[i];part.push(key);for(const next of [...adj.get(key)].sort())if(!seen.has(next)){seen.add(next);queue.push(next);}}components.push(part.sort());}
 const dependency=new Map(nodes.map(n=>[refKey(n.ref),[]]));for(const e of model.edges)if(keys.has(refKey(e.from))&&keys.has(refKey(e.to))){if(mode==='learning'&&e.type==='prerequisites')dependency.get(refKey(e.from)).push(refKey(e.to));if(mode==='structure'&&e.type==='components')dependency.get(refKey(e.to)).push(refKey(e.from));}
 const levels=new Map(),visiting=new Set();const rank=key=>{if(levels.has(key))return levels.get(key);if(visiting.has(key)){warnings.push({code:'PREREQUISITE_CYCLE',ref:key});return 0;}visiting.add(key);const level=Math.max(0,...dependency.get(key).map(k=>rank(k)+1));visiting.delete(key);levels.set(key,level);return level;};
 if(mode!=='free')for(const n of nodes)rank(refKey(n.ref));
 let offset=0;
 for(const component of components){const columns=Math.max(1,Math.ceil(Math.sqrt(component.length))),rowsByRank=new Map();let maxRight=offset;
  component.forEach((key,index)=>{const saved=old.get(key),ref=nodes.find(n=>refKey(n.ref)===key).ref;let x,y;
   if(saved&&(saved.pinned||mode==='free'))({x,y}=saved);
   else if(mode==='learning'||mode==='structure'&&component.some(k=>(levels.get(k)||0)>0)){const level=levels.get(key)||0,row=rowsByRank.get(level)||0;x=offset+level*600+(row%2)*260;y=Math.floor(row/2)*146;rowsByRank.set(level,row+1);}
   else {x=offset+(index%columns)*290;y=Math.floor(index/columns)*146;}
   positions[key]={ref:{...ref},x,y,pinned:!!saved?.pinned};maxRight=Math.max(maxRight,x+size(key).width);
  });offset=maxRight+180;
 }
 if(mode==='structure'&&(model.groups||[]).length>1){let groupOffset=0;const centers=new Map();for(const group of [...model.groups].sort((a,b)=>a.id.localeCompare(b.id))){const own=nodes.filter(n=>n.memberships?.length===1&&n.memberships[0]===group.id),rows=new Map();if(!own.length)continue;for(const n of own){const key=refKey(n.ref),level=levels.get(key)||0,row=rows.get(level)||0;if(!positions[key].pinned){positions[key].x=groupOffset+level*290;positions[key].y=row*146;}rows.set(level,row+1);}const left=Math.min(...own.map(n=>positions[refKey(n.ref)].x)),right=Math.max(...own.map(n=>positions[refKey(n.ref)].x+200));centers.set(group.id,(left+right)/2);groupOffset=right+360;}for(const n of nodes.filter(n=>n.memberships?.length>1)){const key=refKey(n.ref),available=n.memberships.map(g=>centers.get(g)).filter(x=>x!==undefined);if(!positions[key].pinned&&available.length>1)positions[key].x=available.reduce((a,b)=>a+b,0)/available.length-100;}for(const n of nodes.filter(n=>!n.memberships?.length))if(!positions[refKey(n.ref)].pinned)positions[refKey(n.ref)].x+=groupOffset;}
 const placed=[],overlap=(a,b)=>{const sa=size(a),sb=size(b),p=positions[a],q=positions[b];return p.x<q.x+sb.width+16&&p.x+sa.width+16>q.x&&p.y<q.y+sb.height+16&&p.y+sa.height+16>q.y;};
 // Place fixed cards first; move only unpinned cards. At most n squared checks.
 const order=Object.keys(positions).sort((a,b)=>Number(positions[b].pinned)-Number(positions[a].pinned)||a.localeCompare(b));
 for(const key of order){let attempts=0;while(placed.some(other=>overlap(key,other))&&attempts++<=nodes.length){if(positions[key].pinned){warnings.push({code:'PINNED_OVERLAP',ref:key});break;}positions[key].y+=146;}placed.push(key);}
 const groups=(model.groups||[]).map(g=>{const members=g.members.map(refKey).filter(key=>positions[key]&&nodes.find(n=>refKey(n.ref)===key)?.memberships?.[0]===g.id);if(!members.length)return {...g,bounds:null};const left=Math.min(...members.map(k=>positions[k].x)),top=Math.min(...members.map(k=>positions[k].y));return {...g,bounds:{x:left-24,y:top-46,width:Math.max(...members.map(k=>positions[k].x+size(k).width))-left+48,height:Math.max(...members.map(k=>positions[k].y+size(k).height))-top+70}};});
 const all=Object.keys(positions),x=Math.min(0,...all.map(k=>positions[k].x-30)),y=Math.min(0,...all.map(k=>positions[k].y-55));
 const bounds={x,y,width:Math.max(300,...all.map(k=>positions[k].x+size(k).width+30))-x,height:Math.max(200,...all.map(k=>positions[k].y+size(k).height+30))-y};
 return {positions,groups,bounds,warnings};
}
