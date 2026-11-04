import {validateBarData} from './data.mjs';
const modules=new Map(),mounts=new WeakMap();
function load(url){if(!modules.has(url)){const p=import(url);modules.set(url,p);p.catch(()=>modules.delete(url));}return modules.get(url);}
export function enhanceChart(element,{data,moduleURL,signal,state}={}){
 mounts.get(element)?.dispose();
 const valid=validateBarData(data),local=new AbortController();let widget,overlay,observer,idle,timer,settled=false,resolve;
 const ready=new Promise(r=>resolve=r),finish=v=>{if(!settled){settled=true;resolve(v);}};
 const original=element.querySelector('[data-chart-static]')||element.querySelector('picture')||element.querySelector('img');
 const visibility=original?.style.visibility,aria=original?.getAttribute('aria-hidden');
 let saved={selectedCategory:valid?.series[0].points.some(p=>p.category===state?.selectedCategory)?state.selectedCategory:null};
 const capture=()=>{if(widget&&!local.signal.aborted)saved=widget.capture();return {...saved};};
 const instance={ready,capture,dispose(){if(local.signal.aborted)return;capture();local.abort();observer?.disconnect();if(idle!==undefined)globalThis.cancelIdleCallback?.(idle);clearTimeout(timer);signal?.removeEventListener('abort',instance.dispose);widget?.dispose();overlay?.remove();if(original){original.style.visibility=visibility||'';if(aria===null)original.removeAttribute('aria-hidden');else if(aria!==undefined)original.setAttribute('aria-hidden',aria);}element.removeAttribute('data-chart-enhanced');finish(false);if(mounts.get(element)===instance)mounts.delete(element);}};
 mounts.set(element,instance);
 const live=()=>!local.signal.aborted&&element.isConnected;
 async function mount(){
  if(!live()){instance.dispose();return;}
  try{
   const importedAt=globalThis.performance?.now();const module=await load(moduleURL);const loadedAt=globalThis.performance?.now();if(!live())return instance.dispose();
   const rect=element.getBoundingClientRect();if(rect.width<=0||rect.height<=0)return instance.dispose();
   overlay=element.ownerDocument.createElement('div');overlay.className='instant-chart-host';overlay.setAttribute('data-chart-interactive','');
   overlay.style.cssText='position:absolute;inset:0;width:100%;height:100%;visibility:hidden;';element.append(overlay);
   const theme=typeof getComputedStyle==='function'?getComputedStyle(element).getPropertyValue('--theme-color').trim():undefined;
   widget=module.mountChart(overlay,{data:valid,themeColor:theme,signal:local.signal,state});
   timer=setTimeout(()=>instance.dispose(),8000);
   if(!await widget.ready||!live()){instance.dispose();return;}
   clearTimeout(timer);if(typeof importedAt==='number'&&typeof loadedAt==='number'){performance.measure('psych-chart-import',{start:importedAt,end:loadedAt});performance.measure('psych-chart-mount',{start:loadedAt,end:performance.now()});}overlay.style.visibility='visible';if(original){original.style.visibility='hidden';original.setAttribute('aria-hidden','true');}element.setAttribute('data-chart-enhanced','true');finish(true);
  }catch{instance.dispose();}
 }
 const schedule=()=>{observer?.disconnect();if(!live())return instance.dispose();if(typeof requestIdleCallback==='function')idle=requestIdleCallback(()=>{void mount();},{timeout:1500});else timer=setTimeout(()=>{void mount();},0);};
 if(!valid||typeof moduleURL!=='string'||signal?.aborted){instance.dispose();return instance;}
 signal?.addEventListener('abort',instance.dispose,{once:true});
 if(typeof IntersectionObserver==='function'){observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))schedule();},{rootMargin:'180px'});observer.observe(element);}else schedule();
 return instance;
}
