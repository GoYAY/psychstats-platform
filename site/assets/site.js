(function () {
  'use strict';

  function mount(ctx) {
  function on(target, type, listener, options) { if(ctx)ctx.on(target,type,listener,options);else target.addEventListener(type,listener,options); }
  function cleanup(fn) { if(ctx)ctx.deferCleanup(fn); }
  function alive() { return !ctx || ctx.alive(); }
  function later(fn,ms){var handle=setTimeout(function(){if(alive())fn();},ms);cleanup(function(){clearTimeout(handle);});return handle;}

  function wireTabs() {
    document.querySelectorAll('.r-practice').forEach(function (section) {
      section.querySelectorAll('[data-tab]').forEach(function (button) {
        button.addEventListener('click', function () {
          var selected = button.getAttribute('data-tab');
          section.querySelectorAll('[data-panel]').forEach(function (panel) {
            panel.hidden = panel.getAttribute('data-panel') !== selected;
          });
        });
      });
    });
  }

  function selectText(element) {
    var selection = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(element); selection.removeAllRanges(); selection.addRange(range);
  }

  function wireCopy() {
    document.querySelectorAll('[data-copy]').forEach(function (button) {
      button.addEventListener('click', function () {
        var source = document.querySelector(button.getAttribute('data-copy'));
        if (!source) { return; }
        var original = button.textContent;
        var success = function () {
          if (!alive()) return;
          button.textContent = '已复制 ✓';
          later(function () { button.textContent = original; }, 1500);
        };
        var failure = function () {
          if (!alive()) return;
          selectText(source); button.textContent = '复制失败，请手动选择';
          later(function () { button.textContent = original; }, 2500);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(source.textContent || '').then(success, failure);
        } else {
          var area = document.createElement('textarea');
          area.value = source.textContent || ''; document.body.appendChild(area); area.select();
          try { if (document.execCommand('copy')) { success(); } else { failure(); } }
          catch (error) { failure(); }
          document.body.removeChild(area);
        }
      });
    });
  }

  function wireTermQuizzes() {
    document.querySelectorAll('.quiz[data-answer]').forEach(function (quiz) {
      var buttons = Array.from(quiz.querySelectorAll('[data-idx]'));
      var status = quiz.querySelector('.quiz-result');
      buttons.forEach(function (button) {
        button.addEventListener('click', function () {
          var index = Number(button.getAttribute('data-idx'));
          var answer = Number(quiz.getAttribute('data-answer'));
          var feedback = window.PsychPractice.gradeOption(answer, index, button.nextElementSibling.textContent);
          buttons.forEach(function (choice) {
            choice.classList.remove('correct', 'wrong');
            choice.setAttribute('aria-pressed', 'false');
            choice.nextElementSibling.hidden = true;
          });
          button.classList.add(feedback.correct ? 'correct' : 'wrong');
          button.setAttribute('aria-pressed', 'true');
          button.nextElementSibling.hidden = false;
          status.textContent = feedback.correct ? '回答正确。' : '回答错误。正确选项是：' + buttons[answer].textContent + '。';
        });
      });
    });
  }

  function wireSearch() {
    var cards = Array.from(document.querySelectorAll('[data-term]'));
    if (!cards.length || !window.PsychSearch) { return; }
    var controls = {
      topic: document.getElementById('topic-filter'), level: document.getElementById('level-filter'),
      type: document.getElementById('type-filter'), has_r: document.getElementById('r-filter'), origin: document.getElementById('favorite-topic-filter')
    };
    var input = document.getElementById('q');
    function populate(terms) {
      if (!alive()) return;
      var visibleIds = new Set(cards.map(function (card) { return card.getAttribute('data-id'); }));
      terms = terms.filter(function (term) { return visibleIds.has(term.id); });
      var intro = document.getElementById('topic-intro');
      var topics = (window.PsychSiteData && window.PsychSiteData.topics || []).concat([{id:'favorites',zh:'收藏',description:'把需要反复查阅的概念与方法留在这里，沿着自己的研究需求继续学习。',basis:'收藏仅保存在当前浏览器；清除网站数据会移除收藏，不跨设备同步。'}]);
      var activeTopic = intro ? intro.getAttribute('data-topic') : '';
      var defaultTopic = activeTopic;
      var topicStates = {};
      var activeControls = Object.values(controls).filter(Boolean);
      if (window.PsychFilterMenu) {
        activeControls.forEach(function (control) { var menu=window.PsychFilterMenu.enhance(control); cleanup(menu && menu.dispose); });
      }
      function update() {
        var favoritesView = activeTopic === 'favorites';
        var candidates = favoritesView ? terms.filter(function (term) { return window.PsychFavorites && window.PsychFavorites.has(term.id); }) : terms;
        var filters = { topic: favoritesView ? (controls.origin ? controls.origin.value : '') : (activeTopic || (controls.topic ? controls.topic.value : '')), level: controls.level ? controls.level.value : '', type: controls.type ? controls.type.value : '', has_r: controls.has_r ? controls.has_r.value : '' };
        // Header search is independent of topic/difficulty browsing filters.
        var hits = new Set(window.PsychSearch.filterTerms('', filters, candidates).map(function (term) { return term.id; }));
        cards.forEach(function (card) { card.hidden = !hits.has(card.getAttribute('data-id')); });
        var count = document.getElementById('result-count');
        var total = favoritesView ? candidates.length : activeTopic ? terms.filter(function (term) { return term.topic === activeTopic; }).length : cards.length;
        if (count) { count.textContent = hits.size + ' / ' + total + ' 个术语'; }
        var empty = document.getElementById('filter-empty');
        if (empty) { empty.hidden = hits.size > 0; empty.textContent = favoritesView && !candidates.length ? '还没有收藏。点击术语卡片或详情页的收藏按钮，把想继续学习的术语留在这里。' : '没有符合条件的术语，请调整筛选或搜索词。'; }
        var originLabel = document.getElementById('favorite-topic-label');
        if (originLabel) { originLabel.hidden = !favoritesView; }
      }
      if (window.PsychFavorites) { cleanup(window.PsychFavorites.subscribe(update)); }
      activeControls.forEach(function (control) { control.addEventListener('change', update); });
      update();
      function topicFromUrl() {
        if (!window.location) { return defaultTopic; }
        var requested = new URL(window.location.href).searchParams.get('topic');
        return topics.some(function (topic) { return topic.id === requested; }) ? requested : defaultTopic;
      }
      function changeTopic(slug, writeHistory) {
        var topic = topics.find(function (item) { return item.id === slug; });
        if (!intro || !topic || activeTopic === slug) { return; }
        if(writeHistory&&window.PsychSoftNavigation)window.PsychSoftNavigation.saveCurrent();
        topicStates[activeTopic] = {query: input ? input.value : '', level: controls.level.value, type: controls.type.value, has_r: controls.has_r.value, origin: controls.origin ? controls.origin.value : ''};
        activeTopic = slug;
        intro.setAttribute('data-topic', slug);
        document.getElementById('topic-title').textContent = topic.zh;
        document.getElementById('topic-description').textContent = topic.description || '';
        document.getElementById('topic-basis').textContent = topic.overview || topic.basis || '';
        var saved = topicStates[slug] || {query:'',level:'',type:'',has_r:'',origin:''};
        if (input) { input.value = saved.query; }
        ['level','type','has_r','origin'].forEach(function (key) {
          if (!controls[key]) { return; }
          controls[key].value = saved[key];
          controls[key].dispatchEvent(new Event('change', {bubbles:true}));
        });
        document.querySelectorAll('[data-topic-link]').forEach(function (link) {
          if (link.getAttribute('data-topic-link') === slug) { link.setAttribute('aria-current', 'page'); }
          else { link.removeAttribute('aria-current'); }
        });
        update();
        if (window.PsychSearchUI) window.PsychSearchUI.refresh();
        if (writeHistory) {
          var url = new URL(window.location.href);
          url.searchParams.set('topic',slug); url.searchParams.delete('theme');
          if(window.PsychSoftNavigation)window.PsychSoftNavigation.topicHistory(url.href);
          else window.history.pushState({}, '', url.href);
        }
      }
      if (intro && topics.length) {
        var topicElements = [intro].concat(Array.from(document.querySelectorAll('body > main > .filter-bar, body > main > .term-grid, #result-count, #filter-empty')));
        function selectTopic(slug) {
          var motion = window.PsychNavigationMotion;
          if (motion) motion.cancelTopic();
          if (activeTopic === slug) return;
          if (motion) motion.coverTopic(topicElements,function(){changeTopic(slug,true);});
          else changeTopic(slug,true);
        }
        document.querySelectorAll('[data-topic-link]').forEach(function (link) {
          link.addEventListener('click', function (event) {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button > 0) { return; }
            event.preventDefault();
            selectTopic(link.getAttribute('data-topic-link'));
          });
        });
        on(window,'popstate', function () { if(window.PsychSoftNavigation)return; if(window.PsychNavigationMotion)window.PsychNavigationMotion.cancelTopic(); changeTopic(topicFromUrl(), false); });
        changeTopic(topicFromUrl(), false);
      }
    }
    var local = window.PsychSiteData && window.PsychSiteData.search;
    if (Array.isArray(local)) { populate(local); return; }
    fetch('assets/data/search-index.json').then(function (response) { return response.json(); }).then(populate);
  }

  function wireFavorites() {
    var store = window.PsychFavorites;
    if (!store) { return; }
    cleanup(function(){clearTimeout(window.favoriteNoticeTimer);var status=document.getElementById('favorite-status');if(status)status.hidden=true;});
    var buttons = Array.from(document.querySelectorAll('[data-favorite]'));
    function refresh() {
      buttons.forEach(function (button) {
        var active = store.has(button.getAttribute('data-favorite'));
        button.setAttribute('aria-pressed', String(active));
        button.setAttribute('aria-label', (active ? '取消收藏' : '收藏') + button.getAttribute('data-name'));
        button.querySelector('[data-favorite-label]').textContent = active ? '已收藏' : '收藏';
      });
      var count = document.querySelector('[data-topic-count="favorites"]');
      if (count) {
        var available = window.PsychSiteData && window.PsychSiteData.search || [];
        count.textContent = available.filter(function (term) { return store.has(term.id); }).length;
        count.setAttribute('aria-label', count.textContent + '个收藏');
      }
    }
    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        var active = store.toggle(button.getAttribute('data-favorite'));
        var status = document.getElementById('favorite-status');
        if (status) {
          status.hidden = false;
          status.textContent = (active ? '已收藏：' : '已取消收藏：') + button.getAttribute('data-name') + (store.persistent() ? '' : '。浏览器禁止保存，仅在当前页面暂存。');
          clearTimeout(window.favoriteNoticeTimer);
          window.favoriteNoticeTimer = setTimeout(function () { status.hidden = true; }, store.persistent() ? 2200 : 8000);
        }
      });
    });
    cleanup(store.subscribe(refresh)); refresh();
  }

  wireTabs(); wireCopy(); wireFavorites(); wireSearch(); wireTermQuizzes();
  function openDirection() {
    var id = window.location && window.location.hash;
    if (!id || !id.startsWith('#direction-')) { return; }
    var detail = document.getElementById(id.slice(1));
    if (detail) { detail.open = true; detail.scrollIntoView({block:'start',behavior:'instant'}); }
  }
  if (window.addEventListener) { on(window,'hashchange', openDirection); openDirection(); }
  var practice = document.getElementById('practice-app');
  if (practice && window.PsychPractice) { cleanup(window.PsychPractice.init(practice,ctx)); }
  if(ctx&&ctx.state.filters){Object.keys(ctx.state.filters).forEach(function(id){var el=document.getElementById(id);if(el){el.value=ctx.state.filters[id];el.dispatchEvent(new Event('change',{bubbles:true}));}});}
  return {capture:function(){var filters={};['level-filter','type-filter','r-filter','favorite-topic-filter'].forEach(function(id){var el=document.getElementById(id);if(el)filters[id]=el.value;});return {filters:filters,practice:practice&&window.PsychPractice.captureState()};}};
  }
  if(window.PsychPageRuntime)window.PsychPageRuntime.register('site',mount);else mount(null);
}());
