// Same-origin transport. Invitations and CSRF tokens live only in memory.
export function createGenerationClient({apiRoot,origin=globalThis.location?.origin,fetcher=globalThis.fetch,signal}={}){
 const root=new URL(apiRoot,globalThis.location?.href);origin=origin||root.origin;
 if(root.origin!==origin||root.username||root.password||root.search||root.hash||!root.pathname.endsWith('/'))throw Error('生成服务必须使用当前网站的受控接口。');
 let csrf=null;
 async function request(path,{method='GET',value,headers={},raw=false,...options}={}){
  const mutation=!['GET','HEAD'].includes(method),opts={method,credentials:'same-origin',cache:'no-store',signal,...options,headers:{...(mutation&&csrf?{'X-CSRF-Token':csrf}:{}),...headers}};
  if(value!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(value);}
  const response=await fetcher(new URL(path,root),opts);
  if(!response.ok){let value;try{value=await response.json();}catch{}const error=Error(value?.error?.message||'生成服务暂时不可用，请稍后读取原任务。');error.code=value?.error?.code||'request_failed';error.status=response.status;if(error.status===401)csrf=null;throw error;}
  return raw?response:response.json();
 }
 const id=value=>{if(!/^[A-Za-z0-9_-]{1,128}$/.test(value))throw Error('任务标识无效。');return value;};
 return {
  async session(options={}){const s=await request('session',options);csrf=s.csrf;return s;},
  async login(invitation){const s=await request('sessions',{method:'POST',value:{invitation}});csrf=s.csrf;return s;},
  async logout(){try{return await request('session',{method:'DELETE'});}finally{csrf=null;}},
  async create(value,key,options={}){if(!/^[A-Za-z0-9_-]{1,128}$/.test(key))throw Error('缺少可恢复提交标识。');return request('jobs',{...options,method:'POST',value,headers:{'Idempotency-Key':key}});},
  async upload(job,source,file){return request('jobs/'+id(job)+'/sources/'+id(source),{method:'PUT',body:file,headers:{'Content-Type':file.type||'application/pdf'}});},
  start:(job,version,options={})=>request('jobs/'+id(job)+'/start',{...options,method:'POST',value:{version}}),
  resume:(job,version)=>request('jobs/'+id(job)+'/resume',{method:'POST',value:{version}}),
  materials:(job,version,documents)=>request('jobs/'+id(job)+'/materials',{method:'POST',value:{version,documents}}),
  list:()=>request('jobs'),get:(job,options={})=>request('jobs/'+id(job),options),
  answer:(job,version,answer)=>request('jobs/'+id(job)+'/answers',{method:'POST',value:{version,answer}}),
  cancel:(job,version)=>request('jobs/'+id(job)+'/cancel',{method:'POST',value:{version}}),
  async result(job,{onProgress=null,...options}={}){
   const response=await request('jobs/'+id(job)+'/result',{...options,raw:true});
   if(response.headers.get('content-type')?.startsWith('application/json'))return response.json();
   const type=response.headers.get('content-type')||'application/zip',total=Number(response.headers.get('content-length'))||0;
   // A ZIP artifact is read as a stream so the page can show how much arrived;
   // a missing Content-Length leaves total at 0 and the caller reports bytes only.
   if(typeof onProgress!=='function'||!response.body)return response.blob();
   const reader=response.body.getReader(),chunks=[];let received=0;onProgress({received,total});
   try{
    for(;;){const {done,value}=await reader.read();if(done)break;chunks.push(value);received+=value.byteLength;onProgress({received,total});}
   }finally{reader.releaseLock?.();}
   return new Blob(chunks,{type});
  },
 };
}

export async function watchGeneration(client,id,{onState=()=>{},signal,interval=1500}={}){
 while(!signal?.aborted){
  const job=await client.get(id);if(signal?.aborted)return;onState(job);
  if(!['queued','running'].includes(job.state))return job;
  await new Promise(resolve=>{let timer;const done=()=>{clearTimeout(timer);signal?.removeEventListener('abort',done);resolve();};timer=setTimeout(done,interval);signal?.addEventListener('abort',done,{once:true});});
 }
}
