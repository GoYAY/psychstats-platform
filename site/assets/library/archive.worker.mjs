import {Unzip,UnzipInflate,Zip,ZipDeflate,ZipPassThrough} from '../vendor/fflate/fflate.mjs';
import {checkLimits,updateCRC} from './archive-guards.mjs';
import {fail} from './contract.mjs';
const acknowledgements=new Map();let sequence=0;
async function inspect(blob,rows){
 const expected=new Map(rows.map(r=>[r.name,r])),seen=new Set();let expanded=0;const pending=[];
 const unzip=new Unzip(file=>{
  const row=expected.get(file.name);if(!row||seen.has(file.name)||file.compression!==row.compression)fail('INVALID_PACKAGE','ZIP 本地记录与目录不一致。');seen.add(file.name);
  if(file.originalSize!==undefined&&file.originalSize!==row.size)fail('INVALID_PACKAGE','ZIP 声明大小不一致。');
  let chunks=[],size=0,crc=0xffffffff;
  file.ondata=(error,bytes,final)=>{
   if(error)throw error;
   size+=bytes.length;expanded+=bytes.length;checkLimits({file:size,expanded});crc=updateCRC(crc,bytes);chunks.push(bytes);
   if(final){
    if(size!==row.size||((crc^0xffffffff)>>>0)!==row.crc)fail('INVALID_PACKAGE','ZIP 文件大小或 CRC 校验失败。');
    const id=++sequence,blob=new Blob(chunks);chunks=[];
    pending.push(new Promise((resolve,reject)=>acknowledgements.set(id,{resolve,reject})));
    self.postMessage({type:'file',id,path:file.name,blob,expanded,files:seen.size});
   }
  };file.start();
 });
 unzip.register(UnzipInflate);
 for(let offset=0;offset<blob.size;offset+=65536){
  const bytes=new Uint8Array(await blob.slice(offset,offset+65536).arrayBuffer());
  for(let at=0;at<bytes.length;at+=2048){unzip.push(bytes.subarray(at,Math.min(bytes.length,at+2048)));if(pending.length)await Promise.all(pending.splice(0));}
 }
 unzip.push(new Uint8Array(),true);if(pending.length)await Promise.all(pending.splice(0));
 if(seen.size!==rows.length)fail('INVALID_PACKAGE','ZIP 缺少目录中声明的文件。');
 self.postMessage({type:'done',files:seen.size,expanded});
}
async function exportFiles(files){
 checkLimits({files:files.length});let total=0,compressed=0,parts=[];
 const zip=new Zip((error,bytes,final)=>{if(error)throw error;compressed+=bytes.length;checkLimits({compressed});parts.push(bytes);if(final){self.postMessage({type:'exported',blob:new Blob(parts,{type:'application/zip'})});parts=[];}});
 for(let i=0;i<files.length;i++){
  const file=files[i],blob=file.blob;checkLimits({file:blob.size});total+=blob.size;checkLimits({expanded:total});
  const item=/\.(?:pdf|png|jpe?g)$/i.test(file.path)?new ZipPassThrough(file.path):new ZipDeflate(file.path,{level:6});zip.add(item);
  if(!blob.size)item.push(new Uint8Array(),true);
  for(let offset=0;offset<blob.size;offset+=65536)item.push(new Uint8Array(await blob.slice(offset,offset+65536).arrayBuffer()),offset+65536>=blob.size);
  self.postMessage({type:'progress',phase:'export',files:i+1,bytes:total});
 }
 zip.end();
}
self.onmessage=event=>{
 const message=event.data;
 if(message.type==='ack'){const pending=acknowledgements.get(message.id);acknowledgements.delete(message.id);if(pending){if(message.error)pending.reject(new Error(message.error));else pending.resolve();}return;}
 const task=message.type==='inspect'?inspect(message.blob,message.rows):exportFiles(message.files);
 task.catch(error=>self.postMessage({type:'error',error:{code:error.code||'INVALID_PACKAGE',message:error.code?error.message:'备份解码失败。'}}));
};
