/* PR Data Observatory: the Opportunity Zones 2.0 page (opportunity-zones.html, Knowledge Area; HANDOFF decision 103).
   Loads data/opportunity_zones.json (opportunity_zones.py: the US Treasury's 2027 designations and eligible tracts, the 2018 round, 2020 Census residents),
   then data/geo/tracts.geojson for the map. From these it shows:
     - the figures of the designation: tracts, rural or not, residents, the 25 percent limit, the first round;
     - a map of the 2020 census tracts: zones (rural or not), eligible but not designated, not eligible; a click on a tract gives its figures;
     - the municipios: tracts, eligible, zones and the residents in zones (sortable);
     - the barrios of a municipio, or the 25 barrios with the most residents in zones;
     - how a tract qualified: its poverty rate against its median family income as a percent of its area's, with the law's lines;
     - the first round (2018-2027) against the second (2027-2036).
   It describes the federal designation and recommends nothing (decision 103). Every visible string goes through T(); its Spanish is in
   i18n_src/es/oppzones.json, written by docs/analysis/opportunity-zones-2026-11/make_page.py. The choices are kept in the address (#t=<tract>&m=<municipio>). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc && doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const day = (iso) => !iso ? '—' : new Date(iso + 'T12:00:00Z').toLocaleDateString(loc(), { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });   // 2027-12-31 as December 31, 2027 / 31 de diciembre de 2027
  const escH = (s) => (typeof esc === 'function' ? esc(s) : String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
  // the four statuses of a tract (opportunity_zones.py), from the top of the map down; 'none': a tract with no residents (no figures, not eligible)
  const STATUS = {
    2: { label: 'Zone, rural', color: '#e66101' },
    1: { label: 'Zone, not rural', color: '#5e3c99' },
    0: { label: 'Eligible, not designated', color: '#c9c1ae' },
    '-1': { label: 'Not eligible', color: '#eceef1' },
  };
  const ORDER = [2, 1, 0, -1];
  const RULE = { ratio: 70, pov: 20, cap: 125 };   // 26 U.S.C. 1400Z-1(c)(1) as amended by P.L. 119-21: income at most 70% of the area's, or poverty 20% or more with income at most 125%
  const S = { t: null, m: '', sort: ['pop_designated', -1] };
  let D = null, GEO = null, PROJ = null;

  // ── Figures from the file (pure: tests/oz_page.test.js) ──
  const objects = (d, fields, rows) => d[rows].map(r => Object.fromEntries(d[fields].map((f, i) => [f, r[i]])));
  function tracts(d) { return objects(d, 'tract_fields', 'tracts'); }
  function munis(d) { return objects(d, 'muni_fields', 'municipios').map(m => ({ ...m, share: m.pop ? m.pop_designated / m.pop * 100 : null })); }
  /** The barrios of a municipio, most in a zone first; or, with no municipio, the `top` barrios with the most residents in zones. */
  function barrios(d, mun, top = 25) {
    const all = objects(d, 'barrio_fields', 'barrios').map(b => ({ ...b, share: b.pop ? b.pop_designated / b.pop * 100 : null }));
    if (mun) return all.filter(b => b.mun === mun).sort((p, q) => (q.share - p.share) || (q.pop_designated - p.pop_designated) || (q.pop - p.pop));
    return all.filter(b => b.pop_designated > 0).sort((p, q) => q.pop_designated - p.pop_designated || q.pop - p.pop).slice(0, top);
  }
  /** Whether the law's test makes a tract a low-income community, from the two figures Treasury published (no income: the poverty test alone). */
  function eligibleByRule(pov, ratio) { return ratio == null ? pov != null && pov >= RULE.pov : ratio <= RULE.ratio || (pov != null && pov >= RULE.pov && ratio <= RULE.cap); }
  /** How many tracts have each status; tracts with no residents apart. */
  function counts(d) {
    const c = { 2: 0, 1: 0, 0: 0, '-1': 0, none: 0 };
    tracts(d).forEach(t => { if (t.status < 0 && !t.pop) c.none++; else c[t.status]++; });
    return c;
  }
  const statusOf = (t) => (t.status < 0 && !t.pop ? 'none' : t.status);

  // ── The page ──
  if (doc && $('#ozNow')) fetchJson('data/opportunity_zones.json').then(d => {
    D = { d, T: new Map(tracts(d).map(t => [t.id, t])), M: new Map(munis(d).map(m => [m.id, m])) };
    readHash(); drawNow(); drawMunis(); drawBarrioPick(); drawBarrios(); drawScatter(); drawGroups(); drawRounds();
    fetchJson('data/geo/tracts.geojson').then(g => { GEO = g; drawMap(); drawTract(); }, e => {
      $('#ozMap').innerHTML = `<p class="pm-p">${escH(T('The map could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }, (e) => {
    $('#ozNow').innerHTML = `<p class="pm-p">${escH(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  function readHash() {
    const q = new URLSearchParams((root.location.hash || '').slice(1));
    if (D.T.has(q.get('t'))) S.t = q.get('t');
    if (D.M.has(q.get('m'))) S.m = q.get('m');
  }
  function writeHash() {
    const h = [S.t ? `t=${S.t}` : '', S.m ? `m=${S.m}` : ''].filter(Boolean).join('&');
    if ((root.location.hash || '').slice(1) !== h) root.history.replaceState(null, '', h ? '#' + h : root.location.pathname + root.location.search);
  }

  function card(color, label, value, sub) {
    return `<div class="oz-card"><i style="background:${color}" aria-hidden="true"></i><div><div class="oz-v">${escH(value)}</div><div class="oz-l">${escH(label)}</div><div class="oz-s">${escH(sub)}</div></div></div>`;
  }
  function drawNow() {
    const p = D.d.pr, r = D.d.first_round;
    $('#ozNow').innerHTML = `<div class="oz-cards">${[
      card('#5e3c99', T('Census tracts designated'), fmt(p.designated), T('of {e} eligible; the limit was {l}', { e: fmt(p.eligible), l: fmt(p.limit) })),
      card('#e66101', T('Of them, rural zones'), fmt(p.rural), T('{n} not rural', { n: fmt(p.non_rural) })),
      card('#5e3c99', T('Residents in a zone'), fmt(p.pop_designated), T('{s} of Puerto Rico, 2020 Census', { s: pct(p.pop_share) })),
      card('#c9c1ae', T('Municipios with a zone'), fmt(p.municipios_with_zone), T('of 78')),
      card('#8a8f99', T('Zones of the first round'), fmt(r.tracts), T('{s} of residents (2010 Census); they end {d}', { s: pct(r.pop_share), d: day(r.ends) }))].join('')}</div>`;
    $('#ozNow').dataset.done = '1';
  }

  // ── The map of the tracts ──
  function project() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const rings = (g) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates);
    GEO.features.forEach(f => rings(f.geometry).forEach(p => p.forEach(r => r.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }))));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = Math.ceil((y1 - y0) * sc);
    const pt = ([x, y]) => [((x - x0) * k * sc).toFixed(1), ((y1 - y) * sc).toFixed(1)];
    const path = (g) => rings(g).map(p => p.map(r => { let last = '', s = ''; r.forEach(c => { const q = pt(c).join(','); if (q !== last) { s += (s ? 'L' : 'M') + q; last = q; } }); return s + 'Z'; }).join('')).join('');
    PROJ = { W, H, paths: GEO.features.map(f => ({ id: f.properties.GEOID, d: path(f.geometry) })) };
  }
  function tractLabel(t) {
    const m = D.M.get(t.mun), st = statusOf(t);
    return T('Census tract {t}, {muni}: {status}', { t: t.tract, muni: m ? m.name : t.mun, status: st === 'none' ? T('no residents') : T(STATUS[st].label).toLowerCase() });
  }
  function drawMap() {
    if (!GEO) return;
    if (!PROJ) project();
    const by = { 2: '', 1: '', 0: '', '-1': '', none: '' }, n = { 2: 0, 1: 0, 0: 0, '-1': 0, none: 0 };
    for (const p of PROJ.paths) {
      const t = D.T.get(p.id); if (!t) continue;
      const st = statusOf(t); n[st]++;
      by[st] += `<path d="${p.d}" data-id="${p.id}" tabindex="-1" fill="${st === 'none' ? 'url(#ozHatch)' : STATUS[st].color}"${p.id === S.t ? ' class="on"' : ''}><title>${escH(tractLabel(t))}</title></path>`;
    }
    const title = T('Map of the {n} census tracts of Puerto Rico: {z} Opportunity Zones ({r} rural), {e} eligible tracts not designated', { n: fmt(PROJ.paths.length), z: fmt(n[2] + n[1]), r: fmt(n[2]), e: fmt(n[0]) });
    $('#ozMap').innerHTML = `<svg viewBox="0 0 ${PROJ.W} ${PROJ.H}" width="100%" role="img" aria-label="${escH(title)}"><defs><pattern id="ozHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#f7f7f8"/><line x1="0" y1="0" x2="0" y2="6" stroke="#d3d6dc" stroke-width="2"/></pattern></defs>`
      + ['none', -1, 0, 1, 2].map(k => `<g class="oz-g">${by[k]}</g>`).join('') + `</svg>`
      + `<div class="pm-legend oz-legend">${ORDER.map(k => `<span class="pm-keyrow"><i style="background:${STATUS[k].color}"></i>${escH(T(STATUS[k].label))} (${fmt(n[k])})</span>`).join('')}<span class="pm-keyrow"><i class="oz-none"></i>${escH(T('No residents'))} (${fmt(n.none)})</span></div>`;
    $('#ozMap svg').addEventListener('click', (e) => { const p = e.target.closest('path[data-id]'); if (!p) return; S.t = p.dataset.id; writeHash(); mark(); drawTract(); });
    $('#ozMapNote').textContent = T('Select a census tract for its figures. Tracts are drawn from the Census Bureau\'s 1:500,000 outlines; {w} tracts that are only water are not drawn.', { w: fmt(D.d.tracts.length - PROJ.paths.length) });
    $('#ozMap').dataset.done = '1';
  }
  function mark() { $('#ozMap').querySelectorAll('path.on').forEach(p => p.classList.remove('on')); const p = S.t && $(`#ozMap path[data-id="${S.t}"]`); if (p) { p.classList.add('on'); p.parentNode.appendChild(p); } }
  function drawTract() {
    const t = S.t && D.T.get(S.t), box = $('#ozTract');
    if (!t) { box.innerHTML = `<p class="pm-p">${escH(T('No tract selected.'))}</p>`; return; }
    const m = D.M.get(t.mun), st = statusOf(t), area = D.d.areas[t.area] || {};
    const bs = (t.barrios || []).map(b => (D.d.barrios.find(r => r[0] === b) || [])[2]).filter(Boolean);
    const rows = [
      [T('Status'), st === 'none' ? T('No residents') : T(STATUS[st].label)],
      [T('Municipio'), m ? m.name : t.mun],
      [T('Barrios with residents in the tract'), bs.length ? bs.join(', ') : '—'],
      [T('Residents (2020 Census)'), fmt(t.pop)], [T('Housing units (2020 Census)'), fmt(t.hu)], [T('Land area'), T('{v} km²', { v: fmt(t.km2, 1) })],
      [T('Poverty rate (ACS 2020-2024)'), pct(t.pov)],
      [T('Median family income (ACS 2020-2024)'), t.mfi == null ? '—' : T('${v}', { v: fmt(t.mfi) })],
      [T('As a percent of the area\'s median family income'), t.mfi_pct == null ? '—' : T('{v} of the median of {area} ({a})', { v: pct(t.mfi_pct), area: area.name === 'Puerto Rico' ? T('Puerto Rico outside a metropolitan or micropolitan area') : area.name, a: T('${v}', { v: fmt(area.mfi) }) })],
      [T('Rural under the law\'s definition'), t.rural ? T('Yes') : T('No')],
    ];
    box.innerHTML = `<h3 class="oz-h3">${escH(T('Census tract {t}', { t: t.tract }))} <small>${escH(t.id)}</small></h3><dl class="oz-dl">${rows.map(([k, v]) => `<dt>${escH(k)}</dt><dd>${escH(v)}</dd>`).join('')}</dl>`;
  }

  // ── The municipios ──
  function th(key, label, sort) { const on = sort && sort[0] === key; return `<th scope="col"${on ? ` aria-sort="${sort[1] > 0 ? 'ascending' : 'descending'}"` : ''}><button type="button" class="pm-btn" data-k="${key}">${escH(label)}${on ? (sort[1] > 0 ? ' ▲' : ' ▼') : ''}</button></th>`; }
  function drawMunis() {
    const rows = munis(D.d), [k, dir] = S.sort, p = D.d.pr;
    rows.sort((a, b) => (k === 'name' ? a.name.localeCompare(b.name, loc()) : (a[k] ?? -1) - (b[k] ?? -1)) * dir);
    const row = (r, cls = '') => `<tr${cls}><th scope="row">${escH(r.name)}</th><td>${fmt(r.tracts_with_residents)}</td><td>${fmt(r.eligible)}</td><td>${fmt(r.designated)}</td><td>${fmt(r.rural)}</td><td>${fmt(r.pop_designated)}</td><td>${pct(r.share)}</td><td>${fmt(r.pop_eligible)}</td></tr>`;
    $('#ozMunis').innerHTML = `<table class="pm-table oz-table"><caption>${escH(T('Municipios: select a heading to sort. Residents of the 2020 Census.'))}</caption><thead><tr>${th('name', T('Municipio'), S.sort)}${th('tracts_with_residents', T('Tracts with residents'), S.sort)}${th('eligible', T('Eligible tracts'), S.sort)}${th('designated', T('Zones'), S.sort)}${th('rural', T('Rural zones'), S.sort)}${th('pop_designated', T('Residents in zones'), S.sort)}${th('share', T('Share of residents in zones'), S.sort)}${th('pop_eligible', T('Residents in eligible tracts'), S.sort)}</tr></thead>
      <tbody>${row({ name: T('Puerto Rico'), ...p, share: p.pop_share }, ' class="oz-pr"')}${rows.map(r => row(r)).join('')}</tbody></table>`;
    $('#ozMunis').querySelectorAll('button[data-k]').forEach(b => { b.onclick = () => { const kk = b.dataset.k; S.sort = [kk, S.sort[0] === kk ? -S.sort[1] : (kk === 'name' ? 1 : -1)]; drawMunis(); }; });
    $('#ozMunis').dataset.done = '1';
  }

  // ── The barrios ──
  function drawBarrioPick() {
    const ms = munis(D.d).sort((a, b) => a.name.localeCompare(b.name, loc()));
    $('#ozBarrioPick').innerHTML = `<label>${escH(T('Show'))} <select id="ozM"><option value="">${escH(T('The 25 barrios with the most residents in zones'))}</option>${ms.map(m => `<option value="${m.id}"${m.id === S.m ? ' selected' : ''}>${escH(T('The barrios of {m}', { m: m.name }))}</option>`).join('')}</select></label>`;
    $('#ozM').onchange = (e) => { S.m = e.target.value; writeHash(); drawBarrios(); };
  }
  function drawBarrios() {
    const rows = barrios(D.d, S.m), m = S.m && D.M.get(S.m);
    const cap = m ? T('The {n} barrios of {m} with residents, most in a zone first', { n: rows.length, m: m.name }) : T('The {n} barrios with the most residents in zones, of {all} with residents', { n: rows.length, all: fmt(D.d.barrios.length) });
    $('#ozBarrios').innerHTML = `<table class="pm-table oz-table"><caption>${escH(cap)}</caption><thead><tr><th scope="col">${escH(T('Barrio'))}</th><th scope="col">${escH(T('Municipio'))}</th><th scope="col">${escH(T('Residents'))}</th><th scope="col">${escH(T('In a zone'))}</th><th scope="col">${escH(T('Share in a zone'))}</th><th scope="col">${escH(T('In an eligible tract'))}</th></tr></thead>
      <tbody>${rows.map(b => `<tr><th scope="row">${escH(b.name)}</th><td>${escH((D.M.get(b.mun) || {}).name || b.mun)}</td><td>${fmt(b.pop)}</td><td>${fmt(b.pop_designated)}</td><td>${pct(b.share)}</td><td>${fmt(b.pop_eligible)}</td></tr>`).join('')}</tbody></table>`;
    $('#ozBarrios').dataset.done = '1';
  }

  // ── How a tract qualified ──
  function drawScatter() {
    const W = 720, H = 420, L = 52, R = 14, Tp = 14, B = 46, XM = 250, x = (v) => L + Math.min(v, XM) / XM * (W - L - R), y = (v) => Tp + (1 - Math.min(v, 100) / 100) * (H - Tp - B);
    const ts = tracts(D.d).filter(t => t.pop > 0 && t.pov != null && t.mfi_pct != null), noIncome = tracts(D.d).filter(t => t.pop > 0 && t.mfi_pct == null).length;
    let pts = '';
    for (const k of [-1, 0, 1, 2]) ts.filter(t => t.status === k).forEach(t => { pts += `<circle cx="${x(t.mfi_pct).toFixed(1)}" cy="${y(t.pov).toFixed(1)}" r="${k > 0 ? 3.2 : 2.4}" fill="${k < 0 ? '#9aa0aa' : STATUS[k].color}"${k < 0 ? ' fill-opacity=".55"' : ''}><title>${escH(tractLabel(t) + ' · ' + T('poverty {p}, income {i} of the area median', { p: pct(t.pov), i: pct(t.mfi_pct) }))}</title></circle>`; });
    const gx = [0, 50, 100, 150, 200, 250], gy = [0, 20, 40, 60, 80, 100];
    const grid = gx.map(v => `<line x1="${x(v)}" x2="${x(v)}" y1="${Tp}" y2="${H - B}" class="oz-grid"/><text x="${x(v)}" y="${H - B + 16}" text-anchor="middle">${escH(v === XM ? '≥ ' + fmt(v) : fmt(v))}</text>`).join('')
      + gy.map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="oz-grid"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`).join('');
    const zone = `<rect x="${L}" y="${Tp}" width="${x(RULE.ratio) - L}" height="${H - Tp - B}" class="oz-elig"/><rect x="${x(RULE.ratio)}" y="${Tp}" width="${x(RULE.cap) - x(RULE.ratio)}" height="${y(RULE.pov) - Tp}" class="oz-elig"/>`;
    const lines = `<line x1="${x(RULE.ratio)}" x2="${x(RULE.ratio)}" y1="${Tp}" y2="${H - B}" class="oz-rule"/><line x1="${x(RULE.cap)}" x2="${x(RULE.cap)}" y1="${Tp}" y2="${y(RULE.pov)}" class="oz-rule"/><line x1="${x(RULE.ratio)}" x2="${x(RULE.cap)}" y1="${y(RULE.pov)}" y2="${y(RULE.pov)}" class="oz-rule"/>`;
    const title = T('Scatter plot of {n} census tracts: poverty rate against median family income as a percent of the area median, with the eligibility lines at 70% and 125% of income and 20% poverty', { n: fmt(ts.length) });
    $('#ozScatter').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${escH(title)}" class="oz-sc">${zone}${grid}${lines}${pts}`
      + `<text x="${(L + W - R) / 2}" y="${H - 8}" text-anchor="middle" class="oz-ax">${escH(T('Median family income, as a percent of the area median (ACS 2020-2024)'))}</text>`
      + `<text transform="translate(14 ${(Tp + H - B) / 2}) rotate(-90)" text-anchor="middle" class="oz-ax">${escH(T('Poverty rate, %'))}</text></svg>`
      + `<div class="pm-legend oz-legend"><span class="pm-keyrow"><i class="oz-eligkey"></i>${escH(T('Eligible by the law\'s test'))}</span>${[2, 1, 0].map(k => `<span class="pm-keyrow"><i style="background:${STATUS[k].color}"></i>${escH(T(STATUS[k].label))}</span>`).join('')}<span class="pm-keyrow"><i style="background:#9aa0aa"></i>${escH(T('Not eligible'))}</span></div>`;
    $('#ozScatterNote').textContent = T('{n} tracts with residents and both figures are drawn; {m} tracts with residents but no median family income in the survey are left out (Treasury applied the poverty test alone to them). Incomes above 250% are drawn at the right edge.', { n: fmt(ts.length), m: fmt(noIncome) });
    $('#ozScatter').dataset.done = '1';
  }
  function drawGroups() {
    const G = D.d.groups, rows = [['designated_rural', T('Zones, rural')], ['designated_non_rural', T('Zones, not rural')], ['eligible', T('Eligible, not designated')], ['not_eligible', T('Not eligible (with residents)')]];
    $('#ozGroups').innerHTML = `<table class="pm-table oz-table"><caption>${escH(T('The tracts by status: medians of the figures Treasury used (ACS 2020-2024)'))}</caption><thead><tr><th scope="col">${escH(T('Tracts'))}</th><th scope="col">${escH(T('Number'))}</th><th scope="col">${escH(T('Residents (2020 Census)'))}</th><th scope="col">${escH(T('Median poverty rate'))}</th><th scope="col">${escH(T('Median income, % of the area median'))}</th></tr></thead>
      <tbody>${rows.map(([k, lab]) => `<tr><th scope="row">${escH(lab)}</th><td>${fmt(G[k].tracts)}</td><td>${fmt(G[k].pop)}</td><td>${pct(G[k].median_pov)}</td><td>${pct(G[k].median_ratio)}</td></tr>`).join('')}</tbody></table>`;
  }

  // ── The two rounds ──
  function drawRounds() {
    const p = D.d.pr, r = D.d.first_round, v = D.d.vintage;
    const rows = [
      [T('Zones'), T('{n} of {all} census tracts', { n: fmt(r.tracts), all: fmt(r.tracts_2010) }), T('{n} of {all} census tracts', { n: fmt(p.designated), all: fmt(p.tracts) })],
      [T('Census geography'), T('2010 tracts'), T('2020 tracts')],
      [T('Residents in zones'), T('{n} ({s} of the 2010 Census)', { n: fmt(r.pop_in_zones_2010), s: pct(r.pop_share) }), T('{n} ({s} of the 2020 Census)', { n: fmt(p.pop_designated), s: pct(p.pop_share) })],
      [T('How the tracts became zones'), T('Every low-income tract was deemed a zone by law ({lic} tracts), with {c} tracts next to them', { lic: fmt(r.low_income), c: fmt(r.contiguous) }), T('Puerto Rico\'s government could nominate up to a quarter of the {e} eligible tracts ({l}); it nominated {n} and Treasury designated them all', { e: fmt(p.eligible), l: fmt(p.limit), n: fmt(p.designated) })],
      [T('Rural zones with larger benefits'), T('No'), T('{r} of the {n}', { r: fmt(p.rural), n: fmt(p.designated) })],
      [T('In effect'), T('Through {d}', { d: day(r.ends) }), T('From {a} to {b}', { a: day(v.starts), b: day(v.ends) })],
    ];
    $('#ozRounds').innerHTML = `<table class="pm-table oz-table"><caption>${escH(T('The first and second rounds of Opportunity Zones in Puerto Rico'))}</caption><thead><tr><th scope="col"></th><th scope="col">${escH(T('First round (2018)'))}</th><th scope="col">${escH(T('Second round (2027)'))}</th></tr></thead>
      <tbody>${rows.map(([k, a, b]) => `<tr><th scope="row">${escH(k)}</th><td>${escH(a)}</td><td>${escH(b)}</td></tr>`).join('')}</tbody></table>`;
  }

  root.OzPage = { tracts, munis, barrios, counts, eligibleByRule, RULE, STATUS };
})(typeof window !== 'undefined' ? window : globalThis);
