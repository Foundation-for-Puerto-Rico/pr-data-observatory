/* FPR Research in Data · The State of Housing in Puerto Rico (2023 study) — extended with every year the public sources allow.
   Reads data/housing_series.json (built by housing_series.py): ~45 variables by year for the 78 municipalities and Puerto Rico.
   A year bar moves every map, chart and table together; every dataset opens in full (all years, all municipalities, margins of error,
   CSV). Shared helpers are in common.js. */

if (typeof Chart === 'undefined' || typeof L === 'undefined') {
  document.querySelector('.page').insertAdjacentHTML('afterbegin', `<div class="card" role="alert">${Th('<b>The charting libraries did not load.</b> Check your connection, then <a href="" onclick="location.reload();return false">try again</a>.')}</div>`);
  throw new Error('Chart.js or Leaflet unavailable');
}
const money = (n) => n == null ? '—' : '$' + fmt(n);   // locale-aware: Spanish in Puerto Rico writes $1,234 too
const RAMP = Core.palettes.RAMPS.blue, DIV = Core.palettes.DIVERGING, LINES = Core.palettes.LINES;
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (new URLSearchParams(location.search).has('embed')) document.body.classList.add('embed');
const S = { meta: {}, muni: {}, fc: null, paper: {}, series: null, V: {}, NM: [], PR: 0, year: null, base: 2012, selected: 'Ceiba', maps: [], vizzes: [], booting: true, t2: { from: 2020, to: null }, charts: {}, STATIC: {} };

const loadJson = (p) => fetchJson(p);
const idxOf = (name) => S.NM.indexOf(name);

// ── Variables, years and values ────────────────────────────────────────────
// Every variable is {key, label, unit, d, ys: [years], years: {year: [79 values]}, moe?, kind, ref, definition}; the last value is Puerto Rico.
// Display text that comes from data (a variable's label and group, the population basis, the LIHTC type and beneficiaries) reaches the screen
// as T(variable): its Spanish is in i18n_src/es/labels_housing.json (series labels and groups) and housing.json (the rest).
const CHANGE = [   // synthetic variables: the change from the base year to the selected year
  ['home_value_change_pct', 'median_home_value', 'Median home value change', '%'],
  ['gross_rent_change_pct', 'median_gross_rent', 'Median gross rent change', '%'],
  ['income_change_pct', 'median_hh_income', 'Median household income change', '%'],
  ['bachelors_change_pts', 'bachelors_pct', "Adults 25+ with a bachelor's degree or higher, change", ' pts'],
];
const LAND = ['urban_pct', 'urbanizable_pct', 'protected_land_pct'];
const LAND_META = {
  urban_pct: ['Land classified Suelo Urbano', T("Share of the municipality's land (excluding water and roads) classified as urban in the Plan de Uso de Terrenos 2015.")],
  urbanizable_pct: ['Land classified Suelo Urbanizable (programado + no programado)', T('Share of land reserved for future urban growth in the Plan de Uso de Terrenos 2015.')],
  protected_land_pct: ['Land classified Suelo Rústico Especialmente Protegido', T("Share of land under special protection (ecological, agricultural, hydric) in the Plan de Uso de Terrenos 2015, where housing development is restricted.")],
};
function indexSeries() {
  const sr = S.series; S.NM = sr.geo.names; S.PR = S.NM.length - 1;
  sr.vars.forEach(v => { v.ys = Object.keys(v.years).map(Number).sort((a, b) => a - b); S.V[v.key] = v; });
  CHANGE.forEach(([key, base, label, unit]) => {
    const b = S.V[base];
    S.V[key] = { key, synthetic: true, baseKey: base, group: b.group, label, unit, d: 1, kind: b.kind, ref: b.ref, diverging: true,
      definition: T('{label}: the change from the base year to the selected year. Not adjusted for inflation. Choose the base year in the year bar.', { label: T(b.label) }),
      get ys() { return b.ys.filter(y => y > S.base); }, compute(y) { const a = S.V[base].years[y], c = S.V[base].years[S.base]; if (!a || !c) return null; return a.map((x, i) => x == null || c[i] == null ? null : unit === '%' ? (c[i] ? +((x - c[i]) / c[i] * 100).toFixed(2) : null) : +(x - c[i]).toFixed(2)); } };
  });
  LAND.forEach(key => {
    const a = S.NM.map(n => (S.muni[n] || {})[key]);
    S.V[key] = { key, static: true, group: 'Land use', label: LAND_META[key][0], unit: '%', d: 1, kind: 'put', ref: 'Plan de Uso de Terrenos 2015', definition: LAND_META[key][1], ys: [2015], years: { 2015: a.map(x => x == null ? null : x) } };
  });
}
// the year each variable shows for the selected year: the same year if it has one, else the latest before it, else its first (Core.time)
const resolve = (k) => Core.time.resolve(S.V[k], S.year);
function arr(k, y) { const v = S.V[k]; if (!v || y == null) return null; return v.synthetic ? v.compute(y) : (v.years[y] || null); }
function moeArr(k, y) { const v = S.V[k]; return v && v.moe ? v.moe[y] || null : null; }
const at = (k) => { const r = resolve(k); return { ...r, a: arr(k, r.y) }; };
function fv(k, v) {
  const c = S.V[k]; if (v == null || !c) return '—';
  if (c.plain) return String(Math.round(v));
  if (c.unit === '$') return money(v);
  return `${fmt(v, c.d)}${unitText(c.unit)}`;
}
const unitText = (u) => u === ' pts' ? ' ' + T('pts') : (u || '');   // units are compared in code (%, $, pts): only what is shown is translated
function fm(k, v, m) { return v == null ? '—' : m != null ? `${fv(k, v)} <span class="moe">±${S.V[k].unit === '$' ? money(m) : fmt(m, S.V[k].d)}${S.V[k].unit === '%' ? ' ' + T('pts') : ''}</span>` : fv(k, v); }
const winText = (y) => (S.series.notes.acs_windows || {})[y] || String(y);
function srcTag(k, y) {
  const v = S.V[k];
  if (v.kind === 'acs' || v.kind === 'derived') return `ACS ${winText(y)}`;
  if (v.kind === 'pop') return v.basis && /census count/.test(v.basis[y] || '') ? T('Census {year}', { year: y }) : T('Estimate {year}', { year: y });
  if (v.kind === 'census') return T('Census {year}', { year: y });
  if (v.kind === 'fema') return `FEMA ${y}`;
  if (v.kind === 'put') return 'PUT 2015';
  return String(y);
}
function titleOf(k, y) {
  const v = S.V[k];
  if (v.synthetic) return `${T(v.label)}, ${S.base} → ${y ?? '—'}`;
  return T(v.label);
}
const pooledCache = {};
function pooled(k) {   // the classes of a variable: cut from its values in every year at once, so a colour means the same in every year
  const key = k + '|' + S.base; if (pooledCache[key]) return pooledCache[key];
  const v = S.V[k], all = [];
  for (const y of v.ys) { const a = arr(k, y); if (a) for (let i = 0; i < S.PR; i++) if (a[i] != null) all.push(a[i]); }
  all.sort((a, b) => a - b);
  return pooledCache[key] = Core.classify.make(all, { method: 'quantile', k: 5, div: !!v.diverging, center: 0 });
}
function colorFor(k, v) {
  if (v == null) return '#f0f0f0';
  const c = Core.classify.classOf(pooled(k), v);
  return c < 0 ? '#f0f0f0' : (S.V[k].diverging ? DIV : RAMP)[c];
}
const median = Core.stats.median;
function rankOf(k, name, a, short) {
  a = a || at(k).a; const i = idxOf(name); if (!a || i < 0 || a[i] == null) return null;
  const list = a.slice(0, S.PR).filter(x => x != null).sort((x, y) => y - x), r = list.indexOf(a[i]) + 1;
  return short ? T('#{rank} of {total}', { rank: r, total: list.length }) : T('#{rank} of {total}, highest first', { rank: r, total: list.length });
}
const yearsAll = () => S.series.years.filter(y => y >= 2010);
const latestYear = () => Math.max(S.series.latest.pop, S.series.latest.acs);

// ── Variable block: map + ranked bars, driven by the year bar ──────────────
function miniMap(el) {
  const map = L.map(el, { zoomControl: false, attributionControl: false, scrollWheelZoom: false, dragging: !L.Browser.mobile }).setView([18.2, -66.45], 8);
  L.control.zoom({ position: 'topright', zoomInTitle: T('Zoom in'), zoomOutTitle: T('Zoom out') }).addTo(map);
  S.maps.push(map);   // no base tiles: the municipalities are the content (keeps the page key-free and fast)
  return map;
}
const selStyle = (f) => { const on = f.properties.municipality === S.selected; return { color: on ? '#2A2E2E' : '#fff', weight: on ? 3 : .7 }; };
function legendHTML(k, a) {
  const c = S.V[k], b = pooled(k), vals = a ? a.slice(0, S.PR).filter(x => x != null) : [], n = Core.legend.counts(b, vals);
  let items;
  if (c.diverging) {
    const sp = b.span, lab = [T('below {v}', { v: fv(k, -.5 * sp) }), T('{a} to {b}', { a: fv(k, -.5 * sp), b: fv(k, -.1 * sp) }), T('within ±{v}', { v: fv(k, .1 * sp) }), T('{a} to {b}', { a: fv(k, .1 * sp), b: fv(k, .5 * sp) }), T('above {v}', { v: fv(k, .5 * sp) })];
    items = DIV.map((color, i) => ({ color, label: lab[i], n: n[i] }));
  } else {
    items = RAMP.map((color, i) => ({ color, label: T('{a} to {b}', { a: fv(k, b.edges[i]), b: fv(k, b.edges[i + 1]) }), n: n[i] }));
  }
  items = items.filter(i => i.n || !c.diverging);
  return Core.legend.inline(items, (c.diverging ? T('Diverging around 0.') : T('Five equal-count classes (quintiles) taken over every year together.')) + ' ' + T('Colours keep the same meaning in every year, so you can watch the map change. Small numbers are municipalities per class.'));
}
function updateReadout(el) {
  const k = el.dataset.var, r = el.querySelector('.readout'); if (!r) return;
  const { y, a } = at(k), i = idxOf(S.selected), m = moeArr(k, y);
  r.innerHTML = a && a[i] != null ? `<b>${esc(S.selected)}</b>: ${fm(k, a[i], m && m[i])} · ${esc(rankOf(k, S.selected, a) || '')}` : Th('<b>{name}</b>: no value for {year}', { name: S.selected, year: y ?? T('this year') });
}
function yearChip(k) {
  const { y, exact, early } = resolve(k), v = S.V[k];
  if (v.static) return `<span class="tag live">${esc(srcTag(k, y))}</span>`;
  const note = exact ? '' : early ? ` <span class="yr-note-inline">${esc(T('first data {year}', { year: y }))}</span>` : ` <span class="yr-note-inline">${esc(T('latest at or before {year}', { year: S.year }))}</span>`;
  return `<span class="tag live">${esc(srcTag(k, y))}</span>${note}`;
}
function buildViz(el) {
  if (el.dataset.built) return; el.dataset.built = '1'; el.style.minHeight = '';
  const k = el.dataset.var, c = S.V[k]; if (!c) { el.textContent = ''; return; }
  el.innerHTML = `<div class="viz-head"><h3><span class="vt"></span><span class="tag paper">${esc(c.ref)}</span><span class="chip"></span>${helpBtn(k)}</h3><div class="viz-actions"><div class="stats"></div><button type="button" class="btn small" data-open="${esc(k)}"><span class="ms-icon" aria-hidden="true">table_view</span>${esc(T('Full data'))}</button></div></div>
    <div class="viz-body"><div class="mini-col"><div class="mini-map" role="group"></div><div class="readout" aria-live="polite"></div></div><div class="chart-scroll" tabindex="0" role="region"><div class="chart-wrap"><canvas role="img"></canvas></div></div></div>
    <div class="ramp-row"></div>`;
  const map = miniMap(el.querySelector('.mini-map'));
  const st = { key: k, map, chart: null, rows: [] };
  st.layer = L.geoJSON(S.fc, { style: f => ({ ...selStyle(f), fillColor: colorFor(k, (at(k).a || [])[idxOf(f.properties.municipality)]), fillOpacity: .9 }), onEachFeature: (f, l) => {
    const n = f.properties.municipality;
    l.bindTooltip(() => { const { y, a } = at(k), i = idxOf(n), m = moeArr(k, y); return `<b>${esc(n)}</b><br>${esc(titleOf(k, y))}: ${fm(k, a && a[i], m && m[i])}<br><small>${rankOf(k, n, a) || ''} · ${esc(srcTag(k, y))}</small>`; }, { sticky: true });
    l.on('click', () => selectMuni(n));
    l.on('mouseover', () => l.setStyle({ weight: 2, color: '#2A2E2E' })); l.on('mouseout', () => st.layer.resetStyle(l));
  } }).addTo(map);
  S.maps.push; el._viz = st; S.vizzes.push(el);
  st.chart = new Chart(el.querySelector('canvas'), { type: 'bar', data: { labels: [], datasets: [{ data: [], backgroundColor: [], borderWidth: 0, barThickness: 7 }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: t => ` ${fv(k, t.raw)}` } } }, scales: { x: { grid: { color: '#f0f0f0' }, ticks: { font: { size: 10 }, callback: val => fv(k, val) } }, y: { ticks: { font: { size: 9 }, autoSkip: false } } }, onClick: (e, items) => { if (items.length) selectMuni(st.rows[items[0].index].n); } } });
  updateViz(el);
  setTimeout(() => map.invalidateSize(), 50);
}
function updateViz(el) {
  const st = el._viz; if (!st) return; el._stale = false;
  const k = st.key, c = S.V[k], { y, a } = at(k), vals = a ? a.slice(0, S.PR) : [];
  const title = titleOf(k, y);
  el.querySelector('.vt').textContent = title;
  el.querySelector('.chip').innerHTML = yearChip(k);
  const real = vals.filter(x => x != null);
  el.querySelector('.stats').innerHTML = real.length ? Th('Median of the 78 municipalities <b>{median}</b> · lowest <b>{low}</b> · highest <b>{high}</b>', { median: fv(k, median(real)), low: fv(k, Math.min(...real)), high: fv(k, Math.max(...real)) }) + (a && a[S.PR] != null ? ` · ${Th('Puerto Rico <b>{value}</b>', { value: fv(k, a[S.PR]) })}` : '') : esc(T('No values for {year}.', { year: y ?? T('this year') }));
  el.querySelector('.mini-map').setAttribute('aria-label', T('{title}, map of the 78 municipalities. The same values are in the ranked chart and in the municipality profile.', { title }));
  el.querySelector('.chart-scroll').setAttribute('aria-label', T('{title}: ranked list of all 78 municipalities, scrollable', { title }));
  el.querySelector('canvas').setAttribute('aria-label', real.length ? T('{title}, ranked bars for the 78 municipalities. Highest {high}, lowest {low}.', { title, high: fv(k, Math.max(...real)), low: fv(k, Math.min(...real)) }) : T('{title}, ranked bars for the 78 municipalities.', { title }));
  st.layer.eachLayer(l => l.setStyle({ ...selStyle(l.feature), fillColor: colorFor(k, vals[idxOf(l.feature.properties.municipality)]), fillOpacity: .9 }));
  st.rows = vals.map((v, i) => ({ n: S.NM[i], v })).filter(r => r.v != null).sort((p, q) => q.v - p.v);
  const ch = st.chart;
  ch.data.labels = st.rows.map(r => r.n); ch.data.datasets[0].data = st.rows.map(r => r.v); ch.data.datasets[0].backgroundColor = st.rows.map(r => colorFor(k, r.v));
  el.querySelector('.chart-wrap').style.height = Math.max(300, st.rows.length * 11) + 'px';
  ch.update('none');
  el.querySelector('.ramp-row').innerHTML = legendHTML(k, a);
  updateReadout(el);
}

// ── Tables ─────────────────────────────────────────────────────────────────
function table(caption, head, rows, totalRow, cls = '') {
  return `<div class="tbl-wrap"><table class="pt ${cls}"><caption>${caption}</caption><thead><tr>${head.map((h, i) => `<th class="${i ? 'num' : ''}">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td class="${i ? 'num' : ''}">${c}</td>`).join('')}</tr>`).join('')}${totalRow ? `<tr class="total">${totalRow.map((c, i) => `<td class="${i ? 'num' : ''}">${c}</td>`).join('')}</tr>` : ''}</tbody></table></div>`;
}
function signed(v, unit = '%', d = 1) { return v == null ? '—' : `<span class="${v > 0 ? 'pos' : v < 0 ? 'neg' : ''}">${v > 0 ? '+' : v < 0 ? '−' : ''}${fmt(Math.abs(v), d)}${unitText(unit)}</span>`; }
const fullBtn = (id, label = T('Full data')) => `<button type="button" class="btn small" data-open="${esc(id)}"><span class="ms-icon" aria-hidden="true">table_view</span>${esc(label)}</button>`;
const ys = (k) => S.V[k].ys;
const prVal = (k, y) => { const a = arr(k, y); return a ? a[S.PR] : null; };

function renderTable2() {
  const lastPop = S.V.population.ys[S.V.population.ys.length - 1], opts = S.V.population.ys;
  if (S.t2.to == null || !opts.includes(S.t2.to)) S.t2.to = lastPop;
  if (!opts.includes(S.t2.from)) S.t2.from = 2020;
  const pr = (y) => prVal('population', y), basis = (y) => (S.V.population.basis || {})[y] || '';
  const cell = (y) => `${fmt(pr(y))}<small class="cellnote">${esc(y)} · ${esc(/census count/.test(basis(y)) ? T('census count') : T('estimate'))}</small>`;
  const sel = (id, v) => `<select id="${id}" aria-label="${esc(id === 't2from' ? T('Start year') : T('End year'))}">${opts.map(y => `<option${y === v ? ' selected' : ''}>${y}</option>`).join('')}</select>`;
  const row = (src, a, b) => [src, cell(a), cell(b), signed(pr(b) - pr(a), '', 0).replace('+', '+'), signed((pr(b) - pr(a)) / pr(a) * 100)];
  const rows = [
    [T('Study (Table 2, as published)'), `${fmt(3725789)}<small class="cellnote">2010 · ${esc(T('census count'))}</small>`, `${fmt(3285694)}<small class="cellnote">2020 · ${esc(T('census count'))}</small>`, fmt(-440095), '-11.8%'],
    row(T('Census counts, both censuses (live)'), 2010, 2020),
    row(T('Census Bureau, {from} to {to} (choose the years)', { from: S.t2.from, to: S.t2.to }), S.t2.from, S.t2.to),
  ];
  $('#table2').innerHTML = `<div class="t2-controls"><span>${esc(T('Compare'))}</span><label for="t2from" class="sr-only">${esc(T('Start year'))}</label>${sel('t2from', S.t2.from)}<span>${esc(T('with'))}</span><label for="t2to" class="sr-only">${esc(T('End year'))}</label>${sel('t2to', S.t2.to)}${fullBtn('population', T('Full data: every year, every municipality'))}</div>` +
    table(`Table 2 · Puerto Rico's population change, U.S. Census Bureau <span class="tag paper">${esc(T('as published'))}</span><span class="tag live">${esc(T('live'))}</span>`, [T('Source'), T('PR population (start)'), T('PR population (end)'), T('Change'), T('% change')], rows);
  $('#t2from').onchange = e => { S.t2.from = +e.target.value; renderTable2(); }; $('#t2to').onchange = e => { S.t2.to = +e.target.value; renderTable2(); };
  const tw = $('#table2').querySelector('.tbl-wrap'); tw.tabIndex = 0; tw.setAttribute('role', 'region'); tw.setAttribute('aria-label', T("Table 2, Puerto Rico's population change, scrollable"));
}
function renderPopTrend() {
  const v = S.V.population, labels = v.ys, data = labels.map(y => prVal('population', y));
  const cfg = { type: 'line', data: { labels, datasets: [{ label: T('Puerto Rico residents'), data, borderColor: '#205D7B', backgroundColor: '#205D7B', tension: .15, pointRadius: labels.map(y => y === 2010 || y === 2020 ? 6 : 3), pointStyle: labels.map(y => y === 2010 || y === 2020 ? 'triangle' : 'circle'), segment: { borderDash: c => c.p0.parsed.x === 9 ? [4, 4] : undefined } }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: t => { const b = (v.basis || {})[labels[t.dataIndex]]; return ` ${fmt(t.raw)} · ${b ? T(b) : ''}`; } } } }, scales: { y: { ticks: { callback: x => (x / 1e6).toFixed(2) + ' M' }, grid: { color: '#f0f0f0' } }, x: { grid: { display: false } } } } };
  if (S.charts.pop) { S.charts.pop.data.labels = labels; S.charts.pop.data.datasets[0].data = data; S.charts.pop.update('none'); } else { const c = $('#popTrend'); c.setAttribute('role', 'img'); c.setAttribute('aria-label', T('Line chart of Puerto Rico resident population by year, 2010 to 2025')); S.charts.pop = new Chart(c, cfg); }
  $('#popBreak').innerHTML = Th('<b>Reading the line.</b> Triangles are the 2010 and 2020 census counts. {note} The dashed segment marks that change of base.', { note: T(S.series.notes.pop_break) });
}
// Table 6 (affordability by age of householder) and Table 7 (owners by age): the published figures and the live version for the selected year
function payment(income) { const pmt = income * .3 / 12, pi = pmt * 430 / 549, r = .05 / 12; return [pmt, pi, pi * (1 - Math.pow(1 + r, -360)) / r]; }
function renderTable6() {
  const t6 = [[T('Puerto Rico avg.'), 21967, 549, 430, 80181], [T('15 – 24 years'), 7826, 196, 153, 28565], [T('25 – 44 years'), 24445, 611, 479, 89226], [T('45 – 64 years'), 26052, 651, 510, 95092], [T('65 years and over'), 18687, 467, 366, 68209]];
  S.STATIC.table6 = { title: `Table 6 · P.R. home ownership affordability ratio, U.S. Census 2021 (${T('as published')})`, source: 'Foundation for Puerto Rico (2023), Table 6; U.S. Census 2021', head: [T('Age range'), T('Median income per age of householder'), T('30% of income for housing'), T('Monthly payment per maximum'), T('Maximum 30-year mortgage')], rows: t6.map(r => [r[0], r[1], r[2], r[3], r[4]]), note: T('Most of the houses available have an asking price of $90,000+; the median value of housing units is $111,800 (study, p. 22).') };
  const live = S.series.tables.t6_income_by_age, years = Object.keys(live).map(Number).sort((a, b) => a - b);
  const want = S.year == null ? years[years.length - 1] : [...years].filter(y => y <= S.year).pop() || years[0], inc = live[want] || [];
  const names = [T('Puerto Rico avg.'), T('15 – 24 years'), T('25 – 44 years'), T('45 – 64 years'), T('65 years and over')];
  const rows = names.map((n, i) => { const p = inc[i] ? payment(inc[i]) : null; return [n, p ? money(inc[i]) : '—', p ? money(p[0]) : '—', p ? money(p[1]) : '—', p ? money(p[2]) : '—']; });
  const hv = prVal('median_home_value', want);
  $('#table6').innerHTML = `<div class="t2-controls">${fullBtn('table6', T('Full table'))}${fullBtn('t6live', T('Full data: every year'))}</div>` +
    table(`Table 6 · P.R. home ownership affordability ratio, U.S. Census 2021 <span class="tag paper">${esc(T('as published'))}</span>`, S.STATIC.table6.head, t6.map(r => [r[0], money(r[1]), money(r[2]), money(r[3]), money(r[4])])) + '<div class="note">' + esc(S.STATIC.table6.note) + '</div>' +
    table(`${esc(T('The same arithmetic with ACS {window} incomes', { window: winText(want) }))} <span class="tag live">${esc(T('live · {window}', { window: winText(want) }))}</span>`, S.STATIC.table6.head, rows) + (hv && inc[0] ? `<div class="note">${Th("Puerto Rico's median home value in ACS {window} is <b>{value}</b> against a maximum affordable mortgage of <b>{loan}</b> for the median household: a ratio of <b>{ratio}×</b>. Same method as the study (30% of income, 78% of that to principal and interest, 30-year loan at a fixed 5%).", { window: winText(want), value: money(hv), loan: money(payment(inc[0])[2]), ratio: fmt(hv / payment(inc[0])[2], 2) })}</div>` : '');
  S.STATIC.t6live = { title: T('Table 6 method, every year: maximum affordable 30-year mortgage by age of householder'), source: 'US Census Bureau ACS 5-year B19049 (median household income by age of householder), Puerto Rico; FPR Table 6 method', head: [T('ACS window'), ...names.map(n => T('{group}: median income', { group: n })), ...names.map(n => T('{group}: maximum mortgage', { group: n }))], rows: years.map(y => [winText(y), ...live[y].map(x => x), ...live[y].map(x => x ? Math.round(payment(x)[2]) : null)]), note: T("Maximum mortgage: 30% of income for housing, 78% of that to principal and interest, 30-year loan at a fixed 5% (the study's method).") };
}
function renderTable7() {
  const bins = [T('Under 35'), '35–44', '45–54', '55–64', '65–74', '75–84', '85+'], pub = [10.7, 16.4, 18.5, 22.1, 19.5, 9.6, 3.2];
  const live = S.series.tables.t7_owner_age, years = Object.keys(live).map(Number).sort((a, b) => a - b);
  const want = S.year == null ? years[years.length - 1] : [...years].filter(y => y <= S.year).pop() || years[0], data = live[want];
  S.STATIC.table7 = { title: `Table 7 · Owner-occupied units by age of householder (${T('as published and live')})`, source: 'Foundation for Puerto Rico (2023), Table 7; US Census Bureau ACS 5-year B25007', head: [T('Age of householder'), T('Study, % of owner-occupied units'), ...years.map(y => `ACS ${winText(y)}, %`)], rows: bins.map((b, i) => [b, pub[i], ...years.map(y => live[y][i])]), note: T('Owner-occupied units by age of the householder, as a share of all owner-occupied units in Puerto Rico.') };
  const ds = [{ label: T('Study (Table 7)'), data: pub, backgroundColor: '#FFC83C', borderRadius: 4 }, { label: `ACS ${winText(want)}`, data, backgroundColor: RAMP[3], borderRadius: 4 }];
  if (S.charts.t7) { S.charts.t7.data.datasets = ds; S.charts.t7.update('none'); }
  else { const c = $('#table7'); c.setAttribute('role', 'img'); c.setAttribute('aria-label', T('Owner-occupied units by age of householder, as published in Table 7 and from the latest ACS')); S.charts.t7 = new Chart(c, { type: 'bar', data: { labels: bins, datasets: ds }, options: { plugins: { tooltip: { callbacks: { label: t => ` ${T('{label}: {value}% of owner-occupied units', { label: t.dataset.label, value: t.raw })}` } } }, scales: { y: { ticks: { callback: v => v + '%' }, grid: { color: '#f0f0f0' } } } } }); }
}
const BURDEN_BUCKETS = ['< 10%', '10–14.9%', '15–19.9%', '20–24.9%', '25–29.9%', '30–34.9%', '35–39.9%', '40–49.9%', '50%+'];
function renderBurdenCharts() {
  [['grapi', '#grapi', T('renter households'), T('Renters'), '52%'], ['smocapi', '#smocapi', T('owner households with a mortgage'), T('Owners with a mortgage'), '38%']].forEach(([tk, id, who, label, study]) => {
    const live = S.series.tables[tk], years = Object.keys(live).map(Number).sort((a, b) => a - b), want = S.year == null ? years[years.length - 1] : [...years].filter(y => y <= S.year).pop() || years[0], data = live[want];
    S.STATIC[tk + 'live'] = { title: T('{label}: share of households by cost as a % of income, every year', { label }), source: `US Census Bureau ACS 5-year ${tk === 'grapi' ? 'B25070' : 'B25091'}, Puerto Rico`, head: [T('ACS window'), ...BURDEN_BUCKETS.map(b => T('{bucket} of income', { bucket: b }))], rows: years.map(y => [winText(y), ...live[y]]), note: T('Percent of households; the last four classes (30% and above) are the cost-burdened.') };
    const colors = BURDEN_BUCKETS.map((b, i) => i >= 5 ? '#B82415' : RAMP[3]);
    if (S.charts[tk]) { S.charts[tk].data.datasets[0].data = data; S.charts[tk].update('none'); }
    else { const c = $(id); c.setAttribute('role', 'img'); c.setAttribute('aria-label', T('{label}: share of households by cost as a share of income, island-wide', { label })); S.charts[tk] = new Chart(c, { type: 'bar', data: { labels: BURDEN_BUCKETS, datasets: [{ label, data, backgroundColor: colors, borderRadius: 4 }] }, options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: t => ` ${T('{pct}% of households', { pct: fmt(t.raw, 1) })}` } } }, scales: { y: { ticks: { callback: v => v + '%' }, grid: { color: '#f0f0f0' } } } } }); }
    const burdened = data.slice(5).reduce((x, y) => x + y, 0), el = $(id).closest('.card'); let n = el.querySelector('.note.live'); if (!n) { n = document.createElement('div'); n.className = 'note live'; el.appendChild(n); }
    n.innerHTML = Th('<b>{pct}%</b> of {who} pay 30% or more of income (red bars), ACS {window}. Study: {study}.', { pct: fmt(burdened, 1), who, window: winText(want), study });
  });
}
function renderScatter() {
  const inc = at('median_hh_income'), val = at('median_home_value'), ar = at('affordability_ratio');
  const idx = [...Array(S.PR).keys()].filter(i => inc.a && val.a && inc.a[i] && val.a[i]);
  const pts = idx.map(i => ({ x: inc.a[i], y: val.a[i], n: S.NM[i], r: ar.a && ar.a[i] }));
  const loanFor = i => payment(i)[2], maxI = Math.max(...pts.map(p => p.x), 1);
  const data = { datasets: [
    { type: 'scatter', label: T('Municipality'), data: pts, backgroundColor: pts.map(p => p.r > 1 ? '#B82415' : '#79901E'), pointRadius: 5 },
    { type: 'line', label: T('Affordability limit (value = max loan)'), data: [{ x: 0, y: 0 }, { x: maxI * 1.05, y: loanFor(maxI * 1.05) }], borderColor: '#2A2E2E', borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0 },
  ] };
  $('#scatterYear').textContent = `ACS ${winText(inc.y)}`;
  if (S.charts.scatter) { S.charts.scatter.data = data; S.charts.scatter.update('none'); return; }
  const sc = $('#scatter'); sc.setAttribute('role', 'img'); sc.setAttribute('aria-label', T('Scatter of median household income against median home value for each municipality; red dots are above the affordability line, green dots below.'));
  S.charts.scatter = new Chart(sc, { data, options: { animation: false, plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8, generateLabels: () => [{ text: T('Out of reach: home value above the maximum loan'), fillStyle: '#B82415', strokeStyle: '#B82415', pointStyle: 'circle', hidden: false }, { text: T('Within reach'), fillStyle: '#79901E', strokeStyle: '#79901E', pointStyle: 'circle', hidden: false }, { text: T('Limit: value equals maximum loan'), fillStyle: '#2A2E2E', strokeStyle: '#2A2E2E', pointStyle: 'line', hidden: false }] } }, tooltip: { callbacks: { label: t => t.raw.n ? ` ${T('{name}: income {income}, home value {value}, ratio {ratio}×', { name: t.raw.n, income: money(t.raw.x), value: money(t.raw.y), ratio: fmt(t.raw.r, 2) })}` : '' } } }, scales: { x: { title: { display: true, text: T('Median household income') }, ticks: { callback: v => money(v) }, grid: { color: '#f0f0f0' } }, y: { title: { display: true, text: T('Median home value') }, ticks: { callback: v => money(v) }, grid: { color: '#f0f0f0' } } }, onClick: (e, items) => { const it = items[0]; if (it && it.datasetIndex === 0) selectMuni(S.charts.scatter.data.datasets[0].data[it.index].n); } } });
}
function renderPaperTables() {
  const p = S.paper, h = p.headline || {};
  $('#headlineKpis').innerHTML = [
    [fmt(h.housing_units_2020 / 1e6, 1) + ' M', T('housing units'), T('Census 2020 · study p.14')],
    [fmt(h.vacant_homes_2020), T('vacant homes'), T('Census 2020 · study p.14')],
    [fmt(h.abandoned_estimate), T('dilapidated or abandoned units (estimate)'), T('study p.14')],
    [fmt(h.annual_new_housing_deficit), T('new homes needed per year (government estimate)'), T('study · regulation brief 2024')],
    [fmt(3285694), T('residents, 2020 census'), T('study Table 2')],
  ].map(([v, l, s]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${esc(l)}</div><div class="s">${esc(s)}</div></div>`).join('');
  S.STATIC.table2study = null;
  [['#table7', T('Owner-occupied units by age of householder, Table 7')]].forEach(([id, t]) => { const c = $(id); if (c) { c.setAttribute('role', 'img'); c.setAttribute('aria-label', t); } });
  const li = p.lihtc || [];
  S.STATIC.table10 = { title: `Table 10 · LIHTC projects funded with CDBG-DR (${T('as published')})`, source: 'Foundation for Puerto Rico (2023), Table 10', head: [T('Project'), T('Location'), T('Type'), T('Units'), T('Beneficiaries'), T('Est. development cost'), T('Est. CDBG-DR grant')], rows: li.map(r => [r.name, r.municipality, T(r.type), r.units, T(r.beneficiaries), r.cost, r.cdbg_dr]), note: T('As published. Locations are shown at the municipality.') };
  $('#table10').innerHTML = table('', [T('Project'), T('Location'), T('Type'), T('Units'), T('Beneficiaries'), T('Est. development cost'), T('Est. CDBG-DR grant')], li.map(r => [esc(r.name), `<a href="#profile" data-m="${esc(r.municipality)}">${esc(r.municipality)}</a>`, esc(T(r.type)), fmt(r.units), esc(T(r.beneficiaries)), money(r.cost), money(r.cdbg_dr)]), [T('Total'), '', '', fmt(li.reduce((a, r) => a + r.units, 0)), '', money(li.reduce((a, r) => a + r.cost, 0)), money(li.reduce((a, r) => a + r.cdbg_dr, 0))]);
  $('#table10').querySelectorAll('a[data-m]').forEach(a => a.onclick = () => selectMuni(a.dataset.m));
  const lm = miniMap($('#lihtcMap'));
  L.geoJSON(S.fc, { style: { color: '#fff', weight: .7, fillColor: '#E6E6E6', fillOpacity: .9 }, interactive: false }).addTo(lm);
  const centers = {}; L.geoJSON(S.fc, { onEachFeature: (f, l) => centers[f.properties.municipality] = l.getBounds().getCenter() });
  const byM = {}; li.forEach(r => (byM[r.municipality] = byM[r.municipality] || []).push(r));
  Object.entries(byM).forEach(([m, rs]) => { const c = centers[m]; if (!c) return; const units = rs.reduce((a, r) => a + r.units, 0); L.circleMarker(c, { radius: 8 + Math.sqrt(units) / 2, color: '#fff', weight: 2, fillColor: '#FF4D38', fillOpacity: .85 }).bindTooltip(Th('<b>{name}</b> · {n} LIHTC units<br>{projects}', { name: m, n: fmt(units), projects: I18N.raw(rs.map(r => esc(r.name)).join('<br>')) })).addTo(lm).on('click', () => selectMuni(m)); });
  lm.fitBounds(L.geoJSON(S.fc).getBounds());
}

// ── Headline numbers for the latest data ───────────────────────────────────
function renderLatestKpis() {
  const items = [
    ['population', T('residents'), (y) => T('{basis} {year}', { basis: T(S.V.population.basis[y] ? S.V.population.basis[y].replace(/ \(.*/, '') : 'estimate'), year: y })],
    ['pop_change_since_2020_pct', T('change since the 2020 census'), (y) => T('to {year}', { year: y }), '%'],
    ['housing_units', T('housing units'), (y) => `ACS ${winText(y)}`],
    ['vacancy_pct', T('of homes vacant'), (y) => `ACS ${winText(y)}`],
    ['other_vacant_pct', T("'other vacant' homes (abandoned-housing proxy)"), (y) => `ACS ${winText(y)}`],
    ['median_home_value', T('median home value'), (y) => `ACS ${winText(y)}`],
    ['renter_cost_burden_pct', T('of renters pay 30%+ of income on rent'), (y) => `ACS ${winText(y)}`],
    ['affordability_ratio', T('affordability ratio (above 1 = out of reach)'), (y) => `ACS ${winText(y)}`],
  ];
  $('#latestKpis').innerHTML = items.map(([k, label, sub]) => { const { y, a } = at(k); const v = a ? a[S.PR] : null; return `<button type="button" class="kpi kpi-btn" data-open="${k}" aria-label="${esc(T('{label}: open the full data', { label: T(S.V[k].label) }))}"><div class="v">${v == null ? '—' : k === 'population' || k === 'housing_units' ? fmt(v) : fv(k, v)}</div><div class="l">${esc(label)}</div><div class="s">${y == null ? '' : esc(sub(y))} · ${esc(T('open full data'))}</div></button>`; }).join('');
}
function renderLedes() {
  const p0 = prVal('population', 2010), p20 = prVal('population', 2020), lp = S.V.population.ys[S.V.population.ys.length - 1], pl = prVal('population', lp);
  $('#popLede').innerHTML = esc(T("The study opens with depopulation: Puerto Rico lost more than a tenth of its residents between the 2010 and 2020 censuses (Table 2, Map 1): {p0} to {p20}, {change}%. The Census Bureau's population estimates show the loss continuing since: {pl} residents on July 1, {year}, {below}% below the 2020 count. Use the year bar above to move every map and chart, and open any table or map's full data for every year and municipality.", { p0: fmt(p0), p20: fmt(p20), change: fmt((p20 - p0) / p0 * 100, 1), pl: fmt(pl), year: lp, below: fmt((pl - p20) / p20 * 100, 1) }));
}

// ── Municipality profile (Table 11 for any municipality), for the selected year ──
const SPARK_W = 78, SPARK_H = 18;
function spark(k, i) {
  const v = S.V[k]; if (!v || v.static || v.ys.length < 2) return ['', ''];
  const pts = v.ys.map(y => [y, (arr(k, y) || [])[i]]).filter(p => p[1] != null); if (pts.length < 2) return ['', ''];
  const x0 = pts[0][0], x1 = pts[pts.length - 1][0], vs = pts.map(p => p[1]), lo = Math.min(...vs), hi = Math.max(...vs), cur = at(k).y;
  const X = y => (y - x0) / (x1 - x0 || 1) * (SPARK_W - 4) + 2, Y = n => SPARK_H - 2 - (hi === lo ? .5 : (n - lo) / (hi - lo)) * (SPARK_H - 4);
  const dot = pts.find(p => p[0] === cur);
  const span = x1 - x0 + 1;
  return [`<svg class="spark" width="${SPARK_W}" height="${SPARK_H}" viewBox="0 0 ${SPARK_W} ${SPARK_H}" role="img" aria-label="${esc(T('Trend from {from} to {to}: {n} yearly values', { from: x0, to: x1, n: pts.length }))}"><title>${esc(T('{from} to {to}', { from: x0, to: x1 }))}</title><polyline fill="none" stroke="#8C8E8E" stroke-width="1.3" points="${pts.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ')}"/>${dot ? `<circle cx="${X(dot[0]).toFixed(1)}" cy="${Y(dot[1]).toFixed(1)}" r="2.6" fill="#205D7B"/>` : ''}</svg>`, `<small class="spark-cap">${esc(T('{n} yrs', { n: span }))}${pts.length < span ? `, ${esc(T('{n} values', { n: pts.length }))}` : ''}</small>`];
}
function selectMuni(name) {
  S.selected = name; $('#muniPick').value = name;
  const i = idxOf(name); if (i < 0) return;
  const m = S.muni[name] || {};
  const row = (k, label, opts = {}) => {
    const v = S.V[k]; if (!v) return '';
    const { y, a, exact } = at(k), val = a ? a[i] : null, mo = moeArr(k, y), rk = opts.rank === false ? '' : rankOf(k, name, a, true);
    const m = mo && mo[i], hasM = !opts.fmt && !(v.synthetic && v.unit.trim()) && val != null && m != null;
    const shown = opts.fmt ? opts.fmt(val) : (v.synthetic && v.unit.trim() ? signed(val, v.unit) : hasM ? fv(k, val) : fm(k, val, null));
    const note = !exact && y != null ? `<span class="yr-note-inline">${y}</span>` : '';
    const [line, cap] = spark(k, i), side = [hasM ? `<span class="moe">±${v.unit === '$' ? money(m) : fmt(m, v.d)}${v.unit === '%' ? ' ' + T('pts') : ''}</span>` : '', opts.side ? opts.side(val) : '', note].filter(Boolean).join(' ');
    return `<div class="kv-l"><button type="button" class="linklike" data-open="${esc(k)}" title="${esc(T('Open the full data'))}">${esc(label || titleOf(k, y))}</button>${rk ? ` <span class="rank" title="${esc(T('Rank among the 78 municipalities, highest first'))}">${esc(rk)}</span>` : ''}</div>`
      + `<div class="kv-v">${shown}${side ? `<div class="kv-vm">${side}</div>` : ''}</div><div class="kv-m">${side}</div><div class="kv-s">${line}${cap ? `<div class="kv-cs">${cap}</div>` : ''}</div><div class="kv-c">${cap}</div>`;   // the years: their own column, or under the line on a phone (one of the two is shown)
  };
  const plain = (label, value, side = '') => `<div class="kv-l">${esc(label)}</div><div class="kv-v">${value}${side ? `<div class="kv-vm">${side}</div>` : ''}</div><div class="kv-m">${side}</div><div class="kv-s"></div><div class="kv-c"></div>`;   // a figure with no margin or trend, in the same columns
  const sec = (t) => `<div class="sec">${esc(t)}</div>`;
  const ly = resolve('median_home_value').y, py = resolve('population').y;
  const popSmall = (prVal && (arr('population', py) || [])[i] < 25000);
  $('#profileCard').innerHTML = `<div class="profile">
    <div class="card"><h3>${esc(name)}<small>${esc(m.region || '')} · ${esc(T('Table 11 variables, {year}', { year: S.year == null ? T('latest data') : S.year }))}</small></h3>${popSmall ? `<div class="note caution">${esc(T('Small municipality: ACS five-year estimates can be imprecise here. The margin of error (±) is shown beside each estimate; treat small differences as noise.'))}</div>` : ''}<div class="kv">
      ${sec(T('People'))}${row('population', T('Population'))}${row('pop_change_since_2010_pct', T('Change since the 2010 census'))}${row('age65_pct', T('Aged 65 and over'))}${row('median_age', T('Median age'))}
      ${row('median_hh_income', T('Median household income'))}${row('bachelors_pct', T("Adults 25+ with bachelor's or higher"))}${row('employment_rate_pct', T('Employment rate (16+)'))}${row('poverty_pct', T('Population below poverty level'))}
      ${sec(T('Tourism supply (Data Observatory)'))}${plain(T('Tourism places'), fmt(m.assets))}${plain(T('In FEMA flood hazard area'), `${fmt(m.sfha_pct, 1)}%`)}${m.acc_walk400_pct != null ? plain(T('Within a 400 m walk of a stop with a current timetable'), `${fmt(m.acc_walk400_pct, 1)}%`) : m.acc_cur400_pct != null ? plain(T('Within 400 m of a stop with a current timetable'), `${fmt(m.acc_cur400_pct, 1)}%`) : ''}${plain(T('Within 400 m of any mapped stop'), `${fmt(m.transit_pct, 1)}%`)}
    </div></div>
    <div class="card"><h3>${esc(T('Housing indicators'))}<small>${esc(T('Study tables extended to {name}, with the trend 2010–{year} beside each value', { name, year: latestYear() }))}</small></h3><div class="kv">
      ${sec(T('Stock'))}${row('housing_units', T('Housing units'))}${row('vacancy_pct', T('Vacant units'))}${row('seasonal_pct', T('Seasonal / recreational units'))}${row('other_vacant_pct', T("'Other vacant' units (abandoned proxy)"))}${row('rental_vacancy_pct', T('Rental vacancy rate'))}${row('overcrowded_pct', T('Overcrowded homes'))}${row('residents_per_unit', T('Residents per unit (census)'))}
      ${sec(T('Prices and burden'))}${row('median_home_value', T('Median home value'))}${row('median_gross_rent', T('Median gross rent'))}${row('renter_cost_burden_pct', T('Cost-burdened renters'))}${row('renter_severe_burden_pct', T('Severely cost-burdened renters (50%+)'))}${row('owner_cost_burden_pct', T('Cost-burdened owners (mortgage)'))}
      ${sec(T('Affordability (Table 6 method)'))}${row('max_affordable_loan', T('Max affordable 30-year loan'), { rank: false })}${row('affordability_ratio', T('Affordability ratio'), { fmt: v => v == null ? '—' : `<b>${fmt(v, 2)}×</b>`, side: v => v == null ? '' : Math.round(v * 100) / 100 > 1 ? `<span class="neg">${esc(T('out of reach'))}</span>` : `<span class="pos">${esc(T('within reach'))}</span>` })}${row('owner_occupied_pct', T('Owner-occupied share'))}
      ${sec(T('Change {from} → {to}', { from: S.base, to: resolve('median_home_value').y ?? '' }))}${row('gross_rent_change_pct', T('Median gross rent'))}${row('home_value_change_pct', T('Median home value'))}${row('income_change_pct', T('Median income'))}${row('bachelors_change_pts', T("Bachelor's+ share"))}
      ${sec(T('Disaster recovery'))}${row('fema_ia_households', T('FEMA housing assistance, households'), { rank: false, fmt: () => fmt(S.V.fema_ia_households.ys.reduce((s, y) => s + ((arr('fema_ia_households', y) || [])[i] || 0), 0)), side: () => `<span class="yr-note-inline">${esc(T('all disasters'))}</span>` })}
      ${sec(T('Land use (PUT 2015)'))}${plain(T('Urban land'), `${fmt(m.urban_pct, 0)}%`)}${plain(T('Land for urban growth'), `${fmt(m.urbanizable_pct, 0)}%`)}${plain(T('Specially protected rural land'), `${fmt(m.protected_land_pct, 0)}%`)}${plain(T('Tourism places on protected rural land'), fmt(m.places_on_protected_land), `<span class="yr-note-inline">${esc(T('{pct}% of its places', { pct: fmt(m.places_on_protected_land_pct, 0) }))}</span>`)}
    </div><div class="btn-row"><a class="btn" href="index.html#${encodeURIComponent(name)}"><span class="ms-icon" aria-hidden="true">map</span>${esc(T('Open in the Data Observatory'))}</a></div></div>
  </div>`;
  S.vizzes.forEach(el => { el._viz.layer.eachLayer(f => f.setStyle(selStyle(f.feature))); el._viz.layer.eachLayer(f => f.feature.properties.municipality === name && f.bringToFront()); updateReadout(el); });
  if (!S.booting) writeUrl();
}
const prVal2 = null;

// ── Full data: every dataset opens in a dialog with all years, all municipalities, margins of error and CSV ──
const DS = { key: null, sort: { col: 'name', dir: 1 }, find: '', moe: false, picks: new Set(), chart: null, opener: null };
function csvCell(v) { if (v == null) return ''; let s = String(v); if (/^[=+\-@\t\r]/.test(s) && typeof v !== 'number') s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }
function saveCsv(name, header, rows) {
  const csv = '﻿' + [header, ...rows].map(r => r.map(csvCell).join(',')).join('\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 60);
function dsMeta(v) {
  const src = S.series.sources[v.kind === 'derived' ? 'derived' : v.kind === 'acs' ? 'acs' : v.kind] || {};
  const parts = [`<b>${esc(T('Source:'))}</b> ${src.url ? `<a href="${esc(src.url)}" target="_blank" rel="noopener">${esc(src.name || v.ref)}</a>` : esc(v.ref || 'Plan de Uso de Terrenos 2015, Junta de Planificación')}`, `<b>${esc(T('Table:'))}</b> ${esc(v.ref)}`];
  if (v.kind === 'acs' || v.kind === 'derived') parts.push(Th('<b>Years:</b> each column is a five-year ACS window labelled by its last year (2024 = 2020–2024); neighbouring windows share four of five years, so compare windows that do not overlap (2012, 2017, 2022) for real change.'));
  if (v.kind === 'pop') parts.push(Th('<b>Basis:</b> {note}', { note: T(S.series.notes.pop_break) }));
  if (v.kind === 'fema') { const nt = S.series.notes.fema || {}; parts.push(Th('<b>Disasters:</b> {list}', { list: Object.keys(nt).sort().map(y => `${y}: ${[...new Set(Object.values(nt[y]))].join(', ')}`).join('; ') })); }
  if (v.moe) parts.push(Core.reliability.moeKey());
  parts.push(Th('<b>Full entry:</b> <a href="dictionary.html#housing.{key}">meaning, method, cautions and how to cite in the data dictionary</a>', { key: v.key }));
  return `<div class="ds-def">${I18N.en(esc(v.definition))}</div><div class="ds-meta">${parts.map(p => `<div>${p}</div>`).join('')}</div>`;
}
function dsRows() {
  const v = S.V[DS.key], years = v.ys, sel = resolve(DS.key).y;
  let rows = S.NM.map((n, i) => ({ i, n, vals: years.map(y => (arr(DS.key, y) || [])[i]), moes: years.map(y => { const m = moeArr(DS.key, y); return m ? m[i] : null; }) }));
  const pr = rows.pop();
  if (DS.find) rows = rows.filter(r => norm(r.n).includes(norm(DS.find)));
  const { col, dir } = DS.sort, ci = years.indexOf(col);
  rows.sort((a, b) => col === 'name' ? dir * a.n.localeCompare(b.n, 'es') : ((a.vals[ci] == null) - (b.vals[ci] == null)) || dir * ((a.vals[ci] ?? 0) - (b.vals[ci] ?? 0)));
  return { rows: [pr, ...rows], years, sel };
}
function renderDsTable() {
  const v = S.V[DS.key], { rows, years, sel } = dsRows(), d = DS.sort;
  const th = (label, col, num) => `<th scope="col" class="${num ? 'num' : ''} ${col === sel ? 'cur' : ''}" aria-sort="${d.col === col ? (d.dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" class="sortbtn2" data-col="${col}">${label}${d.col === col ? (d.dir > 0 ? ' ▲' : ' ▼') : ''}</button></th>`;
  const cell = (r, j) => { const val = r.vals[j]; if (val == null) return '<td class="num na">—</td>'; const m = r.moes[j], bad = Core.reliability.isUnreliable(val, m); return `<td class="num ${years[j] === sel ? 'cur' : ''} ${bad ? 'unrel' : ''}">${fv(DS.key, val)}${DS.moe && m != null ? ` <span class="moe">±${v.unit === '$' ? money(m) : fmt(m, v.d)}</span>` : ''}${bad ? ` <span class="sr-only">(${esc(Core.reliability.lessReliable())})</span>` : ''}</td>`; };
  const head = `<tr><th scope="col" class="pick">${esc(T('Trend'))}</th>${th(esc(T('Municipality')), 'name')}${years.map(y => th(v.static ? '2015' : S.V[DS.key].kind === 'acs' || S.V[DS.key].kind === 'derived' ? `${y}<small>${winText(y)}</small>` : String(y), y, true)).join('')}</tr>`;
  $('#dsTable').innerHTML = `<table class="pt ds"><thead>${head}</thead><tbody>${rows.map(r => `<tr class="${r.i === S.PR ? 'total' : ''} ${S.NM[r.i] === S.selected ? 'me' : ''}"><td class="pick"><input type="checkbox" data-i="${r.i}" aria-label="${esc(T('Show {name} in the trend chart', { name: r.n }))}" ${DS.picks.has(r.i) ? 'checked' : ''}></td><th scope="row">${esc(r.n)}</th>${years.map((y, j) => cell(r, j)).join('')}</tr>`).join('')}</tbody></table>`;
  $('#dsCount').textContent = `${DS.find ? T('{n} of 78 municipalities match', { n: rows.length - 1 }) : T('{n} of 78 municipalities', { n: rows.length - 1 })} · ${Tn(years.length, '{n} year', '{n} years')}`;
}
function renderDsChart() {
  const v = S.V[DS.key], years = v.ys, wrap = $('#dsChartWrap');
  if (years.length < 2) { wrap.hidden = true; return; } wrap.hidden = false;
  const picks = [...DS.picks].sort((a, b) => a - b), color = (n) => LINES[n % LINES.length];
  const ds = picks.map((i, n) => ({ label: S.NM[i], data: years.map(y => (arr(DS.key, y) || [])[i] ?? null), borderColor: color(n), backgroundColor: color(n), borderWidth: i === S.PR ? 3 : 2, pointRadius: years.length < 6 ? 4 : 2.5, spanGaps: true, tension: .1 }));
  if (DS.chart) { DS.chart.data.labels = years; DS.chart.data.datasets = ds; DS.chart.update('none'); return; }
  const c = $('#dsChart'); c.setAttribute('role', 'img'); c.setAttribute('aria-label', T('Trend of the selected municipalities over the years'));
  DS.chart = new Chart(c, { type: 'line', data: { labels: years, datasets: ds }, options: { maintainAspectRatio: false, animation: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } }, tooltip: { callbacks: { label: t => ` ${t.dataset.label}: ${fv(DS.key, t.raw)}` } } }, scales: { y: { ticks: { callback: x => fv(DS.key, x) }, grid: { color: '#f0f0f0' } }, x: { grid: { display: false } } } } });
}
function dsCsv() {
  const v = S.V[DS.key], years = v.ys, hasMoe = !!v.moe, header = ['GEOID', T('Municipality'), ...years.flatMap(y => hasMoe ? [`${y}`, T('{year} margin of error', { year: y })] : [`${y}`])];
  const rows = S.NM.map((n, i) => [i === S.PR ? '72' : S.series.geo.ids[i], n, ...years.flatMap(y => { const a = arr(DS.key, y), m = moeArr(DS.key, y); return hasMoe ? [a ? a[i] : null, m ? m[i] : null] : [a ? a[i] : null]; })]);
  saveCsv(`pr_housing_${slug(v.key)}.csv`, header, rows);
}
function openDataset(key, opener) {
  const v = S.V[key]; if (!v) return;
  Object.assign(DS, { key, sort: { col: 'name', dir: 1 }, find: '', moe: false, opener: opener || document.activeElement });
  DS.picks = new Set([S.PR, idxOf(S.selected)].filter(i => i >= 0));
  if (DS.chart) { DS.chart.destroy(); DS.chart = null; }
  const title = titleOf(key, resolve(key).y);
  $('#dlgTitle').textContent = title;
  $('#dlgBody').innerHTML = `<div class="ds-tags"><span class="tag paper">${esc(v.ref)}</span><span class="tag live">${esc(T(v.group))}</span></div>${dsMeta(v)}
    <div class="ds-tools"><label class="ds-find">${esc(T('Find a municipality'))} <input type="search" id="dsFind" placeholder="${esc(T('Type a name'))}" autocomplete="off"></label>${v.moe ? `<label class="ds-check"><input type="checkbox" id="dsMoe"> ${esc(T('Show margin of error (±)'))}</label>` : ''}<span id="dsCount" class="ds-count" aria-live="polite"></span><button type="button" class="btn" id="dsCsv"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download CSV'))}</button></div>
    <div id="dsChartWrap" class="ds-chart"><canvas id="dsChart"></canvas></div>
    <div class="ds-hint">${esc(T('Tick municipalities in the first column to draw their trend. Click a column heading to sort.'))}</div>
    <div class="ds-table" id="dsTable" tabindex="0" role="region" aria-label="${esc(T('{title}: full data, scrollable', { title }))}"></div>`;
  $('#dsFind').oninput = e => { DS.find = e.target.value; renderDsTable(); };
  const mo = $('#dsMoe'); if (mo) mo.onchange = e => { DS.moe = e.target.checked; renderDsTable(); };
  $('#dsCsv').onclick = dsCsv;
  $('#dsTable').onclick = e => { const b = e.target.closest('.sortbtn2'); if (b) { const col = b.dataset.col === 'name' ? 'name' : +b.dataset.col; DS.sort = DS.sort.col === col ? { col, dir: -DS.sort.dir } : { col, dir: col === 'name' ? 1 : -1 }; renderDsTable(); } };
  $('#dsTable').onchange = e => { const c = e.target.closest('input[type=checkbox][data-i]'); if (!c) return; const i = +c.dataset.i; if (c.checked) { if (DS.picks.size >= 8) { c.checked = false; toastMsg(T('Up to 8 lines at a time.')); return; } DS.picks.add(i); } else DS.picks.delete(i); renderDsChart(); };
  renderDsTable(); renderDsChart();
  $('#dataDlg').dataset.mode = 'dataset'; showDialog();
  if (history.replaceState) { const u = new URL(location.href); u.searchParams.set('d', key); history.replaceState(null, '', u); }
}
// published tables (and the live tables built from them) open the same dialog
function openStatic(id, opener) {
  const t = S.STATIC[id]; if (!t) return;
  DS.opener = opener || document.activeElement; DS.key = null;
  if (DS.chart) { DS.chart.destroy(); DS.chart = null; }
  $('#dlgTitle').textContent = t.title;
  $('#dlgBody').innerHTML = `<div class="ds-meta"><div><b>${esc(T('Source:'))}</b> ${esc(t.source)}</div></div><div class="ds-tools"><span class="ds-count">${esc(Tn(t.rows.length, '{n} row', '{n} rows'))}</span><button type="button" class="btn" id="dsCsv"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download CSV'))}</button></div>
    <div class="ds-table" tabindex="0" role="region" aria-label="${esc(T('{title}, scrollable', { title: t.title }))}"><table class="pt ds"><thead><tr>${t.head.map((h, i) => `<th scope="col" class="${i ? 'num' : ''}">${esc(h)}</th>`).join('')}</tr></thead><tbody>${t.rows.map(r => `<tr>${r.map((c, i) => `<td class="${i ? 'num' : ''}">${c == null ? '—' : typeof c === 'number' ? (c > 1000 ? fmt(c) : c) : esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${t.note ? `<div class="note">${esc(t.note)}</div>` : ''}`;
  $('#dsCsv').onclick = () => saveCsv(`pr_housing_${slug(id)}.csv`, t.head, t.rows);
  $('#dataDlg').dataset.mode = 'static'; showDialog();
}
function showDialog() { const d = $('#dataDlg'); if (!d.open) d.showModal(); $('#dlgBody').scrollTop = 0; }
function toastMsg(m) { const n = $('#dsCount'); if (n) { n.textContent = m; setTimeout(renderDsTable, 2200); } }
function initDialog() {
  const d = $('#dataDlg');
  $('#dlgClose').onclick = () => d.close();
  d.addEventListener('click', e => { if (e.target === d) d.close(); });   // a click on the backdrop
  d.addEventListener('close', () => { if (DS.chart) { DS.chart.destroy(); DS.chart = null; } const u = new URL(location.href); if (u.searchParams.has('d')) { u.searchParams.delete('d'); history.replaceState(null, '', u); } if (DS.opener && document.contains(DS.opener) && DS.opener.focus) DS.opener.focus({ preventScroll: true }); });
  document.addEventListener('click', e => { const b = e.target.closest('[data-open]'); if (!b) return; e.preventDefault(); const id = b.dataset.open; S.V[id] ? openDataset(id, b) : openStatic(id, b); });
}

// ── Data catalog: every dataset on the page, each one opens in full ────────
function renderCatalog() {
  const groups = {};
  Object.values(S.V).filter(v => !v.synthetic).forEach(v => (groups[v.group] = groups[v.group] || []).push(v));
  const order = ['Population', 'Housing stock', 'Households', 'Prices and incomes', 'Cost burden', 'Affordability', 'Disaster recovery', 'Land use'];
  const stat = [['table2', T('Population change (Table 2): every year')], ['table6', T('Table 6 as published')], ['t6live', T('Table 6 method, every ACS window')], ['table7', T('Table 7 (owners by age), published and live')], ['table10', T('Table 10 (LIHTC projects), as published')], ['grapilive', T('Gross rent as a share of income, every ACS window')], ['smocapilive', T('Owner costs as a share of income, every ACS window')]];
  const years = (v) => v.static ? '2015' : v.ys.length > 3 ? T('{from}–{to} ({n} years)', { from: v.ys[0], to: v.ys[v.ys.length - 1], n: v.ys.length }) : v.ys.join(', ');
  $('#catalogList').innerHTML = order.filter(g => groups[g]).map(g => `<h3 class="cat-h">${esc(T(g))}</h3><div class="cat-grid">${groups[g].map(v => `<div class="cat-item" data-find="${esc(norm(T(v.label) + ' ' + v.ref + ' ' + T(v.group)))}"><button type="button" class="linklike" data-open="${esc(v.key)}">${esc(T(v.label))}</button><span class="cat-src">${esc(v.ref)} · ${esc(years(v))}${v.moe ? ` · ${esc(T('with margins of error'))}` : ''}</span></div>`).join('')}</div>`).join('') +
    `<h3 class="cat-h">${esc(T('Published tables and island-wide series'))}</h3><div class="cat-grid">${stat.map(([id, label]) => `<div class="cat-item" data-find="${esc(norm(label))}"><button type="button" class="linklike" data-open="${id === 'table2' ? 'population' : id}">${esc(label)}</button><span class="cat-src">${esc(id === 'table2' ? T('Census Bureau counts and estimates') : T('FPR 2023 study / Census Bureau ACS'))}</span></div>`).join('')}</div>`;
  $('#catFind').oninput = e => { const q = norm(e.target.value); let n = 0; document.querySelectorAll('.cat-item').forEach(it => { const show = !q || it.dataset.find.includes(q); it.hidden = !show; if (show) n++; }); $('#catCount').textContent = Tn(n, '{n} dataset', '{n} datasets'); };
  $('#catCount').textContent = Tn(document.querySelectorAll('.cat-item').length, '{n} dataset', '{n} datasets');
}

// ── Year bar ───────────────────────────────────────────────────────────────
let playTimer = null;
function setYear(y, { fromUi = false } = {}) {
  S.year = y == null || y === 'latest' ? null : +y;
  $('#yearSel').value = S.year == null ? 'latest' : String(S.year);
  $('#yearRange').value = S.year == null ? $('#yearRange').max : S.year;
  const ly = latestYear();
  $('#yearNote').textContent = S.year == null ? T('Latest available for each dataset (population {pop}, ACS {window}).', { pop: S.series.latest.pop, window: winText(S.series.latest.acs) }) : S.year > S.series.latest.acs ? T("ACS five-year estimates for {from}–{to} are not published yet; the maps show {window} for ACS data. Population is the Census Bureau's {year} estimate.", { from: S.year - 4, to: S.year, window: winText(S.series.latest.acs), year: S.year }) : T('Showing {year}: ACS window {window}; population {basis}.', { year: S.year, window: winText(S.year), basis: S.year <= S.series.latest.pop ? T('estimate for July 1, {year}', { year: S.year }) : '' });
  rerender();
  if (!S.booting) writeUrl();
}
function setBase(y) { S.base = +y; $('#baseSel').value = String(S.base); rerender(); if (!S.booting) writeUrl(); }
function rerender() {
  S.vizzes.forEach(el => { if (el._vis) updateViz(el); else el._stale = true; });
  renderTable2(); renderPopTrend(); renderTable6(); renderTable7(); renderBurdenCharts(); renderScatter(); renderLatestKpis();
  if (S.selected) selectMuniNoUrl();
  document.querySelectorAll('.card .scatter-year').forEach(e => e.textContent = '');
}
function selectMuniNoUrl() { const b = S.booting; S.booting = true; selectMuni(S.selected); S.booting = b; }
function writeUrl() {
  const u = new URL(location.href), p = u.searchParams;
  p.set('m', S.selected); S.year == null ? p.delete('y') : p.set('y', S.year); S.base === 2012 ? p.delete('c') : p.set('c', S.base);
  history.replaceState(null, '', u);
}
function initYearBar() {
  const ys = yearsAll(), max = ys[ys.length - 1], min = ys[0];
  $('#yearSel').innerHTML = `<option value="latest">${esc(T('Latest'))}</option>` + [...ys].reverse().map(y => `<option value="${y}">${y}</option>`).join('');
  const r = $('#yearRange'); r.min = min; r.max = max; r.step = 1;
  $('#baseSel').innerHTML = ys.filter(y => y < S.series.latest.acs).map(y => `<option value="${y}">${y}</option>`).join('');
  $('#yearSel').onchange = e => { stopPlay(); setYear(e.target.value); };
  r.oninput = e => { stopPlay(); setYear(+e.target.value); r.setAttribute('aria-valuetext', T('Year {year}', { year: e.target.value })); };
  const step = (d) => { stopPlay(); const cur = S.year == null ? max : S.year; setYear(Math.min(max, Math.max(min, cur + d))); };
  $('#yrPrev').onclick = () => step(-1); $('#yrNext').onclick = () => step(1);
  $('#baseSel').onchange = e => setBase(e.target.value);
  $('#yrPlay').onclick = () => { if (playTimer) { stopPlay(); return; } let y = S.year == null || S.year >= max ? min : S.year; setYear(y); setPlayBtn(true); playTimer = setInterval(() => { y++; if (y > max) { stopPlay(); return; } setYear(y); }, 1300); };
}
function setPlayBtn(on) { $('#yrPlay').innerHTML = `<span class="ms-icon" aria-hidden="true">${on ? 'pause' : 'play_arrow'}</span><span>${esc(on ? T('Pause') : T('Play'))}</span>`; }
function stopPlay() { if (playTimer) { clearInterval(playTimer); playTimer = null; } setPlayBtn(false); }

// ── Page ───────────────────────────────────────────────────────────────────
initHelp(k => S.V[k] ? [titleOf(k, resolve(k).y), S.V[k].definition + (S.V[k].ref ? ' ' + T('Source: {ref}.', { ref: S.V[k].ref }) : '')] : null);
// The bar of contents follows the section on screen ('nearest': the least scroll). At the top of the page, on the first section or before any section is active, it goes back
// to its start, so the Knowledge Area's tabs (core/knowledge.js) are in view on a phone and on a wide screen.
const toc = document.getElementById('toc'), tocFirst = toc && toc.querySelector('a[href^="#"]');
const tocHome = () => { if (toc && toc.scrollLeft > 0) toc.scrollLeft = 0; };
const atTop = () => window.scrollY < 80;
const obs = new IntersectionObserver(entries => entries.forEach(en => { if (en.isIntersecting) document.querySelectorAll('.toc a[href^="#"]').forEach(a => { const on = a.getAttribute('href') === '#' + en.target.id; a.classList.toggle('active', on); if (on) { a.setAttribute('aria-current', 'location'); if (a === tocFirst || atTop()) tocHome(); else a.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } else a.removeAttribute('aria-current'); }); }), { rootMargin: '-45% 0px -50% 0px' });
window.addEventListener('scroll', () => { if (atTop() || !document.querySelector('.toc a.active')) tocHome(); }, { passive: true });
tocHome();

(async function init() {
  try {
    [S.meta, S.muni, S.fc, S.paper, S.series] = await Promise.all([loadJson('data/meta.json'), loadJson('data/municipalities.json'), loadJson('data/municipios.geojson'), loadJson('data/housing.json'), loadJson('data/housing_series.json')]);
    indexSeries();
    $('#snapshotLabel').innerHTML = `<b>${esc(snapshotLabel(S.meta.label))}</b>`;
    $('#citation').innerHTML = Th('<b>Study.</b> {citation}', { citation: S.paper.citation || '' });
    document.querySelectorAll('.snap').forEach(e => e.textContent = snapshotLabel(S.meta.label));
    $('#sourceList').innerHTML = [...['fpr_housing_2023', 'nalcab', 'census', 'census2010', 'put2015', 'calificacion'].map(k => S.meta.sources[k]), ...Object.values(S.series.sources)].filter(Boolean).map(s => `<div class="src"><b>${esc(s.name)}</b><span>${esc(s.license)}</span><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a></div>`).join('');
    const z = (S.meta.landuse || {}).calificacion || {};
    $('#zoningNote').innerHTML = z.available ? Th('<b>Zoning (Calificación).</b> The Junta de Planificación MIPR zoning service answered on the build date; the district layer is queued for the next build.') : Th('<b>Zoning (Calificación) pending.</b> The Junta de Planificación MIPR zoning service was unavailable when this snapshot was built ({reason}). The build retries automatically; the Plan de Uso de Terrenos classification above is the official land-use layer in the meantime.', { reason: z.reason || T('no response') });
    $('#muniPick').innerHTML = S.NM.slice(0, S.PR).slice().sort((a, b) => a.localeCompare(b, 'es')).map(n => `<option>${esc(n)}</option>`).join('');
    $('#muniPick').onchange = e => selectMuni(e.target.value);
    const q = new URLSearchParams(location.search), want = q.get('m'), start = want && S.NM.slice(0, S.PR).find(k => norm(k) === norm(want));
    if (start) S.selected = start;
    initYearBar(); initDialog();
    S.booting = true;
    const qy = q.get('y'), qc = q.get('c');
    if (qc && /^\d{4}$/.test(qc)) S.base = +qc;
    $('#baseSel').value = String(S.base);
    renderPaperTables(); renderLedes();
    // the maps and charts are built when they come near the viewport, not all at once, and refreshed when they scroll into view after a year change
    const vizObs = new IntersectionObserver(es => es.forEach(e => { const el = e.target; el._vis = e.isIntersecting; if (e.isIntersecting) { if (!el.dataset.built) buildViz(el); else if (el._stale) updateViz(el); } }), { rootMargin: '800px 0px' });
    document.querySelectorAll('.viz[data-var]').forEach(el => { el.style.minHeight = '640px'; vizObs.observe(el); });
    document.querySelectorAll('.block, .hero').forEach(b => obs.observe(b));
    setYear(qy && /^\d{4}$/.test(qy) ? +qy : null);
    renderCatalog();
    S.booting = false;
    const d = q.get('d'); if (d && (S.V[d] || S.STATIC[d])) setTimeout(() => S.V[d] ? openDataset(d) : openStatic(d), 300);
    if (location.hash && document.querySelector(location.hash)) [400, 1500].forEach(ms => setTimeout(() => document.querySelector(location.hash).scrollIntoView(), ms));
    setTimeout(() => S.maps.forEach(m => m.invalidateSize()), 300);
  } catch (e) {
    document.querySelector('.page').insertAdjacentHTML('afterbegin', `<div class="card" role="alert">${Th('<b>The housing data did not load.</b> {message}. Check your connection, then <a href="" onclick="location.reload();return false">try again</a>.', { message: e.message })}</div>`);
    console.error(e);
  }
})();
