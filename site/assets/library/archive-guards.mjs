import {fail,LIMITS,safePath} from './contract.mjs';
export function checkLimits(values){for(const [key,value] of Object.entries(values)){if(!Number.isSafeInteger(value)||value<0)fail('INVALID_PACKAGE','备份计数无效');if(key in LIMITS&&value>LIMITS[key])fail('LIMIT','备份超过安全大小或文件数量限制。',{limit:key});}}
const table=Uint32Array.from({length:256},(_,n)=>{for(let i=0;i<8;i++)n=n&1?(n>>>1)^0xedb88320:n>>>1;return n>>>0;});
export function updateCRC(state,bytes){for(const byte of bytes)state=table[(state^byte)&255]^(state>>>8);return state>>>0;}
export const crc32=bytes=>(updateCRC(0xffffffff,bytes)^0xffffffff)>>>0;
export async function readDirectory(blob){
 checkLimits({compressed:blob.size});if(blob.size<22)fail('INVALID_PACKAGE','ZIP 文件不完整。');
 const tail=new Uint8Array(await blob.slice(Math.max(0,blob.size-65557)).arrayBuffer()),view=new DataView(tail.buffer);let end=-1;
 for(let i=tail.length-22;i>=0;i--)if(view.getUint32(i,true)===0x06054b50&&i+22+view.getUint16(i+20,true)===tail.length){end=i;break;}
 if(end<0)fail('INVALID_PACKAGE','找不到完整 ZIP 目录。');
 const count=view.getUint16(end+10,true),size=view.getUint32(end+12,true),offset=view.getUint32(end+16,true);
 if(view.getUint16(end+4,true)||view.getUint16(end+6,true)||view.getUint16(end+8,true)!==count)fail('UNSUPPORTED_VERSION','不支持分卷 ZIP。');
 if(count===65535||offset===0xffffffff||size===0xffffffff)fail('UNSUPPORTED_VERSION','此版本不接受 ZIP64 备份。');
 checkLimits({files:count});const endPosition=blob.size-tail.length+end;
 if(offset+size!==endPosition)fail('INVALID_PACKAGE','ZIP 目录位置不一致。');
 const bytes=new Uint8Array(await blob.slice(offset,offset+size).arrayBuffer()),dv=new DataView(bytes.buffer),decoder=new TextDecoder('utf-8',{fatal:true}),names=new Set(),rows=[];let at=0,total=0;
 for(let n=0;n<count;n++){
  if(at+46>bytes.length||dv.getUint32(at,true)!==0x02014b50)fail('INVALID_PACKAGE','ZIP 目录记录损坏。');
  const flags=dv.getUint16(at+8,true),compression=dv.getUint16(at+10,true),compressedSize=dv.getUint32(at+20,true),originalSize=dv.getUint32(at+24,true),nameLength=dv.getUint16(at+28,true),extra=dv.getUint16(at+30,true),comment=dv.getUint16(at+32,true),external=dv.getUint32(at+38,true),localOffset=dv.getUint32(at+42,true);
  if(at+46+nameLength+extra+comment>bytes.length)fail('INVALID_PACKAGE','ZIP 文件名记录不完整。');
  let name;try{name=decoder.decode(bytes.subarray(at+46,at+46+nameLength));}catch{fail('INVALID_PACKAGE','ZIP 文件名编码无效。');}
  safePath(name);
  if(name.length>1024||name.split('/').some(p=>p!==p.trim()||/[. ]$/.test(p))||!/[.](?:json|pdf|svg|png|jpg|jpeg|md|txt)$/i.test(name))fail('UNSAFE_ASSET','备份含不支持的附件。');
  if(names.has(name))fail('INVALID_PACKAGE','ZIP 文件路径重复。');names.add(name);
  if((external>>>16&0xf000)===0xa000)fail('UNSAFE_ASSET','备份不允许符号链接。');
  if(flags&1||![0,8].includes(compression))fail('UNSUPPORTED_VERSION','不支持加密或此压缩方式。');
  if(localOffset>=offset||originalSize===0xffffffff||compressedSize===0xffffffff||localOffset+compressedSize>offset)fail('INVALID_PACKAGE','ZIP 文件位置无效。');
  checkLimits({file:originalSize});total+=originalSize;checkLimits({expanded:total});
  rows.push({name,size:originalSize,compressedSize,compression,flags,crc:dv.getUint32(at+16,true),localOffset});at+=46+nameLength+extra+comment;
 }
 if(at!==bytes.length)fail('INVALID_PACKAGE','ZIP 目录含未识别数据。');return rows;
}
