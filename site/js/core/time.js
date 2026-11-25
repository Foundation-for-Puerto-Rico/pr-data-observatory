/* PR Data Observatory core: time. Each dataset declares one time type and the year control treats it accordingly (docs/engine.md, section "Time").

   point     a dated count (census 2010, 2020)            shown for the chosen year, otherwise the latest at or before it (the date is shown)
   period    a calendar or fiscal year (QCEW, USAspending) the exact year, otherwise the latest at or before it (flagged)
   window    a survey window (ACS 5-year)                 the window ending at or before the year; the label gives the whole window (2020-2024)
   vintage   population estimates                         the latest vintage for each year
   snapshot  transit, places, flood, exposure             always the current one, labeled with its date; not animated
   static    boundaries, the land use plan                always shown
   event     storms, declarations                         filtered to the year (a count or a list, not a value for each place)

   Core.time.resolve(ds, year) -> { y, exact, early }: the year a dataset shows when the control says `year` (null = the latest). `early` says the dataset starts after the chosen year. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('time', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const TYPES = ['point', 'period', 'window', 'vintage', 'snapshot', 'static', 'event'];
  const FIXED = new Set(['snapshot', 'static']);   // not animated: one period only

  /** A dataset is fixed in time when it is a snapshot or static (or says so with `static: true`). */
  const isFixed = (ds) => !!ds && (!!ds.static || FIXED.has(ds.time && ds.time.type));

  function resolve(ds, year) {
    if (!ds || !ds.ys || !ds.ys.length) return { y: null, exact: false };
    const ys = ds.ys;
    if (isFixed(ds)) return { y: ys[0], exact: true };
    if (year == null) return { y: ys[ys.length - 1], exact: true };
    let y = null; for (const x of ys) if (x <= year) y = x;
    return y == null ? { y: ys[0], exact: false, early: true } : { y, exact: y === year };
  }

  /** The years the control offers: every year (from `from`) that at least one moving dataset has. */
  function years(datasets, from = 2010) {
    const s = new Set();
    for (const v of datasets) if (!isFixed(v)) v.ys.forEach(y => { if (y >= from) s.add(y); });
    return [...s].sort((a, b) => a - b);
  }

  /** The period a legend names for a dataset at year y: "2020–2024" for a window with a known start, otherwise the year. `ds.time.windowYears` is the length of a window (5 for ACS). */
  function label(ds, y) {
    if (y == null) return '';
    const t = ds && ds.time;
    if (t && t.type === 'window' && t.windowYears) return `${y - t.windowYears + 1}–${y}`;
    return String(y);
  }

  return { TYPES, isFixed, resolve, years, label };
});
