/* PR Data Observatory: the Connections between municipios page (transit-links.html, Knowledge Area; HANDOFF decision 105).
   Loads data/transit_links.json (transit_links.py: the Census Bureau's commuting flows between municipios, the published timetables, the público routes of
   the 2020 list), then data/municipios.geojson and data/simulated_links.geojson for the map. From these it shows:
     - the figures: workers who travel to another municipio, and how many of them travel between a pair with a timetabled route, with only a público route
       on the 2020 list, or with no route listed;
     - a map: the pairs joined by a current timetable (the stretch of the pair's busiest route between the two municipios, timetabled_links.geojson) and
       the simulated connections (along the roads);
     - the pairs of municipios, filtered by municipio and by what is listed today (sortable);
     - the municipios: residents who work elsewhere, workers who come in, how much of that travel has a timetabled route, and the municipio's own system.
   A simulated connection shows where a connection is missing; the page proposes no route (decision 105). Every visible string goes through T(); its Spanish
   is in i18n_src/es/tlinks.json, written by docs/analysis/transit-links-2026-11/make_page.py. The choices are kept in the address (#m=<municipio>&s=<status>). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc && doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const escH = (s) => (typeof esc === 'function' ? esc(s) : String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
  // what is listed today for a pair (transit_links.py), from the most service down; colours: green for a timetable, purple and orange as on the map layer
  const STATUS = {
    timetable: { label: 'Timetabled route', color: '#1b7837' },
    expired: { label: 'Timetable expired', color: '#8a8f99' },
    publico: { label: 'Público route on the 2020 list', color: '#5e3c99' },
    none: { label: 'No route listed', color: '#e66101' },
  };
  const ORDER = ['timetable', 'expired', 'publico', 'none'];
  const OWN = { current: 'Timetable published', expiring: 'Timetable published', expired: 'Timetable expired', none: 'No timetable published' };
  const TOP = 40;   // rows of the pairs table before "Show all"
  const S = { m: '', s: '', sort: ['workers', -1], msort: ['work_elsewhere', -1], all: false };
  let D = null, GEO = null, LINKS = null, TTL = null, PROJ = null;

  // ── Figures from the file (pure: tests/transit_links_page.test.js) ──
  const objects = (d, fields, rows) => d[rows].map(r => Object.fromEntries(d[fields].map((f, i) => [f, r[i]])));
  function pairs(d) {
    const nv = new Map(munis(d).map(m => [m.geoid, m.no_vehicle_pct]));
    return objects(d, 'pair_fields', 'pairs').map(p => ({ ...p, death_km: p.sim && p.deaths_5y != null && p.km ? 10 * p.deaths_5y / p.km : null,   // deaths within 100 m of a simulated connection per 10 km of it, five years
      tt_ratio: p.tt_best != null && p.min ? p.tt_best / p.min : null,   // the fastest journey by timetable over the time by car
      nv_a: nv.get(p.a) ?? null, nv_b: nv.get(p.b) ?? null, nv: Math.max(nv.get(p.a) ?? -1, nv.get(p.b) ?? -1) }));   // households with no vehicle at each end; nv, the higher, for sorting
  }
  function munis(d) { return objects(d, 'muni_fields', 'municipios'); }
  /** The pairs of one municipio (or all), with one status (or all), sorted by a field. */
  function select(all, m, s, sort) {
    const [k, dir] = sort || ['workers', -1];
    const by = (p, q) => (p[k] == null ? (q[k] == null ? 0 : 1) : q[k] == null ? -1 : (p[k] - q[k]) * dir);   // a pair with no value goes last either way
    return all.filter(p => (!m || p.a === m || p.b === m) && (!s || p.status === s)).sort((p, q) => by(p, q) || q.workers - p.workers);
  }
  /** Workers and pairs by status among some pairs. */
  function tally(list) {
    const t = Object.fromEntries(ORDER.map(k => [k, { pairs: 0, workers: 0 }]));
    list.forEach(p => { t[p.status].pairs++; t[p.status].workers += p.workers; });
    return t;
  }

  // ── The page ──
  if (doc && $('#tlNow')) fetchJson('data/transit_links.json').then(d => {
    const ms = munis(d);
    D = { d, P: pairs(d), M: new Map(ms.map(m => [m.geoid, m])), ms };
    readHash(); drawNow(); drawPick(); drawPairs(); drawMunis();
    Promise.all([fetchJson('data/municipios.geojson'), fetchJson('data/simulated_links.geojson'), fetchJson('data/timetabled_links.geojson')]).then(([g, l, t]) => { GEO = g; LINKS = l; TTL = t; drawMap(); }, e => {
      $('#tlMap').innerHTML = `<p class="pm-p">${escH(T('The map could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }, (e) => {
    $('#tlNow').innerHTML = `<p class="pm-p">${escH(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  function readHash() {
    const q = new URLSearchParams((root.location.hash || '').slice(1));
    if (D.M.has(q.get('m'))) S.m = q.get('m');
    if (STATUS[q.get('s')]) S.s = q.get('s');
  }
  function writeHash() {
    const h = [S.m ? `m=${S.m}` : '', S.s ? `s=${S.s}` : ''].filter(Boolean).join('&');
    if ((root.location.hash || '').slice(1) !== h) root.history.replaceState(null, '', h ? '#' + h : root.location.pathname + root.location.search);
  }
  const name = (g) => (D.M.get(g) || {}).name || g;
  const pairName = (p) => `${name(p.a)} – ${name(p.b)}`;

  function card(color, label, value, sub) {
    return `<div class="oz-card"><i style="background:${color}" aria-hidden="true"></i><div><div class="oz-v">${escH(value)}</div><div class="oz-l">${escH(label)}</div><div class="oz-s">${escH(sub)}</div></div></div>`;
  }
  function drawNow() {
    const p = D.d.pr, b = p.by_status;
    const sub = (k) => T('{n} pairs of municipios; {s} of those workers', { n: fmt(b[k].pairs), s: pct(b[k].pct) });
    const tt = D.d.transit_time || {}, rs = D.P.filter(q => q.tt_ratio != null).map(q => q.tt_ratio).sort((x, y) => x - y), ratio = rs.length ? rs[Math.floor(rs.length / 2)] : null;
    $('#tlNow').innerHTML = `<div class="oz-cards">${[
      card('#1d2433', T('Workers who travel to another municipio'), fmt(p.other_municipio), T('{s} of {n} workers, {period}', { s: pct(p.other_municipio_pct), n: fmt(p.workers), period: D.d.flows.period })),
      card(STATUS.timetable.color, T('Between municipios with a timetabled route'), fmt(b.timetable.workers), sub('timetable')),
      ...(b.expired.pairs ? [card(STATUS.expired.color, T('Between municipios whose only timetable expired'), fmt(b.expired.workers), sub('expired'))] : []),
      card(STATUS.publico.color, T('With only a público route on the 2020 list'), fmt(b.publico.workers), sub('publico')),
      card(STATUS.none.color, T('With no route listed'), fmt(b.none.workers), sub('none')),
      card('#8a6d1f', T('Simulated connections'), fmt(p.simulated), T('pairs with {w} workers or more and no timetabled route; {n} workers', { w: fmt(D.d.rules.sim_min_workers), n: fmt(p.simulated_workers) })),
      ...(tt.pairs_with_a_journey != null ? [card('#1b7837', T('Pairs with a journey by timetable'), fmt(tt.pairs_with_a_journey), T('of {n} pairs, town centre to town centre leaving from 6 to 9 a.m.; a median of {r} times as long as by car', { n: fmt(p.pairs), r: fmt(ratio, 1) })),
        card('#8a8f99', T('Town centres with no stop of a weekday timetable within 1 km'), T('{n} of {m}', { n: fmt(tt.centres_without_a_stop), m: fmt(D.ms.length) }), T('there a trip starts with a longer walk, a car or a público'))] : [])].join('')}</div>`;
    $('#tlNow').dataset.done = '1';
  }

  // ── The map: municipios, the timetabled pairs (along their routes) and the simulated connections (along the roads) ──
  function project() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const rings = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
    GEO.features.forEach(f => rings(f.geometry).forEach(p => p.forEach(r => r.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }))));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = Math.ceil((y1 - y0) * sc);
    const pt = ([x, y]) => [((x - x0) * k * sc).toFixed(1), ((y1 - y) * sc).toFixed(1)];
    const run = (r, close) => { let last = '', s = ''; r.forEach(c => { const q = pt(c).join(','); if (q !== last) { s += (s ? 'L' : 'M') + q; last = q; } }); return s + (close ? 'Z' : ''); };
    const line = (g) => (g.type === 'LineString' ? [g.coordinates] : g.coordinates).map(r => run(r, false)).join('');
    PROJ = { W, H, pt, munis: GEO.features.map(f => ({ id: f.properties.GEOID, d: rings(f.geometry).map(p => p.map(r => run(r, true)).join('')).join('') })),
      links: LINKS.features.map(f => ({ p: f.properties, d: line(f.geometry) })), tt: new Map(TTL.features.map(f => [f.properties.geoid_a + '-' + f.properties.geoid_b, line(f.geometry)])) };
  }
  const width = (w) => (1.2 + 6.8 * Math.sqrt(Math.min(1, w / 7500))).toFixed(1);
  function drawMap() {
    if (!GEO || !LINKS || !TTL) return;
    if (!PROJ) project();
    const on = (a, b) => !S.m || a === S.m || b === S.m;
    const shapes = PROJ.munis.map(m => `<path class="tl-m${m.id === S.m ? ' on' : ''}" d="${m.d}" data-id="${m.id}" tabindex="-1"><title>${escH(name(m.id))}</title></path>`).join('');
    const tt = D.P.filter(p => p.status === 'timetable' && (!S.s || S.s === 'timetable') && PROJ.tt.has(p.a + '-' + p.b)).map(p =>   // every current pair has a line (transit_links.py stops otherwise)
      `<path class="tl-tt${on(p.a, p.b) ? '' : ' dim'}" d="${PROJ.tt.get(p.a + '-' + p.b)}" stroke-width="${width(p.workers)}"><title>${escH(T('{pair}: {n} workers; timetabled route, {t} weekday trips', { pair: pairName(p), n: fmt(p.workers), t: fmt(p.tt_trips) }))}</title></path>`).join('');
    const sim = PROJ.links.filter(l => !S.s || S.s === (l.p.c === 2 ? 'publico' : 'none')).map(l => {
      const st = l.p.c === 2 ? 'publico' : 'none';
      return `<path class="tl-sim${on(l.p.geoid_a, l.p.geoid_b) ? '' : ' dim'}" d="${l.d}" stroke="${STATUS[st].color}" stroke-width="${width(l.p.workers)}"><title>${escH(T('{pair}: {n} workers; simulated connection, {s}', { pair: l.p.name, n: fmt(l.p.workers), s: T(STATUS[st].label).toLowerCase() }))}</title></path>`;
    }).join('');
    const dots = D.ms.map(m => { const [x, y] = PROJ.pt([m.lng, m.lat]); return `<circle class="tl-dot" cx="${x}" cy="${y}" r="2.2"/>`; }).join('');
    const title = T('Map of Puerto Rico: {t} pairs of municipios joined by a timetabled route and {n} simulated connections for pairs without one', { t: fmt(D.d.pr.by_status.timetable.pairs), n: fmt(D.d.pr.simulated) });
    $('#tlMap').innerHTML = `<svg viewBox="0 0 ${PROJ.W} ${PROJ.H}" width="100%" role="img" aria-label="${escH(title)}"><g>${shapes}</g><g>${sim}</g><g>${tt}</g><g>${dots}</g></svg>`
      + `<div class="pm-legend oz-legend"><span class="pm-keyrow"><i class="tl-key" style="border-top:3px solid ${STATUS.timetable.color}"></i>${escH(T('Timetabled route today (along its route)'))}</span>`
      + ['none', 'publico'].map(k => `<span class="pm-keyrow"><i class="tl-key" style="border-top:3px dashed ${STATUS[k].color}"></i>${escH(T('Simulated connection'))}: ${escH(T(STATUS[k].label).toLowerCase())}</span>`).join('')
      + `<span class="pm-keyrow">${escH(T('Thicker lines: more workers'))}</span></div>`;
    $('#tlMap svg').addEventListener('click', (e) => { const p = e.target.closest('path[data-id]'); if (!p) return; S.m = S.m === p.dataset.id ? '' : p.dataset.id; S.all = false; writeHash(); drawPick(); drawMap(); drawPairs(); });
    $('#tlMapNote').textContent = T('Select a municipio to see only its connections. Simulated connections follow the fastest roads between two town centres (OpenStreetMap); they are not proposed routes.');
    $('#tlMap').dataset.done = '1';
  }

  // ── The pairs ──
  function drawPick() {
    const opts = D.ms.slice().sort((a, b) => a.name.localeCompare(b.name, loc()));
    $('#tlPick').innerHTML = `<label class="pm-ctl"><span>${escH(T('Municipio'))}</span> <select id="tlM"><option value="">${escH(T('All of Puerto Rico'))}</option>${opts.map(m => `<option value="${m.geoid}"${m.geoid === S.m ? ' selected' : ''}>${escH(m.name)}</option>`).join('')}</select></label> `
      + `<label class="pm-ctl"><span>${escH(T('Listed today'))}</span> <select id="tlS"><option value="">${escH(T('Any'))}</option>${ORDER.filter(k => D.d.pr.by_status[k].pairs).map(k => `<option value="${k}"${k === S.s ? ' selected' : ''}>${escH(T(STATUS[k].label))}</option>`).join('')}</select></label>`;
    $('#tlM').onchange = (e) => { S.m = e.target.value; S.all = false; writeHash(); drawMap(); drawPairs(); };
    $('#tlS').onchange = (e) => { S.s = e.target.value; S.all = false; writeHash(); drawMap(); drawPairs(); };
  }
  function th(key, label, sort) { const on = sort && sort[0] === key; return `<th scope="col"${on ? ` aria-sort="${sort[1] > 0 ? 'ascending' : 'descending'}"` : ''}><button type="button" class="pm-btn" data-k="${key}">${escH(label)}</button></th>`; }   // public_money.css draws the arrow from aria-sort
  function today(p) {
    const st = STATUS[p.status];
    const more = p.tt_routes ? T('{t} weekday trips ({o})', { t: fmt(p.tt_trips), o: p.tt_ops.join(', ') })
      : p.via ? T('timetabled routes join them with a transfer') : '';
    return `<span class="tl-chip" style="--c:${st.color}">${escH(T(st.label))}</span>${more ? ` <small>${escH(more)}</small>` : ''}`;
  }
  function byTimetable(p) {   // the fastest journey by timetable, its multiple of the car and its transfers, or why there is none
    if (p.tt_best == null) return p.tt_why ? `<small>${escH(T(p.tt_why === 1 ? 'no stop within 1 km of a centre' : 'none within 3 hours'))}</small>` : '—';
    const x = p.tt_xfers ? T(p.tt_xfers === 1 ? '1 transfer' : '{n} transfers', { n: fmt(p.tt_xfers) }) : T('direct');
    return `${fmt(p.tt_best)} <small>(${escH(p.tt_ratio != null ? T('{r} times the car', { r: fmt(p.tt_ratio, 1) }) + '; ' : '')}${escH(x)})</small>`;
  }
  function drawPairs() {
    const list = select(D.P, S.m, S.s, S.sort), t = tally(list), total = list.reduce((s, p) => s + p.workers, 0);
    const shown = S.all ? list : list.slice(0, TOP);
    const cap = S.m ? T('{n} pairs of {m} with workers travelling between them: {w} workers; {a} between pairs with a timetabled route, {b} with only a público route on the 2020 list, {c} with no route listed.', { n: fmt(list.length), m: name(S.m), w: fmt(total), a: fmt(t.timetable.workers), b: fmt(t.publico.workers), c: fmt(t.none.workers) })
      : T('{n} pairs of municipios, {w} workers. Select a heading to sort. Workers are survey estimates ({period}); ± is the margin of error.', { n: fmt(list.length), w: fmt(total), period: D.d.flows.period });
    const row = (p) => `<tr><th scope="row">${escH(pairName(p))}${p.low ? ` <small title="${escH(T('The margin of error is as large as the estimate'))}">${escH(T('low reliability'))}</small>` : ''}</th><td>${fmt(p.workers)} <small>± ${fmt(p.moe)}</small></td><td class="tl-l">${today(p)}</td><td>${p.publicos ? fmt(p.publicos) : '—'}</td><td>${fmt(p.km, 1)}</td><td>${fmt(p.min)}</td><td class="tl-l">${byTimetable(p)}</td><td>${p.nv_a != null ? `${pct(p.nv_a)} · ${pct(p.nv_b)}` : '—'}</td><td>${p.sim ? '#' + fmt(p.sim) : '—'}</td><td>${p.aadt_med ? fmt(p.aadt_med) : '—'}</td><td>${p.sim && p.deaths_5y != null && p.km ? fmt(10 * p.deaths_5y / p.km, 1) : '—'}</td><td>${p.along_res != null ? `${fmt(p.along_res)} <small>(${fmt(p.along_far)})</small>` : '—'}</td><td>${p.bridges_poor != null ? fmt(p.bridges_poor) : '—'}</td></tr>`;
    $('#tlPairs').innerHTML = `<table class="pm-table oz-table"><caption>${escH(cap)}</caption><thead><tr><th scope="col">${escH(T('Pair of municipios'))}</th>${th('workers', T('Workers who travel between them'), S.sort)}<th scope="col">${escH(T('Listed today'))}</th>${th('publicos', T('Público routes (2020 list)'), S.sort)}${th('km', T('Road distance, km'), S.sort)}${th('min', T('Minutes by car, no traffic'), S.sort)}${th('tt_best', T('By timetable, minutes (fastest, 6 to 9 a.m.)'), S.sort)}${th('nv', T('Households with no vehicle, each end'), S.sort)}${th('sim', T('Simulated connection'), S.sort)}${th('aadt_med', T('Traffic on its roads, vehicles a day'), S.sort)}${th('death_km', T('Road deaths on its roads, per 10 km, five years'), S.sort)}${th('along_res', T('Residents within 1 km of its roads (beyond 400 m of a stop)'), S.sort)}${th('bridges_poor', T('Bridges in poor condition on its roads'), S.sort)}</tr></thead>
      <tbody>${shown.map(row).join('')}</tbody></table>`
      + (list.length > shown.length ? `<p class="pm-small"><button type="button" class="pm-btn tl-more" id="tlAll">${escH(T('Show all {n} pairs', { n: fmt(list.length) }))}</button></p>` : '');
    $('#tlPairs').querySelectorAll('button[data-k]').forEach(b => { b.onclick = () => { const k = b.dataset.k; S.sort = [k, S.sort[0] === k ? -S.sort[1] : (k === 'sim' || k === 'km' || k === 'min' || k === 'tt_best' ? 1 : -1)]; drawPairs(); }; });
    if ($('#tlAll')) $('#tlAll').onclick = () => { S.all = true; drawPairs(); };
    $('#tlPairs').dataset.done = '1';
  }

  // ── The municipios ──
  function drawMunis() {
    const rows = D.ms.slice(), [k, dir] = S.msort;
    rows.sort((a, b) => (k === 'name' ? a.name.localeCompare(b.name, loc()) : (a[k] ?? -1) - (b[k] ?? -1)) * dir);
    const row = (r) => `<tr><th scope="row">${escH(r.name)}</th><td>${fmt(r.resident_workers)}</td><td>${fmt(r.work_elsewhere)}</td><td>${pct(r.work_elsewhere_pct)}</td><td>${fmt(r.come_in)}</td><td class="tl-l">${r.top_dest ? `${escH(name(r.top_dest))} <small>(${fmt(r.top_dest_workers)})</small>` : '—'}</td><td>${pct(r.linked_pct)}</td><td>${fmt(r.sim_links)}</td><td class="tl-l">${escH(r.own_system ? T(OWN[r.own_system]) : T('None listed'))}</td><td>${r.stop_km != null ? fmt(r.stop_km, 1) : '—'}</td><td>${pct(r.no_vehicle_pct)}</td><td>${pct(r.poverty_pct)}</td></tr>`;
    $('#tlMunis').innerHTML = `<table class="pm-table oz-table"><caption>${escH(T('Municipios: select a heading to sort. Workers 16 and over, {period}.', { period: D.d.flows.period }))}</caption><thead><tr>${th('name', T('Municipio'), S.msort)}${th('resident_workers', T('Workers who live here'), S.msort)}${th('work_elsewhere', T('Work in another municipio'), S.msort)}${th('work_elsewhere_pct', T('Share who work in another municipio'), S.msort)}${th('come_in', T('Come in from another municipio'), S.msort)}<th scope="col">${escH(T('Where most go'))}</th>${th('linked_pct', T('Share of that travel with a timetabled route'), S.msort)}${th('sim_links', T('Simulated connections'), S.msort)}<th scope="col">${escH(T('Its own transit system'))}</th>${th('stop_km', T('Nearest weekday timetable stop to the town centre, km'), S.msort)}${th('no_vehicle_pct', T('Households with no vehicle'), S.msort)}${th('poverty_pct', T('Below the poverty level'), S.msort)}</tr></thead>
      <tbody>${rows.map(row).join('')}</tbody></table>`;
    $('#tlMunis').querySelectorAll('button[data-k]').forEach(b => { b.onclick = () => { const kk = b.dataset.k; S.msort = [kk, S.msort[0] === kk ? -S.msort[1] : (kk === 'name' ? 1 : -1)]; drawMunis(); }; });
    $('#tlMunis').dataset.done = '1';
  }

  root.TransitLinksPage = { pairs, munis, select, tally, STATUS, ORDER };
})(typeof window !== 'undefined' ? window : globalThis);
