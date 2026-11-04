(function (root) {
  'use strict';
  function resolveURL(value, sourceURL) { return new URL(value, sourceURL).href; }
  function shouldHandle(link, click, currentURL, siteRoot) {
    if (!link || !click || click.defaultPrevented || click.button !== 0 || click.ctrlKey || click.metaKey || click.shiftKey || click.altKey || link.download || (link.target && link.target !== '_self')) return false;
    try {
      var current = new URL(currentURL), url = new URL(link.href,current), base = new URL(siteRoot);
      if (!/^https?:$/.test(current.protocol) || url.origin !== base.origin || !url.pathname.startsWith(base.pathname) || !/\.html$/.test(url.pathname)) return false;
      var path = url.pathname.slice(base.pathname.length);
      if (!/^(?:(?:terms|analyses|topics)\/[a-z0-9-]+|library\/index|index|paths|practice|datasets|symbols|analysis|sources)\.html$/.test(path)) return false;
      if (url.pathname === current.pathname && url.search === current.search && url.hash) return false;
      if (path === 'index.html' && current.pathname === url.pathname && url.searchParams.has('topic')) return false;
      return true;
    } catch (_) { return false; }
  }
  function createCache(limit) {
    var entries = new Map(); limit = limit || 12;
    return {get:function(key){if(!entries.has(key))return;var value=entries.get(key);entries.delete(key);entries.set(key,value);return value;},
      set:function(key,value){entries.delete(key);entries.set(key,value);while(entries.size>limit)entries.delete(entries.keys().next().value);},
      clear:function(){entries.clear();},get size(){return entries.size;}};
  }
  function createPrefetchQueue(options) {
    var queue=[], active=0, known=new Set(), epoch=0;
    function pump(){
      while(active<(options.maxConcurrent || 2) && queue.length){
        var job=queue.shift();
        if (job.epoch!==epoch || !options.allowed()){known.delete(job.url);continue;}
        active++;
        Promise.resolve().then(function(job){return options.load(job.url);}.bind(null,job))
          .catch(function(){}).finally(function(job){known.delete(job.url);active--;pump();}.bind(null,job));
      }
    }
    return {enqueue:function(url,priority){
      if(!options.allowed())return;priority=priority||0;
      var pending=queue.find(function(job){return job.url===url;});
      if(pending){pending.priority=Math.max(pending.priority,priority);queue.sort(function(a,b){return b.priority-a.priority;});return;}
      if(known.has(url))return;
      known.add(url);queue.push({url:url,epoch:epoch,priority:priority});queue.sort(function(a,b){return b.priority-a.priority;});
      while(queue.length>(options.maxPending||12))known.delete(queue.pop().url);
      pump();},
      cancel:function(){epoch++;queue.forEach(function(job){known.delete(job.url);});queue=[];}};
  }
  function sameLibraryDocument(from,to,siteRoot){try{var a=new URL(from),b=new URL(to),root=new URL(siteRoot);return a.origin===root.origin&&b.origin===root.origin&&a.pathname===root.pathname+'library/index.html'&&b.pathname===a.pathname&&b.search===a.search;}catch(_){return false;}}
  var api={resolveURL:resolveURL,shouldHandle:shouldHandle,createCache:createCache,createPrefetchQueue:createPrefetchQueue,sameLibraryDocument:sameLibraryDocument};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root)root.PsychNavigationPolicy=api;
})(typeof window==='undefined'?null:window);
