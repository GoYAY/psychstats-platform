(function (window) {
  'use strict';
  if (!/^https?:$/.test(location.protocol) || !window.PsychNavigationPolicy || !window.PsychPageRuntime) return;
  var policy=window.PsychNavigationPolicy, runtime=window.PsychPageRuntime;
  var script=document.querySelector('script[src*="assets/soft-navigation.js"]');
  var siteRoot=new URL('../',script.src).href, cache=policy.createCache(12), flights=new Map();
  var serial=0, currentController=null, activeURL=location.href, activeEntry=null, hoverTimer=null, idleTimer=null;
  var prepared=new Map(), resourceHints=new Map(), inputMode='pointer', visibilityObserver=null, backgroundTimer=null;
  var version=document.querySelector('meta[name="psych-runtime"]')?.content || '';
  // Separate text snapshots keep the travelling opaque shadow below labels.
  document.querySelectorAll('.site-head .nav-row > nav a').forEach(function(link,index){link.style.viewTransitionName='psych-nav-text-'+index;});
  var metrics=[], longTasks=[], entries=new Map();
  var status=document.createElement('p');status.className='soft-navigation-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.hidden=true;document.body.appendChild(status);
  function rootURL(url){var u=new URL(url,activeURL);return u.origin===new URL(siteRoot).origin&&u.pathname.startsWith(new URL(siteRoot).pathname);}
  function key(url){var u=new URL(url);u.hash='';return u.href;}
  function sameReturn(a,b){
    if(key(a)===key(b))return true;
    var first=new URL(a),second=new URL(b);
    if(first.origin!==second.origin||first.pathname!==second.pathname||!first.pathname.endsWith('/index.html'))return false;
    [first,second].forEach(function(url){url.hash='';url.searchParams.delete('theme');if(!url.searchParams.has('topic'))url.searchParams.set('topic','foundations');url.searchParams.sort();});
    return first.href===second.href;
  }
  function normalizeTreeURLs(tree,url) {
    tree.querySelectorAll('[href],[src],[srcset],[action]').forEach(function(el){
      ['href','src','action'].forEach(function(attr){
        if(!el.hasAttribute(attr))return;var value=el.getAttribute(attr);
        if(!value || /^(?:data:|mailto:|tel:|javascript:|blob:)/i.test(value))return;
        el.setAttribute(attr,new URL(value,url).href);
      });
      var srcset=el.getAttribute('srcset');
      if(srcset&&!/^data:/i.test(srcset))el.setAttribute('srcset',srcset.split(',').map(function(item){var parts=item.trim().split(/\s+/);parts[0]=new URL(parts[0],url).href;return parts.join(' ');}).join(', '));
    });
  }
  function parsePage(html,url) {
    var doc=new DOMParser().parseFromString(html,'text/html'), main=doc.querySelector('body > main');
    if(!main || !doc.querySelector('.site-head'))throw Error('目标不是支持的站内页面');
    main.querySelectorAll('script').forEach(function(node){node.remove();});
    main.querySelectorAll('*').forEach(function(node){Array.from(node.attributes).forEach(function(attr){if(/^on/i.test(attr.name))node.removeAttribute(attr.name);});});
    normalizeTreeURLs(main,url);
    var selection=doc.querySelector('.site-head .nav-row > nav a[aria-current="page"]');
    return {doc:doc,main:main,title:doc.title,pageAttrs:{bodyClass:doc.body.className,lang:doc.documentElement.lang},
      searchConfig:{root:siteRoot},navSelection:selection?new URL(selection.getAttribute('href'),url).pathname:null,
      runtimeVersion:doc.querySelector('meta[name="psych-runtime"]')?.content || ''};
  }
  async function load(url,signal) {
    var resourceKey=key(url), existing=cache.get(resourceKey);
    if(existing)return existing;
    // Prefetch promises are shared, but a navigation's AbortController never
    // cancels another navigation's response. The serial gate owns submission.
    if(flights.has(resourceKey))return flights.get(resourceKey);
    var promise=(async function(){
      var response=await fetch(resourceKey,{signal:signal,credentials:'same-origin'});
      if(!response.ok || !/\btext\/html\b/i.test(response.headers.get('content-type')||'') || !policy.shouldHandle({href:response.url},{button:0},siteRoot+'__routing__.html',siteRoot))throw Error('页面未能完整加载');
      // Parse only at submission. Prefetch keeps bytes, not duplicate DOM trees.
      var page={html:await response.text(),url:response.url};cache.set(resourceKey,page);return page;
    })();
    if(!signal){flights.set(resourceKey,promise);promise.finally(function(){flights.delete(resourceKey);}).catch(function(){});}
    return promise;
  }
  function entry(url) {return {entryId:Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),url:url,scroll:[0,0],focusId:null,pageState:{},origin:null};}
  function saveCurrent(){
    if(!activeEntry)return;
    activeEntry=Object.assign({},activeEntry,{url:activeURL,scroll:[scrollX,scrollY],focusId:document.activeElement?.id||null,pageState:runtime.capturePage()});
    entries.set(activeEntry.entryId,activeEntry);
    // During popstate location already names the destination; don't overwrite it.
    if(location.href===activeURL)history.replaceState(Object.assign({},history.state,{psychNav:activeEntry}),'',activeURL);
  }
  function topicHistory(url){
    // site.js captures the outgoing topic before it changes the controls.
    activeURL=url;activeEntry=entry(url);activeEntry.pageState=runtime.capturePage();
    history.pushState(Object.assign({},history.state,{psychNav:activeEntry}),'',url);
    scheduleAdjacent();
  }
  function allowedPrefetch(){var conn=navigator.connection;return !conn || (!conn.saveData&&!/^(slow-2g|2g)$/.test(conn.effectiveType));}
  function rememberPrepared(url,parsed){
    prepared.delete(key(url));prepared.set(key(url),parsed);
    while(prepared.size>10)prepared.delete(prepared.keys().next().value);
  }
  function collectHints(doc){
    var node=doc.querySelector('script[data-psych-resource-hints]');if(!node)return;
    try{Object.entries(JSON.parse(node.textContent)).forEach(function(pair){
      var url=new URL(pair[0],siteRoot);if(!rootURL(url.href))return;
      resourceHints.set(url.origin+url.pathname,pair[1]);
    });while(resourceHints.size>256)resourceHints.delete(resourceHints.keys().next().value);}catch(_){}
  }
  function prepareEarly(url){
    var target=new URL(url),record=resourceHints.get(target.origin+target.pathname);
    // Optional hints may fail; authoritative document preparation retries them.
    return record&&runtime.prepareCriticalResources?runtime.prepareCriticalResources(record,url).catch(function(){}):Promise.resolve();
  }
  async function warmPage(url){
    if(prepared.has(key(url)))return;
    var early=prepareEarly(url);
    var page=await load(url);
    // Yield after the response; background parsing must not monopolize input.
    await new Promise(function(resolve){setTimeout(resolve,0);});
    var parsed=parsePage(page.html,page.url);
    if(parsed.runtimeVersion!==version)return;
    collectHints(parsed.doc);
    await Promise.all([early,runtime.preparePage(parsed.doc,page.url)]);
    rememberPrepared(url,parsed);
  }
  var prefetch=policy.createPrefetchQueue({load:warmPage,allowed:allowedPrefetch,maxConcurrent:2});
  function scheduleAdjacent(){
    clearTimeout(idleTimer);clearTimeout(backgroundTimer);prefetch.cancel();visibilityObserver?.disconnect();
    idleTimer=setTimeout(function(){
      Array.from(document.querySelectorAll('.term-sequence a')).slice(0,2).forEach(function(link){if(rootURL(link.href))prefetch.enqueue(key(link.href),5);});
      // Visible cards keep priority over background destinations as users scroll.
      // Touch screens cannot benefit from a hover-only trigger.
      backgroundTimer=setTimeout(function(){Array.from(document.querySelectorAll('.site-head nav a')).filter(function(link){return policy.shouldHandle(info(link),{button:0},activeURL,siteRoot)&&key(link.href)!==key(activeURL);}).slice(0,6).forEach(function(link){prefetch.enqueue(key(link.href));});},50);
      if(window.IntersectionObserver){
        visibilityObserver=new IntersectionObserver(function(items){
          items.forEach(function(item){if(!item.isIntersecting||!item.target.isConnected||item.target.hidden)return;
            var link=item.target.querySelector('a[data-expand-card]');
            if(link&&policy.shouldHandle(info(link),{button:0},activeURL,siteRoot))prefetch.enqueue(key(link.href),10);
          });
        });
        document.querySelectorAll('.term-card:not([hidden]),.analysis-card,.practice-reading[data-loaded=true]').forEach(function(card){visibilityObserver.observe(card);});
      }
    },150);
  }
  function focusDestination(element){
    if(!element)return;
    if(inputMode==='pointer')element.setAttribute('data-psych-pointer-focus','');
    else element.removeAttribute('data-psych-pointer-focus');
    element.focus({preventScroll:true});
  }
  function showOrigin(origin){
    document.querySelector('[data-return-practice]')?.remove();
    if(!origin||origin.kind!=='practice')return;
    var breadcrumb=document.querySelector('.term-content .breadcrumb');if(!breadcrumb)return;
    var link=document.createElement('a');link.className='practice-return-link';link.href=origin.returnURL;link.dataset.returnPractice='';link.textContent='← 返回练习';breadcrumb.after(link);
  }
  function applyScroll(target,url,isRestore,origin){
    if(isRestore){
      window.scrollTo({left:target.scroll?.[0]||0,top:target.scroll?.[1]||0,behavior:'instant'});
      var focus=target.focusId&&document.getElementById(target.focusId);
      if(!focus&&origin){var main=document.querySelector('body>main');focus=origin.kind==='practice'?main.querySelector('.practice-open-link'):origin.kind==='analysis'?main.querySelector('.analysis-card[data-analysis-id="'+origin.cardId+'"]'):main.querySelector('.term-card[data-id="'+origin.cardId+'"] a[data-expand-card]');}
      focusDestination(focus);return;
    }
    var hash=new URL(url).hash, found=null;
    try{found=hash&&document.getElementById(decodeURIComponent(hash.slice(1)));}catch(_){}
    if(found){for(var el=found;el;el=el.parentElement)if(el.tagName==='DETAILS')el.open=true;found.scrollIntoView({block:'start',behavior:'instant'});}
    else window.scrollTo({top:0,left:0,behavior:'instant'});
    var heading=document.querySelector('body > main h1');if(heading){heading.tabIndex=-1;focusDestination(heading);}
  }
  async function navigate(value,options) {
    options=options || {};var url=new URL(value,activeURL).href, id=++serial;
    if(currentController)currentController.abort();currentController=new AbortController();var controller=currentController;
    if(window.PsychSoftMotion)window.PsychSoftMotion.cancel();
    prefetch.cancel();clearTimeout(hoverTimer);clearTimeout(idleTimer);clearTimeout(backgroundTimer);visibilityObserver?.disconnect();
    if(url===activeURL&&options.historyMode!=='none'){status.hidden=true;scheduleAdjacent();return true;}
    var started=performance.now(), metric={url:url,started:started,cached:!!cache.get(key(url))};
    saveCurrent();var previous=activeEntry;
    status.hidden=false;status.textContent='正在准备页面…';
    try {
      if(!rootURL(url))throw Error('目标不在站点中');
      var early=prepareEarly(url);
      var page=await load(url,controller.signal);if(id!==serial)return false;
      var destination=new URL(page.url);destination.hash=new URL(url).hash || destination.hash;url=destination.href;
      var blueprint=prepared.get(key(url));metric.prepared=!!blueprint;
      if(!blueprint)blueprint=parsePage(page.html,url);
      var parsed=Object.assign({},blueprint,{main:blueprint.main.cloneNode(true)});metric.loaded=performance.now();
      if(parsed.runtimeVersion!==version){cache.clear();prepared.clear();throw Error('网站资源已更新，正在重新载入');}
      collectHints(parsed.doc);
      await Promise.all([early,runtime.preparePage(parsed.doc,url)]);if(id!==serial)return false;
      rememberPrepared(url,blueprint);
      var target=options.state ? (entries.get(options.state.entryId)||options.state) : entry(url), oldMain=document.querySelector('body > main');
      if(options.origin)target.origin=options.origin;
      var returning=previous?.origin&&sameReturn(previous.origin.returnURL,url);
      if(returning&&!options.state){target.pageState=previous.origin.state;target.scroll=previous.origin.scroll;target.focusId=previous.origin.focusId;}
      var destinationOrigin=target.origin;
      function commit(){
        if(id!==serial)return;
        runtime.unmountPage();oldMain.replaceWith(parsed.main);document.title=parsed.title;document.body.className=parsed.pageAttrs.bodyClass;document.documentElement.lang=parsed.pageAttrs.lang;
        activeURL=url;activeEntry=target;
        var historyMode=options.historyMode || 'push';
        if(historyMode!=='none')history[historyMode==='replace'?'replaceState':'pushState'](Object.assign({},history.state,{psychNav:target}),'',url);
        document.querySelectorAll('.site-head .nav-row > nav a').forEach(function(link){if(new URL(link.href).pathname===parsed.navSelection)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
        runtime.mountPage({main:parsed.main,url:url,siteRoot:siteRoot,state:target.pageState});
        showOrigin(destinationOrigin);applyScroll(target,url,options.historyMode==='none'||!!returning,returning?previous.origin:null);
        window.PsychSoftMotion?.syncIndicator(parsed.navSelection);
        metric.committed=performance.now();
        // Preparation is complete. Keep motion completion separate from actual
        // download/resource waiting; the ready animation is not a loading state.
        status.hidden=true;
      }
      var kind=returning?'collapse':(options.motion || 'cover');
      if(window.PsychSoftMotion)await window.PsychSoftMotion.transition({kind:kind,origin:options.origin || previous?.origin,direction:options.direction,commit:commit});else commit();
      if(id!==serial)return false;
      metric.finished=performance.now();metrics.push(metric);if(metrics.length>100)metrics.shift();
      status.hidden=true;scheduleAdjacent();return true;
    }catch(error){
      if(id!==serial||error.name==='AbortError')return false;
      status.textContent='页面加载失败，改用普通页面打开。';
      window.dispatchEvent(new CustomEvent('psych-navigation-error',{detail:{url:url,message:error.message}}));
      location.assign(url);return false;
    }
  }
  function candidate(event){
    var link=event.target.closest?.('a');
    if(!link){var reading=event.target.closest?.('.practice-reading');if(reading)link=reading.querySelector('a[data-expand-card]');}
    return link;
  }
  function info(link){return {href:link.href,target:link.target,download:link.hasAttribute('download')};}
  document.addEventListener('pointerdown',function(){inputMode='pointer';},true);
  document.addEventListener('keydown',function(event){
    if(event.metaKey||event.ctrlKey||event.altKey||['Shift','Control','Alt','Meta'].includes(event.key))return;
    inputMode='keyboard';
    document.querySelectorAll('[data-psych-pointer-focus]').forEach(function(el){el.removeAttribute('data-psych-pointer-focus');});
  },true);
  document.addEventListener('click',function(event){
    var link=candidate(event);if(!link)return;
    var linkURL=new URL(link.href),currentURL=new URL(activeURL);
    if(linkURL.pathname===currentURL.pathname&&linkURL.search===currentURL.search&&linkURL.hash)saveCurrent();
    if(!policy.shouldHandle(info(link),event,activeURL,siteRoot))return;
    if(event.target.closest('button,input,select,textarea')&&!link.contains(event.target))return;
    var selection=window.getSelection();if(selection&&!selection.isCollapsed&&link.closest('.practice-reading'))return;
    event.preventDefault();
    var origin=null, motion='cover', card=link.closest('.term-card,.practice-reading,.analysis-card');
    if(card&&link.hasAttribute('data-expand-card')){
      saveCurrent();var bounds=card.getBoundingClientRect();
      origin={kind:card.matches('.practice-reading')?'practice':card.matches('.analysis-card')?'analysis':'term',returnURL:activeURL,
        cardId:card.dataset.id || card.dataset.analysisId || null,rect:{left:bounds.left,top:bounds.top,width:bounds.width,height:bounds.height},state:activeEntry.pageState,scroll:activeEntry.scroll,focusId:activeEntry.focusId};motion='expand';
    }else if(link.matches('[data-collapse-term],[data-collapse-analysis],[data-return-practice]'))motion='collapse';
    else if(link.matches('.sequence-link'))motion='slide';
    // The active terms tab on index preserves its current topic.
    if(link.closest('.site-head nav')&&new URL(link.href).pathname===new URL(activeURL).pathname)return;
    navigate(link.href,{origin:origin,motion:motion,direction:link.dataset.direction});
  },true);
  document.addEventListener('pointerover',function(event){var link=candidate(event);clearTimeout(hoverTimer);if(link&&policy.shouldHandle(info(link),{button:0},activeURL,siteRoot))hoverTimer=setTimeout(function(){prefetch.enqueue(key(link.href),20);},120);});
  document.addEventListener('pointerout',function(event){if(!event.target.contains?.(event.relatedTarget))clearTimeout(hoverTimer);});
  document.addEventListener('focusin',function(event){var link=candidate(event);if(link&&policy.shouldHandle(info(link),{button:0},activeURL,siteRoot))prefetch.enqueue(key(link.href),20);});
  window.addEventListener('popstate',function(event){if(policy.sameLibraryDocument?.(activeURL,location.href,siteRoot))return;navigate(location.href,{historyMode:'none',state:event.state?.psychNav || entry(location.href),motion:'cover'});});
  window.addEventListener('hashchange',function(){
    if(!activeEntry)return;saveCurrent();var previous=activeEntry;
    activeURL=location.href;activeEntry=Object.assign(entry(activeURL),{pageState:previous.pageState,origin:previous.origin,scroll:[scrollX,scrollY]});
    history.replaceState(Object.assign({},history.state,{psychNav:activeEntry}),'',activeURL);
  });
  window.addEventListener('pagehide',saveCurrent);
  try{new PerformanceObserver(function(list){list.getEntries().forEach(function(item){longTasks.push({start:item.startTime,duration:item.duration});if(longTasks.length>100)longTasks.shift();});}).observe({type:'longtask',buffered:true});}catch(_){}
  var ready=new Promise(function(resolve){document.addEventListener('DOMContentLoaded',function(){
    normalizeTreeURLs(document.documentElement,location.href);document.querySelector('.header-search').dataset.root=siteRoot;
    activeEntry=history.state?.psychNav || entry(location.href);activeEntry.url=location.href;
    showOrigin(activeEntry.origin);
    history.replaceState(Object.assign({},history.state,{psychNav:activeEntry}),'',location.href);history.scrollRestoration='manual';
    // The initial HTML did not pass through load(). Keep it for the first back
    // navigation too, without issuing another network request.
    cache.set(key(activeURL),{html:'<!doctype html>'+document.documentElement.outerHTML,url:activeURL});
    collectHints(document);scheduleAdjacent();resolve();
  },{once:true});});
  window.PsychSoftNavigation={navigate:navigate,parsePage:parsePage,normalizeTreeURLs:normalizeTreeURLs,ready:ready,topicHistory:topicHistory,saveCurrent:saveCurrent,metrics:metrics,longTasks:longTasks,siteRoot:siteRoot,cache:cache};
})(window);
