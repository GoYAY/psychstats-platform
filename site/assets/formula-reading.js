(function () {
  'use strict';
  function mount(ctx) {
  document.querySelectorAll('.formula').forEach(function (section) {
    var keys = Array.from(section.querySelectorAll('.formula-key'));
    var display = section.querySelector('.formula-display');
    if (!display || !keys.length) return;
    var symbols = Array.from(display.querySelectorAll('.katex-html .formula-symbol'));
    var selected = new Set();
    var hovered = null;
    var focused = null;
    function activate() {
      symbols.forEach(function (symbol) {
        var id = Array.from(symbol.classList).find(function (name) { return /^fs-\d+$/.test(name); });
        symbol.classList.toggle('is-active', selected.has(id) || id === hovered);
        symbol.classList.toggle('is-focused', id === focused);
        symbol.classList.toggle('is-pinned', selected.has(id));
      });
      keys.forEach(function (key) {
        var id = key.dataset.symbol;
        var active = selected.has(id) || id === hovered;
        var row = key.closest('.formula-row');
        row.classList.toggle('is-active', active);
        row.classList.toggle('is-pinned', selected.has(id));
        key.classList.toggle('is-active', active);
        key.classList.toggle('is-pinned', selected.has(id));
        key.setAttribute('aria-pressed', String(selected.has(id)));
      });
    }
    function toggle(id) { if (selected.has(id)) selected.delete(id); else selected.add(id); activate(); }
    function enter(id) { hovered = id; activate(); }
    function leave(id) { if (hovered === id) hovered = null; activate(); }
    keys.forEach(function (key) {
      var id = key.dataset.symbol;
      var row = key.closest('.formula-row');
      row.addEventListener('pointerenter', function () { enter(id); });
      row.addEventListener('pointerleave', function () { leave(id); });
      key.addEventListener('focus', function () { focused = id; activate(); });
      key.addEventListener('blur', function () { if (focused === id) focused = null; activate(); });
      row.addEventListener('click', function (event) { if (!event.target.closest('a')) toggle(id); });
    });
    symbols.forEach(function (symbol) {
      var id = Array.from(symbol.classList).find(function (name) { return /^fs-\d+$/.test(name); });
      var key = keys.find(function (button) { return button.dataset.symbol === id; });
      if (!key) return;
      symbol.addEventListener('pointerenter', function () { enter(id); });
      symbol.addEventListener('pointerleave', function () { leave(id); });
      function pin(event) {
        event.preventDefault();
        toggle(id);
      }
      symbol.addEventListener('click', pin);
    });
    // Keep KaTeX's original MathML accessible; its visual tree remains hidden
    // from AT. Native glossary buttons offer equivalent keyboard controls.
    section.addEventListener('pointerleave', function () { hovered = null; activate(); });
    function keyboard(event) {
      // Hover enables shortcuts without stealing focus; other controls keep theirs.
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      var target = event.target;
      var ownKey = keys.includes(target);
      if (!ownKey && target.closest('input, textarea, select, button, a, [contenteditable], [role="button"]')) return;
      var id = ownKey ? target.dataset.symbol : hovered;
      if (!id) return;
      if (event.key === 'Escape') { selected.clear(); hovered = null; activate(); }
      else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); if (!event.repeat) toggle(id); }
      else if (event.key === 'Tab') {
        if (ownKey) { hovered = null; activate(); return; }
        var index = keys.findIndex(function (key) { return key.dataset.symbol === id; });
        var next = index + (event.shiftKey ? -1 : 1);
        hovered = null;
        if (next >= 0 && next < keys.length) { event.preventDefault(); keys[next].focus(); }
        else keys[index].focus(); // Native Tab exits the list at either boundary.
        activate();
      }
    }
    if(ctx)ctx.on(document,'keydown',keyboard);else document.addEventListener('keydown',keyboard);
  });
  }
  if(window.PsychPageRuntime)window.PsychPageRuntime.register('formula',mount);else mount(null);
}());
