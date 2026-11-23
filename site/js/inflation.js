/* PR Data Observatory: the Inflation page (inflation.html, Knowledge Area, Economy; HANDOFF decision 95, docs/inflation-plan-2026-11.md).
   Loads data/inflation.json (inflation.py): the consumer price indexes of Puerto Rico (DTRH) and the United States (BLS CPI-U), their 12-month rates
   since 2000, the projection to five years ahead with 80% and 95% bands (the Cleveland Fed's expected US inflation; the bands are the method's own past
   errors), the backtest, the 8 major groups, household income and Social Security's adjustments. Draws the charts as SVG, the tables, the CSV files and
   the budget calculator. Every visible string goes through T(): its Spanish is in i18n_src/es/inflation.json, written by
   docs/analysis/inflation-2026-11/make_page.py. The chart's start and bands are kept in the address (#from=2000&bands=pr). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc && doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 1) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const usd = (v, d = 0) => v == null || !isFinite(v) ? '—' : '$' + fmt(v, d);
  const esc_ = (s) => (typeof esc === 'function' ? esc(s) : String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
  const C = { pr: '#2A2E2E', us: '#205D7B', grid: '#e4e7ec', muted: '#5b6475' };   // palettes.js LINES: Puerto Rico first (charcoal), then blue
  const GROUP = { food: 'Food and beverages', housing: 'Housing', apparel: 'Apparel', transport: 'Transportation', medical: 'Medical care', recreation: 'Recreation', educom: 'Education and communication', other: 'Other goods and services' };
  const S = { from: 2000, bands: 'pr' };
  let D;

  // ── month arithmetic: 'YYYY-MM' ⇄ a month count ──
  const mi = (k) => { const [y, m] = k.split('-').map(Number); return y * 12 + m - 1; };
  const mk = (i) => `${Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, '0')}`;
  const monthName = (k, style = 'long') => { const [y, m] = k.split('-').map(Number); return new Intl.DateTimeFormat(loc(), { month: style, year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(y, m - 1, 15))); };

  /** The history and projection as one list of {k, pr, us, prP, usP, band...} by month. */
  function series(d) {
    const out = new Map(), s0 = mi(d.monthly.start);
    d.monthly.pr_yoy.forEach((v, i) => { out.set(s0 + i, { k: mk(s0 + i), pr: v, us: d.monthly.us_yoy[i] }); });
    const put = (rows, who) => rows.forEach(([k, c, l8, h8, l9, h9]) => { const i = mi(k); const r = out.get(i) || { k }; Object.assign(r, { [who + 'P']: c, [who + 'l8']: l8, [who + 'h8']: h8, [who + 'l9']: l9, [who + 'h9']: h9 }); out.set(i, r); });
    put(d.projection.pr_path, 'pr'); put(d.projection.us_path, 'us');
    // join each projection to the last observed month so the dashed line starts where the solid one ends
    for (const who of ['pr', 'us']) {
      const o = out.get(mi(d.projection.origin[who]));
      if (o && o[who] != null) Object.assign(o, { [who + 'P']: o[who], [who + 'l8']: o[who], [who + 'h8']: o[who], [who + 'l9']: o[who], [who + 'h9']: o[who] });
    }
    return [...out.entries()].sort((a, b) => a[0] - b[0]).map(([i, r]) => Object.assign(r, { i }));
  }

  /** The cost now (by group and in total) of a monthly budget spent in month `start`, using the 2000-01 basket weights updated by each group's
   *  prices to that month (a Laspeyres basket). groups: [{key, weight, pr_index from 2007-01}]. */
  function budget(groups, start, amount, first = '2007-01') {
    const s = mi(start) - mi(first), last = groups[0].pr_index.length - 1;
    if (s < 0 || s > last) return null;
    const raw = groups.map(g => g.weight * g.pr_index[s] / 100), tot = raw.reduce((a, b) => a + b, 0);
    const rows = groups.map((g, j) => { const then = amount * raw[j] / tot, now = then * g.pr_index[last] / g.pr_index[s]; return { key: g.key, then, now }; });
    return { rows, then: amount, now: rows.reduce((a, r) => a + r.now, 0) };
  }

  /** Puerto Rico's adjustment of a benefit: the product of the cost-of-living adjustments effective in December of the years after `from`. */
  const colaFactor = (rows, fromYear, toYear) => rows.filter(r => r.year >= fromYear && r.year <= toYear).reduce((f, r) => f * (1 + r.pct / 100), 1);

  /** What a yearly income that did not rise can buy after prices go from pThen to pNow: what it buys at the old prices, the share of buying power
   *  lost, the income needed now to buy the same, and the raise that takes. */
  const lostPower = (income, pThen, pNow) => {
    const keeps = income * pThen / pNow, needed = income * pNow / pThen;
    return { keeps, lost: income - keeps, pct: 100 * (1 - pThen / pNow), needed, raise: needed - income };
  };

  if (doc && $('#inMain')) fetchJson('data/inflation.json').then((d) => { D = d; start(); }, (e) => {
    $('#inMain').innerHTML = `<p class="pm-p">${esc_(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    const f = Number(h.get('from')); if ([2000, 2010, 2020].includes(f)) S.from = f;
    if (['pr', 'us', 'both', 'none'].includes(h.get('bands'))) S.bands = h.get('bands');
  }
  function writeHash() {
    const h = new URLSearchParams(location.hash.slice(1)); h.set('from', S.from); h.set('bands', S.bands);
    history.replaceState(null, '', '#' + h.toString());
  }

  // ── 1. The headline chart: 12-month inflation, history and projection ──
  function drawMain() {
    const rows = series(D).filter(r => r.i >= S.from * 12);
    const W = 900, H = 400, L = 52, R = 18, Tp = 16, B = 40;
    const vals = rows.flatMap(r => [r.pr, r.us, r.prP, r.usP, ...(S.bands === 'none' ? [] : [S.bands !== 'us' ? r.prl9 : null, S.bands !== 'us' ? r.prh9 : null, S.bands !== 'pr' ? r.usl9 : null, S.bands !== 'pr' ? r.ush9 : null])]).filter(v => v != null);
    const y0 = Math.floor(Math.min(0, ...vals)), y1 = Math.ceil(Math.max(...vals));
    const i0 = rows[0].i, i1 = rows[rows.length - 1].i;
    const X = (i) => L + (i - i0) / (i1 - i0) * (W - L - R), Y = (v) => Tp + (y1 - v) / (y1 - y0) * (H - Tp - B);
    let s = '';
    const step = y1 - y0 > 12 ? 2 : 1;
    for (let v = y0; v <= y1; v += step) s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? '#8c8e8e' : C.grid}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${esc_(pct(v, 0))}</text>`;
    const yStep = S.from === 2000 ? 5 : S.from === 2010 ? 2 : 1;
    for (let y = Math.ceil(i0 / 12); y * 12 <= i1; y++) if (y % yStep === 0) s += `<line x1="${X(y * 12)}" x2="${X(y * 12)}" y1="${H - B}" y2="${H - B + 4}" stroke="${C.muted}"/><text x="${X(y * 12)}" y="${H - B + 17}" text-anchor="middle" class="tick">${y}</text>`;
    const o = mi(D.projection.origin.pr);
    s += `<rect x="${X(o)}" y="${Tp}" width="${W - R - X(o)}" height="${H - Tp - B}" fill="#f6f7f9"/>`;
    s += `<text x="${X(o) + 6}" y="${Tp + 13}" class="axis">${esc_(T('Projection'))}</text>`;
    const area = (who, lo, hi, op) => { const pts = rows.filter(r => r[who + lo] != null); if (!pts.length) return ''; return `<path d="M${pts.map(r => `${X(r.i).toFixed(1)},${Y(r[who + hi]).toFixed(1)}`).join('L')}L${pts.slice().reverse().map(r => `${X(r.i).toFixed(1)},${Y(r[who + lo]).toFixed(1)}`).join('L')}Z" fill="${C[who]}" fill-opacity="${op}" stroke="none"/>`; };
    for (const who of ['us', 'pr']) if (S.bands === who || S.bands === 'both') s += area(who, 'l9', 'h9', 0.08) + area(who, 'l8', 'h8', 0.14);
    const line = (key, color, dash) => { let d = '', pen = false; rows.forEach(r => { const v = r[key]; if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(r.i).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; }); return `<path d="${d}" fill="none" stroke="${color}" stroke-width="${dash ? 2 : 1.8}"${dash ? ' stroke-dasharray="5 4"' : ''}/>`; };
    s += line('us', C.us) + line('pr', C.pr) + line('usP', C.us, true) + line('prP', C.pr, true);
    s += `<line id="inRule" x1="0" x2="0" y1="${Tp}" y2="${H - B}" stroke="${C.muted}" stroke-dasharray="2 3" visibility="hidden"/><g id="inTip" visibility="hidden"><rect rx="6" fill="#fff" stroke="#c9ced8"/><text class="lab"></text></g>`;
    s += `<rect id="inHit" x="${L}" y="${Tp}" width="${W - L - R}" height="${H - Tp - B}" fill="transparent"/>`;
    const last = D.headline;
    const label = T('Line chart: 12-month inflation in Puerto Rico and the United States from {from} to {to}, then the projection to {end} with bands. Latest: Puerto Rico {pr}, United States {us}.', { from: S.from, to: monthName(D.latest.pr), end: monthName(D.projection.end), pr: pct(last.pr_yoy), us: pct(last.us_yoy) });
    $('#inMain').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc_(label)}">${s}</svg>`;
    const svg = $('#inMain svg'), hit = $('#inHit'), tip = $('#inTip'), rule = $('#inRule');
    const show = (ev) => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY; const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      const i = Math.round(i0 + (p.x - L) / (W - L - R) * (i1 - i0)), r = rows.find(x => x.i === i); if (!r) return;
      const lines = [monthName(r.k, 'short')];
      if (r.pr != null) lines.push(`${T('Puerto Rico')}: ${pct(r.pr)}`); else if (r.prP != null) lines.push(`${T('Puerto Rico')}: ${pct(r.prP)} (${pct(r.prl8)} – ${pct(r.prh8)})`);
      if (r.us != null) lines.push(`${T('United States')}: ${pct(r.us)}`); else if (r.usP != null) lines.push(`${T('United States')}: ${pct(r.usP)} (${pct(r.usl8)} – ${pct(r.ush8)})`);
      const t = tip.querySelector('text'); t.innerHTML = lines.map((l, j) => `<tspan x="10" dy="${j ? 16 : 18}"${j ? '' : ' font-weight="600"'}>${esc_(l)}</tspan>`).join('');
      const w = Math.max(...lines.map(l => l.length)) * 6.6 + 20, h = lines.length * 16 + 12, x = X(i) + 12 + w > W ? X(i) - w - 12 : X(i) + 12;
      tip.querySelector('rect').setAttribute('width', w); tip.querySelector('rect').setAttribute('height', h); tip.setAttribute('transform', `translate(${x},${Tp + 20})`);
      rule.setAttribute('x1', X(i)); rule.setAttribute('x2', X(i)); rule.setAttribute('visibility', 'visible'); tip.setAttribute('visibility', 'visible');
    };
    hit.addEventListener('mousemove', show);
    hit.addEventListener('mouseleave', () => { rule.setAttribute('visibility', 'hidden'); tip.setAttribute('visibility', 'hidden'); });
  }

  // ── 2. Inflation by year: calendar-year averages, history and projection ──
  function yearRows() {
    const p = Object.fromEntries(D.projection.pr_years.map(r => [r.year, r])), u = Object.fromEntries(D.projection.us_years.map(r => [r.year, r]));
    const rows = D.annual.filter(r => !p[r.year]).map(r => ({ year: r.year, pr: r.pr, us: r.us, proj: false }));
    Object.keys(p).map(Number).sort().forEach(y => rows.push({ year: y, pr: p[y].c, us: u[y] ? u[y].c : null, proj: true, part: p[y].observed_months, pl: p[y].lo80, ph: p[y].hi80, ul: u[y] && u[y].lo80, uh: u[y] && u[y].hi80 }));
    return rows;
  }
  function drawYears() {
    const rows = yearRows(), W = 900, H = 330, L = 46, R = 12, Tp = 14, B = 34;
    const vals = rows.flatMap(r => [r.pr, r.us, r.pl, r.ph, r.ul, r.uh]).filter(v => v != null);
    const y0 = Math.floor(Math.min(0, ...vals)), y1 = Math.ceil(Math.max(...vals));
    const bw = (W - L - R) / rows.length, Y = (v) => Tp + (y1 - v) / (y1 - y0) * (H - Tp - B);
    let s = '';
    for (let v = y0; v <= y1; v++) s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? '#8c8e8e' : C.grid}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${esc_(pct(v, 0))}</text>`;
    rows.forEach((r, j) => {
      const x = L + j * bw;
      [['pr', r.pr, r.pl, r.ph], ['us', r.us, r.ul, r.uh]].forEach(([who, v, lo, hi], q) => {
        if (v == null) return;
        const bx = x + bw * (0.12 + q * 0.38), w = bw * 0.36;
        s += `<rect x="${bx.toFixed(1)}" y="${Math.min(Y(v), Y(0)).toFixed(1)}" width="${w.toFixed(1)}" height="${Math.abs(Y(v) - Y(0)).toFixed(1)}" fill="${C[who]}" fill-opacity="${r.proj ? 0.35 : 1}"${r.proj ? ` stroke="${C[who]}" stroke-dasharray="2 2"` : ''}><title>${esc_(`${r.year} · ${T(who === 'pr' ? 'Puerto Rico' : 'United States')}: ${pct(v)}${r.proj ? ' (' + T('projected') + ')' : ''}`)}</title></rect>`;
        if (lo != null && hi != null) s += `<line x1="${(bx + w / 2).toFixed(1)}" x2="${(bx + w / 2).toFixed(1)}" y1="${Y(hi).toFixed(1)}" y2="${Y(lo).toFixed(1)}" stroke="${C[who]}" stroke-width="1.2"/>`;
      });
      if (r.year % 5 === 0) s += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - B + 16}" text-anchor="middle" class="tick">${r.year}</text>`;
    });
    $('#inYears').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc_(T('Bar chart: average inflation of each calendar year in Puerto Rico and the United States; lighter bars are projected, with their 80% range'))}">${s}</svg>`;
    const head = `<tr><th scope="col">${esc_(T('Year'))}</th><th scope="col" class="num">${esc_(T('Puerto Rico'))}</th><th scope="col" class="num">${esc_(T('United States'))}</th><th scope="col" class="num">${esc_(T('Difference (points)'))}</th><th scope="col">${esc_(T('Note'))}</th></tr>`;
    const body = rows.slice().reverse().map(r => `<tr><th scope="row">${r.year}</th><td class="num">${esc_(pct(r.pr))}${r.proj && r.pl != null ? `<br><span class="pm-small">${esc_(pct(r.pl))} – ${esc_(pct(r.ph))}</span>` : ''}</td><td class="num">${esc_(pct(r.us))}${r.proj && r.ul != null ? `<br><span class="pm-small">${esc_(pct(r.ul))} – ${esc_(pct(r.uh))}</span>` : ''}</td><td class="num">${r.pr != null && r.us != null ? esc_(fmt(Math.round((r.pr - r.us) * 10) / 10 + 0, 1)) : '—'}</td><td>${r.proj ? esc_(r.part ? T('{n} months observed, the rest projected', { n: r.part }) : T('projected (80% range)')) : ''}</td></tr>`).join('');
    $('#inYearTable').innerHTML = `<table class="pm-table"><caption class="pm-small">${esc_(T('Average of the 12 monthly index values of each year over the year before.'))}</caption><thead>${head}</thead><tbody>${body}</tbody></table>`;
  }

  // ── 3. The 8 major groups ──
  function drawGroups() {
    const g = D.groups, head = ['Group', 'Weight in Puerto Rico\'s basket', 'Puerto Rico, 12 months', 'United States, 12 months', 'Puerto Rico, since January 2020', 'United States, since January 2020'];
    const body = g.map(r => `<tr><th scope="row">${esc_(T(GROUP[r.key]))}</th><td class="num">${esc_(pct(r.weight))}</td><td class="num">${esc_(pct(r.pr_yoy))}</td><td class="num">${esc_(pct(r.us_yoy))}</td><td class="num">${esc_(pct(r.pr_since2020))}</td><td class="num">${esc_(pct(r.us_since2020))}</td></tr>`).join('');
    $('#inGroups').innerHTML = `<table class="pm-table"><thead><tr>${head.map((h, j) => `<th scope="col"${j ? ' class="num"' : ''}>${esc_(T(h))}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`;
    // since January 2020, a pair of bars per group
    const W = 900, rowH = 30, L = 210, R = 60, H = g.length * rowH + 30;
    const mx = Math.max(...g.flatMap(r => [r.pr_since2020, r.us_since2020])), X = (v) => L + v / mx * (W - L - R);
    let s = '';
    g.forEach((r, j) => {
      const y = 10 + j * rowH;
      s += `<text x="${L - 8}" y="${y + 16}" text-anchor="end" class="lab">${esc_(T(GROUP[r.key]))}</text>`;
      s += `<rect x="${L}" y="${y + 3}" width="${(X(r.pr_since2020) - L).toFixed(1)}" height="10" fill="${C.pr}"/><text x="${(X(r.pr_since2020) + 4).toFixed(1)}" y="${y + 12}" class="val">${esc_(pct(r.pr_since2020, 0))}</text>`;
      s += `<rect x="${L}" y="${y + 14}" width="${(X(r.us_since2020) - L).toFixed(1)}" height="10" fill="${C.us}"/><text x="${(X(r.us_since2020) + 4).toFixed(1)}" y="${y + 23}" class="val">${esc_(pct(r.us_since2020, 0))}</text>`;
    });
    $('#inGroupBars').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc_(T('Bar chart: the rise in prices of each group since January 2020, Puerto Rico and the United States'))}">${s}</svg>`;
  }

  // ── 4. The projection's inputs and the backtest ──
  function drawProjection() {
    const p = D.projection;
    const fw = p.forwards.slice(0, 5).map((f, k) => `<tr><th scope="row">${esc_(T('Year {k} ahead', { k: k + 1 }))}</th><td class="num">${esc_(pct(f, 2))}</td><td class="num">${esc_(pct(p.expected[k], 2))}</td></tr>`).join('');
    $('#inFwd').innerHTML = `<table class="pm-table"><caption class="pm-small">${esc_(T('Cleveland Fed model of {month}', { month: monthName(p.origin.cleveland) }))}</caption><thead><tr><th scope="col">${esc_(T('Horizon'))}</th><th scope="col" class="num">${esc_(T('Expected inflation in that year'))}</th><th scope="col" class="num">${esc_(T('Expected average from now'))}</th></tr></thead><tbody>${fw}</tbody></table>`;
    const NAMES = { us_expected: 'Puerto Rico follows expected US inflation (the method used)', ardl: 'A model of Puerto Rico\'s monthly inflation on US inflation (ARDL)', last12: 'The last 12 months persist', own_mean: 'Puerto Rico\'s own average since 2008', us_plus_gap: 'Expected US inflation plus the last 10 years\' gap' };
    const b = D.backtest, hs = Object.keys(b.count);
    const best = Object.fromEntries(hs.map(h => [h, Math.min(...b.order.map(n => b.rmse[n][h]))]));
    const body = b.order.map(n => `<tr><th scope="row">${esc_(T(NAMES[n]))}</th>${hs.map(h => `<td class="num${b.rmse[n][h] === best[h] ? ' in-best' : ''}">${esc_(fmt(b.rmse[n][h], 2))}</td>`).join('')}</tr>`).join('');
    $('#inBt').innerHTML = `<table class="pm-table"><caption class="pm-small">${esc_(T('Root mean square error, in percentage points of average annual inflation; {n} forecasts from each quarter of {a} to {b}; the smallest in each column is in bold.', { n: b.n_origins, a: b.origins[0].slice(0, 4), b: b.origins[1].slice(0, 4) }))}</caption><thead><tr><th scope="col">${esc_(T('Method'))}</th>${hs.map(h => `<th scope="col" class="num">${esc_(T(h === '1' ? '1 year' : '{h} years', { h }))}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`;
  }

  // ── 5. People and families ──
  function drawIncome() {
    const rows = D.income.rows, W = 900, H = 310, L = 52, R = 120, Tp = 26, B = 34;
    const base = rows[0], idxv = (r, who) => 100 * r[who + '_real'] / base[who + '_real'];
    const vals = rows.flatMap(r => [idxv(r, 'pr'), idxv(r, 'us')]), y0 = Math.floor(Math.min(...vals) / 5) * 5, y1 = Math.ceil(Math.max(...vals) / 5) * 5;
    const a = rows[0].year, z = rows[rows.length - 1].year, X = (y) => L + (y - a) / (z - a) * (W - L - R), Y = (v) => Tp + (y1 - v) / (y1 - y0) * (H - Tp - B);
    let s = '';
    for (let v = y0; v <= y1; v += 5) s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 100 ? '#8c8e8e' : C.grid}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${v}</text>`;
    for (let y = a; y <= z; y++) if (y % 2 === 0) s += `<text x="${X(y)}" y="${H - B + 16}" text-anchor="middle" class="tick">${y}</text>`;
    s += `<text x="${L - 40}" y="12" class="axis">${esc_(T('Median household income after inflation, {a} = 100', { a }))}</text>`;
    for (const who of ['us', 'pr']) {
      let d = '', prev = null;
      rows.forEach(r => { d += `${prev != null && r.year - prev > 1 ? 'M' : (d ? 'L' : 'M')}${X(r.year).toFixed(1)},${Y(idxv(r, who)).toFixed(1)}`; prev = r.year; });
      s += `<path d="${d}" fill="none" stroke="${C[who]}" stroke-width="2"/>` + rows.map(r => `<circle cx="${X(r.year).toFixed(1)}" cy="${Y(idxv(r, who)).toFixed(1)}" r="3" fill="${C[who]}"><title>${esc_(`${r.year} · ${T(who === 'pr' ? 'Puerto Rico' : 'United States')}: ${usd(r[who + '_real'])} (${usd(r[who])} ${T('current dollars')})`)}</title></circle>`).join('');
      const lr = rows[rows.length - 1];
      s += `<text x="${X(lr.year) + 6}" y="${Y(idxv(lr, who)) + 4}" class="val" fill="${C[who]}">${esc_(T(who === 'pr' ? 'Puerto Rico' : 'United States'))}</text>`;
    }
    $('#inIncome').innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc_(T('Line chart: median household income after inflation, {a} = 100, Puerto Rico and the United States, {a} to {z}', { a, z }))}">${s}</svg>`;
    const ref = D.income.ref_year;
    const head = ['Year', 'Puerto Rico, current dollars', 'Puerto Rico, dollars of {y}', 'United States, current dollars', 'United States, dollars of {y}'];
    const body = rows.slice().reverse().map(r => `<tr><th scope="row">${r.year}</th><td class="num">${esc_(usd(r.pr))} <span class="pm-small">± ${esc_(fmt(r.pr_moe, 0))}</span></td><td class="num">${esc_(usd(r.pr_real))}</td><td class="num">${esc_(usd(r.us))} <span class="pm-small">± ${esc_(fmt(r.us_moe, 0))}</span></td><td class="num">${esc_(usd(r.us_real))}</td></tr>`).join('');
    $('#inIncomeTable').innerHTML = `<table class="pm-table"><caption class="pm-small">${esc_(T('Median household income, American Community Survey 1-year; ± is the margin of error at 90% confidence; 2020 has no standard 1-year release. Constant dollars use each place\'s own price index.'))}</caption><thead><tr>${head.map((h, j) => `<th scope="col"${j ? ' class="num"' : ''}>${esc_(T(h, { y: ref }))}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function drawCalc() {
    const amount = Math.max(0, Number($('#inAmt').value) || 0), from = $('#inFrom').value;
    const r = budget(D.groups, from, amount);
    if (!r) { $('#inCalcOut').innerHTML = ''; return; }
    const pj = D.power.pr.proj, last = D.latest.pr;
    const body = r.rows.map(x => `<tr><th scope="row">${esc_(T(GROUP[x.key]))}</th><td class="num">${esc_(usd(x.then, 2))}</td><td class="num">${esc_(usd(x.now, 2))}</td><td class="num">${esc_(pct(100 * (x.now / x.then - 1)))}</td></tr>`).join('');
    const end = r.now * pj.cost / 100, lo = r.now * pj.lo80 / 100, hi = r.now * pj.hi80 / 100;
    $('#inCalcOut').innerHTML = `<div class="in-tiles"><div class="in-tile"><span>${esc_(T('In {month}', { month: monthName(from) }))}</span><b>${esc_(usd(r.then, 2))}</b></div>` +
      `<div class="in-tile"><span>${esc_(T('The same purchases in {month}', { month: monthName(last) }))}</span><b>${esc_(usd(r.now, 2))}</b><small>${esc_(T('{p} more', { p: pct(100 * (r.now / r.then - 1)) }))}</small></div>` +
      `<div class="in-tile"><span>${esc_(T('Projected for {month}', { month: monthName(D.projection.end) }))}</span><b>${esc_(usd(end, 2))}</b><small>${esc_(T('80% range: {lo} to {hi}', { lo: usd(lo, 0), hi: usd(hi, 0) }))}</small></div></div>` +
      `<table class="pm-table"><thead><tr><th scope="col">${esc_(T('Group'))}</th><th scope="col" class="num">${esc_(monthName(from))}</th><th scope="col" class="num">${esc_(monthName(last))}</th><th scope="col" class="num">${esc_(T('Change'))}</th></tr></thead><tbody>${body}</tbody></table>`;
  }

  // Buying power by household income: an income that stays the same, Puerto Rico's index
  const LEVELS = [15000, 25000, 50000, 75000, 100000];
  function drawPower() {
    const inc = Math.max(0, Math.round(Number($('#inInc').value) || 0)), from = $('#inSince').value, last = D.latest.pr;
    const s0 = mi(D.monthly.start), idx = (k) => D.monthly.pr_index[mi(k) - s0], pThen = idx(from), pNow = idx(last);
    const med = D.income.rows[D.income.rows.length - 1], pj = D.power.pr.proj;
    const ahead = (x) => ({ c: x * (1 - 100 / pj.cost), lo: x * (1 - 100 / pj.lo80), hi: x * (1 - 100 / pj.hi80) });
    const r = lostPower(inc, pThen, pNow), e = ahead(inc);
    const tiles = `<div class="in-tiles"><div class="in-tile in-pr"><span>${esc_(T('What {inc} buys today, at the prices of {month}', { inc: usd(inc), month: monthName(from) }))}</span><b>${esc_(usd(r.keeps))}</b><small>${esc_(T('{p} less buying power', { p: pct(r.pct) }))}</small></div>` +
      `<div class="in-tile"><span>${esc_(T('Raise needed to buy the same as in {month}', { month: monthName(from) }))}</span><b>${esc_(usd(r.raise))}</b><small>${esc_(T('{m} a month; an income of {n} a year', { m: usd(r.raise / 12), n: usd(r.needed) }))}</small></div>` +
      `<div class="in-tile"><span>${esc_(T('Buying power lost by {month} if the income stays at {inc}', { month: monthName(D.projection.end), inc: usd(inc) }))}</span><b>${esc_(usd(e.c))}</b><small>${esc_(T('a year, at today\'s prices; 80% range: {lo} to {hi}', { lo: usd(e.lo), hi: usd(e.hi) }))}</small></div></div>`;
    const set = [...new Set([...LEVELS, Math.round(med.pr), inc])].filter(x => x > 0).sort((a, b) => a - b);
    const body = set.map(x => {
      const q = lostPower(x, pThen, pNow), a = ahead(x), me = x === inc;
      const lab = usd(x) + (x === Math.round(med.pr) ? ' ' + T('(median, {y})', { y: med.year }) : '');
      return `<tr${me ? ' class="in-me"' : ''}><th scope="row">${esc_(lab)}</th><td class="num">${esc_(usd(q.keeps))}</td><td class="num">${esc_(usd(q.raise))}</td><td class="num">${esc_(usd(q.raise / 12))}</td><td class="num">${esc_(usd(a.c))}</td></tr>`;
    }).join('');
    const head = [T('Annual household income'), T('Buys today, at the prices of {month}', { month: monthName(from) }), T('Raise needed, a year'), T('A month'), T('More lost by {month}, a year', { month: monthName(D.projection.end) })];
    $('#inPowerOut').innerHTML = tiles + `<div class="card pm-tablebox"><table class="pm-table"><caption class="pm-small">${esc_(T('An income that did not rise since {month}; Puerto Rico\'s consumer price index to {last}. Every income loses the same share, {p}; the row in bold is the income entered.', { month: monthName(from), last: monthName(last), p: pct(r.pct) }))}</caption><thead><tr>${head.map((h, j) => `<th scope="col"${j ? ' class="num"' : ''}>${esc_(h)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function drawCola() {
    const c = D.cola, rows = c.rows;
    $('#inCola').innerHTML = `<table class="pm-table in-cola"><thead><tr><th scope="col">${esc_(T('Effective December of'))}</th>${rows.map(r => `<th scope="col" class="num">${r.year}</th>`).join('')}</tr></thead><tbody><tr><th scope="row">${esc_(T('Adjustment'))}</th>${rows.map(r => `<td class="num">${esc_(pct(r.pct))}</td>`).join('')}</tr></tbody></table>`;
  }

  // ── CSV ──
  function csv() {
    const rows = series(D), q = (v) => v == null ? '' : v;
    const lines = [['month', 'pr_12m_pct', 'us_12m_pct', 'pr_projected', 'pr_lo80', 'pr_hi80', 'pr_lo95', 'pr_hi95', 'us_projected', 'us_lo80', 'us_hi80', 'us_lo95', 'us_hi95'].join(',')];
    rows.forEach(r => lines.push([r.k, q(r.pr), q(r.us), q(r.prP), q(r.prl8), q(r.prh8), q(r.prl9), q(r.prh9), q(r.usP), q(r.usl8), q(r.ush8), q(r.usl9), q(r.ush9)].join(',')));
    const a = doc.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + lines.join('\n')], { type: 'text/csv' })); a.download = 'inflation_pr_us.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function start() {
    readHash();
    $('#inFromSel').value = String(S.from); $('#inBands').value = S.bands;
    $('#inFromSel').addEventListener('change', (e) => { S.from = Number(e.target.value); writeHash(); drawMain(); });
    $('#inBands').addEventListener('change', (e) => { S.bands = e.target.value; writeHash(); drawMain(); });
    $('#inCsv').addEventListener('click', csv);
    const first = mi('2007-01'), last = mi(D.latest.pr);
    const opts = []; for (let i = last; i >= first; i--) if (i % 12 === 0 || i === last) opts.push(`<option value="${mk(i)}">${esc_(monthName(mk(i)))}</option>`);
    $('#inFrom').innerHTML = opts.join(''); $('#inFrom').value = '2020-01';
    $('#inAmt').addEventListener('input', drawCalc); $('#inFrom').addEventListener('change', drawCalc);
    const med = Math.round(D.income.rows[D.income.rows.length - 1].pr), s00 = mi('2000-01');
    const since = []; for (let i = last - 1; i >= s00; i--) if (i % 12 === 0 || i === last - 12) since.push(`<option value="${mk(i)}">${esc_(i === last - 12 ? T('{month} (a year ago)', { month: monthName(mk(i)) }) : monthName(mk(i)))}</option>`);
    $('#inSince').innerHTML = since.join(''); $('#inSince').value = '2020-01';
    $('#inInc').value = String(med);
    $('#inInc').addEventListener('input', drawPower); $('#inSince').addEventListener('change', drawPower);
    $('#inIncReset').addEventListener('click', () => { $('#inInc').value = String(med); drawPower(); });
    drawMain(); drawYears(); drawGroups(); drawProjection(); drawIncome(); drawPower(); drawCalc(); drawCola();
  }

  root.Inflation = { series, budget, colaFactor, lostPower, mi, mk };   // for tests/inflation.test.js
})(typeof window !== 'undefined' ? window : globalThis);
