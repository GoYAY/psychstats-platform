// Adapts the authenticated durable API to the existing suggestion reconciler.
export function createOnlineFrameworkTransport(client){
 return {
  async submit(input,key,{signal}={}){
   const check=()=>signal?.throwIfAborted();check();
   await client.session({signal});check();let job=await client.create({kind:'organize',input,documents:[],model_allowed:true,network_allowed:false},'organize-'+key,{signal});check();
   if(job.state==='draft')job=await client.start(job.id,job.version,{signal});check();
   return {taskId:job.id,status:job.state};
  },
  async get(id,{signal}={}){
   signal?.throwIfAborted();
   const job=await client.get(id,{signal});signal?.throwIfAborted();
   if(job.state==='complete')return {taskId:id,status:'complete',result:await client.result(id,{signal})};
   if(['failed','cancelled','expired','needs_reconciliation','waiting_input'].includes(job.state))return {taskId:id,status:'failed',calls:job.usage?.calls||0,error:{code:job.progress?.error_code||job.state,message:job.state==='needs_reconciliation'?'请求状态需管理员核对，未自动重复调用。':'本次整理未完成，已有科普与人工关系保持不变。'}};
   return {taskId:id,status:job.state==='running'?'running':'queued'};
  },
 };
}
