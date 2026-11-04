// Shared actual-section navigation: no provider calls, routing or reader remount.
export function readingSections(lesson){
 const rows=[];
 for(const b of lesson.blocks||[]){
  rows.push({id:b.id,label:b.id==='real_question'?'你可能会问':b.heading});
  if(b.id==='plain_explanation'&&lesson.visual)rows.push({id:'visual',label:'图解示例'});
  if(b.id==='detailed_explanation'&&lesson.formulas?.length)rows.push({id:'formulas',label:'公式与符号'});
 }
 if(lesson.quiz)rows.push({id:'quiz',label:'检验理解'});
 if(lesson.limitations?.length)rows.push({id:'evidence-scope',label:'现有证据的范围'});
 rows.push({id:'sources',label:'来源与核对'});return rows;
}

export function mountReadingNavigation(aside,article,{lesson,signal,hrefFor=id=>'#'+id}={}){
 const local=new AbortController();let observer,sizeObserver;
 const details=document.createElement('details');details.className='reading-toc';details.open=innerWidth>=1000;
 const summary=document.createElement('summary');summary.textContent='本页导航';details.append(summary);
 const nav=document.createElement('nav');nav.setAttribute('aria-label','本页导航');details.append(nav);
 const mark=id=>{for(const link of nav.querySelectorAll('a'))if(link.dataset.section===id)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');};
 const sections=readingSections(lesson).map(row=>({...row,node:article.querySelector('[id="'+row.id+'"]')})).filter(row=>row.node);
 for(const row of sections){
  const a=document.createElement('a');a.href=hrefFor(row.id);a.textContent=row.label;a.dataset.section=row.id;
  a.addEventListener('click',event=>{if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();row.node.scrollIntoView({block:'start',behavior:'auto'});mark(row.id);},{signal:local.signal});nav.append(a);
 }
 if(sections.length)mark(sections[0].id);aside.prepend(details);
 const adjust=()=>{const flow=innerWidth<1000||aside.scrollHeight>innerHeight-170;aside.classList.toggle('reading-aside-flow',flow);if(innerWidth>=1000)details.open=true;};
 if(typeof ResizeObserver!=='undefined'){sizeObserver=new ResizeObserver(adjust);sizeObserver.observe(aside);}
 window.addEventListener('resize',adjust,{signal:local.signal});adjust();
 if(typeof IntersectionObserver!=='undefined'){
  observer=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);if(visible[0])mark(visible[0].target.id);},{rootMargin:'-145px 0px -60% 0px',threshold:0});
  for(const row of sections)observer.observe(row.node);
 }
 const dispose=()=>{if(local.signal.aborted)return;local.abort();observer?.disconnect();sizeObserver?.disconnect();signal?.removeEventListener('abort',dispose);details.remove();};
 if(signal?.aborted)dispose();else signal?.addEventListener('abort',dispose,{once:true});
 return {dispose};
}
