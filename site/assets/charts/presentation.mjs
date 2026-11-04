// Trusted rendering policy only. Never accept executable component settings.
function inspectionData(visual){
 const text=(v,n)=>typeof v==='string'&&v.trim().length>0&&v.length<=n,number=v=>typeof v==='number'&&Number.isFinite(v);
 if(!text(visual.title,120)||!text(visual.takeaway,400)||!text(visual.alt,1000)||!['conceptual','teaching','source','theoretical'].includes(visual.origin)||['source','theoretical'].includes(visual.origin)&&!visual.refs?.length)return false;
 const p=visual.payload;
 for(const axis of ['x','y'])if(!text(p[axis+'_label'],40)||typeof(p[axis+'_unit']??'')!=='string'||(p[axis+'_unit']||'').length+p[axis+'_label'].length>40)return false;
 return p.series.every(s=>text(s.label,24)&&Array.isArray(s.x)&&Array.isArray(s.y)&&s.x.length>=1&&s.x.length<=200&&s.x.length===s.y.length&&s.x.every(x=>number(x)||text(x,24))&&new Set(s.x.map(String)).size===s.x.length&&s.y.every(y=>number(y)&&y>=0));
}
export function validatePresentation(visual,{required=false}={}){
 const fail=message=>{throw Error('visual.presentation: '+message);};
 if(!Object.hasOwn(visual,'presentation')){if(required)fail('required for this generation policy');return null;}
 const p=visual.presentation,fields=['version','focus','numeric_role','layout','interaction'];
 if(!p||typeof p!=='object'||Array.isArray(p)||Object.keys(p).length!==fields.length||fields.some(k=>!Object.hasOwn(p,k)))fail('unknown or missing fields');
 if(p.version!==1)fail('unsupported version');
 const choices={focus:['whole','local','process','structure'],numeric_role:['exact','relative','none'],layout:['single','facets','overlay','grouped','story'],interaction:['none','inspect']};
 for(const [key,values] of Object.entries(choices))if(!values.includes(p[key]))fail('invalid '+key);
 if(visual.kind==='story'){if(p.layout!=='story'||p.interaction!=='none')fail('unsupported story layout or interaction');return {...p};}
 if(visual.kind!=='statistical'||p.numeric_role==='none')fail('invalid statistical role');
 const payload=visual.payload,series=payload?.series,chart=payload?.chart_type;
 if(!Array.isArray(series)||series.length<1||series.length>4||series.some(s=>!s||typeof s!=='object'||Array.isArray(s)))fail('invalid series');
 const layouts={bar:['grouped','facets'],histogram:['overlay','facets'],line:['overlay'],scatter:['overlay']};
 if(!Object.hasOwn(layouts,chart)||!(series.length===1?['single']:layouts[chart]).includes(p.layout))fail('unsupported chart/layout combination');
 if(p.interaction==='inspect'&&!(chart==='bar'&&['single','grouped'].includes(p.layout)&&p.numeric_role==='exact'))fail('unsupported inspection capability');
 if(p.interaction==='inspect'&&!inspectionData(visual))fail('data exceeds inspection host bounds; use none or supported exact chart without changing observations');
 if(['facets','grouped'].includes(p.layout)){
  const key=chart==='histogram'?'bin_edges':'x',values=series.map(s=>s[key]);
  if(values.some(v=>!Array.isArray(v)||!v.length||v.some(x=>typeof x==='boolean'))||values.slice(1).some(v=>v.length!==values[0].length||v.some((x,i)=>x!==values[0][i])))fail('facets/grouped require identical ordered categories/boundaries');
 }
 return {...p};
}
