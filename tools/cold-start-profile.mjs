// QA only. CPU samples are approximate attribution, not display frame timing.
export function summarizeCPUProfile(profile){
 const nodes=new Map((profile.nodes||[]).map(n=>[n.id,n])),parents=new Map(),rows=new Map();
 for(const n of nodes.values())for(const child of n.children||[])parents.set(child,n.id);
 let sampledMs=0,idleMs=0;
 for(const [i,id] of (profile.samples||[]).entries()){
  const dt=(profile.timeDeltas?.[i]||0)/1000;sampledMs+=dt;
  if(nodes.get(id)?.callFrame?.functionName==='(idle)'){idleMs+=dt;continue;}
  let current=id;const visited=new Set();
  while(nodes.has(current)&&!visited.has(current)){
   visited.add(current);const f=nodes.get(current).callFrame||{},name=f.functionName||'(anonymous)';
   if(name!=='(root)'){
    const key=JSON.stringify([name,f.url,f.lineNumber,f.columnNumber]);
    if(!rows.has(key))rows.set(key,{name,url:f.url||'',line:(f.lineNumber??-1)+1,selfMs:0,inclusiveMs:0});
    const row=rows.get(key);row.inclusiveMs+=dt;if(current===id)row.selfMs+=dt;
   }
   current=parents.get(current);
  }
 }
 const rounded=v=>Math.round(v*100)/100;
 return {sampledMs:rounded(sampledMs),idleMs:rounded(idleMs),functions:[...rows.values()].map(r=>({...r,selfMs:rounded(r.selfMs),inclusiveMs:rounded(r.inclusiveMs)})).sort((a,b)=>b.selfMs-a.selfMs).slice(0,45)};
}
