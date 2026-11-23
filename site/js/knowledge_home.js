/* PR Data Observatory: the Knowledge home page (knowledge.html; docs/knowledge-plan-2026-11.md, PR 1). It draws one card for every published,
   public item of the Knowledge registry (window.KNOWLEDGE, written by knowledge.py into js/knowledge_items.js), grouped by the top domain of its
   home domain in the registry's order, with a search box, the kinds as filters and "Published only". The search, the kind and the filter are kept
   in the address (#q=, #k=, #p=1) so a filtered list can be shared. Labels of the items are { en, es } (data-t="skip"); interface words are T() keys
   of the knowledge_home scope. */
(function () {
  'use strict';
  const K = window.KNOWLEDGE, list = document.getElementById('khList');
  if (!K || !list) return;
  const lang = () => (window.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const L = (o) => (o && (o[lang()] || o.en)) || '';
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const fold = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const dom = Object.fromEntries(K.domains.map(d => [d.id, d]));
  const top = (id) => id.split('.')[0];
  const marked = (it) => it.status === 'in_review' || (it.status === 'published' && it.review === true);
  const month = (ym) => { const [y, m] = ym.split('-').map(Number); return new Intl.DateTimeFormat(lang() === 'es' ? 'es-PR' : 'en-US', { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1)); };
  const byId = Object.fromEntries(K.items.map(it => [it.id, it]));

  // the state, read from and written to the address
  const st = { q: '', k: 'all', p: false };
  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    st.q = h.get('q') || ''; st.k = K.kinds[h.get('k')] ? h.get('k') : 'all'; st.p = h.get('p') === '1';
  }
  function writeHash() {
    const h = new URLSearchParams();
    if (st.q) h.set('q', st.q); if (st.k !== 'all') h.set('k', st.k); if (st.p) h.set('p', '1');
    const s = h.toString(); history.replaceState(null, '', s ? '#' + s : location.pathname + location.search);
  }

  const words = (it) => fold([L(it.title), L(it.label), L(it.summary), it.title.en, it.summary.en,
    ...it.domains.map(d => L((dom[d] || {}).name)), ...(it.datasets || []).map(d => L(K.datasets[d]))].join(' '));
  const shown = () => {
    const q = fold(st.q).split(/\s+/).filter(Boolean);
    return K.items.filter(it => (st.k === 'all' || it.kind === st.k) && (!st.p || !marked(it)) && q.every(w => words(it).includes(w)));
  };

  function statusBadge(it) {
    if (!marked(it)) return `<span class="kh-badge kh-pub-b">${esc(T('Published'))}</span>`;
    const who = (it.reviewer || []).map(r => L(K.reviewers[r])).filter(Boolean);
    return `<span class="kh-badge kh-rev-b">${esc(who.length ? T('In review · {who}', { who: who.join(', ') }) : T('In review'))}</span>`;
  }
  function card(it) {
    const also = it.domains.slice(1).map(d => L((dom[d] || {}).name)).filter(Boolean);
    const rel = (it.related || []).map(r => byId[r]).filter(Boolean);
    const ds = (it.datasets || []).map(d => L(K.datasets[d])).filter(Boolean);
    const dsText = ds.length > 2 ? T('{list} and {n} more', { list: ds.slice(0, 2).join('; '), n: ds.length - 2 }) : ds.join('; ');
    const meta = [T('Updated {month}', { month: month(it.updated) })];
    if (also.length) meta.push(T('Also in {topics}', { topics: also.join(', ') }));
    return `<article class="kh-card" data-t="skip">` +
      `<div class="kh-badges"><span class="kh-badge">${esc(L(K.kinds[it.kind]))}</span>${statusBadge(it)}</div>` +
      `<h3><span class="ms-icon" aria-hidden="true">${esc(it.icon)}</span><a href="${esc(it.page)}">${esc(L(it.title))}</a></h3>` +
      `<p class="kh-sum">${esc(L(it.summary))}</p>` +
      `<p class="kh-meta">${esc(meta.join(' · '))}</p>` +
      (ds.length ? `<p class="kh-meta"><b>${esc(T('Data'))}:</b> ${esc(dsText)}</p>` : '') +
      (rel.length ? `<p class="kh-meta"><b>${esc(T('Related'))}:</b> ${rel.map(r => `<a href="${esc(r.page)}">${esc(L(r.title))}</a>`).join(', ')}</p>` : '') +
      `<p class="kh-links"><a href="${esc(it.page)}">${esc(T('Open page'))}</a><a href="index.html#topic=${esc(top(it.domains[0]))}">${esc(T('On the map'))}</a><a href="${esc(it.page + it.cite)}">${esc(T('Sources and how to cite'))}</a></p>` +
      `</article>`;
  }

  function drawKinds() {
    const counts = {}; K.items.forEach(it => { counts[it.kind] = (counts[it.kind] || 0) + 1; });
    const chip = (k, text) => `<button type="button" class="kh-chip" data-k="${esc(k)}" aria-pressed="${st.k === k}">${esc(text)}</button>`;
    document.getElementById('khKinds').innerHTML = chip('all', T('All {n}', { n: K.items.length })) +
      Object.keys(K.kinds).filter(k => counts[k]).map(k => chip(k, `${L(K.kinds[k])} · ${counts[k]}`)).join('');
  }
  function draw() {
    const items = shown(), groups = new Map();
    K.domains.filter(d => !d.id.includes('.')).forEach(d => groups.set(d.id, []));
    items.forEach(it => { const g = top(it.domains[0]); if (!groups.has(g)) groups.set(g, []); groups.get(g).push(it); });
    let html = '';
    for (const [g, its] of groups) {
      if (!its.length) continue;
      html += `<section class="block kh-group"><h2 data-t="skip">${esc(L((dom[g] || {}).name) || g)} <span class="kh-n">· ${its.length}</span></h2><div class="kh-grid">${its.map(card).join('')}</div></section>`;
    }
    list.innerHTML = html || `<p class="note kh-empty">${esc(T('Nothing matches. Try another word, or show every kind.'))}</p>`;
    drawKinds();
  }

  readHash();
  const q = document.getElementById('khQ'), pub = document.getElementById('khPub');
  q.value = st.q; pub.checked = st.p;
  q.addEventListener('input', () => { st.q = q.value.trim(); writeHash(); draw(); });
  pub.addEventListener('change', () => { st.p = pub.checked; writeHash(); draw(); });
  document.getElementById('khKinds').addEventListener('click', (e) => { const b = e.target.closest('button[data-k]'); if (!b) return; st.k = b.dataset.k; writeHash(); draw(); });
  window.addEventListener('hashchange', () => { readHash(); q.value = st.q; pub.checked = st.p; draw(); });
  draw();
  if (window.I18N) I18N.apply();
})();
