/* PR Data Observatory core: how far a value can be trusted, and the words that say so. One module decides which values are flagged and one wording describes each flag, so the map, the legend,
   the pop-up, the tables and the Housing page warn about the same values in the same way (docs/engine.md, "Reliability").

   Three things make a value less reliable than it looks:
     margin of error   a survey estimate (ACS) whose published margin (90% confidence) is above 30% of the estimate; an estimate of zero with any margin counts
     small number      a rate or a share built on fewer than 10 counted: one more or one less moves it a lot (a dataset of administrative counts, such as the health center sites HRSA lists, says `counted: false`: a site is a site, the count is not an estimate from a few cases)
     withheld          the source hides a figure that could identify one employer (QCEW), so the place has no value
   The flags describe the published estimates. Margins of error are not carried through a normalization (per 1,000 residents, index, change ...); the layer says so.

     Reliability.isUnreliable(value, moe)    true when a margin of error is above 30% of the estimate
     Reliability.assess(E, L, ev)            { moe, small, flagged, withheld, notCarried, n }: for each place (the island is not among them) whether a flag applies, and how many places each flag marks
     Reliability.notes(E, L, ev)             the lines a legend shows under a layer: [{ kind, n, swatch, label }]; swatch is 'hatch' (shaded layers), 'dash' (symbols) or null
     Reliability.cautions(ds)                the standing cautions of a dataset, for its information card: [{ kind, text }]
     Reliability.moeKey(), flagKey(), lessReliable()   the sentences that explain "±" and italics, and the hidden text a screen reader hears
   The thresholds are conventions, not statistical tests: 30% is the rule the Housing page has always used, and fewer than 10 is the usual point below which a count is treated as small. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('reliability', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, Th } = dep('text');
  const MOE_SHARE = 0.3, SMALL_COUNT = 10;
  const SMALL_NORMS = new Set(['per1000', 'perHU', 'shareJobs', 'shareArea', 'lq']);   // views that divide a count by something: a rate or a share of a small count is unstable

  /** A margin of error above 30% of the estimate. An estimate of zero has no share to compute, and any margin on it is too wide to read. */
  const isUnreliable = (value, moe) => value != null && moe != null && moe > 0 && (value === 0 || moe / Math.abs(value) > MOE_SHARE);

  const baseYear = (v, base) => { const ys = v.ys.filter(k => k <= base); return ys.length ? ys[ys.length - 1] : null; };

  /** What is flagged in layer L for its evaluation `ev` ({ y, a }): arrays with one entry for each place (the island excluded). `E` is the engine. */
  function assess(E, L, ev) {
    const pr = E.geo.pr, out = { moe: null, small: null, flagged: new Array(pr).fill(false), withheld: 0, notCarried: false, n: { moe: 0, small: 0, flagged: 0 } };
    if (!ev || !ev.a || ev.y == null) return out;
    const v = E.V[L.key], y = ev.y, a = ev.a;
    if (v.moe && v.moe[y] && v.years[y]) {
      const val = v.years[y], m = v.moe[y], yb = L.norm === 'change' ? baseYear(v, E.base) : null, vb = yb != null ? v.years[yb] : null, mb = yb != null ? v.moe[yb] : null;   // a change is as uncertain as the less certain of its two years
      out.moe = Array.from({ length: pr }, (_, i) => a[i] != null && (isUnreliable(val[i], m[i]) || !!(mb && vb && isUnreliable(vb[i], mb[i]))));
      out.notCarried = L.norm !== 'value';
    }
    let counted = null;   // the count each value rests on
    if (v.counted === false) counted = null;   // the dataset opts out: its counts are what the source lists, not estimates
    else if (v.counted) counted = Array.isArray(v.counted) ? v.counted : v.counted[y];
    else if (v.type === 'count' && SMALL_NORMS.has(L.norm)) counted = v.years[y];
    if (counted) out.small = Array.from({ length: pr }, (_, i) => a[i] != null && counted[i] != null && counted[i] > 0 && counted[i] < SMALL_COUNT);
    if (v.withheld) out.withheld = a.slice(0, pr).filter(x => x == null).length;
    for (let i = 0; i < pr; i++) out.flagged[i] = !!((out.moe && out.moe[i]) || (out.small && out.small[i]));
    out.n = { moe: out.moe ? out.moe.filter(Boolean).length : 0, small: out.small ? out.small.filter(Boolean).length : 0, flagged: out.flagged.filter(Boolean).length };
    return out;
  }

  /** The lines under a layer in a legend. A shaded layer is hatched where it is flagged, a layer of symbols has a dashed outline; both are also written, so color is never the only cue. */
  function notes(E, L, ev) {
    const r = assess(E, L, ev), fill = L.mode !== 'symbol', swatch = fill ? 'hatch' : 'dash', out = [];
    if (r.n.moe) out.push({ kind: 'moe', n: r.n.moe, swatch, label: fill ? T('Hatched: margin of error above 30% of the estimate') : T('Dashed outline: margin of error above 30% of the estimate') });
    if (r.n.small) out.push({ kind: 'small', n: r.n.small, swatch, label: fill ? T('Hatched: fewer than 10 counted') : T('Dashed outline: fewer than 10 counted') });
    if (r.n.flagged && r.notCarried) out.push({ kind: 'notCarried', n: 0, swatch: null, label: T('Margins of error are not carried through this view; the flags use the published estimates') });
    if (r.withheld) out.push({ kind: 'withheld', n: r.withheld, swatch: null, label: T('No value where the source withholds a figure that could identify one employer, or reports none') });
    return out;
  }

  /** Cautions that always go with a kind of dataset (its card shows them): a survey, a count at the workplace, a figure withheld, the dataset's own `caution` when its file gives one, and, for every dataset, that an area is not its people. */
  function cautions(v) {
    const out = [], src = v.sources || [];
    if (v.moe || src.includes('acs')) out.push({ kind: 'survey', text: T('A survey estimate: noisy for small municipalities. The margin of error (±, 90% confidence) is published where available.') });
    if (v.family === 'jobs' || src.includes('qcew')) out.push({ kind: 'workplace', text: T('Counted where the job is, not where people live: commuters make some places look rich in jobs.') });
    if (v.derived) out.push({ kind: 'derived', text: T('Computed in the browser from other series ({formula}); it is not a published figure, and margins of error are not carried through.', { formula: v.derived.formula }) });
    if (v.withheld) out.push({ kind: 'withheld', text: T('Some small-municipality figures are withheld to protect employers’ confidentiality, so the place has no value.') });
    if (v.caution) out.push({ kind: 'dataset', text: T(v.caution) });   // a dataset's own caution, from its file (the drive time to a hospital: which barrios show 0)
    out.push({ kind: 'area', text: T('A pattern across places does not describe the people who live there.') });
    return out;
  }

  const moeKey = () => Th('<b>±</b> is the margin of error at 90% confidence. <i>Italic</i> values have a margin of error above 30% of the estimate: treat them with caution.');   // the note of the Housing tables
  const flagKey = () => T('Italic values are less reliable: a margin of error above 30% of the estimate, or fewer than 10 counted.');   // the note of the pop-up and the tables of the Economy tab
  const lessReliable = () => T('less reliable');

  return { MOE_SHARE, SMALL_COUNT, isUnreliable, assess, notes, cautions, moeKey, flagKey, lessReliable };
});
