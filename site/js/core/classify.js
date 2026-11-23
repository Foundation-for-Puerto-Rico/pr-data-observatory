/* PR Data Observatory core: classification of values into classes for a shaded map, a legend or a bar colour.

   Core.classify.make(pool, { method, k, div, center, edges }) -> breaks
     pool     the values to classify, ascending (Core.stats.pool)
     method   'quantile' (equal counts), 'equal' (equal intervals), 'jenks' (natural breaks) or 'manual' (the inner breaks you give in `edges`)
     k        number of classes (5 for a map of one layer, 3 for each layer of a bivariate map)
     div      the scale runs both ways around `center`: five classes cut at 0.1 and 0.5 of the largest distance from the centre (only for k = 5)
   A breaks object is { edges: [min, b1 ... b(k-1), max], min, max }, or { div: true, center, span, min, max }.
   Core.classify.classOf(breaks, value, k) -> -1 (no value) or 0 ... k-1. A value on a break belongs to the lower class, as in every legend of the observatory.
   Quantile breaks are the values at ranks floor(n * i / k); when the lowest value fills two classes or more (mostly zeros), it gets one class (minFirst). */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('classify', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const JENKS_CAP = 1500;   // the dynamic programme is quadratic in the number of values: a longer pool is thinned to every nth value first

  function jenks(sorted, k) {
    const n = sorted.length; if (n <= k) return [sorted[0], ...sorted.slice(1), sorted[n - 1]].slice(0, k + 1);
    const m1 = Array.from({ length: n + 1 }, () => new Array(k + 1).fill(0)), m2 = Array.from({ length: n + 1 }, () => new Array(k + 1).fill(Infinity));
    for (let i = 1; i <= k; i++) { m1[1][i] = 1; m2[1][i] = 0; }
    let v = 0;
    for (let l = 2; l <= n; l++) {
      let s1 = 0, s2 = 0, w = 0;
      for (let m = 1; m <= l; m++) { const i3 = l - m + 1, val = sorted[i3 - 1]; s2 += val * val; s1 += val; w++; v = s2 - s1 * s1 / w; const i4 = i3 - 1; if (i4 !== 0) for (let j = 2; j <= k; j++) if (m2[l][j] >= v + m2[i4][j - 1]) { m1[l][j] = i3; m2[l][j] = v + m2[i4][j - 1]; } }
      m1[l][1] = 1; m2[l][1] = v;
    }
    const br = new Array(k + 1); br[k] = sorted[n - 1]; br[0] = sorted[0]; let kk = n;
    for (let j = k; j >= 2; j--) { const id = m1[kk][j] - 2; br[j - 1] = sorted[Math.max(0, id)]; kk = m1[kk][j] - 1; }
    return br;
  }

  function quantileEdges(pool, k) {
    const e = [pool[0]];
    for (let i = 1; i < k; i++) e.push(pool[Math.min(pool.length - 1, Math.floor(pool.length * i / k))]);
    e.push(pool[pool.length - 1]);
    return e;
  }
  const equalEdges = (mn, mx, k) => Array.from({ length: k + 1 }, (_, i) => mn + (mx - mn) * i / k);
  /** Quantile edges; when the lowest value fills two classes or more: [min, min, the k - 1 quantile classes of the values above min] */
  function minFirst(pool, k) {
    const e = quantileEdges(pool, k), up = pool.filter(x => x > e[0]);
    return k < 3 || e[2] !== e[0] || !up.length ? e : [e[0], e[0], ...quantileEdges(up, k - 1).slice(1, -1), e[k]];
  }

  function make(pool, o = {}) {
    const method = o.method || 'quantile', k = o.k || 5;
    if (!pool.length) return { edges: [0, 1], span: 1, min: 0, max: 1 };
    const mn = pool[0], mx = pool[pool.length - 1];
    if (o.div && k === 5) { const c = o.center ?? 0, span = Math.max(...pool.map(x => Math.abs(x - c))) || 1; return { div: true, center: c, span, min: mn, max: mx }; }
    let e;
    if (method === 'equal') e = equalEdges(mn, mx, k);
    else if (method === 'jenks') {
      const valid = (x) => Array.isArray(x) && x.length === k + 1 && x.every((v, i) => Number.isFinite(v) && (i === 0 || v >= x[i - 1]));
      try { e = jenks(pool.length > JENKS_CAP ? pool.filter((_, i) => i % Math.ceil(pool.length / JENKS_CAP) === 0) : pool, k); } catch (err) { e = null; }   // too few distinct values for k natural classes
      if (!valid(e)) e = minFirst(pool, k);
    }
    else if (method === 'manual' && o.edges && o.edges.length === k - 1) e = [mn, ...o.edges, mx];
    else e = minFirst(pool, k);
    return { edges: e, min: mn, max: mx };
  }

  function classOf(b, v, k = 5) {
    if (v == null || !isFinite(v)) return -1;
    if (b.div) { const t = (v - b.center) / b.span; return t < -.5 ? 0 : t < -.1 ? 1 : t <= .1 ? 2 : t <= .5 ? 3 : 4; }
    let i = 0; while (i < k - 1 && v > b.edges[i + 1]) i++; return i;
  }

  /** The inner breaks of a quantile classification of `pool` (k - 1 values, as make() cuts them): what a step expression in a map style needs. */
  const inner = (pool, k = 5) => pool.length ? minFirst(pool, k).slice(1, k) : [];

  /** Class i is one value: a legend names it by that value ("0%", not "0% to 0%"); above the first class it is always empty, and a legend leaves it out (hidden). */
  const single = (b, i) => !b.div && !!b.edges && b.edges[i] === b.edges[i + 1];
  const hidden = (b, i) => i > 0 && single(b, i);

  /** Break values made strictly rising, as MapLibre's step expression requires: a tied break is moved up by a hair, so a tied class stays empty as it does in the 2D map. */
  function risingStops(breaks, eps = 1e-6) {
    const stops = []; breaks.forEach(b => stops.push(Math.max(b + eps, stops.length ? stops[stops.length - 1] + eps : -Infinity)));
    return stops;
  }

  /** How a break text is worked out for a user: "10, 20, 30, 40" -> [10, 20, 30, 40]; null when it is not k - 1 rising numbers. */
  function parseBreaks(text, k = 5) {
    const v = String(text || '').split(/[\s;,]+/).filter(Boolean).map(Number);
    return v.length === k - 1 && v.every(isFinite) && v.every((x, i) => i === 0 || x > v[i - 1]) ? v : null;
  }

  return { jenks, quantileEdges, equalEdges, minFirst, make, classOf, inner, single, hidden, risingStops, parseBreaks, JENKS_CAP };
});
