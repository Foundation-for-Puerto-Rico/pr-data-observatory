/* PR Data Observatory: the Data area (data.html; docs/workspace.md). The whole catalog as cards, with a search and filters on the left.

   It is the same catalog as the map's Data Catalog tab and the data dictionary: data/catalog.json (the topics) and data/catalog_index.json (every documented
   entry and source), both written by catalog.py from the registries. Nothing is listed here by hand, so a dataset added to the registry appears on its own.

   A card that can go on the map opens the map with it: "Add to my map" keeps the map as it was last left in this browser (twin.ws.last, written by
   js/ws_map.js) and adds the dataset; "New map" starts from it alone. Both are ordinary links in the map's own address form (e=, l=). */
(function () {
  'use strict';
  const el = (id) => document.getElementById(id);
  const icon = (n) => `<span class="ms-icon" aria-hidden="true">${esc(n)}</span>`;
  const read = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
  const PAGE = 48;
  const st = { rows: [], doms: [], byDom: {}, sources: {}, snap: new Date().getFullYear(), words: {}, q: '', sort: 'topic', shown: PAGE, f: { domain: new Set(), level: new Set(), holds: new Set(), licence: new Set(), source: '', year: '' } };
  const TINT = { '--fpr-blue': 'blue', '--fpr-green': 'green', '--fpr-yellow': 'yellow', '--fpr-red': 'red' };
  const top = (id) => { let d = st.byDom[id]; while (d && d.parent) d = st.byDom[d.parent]; return d || null; };
  const label = (r) => (I18N.has(r.name) ? T(r.name) : r.name);
  const holds = (r) => (!r.map ? 'doc' : r.map[0] === 'econ' ? 'series' : 'layer');
  const HOLDS = () => ({ series: T('Datasets by year, for the map and the timeline'), layer: T('Map layers and places'), doc: T('Documented, not on the map') });

  // ── Links to the map ────────────────────────────────────────────────────────
  const parse = (h) => { const o = {}; String(h || '').replace(/^#/, '').split('&').forEach(p => { const i = p.indexOf('='); if (i > 0) o[p.slice(0, i)] = p.slice(i + 1); else if (p) o[''] = p; }); return o; };
  const write = (o) => '#' + Object.entries(o).filter(([, v]) => v !== '' && v != null).map(([k, v]) => (k ? k + '=' + v : v)).join('&');
  function mapHref(r, add) {
    if (!r.map) return null;
    const last = add ? read('twin.ws.last', '') : '', o = /^#[\w\-.,~%=&:+ ]*$/.test(last) ? parse(last) : {};
    if (r.map[0] === 'econ') { const cur = o.e ? decodeURIComponent(o.e).split(',').filter(Boolean) : []; if (!cur.some(x => x.split('.')[0] === r.map[1])) cur.push(r.map[1] + '.' + (cur.filter(x => x.split('.')[1] !== 's').length >= 2 ? 's' : 'f')); o.e = encodeURIComponent(cur.join(',')); }
    else { const cur = new Set((o.l || '').split(',').filter(Boolean)); r.map[1].split(',').forEach(k => { cur.delete('-' + k); cur.add(k); }); o.l = [...cur].join(','); }
    return 'index.html' + write(o);
  }

  // ── Filtering ───────────────────────────────────────────────────────────────
  const tokens = (s) => norm(s).split(/\s+/).filter(Boolean);
  function match(r, except) {
    const f = st.f;
    if (except !== 'domain' && f.domain.size && ![r.domain, ...(r.domains || [])].some(d => { const t = top(d); return f.domain.has(d) || (t && f.domain.has(t.id)); })) return false;
    if (except !== 'level' && f.level.size && !(r.levels || []).some(l => f.level.has(l))) return false;
    if (except !== 'holds' && f.holds.size && !f.holds.has(holds(r))) return false;
    if (except !== 'licence' && f.licence.size && !f.licence.has(r.licence)) return false;
    if (f.source && !(r.sources || []).includes(f.source)) return false;
    if (f.year && !coversYear(r.years, f.year, st.snap)) return false;
    if (st.q) { const hay = r._hay || (r._hay = norm([r.name, label(r), r.id, (r.sources || []).map(s => (st.sources[s] || {}).name || s).join(' '), I18N.name(st.byDom[r.domain] || {}), st.words[r.id] || '', r.ask ? (r.ask[I18N.lang] || []).join(' ') : ''].join(' '))); if (!tokens(st.q).every(t => hay.includes(t))) return false; }
    return true;
  }
  const sorters = {
    topic: (a, b) => ((st.byDom[a.domain] || {}).order || 999) - ((st.byDom[b.domain] || {}).order || 999) || label(a).localeCompare(label(b)),
    name: (a, b) => label(a).localeCompare(label(b)),
    recent: (a, b) => ((b.years || [0, 0])[1] || 0) - ((a.years || [0, 0])[1] || 0) || label(a).localeCompare(label(b)),
    years: (a, b) => (((b.years || [0, 0])[1] - (b.years || [0, 0])[0]) || 0) - (((a.years || [0, 0])[1] - (a.years || [0, 0])[0]) || 0) || label(a).localeCompare(label(b)),
  };
  const period = (r) => (!r.years ? T('No date') : r.years[0] === r.years[1] ? String(r.years[0]) : T('{from} to {to}', { from: r.years[0], to: r.years[1] }));

  // ── Drawing ─────────────────────────────────────────────────────────────────
  function facet(id, title, opts, set, open) {
    return `<details class="ws-facet"${open ? ' open' : ''}><summary>${esc(title)}${icon('expand_more')}</summary>${opts.map(([v, l, n]) => `<label class="ws-check"><input type="checkbox" data-f="${id}" value="${esc(v)}"${set.has(v) ? ' checked' : ''}><span>${esc(l)}</span><em>${fmt(n)}</em></label>`).join('')}</details>`;
  }
  function filters() {
    const count = (key, test) => st.rows.filter(r => match(r, key) && test(r)).length, LV = LEVEL_LABEL(), LC = LICENCE_LABEL(), H = HOLDS();
    const doms = st.doms.filter(d => !d.parent).map(d => [d.id, I18N.name(d), count('domain', r => [r.domain, ...(r.domains || [])].some(x => (top(x) || {}).id === d.id))]).filter(x => x[2] || st.f.domain.has(x[0]));
    const lv = Object.keys(LV).map(k => [k, LV[k], count('level', r => (r.levels || []).includes(k))]).filter(x => x[2] || st.f.level.has(x[0]));
    const hd = Object.keys(H).map(k => [k, H[k], count('holds', r => holds(r) === k)]);
    const lc = Object.keys(LC).map(k => [k, LC[k], count('licence', r => r.licence === k)]).filter(x => x[2] || st.f.licence.has(x[0]));
    const src = Object.keys(st.sources).map(k => [k, st.sources[k].name]).sort((a, b) => a[1].localeCompare(b[1]));
    el('dtFilters').innerHTML = `<h2>${esc(T('Filters'))}</h2>${facet('domain', T('Topics'), doms, st.f.domain, true)}${facet('holds', T('What it holds'), hd, st.f.holds, true)}${facet('level', T('Geography'), lv, st.f.level, false)}${facet('licence', T('License of the sources (strictest)'), lc, st.f.licence, false)}
      <details class="ws-facet"${st.f.year || st.f.source ? ' open' : ''}><summary>${esc(T('Period and source'))}${icon('expand_more')}</summary>
        <label class="ws-field">${esc(T('Covers year'))}<select id="dtYear"><option value="">${esc(T('Any year'))}</option>${yearOptions(st.snap).map(([v, l]) => `<option value="${esc(v)}"${st.f.year === v ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select></label>
        <label class="ws-field">${esc(T('Source'))}<select id="dtSource"><option value="">${esc(T('Any source'))}</option>${src.map(([v, l]) => `<option value="${esc(v)}"${st.f.source === v ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select></label></details>`;
  }
  function card(r) {
    const d = st.byDom[r.domain] || {}, t = top(r.domain) || d, src = (r.sources || []).map(s => (st.sources[s] || {}).name || s), LV = LEVEL_LABEL(), LC = LICENCE_LABEL(), es = I18N.lang === 'es' && !I18N.has(r.name);
    return `<article class="ws-card"><button type="button" class="ws-card-main" data-open="${esc(r.id)}"><span class="ws-eyebrow">${esc(I18N.name(d))}</span><span class="ws-tile-ic ws-tint-${TINT[t.accent] || 'blue'}">${icon(t.icon || 'dataset')}</span>
      <b${es ? ' lang="en"' : ''}>${esc(label(r))}</b><span class="ws-from">${esc(T('Source'))}: <em translate="no">${esc(src.slice(0, 2).join('; ') || T('the observatory'))}${src.length > 2 ? ' +' + (src.length - 2) : ''}</em></span>
      <span class="ws-foot">${esc(LC[r.licence] || T('License not stated'))} · ${esc(period(r))} · ${esc((r.levels || []).map(l => LV[l] || l).join(', '))}</span></button></article>`;
  }
  function chips() {
    const f = st.f, LV = LEVEL_LABEL(), LC = LICENCE_LABEL(), H = HOLDS(), out = [];
    f.domain.forEach(v => out.push(['domain', v, I18N.name(st.byDom[v] || {})])); f.holds.forEach(v => out.push(['holds', v, H[v]])); f.level.forEach(v => out.push(['level', v, LV[v] || v])); f.licence.forEach(v => out.push(['licence', v, LC[v] || v]));
    if (f.year) out.push(['year', '', T('Covers {year}', { year: f.year === 'future' ? T('projections') : f.year === 'past' ? T('before 2000') : f.year })]);
    if (f.source) out.push(['source', '', (st.sources[f.source] || {}).name || f.source]);
    el('dtChips').innerHTML = out.map(([k, v, l]) => `<button type="button" class="ws-chip" data-unf="${k}" data-v="${esc(v)}">${esc(l)} ${icon('close')}</button>`).join('') + (out.length || st.q ? `<button type="button" class="linklike" id="dtReset">${icon('restart_alt')}${esc(T('Clear filters'))}</button>` : '');
  }
  function list() {
    const by = sorters[st.sort] || sorters.topic, tk = tokens(st.q), inName = (r) => (tk.length && tk.every(t => norm(label(r) + ' ' + r.name).includes(t)) ? 0 : 1);   // a search lists first the entries whose own name holds the words
    const rows = st.rows.filter(r => match(r)).sort((a, b) => inName(a) - inName(b) || by(a, b));
    el('dtCount').textContent = rows.length ? T('{a} to {b} of {n} results', { a: 1, b: Math.min(st.shown, rows.length), n: fmt(rows.length) }) : T('No results');
    el('dtGrid').innerHTML = rows.length ? rows.slice(0, st.shown).map(card).join('') : `<div class="ws-empty-card"><b>${esc(T('Nothing matches these filters.'))}</b><p>${esc(T('Try fewer words, or clear a filter.'))}</p></div>`;
    el('dtMore').hidden = rows.length <= st.shown;
    chips(); hash();
  }
  const draw = () => { filters(); list(); };
  function detail(id) {
    const r = st.rows.find(x => x.id === id); if (!r) return;
    const d = st.byDom[r.domain] || {}, src = (r.sources || []).map(s => st.sources[s] || { name: s }), LV = LEVEL_LABEL(), LC = LICENCE_LABEL(), add = mapHref(r, true), fresh = mapHref(r, false), es = I18N.lang === 'es' && !I18N.has(r.name);
    el('dtDlgTitle').textContent = label(r); if (es) el('dtDlgTitle').lang = 'en'; else el('dtDlgTitle').removeAttribute('lang');
    el('dtDlgBody').innerHTML = `<dl class="ws-dl"><dt>${esc(T('Topic'))}</dt><dd>${esc(I18N.name(d))}</dd><dt>${esc(T('Period'))}</dt><dd>${esc(period(r))}${r.timeline ? ' · ' + esc(I18N.has(r.timeline) ? I18N.t(r.timeline) : r.timeline) : ''}</dd>
      <dt>${esc(T('Geography'))}</dt><dd>${esc((r.levels || []).map(l => LV[l] || l).join(', ') || '—')}</dd><dt>${esc(T('License'))}</dt><dd>${esc(LC[r.licence] || T('License not stated'))}</dd>
      <dt>${esc(T('Sources'))}</dt><dd translate="no">${src.map(s => esc(s.name)).join('<br>') || '—'}</dd></dl>
      <p class="note">${esc(T('The data dictionary gives the full definition, the cautions, how it was computed and how to cite it.'))}</p>
      <div class="btn-row">${add ? `<a class="btn primary" href="${esc(add)}">${icon('add')}${esc(T('Add to my map'))}</a><a class="btn" href="${esc(fresh)}">${icon('map')}${esc(T('New map with it'))}</a>` : `<span class="ws-muted">${esc(T('This entry is documented but has no map layer yet.'))}</span>`}
      <a class="btn" href="dictionary.html#${encodeURIComponent(r.id)}">${icon('menu_book')}${esc(T('Open in the data dictionary'))}</a></div>`;
    if (!el('dtDlg').open) el('dtDlg').showModal();
  }

  // ── The address keeps the search, so a filtered catalog can be shared ───────
  function hash() {
    const f = st.f, o = { q: st.q ? encodeURIComponent(st.q) : '', domain: [...f.domain].join(','), holds: [...f.holds].join(','), level: [...f.level].join(','), licence: [...f.licence].join(','), year: f.year, source: f.source, sort: st.sort === 'topic' ? '' : st.sort };
    const h = write(o); history.replaceState(null, '', location.pathname + location.search + (h.length > 1 ? h : ''));
  }
  function fromHash() {
    const o = parse(location.hash), f = st.f, set = (k, ok) => { f[k] = new Set((o[k] || '').split(',').filter(v => v && ok(v))); };
    try { st.q = o.q ? decodeURIComponent(o.q).slice(0, 120) : ''; } catch (e) { st.q = ''; }
    set('domain', v => !!st.byDom[v]); set('holds', v => v in HOLDS()); set('level', v => v in LEVEL_LABEL()); set('licence', v => v in LICENCE_LABEL());
    f.year = /^(\d{4}|future|past)$/.test(o.year || '') ? o.year : ''; f.source = st.sources[o.source] ? o.source : ''; st.sort = sorters[o.sort] ? o.sort : 'topic';
    el('dtQ').value = st.q; el('dtSort').value = st.sort;
  }
  function wire() {
    let t = 0; el('dtQ').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value.trim(); st.shown = PAGE; draw(); }, 140); });
    el('dtSort').onchange = (e) => { st.sort = e.target.value; list(); };
    el('dtMore').onclick = () => { st.shown += PAGE; list(); };
    el('dtFilterBtn').onclick = () => { const off = document.body.classList.toggle('ws-nofilters'); el('dtFilterBtn').setAttribute('aria-expanded', String(!off)); };
    el('dtFilters').addEventListener('change', (e) => { const c = e.target; if (c.dataset.f) { const s = st.f[c.dataset.f]; c.checked ? s.add(c.value) : s.delete(c.value); } else if (c.id === 'dtYear') st.f.year = c.value; else if (c.id === 'dtSource') st.f.source = c.value; else return; st.shown = PAGE; const open = [...el('dtFilters').querySelectorAll('details')].map(d => d.open); draw(); el('dtFilters').querySelectorAll('details').forEach((d, i) => { d.open = open[i]; }); });
    el('dtChips').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; if (b.id === 'dtReset') { Object.values(st.f).forEach(v => v && v.clear && v.clear()); st.f.year = st.f.source = ''; st.q = ''; el('dtQ').value = ''; } else if (b.dataset.unf === 'year' || b.dataset.unf === 'source') st.f[b.dataset.unf] = ''; else st.f[b.dataset.unf].delete(b.dataset.v); st.shown = PAGE; draw(); });
    el('dtGrid').addEventListener('click', (e) => { const b = e.target.closest('[data-open]'); if (b) detail(b.dataset.open); });
    el('dtDlgClose').onclick = () => el('dtDlg').close(); el('dtDlg').addEventListener('click', (e) => { if (e.target === el('dtDlg')) el('dtDlg').close(); });
    window.addEventListener('hashchange', () => { fromHash(); draw(); });
  }
  async function start() {
    el('dtGrid').innerHTML = `<div class="ws-empty-card" role="status">${esc(T('Loading the catalog…'))}</div>`;
    let cat, ix;
    try { [cat, ix] = await Promise.all([fetchJson('data/catalog.json'), fetchJson('data/catalog_index.json'), I18N.load('catalog').catch(() => null)]); }
    catch (e) { el('dtGrid').innerHTML = `<div class="ws-empty-card" role="alert"><b>${esc(T('The catalog could not be loaded.'))}</b><p>${esc(T('Check your connection.'))}</p><button type="button" class="btn" id="dtRetry">${esc(T('Try again'))}</button></div>`; el('dtRetry').onclick = start; return; }
    if (I18N.lang === 'es') fetchJson('data/catalog_es.json').then(x => { st.words = x.words_es || {}; st.rows.forEach(r => { r._hay = null; }); if (st.q) list(); }, () => null);   // the words of the Spanish summaries, for the search
    const F = ix.index.fields; st.rows = ix.index.rows.map(a => Object.fromEntries(F.map((k, i) => [k, a[i]])));
    st.sources = ix.sources || {}; st.doms = cat.domains.slice().sort((a, b) => a.order - b.order); st.byDom = Object.fromEntries(cat.domains.map(d => [d.id, d]));
    st.snap = +((/(\d{4})/.exec(cat.snapshot || '') || [])[1]) || st.snap;
    const n = (k) => fmt(st.rows.filter(r => holds(r) === k).length);
    el('dtLead').textContent = T('{n} documented entries: {a} datasets by year, {b} map layers and sets of places, and {c} documented only. {snapshot}.', { n: fmt(st.rows.length), a: n('series'), b: n('layer'), c: n('doc'), snapshot: snapshotLabel(cat.snapshot) });
    fromHash(); wire(); draw();
    const want = parse(location.hash).open; if (want) detail(decodeURIComponent(want));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
