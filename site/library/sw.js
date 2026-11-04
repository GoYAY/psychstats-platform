'use strict';
const BUILD_VERSION='__BUILD_VERSION__';
const SCOPE=new URL(self.registration.scope),ROOT=new URL('../',SCOPE),PREFIX='psych-library-offline:'+encodeURIComponent(SCOPE.href)+':',CACHE=PREFIX+BUILD_VERSION;
const MANIFEST=new URL('offline-manifest.json',SCOPE).href;
let manifest;
function allowed(url){return url.origin===SCOPE.origin&&!url.username&&!url.password&&!url.hash&&(!url.search||/^\?v=[a-f0-9]+$/.test(url.search))&&(url.pathname===SCOPE.pathname+'index.html'||url.pathname.startsWith(ROOT.pathname+'assets/'));}
async function storedManifest(){if(manifest)return manifest;const cache=await caches.open(CACHE),response=await cache.match(MANIFEST);if(response)manifest=await response.json();return manifest;}
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(CACHE);if(await cache.match(MANIFEST)){await self.skipWaiting();return;}
 try{
  const response=await fetch(MANIFEST,{cache:'no-store'});if(!response.ok)throw Error('离线清单不可用');const data=await response.json();if(data.version!==BUILD_VERSION||!Array.isArray(data.resources))throw Error('离线版本不匹配');
  let next=0;async function download(){while(next<data.resources.length){const resource=data.resources[next++],url=new URL(resource.url,SCOPE);if(!allowed(url)||!/^[a-f0-9]{64}$/.test(resource.hash))throw Error('离线资源越界');const file=await fetch(url.href,{cache:'reload',credentials:'same-origin'});if(!file.ok)throw Error('离线资源缺失');const digest=await crypto.subtle.digest('SHA-256',await file.clone().arrayBuffer()),actual=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');if(actual!==resource.hash)throw Error('离线资源指纹不符');await cache.put(url.href,file);}}
  const results=await Promise.allSettled(Array.from({length:4},download));const error=results.find(r=>r.status==='rejected');if(error)throw error.reason;
  await cache.put(MANIFEST,Response.json(data));manifest=data;await self.skipWaiting();
 }catch(error){await caches.delete(CACHE);throw error;}
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{if(!await storedManifest())throw Error('不能激活不完整缓存');await self.clients.claim();const previous=(await caches.keys()).filter(k=>k.startsWith(PREFIX)&&k!==CACHE);for(const key of previous.slice(0,-1))await caches.delete(key);})()));
self.addEventListener('message',event=>{if(event.data?.type==='offline-status')event.waitUntil((async()=>{const ready=!!await storedManifest();event.ports[0]?.postMessage({state:ready?'ready':'not-prepared',version:BUILD_VERSION});})());});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);if(request.method!=='GET'||url.origin!==SCOPE.origin)return;
 // Never intercept other HTML routes, uploaded files, APIs or credentials.
 if(url.pathname!==SCOPE.pathname+'index.html'&&!allowed(url))return;
 event.respondWith((async()=>{const data=await storedManifest(),cache=await caches.open(CACHE);const key=url.pathname===SCOPE.pathname+'index.html'?new URL('index.html',SCOPE).href:request.url;
  if(data?.resources.some(r=>new URL(r.url,SCOPE).href===key)){const cached=await cache.match(key);if(cached)return cached;}
  return fetch(request);
 })());
});
