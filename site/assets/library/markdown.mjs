import {fail,safeURL,safeId,originalFile} from './contract.mjs';
import {sha256} from './safe-assets.mjs';
import {buildGraph} from './graph-model.mjs';

const encode=new TextEncoder();
const md=value=>String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/[\\`*_[\]!|#]/g,'\\$&');
const linkPath=path=>path.split('/').map(p=>p==='..'?'..':encodeURIComponent(p)).join('/');
function highlighted(paragraph){
 const text=paragraph.text,ranges=[];
 for(const word of [...paragraph.emphasis||[]].sort((a,b)=>b.length-a.length)){
  let from=0;while(word&&from<text.length){const start=text.indexOf(word,from);if(start<0)break;const end=start+word.length;if(!ranges.some(r=>r.start<end&&r.end>start))ranges.push({start,end});from=end;}
 }
 let at=0,out='';for(const r of ranges.sort((a,b)=>a.start-b.start)){out+=md(text.slice(at,r.start))+'**'+md(text.slice(r.start,r.end))+'**';at=r.end;}return out+md(text.slice(at));
}
function safeName(label){let name=Array.from(String(label).normalize('NFC').replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').replace(/[. ]+$/g,'')).slice(0,60).join('')||'未命名';if(/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i.test(name))name='笔记-'+name;return name;}
function usedSources(lesson){const found=new Set();function visit(v){if(!v||typeof v!=='object')return;if(Array.isArray(v)){for(const x of v)visit(x);return;}for(const ref of v.refs||[])if(ref.source_id)found.add(ref.source_id);for(const [key,item] of Object.entries(v))if(!['refs','provenance','source_relations'].includes(key))visit(item);}visit(lesson);return found;}
const relationLabel={prerequisites:'前置知识',components:'组成部分',contrasts:'对照理解',used_in:'应用关系',next:'后续学习'};

export async function projectMarkdown(snapshot,{includeOriginals=false,includeEvidence=false,catalogue=[],officialGraph={terms:[],edges:[],frameworks:[]}}={}){
 if(includeEvidence)fail('INVALID_PACKAGE','阅读导出不能包含私有原文证据，请使用私人完整备份。');
 const records=snapshot.records,files=new Map(),paths=new Map(),usedPaths=new Map();
 const maps=Object.fromEntries(Object.entries(records).filter(([,list])=>Array.isArray(list)).map(([k,list])=>[k,new Map(list.map(v=>[v.id,v]))]));
 const add=(path,content,mime='text/markdown')=>files.set(path,{path,bytes:encode.encode(content),mime});
 async function nameFor(folder,label,id){const digest=await sha256(encode.encode(id));let path;for(let n=16;n<=64;n+=4){path=folder+'/'+safeName(label)+'--'+digest.slice(0,n)+'.md';const key=path.normalize('NFKC').toLowerCase();if(!usedPaths.has(key)||usedPaths.get(key)===id){usedPaths.set(key,id);return path;}}fail('CONFLICT','导出文件名无法唯一确定。');}
 const terms=records.terms.filter(t=>!t.trashed);
 for(const term of terms)paths.set('term:'+term.id,await nameFor('术语',term.zh||term.en||'自定义术语',term.id));
 const workIds=new Set(),sourceIds=new Set();
 for(const term of terms){const revision=maps.revisions.get(term.currentRevisionId);if(!revision)continue;for(const local of usedSources(revision.lesson)){const source=maps.sources.get(revision.sourceMap[local]);if(source){sourceIds.add(source.id);workIds.add(source.workId);}}}
 for(const workId of workIds){const work=maps.works.get(workId);if(work)paths.set('work:'+workId,await nameFor('文献',work.title,workId));}
 for(const term of terms){
  const path=paths.get('term:'+term.id),revision=maps.revisions.get(term.currentRevisionId);
  const metadata={id:term.id,aliases:term.aliases||[],revision_id:revision?.id||null,source_ids:revision?.sourceIds||[],review_status:revision?.lesson.provenance?.human_scientific_review||'personal-note'};
  let body='---\n'+Object.entries(metadata).map(([k,v])=>k+': '+JSON.stringify(v)).join('\n')+'\n---\n\n# '+md(term.zh||term.en||'自定义术语')+'\n\n';
  if(term.en)body+=md(term.en)+'\n\n';
  if(!revision)body+='这是一份个人术语笔记，尚未保存完整科普。\n\n';
  else{
   const lesson=revision.lesson;
   for(const block of lesson.blocks){
    body+='## '+md(block.heading)+'\n\n'+block.paragraphs.map(highlighted).join('\n\n')+'\n\n';
    if(block.id==='plain_explanation'&&lesson.visual){
     const asset=revision.assetIds.map(id=>maps.assets.get(id)).find(a=>a?.role==='desktop')||revision.assetIds.map(id=>maps.assets.get(id)).find(Boolean);
     if(asset){const assetPath='图示/'+asset.blobHash+'.'+asset.path.split('.').pop();files.set(assetPath,{path:assetPath,blobHash:asset.blobHash,mime:asset.mime});body+='!['+md(lesson.visual.alt)+']('+linkPath('../'+assetPath)+')\n\n'+md(lesson.visual.title)+' · '+md(lesson.visual.takeaway)+'\n\n';}
    }
    if(block.id==='detailed_explanation'&&lesson.formulas?.length){body+='## 公式与符号\n\n';for(const f of lesson.formulas){body+='$$\n'+f.latex+'\n$$\n\n';for(const symbol of f.symbols)body+='- $'+symbol.symbol+'$：'+md(symbol.meaning)+'\n';body+='\n';}}
   }
   if(lesson.glossary?.length){body+='## 必要词汇\n\n';for(const g of lesson.glossary)body+='- **'+md(g.term)+'**：'+md(g.explanation)+'\n';body+='\n';}
   if(lesson.quiz){body+='## 检验理解\n\n'+md(lesson.quiz.question)+'\n\n';for(const o of lesson.quiz.options)body+='- '+o.id.toUpperCase()+'. '+md(o.text)+'\n';body+='\n### 答案与解释\n\n';for(const o of lesson.quiz.options)body+=o.id.toUpperCase()+'：'+(o.id===lesson.quiz.correct_option?'正确。':'')+md(o.explanation)+'\n\n';}
   if(lesson.limitations?.length)body+='## 现有证据的范围\n\n'+lesson.limitations.map(n=>md(n.text)).join('\n\n')+'\n\n';
   const localWorks=new Set([...usedSources(lesson)].map(id=>maps.sources.get(revision.sourceMap[id])?.workId).filter(Boolean));
   if(localWorks.size){body+='## 来源\n\n';for(const id of localWorks){const work=maps.works.get(id),target=paths.get('work:'+id);if(work&&target)body+='- ['+md(work.title)+']('+linkPath('../'+target)+')\n';}body+='\n';}
  }
  const edges=records.edges.filter(e=>e.from.space==='personal'&&e.from.id===term.id&&e.status!=='dismissed');
  if(edges.length){body+='## 相关术语\n\n';for(const edge of edges){let label=edge.to.id;const target=paths.get('term:'+edge.to.id),personal=maps.terms.get(edge.to.id);if(edge.to.space==='personal'&&target)label='['+md(personal?.zh||edge.to.id)+']('+linkPath('../'+target)+')';else if(edge.to.space==='official'){const entry=catalogue.find(t=>t.id===edge.to.id&&t.published===true);if(entry?.url)label='['+md(entry.zh||edge.to.id)+']('+safeURL(entry.url).replace(/[()]/g,c=>c==='('?'%28':'%29')+')';}body+='- '+relationLabel[edge.type]+'：'+label+(edge.status==='suggested'?'（关联建议）':'')+'。'+md(edge.reason)+'\n';}body+='\n';}
  const notes=records.annotations.filter(n=>n.termId===term.id);if(notes.length){body+='## 我的批注\n\n';for(const note of notes)body+=md(note.text)+(note.revisionId&&note.revisionId!==revision?.id?'\n\n（关联到旧修订）':'')+'\n\n';}
  add(path,body);
 }
 for(const id of workIds){const work=maps.works.get(id),path=paths.get('work:'+id);if(!work||!path)continue;let body='---\nid: '+JSON.stringify(id)+'\ndoi: '+JSON.stringify(work.doi||'')+'\n---\n\n# '+md(work.title)+'\n\n';
  const linkedOriginals=new Set();if(includeOriginals)for(const source of records.sources.filter(s=>s.workId===id&&sourceIds.has(s.id)&&s.blobHash)){if(linkedOriginals.has(source.blobHash))continue;linkedOriginals.add(source.blobHash);const file=originalFile(source,{prefix:'原件'}),original=file.path;files.set(original,file);body+='[打开归档原件]('+linkPath('../'+original)+')\n\n';}
  add(path,body);
 }
 for(const note of records.annotations.filter(n=>!n.termId)){const path=await nameFor('笔记',note.fileName||'个人笔记',note.id);add(path,'# 个人笔记\n\n'+md(note.text)+'\n');}
 add('README.md','# 我的知识库\n\n本导出包含 Markdown、图示及所选择的原件，可使用 Obsidian 或普通 Markdown 阅读器查看。\n\n这是阅读导出，网站交互和私有证据需由完整备份恢复。个人批注可能含私人信息，分享前请检查。\n');
 const views=(records.graphViews||[]).map(view=>{const framework=(records.frameworks||[]).find(f=>f.id===view.frameworkId),graph=buildGraph({records,catalogue,officialGraph,view,framework:framework?.legacyTemplate?null:framework});const keys=new Set(graph.nodes.map(n=>n.ref.space+':'+n.ref.id));return {id:view.id,title:view.title,frameworkId:view.frameworkId,mode:view.mode,viewport:view.viewport,nodes:graph.nodes.map(n=>({ref:n.ref,label:n.label,kind:n.kind})),positions:view.nodes.filter(n=>keys.has(n.ref.space+':'+n.ref.id)),groups:graph.groups.map(g=>({id:g.id,title:g.title,members:g.members})),edges:graph.edges.map(e=>({from:e.from,to:e.to,type:e.type,reason:e.reason,origin:e.origin}))};});
 const frameworks=(records.frameworks||[]).map(f=>({id:f.id,title:f.title,description:f.description,scope:f.scope,members:f.members,memberDetails:f.memberDetails,excludedMembers:f.excludedMembers,origin:f.origin}));
 const contexts=(records.contexts||[]).map(c=>{if(c.name)return {id:c.id,name:c.name,aliases:c.aliases,definition:c.definition,basis:c.basis};const g=maps.revisions.get(c.revisionId)?.lesson.glossary?.find(g=>g.id===c.glossaryId);return {id:c.id,name:g?.term||c.id,definition:g?.explanation||'',basis:'literature'};});
 const relations=records.edges.filter(e=>e.status!=='dismissed').map(e=>({from:e.from,to:e.to,type:e.type,reason:e.reason,basis:e.basis||(e.origin==='user'?'manual':'literature')}));
 if(views.length||frameworks.length||contexts.length)add('知识网络/graph.json',JSON.stringify({schemaVersion:3,views,frameworks,contexts,relations},null,2),'application/json');
 return {files:[...files.values()],manifest:{schemaVersion:1,kind:'personal-library-reading',restorable:false,terms:terms.length,includeOriginals,includeEvidence:false}};
}

export async function importMarkdown(value,{fileName='个人笔记.md',baseRevisionId=null}={}){
 if(typeof value!=='string')fail('INVALID_PACKAGE','笔记需要可读文字');if(baseRevisionId!==null)safeId(baseRevisionId);
 const id='note-'+(await sha256(encode.encode(JSON.stringify({value,fileName,baseRevisionId})))).slice(0,32);
 return {id,termId:null,revisionId:baseRevisionId,blockId:null,text:value,fileName:String(fileName).split(/[\\/]/).pop(),origin:'external-markdown',reviewStatus:'user-authored'};
}
