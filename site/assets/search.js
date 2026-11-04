(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) { module.exports = api; }
  else { root.PsychSearch = api; }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function normalizeQuery(text) {
    return String(text == null ? '' : text).normalize('NFKC').toLowerCase().trim().replace(/\s+/g, ' ');
  }

  function haystack(term) {
    var fields = [term.id, term.zh, term.en, term.summary]
      .concat(term.aliases || [], term.problems_solved || [], term.search_terms || [], term.r_functions || [], [term.body_text || '']);
    return normalizeQuery(fields.filter(Boolean).join(' '));
  }

  function filterTerms(query, filters, terms) {
    var needle = normalizeQuery(query);
    filters = filters || {};
    return (terms || []).filter(function (term) {
      if (needle && haystack(term).indexOf(needle) === -1) { return false; }
      if (filters.topic && term.topic !== filters.topic) { return false; }
      if (filters.level && term.level !== filters.level) { return false; }
      if (filters.type && term.type !== filters.type) { return false; }
      if (filters.has_r !== undefined && filters.has_r !== '' && Boolean(term.has_r) !== (filters.has_r === true || filters.has_r === 'true')) { return false; }
      return true;
    });
  }

  function searchTerms(query, filters, terms) {
    var needle = normalizeQuery(query);
    var needles = [needle];
    (terms || []).forEach(function (term) {
      var names = [term.zh,term.en].concat(term.aliases || []).filter(Boolean).map(normalizeQuery);
      if (needle && names.includes(needle)) needles = needles.concat(names);
    });
    needles = Array.from(new Set(needles));
    function score(term) {
      var names = [term.zh,term.en,term.id].concat(term.aliases || [],Object.keys(term.concepts || {})).map(normalizeQuery);
      if (names.includes(needle)) return 0;
      if (names.some(function (name) { return name.includes(needle); })) return 1;
      if (normalizeQuery(term.summary).includes(needle)) return 2;
      return 3;
    }
    var hits = filterTerms('', filters, terms).filter(function (term) {
      return !needle || needles.some(function (variant) { return haystack(term).includes(variant); });
    });
    return needle ? hits.sort(function (a,b) { return score(a)-score(b); }) : hits;
  }
  return { normalizeQuery: normalizeQuery, filterTerms: filterTerms, searchTerms: searchTerms };
}));
