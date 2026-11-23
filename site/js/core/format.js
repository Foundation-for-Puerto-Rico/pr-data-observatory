/* PR Data Observatory core: how a value is written. One place for the number formats of every legend, popup, table and chart, so a figure reads the same everywhere.
   The page supplies `fmt(n, decimals)` (the language layer: Spanish in Puerto Rico uses the US number form) and `T`; without them (tests) plain English numbers are used. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('format', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, num } = dep('text');

  /** A short form for a legend or an axis: 1.2K, 3.4M, $5.6B. `unit` is the unit of the dataset after normalisation ('$', '%', ' pts' or ''). */
  function compact(v, unit, d) {   // d: the decimals of a dataset that says how many a small number needs (dPer); the others keep two
    const s = Math.abs(v), sign = v < 0 ? '−' : '';
    const body = s >= 1e9 ? T('{n}B', { n: (s / 1e9).toFixed(s >= 1e10 ? 0 : 1) }) : s >= 1e6 ? T('{n}M', { n: (s / 1e6).toFixed(s >= 1e7 ? 0 : 1) }) : s >= 1e4 ? T('{n}K', { n: Math.round(s / 1e3) }) : s >= 1000 ? T('{n}K', { n: (s / 1e3).toFixed(1) }) : s >= 100 ? Math.round(s) : d != null ? s.toFixed(d) : s >= 10 ? s.toFixed(1) : s.toFixed(2);
    return `${sign}${unit === '$' ? '$' : ''}${body}${unit === '%' ? '%' : unit === ' pts' ? ' pts' : ''}`;
  }

  /** A value of a dataset `ds` that is shown with the unit and decimals `o` (Core.normalize.describe). null and NaN are a dash. */
  function value(ds, o, x, short) {
    if (x == null || !isFinite(x)) return '—';
    if (short) return compact(x, o.unit, ds.dPer != null ? o.d : undefined);
    if (ds.plain) return String(Math.round(x));
    if (o.unit === '$') return (x < 0 ? '−$' : '$') + num(Math.abs(Number(x)), o.d);
    return `${num(x, o.d)}${o.unit === '%' ? '%' : o.unit === ' pts' ? ' pts' : ''}`;
  }

  return { compact, value, num };
});
