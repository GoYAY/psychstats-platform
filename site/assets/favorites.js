(function () {
  'use strict';
  var key = 'psych-favorites-v1', saved = new Set(), durable = true, listeners = [];
  function read() {
    try {
      var data = JSON.parse(window.localStorage.getItem(key) || '[]');
      saved = new Set(Array.isArray(data) ? data.filter(function (id) { return typeof id === 'string' && /^[a-z0-9-]+$/.test(id); }) : []);
    } catch (error) {
      // Malformed data is recoverable; inaccessible storage uses session memory.
      try { window.localStorage.getItem(key); saved = new Set(); } catch (denied) { durable = false; }
    }
  }
  read();
  function notify() { listeners.forEach(function (listener) { listener(); }); }
  window.PsychFavorites = {
    has: function (id) { return saved.has(id); },
    ids: function () { return Array.from(saved); },
    persistent: function () { return durable; },
    subscribe: function (listener) {
      listeners.push(listener);
      return function () { listeners = listeners.filter(function (item) { return item !== listener; }); };
    },
    toggle: function (id) {
      if (typeof id !== 'string' || !/^[a-z0-9-]+$/.test(id)) { return false; }
      // Read first so a stale tab does not overwrite another tab's additions.
      if (durable) { read(); }
      if (saved.has(id)) { saved.delete(id); } else { saved.add(id); }
      try { window.localStorage.setItem(key, JSON.stringify(Array.from(saved))); durable = true; }
      catch (error) { durable = false; }
      notify(); return saved.has(id);
    }
  };
  window.addEventListener('storage', function (event) { if (event.key === key || event.key === null) { read(); notify(); } });
  window.addEventListener('pageshow', function () { if (durable) { read(); notify(); } });
}());
