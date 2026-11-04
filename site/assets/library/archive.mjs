import {COLLECTIONS,fail,validatePackage,validateStoredRecords,upgradePackage,LibraryError,LIMITS,originalFile} from './contract.mjs';
import {sha256,safeAsset} from './safe-assets.mjs';
import {readDirectory,checkLimits} from './archive-guards.mjs';
import {upgradeSemanticRecords} from './semantic-schema.mjs';

const stable=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const equal=(a,b)=>stable(a)===stable(b);
function compatible(kind,current,incoming){
 if(kind==='sources'){
  const omit=v=>Object.fromEntries(Object.entries(v).filter(([k])=>!['originalStatus','blobHash','fileName'].includes(k)));
  return equal(omit(current),omit(incoming))&&(!current.blobHash||!incoming.blobHash||current.blobHash===incoming.blobHash);
 }
 if(kind==='edges'&&['confirmed','dismissed'].includes(current.status))return equal({...current,status:null},{...incoming,status:null});
 return false;
}
function remap(kind,original,maps,input){
 const v=structuredClone(original),id=(k,x)=>maps[k].get(x)||x;v.id=id(kind,v.id);
 if(kind==='terms'&&v.currentRevisionId)v.currentRevisionId=id('revisions',v.currentRevisionId);
 if(kind==='revisions'){
  v.termId=id('terms',v.termId);v.sourceIds=v.sourceIds.map(x=>id('sources',x));v.sourceMap=Object.fromEntries(Object.entries(v.sourceMap).map(([k,x])=>[k,id('sources',x)]));v.evidenceIds=v.evidenceIds.map(x=>id('evidence',x));v.assetIds=v.assetIds.map(x=>id('assets',x));
  const spaces={...original.targetSpaces||{}};for(const edge of input.edges.filter(e=>e.revisionId===original.id)){const target=edge.to;spaces[target.id]=spaces[target.id]&&spaces[target.id]!==target.space?'pending':target.space;}
  if(v.termId!==original.termId)v.lesson.term.id=v.termId;
  for(const target of [...v.lesson.glossary||[],...v.lesson.relations||[]])if(target.target){const space=target.targetSpace||spaces[target.target]||(maps.terms.has(target.target)?'personal':null);if(space){target.targetSpace=space;if(space==='personal')target.target=id('terms',target.target);}}
  if(Object.keys(spaces).length)v.targetSpaces=Object.fromEntries(Object.entries(spaces).map(([key,space])=>[space==='personal'?id('terms',key):key,space]));
 }
 if(kind==='sources')v.workId=id('works',v.workId);
 if(kind==='evidence'){v.sourceId=id('sources',v.sourceId);v.revisionId=id('revisions',v.revisionId);}
 if(kind==='edges'){for(const ref of [v.from,v.to])if(ref.space==='personal')ref.id=id('terms',ref.id);v.revisionId=id('revisions',v.revisionId);}
 const graphRef=ref=>{if(ref.space==='personal')ref.id=id('terms',ref.id);else if(ref.space==='pending')ref.id=maps.contextRefs.get(ref.id)||ref.id;};
 if(kind==='contexts'){v.id=maps.contextRefs.get(original.id)||v.id;if(v.revisionId)v.revisionId=id('revisions',v.revisionId);}
 if(kind==='edges')for(const ref of [v.from,v.to])if(ref.space==='pending')graphRef(ref);
 if(kind==='graphViews'){
  v.frameworkId=id('frameworks',v.frameworkId);
  for(const n of v.nodes)graphRef(n.ref);for(const ref of v.excludedRefs)graphRef(ref);
  for(const c of v.contextRefs){c.id=maps.contextRefs.get(c.id)||c.id;if(c.revisionId)c.revisionId=id('revisions',c.revisionId);}
  for(const g of v.groups){for(const ref of g.members)graphRef(ref);if(g.sourceRef.kind==='revision')g.sourceRef.id=id('revisions',g.sourceRef.id);}
 }
 if(kind==='frameworks'){for(const ref of v.members)graphRef(ref);for(const row of [...v.memberDetails,...v.excludedMembers])graphRef(row.ref);if(v.provenance)for(const row of v.provenance.memberReasons)graphRef(row.ref);}
 if(kind==='annotations'){if(v.termId)v.termId=id('terms',v.termId);if(v.revisionId)v.revisionId=id('revisions',v.revisionId);for(const anchor of v.anchorHistory||[])if(anchor.revisionId)anchor.revisionId=id('revisions',anchor.revisionId);}
 return v;
}
export async function planRestore(snapshot,validated){
 snapshot={...snapshot,records:upgradeSemanticRecords(snapshot.records)};
 validated=upgradePackage(validated);
 const existing=Object.fromEntries(COLLECTIONS.map(k=>[k,new Map((snapshot.records[k]||[]).map(v=>[v.id,v]))]));
 const digest=(await sha256(new TextEncoder().encode(stable(validated)))).slice(0,16);
 for(let branch=0;branch<100;branch++){
  const suffix='-import-'+digest+(branch?'-'+branch:''),maps=Object.fromEntries(COLLECTIONS.map(k=>[k,new Map(validated[k].map(v=>[v.id,v.id]))]));maps.contextRefs=new Map();
  let changed=true,passes=0;
  while(changed&&passes++<20){
   changed=false;
   for(const c of [...validated.contexts||[],...validated.graphViews.flatMap(v=>v.contextRefs)]){const revision=maps.revisions.get(c.revisionId)||c.revisionId,collision=[...existing.contexts.values(),...[...existing.graphViews.values()].flatMap(v=>v.contextRefs)].some(old=>old.id===c.id&&(old.revisionId!==revision||old.glossaryId!==c.glossaryId));maps.contextRefs.set(c.id,revision!==c.revisionId||collision?c.id.slice(0,140)+suffix:maps.contexts.get(c.id)||c.id);}
   for(const kind of COLLECTIONS)for(const record of validated[kind]){
    if(maps[kind].get(record.id)!==record.id)continue;
    const incoming=remap(kind,record,maps,validated),current=existing[kind].get(record.id);
    if(current&&!equal(current,incoming)&&!compatible(kind,current,incoming)){maps[kind].set(record.id,record.id.slice(0,140)+suffix);changed=true;}
   }
  }
  if(changed)fail('CONFLICT','关联冲突过于复杂，原库未改动。');
  const writes=[],impact=[];let collision=false;
  for(const kind of COLLECTIONS)for(const original of validated[kind]){
   const value=remap(kind,original,maps,validated),current=existing[kind].get(value.id);
   if(current&&equal(current,value))continue;
   if(current&&compatible(kind,current,value)){
    if(kind==='edges'||current.blobHash||!value.blobHash)continue;
   }else if(current){collision=true;break;}
   writes.push({kind,id:value.id,value});if(value.id!==original.id)impact.push({kind,id:original.id,foreignId:value.id});
  }
  if(collision)continue;
  const merged=Object.fromEntries(COLLECTIONS.map(kind=>[kind,[...existing[kind].values()]]));for(const write of writes){merged[write.kind]=merged[write.kind].filter(v=>v.id!==write.id);merged[write.kind].push(write.value);}validateStoredRecords(merged);
  const blobRefs=[...new Set(writes.filter(w=>['sources','assets'].includes(w.kind)).map(w=>w.value.blobHash).filter(Boolean))];
  return {writes,deletes:[],blobRefs,impact};
 }
 fail('CONFLICT','已有过多同名冲突分支，原库未改动。');
}

const abortCheck=signal=>{if(signal?.aborted)fail('CANCELLED','备份操作已取消，原库未改动。');};
const mimeFor=path=>({'pdf':'application/pdf','svg':'image/svg+xml','png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','json':'application/json','md':'text/markdown','txt':'text/plain'}[path.split('.').pop().toLowerCase()]);
export async function inspectBackup(blob,{stageBlob,discardStaged,signal,onProgress=()=>{}}={}){
 abortCheck(signal);if(typeof stageBlob!=='function')fail('INVALID_PACKAGE','备份检查需要隔离暂存接口。');
 const rows=await readDirectory(blob);abortCheck(signal);const files=new Map(),documents=new Map();
 try{
  await new Promise((resolve,reject)=>{
   const worker=new Worker(new URL('./archive.worker.mjs',import.meta.url),{type:'module'});let finished=false;
   const cleanup=()=>{signal?.removeEventListener('abort',abort);worker.terminate();};
   const stop=error=>{if(finished)return;finished=true;cleanup();reject(error instanceof LibraryError?error:new LibraryError('INVALID_PACKAGE','备份读取失败，原库未改动。'));};
   const abort=()=>stop(new LibraryError('CANCELLED','备份导入已取消，原库未改动。'));
   signal?.addEventListener('abort',abort,{once:true});worker.onerror=()=>stop(new LibraryError('INVALID_PACKAGE','备份后台检查失败。'));
   worker.onmessage=async event=>{
    const message=event.data;if(finished)return;
    if(message.type==='error'){stop(new LibraryError(message.error.code,message.error.message));return;}
    if(message.type==='done'){finished=true;cleanup();resolve();return;}
    if(message.type==='file')try{
     abortCheck(signal);const bytes=new Uint8Array(await message.blob.arrayBuffer());
     const descriptor=await safeAsset(bytes,{mime:mimeFor(message.path),path:message.path});abortCheck(signal);
     if(message.path==='manifest.json'||message.path==='library.json'){const parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));documents.set(message.path,parsed);if(message.path==='manifest.json'&&parsed.kind==='personal-library-reading')fail('READING_EXPORT','这是阅读导出。恢复完整交互需要私人完整备份；Markdown 可单独导入为个人笔记。');}
     const stagingId=await stageBlob(descriptor.hash,new Blob([message.blob],{type:descriptor.mime}),{signal});abortCheck(signal);
     files.set(message.path,{...descriptor,stagingId});onProgress({phase:'inflate',files:files.size,bytes:message.expanded});abortCheck(signal);
     worker.postMessage({type:'ack',id:message.id});
    }catch(error){stop(error);}
   };
   worker.postMessage({type:'inspect',blob,rows});
  });
  abortCheck(signal);const manifest=documents.get('manifest.json'),data=documents.get('library.json');
  if(![1,2,3,4].includes(manifest?.schemaVersion))fail('UNSUPPORTED_VERSION','不支持此备份清单版本。');
  if(manifest.kind!=='personal-library-backup'||!Array.isArray(manifest.files)||!data||manifest.packageId!==data.packageId)fail('INVALID_PACKAGE','备份清单与内容不一致。');
  const listed=new Set();for(const entry of manifest.files){if(listed.has(entry.path)||entry.path==='manifest.json')fail('INVALID_PACKAGE','备份清单路径重复。');listed.add(entry.path);const actual=files.get(entry.path);if(!actual||actual.hash!==entry.hash||actual.size!==entry.size||actual.mime!==entry.mime)fail('INVALID_PACKAGE','备份文件指纹、大小或类型不一致。');}
  if(listed.size+1!==files.size)fail('INVALID_PACKAGE','备份含清单之外的文件。');
  const validated=validatePackage(data,files,{catalogue:[]});return {manifest,validated,files};
 }catch(error){if(discardStaged)await discardStaged().catch(()=>{});throw error;}
}

export async function exportBackup(snapshot,readBlob,{signal,onProgress=()=>{},catalogue=[],officialGraph}={}){
 abortCheck(signal);const records=Object.fromEntries(COLLECTIONS.map(k=>[k,structuredClone(snapshot.records[k]||[])])),data=upgradePackage({schemaVersion:4,packageId:'',...records});
 const {projectMarkdown}=await import('./markdown.mjs');const projection=await projectMarkdown(snapshot,{includeOriginals:false,includeEvidence:false,catalogue,officialGraph});
 data.packageId='backup-'+(await sha256(new TextEncoder().encode(stable(data)))).slice(0,32);
 const files=new Map(),descriptors=[];
 for(const source of records.sources)if(source.blobHash){const file=originalFile(source);files.set(file.path,file);}
 for(const asset of records.assets)files.set(asset.path,{path:asset.path,blobHash:asset.blobHash,mime:asset.mime});
 for(const file of projection.files)files.set(file.path,{...file,mime:file.mime||'text/markdown'});
 files.set('library.json',{path:'library.json',bytes:new TextEncoder().encode(stable(data)),mime:'application/json'});
 let total=0;const prepared=[];
 for(const file of files.values()){
  abortCheck(signal);const blob=file.bytes?new Blob([file.bytes]):await readBlob(file.blobHash);if(!(blob instanceof Blob))fail('MISSING_ORIGINAL','待导出的文件缺失。');
  total+=blob.size;checkLimits({file:blob.size,expanded:total,files:files.size+1});
  const hash=file.blobHash||await sha256(new Uint8Array(await blob.arrayBuffer()));descriptors.push({path:file.path,hash,size:blob.size,mime:file.mime});prepared.push({path:file.path,blob});
 }
 const manifest={schemaVersion:4,kind:'personal-library-backup',packageId:data.packageId,files:descriptors};prepared.unshift({path:'manifest.json',blob:new Blob([stable(manifest)])});
 abortCheck(signal);
 return zipPrepared(prepared,{signal,onProgress});
}

export async function exportReading(snapshot,readBlob,{signal,onProgress=()=>{},includeOriginals=false,catalogue=[],officialGraph}={}){
 abortCheck(signal);const {projectMarkdown}=await import('./markdown.mjs');const projection=await projectMarkdown(snapshot,{includeOriginals,includeEvidence:false,catalogue,officialGraph}),prepared=[],descriptors=[];let total=0;
 for(const file of projection.files){abortCheck(signal);const blob=file.bytes?new Blob([file.bytes]):await readBlob(file.blobHash);total+=blob.size;checkLimits({expanded:total,file:blob.size,files:projection.files.length+1});prepared.push({path:file.path,blob});descriptors.push({path:file.path,mime:file.mime,size:blob.size,hash:file.blobHash||await sha256(new Uint8Array(await blob.arrayBuffer()))});}
 const manifest={...projection.manifest,files:descriptors};prepared.unshift({path:'manifest.json',blob:new Blob([stable(manifest)])});abortCheck(signal);return zipPrepared(prepared,{signal,onProgress});
}

function zipPrepared(prepared,{signal,onProgress}){
 return new Promise((resolve,reject)=>{
  const worker=new Worker(new URL('./archive.worker.mjs',import.meta.url),{type:'module'});let finished=false;
  const cleanup=()=>{signal?.removeEventListener('abort',abort);worker.terminate();};
  const stop=error=>{if(finished)return;finished=true;cleanup();reject(error);};
  const abort=()=>stop(new LibraryError('CANCELLED','备份导出已取消。'));signal?.addEventListener('abort',abort,{once:true});worker.onerror=()=>stop(new LibraryError('INVALID_PACKAGE','备份导出后台任务失败。'));
  worker.onmessage=event=>{const m=event.data;if(finished)return;if(m.type==='error')stop(new LibraryError(m.error.code,m.error.message));else if(m.type==='progress')onProgress(m);else if(m.type==='exported'){finished=true;cleanup();resolve(m.blob);}};
  worker.postMessage({type:'export',files:prepared});
 });
}
