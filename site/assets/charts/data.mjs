// Public teaching data only. Never pass a lesson/evidence object to a widget.
import {validatePresentation} from './presentation.mjs';
const text=(v,n)=>typeof v==='string'&&v.trim().length>0&&v.length<=n;
const number=v=>typeof v==='number'&&Number.isFinite(v);
export function validateBarData(input){
 if(!input||input.version!==1||!text(input.title,120)||!text(input.xLabel,80)||!text(input.yLabel,80)||typeof input.note!=='string'||input.note.length>400||!Array.isArray(input.series)||input.series.length<1||input.series.length>4)return null;
 const series=[];let categories;
 for(const [i,s] of input.series.entries()){
  if(!s||!text(s.label,40)||!Array.isArray(s.points)||s.points.length<1||s.points.length>200)return null;
  const points=[];const seen=new Set();
  for(const p of s.points){if(!p||!text(p.category,40)||seen.has(p.category)||!number(p.value)||p.value<0)return null;seen.add(p.category);points.push({category:p.category,value:p.value});}
  const keys=points.map(p=>p.category);if(categories&&keys.some((k,j)=>k!==categories[j])||categories&&keys.length!==categories.length)return null;categories=keys;
  series.push({id:'s'+i,label:s.label,points});
 }
 const result={version:1,title:input.title,xLabel:input.xLabel,yLabel:input.yLabel,series,note:input.note};
 if(input.reference!==undefined){if(!number(input.reference?.value)||!text(input.reference?.label,80))return null;result.reference={value:input.reference.value,label:input.reference.label};}
 return result;
}
export function officialBarData(visual){
 try{
  if(visual?.decision!=='draw'||visual.kind!=='bars'||!Array.isArray(visual.chart?.series))return null;
  const result=validateBarData({version:1,title:visual.title,xLabel:visual.chart.x_label,yLabel:visual.chart.y_label,note:visual.takeaway||'',series:visual.chart.series.map(s=>({label:s.label,points:s.values.map(v=>({category:String(v[0]),value:v[1]}))}))});
  // Only encode an existing numeric-axis mean; never infer midpoints for bins.
  if(result&&result.series.length===2&&result.series.every(s=>s.points.every(p=>/^\d+(?:\.\d+)?$/.test(p.category))&&s.points.reduce((n,p)=>n+p.value,0)===10&&s.points.reduce((n,p)=>n+Number(p.category)*p.value,0)===800))result.reference={value:80,label:'两班均分80分'};
  return result;
 }catch{return null;}
}
export function personalBarData(visual){
 try{
  const policy=visual&&validatePresentation(visual);
  if(policy&&policy.interaction!=='inspect')return null;
  const p=visual?.payload;
  if(visual?.kind!=='statistical'||p?.chart_type!=='bar'||!['conceptual','teaching','source','theoretical'].includes(visual.origin))return null;
  if(!['title','takeaway','alt'].every(k=>text(visual[k],1000))||['source','theoretical'].includes(visual.origin)&&!visual.refs?.length)return null;
  for(const axis of ['x','y'])if(!text(p[axis+'_label'],40)||typeof (p[axis+'_unit']??'')!=='string'||(p[axis+'_unit']||'').length+p[axis+'_label'].length>40)return null;
  if(!Array.isArray(p.series))return null;
  const series=p.series.map(s=>{
   if(!text(s.label,24)||!Array.isArray(s.x)||!Array.isArray(s.y)||s.x.length!==s.y.length)throw Error('Invalid series');
   return {label:s.label,points:s.x.map((x,i)=>{if(!(number(x)||text(x,24)))throw Error('Invalid category');return {category:String(x),value:s.y[i]};})};
  });
  const axis=a=>p[a+'_label']+(p[a+'_unit']?'（'+p[a+'_unit']+'）':'');
  return validateBarData({version:1,title:visual.title,xLabel:axis('x'),yLabel:axis('y'),series,note:visual.takeaway});
 }catch{return null;}
}
