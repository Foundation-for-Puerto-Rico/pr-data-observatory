/* PR Data Observatory core: normalisation. A count of jobs shaded on a map only shows which municipality is big; a rate shows something about the place. A dataset offers the
   normalisations that make sense for its kind (extensive: a count or a dollar total; intensive: a rate, a ratio or a typical value), as the Economy tab always did:

   value      as published                           per1000    per 1,000 residents                    perkm2     per km² of land
   perCapita  $ per resident (dollar totals)         sharePR    % of the Puerto Rico total             shareJobs  % of the municipality's jobs
   lq         location quotient (Puerto Rico = 1)    index      index (Puerto Rico = 100)              diff       difference from Puerto Rico
   change     change since the base year             pctile     percentile among the municipalities    shareArea  % of the area's residents (or housing units): exposure counts
   perHU      per 1,000 housing units (ACS; the latest year at or before the one shown), for counts of things that sit on housing: not jobs, not exposure counts

   A dataset is { key, type: 'count' | 'total$' | 'level$' | 'rate' | 'ratio', unit, d (decimals), family, static, noShare, noIsland, dPer, ys, years: {year: array with the island last}, denom, residents }.
   `residents` marks the count of the residents themselves (the survey's population): per 1,000 residents would read about 1,000 everywhere, so that view is not offered and a shaded layer starts as people per km².
   noIsland: the dataset has no value for Puerto Rico as a whole (a score is not added or averaged), so it offers neither the index nor the difference from Puerto Rico.
   noValue, classes, counted: what an empty place means ("No area shortage designation"), how a layer's classes start ('jenks' for zero-heavy counts and discrete scores; quantiles otherwise), and `counted: false` for administrative counts (no 'fewer than 10 counted' flag): read by the legend, the pop-up, the table, the engine and Core.reliability.
   noPerHU: a count that does not sit on housing (health centers) offers no "per 1,000 housing units". tag: the word the dataset window shows for the kind of figure instead of the type ("score").
   dPer: decimals of the per-resident, per-housing-unit and per-km² views when one is too few (sites for every 1,000 residents run from 0.02 to 1.2); the default is 1.
   Core.normalize.options(ds) -> [[id, English label]]; Core.normalize.describe(ds, norm) -> { unit, d, div, center, suffix } for formatting and for the scale;
   Core.normalize.compute(ds, layer, y, ctx) -> array with the island last, or null. `ctx` is the engine: { pr, area, base, arr(key, y), pop(y), jobs(y), cpi(y) }. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('normalize', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T } = dep('text'), stats = dep('stats');

  const extensive = (v) => v.type === 'count' || v.type === 'total$';

  function options(v) {
    const o = [['value', 'As published']];   // shares of the island total make no sense for a series that is near zero or negative (federal loans)
    if (v.denom) o.push(['shareArea', v.denom.label || '% of the area total']);
    if (v.type === 'count') { if (!v.residents) o.push(['per1000', 'Per 1,000 residents']); if (v.family !== 'jobs' && !v.denom && !v.noPerHU && v.key !== 'housing_units') o.push(['perHU', 'Per 1,000 housing units']); o.push(['perkm2', 'Per km²'], ['sharePR', '% of the Puerto Rico total']); if (v.family === 'jobs') o.push(['shareJobs', "% of the municipality's jobs"], ['lq', 'Location quotient (Puerto Rico = 1)']); }
    else if (v.type === 'total$') { o.push(['perCapita', '$ per resident'], ['perkm2', '$ per km²']); if (!v.noShare) o.push(['sharePR', '% of the Puerto Rico total']); }
    else if (!v.noIsland) o.push(['index', 'Index (Puerto Rico = 100)'], ['diff', 'Difference from Puerto Rico']);   // a score has no value for Puerto Rico as a whole, so nothing to compare with
    if (!v.static) o.push(['change', 'Change since the base year']);
    o.push(['pctile', 'Percentile among municipalities']);
    return o;
  }

  /** The norm a layer starts with: a count or a total is shaded per resident (symbols keep the raw value); an exposure count is shaded as a share of its area. */
  function defaultNorm(v, mode) {
    if (mode !== 'fill') return 'value';
    if (v.denom) return 'shareArea';
    if (v.residents) return 'perkm2';
    return extensive(v) ? (v.type === 'total$' ? 'perCapita' : 'per1000') : 'value';
  }

  function describe(v, n) {   // unit, decimals and whether the scale is diverging, after normalisation
    if (n === 'value') return { unit: v.unit, d: v.d, div: false };
    if (n === 'per1000') return { unit: '', d: v.dPer ?? 1, div: false, suffix: ' ' + T('per 1,000') };
    if (n === 'perHU') return { unit: '', d: v.dPer ?? 1, div: false, suffix: ' ' + T('per 1,000 housing units') };
    if (n === 'perkm2') return { unit: v.unit === '$' ? '$' : '', d: v.unit === '$' ? 0 : (v.dPer ?? 1), div: false, suffix: ' ' + T('per km²') };
    if (n === 'perCapita') return { unit: '$', d: 0, div: false, suffix: ' ' + T('per resident') };
    if (n === 'sharePR') return { unit: '%', d: 2, div: false };
    if (n === 'shareJobs') return { unit: '%', d: 1, div: false };
    if (n === 'shareArea') return { unit: '%', d: 1, div: false };
    if (n === 'lq') return { unit: '', d: 2, div: true, center: 1 };
    if (n === 'index') return { unit: '', d: 0, div: true, center: 100, suffix: ' (PR = 100)' };
    if (n === 'diff') return { unit: v.unit === '%' ? ' pts' : v.unit, d: v.unit === '$' ? 0 : v.d, div: true, center: 0 };
    if (n === 'change') return { unit: v.type === 'rate' ? ' pts' : v.type === 'ratio' ? '' : '%', d: v.type === 'ratio' ? 2 : 1, div: true, center: 0 };
    if (n === 'pctile') return { unit: '', d: 0, div: false, suffix: ' ' + T('percentile') };
    return { unit: v.unit, d: v.d, div: false };
  }

  function compute(v, L, y, ctx) {
    let a = ctx.arr(L.key, y); if (!a) return null; a = a.slice();
    const dollars = v.unit === '$', f = dollars && L.real ? ctx.cpi(y) : 1; if (f !== 1) a = a.map(x => x == null ? null : x * f);
    const PR = ctx.pr, pr = a[PR], n = L.norm;
    switch (n) {
      case 'value': return a;
      case 'per1000': { const p = ctx.pop(y); return a.map((x, i) => x == null || !p[i] ? null : +(x / p[i] * 1000).toFixed(3)); }
      case 'perHU': { const h = ctx.hu ? ctx.hu(y) : null; return h ? a.map((x, i) => x == null || !h[i] ? null : +(x / h[i] * 1000).toFixed(3)) : null; }
      case 'perCapita': { const p = ctx.pop(y); return a.map((x, i) => x == null || !p[i] ? null : x / p[i]); }
      case 'perkm2': return a.map((x, i) => x == null || !ctx.area[i] ? null : x / ctx.area[i]);
      case 'sharePR': return a.map(x => x == null || !pr ? null : x / pr * 100);
      case 'shareJobs': { const j = ctx.jobs(y); return j ? a.map((x, i) => x == null || !j[i] ? null : x / j[i] * 100) : null; }
      case 'shareArea': { const t = v.denom && v.denom.total; return t ? a.map((x, i) => x == null || !t[i] ? null : x / t[i] * 100) : null; }
      case 'lq': { const j = ctx.jobs(y); if (!j || !pr || !j[PR]) return null; return a.map((x, i) => x == null || !j[i] ? null : (x / j[i]) / (pr / j[PR])); }
      case 'index': return a.map(x => x == null || !pr ? null : x / pr * 100);
      case 'diff': return a.map(x => x == null || pr == null ? null : x - pr);
      case 'change': {
        const ys = v.ys.filter(k => k <= ctx.base); if (!ys.length || y <= ys[ys.length - 1]) return null;
        let b = ctx.arr(L.key, ys[ys.length - 1]).slice(); const fb = dollars && L.real ? ctx.cpi(ys[ys.length - 1]) : 1; if (fb !== 1) b = b.map(x => x == null ? null : x * fb);
        return a.map((x, i) => x == null || b[i] == null ? null : v.type === 'rate' || v.type === 'ratio' ? x - b[i] : (b[i] ? (x - b[i]) / b[i] * 100 : null));
      }
      case 'pctile': return stats.percentiles(a, PR);
    }
    return a;
  }

  return { options, defaultNorm, describe, compute, extensive };
});
