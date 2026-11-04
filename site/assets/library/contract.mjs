import {validateGraphViews} from './graph-view-schema.mjs';
import {validatePresentation} from '../charts/presentation.mjs';
import {legacyFrameworks,validateFrameworks} from './framework-schema.mjs';
import {upgradeSemanticRecords,validateSemanticEdge} from './semantic-schema.mjs';
// Static startup bundles and lazy source modules share this non-JSON brand.
// Preserve instanceof across those trusted module instances, not plain objects.
const libraryErrorBrand=Symbol.for('psychstats.library.error.v1');
export class LibraryError extends Error{
 constructor(code,message,details={}){super(message);this.name='LibraryError';this.code=code;this.details=details;Object.defineProperty(this,libraryErrorBrand,{value:true});}
 static [Symbol.hasInstance](value){return value instanceof Error&&value[libraryErrorBrand]===true;}
}
export const COLLECTIONS=['terms','revisions','works','sources','evidence','edges','annotations','assets','graphViews','frameworks','contexts'];
export function upgradePackage(value){if(!value||![1,2,3,4].includes(value.schemaVersion))fail('UNSUPPORTED_VERSION','不支持此知识库格式版本');const copy=structuredClone(value);if(copy.schemaVersion===1){if(copy.graphViews?.length)fail('INVALID_PACKAGE','旧版本不能包含活动画布。');copy.graphViews=[];}if(copy.schemaVersion<3){if(copy.frameworks?.length)fail('INVALID_PACKAGE','旧版本不能包含活动框架。');copy.frameworks=legacyFrameworks(copy.graphViews||[]);}if(copy.contexts===undefined)copy.contexts=[...new Map((copy.graphViews||[]).flatMap(v=>v.contextRefs||[]).map(c=>[c.id,structuredClone(c)])).values()];copy.schemaVersion=4;return upgradeSemanticRecords(copy);}
export const RELATIONS=['prerequisites','components','contrasts','used_in','next'];
export function originalFile(source,{prefix='originals'}={}){const text=/\.txt$/i.test(source.fileName||'');return {path:prefix+'/'+source.blobHash+(text?'.txt':'.pdf'),blobHash:source.blobHash,mime:text?'text/plain':'application/pdf'};}
export const LIMITS=Object.freeze({compressed:256*1024*1024,expanded:1024*1024*1024,file:128*1024*1024,files:10000});
const idPattern=/^[A-Za-z0-9][A-Za-z0-9_:.\-]{0,191}$/;
export function fail(code,message,details){throw new LibraryError(code,message,details);}
export function safeId(value){if(typeof value!=='string'||!idPattern.test(value))fail('INVALID_PACKAGE','资料编号无效');return value;}
export function text(value,{empty=false,max=12000}={}){if(typeof value!=='string'||value.length>max||(!empty&&!value.trim()))fail('INVALID_PACKAGE','文字字段无效');return value;}
export function safePath(value){if(typeof value!=='string'||!value||value.includes('\\')||value.startsWith('/')||value.includes(':')||value.split('/').some(s=>!s||s==='.'||s==='..')||/[\x00-\x1f]/.test(value))fail('UNSAFE_ASSET','文件路径无效');return value;}
export function safeURL(value){if(!value)return '';let url;try{url=new URL(value);}catch{fail('INVALID_PACKAGE','来源地址格式无效');}if(url.protocol!=='https:'||url.username||url.password)fail('INVALID_PACKAGE','来源地址必须是无凭证的 HTTPS 地址');return url.href;}
export function assertPrivateData(value){
 const denied=new Set(['proto','constructor','prototype','apikey','authorization','accesstoken','refreshtoken','password','orders','balance','clientsecret','apisecret','bearertoken']);
 function visit(v,depth){if(depth>80)fail('INVALID_PACKAGE','资料嵌套过深');if(typeof v==='number'&&!Number.isFinite(v))fail('INVALID_PACKAGE','资料包含非有限数值');if(v&&typeof v==='object')for(const [k,item] of Object.entries(v)){if(denied.has(k.toLowerCase().replace(/[^a-z0-9]/g,'')))fail('INVALID_PACKAGE','资料包含不允许归档的凭证或账户字段');if((k==='url'||k==='href')&&typeof item==='string'&&item)safeURL(item);visit(item,depth+1);}}
 visit(value,0);
}
function index(items,name){if(!Array.isArray(items)||items.length>50000)fail('INVALID_PACKAGE','记录列表无效',{name});const map=new Map();for(const item of items){if(!item||typeof item!=='object'||Array.isArray(item))fail('INVALID_PACKAGE','记录无效',{name});safeId(item.id);if(map.has(item.id))fail('INVALID_PACKAGE','重复记录编号',{name,id:item.id});map.set(item.id,item);}return map;}
function reference(ref,revision,evidence){
 const sid=revision.sourceMap?.[ref.source_id];const record=evidence.find(item=>item.sourceId===sid&&item.revisionId===revision.id&&revision.evidenceIds.includes(item.id)),source=record?.data;
 if(record?.status==='deleted'){if(!Number.isInteger(record.originalLength)||!Number.isInteger(ref.start)||!Number.isInteger(ref.end)||ref.start<0||ref.end<=ref.start||ref.end>record.originalLength||ref.excerpt!==undefined)fail('INVALID_PACKAGE','已删除证据只能保留原定位，不能保留引用片段。');return;}
 if(!source||!Number.isInteger(ref.start)||!Number.isInteger(ref.end)||ref.start<0||ref.end<=ref.start||ref.end>source.text.length)fail('INVALID_PACKAGE','引用超出实际保存的资料');
 if(ref.excerpt!==undefined&&ref.excerpt!==source.text.slice(ref.start,ref.end))fail('INVALID_PACKAGE','引用片段与原文不一致');
}
function fields(value,allowed,required=[]){if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k))||required.some(k=>!(k in value)))fail('INVALID_PACKAGE','记录包含未知字段或缺少必要字段。');}
function documentReadings(provenance,revision,evidence){
 const seen=new Set();
 for(const reading of list(provenance?.document_readings||[],10)){
  fields(reading,['source_id','original_sha256','handled_sections','total_sections','source_mapping'],['source_id','original_sha256','handled_sections','total_sections','source_mapping']);
  safeId(reading.source_id);
  if(seen.has(reading.source_id)||!revision.sourceMap[reading.source_id]||!/^[a-f0-9]{64}$/.test(reading.original_sha256)||!Number.isInteger(reading.handled_sections)||!Number.isInteger(reading.total_sections)||reading.handled_sections<0||reading.total_sections<reading.handled_sections)fail('INVALID_PACKAGE','逐篇阅读记录无效。');
  seen.add(reading.source_id);
  const saved=evidence.find(e=>e.sourceId===revision.sourceMap[reading.source_id]&&e.revisionId===revision.id),length=saved?.status==='deleted'?saved.originalLength:saved?.data?.text?.length;
  for(const span of list(reading.source_mapping,200)){
   fields(span,['selected_start','selected_end','original_start','original_end','section_id','source_id'],['selected_start','selected_end','original_start','original_end','section_id','source_id']);
   safeId(span.section_id);
   if(span.source_id!==reading.source_id||!Number.isInteger(length)||!['selected_start','selected_end','original_start','original_end'].every(k=>Number.isInteger(span[k])&&span[k]>=0)||span.original_end<=span.original_start||span.selected_end<=span.selected_start||span.original_end>length||span.selected_end-span.selected_start!==span.original_end-span.original_start)fail('INVALID_PACKAGE','原文与选段的定位映射无效。');
  }
 }
}
function list(value,max=100){if(!Array.isArray(value)||value.length>max)fail('INVALID_PACKAGE','记录列表无效或过长。');return value;}
const strings=(value,max=100)=>list(value,max).forEach(v=>text(v,{max:300}));
const anchorFields=['id','zh','en','aliases','definition','author','year','doi'];
const provenanceFields=['model','template_version','skill','human_scientific_review','human_review','automatic_generation_passed','evidence_status','host_editorial_review','inline_glossary_review','local_editorial_review','model_structure_validation_passed','multi_literature_review','normalizations','original_source_hash','pdf_to_lesson_autonomous','revalidated_exact_saved_response','source_hashes','source_mapping','document_readings','source_preparation','source_request_hash','teaching_body_contributing_works','teaching_body_independent_works','used_independent_works','visual_logic_review','whole_document_handled','removedEvidence','identityRemaps','verified_identity','original_anchor','revision_basis'];
function identityMetadata(provenance,revision,evidence){
 if(provenance?.original_anchor)fields(provenance.original_anchor,anchorFields);
 if(provenance?.revision_basis)text(provenance.revision_basis,{max:300});
 const identity=provenance?.verified_identity;if(!identity)return;
 fields(identity,['en','refs','basis'],['en','refs','basis']);text(identity.en,{max:160});
 if(identity.basis!=='source_located_model_mapping'||!/[a-z]/i.test(identity.en)||!Array.isArray(identity.refs)||identity.refs.length<1||identity.refs.length>3)fail('INVALID_PACKAGE','英文名称的来源定位无效。');
 for(const ref of identity.refs)reference(ref,revision,evidence);
}
function validateNested(value,maps){
 const allowed={terms:['id','zh','en','aliases','anchor','tags','currentRevisionId','trashed'],revisions:['id','termId','lesson','sourceIds','sourceMap','evidenceIds','assetIds','provenance','targetSpaces'],works:['id','title','doi','authors','year','url'],sources:['id','localId','workId','scope','origin','blobHash','originalStatus','fileName','extractedStatus'],evidence:['id','sourceId','revisionId','data','status','originalLength'],edges:['id','from','to','type','reason','refs','status','origin','revisionId','catalogueVersion','basis','taskRecord'],annotations:['id','termId','revisionId','blockId','text','origin','anchorStatus','anchorHistory','fileName','reviewStatus'],assets:['id','role','path','blobHash','mime','size','alt']};
 for(const kind of COLLECTIONS.filter(k=>!['graphViews','frameworks','contexts'].includes(k)))for(const row of value[kind])fields(row,allowed[kind],['id']);
 for(const t of value.terms){strings(t.aliases);strings(t.tags);fields(t.anchor,anchorFields);if(typeof t.trashed!=='boolean')fail('INVALID_PACKAGE','回收状态无效。');}
 for(const w of value.works){text(w.title);text(w.doi||'',{empty:true});strings(w.authors);if(w.year!==null&&w.year!==undefined&&!Number.isInteger(w.year))fail('INVALID_PACKAGE','文献年份无效。');}
 for(const source of value.sources)if(source.originalStatus!=='saved'&&source.blobHash!==null&&source.blobHash!==undefined)fail('INVALID_PACKAGE','未归档来源不能带活动原件。');
 for(const n of value.annotations){text(n.text,{max:2*1024*1024});if(n.termId&&!maps.terms.has(n.termId)||n.revisionId&&!maps.revisions.has(n.revisionId))fail('INVALID_PACKAGE','批注关联记录缺失。');for(const a of list(n.anchorHistory||[])){fields(a,['revisionId','blockId']);if(a.revisionId&&!maps.revisions.has(a.revisionId))fail('INVALID_PACKAGE','批注历史修订缺失。');}}
 for(const a of value.assets){text(a.mime);text(a.alt||'',{empty:true});if(!Number.isInteger(a.size)||a.size<0||a.size>LIMITS.file)fail('INVALID_PACKAGE','图示大小无效。');}
 for(const r of value.revisions){
  for(const key of ['sourceIds','evidenceIds','assetIds'])for(const id of list(r[key],10000))safeId(id);
  fields(r.provenance||{},provenanceFields);if(!r.sourceMap||typeof r.sourceMap!=='object'||Array.isArray(r.sourceMap)||Object.entries(r.sourceMap).some(([k,v])=>!k||!r.sourceIds.includes(v)))fail('INVALID_PACKAGE','来源映射无效。');
  identityMetadata(r.provenance,r,value.evidence);
  documentReadings(r.provenance,r,value.evidence);
  for(const id of r.evidenceIds){const e=maps.evidence.get(id);if(!e||e.revisionId!==r.id||!r.sourceIds.includes(e.sourceId))fail('INVALID_PACKAGE','证据未绑定到当前修订。');}
  if(r.targetSpaces&&Object.values(r.targetSpaces).some(v=>!['personal','official','pending'].includes(v)))fail('INVALID_PACKAGE','术语目标命名空间无效。');
  const l=r.lesson;fields(l,['schema_version','content_id','status','term','blocks','formulas','visual','quiz','relations','missing_evidence','provenance','source_relations','limitations','glossary'],['term','blocks','formulas','quiz']);fields(l.term,anchorFields);safeId(l.term.id);text(l.term.zh,{empty:true});text(l.term.en||'',{empty:true});strings(l.term.aliases||[]);fields(l.provenance||{},provenanceFields);documentReadings(l.provenance,r,value.evidence);
  const refs=v=>{for(const ref of list(v||[])){fields(ref,['source_id','start','end','span_id','excerpt'],['source_id','start','end']);reference(ref,r,value.evidence);}};
  const ids=new Set();for(const b of list(l.blocks,30)){fields(b,['id','heading','paragraphs'],['id','heading','paragraphs']);safeId(b.id);if(ids.has(b.id))fail('INVALID_PACKAGE','小节编号重复。');ids.add(b.id);for(const p of list(b.paragraphs,50)){fields(p,['text','emphasis','kind','refs'],['text','emphasis','kind','refs']);strings(p.emphasis,30);refs(p.refs);}}
  for(const f of list(l.formulas,40)){fields(f,['latex','symbols','refs'],['latex','symbols']);text(f.latex);for(const s of list(f.symbols,60)){fields(s,['symbol','meaning'],['symbol','meaning']);text(s.symbol);text(s.meaning);}refs(f.refs);}
  for(const g of list(l.glossary||[],100)){fields(g,['id','term','aliases','explanation','refs','target','targetSpace'],['id','term','explanation']);safeId(g.id);text(g.term);text(g.explanation);strings(g.aliases||[],30);if(g.target!==null&&g.target!==undefined)safeId(g.target);if(g.targetSpace&&!['personal','official','pending'].includes(g.targetSpace))fail('INVALID_PACKAGE','词汇目标空间无效。');refs(g.refs);}
  for(const edge of list(l.relations||[])){fields(edge,['target','targetSpace','type','reason','refs'],['target','type','reason']);safeId(edge.target);if(!RELATIONS.includes(edge.type))fail('INVALID_PACKAGE','教学关系类型无效。');text(edge.reason);refs(edge.refs);}
  for(const n of list(l.limitations||[])){fields(n,['text','refs'],['text']);text(n.text);refs(n.refs);}
  identityMetadata(l.provenance,r,value.evidence);
  if(l.visual){fields(l.visual,['kind','title','alt','takeaway','learning_goal','adds_beyond_prose','origin','payload','refs','presentation','data_semantics'],['kind','title','alt','takeaway']);for(const k of ['kind','title','alt','takeaway'])text(l.visual[k]);refs(l.visual.refs);try{validatePresentation(l.visual);}catch(error){fail('INVALID_PACKAGE',error.message);}
   if(l.visual.data_semantics){const s=l.visual.data_semantics;fields(s,['type','denominator','rounding_digits'],['type','denominator','rounding_digits']);if(!['partition','independent'].includes(s.type)||s.denominator!==null&&(!Number.isFinite(s.denominator)||s.denominator<=0)||!Number.isInteger(s.rounding_digits)||s.rounding_digits<0||s.rounding_digits>6)fail('INVALID_PACKAGE','百分比数据语义无效。');}
  }
  if(l.quiz){fields(l.quiz,['question','options','correct_option'],['question','options','correct_option']);text(l.quiz.question);const options=list(l.quiz.options,4);if(options.length!==4||new Set(options.map(o=>o.id)).size!==4||!options.some(o=>o.id===l.quiz.correct_option))fail('INVALID_PACKAGE','选择题需要4个独立选项和有效答案。');for(const o of options){fields(o,['id','text','explanation'],['id','text','explanation']);safeId(o.id);text(o.text);text(o.explanation);}}else if(l.status==='complete')fail('INVALID_PACKAGE','完整科普缺少选择题。');
 }
 for(const edge of value.edges)for(const endpoint of [edge.from,edge.to])fields(endpoint,['space','id'],['space','id']);
}
// These descriptors describe already verified stored blobs. This helper does
// not replace safeAsset/byte validation at the external import boundary.
export function validateStoredRecords(records){const files=new Map();for(const a of records.assets)files.set(a.path,{hash:a.blobHash,mime:a.mime,size:a.size});for(const s of records.sources)if(s.blobHash)files.set(originalFile(s).path,{hash:s.blobHash,mime:originalFile(s).mime});return validatePackage({schemaVersion:4,packageId:'stored-state',...Object.fromEntries(COLLECTIONS.map(k=>[k,records[k]||[]]))},files);}
export function validatePackage(value,files=new Map(),{catalogue=[]}={}){
 value=upgradePackage(value);
 const allowed=new Set(['schemaVersion','packageId',...COLLECTIONS]);if(Object.keys(value).some(k=>!allowed.has(k)))fail('INVALID_PACKAGE','知识库包含未知顶层字段');
 assertPrivateData(value);safeId(value.packageId);
 const maps=Object.fromEntries(COLLECTIONS.map(key=>[key,index(value[key],key)]));
 validateNested(value,maps);
 for(const source of value.sources){
  if(!maps.works.has(source.workId)||!['metadata','abstract','excerpt','full_text'].includes(source.scope)||!['saved','missing','deleted'].includes(source.originalStatus))fail('INVALID_PACKAGE','文献身份或范围无效');
  if(source.originalStatus==='saved'&&(!/^[a-f0-9]{64}$/.test(source.blobHash)||![...files.values()].some(f=>f.hash===source.blobHash)))fail('INVALID_PACKAGE','归档原件缺失');
 }
 for(const item of value.evidence){if(!maps.sources.has(item.sourceId)||!maps.revisions.has(item.revisionId)||typeof item.data?.text!=='string')fail('INVALID_PACKAGE','证据记录的来源缺失');}
 for(const term of value.terms){text(term.zh,{empty:true});text(term.en||'',{empty:true});if(!term.zh&&!term.anchor?.definition)fail('INVALID_PACKAGE','术语缺少名称或定义');if(!Array.isArray(term.aliases)||!Array.isArray(term.tags))fail('INVALID_PACKAGE','别名或标签无效');if(term.currentRevisionId!==null&&(!maps.revisions.has(term.currentRevisionId)||maps.revisions.get(term.currentRevisionId).termId!==term.id))fail('INVALID_PACKAGE','术语当前修订无效');}
 for(const revision of value.revisions){
  if(!maps.terms.has(revision.termId)||!Array.isArray(revision.sourceIds)||revision.sourceIds.some(id=>!maps.sources.has(id))||!Array.isArray(revision.assetIds)||revision.assetIds.some(id=>!maps.assets.has(id))||!Array.isArray(revision.evidenceIds)||revision.evidenceIds.some(id=>!maps.evidence.has(id)))fail('INVALID_PACKAGE','科普关联资源缺失');
  const lesson=revision.lesson;if(lesson?.schema_version!==1||!['complete','needs_sources','needs_disambiguation'].includes(lesson.status)||!Array.isArray(lesson.blocks))fail('INVALID_PACKAGE','科普内容结构无效');
  for(const block of lesson.blocks){text(block.heading);if(!Array.isArray(block.paragraphs))fail('INVALID_PACKAGE','正文段落无效');for(const p of block.paragraphs){text(p.text);if(!Array.isArray(p.emphasis)||p.emphasis.some(e=>typeof e!=='string'||!p.text.includes(e)))fail('INVALID_PACKAGE','正文重点与文字不一致');if(!['factual','analogy','illustration'].includes(p.kind)||!Array.isArray(p.refs))fail('INVALID_PACKAGE','段落证据类型无效');for(const ref of p.refs)reference(ref,revision,value.evidence);}}
  const refs=[];for(const f of lesson.formulas||[]){text(f.latex);if(/\\(?:href|url|html\w*|includegraphics|input|write|def|gdef|newcommand|renewcommand)\b/.test(f.latex))fail('INVALID_PACKAGE','公式包含不可执行的外部或脚本命令。');refs.push(...f.refs||[]);}for(const g of lesson.glossary||[])refs.push(...g.refs||[]);for(const r of lesson.relations||[])refs.push(...r.refs||[]);for(const ref of refs)reference(ref,revision,value.evidence);
 }
 for(const asset of value.assets){safePath(asset.path);if(!/^[a-f0-9]{64}$/.test(asset.blobHash)||files.get(asset.path)?.hash!==asset.blobHash)fail('INVALID_PACKAGE','图示文件或指纹缺失');}
 const contexts=validateGraphViews(value,maps);
 validateFrameworks(value,maps,contexts);
 for(const edge of value.edges){
  validateSemanticEdge(edge,maps,contexts);const manual=edge.origin==='user'&&edge.revisionId===null,inferred=edge.basis==='inference';
  if(!RELATIONS.includes(edge.type)||!['suggested','confirmed','dismissed'].includes(edge.status)||!['model','user'].includes(edge.origin)||!manual&&!inferred&&!maps.revisions.has(edge.revisionId)||!Array.isArray(edge.refs)||manual&&edge.refs.length||edge.origin==='model'&&!inferred&&!edge.refs.length)fail('INVALID_PACKAGE','术语关系无效或缺少文献依据');
  for(const ref of [edge.from,edge.to]){if(!ref||!['personal','official','pending'].includes(ref.space))fail('INVALID_PACKAGE','关系目标无效');safeId(ref.id);if(manual&&(ref.space==='personal'&&!maps.terms.has(ref.id)||ref.space==='pending'&&!contexts.has(ref.id)))fail('INVALID_PACKAGE','人工关系缺少已选节点。');}
  if(!manual&&!inferred&&(edge.from.space!=='personal'||!maps.terms.has(edge.from.id)))fail('INVALID_PACKAGE','关系起点缺失');text(edge.reason);for(const ref of edge.refs)reference(ref,maps.revisions.get(edge.revisionId),value.evidence);
 }
 return structuredClone(value);
}
const normalize=v=>String(v||'').normalize('NFKC').trim().toLowerCase().replace(/\s+/g,'');
export function resolveTermRef(input,registry){const query=normalize(input),candidates=[];for(const term of registry){if([term.zh,term.en,...term.aliases||[]].some(v=>v&&normalize(v)===query)){const ref={space:term.space||({classic:'official',personal:'personal',pending:'pending'}[term.kind])||'personal',id:term.id};if(!candidates.some(c=>c.space===ref.space&&c.id===ref.id))candidates.push(ref);}}return {ref:candidates.length===1?candidates[0]:null,candidates};}
