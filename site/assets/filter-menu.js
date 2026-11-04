(function () {
  'use strict';

  function nextIndex(current, count, key) {
    if (!count) { return -1; }
    if (key === 'Home') { return 0; }
    if (key === 'End') { return count - 1; }
    if (key === 'ArrowDown') { return (current + 1 + count) % count; }
    if (key === 'ArrowUp') { return (current - 1 + count) % count; }
    return current;
  }

  function enhance(select) {
    var wrap = document.createElement('span');
    wrap.className = 'filter-select';
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'filter-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-label', select.closest('label').firstChild.textContent.trim());
    var list = document.createElement('span');
    list.className = 'filter-options';
    list.id = select.id + '-options';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', trigger.getAttribute('aria-label'));
    list.hidden = true;
    trigger.setAttribute('aria-controls', list.id);
    wrap.appendChild(trigger);
    wrap.appendChild(list);
    var buttons = [];
    function close(restoreFocus) {
      list.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      if (restoreFocus) { trigger.focus(); }
    }
    function open(focusIndex) {
      var viewportWidth = document.documentElement.clientWidth;
      document.querySelectorAll('.filter-select .filter-options:not([hidden])').forEach(function (other) {
        if (other !== list) { other.hidden = true; other.previousElementSibling.setAttribute('aria-expanded', 'false'); }
      });
      list.hidden = false;
      list.style.left = '0px';
      var bounds = list.getBoundingClientRect();
      if (bounds.right > viewportWidth - 14) {
        list.style.left = (viewportWidth - 14 - bounds.right) + 'px';
      }
      trigger.setAttribute('aria-expanded', 'true');
      if (typeof focusIndex === 'number' && buttons[focusIndex]) { buttons[focusIndex].focus(); }
    }
    function render() {
      list.replaceChildren();
      buttons = Array.from(select.options).map(function (option, index) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'filter-option';
        button.textContent = option.textContent;
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', String(option.selected));
        button.tabIndex = -1;
        button.addEventListener('click', function () {
          select.value = option.value;
          select.dispatchEvent(new Event('change', { bubbles: true }));
          sync();
          close(true);
        });
        button.addEventListener('keydown', function (event) {
          var target = nextIndex(index, buttons.length, event.key);
          if (target !== index || event.key === 'Home' || event.key === 'End') {
            event.preventDefault(); buttons[target].focus();
          } else if (event.key === 'Escape') { event.preventDefault(); close(true); }
          else if (event.key === 'Tab') { close(false); }
        });
        list.appendChild(button);
        return button;
      });
      sync();
    }
    function sync() {
      var chosen = select.options[select.selectedIndex];
      trigger.textContent = chosen ? chosen.textContent : '全部';
      buttons.forEach(function (button, index) {
        button.setAttribute('aria-selected', String(index === select.selectedIndex));
      });
    }
    trigger.addEventListener('click', function () {
      if (list.hidden) { open(); } else { close(false); }
    });
    trigger.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        open(nextIndex(select.selectedIndex, buttons.length, event.key));
      } else if (event.key === 'Escape') { close(false); }
    });
    function outside(event) {
      if (!wrap.contains(event.target)) { close(false); }
    }
    document.addEventListener('pointerdown', outside);
    select.addEventListener('change', sync);
    function resize() { close(false); }
    window.addEventListener('resize', resize);
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    wrap.classList.add('is-enhanced');
    render();
    return { refresh: render, dispose:function(){document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',resize);} };
  }

  if (typeof module !== 'undefined' && module.exports) { module.exports = { nextIndex: nextIndex }; }
  if (typeof window !== 'undefined') { window.PsychFilterMenu = { enhance: enhance }; }
}());
