/* PR Data Observatory: the Broadband gaps page (broadband.html, Knowledge Area; HANDOFF decision 99).
   Loads data/broadband_series.json and data/broadband_barrio.json (broadband.py: the FCC Broadband Data Collection, the release as of June 30 of each year
   2023-2026, by municipio and by barrio), then data/barrios.geojson for the map. From these it shows where broadband infrastructure may be needed:
     - Puerto Rico now and since 2023: the shares served, underserved and unserved in NTIA's BEAD terms, the locations below 100/20 Mbps and fiber;
     - a barrio map shaded by the share of locations below 100/20 Mbps, or the share unserved, or the share with fiber, for any of the four years;
     - the municipios and the barrios with the most locations below 100/20, and with the highest share (barrios with at least MIN_N locations);
     - each municipio's share below 100/20 in each year.
   Counts and shares by area only: no location, address or provider (the files hold none). Every visible string goes through T(): its Spanish is in
   i18n_src/es/broadband.json, written by docs/analysis/broadband-2026-11/make_page.py. The choice is kept in the address (#v=..&y=..). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc && doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const pts = (v, d = 1) => v == null || !isFinite(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '±') + fmt(Math.abs(v), d) + ' ' + T('points');
  const sgn = (v) => v == null || !isFinite(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '±') + fmt(Math.abs(v), 0);
  const escH = (s) => (typeof esc === 'function' ? esc(s) : String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
  const MIN_N = 50;   // a barrio's share is ranked only when it has at least this many locations
  // the three measures of the map; each has its own fixed classes (same for every year, so years compare), from low need to high need
  const MEASURES = {
    below: { label: 'Locations below 100/20 Mbps (underserved or unserved, %)', breaks: [1, 5, 15, 35], ramp: ['#fbe9e7', '#f4b9a7', '#e57f63', '#c4452c', '#8a2312'], high: 'need' },
    unserved: { label: 'Locations unserved, below 25/3 Mbps (%)', breaks: [1, 5, 15, 35], ramp: ['#fbe9e7', '#f4b9a7', '#e57f63', '#c4452c', '#8a2312'], high: 'need' },
    fiber: { label: 'Locations where fiber is available (%)', breaks: [20, 40, 60, 80], ramp: ['#eaf1fb', '#b9d0ef', '#7aa6dd', '#3b73bd', '#1b4a86'], high: 'good' },
  };
  const S = { v: 'below', y: null, sortM: ['below_n', -1], rankB: 'n' };
  let D = null, GEO = null, PROJ = null;

  // ── Figures from the two files (pure: tests/broadband_page.test.js) ──
  function index(doc1) { return Object.fromEntries(doc1.vars.map(v => [v.key, v.years])); }
  /** One area's figures in a year: locations, below 100/20 (count and share), and the three tier shares and fiber. */
  function area(V, y, i) {
    const n = V.bb_locations[y][i], b = V.bb_below100_n[y][i];
    return { n, below_n: b, below: n ? b / n * 100 : null, served: V.bb_served_pct[y][i], under: V.bb_underserved_pct[y][i], unserved: V.bb_unserved_pct[y][i], fiber: V.bb_fiber_pct[y][i] };
  }
  /** Puerto Rico in the first and last year, and the change. */
  function figures(series) {
    const V = index(series), ys = series.years.map(String), y0 = ys[0], y1 = ys[ys.length - 1], pr = series.geo.ids.length - 1;
    const a = area(V, y0, pr), b = area(V, y1, pr);
    return { y0: +y0, y1: +y1, first: a, last: b, change: { served: b.served - a.served, under: b.under - a.under, unserved: b.unserved - a.unserved, below_n: b.below_n - a.below_n, fiber: b.fiber - a.fiber } };
  }
  /** The value of the map's measure for an area. */
  function measure(a, v) { return !a.n ? null : v === 'below' ? a.below : v === 'unserved' ? a.unserved : a.fiber; }
  function classOf(x, breaks) { if (x == null) return -1; let k = 0; while (k < breaks.length && x >= breaks[k]) k++; return k; }
  /** Barrios ranked: by count of locations below 100/20, or by share among the barrios with at least MIN_N locations. */
  function rankBarrios(barrio, y, by, top = 25) {
    const V = index(barrio), rows = barrio.geo.ids.map((id, i) => ({ id, i, ...area(V, String(y), i) })).filter(r => r.n);
    const pool = by === 'share' ? rows.filter(r => r.n >= MIN_N) : rows;
    pool.sort(by === 'share' ? (p, q) => q.below - p.below || q.below_n - p.below_n : (p, q) => q.below_n - p.below_n || q.below - p.below);
    return { rows: pool.slice(0, top), considered: pool.length, all: rows.length };
  }

  // ── The page ──
  if (doc && $('#bbNow')) Promise.all([fetchJson('data/broadband_series.json'), fetchJson('data/broadband_barrio.json')]).then(([s, b]) => {
    D = { s, b, Vs: index(s), Vb: index(b), ys: s.years.map(String) };
    readHash(); start();
    fetchJson('data/barrios.geojson').then(g => { GEO = g; drawMap(); drawBarrios(); }, e => {
      $('#bbMap').innerHTML = `<p class="pm-p">${escH(T('The map could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }, (e) => {
    $('#bbNow').innerHTML = `<p class="pm-p">${escH(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  function readHash() {
    const q = new URLSearchParams((root.location.hash || '').slice(1));
    if (MEASURES[q.get('v')]) S.v = q.get('v');
    S.y = D.ys.includes(q.get('y')) ? q.get('y') : D.ys[D.ys.length - 1];
  }
  function writeHash() { const h = `#v=${S.v}&y=${S.y}`; if (root.location.hash !== h) root.history.replaceState(null, '', h); }

  function start() {
    drawNow(); drawControls(); drawMunis(); drawTrend();   // a language switch reloads the page (js/i18n.js)
  }

  function card(icon, label, value, sub) {
    return `<div class="bb-card"><span class="ms-icon" aria-hidden="true">${icon}</span><div><div class="bb-v">${escH(value)}</div><div class="bb-l">${escH(label)}</div><div class="bb-s">${escH(sub)}</div></div></div>`;
  }
  function drawNow() {
    const F = figures(D.s), a = F.last, c = F.change, since = T('since June {y}', { y: F.y0 });
    $('#bbNow').innerHTML = `<p class="pm-p">${escH(T('As of June 30, {y}, Puerto Rico had {n} broadband serviceable locations.', { y: F.y1, n: fmt(a.n) }))}</p>
      <div class="bb-cards">${[
      card('wifi', T('Served: 100/20 Mbps or more'), pct(a.served), `${pts(c.served)} ${since}`),
      card('signal_cellular_alt_2_bar', T('Underserved: 25/3 to 100/20 Mbps'), pct(a.under), `${pts(c.under)} ${since}`),
      card('signal_cellular_off', T('Unserved: below 25/3 Mbps'), pct(a.unserved), `${pts(c.unserved)} ${since}`),
      card('location_on', T('Locations below 100/20 Mbps'), fmt(a.below_n), `${sgn(c.below_n)} ${since}`),
      card('cable', T('Fiber available'), pct(a.fiber), `${pts(c.fiber)} ${since}`)].join('')}</div>`;
    $('#bbNow').dataset.done = '1';
  }

  function drawControls() {
    const opt = (k, sel, lab) => `<option value="${k}"${k === sel ? ' selected' : ''}>${escH(lab)}</option>`;
    $('#bbControls').innerHTML = `<label>${escH(T('Shade by'))} <select id="bbV">${Object.keys(MEASURES).map(k => opt(k, S.v, T(MEASURES[k].label))).join('')}</select></label>
      <label>${escH(T('As of June 30 of'))} <select id="bbY">${D.ys.map(y => opt(y, S.y, y)).join('')}</select></label>`;
    $('#bbV').onchange = (e) => { S.v = e.target.value; writeHash(); drawMap(); };
    $('#bbY').onchange = (e) => { S.y = e.target.value; writeHash(); drawMap(); drawMunis(); drawBarrios(); };
  }

  function project() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const rings = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
    GEO.features.forEach(f => rings(f.geometry).forEach(p => p.forEach(r => r.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }))));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = Math.ceil((y1 - y0) * sc);
    const pt = ([x, y]) => [((x - x0) * k * sc).toFixed(1), ((y1 - y) * sc).toFixed(1)];
    const path = (g) => rings(g).map(p => p.map(r => { let last = '', s = ''; r.forEach(c => { const q = pt(c).join(','); if (q !== last) { s += (s ? 'L' : 'M') + q; last = q; } }); return s + 'Z'; }).join('')).join('');
    PROJ = { W, H, paths: GEO.features.map(f => ({ id: f.properties.geoid, name: f.properties.barrio, muni: f.properties.municipality, d: path(f.geometry) })) };
  }
  function legend(m) {
    const b = m.breaks, lab = [`< ${fmt(b[0])}`, ...b.slice(0, -1).map((x, i) => `${fmt(x)}–${fmt(b[i + 1])}`), `≥ ${fmt(b[b.length - 1])}`];
    return `<div class="pm-legend bb-legend" aria-hidden="true">${m.ramp.map((c, i) => `<span class="pm-keyrow"><i style="background:${c}"></i>${escH(lab[i])}${lang() === 'es' ? ' %' : '%'}</span>`).join('')}<span class="pm-keyrow"><i class="bb-none"></i>${escH(T('No locations'))}</span></div>`;
  }
  function drawMap() {
    if (!GEO) return;
    if (!PROJ) project();
    const m = MEASURES[S.v], at = new Map(D.b.geo.ids.map((id, i) => [id, i]));
    let s = '', counts = [0, 0, 0, 0, 0], none = 0;
    for (const p of PROJ.paths) {
      const i = at.get(p.id), a = i == null ? { n: 0 } : area(D.Vb, S.y, i), x = measure(a, S.v), k = classOf(x, m.breaks);
      if (k < 0) none++; else counts[k]++;
      const lab = k < 0 ? T('{name} ({muni}): no broadband serviceable locations', { name: p.name, muni: p.muni })
        : T('{name} ({muni}): {value} of {n} locations; {below} below 100/20 Mbps', { name: p.name, muni: p.muni, value: pct(x), n: fmt(a.n), below: fmt(a.below_n) });
      s += `<path d="${p.d}" class="${k < 0 ? 'bb-nodata' : ''}" fill="${k < 0 ? 'url(#bbHatch)' : m.ramp[k]}"><title>${escH(lab)}</title></path>`;
    }
    const title = T('Map of the {n} barrios shaded by {measure}, as of June 30, {y}', { n: PROJ.paths.length, measure: T(m.label).toLowerCase(), y: S.y });
    $('#bbMap').innerHTML = `<svg viewBox="0 0 ${PROJ.W} ${PROJ.H}" width="100%" role="img" aria-label="${escH(title)}"><defs><pattern id="bbHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#f3f4f6"/><line x1="0" y1="0" x2="0" y2="6" stroke="#c5cad3" stroke-width="2"/></pattern></defs><g class="bb-barrios">${s}</g></svg>${legend(m)}`;
    $('#bbMapNote').textContent = T('{a} barrios in the darkest class, {none} with no locations. Hover over or tap a barrio for its figures.', { a: counts[counts.length - 1], none });
    $('#bbMap').dataset.done = '1';
  }

  function th(key, label, sort) { const on = sort && sort[0] === key; return `<th scope="col"${on ? ` aria-sort="${sort[1] > 0 ? 'ascending' : 'descending'}"` : ''}><button type="button" class="pm-btn" data-k="${key}">${escH(label)}${on ? (sort[1] > 0 ? ' ▲' : ' ▼') : ''}</button></th>`; }
  function drawMunis() {
    const ids = D.s.geo.ids, names = D.s.geo.names, pr = ids.length - 1, y = S.y, y0 = D.ys[0];
    const rows = ids.slice(0, pr).map((id, i) => { const a = area(D.Vs, y, i), b = area(D.Vs, y0, i); return { name: names[i], ...a, change: a.below_n - b.below_n }; });
    const [k, dir] = S.sortM;
    rows.sort((p, q) => (k === 'name' ? p.name.localeCompare(q.name, loc()) : (p[k] ?? -1) - (q[k] ?? -1)) * dir);
    const P = area(D.Vs, y, pr), P0 = area(D.Vs, y0, pr);
    const row = (r, cls = '') => `<tr${cls}><th scope="row">${escH(r.name)}</th><td>${fmt(r.n)}</td><td>${fmt(r.below_n)}</td><td>${pct(r.below)}</td><td>${pct(r.unserved)}</td><td>${pct(r.fiber)}</td><td>${sgn(r.change)}</td></tr>`;
    $('#bbMunis').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('Municipios as of June 30, {y}: select a heading to sort', { y }))}</caption><thead><tr>${th('name', T('Municipio'), S.sortM)}${th('n', T('Locations'), S.sortM)}${th('below_n', T('Below 100/20 Mbps'), S.sortM)}${th('below', T('Share below 100/20'), S.sortM)}${th('unserved', T('Unserved'), S.sortM)}${th('fiber', T('Fiber available'), S.sortM)}${th('change', T('Change below 100/20 since {y}', { y: y0 }), S.sortM)}</tr></thead>
      <tbody>${row({ name: T('Puerto Rico'), ...P, change: P.below_n - P0.below_n }, ' class="bb-pr"')}${rows.map(r => row(r)).join('')}</tbody></table>`;
    $('#bbMunis').querySelectorAll('button[data-k]').forEach(b => { b.onclick = () => { const kk = b.dataset.k; S.sortM = [kk, S.sortM[0] === kk ? -S.sortM[1] : (kk === 'name' ? 1 : -1)]; drawMunis(); }; });
    $('#bbMunis').dataset.done = '1';
  }

  function drawBarrios() {
    if (!GEO) return;
    if (!PROJ) project();
    const nm = new Map(PROJ.paths.map(p => [p.id, p])), R = rankBarrios(D.b, S.y, S.rankB);
    const opt = (k, lab) => `<label class="bb-radio"><input type="radio" name="bbRank" value="${k}"${S.rankB === k ? ' checked' : ''}> ${escH(lab)}</label>`;
    $('#bbRankBy').innerHTML = `<fieldset class="bb-fs"><legend>${escH(T('Rank the barrios by'))}</legend>${opt('n', T('number of locations below 100/20 Mbps'))}${opt('share', T('share below 100/20 Mbps (barrios with at least {n} locations)', { n: MIN_N }))}</fieldset>`;
    $('#bbRankBy').querySelectorAll('input').forEach(i => { i.onchange = () => { S.rankB = i.value; drawBarrios(); }; });
    const rows = R.rows.map((r, k) => { const p = nm.get(r.id) || {}; return `<tr><td>${k + 1}</td><th scope="row">${escH(p.name || r.id)}</th><td>${escH(p.muni || '')}</td><td>${fmt(r.n)}</td><td>${fmt(r.below_n)}</td><td>${pct(r.below)}</td><td>${pct(r.unserved)}</td><td>${pct(r.fiber)}</td></tr>`; }).join('');
    $('#bbBarrios').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('The {k} barrios first in this order, of {n}, as of June 30, {y}', { k: R.rows.length, n: R.considered, y: S.y }))}</caption><thead><tr><th scope="col">#</th><th scope="col">${escH(T('Barrio'))}</th><th scope="col">${escH(T('Municipio'))}</th><th scope="col">${escH(T('Locations'))}</th><th scope="col">${escH(T('Below 100/20 Mbps'))}</th><th scope="col">${escH(T('Share below 100/20'))}</th><th scope="col">${escH(T('Unserved'))}</th><th scope="col">${escH(T('Fiber available'))}</th></tr></thead><tbody>${rows}</tbody></table>`;
    $('#bbBarrios').dataset.done = '1';
  }

  function spark(vals) {
    const W = 90, H = 24, ok = vals.filter(v => v != null), hi = Math.max(5, ...ok), x = (i) => 4 + i * (W - 8) / (vals.length - 1), y = (v) => H - 3 - v / hi * (H - 6);
    const d = vals.map((v, i) => v == null ? '' : `${i && vals[i - 1] != null ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
    return `<svg class="bb-spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true"><path d="${d}" fill="none" stroke="#c4452c" stroke-width="1.6"/>${vals.map((v, i) => v == null ? '' : `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${i === vals.length - 1 ? 2.6 : 1.6}" fill="#c4452c"/>`).join('')}</svg>`;
  }
  function drawTrend() {
    const ids = D.s.geo.ids, names = D.s.geo.names, pr = ids.length - 1, ys = D.ys;
    const share = (i, y) => area(D.Vs, y, i).below;
    const rows = ids.map((id, i) => ({ i, name: i === pr ? T('Puerto Rico') : names[i], v: ys.map(y => share(i, y)) }));
    const body = [rows[pr], ...rows.slice(0, pr).sort((p, q) => (q.v[q.v.length - 1] ?? 0) - (p.v[p.v.length - 1] ?? 0))];
    $('#bbTrend').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('Share of locations below 100/20 Mbps, as of June 30 of each year; municipios from the highest share in {y}', { y: ys[ys.length - 1] }))}</caption><thead><tr><th scope="col">${escH(T('Municipio'))}</th>${ys.map(y => `<th scope="col">${y}</th>`).join('')}<th scope="col">${escH(T('Change in points'))}</th><th scope="col"><span class="sr-only">${escH(T('Trend'))}</span></th></tr></thead>
      <tbody>${body.map((r, k) => `<tr${k === 0 ? ' class="bb-pr"' : ''}><th scope="row">${escH(r.name)}</th>${r.v.map(v => `<td>${pct(v)}</td>`).join('')}<td>${pts(r.v[r.v.length - 1] - r.v[0])}</td><td>${spark(r.v)}</td></tr>`).join('')}</tbody></table>`;
    $('#bbTrend').dataset.done = '1';
  }

  root.BroadbandPage = { figures, area, measure, classOf, rankBarrios, index, MEASURES, MIN_N };
})(typeof window !== 'undefined' ? window : globalThis);
