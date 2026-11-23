/* PR Data Observatory: the Reservoirs page (reservoirs.html, Knowledge Area; HANDOFF decision 98).
   Loads data/reservoir_history.json (reservoirs.py: for each reservoir with a live USGS gauge, its range in 2011-2025, its record low, the mean of each week
   of the year in each year 2011-2025, its monthly means since its first daily value and its last 400 days), then asks USGS for the latest readings and the
   daily values since the file was built (one request each, made by the visitor's browser, as the map's Reservoir levels layer does). From these it shows:
     - how Puerto Rico's reservoirs stand now: the 19 of AAA's daily report below, within or above their usual level for this week, and a ranking table;
     - the water in each reservoir as a tank filled to where its level sits in its own 2011-2025 range (a level, not a volume: USGS publishes no volumes);
     - one reservoir in detail: the last 400 days over its usual range, the same month in every year, and its whole monthly history;
     - Puerto Rico over time: how many of AAA's reservoirs were below their usual level for the month, month by month.
   "Usual" is the rule of the map layer (core/facilities.js): below the 10th percentile of the same week's yearly means in 2011-2025 is lower than usual, above
   the 90th higher. AAA's own alert levels are not shown (no licence stated); the page links to AAA's page. Every visible string goes through T(): its Spanish
   is in i18n_src/es/reservoirs.json, written by docs/analysis/reservoirs-2026-11/make_page.py. The chosen reservoir is kept in the address (#r=USGS-...). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 2) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const sgn = (v, d = 2) => v == null || !isFinite(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '±') + fmt(Math.abs(v), d);
  const API = 'https://api.waterdata.usgs.gov/ogcapi/v1/collections';
  const AAA_PAGE = 'https://www.acueductos.pr.gov/infraestructura/niveles-de-los-embalses';
  const FT = 0.3048, DAY = 864e5;
  const STATUS = {   // the map layer's three bands; colour never alone: an icon and a word go with it
    low: { icon: 'arrow_downward', label: 'Lower than usual', cls: 'rv-low' },
    usual: { icon: 'check', label: 'Usual for this time of year', cls: 'rv-usual' },
    high: { icon: 'arrow_upward', label: 'Higher than usual', cls: 'rv-high' },
    none: { icon: 'remove', label: 'No usual range for this week', cls: 'rv-none' },
  };
  let D, live = { ok: null, at: null }, S = { sel: null, sort: ['pct', 1] };

  const prDate = (t) => new Date(t).toLocaleDateString('en-CA', { timeZone: 'America/Puerto_Rico' });   // YYYY-MM-DD in Puerto Rico
  const weekOf = (iso) => { const [y, m, d] = iso.split('-').map(Number); return Math.min(Math.floor((Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 1)) / 6048e5), 52); };   // as reservoirs.py week()
  const dayIdx = (r, iso) => Math.round((Date.parse(iso + 'T12:00:00Z') - Date.parse(r.d0 + 'T12:00:00Z')) / DAY);
  const isoAdd = (iso, n) => new Date(Date.parse(iso + 'T12:00:00Z') + n * DAY).toISOString().slice(0, 10);
  const when = (t) => new Date(t).toLocaleString(loc(), { timeZone: 'America/Puerto_Rico', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' });
  const monthName = (m) => new Date(Date.UTC(2000, m - 1, 15)).toLocaleString(loc(), { month: 'long', timeZone: 'UTC' });
  const quantile = (xs, q) => { const s = xs.slice().sort((a, b) => a - b), pos = (s.length - 1) * q, lo = Math.floor(pos); return lo + 1 >= s.length ? s[lo] : s[lo] + (s[lo + 1] - s[lo]) * (pos - lo); };   // as reservoirs.py quantile()
  const median = (xs) => xs.length ? quantile(xs, 0.5) : null;

  if (doc) fetchJson('data/reservoir_history.json').then((d) => { D = d; prepare(); render(); fetchLive(); }, (e) => {
    $('#rvRank').innerHTML = `<p class="pm-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  // ── the figures of one reservoir now ──
  function prepare() {
    for (const r of D.reservoirs) { r.now = r.level; r.nowTime = r.level_time; }
    const h = new URLSearchParams(location.hash.slice(1)).get('r');
    S.sel = D.reservoirs.some(r => r.usgs === h) ? h : null;
  }
  function figures(r) {
    const day = prDate(r.nowTime), w = weekOf(day), yrs = r.wk[w].filter(v => v != null);
    const p10 = yrs.length >= 8 ? quantile(yrs, 0.1) : null, p90 = yrs.length >= 8 ? quantile(yrs, 0.9) : null;
    const below = yrs.filter(v => v < r.now).length;
    const st = p10 == null ? 'none' : r.now < p10 ? 'low' : r.now > p90 ? 'high' : 'usual';
    const at = (n) => { const i = dayIdx(r, isoAdd(day, -n)); return i >= 0 && i < r.day.length ? r.day[i] : null; };
    const fill = (v) => v == null ? null : Math.max(0, Math.min(100, (v - r.lo) / (r.hi - r.lo) * 100));
    const a7 = at(7), a30 = at(30);
    return { day, w, yrs: yrs.length, below, pct: yrs.length ? Math.round(below / yrs.length * 100) : null, p10, p90, st,
      fill: fill(r.now), band: p10 == null ? null : [fill(p10), fill(p90)], d7: a7 == null ? null : r.now - a7, d30: a30 == null ? null : r.now - a30 };
  }

  // ── live: the latest readings, and the daily values since the file was built (one request each; on failure the file's figures stand) ──
  async function fetchLive() {
    const ids = D.reservoirs.map(r => r.usgs).join(',');
    const get = (u) => fetchRetry(u);   // common.js: tried again with the cache bypassed when an answer fails
    try {
      const last = isoAdd(D.reservoirs[0].d0, D.reservoirs[0].day.length - 1), from = isoAdd(last, -3);
      const [lat, dly] = await Promise.all([
        get(`${API}/latest-continuous/items?f=json&parameter_code=72376&limit=200&skipGeometry=true&properties=monitoring_location_id,time,value&monitoring_location_id=${ids}`),
        get(`${API}/daily/items?f=json&parameter_code=72375&limit=5000&skipGeometry=true&properties=monitoring_location_id,time,value&datetime=${from}/..&monitoring_location_id=${ids}`),
      ]);
      const by = {}; for (const r of D.reservoirs) by[r.usgs] = r;
      for (const f of dly.features || []) {
        const p = f.properties, r = by[p.monitoring_location_id]; if (!r || p.value == null || !isFinite(+p.value)) continue;
        const i = dayIdx(r, p.time.slice(0, 10)); if (i < 0) continue;
        while (r.day.length <= i) r.day.push(null);
        r.day[i] = Math.round(+p.value * FT * 100) / 100;
      }
      for (const f of lat.features || []) { const p = f.properties, r = by[p.monitoring_location_id]; if (r && p.value != null && isFinite(+p.value)) { r.now = +p.value; r.nowTime = p.time; } }
      live = { ok: true, at: Date.now() };
    } catch (e) { live = { ok: false, at: Date.now() }; }
    render();
  }

  // ── a tank: the reservoir's water filled to where its level sits in its own 2011-2025 range, the usual band of this week marked ──
  function tank(f, size) {
    const big = size === 'big', W = big ? 150 : 34, H = big ? 190 : 40, top = big ? 10 : 2, bot = H - (big ? 10 : 2), hh = bot - top;
    const y = (p) => bot - p / 100 * hh, wy = f.fill == null ? bot : y(f.fill);
    const wave = big ? `<path class="rv-wave" d="M0,${wy} q ${W / 8},-6 ${W / 4},0 t ${W / 4},0 t ${W / 4},0 t ${W / 4},0 t ${W / 4},0 V${bot} H0 Z"/>` : '';
    const band = f.band ? `<rect class="rv-band" x="${big ? 2 : 1}" y="${y(f.band[1])}" width="${W - (big ? 4 : 2)}" height="${Math.max(1, y(f.band[0]) - y(f.band[1]))}"/>` : '';
    const label = big ? T('Water at {p}% of its 2011-2025 range', { p: fmt(f.fill, 0) }) : T('{p}% of its range', { p: fmt(f.fill, 0) });
    return `<svg class="rv-tank ${big ? 'big' : ''}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
      <rect class="rv-glass" x="0.5" y="${top - 0.5}" width="${W - 1}" height="${hh + 1}" rx="${big ? 10 : 4}"/>
      <clipPath id="c${tank.n = (tank.n || 0) + 1}"><rect x="1" y="${top}" width="${W - 2}" height="${hh}" rx="${big ? 9 : 3}"/></clipPath>
      <g clip-path="url(#c${tank.n})"><rect class="rv-water" x="0" y="${wy}" width="${W}" height="${bot - wy}"/>${wave}${band}</g>
      ${big && f.band ? `<line class="rv-bandline" x1="0" x2="${W}" y1="${y(f.band[0])}" y2="${y(f.band[0])}"/><line class="rv-bandline" x1="0" x2="${W}" y1="${y(f.band[1])}" y2="${y(f.band[1])}"/>` : ''}
      ${big ? `<text class="rv-tankp" x="${W / 2}" y="${Math.min(bot - 8, Math.max(top + 22, wy + 26))}" text-anchor="middle">${fmt(f.fill, 0)}%</text>` : ''}</svg>`;
  }
  const badge = (st) => `<span class="rv-badge ${STATUS[st].cls}"><span class="ms-icon" aria-hidden="true">${STATUS[st].icon}</span>${esc(T(STATUS[st].label))}</span>`;

  // ── the page ──
  function render() {
    if (!D) return;
    const rows = D.reservoirs.map(r => ({ r, f: figures(r) }));
    const aaa = rows.filter(x => x.r.aaa);
    renderOverall(aaa);
    renderRank(rows, aaa);
    renderDetail(rows);
    renderHistory();
    $('#rvLive').textContent = live.ok === null ? T('Loading the latest readings from USGS…') : live.ok ? T('Latest readings from USGS loaded {t}; they are provisional, as USGS publishes them.', { t: when(live.at) })
      : T('The latest readings could not be loaded from USGS: the figures are those of {date}.', { date: D.vintage });
  }

  function renderOverall(aaa) {
    const n = { low: 0, usual: 0, high: 0, none: 0 }; aaa.forEach(x => n[x.f.st]++);
    const fills = aaa.map(x => x.f.fill).filter(v => v != null), pcts = aaa.map(x => x.f.pct).filter(v => v != null);
    const mf = median(fills), mp = median(pcts);
    $('#rvTank').innerHTML = tank({ fill: mf, band: null }, 'big') + `<div class="rv-tankcap">${esc(T('Puerto Rico: the median of AAA\'s {n} reservoirs', { n: aaa.length }))}</div>`;
    $('#rvCounts').innerHTML = ['low', 'usual', 'high'].map(k => `<div class="rv-count ${STATUS[k].cls}"><span class="ms-icon" aria-hidden="true">${STATUS[k].icon}</span><b>${n[k]}</b><span>${esc(T(STATUS[k].label))}</span></div>`).join('');
    $('#rvOverall').innerHTML = esc(T('Of the {n} reservoirs in AAA\'s daily report, {low} are lower than usual for this time of year, {usual} are within their usual range and {high} are higher.', { n: aaa.length, low: n.low, usual: n.usual, high: n.high }))
      + ' ' + esc(T('The median reservoir sits at {f}% of its own 2011-2025 range, and its level is higher than in {p}% of the years 2011-2025 for this week.', { f: fmt(mf, 0), p: fmt(mp, 0) }));
  }

  const COLS = [
    ['rank', '#', 'num'], ['name', 'Reservoir', ''], ['fill', 'Water (share of its 2011-2025 range)', ''], ['now', 'Level now (m)', 'num'],
    ['d7', 'Change in 7 days (m)', 'num'], ['d30', 'Change in 30 days (m)', 'num'], ['pct', 'Higher than in this share of years, same week', 'num'], ['st', 'Status', ''],
  ];
  function renderRank(rows, aaa) {
    const order = rows.slice().sort((a, b) => (a.f.pct ?? 999) - (b.f.pct ?? 999) || a.f.fill - b.f.fill);
    order.forEach((x, i) => { x.rank = i + 1; });
    const [k, dir] = S.sort, val = (x) => k === 'name' ? x.r.name : k === 'rank' ? x.rank : k === 'now' ? x.r.now : k === 'st' ? ['low', 'usual', 'high', 'none'].indexOf(x.f.st) : x.f[k];
    const list = order.slice().sort((a, b) => { const p = val(a), q = val(b); return (p == null) - (q == null) || (typeof p === 'string' ? p.localeCompare(q, loc()) : p - q) * dir; });
    const pctTxt = (f) => f.pct == null ? '—' : T('{p}% ({b} of {n} years)', { p: fmt(f.pct, 0), b: f.below, n: f.yrs });
    const med = (k2) => median(aaa.map(x => x.f[k2]).filter(v => v != null));
    const head = COLS.map(([c, l, cls]) => `<th scope="col" class="${cls}" aria-sort="${c === k ? (dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${c}">${esc(T(l))}</button></th>`).join('');
    const overall = `<tr class="rv-overall"><td></td><th scope="row">${esc(T('Puerto Rico: median of AAA\'s {n} reservoirs', { n: aaa.length }))}</th><td>${tank({ fill: med('fill'), band: null })}<span class="rv-fillp">${fmt(med('fill'), 0)}%</span></td><td class="num">—</td><td class="num">${sgn(med('d7'))}</td><td class="num">${sgn(med('d30'))}</td><td class="num">${fmt(med('pct'), 0)}%</td><td>${esc(T('{low} lower · {usual} usual · {high} higher', { low: aaa.filter(x => x.f.st === 'low').length, usual: aaa.filter(x => x.f.st === 'usual').length, high: aaa.filter(x => x.f.st === 'high').length }))}</td></tr>`;
    const body = list.map(x => `<tr data-r="${x.r.usgs}" tabindex="0" class="${x.r.usgs === S.sel ? 'sel' : ''}"><td class="num">${x.rank}</td><th scope="row"><b>${esc(x.r.name)}</b><small>${esc(x.r.municipio)}${x.r.aaa ? ' · AAA' : ''}</small></th><td>${tank(x.f)}<span class="rv-fillp">${fmt(x.f.fill, 0)}%</span></td><td class="num">${fmt(x.r.now)}</td><td class="num">${sgn(x.f.d7)}</td><td class="num">${sgn(x.f.d30)}</td><td class="num">${esc(pctTxt(x.f))}</td><td>${badge(x.f.st)}</td></tr>`).join('');
    $('#rvRank').innerHTML = `<table class="pm-table rv-table"><caption class="sr-only">${esc(T('Reservoirs ranked from the lowest to the highest for this time of year'))}</caption><thead><tr>${head}</tr></thead><tbody>${overall}${body}</tbody></table>`;
    $('#rvRank').querySelectorAll('button[data-sort]').forEach(b => b.onclick = () => { const c = b.dataset.sort; S.sort = [c, S.sort[0] === c ? -S.sort[1] : 1]; render(); });
    $('#rvRank').querySelectorAll('tr[data-r]').forEach(tr => { const go = () => { select(tr.dataset.r); $('#detail').scrollIntoView({ behavior: 'smooth', block: 'start' }); }; tr.onclick = go; tr.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } }; });
  }

  function select(id) { S.sel = id; history.replaceState(null, '', '#r=' + id); render(); }

  // ── one reservoir ──
  function renderDetail(rows) {
    const sel = $('#rvSel');
    if (!sel.options.length) {
      sel.innerHTML = rows.map(x => `<option value="${x.r.usgs}">${esc(x.r.name)} (${esc(x.r.municipio)})</option>`).join('');
      sel.onchange = () => select(sel.value);
    }
    const x = rows.find(y => y.r.usgs === S.sel) || rows.slice().sort((a, b) => (a.f.pct ?? 999) - (b.f.pct ?? 999))[0];
    sel.value = x.r.usgs;
    const r = x.r, f = x.f;
    $('#rvBigTank').innerHTML = tank(f, 'big');
    $('#rvFacts').innerHTML = `<h3>${esc(r.name)} <small>${esc(r.municipio)}</small></h3>${badge(f.st)}
      <dl><dt>${esc(T('Level now'))}</dt><dd>${esc(T('{v} m above mean sea level', { v: fmt(r.now) }))} <small>${esc(when(r.nowTime))}</small></dd>
      <dt>${esc(T('Change'))}</dt><dd>${esc(T('{a} m in 7 days, {b} m in 30 days', { a: sgn(f.d7), b: sgn(f.d30) }))}</dd>
      <dt>${esc(T('This week in 2011-2025'))}</dt><dd>${f.p10 == null ? esc(T(STATUS.none.label)) : esc(T('Usual range {a} to {b} m; today\'s level is higher than in {p}% of those years ({k} of {n}).', { a: fmt(f.p10), b: fmt(f.p90), p: fmt(f.pct, 0), k: f.below, n: f.yrs }))}</dd>
      <dt>${esc(T('Its range in 2011-2025'))}</dt><dd>${esc(T('{lo} m ({lod}) to {hi} m ({hid})', { lo: fmt(r.lo), lod: r.lo_date, hi: fmt(r.hi), hid: r.hi_date }))}</dd>
      <dt>${esc(T('Lowest on record'))}</dt><dd>${esc(T('{v} m on {d} (since {m0})', { v: fmt(r.rec_lo), d: r.rec_lo_date, m0: r.m0 }))}</dd></dl>
      <p class="uh-links"><a href="index.html#l=reservoirs"><span class="ms-icon" aria-hidden="true">map</span>${esc(T('See it on the map'))}</a>${r.aaa ? `<a href="${AAA_PAGE}" target="_blank" rel="noopener"><span class="ms-icon" aria-hidden="true">open_in_new</span>${esc(T('AAA\'s alert level for this reservoir'))}</a>` : ''}</p>`;
    chartRecent(r, f);
    chartSameMonth(r, f);
    chartMonthly(r);
  }

  // ── charts: one axis each, thin marks, a hover tooltip on every chart ──
  const tip = () => $('#rvTip');
  function hover(svg, pts, text) {   // pts: [[x, y, data]]; the nearest point by x answers
    const dot = svg.querySelector('.hov');
    const move = (e) => {
      const b = svg.getBoundingClientRect(), vx = (e.clientX - b.left) / b.width * svg.viewBox.baseVal.width;
      let best = null; for (const p of pts) if (!best || Math.abs(p[0] - vx) < Math.abs(best[0] - vx)) best = p;
      if (!best) return;
      dot.setAttribute('cx', best[0]); dot.setAttribute('cy', best[1]); dot.style.display = '';
      const t = tip(); t.innerHTML = text(best[2]); t.hidden = false;
      const tw = t.offsetWidth; t.style.left = Math.min(innerWidth - tw - 8, Math.max(8, e.clientX + 12)) + 'px'; t.style.top = (e.clientY + window.scrollY - t.offsetHeight - 10) + 'px';
    };
    svg.onpointermove = move; svg.onpointerleave = () => { tip().hidden = true; dot.style.display = 'none'; };
  }
  const axisY = (ys, y, W, L) => ys.map(v => `<line class="grid" x1="${L}" x2="${W - 6}" y1="${y(v)}" y2="${y(v)}"/><text class="tick" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v, v % 1 ? 1 : 0)}</text>`).join('');
  const niceTicks = (lo, hi, n = 4) => { const st = Math.pow(10, Math.floor(Math.log10((hi - lo) / n || 1))), m = [1, 2, 2.5, 5, 10].find(k => (hi - lo) / (k * st) <= n) * st; const out = []; for (let v = Math.ceil(lo / m) * m; v <= hi + 1e-9; v += m) out.push(+v.toFixed(6)); return out; };

  function chartRecent(r, f) {
    const W = 720, H = 240, L = 52, B = 26, n = r.day.length, start = r.d0;
    const band = []; for (let i = 0; i < n; i++) { const yrs = r.wk[weekOf(isoAdd(start, i))].filter(v => v != null); band.push(yrs.length >= 8 ? [quantile(yrs, 0.1), quantile(yrs, 0.9)] : null); }
    const vals = [...r.day.filter(v => v != null), r.now, ...band.flat().filter(v => v != null)];
    let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.06 || 0.5; lo -= pad; hi += pad;
    const x = (i) => L + i / (n - 1) * (W - L - 8), y = (v) => H - B - (v - lo) / (hi - lo) * (H - B - 10);
    const up = [], dn = []; band.forEach((b, i) => { if (b) { up.push(`${x(i).toFixed(1)},${y(b[1]).toFixed(1)}`); dn.unshift(`${x(i).toFixed(1)},${y(b[0]).toFixed(1)}`); } });
    let path = '', pen = false; const pts = [];
    r.day.forEach((v, i) => { if (v == null) { pen = false; return; } path += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; pts.push([x(i), y(v), { d: isoAdd(start, i), v, b: band[i] }]); });
    const ti = Math.min(n - 1, dayIdx(r, f.day)); if (ti >= 0) pts.push([x(ti), y(r.now), { d: f.day, v: r.now, b: band[ti], now: true }]);
    const months = []; for (let i = 0; i < n; i++) { const d = isoAdd(start, i); if (d.endsWith('-01')) months.push([i, d]); }
    const svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T('{name}: daily level over the last {n} days, over its usual range for each week', { name: r.name, n }))}">
      ${axisY(niceTicks(lo, hi), y, W, L)}<polygon class="rv-usual" points="${up.concat(dn).join(' ')}"/>
      <path class="rv-line" d="${path}"/><circle class="rv-now" cx="${x(ti)}" cy="${y(r.now)}" r="4.5"/>
      ${months.filter((m, j) => j % 2 === 0).map(([i, d]) => `<text class="tick" x="${x(i)}" y="${H - 8}" text-anchor="middle">${esc(new Date(d + 'T12:00:00Z').toLocaleString(loc(), { month: 'short', year: '2-digit', timeZone: 'UTC' }))}</text>`).join('')}
      <text class="lab" x="${L}" y="12">${esc(T('m above mean sea level'))}</text><circle class="hov" r="5" style="display:none"/></svg>`;
    $('#rvRecent').innerHTML = svg + `<div class="pm-legend"><span><i class="rv-key-line"></i>${esc(T('Daily level'))}</span><span><i class="rv-key-band"></i>${esc(T('Usual range for the week (10th to 90th percentile, 2011-2025)'))}</span><span><i class="rv-key-now"></i>${esc(T('Latest reading'))}</span></div>`;
    hover($('#rvRecent svg'), pts, (p) => `<b>${esc(p.d)}</b><br>${esc(T('{v} m', { v: fmt(p.v) }))}${p.b ? '<br>' + esc(T('Usual: {a} to {b} m', { a: fmt(p.b[0]), b: fmt(p.b[1]) })) : ''}`);
  }

  function chartSameMonth(r, f) {   // the current month in every year since the reservoir's first month, as dots (a level has no zero to start bars from); this year's is the month so far
    const m = Number(f.day.slice(5, 7)), y0 = Number(r.m0.slice(0, 4)), m0 = Number(r.m0.slice(5, 7)), yNow = Number(f.day.slice(0, 4));
    const pts = []; for (let y = y0; y < yNow; y++) { const i = (y - y0) * 12 + (m - m0); const v = i >= 0 && i < r.mon.length ? r.mon[i] : null; if (v != null) pts.push([y, v]); }
    const sofar = []; for (let i = 0; i < r.day.length; i++) { const d = isoAdd(r.d0, i); if (d.slice(0, 7) === f.day.slice(0, 7) && r.day[i] != null) sofar.push(r.day[i]); }
    const cur = sofar.length ? sofar.reduce((a, b) => a + b, 0) / sofar.length : r.now; pts.push([yNow, cur]);
    const W = 720, H = 220, L = 52, B = 26, ys = pts.map(p => p[1]).concat(r.lo, r.hi); let lo = Math.min(...ys), hi = Math.max(...ys); const pad = (hi - lo) * 0.08 || 0.5; lo -= pad; hi += pad;
    const n = yNow - y0 + 1, bw = (W - L - 8) / n, x = (yr) => L + (yr - y0 + 0.5) * bw, y = (v) => H - B - (v - lo) / (hi - lo) * (H - B - 10);
    const dots = pts.map(([yr, v]) => `<circle class="${yr === yNow ? 'rv-dot now' : 'rv-dot'}" cx="${x(yr).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${yr === yNow ? 6 : 4.5}"/>`).join('');
    const yrTicks = pts.filter(([yr]) => (yr % 5 === 0 && yNow - yr >= 3) || yr === yNow).map(([yr]) => `<text class="tick" x="${x(yr)}" y="${H - 8}" text-anchor="middle">${yr}</text>`).join('');
    const ref = `<line class="rv-ref" x1="${L}" x2="${W - 6}" y1="${y(r.lo)}" y2="${y(r.lo)}"/><text class="lab" x="${W - 8}" y="${y(r.lo) - 4}" text-anchor="end">${esc(T('lowest 2011-2025: {v} m', { v: fmt(r.lo) }))}</text>`;
    $('#rvSame').innerHTML = `<h3 class="rv-h3">${esc(T('{month} in every year since {y0}', { month: monthName(m), y0 }))}</h3><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T('{name}: mean level in {month} of each year since {y0}; the last dot is this month so far', { name: r.name, month: monthName(m), y0 }))}">${axisY(niceTicks(lo, hi), y, W, L)}${ref}${dots}${yrTicks}<text class="lab" x="${L}" y="12">${esc(T('m above mean sea level'))}</text><circle class="hov" r="7" style="display:none"/></svg>
      <p class="pm-small">${esc(T('Each dot is the mean level of the month; this year\'s (larger, darker) is the month so far. A missing year had fewer than 15 days of readings that month.'))}</p>`;
    hover($('#rvSame svg'), pts.map(([yr, v]) => [x(yr), y(v), { yr, v }]), (p) => `<b>${esc(monthName(m))} ${p.yr}</b><br>${esc(T('{v} m', { v: fmt(p.v) }))}`);
  }

  function chartMonthly(r) {   // the whole history, month by month, with its 2011-2025 range marked
    const W = 720, H = 220, L = 52, B = 26, n = r.mon.length, y0 = Number(r.m0.slice(0, 4)), mo0 = Number(r.m0.slice(5, 7)) - 1;
    const vals = r.mon.filter(v => v != null).concat(r.lo, r.hi); let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.06 || 0.5; lo -= pad; hi += pad;
    const x = (i) => L + i / Math.max(1, n - 1) * (W - L - 8), y = (v) => H - B - (v - lo) / (hi - lo) * (H - B - 10);
    let path = '', pen = false; const pts = [];
    r.mon.forEach((v, i) => { if (v == null) { pen = false; return; } path += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; const yr = y0 + Math.floor((mo0 + i) / 12), mm = (mo0 + i) % 12 + 1; pts.push([x(i), y(v), { yr, mm, v }]); });
    const yrTicks = []; for (let i = 0; i < n; i++) { const yr = y0 + Math.floor((mo0 + i) / 12); if ((mo0 + i) % 12 === 0 && yr % 5 === 0) yrTicks.push(`<text class="tick" x="${x(i)}" y="${H - 8}" text-anchor="middle">${yr}</text>`); }
    $('#rvMonthly').innerHTML = `<h3 class="rv-h3">${esc(T('Every month since {m0}', { m0: r.m0 }))}</h3><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T('{name}: mean level of every month since {m0}', { name: r.name, m0: r.m0 }))}">${axisY(niceTicks(lo, hi), y, W, L)}
      <line class="rv-ref" x1="${L}" x2="${W - 6}" y1="${y(r.lo)}" y2="${y(r.lo)}"/><text class="lab" x="${W - 8}" y="${y(r.lo) - 4}" text-anchor="end">${esc(T('lowest 2011-2025: {v} m', { v: fmt(r.lo) }))}</text>
      <path class="rv-line" d="${path}"/>${yrTicks.join('')}<text class="lab" x="${L}" y="12">${esc(T('m above mean sea level'))}</text><circle class="hov" r="5" style="display:none"/></svg>`;
    hover($('#rvMonthly svg'), pts, (p) => `<b>${esc(monthName(p.mm))} ${p.yr}</b><br>${esc(T('{v} m', { v: fmt(p.v) }))}`);
  }

  // ── Puerto Rico over time: AAA's reservoirs below their usual level for the month (10th percentile of the same month in 2011-2025), month by month ──
  function renderHistory() {
    if ($('#rvPR').dataset.done) return;
    const aaa = D.reservoirs.filter(r => r.aaa), [Y0, Y1] = D.years;
    const ref = aaa.map(r => { const y0 = +r.m0.slice(0, 4), mo0 = +r.m0.slice(5, 7) - 1, p10 = []; for (let m = 0; m < 12; m++) { const xs = []; for (let y = Y0; y <= Y1; y++) { const i = (y - y0) * 12 + m - mo0; if (i >= 0 && i < r.mon.length && r.mon[i] != null) xs.push(r.mon[i]); } p10.push(xs.length >= 8 ? quantile(xs, 0.1) : null); } return { r, y0, mo0, p10 }; });
    const start = 1995, last = D.vintage.slice(0, 7), months = [];
    for (let y = start, m = 0; `${y}-${String(m + 1).padStart(2, '0')}` <= last; m === 11 ? (y++, m = 0) : m++) {
      let low = 0, n = 0;
      for (const a of ref) { const i = (y - a.y0) * 12 + m - a.mo0; const v = i >= 0 && i < a.r.mon.length ? a.r.mon[i] : null; if (v == null || a.p10[m] == null) continue; n++; if (v < a.p10[m]) low++; }
      months.push({ y, m: m + 1, low, n });
    }
    const W = 720, H = 220, L = 40, B = 26, N = months.length, bw = (W - L - 8) / N, x = (i) => L + i * bw, y = (v) => H - B - v / 100 * (H - B - 10);
    const bars = months.map((d, i) => d.n ? `<rect class="rv-bar low" x="${x(i).toFixed(1)}" y="${y(d.low / d.n * 100).toFixed(1)}" width="${Math.max(1, bw - 0.6).toFixed(2)}" height="${(H - B - y(d.low / d.n * 100)).toFixed(1)}"/>` : '').join('');
    const ticks = months.map((d, i) => d.m === 1 && d.y % 5 === 0 ? `<text class="tick" x="${x(i)}" y="${H - 8}" text-anchor="middle">${d.y}</text>` : '').join('');
    $('#rvPR').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T('Share of AAA\'s reservoirs below their usual level for the month, each month since {y}', { y: start }))}">${axisY([0, 25, 50, 75, 100], y, W, L)}${bars}${ticks}<text class="lab" x="${L}" y="12">${esc(T('% of AAA\'s reservoirs with data'))}</text><circle class="hov" r="0" style="display:none"/></svg>`;
    hover($('#rvPR svg'), months.map((d, i) => [x(i) + bw / 2, y(d.n ? d.low / d.n * 100 : 0), d]), (d) => `<b>${esc(monthName(d.m))} ${d.y}</b><br>${esc(T('{low} of {n} reservoirs below their usual level for the month', { low: d.low, n: d.n }))}`);
    const worst = months.filter(d => d.n >= 10).sort((a, b) => b.low / b.n - a.low / a.n).slice(0, 3);
    $('#rvPRread').textContent = T('The months with the largest share below usual: {list}.', { list: worst.map(d => T('{month} {y} ({low} of {n})', { month: monthName(d.m), y: d.y, low: d.low, n: d.n })).join('; ') });
    $('#rvPR').dataset.done = '1';
  }

  root.ReservoirsPage = { figures, quantile, weekOf };
})(typeof window !== 'undefined' ? window : globalThis);
