// Teaching-only projection. Evidence and raw provider payloads never enter the DOM.
import {personalBarData} from '../charts/data.mjs';
import {enhanceChart} from '../charts/loader.mjs';
import {validatePresentation} from '../charts/presentation.mjs';
const BODY=new Set(['operational_definition','plain_explanation','detailed_explanation','how_to_use']);
const names=t=>[t?.term,t?.zh,t?.en,...t?.aliases||[]].filter(v=>typeof v==='string'&&v.trim());
export function readerProjection(revision,sources=[],works=[]){
 const l=revision.lesson,used=new Set(),presentation=l.visual?validatePresentation(l.visual):null;
 const visit=v=>{if(!v||typeof v!=='object')return;for(const ref of v.refs||[])used.add(revision.sourceMap[ref.source_id]);for(const [k,x] of Object.entries(v))if(!['refs','provenance','source_relations'].includes(k))Array.isArray(x)?x.forEach(visit):visit(x);};visit(l);
 const titles=[...new Set(sources.filter(s=>used.has(s.id)).map(s=>works.find(w=>w.id===s.workId)?.title).filter(Boolean))];
 return {term:{id:l.term.id,zh:l.term.zh,en:l.term.en||l.provenance?.verified_identity?.en||'',aliases:l.term.aliases||[]},blocks:l.blocks.map(b=>({id:b.id,heading:b.heading,paragraphs:b.paragraphs.map(p=>({text:p.text,emphasis:p.emphasis||[]}))})),glossary:(l.glossary||[]).map(g=>({id:g.id,term:g.term,aliases:g.aliases||[],explanation:g.explanation,target:g.target,targetSpace:g.targetSpace||revision.targetSpaces?.[g.target]||null})),formulas:(l.formulas||[]).map(f=>({latex:f.latex,symbols:f.symbols.map(s=>({symbol:s.symbol,meaning:s.meaning}))})),visual:l.visual?{title:l.visual.title,alt:l.visual.alt,takeaway:l.visual.takeaway,presentation,interactiveData:personalBarData(l.visual)}:null,quiz:l.quiz?{question:l.quiz.question,correct_option:l.quiz.correct_option,options:l.quiz.options.map(o=>({id:o.id,text:o.text,explanation:o.explanation}))}:null,sources:titles,evidenceRemoved:!!(revision.provenance?.removedEvidence||l.provenance?.removedEvidence),limitations:(l.limitations||[]).map(n=>n.text)};
}
export function createWordTokenizer(glossary,catalogue,current){
 const entries=new Map();const add=(name,key,self=false)=>{if(name.length===1&&/^[a-z]$/i.test(name))return;const folded=name.toLowerCase(),v=entries.get(folded)||{name,notes:new Set(),self:false};if(key)v.notes.add(key);v.self||=self;entries.set(folded,v);};
 for(const t of catalogue)for(const n of names(t))add(n,null);
 for(const g of glossary)for(const n of names(g))add(n,g.id);
 for(const n of names(current))add(n,null,true);
 const choices=[...entries.values()].sort((a,b)=>b.name.length-a.name.length),buckets=new Map();
 for(const v of choices){v.folded=v.name.toLowerCase();v.left=/^[a-z0-9_]/i.test(v.name);v.right=/[a-z0-9_]$/i.test(v.name);const key=v.name[0].toLowerCase();if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(v);}
 return (text,block)=>{
 if(!BODY.has(block))return [{text}];
 const out=[];let start=0,at=0;
 while(at<text.length){const found=buckets.get(text[at].toLowerCase())?.find(v=>text.slice(at,at+v.name.length).toLowerCase()===v.folded&&(!v.left||!/[a-z0-9_İıſ]/i.test(text[at-1]||''))&&(!v.right||!/[a-z0-9_İıſ]/i.test(text[at+v.name.length]||'')));
  if(!found){at++;continue;}if(at>start)out.push({text:text.slice(start,at)});out.push({text:text.slice(at,at+found.name.length),...(!found.self&&found.notes.size===1?{note:[...found.notes][0]}:{})});at+=found.name.length;start=at;
 }if(start<text.length)out.push({text:text.slice(start)});return out;
 };
}
export function wordTokens(text,block,glossary,catalogue,current){return createWordTokenizer(glossary,catalogue,current)(text,block);}
const scriptFlights=new Map();
function runtimeScript(name,globalName){
 if(window[globalName])return Promise.resolve();
 if(scriptFlights.has(name))return scriptFlights.get(name);
 const flight=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=new URL(name,import.meta.url);s.onload=resolve;s.onerror=()=>{s.remove();reject(Error('读者交互资源未能载入，可重试打开。'));};document.head.append(s);});
 scriptFlights.set(name,flight);flight.catch(()=>{if(scriptFlights.get(name)===flight)scriptFlights.delete(name);});return flight;
}
async function sharedRuntime(formulas){
 const sheet=name=>{const href=new URL(name,import.meta.url).href;if(![...document.querySelectorAll('link[rel=stylesheet]')].some(l=>l.href===href)){const l=document.createElement('link');l.rel='stylesheet';l.href=href;document.head.append(l);}};sheet('reader.css');if(formulas)sheet('../vendor/katex/katex.min.css');
 await Promise.all([runtimeScript('legacy-reader.js','PsychPersonalTeaching'),runtimeScript('legacy-glossary.js','PsychPersonalGlossary')]);
 if(formulas&&!window.katex){const src=new URL('../vendor/katex/katex.min.js',import.meta.url);await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.onload=resolve;s.onerror=()=>reject(Error('公式资源未能载入。'));document.head.append(s);});}
}
const mounts=new WeakMap();
export function mountReader(root,{revision,sources=[],works=[],catalogue=[],resolveAsset,signal,chartHost=null,state={}}={}){
 mounts.get(root)?.dispose();const local=new AbortController(),urls=[];let quizMount,glossaryMount,host,chart,chartFrame,assembled=false;
 const initialData=personalBarData(revision.lesson.visual),initial={selected:revision.lesson.quiz?.options.some(o=>o.id===state.selected)?state.selected:null,chart:initialData?{selectedCategory:initialData.series[0].points.some(p=>p.category===state.chart?.selectedCategory)?state.chart.selectedCategory:null}:null};
 const dispose=()=>{if(local.signal.aborted)return;local.abort();chart?.dispose();quizMount?.dispose();glossaryMount?.dispose();for(const url of urls)URL.revokeObjectURL(url);signal?.removeEventListener('abort',dispose);if(mounts.get(root)===instance)mounts.delete(root);};
 const instance={dispose,capture:()=>({selected:assembled?(host?.querySelector('.quiz-option[aria-pressed=true]')?.dataset.option||null):initial.selected,chart:chart?.capture()||(initial.chart?{...initial.chart}:null)}),ready:null};mounts.set(root,instance);if(signal?.aborted){dispose();instance.ready=Promise.resolve(false);return instance;}signal?.addEventListener('abort',dispose,{once:true});
 instance.ready=(async()=>{
  const view=readerProjection(revision,sources,works),tokenize=createWordTokenizer(view.glossary,catalogue,view.term);host=document.createElement('article');host.className='personal-reader';
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const emphasize=(node,value,phrases)=>{const words=[...phrases].filter(Boolean).sort((a,b)=>b.length-a.length);let at=0;while(at<value.length){let best=null;for(const word of words){const i=value.indexOf(word,at);if(i>=0&&(!best||i<best.i))best={i,word};}if(!best){node.append(document.createTextNode(value.slice(at)));break;}node.append(document.createTextNode(value.slice(at,best.i)),el('strong',best.word));at=best.i+best.word.length;}};
  host.append(el('h1',view.term.zh),el('p',view.term.en,'personal-english'));
  for(const block of view.blocks){const section=el('section',null,block.id==='real_question'?'personal-question':'personal-block');section.id=block.id;section.dataset.blockId=block.id;section.append(el('h2',block.id==='real_question'?'“ 你可能会问':block.heading));
   for(const p of block.paragraphs){const paragraph=el('p');for(const token of tokenize(p.text,block.id)){let node=paragraph;if(token.note){node=el('button',null,'term-help');node.type='button';node.dataset.note=token.note;node.setAttribute('aria-expanded','false');node.setAttribute('aria-haspopup','dialog');node.setAttribute('aria-controls','term-popover');paragraph.append(node);}emphasize(node,token.text,p.emphasis);}section.append(paragraph);}host.append(section);
   if(block.id==='plain_explanation'&&view.visual&&resolveAsset){const asset=await resolveAsset(innerWidth<=650?'mobile':'desktop');if(local.signal.aborted)return false;if(asset){const url=URL.createObjectURL(asset);urls.push(url);const image=el('img');image.src=url;image.alt=view.visual.alt;await image.decode();if(local.signal.aborted)return false;image.width=image.naturalWidth;image.height=image.naturalHeight;image.style.display='block';const figure=el('figure');figure.id='visual';chartFrame=el('div');chartFrame.style.position='relative';if(chartHost?.moduleURL&&view.visual.interactiveData)chartFrame.style.minHeight='460px';chartFrame.dataset.personalChart='true';chartFrame.append(image);figure.append(chartFrame,el('figcaption',view.visual.title+' · '+view.visual.takeaway));host.append(figure);}}
   if(block.id==='detailed_explanation'&&view.formulas.length){const section=el('section',null,'personal-block');section.id='formulas';section.append(el('h2','公式与符号'));for(const f of view.formulas){const box=el('div',null,'personal-formula'),math=el('div',f.latex,'math');math.dataset.latex=f.latex;box.append(math);const list=el('dl');for(const s of f.symbols){const row=el('div'),symbol=el('dt',s.symbol,'symbol-math');symbol.dataset.latex=s.symbol;row.append(symbol,el('dd',s.meaning));list.append(row);}box.append(list);section.append(box);}host.append(section);}
  }
  if(view.quiz){const section=el('section',null,'personal-quiz');section.id='quiz';section.append(el('h2','检验理解'),el('h3',view.quiz.question));for(const o of view.quiz.options){const b=el('button',o.id.toUpperCase()+'. '+o.text,'quiz-option');b.type='button';b.dataset.option=o.id;b.setAttribute('aria-pressed','false');section.append(b);}const feedback=el('p');feedback.id='quiz-feedback';feedback.setAttribute('aria-live','polite');section.append(feedback);host.append(section);}
  if(view.limitations.length||view.evidenceRemoved){const section=el('section',null,'personal-block personal-evidence-scope');section.id='evidence-scope';section.append(el('h2','现有证据的范围'));for(const limitation of view.limitations)section.append(el('p',limitation));if(view.evidenceRemoved)section.append(el('p','本修订的部分提取片段已删除；如需用原文重新核对，请重新导入相应资料。原有科学审核状态保持不变。'));host.append(section);}
  const section=el('section',null,'personal-sources');section.id='sources';section.append(el('h2','来源与核对'));const list=el('ul');for(const title of view.sources)list.append(el('li',title));section.append(list);host.append(section);
  const panel=el('div',null,'term-popover');panel.id='term-popover';panel.hidden=true;panel.tabIndex=-1;panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','false');panel.setAttribute('aria-labelledby','term-popover-title');panel.setAttribute('aria-describedby','term-popover-description');const title=el('div'),description=el('p'),link=el('a','查看完整科普 →');title.id='term-popover-title';description.id='term-popover-description';link.id='term-popover-link';panel.append(title,description,link);host.append(panel);const hint=el('span','按 Enter 或空格打开解释；向下箭头进入，Esc 关闭。','personal-sr-only');hint.id='term-popover-hint';host.append(hint);
  const notes=Object.fromEntries(view.glossary.map(g=>{const targets=catalogue.filter(t=>(t.id===g.target||names(t).some(n=>names(g).includes(n)))&&t.published===true&&(!g.targetSpace||g.targetSpace===t.space)&&g.targetSpace!=='pending');return [g.id,{title:g.term,explanation:g.explanation,href:targets.length===1?targets[0].url:null}];}));
  await sharedRuntime(!!view.formulas.length);if(local.signal.aborted)return false;
  root.replaceChildren(host);quizMount=window.PsychPersonalTeaching.mountPersonalQuiz(host,{signal:local.signal,quiz:view.quiz});glossaryMount=window.PsychPersonalGlossary.mountPersonalGlossary(host,{signal:local.signal,notes});if(initial.selected)[...host.querySelectorAll('.quiz-option')].find(b=>b.dataset.option===initial.selected)?.click();if(chartFrame&&view.visual?.interactiveData&&chartHost?.moduleURL)chart=enhanceChart(chartFrame,{data:view.visual.interactiveData,moduleURL:chartHost.moduleURL,signal:local.signal,state:initial.chart});assembled=true;return true;
 })().catch(e=>{dispose();throw e;});return instance;
}
