/* PR Data Observatory core: scenarios and model outputs (plan item 15, section F; docs/scenarios.md). No page state: objects and text in, objects out.

     Scenario.make({ name, label, notes, hash, outputs, models })   a scenario: what the map showed (its link), the figures it produced, any model outputs loaded with it
     Scenario.check(obj, n)               problems with a scenario read from a file ([] when none); n, when given, is the length of every series (municipios + 1)
     Scenario.read(text, n)               parses and checks
     Scenario.diff(a, b)                  the outputs of two scenarios side by side: [{ key, label, unit, a, b, delta, pct }]
     Scenario.parseModel(text, ids)       a model output file (CSV with a "#" header, or GeoJSON with a "model" member) -> { header, series, errors }; ids are the municipio codes
     Scenario.diffSeries(a, b, ids)       the difference B − A of two series of one variable, per place and period, where both have a value

   A model output is never observed data: every series it gives carries its header (model, version, run, date, assumptions, license, contact label) and the pages label it
   "Model output (not observed data)". Contact details are refused: the header names a team or organization, never a person's e-mail or telephone. */
(function (name, root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('scenario', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const VERSION = 1, MAX_TEXT = 5 * 1024 * 1024, MAX_ROWS = 20000, MAX_NAME = 120, MAX_NOTES = 4000;
  const HEADER = ['model_name', 'model_version', 'run_id', 'date', 'assumptions_url', 'licence', 'contact_label'];
  const COLUMNS = ['geography_key', 'geography_level', 'period', 'variable', 'value', 'unit'];
  const EMAIL = /[^\s@]+@[^\s@]+\.[a-z]{2,}/i, PHONE = /(?:\+?1[\s.-]?)?(?:\([2-9]\d{2}\)[\s.-]?|\b[2-9]\d{2}[\s.-]?)[2-9]\d{2}[\s.-]?\d{4}\b/;   // contact details (an e-mail, a telephone such as 787-555-0123, (787) 555 0123, (787)5550123 or 7875550123: a US number, whose area code and exchange start with 2 to 9): refused wherever free text is kept. A date (2026-10-15) or a run id such as 1760540000 is not a telephone; a date-hour such as 2026101512 is taken for one
  const clean = (s, max) => String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, max);
  const personal = (s) => EMAIL.test(s) || PHONE.test(s);
  const VARIABLE = /^[A-Za-z0-9_ .\-]{1,60}$/;
  const str = (x, max) => typeof x === 'string' && x.length <= max;

  function uid() { return 'sc-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8); }

  function make(o) {
    return { v: VERSION, id: o.id || uid(), name: clean(o.name, MAX_NAME), label: clean(o.label, MAX_NAME), notes: clean(o.notes, MAX_NOTES), created: o.created || new Date().toISOString(),
      hash: String(o.hash || '').replace(/^#/, '').slice(0, 8000), outputs: (o.outputs || []).map(x => ({ key: String(x.key), label: clean(x.label, 200), unit: clean(x.unit, 30), value: Number(x.value) })).filter(x => isFinite(x.value)),
      models: o.models || [] };
  }

  // A series as parseModel gives it: a variable, a unit, and for each year an array of n numbers or nulls (lower and upper are null or the same shape).
  function checkSeries(sr, n) {
    if (!sr || typeof sr !== 'object') return 'is not a series';
    if (!str(sr.variable, 60) || !VARIABLE.test(sr.variable)) return 'has a variable that is not letters, digits, spaces, dots, dashes or underscores';
    if (personal(sr.variable)) return 'has a variable that holds a telephone number';
    if (!str(sr.unit, 20) || personal(sr.unit)) return 'has a unit that is not a short text without contact details';
    for (const f of ['years', 'lower', 'upper']) {
      const o = sr[f]; if (f !== 'years' && o == null) continue;
      if (!o || typeof o !== 'object' || Array.isArray(o) || (f === 'years' && !Object.keys(o).length)) return `has no ${f} by period`;
      for (const [y, a] of Object.entries(o)) if (!/^\d{4}$/.test(y) || !Array.isArray(a) || (n ? a.length !== n : !a.length || a.length > 1000) || a.some(x => x !== null && !(typeof x === 'number' && isFinite(x)))) return `has ${f} that are not numbers by place and year`;
    }
    return '';
  }
  function check(s, n) {
    const P = [];
    if (!s || typeof s !== 'object' || Array.isArray(s)) return ['not a scenario'];
    if (s.v !== VERSION) P.push(`version ${s.v} is not ${VERSION}`);
    if (!s.id || typeof s.id !== 'string' || s.id.length > 80) P.push('no id');
    if (!s.name || !str(s.name, MAX_NAME)) P.push('no name');
    if (!str(s.label, MAX_NAME)) P.push('the label is not a short text');
    if (!str(s.notes, MAX_NOTES)) P.push('the notes are not a text');
    if (typeof s.created !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(s.created)) P.push('no date of creation');
    for (const f of ['name', 'label', 'notes']) if (typeof s[f] === 'string' && personal(s[f])) P.push(`${f} holds an e-mail address or a telephone number`);
    if (typeof s.hash !== 'string' || s.hash.length > 8000 || /[<>"\s]/.test(s.hash)) P.push('the map link is not a link');
    if (!Array.isArray(s.outputs) || s.outputs.some(x => !x || typeof x.key !== 'string' || x.key.length > 200 || personal(x.key) || typeof x.value !== 'number' || !isFinite(x.value) || !str(x.label, 200) || !str(x.unit, 30) || personal(x.label) || personal(x.unit))) P.push('outputs are not a list of figures');
    if (!Array.isArray(s.models)) P.push('models are not a list');
    else s.models.forEach((m, i) => {
      const h = m && m.header;
      if (!h || typeof h !== 'object' || HEADER.some(k => !str(h[k], 300))) { P.push(`model ${i + 1} has no full header`); return; }
      const e = []; checkHeader(h, e); e.forEach(x => P.push(`model ${i + 1}: ${x}`));
      if (!Array.isArray(m.series) || !m.series.length) { P.push(`model ${i + 1} has no series`); return; }
      m.series.forEach((sr, j) => { const x = checkSeries(sr, n); if (x) P.push(`model ${i + 1}, series ${j + 1} ${x}`); });
    });
    return P.slice(0, 50);
  }
  // A checked scenario rebuilt from the fields the observatory knows: anything else in the file (an "author" field, say) is not stored or exported again.
  const pick = (o, ks) => Object.fromEntries(ks.filter(k => o[k] !== undefined).map(k => [k, o[k]]));
  function known(s) {
    return { ...pick(s, ['v', 'id', 'name', 'label', 'notes', 'created', 'hash']), outputs: s.outputs.map(x => pick(x, ['key', 'label', 'unit', 'value'])),
      models: s.models.map(m => ({ header: pick(m.header, HEADER), series: m.series.map(sr => pick(sr, ['variable', 'unit', 'years', 'lower', 'upper'])) })) };
  }
  function read(text, n) {
    let s; try { s = JSON.parse(String(text).slice(0, MAX_TEXT)); } catch { return { scenario: null, errors: ['not JSON'] }; }
    const errors = check(s, n);
    return { scenario: errors.length ? null : known(s), errors };
  }

  function diff(a, b) {
    const keys = [...new Set([...a.outputs.map(x => x.key), ...b.outputs.map(x => x.key)])], A = new Map(a.outputs.map(x => [x.key, x])), B = new Map(b.outputs.map(x => [x.key, x]));
    return keys.map(k => { const x = A.get(k), y = B.get(k), va = x ? x.value : null, vb = y ? y.value : null, d = va != null && vb != null ? vb - va : null;
      return { key: k, label: (y || x).label, unit: (y || x).unit, a: va, b: vb, delta: d, pct: d != null && va ? d / Math.abs(va) * 100 : null }; });
  }

  // ── model outputs ──────────────────────────────────────────────────────
  function csvRows(text) {   // RFC 4180 enough: quoted fields with commas and doubled quotes
    const rows = []; let row = [], f = '', q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; continue; }
      if (c === '"') q = true; else if (c === ',') { row.push(f); f = ''; } else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(f); rows.push(row); row = []; f = ''; } else f += c;
    }
    if (f || row.length) { row.push(f); rows.push(row); }
    return rows.filter(r => r.some(x => x.trim()));
  }

  function checkHeader(h, errors) {
    for (const k of HEADER) if (!h[k]) errors.push(`the header has no ${k}`);
    if (h.date && !/^\d{4}-\d{2}-\d{2}$/.test(h.date)) errors.push('date must be YYYY-MM-DD');
    if (h.assumptions_url && !/^https?:\/\/\S+$/.test(h.assumptions_url)) errors.push('assumptions_url must be a web address');
    for (const k of HEADER) if (h[k] && personal(h[k])) errors.push(`${k} holds an e-mail address or a telephone number: name a team or organization, not a person's contact`);
  }

  /** text: the file's text. ids: the municipio codes (five digits), in order; "72" is Puerto Rico as a whole. */
  function parseModel(text, ids) {
    const errors = [], header = {}, recs = [];
    text = String(text || '');
    if (text.length > MAX_TEXT) return { header, series: [], errors: ['the file is larger than 5 MB'] };
    const t = text.replace(/^﻿/, '').trim();
    if (t.startsWith('{')) {
      let g; try { g = JSON.parse(t); } catch { return { header, series: [], errors: ['the GeoJSON is not valid JSON'] }; }
      if (!g || g.type !== 'FeatureCollection' || !Array.isArray(g.features)) return { header, series: [], errors: ['a GeoJSON model output is a FeatureCollection'] };
      const m = g.model || {}; HEADER.forEach(k => { if (m[k] != null) header[k] = clean(m[k], 300); });
      g.features.forEach(f => recs.push(f && f.properties ? f.properties : {}));
    } else {
      const lines = t.split(/\r?\n/), body = [];
      for (const l of lines) { const m = /^#\s*([a-z_]+)\s*:\s*(.*)$/.exec(l); if (m) { if (HEADER.includes(m[1])) header[m[1]] = clean(m[2], 300); } else if (!/^#/.test(l)) body.push(l); }
      const rows = csvRows(body.join('\n')); if (!rows.length) return { header, series: [], errors: ['no rows'] };
      const cols = rows[0].map(c => c.trim().toLowerCase());
      for (const c of COLUMNS) if (!cols.includes(c)) errors.push(`no column ${c}`);
      if (errors.length) return { header, series: [], errors };
      rows.slice(1).forEach(r => { const o = {}; cols.forEach((c, i) => { o[c] = r[i]; }); recs.push(o); });
    }
    checkHeader(header, errors);
    if (recs.length > MAX_ROWS) errors.push(`more than ${MAX_ROWS} rows`);
    const at = new Map(ids.map((id, i) => [id, i])), n = ids.length + 1, by = new Map();
    recs.slice(0, MAX_ROWS).forEach((r, k) => {
      const row = k + 1, key = String(r.geography_key == null ? '' : r.geography_key).trim(), lvl = String(r.geography_level || '').trim().toLowerCase(), period = String(r.period == null ? '' : r.period).trim(), variable = clean(r.variable, 60), unit = clean(r.unit, 20);
      const num = (x) => x === '' || x == null ? null : Number(x), value = num(r.value), lower = num(r.lower), upper = num(r.upper);
      if (lvl !== 'municipio') { errors.push(`row ${row}: geography_level "${lvl}" is not supported (municipio only)`); return; }
      const i = key === '72' ? ids.length : at.get(key); if (i == null) { errors.push(`row ${row}: "${key}" is not a municipio code`); return; }
      if (!/^\d{4}$/.test(period)) { errors.push(`row ${row}: period must be a year`); return; }
      if (!VARIABLE.test(variable)) { errors.push(`row ${row}: variable must be letters, digits, spaces, dots, dashes or underscores`); return; }
      if (personal(variable)) { errors.push(`row ${row}: variable holds a telephone number`); return; }
      if (personal(unit)) { errors.push(`row ${row}: unit holds an e-mail address or a telephone number`); return; }
      if (value == null || !isFinite(value)) { errors.push(`row ${row}: value is not a number`); return; }
      if ((lower != null && !(isFinite(lower) && lower <= value)) || (upper != null && !(isFinite(upper) && upper >= value))) { errors.push(`row ${row}: lower and upper must bracket the value`); return; }
      if (!by.has(variable)) by.set(variable, { variable, unit, years: {}, lower: {}, upper: {} });
      const s = by.get(variable); if (s.unit !== unit) { errors.push(`row ${row}: variable "${variable}" has two units`); return; }
      for (const [o, x] of [[s.years, value], [s.lower, lower], [s.upper, upper]]) { if (!o[period]) o[period] = new Array(n).fill(null); if (o === s.years && o[period][i] != null) errors.push(`row ${row}: a second value for ${key} in ${period}`); o[period][i] = x; }
    });
    const series = [...by.values()].map(s => ({ ...s, lower: Object.values(s.lower).some(a => a.some(x => x != null)) ? s.lower : null, upper: Object.values(s.upper).some(a => a.some(x => x != null)) ? s.upper : null }));
    return { header, series: errors.length ? [] : series, errors: errors.slice(0, 50) };
  }

  function diffSeries(a, b) {   // B − A for the periods both have; null where either is empty
    const years = {};
    for (const y of Object.keys(a.years)) if (b.years[y]) years[y] = a.years[y].map((x, i) => x == null || b.years[y][i] == null ? null : b.years[y][i] - x);
    return { variable: a.variable, unit: a.unit, years };
  }

  return { VERSION, HEADER, COLUMNS, make, check, read, diff, parseModel, diffSeries, personal };
});
