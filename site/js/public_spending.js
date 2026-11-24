/* PR Data Observatory: the Public spending page (public-spending.html, Knowledge Area; Public spending PR 4, HANDOFF decision 78).
   Loads data/spending_state.json (ogp_budget.py: the Commonwealth budget from OGP's data sheets, by agency, fund, concept of expense and function, one
   column per fiscal year and stage). The reader picks a column; a treemap shows it by function and, on a click, by agency within a function; a dot plot
   sets approved against spent for the year that has both; bars show the funds of every column and the concepts of the chosen one. Island-wide only:
   the budget names no municipio. A fourth section maps the Planning Board's capital projects (PICA, spending_pica.json) by municipio, with the money
   that names no municipio beside the map. A fifth section shows federal money in Puerto Rico (USAspending obligations, spending_federal.json) by
   function, award type and program for the federal fiscal year chosen. After the budget is drawn, js/public_spending_charts.js adds the
   pipeline (proposed, approved, spent by year), the fund-to-function bands and the hex grid of the capital projects map (PR 7), and
   js/public_spending_sectors.js draws section 6, one function across the sources (PR 8). Each data section shows its file's build date, marked
   when it is older than two of its update cycles (data-age, data-cycle in the page). js/public_spending_recovery.js draws section 7, the disaster
   recovery subawards by municipio (spending_cdbgdr.json, PR 9). The choices are kept in the address (#c=2027-approved&f=health&pm=total&pa=..&pg=72127&fy=2025). Every visible string goes through T(): its Spanish is in
   i18n_src/es/public_spending.json, written by docs/analysis/public-spending-2026-11/make_page.py. */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc.querySelector(s);
  const lang = () => (root.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const loc = () => (lang() === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const usd = (v, d = 0) => v == null || !isFinite(v) ? '—' : (v < 0 ? '−$' : '$') + fmt(Math.abs(v), d);   // Puerto Rico writes the sign first in Spanish too ($29.23 mil millones)
  const big = (v) => Math.abs(v) >= 1e9 ? usd(v / 1e9, 2) + ' ' + T('billion') : Math.abs(v) >= 1e6 ? usd(v / 1e6, 1) + ' ' + T('million') : usd(v);
  const pct = (v, d = 0) => fmt(v, d) + (lang() === 'es' ? ' %' : '%');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const NS = 'http://www.w3.org/2000/svg';

  const FUNCTION = { education: 'Education', health: 'Health', public_safety: 'Public safety', transportation: 'Transportation', housing: 'Housing',
    parks_recreation: 'Parks, recreation and culture', environment_natural_resources: 'Environment and natural resources', economic_development: 'Economic development',
    utilities_energy: 'Utilities, energy and communications', social_services: 'Social services', debt_pensions: 'Debt and pensions', general_government: 'General government', other: 'Other' };
  const CONCEPT = { payroll: 'Payroll', purchased_services: 'Purchased and professional services', transfers: 'Transfers, subsidies and contributions',
    capex: 'Capital works and equipment', debt_service: 'Debt service', other: 'Other expenses' };
  const FUND = { general: 'General Fund', federal: 'Federal funds', special: 'Special funds' };
  const STAGE = { actual: 'spent', approved: 'approved', proposed: 'proposed' };
  // Funds in this order: adjacent colours pass the palette checks (light surface; colour-blind separation), and every segment is also labelled
  const FUND_ORDER = ['general', 'federal', 'special'];
  const FUND_COLOR = { general: '#338CB3', federal: '#D17F00', special: '#7A5BA6' };
  const TILE = '#338CB3', TILE_DRILL = '#205D7B';
  const S = { c: null, f: null, pm: 'per', pa: '', pg: null, fy: null, pv: 'map', sx: 'education' };
  let D, PICA, GEO, PROJ, F;
  if (doc) {   // the map's choices are read before either file arrives, because the budget section rewrites the address when it starts
    const p = new URLSearchParams(location.hash.slice(1));
    if (['per', 'total'].includes(p.get('pm'))) S.pm = p.get('pm');
    S.pa = p.get('pa') || '';
    S.pg = /^72\d{3}$/.test(p.get('pg') || '') ? p.get('pg') : null;
    S.fy = /^20\d{2}$/.test(p.get('fy') || '') ? +p.get('fy') : null;
    if (p.get('pv') === 'hex') S.pv = 'hex';
    if (/^[a-z_]+$/.test(p.get('sx') || '')) S.sx = p.get('sx');
  }

  if (doc) fetchJson('data/spending_state.json').then((d) => { D = d; start(); }, (e) => {
    $('#psTree').innerHTML = `<p class="ps-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });
  // The capital projects of the Planning Board's program (PICA) by municipio, with the municipio outlines for the map
  if (doc) Promise.all([fetchJson('data/spending_pica.json'), fetchJson('data/municipios.geojson')]).then(([p, g]) => { PICA = p; GEO = g; startPica(); }, (e) => {
    $('#psMap').innerHTML = `<p class="ps-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  const colKey = (c) => `${c.year}-${c.stage}`;
  const colLabel = (c) => T('FY{year} {stage}', { year: c.year, stage: T(STAGE[c.stage]) });
  const col = () => D.columns.findIndex((c) => colKey(c) === S.c);
  const fn = (i) => D.functions[i], fund = (i) => D.funds[i], concept = (i) => D.concepts[i];
  const agencyName = (a) => `${D.agencies[a]}`;

  function sumBy(ci, key, filter) {
    const out = new Map();
    for (const r of D.rows) {
      if (filter && !filter(r)) continue;
      const k = key(r), v = r[4][ci];
      if (v) out.set(k, (out.get(k) || 0) + v);
    }
    return [...out].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  }

  // ── Squarified treemap (Bruls, Huizing and van Wijk) ──
  function squarify(items, x, y, w, h) {
    const total = items.reduce((s, it) => s + it.v, 0), out = [];
    const scaled = items.map((it) => ({ ...it, a: it.v / total * w * h }));
    let row = [], rect = { x, y, w, h };
    const worst = (r, side) => { const s = r.reduce((t, it) => t + it.a, 0), mx = Math.max(...r.map((it) => it.a)), mn = Math.min(...r.map((it) => it.a)); return Math.max(side * side * mx / (s * s), s * s / (side * side * mn)); };
    const lay = (r) => {
      const s = r.reduce((t, it) => t + it.a, 0);
      if (rect.w >= rect.h) { const cw = s / rect.h; let yy = rect.y; r.forEach((it) => { const ch = it.a / cw; out.push({ ...it, x: rect.x, y: yy, w: cw, h: ch }); yy += ch; }); rect = { x: rect.x + cw, y: rect.y, w: rect.w - cw, h: rect.h }; }
      else { const ch = s / rect.w; let xx = rect.x; r.forEach((it) => { const cw = it.a / ch; out.push({ ...it, x: xx, y: rect.y, w: cw, h: ch }); xx += cw; }); rect = { x: rect.x, y: rect.y + ch, w: rect.w, h: rect.h - ch }; }
    };
    for (const it of scaled) {
      const side = Math.min(rect.w, rect.h);
      if (!row.length || worst(row.concat(it), side) <= worst(row, side)) row.push(it);
      else { lay(row); row = [it]; }
    }
    if (row.length) lay(row);
    return out;
  }

  function el(tag, attrs, parent) { const e = doc.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }

  function drawTree() {
    const ci = col(), box = $('#psTree'), W = Math.max(300, box.clientWidth || 800), H = W < 560 ? 420 : 460;
    const items = S.f
      ? sumBy(ci, (r) => r[0], (r) => fn(r[3]) === S.f).map(([a, v]) => ({ k: a, v, label: agencyName(a) }))
      : sumBy(ci, (r) => fn(r[3])).map(([f, v]) => ({ k: f, v, label: T(FUNCTION[f]) }));
    const total = items.reduce((s, it) => s + it.v, 0);
    box.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'group', 'aria-label': S.f
      ? T('Treemap: {fn}, {col}, by agency', { fn: T(FUNCTION[S.f]), col: colLabel(D.columns[ci]) })
      : T('Treemap: {col}, by function', { col: colLabel(D.columns[ci]) }) }, box);
    for (const t of squarify(items, 0, 0, W, H)) {
      const g = el('g', { class: 'tile', tabindex: '0', role: S.f ? 'img' : 'button',
        'aria-label': T('{label}: {value} ({share} of the total)', { label: t.label, value: big(t.v), share: pct(100 * t.v / total, 1) }) }, svg);
      el('rect', { x: t.x + 1, y: t.y + 1, width: Math.max(0, t.w - 2), height: Math.max(0, t.h - 2), rx: 4, fill: S.f ? TILE_DRILL : TILE }, g);
      el('title', {}, g).textContent = `${t.label}: ${big(t.v)} (${pct(100 * t.v / total, 1)})`;
      if (t.w > 70 && t.h > 34) {
        const lines = wrap(t.label, Math.floor((t.w - 12) / 7.2)), maxLines = Math.max(1, Math.floor((t.h - 26) / 15));
        const tx = el('text', { x: t.x + 7, y: t.y + 18, class: 'tl' }, g);
        lines.slice(0, maxLines).forEach((ln, k) => { const s = el('tspan', { x: t.x + 7, dy: k ? 15 : 0 }, tx); s.textContent = k === maxLines - 1 && lines.length > maxLines ? ln + '…' : ln; });
        const full = `${big(t.v)} · ${pct(100 * t.v / total, 0)}`, fits = (txt) => txt.length * 6.6 <= t.w - 12;   // the value only where it fits the tile
        const val = fits(full) ? full : fits(big(t.v)) ? big(t.v) : fits(pct(100 * t.v / total, 0)) ? pct(100 * t.v / total, 0) : '';
        if (val) el('text', { x: t.x + 7, y: t.y + 18 + 15 * Math.min(lines.length, maxLines), class: 'tv' }, g).textContent = val;
      }
      if (!S.f) {
        const open = () => { S.f = t.k; save(); drawTree(); drawTable(); drawPipeline(); };
        g.addEventListener('click', open);
        g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      }
    }
    $('#psBack').hidden = !S.f;
    $('#psTreeHead').textContent = S.f
      ? T('{fn}: {value}, by agency. Select “All functions” to go back.', { fn: T(FUNCTION[S.f]), value: big(total) })
      : T('{col}: {value}, by function. Select a function to see its agencies.', { col: colLabel(D.columns[ci]), value: big(total) });
  }
  function wrap(s, n) { const out = []; let line = ''; for (const w of String(s).split(/\s+/)) { if ((line + ' ' + w).trim().length > n && line) { out.push(line); line = w; } else line = (line + ' ' + w).trim(); } if (line) out.push(line); return out; }

  function drawTiles() {
    const ci = col(), byFund = new Map(sumBy(ci, (r) => fund(r[1])));
    const total = [...byFund.values()].reduce((s, v) => s + v, 0);
    $('#psTiles').innerHTML = [[T('Total'), total, null]].concat(FUND_ORDER.map((f) => [T(FUND[f]), byFund.get(f) || 0, f]))
      .map(([l, v, f]) => `<div class="ps-tile">${f ? `<i style="background:${FUND_COLOR[f]}" aria-hidden="true"></i>` : ''}<span>${esc(l)}</span><b>${esc(big(v))}</b>${f ? `<small>${esc(pct(100 * v / total, 0))}</small>` : ''}</div>`).join('');
  }

  function drawTable() {
    const ci = col();
    const rows = S.f ? sumBy(ci, (r) => r[0], (r) => fn(r[3]) === S.f).map(([a, v]) => [agencyName(a), v]) : sumBy(ci, (r) => fn(r[3])).map(([f, v]) => [T(FUNCTION[f]), v]);
    const total = rows.reduce((s, r) => s + r[1], 0);
    $('#psTable').innerHTML = `<table class="ps-table"><caption>${esc(S.f ? T('{fn} by agency, {col}', { fn: T(FUNCTION[S.f]), col: colLabel(D.columns[ci]) }) : T('By function, {col}', { col: colLabel(D.columns[ci]) }))}</caption>
      <thead><tr><th scope="col">${esc(S.f ? T('Agency') : T('Function'))}</th><th scope="col">${esc(T('Dollars'))}</th><th scope="col">${esc(T('Share'))}</th></tr></thead><tbody>${
      rows.map(([l, v]) => `<tr><th scope="row">${esc(l)}</th><td>${esc(usd(v))}</td><td>${esc(pct(100 * v / total, 1))}</td></tr>`).join('')}</tbody></table>`;
  }

  // ── Approved against spent: the fiscal years that have both columns ──
  function drawGap() {
    const years = D.columns.filter((c) => c.stage === 'actual' && D.columns.some((d) => d.year === c.year && d.stage === 'approved')).map((c) => c.year);
    const box = $('#psGap');
    if (!years.length) { box.innerHTML = `<p class="ps-p">${esc(T('No fiscal year has both an approved and a spent column yet.'))}</p>`; return; }
    const y = Math.max(...years), ai = D.columns.findIndex((c) => c.year === y && c.stage === 'approved'), si = D.columns.findIndex((c) => c.year === y && c.stage === 'actual');
    const ap = new Map(sumBy(ai, (r) => fn(r[3]))), sp = new Map(sumBy(si, (r) => fn(r[3])));
    const keys = [...new Set([...ap.keys(), ...sp.keys()])].sort((a, b) => (ap.get(b) || 0) - (ap.get(a) || 0));
    const W = Math.max(320, box.clientWidth || 800), narrow = W < 620, LW = narrow ? 0 : 250, RW = narrow ? 0 : 190, rowH = narrow ? 46 : 30, top = 26;
    const max = Math.max(...keys.map((k) => Math.max(ap.get(k) || 0, sp.get(k) || 0)));
    const x0 = LW + 8, x1 = W - RW - 14, X = (v) => x0 + (x1 - x0) * v / max;
    box.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${W} ${top + rowH * keys.length + 8}`, width: '100%', role: 'img',
      'aria-label': T('Dot plot: approved and spent by function, FY{year}. The table below has the figures.', { year: y }) }, box);
    (narrow ? [0, 1] : [0, 0.25, 0.5, 0.75, 1]).forEach((f) => { const xx = X(max * f); el('line', { x1: xx, x2: xx, y1: top - 6, y2: top + rowH * keys.length, class: 'grid' }, svg); el('text', { x: xx, y: top - 10, class: 'tick', 'text-anchor': f === 0 ? 'start' : f === 1 ? 'end' : 'middle' }, svg).textContent = big(max * f); });
    keys.forEach((k, i) => {
      const a = ap.get(k) || 0, s = sp.get(k) || 0, cy = top + rowH * i + (narrow ? 30 : rowH / 2);
      const lab = el('text', { x: narrow ? 0 : LW, y: narrow ? cy - 14 : cy + 4, class: 'lab', 'text-anchor': narrow ? 'start' : 'end' }, svg); lab.textContent = T(FUNCTION[k]);
      el('line', { x1: X(Math.min(a, s)), x2: X(Math.max(a, s)), y1: cy, y2: cy, class: 'link' }, svg);
      const g = el('g', {}, svg);
      el('title', {}, g).textContent = T('{fn}: {spent} spent of {approved} approved ({share})', { fn: T(FUNCTION[k]), spent: big(s), approved: big(a), share: a ? pct(100 * s / a, 0) : '—' });
      el('circle', { cx: X(a), cy, r: 6, class: 'ap' }, g);
      el('circle', { cx: X(s), cy, r: 5, class: 'sp' }, g);
      const t = el('text', { x: narrow ? W : W - 4, y: narrow ? cy - 14 : cy + 4, class: 'val', 'text-anchor': 'end' }, svg);
      t.textContent = a ? T('{share} spent', { share: pct(100 * s / a, 0) }) : T('not approved');
    });
    const A = [...ap.values()].reduce((x, v) => x + v, 0), Sp = [...sp.values()].reduce((x, v) => x + v, 0);
    $('#psGapNote').textContent = T('FY{year}: {spent} spent of {approved} approved ({share}). Hollow dot: approved; filled dot: spent.', { year: y, spent: big(Sp), approved: big(A), share: pct(100 * Sp / A, 0) });
    $('#psGapTable').innerHTML = `<table class="ps-table"><caption>${esc(T('Approved and spent by function, FY{year}', { year: y }))}</caption><thead><tr><th scope="col">${esc(T('Function'))}</th><th scope="col">${esc(T('Approved'))}</th><th scope="col">${esc(T('Spent'))}</th><th scope="col">${esc(T('Spent as a share of approved'))}</th></tr></thead><tbody>${
      keys.map((k) => { const a = ap.get(k) || 0, s = sp.get(k) || 0; return `<tr><th scope="row">${esc(T(FUNCTION[k]))}</th><td>${esc(usd(a))}</td><td>${esc(usd(s))}</td><td>${esc(a ? pct(100 * s / a, 0) : '—')}</td></tr>`; }).join('')}</tbody></table>`;
  }

  // ── After ready (public_spending_charts.js): the pipeline, the fund-to-function bands, the hex grid ──
  const STAGE_COLOR = { proposed: '#BDE0F2', approved: '#5FAFDA', actual: '#205D7B' };
  let HEXP;
  function loadCharts() {   // the Spanish of the after-ready parts (module 'after', es.publicspending.after.js) first; sections 6 and 7, the stage lines and the gap note wait unseen until it is in
    const wait = () => doc.querySelectorAll('main [data-t-wait]'), done = () => wait().forEach((e) => { e.removeAttribute('data-t-wait'); if (root.Core && Core.glossary && Core.glossary.mark) Core.glossary.mark(e); });
    I18N.load('after').then(() => { wait().forEach((e) => I18N.apply(e)); }, (e) => console.error(e)).finally(() => {
      done();
      const s = doc.createElement('script'); s.src = 'js/public_spending_charts.js?v=4';
      s.onload = () => { drawPipeline(); drawSankey(); if (PICA && S.pv === 'hex') drawPica(); PSCharts.basis($('#psBasis'), { D, T, esc, big, pct, FUNCTION }); };
      doc.body.appendChild(s);
      const x = doc.createElement('script'); x.src = 'js/public_spending_sectors.js?v=2'; x.onload = drawSector; doc.body.appendChild(x);
      const v = doc.createElement('script'); v.src = 'js/public_spending_recovery.js?v=4'; v.onload = startRecovery; doc.body.appendChild(v);
      const o = doc.createElement('script'); o.src = 'js/public_spending_outlays.js?v=2'; o.onload = () => root.PSOutlays && PSOutlays.start({ $, T, esc, big, pct, loc, fetchJson, age, FUNCTION }); doc.body.appendChild(o);
      const m = doc.createElement('script'); m.src = 'js/public_spending_fema.js?v=1'; m.onload = startFema; doc.body.appendChild(m);
    });
  }
  // ── Section 1: approved and reported spent by agency and fund (public_spending_agencies.js and its Spanish module 'agencies', on first use; decision 112, step 2) ──
  function startAgencies() {
    const sel = $('#psAgFund'); let asked = false; if (!sel) return;
    FUND_ORDER.forEach((k) => { const o = doc.createElement('option'); o.value = k; o.textContent = T(FUND[k]); sel.appendChild(o); });
    sel.addEventListener('change', () => {
      if (root.PSAgencies) return PSAgencies.show(sel.value);
      if (asked) return; asked = true;
      const go = () => { const s = doc.createElement('script'); s.src = 'js/public_spending_agencies.js?v=2'; s.onload = () => PSAgencies.start({ $, T, esc, big, pct, usd, D, FUND, CONCEPT }, sel.value); doc.body.appendChild(s); };
      I18N.load('agencies').then(go, go);
    });
  }
  // ── Section 9: My municipio (public_spending_municipio.js and its Spanish module 'municipio', on first use; decision 109, step 5) ──
  let muniAsked = false;
  function startMuni() {
    const sel = $('#psMuniPick'); if (!sel || !PICA || sel.options.length > 1) return;
    PICA.geo.ids.map((id, i) => [id, PICA.geo.names[i]]).sort((a, b) => a[1].localeCompare(b[1], loc())).forEach(([id, n]) => { const o = doc.createElement('option'); o.value = id; o.textContent = n; sel.appendChild(o); });
    sel.addEventListener('change', () => {
      if (root.PSMuni) return PSMuni.show(sel.value);
      if (muniAsked) return; muniAsked = true;
      const go = () => { const s = doc.createElement('script'); s.src = 'js/public_spending_municipio.js?v=4'; s.onload = () => PSMuni.start({ $, T, esc, big, pct, loc, fetchJson }, sel.value); doc.body.appendChild(s); };
      I18N.load('municipio').then(go, go);
    });
  }
  // ── Section 8: FEMA Public Assistance by stage and age (public_spending_fema.js), once the module and the municipio outlines are here ──
  let femaStarted = false;
  function startFema() {
    if (femaStarted || !root.PSFema || !GEO) return;
    femaStarted = true;
    PSFema.start({ $, T, esc, big, usd, pct, loc, fetchJson, age, proj: () => { if (!PROJ) projectGeo(); return PROJ; } });
  }
  // ── Section 7: disaster recovery subawards by municipio (public_spending_recovery.js), once the module and the municipio outlines are here ──
  let recStarted = false;
  function startRecovery() {
    if (recStarted || !root.PSRecovery || !GEO) return;
    recStarted = true;
    PSRecovery.start({ $, T, esc, big, usd, pct, loc, fetchJson, age, proj: () => { if (!PROJ) projectGeo(); return PROJ; } });
  }
  // ── Section 6: one function across the budget, federal money and capital projects (public_spending_sectors.js) ──
  function startSector() {
    const sel = $('#psSectorPick'), keys = D.functions.filter((k) => k !== 'other');
    if (!keys.includes(S.sx)) S.sx = 'education';
    sel.innerHTML = keys.map((k) => `<option value="${k}">${esc(T(FUNCTION[k]))}</option>`).join('');
    sel.value = S.sx;
    sel.addEventListener('change', () => { S.sx = sel.value; save(); drawSector(); });
  }
  function drawSector() {
    if (!root.PSSectors || !D) return;
    PSSectors.draw($('#psSector'), { D, F, PICA, T, big, usd, pct, esc, fmt, fn, fetchJson, FUNCTION, sector: S.sx });
  }
  // ── Data age: each data section says when its file was built, and marks it when older than two update cycles ──
  function age(file, d) {
    const e = doc.querySelector(`[data-age="${file}"]`); if (!e || !d || !d.built) return;
    const days = (Date.now() - Date.parse(d.built)) / 864e5, old = days > 2 * (+e.dataset.cycle || 365);
    e.classList.toggle('old', old);
    e.textContent = old ? T('Data built {date}: older than two update cycles, a newer release may exist.', { date: d.built }) : T('Data built {date}.', { date: d.built });
  }
  function drawPipeline() {
    if (!root.PSCharts) return;
    const years = [...new Set(D.columns.map((c) => c.year))].sort(), filter = S.f ? (r) => fn(r[3]) === S.f : null;
    const val = (y, st) => { const ci = D.columns.findIndex((c) => c.year === y && c.stage === st); return ci < 0 ? null : sumBy(ci, () => 1, filter).reduce((a, [, v]) => a + v, 0); };
    $('#psBack2').hidden = !S.f;
    $('#psPipeHead').textContent = S.f ? T('{fn}: proposed, approved and spent by fiscal year', { fn: T(FUNCTION[S.f]) }) : T('The whole budget: proposed, approved and spent by fiscal year');
    PSCharts.pipeline($('#psPipe'), { years, stages: ['proposed', 'approved', 'actual'].map((k) => [k, T(STAGE[k]), STAGE_COLOR[k]]), value: val, money: big,
      short: (v) => usd(v / 1e9, 1), yearLabel: (y) => T('FY{year}', { year: y }), label: T('Columns: proposed, approved and spent in each fiscal year. The table below has the figures.') });
    $('#psPipeKey').innerHTML = ['proposed', 'approved', 'actual'].map((k) => `<span><i style="background:${STAGE_COLOR[k]}" aria-hidden="true"></i>${esc(T(STAGE[k]))}</span>`).join('');
    $('#psPipeTable').innerHTML = `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Fiscal year'))}</th>${['proposed', 'approved', 'actual'].map((k) => `<th scope="col">${esc(T(STAGE[k]))}</th>`).join('')}</tr></thead><tbody>${
      years.map((y) => `<tr><th scope="row">${esc(T('FY{year}', { year: y }))}</th>${['proposed', 'approved', 'actual'].map((k) => { const v = val(y, k); return `<td>${esc(v == null ? '—' : usd(v))}</td>`; }).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function drawSankey() {
    if (!root.PSCharts) return;
    const ci = col(), flows = new Map(), byFn = new Map(), byFund = new Map();
    for (const r of D.rows) { const v = r[4][ci]; if (!v) continue; const k = fund(r[1]) + '|' + fn(r[3]); flows.set(k, (flows.get(k) || 0) + v); byFn.set(fn(r[3]), (byFn.get(fn(r[3])) || 0) + v); byFund.set(fund(r[1]), (byFund.get(fund(r[1])) || 0) + v); }
    $('#psFlowHead').textContent = T('{col}: from the fund to the function', { col: colLabel(D.columns[ci]) });
    PSCharts.sankey($('#psFlow'), { left: FUND_ORDER.map((f) => [f, T(FUND[f]), FUND_COLOR[f], Math.max(0, byFund.get(f) || 0)]),
      right: [...byFn].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k, T(FUNCTION[k]), v]),
      flows: [...flows].map(([k, v]) => [...k.split('|'), v]), money: big, label: T('Bands: each fund of the budget chosen above, split by the function it pays for. The table of section 2 has the funds of every budget.') });
    $('#psFlowKey').innerHTML = FUND_ORDER.map((f) => `<span><i style="background:${FUND_COLOR[f]}" aria-hidden="true"></i>${esc(T(FUND[f]))}</span>`).join('');
  }

  // ── Funds of every column (stacked bars, labelled), and concepts of the chosen column ──
  function drawFunds() {
    const box = $('#psFunds'), W = Math.max(320, box.clientWidth || 800), narrow = true, LW = 0, rowH = 50;   // each column's name sits above its bar, at every width
    const cols = D.columns.map((c, i) => ({ c, i })).sort((a, b) => a.c.year - b.c.year || ['actual', 'approved', 'proposed'].indexOf(a.c.stage) - ['actual', 'approved', 'proposed'].indexOf(b.c.stage));
    const max = Math.max(...D.columns.map((c) => c.total)), x0 = LW + 8, x1 = W - 8, X = (v) => (x1 - x0) * v / max;
    box.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${W} ${rowH * cols.length + 6}`, width: '100%', role: 'img', 'aria-label': T('Bars: each column of the budget by fund. The table below has the figures.') }, box);
    cols.forEach(({ c, i }, r) => {
      const by = new Map(sumBy(i, (row) => fund(row[1]))), y = r * rowH + (narrow ? 20 : 6), h = narrow ? 22 : 20;
      el('text', { x: narrow ? 0 : LW, y: narrow ? y - 5 : y + 15, class: 'lab', 'text-anchor': narrow ? 'start' : 'end' }, svg).textContent = `${colLabel(c)} · ${big(c.total)}`;
      let x = x0;
      FUND_ORDER.forEach((f) => {
        const v = by.get(f) || 0, w = X(v); if (!w) return;
        const g = el('g', {}, svg); el('title', {}, g).textContent = `${T(FUND[f])}: ${big(v)} (${pct(100 * v / c.total, 0)})`;
        el('rect', { x: x + 1, y, width: Math.max(0, w - 2), height: h, rx: 3, fill: FUND_COLOR[f] }, g);
        if (w > 44) el('text', { x: x + w / 2, y: y + h / 2 + 4, class: 'seg', 'text-anchor': 'middle' }, g).textContent = pct(100 * v / c.total, 0);
        x += w;
      });
    });
    $('#psFundKey').innerHTML = FUND_ORDER.map((f) => `<span><i style="background:${FUND_COLOR[f]}" aria-hidden="true"></i>${esc(T(FUND[f]))}</span>`).join('');
    $('#psFundTable').innerHTML = `<table class="ps-table"><caption>${esc(T('Each column of the budget by fund'))}</caption><thead><tr><th scope="col">${esc(T('Column'))}</th>${FUND_ORDER.map((f) => `<th scope="col">${esc(T(FUND[f]))}</th>`).join('')}<th scope="col">${esc(T('Total'))}</th></tr></thead><tbody>${
      cols.map(({ c, i }) => { const by = new Map(sumBy(i, (row) => fund(row[1]))); return `<tr><th scope="row">${esc(colLabel(c))}</th>${FUND_ORDER.map((f) => `<td>${esc(usd(by.get(f) || 0))}</td>`).join('')}<td>${esc(usd(c.total))}</td></tr>`; }).join('')}</tbody></table>`;
  }

  function drawConcepts() {
    const ci = col(), items = sumBy(ci, (r) => concept(r[2])), total = items.reduce((s, [, v]) => s + v, 0), max = items.length ? items[0][1] : 1;
    $('#psConceptsHead').textContent = T('{col}, by what the money pays for', { col: colLabel(D.columns[ci]) });
    $('#psConcepts').innerHTML = `<div class="ps-cx">${items.map(([k, v]) => `<details data-k="${k}"><summary class="ps-bars"><span class="l">${esc(T(CONCEPT[k]))}</span><span class="b"><i style="width:${(100 * v / max).toFixed(1)}%"></i></span><span class="v">${esc(big(v))} · ${esc(pct(100 * v / total, 0))}</span></summary><div class="ps-cx-body"></div></details>`).join('')}</div>`;
    $('#psConcepts').querySelectorAll('details').forEach((d) => d.addEventListener('toggle', () => { if (d.open && root.PSCharts && PSCharts.concept) PSCharts.concept(d.lastChild, { D, ci, k: d.dataset.k, T, esc, big, pct, FUNCTION }); }));
  }

  // ── Capital projects by municipio (PICA): a choropleth, the money not placed in a municipio, a ranking ──
  const RAMP = ['#BDE0F2', '#8FCAE8', '#5FAFDA', '#338CB3', '#205D7B'], NONE = '#eef0f3';
  function picaValues() {
    const n = PICA.geo.ids.length, out = new Array(n).fill(0);
    if (S.pa) { const a = PICA.by_agency.find((x) => x[0] === S.pa); for (let i = 0; i < n; i++) out[i] = a ? a[1][i] : 0; }
    else for (const yr of PICA.by_muni) for (let i = 0; i < n; i++) out[i] += yr[i];
    return out;
  }
  const picaUnplaced = () => (S.pa ? (PICA.by_agency.find((x) => x[0] === S.pa) || [0, 0, 0])[2] : PICA.unplaced.reduce((x, v) => x + v, 0));
  const perRes = (v, i) => (PICA.population[i] ? v / PICA.population[i] : null);
  function classes(vals) {   // five classes of equal count among the municipios with projects (quintiles)
    const xs = vals.filter((v) => v > 0).sort((a, b) => a - b);
    if (!xs.length) return [];
    return [1, 2, 3, 4].map((k) => xs[Math.min(xs.length - 1, Math.floor(k * xs.length / 5))]);
  }
  function projectGeo() {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    const each = (g, fn) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).forEach((p) => p.forEach((r) => r.forEach(fn)));
    GEO.features.forEach((f) => each(f.geometry, ([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }));
    const k = Math.cos(18.2 * Math.PI / 180), W = 900, sc = W / ((x1 - x0) * k), H = (y1 - y0) * sc;
    const f = ([x, y]) => `${((x - x0) * k * sc).toFixed(1)},${((y1 - y) * sc).toFixed(1)}`;
    PROJ = { W, H: Math.ceil(H), paths: GEO.features.map((ft) => ({ id: String(ft.properties.GEOID).slice(0, 5),
      d: (ft.geometry.type === 'Polygon' ? [ft.geometry.coordinates] : ft.geometry.coordinates).map((p) => p.map((r) => 'M' + r.map(f).join('L') + 'Z').join('')).join('') })) };
  }
  function drawPica() {
    if (!PROJ) projectGeo();
    const hex = S.pv === 'hex' && root.PSCharts, P = hex ? (HEXP = HEXP || PSCharts.hexMap()) : PROJ;
    const ids = PICA.geo.ids, at = new Map(ids.map((g, i) => [g, i])), raw = picaValues();
    const vals = raw.map((v, i) => (S.pm === 'per' ? perRes(v, i) || 0 : v)), cut = classes(vals);
    const cls = (v) => (v > 0 ? cut.filter((c) => v >= c).length : -1), money = (v) => (S.pm === 'per' ? usd(v) : big(v));
    const lab = S.pm === 'per' ? T('dollars per resident') : T('dollars');
    const said = (i) => `${PICA.geo.names[i]}: ${vals[i] > 0 ? money(vals[i]) : T('no projects')}`;
    let svg = `<svg viewBox="0 0 ${P.W} ${P.H}" width="100%" role="group" aria-label="${esc(T('Map: capital projects of the four-year program by municipio, {measure}', { measure: lab }))}">`;
    for (const p of P.paths) {
      const i = at.get(p.id); if (i == null) continue;
      const c = cls(vals[i]), on = S.pg === p.id;
      svg += `<path class="mu${on ? ' on' : ''}" data-g="${p.id}" tabindex="0" role="button" d="${p.d}" fill="${c < 0 ? NONE : RAMP[c]}" aria-label="${esc(said(i))}"><title>${esc(said(i))}</title></path>`;
      if (hex) svg += `<text class="hx${c >= 3 ? ' dk' : ''}" x="${p.x}" y="${p.y + 5}" text-anchor="middle" aria-hidden="true">${esc(p.abbr)}</text>`;
    }
    $('#psMap').innerHTML = svg + '</svg>';
    $('#psMap').querySelectorAll('path.mu').forEach((el) => {
      const pick = () => { S.pg = S.pg === el.dataset.g ? null : el.dataset.g; save(); drawPica(); };
      el.addEventListener('click', pick);
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
    });
    const bounds = [0].concat(cut);
    $('#psMapKey').innerHTML = `<span><i style="background:${NONE}" aria-hidden="true"></i>${esc(T('no projects'))}</span>` +
      RAMP.map((c, k) => `<span><i style="background:${c}" aria-hidden="true"></i>${esc(k === 0 ? T('under {b}', { b: money(cut[0]) }) : k < 4 ? T('{a} to {b}', { a: money(bounds[k]), b: money(cut[k]) }) : T('{a} or more', { a: money(cut[3]) }))}</span>`).join('');
    // the money that names no single municipio, beside the map, so nothing silently disappears
    const placed = raw.reduce((x, v) => x + v, 0), un = picaUnplaced(), all = placed + un;
    $('#psUnplaced').innerHTML = `<h3>${esc(T('Not placed in a municipio'))}</h3><p class="ps-big">${esc(big(un))}</p><p class="ps-small">${esc(T('{share} of the program{agency}: lines for a region, several municipios, the whole island or no defined place. They are not on the map.', { share: all ? pct(100 * un / all, 0) : '—', agency: S.pa ? ' (' + S.pa + ')' : '' }))}</p>` +
      `<p class="ps-small">${esc(T('On the map: {placed}. Total of the lines read: {all}.', { placed: big(placed), all: big(all) }))}</p>`;
    // the chosen municipio, or the ranking
    const pi = S.pg ? at.get(S.pg) : null;
    if (pi != null) {
      const rows = PICA.by_agency.map(([a, m]) => [a, m[pi]]).filter(([, v]) => v > 0).sort((x, y) => y[1] - x[1]);
      $('#psPlace').innerHTML = `<h3>${esc(PICA.geo.names[pi])}</h3><dl><dt>${esc(T('Four-year program'))}</dt><dd>${esc(big(raw[pi]))}</dd><dt>${esc(T('Per resident'))}</dt><dd>${esc(usd(perRes(raw[pi], pi)))}</dd></dl>` +
        (rows.length ? `<ul class="ps-bars">${rows.map(([a, v]) => `<li><span class="l">${esc(a)}</span><span class="b"><i style="width:${(100 * v / rows[0][1]).toFixed(1)}%"></i></span><span class="v">${esc(big(v))}</span></li>`).join('')}</ul>` : `<p class="ps-small">${esc(T('No projects in this municipio.'))}</p>`) +
        `<button type="button" class="btn" id="psPlaceClose">${esc(T('Show the ranking'))}</button>`;
      $('#psPlaceClose').addEventListener('click', () => { S.pg = null; save(); drawPica(); });
    } else {
      const order = ids.map((g, i) => i).filter((i) => vals[i] > 0).sort((x, y) => vals[y] - vals[x]).slice(0, 10), mx = order.length ? vals[order[0]] : 1;
      $('#psPlace').innerHTML = `<h3>${esc(S.pm === 'per' ? T('Capital projects planned per resident: the ten highest municipios') : T('Capital projects planned, in dollars: the ten highest municipios'))}</h3><ul class="ps-bars">${order.map((i) => `<li><span class="l">${esc(PICA.geo.names[i])}</span><span class="b"><i style="width:${(100 * vals[i] / mx).toFixed(1)}%"></i></span><span class="v">${esc(money(vals[i]))}</span></li>`).join('')}</ul><p class="ps-small">${esc(T('Select a municipio on the map to see its agencies.'))}</p>`;
    }
    $('#psPicaTable').innerHTML = `<table class="ps-table"><caption>${esc(T('Capital projects by municipio, fiscal years {a} to {b}', { a: PICA.years[0], b: PICA.years[PICA.years.length - 1] }))}</caption><thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col">${esc(T('Dollars'))}</th><th scope="col">${esc(T('Per resident'))}</th></tr></thead><tbody>${
      ids.map((g, i) => i).sort((x, y) => PICA.geo.names[x].localeCompare(PICA.geo.names[y], loc())).map((i) => `<tr><th scope="row">${esc(PICA.geo.names[i])}</th><td>${esc(usd(raw[i]))}</td><td>${esc(usd(perRes(raw[i], i)))}</td></tr>`).join('')}</tbody></table>`;
  }
  function startPica() {
    if (!PICA.by_agency.some((a) => a[0] === S.pa)) S.pa = '';
    if (!PICA.geo.ids.includes(S.pg)) S.pg = null;
    const sel = $('#psPicaAgency');
    sel.innerHTML = `<option value="">${esc(T('All agencies'))}</option>` + PICA.by_agency.map(([a]) => `<option value="${esc(a)}">${esc(a)}</option>`).join('');
    sel.value = S.pa; $('#psPicaMeasure').value = S.pm;
    sel.addEventListener('change', () => { S.pa = sel.value; save(); drawPica(); });
    $('#psPicaMeasure').addEventListener('change', (e) => { S.pm = e.target.value; save(); drawPica(); });
    $('#psPicaView').value = S.pv;
    $('#psPicaView').addEventListener('change', (e) => { S.pv = e.target.value; save(); drawPica(); });
    age('spending_pica.json', PICA); drawSector(); startRecovery(); startFema(); startMuni();
    $('#psPicaNote').textContent = T('The program for fiscal years {a} to {b}: {total} in project lines, of the {stated} the program states.', { total: big(PICA.total_usd), a: PICA.years[0], b: PICA.years[PICA.years.length - 1], stated: big(PICA.stated_total_usd) });
    drawPica();
  }

  // ── Federal money in Puerto Rico (spending_federal.json, federal_awards.py): tiles by award type, every year, the chosen year by function ──
  const GROUP = { grants: 'Grants', direct_payments: 'Direct payments', contracts: 'Contracts', loans: 'Loans (cost to the government)', other: 'Insurance and other' };
  const fedYear = () => F.years.indexOf(S.fy);
  const fedTotal = (yi) => F.groups.reduce((s, g) => s + F.totals[g][yi], 0);
  function loadFed() {   // fetched once the budget is drawn: the page is usable before this file arrives
    fetchJson('data/spending_federal.json').then((d) => { F = d; startFed(); }, (e) => {
      $('#psFedFns').innerHTML = `<p class="ps-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }
  function startFed() {
    if (!F.years.includes(S.fy)) S.fy = F.years[F.years.length - 1];
    const sel = $('#psFedYear');
    sel.innerHTML = F.years.slice().reverse().map((y) => `<option value="${y}">${esc(T('Federal FY{year}', { year: y }))}</option>`).join('');
    sel.value = String(S.fy);
    sel.addEventListener('change', () => { S.fy = +sel.value; save(); drawFed(); });
    $('#psFedCsv').addEventListener('click', fedCsv);
    drawFed(); save(); age('spending_federal.json', F); drawSector();
  }
  function drawFed() {
    const yi = fedYear(), total = fedTotal(yi), tg = (g) => F.totals[g][yi];
    const rest = tg('contracts') + tg('loans') + tg('other');
    $('#psFedTiles').innerHTML = [[T('Total'), total, false], [T('Direct payments'), tg('direct_payments'), true], [T('Grants'), tg('grants'), true], [T('Contracts, loans and other'), rest, true]]
      .map(([l, v, sh]) => `<div class="ps-tile"><span>${esc(l)}</span><b>${esc(big(v))}</b>${sh ? `<small>${esc(pct(100 * v / total, 0))}</small>` : ''}</div>`).join('');
    drawFedYears();
    const byFn = new Map();
    F.rows.forEach((r) => byFn.set(F.functions[r[3]], (byFn.get(F.functions[r[3]]) || 0) + r[5][yi]));
    const items = [...byFn].filter(([, v]) => Math.round(v / 1e5) > 0).sort((a, b) => b[1] - a[1]), max = items.length ? items[0][1] : 1;
    $('#psFedHead').textContent = T('Federal fiscal year {year} (October {prev} to September {year}): {total}, by function', { year: S.fy, prev: S.fy - 1, total: big(total) });
    $('#psFedFns').innerHTML = `<ul class="ps-bars">${items.map(([k, v]) => `<li><span class="l">${esc(T(FUNCTION[k]))}</span><span class="b"><i style="width:${(100 * v / max).toFixed(1)}%"></i></span><span class="v">${esc(big(v))} · ${esc(pct(100 * v / total, 0))}</span></li>`).join('')}</ul>`;
    const top = F.rows.filter((r) => !/\*$/.test(r[0])).sort((a, b) => b[5][yi] - a[5][yi]).slice(0, 15);
    $('#psFedTable').innerHTML = `<table class="ps-table"><caption>${esc(T('The 15 largest programs, federal fiscal year {year}', { year: S.fy }))}</caption><thead><tr><th scope="col">${esc(T('Program'))}</th><th scope="col">${esc(T('Award type'))}</th><th scope="col">${esc(T('Function'))}</th><th scope="col">${esc(T('Dollars'))}</th></tr></thead><tbody>${
      top.map((r) => `<tr><th scope="row">${esc(r[0].startsWith('contracts:') ? r[1] : `${r[0]} ${r[1]}`)}</th><td>${esc(T(GROUP[F.groups[r[2]]]))}</td><td>${esc(T(FUNCTION[F.functions[r[3]]]))}</td><td>${esc(usd(r[5][yi]))}</td></tr>`).join('')}</tbody></table>`;
  }
  function drawFedYears() {   // one column per year; the chosen year is darker and every column is labelled
    const box = $('#psFedYears'), W = Math.max(320, box.clientWidth || 800), H = 170, top = 22, base = H - 22, n = F.years.length;
    const tot = F.years.map((y, i) => fedTotal(i)), max = Math.max(...tot), cw = (W - 8) / n, bw = Math.min(56, cw * 0.7);
    box.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': T('Columns: federal money in Puerto Rico in each federal fiscal year. The selector above changes the year.') }, box);
    el('line', { x1: 0, x2: W, y1: base, y2: base, class: 'grid' }, svg);
    F.years.forEach((y, i) => {
      const h = (base - top) * Math.max(0, tot[i]) / max, x = 4 + i * cw + (cw - bw) / 2, on = y === S.fy;
      const g = el('g', {}, svg); el('title', {}, g).textContent = `${T('Federal FY{year}', { year: y })}: ${big(tot[i])}`;
      el('rect', { x, y: base - h, width: bw, height: h, rx: 3, fill: on ? TILE_DRILL : TILE, opacity: on ? 1 : 0.55 }, g);
      el('text', { x: x + bw / 2, y: base - h - 6, class: 'val', 'text-anchor': 'middle' }, g).textContent = usd(tot[i] / 1e9, W < 520 ? 0 : 1);
      el('text', { x: x + bw / 2, y: base + 16, class: 'tick', 'text-anchor': 'middle' }, g).textContent = String(y);
    });
    $('#psFedYearsNote').textContent = T('Billions of dollars obligated in each federal fiscal year, not adjusted for inflation; the darker column is the year chosen. Years before 2017 are less complete: agencies reported less to USAspending before the DATA Act.');
  }
  function fedCsv() {
    const head = ['program', 'name', 'award_type', 'function_category', 'confidence'].concat(F.years.map((y) => `federal_fy${y}_usd`));
    const q = (v) => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v;
    const lines = [head.join(',')].concat(F.rows.map((r) => [r[0], r[1], F.groups[r[2]], F.functions[r[3]], F.confidence[r[4]]].concat(r[5]).map(q).join(',')));
    const a = doc.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' }));
    a.download = 'pr-federal-awards-usaspending.csv'; doc.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function csv() {
    const head = ['agency_code', 'agency', 'fund', 'concept_of_expense', 'function_category'].concat(D.columns.map((c) => `fy${c.year}_${c.stage}_usd`));
    const lines = [head.join(',')].concat(D.rows.map((r) => [r[0], D.agencies[r[0]], fund(r[1]), concept(r[2]), fn(r[3])].concat(r[4]).map((v) => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v).join(',')));
    const a = doc.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' }));
    a.download = 'pr-commonwealth-budget-ogp.csv'; doc.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function save() {
    if (!S.c) return;
    const h = `c=${S.c}` + (S.f ? `&f=${S.f}` : '') + (S.pm !== 'per' ? `&pm=${S.pm}` : '') + (S.pa ? `&pa=${encodeURIComponent(S.pa)}` : '') + (S.pg ? `&pg=${S.pg}` : '') + (S.fy ? `&fy=${S.fy}` : '') + (S.pv === 'hex' ? '&pv=hex' : '') + (S.sx !== 'education' ? `&sx=${S.sx}` : '');
    if (location.hash.slice(1) !== h) history.replaceState(null, '', '#' + h);
  }
  function load() {
    const p = new URLSearchParams(location.hash.slice(1));
    const keys = D.columns.map(colKey), latestApproved = D.columns.filter((c) => c.stage === 'approved').sort((a, b) => b.year - a.year)[0];
    S.c = keys.includes(p.get('c')) ? p.get('c') : colKey(latestApproved || D.columns[0]);
    S.f = D.functions.includes(p.get('f')) ? p.get('f') : null;
  }
  function drawAll() { drawTiles(); drawTree(); drawTable(); drawConcepts(); }

  function start() {
    load();
    const sel = $('#psCol');
    const order = D.columns.slice().sort((a, b) => b.year - a.year || ['approved', 'proposed', 'actual'].indexOf(a.stage) - ['approved', 'proposed', 'actual'].indexOf(b.stage));
    sel.innerHTML = order.map((c) => `<option value="${colKey(c)}">${esc(colLabel(c))}</option>`).join('');
    sel.value = S.c;
    sel.addEventListener('change', () => { S.c = sel.value; save(); drawAll(); drawSankey(); });
    const back = (e) => { S.f = null; save(); drawTree(); drawTable(); drawPipeline(); if (e.currentTarget.id === 'psBack') $('#psTree .tile')?.focus(); };   // the second control, at the stages chart, leaves the reader there
    $('#psBack').addEventListener('click', back); $('#psBack2').addEventListener('click', back);
    $('#psCsv').addEventListener('click', csv);
    drawAll(); drawGap(); startAgencies(); drawFunds(); save(); age('spending_state.json', D); startSector();
    loadFed(); loadCharts();
    let w = root.innerWidth;
    root.addEventListener('resize', () => { if (Math.abs(root.innerWidth - w) < 40) return; w = root.innerWidth; drawTree(); drawGap(); drawFunds(); drawPipeline(); drawSankey(); if (F) drawFedYears(); });
  }

  if (typeof module !== 'undefined') module.exports = { squarify, wrap };
})(typeof window !== 'undefined' ? window : globalThis);
