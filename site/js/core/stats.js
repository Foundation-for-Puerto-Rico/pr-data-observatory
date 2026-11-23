/* PR Data Observatory core: small statistics shared by the maps, the workbench and the chat. No data and no page state here: arrays in, numbers out.
   An array is "with the island": one value per place and, last, Puerto Rico as a whole (see docs/engine.md); `places` is how many places (the island is index `places`). */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('stats', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const finite = (x) => x != null && isFinite(x);
  const ascending = (a) => a.slice().sort((p, q) => p - q);

  /** Median of the values that are not null (null when there are none). */
  function median(a) {
    const v = a.filter(x => x != null).sort((x, y) => x - y);
    return v.length ? (v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2) : null;
  }

  /** Pearson correlation and the least-squares line of ys on xs: { n, r, slope, intercept, mx, my }. r is null when either side does not vary. */
  function pearson(xs, ys) {
    const n = xs.length, mx = xs.reduce((s, x) => s + x, 0) / n, my = ys.reduce((s, y) => s + y, 0) / n;
    let sxx = 0, syy = 0, sxy = 0;
    for (let i = 0; i < n; i++) { sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; sxy += (xs[i] - mx) * (ys[i] - my); }
    const slope = sxx ? sxy / sxx : 0;
    return { n, r: sxx && syy ? sxy / Math.sqrt(sxx * syy) : null, slope, intercept: my - slope * mx, mx, my };
  }

  /** "#rank of n" among the places (island excluded), highest first; { rank, n } or null when the place has no value. */
  function rank(a, i, places) {
    if (!a || a[i] == null || i === places) return null;
    const list = a.slice(0, places).filter(x => x != null).sort((p, q) => q - p);
    return { rank: list.indexOf(a[i]) + 1, n: list.length };
  }
  const prng = (s) => () => { s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const simCache = new WeakMap();
  /** Ranks each place could hold given 90% margins m: 1,000 seeded draws (mulberry32) from normals with sd m/1.645; 5th-95th percentile rank. [{ lo, hi } | null] */
  function rankRanges(a, m, places, draws = 1000) {
    if (!a || !m) return null; const c = simCache.get(a); if (c && c.m === m) return c.r;
    const idx = []; for (let j = 0; j < places; j++) if (a[j] != null) idx.push(j);
    const rnd = prng(1), z = () => Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(2 * Math.PI * rnd()), rk = idx.map(() => new Uint16Array(draws));
    for (let d = 0; d < draws; d++) { const v = idx.map(j => a[j] + (m[j] || 0) / 1.645 * z()); v.map((x, k) => k).sort((p, q) => v[q] - v[p]).forEach((k, r) => { rk[k][d] = r + 1; }); }
    const r = new Array(places).fill(null); idx.forEach((j, k) => { const s = rk[k].sort(); r[j] = { lo: s[Math.floor(.05 * draws)], hi: s[Math.ceil(.95 * draws) - 1] }; });
    simCache.set(a, { m, r }); return r;
  }
  const rangeAt = (r, i, n, desc) => { const g = r && r[i]; return !g || g.lo === g.hi ? '' : desc ? `${g.lo}–${g.hi}` : `${n + 1 - g.hi}–${n + 1 - g.lo}`; };   // as text, in the order shown
  function rankRange(a, m, i, places) { if (!a || !m || a[i] == null || m[i] == null || i === places) return null; return rankRanges(a, m, places)[i]; }

  /** Percentile (0 to 100) of every place among the places that have a value, island excluded; the island itself gets null. */
  function percentiles(a, places) {
    const vals = a.slice(0, places).filter(x => x != null).sort((p, q) => p - q);
    return a.map((x, i) => x == null || i === places ? null : vals.indexOf(x) / Math.max(1, vals.length - 1) * 100);
  }

  /** The values of the places (island excluded) that are numbers, ascending: what a class break is worked out from. */
  function pool(a, places) { const out = []; for (let i = 0; i < places; i++) if (finite(a[i])) out.push(a[i]); return out.sort((p, q) => p - q); }

  /** Ranks 1..n of a list of numbers, ties sharing the mean of their ranks (what Spearman's correlation needs). */
  function ranks(xs) {
    const order = xs.map((x, i) => i).sort((p, q) => xs[p] - xs[q]), out = new Array(xs.length);
    for (let i = 0; i < order.length;) { let j = i; while (j + 1 < order.length && xs[order[j + 1]] === xs[order[i]]) j++; const r = (i + j) / 2 + 1; for (let k = i; k <= j; k++) out[order[k]] = r; i = j + 1; }
    return out;
  }

  /** The correlation of two arrays over the places (island excluded) where both have a number: { r, n }. `method` is 'pearson' or 'spearman' (Pearson on the ranks). r is null below 3 places or when a side does not vary. */
  function correlation(a, b, places, method = 'pearson') {
    const xs = [], ys = [];
    for (let i = 0; i < places; i++) if (finite(a[i]) && finite(b[i])) { xs.push(a[i]); ys.push(b[i]); }
    if (xs.length < 3) return { r: null, n: xs.length };
    const p = method === 'spearman' ? pearson(ranks(xs), ranks(ys)) : pearson(xs, ys);
    return { r: p.r, n: xs.length };
  }

  /** Every pair of a list of arrays: { r: [[...]], n: [[...]] }, each pair over the places both have (pairwise complete). The diagonal is 1 and the count of places with a value. */
  function matrix(cols, places, method = 'pearson') {
    const k = cols.length, r = [...Array(k)].map(() => new Array(k).fill(null)), n = [...Array(k)].map(() => new Array(k).fill(0));
    for (let i = 0; i < k; i++) for (let j = i; j < k; j++) {
      const c = i === j ? { r: null, n: cols[i].slice(0, places).filter(finite).length } : correlation(cols[i], cols[j], places, method);
      r[i][j] = r[j][i] = i === j ? (c.n ? 1 : null) : c.r; n[i][j] = n[j][i] = c.n;
    }
    return { r, n };
  }

  /** Each value as a z-score over the places that have one (mean 0, standard deviation 1, the standard deviation of those places); null where there is no value or no spread. Island excluded and set to null. */
  function zscores(a, places) {
    const v = a.slice(0, places).filter(finite), m = v.reduce((s, x) => s + x, 0) / (v.length || 1), sd = Math.sqrt(v.reduce((s, x) => s + (x - m) ** 2, 0) / (v.length || 1));
    return a.map((x, i) => i >= places || !finite(x) || !sd ? null : (x - m) / sd);
  }

  /** The k places most like place i: the shortest distance over standardised features (each feature an array of values, island excluded, put on z-scores first).
      A place with a missing feature is left out. Returns [{ i, d }] nearest first, ties broken by index. */
  function peers(i, features, places, k = 5) {
    const Z = features.map(f => zscores(f, places)), ok = (j) => Z.every(z => z[j] != null);
    if (!ok(i)) return [];
    const out = [];
    for (let j = 0; j < places; j++) if (j !== i && ok(j)) out.push({ i: j, d: Math.sqrt(Z.reduce((s, z) => s + (z[j] - z[i]) ** 2, 0)) });
    return out.sort((p, q) => p.d - q.d || p.i - q.i).slice(0, k);
  }

  return { finite, ascending, median, pearson, rank, rankRange, rankRanges, rangeAt, percentiles, pool, ranks, correlation, matrix, zscores, peers };
});
