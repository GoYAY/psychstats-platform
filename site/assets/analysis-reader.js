(function () {
  'use strict';
  function mount(ctx) {
  function on(target,type,fn,options){if(ctx)ctx.on(target,type,fn,options);else target.addEventListener(type,fn,options);}
  var fields = Array.from(document.querySelectorAll('[data-analysis-field]'));
  var pinned = new Set(), hover = null, focus = null;
  function paint() {
    fields.forEach(function (button) {
      var id = button.dataset.analysisField;
      button.classList.toggle('is-highlighted', pinned.has(id) || hover === id || focus === id);
      button.setAttribute('aria-pressed', String(pinned.has(id)));
    });
    document.querySelectorAll('[data-analysis-meaning]').forEach(function (row) {
      var id = row.dataset.analysisMeaning;
      row.classList.toggle('is-highlighted', pinned.has(id) || hover === id || focus === id);
    });
  }
  fields.forEach(function (button) {
    var id = button.dataset.analysisField;
    button.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') { hover = id; paint(); } });
    button.addEventListener('pointerleave', function () { hover = null; paint(); });
    button.addEventListener('focus', function () { focus = id; paint(); });
    button.addEventListener('blur', function () { focus = null; paint(); });
    button.addEventListener('click', function () { pinned.has(id) ? pinned.delete(id) : pinned.add(id); paint(); });
  });
  var clear = document.querySelector('[data-analysis-clear]');
  document.querySelectorAll('[data-analysis-locate]').forEach(function (button) {
    button.addEventListener('click', function () {
      var id = button.dataset.analysisLocate;
      var target = fields.find(function (field) { return field.dataset.analysisSource === id; });
      if (!target) return;
      for (var parent = target.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') parent.open = true;
      }
      pinned.add(id); paint();
      target.scrollIntoView({block:'center', inline:'nearest', behavior:'instant'});
      target.focus({preventScroll:true});
    });
  });
  if (clear) clear.addEventListener('click', function () { pinned.clear(); hover = focus = null; paint(); });
  var sectionLinks = Array.from(document.querySelectorAll('[data-analysis-section]'));
  var sections = sectionLinks.map(function (link) { return document.getElementById(link.hash.slice(1)); }).filter(Boolean);
  if (sections.length) {
    var queued = false, raf = null;
    if(ctx)ctx.deferCleanup(function(){if(raf!==null)cancelAnimationFrame(raf);});
    function updateSection() {
      if(ctx&&!ctx.alive())return;
      queued = false;
      var current = sections[0];
      sections.forEach(function (section) {
        var threshold = (parseFloat(getComputedStyle(section).scrollMarginTop) || 110) + 40;
        if (section.getBoundingClientRect().top <= threshold) current = section;
      });
      sectionLinks.forEach(function (link) {
        if (link.hash === '#' + current.id) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    }
    on(window,'scroll', function () {
      if (!queued) { queued = true; raf=requestAnimationFrame(updateSection); }
    }, {passive:true});
    on(window,'resize', updateSection);
    updateSection();
  }
  var filter = document.getElementById('analysis-filter');
  function updateFilter() {
    var needle = filter.value.normalize('NFKC').toLowerCase().trim(), n = 0;
    document.querySelectorAll('.analysis-card').forEach(function (card) {
      card.hidden = !card.dataset.analysisSearch.toLowerCase().includes(needle);
      if (!card.hidden) n++;
    });
    document.querySelectorAll('.analysis-group').forEach(function (group) { group.hidden = !group.querySelector('.analysis-card:not([hidden])'); });
    document.getElementById('analysis-filter-status').textContent = n + ' 个分析示例';
  }
  if(filter){filter.addEventListener('input',updateFilter);if(ctx&&ctx.state.filter){filter.value=ctx.state.filter;updateFilter();}}
  return {capture:function(){return {filter:filter?filter.value:''};}};
  }
  if(window.PsychPageRuntime)window.PsychPageRuntime.register('analysis',mount);else mount(null);
}());
