(function (window) {
  'use strict';
  var modules = new Map(), mounted = [], controller = null, resources = new Map();
  function register(name, mount) { modules.set(name, mount); }
  function unmountPage() {
    if (controller) controller.abort();
    mounted.reverse().forEach(function (item) { item.cleanup.forEach(function (fn) { try { fn(); } catch (error) { console.error(error); } }); });
    mounted = []; controller = null;
  }
  function mountPage(options) {
    unmountPage(); controller = new AbortController(); var active = controller;
    modules.forEach(function (mount, name) {
      var cleanup = [], ctx = {main:options.main,url:options.url,siteRoot:options.siteRoot,state:(options.state || {})[name] || {},signal:active.signal,
        alive:function () { return !active.signal.aborted; },
        deferCleanup:function (fn) { if(typeof fn==='function')cleanup.push(fn); },
        on:function (target,event,fn,settings) { target.addEventListener(event,fn,settings); cleanup.push(function(){target.removeEventListener(event,fn,settings);}); }};
      var item={name:name,result:{},cleanup:cleanup};mounted.push(item);
      var result;
      try { result=mount(ctx) || {}; }
      catch(error){unmountPage();throw error;}
      item.result=result;
      if(result.dispose)cleanup.push(result.dispose);
    });
  }
  function capturePage() {
    var state={}; mounted.forEach(function (item) { if(item.result.capture)state[item.name]=item.result.capture(); }); return state;
  }
  function ensureResource(node,url) {
    var href=new URL(node.getAttribute(node.tagName==='SCRIPT'?'src':'href'),url).href;
    if(resources.has(href))return resources.get(href);
    var attr=node.tagName==='SCRIPT'?'src':'href';
    var existing=Array.from(document.querySelectorAll(node.tagName==='SCRIPT'?'script[src]':'link[rel="stylesheet"]')).find(function(el){return el[attr]===href;});
    if(existing){var ready=Promise.resolve();resources.set(href,ready);return ready;}
    var promise=new Promise(function(resolve,reject){
      var el=document.createElement(node.tagName.toLowerCase());
      if(attr==='href')el.rel='stylesheet'; else el.async=false;
      el[attr]=href; var timer=setTimeout(function(){el.remove();reject(new Error('页面资源加载超时'));},10000);
      el.onload=function(){clearTimeout(timer);resolve();};el.onerror=function(){clearTimeout(timer);el.remove();reject(new Error('页面资源加载失败'));};
      document.head.appendChild(el);
    });
    resources.set(href,promise); promise.catch(function(){resources.delete(href);});return promise;
  }
  function preparePage(doc,url) {
    var allowed=/\/assets\/(?:symbols\.js|analysis-reader\.(?:js|css)|data\/practice-data\.js|library-runtime\.js|library(?:-[a-f0-9]{16})?\/(?:library|reader)\.css)(?:\?|$)/;
    var nodes=Array.from(doc.querySelectorAll('script[src],link[rel="stylesheet"]')).filter(function(node){
      var resource=new URL(node.getAttribute(node.tagName==='SCRIPT'?'src':'href'),url);
      return resource.origin===new URL(url).origin&&allowed.test(resource.pathname+resource.search);
    });
    return nodes.reduce(function(chain,node){return chain.then(function(){return ensureResource(node,url);});},Promise.resolve());
  }
  window.PsychPageRuntime={register:register,mountPage:mountPage,unmountPage:unmountPage,capturePage:capturePage,preparePage:preparePage};
  register('reading-layout',function(ctx){
    if(!window.ResizeObserver||!window.CSS?.supports('content-visibility','auto'))return {};
    var blocks=Array.from(ctx.main.querySelectorAll('.term-content > section'));
    if(!blocks.length)return {};
    // ResizeObserver supplies already-computed sizes; never measure every
    // off-screen block synchronously just to remember a reading position.
    var sizes=[],restored=ctx.state.viewport===window.innerWidth?ctx.state.sizes:[];
    blocks.forEach(function(block,index){
      var height=restored?.[index];
      if(Number.isFinite(height)&&height>=0){sizes[index]=height;block.style.containIntrinsicBlockSize='auto '+height+'px';}
    });
    var indexes=new Map(blocks.map(function(block,index){return [block,index];}));
    var observer=new ResizeObserver(function(entries){
      entries.forEach(function(entry){sizes[indexes.get(entry.target)]=entry.contentRect.height;});
    });
    blocks.forEach(function(block){observer.observe(block);});
    ctx.deferCleanup(function(){observer.disconnect();});
    return {capture:function(){return {viewport:window.innerWidth,sizes:sizes.slice()};}};
  });
  document.addEventListener('DOMContentLoaded',function(){
    var main=document.querySelector('body > main'); if(!main)return;
    var script=document.querySelector('script[src*="assets/page-runtime.js"]');
    var siteRoot=script?new URL('../',script.src).href:new URL('./',window.location.href).href;
    mountPage({main:main,url:window.location.href,siteRoot:siteRoot,state:window.history?.state?.psychNav?.pageState || {}});
  },{once:true});
})(window);
