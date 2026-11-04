import {fail} from './contract.mjs';
let state={state:'not-prepared',message:'尚未准备离线阅读'};
export const offlineStatus=()=>({...state});
export function validateOfflineResources(manifest,scope){
 const base=new URL(scope),root=new URL('../',base);if(!base.pathname.endsWith('/library/'))fail('INVALID_PACKAGE','离线作用域仅限 library/。');
 if(!manifest?.version||!Array.isArray(manifest.resources))fail('INVALID_PACKAGE','离线清单无效。');
 return manifest.resources.map(item=>{const url=new URL(item.url,base);if(url.origin!==base.origin||url.username||url.password||url.hash||url.search&&(!/^\?v=[a-f0-9]+$/.test(url.search))||!(/^[a-f0-9]{64}$/.test(item.hash))||!(url.pathname===base.pathname+'index.html'||url.pathname.startsWith(root.pathname+'assets/')))fail('INVALID_PACKAGE','离线清单包含范围外资源。');return {...item,url:url.href};});
}
function queryWorker(worker,signal){return new Promise((resolve,reject)=>{const channel=new MessageChannel(),timer=setTimeout(()=>finish(null,Error('离线状态读取超时，请重试。')),10000);const abort=()=>finish(null,Error('已取消离线准备。'));function finish(value,error){clearTimeout(timer);channel.port1.close();channel.port2.close();signal?.removeEventListener('abort',abort);error?reject(error):resolve(value);}signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted){abort();return;}channel.port1.onmessage=e=>finish(e.data);worker.postMessage({type:'offline-status'},[channel.port2]);});}
export async function prepareOffline({scope,manifest,signal}={}){
 if(!globalThis.navigator?.serviceWorker||!globalThis.isSecureContext)return state={state:'unavailable',message:'此浏览器或地址不支持离线缓存。'};
 const base=new URL(scope),workerURL=new URL('sw.js',base);validateOfflineResources(manifest,base);
 const registrations=await navigator.serviceWorker.getRegistrations(),existing=registrations.find(r=>r.scope===base.href);
 if(existing&&[existing.active,existing.waiting,existing.installing].filter(Boolean).some(w=>new URL(w.scriptURL).pathname!==workerURL.pathname))return state={state:'unavailable',message:'此路径已有其他离线程序，未替换其注册。'};
 if(signal?.aborted)throw Error('已取消离线准备。');state={state:'preparing',message:'正在校验离线资源'};
 try{
  const registration=await navigator.serviceWorker.register(workerURL,{scope:base.href,updateViaCache:'none'});
  if(!registration.active){await new Promise((resolve,reject)=>{const timer=setTimeout(()=>finish(Error('离线资源准备超时，联网时可以重试。')),30000),abort=()=>finish(Error('已取消离线准备。'));let worker=registration.installing||registration.waiting;const changed=()=>{if(worker?.state==='activated')finish();if(worker?.state==='redundant')finish(Error('离线资源校验未通过，已有缓存保持不变。'));};function finish(error){clearTimeout(timer);signal?.removeEventListener('abort',abort);worker?.removeEventListener('statechange',changed);registration.removeEventListener('updatefound',found);error?reject(error):resolve();}function found(){worker=registration.installing;worker?.addEventListener('statechange',changed);changed();}registration.addEventListener('updatefound',found);signal?.addEventListener('abort',abort,{once:true});worker?.addEventListener('statechange',changed);changed();});}
  const result=await queryWorker(registration.active,signal);if(result.state!=='ready')throw Error('离线缓存尚未完整准备。');return state={state:'ready',version:result.version,message:'离线阅读已就绪；个人资料保存在本机数据库。'};
 }catch(e){state={state:'not-prepared',message:e.message};throw e;}
}
