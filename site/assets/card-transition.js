(function () {
  'use strict';

  var key = 'psychstats.card-transition.v1';
  var practiceKey = 'psychstats.practice-return.v1';
  var analysisKey = 'psychstats.analysis-origin.v1';
  var motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var leaving = false, scene = null, pending = null, cancelArrival = null, flyingTitle = null;
  var root = document.documentElement;
  var navIndicator = null, navAnimation = null, cancelTopic = null;

  function emerge(element, distance) {
    // Keep the previous opaque view underneath; only the incoming layer blends in.
    var sliding = Boolean(distance);
    return element.animate([
      {opacity:0,transform:sliding ? 'translateX('+distance+'px) scale(0.995)' : 'scale(0.995)'},
      {opacity:1,transform:sliding ? 'translateX(0px) scale(1)' : 'scale(1)'}
    ],{duration:sliding ? 420 : 200,easing:'cubic-bezier(.22,1,.36,1)',fill:'both'});
  }

  function initNav(source) {
    var nav = document.querySelector('.site-head .nav-row > nav');
    var selected = nav && nav.querySelector('a[aria-current="page"]');
    if (!selected) return;
    if (!navIndicator) {
      navIndicator = document.createElement('span');
      navIndicator.className = 'nav-motion-indicator';
      navIndicator.setAttribute('aria-hidden','true');
      nav.appendChild(navIndicator);
      nav.classList.add('nav-motion-ready');
    }
    if (navAnimation) navAnimation.cancel();
    var box = rect(selected), origin = rect(nav);
    Object.assign(navIndicator.style,{left:(box.left-origin.left+nav.scrollLeft)+'px',top:(box.top-origin.top+nav.scrollTop)+'px',width:box.width+'px',height:box.height+'px'});
    if (source && !motion.matches) {
      navAnimation = navIndicator.animate([
        {transform:'translate('+(source.left-box.left)+'px,'+(source.top-box.top)+'px) scale('+(source.width/box.width)+','+(source.height/box.height)+')'},
        {transform:'translate(0,0) scale(1,1)'}
      ],{duration:240,easing:'cubic-bezier(.22,1,.36,1)'});
    }
  }

  function stopTopic() { if (cancelTopic) cancelTopic(); }
  window.PsychNavigationMotion = {
    syncNav:initNav,
    cancelTopic:function(){if(window.PsychSoftMotion&&/^https?:$/.test(location.protocol))window.PsychSoftMotion.cancel();else stopTopic();},
    coverTopic:function (elements, update) {
      if(window.PsychSoftMotion&&/^https?:$/.test(location.protocol)){window.PsychSoftMotion.transition({kind:'cover',elements:elements,commit:update});return;}
      stopTopic();
      if (cancelArrival) cancelArrival();
      if (motion.matches || !Element.prototype.animate) { update(); return; }
      var animations = [], cancelled = false, layers = [], updated = false, timer = null;
      function clean() {
        if (cancelled) return;
        cancelled = true;
        window.clearTimeout(timer);
        animations.forEach(function(a){a.cancel();});
        layers.forEach(function(layer){layer.element.remove();});
        cancelTopic = null;
        motion.removeEventListener('change', reduce);
      }
      function reduce() { if (cancelled) return; clean(); if (!updated) { updated=true; update(); } }
      cancelTopic = clean;
      motion.addEventListener('change',reduce);
      try {
        var main = document.querySelector('body > main'), area = viewport();
        area.top = Math.max(area.top,rect(elements[0]).top);
        area.height = Math.max(1,innerHeight-area.top);
        var old = snapshotScene(snapshot(main,null),'topic-cover-scene');
        layers.push(old);
        old.element.style.visibility='hidden';
        old.element.style.clipPath=polygon(area,{left:0,top:0});
        old.ready.then(function(){
          if (cancelled) return;
          old.element.style.visibility='visible';
          updated=true; update();
          var incoming = snapshotScene(snapshot(main,null),'topic-cover-scene topic-cover-next');
          layers.push(incoming);
          incoming.element.style.visibility='hidden';
          incoming.element.style.clipPath=polygon(area,{left:0,top:0});
          return incoming.ready.then(function(){
            if (cancelled) return;
            incoming.element.style.visibility='visible';
            animations.push(emerge(incoming.element));
            return animations[0].finished.then(clean,clean);
          });
        }).catch(function(){ if (cancelled) return; clean(); if (!updated) { updated=true; update(); } });
        timer=window.setTimeout(reduce,1800);
      } catch (_) { clean(); if (!updated) { updated=true; update(); } }
    }
  };

  function rect(element) {
    var box = element.getBoundingClientRect();
    return {left: box.left, top: box.top, width: box.width, height: box.height};
  }

  function discard() {
    if (scene) { scene.remove(); scene = null; }
    if (flyingTitle) { flyingTitle.remove(); flyingTitle = null; }
    root.classList.remove('term-transition-pending', 'term-transition-active', 'term-transition-collapsing', 'navigation-motion-active', 'navigation-slide-active', 'navigation-cover-active');
    root.style.removeProperty('--navigation-main-top');
  }

  function read(name) { try { return JSON.parse(sessionStorage.getItem(name) || 'null'); } catch (_) { return null; } }
  function write(name, value) { try { sessionStorage.setItem(name, JSON.stringify(value)); } catch (_) {} }
  function remove(name) { try { sessionStorage.removeItem(name); } catch (_) {} }
  function samePage(first, second) {
    try {
      var a = new URL(first, location.href), b = new URL(second, location.href);
      return a.origin === b.origin && a.pathname === b.pathname && a.search === b.search;
    } catch (_) { return false; }
  }
  function viewport() {
    var header = document.querySelector('.site-head');
    var top = header ? header.getBoundingClientRect().bottom : 0;
    return {left:0, top:top, width:root.clientWidth, height:Math.max(1, innerHeight-top)};
  }
  function visible(box) {
    var area = viewport(), top = Math.max(area.top, box.top);
    return {left:box.left, top:top, width:box.width,
            height:Math.max(1, Math.min(innerHeight, box.top+box.height)-top)};
  }
  function polygon(box, offset) {
    var left = box.left-offset.left, top = box.top-offset.top;
    return 'polygon('+left+'px '+top+'px,'+(left+box.width)+'px '+top+'px,'+
      (left+box.width)+'px '+(top+box.height)+'px,'+left+'px '+(top+box.height)+'px)';
  }
  function practiceReturn() {
    var saved = read(practiceKey), article = document.querySelector('body > main .term-content');
    var existing = document.querySelector('[data-return-practice]');
    if (!saved || !samePage(saved.href, location.href) || !article || Date.now()-saved.time > 1800000) {
      if (existing) existing.remove();
      if (saved) remove(practiceKey);
      return;
    }
    if (existing) return;
    var link = document.createElement('a');
    link.className = 'practice-return-link';
    link.href = saved.practiceUrl;
    link.setAttribute('data-return-practice', '');
    link.textContent = '← 返回练习';
    article.querySelector('.breadcrumb').after(link);
  }

  // Snapshots contain generated page content only, never scripts or live controls.
  function snapshot(main, card) {
    var copy = main.cloneNode(true);
    var originals = [main].concat(Array.from(main.querySelectorAll('*')));
    var copies = [copy].concat(Array.from(copy.querySelectorAll('*')));
    originals.forEach(function (original, index) {
      var clone = copies[index];
      if (original.id) {
        // Preserve layout rules using IDs (notably #practice-app) without duplicate IDs.
        var style = getComputedStyle(original);
        ['display', 'width', 'max-width', 'min-width', 'padding', 'margin'].forEach(function (property) {
          clone.style.setProperty(property, style.getPropertyValue(property));
        });
      }
      clone.removeAttribute('id');
      Array.from(clone.attributes).forEach(function (attribute) {
        if ((attribute.name.indexOf('data-') === 0 && attribute.name !== 'data-topic') ||
            attribute.name.indexOf('on') === 0 || attribute.name === 'autofocus') {
          clone.removeAttribute(attribute.name);
        }
      });
      if (original === card) { clone.setAttribute('data-transition-origin', ''); }
      if (original.matches('.term-card, .analysis-card') && !original.hidden) {
        // Clones cannot retain :hover/:focus-within. Freeze the real painted edge
        // rather than briefly reverting to the unfocused stylesheet default.
        var cardStyle=getComputedStyle(original);
        ['border-color','border-width','border-style','border-radius','box-shadow','background-color','transform'].forEach(function(property){
          clone.style.setProperty(property,cardStyle.getPropertyValue(property));
        });
        clone.style.transition='none';
      }
      if (original.tagName === 'IMG') { clone.src = original.src; }
      if (original.tagName === 'INPUT') { clone.removeAttribute('value'); }
    });
    copy.querySelectorAll('[hidden],script,iframe,object,embed').forEach(function (element) { element.remove(); });
    copy.style.position = 'absolute';
    copy.style.top = main.getBoundingClientRect().top + 'px';
    copy.style.left = '0';
    copy.style.width = '100%';
    copy.style.margin = '0';
    copy.setAttribute('inert', '');
    return copy.outerHTML;
  }

  function snapshotScene(html, extraClass, styles) {
    var element = make('term-transition-scene '+(extraClass||''),root);
    element.setAttribute('aria-hidden','true'); element.setAttribute('inert','');
    make('term-transition-backdrop',element);
    var host=make('term-transition-snapshot',element), shadow=host.attachShadow({mode:'open'});
    var ready=Promise.all((styles || Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(function(s){return s.href;})).map(function(href){
      return new Promise(function(resolve,reject){
        var stylesheet=document.createElement('link');
        stylesheet.rel='stylesheet'; stylesheet.href=href;
        stylesheet.onload=resolve; stylesheet.onerror=reject; shadow.appendChild(stylesheet);
      });
    }));
    var content=document.createElement('div');content.innerHTML=html;shadow.appendChild(content);
    return {element:element,ready:ready};
  }

  function remember(card, link) {
    if (motion.matches || !Element.prototype.animate) { return; }
    var heading = card.querySelector('h2,h3'), main = document.querySelector('body > main');
    if (!heading || !main) { return; }
    var box = rect(card), titleBox = rect(heading), header = document.querySelector('.site-head');
    var headerBottom = header ? header.getBoundingClientRect().bottom : 0;
    var top = Math.max(headerBottom, box.top), bottom = Math.min(innerHeight, box.top + box.height);
    if (bottom <= top || box.width <= 0) { return; }
    var html = snapshot(main, card);
    if (html.length > 500000) { return; }
    var record = {
      href: link.href, time: Date.now(), width: innerWidth, height: innerHeight,
      html: html, box: box, title: heading.textContent, titleBox: titleBox,
      titleSize: parseFloat(getComputedStyle(heading).fontSize),
      panel: {left: box.left, top: top, width: box.width, height: bottom - top},
      background: getComputedStyle(card).backgroundColor
    };
    record.styles = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(function (style) { return style.href; });
    record.direction = 'expand';
    record.kind = card.matches('.analysis-card') ? 'analysis' : 'term';
    try { sessionStorage.setItem(key, JSON.stringify(record)); } catch (_) { /* Native navigation remains available. */ }
  }

  function rememberReturn(link, article, context) {
    if (motion.matches || !Element.prototype.animate) return;
    var main = document.querySelector('body > main'), heading = article.querySelector('header h1,h1');
    var html = snapshot(main, article);
    if (html.length > 500000) return;
    write(key, {
      direction:'collapse', destination:article.dataset.analysisCase ? 'analysis' : context ? 'practice' : 'topic', termId:article.dataset.termId,
      analysisId:article.dataset.analysisCase, filter:context && context.filter,
      href:link.href, time:Date.now(), width:innerWidth, height:innerHeight, html:html,
      panel:viewport(), title:heading.textContent, titleBox:rect(heading),
      titleSize:parseFloat(getComputedStyle(heading).fontSize),
      returnScroll:context ? context.scrollY : null,
      styles:Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(function (style) { return style.href; })
    });
  }

  function rememberNavigation(link, direction) {
    var main = document.querySelector('body > main');
    if (!main) return false;
    var current = document.querySelector('.site-head nav a[aria-current="page"]');
    var html = snapshot(main, null);
    if (html.length > 500000) return false;
    try {
      sessionStorage.setItem(key,JSON.stringify({direction:direction,href:link.href,time:Date.now(),
        width:innerWidth,height:innerHeight,html:html,navBox:direction==='cover'&&current?rect(current):null,
        styles:Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(function(s){return s.href;})}));
      return true;
    } catch (_) { return false; }
  }

  function animateNavigation() {
    var main = document.querySelector('body > main'), animations = [], finished = false, incomingScene = null;
    var previousBackground=main && main.style.backgroundColor, previousHeight=main && main.style.minHeight, previousOrigin=main && main.style.transformOrigin;
    function finish() {
      if (finished) return;
      finished = true;
      animations.forEach(function(a){a.cancel();});
      if (incomingScene) incomingScene.element.remove();
      main.style.backgroundColor=previousBackground; main.style.minHeight=previousHeight;
      main.style.transformOrigin=previousOrigin;
      cancelArrival = null;
      discard();
      motion.removeEventListener('change',finish);
    }
    if (!main || motion.matches) { discard(); return; }
    cancelArrival = finish;
    try {
      window.scrollTo({top:0,behavior:'instant'});
      initNav(pending.navBox);
      var distance = pending.direction==='cover' ? 0 :
        (pending.direction==='previous' ? -1 : 1) * (root.clientWidth<600 ? 24 : 32);
      var area=polygon(viewport(),{left:0,top:0});
      scene.style.clipPath=area;
      incomingScene=snapshotScene(snapshot(main,null),'navigation-cover-next');
      incomingScene.element.style.visibility='hidden';
      incomingScene.element.style.clipPath=area;
      root.classList.add('navigation-cover-active');
      motion.addEventListener('change',finish);
      incomingScene.ready.then(function(){
        if (finished) return;
        incomingScene.element.style.visibility='visible';
        animations.push(emerge(incomingScene.element,distance));
        root.classList.remove('term-transition-pending');
        root.classList.add('term-transition-active','navigation-motion-active');
        return animations[0].finished.then(finish,finish);
      }).catch(finish);
    } catch (_) { finish(); }
  }

  function make(className, parent) {
    var element = document.createElement('div');
    element.className = className;
    parent.appendChild(element);
    return element;
  }

  function animateArrival() {
    if (['cover','next','previous'].indexOf(pending.direction)>=0) { animateNavigation(); return; }
    var main = document.querySelector('body > main');
    var collapse = pending.direction === 'collapse';
    if (collapse && pending.destination === 'analysis') restoreAnalysisOrigin();
    var target = collapse ? (pending.destination === 'analysis' ? document.querySelector('.analysis-card[data-analysis-id="'+pending.analysisId+'"]') : pending.destination === 'practice' ? document.querySelector('.practice-reading') :
      document.querySelector('.term-card[data-id="'+pending.termId+'"]')) : document.querySelector('.term-content');
    var heading = target && target.querySelector(collapse ? 'h2,h3' : 'header h1,h1');
    if (!scene || !heading || !main || motion.matches) { discard(); return; }
    var animations = [], visibility = heading.style.visibility, finished = false;
    function finish() {
      if (finished) { return; }
      finished = true;
      cancelArrival = null;
      animations.forEach(function (animation) { animation.cancel(); });
      heading.style.visibility = visibility;
      if (collapse && pending.destination === 'analysis') remove(analysisKey);
      discard();
      motion.removeEventListener('change', finish);
    }
    cancelArrival = finish;
    try {
      if (collapse && pending.destination === 'topic') {
        if (target.hidden) { discard(); return; }
        target.scrollIntoView({block:'center', behavior:'instant'});
      } else {
        window.scrollTo({top:collapse && Number.isFinite(pending.returnScroll) ? pending.returnScroll : 0, behavior:'instant'});
      }
      var destination = collapse ? visible(rect(target)) : viewport(), titleBox = rect(heading);
      var source = pending.panel;
      var panel = make('term-transition-panel', scene);
      Object.assign(panel.style, {
        left: destination.left + 'px', top: destination.top + 'px',
        width: destination.width + 'px', height: destination.height + 'px'
      });
      var snapshotHost = scene.querySelector('.term-transition-snapshot');
      var origin = snapshotHost.shadowRoot.querySelector('[data-transition-origin]');
      if (origin && !collapse) {
        var floating = origin.cloneNode(true);
        floating.querySelector('h2,h3').style.visibility = 'hidden';
        origin.style.visibility = 'hidden';
        Object.assign(floating.style, {
          position: 'absolute', left: pending.box.left + 'px', top: pending.box.top + 'px',
          width: pending.box.width + 'px', height: pending.box.height + 'px', margin: '0',
          transform: 'none', background: 'transparent', borderColor: 'transparent', boxShadow: 'none'
        });
        scene.appendChild(floating);
        animations.push(floating.animate([{opacity: 1}, {opacity: 0}], {duration: 120, fill: 'both'}));
      }
      var title = make('term-transition-title', root);
      flyingTitle = title;
      title.textContent = heading.textContent;
      var style = getComputedStyle(heading);
      Object.assign(title.style, {
        left: titleBox.left + 'px', top: titleBox.top + 'px', width: titleBox.width + 'px',
        font: style.font, letterSpacing: style.letterSpacing
      });
      heading.style.visibility = 'hidden';
      var scale = pending.titleSize / parseFloat(style.fontSize);
      var sourceTop = Math.max(pending.titleBox.top, source.top + 8);
      var easing = collapse ? 'cubic-bezier(.4, 0, .2, 1)' : 'cubic-bezier(.22, 1, .36, 1)';
      animations.push(panel.animate([
        {transform: 'translate(' + (source.left - destination.left) + 'px,' + (source.top - destination.top) + 'px) scale(' + source.width / destination.width + ',' + source.height / destination.height + ')', borderRadius:collapse ? '0px' : '11px', backgroundColor:pending.background || '#fff'},
        {transform: 'translate(0,0) scale(1,1)', borderRadius:collapse ? '11px' : '0px', backgroundColor:'#fff'}
      ], {duration: 400, easing: easing, fill: 'both'}));
      animations.push(panel.animate([{opacity:1}, {opacity:0}], {duration:collapse ? 160 : 180, delay:collapse ? 240 : 120, fill:'both'}));
      animations.push(title.animate([
        {transform: 'translate(' + (pending.titleBox.left - titleBox.left) + 'px,' + (sourceTop - titleBox.top) + 'px) scale(' + scale + ')'},
        {transform: 'translate(0,0) scale(1)'}
      ], {duration: 400, easing: easing, fill: 'both'}));
      animations.push(snapshotHost.animate([{opacity:1}, {opacity:0}], {duration:220, delay:collapse ? 40 : 0, fill:'both'}));
      if (collapse) {
        animations.push(scene.animate([{clipPath:polygon(source,{left:0,top:0})}, {clipPath:polygon(destination,{left:0,top:0})}], {duration:400,easing:easing,fill:'both'}));
        animations.push(scene.querySelector('.term-transition-backdrop').animate([{opacity:1},{opacity:0}],{duration:160,delay:240,fill:'both'}));
        root.classList.add('term-transition-collapsing');
      } else {
        // Reveal the real page within the growing surface, not inside an article-width popup.
        var offset = rect(main);
        animations.push(main.animate([{clipPath:polygon(source,offset)}, {clipPath:polygon(destination,offset)}], {duration:400,easing:easing,fill:'both'}));
        animations.push(main.animate([{opacity:0},{opacity:1}],{duration:220,delay:70,fill:'both'}));
        animations.push(scene.querySelector('.term-transition-backdrop').animate([{opacity:1},{opacity:0}],{duration:180,delay:180,fill:'both'}));
        target.querySelectorAll('header > p, header > .breadcrumb, header > .favorite-button, header > .practice-return-link').forEach(function (detail) {
          animations.push(detail.animate([{opacity:0},{opacity:1}],{duration:120,delay:280,fill:'both'}));
        });
      }
      root.classList.remove('term-transition-pending');
      root.classList.add('term-transition-active');
      motion.addEventListener('change', finish);
      Promise.all(animations.map(function (animation) { return animation.finished; })).then(finish, finish);
    } catch (_) { finish(); }
  }

  // Read before the destination's first paint; consume once, never replay on Back.
  try {
    var saved = sessionStorage.getItem(key);
    if (saved) {
      var record = JSON.parse(saved);
      sessionStorage.removeItem(key);
      var age = Date.now() - record.time;
      if (!/^https?:$/.test(location.protocol) && record.href === location.href && age >= 0 && age < 6000 &&
          record.width === innerWidth && record.height === innerHeight &&
          !motion.matches && Element.prototype.animate &&
          (record.direction === 'cover' ? /\/(index|paths|practice|datasets|symbols|analysis|sources)\.html$/.test(location.pathname) || /\/analyses\/[a-z0-9-]+\.html$/.test(location.pathname) : record.direction === 'collapse' ? /\/(index|practice|analysis)\.html$/.test(location.pathname) : /\/(terms|analyses)\/[a-z0-9-]+\.html$/.test(location.pathname))) {
        pending = record;
        root.classList.add('term-transition-pending');
        var mounted=snapshotScene(record.html,'',record.styles);
        scene=mounted.element;
        var stylesReady=mounted.ready;
        document.addEventListener('DOMContentLoaded', function () { stylesReady.then(animateArrival, discard); }, {once:true});
        // Parsing failures or interrupted loads must never leave the page hidden.
        window.setTimeout(function () { if (cancelArrival) { cancelArrival(); } else { discard(); } }, 1800);
      }
    }
  } catch (_) { discard(); }

  document.addEventListener('click', function (event) {
    if (window.PsychSoftNavigation || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) { return; }
    var target = event.target.closest && event.target.closest('a,button,input,select,textarea,[contenteditable]');
    var article = document.querySelector('body > main .term-content');
    if (target && target.matches('a') && target.target !== '_blank' && !target.hasAttribute('download')) {
      var context = read(practiceKey);
      if (article && (target.hasAttribute('data-collapse-term') || target.hasAttribute('data-return-practice') || target.hasAttribute('data-collapse-analysis') || article.dataset.analysisCase && samePage(target.href, new URL('../analysis.html',location.href).href))) {
        if (target.hasAttribute('data-return-practice') && context) {
          write('psychstats.practice-resume.v1',{state:context.state,scrollY:context.scrollY,time:Date.now()});
        }
        if (leaving) { event.preventDefault(); return; }
        leaving = true;
        rememberReturn(target, article, target.hasAttribute('data-collapse-analysis') || article.dataset.analysisCase ? read(analysisKey) : target.hasAttribute('data-return-practice') ? context : null);
        // The return branch owns this click, including a top-navigation return.
        return;
      }
      if (article && article.dataset.analysisCase && !samePage(target.href, location.href)) remove(analysisKey);
      if (!samePage(target.href, location.href)) {
        remove(practiceKey);
        var pointer = document.querySelector('[data-return-practice]');
        if (pointer) pointer.remove();
      }
      var navigation = target.closest('.site-head nav'), neighbor = target.matches('.sequence-link');
      if (navigation || neighbor) {
        if (samePage(target.href, location.href) || (navigation && new URL(target.href).pathname === location.pathname)) { event.preventDefault(); return; }
        if (leaving) { event.preventDefault(); return; }
        if (!motion.matches && Element.prototype.animate && rememberNavigation(target,neighbor?target.dataset.direction:'cover')) {
          event.preventDefault(); leaving = true;
          if (cancelArrival) cancelArrival();
          stopTopic();
          location.assign(target.href);
        }
        return;
      }
    }
    var link = target && target.matches('a[data-expand-card]') ? target : null;
    var reading = event.target.closest && event.target.closest('.practice-reading[data-loaded="true"]');
    if (!link && reading && !target) { link = reading.querySelector('a[data-expand-card]'); }
    if (!link || link.target === '_blank' || link.hasAttribute('download')) { return; }
    var card = link.closest('.term-card, .practice-reading, .analysis-card');
    if (!card) { return; }
    var selection = window.getSelection();
    if (selection && !selection.isCollapsed && card.contains(selection.anchorNode)) { event.preventDefault(); return; }
    if (leaving) { event.preventDefault(); return; }
    leaving = true;
    if (card.matches('.analysis-card')) {
      write(analysisKey,{href:link.href,indexUrl:location.href,caseId:card.dataset.analysisId,
                        filter:document.querySelector('#analysis-filter')?.value || '',scrollY:scrollY,time:Date.now()});
    }
    if (reading && window.PsychPractice && window.PsychPractice.captureState) {
      write(practiceKey,{href:link.href,practiceUrl:location.href,time:Date.now(),
                        state:window.PsychPractice.captureState(),scrollY:scrollY});
    }
    remember(card, link);
    if (target !== link) { event.preventDefault(); location.assign(link.href); }
  });
  document.addEventListener('DOMContentLoaded', practiceReturn, {once:true});
  function restoreAnalysisOrigin() {
    var context = read(analysisKey);
    if (!context || !samePage(context.indexUrl,location.href) || Date.now()-context.time>1800000) return;
    var filter=document.querySelector('#analysis-filter');
    if (filter) {filter.value=context.filter || '';filter.dispatchEvent(new Event('input',{bubbles:true}));}
    window.scrollTo({top:context.scrollY || 0,behavior:'instant'});
    if (motion.matches) remove(analysisKey);
  }
  document.addEventListener('DOMContentLoaded', restoreAnalysisOrigin, {once:true});
  document.addEventListener('DOMContentLoaded',function(){if (!navIndicator) initNav();},{once:true});
  window.addEventListener('resize',function(){
    // Mobile's initial viewport resize can occur just after the arrival starts.
    // Keep the moving indicator alive, then align it to the final layout.
    if (navAnimation && navAnimation.playState==='running') navAnimation.finished.then(function(){initNav();},function(){});
    else initNav();
  });
  motion.addEventListener('change',function(){initNav();});
  window.addEventListener('pageshow', function (event) {
    leaving = false;
    if(window.PsychSoftNavigation){initNav();return;}
    practiceReturn();
    // Ordinary pageshow follows DOMContentLoaded: do not remove an in-flight arrival.
    if (event.persisted) {
      if (cancelArrival) {cancelArrival();} else {discard();}
      document.querySelector('body > main').getAnimations().forEach(function(a){a.cancel();});initNav();
      restoreAnalysisOrigin();
      var back=read(key);
      if (back && back.direction==='collapse' && back.destination==='analysis' && samePage(back.href,location.href) && Date.now()-back.time<6000 && !motion.matches) {
        remove(key);pending=back;root.classList.add('term-transition-pending');
        var mounted=snapshotScene(back.html,'',back.styles);scene=mounted.element;
        mounted.ready.then(animateArrival,discard);
      }
    }
  });
  window.addEventListener('pagehide', function () {
    if(window.PsychSoftNavigation)return;
    var context=read(analysisKey),article=document.querySelector('[data-analysis-case]');
    if (!leaving && context && article && samePage(context.href,location.href)) rememberReturn({href:context.indexUrl},article,context);
    stopTopic();if (cancelArrival) {cancelArrival();}
  });
}());
