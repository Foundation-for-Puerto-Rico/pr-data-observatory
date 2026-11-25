/* PR Data Observatory: the disaster funding and need page (public-money.html, Knowledge Area; Public money v2, step 5; HUD CDBG, decision 100).
   Loads data/public_money_need.json (public_money_need.py: FEMA money of disasters and grants of 2017 to 2025 and HUD CDBG-DR, CDBG-MIT and yearly
   CDBG money of federal fiscal years 2019 on, summed by municipio, two measures of need and Hazard Mitigation by status) and data/municipios.geojson (the map). The reader picks a money measure and a need measure; each municipio falls in a
   third (tercile) of each, and the map shows the nine pairs (a bivariate map). The page states the facts and draws no conclusion.
   The choice is kept in the address (#m=..&n=..&g=..). Every visible string goes through T(): its Spanish is in i18n_src/es/public_money.json,
   written by docs/analysis/public-money-v2-2026-10/make_page.py. */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const usd = (v, d = 0) => v == null || !isFinite(v) ? '—' : (lang() === 'es' ? fmt(v, d) + ' $' : '$' + fmt(v, d));
  const big = (v) => v >= 1e9 ? usd(v / 1e9, 2) + ' ' + T('billion') : v >= 1e6 ? usd(v / 1e6, 1) + ' ' + T('million') : usd(v);
  const pct = (v, d = 1) => fmt(v, d) + (lang() === 'es' ? ' %' : '%');

  // The money measures (per resident, summed over the years) and the need measures. 'all' adds the three FEMA programs; HUD's money is never added
  // to FEMA's (another time base: the year HUD obligated it).
  const MONEY = [['pa', 'FEMA Public Assistance obligated'], ['ia', 'FEMA Individual Assistance approved'], ['hma', 'FEMA Hazard Mitigation approved'], ['all', 'The three FEMA programs together'],
    ['cdbg_dr', 'HUD CDBG-DR and CDBG-MIT subawards'], ['cdbg', 'HUD CDBG yearly grants']];
  const NEED = [['eal', 'Expected annual loss from natural hazards, per resident'], ['cre3', 'Residents with three or more risk factors']];
  // Nine colors: rows are money (low to high), columns are need (low to high); the corners differ in hue and the diagonal darkens (Stevens' scheme)
  const BIV = [['#e8e8e8', '#e4acac', '#c85a5a'], ['#b0d5df', '#ad9ea5', '#985356'], ['#64acbe', '#627f8c', '#574249']];
  const S = { m: 'pa', n: 'eal', g: null, sort: { pmHma: ['name', 1], pmHud: ['name', 1] } };
  let D, GEO, PROJ;

  if (doc) Promise.all([fetchJson('data/public_money_need.json'), fetchJson('data/municipios.geojson')]).then(([d, g]) => { D = d; GEO = g; start(); }, (e) => {
    $('#pmMap').innerHTML = `<p class="pm-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  const ids = () => D.geo.ids;
  const name = (i) => D.geo.names[i];
  function moneyTotal(k, i) { return k === 'all' ? D.money.pa[i] + D.money.ia[i] + D.money.hma[i] : D.money[k][i]; }
  const money = (i, k = S.m) => moneyTotal(k, i) / D.population[i];
  const need = (i, k = S.n) => (k === 'eal' ? D.need.eal[i] / D.population[i] : D.need.cre3[i]);
  const needFmt = (v, k = S.n) => (k === 'eal' ? usd(v) : pct(v));
  const label = (list, k) => T(list.find(x => x[0] === k)[1]);
  const years = (k) => { const y = D.money_years[k === 'all' ? 'pa' : k]; return T('{a} to {b}', { a: y[0], b: y[1] }); };

  // Thirds by rank: the 26 lowest, the 26 in the middle and the 26 highest (ties keep the order of the values)
  function thirds(vals) {
    const order = vals.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0] || a[1] - b[1]), cls = new Array(vals.length);
    order.forEach(([, i], r) => { cls[i] = Math.min(2, Math.floor(3 * r / vals.length)); });
    const cut = [order[Math.floor(vals.length / 3)][0], order[Math.floor(2 * vals.length / 3)][0]];
    return { cls, cut };
  }
  function median(xs) { const s = xs.slice().sort((a, b) => a - b), h = s.length >> 1; return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2; }
  function spearman(a, b) {
    const rank = (x) => { const o = x.map((v, i) => [v, i]).sort((p, q) => p[0] - q[0]), r = new Array(x.length); let k = 0; while (k < o.length) { let j = k; while (j + 1 < o.length && o[j + 1][0] === o[k][0]) j++; for (let t = k; t <= j; t++) r[o[t][1]] = (k + j) / 2; k = j + 1; } return r; };
    const ra = rank(a), rb = rank(b), n = a.length, ma = (n - 1) / 2;
    let sab = 0, sa = 0, sb = 0; for (let i = 0; i < n; i++) { sab += (ra[i] - ma) * (rb[i] - ma); sa += (ra[i] - ma) ** 2; sb += (rb[i] - ma) ** 2; }
    return sab / Math.sqrt(sa * sb);
  }
  function current() {
    const n = ids().length, mv = [], nv = [];
    for (let i = 0; i < n; i++) { mv.push(money(i)); nv.push(need(i)); }
    const tm = thirds(mv), tn = thirds(nv);
    return { mv, nv, tm, tn, cell: mv.map((_, i) => [tm.cls[i], tn.cls[i]]), rho: spearman(mv, nv) };
  }
  const WORD = ['lower third', 'middle third', 'upper third'];

  // ── The map ──
  function project() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const each = (g, fn) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).forEach(p => p.forEach(r => r.forEach(fn)));
    GEO.features.forEach(f => each(f.geometry, ([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = (y1 - y0) * sc;
    PROJ = { W, H: Math.ceil(H), f: ([x, y]) => [((x - x0) * k * sc).toFixed(1), ((y1 - y) * sc).toFixed(1)] };
    PROJ.paths = GEO.features.map(f => ({ id: f.properties.GEOID, d: (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates).map(p => p.map(r => 'M' + r.map(PROJ.f).join('L') + 'Z').join('')).join('') }));
  }
  function cellText(c) { return T('Money: {m}. Need: {n}.', { m: T(WORD[c[0]]), n: T(WORD[c[1]]) }); }
  function drawMap(C) {
    if (!PROJ) project();
    const at = new Map(ids().map((g, i) => [g, i]));
    let s = '';
    PROJ.paths.forEach(p => {
      const i = at.get(p.id); if (i == null) return;
      const c = C.cell[i], on = S.g === p.id;
      const lab = T('{name}: {money} per resident; {need}. {cell} Select for the figures.', { name: name(i), money: usd(C.mv[i]), need: needFmt(C.nv[i]), cell: cellText(c) });
      s += `<path d="${p.d}" fill="${BIV[c[0]][c[1]]}" class="mu${on ? ' on' : ''}" data-id="${p.id}" tabindex="0" role="button" aria-pressed="${on}" aria-label="${esc(lab)}"><title>${esc(lab)}</title></path>`;
    });
    PROJ.paths.filter(p => p.id === S.g).forEach(p => { s += `<path d="${p.d}" fill="none" stroke="#1d2433" stroke-width="2.6" pointer-events="none"/>`; });
    $('#pmMap').innerHTML = `<svg viewBox="0 0 ${PROJ.W} ${PROJ.H}" width="100%" aria-label="${esc(T('Bivariate map: {money} and {need}, by municipio', { money: label(MONEY, S.m), need: label(NEED, S.n) }))}">${s}</svg>`;
    drawKey(C);
  }
  function drawKey(C) {   // the 3 x 3 key, with how many municipios fall in each pair
    const count = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]; C.cell.forEach(([a, b]) => { count[a][b]++; });
    const Z = 34, X = 70, Y = 8;
    let s = '';
    for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) {
      const x = X + b * Z, y = Y + (2 - a) * Z;
      s += `<rect x="${x}" y="${y}" width="${Z}" height="${Z}" fill="${BIV[a][b]}" stroke="#fff"/><text x="${x + Z / 2}" y="${y + Z / 2 + 4}" text-anchor="middle" class="kn">${count[a][b]}</text>`;
    }
    s += `<text x="${X + 1.5 * Z}" y="${Y + 3 * Z + 16}" text-anchor="middle" class="ka">${esc(T('Need'))} →</text>`;
    s += `<text transform="translate(${X - 10},${Y + 1.5 * Z}) rotate(-90)" text-anchor="middle" class="ka">${esc(T('Money'))} →</text>`;
    $('#pmKey').innerHTML = `<svg viewBox="0 0 ${X + 3 * Z + 8} ${Y + 3 * Z + 24}" width="190" role="img" aria-label="${esc(T('Key: money per resident in thirds, from bottom to top, and need in thirds, from left to right; each square says how many municipios'))}">${s}</svg>` +
      `<p class="pm-small">${esc(T('Each square counts the municipios. Thirds of money per resident: below {a}, from {a} to below {b}, {b} or more. Thirds of need: below {c}, from {c} to below {d}, {d} or more.', { a: usd(C.tm.cut[0]), b: usd(C.tm.cut[1]), c: needFmt(C.tn.cut[0]), d: needFmt(C.tn.cut[1]) }))}</p>`;
  }

  // ── One municipio ──
  function drawPlace(C) {
    const box = $('#pmPlace');
    const i = ids().indexOf(S.g);
    if (i < 0) { box.innerHTML = `<h3>${esc(T('Puerto Rico'))}</h3><p class="pm-small">${esc(T('Select a municipio on the map or in the chart for its figures.'))}</p>` + islandList(C); return; }
    const rows = [[T('Residents (2020 Census)'), fmt(D.population[i])], ...MONEY.map(([k, l]) => [T(l) + ', ' + years(k), T('{total} ({per} per resident)', { total: big(moneyTotal(k, i)), per: usd(money(i, k)) })]),
      [T(NEED[0][1]), usd(need(i, 'eal'))], [T(NEED[1][1]), pct(need(i, 'cre3'))]];
    box.innerHTML = `<h3>${esc(name(i))}</h3><p class="pm-cell"><i style="background:${BIV[C.cell[i][0]][C.cell[i][1]]}"></i>${esc(cellText(C.cell[i]))}</p>` +
      `<dl>${rows.map(([a, b]) => `<dt>${esc(a)}</dt><dd>${esc(b)}</dd>`).join('')}</dl><button type="button" class="pm-btn" id="pmClear">${esc(T('Back to Puerto Rico'))}</button>`;
    $('#pmClear').addEventListener('click', () => { S.g = null; render(); });
  }
  function islandList(C) {
    return `<dl><dt>${esc(T('Median money per resident'))}</dt><dd>${esc(usd(median(C.mv)))}</dd><dt>${esc(T('Median need'))}</dt><dd>${esc(needFmt(median(C.nv)))}</dd>` +
      `<dt>${esc(T('Rank correlation (Spearman) between the two'))}</dt><dd>${esc(fmt(C.rho, 2))}</dd></dl>` +
      `<p class="pm-small">${esc(T('A rank correlation near 0 means the order of the municipios by money says little about their order by need; near 1, the two orders agree; below 0, they run opposite.'))}</p>`;
  }

  // ── The scatter plot: need across, money per resident up (log scale, since a few municipios have many times the median) ──
  function drawScatter(C) {
    const W = 860, H = 380, L = 70, R = 16, Tp = 14, B = 46, floor = 10;
    const xs = C.nv, ys = C.mv.map(v => Math.max(v, floor));
    const x0 = Math.min(...xs), x1 = Math.max(...xs), lo = Math.floor(Math.log10(Math.min(...ys))), hi = Math.ceil(Math.log10(Math.max(...ys)));
    const X = (v) => L + (v - x0) / (x1 - x0 || 1) * (W - L - R), Y = (v) => Tp + (hi - Math.log10(v)) / (hi - lo || 1) * (H - Tp - B);
    let s = '';
    for (let p = lo; p <= hi; p++) s += `<line x1="${L}" x2="${W - R}" y1="${Y(10 ** p)}" y2="${Y(10 ** p)}" stroke="#e4e7ec"/><text x="${L - 6}" y="${Y(10 ** p) + 4}" text-anchor="end" class="tick">${esc(usd(10 ** p))}</text>`;
    for (let k = 0; k <= 4; k++) { const v = x0 + (x1 - x0) * k / 4; s += `<text x="${X(v)}" y="${H - B + 16}" text-anchor="middle" class="tick">${esc(needFmt(v))}</text>`; }
    const mx = median(xs), my = median(C.mv);
    s += `<line x1="${X(mx)}" x2="${X(mx)}" y1="${Tp}" y2="${H - B}" class="med"/><line x1="${L}" x2="${W - R}" y1="${Y(Math.max(my, floor))}" y2="${Y(Math.max(my, floor))}" class="med"/>`;
    s += `<text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle" class="axis">${esc(label(NEED, S.n))}</text>`;
    s += `<text transform="translate(14,${(Tp + H - B) / 2}) rotate(-90)" text-anchor="middle" class="axis">${esc(T('{money}, per resident', { money: label(MONEY, S.m) }))}</text>`;
    xs.forEach((v, i) => {
      const c = C.cell[i], on = ids()[i] === S.g, lab = T('{name}: {money} per resident; {need}', { name: name(i), money: usd(C.mv[i]), need: needFmt(v) });
      s += `<circle cx="${X(v).toFixed(1)}" cy="${Y(ys[i]).toFixed(1)}" r="${on ? 8 : 5.5}" fill="${BIV[c[0]][c[1]]}" stroke="${on ? '#1d2433' : '#5b6475'}" stroke-width="${on ? 2.4 : 0.8}" data-id="${ids()[i]}" class="dot"><title>${esc(lab)}</title></circle>`;
    });
    $('#pmScatter').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(T('Scatter plot: each dot is a municipio; dashed lines mark the medians'))}">${s}</svg>`;
    const q = [[0, 0], [0, 0]]; xs.forEach((v, i) => { q[C.mv[i] > my ? 1 : 0][v > mx ? 1 : 0]++; });
    $('#pmRead').textContent = T('Above the median in money and in need: {hh} municipios. Above in money, below in need: {hl}. Below in money, above in need: {lh}. Below in both: {ll}. Rank correlation: {rho}.',
      { hh: q[1][1], hl: q[1][0], lh: q[0][1], ll: q[0][0], rho: fmt(C.rho, 2) });
  }

  // ── How much of each program a municipio map can show ──
  function drawPlaced() {
    const W = 860, row = 42, L = 290, R = 175, rows = MONEY.filter(([k]) => k !== 'all');
    let s = '';
    rows.forEach(([k, l], r) => {
      const t = D.island[k], share = t.total ? t.placed / t.total : 0, y = 8 + r * row, w = (W - L - R);
      s += `<text x="${L - 8}" y="${y + 17}" text-anchor="end" class="lab">${esc(T(l))}</text>`;
      s += `<rect x="${L}" y="${y + 4}" width="${(w * share).toFixed(1)}" height="18" fill="#205D7B"/><rect x="${(L + w * share).toFixed(1)}" y="${y + 4}" width="${(w * (1 - share)).toFixed(1)}" height="18" fill="#D5D9DE"/>`;
      s += `<text x="${W - R + 8}" y="${y + 17}" class="val">${esc(T('{p} of {total}', { p: pct(100 * share, 0), total: big(t.total) }))}</text>`;
      s += `<text x="${L - 8}" y="${y + 31}" text-anchor="end" class="tick">${esc(years(k))}</text>`;
    });
    $('#pmPlaced').innerHTML = `<svg viewBox="0 0 ${W} ${8 + rows.length * row + 6}" width="100%" role="img" aria-label="${esc(T('Share of each program placed in a municipio'))}">${s}</svg>` +
      `<div class="pm-legend"><span><i style="background:#205D7B"></i>${esc(T('placed in a municipio (on the map)'))}</span><span><i style="background:#D5D9DE"></i>${esc(T('recorded as statewide or not placed'))}</span></div>`;
  }

  // ── Sortable tables by municipio: Hazard Mitigation by status, and HUD's money ──
  const HCOLS = [['name', 'Municipio'], ['approved', 'Federal share approved'], ['obligated', 'Federal money obligated'], ['share', 'Obligated as a share of approved'], ['pending', 'Awaiting a FEMA decision'], ['projects', 'Approved subapplications']];
  function hval(k, i) { const h = D.hma; return k === 'name' ? name(i) : k === 'share' ? (h.approved[i] ? 100 * h.obligated[i] / h.approved[i] : null) : h[k][i]; }
  function hcell(k, v) { return k === 'name' ? esc(v) : k === 'share' ? esc(v == null ? '—' : pct(v, 0)) : k === 'projects' ? esc(fmt(v)) : esc(usd(v)); }
  const UCOLS = [['name', 'Municipio'], ['dr', 'CDBG-DR and CDBG-MIT subawards'], ['dr_pc', 'CDBG-DR and CDBG-MIT, per resident'], ['ent', 'CDBG entitlement grant'], ['st', 'CDBG state program subawards'], ['cdbg_pc', 'CDBG yearly grants, per resident']];
  function uval(k, i) {
    const P = D.cdbg_parts;
    return k === 'name' ? name(i) : k === 'dr' ? D.money.cdbg_dr[i] : k === 'dr_pc' ? money(i, 'cdbg_dr') : k === 'ent' ? P.entitlement[i] : k === 'st' ? P.state[i] : money(i, 'cdbg');
  }
  function ucell(k, v) { return k === 'name' ? esc(v) : esc(usd(v)); }
  function table(id, cols, val, cell, isl, caption) {
    const [key, dir] = S.sort[id], n = ids().length, order = [...Array(n).keys()].sort((a, b) => {
      const x = val(key, a), y = val(key, b);
      return key === 'name' ? dir * x.localeCompare(y, loc()) : dir * ((x == null ? -1 : x) - (y == null ? -1 : y)) || a - b;
    });
    const head = cols.map(([k, l]) => `<th scope="col"${k === 'name' ? '' : ' class="num"'} aria-sort="${k === key ? (dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" data-k="${k}">${esc(T(l))}</button></th>`).join('');
    const body = order.map(i => `<tr>${cols.map(([k]) => `<td${k === 'name' ? '' : ' class="num"'}>${cell(k, val(k, i))}</td>`).join('')}</tr>`).join('');
    const foot = `<tr>${cols.map(([k]) => `<td${k === 'name' ? '' : ' class="num"'}><b>${cell(k, isl[k])}</b></td>`).join('')}</tr>`;
    $('#' + id).innerHTML = `<table class="pm-table"><caption class="sr-only">${esc(caption)}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody><tfoot>${foot}</tfoot></table>`;
  }
  function drawHma() {
    const I = D.hma_island, isl = { name: T('Puerto Rico (its own total, with what is statewide)'), approved: I.approved, obligated: I.obligated, share: I.approved ? 100 * I.obligated / I.approved : null, pending: I.pending, projects: I.projects };
    table('pmHma', HCOLS, hval, hcell, isl, T('FEMA Hazard Mitigation by benefiting municipio, fiscal years 2017 to 2025'));
  }
  function drawHud() {
    const P = D.cdbg_parts, pop = D.population.reduce((a, b) => a + b, 0), I = D.island;
    const isl = { name: T('Puerto Rico (the prime grants, with what is not placed)'), dr: I.cdbg_dr.total, dr_pc: I.cdbg_dr.total / pop, ent: P.entitlement_total, st: P.state_prime, cdbg_pc: I.cdbg.total / pop };
    table('pmHud', UCOLS, uval, ucell, isl, T('HUD CDBG-DR, CDBG-MIT and yearly CDBG by municipio, federal fiscal years {y}', { y: years('cdbg') }));
  }

  function csv() {
    const C = current();
    const out = [[T('Municipio'), 'GEOID', T('Residents (2020 Census)'), ...MONEY.map(([, l]) => T(l) + ' ($)'), ...MONEY.map(([, l]) => T('{money}, per resident', { money: T(l) }) + ' ($)'),
      T('Expected annual loss from natural hazards ($ a year)'), T(NEED[0][1]) + ' ($)', T(NEED[1][1]) + ' (%)', T('Third of money (1 to 3)'), T('Third of need (1 to 3)'),
      ...HCOLS.slice(1).map(([, l]) => T(l)), ...UCOLS.slice(3, 5).map(([, l]) => T(l) + ' ($)')]];
    ids().forEach((g, i) => out.push([name(i), g, D.population[i], ...MONEY.map(([k]) => moneyTotal(k, i)), ...MONEY.map(([k]) => money(i, k).toFixed(2)),
      D.need.eal[i], need(i, 'eal').toFixed(2), D.need.cre3[i], C.cell[i][0] + 1, C.cell[i][1] + 1, ...HCOLS.slice(1).map(([k]) => { const v = hval(k, i); return v == null ? '' : k === 'share' ? v.toFixed(1) : v; }), ...UCOLS.slice(3, 5).map(([k]) => uval(k, i))]));
    const text = out.map(r => r.map(v => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v).join(',')).join('\n');
    const a = doc.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + text], { type: 'text/csv' })); a.download = `public_money_need_${S.m}_${S.n}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function writeHash() { history.replaceState(null, '', `#m=${S.m}&n=${S.n}${S.g ? '&g=' + S.g : ''}`); }
  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    if (MONEY.some(x => x[0] === h.get('m'))) S.m = h.get('m');
    if (NEED.some(x => x[0] === h.get('n'))) S.n = h.get('n');
    if (ids().includes(h.get('g'))) S.g = h.get('g');
  }
  function render() {
    const C = current();
    drawMap(C); drawPlace(C); drawScatter(C);
    writeHash();
  }
  function pick(e) {
    const t = e.target.closest('[data-id]'); if (!t) return;
    const id = t.dataset.id, keep = e.type === 'keydown' && t.closest('#pmMap');
    S.g = S.g === id ? null : id; render();
    if (keep) { const p = $(`#pmMap [data-id="${id}"]`); if (p) p.focus({ preventScroll: true }); }   // the map was redrawn: keep the keyboard on the same municipio
  }
  function start() {
    readHash();
    const opts = (list) => list.map(([k, l]) => `<option value="${k}">${esc(T(l))}</option>`).join('');
    $('#pmMoney').innerHTML = opts(MONEY); $('#pmMoney').value = S.m;
    $('#pmNeed').innerHTML = opts(NEED); $('#pmNeed').value = S.n;
    $('#pmMoney').addEventListener('change', (e) => { S.m = e.target.value; render(); });
    $('#pmNeed').addEventListener('change', (e) => { S.n = e.target.value; render(); });
    ['#pmMap', '#pmScatter'].forEach(id => $(id).addEventListener('click', pick));
    $('#pmMap').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(e); } });
    [['pmHma', drawHma], ['pmHud', drawHud]].forEach(([id, draw]) => $('#' + id).addEventListener('click', (e) => {
      const b = e.target.closest('button[data-k]'); if (!b) return;
      const k = b.dataset.k, o = S.sort[id]; S.sort[id] = [k, o[0] === k ? -o[1] : (k === 'name' ? 1 : -1)]; draw();
      const f = $(`#${id} button[data-k="${k}"]`); if (f) f.focus({ preventScroll: true });
    }));
    $('#pmCsv').addEventListener('click', csv);
    drawPlaced(); drawHma(); drawHud(); render();
    if (S.g) { const p = $(`#pmMap [data-id="${S.g}"]`); if (p) p.focus({ preventScroll: true }); }
  }
  root.PublicMoney = { thirds, spearman, median };   // for tests/public_money.test.js
})(typeof window !== 'undefined' ? window : globalThis);
