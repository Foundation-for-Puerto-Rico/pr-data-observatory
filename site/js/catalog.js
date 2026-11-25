/* PR Data Observatory — Overview and Catalog tabs of the 2D map.
   Loaded after app.js. Reads S.catalog (data/catalog.json, built by catalog.py): the registry's domains with a headline figure and trend for each. The index of the dictionary
   (data/catalog_index.json) and the Spanish of its names (I18N.load('catalog')) load the first time the Catalog tab opens or a card sends you to it (ensure).
   Nothing here names a domain or counts them. The cards, the filters, the top-bar subtitle and the About list are generated from the registry (docs/adding-data.md), so a new domain
   appears everywhere when its object is added to dictionary_src/domains.json. Every visible text goes through T / Tn / Th (docs/i18n.md). */

const Catalog = (() => {
  const START = (() => { const m = /(?:^#|&)topic=([\w.-]+)/.exec(location.hash || ''); return m ? m[1] : null; })();   // #topic=<domain> (a Knowledge Area page's link back): read before the map rewrites its address
  const st = { rows: null, q: '', f: { domain: '', level: '', year: '', licence: '', source: '', mapOnly: true }, limit: 40, ready: false, timer: null };

  // ── Registry helpers ───────────────────────────────────────────────────────
  const doms = () => (S.catalog ? S.catalog.domains : []);
  const byId = () => Object.fromEntries(doms().map(d => [d.id, d]));
  const dname = (id) => { const d = byId()[id]; return d ? I18N.name(d) : id; };
  const dpath = (id) => { const d = byId()[id]; return d && d.parent ? `${dname(d.parent)} › ${dname(id)}` : dname(id); };
  const tintOf = (d) => (/--fpr-(blue|green|yellow|red)\b/.exec(d.accent || '') || [0, 'blue'])[1];
  const tops = () => doms().filter(d => !d.system && !d.parent).sort((a, b) => a.order - b.order);
  const kids = (id) => doms().filter(d => d.parent === id && !d.system).sort((a, b) => a.order - b.order);
  const wantedLeft = (d) => Object.entries(d.wanted || {}).filter(([s]) => s !== 'live').reduce((n, [, v]) => n + v, 0);

  // ── What can go on the map ─────────────────────────────────────────────────
  // An action is ['econ', key, norm] (a yearly series joins the Economy tab), ['layers', 'flood,slr'] (switch layers on).
  function canMap(a) {
    if (!a) return false;
    if (a[0] === 'econ') return true;   // the Economy tab loads its data when it is first used
    if (a[0] === 'layers') return a[1].split(',').every(k => LAYER_KEYS[k]);
    return false;
  }
  async function apply(a) {
    if (!canMap(a) || (a[0] === 'econ' && typeof ECON === 'undefined')) return false;
    if (a[0] === 'econ') {
      if (ECON.api.state().layers.some(l => l.key === a[1])) { toast(T('That is already on the map. Change it in the On the map panel.'), 5000); return true; }   // a second copy would only stack on the first
      const r = await ECON.api.show({ clear: false, stay: true, layers: [{ key: a[1], mode: 'fill', ...(a[2] === 'count' ? { norm: 'value' } : a[2] && a[2] !== 'value' ? { norm: a[2] } : {}) }] });   // 'value': the Economy tab picks the shading that suits the series; 'count': the count as published (Comunidades Especiales: per resident means little)
      if (!r.applied.length) toast(T('That could not be put on the map. Find it in Home to add it.'), 5000);
      return r.applied.length > 0;
    }
    let n = 0;
    const loadsListings = a[1].split(',').includes('places') && !S.placesLoaded;   // the page says "Loading tourism places…" itself: do not cover it
    for (const k of a[1].split(',')) { const el = $('#' + LAYER_KEYS[k]); if (el && !el.checked) { el.checked = true; el.dispatchEvent(new Event('change')); n++; } }
    refreshFolds();
    if (!loadsListings) toast(n ? T('Switched on. You can turn it off in the On the map panel.') : T('That layer is already on.'), 4500);
    if (isMobile()) setPanel(false);
    return true;
  }

  // ── Ready-made views of a topic (navigation plan PR 6, decision 81) ────────
  // A view puts a few datasets and layers on the map at once, in place of what was on (as the Analysis tab's presets do). They come with the index
  // (data/catalog_views.json, built by catalog.py from dictionary_src/domains.json), each with the ids of its data sources, named from the index's sources.
  const views = () => st.viewsP || (st.viewsP = fetchJson('data/catalog_views.json').then(x => { S.catalog.presets = x.presets || {}; }, () => { st.viewsP = null; S.catalog.presets = {}; }));   // a topic page draws without them when they do not load
  const VIEW_OFF = () => Object.keys(LAYER_KEYS).filter(k => k !== 'muni' && k !== 'barrios' && k !== 'rings');   // the boundaries and the walk rings are settings: a view leaves them as they are
  const viewsOf = (d) => [d, ...kids(d.id)].flatMap(p => ((S.catalog.presets || {})[p.id] || []).map(v => ({ ...v, dom: p.id })));   // a sub-topic's after the topic's: the visitor economy last
  function viewsHtml(d) {
    const vs = viewsOf(d), src = S.catalog.sources || {};
    if (!vs.length) return '';
    return `<h3 class="sec">${esc(T('Ready-made views'))}</h3><div class="ex-views">${vs.map(v => `<div class="ex-view">
      <button type="button" class="btn small" data-view="${esc(v.dom)}:${esc(v.id)}">${icon('layers', { size: 14 })}${esc(I18N.text(v.name))}</button>
      <p class="note">${esc(I18N.text(v.note))}</p>${v.sources.length ? `<p class="ex-src">${esc(T('Sources:'))} <span translate="no">${esc(v.sources.map(x => (src[x] || {}).name || x).join('; '))}</span></p>` : ''}</div>`).join('')}</div>`;
  }
  async function applyView(dom, id) {
    const v = ((S.catalog.presets || {})[dom] || []).find(x => x.id === id);
    if (!v || typeof ECON === 'undefined') return false;
    const r = await ECON.api.show({ clear: true, stay: true, layers: v.show.map(([key, mode, o]) => ({ key, mode, ...(o || {}) })) });
    if (v.show.length && !r.applied.length) { toast(T('That could not be put on the map. Find it in Home to add it.'), 5000); return false; }
    const want = new Set(v.on);
    for (const k of VIEW_OFF()) { const el = $('#' + LAYER_KEYS[k]); if (el && el.checked !== want.has(k)) { el.checked = want.has(k); el.dispatchEvent(new Event('change')); } }
    refreshFolds();
    toast(T('Showing “{name}”, in place of what was on the map. Change it in the On the map panel.', { name: I18N.text(v.name) }), 6000);
    if (isMobile()) setPanel(false);
    return true;
  }

  // ── Overview: one card per domain ──────────────────────────────────────────
  function valText(h, v) {
    if (v == null) return '—';
    const n = fmt(v, h.d || 0);
    return h.unit === '$' ? '$' + n : h.unit === '%' ? n + '%' : n;
  }
  function periodText(h) {
    const p = h.period || {};
    if (p.type === 'window') return T('{first}–{last}, five-year estimate', { first: p.first, last: p.last });
    if (p.type === 'year') return String(p.year);
    if (p.type === 'event') return T('{year}, by year of declaration', { year: p.year });
    if (p.type === 'snapshot') return snapshotLabel(S.catalog.snapshot);
    return '';
  }
  const labelOf = (h) => I18N.text(h.label) || T(h.name || h.variable);
  const tName = (n) => I18N.has(n) ? T(n) : n;   // the name of a dictionary entry in the page language when it has Spanish; else English, and not listed in I18N.missed (docs/i18n.md)
  const nameHtml = (n) => { const t = tName(n); return t === n ? I18N.en(esc(t)) : esc(t); };   // an entry name that has no Spanish is English text in a Spanish page
  const named = (label, name) => esc(T('{label}: {name}', { label, name }));   // for aria-label: "Show on map: Median monthly gross rent"
  const pressedFocus = (id) => { const el = $(id); if (el) el.focus({ preventScroll: true }); };   // after a button sends you to another tab, focus follows
  function spark(h) {   // a trend of the Puerto Rico figure; the value and the period are in the text beside it
    if (!h.series || h.series.length < 2) return '';
    const W = 96, H = 26, xs = h.series.map(p => p[0]), ys = h.series.map(p => p[1]);
    const x0 = xs[0], x1 = xs[xs.length - 1], lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
    const px = (x) => 3 + (x - x0) / ((x1 - x0) || 1) * (W - 6), py = (y) => H - 3 - (y - lo) / span * (H - 6);
    const last = h.series[h.series.length - 1];
    const alt = T('Trend of {name}, Puerto Rico, {from} to {to}: from {a} to {b}', { name: labelOf(h), from: x0, to: x1, a: valText(h, h.series[0][1]), b: valText(h, last[1]) });
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(alt)}"><polyline points="${h.series.map(p => `${px(p[0]).toFixed(1)},${py(p[1]).toFixed(1)}`).join(' ')}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${px(last[0]).toFixed(1)}" cy="${py(last[1]).toFixed(1)}" r="2.3" fill="currentColor"/></svg>`;
  }
  function metricHtml(h, d, sub) {
    const act = canMap(h.map);
    return `<div class="dm">
      <div class="dm-name">${sub ? `<span class="dm-sub">${esc(dname(d.id))}</span>` : ''}${esc(labelOf(h))}</div>
      <div class="dm-line"><b class="dm-val">${esc(valText(h, h.value))}</b>${spark(h)}</div>
      <div class="dm-per">${esc(T('Puerto Rico · {period}', { period: periodText(h) }))}</div>
      <div class="dm-act">${act ? `<button type="button" class="btn small" data-show="${esc(h.variable)}" aria-label="${named(T('Show on map'), labelOf(h))}">${icon('map', { size: 14 })}${esc(T('Show on map'))}</button>` : ''}<a href="dictionary.html#${esc(h.dict)}" aria-label="${named(T('What it means'), labelOf(h))}">${esc(T('What it means'))}</a></div>
    </div>`;
  }
  function cardHtml(d) {
    const heads = [d.headline && { h: d.headline, d, sub: false }, ...kids(d.id).map(k => k.headline && { h: k.headline, d: k, sub: true })].filter(Boolean);
    const status = d.status === 'planned' ? T('No data yet') : d.status === 'partial' ? T('Some data') : '';
    const left = wantedLeft(d);
    const plannedBtn = left ? `<button type="button" class="linklike" data-planned="${esc(d.id)}" aria-expanded="false" aria-controls="pl-${esc(d.id)}" aria-label="${named(T('What is planned'), I18N.name(d))}">${esc(T('What is planned'))}</button>` : '';
    const empty = heads.length ? '' : `<p class="dc-empty">${esc(d.status === 'planned' ? T('No data yet.') : T('No headline figure yet.'))} ${left ? esc(Tn(left, '{n} dataset is on the wish list.', '{n} datasets are on the wish list.', { n: fmt(left) })) : ''} ${plannedBtn}</p>`;
    const more = d.entries ? (() => { const t = Tn(d.entries, 'Browse {n} documented item', 'Browse {n} documented items', { n: fmt(d.entries) }); return `<button type="button" class="linklike" data-browse="${esc(d.id)}" aria-label="${named(t, I18N.name(d))}">${esc(t)}</button>`; })() : '';
    const open = `<button type="button" class="btn small" data-open-dom="${esc(d.id)}" aria-label="${named(T('Open the topic'), I18N.name(d))}">${icon('explore', { size: 14 })}${esc(T('Open the topic'))}</button>`;
    const foot = [open, more, heads.length ? plannedBtn : ''].filter(Boolean).join(' ');
    return `<article class="dom-card" data-tint="${tintOf(d)}" aria-labelledby="dc-${esc(d.id)}">
      <header class="dc-head"><span class="ms-icon dc-ic" aria-hidden="true">${esc(d.icon)}</span><h3 id="dc-${esc(d.id)}">${esc(I18N.name(d))}</h3>${status ? `<span class="dc-status">${esc(status)}</span>` : ''}</header>
      <p class="dc-desc">${esc(I18N.text(d.description))}</p>
      ${heads.map(x => metricHtml(x.h, x.d, x.sub)).join('')}${empty}
      ${foot ? `<div class="dc-foot">${foot}</div>` : ''}
      <div class="dc-planned" id="pl-${esc(d.id)}" hidden></div>
    </article>`;
  }
  function renderOverview() {
    const root = $('#ovCards');
    if (!S.catalog) { root.innerHTML = `<div class="note">${Th('The overview could not be loaded. The <a href="dictionary.html">data dictionary</a> lists everything the observatory holds, and the other tabs still work.')}</div>`; return; }
    root.innerHTML = tops().map(cardHtml).join('');
    $('#ovFoot').textContent = T('Each figure is for the whole of Puerto Rico and comes from the data named in the dictionary entry behind “What it means”. A figure for tourism places counts listings with confidence 0.50 or higher, places of worship left out, not businesses. {snapshot}.', { snapshot: snapshotLabel(S.catalog.snapshot) });
  }

  // ── Explore: a domain's page and the search across all the data (navigation plan PR 3, decision 81) ──
  // A domain's page lists what can go on the map whose home is the domain or one of its sub-domains, by area (figures by municipio, barrio or tract) and as
  // points, lines and areas, then what is also in the domain, its Knowledge Area pages, and everything in the Catalog. It reads the Catalog's index (ensure).
  const inDom = (id, x) => x === id || String(x).startsWith(id + '.');
  const byName = (a, b) => a._shown.localeCompare(b._shown, I18N.lang);
  const exBox = (show) => { $('#exDomain').hidden = show !== 'dom'; $('#exResults').hidden = show !== 'find'; $('#ovCards').hidden = !!show; };
  function openDomain(id, opts = {}) {
    const d = byId()[id]; if (!d) return false;
    if (!opts.stay) showTab('overview');
    const box = $('#exDomain'); exBox('dom'); $('#exQ').value = '';
    box.innerHTML = `<div class="note" role="status">${esc(T('Loading…'))}</div>`;
    Promise.all([ensure(), views()]).then(() => { renderDomain(d); const h = box.querySelector('h2'); if (h && !opts.stay) h.focus({ preventScroll: false }); }, () => { box.innerHTML = `<div class="note">${esc(T('The list could not be loaded. Try again in a moment.'))}</div>`; });
    return true;
  }
  function renderDomain(d) {
    const R = rows().filter(o => canMap(o.map)), parts = [d, ...kids(d.id)];
    const list = (items) => items.sort(byName).map(rowHtml).join('');
    const block = (title, items) => items.length ? `<h3 class="sec">${esc(title)} <span class="ec-count">${fmt(items.length)}</span></h3>${list(items)}` : '';
    let body = '';
    for (const p of parts) {
      const mine = R.filter(o => o.domain === p.id), area = mine.filter(o => o.map[0] !== 'layers'), pts = mine.filter(o => o.map[0] === 'layers');
      if (!mine.length) continue;
      if (p !== d) body += `<h3 class="ex-sub">${esc(dname(p.id))}</h3>`;
      body += block(T('By area'), area) + block(T('Points, lines and areas'), pts);
    }
    const also = R.filter(o => !parts.some(p => p.id === o.domain) && o.domains.some(x => inDom(d.id, x)));
    const ka = (d.knowledge || []).map(a => `<li><a href="${esc(a.page)}"><span class="ms-icon" aria-hidden="true">${esc(a.icon)}</span>${esc(I18N.text(a.label))}</a></li>`).join('');
    $('#exDomain').innerHTML = `<button type="button" class="linklike ex-back" data-ex-back="1">${icon('arrow_back', { size: 14 })}${esc(T('All topics'))}</button>
      <h2 tabindex="-1"><span class="ms-icon" aria-hidden="true">${esc(d.icon)}</span> ${esc(I18N.name(d))}</h2><p class="note">${esc(I18N.text(d.description))}</p>
      ${viewsHtml(d)}
      ${body || `<div class="note">${esc(T('Nothing in this topic can go on the map yet.'))}</div>`}
      ${also.length ? `<details class="ex-also"><summary>${esc(T('Also in this topic'))} <span class="ec-count">${fmt(also.length)}</span></summary>${list(also)}</details>` : ''}
      ${ka ? `<h3 class="sec">${esc(T("FPR's analyses on this topic"))}</h3><ul class="plain-list ex-ka">${ka}</ul>` : ''}
      <div class="btn-row"><button type="button" class="btn" data-browse="${esc(d.id)}">${icon('table_view', { size: 14 })}${esc(T('Everything in the Catalog'))}</button></div>`;
  }
  function find(q) {   // the search box of Explore: what can go on the map, and the Knowledge Area pages, across every topic
    const toks = norm(q).split(/\s+/).filter(Boolean);
    if (!toks.length) { exBox(null); return; }
    exBox('find'); const box = $('#exResults');
    ensure().then(() => {
      const sc = (o) => toks.reduce((s, t) => s + (o._name.includes(t) ? 4 : 0) + (norm(o.id).includes(t) ? 1 : 0), 0);
      const hits = rows().filter(o => canMap(o.map) && toks.every(t => o._hay.includes(t))).sort((a, b) => sc(b) - sc(a) || byName(a, b));
      const ka = doms().flatMap(d => (d.knowledge || []).filter(a => toks.every(t => norm(I18N.text(a.label)).includes(t))));
      box.innerHTML = `<p class="note">${esc(Tn(hits.length, '{n} map found', '{n} maps found', { n: fmt(hits.length) }))}</p>`
        + (ka.length ? `<ul class="plain-list ex-ka">${ka.map(a => `<li><a href="${esc(a.page)}"><span class="ms-icon" aria-hidden="true">${esc(a.icon)}</span>${esc(I18N.text(a.label))}</a></li>`).join('')}</ul>` : '')
        + hits.slice(0, 30).map(rowHtml).join('')
        + (hits.length > 30 ? `<div class="btn-row"><button type="button" class="btn" data-ex-all="1">${esc(T('See all in the Catalog'))}</button></div>` : '');
    }, () => { box.innerHTML = `<div class="note">${esc(T('The list could not be loaded. Try again in a moment.'))}</div>`; });
  }

  // What is planned: the wanted datasets of a field (site/data/wanted.json, a candidate list: source, license and terms are still to be confirmed before anything is harvested).
  const WANTED_STATUS = () => ({ candidate: T('Candidate'), checked: T('Checked'), building: T('Building'), blocked: T('Blocked') });   // a dataset already live is not listed as planned
  async function togglePlanned(btn) {
    const box = $('#pl-' + btn.dataset.planned), open = box.hidden;
    btn.setAttribute('aria-expanded', String(open)); box.hidden = !open;
    if (!open || box.dataset.ready) return;
    box.innerHTML = `<div class="note">${esc(T('Loading…'))}</div>`;
    try {
      st.wanted = st.wanted || await fetchJson('data/wanted.json');
      const id = btn.dataset.planned, labels = WANTED_STATUS();
      const rows = st.wanted.items.filter(i => i.status !== 'live' && (i.domain === id || String(i.domain).startsWith(id + '.')));
      box.innerHTML = `<ul class="plain-list">${rows.map(i => `<li><b>${esc(i.title)}</b> <span class="tag">${esc(labels[i.status] || i.status)}</span><br><small>${esc(i.source || '')}</small></li>`).join('')}</ul><div class="note">${esc(T('A wish list, not a promise: each source, license and the terms of use are checked before anything is added. The titles are in English for now.'))}</div>`;
      box.dataset.ready = '1';
    } catch { box.innerHTML = `<div class="note">${esc(T('The list could not be loaded. Try again in a moment.'))}</div>`; }
  }

  // ── Catalog: find data and put it on the map ───────────────────────────────
  const snapYear = () => +String((S.catalog || {}).built || '').slice(0, 4) || 2026;
  function rows() {   // once the index is in (ensure). A Spanish page also finds an entry by its Spanish name and by the words of its Spanish summary (data/catalog_es.json)
    if (st.rows) return st.rows;
    const { fields, rows: raw } = S.catalog.index, es = I18N.lang === 'es';
    st.rows = raw.map(r => { const o = {}; fields.forEach((f, i) => { o[f] = r[i]; }); o.domains = o.domains || [o.domain]; o._shown = tName(o.name); o._name = norm(o._shown); o._hay = norm([o.name, es ? o._shown : '', o.id, (o.domains || []).map(dname).join(' '), o.ask ? [...(o.ask.en || []), ...(o.ask.es || [])].join(' ') : '', es ? st.es[o.id] || '' : ''].join(' ')); return o; });
    return st.rows;
  }
  // The index, the Spanish of its names (with the terrain and climate names of the module econ_terrain, which economy.js also loads) and, on a Spanish page, the words of the Spanish summaries, on first use; the filters that come from the index are filled
  // once all are in. A failure can be tried again.
  function ensure() {
    const words = () => I18N.lang !== 'es' || st.es ? null : fetchJson('data/catalog_es.json').then(x => { st.es = x.words_es || {}; });
    return st.ixP || (st.ixP = allIn([withIndex(S.catalog), I18N.load('catalog'), I18N.load('econ_terrain').catch(() => null), words()]).then(() => { if (!st.filled) { st.filled = true; fillFilters(); syncControls(); } }, e => { st.ixP = null; throw e; }));
  }
  function list() {   // the list once the index is in: "Loading…" until then, and a message when it could not be loaded
    if (st.filled) { renderList(); return; }
    if (!S.catalog) return;
    $('#catList').innerHTML = `<div class="note" role="status">${esc(T('Loading…'))}</div>`;
    ensure().then(renderList, () => { st.listed = false; $('#catList').innerHTML = `<div class="note">${esc(T('The list could not be loaded. Try again in a moment.'))}</div>`; });
  }
  const sel = (id, first, opts) => { $(id).innerHTML = `<option value="">${esc(first)}</option>` + opts.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join(''); };
  function fillDomains() {   // from the registry, before the index
    const order = doms().slice().sort((a, b) => (a.system - b.system) || (a.parent ? 1 : 0) - (b.parent ? 1 : 0) || a.order - b.order);
    const ds = []; for (const d of order.filter(x => !x.parent)) { ds.push([d.id, dpath(d.id)]); order.filter(x => x.parent === d.id).forEach(k => ds.push([k.id, '— ' + dname(k.id)])); }
    sel('#catDomain', T('All domains'), ds);
  }
  function fillFilters() {   // from the index
    const R = rows();
    const levels = LEVEL_LABEL(), seenL = [...new Set(R.flatMap(r => r.levels))].filter(l => levels[l]);
    sel('#catLevel', T('Any geography'), seenL.map(l => [l, levels[l]]));
    sel('#catYear', T('Any year'), yearOptions(snapYear()));
    const lic = LICENCE_LABEL(); sel('#catLicence', T('Any license'), Object.keys(lic).filter(c => R.some(r => r.licence === c)).map(c => [c, lic[c]]));
    const srcs = S.catalog.sources || {}, used = new Set(R.flatMap(r => r.sources));
    sel('#catSource', T('Any source'), Object.entries(srcs).filter(([id]) => used.has(id)).sort((a, b) => a[1].name.localeCompare(b[1].name)).map(([id, s]) => [id, s.name.length > 48 ? s.name.slice(0, 46) + '…' : s.name]));
    if (I18N.lang !== 'en') $('#catLang').hidden = false;
  }
  function results() {
    const f = st.f, toks = norm(st.q).split(/\s+/).filter(Boolean);
    const ok = (o) => (!f.mapOnly || canMap(o.map)) && (!f.domain || o.domains.some(x => x === f.domain || x.startsWith(f.domain + '.'))) && (!f.level || o.levels.includes(f.level)) &&
      coversYear(o.years, f.year, snapYear()) && (!f.licence || o.licence === f.licence) && (!f.source || o.sources.includes(f.source)) && toks.every(t => o._hay.includes(t));
    const out = rows().filter(ok);
    const order = Object.fromEntries(doms().map((d, i) => [d.id, i]));
    if (toks.length) { const sc = (o) => toks.reduce((s, t) => s + (norm(o.name).includes(t) || o._name.includes(t) ? 4 : 0) + (norm(o.id).includes(t) ? 2 : 0), 0); out.sort((a, b) => sc(b) - sc(a) || a._shown.localeCompare(b._shown)); }
    else out.sort((a, b) => (order[a.domain] ?? 99) - (order[b.domain] ?? 99) || a.name.localeCompare(b.name));
    return out;
  }
  function rowHtml(o) {
    const lv = LEVEL_LABEL(), lic = LICENCE_LABEL(), d = byId()[o.domain];
    const meta = [o.years ? (o.years[0] === o.years[1] ? String(o.years[0]) : `${o.years[0]}–${o.years[1]}`) : '', o.levels.map(l => lv[l]).filter(Boolean).join(', '), lic[o.licence] || ''].filter(Boolean).join(' · ');
    return `<div class="cat-row"><div class="cr-main"><b class="cr-name">${nameHtml(o.name)}</b>
      <div class="cr-meta">${d ? `<span class="ms-icon" aria-hidden="true">${esc(d.icon)}</span> ` : ''}${esc(dpath(o.domain))}${meta ? ' · ' + esc(meta) : ''}</div></div>
      <div class="cr-act">${canMap(o.map) ? `<button type="button" class="btn small" data-add="${esc(o.id)}" aria-label="${esc(T('Add to map: {name}', { name: tName(o.name) }))}">${icon('add', { size: 14 })}${esc(T('Add to map'))}</button>` : ''}<a href="dictionary.html#${esc(o.id)}" aria-label="${named(T('Details'), tName(o.name))}">${esc(T('Details'))}</a></div></div>`;
  }
  function renderList() {
    const all = results(), shown = all.slice(0, st.limit), f = st.f;
    $('#catCount').textContent = T('{n} of {m} items', { n: fmt(all.length), m: fmt(rows().length) });
    $('#catList').innerHTML = shown.length ? shown.map(rowHtml).join('') : `<div class="note">${esc(T('Nothing matches. Try fewer words, or reset the filters. If a dataset is missing from the observatory, ask the chat “What data is missing?”.'))}</div>`;
    $('#catMoreRow').hidden = all.length <= shown.length;
    const q = new URLSearchParams(); if (st.q) q.set('q', st.q); if (f.domain) q.set('domain', f.domain);
    $('#catDict').href = 'dictionary.html' + (q.toString() ? '?' + q : '') + '#browse';
  }
  function syncControls() {
    const f = st.f; $('#catQ').value = st.q; $('#catDomain').value = f.domain; $('#catLevel').value = f.level; $('#catYear').value = f.year; $('#catLicence').value = f.licence; $('#catSource').value = f.source; $('#catMapOnly').checked = f.mapOnly;
  }
  function wire() {
    const again = () => { st.limit = 40; list(); };
    $('#catQ').addEventListener('input', e => { st.q = e.target.value; clearTimeout(st.timer); st.timer = setTimeout(again, 120); });
    for (const [id, key] of [['#catDomain', 'domain'], ['#catLevel', 'level'], ['#catYear', 'year'], ['#catLicence', 'licence'], ['#catSource', 'source']]) $(id).addEventListener('change', e => { st.f[key] = e.target.value; again(); });
    $('#catMapOnly').addEventListener('change', e => { st.f.mapOnly = e.target.checked; again(); });
    $('#catReset').addEventListener('click', () => { st.q = ''; st.f = { domain: '', level: '', year: '', licence: '', source: '', mapOnly: true }; syncControls(); again(); });
    $('#catMore').addEventListener('click', () => { st.limit += 40; renderList(); });
    $('#catList').addEventListener('click', async e => {
      const b = e.target.closest('[data-add]'); if (!b) return;
      const o = rows().find(r => r.id === b.dataset.add); if (o) await apply(o.map);
    });
    $('#exQ').addEventListener('input', e => { clearTimeout(st.exT); st.exT = setTimeout(() => find(e.target.value), 150); });
    $('#tab-overview').addEventListener('click', async e => {
      const o = e.target.closest('[data-open-dom]'); if (o) { openDomain(o.dataset.openDom); return; }
      const m = e.target.closest('#exDomain [data-browse]'); if (m) { browse(m.dataset.browse); return; }
      if (e.target.closest('[data-ex-back]')) { exBox(null); pressedFocus('#exQ'); return; }
      const w = e.target.closest('#exDomain [data-view]'); if (w) { const [dom, id] = w.dataset.view.split(':'); await applyView(dom, id); return; }
      if (e.target.closest('[data-ex-all]')) { st.q = $('#exQ').value; st.f = { domain: '', level: '', year: '', licence: '', source: '', mapOnly: true }; st.limit = 40; syncControls(); list(); showTab('catalog'); return; }
      const b = e.target.closest('#exDomain [data-add], #exResults [data-add]'); if (b) { const r = rows().find(x => x.id === b.dataset.add); if (r) await apply(r.map); }
    });
    $('#ovCards').addEventListener('click', async e => {
      const s = e.target.closest('[data-show]');
      if (s) { const h = doms().map(d => d.headline).find(x => x && x.variable === s.dataset.show); if (h) await apply(h.map); return; }
      const m = e.target.closest('[data-browse]'); if (m) { browse(m.dataset.browse); return; }
      const p = e.target.closest('[data-planned]'); if (p) await togglePlanned(p);
    });
    document.addEventListener('click', e => { const g = e.target.closest('[data-tab-go]'); if (g) { e.preventDefault(); showTab(g.dataset.tabGo); if (g.dataset.tabGo === 'catalog') pressedFocus('#catQ'); } });
  }
  function browse(domainId) {   // from a card: every documented item of the domain, whether or not it can go on the map
    st.q = ''; st.f = { domain: domainId, level: '', year: '', licence: '', source: '', mapOnly: false }; st.limit = 40; syncControls(); list(); showTab('catalog'); pressedFocus('#catQ');
  }

  // ── Places that list domains: generated from the registry ──────────────────
  function subtitle() {   // the top bar's line under the name
    const el = $('#brandSub'); if (!el || !S.catalog) return;
    const names = tops().map(d => I18N.name(d)); if (names.length) el.textContent = names.join(' · ');
  }
  function aboutList() {
    const el = $('#aboutDomains'); if (!el) return;
    if (!S.catalog) { el.innerHTML = `<li>${esc(T('The list of fields could not be loaded.'))}</li>`; return; }
    el.innerHTML = tops().map(d => `<li><b>${esc(I18N.name(d))}:</b> ${esc(I18N.text(d.description))}${d.status === 'planned' ? ` <i>${esc(T('(no data yet)'))}</i>` : ''}</li>`).join('');
  }

  function init() {
    if (st.ready) return; st.ready = true;
    renderOverview();
    aboutList();
    if (S.catalog) { fillDomains(); syncControls(); subtitle(); }
    wire();
    if (START && S.catalog && byId()[START]) openDomain(START);
  }
  function shown(name) {   // a tab was opened
    if (name === 'catalog' && S.catalog && !st.listed) { st.listed = true; list(); }
  }
  // the levels (municipio, barrio, tract, block-group) the dictionary says an entry exists at; none before the index is in (the Economy tab waits for it: ecLoad)
  const levelsOf = (id) => { const ix = S.catalog && S.catalog.index; if (!ix) return []; if (!st.levels) { const F = ix.fields; st.levels = new Map(ix.rows.map(r => [r[F.indexOf('id')], r[F.indexOf('levels')]])); } return st.levels.get(id) || []; };
  return { init, shown, apply, canMap, browse, levelsOf, ensure, openDomain, homeOf: (id) => { const r = st.rows && st.rows.find(x => x.id === id); return r ? r.domain : null; }, names: () => tops().map(d => I18N.name(d)) };
})();

const _catPrevReady = window.onMapReady;
window.onMapReady = async function () { Catalog.init(); if (_catPrevReady) await _catPrevReady(); };
