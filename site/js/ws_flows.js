/* PR Data Observatory: the Workflows area (workflows.html; docs/workspace.md). A workflow is a short list of steps with a result at each one:

     source    a set of places (a published file of points)
     filter    keep the rows where a column compares with a value
     within    mark the places that lie inside the outlines of an area file (flood zones, protected areas, watersheds…)
     group     count them by municipio, and add up a column
     output    the table, to download

   Everything runs in the browser on the published files; nothing is uploaded. The sources are not listed by hand: they are the files of points in
   data/registry.json (registry.py), so a new one appears on its own. The areas are the outline files below that the registry holds.
   A workflow counts places whose point lies inside an outline. It does not know a building's height, whether it flooded, or where its users live. */
(function () {
  'use strict';
  const el = (id) => document.getElementById(id);
  const icon = (n) => `<span class="ms-icon" aria-hidden="true">${esc(n)}</span>`;
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } } };
  const flat = (s) => norm(String(s == null ? '' : s));
  // Outline files a place can be tested against: [id, label, file, which features, the name of the one a place falls in]. Listed only when the registry holds the file.
  const AREAS = () => [
    ['flood:sfha', T('The FEMA 1% flood area (A and V zones)'), 'flood.geojson', (p) => p.SFHA_TF === 'T', (p) => p.FLD_ZONE || ''],
    ['flood:all', T('The FEMA 1% or 0.2% flood area'), 'flood.geojson', (p) => p.FLD_ZONE !== 'X' || /0\.2/.test(p.ZONE_SUBTY || ''), (p) => p.FLD_ZONE + (p.ZONE_SUBTY ? ' ' + p.ZONE_SUBTY : '')],
    ['protected', T('A protected area'), 'protected.geojson', () => true, (p) => p.Unit_Nm || ''],
    ['watersheds', T('A watershed (names it)'), 'watersheds.geojson', () => true, (p) => p.name || ''],
    ['comunidades', T('A Comunidad Especial (names it)'), 'comunidades.geojson', () => true, (p) => p.nombre || ''],
    ['oz', T('An Opportunity Zone tract'), 'oz_tracts.geojson', () => true, (p) => p.g || ''],
  ];
  const OPS = () => ({ source: T('Source: a set of places'), filter: T('Keep the rows where'), within: T('Mark the ones that lie inside'), group: T('Summarize by municipio'), output: T('Output: a table to download') });
  const S = { reg: [], sources: [], areas: [], muni: null, files: new Map(), W: null, results: [], running: false, run: 0 };
  const file = (f) => { if (!S.files.has(f)) S.files.set(f, fetchJson('data/' + f).catch(e => { S.files.delete(f); throw e; })); return S.files.get(f); };

  // ── Geometry: is a point inside an outline? (even-odd rule on each ring; a hole takes the point out) ──
  const inRing = (x, y, r) => { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  const inPoly = (x, y, poly) => inRing(x, y, poly[0]) && !poly.slice(1).some(h => inRing(x, y, h));
  function index(features) {
    const out = [];
    features.forEach(f => { const g = f.geometry; if (!g) return; const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : []; polys.forEach(poly => { let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; poly[0].forEach(c => { if (c[0] < x0) x0 = c[0]; if (c[0] > x1) x1 = c[0]; if (c[1] < y0) y0 = c[1]; if (c[1] > y1) y1 = c[1]; }); out.push({ b: [x0, y0, x1, y1], poly, p: f.properties || {} }); }); });
    return out;
  }
  const hit = (ix, x, y) => ix.find(o => x >= o.b[0] && x <= o.b[2] && y >= o.b[1] && y <= o.b[3] && inPoly(x, y, o.poly)) || null;
  /** Metres from a point to the nearest edge of the outlines within `m` metres of it (Infinity when none is that near): a place this close to an edge can fall on either side. */
  function edge(ix, x, y, m) {
    const dx = m / (111320 * Math.cos(y * Math.PI / 180)), dy = m / 110540; let best = Infinity;
    ix.forEach(o => { if (x < o.b[0] - dx || x > o.b[2] + dx || y < o.b[1] - dy || y > o.b[3] + dy) return;
      o.poly.forEach(r => { for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const ax = (r[j][0] - x) / dx * m, ay = (r[j][1] - y) / dy * m, bx = (r[i][0] - x) / dx * m, by = (r[i][1] - y) / dy * m, vx = bx - ax, vy = by - ay, t = Math.max(0, Math.min(1, -(ax * vx + ay * vy) / ((vx * vx + vy * vy) || 1))), d = Math.hypot(ax + t * vx, ay + t * vy); if (d < best) best = d; } }); });
    return best <= m ? best : Infinity;
  }
  const muniOf = (x, y) => { const h = S.muni ? hit(S.muni, x, y) : null; return h ? h.p.GEOID : null; };
  const muniName = (id) => { const o = S.muni && S.muni.find(m => m.p.GEOID === id); return o ? o.p.municipality : id; };
  const numFields = (rows) => { const c = {}; rows.slice(0, 200).forEach(r => Object.entries(r.p).forEach(([k, v]) => { if (v !== '' && v != null && typeof v !== 'object' && isFinite(+v) && !/^(geoid|nces|usgs|sn|id|lat|lon|lng|zip)$/i.test(k)) c[k] = (c[k] || 0) + 1; })); return Object.keys(c).filter(k => c[k] > Math.min(rows.length, 200) * 0.4); };

  // ── Running ─────────────────────────────────────────────────────────────────
  /** Run the steps in order. Each gives { rows | table, text } or { error }; a step after an error does not run. A run started later replaces an earlier one still loading. */
  async function run() {
    const mine = ++S.run; S.running = true; S.results = []; render(); let rows = null, table = null; const results = [];
    for (const stp of S.W.steps) {
      let res;
      try {
        if (stp.op === 'source') {
          const def = S.sources.find(s => s.file === stp.ref); if (!def) throw new Error(T('Choose a set of places.'));
          const g = await file(def.file), fs = (g.features || []).filter(f => f.geometry && f.geometry.type === 'Point');
          if (!fs.length) throw new Error(T('This file has no points to count.'));
          rows = fs.map(f => ({ x: f.geometry.coordinates[0], y: f.geometry.coordinates[1], p: f.properties || {}, g: muniOf(f.geometry.coordinates[0], f.geometry.coordinates[1]) })); table = null;
          res = { rows, text: T('{n} places: {name}.', { n: fmt(rows.length), name: def.title }) };
        } else if (!rows && stp.op !== 'output') throw new Error(T('This step needs places. Put a source step before it.'));
        else if (stp.op === 'filter') {
          const f = stp.field, v = stp.value, n = parseFloat(v), cmp = stp.cmp || '=';
          if (!f) throw new Error(T('Choose a column.')); if (v == null || v === '') throw new Error(T('Write the value to compare with.'));
          if ((cmp === '>' || cmp === '<') && !isFinite(n)) throw new Error(T('"Greater than" and "less than" need a number.'));
          const before = rows.length, val = (r) => (f === 'inside' ? (r.inside ? 'yes' : 'no') : f === 'zone' ? r.zone : r.p[f]);
          rows = rows.filter(r => { const x = val(r); return cmp === '>' ? +x > n : cmp === '<' ? +x < n : cmp === 'has' ? flat(x).includes(flat(v)) : flat(x) === flat(v); });
          res = { rows, text: T('{n} of {m} places kept.', { n: fmt(rows.length), m: fmt(before) }) };
        } else if (stp.op === 'within') {
          const a = S.areas.find(x => x[0] === stp.area); if (!a) throw new Error(T('Choose the areas.'));
          const g = await file(a[2]), ix = index((g.features || []).filter(f => a[3](f.properties || {}))); let n = 0; const near = [];
          rows = rows.map(r => { const h = hit(ix, r.x, r.y); if (h) n++; if (edge(ix, r.x, r.y, 5) <= 5) near.push(String(r.p.name || r.p.NAME || '?')); return Object.assign({}, r, { inside: !!h, zone: h ? String(a[4](h.p)) : '' }); });
          res = { rows, text: T('{n} of {m} places lie inside: {area} ({k} outlines tested). Each place got two new columns, "inside" and "zone".', { n: fmt(n), m: fmt(rows.length), area: a[1], k: fmt(ix.length) })
            + (near.length ? ' ' + Tn(near.length, '{n} place stands within 5 m of an edge, closer than either file can be trusted: {names}.', '{n} places stand within 5 m of an edge, closer than either file can be trusted: {names}.', { names: near.slice(0, 8).join('; ') + (near.length > 8 ? '…' : '') }) : '') };
        } else if (stp.op === 'group') {
          const by = {}, fld = stp.sum || null, marked = rows.length > 0 && 'inside' in rows[0];
          rows.forEach(r => { if (!r.g) return; const o = by[r.g] || (by[r.g] = { n: 0, n_in: 0, sum: 0, sum_in: 0 }); o.n++; const v = fld ? +r.p[fld] : 0, ok = fld && isFinite(v); if (ok) o.sum += v; if (r.inside) { o.n_in++; if (ok) o.sum_in += v; } });
          table = { by, fld, marked, lost: rows.filter(r => !r.g).length };
          const tot = Object.values(by).reduce((p, o) => ({ n: p.n + o.n, n_in: p.n_in + o.n_in, sum: p.sum + o.sum, sum_in: p.sum_in + o.sum_in }), { n: 0, n_in: 0, sum: 0, sum_in: 0 });
          res = { table, tot, text: Tn(Object.keys(by).length, '{n} municipio has at least one place.', '{n} municipios have at least one place.') + ' ' + T('In all: {n} places.', { n: fmt(tot.n) }) + (marked ? ' ' + T('{n} inside.', { n: fmt(tot.n_in) }) : '')
            + (fld ? ' ' + T('{column}: {sum}.', { column: fld, sum: fmt(tot.sum) }) + (marked ? ' ' + T('{sum} of it at the places inside.', { sum: fmt(tot.sum_in) }) : '') : '') + (table.lost ? ' ' + Tn(table.lost, '{n} place in no municipio was left out.', '{n} places in no municipio were left out.') : '') };
        } else if (stp.op === 'output') {
          if (!table) throw new Error(T('An output needs a summary by municipio before it.')); if (!(stp.name || '').trim()) throw new Error(T('Give the output a name.'));
          res = { out: table, text: T('The table is ready to download.') };
        }
      } catch (e) { res = { error: e.message || String(e) }; }
      if (mine !== S.run) return;   // a newer run took over while a file was loading
      results.push(res); if (res.error) break;
    }
    S.results = results; S.running = false; render();
  }
  const csvCell = (v) => { const s = String(v == null ? '' : v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  function download(name, text) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }
  const slug = (s) => norm(s).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50) || 'workflow';
  function plainCsv(t, name) {
    const head = ['geoid', 'municipio', 'places'].concat(t.marked ? ['places_inside'] : [], t.fld ? [t.fld] : [], t.fld && t.marked ? [t.fld + '_at_places_inside'] : []);
    const rows = Object.entries(t.by).sort((a, b) => muniName(a[0]).localeCompare(muniName(b[0]))).map(([id, o]) => [id, muniName(id), o.n].concat(t.marked ? [o.n_in] : [], t.fld ? [o.sum] : [], t.fld && t.marked ? [o.sum_in] : []));
    download(slug(name) + '.csv', '﻿' + [head, ...rows].map(r => r.map(csvCell).join(',')).join('\r\n') + '\r\n');
  }
  /** The same table in the file form the map reads (docs/scenarios.md, "Model outputs"): open it on the map under Tools, Scenarios, "Add a model output". The map labels it as computed, not observed. */
  function mapCsv(t, name) {
    const yr = new Date().getFullYear(), v = (s) => (name + ' ' + s).replace(/[^A-Za-z0-9_ .\-]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60);
    const lines = ['# model_name: ' + name.replace(/[\r\n#]/g, ' ').slice(0, 100), '# model_version: 1', '# run_id: ' + new Date().toISOString().slice(0, 10), '# date: ' + new Date().toISOString().slice(0, 10), '# assumptions_url: https://observatory.foundationpr.org/workflows.html', '# licence: as the source files', '# contact_label: PR Data Observatory workflow', 'geography_key,geography_level,period,variable,value,unit'];
    Object.entries(t.by).forEach(([id, o]) => { lines.push([id, 'municipio', yr, v('places'), o.n, 'places'].map(csvCell).join(',')); if (t.marked) lines.push([id, 'municipio', yr, v('places inside'), o.n_in, 'places'].map(csvCell).join(',')); if (t.fld) lines.push([id, 'municipio', yr, v(t.fld), o.sum, ''].map(csvCell).join(',')); });
    download(slug(name) + '-for-the-map.csv', lines.join('\n') + '\n');
  }

  // ── Drawing ─────────────────────────────────────────────────────────────────
  const opt = (list, cur) => list.map(([v, l]) => `<option value="${esc(v)}"${v === cur ? ' selected' : ''}>${esc(l)}</option>`).join('');
  function stepCard(stp, i) {
    const r = S.results[i], prev = S.results.slice(0, i).reverse().find(x => x && x.rows), prevRows = prev ? prev.rows : null, ops = OPS();
    let ctl = '';
    if (stp.op === 'source') ctl = `<select data-wf="ref" data-i="${i}" aria-label="${esc(T('Places'))}">${opt(S.sources.map(s => [s.file, s.title]), stp.ref)}</select>`;
    else if (stp.op === 'filter') { const cols = prevRows && prevRows.length ? Object.keys(prevRows[0].p).concat('inside' in prevRows[0] ? ['inside', 'zone'] : []) : (stp.field ? [stp.field] : []);
      ctl = `<select data-wf="field" data-i="${i}" aria-label="${esc(T('Column'))}"><option value="">${esc(T('(column)'))}</option>${opt(cols.map(c => [c, c]), stp.field)}</select><select data-wf="cmp" data-i="${i}" aria-label="${esc(T('Comparison'))}">${opt([['=', T('is')], ['>', T('is greater than')], ['<', T('is less than')], ['has', T('contains')]], stp.cmp || '=')}</select><input type="text" data-wf="value" data-i="${i}" value="${esc(stp.value || '')}" aria-label="${esc(T('Value'))}">`; }
    else if (stp.op === 'within') ctl = `<select data-wf="area" data-i="${i}" aria-label="${esc(T('Areas'))}">${opt(S.areas.map(a => [a[0], a[1]]), stp.area)}</select>`;
    else if (stp.op === 'group') ctl = `<label>${esc(T('and add up'))} <select data-wf="sum" data-i="${i}"><option value="">${esc(T('(nothing: count only)'))}</option>${opt((prevRows ? numFields(prevRows) : stp.sum ? [stp.sum] : []).map(c => [c, c]), stp.sum)}</select></label>`;
    else ctl = `<input type="text" data-wf="name" data-i="${i}" value="${esc(stp.name || '')}" aria-label="${esc(T('Name of the output'))}">`;
    let look = '';
    if (r && r.rows && r.rows.length) { const cols = Object.keys(r.rows[0].p).filter(c => typeof r.rows[0].p[c] !== 'object').slice(0, 5).concat('inside' in r.rows[0] ? ['inside', 'zone'] : []);
      look = `<details><summary>${esc(T('Look at the first rows'))}</summary><div class="ws-tblwrap"><table class="ws-tbl"><thead><tr>${cols.map(c => `<th scope="col">${esc(c)}</th>`).join('')}</tr></thead><tbody>${r.rows.slice(0, 6).map(x => `<tr>${cols.map(c => `<td>${esc(String(c === 'inside' ? (x.inside ? T('yes') : T('no')) : c === 'zone' ? x.zone : x.p[c] == null ? '' : x.p[c]).slice(0, 34))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`; }
    else if (r && r.table) { const t = r.table, top = Object.entries(t.by).sort((a, b) => (b[1].n_in - a[1].n_in) || (b[1].n - a[1].n)).slice(0, 8);
      look = `<details open><summary>${esc(T('The municipios with the most'))}</summary><div class="ws-tblwrap"><table class="ws-tbl"><thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col" class="num">${esc(T('Places'))}</th>${t.marked ? `<th scope="col" class="num">${esc(T('Inside'))}</th>` : ''}${t.fld ? `<th scope="col" class="num">${esc(t.fld)}</th>` : ''}${t.fld && t.marked ? `<th scope="col" class="num">${esc(T('at places inside'))}</th>` : ''}</tr></thead>
        <tbody>${top.map(([id, x]) => `<tr><th scope="row">${esc(muniName(id))}</th><td class="num">${fmt(x.n)}</td>${t.marked ? `<td class="num">${fmt(x.n_in)}</td>` : ''}${t.fld ? `<td class="num">${fmt(x.sum)}</td>` : ''}${t.fld && t.marked ? `<td class="num">${fmt(x.sum_in)}</td>` : ''}</tr>`).join('')}</tbody></table></div></details>`; }
    return `<li class="ws-step${r && r.error ? ' bad' : r ? ' done' : ''}"><div class="ws-step-head"><span class="ws-num">${i + 1}</span><b>${esc(ops[stp.op])}</b>${i ? `<button type="button" class="icon-btn small" data-wf="del" data-i="${i}" aria-label="${esc(T('Remove step {n}', { n: i + 1 }))}">${icon('close')}</button>` : ''}</div>
      <div class="ws-step-ctl">${ctl}</div>${r ? (r.error ? `<p class="ws-bad" role="alert">${icon('error')}${esc(r.error)}</p>` : `<p class="ws-ok">${icon('check_circle')}${esc(r.text)}</p>${look}`) : `<p class="ws-muted">${esc(S.running ? T('Running…') : T('Not run yet.'))}</p>`}</li>`;
  }
  function render() {
    const saved = store.get('twin.flows', []), W = S.W, last = S.results[S.results.length - 1], done = !S.running && W && S.results.length === W.steps.length && last && last.out, ops = OPS();
    el('wfBody').innerHTML = `<div class="ws-flows"><aside class="ws-flow-list"><button type="button" class="btn primary" data-wf="example">${icon('add')}${esc(T('Schools and flood zones (example)'))}</button><button type="button" class="btn" data-wf="new">${icon('add')}${esc(T('New empty workflow'))}</button>
        <h2>${esc(T('Saved in this browser'))}</h2>${saved.map(w => `<div class="ws-flow-row"><button type="button" class="ws-tile${W && W.id === w.id ? ' on' : ''}" data-wf="open" data-id="${esc(w.id)}"><span><b>${esc(w.name)}</b><i>${esc(Tn(w.steps.length, '{n} step', '{n} steps'))}</i></span></button><button type="button" class="icon-btn small" data-wf="forget" data-id="${esc(w.id)}" aria-label="${esc(T('Delete {name}', { name: w.name }))}">${icon('delete')}</button></div>`).join('') || `<p class="ws-muted">${esc(T('None yet.'))}</p>`}
        <p class="ws-muted">${esc(T('Steps run here, in your browser, on the published files. Nothing is uploaded. A workflow that should run on a schedule needs a server; that is not built.'))}</p></aside>
      <section class="ws-flow-main" aria-live="polite">${W ? `<div class="ws-save"><input id="wfName" type="text" maxlength="80" value="${esc(W.name)}" aria-label="${esc(T('Name of the workflow'))}"><button type="button" class="btn primary" data-wf="run"${S.running ? ' disabled' : ''}>${icon('play_arrow')}${esc(S.running ? T('Running…') : T('Run'))}</button><button type="button" class="btn" data-wf="save">${icon('save')}${esc(T('Save'))}</button></div>
        <ol class="ws-steps">${W.steps.map(stepCard).join('')}</ol>
        <div class="ws-step-ctl"><span class="ws-muted">${esc(T('Add a step:'))}</span>${['filter', 'within', 'group', 'output'].map(k => `<button type="button" class="btn small" data-wf="add" data-op="${k}">${esc(ops[k].split(':')[0])}</button>`).join('')}</div>
        ${done ? `<div class="ws-flow-out"><p><b>${esc(T('What this result says, and what it does not.'))}</b> ${esc(T("It counts places whose point lies inside an area's outline. It does not know a building's floor height, whether it has flooded, or where the people who use it live. Only the point is tested, not the whole property."))}</p>
          <div class="btn-row"><button type="button" class="btn primary" data-wf="csv">${icon('download')}${esc(T('Download the table (CSV)'))}</button><button type="button" class="btn" data-wf="mapcsv">${icon('map')}${esc(T('Download it for the map'))}</button></div>
          <p class="ws-muted">${esc(T('To shade the result on the map: download it for the map, then on the map open Tools, Map tools, Scenarios and add it as a model output. The map labels it as computed, not observed.'))}</p></div>` : ''}`
        : `<div class="ws-empty-card"><b>${esc(T('A workflow is a list of steps with a result at each one.'))}</b><p>${esc(T('Start from the example, or from an empty one.'))}</p></div>`}</section></div>`;
  }
  const example = () => ({ id: 'wf' + Date.now(), name: T('Public schools in the 1% flood zone'), steps: [{ op: 'source', ref: 'public_schools.geojson' }, { op: 'within', area: 'flood:sfha' }, { op: 'group', sum: (S.sources.find(s => s.file === 'public_schools.geojson') ? 'students' : '') }, { op: 'output', name: T('Schools in the flood zone') }] });
  function wire() {
    const body = el('wfBody'), name = () => { const n = el('wfName'); if (n && S.W) S.W.name = (n.value || S.W.name).trim().slice(0, 80); };
    body.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b || !b.dataset.wf) return; const k = b.dataset.wf, i = +b.dataset.i, saved = store.get('twin.flows', []);
      if (k === 'example') { S.W = example(); run(); }
      else if (k === 'new') { S.W = { id: 'wf' + Date.now(), name: T('My workflow'), steps: [{ op: 'source', ref: (S.sources[0] || {}).file }] }; S.results = []; render(); }
      else if (k === 'open') { const w = saved.find(x => x.id === b.dataset.id); if (w) { S.W = JSON.parse(JSON.stringify(w)); run(); } }
      else if (k === 'forget') { store.set('twin.flows', saved.filter(x => x.id !== b.dataset.id)); render(); }
      else if (k === 'run') { name(); run(); }
      else if (k === 'save') { name(); store.set('twin.flows', saved.filter(x => x.id !== S.W.id).concat(JSON.parse(JSON.stringify(S.W))).slice(-40)); render(); }
      else if (k === 'del') { name(); S.W.steps.splice(i, 1); S.results = S.results.slice(0, i); render(); }
      else if (k === 'add') { name(); S.W.steps.push(b.dataset.op === 'within' ? { op: 'within', area: (S.areas[0] || [])[0] } : b.dataset.op === 'output' ? { op: 'output', name: S.W.name } : { op: b.dataset.op }); render(); }
      else if (k === 'csv' || k === 'mapcsv') { const out = S.results[S.results.length - 1].out, nm = (S.W.steps[S.W.steps.length - 1].name || S.W.name); (k === 'csv' ? plainCsv : mapCsv)(out, nm); }
    });
    body.addEventListener('change', (e) => { const t = e.target; if (!t.dataset.wf || !S.W) return; const i = +t.dataset.i; name(); S.W.steps[i][t.dataset.wf] = t.value; S.results = S.results.slice(0, i); render(); });
  }
  async function start() {
    el('wfBody').innerHTML = `<div class="ws-empty-card" role="status">${esc(T('Loading the list of files…'))}</div>`;
    let reg, muni;
    try { [reg, muni] = await Promise.all([fetchJson('data/registry.json'), fetchJson('data/municipios.geojson')]); }
    catch (e) { el('wfBody').innerHTML = `<div class="ws-empty-card" role="alert"><b>${esc(T('The list of files could not be loaded.'))}</b><p>${esc(T('Check your connection.'))}</p><button type="button" class="btn" id="wfRetry">${esc(T('Try again'))}</button></div>`; el('wfRetry').onclick = start; return; }
    const files = reg.files || [], have = new Set(files.map(f => f.file));
    S.muni = index(muni.features);
    // every published file of points, by its own title (the registry says "points" in it); the newest file of points appears here without an edit
    S.sources = files.filter(f => /\.geojson$/.test(f.file) && /\bpoints\b/i.test(f.title || '') && (f.records || 0) <= 20000).map(f => ({ file: f.file, title: (I18N.lang === 'es' && f.title_es) || f.title })).sort((a, b) => a.title.localeCompare(b.title));
    S.areas = AREAS().filter(a => have.has(a[2]));
    wire(); render();
  }
  window.Workflows = { state: S, run, _test: { inPoly, index, hit, edge } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
