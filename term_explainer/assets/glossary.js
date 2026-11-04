'use strict';
(()=>{const mounted=new WeakMap();
function mountPersonalGlossary(root,{signal,notes:provided}={}){
 mounted.get(root)?.();const controller=new AbortController();
 const listen=(target,type,fn,options={})=>target.addEventListener(type,fn,{...options,signal:controller.signal});
 const data=root.querySelector('#term-notes'),panel=root.querySelector('#term-popover');
 const dispose=()=>{close();controller.abort();signal?.removeEventListener('abort',dispose);mounted.delete(root);};
 let active=null;
 if((!data&&!provided)||!panel)return {dispose:()=>controller.abort()};
 const notes=provided||JSON.parse(data.textContent),title=root.querySelector('#term-popover-title'),description=root.querySelector('#term-popover-description'),link=root.querySelector('#term-popover-link');
 if(signal?.aborted)return {dispose};signal?.addEventListener('abort',dispose,{once:true});mounted.set(root,dispose);
 function disconnect(){if(active){active.setAttribute('aria-expanded','false');active.setAttribute('aria-describedby','term-popover-hint');}}
 function close(){disconnect();panel.hidden=true;active=null;}
 function place(){
  if(!active||panel.hidden)return;
  const r=active.getBoundingClientRect(),w=panel.offsetWidth,h=panel.offsetHeight;
  const viewportWidth=document.documentElement.clientWidth,viewportHeight=innerHeight;
  const left=Math.max(12,Math.min(viewportWidth-w-12,r.left+r.width/2-w/2));
  const top=r.bottom+h+20<=viewportHeight?r.bottom+9:Math.max(12,r.top-h-9);
  panel.style.left=left+'px';panel.style.top=Math.min(Math.max(12,top),Math.max(12,viewportHeight-h-12))+'px';
 }
 function open(trigger){
  const note=notes[trigger.dataset.note];if(!note)return;
  disconnect();
  active=trigger;title.textContent=note.title;description.textContent=note.explanation;
  link.hidden=!note.href;
  if(note.href)link.setAttribute('href',note.href);else link.removeAttribute('href');
  trigger.setAttribute('aria-expanded','true');
  trigger.setAttribute('aria-describedby','term-popover-description term-popover-hint');panel.hidden=false;place();
 }
 for(const trigger of root.querySelectorAll('[data-note]')){
  listen(trigger,'click',event=>{
   event.preventDefault();
   if(active===trigger)close();else open(trigger);
  });
 }
 listen(document,'focusin',event=>{
  if(event.target!==active&&!panel.contains(event.target))close();
 });
 listen(document,'click',event=>{if(!event.target.closest('[data-note]')&&!panel.contains(event.target))close();});
 listen(document,'keydown',event=>{
  if(event.key==='ArrowDown'&&active&&event.target===active){
   event.preventDefault();(link.hidden?panel:link).focus({preventScroll:true});return;
  }
  if(event.key==='Tab'&&active&&panel.contains(event.target)){
   const previous=active;event.preventDefault();
   if(event.shiftKey){previous.focus({preventScroll:true});return;}
   // The shared panel lives at the end of main. Continue in the trigger's
   // logical reading order instead of skipping the remainder of the article.
   const controls=[...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
    .filter(el=>el.tabIndex>=0&&!el.disabled&&!panel.contains(el)&&el.getClientRects().length);
   const next=controls[controls.indexOf(previous)+1];close();
   if(next)next.focus({preventScroll:true});
   else previous.focus({preventScroll:true});
   return;
  }
  if(event.key==='Escape'&&active){const previous=active;const restore=panel.contains(document.activeElement);close();
   if(restore)previous.focus({preventScroll:true});}
 });
 listen(document,'scroll',event=>{
  if(panel.contains(event.target))return;
  // Tab/focus can scroll a previously offscreen word into view. Preserve its
  // accessible explanation throughout smooth scrolling (the word can still be
  // offscreen in early frames). Focus/blur owns dismissal for keyboard users.
  if(active&&(active.matches(':focus-visible')||panel.contains(document.activeElement))){
   place();return;
  }
  close();
 },{passive:true,capture:true});
 listen(window,'resize',close,{passive:true});
 return {dispose};
}
window.PsychPersonalGlossary={mountPersonalGlossary};
document.addEventListener('DOMContentLoaded',()=>mountPersonalGlossary(document),{once:true});
})();
