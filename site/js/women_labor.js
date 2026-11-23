/* PR Data Observatory: the Women in the labor force page (women-labor.html, Knowledge Area).
   Loads data/women_labor.json (women_labor.py: counts by sex, age group and employment status for the island and the 78 municipios, three five-year
   windows, with 90% margins) and data/municipios.geojson (the map). Every chart follows the area chosen at the top of the page: the Eastern Region (ERSV) at first,
   a preset region, or any municipios clicked on the map. Rates are pooled (sums of counts, then divided) and their margins follow the Census Bureau's
   formulas, the same arithmetic as women_labor.py (tests/women_labor.test.js checks that the two agree). The area is kept in the address (#a=..&w=..&s=..).
   Every visible string goes through T(): its Spanish is in i18n_src/es/women_labor.json, written by docs/analysis/women-labor-2026-10/make_page.py. */
(function (root) {
  'use strict';
  const NAGE = 7, PRIME = [2, 3, 4], KIDS = ['u6', '617', 'none'], CV_MAX = 30, Z = 1.645;

  // ── Estimate-and-margin arithmetic (women_labor.py: esum, prop, diff) ──
  const esum = (cells) => cells.some(c => !c || c[0] == null) ? null : [cells.reduce((s, c) => s + c[0], 0), Math.sqrt(cells.reduce((s, c) => s + (c[1] || 0) ** 2, 0))];
  function prop(num, den) {
    if (!num || !den || !den[0]) return null;
    const p = num[0] / den[0]; let u = num[1] ** 2 - p * p * den[1] ** 2;
    if (u < 0) u = num[1] ** 2 + p * p * den[1] ** 2;
    return [100 * p, 100 * Math.sqrt(u) / den[0]];
  }
  function diff(a, b) { if (!a || !b) return null; const d = a[0] - b[0], m = Math.hypot(a[1], b[1]); return { v: d, m, sig: Math.abs(d) > m }; }
  const cv = (e) => !e ? null : !e[0] ? (e[1] > 0 ? Infinity : null) : 100 * (e[1] / Z) / e[0];   // a zero estimate with a margin cannot be relied on
  function combine(recs) {
    const out = {};
    for (const s of ['m', 'f']) out[s] = Array.from({ length: NAGE }, (_, a) => [0, 1, 2, 3].map(k => esum(recs.map(r => r[s][a][k]))));
    if (recs.every(r => r.kids)) out.kids = Object.fromEntries(KIDS.map(k => [k, [0, 1].map(j => esum(recs.map(r => r.kids[k][j])))]));
    if (recs.every(r => r.sample)) out.sample = { people: recs.reduce((s, r) => s + (r.sample.people || 0), 0), homes: recs.reduce((s, r) => s + (r.sample.homes || 0), 0) };
    return out;
  }
  const totals = (rec, s, ages) => [0, 1, 2, 3].map(k => esum((ages || [0, 1, 2, 3, 4, 5, 6]).map(a => rec[s][a][k])));
  function measures(rec) {
    const f = totals(rec, 'f'), m = totals(rec, 'm'), fp = totals(rec, 'f', PRIME), mp = totals(rec, 'm', PRIME);
    return {
      women16: f[0], women_lf: f[1], women_une: f[3], women_emp: f[2] && f[3] ? [f[2][0] - f[3][0], 0] : null,
      lfpr_f: prop(f[1], f[0]), lfpr_m: prop(m[1], m[0]), lfpr_f_prime: prop(fp[1], fp[0]), lfpr_m_prime: prop(mp[1], mp[0]),
      unemp_f: prop(f[3], f[2]), unemp_m: prop(m[3], m[2]),
      by_age_f: rec.f.map(g => prop(g[1], g[0])), by_age_m: rec.m.map(g => prop(g[1], g[0])),
      kids: rec.kids ? Object.fromEntries(KIDS.map(k => [k, prop(rec.kids[k][1], rec.kids[k][0])])) : null, sample: rec.sample || null,
    };
  }
  /** Kitagawa split of the women's rate gap between `a` and `b` (points), with b's age mix as the standard of the adjusted rate. */
  function ageSplit(a, b) {
    const ra = a.f.map(g => g[1][0] / g[0][0]), rb = b.f.map(g => g[1][0] / g[0][0]);
    const ta = a.f.reduce((s, g) => s + g[0][0], 0), tb = b.f.reduce((s, g) => s + g[0][0], 0);
    const wa = a.f.map(g => g[0][0] / ta), wb = b.f.map(g => g[0][0] / tb);
    let mix = 0, rate = 0, adj = 0;
    for (let i = 0; i < NAGE; i++) { mix += (wa[i] - wb[i]) * (ra[i] + rb[i]) / 2; rate += (ra[i] - rb[i]) * (wa[i] + wb[i]) / 2; adj += ra[i] * wb[i]; }
    return { from_age_mix: 100 * mix, from_rates: 100 * rate, adjusted: 100 * adj };
  }
  const calc = { esum, prop, diff, cv, combine, totals, measures, ageSplit };
  if (typeof module === 'object' && module.exports) { module.exports = calc; return; }   // Node tests use the arithmetic only

  const doc = root.document, $ = (s) => doc.querySelector(s), NS = 'http://www.w3.org/2000/svg';
  const loc = () => (root.I18N && I18N.lang === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 1) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const C = { f: '#338CB3', m: '#B56D00', area: '#205D7B', rest: '#8C8E8E', grid: '#e4e7ec', muted: '#5b6475', emp: '#205D7B', une: '#FFA600', nilf: '#D5D9DE' };
  const S = { win: null, sel: new Set(), shade: 'lfpr_f', preset: 'ersv' };
  let D, GEO;

  Promise.all([fetchJson('data/women_labor.json'), fetchJson('data/municipios.geojson')]).then(([d, g]) => { D = d; GEO = g; start(); }, (e) => {
    $('#wlCompare').innerHTML = `<p class="wl-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const muniIds = () => Object.keys(D.names);
  const rec = (g, w = S.win) => D.areas[String(w)][g];
  const areaRec = (ids, w = S.win) => combine(ids.map(g => rec(g, w)));
  const restIds = () => muniIds().filter(g => !S.sel.has(g));
  const allIsland = () => S.sel.size === muniIds().length;
  const restLabel = () => (allIsland() ? T('Puerto Rico') : T('Rest of Puerto Rico'));   // with every municipio chosen, the area is compared with the island figure itself
  function areaName() {
    if (allIsland()) return T('Puerto Rico');
    if (S.preset === 'ersv') return T('Eastern Region (ERSV)');
    const p = S.preset && D.groups[S.preset];
    if (p) return p.name[lang()] || p.name.en;
    return S.sel.size === 1 ? D.names[[...S.sel][0]] : T('{n} municipios selected', { n: S.sel.size });
  }
  function svg(w, h, label, body) { return `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${body}</svg>`; }
  const tx = (x, y, s, cls = '', anchor = 'start') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(s)}</text>`;
  const scale = (lo, hi, a, b) => (v) => a + (b - a) * (v - lo) / (hi - lo);
  function niceRange(vals, pad = 3) {
    const lo = Math.max(0, Math.floor((Math.min(...vals) - pad) / 5) * 5), hi = Math.min(100, Math.ceil((Math.max(...vals) + pad) / 5) * 5);
    return [lo, hi === lo ? lo + 5 : hi];
  }
  function axis(x, lo, hi, y0, y1, step) {
    let s = '';
    for (let v = lo; v <= hi + 1e-9; v += step) s += `<line x1="${x(v)}" x2="${x(v)}" y1="${y0}" y2="${y1}" stroke="${C.grid}"/>` + tx(x(v), y1 + 15, fmt(v, 0), 'tick', 'middle');
    return s;
  }
  const whisker = (x, y, e, color, r = 5, title = '') => !e ? '' :
    `<g><title>${esc(title)}</title><line x1="${x(Math.max(0, e[0] - e[1]))}" x2="${x(Math.min(100, e[0] + e[1]))}" y1="${y}" y2="${y}" stroke="${color}" stroke-width="2.5" stroke-linecap="round" opacity=".55"/>` +
    `<circle cx="${x(e[0])}" cy="${y}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1.5"/></g>`;

  // ── 1 · Area, rest, island: women and men ──
  function drawCompare(A, R, P) {
    const rows = allIsland() ? [[areaName(), A]] : [[areaName(), A], [T('Rest of Puerto Rico'), R], [T('Puerto Rico'), P]];
    const vals = rows.flatMap(([, m]) => [m.lfpr_f, m.lfpr_m].filter(Boolean).flatMap(e => [e[0] - e[1], e[0] + e[1]]));
    const [lo, hi] = niceRange(vals), W = 860, L = Math.min(330, 40 + 7.2 * Math.max(...rows.map(r => r[0].length))), Rr = 70, row = 46, top = 30, H = top + rows.length * row + 30, x = scale(lo, hi, L, W - Rr);
    let s = axis(x, lo, hi, top - 8, top + rows.length * row - 6, 5);
    s += `<g class="lg">${tx(L, 14, '●', 'dotf')}${tx(L + 14, 14, T('Women'), 'lab')}${tx(L + 90, 14, '●', 'dotm')}${tx(L + 104, 14, T('Men'), 'lab')}</g>`;
    rows.forEach(([name, m], i) => {
      const y = top + i * row + 12;
      s += tx(L - 10, y + 10, name, i === 0 ? 'lab b' : 'lab', 'end');
      [['f', m.lfpr_f, 0], ['m', m.lfpr_m, 18]].forEach(([sx, e, dy]) => {
        const nm = sx === 'f' ? T('Women') : T('Men');
        s += whisker(x, y + dy, e, C[sx], 6, T('{name}, {sex}: {v}% ± {m}', { name, sex: nm, v: fmt(e && e[0]), m: fmt(e && e[1]) }));
        if (e) s += tx(x(Math.min(100, e[0] + e[1])) + 6, y + dy + 4, pct(e[0]), 'val');
      });
    });
    s += tx((L + W - Rr) / 2, H - 2, T('Labor force participation (%)'), 'axis', 'middle');
    $('#wlCompare').innerHTML = svg(W, H, T('Women and men 16 and over: labor force participation, with 90% margins of error'), s);
  }

  // ── 2 · Of every 100 women ──
  function drawWaffle(A) {
    const f = A.women16, lf = A.women_lf, une = A.women_une;
    const raw = [lf[0] - une[0], une[0], f[0] - lf[0]].map(v => 100 * v / f[0]);
    const n = raw.map(Math.floor); let left = 100 - n.reduce((a, b) => a + b, 0);
    raw.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (left > 0) { n[i]++; left--; } });   // largest remainder: the squares add up to 100
    const cols = [C.emp, C.une, C.nilf], what = [T('in the labor force, working'), T('in the labor force, looking for work'), T('not in the labor force')];
    let s = '', k = 0; const sz = 22, gap = 4, W = 10 * (sz + gap) + 340, H = 10 * (sz + gap) + 4;
    n.forEach((cnt, c) => { for (let j = 0; j < cnt; j++, k++) { const r = Math.floor(k / 10), q = k % 10; s += `<rect x="${q * (sz + gap)}" y="${r * (sz + gap)}" width="${sz}" height="${sz}" rx="4" fill="${cols[c]}"><title>${esc(T('{n} of every 100 women {what}', { n: cnt, what: what[c] }))}</title></rect>`; } });
    n.forEach((cnt, c) => { const y = 30 + c * 64, x0 = 10 * (sz + gap) + 16; s += `<rect x="${x0}" y="${y - 14}" width="14" height="14" rx="3" fill="${cols[c]}"/>` + tx(x0 + 22, y - 2, String(cnt), 'big') + `<text x="${x0 + 22}" y="${y + 16}" class="lab">${esc(what[c])}</text>`; });
    $('#wlWaffle').innerHTML = `<h3>${esc(T('Of every 100 women 16 and over in the selected area'))}</h3>` + svg(W, H, T('Of every 100 women 16 and over in the selected area'), s);
    const rows = [[T('Women 16 and over in the area'), fmt(f[0], 0) + ' ± ' + fmt(f[1], 0)], [T('Women in the labor force'), fmt(lf[0], 0) + ' ± ' + fmt(lf[1], 0)],
      [T('Unemployment rate, women'), A.unemp_f ? pct(A.unemp_f[0]) + ' ± ' + fmt(A.unemp_f[1]) : '—']];
    if (A.sample) rows.push([T('People interviewed by the survey in five years (all ages, both sexes)'), fmt(A.sample.people, 0)]);
    $('#wlSample').innerHTML = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  }

  // ── 3 · Age ──
  function drawAge(Ar, Rr) {
    const A = measures(Ar), R = measures(Rr), W = 860, L = 70, Rm = 20, top = 34, H = 300, bw = (W - L - Rm) / NAGE, y = scale(0, 100, H - 40, top);
    let s = '';
    for (let v = 0; v <= 100; v += 20) s += `<line x1="${L}" x2="${W - Rm}" y1="${y(v)}" y2="${y(v)}" stroke="${C.grid}"/>` + tx(L - 8, y(v) + 4, fmt(v, 0), 'tick', 'end');
    s += `<g class="lg">${tx(L, 14, '●', 'dotarea')}${tx(L + 14, 14, areaName(), 'lab')}${tx(L + 330, 14, '●', 'dotrest')}${tx(L + 344, 14, restLabel(), 'lab')}</g>`;
    D.ages.forEach((age, i) => {
      const cx = L + bw * i + bw / 2, a = A.by_age_f[i], r = R.by_age_f[i], d = diff(a, r);
      [[a, C.area, -10, areaName()], [r, C.rest, 10, restLabel()]].forEach(([e, col, dx, nm]) => {
        if (!e) return;
        s += `<g><title>${esc(T('{age}: {name} {v}% ± {m}', { age, name: nm, v: fmt(e[0]), m: fmt(e[1]) }))}</title><line x1="${cx + dx}" x2="${cx + dx}" y1="${y(Math.max(0, e[0] - e[1]))}" y2="${y(Math.min(100, e[0] + e[1]))}" stroke="${col}" stroke-width="2.5" opacity=".55"/><rect x="${cx + dx - 7}" y="${y(e[0])}" width="14" height="${y(0) - y(e[0])}" fill="${col}" opacity=".85" rx="2"/></g>`;
      });
      if (a) s += tx(cx - 10, y(a[0]) - 6, fmt(a[0], 0), 'val', 'middle');
      s += tx(cx, H - 22, age, 'lab', 'middle');
      if (d) s += `<text x="${cx}" y="${H - 6}" text-anchor="middle" class="${d.sig ? 'sig' : 'nsig'}">${d.sig ? '◆' : '·'}<title>${esc(d.sig ? T('difference significant at 90%') : T('no significant difference'))}</title></text>`;
    });
    $('#wlAge').innerHTML = svg(W, H, T('Labor force participation of women by age group, selected area and rest of Puerto Rico'), s) +
      `<p class="wl-small"><span class="sig">◆</span> ${esc(T('difference significant at 90%'))}</p>`;
    // the bridge: rest's rate, + age mix, + participation within each age = the area's rate
    const k = ageSplit(Ar, Rr), base = R.lfpr_f[0], steps = [[allIsland() ? T("Women's rate, Puerto Rico") : T("Women's rate, rest of Puerto Rico"), 0, base, C.rest], [T('age mix'), base, base + k.from_age_mix, null], [T('participation within each age'), base + k.from_age_mix, base + k.from_age_mix + k.from_rates, null], [areaName(), 0, A.lfpr_f[0], C.area]];
    const lo = Math.floor(Math.min(...steps.flatMap(st => [st[1] || st[2], st[2]]).filter(v => v > 0)) - 3), hi = Math.ceil(Math.max(...steps.map(st => st[2])) + 2), BW = 860, BL = 290, x = scale(lo, hi, BL, BW - 60), row = 34;
    let b = axis(x, lo, hi, 6, 6 + row * 4, 1);
    steps.forEach(([lab, a0, a1, col], i) => {
      const yy = 10 + i * row, from = col ? lo : Math.min(a0, a1), to = col ? a1 : Math.max(a0, a1), c = col || (a1 >= a0 ? C.f : C.m), dv = a1 - a0;
      b += tx(BL - 10, yy + 15, lab, 'lab', 'end') + `<rect x="${x(from)}" y="${yy}" width="${Math.max(2, x(to) - x(from))}" height="20" rx="3" fill="${c}"><title>${esc(T('{part}: {v} points', { part: lab, v: fmt(col ? a1 : dv) }))}</title></rect>` +
        tx(x(to) + 6, yy + 15, col ? pct(a1) : (dv >= 0 ? '+' : '') + fmt(dv), 'val');
    });
    $('#wlBridge').innerHTML = svg(BW, 10 + row * 4 + 26, T('How the gap with the rest of Puerto Rico splits: age mix and participation within each age'), b);
  }

  // ── 4 · Children ──
  function drawKids(A, R) {
    const box = $('#wlKids');
    if (!A.kids || !R.kids) { box.innerHTML = ''; return; }
    const cats = [['u6', T('With children under 6')], ['617', T('With children 6 to 17 only')], ['none', T('No own children under 18')]];
    const W = 860, L = 230, Rm = 70, row = 50, top = 26, H = top + row * 3 + 26;
    const [lo, hi] = niceRange(cats.flatMap(([k]) => [A.kids[k], R.kids[k]].filter(Boolean).flatMap(e => [e[0] - e[1], e[0] + e[1]]))), x = scale(lo, hi, L, W - Rm);
    let s = axis(x, lo, hi, top - 6, top + row * 3 - 8, 5);
    s += `<g class="lg">${tx(L, 12, '●', 'dotarea')}${tx(L + 14, 12, areaName(), 'lab')}${tx(L + 330, 12, '●', 'dotrest')}${tx(L + 344, 12, restLabel(), 'lab')}</g>`;
    cats.forEach(([k, lab], i) => {
      const y = top + i * row + 10;
      s += tx(L - 10, y + 9, lab, 'lab', 'end');
      [[A.kids[k], C.area, 0, areaName()], [R.kids[k], C.rest, 18, restLabel()]].forEach(([e, col, dy, nm]) => {
        s += whisker(x, y + dy, e, col, 6, T('{name}: {v}% (90% margin of error ± {m})', { name: nm, v: fmt(e && e[0]), m: fmt(e && e[1]) }));
        if (e) s += tx(x(Math.min(100, e[0] + e[1])) + 6, y + dy + 4, pct(e[0]), 'val');
      });
    });
    s += tx((L + W - Rm) / 2, H - 2, T('Labor force participation (%)'), 'axis', 'middle');
    box.innerHTML = svg(W, H, T('Women 20 to 64: labor force participation by own children, selected area and rest of Puerto Rico'), s);
  }

  // ── 5 · Over time ──
  function drawTrend() {
    const ws = D.window_ends, series = [['lfpr_f_prime', T('Women 25 to 54'), C.f], ['lfpr_f', T('Women 16 and over'), C.area], ['lfpr_m', T('Men 16 and over'), C.m]];
    const vals = {};
    ws.forEach(w => { vals[w] = { a: measures(areaRec([...S.sel], w)), r: measures(areaRec(restIds(), w)) }; });
    const all = ws.flatMap(w => series.flatMap(([k]) => [vals[w].a[k], vals[w].r[k]].filter(Boolean).flatMap(e => [e[0] - e[1], e[0] + e[1]])));
    const [lo, hi] = niceRange(all), W = 860, L = 60, Rm = 230, top = 30, H = 320, x = (i) => L + (W - L - Rm) * i / (ws.length - 1), y = scale(lo, hi, H - 34, top);
    let s = '';
    for (let v = lo; v <= hi; v += 5) s += `<line x1="${L}" x2="${W - Rm}" y1="${y(v)}" y2="${y(v)}" stroke="${C.grid}"/>` + tx(L - 8, y(v) + 4, fmt(v, 0), 'tick', 'end');
    ws.forEach((w, i) => { s += tx(x(i), H - 12, D.windows[i], 'lab', 'middle'); });
    series.forEach(([k, lab, col]) => {
      ['r', 'a'].forEach(which => {
        const pts = ws.map((w, i) => [x(i), vals[w][which][k]]).filter(p => p[1]);
        s += `<polyline fill="none" stroke="${col}" stroke-width="${which === 'a' ? 3 : 1.5}" ${which === 'r' ? 'stroke-dasharray="5 4" opacity=".7"' : ''} points="${pts.map(p => `${p[0]},${y(p[1][0])}`).join(' ')}"/>`;
        if (which === 'a') pts.forEach(([px, e], i) => { s += `<g><title>${esc(T('{name}, {window}: {v}% ± {m}', { name: areaName() + ' · ' + lab, window: D.windows[i], v: fmt(e[0]), m: fmt(e[1]) }))}</title><line x1="${px}" x2="${px}" y1="${y(e[0] - e[1])}" y2="${y(e[0] + e[1])}" stroke="${col}" stroke-width="2.5" opacity=".5"/><circle cx="${px}" cy="${y(e[0])}" r="5" fill="${col}" stroke="#fff" stroke-width="1.5"/></g>`; });
      });
      const last = vals[ws[ws.length - 1]].a[k];
      if (last) s += tx(W - Rm + 10, y(last[0]) + 4, `${lab} ${pct(last[0])}`, 'lab');
    });
    s += `<g class="lg">${tx(L, 12, '— ' + areaName(), 'lab')}${allIsland() ? '' : tx(L + 300, 12, '- - ' + T('Rest of Puerto Rico'), 'lab')}</g>`;
    $('#wlTrend').innerHTML = svg(W, H, T('Labor force participation in three five-year windows that share no year'), s);
  }

  // ── 6 · The map, the region panel and the municipio dots ──
  const SHADES = [
    ['lfpr_f', T("Women's labor force participation, women 16 and over"), (m) => m.lfpr_f],
    ['lfpr_f_prime', T("Women's labor force participation, women 25 to 54"), (m) => m.lfpr_f_prime],
    ['gap', T('Gap, men minus women (points)'), (m) => { const d = diff(m.lfpr_m, m.lfpr_f); return d && [d.v, d.m]; }],
    ['unemp_f', T('Unemployment rate, women'), (m) => m.unemp_f],
    ['cv', T('Coefficient of variation of the women\'s rate (%)'), (m) => m.lfpr_f && [cv(m.lfpr_f), 0]],
  ];
  const RAMP = ['#EAF4FA', '#BDE0F2', '#8FCAE8', '#5FAFDA', '#338CB3', '#205D7B'];
  let PROJ = null;
  function project() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const each = (g, fn) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).forEach(p => p.forEach(r => r.forEach(fn)));
    GEO.features.forEach(f => each(f.geometry, ([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = (y1 - y0) * sc;
    PROJ = { W, H: Math.ceil(H), f: ([x, y]) => [((x - x0) * k * sc).toFixed(1), ((y1 - y) * sc).toFixed(1)] };
    PROJ.paths = GEO.features.map(f => ({ id: f.properties.GEOID, d: (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates).map(p => p.map(r => 'M' + r.map(PROJ.f).join('L') + 'Z').join('')).join('') }));
  }
  function drawMap() {
    if (!PROJ) project();
    const sh = SHADES.find(s => s[0] === S.shade) || SHADES[0], vals = {};
    muniIds().forEach(g => { vals[g] = sh[2](measures(rec(g))); });
    const xs = Object.values(vals).filter(Boolean).map(e => e[0]).sort((a, b) => a - b), q = [1, 2, 3, 4, 5].map(i => xs[Math.min(xs.length - 1, Math.floor(xs.length * i / 6))]);
    const cls = (v) => v == null ? -1 : q.filter(t => v >= t).length;
    let s = `<defs><pattern id="wlHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#2A2E2E" stroke-width="1.2" opacity=".55"/></pattern></defs>`;
    PROJ.paths.forEach(p => {
      const e = vals[p.id], c = e ? RAMP[cls(e[0])] : '#f0f0f0', on = S.sel.has(p.id), weak = S.shade !== 'cv' && e && S.shade !== 'gap' && cv(e) > CV_MAX;
      const lab = e ? T('{name}: {v} (± {m}). Select to add it to the area or take it out.', { name: D.names[p.id], v: fmt(e[0]), m: fmt(e[1]) }) : T('{name}: no value', { name: D.names[p.id] });
      s += `<path d="${p.d}" fill="${c}" class="mu${on ? ' on' : ''}" data-id="${p.id}" tabindex="0" role="button" aria-pressed="${on}" aria-label="${esc(lab)}"><title>${esc(lab)}</title></path>` + (weak ? `<path d="${p.d}" fill="url(#wlHatch)" pointer-events="none"/>` : '');
    });
    PROJ.paths.filter(p => S.sel.has(p.id)).forEach(p => { s += `<path d="${p.d}" fill="none" stroke="#1d2433" stroke-width="2.6" pointer-events="none"/>`; });
    $('#wlMap').innerHTML = `<svg viewBox="0 0 ${PROJ.W} ${PROJ.H}" width="100%" aria-label="${esc(sh[1])}">${s}</svg>`;
    const unit = S.shade === 'gap' ? ' ' + T('percentage points') : '%';
    $('#wlLegend').innerHTML = `<b>${esc(sh[1])}</b> ` + [xs[0], ...q].map((t, i) => `<span><i style="background:${RAMP[i]}"></i>${esc(fmt(t))}${i < 5 ? '–' + esc(fmt(q[i])) : '+'}</span>`).join('') + `<span>${esc(unit.trim())}</span>` +
      (S.shade !== 'cv' && S.shade !== 'gap' ? `<span><i class="hatch"></i>${esc(T('Less reliable (coefficient of variation over 30%)'))}</span>` : '');
  }
  function drawRegion(A, R) {
    const box = $('#wlRegion');
    if (!S.sel.size) { box.innerHTML = `<p>${esc(T('Select at least one municipio on the map.'))}</p>`; return; }
    const d = R ? diff(A.lfpr_f, R.lfpr_f) : null, gap = diff(A.lfpr_m, A.lfpr_f);
    const mean = [...S.sel].map(g => measures(rec(g)).lfpr_f).filter(Boolean), avg = mean.reduce((s, e) => s + e[0], 0) / mean.length;
    const row = (k, v) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`, pe = (e) => e ? `${pct(e[0])} ± ${fmt(e[1])}` : '—';
    box.innerHTML = `<h3>${esc(areaName())}</h3><p class="wl-small">${esc(S.sel.size === 1 ? T('1 municipio selected') : T('{n} municipios selected', { n: S.sel.size }))} · ${esc(D.windows[D.window_ends.indexOf(S.win)])}</p>` +
      `<div class="wl-big">${esc(pct(A.lfpr_f[0]))}<small> ± ${esc(fmt(A.lfpr_f[1]))}</small></div><p class="wl-small">${esc(T("Women's labor force participation"))}</p>` +
      (R ? `<p>${esc(T('Rest of Puerto Rico: {v}%', { v: fmt(R.lfpr_f[0]) }))}<br>${esc(T('Difference: {d} points ± {m}', { d: (d.v >= 0 ? '+' : '') + fmt(d.v), m: fmt(d.m) }))}<br><b class="${d.sig ? 'sig' : 'nsig'}">${esc(d.sig ? T('Statistically significant at 90%') : T('Not statistically significant at 90%: the two may be equal'))}</b></p>`
        : `<p>${esc(T('All of Puerto Rico is selected: there is no rest of the island to compare with.'))}</p>`) +
      `<dl>${row(T('Women 16 and over in the area'), fmt(A.women16[0], 0) + ' ± ' + fmt(A.women16[1], 0))}${row(T('Women in the labor force'), fmt(A.women_lf[0], 0) + ' ± ' + fmt(A.women_lf[1], 0))}` +
      `${row(T('Women 25 to 54 (prime working age)'), pe(A.lfpr_f_prime))}${row(T('Men 16 and over'), pe(A.lfpr_m))}${row(T('Gap, men minus women'), gap ? T('{v} points', { v: fmt(gap.v) }) + ' ± ' + fmt(gap.m) : '—')}` +
      `${row(T('Unemployment rate, women'), pe(A.unemp_f))}${A.sample ? row(T('People interviewed by the survey in five years (all ages, both sexes)'), fmt(A.sample.people, 0)) : ''}` +
      `${S.sel.size > 1 ? row(T('Simple average of the municipio rates (not the area\'s rate)'), pct(avg)) : ''}</dl>`;
  }
  function drawDots(R) {
    const ids = [...S.sel].sort((a, b) => (measures(rec(b)).lfpr_f || [0])[0] - (measures(rec(a)).lfpr_f || [0])[0]);
    const A = measures(areaRec(ids)), vals = ids.map(g => measures(rec(g)).lfpr_f).filter(Boolean);
    if (!vals.length) { $('#wlDots').innerHTML = ''; return; }
    const [lo, hi] = niceRange(vals.flatMap(e => [e[0] - e[1], e[0] + e[1]]).concat([A.lfpr_f[0]], R ? [R.lfpr_f[0]] : [])), W = 860, L = 170, Rm = 70, row = 22, top = 34, H = top + row * ids.length + 30, x = scale(lo, hi, L, W - Rm);
    let s = axis(x, lo, hi, top - 6, top + row * ids.length, 5);
    s += `<line x1="${x(A.lfpr_f[0])}" x2="${x(A.lfpr_f[0])}" y1="${top - 10}" y2="${top + row * ids.length}" stroke="${C.area}" stroke-width="2"/>` + tx(x(A.lfpr_f[0]), top - 14, areaName() + ' ' + pct(A.lfpr_f[0]), 'lab b', 'middle');
    if (R) s += `<line x1="${x(R.lfpr_f[0])}" x2="${x(R.lfpr_f[0])}" y1="${top - 10}" y2="${top + row * ids.length}" stroke="${C.rest}" stroke-width="2" stroke-dasharray="5 4"/>` + tx(x(R.lfpr_f[0]), H - 4, T('Rest of Puerto Rico: {v}%', { v: fmt(R.lfpr_f[0]) }), 'lab', 'middle');
    ids.forEach((g, i) => {
      const e = measures(rec(g)).lfpr_f, y = top + i * row + 10, weak = e && cv(e) > CV_MAX;
      s += tx(L - 10, y + 4, D.names[g], 'lab', 'end') + whisker(x, y, e, weak ? C.rest : C.f, 5, T('{name}: {v}% (90% margin of error ± {m})', { name: D.names[g], v: fmt(e && e[0]), m: fmt(e && e[1]) }));
      if (e) s += tx(x(Math.min(100, e[0] + e[1])) + 6, y + 4, fmt(e[0]), 'val');
    });
    $('#wlDots').innerHTML = svg(W, H, T("Women's labor force participation, women 16 and over"), s);
  }

  // ── The notes under the charts: what the charts show for the area chosen ──
  const sgn = (v) => (v >= 0 ? '+' : '') + fmt(v);
  const sigText = (d) => (d.sig ? T('it is statistically significant at 90%') : T('it is not statistically significant at 90%'));
  const sigChange = (d) => (d.sig ? T('the change is statistically significant at 90%') : T('the change is not statistically significant at 90%'));
  function drawNotes(Ar, Rr) {
    const A = measures(Ar), g = diff(A.lfpr_m, A.lfpr_f), R = Rr ? measures(Rr) : null, d = R && diff(A.lfpr_f, R.lfpr_f), area = areaName();
    const gap = T('Gap, men minus women: {g} points (± {gm}); {gsig}.', { g: sgn(g.v), gm: fmt(g.m), gsig: sigText(g) });
    $('#wlReadCompare').textContent = (d ? T('Reading it ({area}): the difference with the rest of Puerto Rico is {d} points (± {m}); {sig}.', { area, d: sgn(d.v), m: fmt(d.m), sig: sigText(d) }) : T('Reading it ({area}):', { area })) + ' ' + gap;
    if (!Rr) $('#wlReadAge').textContent = '';   // every municipio chosen: there is no rest of the island to compare ages with
    else {
      const ages = D.ages.filter((_, i) => { const x = diff(A.by_age_f[i], R.by_age_f[i]); return x && x.sig; }), k = ageSplit(Ar, Rr);
      $('#wlReadAge').textContent = (ages.length === D.ages.length ? T('Reading it ({area}): every age group differs significantly from the rest of Puerto Rico.', { area })
        : ages.length ? T('Reading it ({area}): the age groups that differ significantly from the rest of Puerto Rico are {ages}.', { area, ages: ages.join(', ') })
          : T('Reading it ({area}): no age group differs significantly from the rest of Puerto Rico.', { area })) + ' ' +
        T('Age-adjusted rate: {adj}% (actual rate {crude}%). Age mix: {mix} points; participation within each age: {rate} points.', { adj: fmt(k.adjusted), crude: fmt(A.lfpr_f[0]), mix: sgn(k.from_age_mix), rate: sgn(k.from_rates) });
    }
    const w0 = D.window_ends[0], w1 = D.window_ends[D.window_ends.length - 1], m0 = measures(areaRec([...S.sel], w0)), m1 = measures(areaRec([...S.sel], w1));
    const c = diff(m1.lfpr_f, m0.lfpr_f), c2 = diff(m1.lfpr_f_prime, m0.lfpr_f_prime);
    $('#wlReadTrend').textContent = c && c2 ? T('Reading it ({area}): from {w0} to {w1}, the participation of women 16 and over changed {d} points (± {m}); {sig}. For women 25 to 54 it changed {d2} points (± {m2}); {sig2}.',
      { w0: D.windows[0], w1: D.windows[D.windows.length - 1], area, d: sgn(c.v), m: fmt(c.m), sig: sigChange(c), d2: sgn(c2.v), m2: fmt(c2.m), sig2: sigChange(c2) }) : '';
  }

  function csv() {
    const out = [[T('Area'), T('Window'), T('Measure'), T('Estimate'), T('Margin of error (90%)')]];
    const put = (name, w, m) => [["Women's labor force participation", m.lfpr_f], ['Women 25 to 54 (prime working age)', m.lfpr_f_prime], ['Men 16 and over', m.lfpr_m], ['Unemployment rate, women', m.unemp_f], ['Women 16 and over in the area', m.women16], ['Women in the labor force', m.women_lf]]
      .forEach(([k, e]) => out.push([name, D.windows[D.window_ends.indexOf(w)], T(k), e ? e[0].toFixed(k.startsWith('Women 16') || k.startsWith('Women in') ? 0 : 1) : '', e ? e[1].toFixed(1) : '']));
    D.window_ends.forEach(w => { put(areaName(), w, measures(areaRec([...S.sel], w))); if (S.sel.size < 78) put(T('Rest of Puerto Rico'), w, measures(areaRec(restIds(), w))); [...S.sel].forEach(g => put(D.names[g], w, measures(rec(g, w)))); });
    const text = out.map(r => r.map(v => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v).join(',')).join('\n');
    const a = doc.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + text], { type: 'text/csv' })); a.download = 'women_labor_force.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function writeHash() {
    const a = S.preset || [...S.sel].sort().join(',') || 'none';
    history.replaceState(null, '', `#a=${a}&w=${S.win}&s=${S.shade}`);
  }
  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1)), a = h.get('a'), w = +h.get('w'), s = h.get('s');
    if (D.window_ends.includes(w)) S.win = w;
    if (SHADES.some(x => x[0] === s)) S.shade = s;
    if (a && D.groups[a]) setPreset(a, false);
    else if (a === 'none') { S.sel = new Set(); S.preset = null; }
    else if (a) { const ids = a.split(',').filter(g => D.names[g]); if (ids.length) { S.sel = new Set(ids); S.preset = matchPreset(); } }
  }
  function matchPreset() {
    const key = [...S.sel].sort().join(',');
    return Object.keys(D.groups).find(k => D.groups[k].ids.slice().sort().join(',') === key) || null;
  }
  function setPreset(id, draw = true) { S.preset = id; S.sel = new Set(D.groups[id].ids); if (draw) render(); }

  function render() {
    const ids = [...S.sel], A = ids.length ? measures(areaRec(ids)) : null, rest = restIds(), R = rest.length ? measures(areaRec(rest)) : null, P = measures(rec('72'));
    $('#wlPresets').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.p === S.preset)));
    drawMap(); drawRegion(A || {}, R);
    if (A) {
      drawCompare(A, R || P, P); drawWaffle(A); drawKids(A, R || P); drawTrend(); drawDots(R);
      drawAge(areaRec(ids), rest.length ? areaRec(rest) : rec('72'));
      drawNotes(areaRec(ids), rest.length ? areaRec(rest) : null);
    } else {   // nothing chosen: no chart keeps the previous area
      const msg = `<p class="wl-p">${esc(T('Select at least one municipio on the map.'))}</p>`;
      ['#wlCompare', '#wlWaffle', '#wlAge', '#wlBridge', '#wlKids', '#wlTrend', '#wlDots'].forEach(id => { $(id).innerHTML = msg; });
      $('#wlSample').innerHTML = '';
      ['#wlReadCompare', '#wlReadAge', '#wlReadTrend'].forEach(id => { $(id).textContent = ''; });
    }
    writeHash();
  }

  function start() {
    S.win = D.latest;
    setPreset('ersv', false);
    readHash();
    const pres = [['ersv', T('Eastern Region (ERSV, 15)')], ...Object.keys(D.groups).filter(k => k !== 'ersv').map(k => [k, D.groups[k].name[lang()] || D.groups[k].name.en])];
    $('#wlPresets').innerHTML = pres.map(([k, n]) => `<button type="button" data-p="${esc(k)}" aria-pressed="false">${esc(n)}</button>`).join('') + `<button type="button" data-p="" aria-pressed="false">${esc(T('Clear selection'))}</button>`;
    $('#wlPresets').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; if (b.dataset.p) setPreset(b.dataset.p); else { S.sel.clear(); S.preset = null; render(); } });
    $('#wlShade').innerHTML = SHADES.map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join(''); $('#wlShade').value = S.shade;
    $('#wlShade').addEventListener('change', (e) => { S.shade = e.target.value; render(); });
    $('#wlWindow').innerHTML = D.window_ends.map((w, i) => `<option value="${w}">${esc(D.windows[i])}</option>`).join(''); $('#wlWindow').value = S.win;
    $('#wlWindow').addEventListener('change', (e) => { S.win = +e.target.value; render(); });
    const toggle = (el) => { const g = el.dataset.id; if (S.sel.has(g)) S.sel.delete(g); else S.sel.add(g); S.preset = matchPreset(); render(); const again = $(`#wlMap path[data-id="${g}"]`); if (again) again.focus(); };
    $('#wlMap').addEventListener('click', (e) => { const p = e.target.closest('path.mu'); if (p) toggle(p); });
    $('#wlMap').addEventListener('keydown', (e) => { const p = e.target.closest('path.mu'); if (p && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggle(p); } });
    $('#wlCsv').addEventListener('click', (e) => { e.preventDefault(); csv(); });
    root.addEventListener('hashchange', () => { readHash(); $('#wlShade').value = S.shade; $('#wlWindow').value = S.win; render(); });
    render();
  }
})(typeof window !== 'undefined' ? window : globalThis);
