import {nextFrameworkBatch,frameworkInputHash,frameworkTermFingerprint} from './framework-summary.mjs';
import {planFrameworkSuggestions} from './framework-suggestions.mjs';
import {planGraphInverse} from './graph-commands.mjs';
export function startFrameworkOrganizer({store,serviceURL='http://127.0.0.1:8781',getPublicContext,onState=()=>{},onApplied=()=>{},signal,fetcher=globalThis.fetch,transport=null}={}){
 const preferenceKey=transport?'framework-organizer-online':'framework-organizer',consentVersion=transport?3:2;const url=new URL(serviceURL);if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||url.username||url.password||url.pathname!=='/'||url.search||url.hash)throw Error('整理服务只能使用本机回环地址。');
 let disposed=false,settings={enabled:false,processedTerms:{}},timer,running=null,requestAbort,epoch=0,queued=false,status={status:'disabled',enabled:false,canUndo:false};
 const notify=next=>{status={...status,...next,enabled:!!settings.enabled,canUndo:!!settings.lastInverse,report:settings.lastReport||null};if(!disposed)onState({...status});};
 const persist=async()=>{if(!disposed)await store.setPreference(preferenceKey,settings);};
 const ready=(async()=>{const saved=await store.getPreference(preferenceKey);if(saved&&typeof saved==='object')settings={...settings,...saved};if(settings.consentVersion!==consentVersion){settings.enabled=false;if(settings.pending){settings.previousPending=settings.pending;settings.pending=null;}settings.processedTerms={};}notify({status:!settings.enabled?'disabled':settings.pending?'pending':settings.lastReport?.status||'idle',message:settings.consentVersion!==consentVersion?'新整理包含背景简释和推断关系，请阅读发送范围后重新开启。':settings.lastReport?.message||''});if(settings.enabled)schedule();})();
 async function execute({retry=false}={}){
  const token=++epoch;requestAbort=new AbortController();const controller=requestAbort,live=()=>!disposed&&settings.enabled&&epoch===token&&!controller.signal.aborted;
  await ready;if(!live())return null;const context=await getPublicContext();if(!live())return null;const snapshot=await store.snapshot();if(!live())return null;
  const batch=await nextFrameworkBatch(snapshot.records,context,settings.processedTerms||{},retry);if(!live())return null;
  let pending=settings.pending;
  if(pending?.invalid){if(!retry){notify({status:'needs-review',message:'上次任务已失效。手动重试将重新提交，可能再次消耗模型额度。'});return null;}pending.taskId=null;delete pending.invalid;await persist();if(!live())return null;}
  if(!pending){
   if(!batch.changed){notify({status:settings.lastReport?.status||'idle',message:settings.lastReport?.message||'没有新增或变更的概念需要整理。'});return null;}
   const hash=await frameworkInputHash(batch.input);if(!live())return null;
   if(!retry&&settings.failedInputHash===hash)return null;
   pending={input:batch.input,inputHash:hash,taskId:null,fingerprints:batch.fingerprints,remaining:batch.remaining,scope:{changed:batch.changed,anchors:batch.anchors,referenceFrames:batch.referenceFrames,totalFrames:batch.totalFrames}};
   settings.pending=pending;settings.lastInverse=null;await persist();if(!live())return null;
  }else if(!pending.taskId&&!retry){notify({status:'needs-review',message:'上次任务的提交状态未确认。请手动重试以核对，已有资料保持不变。'});return null;}
  async function json(path,options={}){if(!live())throw new DOMException('Cancelled','AbortError');if(transport){if(path==='/jobs'&&options.method==='POST')return transport.submit(JSON.parse(options.body),pending.inputHash,{signal:controller.signal});if(path.startsWith('/jobs/'))return transport.get(decodeURIComponent(path.slice(6)),{signal:controller.signal});throw Error('不支持的整理请求。');}const response=await fetcher(new URL(path,url).href,{cache:'no-store',credentials:'omit',...options,signal:controller.signal});if(!live())throw new DOMException('Cancelled','AbortError');const value=await response.json();if(!response.ok){const error=Error(value.error?.message||'本机任务不可读取，请核对服务后手动重试。');error.status=response.status;throw error;}return value;}
  notify({status:'running',message:pending.taskId?'继续领取已提交的后台任务，不重复调用模型。':'正在后台整理新增或变更的概念，阅读不受影响。'});
  if(!pending.taskId){const submitted=await json('/jobs',{method:'POST',headers:{'Content-Type':'application/json',...(retry?{'X-Framework-Retry':'1'}:{})},body:JSON.stringify(pending.input)});if(!live())return null;pending.taskId=submitted.taskId;settings.lastTaskId=submitted.taskId;await persist();if(!live())return null;}
  const started=Date.now();let job;
  while(live()){job=await json('/jobs/'+encodeURIComponent(pending.taskId));if(job.status==='complete'||job.status==='failed')break;if(Date.now()-started>600000)throw Error('任务等待较久，稍后可继续领取原任务；已有资料保持不变。');await new Promise(resolve=>setTimeout(resolve,500));}
  if(!live())return null;
  if(job.status==='failed'){
   settings.failedInputHash=pending.inputHash;settings.pending=null;settings.lastReport={status:'failed',message:job.error?.message||'整理未完成，可手动重试。',taskId:pending.taskId,usage:job.usage||null,calls:job.calls||0,conflicts:[],unassigned:[],scope:pending.scope};await persist();if(live())notify({status:'failed',message:settings.lastReport.message});return null;
  }
  const fresh=await store.snapshot();if(!live())return null;
  const planned=await planFrameworkSuggestions(fresh,job.result,{taskId:pending.taskId,baseInput:pending.input,baseInputHash:pending.inputHash,...context});if(!live())return null;
  if(planned.plan.writes.length){await store.commit(planned.plan,{expectedVersion:fresh.version,signal:controller.signal});if(!live())return null;settings.lastInverse=planned.inverse;}
  settings.processedTerms={...settings.processedTerms,...pending.fingerprints};
  const expected=structuredClone(fresh.records);for(const w of planned.plan.writes)expected[w.kind]=[...expected[w.kind].filter(v=>v.id!==w.id),w.value];
  const inputKeys=new Set(pending.input.terms.map(t=>t.ref.space+':'+t.ref.id));for(const w of planned.plan.writes.filter(w=>w.kind==='frameworks'))for(const row of w.value.provenance?.memberReasons||[]){const key=row.ref.space+':'+row.ref.id;if(!inputKeys.has(key)){const fingerprint=await frameworkTermFingerprint(expected,row.ref,context);if(fingerprint)settings.processedTerms[key]=fingerprint;}}
  settings.pending=null;settings.failedInputHash=null;settings.lastInputHash=pending.inputHash;
  const message=(planned.conflicts.length||planned.review?.length)?'整理建议待审阅，未覆盖人工修改。':'框架已自动整理，可修改或撤销。';
  settings.lastReport={status:planned.conflicts.length||planned.review?.length?'needs-review':'complete',message,taskId:pending.taskId,usage:job.result.usage,calls:job.result.calls,conflicts:planned.conflicts,review:planned.review||[],contexts:job.result.contexts||[],groups:job.result.groups,unassigned:job.result.unassigned,scope:pending.scope};await persist();if(!live())return null;
  notify({status:settings.lastReport.status,message,calls:job.result.calls,usage:job.result.usage});await onApplied(planned);
  if(pending.remaining)queued=true;
  return planned;
 }
 function runNow(options={}){clearTimeout(timer);if(disposed)return Promise.resolve(null);if(running){queued=true;return running;}running=execute(options).catch(async e=>{if(!disposed&&settings.enabled&&e.status===404&&settings.pending){settings.pending.invalid=true;await persist();notify({status:'needs-review',message:'上次任务已失效。手动重试将重新提交，可能再次消耗模型额度。'});return null;}if(!disposed&&settings.enabled&&e.name!=='AbortError')notify({status:'failed',message:e.message||'整理服务暂不可用，仍可手动整理。'});return null;}).finally(()=>{running=null;if(queued&&!disposed&&settings.enabled){queued=false;schedule();}});return running;}
 function schedule(){if(disposed||!settings.enabled)return;if(running){queued=true;return;}clearTimeout(timer);timer=setTimeout(()=>runNow(),750);}
 async function setEnabled(enabled){await ready;settings.enabled=!!enabled;if(enabled)settings.consentVersion=consentVersion;if(!enabled){epoch++;queued=false;clearTimeout(timer);requestAbort?.abort();}await persist();notify({status:enabled?'idle':'disabled',message:enabled?'已开启：增量整理框架、必要简释及可撤销推断关系。':'自动整理已关闭。'});if(enabled)schedule();}
 async function dismissReport(){await ready;if(settings.lastReport){settings.lastReport={...settings.lastReport,status:'complete',message:'已忽略本次建议，原有框架保持不变。',conflicts:[],review:[],dismissed:true};await persist();notify({status:settings.enabled?'complete':'disabled',message:settings.lastReport.message});}}
 async function undoLast(){await ready;if(!settings.lastInverse)return;const s=await store.snapshot(),result=planGraphInverse(s,settings.lastInverse);await store.commit(result.plan,{expectedVersion:s.version});settings.lastInverse=null;await persist();notify({status:'idle',message:'已撤销上次模型整理。'});await onApplied(result);}
 function dispose(){disposed=true;epoch++;queued=false;clearTimeout(timer);requestAbort?.abort();signal?.removeEventListener('abort',dispose);}signal?.addEventListener('abort',dispose,{once:true});
 return {ready,schedule,runNow,setEnabled,acceptSemanticConsent:()=>setEnabled(true),undoLast,dismissReport,dispose,getState:()=>({...status})};
}
