import {fail,safePath,LIMITS} from './contract.mjs';
export async function sha256(bytes){const data=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes);const result=await crypto.subtle.digest('SHA-256',data);return [...new Uint8Array(result)].map(x=>x.toString(16).padStart(2,'0')).join('');}
const tags=new Set(['svg','g','defs','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','clipPath','style','use','linearGradient','radialGradient','stop','marker','title','desc','metadata','RDF','Work','type','format','date','creator','Agent']);
const attrs=new Set(['id','version','width','height','viewBox','xmlns','xmlns:xlink','xmlns:dc','xmlns:cc','xmlns:rdf','xmlns:svg','xmlns:ns0','d','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','points','transform','style','fill','stroke','stroke-width','stroke-linejoin','stroke-linecap','stroke-dasharray','stroke-dashoffset','fill-rule','fill-opacity','stroke-opacity','opacity','clip-path','clipPathUnits','href','xlink:href','font-family','font-size','font-weight','font-style','text-anchor','type','offset','stop-color','stop-opacity','gradientUnits','gradientTransform','markerWidth','markerHeight','refX','refY','orient','preserveAspectRatio','xml:space','about','resource','rdf:about','rdf:resource']);
function checkStyle(value){if(/@|\\|expression|javascript|behavior|-moz-binding/i.test(value)||[...value.matchAll(/url\s*\(([^)]*)\)/gi)].some(m=>!/^['"]?#[\w:.-]+['"]?$/.test(m[1].trim())))fail('UNSAFE_ASSET','图示样式引用了外部或可执行内容');}
function checkSVG(text){
 if(/<!ENTITY|<!DOCTYPE[^>]*\[|<\?(?!xml(?:\s|\?>))/i.test(text))fail('UNSAFE_ASSET','不允许 SVG 实体或外部样式指令');
 if(typeof DOMParser==='undefined')fail('UNSAFE_ASSET','SVG 必须在具备安全 XML 解析能力的浏览器中校验');
 const doc=new DOMParser().parseFromString(text,'image/svg+xml');
 if(doc.querySelector('parsererror')||doc.documentElement.localName!=='svg'||doc.documentElement.namespaceURI!=='http://www.w3.org/2000/svg')fail('UNSAFE_ASSET','SVG 文档无效');
 for(const node of doc.querySelectorAll('*')){
  if(!tags.has(node.localName))fail('UNSAFE_ASSET','SVG 包含不支持的元素',{tag:node.localName});
  for(const a of node.attributes){if(/^on/i.test(a.name)||!attrs.has(a.name))fail('UNSAFE_ASSET','SVG 包含不支持的属性',{attribute:a.name});if(['href','xlink:href'].includes(a.name)&&!/^#[\w:.-]+$/.test(a.value))fail('UNSAFE_ASSET','SVG 不允许外部链接');if(a.name==='style'||a.name==='clip-path'||a.name==='fill'||a.name==='stroke')checkStyle(a.value);}
  if(node.localName==='style')checkStyle(node.textContent);
 }
}
export async function safeAsset(input,{mime,path}){
 safePath(path);const bytes=input instanceof Uint8Array?input:new Uint8Array(input);if(bytes.byteLength>LIMITS.file)fail('LIMIT','单个文件超过 128 MiB');
 const extension=path.split('.').pop().toLowerCase(),head=new TextDecoder().decode(bytes.subarray(0,2048));
 if(mime==='application/pdf'){if(extension!=='pdf'||!head.startsWith('%PDF-'))fail('UNSAFE_ASSET','PDF 文件签名不匹配');}
 else if(mime==='image/png'){if(extension!=='png'||![137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v))fail('UNSAFE_ASSET','PNG 文件签名不匹配');}
 else if(mime==='image/jpeg'){if(!['jpg','jpeg'].includes(extension)||bytes[0]!==255||bytes[1]!==216||bytes[2]!==255)fail('UNSAFE_ASSET','JPEG 文件签名不匹配');}
 else if(mime==='image/svg+xml'){if(extension!=='svg')fail('UNSAFE_ASSET','SVG 类型不匹配');checkSVG(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
 else if(mime==='application/json'){if(extension!=='json')fail('UNSAFE_ASSET','JSON 类型不匹配');try{JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{fail('INVALID_PACKAGE','JSON 文件无法读取');}}
 else if(mime==='text/markdown'||mime==='text/plain'){if(!['md','txt'].includes(extension))fail('UNSAFE_ASSET','文字附件类型不匹配');new TextDecoder('utf-8',{fatal:true}).decode(bytes);}
 else fail('UNSAFE_ASSET','不支持此附件类型');
 return {hash:await sha256(bytes),mime,size:bytes.byteLength,path};
}
