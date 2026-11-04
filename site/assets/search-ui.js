(function () {
  'use strict';
  var input = document.getElementById('q'), scope = document.getElementById('search-scope');
  if (!input || !scope || !window.PsychSearch) return;
  var host = input.closest('.header-search'), panel = document.getElementById('search-panel');
  var list = document.getElementById('search-results'), status = document.getElementById('search-status');
  var help = document.getElementById('search-help'), controls = document.getElementById('page-find-controls');
  var article = document.querySelector('.term-content'), intro = document.getElementById('topic-intro');
  var terms = window.PsychSiteData && window.PsychSiteData.search || [];
  var marks = [], current = -1, timer;
  function updatePage(ctx) {
    clearTimeout(timer);clearMarks();
    article=document.querySelector('.term-content');intro=document.getElementById('topic-intro');
    Array.from(scope.options).forEach(function(option){if(option.value!=='global')option.remove();});
    if(intro||article){var option=document.createElement('option');option.value=article?'page':'topic';option.textContent=article?'本页':'本主题';scope.appendChild(option);}
    scope.value=ctx.state.scope||'global';input.value=ctx.state.query||'';panel.hidden=true;render();measureHeader();
    return {capture:function(){return {query:input.value,scope:scope.value};},dispose:function(){clearTimeout(timer);clearMarks();article=null;intro=null;panel.hidden=true;}};
  }
  function measureHeader() {
    var header = document.querySelector('.site-head');
    if (header) document.documentElement.style.setProperty('--header-height', header.getBoundingClientRect().height + 'px');
  }
  measureHeader();
  window.addEventListener('resize', measureHeader);
  if (intro || article) {
    var option = document.createElement('option');
    option.value = article ? 'page' : 'topic'; option.textContent = article ? '本页' : '本主题';
    scope.appendChild(option);
  }
  function clearMarks() {
    marks.forEach(function (mark) { var parent = mark.parentNode; if (parent) { mark.replaceWith(document.createTextNode(mark.textContent)); parent.normalize(); } });
    marks = []; current = -1;
  }
  function pageMatches(query) {
    clearMarks();
    if (!query) return;
    var walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
    var nodes = [], node;
    while ((node = walker.nextNode())) {
      var parent = node.parentElement;
      if (!parent || parent.closest('header, .formula-display, button, code, script, style, [hidden], .term-sequence') || !parent.getClientRects().length) continue;
      nodes.push(node);
    }
    var escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    var pattern = new RegExp(escaped, 'giu');
    nodes.forEach(function (textNode) {
      var text = textNode.textContent, hits = Array.from(text.matchAll(pattern));
      if (!hits.length) return;
      var fragment = document.createDocumentFragment(), end = 0;
      hits.forEach(function (hit) {
        fragment.appendChild(document.createTextNode(text.slice(end, hit.index)));
        var mark = document.createElement('mark'); mark.className = 'search-hit'; mark.textContent = hit[0];
        fragment.appendChild(mark); marks.push(mark); end = hit.index + hit[0].length;
      });
      fragment.appendChild(document.createTextNode(text.slice(end))); textNode.replaceWith(fragment);
    });
  }
  function moveMatch(direction, scroll) {
    if (!marks.length) return;
    if (current >= 0) marks[current].classList.remove('is-current');
    current = (current + direction + marks.length) % marks.length;
    marks[current].classList.add('is-current');
    status.textContent = '本页：第 ' + (current+1) + ' / ' + marks.length + ' 处';
    if (scroll) marks[current].scrollIntoView({block:'center', behavior:'instant'});
  }
  function textElement(tag, text, className) {
    var element = document.createElement(tag); element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function render() {
    clearTimeout(timer);
    var query = input.value.trim(), local = scope.value;
    clearMarks(); list.replaceChildren(); controls.hidden = local !== 'page';
    var topic = intro && intro.getAttribute('data-topic');
    var topicName = intro && document.getElementById('topic-title').textContent;
    help.textContent = local === 'page' ? '本页：查可见正文，标出匹配词；上一处 / 下一处定位。公式与代码不改动。' :
      local === 'topic' ? '本主题（' + topicName + '）：查术语名称和正文，显示提到关键词的页面。' :
      '全站：不受主题、难度或收藏筛选限制；名称优先，也查正文。';
    input.placeholder = local === 'page' ? '查找本页正文' : local === 'topic' ? '搜索本主题正文' : '搜索全站术语';
    input.setAttribute('aria-label', input.placeholder);
    if (!query) {
      status.textContent = '输入关键词即可搜索；无需输入主题名称或斜线。';
      document.getElementById('find-previous').disabled = true;
      document.getElementById('find-next').disabled = true;
      return;
    }
    if (local === 'page') {
      pageMatches(query);
      document.getElementById('find-previous').disabled = !marks.length;
      document.getElementById('find-next').disabled = !marks.length;
      status.textContent = marks.length ? '本页：找到 ' + marks.length + ' 处，使用上一处 / 下一处定位。' : '本页可见正文没有匹配。试试更短的关键词，或切换全站。';
      moveMatch(1, false); return;
    }
    var filters = local === 'topic' && topic !== 'favorites' ? {topic:topic} : {};
    var candidates = local === 'topic' && topic === 'favorites' ? terms.filter(function (term) { return window.PsychFavorites && window.PsychFavorites.has(term.id); }) : terms;
    var hits = window.PsychSearch.searchTerms(query, filters, candidates);
    status.textContent = (local === 'topic' ? '本主题' : '全站') + '：' + hits.length + ' 个结果' + (hits.length ? '，按名称匹配优先排序。' : '。试试简称、英文名称或更短的关键词。');
    hits.forEach(function (term) {
      var item = document.createElement('li'), link = document.createElement('a');
      link.href = (host.dataset.root || '') + (term.url || 'terms/' + term.id + '.html');
      var concept = Object.keys(term.concepts || {}).find(function (name) { return window.PsychSearch.normalizeQuery(name) === window.PsychSearch.normalizeQuery(query); });
      if (concept) link.href += '#' + term.concepts[concept];
      link.appendChild(textElement('strong',term.zh));
      link.appendChild(textElement('span',term.en + ' · ' + term.topic_label,'search-result-meta'));
      var text = term.body_text || term.summary || '', at = text.toLowerCase().indexOf(query.toLowerCase());
      var excerpt = at >= 0 ? text.slice(Math.max(0,at-24),at+query.length+45) : term.summary;
      link.appendChild(textElement('span',excerpt || '', 'search-result-excerpt'));
      item.appendChild(link); list.appendChild(item);
    });
  }
  function show() { panel.hidden = false; render(); }
  input.addEventListener('focus',show);
  input.addEventListener('input',function () { panel.hidden = false; clearTimeout(timer); timer = setTimeout(render,80); });
  scope.addEventListener('change',show);
  document.getElementById('find-previous').addEventListener('click',function () { moveMatch(-1,true); });
  document.getElementById('find-next').addEventListener('click',function () { moveMatch(1,true); });
  input.addEventListener('keydown',function (event) {
    if (event.key === 'Escape') { clearTimeout(timer); panel.hidden = true; return; }
    if (event.key === 'Enter') {
      event.preventDefault(); render();
      if (scope.value === 'page') moveMatch(0,true);
      else if (list.querySelector('a')) list.querySelector('a').click();
    } else if (event.key === 'ArrowDown') { var first = list.querySelector('a'); if (first) { event.preventDefault(); first.focus(); } }
  });
  host.addEventListener('keydown',function (event) { if (event.key === 'Escape') { clearTimeout(timer); panel.hidden = true; input.focus(); panel.hidden = true; } });
  document.addEventListener('pointerdown',function (event) { if (!host.contains(event.target)) panel.hidden = true; });
  window.addEventListener('pageshow',render);
  if (window.PsychFavorites) window.PsychFavorites.subscribe(function () { if (scope.value === 'topic') render(); });
  window.PsychSearchUI = {refresh:render}; render();
  if(window.PsychPageRuntime)window.PsychPageRuntime.register('search',updatePage);
}());
