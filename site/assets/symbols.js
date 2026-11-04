(function (root) {
  'use strict';
  const normalize = value => String(value || '').normalize('NFKC').trim();
  function matches(row, query, kind) {
    if (kind && row.kind !== kind) return false;
    const q = normalize(query);
    if (!q) return true;
    // Searching a single Latin letter is intentional, not a substring of prose.
    if (/^[a-z]$/i.test(q)) return row.tokens.some(token => normalize(token) === q);
    const lower = q.toLocaleLowerCase();
    return normalize(row.search).toLocaleLowerCase().includes(lower) ||
      row.tokens.some(token => normalize(token).toLocaleLowerCase().includes(lower));
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {matches};
  if (!root.document) return;
  function mount(ctx) {
  const query = document.getElementById('symbol-query');
  if (!query) return;
  const category = document.getElementById('symbol-kind');
  const rows = [...document.querySelectorAll('[data-symbol-row]')];
  const records = rows.map(row => ({element: row, kind: row.dataset.kind,
    tokens: JSON.parse(row.dataset.tokens), search: row.dataset.search}));
  function update() {
    let visible = 0;
    records.forEach(row => {
      row.element.hidden = !matches(row, query.value, category.value);
      if (!row.element.hidden) visible++;
    });
    document.getElementById('symbol-count').textContent = `显示 ${visible} / ${rows.length} 条释义`;
    document.getElementById('symbol-empty').hidden = visible !== 0;
  }
  query.addEventListener('input', update);
  category.addEventListener('change', update);
  document.getElementById('symbol-clear').addEventListener('click', () => {
    query.value = ''; category.value = ''; update(); query.focus();
  });
  function revealHash() {
    let key;
    try { key = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const row = document.getElementById(key);
    if (!row?.matches('[data-symbol-row]')) return;
    query.value = ''; category.value = ''; update();
    row.scrollIntoView({block: 'center', behavior: 'instant'});
    row.focus({preventScroll: true});
  }
  if(ctx)ctx.on(window,'hashchange',revealHash);else window.addEventListener('hashchange', revealHash);
  if(ctx&&ctx.state.query){query.value=ctx.state.query;category.value=ctx.state.kind||'';}
  update(); revealHash();
  return {capture:()=>({query:query.value,kind:category.value})};
  }
  if(root.PsychPageRuntime)root.PsychPageRuntime.register('symbols',mount);else mount(null);
})(typeof window === 'undefined' ? globalThis : window);
