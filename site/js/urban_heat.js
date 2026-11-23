/* PR Data Observatory: the Urban heat page (urban-heat.html, Knowledge Area; terrain and climate plan, step 3, decision 80).
   Loads data/urban_heat.json (urban_heat.py: for the 901 barrios, the land's summer surface heat in the morning and at night and its greenness, beside
   measures of the residents: 65 and older, poverty, no vehicle, living alone, drive time to a general hospital). The reader picks one land measure and one
   people measure, and a municipio; the page shows them side by side and never combines them. It states facts and draws no conclusion.
   The choice is kept in the address (#l=..&p=..&m=..). Every visible string goes through T(): its Spanish is in i18n_src/es/urban_heat.json, written by
   docs/analysis/urban-heat-2026-11/make_page.py. */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');

  // [key, label, unit kind, decimals]
  const LAND = [['day', 'Surface temperature, summer mornings (°C)', 'c', 1], ['night', 'Surface temperature, summer nights (°C)', 'c', 1], ['ndvi', 'Vegetation greenness (NDVI)', 'n', 2]];
  const PEOPLE = [['age65', 'Residents 65 and older (%)', 'p', 1], ['pov', 'Residents below the poverty level (%)', 'p', 1], ['noveh', 'Households without a vehicle (%)', 'p', 1],
    ['alone', 'Households of one person living alone (%)', 'p', 1], ['hosp', 'Drive time to a general hospital (minutes)', 'm', 0]];
  const MAPKEY = { day: 'heat_lst_med', night: 'night_lst_med', ndvi: 'veg_ndvi_med' };
  const S = { l: 'night', p: 'age65', m: '', sort: ['day', -1] };
  let D;

  if (doc) fetchJson('data/urban_heat.json').then((d) => { D = d; start(); }, (e) => {
    $('#uhScatter').innerHTML = `<p class="pm-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  const def = (list, k) => list.find(x => x[0] === k);
  const show = (kind, v, d) => kind === 'c' ? (v == null ? '—' : fmt(v, d) + ' °C') : kind === 'p' ? pct(v, d) : kind === 'm' ? (v == null ? '—' : fmt(v, d) + ' min') : fmt(v, d);
  const landV = (k, i) => D.land[k][i];
  const peopleV = (k, i) => D.people[k][i];
  const moeV = (k, i) => (D.moe[k] ? D.moe[k][i] : null);
  /** The rule of core/reliability.js: a margin of error above 30% of the estimate, or any margin on an estimate of zero. */
  const unreliable = (v, m) => v != null && m != null && m > 0 && (v === 0 || m / Math.abs(v) > 0.3);
  const inMuni = (i) => !S.m || D.geo.muni[i] === S.m;

  function median(xs) { const s = xs.slice().sort((a, b) => a - b), h = s.length >> 1; return s.length ? (s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2) : null; }
  function spearman(a, b) {
    const rank = (x) => { const o = x.map((v, i) => [v, i]).sort((p, q) => p[0] - q[0]), r = new Array(x.length); let k = 0; while (k < o.length) { let j = k; while (j + 1 < o.length && o[j + 1][0] === o[k][0]) j++; for (let t = k; t <= j; t++) r[o[t][1]] = (k + j) / 2; k = j + 1; } return r; };
    const ra = rank(a), rb = rank(b), n = a.length, ma = (n - 1) / 2;
    let sab = 0, sa = 0, sb = 0; for (let i = 0; i < n; i++) { sab += (ra[i] - ma) * (rb[i] - ma); sa += (ra[i] - ma) ** 2; sb += (rb[i] - ma) ** 2; }
    return sa && sb ? sab / Math.sqrt(sa * sb) : null;
  }
  const pairs = (only) => D.geo.ids.map((_, i) => i).filter(i => landV(S.l, i) != null && peopleV(S.p, i) != null && (!only || inMuni(i)));

  // ── The scatter: the land measure across, the people measure up; the barrios of the chosen municipio on top ──
  function drawScatter() {
    const [, ll, lk, ld] = def(LAND, S.l), [, pl, pk, pd] = def(PEOPLE, S.p);
    const all = pairs(false), W = 860, H = 400, L = 64, R = 16, Tp = 12, B = 48;
    const xs = all.map(i => landV(S.l, i)), ys = all.map(i => peopleV(S.p, i));
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = 0, y1 = Math.max(...ys) || 1;
    const X = (v) => L + (v - x0) / (x1 - x0 || 1) * (W - L - R), Y = (v) => Tp + (y1 - v) / (y1 - y0 || 1) * (H - Tp - B);
    let s = '';
    for (let k = 0; k <= 4; k++) {
      const v = y0 + (y1 - y0) * k / 4, x = x0 + (x1 - x0) * k / 4;
      s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e4e7ec"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${esc(show(pk, v, pk === 'm' ? 0 : 0))}</text>`;
      s += `<text x="${X(x)}" y="${H - B + 16}" text-anchor="middle" class="tick">${esc(show(lk, x, ld))}</text>`;
    }
    const mx = median(xs), my = median(ys);
    s += `<line x1="${X(mx)}" x2="${X(mx)}" y1="${Tp}" y2="${H - B}" class="med"/><line x1="${L}" x2="${W - R}" y1="${Y(my)}" y2="${Y(my)}" class="med"/>`;
    s += `<text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle" class="axis">${esc(T(ll))}</text>`;
    s += `<text transform="translate(14,${(Tp + H - B) / 2}) rotate(-90)" text-anchor="middle" class="axis">${esc(T(pl))}</text>`;
    const back = all.filter(i => !(S.m && inMuni(i))), front = S.m ? all.filter(inMuni) : [];
    const dot = (i, on) => {
      const v = landV(S.l, i), w = peopleV(S.p, i), weak = unreliable(w, moeV(S.p, i));
      const lab = T('{name} ({muni}): {land}; {people}', { name: D.geo.names[i], muni: D.geo.muni_names[D.geo.muni[i]], land: show(lk, v, ld), people: show(pk, w, pd) }) + (weak ? ' · ' + T('margin of error above 30% of the estimate') : '');
      return `<circle cx="${X(v).toFixed(1)}" cy="${Y(w).toFixed(1)}" r="${on ? 5.5 : 3.2}" fill="${weak ? '#fff' : on ? '#C8102E' : (S.m ? '#c9ced8' : '#205D7B')}" fill-opacity="${on || !S.m ? 0.85 : 0.6}" stroke="${on ? '#7a0a1c' : (S.m ? '#aab1bd' : '#205D7B')}" stroke-width="${weak ? 1.2 : 0.6}"><title>${esc(lab)}</title></circle>`;
    };
    back.forEach(i => { s += dot(i, false); }); front.forEach(i => { s += dot(i, true); });
    $('#uhScatter').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(T('Scatter plot: each dot is a barrio; dashed lines mark the medians of all barrios'))}">${s}</svg>`;
    const rAll = spearman(xs, ys), sub = pairs(true);
    let txt = T('Rank correlation across the {n} barrios with both values: {rho}.', { n: fmt(all.length), rho: fmt(rAll, 2) });
    if (S.m) {
      const name = D.geo.muni_names[S.m];
      txt += ' ' + (sub.length >= 10 ? T('Within {muni} ({n} barrios): {rho}.', { muni: name, n: fmt(sub.length), rho: fmt(spearman(sub.map(i => landV(S.l, i)), sub.map(i => peopleV(S.p, i))), 2) })
        : T('{muni} has {n} barrios with both values, too few for a rank correlation.', { muni: name, n: fmt(sub.length) }));
    }
    $('#uhRead').textContent = txt;
  }

  // ── The table: the barrios of the municipio (or of Puerto Rico), every measure side by side ──
  const COLS = [['name', 'Barrio'], ['muni', 'Municipio'], ['pop', 'Residents (2020 Census)'], ...LAND.map(([k, l]) => [k, l]), ...PEOPLE.map(([k, l]) => [k, l])];
  function val(k, i) {
    if (k === 'name') return D.geo.names[i];
    if (k === 'muni') return D.geo.muni_names[D.geo.muni[i]];
    if (k === 'pop') return D.population[i];
    return D.land[k] ? landV(k, i) : peopleV(k, i);
  }
  function cell(k, i) {
    const v = val(k, i);
    if (k === 'name' || k === 'muni') return `<td>${esc(v)}</td>`;
    if (k === 'pop') return `<td class="num">${esc(fmt(v))}</td>`;
    const d = def(LAND, k) || def(PEOPLE, k), m = moeV(k, i), weak = unreliable(v, m);
    const txt = v == null ? '—' : fmt(v, d[3]) + (m != null && v != null ? ` ± ${fmt(m, d[3])}` : '');
    return `<td class="num${weak ? ' weak' : ''}"${weak ? ` title="${esc(T('margin of error above 30% of the estimate'))}"` : ''}>${esc(txt)}</td>`;
  }
  function drawTable() {
    const [key, dir] = S.sort, rows = D.geo.ids.map((_, i) => i).filter(inMuni).sort((a, b) => {
      const x = val(key, a), y = val(key, b);
      if (key === 'name' || key === 'muni') return dir * String(x).localeCompare(String(y), loc()) || a - b;
      if (x == null || y == null) return (x == null) - (y == null) || a - b;   // blanks last, whatever the direction
      return dir * (x - y) || a - b;
    });
    const head = COLS.map(([k, l]) => `<th scope="col"${['name', 'muni'].includes(k) ? '' : ' class="num"'} aria-sort="${k === key ? (dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" data-k="${k}">${esc(T(l))}</button></th>`).join('');
    const body = rows.map(i => `<tr>${COLS.map(([k]) => cell(k, i)).join('')}</tr>`).join('');
    $('#uhTable').innerHTML = `<table class="pm-table uh-table"><caption class="sr-only">${esc(T('Barrios: surface heat, greenness and residents, side by side'))}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    $('#uhCount').textContent = T('{n} barrios. Values in italics have a margin of error above 30% of the estimate; ± is the margin of error at 90% confidence.', { n: fmt(rows.length) });
  }

  // ── The grid of rank correlations across all barrios (from the data file) ──
  function drawGrid() {
    const r = (a, b) => (D.rho[`${a}:${b}`] || D.rho[`${b}:${a}`] || {}).rho;
    const head = `<th scope="col"></th>${PEOPLE.map(([, l]) => `<th scope="col" class="num">${esc(T(l))}</th>`).join('')}`;
    const body = LAND.map(([k, l]) => `<tr><th scope="row">${esc(T(l))}</th>${PEOPLE.map(([p]) => `<td class="num">${esc(fmt(r(k, p), 2))}</td>`).join('')}</tr>`).join('');
    const land = [['day', 'night'], ['day', 'ndvi'], ['night', 'ndvi']].map(([a, b]) => `<li>${esc(T('{a} and {b}: {rho}', { a: T(def(LAND, a)[1]), b: T(def(LAND, b)[1]), rho: fmt(r(a, b), 2) }))}</li>`).join('');
    $('#uhGrid').innerHTML = `<table class="pm-table uh-grid"><caption class="sr-only">${esc(T('Rank correlations across the barrios'))}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table><ul class="pm-small uh-land">${land}</ul>`;
  }

  function mapLink() {
    const a = $('#uhMap');
    if (a) a.href = `index.html${lang() === 'es' ? '?lang=es' : ''}#e=${MAPKEY[S.l]}.b.value.${S.l === 'ndvi' ? 'green' : 'red'}.q.1.0.0.85.0`;
  }

  function csv() {
    const out = [[T('Barrio'), 'GEOID', T('Municipio'), T('Residents (2020 Census)'), ...LAND.map(([, l]) => T(l)), ...PEOPLE.flatMap(([k, l]) => D.moe[k] ? [T(l), T('{measure}: margin of error', { measure: T(l) })] : [T(l)])]];
    D.geo.ids.forEach((g, i) => { if (inMuni(i)) out.push([D.geo.names[i], g, D.geo.muni_names[D.geo.muni[i]], D.population[i], ...LAND.map(([k]) => landV(k, i) ?? ''), ...PEOPLE.flatMap(([k]) => D.moe[k] ? [peopleV(k, i) ?? '', moeV(k, i) ?? ''] : [peopleV(k, i) ?? ''])]); });
    const text = out.map(r => r.map(v => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v).join(',')).join('\n');
    const a = doc.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + text], { type: 'text/csv' })); a.download = `urban_heat_${S.m || 'pr'}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function writeHash() { history.replaceState(null, '', `#l=${S.l}&p=${S.p}${S.m ? '&m=' + S.m : ''}`); }
  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    if (def(LAND, h.get('l'))) S.l = h.get('l');
    if (def(PEOPLE, h.get('p'))) S.p = h.get('p');
    if (D.geo.muni_names[h.get('m')]) S.m = h.get('m');
  }
  function render() { drawScatter(); drawTable(); mapLink(); writeHash(); }
  function start() {
    readHash();
    const opts = (list) => list.map(([k, l]) => `<option value="${k}">${esc(T(l))}</option>`).join('');
    const munis = Object.entries(D.geo.muni_names).sort((a, b) => a[1].localeCompare(b[1], loc()));
    $('#uhLand').innerHTML = opts(LAND); $('#uhLand').value = S.l;
    $('#uhPeople').innerHTML = opts(PEOPLE); $('#uhPeople').value = S.p;
    $('#uhMuni').innerHTML = `<option value="">${esc(T('All of Puerto Rico'))}</option>` + munis.map(([g, n]) => `<option value="${g}">${esc(n)}</option>`).join(''); $('#uhMuni').value = S.m;
    $('#uhLand').addEventListener('change', (e) => { S.l = e.target.value; render(); });
    $('#uhPeople').addEventListener('change', (e) => { S.p = e.target.value; render(); });
    $('#uhMuni').addEventListener('change', (e) => { S.m = e.target.value; render(); });
    $('#uhTable').addEventListener('click', (e) => { const b = e.target.closest('button[data-k]'); if (!b) return; S.sort = [b.dataset.k, S.sort[0] === b.dataset.k ? -S.sort[1] : (['name', 'muni'].includes(b.dataset.k) ? 1 : -1)]; drawTable(); });
    $('#uhCsv').addEventListener('click', csv);
    drawGrid(); render();
  }
  root.UrbanHeat = { spearman, median, unreliable };   // for tests/urban_heat.test.js
})(typeof window !== 'undefined' ? window : globalThis);
