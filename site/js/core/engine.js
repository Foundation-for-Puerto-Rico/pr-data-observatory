/* PR Data Observatory core: the layer engine. One object that holds the datasets of every domain, resolves what period each shows, normalises, classifies and describes them, so that
   the map, the legend, the popup, the workbench, the chat and the 3D view all ask the same thing and get the same answer (docs/engine.md).

     const E = Core.engine.create();                  // an engine; the page keeps one
     Core.adapters.series(E, econ, hous);              // adapters turn a published file into datasets (adapters.js): series, snapshot fields, exposure, derived
     E.values(key, { year, norm, real, base })         // the numbers of a dataset as a layer would show them (what the chat reads)
     E.series(layer, period, level)                    // the contract: { ids, names, values, moe, flags, meta } for any level a dataset has
     E.reliability(layer, evaluation)                  // which places are flagged less reliable: a wide margin of error, fewer than 10 counted (reliability.js)

   Arrays are "with the island": one value for each place, in the order of E.geo.ids, and last the value for Puerto Rico as a whole (index E.geo.pr).
   A layer is what a person puts on the map: { key, mode: 'fill' | 'symbol', norm, ramp, classes, fixed, opacity, visible, real, color }. It carries no data. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('engine', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, lang } = dep('text'), palettes = dep('palettes'), classify = dep('classify'), norm = dep('normalize'), time = dep('time'), format = dep('format'), reliability = dep('reliability');
  const MODE_CODE = { fill: 'f', symbol: 's' }, CLASS_CODE = { quantile: 'q', equal: 'e', jenks: 'j', manual: 'm' }, CLASS_NAME = { q: 'quantile', e: 'equal', j: 'jenks', m: 'manual' };
  const RMAX = (small) => small ? 20 : 30;   // largest symbol radius in pixels (smaller on a phone)

  function create() {
    const E = {
      V: Object.create(null), geo: { ids: [], names: [], pr: 0, area: [] }, year: null, base: 2014, cpi: {}, cpiRef: null, snapYear: 2026,   // V has no prototype: a link asking for 'constructor' or 'toString' finds no dataset
      sources: {}, notes: {}, extras: {}, built: null, cache: {},
      denominators: { pop: 'population', jobs: 'qcew_jobs', hu: 'housing_units' },   // the datasets other datasets are divided by
    };

    // ── Datasets and places ──────────────────────────────────────────────────
    E.add = (ds) => {
      if (!ds.ys) ds.ys = Object.keys(ds.years).map(Number).sort((a, b) => a - b);
      if (ds.key === E.denominators.pop) ds.residents = true;   // the residents other datasets are divided by: per 1,000 residents would be 1,000 everywhere (normalize.js), so it is not offered and a shaded layer starts as people per km²
      E.V[ds.key] = ds; E.cache = {}; return ds;
    };
    E.setGeo = (ids, names, area) => { E.geo = { ids, names, pr: names.length - 1, area }; E.cache = {}; };
    E.setDeflator = (cpi) => { E.cpi = Object.fromEntries(Object.entries(cpi || {}).map(([y, v]) => [+y, v])); const ys = Object.keys(E.cpi).map(Number); E.cpiRef = ys.length ? Math.max(...ys) : null; };
    E.list = () => Object.values(E.V);
    E.years = () => time.years(E.list());
    E.arr = (key, y) => { const v = E.V[key]; return v && v.years[y] ? v.years[y] : null; };
    E.placeIndex = (name) => { const n = (name || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim(); return E.geo.names.findIndex(x => x.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim() === n); };

    // ── What the normalisations divide by ────────────────────────────────────
    E.pop = (y) => { const v = E.V[E.denominators.pop]; let k = v.ys[0]; for (const x of v.ys) if (x <= y) k = x; return v.years[k]; };
    E.jobs = (y) => { const v = E.V[E.denominators.jobs]; if (!v) return null; let k = v.ys[0]; for (const x of v.ys) if (x <= y) k = x; if (y < v.ys[0]) return null; return v.years[k]; };
    E.hu = (y) => { const v = E.V[E.denominators.hu]; if (!v) return null; let k = v.ys[0]; for (const x of v.ys) if (x <= y) k = x; return v.years[k]; };   // housing units (ACS): the latest year at or before y
    E.cpiFactor = (y) => { if (!E.cpiRef) return 1; const ks = Object.keys(E.cpi).map(Number); const yy = Math.min(Math.max(y, Math.min(...ks)), Math.max(...ks)); return E.cpi[E.cpiRef] / E.cpi[yy]; };
    E.ctx = (base = E.base) => ({ pr: E.geo.pr, area: E.geo.area, base, arr: E.arr, pop: E.pop, jobs: E.jobs, hu: E.hu, cpi: E.cpiFactor });

    // ── One layer: its period, values, classes ───────────────────────────────
    E.resolve = (key, year = E.year) => time.resolve(E.V[key], year);
    E.normOptions = (key) => norm.options(E.V[key]);
    E.out = (L) => norm.describe(E.V[L.key], L.norm);
    E.calc = (L, y, base = E.base) => norm.compute(E.V[L.key], L, y, E.ctx(base));
    E.fmt = (L, x, short) => format.value(E.V[L.key], E.out(L), x, short);
    E.missing = (L, i) => { const v = E.V[L.key]; return v && v.noValue && i !== E.geo.pr ? T(v.noValue) : null; };   // what an empty place means when the dataset says so (a shortage area: "No area shortage designation"); Puerto Rico is empty for another reason
    E.pool = (L, current) => {   // the values the classes are cut from: every year at once when the classes are held fixed, else the year shown
      const v = E.V[L.key], ys = L.fixed && !v.static ? v.ys : [current], out = [];
      for (const y of ys) { const a = E.calc(L, y); if (a) for (let i = 0; i < E.geo.pr; i++) if (a[i] != null && isFinite(a[i])) out.push(a[i]); }
      return out.sort((p, q) => p - q);
    };
    E.breaks = (L, current, k = 5) => {
      const key = [L.key, L.norm, L.real, E.base, L.classes, L.breaks || '', L.fixed ? 'f' : current, k].join('|'); if (E.cache[key]) return E.cache[key];
      const o = E.out(L), manual = L.classes === 'manual' ? classify.parseBreaks(L.breaks, k) : null;
      return E.cache[key] = classify.make(E.pool(L, current), { method: manual ? 'manual' : L.classes === 'manual' ? 'quantile' : L.classes, k, div: o.div, center: o.center, edges: manual });
    };
    E.ramp = (L) => palettes.ramp(L.ramp);
    E.evaluate = (layers) => { const ev = {}; for (const L of layers) { const r = E.resolve(L.key), a = r.y == null ? null : E.calc(L, r.y); ev[L.id] = { ...r, a }; } return ev; };
    /** The margins of error (90% confidence) of the values a layer shows, scaled like the values; null when the dataset has none or the layer is normalised. */
    E.moe = (L, y) => { const v = E.V[L.key]; const m = L.norm === 'value' && v.moe ? v.moe[y] : null; if (!m) return null; const f = v.unit === '$' && L.real ? E.cpiFactor(y) : 1; return f === 1 ? m : m.map(x => x == null ? null : x * f); };

    // ── How far the values can be trusted (reliability.js) ───────────────────
    const relCache = new WeakMap();
    /** What is flagged less reliable in layer L for its evaluation `ev`: { moe, small, flagged, withheld, notCarried, n }, one entry for each place (the island excluded). */
    E.reliability = (L, ev) => { if (!ev) return reliability.assess(E, L, ev); let r = relCache.get(ev); if (!r) { r = reliability.assess(E, L, ev); relCache.set(ev, r); } return r; };
    /** The places (indexes, the island excluded) where any of these layers is flagged less reliable. */
    E.flagged = (layers, evals) => { const out = new Set(); for (const L of layers) E.reliability(L, evals[L.id]).flagged.forEach((f, i) => { if (f) out.add(i); }); return [...out].sort((p, q) => p - q); };
    /** The limits a layer starts with when its classes are switched to "my own limits": the four inner breaks of the classes it has now, to three digits, as text. */
    E.manualDefault = (L, y) => { const b = E.breaks({ ...L, classes: L.classes === 'manual' ? 'quantile' : L.classes }, y); return b.edges ? b.edges.slice(1, -1).map(x => String(+x.toPrecision(3))).join(', ') : ''; };

    // ── Text about a layer ───────────────────────────────────────────────────
    const lc = (s) => lang() === 'en' ? s.toLowerCase() : s.replace(/^./, c => c.toLowerCase());   // a label inside a title: English lower-cases all of it; Spanish only the first letter, so "Puerto Rico" keeps its capitals
    E.lc = lc;
    E.normLabel = (L) => { const o = norm.options(E.V[L.key]).find(n => n[0] === L.norm); return o ? T(o[1]) : L.norm; };
    E.title = (L, y) => {
      const v = E.V[L.key], nopt = norm.options(v).find(n => n[0] === L.norm);
      const real = v.unit === '$' && L.real ? `, ${T('{year} dollars', { year: E.cpiRef })}` : '';
      return `${T(v.label)}${L.norm === 'value' ? '' : ' · ' + (nopt ? lc(T(nopt[1])) : L.norm)}${L.norm === 'change' ? ` (${E.base} → ${y ?? ''})` : ''}${real}`;
    };
    E.chip = (L, ev) => {   // which period a layer shows: a year, or the whole window of a survey (2020–2024)
      if (!ev || ev.y == null) return '';
      const v = E.V[L.key], lab = time.label(v, ev.y);
      return time.isFixed(v) ? T('snapshot {year}', { year: ev.y }) : ev.exact ? lab : ev.early ? T('first data {year}', { year: lab }) : T('{year} (latest at or before {max})', { year: lab, max: E.year });
    };

    // ── Colours of a shaded layer or two, and the sizes of symbols ───────────
    /** One colour for each place (island excluded) from the first visible shaded layer, or the first two together as a bivariate map (three classes each). */
    E.fillColors = (fills, evals) => {
      const A = fills[0], B = fills[1], ea = evals[A.id], ba = E.breaks(A, ea.y), eb = B && evals[B.id], bb = B && E.breaks(B, eb.y, 3), ba3 = B && E.breaks(A, ea.y, 3);
      return Array.from({ length: E.geo.pr }, (_, i) => {
        if (B) { const ca = classify.classOf(ba3, ea.a[i], 3), cb = classify.classOf(bb, eb.a[i], 3); return ca < 0 || cb < 0 ? palettes.NOVAL : palettes.BIVARIATE[cb][ca]; }
        const c = classify.classOf(ba, ea.a[i]); return c < 0 ? palettes.NOVAL : (ba.div ? palettes.DIVERGING : E.ramp(A))[c];
      });
    };
    /** Symbols of a layer: one per place with a value, largest first; the area of a symbol is proportional to the value. `small` is true on a phone. */
    E.symbols = (L, ev, small) => {
      const a = ev.a, pool = E.pool(L, ev.y), mx = pool.length ? Math.max(...pool.map(Math.abs)) : 1, sign = pool.some(x => x < 0), rmax = RMAX(small);
      const rows = E.geo.names.slice(0, E.geo.pr).map((n, i) => ({ n, i, v: a[i] })).filter(r => r.v != null && isFinite(r.v)).sort((p, q) => Math.abs(q.v) - Math.abs(p.v));
      return { mx, sign, rmax, rows: rows.map(r => ({ ...r, r: Math.max(2.5, rmax * Math.sqrt(Math.abs(r.v) / (mx || 1))), fill: sign && r.v < 0 ? '#B82415' : sign ? '#205D7B' : L.color })) };
    };

    // ── Making layers, and writing them to and reading them from a link ──────
    /** A new layer for dataset `key`, with the defaults of the stack it joins (`layers`); { error: 'two-fills' } when the stack already shades two datasets. */
    E.makeLayer = (key, mode, opts = {}, layers = []) => {
      const v = E.V[key]; if (!v) return null;
      const fills = layers.filter(l => l.mode === 'fill').length, syms = layers.filter(l => l.mode === 'symbol').length;
      if (mode === 'fill' && fills >= 2) return { error: 'two-fills' };
      const L = { key, mode, norm: opts.norm || norm.defaultNorm(v, mode), ramp: opts.ramp || palettes.RAMP_ORDER[fills % palettes.RAMP_ORDER.length], classes: opts.classes || v.classes || 'quantile', fixed: opts.fixed !== false, opacity: opts.opacity ?? (mode === 'fill' ? .85 : .75), visible: opts.visible !== false, real: !!opts.real, color: opts.color || palettes.SYMBOLS[syms % palettes.SYMBOLS.length] };
      if (opts.breaks) L.breaks = opts.breaks;
      const lv = opts.level || v.level; if (lv && mode === 'fill') L.level = lv;   // a dataset with barrio values only (WCRP) starts by barrio
      if (v.static) L.fixed = false;
      return L;
    };
    E.encode = (layers) => layers.map(l => [l.key, l.level === 'barrio' ? 'b' : MODE_CODE[l.mode], l.norm, l.ramp, CLASS_CODE[l.classes] || 'q', l.visible ? 1 : 0, l.fixed ? 1 : 0, l.real ? 1 : 0, Math.round(l.opacity * 100), palettes.SYMBOLS.indexOf(l.color), ...(l.classes === 'manual' && l.breaks ? [String(l.breaks).replace(/[\s,]+/g, '~')] : [])].join('.')).join(',');
    E.decode = (str) => {   // a list of layers from a link; datasets this engine does not have are skipped, a normalisation the dataset does not offer becomes its own start in restore() ("as published" for a rate or a score); a link with no class field takes the dataset's own start (makeLayer: natural breaks for the zero-heavy health counts, quantiles for the rest)
      const out = [];
      String(str || '').split(',').forEach(t => {
        const f = t.split('.'), [key, m, n, ramp, cl, vis, fixed, real, op, col] = f, br = f.slice(10).join('.'); if (!E.V[key]) return;   // the limits come last and may hold decimal points (1.79~2.6): everything after the tenth field is theirs
        const opts = { norm: n, ramp: ramp && !Object.prototype.hasOwnProperty.call(palettes.RAMPS, ramp) ? 'blue' : ramp, classes: Object.prototype.hasOwnProperty.call(CLASS_NAME, cl) ? CLASS_NAME[cl] : undefined, visible: vis !== '0', fixed: fixed !== '0', real: real === '1', opacity: (+op || 80) / 100, color: palettes.SYMBOLS[+col] || undefined, breaks: br ? br.replace(/~/g, ', ') : undefined };
        if (m === 'b') opts.level = 'barrio';
        out.push({ key, mode: m === 's' ? 'symbol' : 'fill', opts });
      });
      return out;
    };
    E.restore = (str, layers = []) => {   // layers from a link, added one after the other (so the defaults of each follow the ones before it)
      const made = [];
      for (const { key, mode, opts } of E.decode(str)) {
        const L = E.makeLayer(key, mode, opts, [...layers, ...made]); if (!L || L.error) continue;
        const offered = (n) => norm.options(E.V[key]).some(o => o[0] === n);
        if (!offered(L.norm)) { const d = norm.defaultNorm(E.V[key], L.mode); L.norm = offered(d) ? d : 'value'; }   // a view the dataset does not offer (an old link: the population per 1,000 residents) becomes the dataset's own start, so a count is not shaded raw
        made.push(L);
      }
      return made;
    };

    // ── What other code reads: the chat, the workbench, the pages ────────────
    E.info = () => E.list().map(v => ({ key: v.key, label: v.label, group: v.group, unit: v.unit, type: v.type, family: v.family || null, sources: v.sources || [], years: v.ys, snapshot: time.isFixed(v), definition: v.definition, ref: v.ref, moe: !!v.moe }));
    E.dictId = (key) => { const v = E.V[key]; return v ? (v.dictId || ((v.housing || v.from === 'housing') ? 'housing.' : 'economy.') + key) : null; };
    E.values = (key, { year = null, norm: n = 'value', real = false, base = null } = {}) => {
      const v = E.V[key]; if (!v) return null;
      const L = { id: -1, key, mode: 'fill', norm: n, real, ramp: 'blue', classes: 'quantile', fixed: true, opacity: .85, visible: true, color: palettes.SYMBOLS[0] };
      const r = E.resolve(key, year), a = r.y == null ? null : E.calc(L, r.y, base != null ? base : E.base);
      return a ? { year: r.y, exact: r.exact, values: a, layer: L } : null;
    };
    /** The contract of the engine: the values of a layer for a period at a level. `level` is a place level the dataset has ('municipio' for every dataset today; a dataset can add barrio and tract).
        Returns { ids, names, values, moe, flags, meta }: values and moe are in the order of ids and (for the municipio level) end with Puerto Rico. */
    E.series = (layer, period = null, level = 'municipio') => {
      const v = E.V[layer.key]; if (!v) return null;
      const lv = v.levels && v.levels[level];   // a dataset that has finer levels (barrio, tract) says how to read them
      if (level !== 'municipio' && !lv) return null;
      const r = time.resolve(v, period), L = { norm: 'value', real: false, ...layer };
      if (lv) return lv.series(E, L, r, period);
      const a = r.y == null ? null : E.calc(L, r.y);
      const m = r.y == null ? null : E.moe(L, r.y);
      return { ids: E.geo.ids, names: E.geo.names, values: a, moe: m, flags: { exact: r.exact, early: !!r.early, noValue: a ? a.map(x => x == null) : null },
        meta: { key: v.key, level, period: r.y, timeType: (v.time && v.time.type) || (time.isFixed(v) ? 'snapshot' : 'period'), unit: E.out(L).unit, decimals: E.out(L).d, label: v.label, norm: L.norm } };
    };
    return E;
  }

  return { create, MODE_CODE, CLASS_CODE, RMAX };
});
