/* PR Data Observatory: the map workspace (docs/workspace.md). Loaded with the 2D map, after app.js and econ_shell.js.

   It adds four things around the map and computes no statistic of its own; every figure comes from the engine (js/core/, through ECON.api):

     the project bar   the map's name, Undo and Redo, Copy link, Save and My maps (kept in this browser only)
     the timeline      one slider for the year of every dataset on the map; each layer says the period it really shows
     the Insights      key figure, over time, spread, by region, highest and lowest, for one dataset on the map, with filters that say what they count
     the grip          drag the top edge of the workbench to resize it

   The engine loads on first use (js/econ_shell.js), so the timeline and the widgets wait for it: until a dataset is on the map they say what to do.
   The year lives where it always did (EC.year, ey= in the address): the timeline is a new control for it, not a second state. */
(function () {
  'use strict';
  const el = (id) => document.getElementById(id);
  const html = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const icon = (n) => `<span class="ms-icon" aria-hidden="true">${n}</span>`;
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } } };
  const engine = () => (window.ECON && !window.ECON.shell ? window.ECON.api : null);   // null until the engine has loaded
  const reduced = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const say = (msg, ms) => { if (typeof toast === 'function') toast(msg, ms || 3500); };

  // ── What is on the map, as the engine sees it ────────────────────────────────
  let years = [], ready = false;
  const state = () => { const a = engine(); return a ? a.state() : { year: null, layers: [] }; };
  const meta = (key) => { const a = engine(); return a ? a.meta(key) : null; };
  const maxYear = () => years[years.length - 1], minYear = () => years[0];
  const shownYear = () => { const y = state().year; return y == null ? maxYear() : y; };
  /** The period a dataset shows for the year of the timeline, in the engine's own words (js/core/engine.js, E.chip). */
  function period(key) {
    const v = meta(key); if (!v || !window.Core || !Core.time) return null;
    const y = state().year, r = Core.time.resolve(v, y), lab = Core.time.label(v, r.y);
    if (r.y == null) return { text: T('no data'), kind: 'none' };
    if (Core.time.isFixed(v)) return { text: T('snapshot {year}', { year: lab }), kind: 'fixed' };
    if (r.exact) return { text: lab, kind: 'exact' };
    if (r.early) return { text: T('first data {year}', { year: lab }), kind: 'early' };
    return { text: T('{year} (latest at or before {max})', { year: lab, max: y }), kind: 'before' };
  }

  // ── The timeline ─────────────────────────────────────────────────────────────
  const TL = { timer: null, raf: 0, want: null, pending: false };
  function tlBuild() {
    const a = engine(); if (!a) return;
    years = a.years(); ready = years.length > 0;
    const r = el('wtRange'); r.min = 0; r.max = Math.max(0, years.length - 1); r.step = 1; r.disabled = !ready;
    ['wtPrev', 'wtNext', 'wtPlay', 'wtLatest', 'wtSpeed'].forEach(id => { el(id).disabled = !ready; });
    tlTicks(); tlSync();
  }
  /** Ticks under the slider: one for each year the data has, a label on as many as fit. A year no layer on the map has data for is drawn lighter. */
  function tlTicks() {
    const box = el('wtTicks'); if (!ready) { box.innerHTML = ''; return; }
    const w = box.clientWidth || 600, n = years.length, every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(w / 46))));
    const have = new Set(); state().layers.forEach(l => { const v = meta(l.key); if (v && v.ys && !Core.time.isFixed(v)) v.ys.forEach(y => have.add(y)); });
    box.innerHTML = years.map((y, i) => { const lab = i === n - 1 || (i % every === 0 && n - 1 - i >= every * 0.6); return `<i class="${have.size && !have.has(y) ? 'none' : ''}${lab ? ' lab' : ''}" style="left:${n > 1 ? (i / (n - 1) * 100).toFixed(3) : 50}%">${lab ? `<b>${y}</b>` : ''}</i>`; }).join('');
  }
  /** Bring the control in line with the engine's year (it can change from the chat, a link, the legend's "Match periods" or a saved map). */
  function tlSync() {
    const st = state(), latest = st.year == null, y = shownYear(), r = el('wtRange');
    if (ready) { const i = Math.max(0, years.indexOf(y) < 0 ? years.findIndex(x => x >= y) : years.indexOf(y)); if (!TL.pending) r.value = i < 0 ? years.length - 1 : i; }
    const text = !ready ? T('Timeline') : latest ? T('Latest ({year})', { year: y }) : String(y);
    el('wtLabel').textContent = text;
    r.setAttribute('aria-valuetext', ready ? (latest ? T('Latest available, {year}', { year: y }) : String(y)) : T('No dataset with years on the map'));
    el('wtLatest').setAttribute('aria-pressed', String(ready && latest));
    el('wtPrev').disabled = !ready || y <= minYear(); el('wtNext').disabled = !ready || (y >= maxYear() && !latest ? true : y >= maxYear());
    // each layer's real period: a 2020–2024 survey estimate is never called a 2026 observation
    const moving = st.layers.filter(l => l.visible !== false), box = el('wtLayers');
    if (!engine()) box.innerHTML = `<span class="wt-hint">${html(T('Put a dataset on the map to use the timeline.'))} <button type="button" class="linklike" id="wtChoose">${html(T('Choose a dataset'))}</button></span>`;
    else if (!moving.length) box.innerHTML = `<span class="wt-hint">${html(T('No dataset on the map yet. The timeline sets the year of every dataset you add.'))} <button type="button" class="linklike" id="wtChoose">${html(T('Choose a dataset'))}</button></span>`;
    else box.innerHTML = moving.map(l => { const p = period(l.key), v = meta(l.key); return p ? `<span class="wt-chip ${p.kind}" title="${html(T(v.label))}: ${html(p.text)}"><b>${html(T(v.label))}</b> ${html(p.text)}</span>` : ''; }).join('')
      + (moving.some(l => { const p = period(l.key); return p && p.kind === 'before'; }) ? `<span class="wt-hint">${html(T('A layer with no data for the chosen year shows its latest earlier period. Nothing is estimated between years.'))}</span>` : '');
    const c = el('wtChoose'); if (c) c.onclick = () => { if (typeof showTab === 'function') showTab('economy'); };
    tlModes();
  }
  /** The other clocks of the map are not years and keep their own controls: the timeline only says so. */
  function tlModes() {
    const out = [], slr = el('lySlr'), now = el('lyNow');
    if (slr && slr.checked) out.push(T('Sea level rise: {feet} ft, a scenario and not a year (set it in Map layers, Hazards).', { feet: el('slr').value }));
    if (now && now.checked) out.push(T('Vehicles on their timetable now: a schedule estimate in Puerto Rico time, not live positions.'));
    const m = el('wtModes'); m.hidden = !out.length; document.body.classList.toggle('ws-modes', out.length > 0); m.innerHTML = out.map(t => `<span>${icon('info')}${html(t)}</span>`).join('');
  }
  /** Set the year. `i` is an index of `years`, or null for the latest. Rapid moves are applied once per frame and only the last one wins. */
  function tlSet(i, playing) {
    if (!ready) return;
    if (!playing) tlStop();
    TL.want = i; TL.pending = true;
    if (TL.raf) return;
    TL.raf = requestAnimationFrame(() => {
      TL.raf = 0; const want = TL.want; TL.pending = false;   // the value asked for last: a drag that crossed five years draws once, at the fifth
      const a = engine(); if (!a) return;
      const y = want == null ? null : years[Math.max(0, Math.min(years.length - 1, want))];
      if (y === state().year) { tlSync(); return; }
      a.setYear(y);   // the engine redraws the map, the legend, the cards and the workbench; its render calls back into onChange() below
    });
  }
  function tlStep(d) { if (!ready) return; const i = years.indexOf(shownYear()); tlSet(Math.max(0, Math.min(years.length - 1, (i < 0 ? years.length - 1 : i) + d))); }
  function tlStop() { if (TL.timer) { clearInterval(TL.timer); TL.timer = null; } const b = el('wtPlay'); if (b) { b.innerHTML = icon('play_arrow'); b.setAttribute('aria-label', T('Play the years')); b.title = T('Play the years'); b.setAttribute('aria-pressed', 'false'); } const l = el('wtLabel'); if (l) l.setAttribute('aria-live', 'polite'); }
  function tlPlay() {
    if (TL.timer) { tlStop(); return; }
    if (!ready || years.length < 2) return;
    let i = years.indexOf(shownYear()); if (i < 0 || i >= years.length - 1) i = 0;
    const b = el('wtPlay'); b.innerHTML = icon('pause'); b.setAttribute('aria-label', T('Pause')); b.title = T('Pause'); b.setAttribute('aria-pressed', 'true');
    el('wtLabel').setAttribute('aria-live', 'off');   // a screen reader is not read every year of a playback; the slider's value is still there to ask for
    tlSet(i, true);
    const ms = Math.max(reduced() ? 2000 : 0, +el('wtSpeed').value || 1200);   // reduced motion: never faster than one step every two seconds
    TL.timer = setInterval(() => { i++; if (i > years.length - 1) { tlStop(); return; } tlSet(i, true); }, ms);
  }
  function tlWire() {
    const r = el('wtRange');
    r.addEventListener('input', () => tlSet(+r.value));
    el('wtPrev').onclick = () => tlStep(-1); el('wtNext').onclick = () => tlStep(1);
    el('wtPlay').onclick = tlPlay; el('wtLatest').onclick = () => tlSet(null);
    el('wtSpeed').onchange = () => { store.set('twin.ws.speed', el('wtSpeed').value); if (TL.timer) { tlStop(); tlPlay(); } };
    const sp = store.get('twin.ws.speed', null); if (sp && [...el('wtSpeed').options].some(o => o.value === String(sp))) el('wtSpeed').value = String(sp);
    if (reduced()) el('wtSpeed').value = '2000';
    window.addEventListener('resize', () => { if (ready) tlTicks(); });
    document.addEventListener('visibilitychange', () => { if (document.hidden) tlStop(); });
    tlStop(); tlSync();
  }

  // ── The widgets ──────────────────────────────────────────────────────────────
  const W = { key: null, regions: new Set(), range: null, view: false, closed: new Set(store.get('twin.ws.closed', [])), drag: null };
  // Back from the 3D view: the Insights' filters as they were left (the address carries the rest).
  try { const t = JSON.parse(sessionStorage.getItem('twin.ws.trip') || 'null'); sessionStorage.removeItem('twin.ws.trip'); if (t && /3d\.html/.test(document.referrer)) { W.key = t.key || null; W.regions = new Set(t.regions || []); W.range = Array.isArray(t.range) ? t.range : null; W.view = !!t.view; } } catch (x) { /* none kept */ }
  const places = () => { const a = engine(); return a ? a.places() : []; };
  const regionOf = (() => { let m = null; return (name) => { if (!m && typeof S !== 'undefined' && S.muniFc) { m = {}; S.muniFc.features.forEach(f => { m[f.properties.municipality] = f.properties.region || ''; }); } return m ? m[name] || '' : ''; }; })();
  const inView = () => { if (typeof S === 'undefined' || !S.muniFc || typeof map === 'undefined') return null; const b = map.getBounds(), s = new Set(); S.muniFc.features.forEach(f => { const c = typeof ecCentroid === 'function' ? ecCentroid(f.geometry) : null; if (c && b.contains(c)) s.add(f.properties.municipality); }); return s; };
  function focusLayer() { const ls = state().layers; if (!ls.length) return null; return ls.find(l => l.key === W.key) || ls.find(l => l.mode === 'fill') || ls[0]; }
  /** The values of the widgets' dataset for the year of the timeline: { v: [per municipio], pr: Puerto Rico's own published value, year, names }. */
  function read(L, year) {
    const a = engine(), r = a.values(L.key, { year: year === undefined ? state().year : year, norm: L.norm || 'value', real: !!L.real }); if (!r) return null;
    const names = places(), n = names.length, pr = r.values.length > n - 1 ? r.values[n - 1] : null;   // the engine's rows end with Puerto Rico
    return { v: r.values.slice(0, n - 1), pr, year: r.year, names: names.slice(0, n - 1) };
  }
  function passing(d, except) {
    const view = W.view ? inView() : null, out = [];
    d.names.forEach((nm, i) => {
      if (W.regions.size && !W.regions.has(regionOf(nm))) return;
      if (view && !view.has(nm)) return;
      if (W.range && except !== 'range') { const x = d.v[i]; if (x == null || x < W.range[0] || x > W.range[1]) return; }
      out.push(i);
    });
    return out;
  }
  const filterCount = () => W.regions.size + (W.range ? 1 : 0) + (W.view ? 1 : 0);
  const median = (a) => { const s = a.slice().sort((x, y) => x - y), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };
  /** One figure for a set of municipios, with the words that say what it is. A count or a dollar total as published is added up; anything else is the
      median of the municipal values and is labeled as that: it is not a population-weighted rate. With no filter the figure is Puerto Rico's own published value. */
  function aggregate(L, d, idx) {
    const v = meta(L.key), xs = idx.map(i => d.v[i]).filter(x => x != null && isFinite(x));
    if (!xs.length) return { v: null, how: T('No value') };
    const add = (L.norm || 'value') === 'value' && (v.type === 'count' || v.type === 'total$');
    return { v: add ? xs.reduce((p, q) => p + q, 0) : median(xs), how: add ? Tn(xs.length, 'Sum of {n} municipio', 'Sum of {n} municipios') : Tn(xs.length, 'Median of the values of {n} municipio', 'Median of the values of {n} municipios') };
  }
  const headline = (L, d) => (!filterCount() && d.pr != null ? { v: d.pr, how: T('Puerto Rico') } : aggregate(L, d, passing(d)));
  const F = (L, x) => (x == null ? '—' : engine().fmt(L.key, x, L.norm || 'value', !!L.real));

  function line(points, year, f, w = 300, h = 140) {
    const m = { l: 46, r: 10, t: 10, b: 22 }, xs = points.map(p => p[0]), ys = points.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs); let y0 = Math.min(...ys), y1 = Math.max(...ys); if (y0 === y1) { y0 -= 1; y1 += 1; } const pad = (y1 - y0) * 0.08; y0 -= pad; y1 += pad;
    const X = (x) => m.l + (x - x0) / (x1 - x0 || 1) * (w - m.l - m.r), Y = (y) => h - m.b - (y - y0) / (y1 - y0) * (h - m.t - m.b);
    const d = points.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(''), cur = points.find(p => p[0] === year);
    const xl = xs.length > 6 ? [x0, xs[Math.floor(xs.length / 2)], x1] : xs, tk = [y0 + pad, (y0 + y1) / 2, y1 - pad];
    return `<svg class="ws-chart" viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="${html(T('Line chart by year'))}">
      ${tk.map(t => `<line class="g" x1="${m.l}" x2="${w - m.r}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/><text class="t" x="${m.l - 6}" y="${(Y(t) + 3.5).toFixed(1)}" text-anchor="end">${html(f(t))}</text>`).join('')}
      ${xl.map(x => `<text class="t" x="${X(x).toFixed(1)}" y="${h - 6}" text-anchor="${x === x0 ? 'start' : x === x1 ? 'end' : 'middle'}">${x}</text>`).join('')}
      ${cur ? `<line class="c" x1="${X(cur[0]).toFixed(1)}" x2="${X(cur[0]).toFixed(1)}" y1="${m.t}" y2="${h - m.b}"/>` : ''}<path class="s" d="${d}"/>
      ${points.map(p => `<circle class="d" data-y="${p[0]}" cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="${cur && p[0] === cur[0] ? 5 : 2.2}"><title>${p[0]}: ${html(f(p[1]))}</title></circle>`).join('')}
      <rect class="hit" data-x0="${x0}" data-x1="${x1}" data-l="${m.l / w}" data-r="${(w - m.r) / w}" x="${m.l - 8}" y="0" width="${w - m.l - m.r + 16}" height="${h}" fill="transparent"/></svg>`;
  }
  function histogram(bins, f, w = 300, h = 110) {
    const m = { l: 6, r: 6, t: 8, b: 20 }, max = Math.max(1, ...bins.map(b => b.n)), bw = (w - m.l - m.r) / bins.length;
    return `<svg class="ws-chart hist" viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="${html(T('Histogram: municipios by value'))}"><line class="g" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>
      ${bins.map((b, i) => { const bh = b.n ? Math.max(2, b.n / max * (h - m.t - m.b)) : 0; return `<rect class="b${b.on ? '' : ' off'}" x="${(m.l + i * bw + 1).toFixed(1)}" y="${(h - m.b - bh).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${bh.toFixed(1)}" rx="2"><title>${html(T('{lo} to {hi}', { lo: f(b.lo), hi: f(b.hi) }))}: ${html(Tn(b.n, '{n} municipio', '{n} municipios'))}</title></rect>`; }).join('')}
      <text class="t" x="${m.l}" y="${h - 5}">${html(f(bins[0].lo))}</text><text class="t" x="${w - m.r}" y="${h - 5}" text-anchor="end">${html(f(bins[bins.length - 1].hi))}</text>
      <rect class="brush" x="0" y="${m.t}" width="0" height="${h - m.t - m.b}" style="display:none"/><rect class="hit" data-l="${m.l / w}" data-bw="${bw / w}" data-n="${bins.length}" x="0" y="0" width="${w}" height="${h}" fill="transparent"/></svg>`;
  }
  const card = (id, title, body, note) => `<section class="ws-w${W.closed.has(id) ? ' closed' : ''}" data-w="${id}"><header><h3>${html(title)}</h3><button type="button" class="icon-btn small" data-wfold="${id}" aria-expanded="${!W.closed.has(id)}" aria-label="${html(T('Show or hide: {name}', { name: title }))}">${icon(W.closed.has(id) ? 'expand_more' : 'expand_less')}</button></header><div class="ws-w-body">${body}${note ? `<p class="ws-how">${html(note)}</p>` : ''}</div></section>`;

  function widgets() {
    const body = el('wsRightBody'), bar = el('wsFilter'); if (!body) return;
    const a = engine(), L = a ? focusLayer() : null;
    if (!L) {
      bar.innerHTML = '';
      body.innerHTML = `<div class="ws-empty">${icon('bar_chart')}<p>${html(T('Insights show figures and charts for a dataset on the map. They follow the timeline.'))}</p><button type="button" class="btn primary" id="wsAdd">${icon('add')}${html(T('Add a dataset'))}</button></div>`;
      el('wsAdd').onclick = () => { if (typeof showTab === 'function') showTab('economy'); };
      return;
    }
    W.key = L.key;
    const v = meta(L.key), d = read(L); if (!d) { body.innerHTML = `<div class="ws-empty"><p>${html(T('This dataset has no values for the chosen year.'))}</p></div>`; return; }
    const idx = passing(d), n = d.names.length, f = (x) => F(L, x), per = period(L.key), head = headline(L, d), fc = filterCount();
    const scope = fc ? T('{n} of {m} municipios', { n: idx.length, m: n }) : T('All {m} municipios', { m: n });
    // the filter line: what the figures count, always visible, with a way back
    bar.innerHTML = `<div class="ws-scope">${icon('filter_alt')}<b>${html(scope)}</b>${fc ? `<button type="button" class="linklike" id="wsClear">${icon('restart_alt')}${html(T('Clear filters'))}</button>` : ''}</div>
      <p class="ws-how">${html(fc ? T('The figures below count only these municipios. The map and the workbench still show all of them.') : T('Click a region or drag across the histogram to filter the figures below.'))}</p>
      <div class="ws-chips">${[...W.regions].map(r => `<button type="button" class="ws-chip" data-unregion="${html(r)}">${html(r)} ${icon('close')}</button>`).join('')}${W.range ? `<button type="button" class="ws-chip" data-unrange="1">${html(T('{lo} to {hi}', { lo: f(W.range[0]), hi: f(W.range[1]) }))} ${icon('close')}</button>` : ''}</div>
      <label class="ws-switch"><input type="checkbox" id="wsView"${W.view ? ' checked' : ''}><span></span>${html(T('Only what the map shows'))}</label>
      <label class="ws-for">${html(T('Figures for'))} <select id="wsFor">${state().layers.map(l => `<option value="${html(l.key)}"${l.key === L.key ? ' selected' : ''}>${html(T(meta(l.key).label))}</option>`).join('')}</select></label>`;
    // key figure
    const out = [card('figure', T('Key figure'), `<div class="ws-big">${html(f(head.v))}</div><div class="ws-sub">${html(head.how)} · ${html(per ? per.text : '')}</div>`,
      fc ? T('A figure for part of the island is worked out from the municipal values, as the line above says. It is not an official figure for that area.') : T("Puerto Rico's own published value for this period."))];
    // over time: Puerto Rico's own series with no filter; the same rule as the key figure with one
    const ys = (v.ys || []).filter(y => !years.length || y >= years[0]), pts = Core.time.isFixed(v) ? [] : ys.map(y => { const dy = read(L, y); if (!dy || dy.year !== y) return null; const h = !fc && dy.pr != null ? dy.pr : aggregate(L, dy, passing(dy)).v; return h == null ? null : [y, h]; }).filter(Boolean);
    out.push(card('time', T('Over time'), pts.length > 1 ? `<div class="ws-chartbox" id="wsLine">${line(pts, d.year, f)}</div>` : `<p class="ws-none">${html(Core.time.isFixed(v) ? T('This dataset is a snapshot: it has one period and does not change with the timeline.') : T('This dataset has one period.'))}</p>`,
      pts.length > 1 ? (fc ? T('The filtered figure in each period. Click a point to move the timeline. Missing periods are left as gaps.') : T('Puerto Rico in each period. Click a point to move the timeline. Missing periods are left as gaps.')) + (v.time && v.time.type === 'window' ? ' ' + T('Each point is a five-year survey window named by its last year; windows that overlap share most of their answers.') : '') : ''));
    // spread
    const base = passing(d, 'range'), vals = base.map(i => d.v[i]).filter(x => x != null && isFinite(x));
    if (vals.length > 2) {
      const lo = Math.min(...vals), hi = Math.max(...vals), nb = 12, step = (hi - lo) / nb || 1, bins = Array.from({ length: nb }, (_, i) => ({ lo: lo + i * step, hi: lo + (i + 1) * step, n: 0, on: true }));
      vals.forEach(x => { bins[Math.min(nb - 1, Math.floor((x - lo) / step))].n++; });
      if (W.range) bins.forEach(b => { b.on = b.hi >= W.range[0] && b.lo <= W.range[1]; });
      W.bins = bins;
      out.push(card('hist', T('Spread of values'), `<div class="ws-chartbox" id="wsHist">${histogram(bins, f)}</div>`, T('How many municipios fall in each range. Drag across the bars to keep a range; the other figures then count only those municipios.')));
    }
    // by region
    const regs = {};
    d.names.forEach((nm, i) => { const r = regionOf(nm); if (!r) return; (regs[r] = regs[r] || []).push(i); });
    const rk = Object.keys(regs).sort((p, q) => p.localeCompare(q));
    if (rk.length) {
      const rows = rk.map(r => ({ r, a: aggregate(L, d, regs[r].filter(i => !W.range || (d.v[i] != null && d.v[i] >= W.range[0] && d.v[i] <= W.range[1]))) })), mx = Math.max(...rows.map(x => Math.abs(x.a.v || 0))) || 1;
      out.push(card('region', T('By tourism region'), `<div class="ws-bars">${rows.map(x => `<button type="button" class="ws-bar${W.regions.size && !W.regions.has(x.r) ? ' off' : ''}${W.regions.has(x.r) ? ' on' : ''}" data-region="${html(x.r)}" aria-pressed="${W.regions.has(x.r)}"><span class="bl"><b>${html(x.r)}</b><em>${html(f(x.a.v))}</em></span><span class="tr"><i style="width:${Math.max(2, Math.abs(x.a.v || 0) / mx * 100).toFixed(1)}%"></i></span></button>`).join('')}</div>`,
        T('Each bar is worked out from the municipios of the region ({how}). Click a region to filter.', { how: (v.type === 'count' || v.type === 'total$') && (L.norm || 'value') === 'value' ? T('their sum') : T('the median of their values') })));
    }
    // highest and lowest
    const ranked = idx.filter(i => d.v[i] != null && isFinite(d.v[i])).sort((p, q) => d.v[q] - d.v[p]);
    if (ranked.length) {
      const pick = ranked.length > 10 ? [...ranked.slice(0, 5), null, ...ranked.slice(-5)] : ranked;
      out.push(card('rank', T('Highest and lowest'), `<ol class="ws-rank">${pick.map(i => i == null ? '<li class="gap" aria-hidden="true">…</li>' : `<li><button type="button" data-place="${html(d.names[i])}"><span class="n">${ranked.indexOf(i) + 1}</span><span class="nm">${html(d.names[i])}</span><span class="v">${html(f(d.v[i]))}</span></button></li>`).join('')}</ol>`,
        T('Ranked among the {n} municipios counted. A rank says where a place stands, not whether that is good. Click a place to open it on the map.', { n: ranked.length })));
    }
    body.innerHTML = `<div class="ws-about"><b>${html(T(v.label))}</b><span>${html(per ? per.text : '')}</span><button type="button" class="linklike" id="wsInfo">${icon('info')}${html(T('What it means, source and cautions'))}</button></div>` + out.join('');
    wireWidgets(L, d);
  }
  function wireWidgets(L, d) {
    const body = el('wsRightBody'), bar = el('wsFilter');
    const c = el('wsClear'); if (c) c.onclick = () => { W.regions.clear(); W.range = null; W.view = false; widgets(); };
    el('wsView').onchange = (e) => { W.view = e.target.checked; widgets(); };
    el('wsFor').onchange = (e) => { W.key = e.target.value; W.range = null; widgets(); };
    el('wsInfo').onclick = () => engine().info(L.key);
    bar.querySelectorAll('[data-unregion]').forEach(b => { b.onclick = () => { W.regions.delete(b.dataset.unregion); widgets(); }; });
    bar.querySelectorAll('[data-unrange]').forEach(b => { b.onclick = () => { W.range = null; widgets(); }; });
    body.querySelectorAll('[data-wfold]').forEach(b => { b.onclick = () => { const id = b.dataset.wfold; W.closed.has(id) ? W.closed.delete(id) : W.closed.add(id); store.set('twin.ws.closed', [...W.closed]); widgets(); }; });
    body.querySelectorAll('[data-region]').forEach(b => { b.onclick = () => { const r = b.dataset.region; W.regions.has(r) ? W.regions.delete(r) : W.regions.add(r); widgets(); }; });
    body.querySelectorAll('[data-place]').forEach(b => { b.onclick = () => engine().show({ clear: false, stay: true, select: b.dataset.place }); });
    const ln = el('wsLine'); if (ln) ln.onclick = (e) => { const p = e.target.closest('[data-y]'); let y = p ? +p.dataset.y : null;
      if (y == null) { const hit = ln.querySelector('.hit'), r = ln.querySelector('svg').getBoundingClientRect(), fx = (e.clientX - r.left) / r.width, x0 = +hit.dataset.x0, x1 = +hit.dataset.x1, x = x0 + (fx - +hit.dataset.l) / (+hit.dataset.r - +hit.dataset.l) * (x1 - x0); y = years.reduce((p2, q) => (Math.abs(q - x) < Math.abs(p2 - x) ? q : p2), years[0]); }
      const i = years.indexOf(y); if (i >= 0) tlSet(i); };
    const hs = el('wsHist'); if (hs && W.bins) {
      const svg = hs.querySelector('svg'), hit = hs.querySelector('.hit'), brush = hs.querySelector('.brush'), nb = +hit.dataset.n, l = +hit.dataset.l, bw = +hit.dataset.bw;
      const at = (e) => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(nb - 1, Math.floor(((e.clientX - r.left) / r.width - l) / bw))); };
      const draw = (i, j) => { const vb = svg.viewBox.baseVal.width, p = Math.min(i, j), q = Math.max(i, j); brush.style.display = ''; brush.setAttribute('x', ((l + p * bw) * vb).toFixed(1)); brush.setAttribute('width', ((q - p + 1) * bw * vb).toFixed(1)); };
      hit.onpointerdown = (e) => { W.drag = at(e); hit.setPointerCapture(e.pointerId); draw(W.drag, W.drag); };
      hit.onpointermove = (e) => { if (W.drag != null) draw(W.drag, at(e)); };
      hit.onpointerup = (e) => { if (W.drag == null) return; const i = W.drag, j = at(e); W.drag = null; const p = Math.min(i, j), q = Math.max(i, j);
        if (p === 0 && q === nb - 1) W.range = null; else W.range = [W.bins[p].lo, W.bins[q].hi]; widgets(); };
    }
  }
  function rightWire() {
    const set = (open, keep) => { document.body.classList.toggle('ws-noright', !open); el('wsRightShow').hidden = open; if (keep && window.innerWidth > 1100) store.set('twin.ws.right', open); setTimeout(() => { if (typeof map !== 'undefined') map.invalidateSize(); }, 220); };
    el('wsRightHide').onclick = () => set(false, true); el('wsRightShow').onclick = () => set(true, true);
    set(window.innerWidth > 1100 ? store.get('twin.ws.right', window.innerWidth >= 1280) : false);   // a drawer over the map on a narrow screen: it starts shut
    let t = 0; const later = () => { clearTimeout(t); t = setTimeout(() => { if (W.view) widgets(); }, 200); };
    const hook = () => { if (typeof map === 'undefined' || !map || !map.on) return setTimeout(hook, 400); map.on('moveend', () => { later(); keep(); }); }; hook();
  }

  // ── The workbench's edge ─────────────────────────────────────────────────────
  function gripWire() {
    const g = el('wsGrip'), root = document.documentElement, clamp = (h) => Math.max(140, Math.min(Math.round(window.innerHeight * 0.72), h));
    const apply = (h, keep) => { root.style.setProperty('--bench-h', clamp(h) + 'px'); if (keep) store.set('twin.ws.bench', clamp(h)); if (typeof map !== 'undefined' && map.invalidateSize) map.invalidateSize(); window.dispatchEvent(new Event('resize')); };
    const saved = store.get('twin.ws.bench', null); if (saved) root.style.setProperty('--bench-h', clamp(saved) + 'px');
    const height = () => { const b = el('econBench') || el('luBench'); return b ? b.getBoundingClientRect().height : 300; };
    let y0 = 0, h0 = 0, on = false;
    g.onpointerdown = (e) => { on = true; y0 = e.clientY; h0 = height(); g.setPointerCapture(e.pointerId); document.body.classList.add('ws-resizing'); };
    g.onpointermove = (e) => { if (on) root.style.setProperty('--bench-h', clamp(h0 + (y0 - e.clientY)) + 'px'); };
    g.onpointerup = (e) => { if (!on) return; on = false; document.body.classList.remove('ws-resizing'); apply(h0 + (y0 - e.clientY), true); };
    g.onkeydown = (e) => { const d = e.key === 'ArrowUp' ? 24 : e.key === 'ArrowDown' ? -24 : 0; if (d) { e.preventDefault(); apply(height() + d, true); } };
    g.ondblclick = () => { root.style.removeProperty('--bench-h'); store.set('twin.ws.bench', null); if (typeof map !== 'undefined') map.invalidateSize(); };
  }

  // ── Undo, redo, saved maps ───────────────────────────────────────────────────
  // What can be undone is what "Turn all off" already knows how to put back (core/activelayers.js: the layer switches, the engine's layers, the route plan), plus the year.
  const H = { undo: [], redo: [], cur: null, busy: false, name: store.get('twin.ws.name', '') };
  const adapter = () => (window.ActiveLayers ? ActiveLayers.adapter : null);
  const snap = () => { const a = adapter(); return a ? { sig: a.sig() + '|' + state().year + '|' + JSON.stringify(state().layers), s: a.snapshot(), y: state().year } : null; };
  function track() {
    if (H.busy) return; const s = snap(); if (!s) return;
    if (!H.cur) { H.cur = s; return bar(); }
    if (s.sig === H.cur.sig) return;
    H.undo.push(H.cur); if (H.undo.length > 60) H.undo.shift(); H.redo = []; H.cur = s; bar();
  }
  function go(from, to) {
    const a = adapter(); if (!a || !from.length) return;
    H.busy = true; to.push(H.cur); const s = from.pop();
    try { a.restore(s.s); const e = engine(); if (e && s.y !== state().year) e.setYear(s.y); if (window.ActiveLayers) ActiveLayers.render(); if (typeof writeHash === 'function') writeHash(); } finally { H.busy = false; }
    H.cur = snap() || s; bar(); onChange();
  }
  const MAPS = 'twin.maps';
  const maps = () => store.get(MAPS, {});
  const here = () => { if (typeof writeHash === 'function') writeHash(); return new Promise(ok => setTimeout(() => ok(location.hash), 320)); };   // writeHash waits 250 ms before it writes the address
  function bar() {
    el('wsUndo').disabled = !H.undo.length; el('wsRedo').disabled = !H.redo.length;
    el('wsName').textContent = H.name || T('Untitled map');
  }
  function mapsDialog() {
    const all = maps(), names = Object.keys(all).sort((p, q) => String(all[q].saved).localeCompare(String(all[p].saved))), dlg = el('wsMaps');
    el('wsMapsBody').innerHTML = `<p class="note">${html(T('Saved maps are kept in this browser, on this computer. Nothing is sent anywhere and nobody else can open them. To pass one on, copy its link or download it.'))}</p>
      <div class="ws-save"><input type="text" id="wsSaveName" maxlength="80" value="${html(H.name)}" placeholder="${html(T('Name this map'))}" aria-label="${html(T('Name this map'))}"><button type="button" class="btn primary" id="wsSaveGo">${icon('save')}${html(T('Save this map'))}</button></div>
      ${names.length ? `<ul class="ws-maps">${names.map(n => `<li><span><b>${html(n)}</b><i>${html(I18N.date(new Date(all[n].saved), { dateStyle: 'medium' }))}</i></span><button type="button" class="btn small" data-open="${html(n)}">${html(T('Open'))}</button><button type="button" class="icon-btn small" data-copy="${html(n)}" aria-label="${html(T('Copy the link of {name}', { name: n }))}">${icon('link')}</button><button type="button" class="icon-btn small" data-del="${html(n)}" aria-label="${html(T('Delete {name}', { name: n }))}">${icon('delete')}</button></li>`).join('')}</ul>` : `<p class="ws-none">${html(T('No saved maps yet.'))}</p>`}
      <div class="btn-row"><button type="button" class="btn small" id="wsExport">${icon('download')}${html(T('Download my maps (JSON)'))}</button><label class="btn small">${icon('upload')}${html(T('Open a maps file'))}<input type="file" id="wsImport" accept="application/json,.json" hidden></label></div>`;
    const url = (h) => location.origin + location.pathname + location.search + h;
    el('wsSaveGo').onclick = async () => { const n = el('wsSaveName').value.trim(); if (!n) { el('wsSaveName').focus(); return; } const all2 = maps(); all2[n] = { saved: new Date().toISOString(), hash: await here() }; if (!store.set(MAPS, all2)) { say(T('This browser did not let the map be saved.'), 5000); return; } H.name = n; store.set('twin.ws.name', n); bar(); mapsDialog(); say(T('Saved in this browser: {name}', { name: n })); };
    el('wsMapsBody').querySelectorAll('[data-open]').forEach(b => { b.onclick = () => { const m = maps()[b.dataset.open]; if (!m) return; store.set('twin.ws.name', b.dataset.open); location.hash = m.hash; location.reload(); }; });   // a reload, as the scenarios do: every part of the map reads the address when it starts
    el('wsMapsBody').querySelectorAll('[data-copy]').forEach(b => { b.onclick = () => { const m = maps()[b.dataset.copy]; if (m) copy(url(m.hash)); }; });
    el('wsMapsBody').querySelectorAll('[data-del]').forEach(b => { b.onclick = () => { const all2 = maps(); delete all2[b.dataset.del]; store.set(MAPS, all2); mapsDialog(); }; });
    el('wsExport').onclick = () => { const blob = new Blob([JSON.stringify({ app: 'PR Data Observatory', kind: 'saved maps', exported: new Date().toISOString(), maps: maps() }, null, 1)], { type: 'application/json' }), a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'observatory-maps.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); };
    el('wsImport').onchange = async (e) => { const f = e.target.files[0]; if (!f) return; try { const o = JSON.parse(await f.text()), inn = o && o.maps; if (!inn || typeof inn !== 'object') throw new Error('shape'); const all2 = maps(); let k = 0; Object.entries(inn).forEach(([n, m]) => { if (m && typeof m.hash === 'string' && /^#?[\w\-.,~%=&:+ ]*$/.test(m.hash) && m.hash.length < 4000) { all2[String(n).slice(0, 80)] = { saved: m.saved || new Date().toISOString(), hash: m.hash[0] === '#' ? m.hash : '#' + m.hash }; k++; } }); store.set(MAPS, all2); mapsDialog(); say(Tn(k, '{n} map added from the file', '{n} maps added from the file')); } catch (err) { say(T('That file is not a saved-maps file of the observatory.'), 5000); } };
    if (!dlg.open) dlg.showModal();
  }
  function copy(text) { (navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => say(T('Link copied')), () => say(T('The link is in the address bar: copy it from there.'), 5000)); }
  function barWire() {
    // 2D / 3D: the same analysis in the other view. The address carries it (js/core/viewstate.js): the place, the layers, the datasets and the year.
    const m3 = el('wsMode3d'); if (m3) m3.onclick = async (e) => { e.preventDefault(); tlStop(); try { sessionStorage.setItem('twin.ws.trip', JSON.stringify({ key: W.key, regions: [...W.regions], range: W.range, view: W.view })); } catch (x) { /* the filters are an extra */ } const h = await here(); location.href = '3d.html' + location.search + h; };
    el('wsUndo').onclick = () => go(H.undo, H.redo); el('wsRedo').onclick = () => go(H.redo, H.undo);
    el('wsLink').onclick = async () => { const h = await here(); copy(location.origin + location.pathname + location.search + h); };
    el('wsSave').onclick = mapsDialog; el('wsOpen').onclick = mapsDialog;
    el('wsName').onclick = mapsDialog;
    el('wsMapsClose').onclick = () => el('wsMaps').close();
    document.addEventListener('keydown', (e) => { if (!(e.ctrlKey || e.metaKey) || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || ''))) return; const k = e.key.toLowerCase(); if (k === 'z' && !e.shiftKey) { e.preventDefault(); go(H.undo, H.redo); } else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); go(H.redo, H.undo); } });
    bar();
  }

  // ── When something changes ───────────────────────────────────────────────────
  let queued = false;
  function onChange() { if (queued) return; queued = true; Promise.resolve().then(() => { queued = false; if (engine() && !years.length) tlBuild(); else if (ready) { tlTicks(); tlSync(); } else tlSync(); widgets(); track(); keep(); }); }
  // the map as it is, for Explore's "Continue where you left off" and for Data's "Add to my map" (the address is written 250 ms after a change)
  let kt = 0; function keep() { clearTimeout(kt); kt = setTimeout(() => store.set('twin.ws.last', location.hash), 600); }
  function start() {
    if (!el('wsTime')) return;
    tlWire(); rightWire(); gripWire(); barWire(); widgets();
    // the engine tells the "On the map" chip every time it draws (Core.activelayers.changed) and when it has built its year control (dock): listen there, so economy.js needs no change
    if (window.Core && Core.activelayers) {
      const ch = Core.activelayers.changed, dk = Core.activelayers.dock;
      Core.activelayers.changed = function () { ch.apply(this, arguments); onChange(); };
      Core.activelayers.dock = function () { dk.apply(this, arguments); tlBuild(); onChange(); };
    }
    document.addEventListener('change', (e) => { if (e.target && /^(ly|slr$|walkRings)/.test(e.target.id || '')) onChange(); }, true);
    document.addEventListener('themechange', () => {   // the base map follows the theme unless the viewer chose one (bm= in the address, or a default kept in this browser)
      try { if (typeof bmH !== 'undefined' && bmH && bmH.set && !bmLink && window.Core && Core.basemap && !Core.basemap.stored()) { const n = Core.basemap.defaultOf('2d'); bmH.set(n); if (bmCtl) bmCtl.set(n); } } catch (e) { /* the base map has not loaded: it will pick the theme's style when it does */ }
      widgets();
    });
    if (engine()) { tlBuild(); onChange(); }
  }
  window.Workspace = { start, timeline: { set: tlSet, step: tlStep, play: tlPlay, stop: tlStop, years: () => years.slice(), sync: tlSync }, widgets, filters: W, history: H, period, _test: { aggregate, median } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
