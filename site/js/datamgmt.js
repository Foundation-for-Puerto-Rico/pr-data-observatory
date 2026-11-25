/* PR Data Observatory: the Data management page (site/data-management.html; docs/data-management.md).
   It reads data/registry.json (registry.py), which holds every published file with its size, records, fields, values and vertices (counted by ledger.py),
   the dates it was first published and last updated (the ledger, dictionary_src/data_ledger.json), the dictionary items that document it and its compliance
   review (the data contract, dictionary_src/datasets.json); the totals and their history; and the counts of what is not published.
   The functions in DM have no page and no language: tests/datamgmt.test.js runs them in Node. */

const DM = (() => {
  const RANK = { open: 0, unstated: 1, cleared: 2, none: 3 };   // the Compliance review column sorts what needs attention first
  const isNum = (v) => typeof v === 'number' && isFinite(v);

  /** Rows sorted on a key, numbers and dates in order and text by locale; a row without a value (documentation, a missing date) is last in both directions;
      ties keep the file names in order. */
  function sortRows(rows, keyOf, dir, collate = (a, b) => (a < b ? -1 : a > b ? 1 : 0)) {
    const s = dir === 'desc' ? -1 : 1;
    return rows.map((r, i) => [keyOf(r), r, i]).sort((a, b) => {
      const ea = a[0] == null || a[0] === '', eb = b[0] == null || b[0] === '';
      if (ea || eb) return ea === eb ? (a[1].file < b[1].file ? -1 : 1) : ea ? 1 : -1;
      const c = isNum(a[0]) && isNum(b[0]) ? a[0] - b[0] : Array.isArray(a[0]) ? cmpList(a[0], b[0], collate) : collate(String(a[0]), String(b[0]));
      return c ? s * c : (a[1].file < b[1].file ? -1 : 1);
    }).map(x => x[1]);
  }
  function cmpList(a, b, collate) {
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      const x = a[i], y = b[i];
      if (x === y) continue;
      if (x == null) return -1;
      if (y == null) return 1;
      const c = isNum(x) && isNum(y) ? x - y : collate(String(x), String(y));
      if (c) return c;
    }
    return 0;
  }
  /** The sort key of the Compliance review column: status (open, license not stated, cleared, not required), then the most recent clearance first. */
  const reviewKey = (f) => { const r = f.review || {}; return [RANK[r.status] ?? 4, r.cleared ? -Number(r.cleared.replace(/-/g, '')) : 0]; };

  /** The totals of the rows shown: records, fields and values over the counted files; bytes and the documenting items over all; the first and last dates. */
  function totalsOf(rows) {
    const sum = (k) => rows.reduce((s, f) => s + (isNum(f[k]) ? f[k] : 0), 0);
    const dates = (k) => rows.map(f => f[k]).filter(Boolean).sort();
    const fp = dates('first_published'), lu = dates('last_updated');
    return { files: rows.length, counted: rows.filter(f => f.kind === 'data').length, records: sum('records'), fields: sum('fields'), values: sum('values'), vertices: sum('vertices'),
      bytes: sum('bytes'), documented_by: sum('documented_by'), first_published: fp[0] || null, last_updated: lu[lu.length - 1] || null };
  }

  /** One CSV cell: quoted when it holds a comma, a quote or a line end; a text that a spreadsheet would run as a formula starts with an apostrophe. */
  function csvCell(v) {
    if (v == null) return '';
    let s = String(v);
    if (typeof v !== 'number' && /^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }
  const csvText = (head, rows) => '﻿' + [head, ...rows].map(r => r.map(csvCell).join(',')).join('\n');

  /** Clean axis ticks from 0 to at least max: steps of 1, 2 or 5 times a power of ten. */
  function ticks(max, n = 4) {
    if (!(max > 0)) return [0, 1];
    const raw = max / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p, step = (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
    const out = [];
    for (let v = 0; v <= max + step * 0.999; v += step) out.push(Math.round(v / step) * step);
    return out;
  }
  /** The path of a step line: a total holds from its date until the next one. */
  function stepPath(pts) {
    return pts.map((p, i) => (i ? `H${p[0].toFixed(1)}V${p[1].toFixed(1)}` : `M${p[0].toFixed(1)},${p[1].toFixed(1)}`)).join('');
  }
  /** Days from the first date, for a time axis of calendar dates (YYYY-MM-DD). */
  const dayNo = (d) => Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)) / 864e5;

  /** The review filter: a flag (federal-grant, counts-only) or a status; "unstated" keeps every file whose license class is unstated, also those with a
      review (their status is open or cleared and they carry the license-unstated flag). */
  function reviewMatch(r, want) {
    r = r || {};
    const flags = r.flags || [];
    if (want === 'federal-grant' || want === 'counts-only') return flags.includes(want);
    if (want === 'unstated') return r.status === 'unstated' || flags.includes('licence-unstated');
    return r.status === want;
  }
  /** The category filter: a file is in a domain when it carries it or one of its sub-domains ("economy" keeps "economy.visitor-economy"); no choice keeps all. */
  function domainMatch(domains, want) {
    return !want || (domains || []).some(d => d === want || d.startsWith(want + '.'));
  }
  /** The choices of the category filter, in the order of the registry's names: every domain that has a file, with how many, and its depth (a sub-domain is 1). */
  function domainOptions(files, names) {
    return Object.keys(names || {}).map(id => ({ id, depth: id.split('.').length - 1, n: files.filter(f => domainMatch(f.domains, id)).length })).filter(o => o.n);
  }
  /** The "Sort by" list: a choice is written "column:direction" ("last_updated:desc" is newest update first). */
  function sortChoice(sort, dir) { return sort + ':' + dir; }
  function sortParse(v) {
    const m = /^([a-z_]+):(asc|desc)$/.exec(v || '');
    return m ? { sort: m[1], dir: m[2] } : null;
  }
  /** The address that opens the map on a file's data (registry.py on_map): its layers switched on (l=) and its first dataset shaded (e=, a Shaded layer of
      the Analysis tab). Null for a file the map does not draw. A key that is not plain letters, digits and "_" is left out: it cannot add a part to the address. */
  function mapHref(m) {
    if (!m) return null;
    const l = String(m.l || '').split(',').filter(k => /^[a-z]+$/.test(k)), e = /^[A-Za-z0-9_]+$/.test(m.e || '') ? m.e : '';
    const parts = [l.length ? 'l=' + l.join(',') : '', e ? 'e=' + e + '.f' : ''].filter(Boolean);
    return parts.length ? 'index.html#' + parts.join('&') : null;
  }
  /** What the growth history says: the measures that never fell, and the largest fall of the size (a file compressed or trimmed). */
  function growthFacts(H) {
    const KEYS = ['files', 'records', 'fields', 'values', 'items'];
    const fell = KEYS.filter(k => H.some((h, i) => i && h[k] != null && H[i - 1][k] != null && h[k] < H[i - 1][k]));
    let drop = null;
    H.forEach((h, i) => { if (i && h.bytes < H[i - 1].bytes && (!drop || H[i - 1].bytes - h.bytes > drop.bytes)) drop = { date: h.date, bytes: H[i - 1].bytes - h.bytes }; });
    return { grew: fell.length === 0, fell, drop };
  }

  return { sortRows, reviewKey, reviewMatch, domainMatch, domainOptions, sortChoice, sortParse, mapHref, growthFacts, totalsOf, csvCell, csvText, ticks, stepPath, dayNo, RANK };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = DM;
else (() => {
  const S = { reg: null, files: [], q: '', dom: '', kind: '', rev: '', sort: 'values', dir: 'desc', measure: 'values' };
  const LANG = I18N.lang;
  const TK = (t) => t;   // translated where it is shown, with T()
  const sizeText = (b) => b == null ? '—' : b >= 1048576 ? fmt(b / 1048576, 1) + ' MB' : fmt(Math.max(1, Math.round(b / 1024))) + ' KB';
  const FLAG = {
    'federal-grant': ['account_balance', TK('Federal grant content')],
    'counts-only': ['visibility_off', TK('Counts only')],
    'licence-unstated': ['help', TK('License not stated')],
    'licensed-not-open': ['lock', TK('Licensed, not open')],
  };
  const REVIEW_TYPE = { pii: TK('personal data'), licence: TK('license'), compliance: TK('compliance') };
  const KIND = { data: TK('Data'), documentation: TK('Documentation'), index: TK('Index') };
  const MEASURES = [['values', TK('Values')], ['records', TK('Records')], ['bytes', TK('Size')], ['files', TK('Files')], ['items', TK('Documented items')]];
  const dname = (id) => { const n = (S.reg.domain_names || {})[id]; return n ? (n[LANG] || n.en) : id; };
  const title = (f) => LANG === 'es' && f.title_es ? f.title_es : f.title;

  // ── The Compliance review column, in words ───────────────────────────────
  // a file takes the most restrictive license class of its sources: "License not stated" and "Licensed, not open" name the sources that set it
  const fromText = (r) => I18N.list((r.licence_from || []).map(x => x[LANG] || x.en));
  const withFrom = (label, r) => (r.licence_from || []).length ? T('{label}: {sources}', { label, sources: fromText(r) }) : label;
  function reviewParts(f) {
    const r = f.review || { status: 'none', flags: [] }, lines = [];
    if (r.status === 'open') for (const o of r.open || []) lines.push(T('Open: {reason}', { reason: o.summary ? (o.summary[LANG] || o.summary.en) : T(REVIEW_TYPE[o.type] || o.type) }));
    else if (r.status === 'cleared') lines.push(r.cleared ? T('Cleared {date}', { date: r.cleared }) : T('Cleared'));
    else if (r.status === 'unstated') lines.push(withFrom(T('License not stated'), r));
    else lines.push(T('Not required'));
    const flags = (r.flags || []).filter(x => !(x === 'licence-unstated' && r.status === 'unstated')).filter(x => FLAG[x])
      .map(x => [x, x === 'licence-unstated' || x === 'licensed-not-open' ? withFrom(T(FLAG[x][1]), r) : T(FLAG[x][1])]);
    return { status: r.status, lines, flags };
  }
  function reviewHtml(f) {
    const p = reviewParts(f), icon = { open: 'pending', cleared: 'check_circle', unstated: 'help', none: '' }[p.status];
    return p.lines.map(l => `<span class="dm-st ${p.status}">${icon ? `<span class="ms-icon" aria-hidden="true">${icon}</span>` : ''}<span>${esc(l)}</span></span>`).join('<br>')
      + (p.flags.length ? `<div class="dm-flags">${p.flags.map(([x, text]) => `<span class="dm-flag"><span class="ms-icon" aria-hidden="true">${FLAG[x][0]}</span>${esc(text)}</span>`).join('')}</div>` : '');
  }
  const reviewText = (f) => { const p = reviewParts(f); return [...p.lines, ...p.flags.map(x => x[1])].join('; '); };

  // ── Columns: label, sort key, cell ────────────────────────────────────────
  const counted = (f, k) => f.kind === 'data' ? `<td class="num">${fmt(f[k])}</td>` : `<td class="num na" title="${esc(T('Documentation and index files are not counted'))}">—</td>`;
  const holds = (f) => {
    const bits = [f.datasets ? Tn(f.datasets, '{n} dataset', '{n} datasets') : '', f.years ? `${f.years[0]}–${f.years[1]}` : '', f.kind !== 'data' && f.items ? Tn(f.items, '{n} entry', '{n} entries') : '', f.kind !== 'data' ? T(KIND[f.kind]) : ''].filter(Boolean);
    const h = DM.mapHref(f.map), n = (f.map || {}).n;   // the files the map draws carry a link to it under their title; the others carry nothing
    const link = h ? `<a class="dm-onmap" href="${esc(h)}"${n > 1 ? ` title="${esc(T('Opens the map with the first of the {n} datasets of this file. The others are in the Analysis tab.', { n: fmt(n) }))}"` : ''} aria-label="${esc(T('Show on the map: {name}', { name: title(f) }))}"><span class="ms-icon" aria-hidden="true">map</span>${esc(T('Show on the map'))}</a>` : '';
    return esc(title(f)) + (bits.length ? ` <small>· ${esc(bits.join(' · '))}</small>` : '') + link;
  };
  const COLS = [
    { k: 'file', label: TK('File'), key: f => f.file, cell: f => `<th scope="row"><a href="data/${esc(f.file)}" download>${esc(f.file).replace(/([_/])/g, '$1<wbr>')}</a></th>`, foot: t => `<th scope="row">${esc(Tn(t.files, 'Total: {n} file', 'Total: {n} files'))}</th>` },
    { k: 'what', label: TK('What it holds'), key: f => title(f), cell: f => `<td class="what">${holds(f)}</td>`, foot: t => `<td class="what"><small>${esc(Tn(t.counted, '{n} counted data file', '{n} counted data files'))}</small></td>` },
    { k: 'domain', label: TK('Domain'), key: f => (f.domains || []).map(dname).join(', '), cell: f => { const d = f.domains || []; return `<td class="dom"${d.length > 1 ? ` title="${esc(d.map(dname).join(', '))}"` : ''}><span class="p">${esc(d.length ? dname(d[0]) : '—')}</span>${d.length > 1 ? ` <small>${esc(T('+{n} more', { n: d.length - 1 }))}</small>` : ''}</td>`; }, foot: () => '<td></td>' },
    { k: 'records', label: TK('Records'), num: true, key: f => f.records, cell: f => counted(f, 'records'), foot: t => `<td class="num">${fmt(t.records)}</td>` },
    { k: 'fields', label: TK('Fields'), num: true, key: f => f.fields, cell: f => counted(f, 'fields'), foot: t => `<td class="num">${fmt(t.fields)}</td>` },
    { k: 'values', label: TK('Values'), num: true, key: f => f.values, cell: f => counted(f, 'values'), foot: t => `<td class="num">${fmt(t.values)}</td>` },
    { k: 'bytes', label: TK('Size'), num: true, key: f => f.bytes, cell: f => `<td class="num" title="${esc(T('{n} bytes', { n: fmt(f.bytes) }))}">${sizeText(f.bytes)}</td>`, foot: t => `<td class="num" title="${esc(T('{n} bytes', { n: fmt(t.bytes) }))}">${sizeText(t.bytes)}</td>` },
    { k: 'first_published', label: TK('First published'), num: true, key: f => f.first_published, cell: f => `<td class="num">${esc(f.first_published || '—')}</td>`, foot: t => `<td class="num">${esc(t.first_published || '—')}</td>` },
    { k: 'last_updated', label: TK('Last updated'), num: true, key: f => f.last_updated, cell: f => `<td class="num"${f.versions > 1 ? ` title="${esc(Tn(f.versions, '{n} version published', '{n} versions published'))}"` : ''}>${esc(f.last_updated || '—')}</td>`, foot: t => `<td class="num">${esc(t.last_updated || '—')}</td>` },
    { k: 'documented_by', label: TK('Documented by'), num: true, key: f => f.documented_by, cell: f => `<td class="num">${f.documented_by ? `<a href="dictionary.html?file=${encodeURIComponent(f.file)}#browse">${esc(Tn(f.documented_by, '{n} item', '{n} items'))}</a>` : '—'}</td>`, foot: t => `<td class="num" title="${esc(T('An item that documents two files counts in each'))}">${esc(Tn(t.documented_by, '{n} item', '{n} items'))}</td>` },
    { k: 'review', label: TK('Compliance review'), key: DM.reviewKey, cell: f => `<td class="rev">${reviewHtml(f)}</td>`, foot: () => '<td></td>' },
  ];

  // ── Summary tiles ─────────────────────────────────────────────────────────
  function renderTiles() {
    const r = S.reg, t = r.totals || {};
    const tile = (v, l, s) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div>${s ? `<div class="s">${esc(s)}</div>` : ''}</div>`;
    $('#dmTiles').innerHTML = [
      tile(fmt(t.files), T('published files'), Tn(t.counted_files, '{n} data file counted', '{n} data files counted')),
      tile(sizeText(r.total_bytes), T('size'), T('{pct}% of the 1 GB GitHub Pages limit', { pct: fmt(r.total_bytes / r.limits.site_bytes * 100, 1) })),
      tile(fmt(t.records), T('records'), T('observation units')),
      tile(fmt(t.values), T('values'), T('data points, in {n} fields', { n: fmt(t.fields) })),
      tile(fmt(t.items), T('documented items'), T('in the data dictionary')),
      tile(t.last_updated || '—', T('last update'), t.first_published ? T('first data published {date}', { date: t.first_published }) : ''),
    ].join('');
    $('#filesLede').textContent = T('{n} files, {size}. Sort with “Sort by” or on any column heading, filter by text, category, kind or review, and download what is shown as CSV. A file name downloads the file; “Documented by” opens its entries in the data dictionary; “Show on the map”, under the title of a file the map draws, opens the map with its data.', { n: fmt(t.files), size: sizeText(r.total_bytes) });
  }

  // ── The files table ───────────────────────────────────────────────────────
  const hay = (f) => norm([f.file, f.title, f.title_es, ...(f.domains || []).map(dname), T(KIND[f.kind] || ''), reviewText(f), (f.review && (f.review.open || []).map(o => o.summary ? o.summary.en + ' ' + o.summary.es : '').join(' ')) || ''].join(' '));
  function shown() {
    const q = norm(S.q).split(/\s+/).filter(Boolean);
    return S.files.filter(f => DM.domainMatch(f.domains, S.dom) && (!S.kind || (S.kind === 'data' ? f.kind === 'data' : f.kind !== 'data'))
      && (!S.rev || DM.reviewMatch(f.review, S.rev))
      && q.every(w => f._hay.includes(w)));
  }
  function renderTable() {
    const col = COLS.find(c => c.k === S.sort) || COLS[0];
    const collate = new Intl.Collator(LANG === 'es' ? 'es-PR' : 'en-US', { sensitivity: 'base', numeric: true }).compare;
    const rows = DM.sortRows(shown(), col.key, S.dir, collate), t = DM.totalsOf(rows);
    const th = (c) => {
      const on = c.k === S.sort, arrow = on ? (S.dir === 'asc' ? '▲' : '▼') : '↕';
      return `<th scope="col"${c.num ? ' class="num"' : ''}${on ? ` aria-sort="${S.dir === 'asc' ? 'ascending' : 'descending'}"` : ''}><button type="button" data-sort="${c.k}">${esc(T(c.label))}<span class="dm-sort" aria-hidden="true">${arrow}</span></button></th>`;
    };
    $('#dmTbl').innerHTML = `<caption class="sr-only">${esc(T('Published data files'))}</caption><thead><tr>${COLS.map(th).join('')}</tr></thead>`
      + `<tbody>${rows.map(f => `<tr${f.kind !== 'data' ? ' class="doc"' : ''}>${COLS.map(c => c.cell(f)).join('')}</tr>`).join('') || `<tr><td colspan="${COLS.length}">${esc(T('No file matches. Clear the search or reset the filters.'))}</td></tr>`}</tbody>`
      + `<tfoot><tr>${COLS.map(c => c.foot(t)).join('')}</tr></tfoot>`;
    const all = S.files.length;
    $('#dmCount').textContent = rows.length === all ? T('{n} files, sorted by {col}', { n: fmt(all), col: T(col.label).toLowerCase() }) : T('{n} of {m} files match, sorted by {col}', { n: fmt(rows.length), m: fmt(all), col: T(col.label).toLowerCase() });
    S.rows = rows;
    const pick = $('#dmSort'), want = DM.sortChoice(S.sort, S.dir);   // the "Sort by" list follows a click on a column heading; an order it does not offer shows "Column heading"
    pick.value = [...pick.options].some(o => o.value === want) ? want : '';
  }
  function downloadCsv() {
    const rows = S.rows || [], t = DM.totalsOf(rows);
    const head = [T('file'), T('title'), T('domains'), T('kind'), T('records'), T('fields'), T('values'), T('vertices'), T('bytes'), T('first published'), T('last updated'), T('versions published'), T('documented by (items)'), T('compliance review'), T('license class'), T('URL')];
    const base = location.href.replace(/[#?].*$/, '').replace(/[^/]*$/, '');
    const body = rows.map(f => [f.file, title(f), (f.domains || []).map(dname).join('; '), T(KIND[f.kind] || ''), f.records, f.fields, f.values, f.vertices, f.bytes, f.first_published, f.last_updated, f.versions, f.documented_by, reviewText(f), f.licence_class, base + 'data/' + f.file]);
    body.push([Tn(t.files, 'Total: {n} file', 'Total: {n} files'), '', '', '', t.records, t.fields, t.values, t.vertices, t.bytes, t.first_published, t.last_updated, '', t.documented_by, '', '', '']);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([DM.csvText(head, body)], { type: 'text/csv;charset=utf-8' }));
    a.download = 'pr_digital_twin_data_files.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  // ── Growth: one measure at a time, a step line with a crosshair ──────────
  const mval = (h, k) => k === 'bytes' ? h.bytes : h[k];
  const mtext = (v, k) => v == null ? '—' : k === 'bytes' ? sizeText(v) : fmt(v);
  function renderMeasure() {
    $('#dmMeasure').innerHTML = MEASURES.map(([k, l]) => `<button type="button" data-measure="${k}" aria-pressed="${k === S.measure}">${esc(T(l))}</button>`).join('');
  }
  function renderChart() {
    const H = (S.reg.history || []).filter(h => mval(h, S.measure) != null), k = S.measure, box = $('#dmChart');
    const label = T((MEASURES.find(m => m[0] === k) || MEASURES[0])[1]);
    if (H.length < 2) { box.innerHTML = `<p class="note">${esc(T('The history needs two dates to draw.'))}</p>`; return; }
    const W = Math.max(320, Math.min(1180, box.clientWidth || 900)), Ht = W < 520 ? 220 : 260, m = { l: W < 520 ? 46 : 64, r: W < 520 ? 70 : 96, t: 12, b: 26 };
    const d0 = DM.dayNo(H[0].date), d1 = DM.dayNo(H[H.length - 1].date) + 1, max = Math.max(...H.map(h => mval(h, k)));
    const yt = DM.ticks(max), ymax = yt[yt.length - 1];
    const x = (d) => m.l + (DM.dayNo(d) - d0) / (d1 - d0) * (W - m.l - m.r), y = (v) => Ht - m.b - v / ymax * (Ht - m.t - m.b);
    const pts = H.map(h => [x(h.date), y(mval(h, k))]), xEnd = x(H[H.length - 1].date) + (W - m.l - m.r) / (d1 - d0);
    const line = DM.stepPath(pts) + `H${xEnd.toFixed(1)}`;
    const area = line + `V${(Ht - m.b).toFixed(1)}H${pts[0][0].toFixed(1)}Z`;
    const yfmt = (v) => k === 'bytes' ? fmt(v / 1048576, 0) + ' MB' : v >= 1e6 ? fmt(v / 1e6, v % 1e6 ? 1 : 0) + 'M' : v >= 1e3 ? fmt(v / 1e3, 0) + 'K' : fmt(v);
    const nX = W < 520 ? 3 : 6, step = Math.max(1, Math.ceil((d1 - d0) / nX)), xt = [];
    for (let dd = d0; dd < d1; dd += step) xt.push(dd);
    const iso = (dd) => new Date(dd * 864e5).toISOString().slice(0, 10), short = (s) => I18N.date(s, { month: 'short', day: 'numeric' });
    const last = H[H.length - 1], lp = pts[pts.length - 1];
    box.innerHTML = `<svg viewBox="0 0 ${W} ${Ht}" role="img" tabindex="0" aria-label="${esc(T('{measure} published, by date: {first} on {d0} to {last} on {d1}. Use the arrow keys to read each date.', { measure: label, first: mtext(mval(H[0], k), k), d0: H[0].date, last: mtext(mval(last, k), k), d1: last.date }))}">
      <g class="grid">${yt.map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>`).join('')}</g>
      <g class="tick">${yt.map(v => `<text x="${m.l - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${esc(yfmt(v))}</text>`).join('')}${xt.map(dd => `<text x="${x(iso(dd)).toFixed(1)}" y="${Ht - 8}" text-anchor="middle">${esc(short(iso(dd)))}</text>`).join('')}</g>
      <path class="ar" d="${area}"/><path class="ln" d="${line}"/>
      <circle class="pt" cx="${xEnd.toFixed(1)}" cy="${lp[1].toFixed(1)}" r="4"/>
      <text class="end-lbl" x="${(xEnd + 9).toFixed(1)}" y="${(lp[1] + 4).toFixed(1)}">${esc(mtext(mval(last, k), k))}</text>
      <line class="xh" id="dmXh" x1="0" x2="0" y1="${m.t}" y2="${Ht - m.b}" visibility="hidden"/>
      <rect id="dmHit" x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${Ht - m.t - m.b}" fill="transparent"/>
    </svg>`;
    $('#dmChartCap').textContent = T('{measure} at the end of each date on which a total changed (Puerto Rico dates). A total holds until the next date. The table below lists every date.', { measure: label });
    const svg = box.querySelector('svg'), xh = svg.querySelector('#dmXh'), tip = $('#dmTip');
    let cur = H.length - 1;
    const show = (i) => {
      cur = Math.max(0, Math.min(H.length - 1, i));
      const h = H[cur], prev = cur ? mval(H[cur - 1], k) : null, v = mval(h, k), px = pts[cur][0];
      xh.setAttribute('x1', px); xh.setAttribute('x2', px); xh.setAttribute('visibility', 'visible');
      const ch = prev == null ? '' : v - prev;
      tip.innerHTML = `<span class="k"></span>${esc(label)}<b>${esc(mtext(v, k))}</b>${esc(h.date)}${ch !== '' ? `<br><small>${esc(ch === 0 ? T('no change in this measure') : T('{sign}{n} since {date}', { sign: ch > 0 ? '+' : '−', n: mtext(Math.abs(ch), k), date: H[cur - 1].date }))}</small>` : ''}`;
      const scale = svg.getBoundingClientRect().width / W, left = px * scale + 14;
      tip.style.left = Math.min(left, svg.getBoundingClientRect().width - 150) + 'px'; tip.style.top = '18px'; tip.classList.add('show');
    };
    const hide = () => { tip.classList.remove('show'); xh.setAttribute('visibility', 'hidden'); };
    svg.addEventListener('pointermove', (e) => {
      const r = svg.getBoundingClientRect(), px = (e.clientX - r.left) / r.width * W;
      let best = 0; pts.forEach((p, i) => { if (p[0] <= px) best = i; });   // a total holds from its date: the readout is the last date at or before the pointer
      show(best);
    });
    svg.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', () => show(cur)); svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', (e) => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); show(cur + (e.key === 'ArrowRight' ? 1 : -1)); } });
  }
  function renderHistory() {
    const H = S.reg.history || [], cols = [['files', T('Files')], ['bytes', T('Size')], ['records', T('Records')], ['fields', T('Fields')], ['values', T('Values')], ['items', T('Documented items')]];
    const rows = H.map((h, i) => ({ h, p: i ? H[i - 1] : null })).reverse();
    const cell = (h, p, c) => { const v = mval(h, c), d = p && v != null && mval(p, c) != null ? v - mval(p, c) : null; return `<td class="num">${esc(mtext(v, c))}${d ? `<br><small class="${d > 0 ? 'up' : 'down'}">${esc((d > 0 ? '+' : '−') + mtext(Math.abs(d), c))}</small>` : ''}</td>`; };
    $('#dmHist').innerHTML = `<caption class="sr-only">${esc(T('Totals by date'))}</caption><thead><tr><th scope="col">${esc(T('Date'))}</th>${cols.map(c => `<th scope="col" class="num">${esc(c[1])}</th>`).join('')}</tr></thead>`
      + `<tbody>${rows.map(({ h, p }) => `<tr><th scope="row" class="date">${esc(h.date)}</th>${cols.map(c => cell(h, p, c[0])).join('')}</tr>`).join('')}</tbody>`;
    const first = H[0], last = H[H.length - 1];
    const g = DM.growthFacts(H);
    $('#growthLede').textContent = first && last ? [T('From {d0} to {d1} the published values went from {v0} to {v1} and the files from {f0} to {f1}.', { d0: first.date, d1: last.date, v0: fmt(first.values), v1: fmt(last.values), f0: fmt(first.files), f1: fmt(last.files) }),
      g.grew ? T('Files, records, fields, values and dictionary items only grew; the size can fall when a file is compressed or trimmed.') : T('A total can fall when a file is compressed, trimmed or removed.'),
      g.drop ? T('The size fell by {size} on {date}.', { size: sizeText(g.drop.bytes), date: g.drop.date }) : '',
      T('One row for each date on which a total changed: a new file, a file whose content or size changed, or a new dictionary item.')].filter(Boolean).join(' ') : '';
  }

  // ── What is not published ─────────────────────────────────────────────────
  const WITHHELD = {
    places_not_drawn: [TK('Tourism places counted but not drawn'), TK('A holiday rental, or a rented unit named by its street address, is usually someone’s home: it is counted in its municipio and barrio, with no name, no point and no address.')],
    not_tourism: [TK('Listings that are not tourism, left out'), TK('Residential buildings, housing estates, private homes, numbered homes and care, shelter and treatment services filed under tourism categories are left out of the file and of every count.')],
    hrsa_sites: [TK('Health center service sites'), TK('Counted by municipio and used to measure distances. The points of the sites are kept in the build’s local cache and never published.')],
    shelters: [TK('Shelters'), TK('None is published. Hurricane-shelter lists state no license, so they are not harvested (the wish list marks them blocked); domestic-violence and children’s shelters are never published.')],
    nrhp_private_homes: [TK('National Register listings that are private homes'), TK('Counted in their municipio; they have no point and their names are published nowhere.')],
    public_housing_approximate: [TK('Public housing developments at an approximate location'), TK('The source places them at the center of a block group or a census tract, not at the building: counted by municipio, not drawn.')],
    lihtc_not_drawn: [TK('Tax credit housing projects not drawn'), TK('Counted by municipio, not drawn: most have only a city in the source, and those that serve people who are homeless or living with HIV, and care homes for older adults, are never drawn or named.')],
    treatment_facilities: [TK('Substance use and mental health treatment facilities'), TK('Counted by municipio and type of care; no names and no points.')],
    nonprofits: [TK('Tax-exempt organizations'), TK('Counted by municipio and type of activity; no names and no addresses.')],
  };
  const PART = { holiday_rental: TK('holiday rentals'), address: TK('named by a street address'), permanent: TK('permanent sites'), mobile_vans: TK('mobile vans') };
  function renderWithheld() {
    const rows = (S.reg.withheld || []).filter(w => WITHHELD[w.id]);
    const count = (w) => {
      if (w.count == null) return '—';
      let s = w.of ? T('{n} of {m}', { n: fmt(w.count), m: fmt(w.of) }) : fmt(w.count);
      const parts = Object.entries(w.parts || {}).filter(([p]) => PART[p]).sort((a, b) => b[1] - a[1]).map(([p, n]) => `${fmt(n)} ${T(PART[p])}`);
      return esc(s) + (parts.length ? `<br><small>${esc(parts.join(' · '))}</small>` : '');
    };
    $('#dmWithheld').innerHTML = `<caption class="sr-only">${esc(T('What is not published'))}</caption><thead><tr><th scope="col">${esc(T('What'))}</th><th scope="col" class="num cnt">${esc(T('Count'))}</th><th scope="col">${esc(T('Rule'))}</th><th scope="col">${esc(T('Count read from'))}</th></tr></thead>`
      + `<tbody>${rows.map(w => `<tr><th scope="row">${esc(T(WITHHELD[w.id][0]))}</th><td class="num cnt">${count(w)}</td><td class="rule">${esc(T(WITHHELD[w.id][1]))} <a href="dictionary.html#${esc(w.doc)}">${esc(T('The rule in the dictionary'))}</a></td><td><code>${esc(w.file)}</code></td></tr>`).join('')}</tbody>`;
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  // the category filter's choices: the registry's domains that have a file, a sub-domain under its parent, each with its number of files
  function renderDomains() {
    $('#dmDom').insertAdjacentHTML('beforeend', DM.domainOptions(S.files, S.reg.domain_names).map(o => `<option value="${esc(o.id)}">${o.depth ? '— ' : ''}${esc(dname(o.id))} (${fmt(o.n)})</option>`).join(''));
  }
  function wire() {
    $('#dmDom').onchange = (e) => { S.dom = e.target.value; renderTable(); };
    let t; $('#dmQ').oninput = (e) => { clearTimeout(t); t = setTimeout(() => { S.q = e.target.value.trim(); renderTable(); }, 120); };
    $('#dmKind').onchange = (e) => { S.kind = e.target.value; renderTable(); };
    $('#dmRev').onchange = (e) => { S.rev = e.target.value; renderTable(); };
    $('#dmSort').onchange = (e) => { const c = DM.sortParse(e.target.value); if (!c || !COLS.some(x => x.k === c.sort)) return; S.sort = c.sort; S.dir = c.dir; renderTable(); };
    $('#dmReset').onclick = () => { S.q = S.dom = S.kind = S.rev = ''; S.sort = 'values'; S.dir = 'desc'; $('#dmQ').value = ''; $('#dmDom').value = ''; $('#dmKind').value = ''; $('#dmRev').value = ''; renderTable(); };
    $('#dmCsv').onclick = downloadCsv;
    $('#dmTbl').addEventListener('click', (e) => {
      const b = e.target.closest('[data-sort]'); if (!b) return;
      const k = b.dataset.sort, c = COLS.find(x => x.k === k);
      S.dir = S.sort === k ? (S.dir === 'asc' ? 'desc' : 'asc') : (c.num ? 'desc' : 'asc'); S.sort = k;   // numbers and dates: largest and newest first
      renderTable(); const again = $(`#dmTbl [data-sort="${k}"]`); if (again) again.focus();
    });
    $('#dmMeasure').addEventListener('click', (e) => { const b = e.target.closest('[data-measure]'); if (!b) return; S.measure = b.dataset.measure; renderMeasure(); renderChart(); });
    let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(renderChart, 150); });
  }
  async function boot() {
    try { S.reg = await fetchJson('data/registry.json'); } catch (e) { $('#dmTbl').innerHTML = `<tbody><tr><td>${esc(T('The list of files could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</td></tr></tbody>`; return; }
    S.files = (S.reg.files || []).map(f => ({ ...f, review: f.review || { status: 'none', flags: [] } }));
    S.files.forEach(f => { f._hay = hay(f); });
    $('#snapshotLabel').textContent = snapshotLabel(S.reg.snapshot);
    renderTiles(); renderDomains(); renderTable(); renderMeasure(); renderChart(); renderHistory(); renderWithheld(); wire();
    performance.mark('ready');
    let h = ''; try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { /* a broken % names no section */ } if (h) { const el = document.getElementById(h); if (el) setTimeout(() => el.scrollIntoView({ block: 'start' }), 60); }
  }
  boot();
})();
