import {LibraryError,COLLECTIONS,fail,safeId,assertPrivateData,LIMITS} from './contract.mjs';
import {sha256} from './safe-assets.mjs';
import {upgradeSemanticRecords} from './semantic-schema.mjs';

export const databaseName=environment=>'psych-term-library-v1-'+safeId(environment);
function normalized(error){if(error instanceof LibraryError)return error;if(error?.name==='QuotaExceededError')return new LibraryError('QUOTA','本机存储空间不足，尚未保存；请先导出备份。');if(error?.name==='AbortError')return new LibraryError('CANCELLED','操作已取消，已有资料保持不变。');return new LibraryError('STORAGE_UNAVAILABLE','浏览器本机存储不可用，本次操作未保存。',{name:error?.name||'Error'});}
const checkSignal=signal=>{if(signal?.aborted)fail('CANCELLED','操作已取消。');};
const request=r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(normalized(r.error));});

export async function openLibrary(context,{factory=globalThis.indexedDB}={}){
 const environment=safeId(context?.environment),libraryId=safeId(context?.libraryId),owner=context.owner??null;
 if(!factory?.open)fail('STORAGE_UNAVAILABLE','此浏览器无法使用本机持久存储。');
 let abandoned=false;
 const db=await new Promise((resolve,reject)=>{
  let opening;try{opening=factory.open(databaseName(environment),2);}catch(error){reject(normalized(error));return;}
  opening.onblocked=()=>{abandoned=true;reject(new LibraryError('BLOCKED','另一个标签页阻止了存储升级，请关闭旧标签页后重试。'));};
  opening.onerror=()=>reject(normalized(opening.error));
  opening.onupgradeneeded=()=>{
   const d=opening.result;
   if(!d.objectStoreNames.contains('meta'))d.createObjectStore('meta',{keyPath:'id'});
   if(!d.objectStoreNames.contains('records')){const s=d.createObjectStore('records',{keyPath:'key'});s.createIndex('byLibrary','libraryId');}
   if(!d.objectStoreNames.contains('blobs'))d.createObjectStore('blobs',{keyPath:'hash'});
   if(!d.objectStoreNames.contains('staging')){const s=d.createObjectStore('staging',{keyPath:'key'});s.createIndex('byLibrary','libraryId');}
  };
  opening.onsuccess=()=>{if(abandoned)opening.result.close();else resolve(opening.result);};
 });
 const metaKey='library:'+libraryId,sessionId=crypto.randomUUID(),transactions=new Set(),listeners=new Set();let closed=false;
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel(databaseName(environment)+':'+libraryId):null;
 if(channel)channel.onmessage=e=>{for(const fn of listeners)fn(e.data);};
 function tx(names,mode,signal){
  checkSignal(signal);if(closed)fail('CANCELLED','本机知识库连接已关闭。');
  let value;try{value=db.transaction(names,mode);}catch(error){throw normalized(error);}
  transactions.add(value);const cancel=()=>{try{value.abort();}catch{}};signal?.addEventListener('abort',cancel,{once:true});
  const finished=new Promise((resolve,reject)=>{value.oncomplete=resolve;value.onabort=()=>reject(normalized(value.error||new DOMException('Aborted','AbortError')));});
  finished.then(()=>{},()=>{}).finally(()=>{transactions.delete(value);signal?.removeEventListener('abort',cancel);});
  return {value,finished};
 }
 async function snapshot(){
  const t=tx(['meta','records'],'readonly');
  const [meta,rows]=await Promise.all([request(t.value.objectStore('meta').get(metaKey)),request(t.value.objectStore('records').index('byLibrary').getAll(libraryId))]);await t.finished;
  const records=Object.fromEntries(COLLECTIONS.map(k=>[k,[]]));for(const row of rows)records[row.kind].push(row.value);
  return {version:meta?.version||0,records:upgradeSemanticRecords(records)};
 }
 async function read(kinds){
  if(!Array.isArray(kinds)||kinds.some(k=>!COLLECTIONS.includes(k)))fail('INVALID_PACKAGE','读取类型无效');
  const t=tx(['meta','records'],'readonly'),store=t.value.objectStore('records');
  const pending=kinds.map(kind=>request(store.getAll(IDBKeyRange.bound([libraryId,kind],[libraryId,kind,'\uffff']))));const meta=await request(t.value.objectStore('meta').get(metaKey)),rows=await Promise.all(pending);await t.finished;
  const records=Object.fromEntries(COLLECTIONS.map(k=>[k,[]]));for(let i=0;i<kinds.length;i++)records[kinds[i]]=rows[i].map(r=>r.value);return {version:meta?.version||0,records};
 }
 async function getRecord(kind,id){if(!COLLECTIONS.includes(kind))fail('INVALID_PACKAGE','记录类型无效');safeId(id);const t=tx(['records'],'readonly'),row=await request(t.value.objectStore('records').get([libraryId,kind,id]));await t.finished;return row?.value||null;}
 async function stageBlob(hash,blob,{signal}={}){
  checkSignal(signal);if(!(blob instanceof Blob)||blob.size>LIMITS.file)fail('LIMIT','待保存文件超过大小限制。');
  if(!/^[a-f0-9]{64}$/.test(hash)||await sha256(new Uint8Array(await blob.arrayBuffer()))!==hash)fail('INVALID_PACKAGE','待保存文件指纹不匹配。');
  checkSignal(signal);const t=tx(['blobs','staging'],'readwrite',signal);
  try{const blobs=t.value.objectStore('blobs');if(!await request(blobs.get(hash)))blobs.put({hash,blob});t.value.objectStore('staging').put({key:[libraryId,sessionId,hash],libraryId,sessionId,hash,createdAt:Date.now()});await t.finished;return hash;}
  catch(error){try{t.value.abort();}catch{}await t.finished.catch(()=>{});throw normalized(error);}
 }
 async function commit(plan,{expectedVersion,signal}={}){
  checkSignal(signal);if(!Number.isInteger(expectedVersion)||expectedVersion<0)fail('CONFLICT','保存需要当前资料版本。');
  if(!Array.isArray(plan?.writes)||!Array.isArray(plan?.deletes)||!Array.isArray(plan?.blobRefs))fail('INVALID_PACKAGE','变更计划无效。');
  for(const item of [...plan.writes,...plan.deletes]){if(!COLLECTIONS.includes(item.kind))fail('INVALID_PACKAGE','记录类型无效');safeId(item.id);if('value' in item){if(item.value?.id!==item.id)fail('INVALID_PACKAGE','记录身份不一致');assertPrivateData(item.value);}}
  const t=tx(['meta','records','blobs','staging'],'readwrite',signal);
  try{
   const metaStore=t.value.objectStore('meta'),records=t.value.objectStore('records'),blobs=t.value.objectStore('blobs');
   const prior=await request(metaStore.get(metaKey));const meta=prior||{id:metaKey,version:0,owner,refs:{}};
   if(meta.version!==expectedVersion||meta.owner!==owner)fail('CONFLICT','资料已在其他页面更新，请刷新后保留或重新提交修改。');
   if(!plan.writes.length&&!plan.deletes.length){await t.finished;return meta.version;}
   const refs={...meta.refs};
   const adjust=(record,delta)=>{if(record?.blobHash){refs[record.blobHash]=(refs[record.blobHash]||0)+delta;if(refs[record.blobHash]<=0)delete refs[record.blobHash];}};
   for(const item of [...plan.deletes,...plan.writes]){
    const key=[libraryId,item.kind,item.id],old=await request(records.get(key));
    if(['sources','assets'].includes(item.kind))adjust(old?.value,-1);
    if('value' in item){
     if(['sources','assets'].includes(item.kind)){const hash=item.value.blobHash;if(hash&&!await request(blobs.get(hash)))fail('INVALID_PACKAGE','变更引用了尚未保存的文件。');adjust(item.value,1);}
     records.put({key,libraryId,kind:item.kind,id:item.id,value:item.value});
    }else records.delete(key);
   }
   for(const hash of plan.blobRefs){if(!await request(blobs.get(hash)))fail('INVALID_PACKAGE','归档文件缺失。');t.value.objectStore('staging').delete([libraryId,sessionId,hash]);}
   metaStore.put({...meta,version:meta.version+1,refs,updatedAt:Date.now()});await t.finished;
   const message={version:meta.version+1};channel?.postMessage(message);for(const fn of listeners)fn({...message,changes:plan});return message.version;
  }catch(error){try{t.value.abort();}catch{}await t.finished.catch(()=>{});throw normalized(error);}
 }
 async function getBlob(hash){
  const t=tx(['meta','blobs'],'readonly');const [meta,record]=await Promise.all([request(t.value.objectStore('meta').get(metaKey)),request(t.value.objectStore('blobs').get(hash))]);await t.finished;
  if(!meta?.refs?.[hash]||!record)fail('MISSING_ORIGINAL','这份文件尚未归档，或已经删除。');return record.blob;
 }
 async function discardStaged({staleOnly=false}={}){
  const t=tx(['meta','blobs','staging'],'readwrite');
  try{
   const stage=t.value.objectStore('staging'),blobs=t.value.objectStore('blobs');const rows=await request(stage.getAll());
   const discard=rows.filter(r=>r.libraryId===libraryId&&(staleOnly?r.createdAt<Date.now()-86400000:r.sessionId===sessionId));
   for(const row of discard)stage.delete(row.key);
   const keep=rows.filter(r=>!discard.includes(r)),metas=await request(t.value.objectStore('meta').getAll());
   const allHashes=await request(blobs.getAllKeys());for(const hash of allHashes)if(!keep.some(r=>r.hash===hash)&&!metas.some(m=>m.refs?.[hash]))blobs.delete(hash);
   await t.finished;return discard.length;
  }catch(error){try{t.value.abort();}catch{}await t.finished.catch(()=>{});throw normalized(error);}
 }
 async function getPreference(name){safeId(name);const t=tx(['meta'],'readonly'),row=await request(t.value.objectStore('meta').get('preference:'+libraryId+':'+name));await t.finished;return row?structuredClone(row.value):null;}
 async function setPreference(name,value){safeId(name);assertPrivateData(value);if(new TextEncoder().encode(JSON.stringify(value)).length>2*1024*1024)fail('LIMIT','本机设置记录过大。');const t=tx(['meta'],'readwrite');t.value.objectStore('meta').put({id:'preference:'+libraryId+':'+name,value:structuredClone(value)});await t.finished;}
 function close(){if(closed)return;closed=true;for(const transaction of transactions){try{transaction.abort();}catch{}}channel?.close();listeners.clear();db.close();}
 db.onversionchange=close;
 const store={snapshot,read,getRecord,getPreference,setPreference,stageBlob,commit,getBlob,discardStaged,close,subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);}};
 try{await discardStaged({staleOnly:true});}catch(error){close();throw error;}
 return store;
}
