/* PR Data Observatory: the Energy page (energy.html, Knowledge Area; HANDOFF decision 104, step 3).
   Loads data/energy.json (energy_series.py: LUMA's filings at the Energy Bureau, EIA-861M, and the observatory's plant, line and flood files) and shows:
     - Puerto Rico now: plant capacity, rooftop solar, home batteries, the renewable share of production and the residential price;
     - where electricity comes from, every year since 2010, with rooftop exports apart, against the law's target;
     - rooftop solar every month since 2010 against the renewable plants, and batteries since 2021;
     - batteries, electricity use and smart meters by municipio; rooftop solar by LUMA district;
     - reliability (SAIDI) every month and by district; the residential price against the United States;
     - the transmission lines and plants inside FEMA's flood hazard areas.
   Totals by month, municipio or district only: no customer, address or installation (the sources hold none). Every visible string goes through T(): its
   Spanish is in i18n_src/es/energy.json, written by docs/analysis/energy-2026-11/make_page.py. */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc && doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const escH = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const MON = (m) => { const [y, k] = m.split('-').map(Number); return new Date(Date.UTC(y, k - 1, 15)).toLocaleDateString(loc(), { year: 'numeric', month: 'long', timeZone: 'UTC' }); };
  // the fuels, in the colours of the Power plants layer (core/facilities.js; Okabe-Ito); rooftop exports in a darker gold
  const FUEL = { oil: ['#E69F00', 'Oil'], gas: ['#CC79A7', 'Natural gas'], coal: ['#3a3a3a', 'Coal'], hydro: ['#009E73', 'Hydroelectric'], solar: ['#F0E442', 'Solar plants'],
    wind: ['#56B4E9', 'Wind'], landfill: ['#D55E00', 'Landfill gas'], dg: ['#9c7a00', 'Rooftop solar sent to the grid'] };
  const RENEW = ['hydro', 'solar', 'wind', 'landfill'];
  const S = { sortM: ['bess100', -1], sortD: ['mw', -1], sortR: ['saidi', -1] };
  let D = null;

  // ── Figures (pure: tests/energy_page.test.js) ──
  /** Shares of a year's production: the renewable share with rooftop exports, and of the plants alone. */
  function shares(y) {
    const tot = Object.values(y).reduce((a, b) => a + b, 0), ren = RENEW.reduce((a, k) => a + (y[k] || 0), 0);
    return { total: tot, withRooftop: (ren + (y.dg || 0)) / tot * 100, plants: ren / (tot - (y.dg || 0)) * 100, rooftop: (y.dg || 0) / tot * 100 };
  }
  /** The municipio rows of the table. */
  function muniRows(m) {
    return m.ids.map((id, i) => ({ id, name: m.names[i], bess: m.bess[i], bess100: m.hu[i] ? m.bess[i] / m.hu[i] * 100 : null, kwh: m.bess_kwh[i],
      sales: m.sales_gwh_12m[i], perRes: m.pop[i] ? m.sales_gwh_12m[i] * 1e3 / m.pop[i] : null, ami: m.ami_pct[i] }));
  }
  /** Sum of the last n months of a series (null when a month is missing). */
  function lastSum(arr, n = 12) { const a = arr.slice(-n); return a.length === n && a.every(v => v != null) ? a.reduce((p, q) => p + q, 0) : null; }
  const lastOf = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return [arr[i], i]; return [null, -1]; };

  // ── Page ──
  if (doc && $('#enNow')) fetchJson('data/energy.json').then(d => { D = d; start(); }, (e) => {
    $('#enNow').innerHTML = `<p class="pm-p">${escH(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });
  function start() { drawNow(); drawMix(); drawRooftop(); drawMunis(); drawDistricts(); drawSaidi(); drawPrice(); drawHazards(); }
  function card(icon, label, value, sub) {
    return `<div class="bb-card"><span class="ms-icon" aria-hidden="true">${icon}</span><div><div class="bb-v">${escH(value)}</div><div class="bb-l">${escH(label)}</div><div class="bb-s">${escH(sub)}</div></div></div>`;
  }
  const lastYear = () => Object.keys(D.annual_gwh).sort().pop();
  function drawNow() {
    const c = D.capacity, s = D.series, [cust, ci] = lastOf(s.rooftop_customers), y = lastYear(), sh = shares(D.annual_gwh[y]), m = D.municipios;
    const bess = m.bess.reduce((a, b) => a + b, 0), p = D.price, pi = p.months.length - 1;
    $('#enNow').innerHTML = `<div class="bb-cards">${[
      card('bolt', T('Power plants of 1 MW or more'), T('{v} MW', { v: fmt(c.mw) }), T('{r} MW renewable; EIA, {m}', { r: fmt(c.renewable_mw), m: MON(c.as_of) })),
      card('solar_power', T('Rooftop solar'), T('{v} MW', { v: fmt(c.rooftop_mw) }), T('{n} customers; LUMA, {m}', { n: fmt(cust), m: MON(s.months[ci]) })),
      card('battery_charging_full', T('Home and business batteries'), fmt(bess), T('installations; LUMA, {m}', { m: MON(m.as_of) })),
      card('eco', T('Renewable share of production, {y}', { y }), pct(sh.withRooftop), T('{p} from the plants alone', { p: pct(sh.plants) })),
      card('payments', T('Residential price'), T('{v} ¢/kWh', { v: fmt(p.pr[pi], 1) }), T('United States {u} ¢/kWh; EIA, {m}', { u: fmt(p.us[pi], 1), m: MON(p.months[pi]) }))].join('')}</div>`;
    $('#enNow').dataset.done = '1';
  }

  // 1 · the mix, every full year: stacked bars of shares
  function drawMix() {
    const A = D.annual_gwh, ys = Object.keys(A).sort(), keys = Object.keys(FUEL);
    const W = 900, H = 340, L = 44, R = 10, Tp = 10, B = 34, bw = (W - L - R) / ys.length;
    let s = '';
    for (let v = 0; v <= 100; v += 25) s += `<line x1="${L}" x2="${W - R}" y1="${Tp + (100 - v) / 100 * (H - Tp - B)}" y2="${Tp + (100 - v) / 100 * (H - Tp - B)}" stroke="#e3e6ec"/><text x="${L - 6}" y="${Tp + (100 - v) / 100 * (H - Tp - B) + 4}" text-anchor="end" class="tick">${escH(pct(v, 0))}</text>`;
    ys.forEach((y, i) => {
      const t = keys.reduce((a, k) => a + (A[y][k] || 0), 0); let acc = 0;
      keys.forEach(k => {
        const v = (A[y][k] || 0) / t * 100; if (!v) return;
        const y0 = Tp + (100 - acc - v) / 100 * (H - Tp - B), h = v / 100 * (H - Tp - B); acc += v;
        s += `<rect x="${(L + i * bw + 2).toFixed(1)}" y="${y0.toFixed(1)}" width="${(bw - 4).toFixed(1)}" height="${h.toFixed(2)}" fill="${FUEL[k][0]}"><title>${escH(`${y} · ${T(FUEL[k][1])}: ${pct(v)} (${fmt(A[y][k])} GWh)`)}</title></rect>`;
      });
      if (i % 2 === 0 || ys.length < 12) s += `<text x="${(L + i * bw + bw / 2).toFixed(1)}" y="${H - B + 16}" text-anchor="middle" class="tick">${y}</text>`;
    });
    const last = ys[ys.length - 1], sh = shares(A[last]);
    const label = T('Stacked bar chart: Puerto Rico\'s electricity production by source, every year from {a} to {b}. In {b}, renewables were {r} of production with rooftop solar sent to the grid, {p} from the plants alone.', { a: ys[0], b: last, r: pct(sh.withRooftop), p: pct(sh.plants) });
    $('#enMix').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${escH(label)}">${s}</svg>`
      + `<div class="pm-legend bb-legend">${keys.map(k => `<span class="pm-keyrow"><i style="background:${FUEL[k][0]}"></i>${escH(T(FUEL[k][1]))}</span>`).join('')}</div>`;
    const rps = D.series.rps_pct, rm = D.series.months, yr = rm.map((m, i) => [m, rps[i]]).filter(([m, v]) => m.startsWith(last) && v != null);
    const avg = yr.length ? yr.reduce((a, [, v]) => a + v, 0) / yr.length : null;
    $('#enMixNote').textContent = T('LUMA counted {a} of the electricity it distributed in {y} toward the renewable portfolio standard, on average over the year. Act 17-2019 set 40% for 2025; Act 1-2025 removed that target and kept 100% for 2050.', { a: pct(avg), y: last });
    $('#enMix').dataset.done = '1';
  }

  // a line chart of monthly series: [{ values, color, label, dash }], optional flat reference lines
  function lineChart(months, lines, opt = {}) {
    const W = 900, H = opt.h || 300, L = 56, R = 14, Tp = 12, B = 34, n = months.length;
    const vals = lines.flatMap(l => l.values).concat((opt.refs || []).map(r => r.v)).filter(v => v != null);
    const y1 = Math.max(...vals) * 1.08 || 1, X = (i) => L + i / Math.max(1, n - 1) * (W - L - R), Y = (v) => Tp + (1 - v / y1) * (H - Tp - B);
    let s = '';
    const step = Math.pow(10, Math.floor(Math.log10(y1))) / (y1 / Math.pow(10, Math.floor(Math.log10(y1))) < 2.5 ? 4 : y1 / Math.pow(10, Math.floor(Math.log10(y1))) < 5 ? 2 : 1);
    for (let v = 0; v <= y1; v += step) s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e3e6ec"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${escH(fmt(v, step < 1 ? 1 : 0))}</text>`;
    months.forEach((m, i) => { if (m.endsWith('-01') && (n < 80 || +m.slice(0, 4) % 2 === 0)) s += `<text x="${X(i)}" y="${H - B + 16}" text-anchor="middle" class="tick">${m.slice(0, 4)}</text>`; });
    (opt.refs || []).forEach(r => { s += `<line x1="${L}" x2="${W - R}" y1="${Y(r.v)}" y2="${Y(r.v)}" stroke="${r.color}" stroke-dasharray="5 4"/><text x="${W - R}" y="${Y(r.v) - 5}" text-anchor="end" class="tick" fill="${r.color}">${escH(r.label)}</text>`; });
    lines.forEach(l => { let d = '', pen = false; l.values.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; }); s += `<path d="${d}" fill="none" stroke="${l.color}" stroke-width="2.4"${l.dash ? ' stroke-dasharray="6 4"' : ''}/>`; });
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${escH(opt.label || '')}">${s}</svg>`
      + `<div class="pm-legend bb-legend">${lines.map(l => `<span class="pm-keyrow"><i style="background:${l.color}"></i>${escH(l.label)}</span>`).join('')}</div>`;
  }

  // 2 · rooftop solar and batteries
  function drawRooftop() {
    const s = D.series, i0 = s.rooftop_mw.findIndex(v => v != null && v > 0), months = s.months.slice(i0), mw = s.rooftop_mw.slice(i0), [last, li] = lastOf(s.rooftop_mw);
    const label = T('Line chart: rooftop solar capacity registered with the utility, every month from {a} to {b}, reaching {v} MW, against the {r} MW of renewable power plants.', { a: MON(months[0]), b: MON(s.months[li]), v: fmt(last), r: fmt(D.capacity.renewable_mw) });
    $('#enRooftop').innerHTML = lineChart(months, [{ values: mw, color: '#9c7a00', label: T('Rooftop solar, MW (LUMA)') }],
      { label, refs: [{ v: D.capacity.renewable_mw, color: '#009E73', label: T('Renewable power plants: {v} MW (EIA, {m})', { v: fmt(D.capacity.renewable_mw), m: MON(D.capacity.as_of) }) }] });
    const b = D.municipios.bess_series, bl = b.total[b.total.length - 1], j = Math.max(i0, li - 60);   // five years before the last month
    $('#enRooftopNote').textContent = T('Rooftop solar grew from {a} MW in {ma} to {b} MW in {mb}, {x} times the capacity of the renewable power plants. Batteries: {n} installations in {mn}, {f} in {mf}.', {
      a: fmt(s.rooftop_mw[j]), ma: MON(s.months[j]), b: fmt(last), mb: MON(s.months[li]),
      x: fmt(last / D.capacity.renewable_mw, 1), n: fmt(bl), mn: MON(b.months[b.months.length - 1]), f: fmt(b.total[0]), mf: MON(b.months[0]) });
    $('#enRooftop').dataset.done = '1';
  }

  function th(key, label, sort) { const on = sort && sort[0] === key; return `<th scope="col"${on ? ` aria-sort="${sort[1] > 0 ? 'ascending' : 'descending'}"` : ''}><button type="button" class="pm-btn" data-k="${key}">${escH(label)}${on ? (sort[1] > 0 ? ' ▲' : ' ▼') : ''}</button></th>`; }
  function sortRows(rows, [k, dir]) { rows.sort((p, q) => (k === 'name' ? String(p.name).localeCompare(String(q.name), loc()) : (p[k] ?? -1) - (q[k] ?? -1)) * dir); }
  function bindSort(box, key, redraw) { box.querySelectorAll('button[data-k]').forEach(b => { b.onclick = () => { const kk = b.dataset.k; S[key] = [kk, S[key][0] === kk ? -S[key][1] : (kk === 'name' ? 1 : -1)]; redraw(); }; }); }

  // 3 · municipios
  function drawMunis() {
    const m = D.municipios, rows = muniRows(m); sortRows(rows, S.sortM);
    const tot = { name: T('Puerto Rico'), bess: m.bess.reduce((a, b) => a + b, 0), kwh: m.bess_kwh.reduce((a, b) => a + b, 0), sales: m.sales_gwh_12m.reduce((a, b) => a + b, 0) };
    tot.bess100 = tot.bess / m.hu.reduce((a, b) => a + b, 0) * 100; tot.perRes = tot.sales * 1e3 / m.pop.reduce((a, b) => a + b, 0); tot.ami = m.ami_system_pct;
    const row = (r, cls = '') => `<tr${cls}><th scope="row">${escH(r.name)}</th><td>${fmt(r.bess)}</td><td>${fmt(r.bess100, 1)}</td><td>${fmt(r.kwh / 1000, 1)}</td><td>${fmt(r.sales, 1)}</td><td>${fmt(r.perRes, 2)}</td><td>${r.ami == null ? '—' : pct(r.ami)}</td></tr>`;
    $('#enMunis').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('Batteries in {b}; electricity sales from {s0} to {s1}. Select a heading to sort.', { b: MON(m.as_of), s0: MON(m.sales_months[0]), s1: MON(m.sales_months[1]) }))}</caption><thead><tr>${th('name', T('Municipio'), S.sortM)}${th('bess', T('Batteries'), S.sortM)}${th('bess100', T('Per 100 housing units'), S.sortM)}${th('kwh', T('Stored, MWh'), S.sortM)}${th('sales', T('Sales, GWh in 12 months'), S.sortM)}${th('perRes', T('MWh per resident'), S.sortM)}${th('ami', T('Smart meters'), S.sortM)}</tr></thead>
      <tbody>${row(tot, ' class="bb-pr"')}${rows.map(r => row(r)).join('')}</tbody></table>`;
    bindSort($('#enMunis'), 'sortM', drawMunis);
    $('#enMunis').dataset.done = '1';
  }
  // 4 · districts
  function drawDistricts() {
    const d = D.districts, rows = d.rows.map(([name, mw, n]) => ({ name, mw, n, kw: n ? mw * 1000 / n : null })); sortRows(rows, S.sortD);
    $('#enDistricts').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('Rooftop solar by LUMA commercial district, {m}. LUMA publishes no map of its districts; each is named after its main town.', { m: MON(d.as_of) }))}</caption><thead><tr>${th('name', T('District'), S.sortD)}${th('mw', T('Rooftop solar, MW'), S.sortD)}${th('n', T('Installations'), S.sortD)}${th('kw', T('kW per installation'), S.sortD)}</tr></thead>
      <tbody>${rows.map(r => `<tr><th scope="row">${escH(r.name)}</th><td>${fmt(r.mw, 1)}</td><td>${fmt(r.n)}</td><td>${fmt(r.kw, 1)}</td></tr>`).join('')}</tbody></table>`;
    bindSort($('#enDistricts'), 'sortD', drawDistricts);
  }
  // 5 · reliability
  function drawSaidi() {
    const s = D.saidi, sum = lastSum(s.td), e = s.eia861_2025;
    const label = T('Line chart: minutes without power per customer each month from transmission and distribution outages (SAIDI), {a} to {b}. The last 12 months add up to {v} minutes.', { a: MON(s.months[0]), b: MON(s.months[s.months.length - 1]), v: fmt(sum) });
    $('#enSaidi').innerHTML = lineChart(s.months, [{ values: s.td, color: '#4a1486', label: T('SAIDI, transmission and distribution (minutes)') }, { values: s.dist, color: '#a39fc9', label: T('Of it, distribution'), dash: true }], { label, h: 260 });
    $('#enSaidiNote').textContent = T('In the 12 months to {m}, the average customer was without power {v} minutes ({h} hours) from transmission and distribution outages. Counting every event, generation shortfalls included, EIA\'s figure for 2025 is {a} minutes ({ah} hours), {f} interruptions per customer.', {
      m: MON(s.months[s.months.length - 1]), v: fmt(sum), h: fmt(sum / 60, 1), a: fmt(e.saidi_all), ah: fmt(e.saidi_all / 60, 1), f: fmt(e.saifi_all, 1) });
    const rows = Object.entries(s.districts).map(([name, v]) => ({ name, saidi: lastSum(v) })); sortRows(rows, S.sortR);
    $('#enSaidiD').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('SAIDI by LUMA technical district, minutes in the 12 months to {m}', { m: MON(s.months[s.months.length - 1]) }))}</caption><thead><tr>${th('name', T('District'), S.sortR)}${th('saidi', T('Minutes without power per customer'), S.sortR)}</tr></thead>
      <tbody>${rows.map(r => `<tr><th scope="row">${escH(r.name)}</th><td>${fmt(r.saidi)}</td></tr>`).join('')}</tbody></table>`;
    bindSort($('#enSaidiD'), 'sortR', drawSaidi);
  }
  // 6 · price
  function drawPrice() {
    const p = D.price, i = p.months.length - 1;
    const label = T('Line chart: average residential price of electricity in Puerto Rico and the United States, every month from {a} to {b}: {pr} and {us} cents per kWh in the last month.', { a: MON(p.months[0]), b: MON(p.months[i]), pr: fmt(p.pr[i], 1), us: fmt(p.us[i], 1) });
    $('#enPrice').innerHTML = lineChart(p.months, [{ values: p.pr, color: '#c4452c', label: T('Puerto Rico (the utility)') }, { values: p.us, color: '#3b73bd', label: T('United States') }], { label, h: 260 });
  }
  // 7 · flood hazard
  function drawHazards() {
    const x = D.exposure, kv = ['230', '115', '38'];
    $('#enHazLines').innerHTML = `<table class="pm-table bb-table"><caption>${escH(T('Transmission lines inside FEMA flood hazard areas, as drawn on the map (simplified)'))}</caption><thead><tr><th scope="col">${escH(T('Voltage'))}</th><th scope="col">${escH(T('Km mapped'))}</th><th scope="col">${escH(T('Km in the 1% flood area'))}</th><th scope="col">${escH(T('Share'))}</th><th scope="col">${escH(T('Km in coastal V zones'))}</th></tr></thead>
      <tbody>${kv.map(k => { const r = x.lines[k]; return `<tr><th scope="row">${k} kV</th><td>${fmt(r.km)}</td><td>${fmt(r.sfha_km)}</td><td>${pct(r.sfha_km / r.km * 100)}</td><td>${fmt(r.v_km, 1)}</td></tr>`; }).join('')}</tbody></table>`;
    $('#enHazPlants').innerHTML = `<p class="pm-p">${escH(T('{n} of the {all} plants with an operating generator ({mw} of {allmw} MW) stand inside the 1% flood area. The largest:', { n: x.plants_sfha, all: x.plants, mw: fmt(x.plants_sfha_mw), allmw: fmt(x.plants_mw) }))}</p><ul class="en-list">${x.plants_sfha_list.map(([n, m, mw]) => `<li>${escH(T('{name}, {muni}: {mw} MW', { name: n, muni: m, mw: fmt(mw, 1) }))}</li>`).join('')}</ul>`;
  }

  if (typeof module === 'object' && module.exports) module.exports = { shares, muniRows, lastSum };
})(typeof window !== 'undefined' ? window : globalThis);
