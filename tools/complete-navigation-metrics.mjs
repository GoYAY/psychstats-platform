export const percentile=(values,p)=>{const sorted=values.filter(Number.isFinite).sort((a,b)=>a-b);return sorted.length?sorted[Math.ceil(sorted.length*p)-1]:null;};
export function presentationEvidence(events){
 // DrawFrame/BeginFrame and RAF are opportunities, not display presentation.
 // This CDP trace lacks an authenticated frame-to-display timestamp mapping.
 return {status:'unmeasured',candidateEvents:events.filter(e=>/FramePresented|PresentationFeedback/.test(e.name)).length,reason:'No verified compositor frame-to-display mapping; RAF is not used as a substitute.'};
}
export function evaluateGate(samples){
 const reasons=[],summary={};
 for(const version of ['old','new','online'])for(const scenario of ['paths','topic','variable','sem']){
  const group=samples.filter(s=>s.version===version&&s.scenario===scenario);summary[version+':'+scenario]={};
  for(const temperature of ['cold','warm']){const rows=group.filter(s=>s.temperature===temperature),required=temperature==='cold'?3:5;
   if(rows.length<required||rows.some(r=>!Number.isFinite(r.targetReadyMs)||!Number.isFinite(r.clientCommitMs)))reasons.push(`Missing valid ${version}/${scenario}/${temperature} metrics`);
   summary[version+':'+scenario][temperature]={n:rows.length,readyMedian:percentile(rows.map(r=>r.targetReadyMs),.5),readyP95:percentile(rows.map(r=>r.targetReadyMs),.95),clientMedian:percentile(rows.map(r=>r.clientCommitMs),.5),layoutMax:Math.max(0,...rows.flatMap(r=>(r.layout||[]).map(x=>x.ms)))};
  }
 }
 for(const scenario of ['paths','topic','variable','sem']){
  const old=summary['old:'+scenario].cold,next=summary['new:'+scenario].cold;
  if(next.readyMedian>=old.readyMedian||next.readyP95>=old.readyP95)reasons.push(`Cold target-ready has not improved for ${scenario}`);
 }
 if(samples.some(s=>s.version==='new'&&s.anchorDrift>1))reasons.push('New shell/topic anchor drift exceeds 1px');
 if(samples.some(s=>s.version==='new'&&(s.layout||[]).some(l=>l.ms>50)))reasons.push('New version still has a layout task over 50ms');
 if(!samples.length||samples.some(s=>s.version==='new'&&s.presentationStatus!=='measured'))reasons.push('Presentation p95 unmeasured; automatic performance PASS is withheld');
 return {status:reasons.length?'fail':'pass',reasons,summary};
}
