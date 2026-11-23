/* PR Data Observatory core: the composite index a person builds in the workbench (plan B6, docs/workbench.md). No page state: arrays in, numbers out.

     Composite.compute(cols, spec, places)   cols[k] is the array (island last) of input k; spec = { t, items: [{ key, dir, w }] }
                                             -> { score, parts, cover }: score is one value per place (the island is null), parts[i][k] what input k adds to place i's score, cover[i] the share of the weight present
     Composite.encode(spec) / decode(text, has)   the spec in a link (#ix=), e.g. "z,poverty_pct:l:2,qcew_avg_pay:h:1"; decode keeps only datasets has(key) knows

   Each input is put on one scale across the municipios first (t: 'z' z-score, 'mm' 0 to 100 between the lowest and highest, 'pct' percentile rank 0 to 100), turned round when a lower value
   is better (dir -1), and the score is the weighted mean of the inputs a place has. A place with less than 80% of the weight present is left blank. The island is never scored. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('composite', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const stats = dep('stats');
  const TRANSFORMS = ['z', 'mm', 'pct'], MIN_COVER = 0.8, MAX_ITEMS = 12;

  /** One input on its common scale, higher always better; null where the place has no value (or the input does not vary). */
  function scale(a, t, dir, places) {
    let s;
    if (t === 'z') s = stats.zscores(a, places);
    else if (t === 'pct') {   // percentile rank 0 to 100, tied values sharing the mean of their ranks (so turning an input round gives the same result as negating it)
      const at = [], v = []; for (let i = 0; i < places; i++) if (stats.finite(a[i])) { at.push(i); v.push(a[i]); }
      const r = stats.ranks(v), flat = v.every(x => x === v[0]); s = new Array(a.length).fill(null); at.forEach((i, k) => { s[i] = v.length > 1 && !flat ? (r[k] - 1) / (v.length - 1) * 100 : null; });   // an input that does not vary counts as missing, as on the other two scales
    }
    else {
      const v = a.slice(0, places).filter(stats.finite), lo = Math.min(...v), hi = Math.max(...v);
      s = a.map((x, i) => i >= places || !stats.finite(x) || !(hi > lo) ? null : (x - lo) / (hi - lo) * 100);
    }
    s = s.map((x, i) => i >= places || x == null || !isFinite(x) ? null : x);
    return dir < 0 ? s.map(x => x == null ? null : t === 'z' ? -x : 100 - x) : s;
  }

  function compute(cols, spec, places) {
    const items = spec.items, total = items.reduce((s, it) => s + it.w, 0), S = items.map((it, k) => scale(cols[k], spec.t, it.dir, places));
    const score = new Array(places + 1).fill(null), parts = [], cover = new Array(places + 1).fill(null);
    for (let i = 0; i < places; i++) {
      let w = 0, sum = 0;
      items.forEach((it, k) => { if (S[k][i] != null) { w += it.w; sum += it.w * S[k][i]; } });
      cover[i] = total ? w / total : 0;
      const ok = total && w && w / total >= MIN_COVER - 1e-9;
      parts[i] = items.map((it, k) => !ok || S[k][i] == null ? null : it.w * S[k][i] / w);   // a place left blank has no contributions either
      if (ok) score[i] = sum / w;
    }
    parts[places] = items.map(() => null);
    return { score, parts, cover, scaled: S };
  }

  const KEY = /^[A-Za-z0-9_]+$/;
  function encode(spec) { return [spec.t, ...spec.items.map(it => `${it.key}:${it.dir < 0 ? 'l' : 'h'}:${+it.w}`)].join(','); }
  function decode(text, has = () => true) {
    const f = String(text || '').split(','), t = f[0];
    if (!TRANSFORMS.includes(t)) return null;
    const items = [];
    for (const x of f.slice(1)) {
      const [key, d, w] = x.split(':'), wt = +w;
      if (!KEY.test(key || '') || !has(key) || !(d === 'h' || d === 'l') || !(wt > 0 && wt <= 100) || items.some(it => it.key === key)) continue;
      items.push({ key, dir: d === 'l' ? -1 : 1, w: wt });
      if (items.length >= MAX_ITEMS) break;
    }
    return items.length ? { t, items } : null;
  }

  return { TRANSFORMS, MIN_COVER, MAX_ITEMS, scale, compute, encode, decode };
});
