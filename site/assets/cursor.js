(function () {
  'use strict';

  function initCursor(doc, win) {
    if (!win.matchMedia('(hover: hover) and (pointer: fine) and (forced-colors: none)').matches) {
      return false;
    }
    var dot = doc.createElement('span');
    dot.className = 'cursor-dot';
    dot.hidden = true;
    dot.setAttribute('aria-hidden', 'true');
    doc.body.appendChild(dot);
    doc.documentElement.classList.add('dot-cursor');
    // A modal lives in the browser top layer, above every ordinary z-index.
    // Keep one ring in that same layer and return it when the dialog closes.
    function syncCursorLayer(target) {
      var host = target && target.closest('dialog:modal');
      if (!host) {
        var modals = doc.querySelectorAll('dialog:modal');
        host = modals.length ? modals[modals.length - 1] : doc.body;
      }
      if (dot.parentNode !== host) { host.appendChild(dot); }
    }
    new win.MutationObserver(function () { syncCursorLayer(); }).observe(doc.body, {
      subtree: true, childList: true, attributes: true, attributeFilter: ['open']
    });
    function updateCursor(event) {
      syncCursorLayer(event.target);
      if ((event.pointerType && event.pointerType !== 'mouse') || event.target.closest('input, textarea, [contenteditable]')) {
        dot.hidden = true;
        dot.className = 'cursor-dot';
        return;
      }
      var interactive = event.target.closest('a[href], button, select, summary, [role="button"], [role="link"], [data-chart-interactive], .formula-symbol, .practice-reading[data-loaded="true"]');
      var disabled = event.target.closest(':disabled, [aria-disabled="true"], [inert]');
      dot.className = interactive && !disabled ? 'cursor-dot is-interactive' : 'cursor-dot';
      dot.hidden = false;
      dot.style.transform = 'translate3d(' + event.clientX + 'px, ' + event.clientY + 'px, 0) translate(-50%, -50%)';
    }
    doc.addEventListener('pointermove', updateCursor);
    doc.addEventListener('pointerover', updateCursor);
    doc.addEventListener('pointerout', function (event) {
      if (!event.relatedTarget) { dot.hidden = true; dot.className = 'cursor-dot'; }
    });
    win.addEventListener('blur', function () { dot.hidden = true; dot.className = 'cursor-dot'; });
    return true;
  }

  if (typeof module !== 'undefined' && module.exports) { module.exports = { initCursor: initCursor }; }
  if (typeof document !== 'undefined') { initCursor(document, window); }
}());
