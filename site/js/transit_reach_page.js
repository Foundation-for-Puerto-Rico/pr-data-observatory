/* PR Data Observatory: the page "Transit, barrio by barrio" (transit-reach.html, Knowledge Area).
   Loads data/transit_reach.json (transit_reach.py: the class of each of the 901 barrios by the transit inside it), then data/barrios.geojson for the map.
   It shows the headline figures, a map with two views (the class of each barrio, or the share of households with no vehicle), the figures of a selected
   barrio and a sortable table of the municipios. It describes the published lists and recommends nothing. Every visible string goes through T(); its
   Spanish is in i18n_src/es/treach.json, written by docs/analysis/transit-reach-2026-11/make_page.py. The choices are kept in the address (#b=<geoid>&v=veh). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc && doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const day = (iso) => !iso ? '—' : new Date(iso + 'T12:00:00Z').toLocaleDateString(loc(), { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
  const escH = (s) => (typeof esc === 'function' ? esc(s) : String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
  // the three classes of transit_reach.py, from the top of the legend down
  const CLASS = {
    3: { label: 'A stop with a current timetable', color: '#e7e3d8' },
    2: { label: 'Only service without a current timetable', color: '#7f90a6' },
    1: { label: 'Nothing on file', color: '#272b33' },
  };
  const PASS = '#e0a800', LINE = '#d7301f';
  // households with no vehicle (ACS B25044): five steps
  const VEH = [[5, '#eff3ff'], [10, '#bdd7e7'], [20, '#6baed6'], [30, '#3182bd'], [Infinity, '#08519c']];
  const vehColor = (v) => VEH.find(([top]) => v < top)[1];
  const vehLabels = () => [T('Under 5%'), T('5% to 10%'), T('10% to 20%'), T('20% to 30%'), T('30% or more')];
  const S = { b: null, v: 'cls', sort: ['p_out', -1] };
  let D = null, GEO = null, PROJ = null;

  // ── Figures from the file (pure) ──
  const objects = (d, fields, rows) => d[rows].map(r => Object.fromEntries(d[fields].map((f, i) => [f, r[i]])));
  function barrios(d) { return objects(d, 'barrio_fields', 'barrios'); }
  function munis(d) { return objects(d, 'muni_fields', 'municipios').map(m => ({ ...m, p_out: m.p2 + m.p1, share_out: m.pop ? (m.p2 + m.p1) / m.pop * 100 : null })); }

  // ── The page ──
  if (doc && $('#trNow')) fetchJson('data/transit_reach.json').then(d => {
    D = { d, B: new Map(barrios(d).map(b => [b.geoid, b])), M: new Map(munis(d).map(m => [m.geoid, m])) };
    readHash(); drawNow(); drawToggle(); drawMunis();
    fetchJson('data/barrios.geojson').then(g => { GEO = g; drawMap(); drawBarrio(); }, e => {
      $('#trMap').innerHTML = `<p class="pm-p">${escH(T('The map could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }, (e) => {
    $('#trNow').innerHTML = `<p class="pm-p">${escH(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  function readHash() {
    const q = new URLSearchParams((root.location.hash || '').slice(1));
    if (D.B.has(q.get('b'))) S.b = q.get('b');
    if (q.get('v') === 'veh') S.v = 'veh';
  }
  function writeHash() {
    const h = [S.b ? `b=${S.b}` : '', S.v === 'veh' ? 'v=veh' : ''].filter(Boolean).join('&');
    if ((root.location.hash || '').slice(1) !== h) root.history.replaceState(null, '', h ? '#' + h : root.location.pathname + root.location.search);
  }

  function card(color, label, value, sub) {
    return `<div class="oz-card"><i style="background:${color}" aria-hidden="true"></i><div><div class="oz-v">${escH(value)}</div><div class="oz-l">${escH(label)}</div><div class="oz-s">${escH(sub)}</div></div></div>`;
  }
  function drawNow() {
    const p = D.d.pr;
    $('#trNow').innerHTML = `<div class="oz-cards">${[
      card(CLASS[3].color, T('Barrios with a stop with a current timetable'), fmt(p.b3), T('of {n}; {s} of residents', { n: fmt(p.barrios), s: pct(p.p3_share) })),
      card(CLASS[2].color, T('Barrios with only service without a timetable'), fmt(p.b2), T('{s} of residents', { s: pct(p.p2_share) })),
      card(CLASS[1].color, T('Barrios with nothing on file'), fmt(p.b1), T('{n} residents', { n: fmt(p.p1) })),
      card(PASS, T('A route passes, with no stop'), fmt(p.passes), T('{n} residents', { n: fmt(p.pop_passes) })),
      card('#6baed6', T('Households with no vehicle outside a barrio with a current stop'), fmt(p.hh_no_vehicle_outside), T('of {n} in Puerto Rico (ACS 2020-2024)', { n: fmt(p.hh_no_vehicle) }))].join('')}</div>`;
    $('#trNow').dataset.done = '1';
  }

  function drawToggle() {
    const b = (v, label) => `<button type="button" class="pm-btn tr-tab" data-v="${v}" aria-pressed="${S.v === v}">${escH(label)}</button>`;
    $('#trToggle').innerHTML = `<span role="group" aria-label="${escH(T('Map view'))}">${b('cls', T('Transit'))}${b('veh', T('Households with no vehicle'))}</span>`;
    $('#trToggle').querySelectorAll('button').forEach(x => { x.onclick = () => { S.v = x.dataset.v; writeHash(); drawToggle(); drawMap(); }; });
  }

  // ── The map ──
  function project() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const rings = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
    GEO.features.forEach(f => rings(f.geometry).forEach(p => p.forEach(r => r.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }))));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = Math.ceil((y1 - y0) * sc);
    const pt = ([x, y]) => [((x - x0) * k * sc).toFixed(1), ((y1 - y) * sc).toFixed(1)];
    const path = (g) => rings(g).map(p => p.map(r => { let last = '', s = ''; r.forEach(c => { const q = pt(c).join(','); if (q !== last) { s += (s ? 'L' : 'M') + q; last = q; } }); return s + 'Z'; }).join('')).join('');
    const line = (parts) => parts.map(r => r.map((c, i) => (i ? 'L' : 'M') + pt(c).join(',')).join('')).join('');
    PROJ = { W, H, paths: GEO.features.map(f => ({ id: f.properties.geoid, d: path(f.geometry) })), lines: D.d.lines.map(l => ({ name: l.name, d: line(l.c) })) };
  }
  function label(b) {
    const m = D.M.get(b.mun), where = `${b.name}, ${m ? m.name : b.mun}`;
    if (S.v === 'veh') return T('{b}: households with no vehicle {v}', { b: where, v: b.noveh_pct == null ? '—' : pct(b.noveh_pct) + (b.low ? ' (' + T('unreliable') + ')' : '') });
    return T('{b}: {c}', { b: where, c: T(CLASS[b.cls].label).toLowerCase() }) + (b.passes ? ' · ' + T('a route passes, with no stop') : '');
  }
  function fill(b) {
    if (!b.pop) return 'url(#trHatch)';
    if (S.v === 'veh') return b.noveh_pct == null ? '#f2f2f2' : vehColor(b.noveh_pct);
    return CLASS[b.cls].color;
  }
  function drawMap() {
    if (!GEO) return;
    if (!PROJ) project();
    let body = '', edge = '';
    const n = { 3: 0, 2: 0, 1: 0, none: 0, passes: 0, low: 0 };
    for (const p of PROJ.paths) {
      const b = D.B.get(p.id); if (!b) continue;
      if (!b.pop) n.none++; else n[b.cls]++;
      const faint = S.v === 'veh' && b.low && b.pop ? ' fill-opacity=".45"' : '';
      if (S.v === 'veh' && b.low && b.pop) n.low++;
      body += `<path d="${p.d}" data-id="${p.id}" fill="${fill(b)}"${faint}${p.id === S.b ? ' class="on"' : ''}><title>${escH(label(b))}</title></path>`;
      if (S.v === 'cls' && b.passes) { n.passes++; edge += `<path d="${p.d}" class="tr-pass"/>`; }
    }
    const lines = S.v === 'cls' ? `<g class="tr-lines">${PROJ.lines.map(l => `<path d="${l.d}"><title>${escH(l.name)}</title></path>`).join('')}</g>` : '';
    const title = S.v === 'cls'
      ? T('Map of the {n} barrios of Puerto Rico: {a} with a stop with a current timetable, {b} with only service without a timetable, {c} with nothing on file', { n: fmt(PROJ.paths.length), a: fmt(n[3]), b: fmt(n[2]), c: fmt(n[1]) })
      : T('Map of the {n} barrios of Puerto Rico by the share of households with no vehicle', { n: fmt(PROJ.paths.length) });
    const legend = S.v === 'cls'
      ? [3, 2, 1].map(k => `<span class="pm-keyrow"><i style="background:${CLASS[k].color}"></i>${escH(T(CLASS[k].label))} (${fmt(n[k])})</span>`).join('')
        + `<span class="pm-keyrow"><i class="tr-passkey"></i>${escH(T('A route with a current timetable passes, with no stop'))} (${fmt(n.passes)})</span>`
        + `<span class="pm-keyrow"><i class="tr-linekey"></i>${escH(T('Tren Urbano and ferries'))}</span>`
      : VEH.map(([, c], i) => `<span class="pm-keyrow"><i style="background:${c}"></i>${escH(vehLabels()[i])}</span>`).join('')
        + `<span class="pm-keyrow"><i style="background:#6baed6;opacity:.45"></i>${escH(T('Lighter: estimate unreliable'))} (${fmt(n.low)})</span>`;
    $('#trMap').innerHTML = `<svg viewBox="0 0 ${PROJ.W} ${PROJ.H}" width="100%" role="img" aria-label="${escH(title)}"><defs><pattern id="trHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#f7f7f8"/><line x1="0" y1="0" x2="0" y2="6" stroke="#d3d6dc" stroke-width="2"/></pattern></defs>`
      + `<g class="tr-g">${body}</g><g class="tr-edge">${edge}</g>${lines}</svg>`
      + `<div class="pm-legend oz-legend">${legend}<span class="pm-keyrow"><i class="oz-none"></i>${escH(T('No residents'))} (${fmt(n.none)})</span></div>`;
    $('#trMap svg').addEventListener('click', (e) => { const p = e.target.closest('path[data-id]'); if (!p) return; S.b = p.dataset.id; writeHash(); mark(); drawBarrio(); });
    $('#trMapNote').textContent = S.v === 'cls'
      ? T('Select a barrio for its figures. Timetables as of {d}.', { d: day(D.d.as_of) })
      : T('Select a barrio for its figures. Lighter barrios have fewer than {n} residents or a margin of error as large as the estimate.', { n: fmt(D.d.rules.min_pop) });
    mark();
    $('#trMap').dataset.done = '1';
  }
  function mark() { const p = S.b && $(`#trMap path[data-id="${S.b}"]`); if (p) { p.classList.add('on'); p.parentNode.appendChild(p); } }
  function drawBarrio() {
    const b = S.b && D.B.get(S.b), box = $('#trBarrio');
    if (!b) { box.innerHTML = `<p class="pm-p">${escH(T('No barrio selected.'))}</p>`; return; }
    const m = D.M.get(b.mun) || {};
    const rows = [
      [T('Class'), b.pop ? T(CLASS[b.cls].label) : T('No residents')],
      [T('Municipio'), m.name || b.mun],
      [T('Stops with a current timetable'), fmt(b.cur)], [T('Stops whose timetable has ended'), fmt(b.expired)], [T('Stops mapped in OpenStreetMap, no timetable'), fmt(b.osm)],
      [T('Público routes of the 2020 list that cross it'), fmt(b.publicos)],
      [T('A route with a current timetable passes, with no stop'), b.passes ? T('Yes') : T('No')],
      [T('Residents (2020 Census)'), fmt(b.pop)], [T('Residents within 400 m of a stop with a current timetable, timetables of {d}', { d: day(D.d.pr.pop_400m_as_of) }), fmt(b.pop_400m)],
      [T('Households (ACS 2020-2024)'), fmt(b.hh)],
      [T('Households with no vehicle (ACS 2020-2024)'), b.noveh_pct == null ? '—' : T('{v} ± {m}', { v: pct(b.noveh_pct), m: fmt(b.noveh_moe, 1) }) + (b.low ? ' · ' + T('unreliable') : '')],
    ];
    if (m.ntd_no_feed) rows.push([T('Municipal system'), T('{m} reports a bus system to the National Transit Database but publishes no timetable', { m: m.name })]);
    box.innerHTML = `<h3 class="oz-h3">${escH(b.name)} <small>${escH(b.geoid)}</small></h3><dl class="oz-dl">${rows.map(([k, v]) => `<dt>${escH(k)}</dt><dd>${escH(v)}</dd>`).join('')}</dl>`;
  }

  // ── The municipios ──
  function th(key, lab) { const on = S.sort[0] === key; return `<th scope="col"${on ? ` aria-sort="${S.sort[1] > 0 ? 'ascending' : 'descending'}"` : ''}><button type="button" class="pm-btn" data-k="${key}">${escH(lab)}${on ? (S.sort[1] > 0 ? ' ▲' : ' ▼') : ''}</button></th>`; }
  function sysLabel(s) { return s === 'current' ? T('Current timetable') : s === 'expired' ? T('Timetable ended') : s === 'none' ? T('Reports to the NTD, no timetable') : '—'; }
  function drawMunis() {
    const rows = munis(D.d), [k, dir] = S.sort, p = D.d.pr;
    rows.sort((a, b) => (k === 'name' ? a.name.localeCompare(b.name, loc()) : (a[k] ?? -1) - (b[k] ?? -1)) * dir);
    const row = (r, cls = '') => `<tr${cls}><th scope="row">${escH(r.name)}</th><td>${fmt(r.barrios)}</td><td>${fmt(r.b3)}</td><td>${fmt(r.b2)}</td><td>${fmt(r.b1)}</td><td>${fmt(r.passes)}</td><td>${fmt(r.pop)}</td><td>${fmt(r.p_out)}</td><td>${pct(r.share_out)}</td><td>${escH(r.system === undefined ? '' : sysLabel(r.system))}</td></tr>`;
    $('#trMunis').innerHTML = `<table class="pm-table oz-table"><caption>${escH(T('Municipios: select a heading to sort. Residents of the 2020 Census.'))}</caption><thead><tr>${th('name', T('Municipio'))}${th('barrios', T('Barrios'))}${th('b3', T('With a current timetable'))}${th('b2', T('Only without a timetable'))}${th('b1', T('Nothing on file'))}${th('passes', T('A route passes, no stop'))}${th('pop', T('Residents'))}${th('p_out', T('Residents without a current stop in their barrio'))}${th('share_out', T('Share'))}<th scope="col">${escH(T('Municipal system'))}</th></tr></thead>
      <tbody>${row({ name: T('Puerto Rico'), barrios: p.barrios, b3: p.b3, b2: p.b2, b1: p.b1, passes: p.passes, pop: p.pop, p_out: p.p_out, share_out: p.p_out_share }, ' class="oz-pr"')}${rows.map(r => row(r)).join('')}</tbody></table>`;
    $('#trMunis').querySelectorAll('button[data-k]').forEach(b => { b.onclick = () => { const kk = b.dataset.k; S.sort = [kk, S.sort[0] === kk ? -S.sort[1] : (kk === 'name' ? 1 : -1)]; drawMunis(); }; });
    $('#trMunis').dataset.done = '1';
  }

  root.TransitReachPage = { barrios, munis, vehColor, CLASS };
})(typeof window !== 'undefined' ? window : globalThis);
