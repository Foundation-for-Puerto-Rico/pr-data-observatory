// Tests for the shared engine in site/js/core/ (plan item 6). Run: node --test tests/core.test.js   (python -m unittest discover runs it too when node is installed)
//  - unit tests of the pure parts: palettes, classification, time, normalization, statistics, formats
//  - the engine on the real published series, against tests/golden/economy.json (made from the Economy tab as it was before the engine was shared: tests/browser/make_golden.js)
const test = require('node:test');
const assert = require('node:assert');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { flat } = require('./golden_flat.js');

globalThis.fmt = (n, d = 0) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });   // the page's fmt, in English
const core = (n) => require(path.join(__dirname, '..', 'site', 'js', 'core', n + '.js'));
const readData = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
const sha = (v) => crypto.createHash('sha1').update(JSON.stringify(v)).digest('hex');
const reliability = core('reliability'), palettes = core('palettes'), classify = core('classify'), time = core('time'), stats = core('stats'), normalize = core('normalize'), format = core('format'), engine = core('engine'), adapters = core('adapters'), legend = core('legend'), stackLegend = core('stack'), panel = core('panel'), popup = core('popup'), datasets = core('datasets'), composite = core('composite'), minimap = core('minimap');

// ── palettes ────────────────────────────────────────────────────────────────
test('palettes: five classes in every ramp, and an unknown name falls back to blue', () => {
  for (const r of palettes.RAMP_ORDER) assert.strictEqual(palettes.RAMPS[r].length, 5, r);
  assert.strictEqual(palettes.DIVERGING.length, 5);
  assert.strictEqual(palettes.BIVARIATE.length, 3);
  assert.ok(palettes.BIVARIATE.every(r => r.length === 3));
  assert.strictEqual(palettes.ramp('nope'), palettes.RAMPS.blue);
  const all = [...Object.values(palettes.RAMPS).flat(), ...palettes.DIVERGING, ...palettes.BIVARIATE.flat(), ...palettes.SYMBOLS, ...palettes.LINES, palettes.NOVAL];
  assert.ok(all.every(c => /^#[0-9a-fA-F]{6}$/.test(c)), 'every color is a six-digit hex color');
});

// ── classification ──────────────────────────────────────────────────────────
test('classify: quantile, equal and manual breaks', () => {
  const pool = Array.from({ length: 10 }, (_, i) => i + 1);
  assert.deepStrictEqual(classify.make(pool, { method: 'quantile' }).edges, [1, 3, 5, 7, 9, 10]);
  assert.deepStrictEqual(classify.make(pool, { method: 'equal' }).edges, [1, 2.8, 4.6, 6.4, 8.2, 10]);
  assert.deepStrictEqual(classify.make(pool, { method: 'manual', edges: [2, 4, 6, 8] }).edges, [1, 2, 4, 6, 8, 10]);
  assert.deepStrictEqual(classify.make(pool, { method: 'manual', edges: [2, 4] }).edges, [1, 3, 5, 7, 9, 10], 'a manual list of the wrong length falls back to quantiles');
  assert.deepStrictEqual(classify.make([], {}), { edges: [0, 1], span: 1, min: 0, max: 1 });
  assert.deepStrictEqual(classify.inner(pool, 5), [3, 5, 7, 9]);
});
test('classify: a value on a break belongs to the lower class, no value is -1', () => {
  const b = classify.make([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], { method: 'quantile' });   // edges 1 3 5 7 9 10
  assert.deepStrictEqual([1, 3, 3.1, 5, 9, 9.5, 10].map(v => classify.classOf(b, v)), [0, 0, 1, 1, 3, 4, 4]);
  assert.strictEqual(classify.classOf(b, null), -1);
  assert.strictEqual(classify.classOf(b, NaN), -1);
  assert.strictEqual(classify.classOf(b, Infinity), -1);
});
test('classify: diverging scales cut at 0.1 and 0.5 of the largest distance from the center', () => {
  const b = classify.make([-10, -2, 0, 1, 5], { div: true, center: 0 });
  assert.deepStrictEqual([b.div, b.center, b.span], [true, 0, 10]);
  assert.deepStrictEqual([-10, -5.1, -5, -1.1, -1, 0, 1, 1.1, 5, 5.1, 10].map(v => classify.classOf(b, v)), [0, 0, 1, 1, 2, 2, 2, 3, 3, 4, 4]);
  assert.strictEqual(classify.make([-10, 10], { div: true, center: 0, k: 3 }).div, undefined, 'three classes (a bivariate layer) are never diverging');
  assert.strictEqual(classify.make([5, 5], { div: true, center: 5 }).span, 1, 'a scale with no spread has a span of 1');
});
test('classify: natural breaks separate clusters, and a long pool is thinned', () => {
  const pool = [1, 2, 3, 10, 11, 12, 50, 51, 52];
  const b = classify.make(pool, { method: 'jenks', k: 3 });
  const classes = pool.map(v => classify.classOf(b, v, 3));
  assert.deepStrictEqual(classes, [0, 0, 0, 1, 1, 1, 2, 2, 2]);
  const long = Array.from({ length: 4000 }, (_, i) => i);
  assert.strictEqual(classify.make(long, { method: 'jenks' }).edges.length, 6);
});
test('classify: user breaks are k - 1 rising numbers', () => {
  assert.deepStrictEqual(classify.parseBreaks('10, 20; 30 40'), [10, 20, 30, 40]);
  assert.strictEqual(classify.parseBreaks('10, 20, 30'), null);
  assert.strictEqual(classify.parseBreaks('10, 5, 30, 40'), null);
  assert.strictEqual(classify.parseBreaks('a, b, c, d'), null);
  assert.strictEqual(classify.parseBreaks(''), null);
  const up = classify.risingStops([0, 0, 1, 1]), want = [1e-6, 2e-6, 1 + 1e-6, 1 + 2e-6];
  assert.ok(up.every((x, i) => Math.abs(x - want[i]) < 1e-12) && up.every((x, i) => i === 0 || x > up[i - 1]), 'strictly rising, each tied break moved up by a hair');
});

// ── time ────────────────────────────────────────────────────────────────────
test('time: the year a dataset shows', () => {
  const ds = { ys: [2012, 2015, 2020] };
  assert.deepStrictEqual(time.resolve(ds, null), { y: 2020, exact: true });
  assert.deepStrictEqual(time.resolve(ds, 2015), { y: 2015, exact: true });
  assert.deepStrictEqual(time.resolve(ds, 2018), { y: 2015, exact: false });
  assert.deepStrictEqual(time.resolve(ds, 2009), { y: 2012, exact: false, early: true });
  assert.deepStrictEqual(time.resolve({ ys: [2026], static: true }, 2012), { y: 2026, exact: true }, 'a snapshot is always the current one');
  assert.deepStrictEqual(time.resolve({ ys: [2026], time: { type: 'snapshot' } }, 2012), { y: 2026, exact: true });
  assert.deepStrictEqual(time.resolve(null, 2012), { y: null, exact: false });
  assert.deepStrictEqual(time.resolve({ ys: [] }, 2012), { y: null, exact: false });
  assert.deepStrictEqual(time.years([{ ys: [2008, 2012, 2020] }, { ys: [2026], static: true }, { ys: [2011, 2020] }]), [2011, 2012, 2020], 'snapshots and years before 2010 are not offered');
  assert.strictEqual(time.label({ time: { type: 'window', windowYears: 5 } }, 2024), '2020–2024');
  assert.strictEqual(time.label({}, 2024), '2024');
});

// ── statistics ──────────────────────────────────────────────────────────────
test('stats: median, correlation, rank and percentile', () => {
  assert.strictEqual(stats.median([3, null, 1, 2]), 2);
  assert.strictEqual(stats.median([4, 1, 3, 2]), 2.5);
  assert.strictEqual(stats.median([null]), null);
  const p = stats.pearson([1, 2, 3, 4], [2, 4, 6, 8]);
  assert.deepStrictEqual([p.n, p.r, p.slope, p.intercept], [4, 1, 2, 0]);
  assert.strictEqual(stats.pearson([1, 1, 1], [1, 2, 3]).r, null);
  const a = [10, 30, null, 20, 99];   // three places with a value, one without, and the island last
  assert.deepStrictEqual(stats.rank(a, 1, 4), { rank: 1, n: 3 });
  assert.strictEqual(stats.rank(a, 2, 4), null);
  assert.strictEqual(stats.rank(a, 4, 4), null, 'the island has no rank');
  // rank ranges from margins of error (review 2026-11-05): 50±2 overlaps 52±1 and 47±2, not 60±1 or 40±1
  const v = [60, 52, 50, 47, 40, 51], m = [1, 1, 2, 2, 1, 0];
  assert.deepStrictEqual(stats.rankRange(v, m, 2, 5), { lo: 2, hi: 3 }, 'third, could be second or third (1,000 draws; the old overlap rule said 2-4)');
  assert.deepStrictEqual(stats.rankRanges(v.slice(), m, 5), stats.rankRanges(v.slice(), m, 5), 'a fixed seed: the same data gives the same ranges');
  { const a = Array.from({ length: 79 }, (_, i) => 30 + (i * 37 % 41)), mm = a.map(() => 3), r = stats.rankRanges(a, mm, 78); assert.ok(r.slice(0, 78).every((g, i) => g.lo <= stats.rank(a, i, 78).rank + 1 && g.hi >= stats.rank(a, i, 78).rank - 1), 'each range sits around the shown rank'); }
  assert.deepStrictEqual(stats.rankRange(v, m, 0, 5), { lo: 1, hi: 1 }, 'clearly first');
  assert.strictEqual(stats.rankRange(v, null, 2, 5), null, 'no margins, no range');
  assert.strictEqual(stats.rankRange(v, m, 5, 5), null, 'the island has no rank');
  assert.deepStrictEqual(stats.percentiles(a, 4), [0, 100, null, 50, null]);
  assert.deepStrictEqual(stats.pool(a, 4), [10, 20, 30]);
});

test('stats: ranks with ties, Spearman, pairwise-complete correlation and the matrix (plan item 12)', () => {
  assert.deepStrictEqual(stats.ranks([10, 30, 20, 30]), [1, 3.5, 2, 3.5], 'ties share the mean of their ranks');
  // a monotone curve: Spearman is exactly 1, Pearson is below 1
  const x = [1, 2, 3, 4, 5, 6, 99], y = [1, 4, 9, 16, 25, 1000, 99];   // six places and the island last
  assert.strictEqual(stats.correlation(x, y, 6, 'spearman').r, 1);
  assert.ok(stats.correlation(x, y, 6, 'pearson').r < 0.9);
  assert.strictEqual(stats.correlation(x, y, 6).n, 6, 'the island is never a place');
  // only the places where both have a value count, and fewer than 3 gives no r
  const a = [1, 2, null, 4, 5, 0], b = [2, 4, 6, null, 10, 0];
  assert.deepStrictEqual(stats.correlation(a, b, 5), { r: 1, n: 3 });
  assert.deepStrictEqual(stats.correlation([1, 2, null, 0], [1, null, 3, 0], 3), { r: null, n: 1 });
  // Spearman with ties equals Pearson on the mean ranks (checked by hand: ranks x 1 2.5 2.5 4, y 1 2 3 4)
  const sx = [5, 7, 7, 9], sy = [1, 2, 3, 4], expect = stats.pearson([1, 2.5, 2.5, 4], [1, 2, 3, 4]).r;
  assert.ok(Math.abs(stats.correlation([...sx, 0], [...sy, 0], 4, 'spearman').r - expect) < 1e-12);
  const M = stats.matrix([x, y, x.map(v => -v)], 6, 'pearson');
  assert.strictEqual(M.r[0][0], 1); assert.strictEqual(M.n[1][1], 6); assert.strictEqual(M.r[0][1], M.r[1][0]);
  assert.ok(Math.abs(M.r[0][2] + 1) < 1e-12, 'a variable and its negative: -1');
});

test('stats: z-scores and the nearest peers', () => {
  const z = stats.zscores([1, 2, 3, null, 50], 4);
  assert.deepStrictEqual(z.map(v => v == null ? null : +v.toFixed(4)), [-1.2247, 0, 1.2247, null, null], 'standard deviation of the places, island left out');
  assert.deepStrictEqual(stats.zscores([2, 2, 2, 9], 3), [null, null, null, null], 'no spread: no z-score');
  // five places on two features; place 0 is nearest to 1, then 2; place 4 has a missing feature and is never a peer
  const f1 = [0, 1, 3, 10, 0, 0], f2 = [0, 0, 0, 10, null, 0];
  assert.deepStrictEqual(stats.peers(0, [f1, f2], 5, 2).map(p => p.i), [1, 2]);
  assert.deepStrictEqual(stats.peers(4, [f1, f2], 5, 2), [], 'a place with a missing feature has no peers');
  assert.ok(!stats.peers(0, [f1, f2], 5, 9).some(p => p.i === 4 || p.i === 0));
});

test('composite: scales, direction, weights, the 80% rule and the link (plan B6)', () => {
  const places = 4, A = [0, 5, 10, null, 99], B = [10, 20, 30, 40, 99], C = [1, 1, 1, 1, 9];
  assert.deepStrictEqual(composite.scale(A, 'mm', 1, places), [0, 50, 100, null, null]);
  assert.deepStrictEqual(composite.scale(A, 'mm', -1, places), [100, 50, 0, null, null], 'lower is better turns the scale round');
  assert.deepStrictEqual(composite.scale(B, 'pct', 1, places), [0, 1 / 3 * 100, 2 / 3 * 100, 100, null]);
  for (const t of ['z', 'mm', 'pct']) assert.deepStrictEqual(composite.scale(C, t, 1, places), [null, null, null, null, null], `${t}: an input that does not vary counts as missing`);
  const flatR = composite.compute([[1, 2, 3, 4, 9], C], { t: 'pct', items: [{ key: 'a', dir: 1, w: 3 }, { key: 'k', dir: 1, w: 1 }] }, places);
  assert.deepStrictEqual([flatR.cover[0], flatR.score[0]], [0.75, null], 'the same on every scale: a constant input with 25% of the weight leaves the places blank');
  const zA = composite.scale(A, 'z', -1, places); assert.ok(Math.abs(zA[0] - 1.2247) < 1e-4 && zA[3] === null);
  // weights 3 and 1 on the 0-100 scale: place 0 = (3*0 + 1*0)/4 = 0; place 1 = (3*50 + 1*33.3)/4; place 3 has only B (25% of the weight): blank
  const r = composite.compute([A, B], { t: 'mm', items: [{ key: 'a', dir: 1, w: 3 }, { key: 'b', dir: 1, w: 1 }] }, places);
  assert.strictEqual(r.score[0], 0);
  assert.ok(Math.abs(r.score[1] - (3 * 50 + 100 / 3) / 4) < 1e-9);
  assert.strictEqual(r.score[3], null); assert.strictEqual(r.cover[3], 0.25);
  assert.deepStrictEqual(r.parts[3], [null, null], 'a place left blank has no contributions either');
  // percentile ranks: tied values share the mean of their ranks, so 'lower is better' on x equals 'higher is better' on -x
  const T6 = [0, 0, 0, 1, 2, 3, 9];
  assert.deepStrictEqual(composite.scale(T6, 'pct', -1, 6), composite.scale(T6.map(v => -v), 'pct', 1, 6));
  assert.deepStrictEqual(composite.scale(T6, 'pct', 1, 6), [20, 20, 20, 60, 80, 100, null]);
  assert.strictEqual(r.score[places], null, 'the island is never scored');
  for (let i = 0; i < 3; i++) assert.ok(Math.abs(r.parts[i].reduce((s, x) => s + x, 0) - r.score[i]) < 1e-9, 'the contributions add up to the score');
  // exactly 80% of the weight present is enough
  const r80 = composite.compute([B, A], { t: 'mm', items: [{ key: 'b', dir: 1, w: 4 }, { key: 'a', dir: 1, w: 1 }] }, places);
  assert.strictEqual(r80.cover[3], 0.8); assert.strictEqual(r80.score[3], 100);
  // the link
  const spec = { t: 'pct', items: [{ key: 'poverty_pct', dir: -1, w: 2 }, { key: 'qcew_avg_pay', dir: 1, w: 1.5 }] };
  assert.strictEqual(composite.encode(spec), 'pct,poverty_pct:l:2,qcew_avg_pay:h:1.5');
  assert.deepStrictEqual(composite.decode(composite.encode(spec)), spec);
  assert.deepStrictEqual(composite.decode('z,a:h:1,a:l:2,b:x:1,c:h:0,d:h:101,e<f:h:1,g:l:3', k => k !== 'g'), { t: 'z', items: [{ key: 'a', dir: 1, w: 1 }] }, 'repeats, bad directions, weights outside 0-100, odd keys and unknown datasets are dropped');
  assert.strictEqual(composite.decode('rank,a:h:1'), null);
  assert.strictEqual(composite.decode(''), null);
});

test('datasets: an optional file that fails is left out and named; a required one stops the load', async () => {
  const docs = Object.fromEntries(datasets.FILES.map(f => [f.file, readData(f.file)])), muni = readData('municipalities.json');
  const get = (miss) => (p) => { const f = p.replace('data/', ''); return f === miss ? Promise.reject(new Error('404')) : Promise.resolve(docs[f]); };
  const X = engine.create(), r = await datasets.load(X, get('environment_series.json'), muni, 2026);
  assert.deepStrictEqual(r.failed, ['data/environment_series.json']);
  assert.ok(!X.V.nri_eal_total && X.V.quakes_m25, 'its datasets are missing, the others are there');
  await assert.rejects(datasets.load(engine.create(), get('economy_series.json'), muni, 2026));
});

test('minimap: every municipio gets an outline inside the frame, in the order asked', () => {
  const fc = readData('municipios.geojson'), names = fc.features.map(f => f.properties.municipality).sort(), P = minimap.project(fc, names, 600);
  assert.strictEqual(P.d.length, 78); assert.ok(P.d.every(d => /^M[\d.]+ [\d.]+/.test(d)), 'every place has a path');
  const nums = P.d.join(' ').match(/-?[\d.]+/g).map(Number);
  assert.ok(Math.min(...nums) >= 0 && Math.max(...nums) <= 600.1, 'inside the frame');
  assert.ok(P.h > 100 && P.h < 300, 'the island is wide and low');
  const svg = minimap.svg(P, names.map(() => '#123456'), { label: 'x', strong: new Set([3]), titles: names });
  assert.strictEqual((svg.match(/<path /g) || []).length, 78, 'a place with a dark outline is drawn once, on top');
});

// ── formats ─────────────────────────────────────────────────────────────────
test('format: compact numbers and values', () => {
  assert.strictEqual(format.compact(1234, ''), '1.2K');
  assert.strictEqual(format.compact(15200, ''), '15K');
  assert.strictEqual(format.compact(2.5e6, '$'), '$2.5M');
  assert.strictEqual(format.compact(-3.2e9, ''), '−3.2B');
  assert.strictEqual(format.compact(5.5, '%'), '5.50%');
  assert.strictEqual(format.compact(42, ' pts'), '42.0 pts');
  assert.strictEqual(format.value({ unit: '$' }, { unit: '$', d: 0 }, -1234.5), '−$1,235');
  assert.strictEqual(format.value({}, { unit: '%', d: 1 }, 12.345), '12.3%');
  assert.strictEqual(format.value({ plain: true }, { unit: '', d: 0 }, 1987.4), '1987');
  assert.strictEqual(format.value({}, { unit: '', d: 0 }, null), '—');
  assert.strictEqual(format.value({}, { unit: '', d: 0 }, NaN), '—');
});

// ── normalization ───────────────────────────────────────────────────────────
test('normalize: the options a kind of dataset offers', () => {
  const ids = (v) => normalize.options(v).map(o => o[0]);
  assert.deepStrictEqual(ids({ type: 'count' }), ['value', 'per1000', 'perHU', 'perkm2', 'sharePR', 'change', 'pctile']);
  assert.deepStrictEqual(ids({ type: 'count', key: 'housing_units' }), ['value', 'per1000', 'perkm2', 'sharePR', 'change', 'pctile'], 'housing units per housing unit says nothing');
  assert.deepStrictEqual(ids({ type: 'count', family: 'jobs' }), ['value', 'per1000', 'perkm2', 'sharePR', 'shareJobs', 'lq', 'change', 'pctile']);
  assert.deepStrictEqual(ids({ type: 'total$' }), ['value', 'perCapita', 'perkm2', 'sharePR', 'change', 'pctile']);
  assert.deepStrictEqual(ids({ type: 'total$', noShare: true }), ['value', 'perCapita', 'perkm2', 'change', 'pctile'], 'a total that is near zero or negative has no share of the island');
  assert.deepStrictEqual(ids({ type: 'rate' }), ['value', 'index', 'diff', 'change', 'pctile']);
  assert.deepStrictEqual(ids({ type: 'rate', static: true }), ['value', 'index', 'diff', 'pctile'], 'a snapshot has no change since a base year');
  assert.deepStrictEqual(ids({ type: 'count', denom: { total: [] } }), ['value', 'shareArea', 'per1000', 'perkm2', 'sharePR', 'change', 'pctile']);
  assert.deepStrictEqual(ids({ type: 'count', residents: true }), ['value', 'perHU', 'perkm2', 'sharePR', 'change', 'pctile'], 'the residents themselves are not divided by the residents');
  assert.strictEqual(normalize.defaultNorm({ type: 'count', residents: true }, 'fill'), 'perkm2', 'shaded, they start as people per km²');
  assert.strictEqual(normalize.defaultNorm({ type: 'count', residents: true }, 'symbol'), 'value');
  assert.strictEqual(normalize.defaultNorm({ type: 'count' }, 'fill'), 'per1000');
  assert.strictEqual(normalize.defaultNorm({ type: 'count' }, 'symbol'), 'value');
  assert.strictEqual(normalize.defaultNorm({ type: 'total$' }, 'fill'), 'perCapita');
  assert.strictEqual(normalize.defaultNorm({ type: 'rate' }, 'fill'), 'value');
  assert.strictEqual(normalize.defaultNorm({ type: 'count', denom: { total: [] } }, 'fill'), 'shareArea');
  assert.deepStrictEqual(normalize.describe({ unit: '%', d: 1, type: 'rate' }, 'change'), { unit: ' pts', d: 1, div: true, center: 0 });
  assert.deepStrictEqual(normalize.describe({ unit: '$', d: 0, type: 'level$' }, 'change'), { unit: '%', d: 1, div: true, center: 0 });
  assert.strictEqual(normalize.describe({ unit: '', d: 0 }, 'index').center, 100);
});
test('normalize: each normalization on a small invented island', () => {
  // three municipalities and the island; population 100, 200, 700; jobs 10, 20, 70
  const years = { 2020: [10, 40, 100, 150], 2022: [20, 60, 120, 200] };
  const V = { x: { key: 'x', type: 'count', unit: '', d: 0, ys: [2020, 2022], years }, population: { key: 'population', ys: [2020], years: { 2020: [100, 200, 700, 1000] } }, qcew_jobs: { key: 'qcew_jobs', ys: [2020], years: { 2020: [10, 20, 70, 100] } } };
  const ctx = { pr: 3, area: [1, 2, 10, 13], base: 2020, arr: (k, y) => V[k].years[y] || null, pop: () => V.population.years[2020], jobs: () => V.qcew_jobs.years[2020], hu: () => [50, 100, 300, 450], cpi: () => 1 };
  const run = (norm, y = 2022) => normalize.compute(V.x, { key: 'x', norm, real: false }, y, ctx);
  assert.deepStrictEqual(run('value'), [20, 60, 120, 200]);
  assert.deepStrictEqual(run('per1000'), [200, 300, 171.429, 200]);
  assert.deepStrictEqual(run('perkm2'), [20, 30, 12, 200 / 13]);
  assert.deepStrictEqual(run('perHU'), [400, 600, 400, 444.444], 'per 1,000 housing units');
  assert.strictEqual(normalize.compute(V.x, { key: 'x', norm: 'perHU' }, 2022, { ...ctx, hu: () => null }), null, 'no housing units, no rate');
  assert.deepStrictEqual(run('sharePR'), [10, 30, 60, 100]);
  assert.deepStrictEqual(run('shareJobs'), [200, 300, 171.42857142857142, 200]);
  assert.deepStrictEqual(run('index'), [10, 30, 60, 100]);
  assert.deepStrictEqual(run('diff'), [-180, -140, -80, 0]);
  assert.deepStrictEqual(run('change'), [100, 50, 20, 33.33333333333333], 'a count changes in per cent');
  assert.strictEqual(run('change', 2020), null, 'no change in or before the base year');
  assert.deepStrictEqual(run('pctile'), [0, 50, 100, null]);
  const lq = run('lq'); assert.ok(Math.abs(lq[0] - (20 / 10) / (200 / 100)) < 1e-12);
  assert.strictEqual(normalize.compute(V.x, { key: 'x', norm: 'value' }, 2018, ctx), null, 'no data for a year the dataset does not have');
});

// ── the engine on the real published series ─────────────────────────────────
const golden = JSON.parse(fs.readFileSync(path.join(__dirname, 'golden', 'economy.json'), 'utf8'));
function realEngine() {
  const E = engine.create(), muni = readData('municipalities.json'), meta = readData('meta.json');
  adapters.series(E, readData('economy_series.json'), readData('housing_series.json'), muni);
  adapters.tourism(E, muni, +((meta.generated_at || '').slice(0, 4)) || 2026);
  E.base = golden.base;
  return E;
}
const E = realEngine();

test('engine: the residents other datasets are divided by are never shown per 1,000 residents (review finding, 2026-11-05)', () => {
  const X = realEngine(), pop = X.V[X.denominators.pop];
  assert.ok(pop && pop.residents, 'the population denominator is marked as the residents');
  assert.ok(!X.normOptions('population').some(o => o[0] === 'per1000'), 'population ÷ population × 1,000 is 1,000 everywhere: not offered');
  const L = X.makeLayer('population', 'fill');
  assert.strictEqual(L.norm, 'perkm2', 'shaded, the population starts as people per km²');
  assert.strictEqual(X.makeLayer('population', 'symbol').norm, 'value', 'as symbols it keeps the count');
  const a = X.calc(L, X.resolve('population').y).slice(0, X.geo.pr).filter(x => x != null);
  assert.ok(new Set(a.map(x => Math.round(x))).size > 50, 'the shaded values differ from place to place');
  const [old] = X.restore('population.f.per1000.blue.q.1.1.0.85.0');
  assert.strictEqual(old.norm, 'perkm2', 'an old link asking for per 1,000 residents gets people per km², not a shaded raw count');
  assert.ok(X.normOptions('qcew_jobs').some(o => o[0] === 'per1000'), 'other counts keep per 1,000 residents');
});
test('legend: a view in which every area has the same value says so (review finding, 2026-11-05)', () => {
  const X = realEngine(), flatL = { ...X.makeLayer('population', 'fill'), id: 'a', norm: 'per1000' }, goodL = { ...X.makeLayer('population', 'fill'), id: 'b' }, rateL = { ...X.makeLayer('poverty_pct', 'fill'), id: 'c' };
  const warn = (layers) => stackLegend.blocks(X, layers, X.evaluate(layers)).join('').match(/el-flat[^>]*>([^<]*)/g) || [];
  assert.strictEqual(warn([flatL]).length, 1, 'population per 1,000 residents: 1,000 in every municipio, warned');
  assert.strictEqual(warn([goodL]).length, 0, 'people per km² differ: no warning');
  assert.strictEqual(warn([rateL]).length, 0, 'a rate that differs: no warning');
  const biv = warn([flatL, rateL]);
  assert.strictEqual(biv.length, 1, 'two datasets together: only the flat one is warned');
  assert.ok(biv[0].includes(X.V.population.label), 'and named');
});
test('pop-up: a rank beside a margin of error gives the ranks the place could hold (review finding, 2026-11-05)', () => {
  const X = realEngine(), L = { ...X.makeLayer('poverty_pct', 'fill'), id: 'p' }, ev = X.evaluate([L]).p, i = X.geo.names.indexOf('Orocovis');
  const r = core('popup').value(X, L, ev, i).rank, m = /^#(\d+) of (\d+), could be (\d+)–(\d+)$/.exec(r);
  assert.ok(m, `Orocovis: ${r}`);
  const [, rk, n, lo, hi] = m.map(Number);
  assert.ok(lo <= rk && rk <= hi && lo < hi && hi <= n, `the shown rank sits inside the range: ${r}`);
  const jobs = { ...X.makeLayer('qcew_jobs', 'fill'), id: 'q' }, rj = core('popup').value(X, jobs, X.evaluate([jobs]).q, i).rank;
  assert.ok(/^#\d+ of \d+$/.test(rj), `a series without margins keeps a plain rank: ${rj}`);
});
test('legend: sized symbols over a shaded layer are drawn as hollow rings, alone they are filled (review finding, 2026-11-05)', () => {
  const X = realEngine(), fill = { ...X.makeLayer('poverty_pct', 'fill'), id: 'f' }, sym = { ...X.makeLayer('qcew_jobs', 'symbol'), id: 's' };
  const html = (layers) => stackLegend.blocks(X, layers, X.evaluate(layers)).join('');
  assert.ok(/background:none;border:2px solid/.test(html([fill, sym])), 'over shading: rings');
  assert.ok(!/background:none;border:2px solid/.test(html([sym])) && /background:#/.test(html([sym])), 'alone: filled');
});
test('legend: a histogram with the class breaks, and "Match periods" to the latest year every layer has (map review 2026-11-05)', () => {
  const X = realEngine(), lay = (key, mode, id) => ({ ...X.makeLayer(key, mode), id }), html = (ls) => stackLegend.blocks(X, ls, X.evaluate(ls)).join('');
  const pov = lay('poverty_pct', 'fill', 'p'), unemp = lay('laus_unemp_rate', 'fill', 'u');
  const h = html([pov]), bars = (h.match(/<div class="el-hist"[^>]*>(.*?)<\/div>/) || [])[1] || '';
  assert.strictEqual((bars.match(/<i /g) || []).length, 24, 'twenty-four bars'); assert.ok((bars.match(/<b /g) || []).length >= 2, 'the inner class breaks are marked');
  const common = X.V.poverty_pct.ys.filter(y => X.V.laus_unemp_rate.ys.includes(y)), cy = Math.max(...common);
  const m = /data-ecyear="(\d{4})"/.exec(html([pov, unemp]));
  assert.ok(m && +m[1] === cy, `the button offers ${cy}, the latest year both have`);
  X.year = cy; assert.ok(!/data-ecyear/.test(html([pov, unemp])), 'no button once both show that year'); X.year = null;
});
test('legend: layers from different periods say so (review finding, 2026-11-05)', () => {
  const X = realEngine(), lay = (key, mode, id) => ({ ...X.makeLayer(key, mode), id });
  const note = (layers) => (stackLegend.blocks(X, layers, X.evaluate(layers)).join('').match(/el-period[^>]*>([^<]*)/) || [])[1] || '';
  const pov = lay('poverty_pct', 'fill', 'p'), unemp = lay('laus_unemp_rate', 'fill', 'u'), jobs = lay('laus_unemployed', 'symbol', 'j');
  const ev = X.evaluate([pov, unemp]), pp = X.V.poverty_pct, pu = X.V.laus_unemp_rate;
  const lp = core('time').label(pp, ev.p.y), lu = core('time').label(pu, ev.u.y);
  assert.notStrictEqual(lp, lu, `the review's pair covers two periods: ${lp} and ${lu}`);
  const n = note([pov, unemp]);
  assert.ok(n.includes(lp) && n.includes(lu), `a survey window beside a yearly series is named: ${n}`);
  assert.strictEqual(note([pov]), '', 'one layer: no note');
  assert.strictEqual(note([unemp, jobs]), '', 'two series of the same year: no note');
  const twin = X.list().find(v => v.key !== 'poverty_pct' && v.time && v.time.type === 'window' && v.ys.includes(ev.p.y) && v.ys[v.ys.length - 1] === ev.p.y && !v.static);
  if (twin) assert.strictEqual(note([pov, lay(twin.key, 'symbol', 't')]), '', `two survey windows of the same years (${twin.key}): no note`);
});

const ADDED_SINCE_GOLDEN = new Set(['crime_type1', 'crime_violent', 'crime_property', 'crime_murders',
  'fema_pa_cat_a', 'fema_pa_cat_b', 'fema_pa_cat_c', 'fema_pa_cat_d', 'fema_pa_cat_e', 'fema_pa_cat_f', 'fema_pa_cat_g', 'fema_pa_cat_z', 'fema_pa_406_mitigation',
  'hma_approved_federal', 'hma_obligated', 'hma_pending_federal', 'hma_projects',
  'fed_prog_ss_retirement', 'fed_prog_ss_disability', 'fed_prog_ss_survivors', 'fed_prog_va_compensation', 'fed_prog_pell', 'fed_prog_head_start', 'fed_prog_pbra',
  'fac_expended', 'fac_direct', 'fac_passthrough', 'fac_hhs', 'fac_hud', 'fac_dhs', 'fac_treasury', 'fac_other',
  'nmtc_qlici', 'nmtc_projects']);   // series added to economy_series.json after the fingerprints were taken
test('engine: the same datasets, in the same order, as the Economy tab had', () => {
  assert.deepStrictEqual(E.list().map(v => v.key).filter(k => !ADDED_SINCE_GOLDEN.has(k)), golden.datasets);
  assert.deepStrictEqual(E.geo.names, golden.places);
  assert.deepStrictEqual(E.years(), golden.years);
});
test('engine: every dataset offers, defaults and writes what the Economy tab did', () => {
  for (const [k, g0] of Object.entries(golden.perKey)) {
    // one deliberate change since the fingerprints: the population denominator no longer offers or starts as per 1,000 residents (1,000 everywhere), but as people per km²
    const g = k === E.denominators.pop ? { ...g0, norm: g0.norm.filter(o => o[0] !== 'per1000'), defaultFill: 'perkm2' } : g0;
    assert.deepStrictEqual(E.normOptions(k).filter(o => o[0] !== 'perHU'), g.norm, k);   // the options the tab had; the one new option is per 1,000 housing units
    assert.strictEqual(E.normOptions(k).some(o => o[0] === 'perHU'), E.V[k].type === 'count' && E.V[k].family !== 'jobs' && k !== 'housing_units', `${k}: per housing unit`);
    assert.strictEqual(norm_default(k, 'fill'), g.defaultFill, k);
    assert.strictEqual(norm_default(k, 'symbol'), g.defaultSymbol, k);
    assert.strictEqual(E.dictId(k), g.dictId, k);
    for (const [n] of g.norm) {
      const o = E.out({ key: k, norm: n });
      assert.deepStrictEqual({ suffix: o.suffix || '', unit: o.unit }, g.units[n], `${k} ${n} units`);
      const f = [0, 1.2345, 1234567.891, -5.5, 0.04].map(x => E.fmt({ key: k, norm: n, real: false }, x)).concat([E.fmt({ key: k, norm: n, real: false }, null)]);
      assert.deepStrictEqual(f, g.fmt[n], `${k} ${n} formats`);
    }
  }
});
function norm_default(k, mode) { return normalize.defaultNorm(E.V[k], mode); }
test('engine: every value of every dataset under every normalization, year and price basis is what the Economy tab computed', () => {
  let n = 0;
  for (const [k, g] of Object.entries(golden.perKey)) {
    for (const [c, want] of Object.entries(g.values)) {
      const [norm, year, real] = c.split('|');
      const r = E.values(k, { year: year === 'null' ? null : +year, norm, real: real === 'real', base: 2014 });
      if (want === null) { assert.strictEqual(r, null, `${k} ${c}`); continue; }
      assert.ok(r, `${k} ${c}: a value was expected`);
      assert.deepStrictEqual([r.year, r.exact], [want.year, want.exact], `${k} ${c}`);
      assert.strictEqual(sha(r.values), want.sha1, `${k} ${c}`);
      n++;
    }
  }
  assert.strictEqual(n, Object.values(golden.perKey).reduce((t, g) => t + Object.values(g.values).filter(Boolean).length, 0), 'every combination that has values was checked');
  assert.ok(n > 2000, `checked ${n} combinations`);
});

// the stacks of layers, as api.show builds them
const stripRel = (h) => h.replace(/<div class="el-hist"[^>]*>.*?<\/div>/g, '').replace(/box-sizing:border-box;opacity:1;background:none;border:2px solid (#[0-9A-Fa-f]+);box-shadow:0 0 0 1\.5px #fff/g, 'background:$1').replace(/<div class="row rel">.*?<\/div>/g, '').replace(/<div class="el-note">.*?<\/div>/g, '').replace(/<div class="el-note el-period"[^>]*>.*?<\/div>/g, '');   // the lines reliability.js adds under a layer, and the note on layers of different periods (added 2026-11-10)
const noWindow = (h) => h.replace(/\b(\d{4})–(\d{4})\b/g, (m, a, b) => +b - +a === 4 ? b : m);   // a survey year is now written as its window
const noManual = (h) => noWindow(h).replace(/ My own limits/g, '').replace(/ Per 1,000 housing units/g, '').replace(/ close Shaded Symbol /g, ' close ');   // the two options the menus gained and the card's Shaded / Symbol switches (the golden is the text of the card)
function stack(cfg) {
  E.year = cfg.year; E.base = cfg.base; E.cache = {};
  const layers = []; let seq = 0;
  for (const l of cfg.layers) {
    const v = E.V[l.key]; let mode = l.mode || 'fill';
    if (mode === 'fill' && layers.filter(x => x.mode === 'fill').length >= 2) mode = 'symbol';
    const opts = { ramp: l.ramp, real: !!l.real, classes: l.classes, fixed: l.fixed };
    if (l.norm && E.normOptions(l.key).some(o => o[0] === l.norm)) opts.norm = l.norm;
    const L = E.makeLayer(l.key, mode, opts, layers); L.id = ++seq; layers.push(L);
  }
  return { layers, evals: E.evaluate(layers) };
}
const configs = JSON.parse(fs.readFileSync(path.join(__dirname, 'browser', 'economy_configs.json'), 'utf8'));
test('engine: the legend, the layer cards, the colors and the symbols of 26 layer stacks are what the Economy tab drew', () => {
  for (const cfg of configs) {
    const g = golden.configs[cfg.id], { layers, evals } = stack(cfg);
    assert.deepStrictEqual(layers.map(l => ({ key: l.key, mode: l.mode })), g.applied.map(a => ({ key: a.key, mode: a.mode })), `${cfg.id}: layers`);
    assert.strictEqual(E.encode(layers), g.encode, `${cfg.id}: link`);
    assert.strictEqual(noWindow(flat(stripRel(stackLegend.blocks(E, layers, evals, false).join('')))), g.legend, `${cfg.id}: legend`);
    assert.strictEqual(noManual(flat(layers.map((L, k) => panel.layerCard(E, L, k, layers.length, evals[L.id])).join(''))), g.cards, `${cfg.id}: layer cards`);
    const fills = layers.filter(l => l.mode === 'fill' && l.visible && evals[l.id] && evals[l.id].a);
    if (g.fills) { assert.ok(fills.length, `${cfg.id}: a shaded layer`); assert.deepStrictEqual(E.fillColors(fills, evals), g.fills, `${cfg.id}: colors`); assert.strictEqual(fills[0].opacity, g.opacity); }
    else assert.strictEqual(fills.length, 0, `${cfg.id}: no shaded layer`);
    const syms = layers.filter(l => l.mode === 'symbol' && l.visible && evals[l.id] && evals[l.id].a).flatMap(L => E.symbols(L, evals[L.id], false).rows.map(r => [+r.r.toFixed(3), r.fill, L.opacity]));
    assert.deepStrictEqual(syms, g.symbols.map(s => [s[0], s[1], s[2]]), `${cfg.id}: symbols`);
  }
});
test('engine: a layer stack survives the trip through a link', () => {
  for (const cfg of configs) {
    const { layers } = stack(cfg), back = E.restore(E.encode(layers));
    assert.strictEqual(E.encode(back), E.encode(layers), cfg.id);
    assert.deepStrictEqual(back.map(l => [l.key, l.mode, l.norm, l.ramp, l.classes, l.visible, l.fixed, l.real, l.opacity, l.color]), layers.map(l => [l.key, l.mode, l.norm, l.ramp, l.classes, l.visible, l.fixed, l.real, l.opacity, l.color]), cfg.id);
  }
  assert.deepStrictEqual(E.restore('nope.f.value.blue.q.1.1.0.85.0'), [], 'a dataset the engine does not have is skipped');
  assert.strictEqual(E.restore('qcew_jobs.f.sharePR.blue.q.1.1.0.85.0,qcew_jobs.f.lq.blue.q.1.1.0.85.0,qcew_jobs.f.value.blue.q.1.1.0.85.0').length, 2, 'a third shaded layer is left out');
  assert.strictEqual(E.restore('poverty_pct.f.lq.blue.q.1.1.0.85.0')[0].norm, 'value', 'a normalization the dataset does not offer becomes "as published"');
  const m = E.restore('poverty_pct.f.value.blue.m.1.1.0.85.0.1~2~3~4');
  assert.deepStrictEqual([m[0].classes, m[0].breaks], ['manual', '1, 2, 3, 4']);
  // a shaded layer drawn on the barrios (js/econ_level.js) keeps its level in the link: mode code 'b'; a symbol layer has no level
  const b = E.restore('poverty_pct.b.value.blue.q.1.1.0.85.0');
  assert.deepStrictEqual([b[0].mode, b[0].level], ['fill', 'barrio']);
  assert.strictEqual(E.encode(b), 'poverty_pct.b.value.blue.q.1.1.0.85.0');
  assert.strictEqual(E.restore('poverty_pct.f.value.blue.q.1.1.0.85.0')[0].level, undefined);
  const card = (L) => panel.layerCard(E, L, 0, 1, {});
  assert.ok(!card(b[0]).includes('data-f="level"'), 'no Area choice unless economy.js says the dataset has barrios');
  assert.ok(card({ ...b[0], levels: ['barrio'] }).includes('<option value="barrio" selected>'), 'the Area choice shows the barrio level when it is on');
  // the card's Shaded and Symbol switches: what `on` says (the dataset list's checkboxes), the layer's own mode without it; with two shaded layers the Shaded tooltip says why not a third
  const sw = (h) => [...h.matchAll(/data-mode="(\w+)" aria-pressed="(\w+)" title="([^"]*)"/g)].map(m => [m[1], m[2], m[3]]);
  assert.deepStrictEqual(sw(card(b[0])).map(s => s.slice(0, 2)), [['fill', 'true'], ['symbol', 'false']]);
  const both = sw(panel.layerCard(E, b[0], 0, 1, {}, () => true));
  assert.deepStrictEqual(both, [['fill', 'true', 'Turn the shading off'], ['symbol', 'true', 'Turn the symbols off']]);
  const sym = { ...b[0], mode: 'symbol' }, full = sw(panel.layerCard(E, sym, 0, 1, {}, (k, m) => m === 'symbol', true));
  assert.deepStrictEqual(full.map(s => s.slice(0, 2)), [['fill', 'false'], ['symbol', 'true']]);
  assert.ok(/bivariate/.test(full[0][2]), full[0][2]);
  assert.strictEqual(sw(panel.layerCard(E, sym, 0, 1, {}, (k, m) => m === 'symbol', false))[0][2], 'Shade the map by this dataset');
});
test('engine: the contract returns ids, names, values, margins and flags', () => {
  const s = E.series({ key: 'median_gross_rent' }, 2020);
  assert.deepStrictEqual([s.ids.length, s.names.length, s.values.length], [79, 79, 79]);
  assert.deepStrictEqual([s.meta.period, s.meta.key, s.meta.level, s.meta.unit], [2020, 'median_gross_rent', 'municipio', '$']);
  assert.ok(s.moe && s.moe.length === 79, 'rent is a survey: margins of error');
  assert.strictEqual(E.series({ key: 'median_gross_rent' }, 2020, 'tract'), null, 'a dataset without that level');
  assert.strictEqual(E.series({ key: 'no_such_dataset' }), null);
  const snap = E.series({ key: 'tourism_places' }, 1999);
  assert.deepStrictEqual([snap.meta.timeType, snap.flags.exact], ['snapshot', true], 'a snapshot is the current one whatever the year');
});
test('engine: a margin of error follows the layer it belongs to', () => {
  const L = { key: 'median_gross_rent', norm: 'value', real: false }, y = 2020;
  assert.ok(E.moe(L, y).some(x => x != null));
  assert.strictEqual(E.moe({ ...L, norm: 'per1000' }, y), null, 'a normalized layer has no published margin');
  const real = E.moe({ ...L, real: true }, y), f = E.cpiFactor(y);
  assert.ok(real.every((x, i) => x == null || Math.abs(x - E.moe(L, y)[i] * f) < 1e-9));
});

// ── the popup ───────────────────────────────────────────────────────────────
test('popup: a value, its rank and its margin', () => {
  E.year = null; E.base = 2014;
  const L = E.makeLayer('median_gross_rent', 'fill', {}, []); L.id = 1;
  const ev = E.evaluate([L]), i = E.geo.names.indexOf('Guaynabo');
  const v = popup.value(E, L, ev[1], i);
  assert.ok(/^\$\d+/.test(v.txt), v.txt);
  assert.strictEqual(v.rank, '#1 of 78', 'Guaynabo leads in at least 95% of the 1,000 draws (the old overlap rule said 1-2)');
  assert.ok(/^±\$\d+/.test(v.moe), v.moe);
  assert.strictEqual(popup.value(E, L, undefined, i).txt, '—');
  assert.ok(popup.inspect(E, [L], ev, i, true).includes('Guaynabo'));
  assert.ok(popup.hover(E, [L], ev, i).startsWith('<b>Guaynabo</b>'));
});

// ── the exposure adapter, on the real exposure files ─────────────────────────
function exposureEngine(withLevels) {
  const X = realEngine(), files = { municipio: readData('exposure_municipio.json') };
  if (withLevels) { files.barrio = readData('exposure_barrio.json'); files.tract = readData('exposure_tract.json'); }
  adapters.exposure(X, files);
  return X;
}
test('exposure: 84 datasets, residents and housing units for each of 42 families, in twelve groups', () => {
  const X = exposureEngine(false), list = X.list().filter(v => v.family === 'exposure');
  assert.strictEqual(list.length, 84);   // 30 families, the two walking ones (2026-10-16) and ten storm surge ones (2026-11-17)
  assert.ok(X.V.exp_walk_cur_pop && X.V.exp_walk_freq_hu, 'the walking families join the stack');
  assert.ok(X.V.exp_surge_cat3_pop && X.V.exp_surge_deep_cat5_hu, 'the storm surge families join the stack');
  assert.strictEqual(X.V.exp_surge_cat3_pop.group, 'Residents · Storm surge · NOAA NHC (near worst case, high tide)');
  assert.deepStrictEqual(X.V.exp_surge_cat3_pop.sources, ['exp_blocks', 'exp_surge']);
  assert.strictEqual(new Set(list.map(v => v.group)).size, 12);
  assert.ok(list.every(v => v.static && v.type === 'count' && v.ys.length === 1 && /^exposure.(pop|hu)_(flood|slr|low|surge|protected|transit)$/.test(v.dictId)));
  assert.strictEqual(X.V.exp_flood_sfha_pop.label, 'Residents: Inside a Special Flood Hazard Area (1% annual chance)');
  assert.strictEqual(X.V.exp_stop_cur_hu.group, 'Housing units · Transit stops within 400 m');
  assert.deepStrictEqual(X.normOptions('exp_slr_3ft_pop').map(o => o[0]), ['value', 'shareArea', 'per1000', 'perkm2', 'sharePR', 'pctile'], 'an exposure count is shown as a share of its own area, so it has no per-housing-unit view');
  assert.strictEqual(normalize.defaultNorm(X.V.exp_slr_3ft_pop, 'fill'), 'shareArea');
  assert.strictEqual(normalize.defaultNorm(X.V.exp_slr_3ft_pop, 'symbol'), 'value');
});
test("exposure: the counts are the file’s, the island is their sum and a share is the count over the area’s own total", () => {
  const X = exposureEngine(false), m = readData('exposure_municipio.json'), i = X.geo.ids.indexOf('72127');
  const count = X.values('exp_flood_sfha_pop', { norm: 'value' }), share = X.values('exp_flood_sfha_pop', { norm: 'shareArea' });
  assert.strictEqual(count.values[X.geo.pr], m.vars.flood_sfha.pop.reduce((a, b) => a + b, 0));
  assert.strictEqual(count.values[X.geo.pr], 316309, 'residents in a 1% flood area, island');
  assert.strictEqual(count.values[i], m.vars.flood_sfha.pop[m.geo.ids.indexOf('72127')]);
  assert.ok(Math.abs(share.values[i] - count.values[i] / m.total.pop[m.geo.ids.indexOf('72127')] * 100) < 1e-9);
  assert.ok(Math.abs(share.values[X.geo.pr] - 9.626327728939) < 1e-9, 'the island share');
  assert.deepStrictEqual([share.year, share.exact], [2026, true]);
  for (const k of Object.keys(m.vars)) {   // a count is never more than its total
    for (const meas of ['pop', 'hu']) { const v = X.values(`exp_${k}_${meas}`, { norm: 'shareArea' }).values; assert.ok(v.every(x => x == null || (x >= 0 && x <= 100)), `${k} ${meas}`); }
  }
  const sharePR = X.values('exp_flood_sfha_pop', { norm: 'sharePR' }).values;
  assert.ok(Math.abs(sharePR[i] - count.values[i] / count.values[X.geo.pr] * 100) < 1e-9);
});
test('exposure: a place with no mapped hazard shows zero, not a gap', () => {
  const X = exposureEngine(false), v = X.values('exp_flood_sfha_pop', { norm: 'shareArea' }).values;
  assert.strictEqual(v[X.geo.ids.indexOf('72054')], 0, 'Florida is mapped entirely as minimal hazard');
  assert.ok(v.slice(0, X.geo.pr).every(x => x != null), 'every municipality has a value');
});
test('exposure: the finer levels answer through the contract', () => {
  const X = exposureEngine(true), L = { key: 'exp_slr_3ft_pop' }, m = readData('exposure_municipio.json');
  assert.strictEqual(X.series(L, null, 'region'), null, 'a level the dataset does not have');
  for (const [level, n] of [['barrio', 901], ['tract', 981]]) {
    const s = X.series({ ...L, norm: 'value' }, null, level);
    assert.strictEqual(s.ids.length, n); assert.strictEqual(s.values.length, n);
    assert.strictEqual(s.values.reduce((a, b) => a + b, 0), 25302, `${level} counts add up to the island`);
    assert.deepStrictEqual([s.meta.level, s.meta.period, s.meta.timeType, s.meta.island], [level, 2026, 'snapshot', 25302]);
    const sh = X.series({ ...L, norm: 'shareArea' }, null, level);
    assert.strictEqual(sh.meta.unit, '%');
    assert.ok(Math.abs(sh.meta.island - 25302 / 3285874 * 100) < 1e-9);
    assert.ok(sh.values.every(x => x == null || (x >= 0 && x <= 100)));
  }
  const mun = X.series({ ...L, norm: 'value' }, null, 'municipio');
  assert.strictEqual(mun.values[X.geo.pr], 25302);
  assert.strictEqual(X.series({ key: 'median_gross_rent' }, 2020, 'barrio'), null, 'a series that has no barrio level');
});
test("exposure: the Spanish names the language tool holds are the file’s own", () => {
  const m = readData('exposure_municipio.json'), es = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'es', 'labels_exposure.json'), 'utf8')), X = exposureEngine(false);
  for (const v of X.list().filter(x => x.family === 'exposure')) {
    assert.ok(es[v.label], v.label); assert.ok(es[v.group], v.group);
    const [meas, fam] = v.key.endsWith('_pop') ? ['Residentes', v.key.slice(4, -4)] : ['Unidades de vivienda', v.key.slice(4, -3)];
    assert.strictEqual(es[v.label], meas + ': ' + m.vars[fam].label.es, v.key);
  }
  assert.ok(es["% of the area's residents"] && es["% of the area's housing units"]);
});

// ── the snapshot fields of municipalities.json ───────────────────────────────
test('snapshot: 22 fields of municipalities.json join the stack, the island worked out by the rule of each field', () => {
  const X = realEngine(), muni = readData('municipalities.json'); adapters.snapshot(X, muni, X.snapYear);
  const keys = adapters.SNAPSHOT_FIELDS.map(f => f.key);
  assert.strictEqual(keys.length, 22);   // nine, the residents within a 400 m walk (2026-10-16), and the 11 measures of the retired shading menu (2026-11-04, decision 81 (d))
  const idx = new Set(readData('catalog_index.json').index.rows.map(r => r[0]));
  for (const k of keys) {
    const v = X.V[k]; assert.ok(v, k);
    assert.ok(v.static && v.ys.length === 1 && v.years[v.ys[0]].length === 79, k);
    assert.ok(idx.has(v.dictId), `${k}: the dictionary has the entry ${v.dictId}`);
    const a = X.values(k, { norm: 'value' }).values, raw = muni[X.geo.names[0]][k], first = typeof raw === 'boolean' ? +raw : raw;
    assert.strictEqual(a[0], first, `${k}: the first municipality`);
    assert.ok(a.slice(0, 78).every(x => x != null), `${k}: a value for every municipality`);
  }
  const isl = (k) => X.values(k, { norm: 'value' }).values[78], tot = (f) => Object.values(muni).reduce((a, m) => a + m[f], 0);
  assert.strictEqual(isl('in_sfha'), tot('in_sfha'));
  assert.strictEqual(isl('transit_stops'), tot('transit_stops'));
  assert.ok(Math.abs(isl('sfha_pct') - tot('in_sfha') / tot('assets') * 100) < 1e-9, 'a share of places is the ratio of the sums');
  // Computed from the data, not a fixed number: the nightly transit refresh changes this share, and a constant here blocked every new timetable (2026-10-29).
  assert.ok(Math.abs(isl('pop_served_active_pct') - Object.values(muni).reduce((a, m) => a + m.population_2020 * (m.pop_served_active_pct || 0), 0) / tot('population_2020')) < 1e-9, 'a share of residents is weighted by residents');
  assert.ok(Math.abs(isl('urban_pct') - Object.values(muni).reduce((a, m) => a + m.land_km2 * m.urban_pct, 0) / tot('land_km2')) < 1e-9, 'a share of land is weighted by land');
  assert.deepStrictEqual(X.normOptions('pop_served_pct').map(o => o[0]), ['value', 'index', 'diff', 'pctile']);
  assert.strictEqual(isl('gross_rent_change_pct'), null, 'no island value where the file has none'); assert.strictEqual(isl('uber_listed'), null);
  assert.ok(Math.abs(isl('acc_walk400_pct') - Object.values(muni).reduce((a, m) => a + m.assets * (m.acc_walk400_pct || 0), 0) / tot('assets')) < 1e-9, 'a share of places is weighted by places');
  assert.deepStrictEqual(X.normOptions('in_sfha').map(o => o[0]), ['value', 'per1000', 'perHU', 'perkm2', 'sharePR', 'pctile']);
});

// ── reliability: margins of error, few counted, withheld ────────────────────
test('reliability: a margin of error above 30% of the estimate, and an estimate of zero with any margin', () => {
  const u = reliability.isUnreliable;
  assert.strictEqual(u(100, 30), false, 'exactly 30% is not above 30%');
  assert.strictEqual(u(100, 30.1), true);
  assert.strictEqual(u(-100, 31), true, 'a negative estimate is judged by its size');
  assert.strictEqual(u(0, 5), true, 'zero with a margin is too wide to read');
  assert.strictEqual(u(0, 0), false);
  assert.ok(!u(null, 5) && !u(5, null) && !u(undefined, undefined), 'no estimate or no margin: nothing to flag');
  assert.deepStrictEqual([reliability.MOE_SHARE, reliability.SMALL_COUNT], [0.3, 10]);
});
function layerOf(X, key, o = {}) { const L = X.makeLayer(key, o.mode || 'fill', o, []); L.id = 1; X.year = o.year ?? null; X.base = 2014; X.cache = {}; return { L, ev: X.evaluate([L])[1] }; }
test('reliability: the municipalities flagged in real survey series match an independent count (Python, from the published files)', () => {
  const X = realEngine();
  for (const [k, n] of [['nonprofit_worker_pct', 66], ['commute_walk_pct', 74], ['seasonal_units', 40], ['workers_16plus', 0], ['gini', 0], ['poverty_pct', 1], ['median_gross_rent', 2]]) {
    const { L, ev } = layerOf(X, k, { norm: 'value' }), r = X.reliability(L, ev);
    assert.strictEqual(r.n.moe, n, k); assert.strictEqual(r.flagged.length, 78, 'one entry for each municipality, none for the island');
    assert.strictEqual(r.notCarried, false); assert.strictEqual(r.small, null);
  }
  const walk = layerOf(X, 'commute_walk_pct', { norm: 'index' });
  const r = X.reliability(walk.L, walk.ev);
  assert.deepStrictEqual([r.n.moe, r.notCarried], [74, true], 'a view that is not as published keeps the flags and says the margins are not carried through');
  const pov = layerOf(X, 'poverty_pct', { norm: 'change' });
  assert.strictEqual(X.reliability(pov.L, pov.ev).n.moe, 1, 'a change is as uncertain as the less certain of its two years');
  assert.strictEqual(X.reliability(layerOf(X, 'qcew_jobs').L, null).n.flagged, 0, 'no evaluation, no flags');
  assert.strictEqual(X.reliability(layerOf(X, 'qcew_jobs', { norm: 'per1000' }).L, layerOf(X, 'qcew_jobs').ev).moe, null, 'a series without margins has none to flag');
});
test('reliability: a rate of a count of fewer than 10 is flagged, a raw count is not', () => {
  const X = exposureEngine(false);
  for (const [k, n] of [['exp_slr_3ft_hu', 10], ['exp_slr_3ft_pop', 2], ['exp_flood_sfha_hu', 3], ['exp_flood_sfha_pop', 0]]) {
    const { L, ev } = layerOf(X, k, { norm: 'shareArea' }), r = X.reliability(L, ev);
    assert.strictEqual(r.n.small, n, k);
    const i = r.small.findIndex(Boolean); if (n) assert.ok(i >= 0 && ev.a[i] != null);
    assert.strictEqual(X.reliability(...Object.values(layerOf(X, k, { norm: 'value' }))).small, null, `${k}: a raw count is exact`);
  }
  // a share built on a count a dataset names (the share of places in a flood area rests on the number of places)
  const Y = engine.create(); Y.setGeo(['a', 'b', 'c', 'p'], ['A', 'B', 'C', 'PR'], [1, 1, 1, 3]);
  Y.add({ key: 's', label: 'S', group: 'g', unit: '%', d: 1, type: 'rate', years: { 2020: [50, 20, 10, 25] }, counted: [4, 40, 9, 53] });
  Y.denominators.pop = 's';
  const { L, ev } = layerOf(Y, 's', {}); const r = Y.reliability(L, ev);
  assert.deepStrictEqual([r.small, r.n.small, r.n.flagged], [[true, false, true], 2, 2]);
});
test('reliability: figures a source withholds are counted as blanks, with a note', () => {
  const X = realEngine();
  assert.strictEqual(X.V.jobs_naics_21.withheld, true); assert.ok(!X.V.qcew_jobs.withheld && !X.V.gini.withheld);
  const { L, ev } = layerOf(X, 'jobs_naics_21', { norm: 'value' }), r = X.reliability(L, ev);
  assert.strictEqual(r.withheld, 77);
  const n = reliability.notes(X, L, ev);
  assert.deepStrictEqual(n.map(x => [x.kind, x.n, x.swatch]), [['withheld', 77, null]]);
  assert.ok(reliability.cautions(X.V.jobs_naics_21).map(c => c.kind).join() === 'workplace,withheld,area');
  assert.ok(reliability.cautions(X.V.median_gross_rent).map(c => c.kind).join() === 'survey,area');
  assert.ok(reliability.cautions(X.V.population).map(c => c.kind).join() === 'area', 'a count that is not a survey has only the standing caution');
});
test('reliability: the legend says it in words and in hatching, and a layer of symbols says it with a dashed outline', () => {
  const X = realEngine(), { L, ev } = layerOf(X, 'commute_walk_pct', { norm: 'value' });
  let n = reliability.notes(X, L, ev);
  assert.deepStrictEqual(n.map(x => [x.kind, x.n, x.swatch, x.label]), [['moe', 74, 'hatch', 'Hatched: margin of error above 30% of the estimate']]);
  const html = stackLegend.blocks(X, [L], { 1: ev }, false).join('');
  assert.ok(html.includes('<span class="sw hatch"></span>Hatched: margin of error above 30% of the estimate<small>74</small>'), html.slice(-400));
  assert.ok(!html.includes('are not carried through'), 'as published: the margins are carried');
  const idx = layerOf(X, 'commute_walk_pct', { norm: 'index' });
  assert.deepStrictEqual(reliability.notes(X, idx.L, idx.ev).map(x => x.kind), ['moe', 'notCarried']);
  const sym = layerOf(X, 'seasonal_units', { mode: 'symbol' });
  n = reliability.notes(X, sym.L, sym.ev);
  assert.deepStrictEqual(n.map(x => [x.kind, x.n, x.swatch, x.label]), [['moe', 40, 'dash', 'Dashed outline: margin of error above 30% of the estimate']]);
  const clean = layerOf(X, 'median_hh_income', { norm: 'value' });
  assert.deepStrictEqual(reliability.notes(X, clean.L, clean.ev), [], 'nothing flagged: nothing added');
  assert.ok(!/class="row rel"|el-note/.test(stackLegend.blocks(X, [clean.L], { 1: clean.ev }, false).join('')));
  // two shaded layers together: each layer's lines carry its name
  const A = X.makeLayer('commute_walk_pct', 'fill', { norm: 'value' }, []), B = X.makeLayer('median_hh_income', 'fill', { norm: 'value' }, [A]); A.id = 1; B.id = 2;
  const evs = X.evaluate([A, B]), biv = stackLegend.blocks(X, [A, B], evs, false).join('');
  assert.ok(biv.includes('Walk to work (%): Hatched') || /<div class="row rel"><span class="sw hatch"><\/span>[^<]*: Hatched: margin of error/.test(biv), biv.slice(-500));
  assert.deepStrictEqual(X.flagged([A, B], evs).length, 74, 'the places flagged in either layer');
});
test('reliability: the pop-up, the hover card and the tables mark a less reliable value in italics', () => {
  const X = realEngine(), { L, ev } = layerOf(X, 'commute_walk_pct', { norm: 'value' }), r = X.reliability(L, ev);
  const bad = r.flagged.indexOf(true), good = r.flagged.indexOf(false);
  assert.ok(bad >= 0 && good >= 0);
  assert.strictEqual(popup.value(X, L, ev, bad).flagged, true); assert.strictEqual(popup.value(X, L, ev, good).flagged, false);
  assert.strictEqual(popup.value(X, L, ev, X.geo.pr).flagged, false, 'the island is never flagged');
  const insp = popup.inspect(X, [L], { 1: ev }, bad, true), ok = popup.inspect(X, [L], { 1: ev }, good, true);
  assert.ok(insp.includes('<td class="num unrel">') && insp.includes('less reliable') && insp.includes('Italic values are less reliable'), 'flagged value, hidden text for screen readers, and the sentence');
  assert.ok(!ok.includes('unrel') && !ok.includes('Italic values'), 'an unflagged value is drawn as it always was');
  assert.ok(popup.hover(X, [L], { 1: ev }, bad).includes('<b class="unrel">') && !popup.hover(X, [L], { 1: ev }, good).includes('unrel'));
  assert.ok(reliability.moeKey().includes('<i>Italic</i>') && reliability.flagKey().startsWith('Italic values'));
});

// ── class limits a user types ───────────────────────────────────────────────
test('classes: limits typed by a user cut the five classes; anything else falls back to quantiles', () => {
  const X = realEngine(), { L, ev } = layerOf(X, 'poverty_pct', { norm: 'value', classes: 'manual', breaks: '20, 30, 40, 50' });
  assert.deepStrictEqual(X.breaks(L, ev.y).edges.slice(1, -1), [20, 30, 40, 50]);
  const q = X.breaks({ ...L, classes: 'quantile' }, ev.y).edges;
  assert.deepStrictEqual(X.breaks({ ...L, breaks: '20, 30' }, ev.y).edges, q, 'two numbers are not four limits');
  assert.deepStrictEqual(X.breaks({ ...L, breaks: '50, 40, 30, 20' }, ev.y).edges, q, 'limits must rise');
  const text = X.manualDefault({ ...L, classes: 'quantile', breaks: undefined }, ev.y);
  assert.deepStrictEqual(classify.parseBreaks(text, 5).length, 4, text);
  assert.deepStrictEqual(classify.parseBreaks(text, 5), q.slice(1, -1).map(x => +x.toPrecision(3)), 'it starts from the classes the layer has now');
  assert.strictEqual(X.manualDefault({ ...L, norm: 'index' }, ev.y), '', 'a scale around a center has fixed cut-offs');
  // the legend uses them, and a link keeps them
  const html = stackLegend.blocks(X, [L], { 1: ev }, false).join('');
  assert.ok(html.includes('20.0% to 30.0%'), html.slice(0, 400));
  assert.ok(X.encode([L]).includes('.m.') && X.encode([L]).endsWith('.20~30~40~50'), X.encode([L]));
});
test('classes: the layer card offers my own limits, shows the field when they are chosen and flags a text that is not four rising numbers', () => {
  const X = realEngine(), { L, ev } = layerOf(X, 'poverty_pct', { norm: 'value' });
  const card = (l) => panel.layerCard(X, l, 0, 1, ev);
  assert.ok(card(L).includes('<option value="manual">My own limits</option>') && !card(L).includes('data-f="breaks"'));
  const m = { ...L, classes: 'manual', breaks: '20, 30, 40, 50' };
  assert.ok(card(m).includes('<option value="manual" selected>My own limits</option>') && card(m).includes('data-f="breaks"') && !card(m).includes('aria-invalid'));
  assert.ok(card({ ...m, breaks: '20, 30' }).includes('aria-invalid="true"') && card({ ...m, breaks: '20, 30' }).includes('Until then the classes are quantiles'));
  assert.ok(!card({ ...m, mode: 'symbol' }).includes('data-f="breaks"'), 'symbols have no classes');
});

// ── hexagons ────────────────────────────────────────────────────────────────
const hexbin = core('hexbin');
const sphArea = (ring) => { let s = 0; for (let i = 0; i < ring.length; i++) { const [la1, lo1] = ring[i], [la2, lo2] = ring[(i + 1) % ring.length]; s += (lo2 - lo1) * Math.PI / 180 * (2 + Math.sin(la1 * Math.PI / 180) + Math.sin(la2 * Math.PI / 180)); } return Math.abs(s) * 6371.0088 ** 2 / 2; };   // km², a polygon whose sides run along parallels and meridians (Chamberlain and Duquette)
test('hexbin: the projection is equal-area and can be undone', () => {
  for (const [la, lo] of [[18.2, -66.45], [18.45, -65.25], [17.95, -67.2], [18.33, -64.9]]) { const [x, y] = hexbin.project(la, lo), [la2, lo2] = hexbin.unproject(x, y); assert.ok(Math.abs(la - la2) < 1e-9 && Math.abs(lo - lo2) < 1e-9, `${la},${lo}`); }
  assert.ok(hexbin.project(18.2, -66.45).every(v => Math.abs(v) < 1e-9), 'the center of the island is the origin');
  const flat = (ring) => { const p = ring.map(([la, lo]) => hexbin.project(la, lo)); let s = 0; for (let i = 0; i < p.length; i++) { const [x1, y1] = p[i], [x2, y2] = p[(i + 1) % p.length]; s += x1 * y2 - x2 * y1; } return Math.abs(s) / 2; };
  for (const [la, lo] of [[18.0, -67.1], [18.45, -65.3], [18.2, -66.45], [18.35, -64.95]]) {
    const q = [[la, lo], [la, lo + .1], [la + .1, lo + .1], [la + .1, lo]];
    assert.ok(Math.abs(sphArea(q) / flat(q) - 1) < 1e-3, `${la},${lo}: ${sphArea(q)} km² on the ground, ${flat(q)} km² on the plane`);
  }
});
test('hexbin: every hexagon holds the same area on the ground, wherever it is', () => {
  const places = readData('places.json');
  for (const km2 of [2, 10, 50]) {
    const b = hexbin.bin(places, { area: km2 }), feats = hexbin.features(b);
    assert.strictEqual(feats.length, b.cells.length);
    for (const i of [0, 7, 100, 333, b.cells.length - 1].filter(i => i < feats.length)) {
      const ring = feats[i].geometry.coordinates[0];
      assert.strictEqual(ring.length, 7); assert.deepStrictEqual(ring[0], ring[6], 'a closed ring');
      const area = sphArea(ring.slice(0, 6).map(([lo, la]) => [la, lo]));
      assert.ok(Math.abs(area / km2 - 1) < 0.01, `${km2} km² hexagon number ${i}: ${area.toFixed(3)} km² on the ground`);
    }
  }
});
test('hexbin: counts are conserved, ids are unique and a larger hexagon means fewer cells', () => {
  const places = readData('places.json'), sizes = [2, 10, 50].map(km2 => hexbin.bin(places, { area: km2 }));
  const located = places.filter(p => p.lat != null && p.lng != null).length;   // a place withheld from the map has no point (places_privacy.py)
  assert.ok(located < places.length && located > 30000, `${located} of ${places.length} listings have a point`);
  for (const b of sizes) { assert.strictEqual(b.cells.reduce((t, c) => t + c.n, 0), located); assert.strictEqual(new Set(b.cells.map(c => c.id)).size, b.cells.length); assert.ok(b.cells.every(c => c.n >= 1 && c.w === c.n)); }
  assert.ok(sizes[0].cells.length > sizes[1].cells.length && sizes[1].cells.length > sizes[2].cells.length, sizes.map(b => b.cells.length).join(' > '));
  assert.ok(sizes[1].cells.length > 300 && sizes[1].cells.length < 2500, `${sizes[1].cells.length} hexagons of 10 km² hold the 35,000 listings`);
  assert.strictEqual(hexbin.bin([{ lat: 18.2, lng: -66.45 }, { lat: null, lng: -66 }, { lat: 18, lng: undefined }]).cells.length, 1, 'a point without a position is left out');
  assert.strictEqual(hexbin.bin([{ lat: 18.2, lng: -66.45 }]).cells[0].id, '0,0', 'the hexagon at the origin is 0,0 and not -0,0');
  assert.strictEqual(hexbin.bin([{ lat: 18.2, lng: -66.45, w: 5 }, { lat: 18.2, lng: -66.45 }]).cells[0].w, 6, 'a weight counts for what it says');
});
test('hexbin: a point belongs to the hexagon whose center is nearest, and neighbors are the same distance apart', () => {
  const s = hexbin.size(10), at = (x, y) => { const [la, lo] = hexbin.unproject(x, y); return hexbin.bin([{ lat: la, lng: lo }], { area: 10 }).cells[0].id; };
  const c = (q, r) => [s * Math.sqrt(3) * (q + r / 2), s * 1.5 * r];
  for (const [q, r] of [[0, 0], [3, -2], [-5, 4], [10, 1]]) {
    const [x, y] = c(q, r);
    assert.strictEqual(at(x, y), `${q},${r}`);
    for (const a of [0, 60, 120, 180, 240, 300]) assert.strictEqual(at(x + .8 * s * Math.sqrt(3) / 2 * Math.cos(a * Math.PI / 180), y + .8 * s * Math.sqrt(3) / 2 * Math.sin(a * Math.PI / 180)), `${q},${r}`, `inside the inscribed circle at ${a} degrees`);
  }
  const d = (p, q) => Math.hypot(c(...p)[0] - c(...q)[0], c(...p)[1] - c(...q)[1]);
  assert.ok([[1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, -1]].every(n => Math.abs(d([0, 0], n) - s * Math.sqrt(3)) < 1e-9), 'six neighbors at the same distance');
  assert.ok(Math.abs(3 * Math.sqrt(3) / 2 * s * s - 10) < 1e-9, 'the area of the hexagon is the one asked for');
});
test('adapters: a list of points becomes a count for each municipality and, as the hex level, a count for each hexagon', () => {
  const X = realEngine(), places = readData('places.json'), muni = readData('municipalities.json');
  const ds = adapters.points(X, { key: 'listings_shown', label: 'Listings shown', group: 'Tourism supply', points: places, filter: p => p.confidence >= .5 && p.type !== 'Places of Worship', sources: ['overture'], ref: 'Overture', definition: 'Listings that pass the filter.' });
  assert.ok(ds.static && ds.type === 'count' && ds.ys.length === 1);
  const c = X.values('listings_shown', { norm: 'value' }).values;
  assert.strictEqual(c.length, 79);
  assert.strictEqual(c[X.geo.pr], c.slice(0, 78).reduce((a, b) => a + b, 0), 'the island is the sum');
  assert.deepStrictEqual(c.slice(0, 78), X.geo.names.slice(0, 78).map(n => muni[n].assets), 'the same count as the snapshot field, which was made with the same filter');
  const L = { key: 'listings_shown', hex: { area: 10 } }, s = X.series(L, null, 'hex');
  const shownWithPoint = places.filter(p => p.lat != null && p.confidence >= .5 && p.type !== 'Places of Worship').length;
  assert.strictEqual(s.values.reduce((a, b) => a + b, 0), shownWithPoint, 'the hexagons hold the same listings, less those withheld from the map (no point: places_privacy.py)');
  assert.strictEqual(c[X.geo.pr] - shownWithPoint, places.filter(p => p.withheld && p.confidence >= .5 && p.type !== 'Places of Worship').length, 'the municipal counts include the withheld places');
  assert.deepStrictEqual([s.meta.level, s.meta.timeType, s.meta.cell.km2, s.meta.method], ['hex', 'snapshot', 10, 'points counted in each hexagon; hexagons are equal-area']);
  assert.strictEqual(s.ids.length, s.values.length);
  assert.ok(X.series({ key: 'listings_shown', hex: { area: 2 } }, null, 'hex').ids.length > s.ids.length, 'smaller hexagons, more of them');
  assert.strictEqual(X.series(L, null, 'tract'), null, 'a level the points do not have');
});

// ── time: survey windows ────────────────────────────────────────────────────
test('time: a survey year is named by its whole window, a count by its year', () => {
  const X = realEngine();
  const chip = (key, year = 2020) => { X.year = year; X.cache = {}; const L = X.makeLayer(key, 'fill', {}, []); L.id = 1; return X.chip(L, X.evaluate([L])[1]); };
  assert.strictEqual(chip('median_gross_rent'), '2016–2020');
  assert.strictEqual(chip('poverty_pct'), '2016–2020');
  assert.strictEqual(chip('median_gross_rent', 2007), 'first data 2006–2010');
  assert.strictEqual(chip('median_gross_rent', 2026), '2020–2024 (latest at or before 2026)');
  assert.strictEqual(chip('qcew_jobs'), '2020');
  assert.strictEqual(chip('jobs_per_employed_resident'), '2020', 'a yearly count over a survey is not a window');
  assert.strictEqual(chip('population'), '2020', 'a count of people is not a survey window');
  assert.strictEqual(chip('tourism_places', 2012), 'snapshot 2026');
  const windows = X.list().filter(v => v.time && v.time.type === 'window');
  assert.ok(windows.length > 50, `${windows.length} survey series`);
  assert.ok(windows.every(v => v.time.windowYears === 5 && v.sources.every(s => s === 'acs' || s === 'hs_derived')), 'only series made from ACS tables');
  assert.ok(X.list().filter(v => (v.sources || []).some(s => ['qcew', 'laus', 'usaspending', 'openfema', 'pep'].includes(s))).every(v => !v.time), 'no yearly source is called a window');
});

// ── the derived adapter ─────────────────────────────────────────────────────
test('adapters: a dataset computed from two others keeps its formula and is labeled as derived', () => {
  const X = realEngine();
  const r = adapters.derived(X, { key: 'jobs_per_1000_x', label: 'Jobs per 1,000 residents (derived)', group: 'Derived', of: ['qcew_jobs', 'population'], op: 'ratio', scale: 1000, unit: '', d: 1, definition: 'Jobs at employers in the municipality for every 1,000 residents.' });
  assert.ok(r && r.derived.formula === 'Jobs (all employers) ÷ Resident population × 1000', r && r.derived.formula);
  assert.deepStrictEqual(r.ys, X.V.qcew_jobs.ys.filter(y => X.V.population.years[y]), 'the years both inputs have');
  const mine = X.values('jobs_per_1000_x', { year: 2022, norm: 'value' }).values, theirs = X.values('qcew_jobs', { year: 2022, norm: 'per1000' }).values;
  assert.ok(mine.slice(0, 78).every((x, i) => x == null || theirs[i] == null || Math.abs(x - theirs[i]) < 5e-4), 'the same as the per-1,000 view of the jobs');
  assert.ok(r.definition.endsWith('Formula: Jobs (all employers) ÷ Resident population × 1000.') && r.ref.startsWith('Computed in the browser'));
  assert.deepStrictEqual(r.sources.slice().sort(), [...new Set([...X.V.qcew_jobs.sources, ...X.V.population.sources])].sort());
  assert.ok(!r.moe, 'margins of error are not carried through');
  assert.ok(reliability.cautions(r).some(c => c.kind === 'derived' && c.text.includes('not a published figure')));
  const d = adapters.derived(X, { key: 'x_diff', label: 'Gap', of: ['population', 'households'], op: 'diff', type: 'count', unit: '', d: 0 });
  assert.strictEqual(X.values('x_diff', { year: 2022, norm: 'value' }).values[0], X.values('population', { year: 2022 }).values[0] - X.values('households', { year: 2022 }).values[0]);
  assert.strictEqual(adapters.derived(X, { key: 'nope', label: 'x', of: ['qcew_jobs', 'no_such_series'] }), null, 'an input that does not exist');
  assert.strictEqual(adapters.derived(X, { key: 'nope2', label: 'x', of: ['qcew_jobs', 'population'], op: 'median' }), null, 'an operation that does not exist');
  const flat0 = adapters.derived(X, { key: 'x_ratio', label: 'ratio', of: ['qcew_jobs', 'population'], op: 'ratio' });
  assert.ok(flat0.derived.scale === 1 && flat0.derived.formula === 'Jobs (all employers) ÷ Resident population');
});

// ── the snapshot series file adapter, on the real health series (health_series.py) ──
function healthEngine(doc = readData('health_series.json')) {
  const X = realEngine();
  adapters.snapshotFile(X, doc, { dict: 'health.', group: 'Health care · ' });
  return X;
}
test('health series: eleven snapshot datasets in four groups, each with its dictionary id and source', () => {
  const X = healthEngine(), doc = readData('health_series.json'), list = X.list().filter(v => v.family === 'health');
  assert.strictEqual(list.length, 11);
  assert.deepStrictEqual([...new Set(list.map(v => v.group))], ['Health care · Health centers', 'Health care · Primary care shortage areas', 'Health care · Dental shortage areas', 'Health care · Mental health shortage areas']);
  assert.ok(list.every(v => v.static && v.ys.length === 1 && v.ys[0] === doc.years[0] && v.time.type === 'snapshot' && v.time.asOf === doc.as_of && v.built === doc.built && v.dictId === 'health.' + v.key));
  assert.ok(list.every(v => v.sources.length === 1 && X.sources[v.sources[0]] && X.sources[v.sources[0]].url), 'the source of each dataset is described in the engine');
  assert.deepStrictEqual(X.geo.ids, doc.geo.ids, 'the file lists the places in the engine order');
  assert.ok(list.every(v => v.years[v.ys[0]].length === 79), 'one value for each of the 78 municipalities and Puerto Rico last');
});
test('health series: an empty value stays empty, a count of none stays a zero, and a score has no island value', () => {
  const X = healthEngine(), at = (n) => X.geo.names.indexOf(n), v = (k) => X.values(k, { norm: 'value' }).values;
  const doc = readData('health_series.json'), col = (k) => Object.values(doc.vars.find(x => x.key === k).years)[0], first = (k, f) => doc.geo.names.find((n, i) => i < 78 && f(col(k)[i]));   // the file's own figures
  const noSite = first('hc_sites', x => x === 0), withSite = first('hc_sites', x => x > 0), noDesignation = first('hpsa_pc_score', x => x === null), scored = first('hpsa_pc_score', x => x > 0), zeroMet = first('hpsa_pc_met', x => x === 0);
  assert.ok(noSite && withSite && noDesignation && scored && zeroMet, 'the file has a municipality with no site, one with a site, one with no primary care designation, one with a score and one with a real zero of need met');
  assert.strictEqual(v('hc_sites')[at(noSite)], 0, 'HRSA lists no site there: a true zero');
  assert.strictEqual(v('hc_sites')[at(withSite)], col('hc_sites')[at(withSite)]);
  assert.strictEqual(v('hc_sites')[X.geo.pr], col('hc_sites').slice(0, 78).reduce((a, x) => a + x, 0), 'the island is the sum of the 78');
  assert.strictEqual(v('hpsa_pc_score')[at(noDesignation)], null, 'no area-level designation: no value, not a score of zero');
  assert.strictEqual(v('hpsa_pc_short')[at(noDesignation)], null);
  assert.ok(v('hpsa_pc_score')[at(scored)] > 0 && v('hpsa_pc_score')[X.geo.pr] === null, 'a score is not added or averaged');
  assert.strictEqual(v('hpsa_pc_met')[at(zeroMet)], col('hpsa_pc_met')[at(zeroMet)], 'a real zero (HRSA counts no practitioner for it) stays a zero for a municipality that has a designation');
  assert.strictEqual(v('hpsa_pc_met')[at(zeroMet)], 0);
  const sum = v('hpsa_pc_short').slice(0, 78).reduce((a, x) => a + (x || 0), 0);
  assert.ok(Math.abs(sum - v('hpsa_pc_short')[X.geo.pr]) < 0.01, 'the island shortage is the sum of the municipal ones');
  const r = X.series({ key: 'hpsa_pc_score' }), none = r.flags.noValue.slice(0, 78).filter(Boolean).length;
  assert.strictEqual(none, col('hpsa_pc_score').slice(0, 78).filter(x => x === null).length, 'the contract flags the municipalities with no value');
  assert.strictEqual(r.meta.timeType, 'snapshot');
});
test('health series: a score offers no comparison with Puerto Rico; a share and a count offer what they should', () => {
  const X = healthEngine(), opts = (k) => X.normOptions(k).map(o => o[0]);
  assert.deepStrictEqual(opts('hpsa_pc_score'), ['value', 'pctile'], 'no index and no difference from an island value that does not exist');
  assert.deepStrictEqual(opts('hpsa_dh_met'), ['value', 'index', 'diff', 'pctile']);
  assert.ok(['per1000', 'perkm2', 'sharePR'].every(o => opts('hc_sites').includes(o)));
  assert.ok(!opts('hc_sites').includes('change'), 'a snapshot has no change since a base year');
  assert.strictEqual(normalize.defaultNorm(X.V.hc_sites, 'fill'), 'per1000');
  assert.strictEqual(normalize.defaultNorm(X.V.hpsa_pc_score, 'fill'), 'value');
  const a = X.values('hc_sites', { norm: 'per1000' }).values, pop = X.pop(2026), sites = Object.values(readData('health_series.json').vars.find(x => x.key === 'hc_sites').years)[0], i = sites.findIndex((x, j) => j < 78 && x > 0);
  assert.ok(i >= 0 && pop[i] > 0, 'the file has a municipality with a site');
  assert.ok(Math.abs(a[i] - sites[i] / pop[i] * 1000) < 1e-3, 'per 1,000 residents uses the latest population at or before the snapshot year');
  assert.strictEqual(X.chip({ key: 'hc_sites' }, { y: 2026, exact: true }), 'snapshot 2026');
});
test('health series: places in another order are put in the engine order, and a place the engine lacks is skipped', () => {
  const doc = JSON.parse(JSON.stringify(readData('health_series.json'))), n = doc.geo.ids.length, order = Array.from({ length: n }, (_, i) => (i * 7) % n);   // 7 and 79 share no factor: a real permutation
  const mix = (a) => order.map(i => a[i]);
  doc.geo = { ids: mix(doc.geo.ids), names: mix(doc.geo.names) };
  doc.vars.forEach(v => { for (const y of Object.keys(v.years)) v.years[y] = mix(v.years[y]); });
  const X = healthEngine(doc), plain = healthEngine(), same = (k) => assert.deepStrictEqual(X.V[k].years[2026], plain.V[k].years[2026], k);
  doc.vars.forEach(v => same(v.key));
  doc.geo.ids[0] = '99999';   // a place the engine does not have
  assert.doesNotThrow(() => healthEngine(doc));
});
test('health series: a layer of it goes into a link and comes back', () => {
  const X = healthEngine(), L = X.makeLayer('hpsa_mh_met', 'fill', {}, []), s = X.encode([L]), back = X.decode(s);
  assert.ok(s.startsWith('hpsa_mh_met.f.value.'), s);
  assert.deepStrictEqual(back.map(b => b.key), ['hpsa_mh_met']);
  const r = X.restore('hpsa_pc_score.f.index.blue.q.1.0.0.80.0', []);
  assert.strictEqual(r[0].norm, 'value', 'a normalization the dataset does not offer becomes "as published"');
});
test('health series: the legend says an empty place has no shortage designation, and "No data" stays for the other datasets', () => {
  const X = healthEngine(), html = (key) => { const L = X.makeLayer(key, 'fill', {}, []); L.id = 1; return stackLegend.blocks(X, [L], X.evaluate([L]), false).join(''); };
  const score = html('hpsa_pc_score');
  const none = Object.values(X.V.hpsa_pc_score.years)[0].slice(0, 78).filter(x => x === null).length;
  assert.ok(score.includes('No area shortage designation') && !score.includes('No data'), `the ${none} municipalities with no area designation are not "no data"`);
  assert.ok(score.includes(`<small>${none}</small>`), 'and the legend counts them');
  assert.ok(!html('hc_sites').includes('No area shortage designation'), 'a count of sites has true zeros, not empty places');
  assert.ok(X.list().filter(v => v.noValue).every(v => v.family === 'health' && /^hpsa_/.test(v.key)), 'only the shortage-area datasets say it');
});

test('health series: a link with no class field takes the dataset\'s own start, and every dataset says whether it offers a view per housing unit and what kind of figure it is', () => {
  const X = healthEngine();
  assert.strictEqual(X.restore('hpsa_mh_met.f.value', [])[0].classes, 'jenks', 'the dictionary\'s own links (index.html#e=hpsa_mh_met.f) carry no class field');
  assert.strictEqual(X.restore('hpsa_mh_met.f.value.blue.q.1.0.0.85.0', [])[0].classes, 'quantile', 'a link that names a class method keeps it');
  assert.strictEqual(X.restore('poverty_pct.f.value', [])[0].classes, 'quantile', 'the datasets that did not ask keep quantiles');
  const opts = (k) => X.normOptions(k).map(o => o[0]);
  for (const k of ['hc_sites', 'hc_vans', 'hpsa_pc_short', 'hpsa_dh_short', 'hpsa_mh_short']) assert.ok(opts(k).includes('per1000') && !opts(k).includes('perHU'), `${k}: a count that does not sit on housing has no view per housing unit`);
  assert.ok(opts('lodging_places').includes('perHU'), 'other counts keep theirs');
  assert.deepStrictEqual(X.list().filter(v => v.tag).map(v => v.key).sort(), ['hpsa_dh_score', 'hpsa_mh_score', 'hpsa_pc_score'], 'a score is a score, not a ratio');
  assert.ok(X.list().filter(v => v.tag).every(v => v.tag === 'score'));
});
test('health series: the symbol and two-layer legends say what an empty place means, and short numbers keep the decimals of the dataset', () => {
  const X = healthEngine(), none = Object.values(X.V.hpsa_pc_score.years)[0].slice(0, 78).filter(x => x === null).length;
  const sym = X.makeLayer('hpsa_pc_score', 'symbol', {}, []); sym.id = 1;
  const hs = stackLegend.blocks(X, [sym], X.evaluate([sym]), false).join('');
  assert.ok(hs.includes('No area shortage designation') && hs.includes(`<small>${none}</small>`), 'the symbol legend counts the places with no designation');
  const A = X.makeLayer('hpsa_pc_score', 'fill', {}, []), B = X.makeLayer('poverty_pct', 'fill', {}, [A]); A.id = 1; B.id = 2;
  const hb = stackLegend.blocks(X, [A, B], X.evaluate([A, B]), false).join('');
  assert.ok(hb.includes(`${X.V.hpsa_pc_score.label}: No area shortage designation`), 'the two-layer legend names the layer the empty places belong to');
  const cnt = X.makeLayer('hc_sites', 'symbol', {}, []); cnt.id = 1;
  assert.ok(!stackLegend.blocks(X, [cnt], X.evaluate([cnt]), false).join('').includes('No area shortage designation'), 'a count with true zeros says nothing of the kind');
  assert.strictEqual(format.compact(0.034, '', 3), '0.034', 'a dataset that asks for three decimals gets them');
  assert.strictEqual(format.compact(0.034, ''), '0.03', 'the others keep two');
  assert.strictEqual(format.compact(8, '', 0), '8');
  for (const [k, norm] of [['hpsa_mh_short', 'per1000'], ['hpsa_mh_short', 'perkm2'], ['hpsa_pc_short', 'per1000'], ['hc_sites', 'per1000']]) {
    const L = X.makeLayer(k, 'fill', { norm }, []); L.id = 1;
    const html = stackLegend.blocks(X, [L], X.evaluate([L]), false).join(''), pairs = [...html.matchAll(/(\d+\.\d+) to (\d+\.\d+)/g)];
    assert.ok(pairs.length >= 3, `${k} ${norm}: the legend has class limits`);
    assert.ok(pairs.every(m => m[1] !== m[2]), `${k} ${norm}: a class that starts and ends at the same printed number (${pairs.map(m => m[0]).join(', ')})`);
  }
});
test('economy.js: the table, the pop-up and the dataset window read the empty-place wording, the file\'s build date and the kind of figure', () => {
  const eco = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'economy.js'), 'utf8'), pop = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'core', 'popup.js'), 'utf8');
  const table = eco.slice(eco.indexOf("$('#ebBody').innerHTML"), eco.indexOf("$('#ebBody').innerHTML") + 6000);
  assert.ok(/E\.missing\(/.test(table), 'the workbench table says what an empty place means');
  assert.ok(/E\.missing\(L, i\)/.test(pop), 'the pop-up does');
  assert.ok(eco.includes('v.built || EC.built'), 'the dataset window shows the date the file was made');
  assert.ok(eco.includes('v.tag ? T(v.tag)'), 'and the kind of figure the dataset says it is');
  assert.ok(/missing\(key, i\) \{ return E\.missing\(\{ key \}, i\); \}/.test(eco), 'the chat can ask what an empty place means');
});
test('health series: no legend of a health dataset repeats a limit, in any view it offers, and a score or a share is not written with decimals it does not have', () => {
  const X = healthEngine();
  for (const v of X.list().filter(x => x.family === 'health')) {
    for (const [norm, mode] of [['value', 'fill'], ...X.normOptions(v.key).map(o => o[0]).filter(n => n !== 'value').map(n => [n, 'fill']), ['value', 'symbol']]) {
      const L = X.makeLayer(v.key, mode, { norm }, []); L.id = 1;
      const html = stackLegend.blocks(X, [L], X.evaluate([L]), false).join(''), pairs = [...html.matchAll(/(-?[\d,]+(?:\.\d+)?%?) to (-?[\d,]+(?:\.\d+)?%?)/g)];
      assert.ok(pairs.every(m => m[1] !== m[2]), `${v.key} ${norm} ${mode}: a class that starts and ends at the same printed number (${pairs.map(m => m[0]).join(', ')})`);
    }
  }
  const score = X.makeLayer('hpsa_dh_score', 'fill', {}, []); score.id = 1;
  const sh = stackLegend.blocks(X, [score], X.evaluate([score]), false).join('');
  assert.ok(!/\d\.\d/.test(sh.replace(/<small>[^<]*<\/small>/g, '')), `an integer score is written as an integer: ${sh.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 200)}`);
  const met = X.makeLayer('hpsa_mh_met', 'fill', {}, []); met.id = 1;
  const mh = stackLegend.blocks(X, [met], X.evaluate([met]), false).join('');
  assert.ok(/0\.0%/.test(mh) && !/\d\.\d\d%/.test(mh), `a share with one decimal in the data has one decimal in the legend: ${mh.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 200)}`);
  assert.ok(/<span class="sw"[^>]*><\/span>0\.0%<small>/.test(mh), 'and a class that holds only the zeros is named once, not "0.0% to 0.0%"');
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'css', 'economy.css'), 'utf8'), pop = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'core', 'popup.js'), 'utf8');
  assert.ok(/\.eh-row b\.miss \{[^}]*white-space: normal/.test(src) && pop.includes("r.miss ? 'miss'") && pop.includes('miss: ev.a[i] == null && !!E.missing(L, i)') && pop.includes("${r.miss ? ' miss' : ''}") && /table\.ec-tbl td\.num\.miss \{[^}]*white-space: normal/.test(src), 'the words of an empty place wrap in the hover card and in the pop-up table instead of leaving them on a phone');
});
test('health series: a count per resident keeps three decimals, so a site for every 1,000 residents is not shown as 0.0', () => {
  const X = healthEngine(), L = { key: 'hc_sites', norm: 'per1000' }, vals = X.values('hc_sites', { norm: 'per1000' }).values, low = Math.min(...vals.slice(0, 78).filter(x => x > 0));
  assert.strictEqual(X.out(L).d, 3);
  assert.ok(low < 0.05, `the file has a municipality with fewer than one site for every 20 residents per 1,000 (${low}), a value that one decimal would show as 0.0`);
  assert.strictEqual(X.fmt(L, low), low.toFixed(3));
  assert.strictEqual(X.out({ key: 'hc_sites', norm: 'perkm2' }).d, 3);
  assert.strictEqual(X.out({ key: 'qcew_jobs', norm: 'per1000' }).d, 1, 'the other datasets keep one decimal');
  assert.strictEqual(X.out({ key: 'hpsa_mh_short', norm: 'value' }).d, 1, 'a count as published keeps its own decimals');
});

test('reliability: every table cell that is italic for a less reliable value also says so in words for a screen reader', () => {
  const src = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', 'js', f), 'utf8');
  for (const f of ['core/popup.js', 'economy.js', 'housing.js']) {
    const s = src(f), hits = [...s.matchAll(/unrel/g)].map(m => m.index);
    assert.ok(hits.length > 0, f);
    for (const i of hits) assert.ok(s.slice(i, i + 700).includes('lessReliable()'), `${f}: a cell with the unrel class has no hidden text near character ${i}`);
  }
});
test('reliability: the field of class limits uses a keypad that has a comma and a space', () => {
  const s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'core', 'panel.js'), 'utf8');
  assert.ok(s.includes('data-f="breaks"') && s.includes('inputmode="text"') && !s.includes('inputmode="decimal"'), 'a decimal keypad on a phone has no comma or space, and the limits need both');
});

test('engine: class limits with decimal points survive the trip through a link', () => {
  const L = E.makeLayer('poverty_pct', 'fill', { classes: 'manual', breaks: '1.79, 2.6, 3.47, 4.72' }, []), s = E.encode([L]);
  assert.ok(s.endsWith('.1.79~2.6~3.47~4.72'), s);
  const back = E.restore(s);
  assert.deepStrictEqual([back[0].classes, back[0].breaks], ['manual', '1.79, 2.6, 3.47, 4.72']);
  assert.strictEqual(E.encode(back), s, 'the same link comes back');
  const neg = E.restore('poverty_pct.f.value.blue.m.1.1.0.85.0.-1.5~0~2.25~10');
  assert.strictEqual(neg[0].breaks, '-1.5, 0, 2.25, 10');
  const two = E.restore('poverty_pct.f.value.blue.m.1.1.0.85.0.1.5~2~3~4.5,qcew_jobs.s.value.green.q.1.0.0.75.0');
  assert.deepStrictEqual(two.map(l => l.key), ['poverty_pct', 'qcew_jobs'], 'the layer after it is still read');
});
test('classify: natural breaks on fewer distinct values than classes fall back to quantiles instead of throwing', () => {
  for (const pool of [[1, 2, 2, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1], [5], [1, 2, 3], [0, 0, 0, 0, 0, 7, 9, 9, 9, 9]]) {
    const b = classify.make(pool, { method: 'jenks' });
    assert.strictEqual(b.edges.length, 6, JSON.stringify(pool));
    assert.ok(b.edges.every((x, i) => Number.isFinite(x) && (i === 0 || x >= b.edges[i - 1])), JSON.stringify(pool));
    assert.ok(pool.every(v => { const c = classify.classOf(b, v); return c >= 0 && c <= 4; }), 'every value has a class');
  }
  const many = Array.from({ length: 40 }, (_, i) => i * i);
  assert.strictEqual(classify.make(many, { method: 'jenks' }).edges.length, 6, 'enough distinct values: natural breaks as before');
});
test('adapters: the datasets that withhold small cells are the 19 industry job counts, named by key', () => {
  assert.deepStrictEqual(E.list().filter(v => v.withheld).map(v => v.key), E.list().filter(v => /^jobs_naics_/.test(v.key)).map(v => v.key));
  assert.strictEqual(E.list().filter(v => v.withheld).length, 19);
});
test('links: a broken percent escape is read without throwing, on every page that decodes a link', () => {
  for (const f of ['economy.js', 'network.js', 'dictionary.js', 'app.js']) {
    const s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', f), 'utf8');
    const bare = [...s.matchAll(/decodeURIComponent\(/g)].filter(m => { const before = s.slice(Math.max(0, m.index - 80), m.index); return !before.includes('const safeDecode') && !/try \{[^}]*$/.test(before); });
    assert.strictEqual(bare.length, 0, `${f}: every decode of a link is inside a try or goes through safeDecode`);
  }
});
test('engine: a link that names an object method as a dataset opens nothing', () => {
  const X = engine.create(); X.setGeo(['72001', '72'], ['Uno', 'Puerto Rico'], [10, 10]);
  assert.deepStrictEqual(X.decode('constructor.f.value.blue.q.1.1.0.85.0,toString.s.value.blue.q.1.1.0.75.0,__proto__.f.value.blue.q.1.1.0.85.0'), []);
  assert.deepStrictEqual(X.restore('constructor.f.value.blue.q.1.1.0.85.0'), []);
});

test('engine: a fresh engine starts with the year, the base year and the snapshot year the pages rely on', () => {
  const X = engine.create();   // not realEngine(): that one sets the base year itself, which hid a comment that had swallowed the defaults
  assert.deepStrictEqual([X.year, X.base, X.snapYear, X.cpiRef], [null, 2014, 2026, null]);
  assert.deepStrictEqual(Object.keys(X.denominators).sort(), ['hu', 'jobs', 'pop']);
  assert.strictEqual(Object.getPrototypeOf(X.V), null);
});

// ── the chat's correlation tool ─────────────────────────────────────────────────────────────────
// The real helpers and tools of site/js/chat.js (from "Data helpers" to "Chat messages": chVec, chTitle, chPearson, chNormFor, Tools), with no page. The engine behind chApi() is whatever a test hands
// to env.setApi: here a thin wrapper of a real engine, with the methods of ECON.api (economy.js) that these functions call.
function chatToolsEnv() {
  const s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8'), body = s.slice(s.indexOf('// ── Data helpers'), s.indexOf('// ── Chat messages'));
  const code = `let API = null; const chApi = () => API; const I18N = { lang: 'en' };\n${body}\nreturn { Tools, chTitle, chNormFor, chPearson, setApi: (a) => { API = a; } };`;
  return new Function('T', code)(core('text').T);
}
const apiOf = (X) => ({ values: (k, o) => X.values(k, o), defaultNorm: (k, mode = 'fill') => normalize.defaultNorm(X.V[k], mode), normOptions: (k) => normalize.options(X.V[k]), meta: (k) => X.V[k] || null, places: () => X.geo.names.slice() });
test('chat: a correlation with the resident population uses people per km² (per 1,000 residents it is 1,000 in every municipio), and the title line says which view each side used', () => {
  const sum = (a) => a.reduce((t, x) => t + x, 0), withPR = (a, pr = sum(a)) => [...a, pr];
  const pearson = (x, y) => { const mx = sum(x) / x.length, my = sum(y) / y.length; let xy = 0, xx = 0, yy = 0; x.forEach((v, i) => { xy += (v - mx) * (y[i] - my); xx += (v - mx) ** 2; yy += (y[i] - my) ** 2; }); return xy / Math.sqrt(xx * yy); };
  const names = Array.from({ length: 10 }, (_, i) => 'Muni ' + (i + 1));   // ten municipios and the island: chPearson wants at least eight places
  const pop = [1200, 54000, 8300, 129000, 23000, 310000, 4700, 67000, 15500, 41000], pov = [31.2, 44.5, 38.1, 22.9, 35, 28.4, 47.2, 25.1, 41.3, 33.8], est = [40, 900, 150, 3100, 410, 6800, 90, 1400, 260, 780];
  const X = engine.create(); X.setGeo(names.map((_, i) => '72' + String(i + 1).padStart(3, '0')).concat('72'), [...names, 'Puerto Rico'], withPR(names.map((_, i) => 10 + i * 7)));
  X.add({ key: 'population', label: 'Resident population', group: 'People', unit: '', d: 0, type: 'count', family: 'people', years: { 2024: withPR(pop.map(x => Math.round(x * .98))), 2025: withPR(pop) } });
  X.add({ key: 'poverty_pct', label: 'Population below the poverty level', group: 'Income and poverty', unit: '%', d: 1, type: 'rate', years: { 2024: withPR(pov, 36) } });
  X.add({ key: 'establishments', label: 'Establishments', group: 'Jobs and employers', unit: '', d: 0, type: 'count', years: { 2025: withPR(est) } });
  X.add({ key: 'sparse', label: 'Sparse count', group: 'Jobs and employers', unit: '', d: 0, type: 'count', years: { 2025: withPR([5, 9, 3, ...Array(7).fill(null)]) } });   // a value in three municipios only
  X.add({ key: 'same_rate', label: 'A rate that is the same everywhere', group: 'Income and poverty', unit: '%', d: 1, type: 'rate', years: { 2024: withPR(Array(10).fill(12), 12) } });
  const env = chatToolsEnv(); env.setApi(apiOf(X));
  // the cause: per 1,000 residents of the resident population is one number, so chPearson has nothing to work with; since 2026-11-05 the engine marks the population
  // denominator as the residents, so its shaded default is people per km² and per 1,000 residents is no longer offered (the map review's critical finding)
  const per1000 = X.values('population', { norm: 'per1000' }).values;
  assert.strictEqual(env.chNormFor('population'), 'perkm2');
  assert.ok(per1000.every(x => x === 1000), 'the resident population per 1,000 residents is 1,000 in every municipio');
  assert.strictEqual(env.chPearson(per1000, X.values('poverty_pct', { norm: 'value' }).values), null, 'no correlation can be computed from that view');
  // the population against a rate: a correlation, of people per km² (the map's view of the residents), never of a view that is one number everywhere
  const area = names.map((_, i) => 10 + i * 7), density = pop.map((x, i) => x / area[i]);
  const c = env.Tools.correlate({ a: 'population', b: 'poverty_pct' });
  assert.strictEqual(c.error, undefined, 'population with poverty is not "too few places with both values"');
  assert.deepStrictEqual([c.normA, c.normB, c.yearA, c.yearB, c.n], ['perkm2', 'value', 2025, 2024, 10]);
  assert.ok(Math.abs(c.r - pearson(density, pov)) < 1e-9, `r is that of people per km² with the rates: ${c.r}`);
  assert.deepStrictEqual([env.chTitle('population', c.normA, c.yearA), env.chTitle('poverty_pct', c.normB, c.yearB)], ['Resident population · per km² · 2025', 'Population below the poverty level · 2024']);
  // the other way round, and beside a count whose default view is fine: each side says its own view
  const back = env.Tools.correlate({ a: 'poverty_pct', b: 'population' });
  assert.deepStrictEqual([back.normA, back.normB, back.n], ['value', 'perkm2', 10]); assert.ok(Math.abs(back.r - c.r) < 1e-12);
  const m = env.Tools.correlate({ a: 'population', b: 'establishments' });
  assert.deepStrictEqual([m.normA, m.normB], ['perkm2', 'per1000']);
  assert.deepStrictEqual([env.chTitle('population', m.normA, m.yearA), env.chTitle('establishments', m.normB, m.yearB)], ['Resident population · per km² · 2025', 'Establishments · per 1,000 residents · 2025']);
  // nothing else moves: a default view that tells places apart is kept, and the errors of a pair with too few places or no spread are as they were
  const u = env.Tools.correlate({ a: 'establishments', b: 'poverty_pct' });
  assert.deepStrictEqual([u.normA, u.normB], ['per1000', 'value']);
  assert.ok(Math.abs(u.r - pearson(est.map((x, i) => x / pop[i] * 1000), pov)) < 1e-4, `r of the counts per 1,000 residents: ${u.r}`);
  assert.deepStrictEqual(env.Tools.correlate({ a: 'sparse', b: 'poverty_pct' }), { error: 'too few places with both values' }, 'three municipios are too few, and the published value does not change that');
  assert.deepStrictEqual(env.Tools.correlate({ a: 'same_rate', b: 'poverty_pct' }), { error: 'too few places with both values' }, 'a rate that is the same everywhere has nothing to correlate');
});

// ── what the dictionary says about the Economy tab's dataset list ───────────────────────────────
function tabEngine() {   // the datasets the Economy tab holds once ecLoad() has run: the files of js/core/datasets.js, added in its order (the area profiles use the same list)
  const X = engine.create(), muni = readData('municipalities.json'), meta = readData('meta.json'), docs = {};
  for (const f of datasets.FILES) docs[f.name] = readData(f.file);
  datasets.apply(X, docs, muni, +((meta.generated_at || '').slice(0, 4)) || 2026);
  return X;
}
const dictEntries = (() => {
  const dir = path.join(__dirname, '..', 'dictionary_src', 'entries'), out = {};
  for (const f of fs.readdirSync(dir).filter(n => n.endsWith('.json'))) for (const e of JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'))) out[e.id] = e;
  return out;
})();
test('the Economy tab and the area profiles load the datasets of js/core/datasets.js (when it changes, change the dictionary numbers below)', () => {
  const src = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', 'js', f), 'utf8');
  const eco = src('economy.js'), body = eco.slice(eco.indexOf('async function ecLoad()'), eco.indexOf('function ecAdd('));
  assert.match(body, /Core\.datasets\.fetchFiles\(Data\.json\), lab\]\)/, 'every dataset file, fetched alongside the Spanish of the terrain and climate groups (econ_terrain)');
  assert.match(body, /Core\.datasets\.apply\(E, docs, S\.muni,/, 'then added in the order of datasets.js');
  assert.match(body, /I18N\.load\('econ_terrain'\)\.catch\(\(\) => null\)/, 'a module that does not load leaves the names in English, not the tab broken');
  assert.doesNotMatch(body, /Core\.adapters\./, 'the tab adds no dataset of its own');
  assert.match(src('profile.js'), /Core\.datasets\.fetchFiles\(getJson, FIRST\)/, 'the profile fetches the files of its first field first (tests/profile_first.test.js)');
  assert.match(src('profile.js'), /Core\.datasets\.apply\(X, \{ \.\.\.P\.docs, \.\.\.rest\.docs \}, P\.muni, P\.year\)/, 'then every file, in the order of datasets.js');
  const ds = src('core/datasets.js'), applyBody = ds.slice(ds.indexOf('function apply('), ds.indexOf('async function load('));
  assert.deepStrictEqual([...applyBody.matchAll(/A\.(\w+)\(E,/g)].map(m => m[1]), ['series',  'tourism',  'snapshot',  'exposure',  'seriesFile',  'seriesFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'seriesFile',  'snapshotFile',  'seriesFile',  'seriesFile',  'seriesFile',  'snapshotFile',  'seriesFile',  'seriesFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'snapshotFile',  'levelFile']);
  for (const f of datasets.FILES) assert.ok(fs.existsSync(path.join(__dirname, '..', 'site', 'data', f.file)), f.file);
});
test('dictionary: the numbers it gives for the Economy tab (datasets, yearly series, one-year datasets, groups, margins of error) are the tab\'s', () => {
  const X = tabEngine(), vs = X.list(), n = vs.length, once = vs.filter(v => v.static).length, withMoe = vs.filter(v => v.moe).length;
  const groups = new Map();
  for (const v of vs) groups.set(v.group, (groups.get(v.group) || 0) + 1);
  const econ = readData('economy_series.json').vars.length;
  const tab = dictEntries['layers.economy_tab'].definition;
  assert.deepStrictEqual(tab.match(/the tab lists (\d+) datasets: (\d+) yearly series .*? and (\d+) counts and shares for a single year/).slice(1).map(Number), [n, n - once, once], 'layers.economy_tab: datasets, yearly series, one-year datasets');
  assert.deepStrictEqual(tab.match(/Of the (\d+) series, (\d+) are listed in the economy file .*? and (\d+) more come from/).slice(1).map(Number), [n - once, econ, n - once - econ], 'layers.economy_tab: the economy file and the Housing page');
  const list = dictEntries['layers.economy_datasets'];
  assert.strictEqual(+list.definition.match(/the list has (\d+) groups/)[1], groups.size, 'layers.economy_datasets: groups');
  assert.deepStrictEqual(Object.keys(list.values).sort(), [...groups.keys()].sort(), 'layers.economy_datasets: the groups it lists');
  for (const [g, c] of groups) assert.strictEqual(+list.values[g].match(/^(\d+) datasets?\b/)[1], c, `layers.economy_datasets: ${g}`);
  const chat = dictEntries['layers.chat'];
  assert.strictEqual(+chat.definition.match(/\((\d+) in Snapshot/)[1], n, 'layers.chat: definition');
  assert.strictEqual(+chat.values['What it can answer'].match(/\((\d+) in Snapshot/)[1], n, 'layers.chat: what it can answer');
  assert.deepStrictEqual(dictEntries['measures.margin_of_error'].how_to_read.match(/(\d+) of the (\d+) Analysis tab datasets have margins/).slice(1).map(Number), [withMoe, n], 'measures.margin_of_error');
});

test('WCRP vulnerability (wcrp_rvi_barrio.json): barrio-only datasets that start by barrio, with no municipio value, no CSV by area, and left out of the profiles and the 3D view', async () => {
  const X = tabEngine(), keys = Object.keys(X.V).filter(k => /^rvi_/.test(k));
  assert.strictEqual(keys.length, 14, 'seven indices in two versions');
  for (const k of keys) {
    const v = X.V[k];
    assert.ok(v.level === 'barrio' && v.fifths && v.noIsland, k);
    assert.ok(Object.values(v.years).every(a => a.every(x => x == null)), `${k}: no municipio and no island value`);
    assert.strictEqual(X.makeLayer(k, 'fill').level, 'barrio', `${k}: a shaded layer starts by barrio`);
    assert.deepStrictEqual(adapters.levelsFor(v, ['barrio']), [], `${k}: the CSV by area is for the survey's own barrio files`);
  }
  const s = X.series({ key: 'rvi_overall_orig' }, null, 'barrio'), ids = readData('barrios.geojson').features.map(f => f.properties.geoid).sort();
  assert.deepStrictEqual(s.ids, ids, 'the 901 barrios of barrios.geojson');
  assert.strictEqual(s.values.filter(x => x != null).length, 887, 'the 14 barrios with no residents have no value');
  assert.strictEqual(X.series({ key: 'rvi_overall_orig', norm: 'pctile' }, null, 'barrio').meta.norm, 'pctile');
  assert.strictEqual(X.makeLayer('poverty_pct', 'fill').level, undefined, 'other datasets still start by municipio');
  assert.ok(X.restore('rvi_econ_rebuild.f.value.red.q.1.0.0.85.0')[0].level === 'barrio', 'an older link with a municipio map opens by barrio');
  const docs = Object.fromEntries(datasets.FILES.map(f => [f.file, readData(f.file)])), muni = readData('municipalities.json');
  const asked = [], Y = engine.create();
  await datasets.load(Y, (p) => { asked.push(p); return Promise.resolve(docs[p.replace('data/', '')]); }, muni, 2026, ['wcrp']);
  assert.ok(!asked.includes('data/wcrp_rvi_barrio.json') && !Y.V.rvi_overall_orig && Y.V.poverty_pct, 'skip: the file is not fetched');
  const src = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', 'js', f), 'utf8');
  assert.match(src('twin3d.js'), /Core\.datasets\.load\([^;]*, \['wcrp'\]\)/, 'twin3d.js skips the barrio-only file');
  const prof = src('profile.js'), first = JSON.parse(prof.match(/const FIRST = (\[[^\]]*\]);/)[1].replace(/'/g, '"'));   // the profile fetches FIRST, then the rest less LEFT_OUT
  assert.match(prof, /const LEFT_OUT = \['wcrp'\];/, 'profile.js leaves the barrio-only file out');
  assert.match(prof, /fetchFiles\(getJson, Core\.datasets\.FILES\.map\(f => f\.name\)\.filter\(n => !FIRST\.includes\(n\) && !LEFT_OUT\.includes\(n\)\)\)/, 'profile.js: the later files leave it out');
  assert.ok(!first.includes('wcrp'), 'profile.js: not among the first files');
});

// ── a series file with windows, and the finer levels of a dataset (plan item 7) ──
const tinyEngine = () => { const X = engine.create(); X.setGeo(['72001', '72003', '72005', '72'], ['Uno', 'Dos', 'Tres', 'Puerto Rico'], [10, 20, 30, 60]); return X; };
const tinyDoc = () => ({ built: '2026-10-06', years: [2023, 2024], geo: { ids: ['72003', '72', '72001', '72005'] }, vars: [{ key: 'acs_x', group: 'Population and age', label: 'X', unit: '%', d: 1, type: 'rate', sources: ['acs'], ref: 'ACS', definition: 'd', family: 'population',
  years: { 2023: [2, 6, 1, null], 2024: [3, 7, 2, 4] }, moe: { 2023: [.2, .6, .1, null], 2024: [.3, .7, .2, .4] } }] });
test('seriesFile: arrays are put in the order of the engine places, a survey series is a window and a gap stays a gap', () => {
  const X = tinyEngine(); adapters.seriesFile(X, tinyDoc(), { dict: 'population.', group: 'Population · ' });
  const v = X.V.acs_x;
  assert.deepStrictEqual(v.years[2024], [2, 3, 4, 7]);
  assert.deepStrictEqual(v.years[2023], [1, 2, null, 6], 'no estimate stays no value, not a zero');
  assert.deepStrictEqual(v.moe[2024], [.2, .3, .4, .7]);
  assert.deepStrictEqual(v.ys, [2023, 2024]);
  assert.deepStrictEqual(v.time, { type: 'window', windowYears: 5 });
  assert.strictEqual(v.group, 'Population · Population and age');
  assert.strictEqual(v.dictId, 'population.acs_x');
  assert.strictEqual(v.built, '2026-10-06');
  assert.strictEqual(X.chip({ key: 'acs_x' }, { y: 2024, exact: true }), '2020–2024');
  const s = X.series({ key: 'acs_x' }, 2024);
  assert.deepStrictEqual([s.values, s.moe[3], s.meta.timeType], [[2, 3, 4, 7], .7, 'window']);
});
test('levelFile: an area empty for a reason of its own (noValueWhy) says so; the others keep the noValue of the dataset', () => {
  const X = tinyEngine(); adapters.seriesFile(X, tinyDoc());
  adapters.levelFile(X, { level: 'barrio', geo: { ids: ['b1', 'b2', 'b3', 'b4'] }, vars: [{ key: 'acs_x', noValueWhy: [{ why: 'No residents in 2020', ids: ['b3'] }], years: { 2024: [2, null, null, 4] } }] });
  const s = X.series({ key: 'acs_x' }, 2024, 'barrio');
  assert.deepStrictEqual([s.flags.noValue, s.flags.why], [[false, true, true, false], [null, null, 'No residents in 2020', null]], 'b2 has no reason of its own, b3 has one');
  adapters.levelFile(X, { level: 'tract', geo: { ids: ['t1'] }, vars: [{ key: 'acs_x', years: { 2024: [1] } }] });
  assert.strictEqual(X.series({ key: 'acs_x' }, 2024, 'tract').flags.why, null, 'no reasons, no array');
});
test('levelFile: a level of an existing dataset answers the contract with margins, windows and flags, and leaves the municipal values alone', () => {
  const X = tinyEngine(); adapters.seriesFile(X, tinyDoc());
  const names = [{ es: 'Sector 1', en: 'Tract 1' }, { es: 'Sector 2', en: 'Tract 2' }, { es: 'Sector 3', en: 'Tract 3' }];
  adapters.levelFile(X, { level: 'tract', windows: [2023, 2024], geo: { ids: ['t1', 't2', 't3'] }, vars: [
    { key: 'acs_x', years: { 2023: [1, null, 3], 2024: [2, 5, 4] }, moe: { 2023: [.1, null, .3], 2024: [.2, .5, .4] } }, { key: 'not_a_dataset', years: { 2024: [1, 2, 3] }, moe: { 2024: [0, 0, 0] } }] }, { names });
  const s = X.series({ key: 'acs_x' }, 2024, 'tract');
  assert.deepStrictEqual([s.ids, s.values, s.moe, s.names], [['t1', 't2', 't3'], [2, 5, 4], [.2, .5, .4], names]);
  assert.deepStrictEqual([s.flags.exact, s.flags.early, s.flags.noValue, s.meta.level, s.meta.period, s.meta.unit, s.meta.decimals, s.meta.norm], [true, false, [false, false, false], 'tract', 2024, '%', 1, 'value']);
  const early = X.series({ key: 'acs_x' }, 2010, 'tract'), late = X.series({ key: 'acs_x' }, 2030, 'tract'), now = X.series({ key: 'acs_x' }, null, 'tract');
  assert.deepStrictEqual([early.meta.period, early.flags.early, early.flags.exact, early.values], [2023, true, false, [1, null, 3]], 'before the first window: the first, flagged');
  assert.deepStrictEqual([late.meta.period, late.flags.early, late.flags.exact], [2024, false, false], 'after the last window: the last, not exact');
  assert.strictEqual(now.meta.period, 2024);
  assert.deepStrictEqual(X.series({ key: 'acs_x' }, 2023, 'tract').flags.noValue, [false, true, false], 'a tract the Census Bureau gives no estimate for has no value');
  const p = X.series({ key: 'acs_x', norm: 'pctile' }, 2024, 'tract');
  assert.deepStrictEqual([p.values, p.moe, p.meta.norm], [[0, 100, 50], null, 'pctile'], 'the percentile among the areas of the level; a margin is not carried through');
  assert.strictEqual(X.series({ key: 'acs_x', norm: 'per1000' }, 2024, 'tract').meta.norm, 'value', 'a rescaling that needs the residents of each area is not offered: as published');
  assert.strictEqual(X.series({ key: 'acs_x' }, 2024, 'barrio'), null, 'a level the dataset does not have');
  assert.strictEqual(X.V.not_a_dataset, undefined, 'a variable of the file that is no dataset is skipped');
  assert.deepStrictEqual(X.values('acs_x', { year: 2024 }).values, [2, 3, 4, 7], 'the municipal values are untouched');
  adapters.levelFile(X, { level: 'barrio', geo: { ids: ['b1'] }, vars: [{ key: 'acs_x', years: { 2024: [9] }, moe: { 2024: [1] } }] });
  assert.ok(X.series({ key: 'acs_x' }, 2024, 'barrio') && X.series({ key: 'acs_x' }, 2024, 'tract'), 'a second level does not replace the first');
});
test('levelTable: the CSV by area marks the less reliable values and says why a margin is blank, and a count of 100 is not a share', () => {
  const X = tinyEngine(), doc = tinyDoc();
  doc.vars.push({ ...doc.vars[0], key: 'acs_n', label: 'N', unit: '', type: 'count', years: { 2023: [1, 1, 1, 1], 2024: [2, 2, 2, 2] }, moe: { 2023: [0, 0, 0, 0], 2024: [0, 0, 0, 0] } });
  adapters.seriesFile(X, doc);
  const names = ['Uno', 'Dos', 'Tres', 'Cuatro'].map((n, i) => ({ es: `Sector ${i + 1}`, en: `Tract ${i + 1}` }));
  adapters.levelFile(X, { level: 'tract', windows: [2023, 2024], geo: { ids: ['72001a', '72003b', '72005c', '72001d'] }, vars: [
    { key: 'acs_x', years: { 2023: [10, 100, 50, null], 2024: [20, 100, 50, 7] }, moe: { 2023: [1, null, 5, null], 2024: [9, null, 5, 3] } },
    { key: 'acs_n', years: { 2023: [100, 100, 5, 5], 2024: [100, 100, 5, 5] }, moe: { 2023: [null, null, 1, 1], 2024: [null, null, 1, 1] } }] }, { names });
  const it = adapters.levelTable(X, 'acs_x', 'tract', { name: (n) => n && n.es, municipality: (id) => ({ '72001': 'Uno', '72003': 'Dos', '72005': 'Tres' })[id.slice(0, 5)] });
  assert.deepStrictEqual(it.header, ['GEOID', 'Area', 'Municipality', '2019–2023', '2019–2023 margin of error', '2019–2023 less reliable', '2020–2024', '2020–2024 margin of error', '2020–2024 less reliable', 'Variable', 'Unit', 'Dictionary entry', 'Source', 'Note']);
  const src = 'US Census Bureau, American Community Survey 5-year estimates; margins of error at 90% confidence; neighboring windows share four of their five years', why = it.rows[1][13];
  assert.ok(/blank margin of error means that none is published/.test(why));
  assert.deepStrictEqual(it.rows[0], ['72001a', 'Sector 1', 'Uno', 10, 1, '', 20, 9, 'yes', 'X', 'percent', 'acs_x', src, ''], 'a margin above 30% of the estimate marks the window; the other window is not marked');
  assert.deepStrictEqual(it.rows[1], ['72003b', 'Sector 2', 'Dos', 100, null, 'yes', 100, null, 'yes', 'X', 'percent', 'acs_x', src, why], 'a share of exactly 100% has no margin: it is marked, and the note says why the margin is blank');
  assert.deepStrictEqual(it.rows[2], ['72005c', 'Sector 3', 'Tres', 50, 5, '', 50, 5, '', 'X', 'percent', 'acs_x', src, ''], 'a margin of 10% of the estimate is not marked');
  assert.deepStrictEqual(it.rows[3], ['72001d', 'Sector 4', 'Uno', null, null, '', 7, 3, 'yes', 'X', 'percent', 'acs_x', src, ''], 'no estimate is blank, not zero, and needs no note; 3 of 7 is above 30%');
  const ct = adapters.levelTable(X, 'acs_n', 'tract');
  assert.deepStrictEqual(ct.rows[0].slice(3, 6), [100, null, ''], 'a count of 100 with no margin is not a share of 100%: not marked');
  assert.strictEqual(ct.rows[0][ct.rows[0].length - 1], why, 'but its blank margin is explained');
  assert.deepStrictEqual(ct.rows[0].slice(-4, -2), ['count', 'acs_n'], 'a count says so, and where its entry is');
  assert.strictEqual(adapters.levelTable(X, 'acs_x', 'barrio'), null, 'a level the dataset does not have');
  assert.strictEqual(adapters.levelTable(X, 'not_a_dataset', 'tract'), null);
});
const haveData = (...f) => f.every(x => fs.existsSync(path.join(__dirname, '..', 'site', 'data', x)));
test('landslide by barrio: only the 15 barrios the map does not cover are "not mapped"; the 3 with no residents in 2020 say so', { skip: !haveData('landslide_series.json', 'landslide_barrio.json') }, () => {
  const X = realEngine(); adapters.snapshotFile(X, readData('landslide_series.json'), { dict: 'landslide.' }); adapters.levelFile(X, readData('landslide_barrio.json'), { level: 'barrio' });
  const s = X.series({ key: 'ls_res_high_pct' }, null, 'barrio'), empty = s.values.filter(x => x == null).length, own = s.flags.why.filter(Boolean);
  assert.deepStrictEqual([empty, own.length, empty - own.length, [...new Set(own)]], [18, 3, 15, ['No residents in 2020']]);
  const land = X.series({ key: 'ls_land_high_pct' }, null, 'barrio');
  assert.deepStrictEqual([land.values.filter(x => x == null).length, land.flags.why], [15, null], 'land: the 15 not mapped, no other reason');
});
test('a yearly barrio file of its own (FCC broadband, night lights) is a year, not a five-year survey window: no margin of error, and the barrio legend says so', { skip: !haveData('broadband_series.json', 'broadband_barrio.json', 'nightlights_series.json', 'nightlights_barrio.json') }, () => {
  const X = realEngine();
  for (const [name, key] of [['broadband', 'bb_served_pct'], ['nightlights', 'ntl_radiance']]) {
    const doc = readData(name + '_series.json'), bar = readData(name + '_barrio.json');
    adapters.seriesFile(X, doc, { dict: name + '.', group: '' }); adapters.levelFile(X, bar, { level: 'barrio' });
    assert.ok(!X.V[key].time, `${key}: no survey window at the municipio`);
    const last = Math.max(...Object.keys(bar.vars.find(v => v.key === key).years).map(Number)), s = X.series({ key }, null, 'barrio');
    assert.deepStrictEqual([s.meta.timeType, s.meta.period, s.moe, s.flags.exact], ['period', last, null, true], `${key}: a year with no margin`);
    assert.strictEqual(X.series({ key }, last - 1, 'barrio').meta.period, last - 1, `${key}: each year is its own`);
  }
  const lv = { level: 'barrio', geo: { ids: ['b1'] }, vars: [{ key: 'acs_x', years: { 2024: [9] }, moe: { 2024: [1] } }] }, Y = tinyEngine(); adapters.seriesFile(Y, tinyDoc());
  adapters.levelFile(Y, lv); assert.strictEqual(Y.series({ key: 'acs_x' }, null, 'barrio').meta.timeType, 'window', 'a survey dataset stays a window');
  const el = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'econ_level.js'), 'utf8');
  assert.match(el, /const tt = r\.s\.meta\.timeType, win = tt === 'window'/, 'the barrio legend reads the period type from the contract, not from a missing time');
  assert.doesNotMatch(el, /!v\.time \|\| v\.time\.type === 'window'/, 'a dataset with no time is not taken for the survey');
});
test('storm recovery: the two storm years read by municipio and by barrio, each its own year, and a dim barrio has no value', { skip: !haveData('storm_recovery_series.json', 'storm_recovery_barrio.json') }, () => {
  const X = realEngine(), doc = readData('storm_recovery_series.json'), bar = readData('storm_recovery_barrio.json');
  adapters.seriesFile(X, doc, { dict: 'storm_recovery.', group: '' }); adapters.levelFile(X, bar, { level: 'barrio' });
  for (const y of [2017, 2022]) {
    const s = X.series({ key: 'storm_months_back' }, y, 'barrio'), raw = bar.vars.find(v => v.key === 'storm_months_back').years[y];
    assert.deepStrictEqual([s.meta.period, s.moe, s.values.filter(x => x == null).length], [y, null, raw.filter(x => x == null).length], `${y}: its own year, no margin, the dim barrios empty`);
  }
  assert.strictEqual(X.V.storm_months_back.dictId, 'storm_recovery.storm_months_back');
});
test('essentials: seven road-distance estimates by municipio and barrio, shaded as distances (not per 1,000 residents), any food store never farther than a supermarket', { skip: !haveData('essentials_series.json', 'essentials_barrio.json') }, () => {
  const X = realEngine(), doc = readData('essentials_series.json'), bar = readData('essentials_barrio.json'), y = doc.years[0];
  adapters.seriesFile(X, doc, { dict: 'essentials.', group: '' }); adapters.levelFile(X, bar, { level: 'barrio' });
  assert.strictEqual(doc.vars.length, 7);
  for (const v of doc.vars) {
    assert.ok(/\(estimate, (km|%)\)$/.test(v.label), v.key + ': the word estimate in its name');
    assert.strictEqual(normalize.defaultNorm(X.V[v.key], 'fill'), 'value', v.key + ': a distance or a share is shaded as it is');
    assert.strictEqual(X.series({ key: v.key }, y, 'barrio').values.length, bar.geo.ids.length);
  }
  const sup = X.series({ key: 'ess_supermarket_km' }, y, 'barrio').values, gro = X.series({ key: 'ess_grocery_km' }, y, 'barrio').values;
  assert.ok(sup.every((s, i) => s == null || gro[i] == null || gro[i] <= s + 1e-9), 'a supermarket is a food store, so the nearest food store is never farther');
  assert.strictEqual(X.V.ess_pharmacy_km.dictId, 'essentials.ess_pharmacy_km');
});
test('cut off from hospitals: five estimates by municipio and barrio, shares shaded as they are, dry streets and bridges never more than the whole', { skip: !haveData('cutoff_series.json', 'cutoff_barrio.json') }, () => {
  const X = realEngine(), doc = readData('cutoff_series.json'), bar = readData('cutoff_barrio.json'), y = doc.years[0];
  adapters.seriesFile(X, doc, { dict: 'cutoff.', group: '' }); adapters.levelFile(X, bar, { level: 'barrio' });
  assert.strictEqual(doc.vars.length, 5);
  for (const v of doc.vars) {
    assert.ok(/\(estimate(, %)?\)$/.test(v.label), v.key + ': the word estimate in its name');
    if (v.unit === '%') assert.strictEqual(normalize.defaultNorm(X.V[v.key], 'fill'), 'value', v.key + ': a share is shaded as it is');
    assert.strictEqual(X.series({ key: v.key }, y, 'barrio').values.length, bar.geo.ids.length);
  }
  const all = X.series({ key: 'cut_flood_pct' }, y, 'barrio').values, dry = X.series({ key: 'cut_flood_dry_pct' }, y, 'barrio').values, both = X.series({ key: 'cut_both_pct' }, y, 'barrio').values;
  assert.ok(all.every((a, i) => a == null || dry[i] <= a + 1e-9), 'the residents on dry streets are some of those cut off');
  assert.ok(all.every((a, i) => a == null || both[i] >= a - 1e-9), 'closing the poor bridges too never reconnects anyone');
  assert.strictEqual(X.V.cut_flood_pct.dictId, 'cutoff.cut_flood_pct');
});
test('jobs within reach: four estimates by municipio, shaded as they are, more jobs within 45 minutes than within 30', { skip: !haveData('jobs_reach_series.json') }, () => {
  const X = realEngine(), doc = readData('jobs_reach_series.json'), y = doc.years[0];
  adapters.seriesFile(X, doc, { dict: 'jobs_reach.', group: '' });
  assert.strictEqual(doc.vars.length, 4);
  for (const v of doc.vars) {
    assert.ok(/\(estimate(, %)?\)$/.test(v.label), v.key + ': the word estimate in its name');
    assert.strictEqual(normalize.defaultNorm(X.V[v.key], 'fill'), 'value', v.key + ': an average or a share is shaded as it is');
  }
  const a = X.series({ key: 'jobs_reach_30' }, y).values, b = X.series({ key: 'jobs_reach_45' }, y).values;
  assert.ok(a.every((x, i) => x == null || b[i] >= x), 'what is within 30 minutes is within 45');
  assert.strictEqual(X.V.jobs_reach_30.dictId, 'jobs_reach.jobs_reach_30');
});
test('net migration by age: six rates and a count by municipio, shaded as they are, the young left the most', { skip: !haveData('netmig_age_series.json') }, () => {
  const X = realEngine(), doc = readData('netmig_age_series.json'), y = doc.years[0];
  adapters.seriesFile(X, doc, { dict: 'netmig_age.', group: '' });
  assert.strictEqual(doc.vars.length, 7);
  for (const v of doc.vars) assert.ok(/\(estimate, (% of expected|people)\)$/.test(v.label), v.key + ': the word estimate in its name');
  assert.strictEqual(normalize.defaultNorm(X.V.netmig_20_29_pct, 'fill'), 'value', 'a rate is shaded as it is');
  const pr = (k) => X.series({ key: k }, y).values.slice(-1)[0];
  assert.ok(pr('netmig_20_29_pct') < pr('netmig_65_plus_pct'), 'the island lost more of its young adults than of its elders');
  assert.strictEqual(X.V.netmig_10_plus_pct.dictId, 'netmig_age.netmig_10_plus_pct');
});
test('levelTable on the real tract and barrio files: a row for each area, three columns for each window, the marks as the rule gives them', { skip: !haveData('population_series.json', 'acs_tract.json', 'acs_barrio.json') }, () => {
  const X = realEngine(); adapters.seriesFile(X, readData('population_series.json'), { dict: 'population.', group: 'Population · ' });
  for (const [file, level] of [['acs_tract.json', 'tract'], ['acs_barrio.json', 'barrio']]) {
    const doc = readData(file); adapters.levelFile(X, doc, { level });
    for (const key of ['acs_under18_pct', 'acs_female_pct', 'median_hh_income', 'acs_population']) {
      const t = adapters.levelTable(X, key, level), v = doc.vars.find(x => x.key === key), ys = Object.keys(v.years).sort(), share = X.V[key].unit === '%';
      assert.strictEqual(t.rows.length, doc.geo.ids.length, `${level} ${key}: a row for each area`);
      assert.strictEqual(t.header.length, 3 + ys.length * 3 + 5, `${level} ${key}: GEOID, area, municipality, three columns for each window, variable, unit, dictionary entry, source, note`);
      const meta = X.V[key], unitCell = t.rows[0][t.rows[0].length - 4];
      assert.strictEqual(unitCell, meta.unit === '%' ? 'percent' : meta.unit === '$' ? 'US dollars of the last year of each window' : 'people', `${level} ${key}: the unit`);
      assert.strictEqual(t.rows[0][t.rows[0].length - 3], meta.dictId, `${level} ${key}: the dictionary entry`);
      let marked = 0, blank = 0;
      t.rows.forEach((r, i) => {
        assert.strictEqual(r[0], doc.geo.ids[i]);
        let noMargin = false;
        ys.forEach((y, w) => {
          const x = v.years[y][i], m = v.moe[y][i], rough = x != null && ((m != null && m > 0 && (x === 0 || m / Math.abs(x) > 0.3)) || (share && x === 100 && m == null));
          assert.strictEqual(r[3 + w * 3], x ?? null); assert.strictEqual(r[4 + w * 3], m ?? null); assert.strictEqual(r[5 + w * 3], rough ? 'yes' : '', `${level} ${key} ${doc.geo.ids[i]} ${y}`);
          if (rough) marked++;
          if (x != null && m == null) noMargin = true;
        });
        assert.strictEqual(r[r.length - 1] !== '', noMargin, `${level} ${key} ${doc.geo.ids[i]}: the note is there when a value has no margin`);
        if (noMargin) blank++;
      });
      assert.ok(marked > 0, `${level} ${key}: some values are marked less reliable`);
      if (key === 'acs_population' && level === 'barrio') assert.ok(blank >= 1, 'Florida Adentro, the one barrio whose population the Census Bureau controls, has a blank margin and a note');
    }
  }
});
test('population series and the levels below the municipio, on the real files', { skip: !haveData('population_series.json', 'acs_barrio.json', 'acs_tract.json', 'acs_blockgroup.json') }, () => {
  const X = realEngine(), pop = readData('population_series.json');
  adapters.seriesFile(X, pop, { dict: 'population.', group: 'Population · ' });
  const mine = X.list().filter(v => v.family === 'population');
  assert.strictEqual(mine.length, 30);   // 10, the shares of seven age groups and the counts of nine since 2026-10-18; English ability, nutrition assistance and poverty by age since 2026-11-14
  assert.deepStrictEqual(mine.filter(v => v.residents).map(v => v.key), ['acs_population'], 'only the count of residents starts as density');
  assert.ok(mine.every(v => v.time && v.time.type === 'window' && v.moe && v.dictId === 'population.' + v.key && v.years[pop.years[0]].length === 79));
  assert.deepStrictEqual(X.V.acs_population.years[pop.years.at(-1)].at(-1), pop.vars.find(v => v.key === 'acs_population').years[pop.years.at(-1)].at(-1), 'Puerto Rico is last');
  for (const [level, file] of [['barrio', 'acs_barrio.json'], ['tract', 'acs_tract.json'], ['block-group', 'acs_blockgroup.json']]) {
    const doc = readData(file); adapters.levelFile(X, doc);
    const withLevel = X.list().filter(v => v.levels && v.levels[level]).map(v => v.key), want = doc.vars.map(v => v.key);
    assert.deepStrictEqual(withLevel.sort(), want.slice().sort(), `${level}: every variable of the file is a level of a dataset that exists`);
    const hu = X.series({ key: 'housing_units' }, doc.windows.at(-1), level), mun = X.values('housing_units', { year: doc.windows.at(-1) }).values, sums = new Map();
    hu.ids.forEach((id, i) => { if (hu.values[i] != null) sums.set(id.slice(0, 5), (sums.get(id.slice(0, 5)) || 0) + hu.values[i]); });
    assert.ok(X.geo.ids.slice(0, 78).every((id, i) => Math.abs((sums.get(id) || 0) - mun[i]) < 0.5), `${level}: housing units add up to the municipio`);
  }
});

test('area buttons: a dataset is offered a level only when the level file holds it, and every level a file holds is offered', { skip: !haveData('population_series.json', 'acs_barrio.json', 'acs_tract.json', 'acs_blockgroup.json', 'catalog_index.json', 'exposure_municipio.json') }, () => {
  const X = realEngine(), muni = readData('municipalities.json');
  adapters.snapshot(X, muni, X.snapYear); adapters.exposure(X, { municipio: readData('exposure_municipio.json') });
  adapters.seriesFile(X, readData('population_series.json'), { dict: 'population.', group: 'Population · ' });
  let held = 0;
  for (const file of ['acs_barrio.json', 'acs_tract.json', 'acs_blockgroup.json']) { const doc = readData(file); adapters.levelFile(X, doc); held += doc.vars.length; }
  const cat = readData('catalog_index.json'), F = cat.index.fields, levelsOfEntry = new Map(cat.index.rows.map(r => [r[F.indexOf('id')], r[F.indexOf('levels')]]));
  assert.ok(X.list().some(v => /^exp_/.test(v.key) && (levelsOfEntry.get(X.dictId(v.key)) || []).includes('tract')), 'the dictionary lists the exposure datasets at tract level: the case this test is about');
  let offeredCount = 0;
  for (const v of X.list()) {
    const offered = adapters.levelsFor(v, levelsOfEntry.get(X.dictId(v.key)) || []);
    for (const l of offered) assert.ok(v.levels && v.levels[l], `${v.key}: offered ${l} but the level file has no values for it`);
    for (const l of ['barrio', 'tract', 'block-group']) if (v.levels && v.levels[l]) assert.ok(offered.includes(l), `${v.key}: has ${l} values but is not offered the button`);
    offeredCount += offered.length;
  }
  assert.strictEqual(offeredCount, held, 'one button for each variable of each level file');
});

// ── the chat's lexicon and parser, on the rules of the Population series ──
// The real functions of site/js/chat.js (concepts, qualifiers, language, intent, parse and the notes), with no page and no datasets unless a test hands them over (env.setApi).
function chatEnv() {
  const s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8'), at = s.indexOf('const CONCEPTS = [');
  const concepts = s.slice(at, s.indexOf('\n];', at) + 3), mid = s.slice(s.indexOf('const STOP'), s.indexOf('function chFuzzy')), intent = s.slice(s.indexOf('function chIntent'), s.indexOf('// ── Data helpers'));
  const norm = (x) => (x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();   // common.js
  const esc = (x) => x == null ? '' : String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');   // common.js
  const code = `let API = null; const chApi = () => API; const I18N = { lang: 'en' }; const CH = { lastLang: null, ui: 'en', ctx: { keys: [], year: null, muni: null } }; const CH_CONTEXT = [];\n${concepts}\n${mid}\n${intent}\n`
    + 'return { chParse, chConcepts, chRankNotes, chWindowNote, chDroppedNote, chMoeNote, chMoeText, chAsksRelation, chBlank, CH, setApi: (a) => { API = a; } };';
  const env = new Function('norm', 'esc', 'fmt', 'T', code)(norm, esc, (n) => String(n), (x) => x);
  const keys = (q) => env.chConcepts(norm(q)).keys;
  keys.full = (q) => env.chConcepts(norm(q)); keys.parse = env.chParse; keys.env = env;
  return keys;
}
const chatConcepts = chatEnv;
test('chat: the generated lexicon (plan item 14) finds the datasets the rules do not name, from their names and the words of their dictionary entries', () => {
  const env = chatEnv().env, X = tabEngine(), cat = readData('catalog_index.json'), F = cat.index.fields;
  env.setApi({ datasets: () => X.info(), meta: (k) => X.V[k] || null, dictId: (k) => X.dictId(k), places: () => X.geo.names.slice() });
  env.CH.ask = {}; cat.index.rows.forEach(r => { if (r[F.indexOf('ask')]) env.CH.ask[r[F.indexOf('id')]] = r[F.indexOf('ask')]; });
  const p = (q) => env.chParse(q);
  for (const [q, keys, intent] of [
    ['¿Dónde hay más puentes en mala condición?', ['bridges_poor'], 'rank'], ['Which municipalities have the most bridges in poor condition?', ['bridges_poor'], 'rank'],
    ['where are the landslides', ['landslides_maria'], 'rank'], ['¿Dónde hubo más derrumbes después de María?', ['landslides_maria'], 'rank'],
    ['earthquakes in Guánica', ['quakes_m25'], 'value'], ['¿Cuántas escuelas hay en Ponce?', ['sch_open'], 'value'], ['¿Qué municipios tienen más humedales?', ['wetland_km2'], 'rank'],
    ['riesgo de huracanes', ['nri_eal_hurricane'], 'show'], ['distance to a health center', ['hc_road_km'], 'show'], ['distancia a un centro de salud en Utuado', ['hc_road_km'], 'value'],
    ['energía renovable', ['power_renewable_mw'], 'show'], ['compare poverty and bridges in poor condition', ['poverty_pct', 'bridges_poor'], 'compare'],
    // community assets (2026-10-18): "historic places" names a dataset, not a trend; an "ask" phrase written with a hyphen in the question
    ['Where are the most historic places?', ['nrhp_places'], 'rank'], ['¿Dónde hay más lugares históricos?', ['nrhp_places'], 'rank'],
    ['non-PRASA water systems', ['water_nonprasa'], 'show'], ['water systems outside PRASA', ['water_nonprasa'], 'show'], ['sistemas non-prasa en Lares', ['water_nonprasa'], 'value'],
    ['Which municipalities have the most treatment facilities?', ['bh_all'], 'rank'],
  ]) { const r = p(q); assert.deepStrictEqual([r.keys, r.intent], [keys, intent], q); }
  assert.strictEqual(p('How has unemployment changed since 2015?').intent, 'trend');
  assert.strictEqual(p('the history of unemployment').intent, 'trend', '"history" still asks for a trend');
  // the rules keep what they had: a doctor is not Medicare, hospitals stay the health-care jobs rule's
  assert.deepStrictEqual([p('médicos en Ponce').keys, p('médicos en Ponce').intent], [['prov_primary_care'], 'value'], 'doctors are counted since step 8 of decision 107 (NPPES)');
  assert.deepStrictEqual([p('enfermeras en Ponce').keys, p('enfermeras en Ponce').intent], [[], 'practitioners'], 'nurses are not: only those who bill have an NPI');
  assert.deepStrictEqual(p('rent of students with children').keys, ['median_gross_rent'], 'a one-word "ask" phrase does not join a rule\'s dataset');
  assert.deepStrictEqual(p('poverty in Ponce').keys, ['poverty_pct']);
});
test('chat: places side by side, the area profile and the composite builder (plan item 14)', () => {
  const env = chatEnv().env, X = tabEngine();
  env.setApi({ datasets: () => X.info(), meta: (k) => X.V[k] || null, dictId: (k) => X.dictId(k), places: () => X.geo.names.slice() });
  const p = (q) => env.chParse(q);
  assert.deepStrictEqual([p('Compare Ponce and Mayagüez').intent, p('Compare Ponce and Mayagüez').places], ['areas', ['Ponce', 'Mayagüez']]);
  assert.strictEqual(p('Compara Ponce, Mayagüez y Arecibo').places.length, 3);
  assert.strictEqual(p('poverty in Ponce and Caguas').intent, 'areas');
  assert.strictEqual(p('poverty in Ponce').intent, 'value', 'one place is still one value');
  assert.strictEqual(p('Tell me about Ponce').intent, 'muni');
  for (const q of ['build an index of poverty and unemployment', 'índice compuesto de pobreza y desempleo']) assert.deepStrictEqual([p(q).intent, p(q).keys], ['compose', ['poverty_pct', 'laus_unemp_rate']], q);
  assert.strictEqual(p('poverty and unemployment').intent !== 'compose', true, 'no index word: not the builder');
});
test('chat: the Population variables are found by their own words and by nothing else', () => {
  const keys = chatConcepts(), has = (q, k) => assert.ok(keys(q).includes(k), `"${q}" should find ${k}, found ${keys(q)}`), not = (q, k) => assert.ok(!keys(q).includes(k), `"${q}" must not find ${k}, found ${keys(q)}`);
  for (const q of ['where do most veterans live?', 'veteranas', 'veteranos en Ponce']) has(q, 'acs_veteran_pct');
  for (const q of ['people with a disability', 'impedimentos', 'discapacidad en Utuado']) has(q, 'acs_disability_pct');
  for (const q of ['households of one person', 'single-person households', 'one person households', 'hogares de una persona', 'who lives alone', 'personas que viven solas', 'donde viven mas personas solas']) { has(q, 'acs_living_alone_pct'); not(q, 'households'); }
  for (const q of ['family households', 'hogares familiares']) has(q, 'acs_family_households_pct');
  for (const q of ['children', 'share under 18', 'menores de edad', 'niñez', 'ninos']) has(q, 'acs_under18_pct');
  for (const q of ['share of women', 'females', 'mujeres']) has(q, 'acs_female_pct');
  not('commute under 18 minutes', 'acs_under18_pct');
  for (const q of ['female-headed households', 'women-owned businesses', 'mujeres jefas de hogar', 'women owned businesses']) not(q, 'acs_female_pct');
  for (const q of ['people 65 and older', 'mayores de 65', 'personas de 65 anos o mas']) assert.deepStrictEqual(keys(q), ['acs_age65plus_pct'], q);
  for (const q of ['survey estimate of the population', 'Population (survey estimate)']) assert.deepStrictEqual(keys(q), ['acs_population'], q);
  assert.deepStrictEqual(keys('poblacion'), ['population']); assert.deepStrictEqual(keys('alquiler'), ['median_gross_rent']); assert.deepStrictEqual(keys('alquileres'), ['median_gross_rent']);
  for (const [q, k] of [['carga de costos de alquiler', 'renter_cost_burden_pct'], ['tasa de vacantes de alquiler', 'vacancy_pct'], ['asequibilidad del alquiler', 'affordability_ratio'], ['viviendas de alquiler', 'housing_units'], ['viviendas en alquiler', 'housing_units'],
    ['precio del alquiler', 'median_gross_rent'], ['costo de alquiler', 'median_gross_rent'], ['el alquiler en Ponce', 'median_gross_rent'], ['alquiler mediano', 'median_gross_rent']]) assert.deepStrictEqual(keys(q), [k], `"${q}" is about ${k} only`);   // alquiler describes another thing in the first five
  assert.deepStrictEqual(keys('compara el alquiler con las vacantes').sort(), ['median_gross_rent', 'vacancy_pct'], 'two things put side by side keep both');
  for (const q of ['tendencia de alquileres', 'evolución de alquileres', 'ranking de alquileres', 'mapa de alquileres', 'datos de alquileres', 'promedio de alquileres', 'mediana de alquileres', 'estadísticas de alquileres', 'índice de alquileres', 'variación de alquileres',
    'cifras de alquileres', 'tabla de alquileres', 'mercado de alquileres', 'tasa de alquileres', 'evolución del alquiler', 'promedio del alquiler', 'mapa del alquiler', 'datos del alquiler', 'nivel de alquiler']) assert.deepStrictEqual(keys(q), ['median_gross_rent'], `"${q}" is the rent (it was on main for the plural)`);
  for (const q of ['casas de alquiler', 'contratos de alquiler', 'ayuda de alquiler', 'asistencia de alquiler']) assert.deepStrictEqual(keys(q), [], `"${q}" is not the rent`);
  for (const q of ['carga de alquiler', 'carga del alquiler', 'inquilinos con carga de alquiler', '¿cuánto es la carga de alquiler?', 'carga de alquiler en Ponce']) assert.deepStrictEqual(keys(q), ['renter_cost_burden_pct'], `"${q}" is the renter burden`);
  for (const q of ['alquiler asequible', 'alquileres asequibles']) assert.deepStrictEqual(keys(q), ['affordability_ratio'], `"${q}" is the affordability only, as on main`);
  assert.deepStrictEqual(keys('Residents aged 65 and over'), ['age65_pct'], 'the whole label of the older dataset names it'); assert.deepStrictEqual(keys('people 65 and older'), ['acs_age65plus_pct']);
  assert.deepStrictEqual(keys('de alquiler'), ['median_gross_rent'], 'with no word before the preposition there is nothing it describes');
  assert.deepStrictEqual(keys('alquiler a corto plazo'), ['seasonal_pct'], 'a short-term rental is the seasonal share, as in English');
  has('seniors', 'age65_pct'); has('unemployment', 'laus_unemp_rate');   // the rules that were there are untouched
});
test('chat: whose figure it is: a group of people beside another dataset is a qualifier, however the question is worded; two things put side by side keep both', () => {
  const keys = chatEnv();
  const alone = [   // [question, the dataset kept, the words of the groups left out]
    ['poverty among women', ['poverty_pct'], ['women']], ['poverty rate among women', ['poverty_pct'], ['women']], ['how many kids are in poverty?', ['poverty_pct'], ['kids']], ["women's poverty", ['poverty_pct'], ['women']],
    ["veterans' income", ['median_hh_income'], ['veterans']], ['female unemployment', ['laus_unemp_rate'], ['female']], ['poverty among people with disabilities', ['poverty_pct'], ['disabilities']],
    ['households headed by women', ['households'], ['women']], ['compare poverty among women and men', ['poverty_pct'], ['women']], ['poverty among women and children', ['poverty_pct'], ['women', 'children']],
    ['disability among the elderly', ['acs_disability_pct'], ['elderly']], ['unemployment of young women', ['laus_unemp_rate'], ['women']], ['income of veterans', ['median_hh_income'], ['veterans']], ['kids in poverty', ['poverty_pct'], ['kids']],
    ['pobreza entre mujeres', ['poverty_pct'], ['mujeres']], ['mujeres en pobreza', ['poverty_pct'], ['mujeres']], ['ninos en pobreza', ['poverty_pct'], ['ninos']], ['hogares encabezados por mujeres', ['households'], ['mujeres']],
    ['hogares con jefatura femenina', ['households'], ['femenina']], ['poverty among family households', ['poverty_pct'], ['family households']], ['poverty rates for women', ['poverty_pct'], ['women']],
    ['where is poverty highest among seniors', ['poverty_pct'], ['seniors']], ['seniors in median rent', ['median_gross_rent'], ['seniors']], ['pobreza entre ancianos', ['poverty_pct'], ['ancianos']], ['hogares encabezados por ancianos', ['households'], ['ancianos']], ["seniors' poverty", ['poverty_pct'], ['seniors']],
    ['compare poverty among seniors', ['poverty_pct'], ['seniors']], ['compare poverty among women', ['poverty_pct'], ['women']], ['how many seniors are in poverty', ['poverty_pct'], ['seniors']], ['ingresos de ancianos', ['median_hh_income'], ['ancianos']], ['what share of seniors live in poverty', ['poverty_pct'], ['seniors']], ['what percentage of children are in poverty', ['poverty_pct'], ['children']], ['poverty in seniors', ['poverty_pct'], ['seniors']],
    ['pobreza de las mujeres', ['poverty_pct'], ['mujeres']], ['where is poverty highest among women', ['poverty_pct'], ['women']], ['internet access among seniors', ['internet_subscription_pct'], ['seniors']], ['commute time among veterans', ['commute_45plus_pct'], ['veterans']],
    ['women in median rent', ['median_gross_rent'], ['women']], ['veterans among the elderly', ['acs_veteran_pct'], ['elderly']], ['donde es mas alta la pobreza entre mujeres', ['poverty_pct'], ['mujeres']], ['ninos que viven en pobreza', ['poverty_pct'], ['ninos']], ['poverty among people with disabilities and veterans', ['poverty_pct'], ['disabilities', 'veterans']],
    ['poverty is always very high for all the women', ['poverty_pct'], ['women']], ['poverty is always very high for the women', ['poverty_pct'], ['women']], ['poverty among u.s. women', ['poverty_pct'], ['women']], ['hogares unipersonales de ancianos', ['acs_living_alone_pct'], ['ancianos']], ['ingresos de veteranos', ['median_hh_income'], ['veteranos']], ['desempleo femenino', ['laus_unemp_rate'], ['femenino']],
  ];
  for (const [q, kept, out] of alone) { const r = keys.full(q); assert.deepStrictEqual(r.keys, kept, `"${q}" keeps ${kept}, found ${r.keys}`); assert.deepStrictEqual(r.dropped.map(d => d.text), out, `"${q}" leaves out ${out}`); }
  const both = [['poverty and women', 2], ['compare poverty with veterans', 2], ['poverty versus children', 2], ['veterans and children', 2], ['show poverty, women and children', 3], ['compara la pobreza con los veteranos', 2], ['where do most women live', 1], ['women', 1], ['veterans', 1],
    ['women with children', 2], ['veterans with disability', 2],     ['compare poverty with the share of seniors', 2], ['show poverty next to seniors', 2], ['overlay seniors on poverty', 2], ['poverty where seniors live', 2], ['poverty in places with many seniors', 2], ['is poverty higher where there are more seniors', 2],
    ['do places with more elderly have higher poverty', 2], ['how does poverty vary with the share of seniors', 2], ['does income rise with the share of older adults', 2], ['compara el desempleo con la proporcion de ancianos', 2], ['¿es mayor la pobreza donde hay mas ancianos?', 2],
    ['compare poverty with the share of women', 2], ['show poverty next to veterans', 2],
    ['compare poverty seniors', 2], ['poverty in places with veterans', 2], ['places with veterans have higher poverty', 2], ['lugares con ninos tienen mas pobreza', 2], ['does poverty move with women', 2], ['does poverty change with people with disabilities', 2], ['correlacion la pobreza ancianos', 2], ['overlay poverty seniors', 2], ['poverty seniors together', 2], ['seniors among women', 2], ['veterans among people with disabilities', 2], ['poverty as well as women', 2], ['poverty along with women', 2], ['show women. show poverty.', 2], ['pobreza asi como mujeres', 2]];   // two groups of one level do not qualify each other; "as well as" and a full stop put two things side by side
  for (const [q, n] of both) { const r = keys.full(q); assert.strictEqual(r.keys.length, n, `"${q}" keeps ${n}, found ${r.keys}`); assert.deepStrictEqual(r.dropped, [], q); }
});
test('chat: a group beside "population" is the group\'s own dataset: nothing is left out, so no note says there is no such breakdown', () => {
  const keys = chatEnv();
  for (const q of ['where is the elderly population highest?', 'elderly population', 'senior population', 'population aging', 'is the population aging?', 'population over 65', 'población de adultos mayores', 'envejecimiento de la población']) {   // main had the elderly's dataset: both, as on main
    const r = keys.full(q);
    assert.deepStrictEqual(r.dropped, [], `"${q}" leaves nothing out`);
    assert.ok(r.keys.includes('population') && r.keys.length >= 2, `"${q}" keeps the population and the group's dataset: ${r.keys}`);
  }
  for (const [q, k] of [['population 65 and older', 'acs_age65plus_pct'], ['veteran population', 'acs_veteran_pct'], ['population with a disability', 'acs_disability_pct'], ['poblacion con discapacidad', 'acs_disability_pct'], ['habitantes con discapacidad', 'acs_disability_pct'], ['female population', 'acs_female_pct'], ['population of women', 'acs_female_pct']]) {
    const r = keys.full(q);   // the survey's share is the group's figure: the total population is not asked
    assert.deepStrictEqual(r.keys, [k], `"${q}"`); assert.deepStrictEqual(r.dropped, [], q);
  }
  assert.deepStrictEqual(keys.full('poverty among women').keys, ['poverty_pct'], 'a group still says whose figure a dataset with no breakdown by it is');
  assert.deepStrictEqual(keys.full('compare poverty for women and the general population').keys, ['poverty_pct'], '"the general population" is the counterpart of the group, not the Resident population dataset');
  assert.deepStrictEqual(keys.full('compara la pobreza de mujeres y la poblacion general').keys, ['poverty_pct']);
  for (const q of ['how large is the general population', 'general population by municipality', 'the general population of the island', 'the rest of the population', 'resto de la población', 'la población general']) assert.deepStrictEqual(keys(q), ['population'], `"${q}" is the Resident population when no group is in the question, as on main`);
  for (const [q, k] of [['population and veterans', ['population', 'acs_veteran_pct']], ['veterans and population', ['acs_veteran_pct', 'population']], ['population versus veterans', ['population', 'acs_veteran_pct']], ['population and women', ['population', 'acs_female_pct']], ['women and population', ['acs_female_pct', 'population']], ['población y veteranos', ['population', 'acs_veteran_pct']]]) assert.deepStrictEqual(keys(q), k, `"${q}" names both: both are asked, in the order of the words`);
  assert.deepStrictEqual(keys.full('población con discapacidad').keys, ['acs_disability_pct'], 'the survey\'s share answers, the total population is not asked');
  assert.deepStrictEqual(keys.full('population of the elderly').keys, ['age65_pct', 'population'], 'the elderly (main had their dataset) keep both, the group\'s own first');
  for (const [q, k] of [['which municipalities have the highest population and the lowest poverty', ['population', 'poverty_pct']], ['how have population and poverty changed since 2015', ['population', 'poverty_pct']], ['top 5 municipalities by population and unemployment', ['population', 'laus_unemp_rate']]]) assert.deepStrictEqual(keys.full(q).keys, k, `"${q}": the order of the datasets is the order of the words when no group is named`);
});
test('chat: natural wordings: a question that says whose figure it is leaves the group out, a question that relates two datasets keeps both', () => {
  const keys = chatEnv(), GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const say = ['women below the poverty line', 'veterans below the poverty line', 'children living below the poverty line', 'what percent of women are below the poverty line', 'how many veterans live below the poverty line', 'mujeres por debajo del nivel de pobreza', 'veteranos bajo el nivel de pobreza',
    'poverty among families with children', 'poverty among households with children', 'income of households with children', 'income of households with veterans', 'pobreza entre las familias con niños', 'pobreza en hogares con niños',
    'poverty among single women', 'poverty among older women', 'poverty among Puerto Rican women', "poverty among the island's veterans", 'poor people with disabilities', 'rent paid by veterans', 'alquiler que pagan las mujeres', 'alquiler que pagan los veteranos',
    'how poor are children', 'how rich are veterans', '¿son más pobres las mujeres?', '¿qué tan pobres son los niños?', 'women with low income', 'veterans with low income', 'poverty among people living alone', 'jobs held by women', 'rent paid by women', 'poverty among U.S. women', 'pobreza en personas que viven solas',
    'compare poverty for women and men', 'poverty gap between women and men', 'income gap between women and men', 'compare unemployment for men and women', 'compare poverty between women and men', 'women versus men in poverty', 'poverty for women vs men', 'compare income of women with income of men',
    'compara la pobreza de mujeres y hombres', 'compare el desempleo entre hombres y mujeres', 'poverty of veterans compared with non-veterans', 'compare poverty for veterans and non-veterans',
    'poverty among women', 'poverty rate among women', 'how many kids are in poverty?', "women's poverty", "veterans' income", 'female unemployment', 'poverty among people with disabilities', 'households headed by women', 'compare poverty among women and men', 'poverty among women and children', 'unemployment of young women', 'income of veterans', 'kids in poverty',
    'pobreza entre mujeres', 'mujeres en pobreza', 'ninos en pobreza', 'hogares encabezados por mujeres', 'desempleo femenino', 'where is poverty highest among women', 'internet access among seniors', 'commute time among veterans', 'women in median rent', 'poverty is always very high for the women', 'where is unemployment highest among women',
    'show me where poverty is highest among veterans', '¿dónde es más alta la pobreza entre mujeres?', 'which municipalities have the most children in poverty', 'unemployment among women in Ponce', 'poverty in women over 65',
    'compare poverty for children and adults', 'compare poverty for females and males', 'female versus male poverty', 'compare unemployment for veterans and everyone else', 'compare poverty for people with and without disabilities', 'compare poverty for women and the general population',
    'poverty for children versus adults', 'children vs adults in poverty', 'compare poverty for people living alone and families', 'one-person households versus family households poverty', 'compare income for households with and without children',
    'compara la pobreza de niños y adultos', 'compara la pobreza de mujeres y varones', 'compare poverty for veterans and civilians', 'compara la pobreza de veteranos y civiles', 'compare poverty for women and other residents', 'compare poverty for veterans and the rest of the residents',
    'compare poverty for people with disabilities and non-disabled people', 'compara la pobreza de personas con y sin discapacidad', 'compara la pobreza de mujeres y otros residentes', 'compara la pobreza de mujeres y el resto', 'compare unemployment for men and women', 'compara el desempleo entre hombres y mujeres',
    'compare teenagers and children poverty', 'compare poverty children and teenagers', 'veterans among civilians and unemployment', 'poverty among women, men and other residents', 'unemployment among veterans, non-veterans', 'pobreza entre veteranos, civiles', 'income among people with disabilities, non-disabled', 'pobreza entre mujeres, hombres',
    'Who has higher poverty, women or men?', 'poverty: women versus men', 'women vs men: poverty', 'poverty for men and the women', "compare women's and men's poverty", "women's and men's income", "veterans' and non-veterans' poverty", "compare veterans' and civilians' unemployment",
    'poverty for men and for women', 'pobreza: mujeres versus hombres', 'la pobreza de los hombres y las mujeres', 'mujeres comparado con hombres en la pobreza', 'disabled people compared with able-bodied people in terms of poverty',
    'poverty among women and the veterans', 'poverty among children and the veterans', 'poverty among women and the people with disabilities', 'unemployment among women and the veterans', 'poverty among veterans and the children', 'poverty among women and also veterans', 'poverty among women, who are veterans', 'poverty among women, particularly veterans', 'poverty among veterans, particularly women', 'pobreza de los niños y los veteranos', 'pobreza entre las mujeres y los veteranos',
    'compare la pobreza de los hogares unipersonales y los hogares familiares', 'How does poverty among veterans vary across municipalities?', 'poverty among women near San Juan', 'unemployment among veterans near the coast', 'does poverty among women depend on the municipality',
    'poverty among veterans grows with age', 'how did Hurricane Maria affect poverty among veterans', 'how many women are affected by poverty', 'how does rent for women vary by municipality', 'per capita income for women versus the general population',
    '¿cómo varía la pobreza entre veteranos por municipio?', 'poverty among women in the municipalities of Ponce and Caguas', 'poverty among women in the towns of Ponce and Caguas', 'poverty among women in rural areas and cities'];
  const relate = ['compare poverty with the share of women', 'show poverty next to veterans', 'is poverty higher where there are more veterans', 'do places with more women have higher poverty', 'how does poverty vary with the share of children', 'does income rise with the share of veterans',
    'poverty in places with many veterans', 'poverty and women', 'compare poverty with veterans', 'correlate poverty and disability', 'poverty versus children', 'overlay women on poverty', 'map poverty and veterans together', 'show poverty. show women.', 'is poverty related to the share of people with disabilities',
    'poverty vs disability', 'compare poverty seniors', 'does poverty change with women', 'how does poverty track the share of veterans', 'is unemployment higher in places with more children', 'relationship between poverty and the share of women',
    'compara la pobreza con la proporcion de mujeres', 'muestra la pobreza junto a los veteranos', 'pobreza donde viven mas ninos', 'correlacion entre pobreza y discapacidad', 'es mayor la pobreza donde hay mas veteranos', 'pobreza en lugares con muchas mujeres', 'muestra la pobreza y las mujeres',
    'compare poverty with the share of seniors', 'show poverty next to seniors', 'overlay seniors on poverty', 'poverty where seniors live', 'poverty in places with many seniors', 'is poverty higher where there are more seniors', 'do places with more elderly have higher poverty', 'how does poverty vary with the share of seniors', 'does income rise with the share of older adults',
    'women and girls and poverty', 'map poverty and women and girls', 'women and girls vs unemployment', 'pobreza y veteranos entre civiles',
    'seniors in poor municipalities', 'elderly in poor towns', 'seniors in wealthy areas', 'where do rich seniors live', 'dónde viven los ancianos ricos', 'women in poor municipalities', 'children in poor towns', 'kids in high-poverty areas', 'veterans in wealthy areas',
    'where do wealthy veterans live', 'mujeres en municipios ricos', 'dónde viven los veteranos desempleados', 'does the share of women affect poverty', 'the more women the more poverty', 'poverty by the share of women', '¿afecta el porcentaje de mujeres a la pobreza?', 'women: poverty',
    'compare internet access and women', 'compare women with poverty', 'compare veterans with unemployment', 'compara las mujeres con la pobreza', 'compare people under 18 with poverty', 'women and median rent', 'mujeres y la pobreza', 'where do poor people with disabilities live',
    'which municipalities have more veterans and more unemployment', 'where are there more veterans and fewer jobs', 'most veterans and most poverty', 'veterans and high unemployment', 'veteranos y mucho desempleo', 'más niños y menos ingresos'];
  for (const q of say) { const r = keys.full(q); assert.ok(!r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}" is about the other dataset, for the group: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); }
  for (const q of relate) { const r = keys.full(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.length >= 2 && r.dropped.length === 0, `"${q}" asks how two datasets relate: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); }
});
test('chat: seventh check: a group next to the topic, a word of relation in another sense, a verb of effect before the group, "with high", two groups joined by more than "and", "figures on" say whose figure it is; a total named beside a group keeps both', () => {
  const keys = chatEnv(), GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const say = [
    'compare female unemployment across municipalities', 'compare veteran unemployment in Ponce and Caguas', 'plot veteran poverty by town', 'chart veteran poverty by town', 'link veteran poverty', 'connect veteran poverty', 'against veteran poverty', 'vs veteran poverty', 'versus veteran poverty',   // a group next to the topic is an adjective of it, whatever verb of comparing the question has
    'compara el desempleo femenino entre municipios', 'grafica la pobreza femenina por municipio', '¿cómo se compara la pobreza femenina entre pueblos?', 'compare poverty women', 'compare internet access veterans', 'compara el ingreso mediano mujeres', 'compara el desempleo mujeres', 'compare poverty women and girls',
    'poverty of women relative to men', 'relatively high poverty among women', 'poverty among women in relation to the island average', 'la pobreza de las mujeres en relación con el promedio de la isla', 'poverty among women by relationship status', 'poverty among women and children together', 'datos de la Junta de Planificación sobre pobreza de mujeres',   // "relative", "relation", "together", "Junta": not a question about how two datasets relate
    "how did the hurricane affect women's poverty", "what affects women's poverty", 'what impacts women in poverty', "did the pandemic impact veterans' unemployment", 'what influences veterans in poverty', '¿qué afecta la pobreza de las mujeres?',   // a verb of effect before the group is about what is affected
    'women with high poverty', 'veterans with high unemployment', 'women with high rent', 'mujeres con alta pobreza', 'veteranos con alto desempleo', 'women with the lowest rent', 'veterans with lower income', 'children with more poverty',   // "with" and then words like high, more, the lowest describe the group
    'poverty of women compared to the children', 'poverty of women compared to the veterans', 'poverty of women compared to the disabled', 'poverty of women compared to those living alone', 'poverty of women versus the veterans', 'poverty for veterans along with women', 'la pobreza de veteranos y de mujeres',
    'poverty of veterans together with women', 'pobreza de veteranos junto con mujeres', 'poverty for veterans, besides women', 'poverty for women and for veterans',   // two groups joined by more than "and": one breakdown
    'poverty figures on women', 'unemployment numbers on veterans', 'poverty rates on women', 'cifras de pobreza sobre mujeres',   // "on" and "sobre" are prepositions
    'correlation between poverty and income among women', 'poverty and income correlation among women',   // the word of relation is about the two others
    "what correlates with veterans' unemployment", "what depends on women's poverty", "correlation of women's poverty", 'poverty for veterans near women', 'poverty for veterans next to women', "poverty vs women's income", "poverty among women versus men's income",   // a possessive says whose figure it is; a group tied only to a group that is left out is left out too
    'men versus women and poverty', 'men and women and poverty', 'hombres y mujeres y pobreza', 'poverty and women versus children', 'poverty and women versus veterans', 'pobreza y mujeres versus veteranos', 'la pobreza de mujeres comparadas con los veteranos',   // a counterpart before or after the group, or two groups against each other, make it the breakdown even when "and" stands between the group and the topic
    'poverty of veterans along with women', 'poverty for veterans in addition to women', 'poverty among veterans alongside women',   // a group tied by any connector to a group that is left out
    'correlation is a hard word to spell but poverty among women is what I ask about',   // a word of relation seven words away is not next to the datasets
    'correlate female unemployment across municipalities', 'overlay veteran poverty by town', 'scatter female unemployment', 'scatter poverty women', 'correlacion pobreza femenina entre municipios', 'superpone la pobreza femenina por municipio', 'poverty correlation among women', 'unemployment correlation for veterans',   // two datasets next to each other: an adjective, whatever the word of relation; a word of relation inside the gap with "among" after it is about the group
    'poverty among women with children', 'poverty among veterans with disabilities', 'poverty among women who live alone', 'poverty of women near veterans', 'poverty of women along with veterans', 'poverty among women, together with veterans', 'poverty of women in addition to people living alone', 'poverty of women compared to the people with disabilities', 'poverty of women alongside the veterans', 'la pobreza entre mujeres junto con veteranos', 'la pobreza entre mujeres junto a veteranos',   // a group a few words from the group that is the breakdown is part of it
    'poverty of women and people living alone', 'correlation of poverty among people with disabilities with income',
    'scatter poverty rate women', 'overlay unemployment rate veterans', 'poverty and women compared to the children', 'pobreza y mujeres comparadas con ninos', 'poverty and women compared to the people with disabilities', 'poverty and women versus non-veterans', 'poverty: women vs non-veterans',   // the rest of a dataset's name is not a word between two datasets; two groups set against each other, though the first is tied to the dataset by "and"
    'poverty among women: correlation with income', 'poverty and unemployment among women, correlation', 'correlation of poverty among women with income', 'poverty among women, scatter against income', 'poverty among women is what the long report is about, with a section on correlation',   // a word of relation with another dataset just as near may be about that one, and one many words away is not next to them
  ];
  for (const q of say) { const r = keys.full(q); assert.ok(r.keys.length > 0 && !r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}" is about the other dataset, for the group: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.deepStrictEqual(!!keys.parse(q).related, false, q); }
  const relate = ['Self-employed residents and women', 'women and the share of poverty', 'veterans and the percentage of unemployment', 'plot women with poverty', 'grafica mujeres con pobreza', 'link women with poverty', 'pobreza y mujeres y tambien muestra desempleo', 'pobreza y mujeres y muestra el desempleo', 'poverty and veterans along with women', 'poverty in relation to women', 'pobreza en relacion con las mujeres', 'poverty + women', 'poverty / women', 'poverty and/or women', 'correlation between poverty and women', 'relationship between poverty and women', 'poverty and women, correlation', 'scatter poverty and veterans', 'overlay veterans on poverty', 'how does poverty relate to the share of women',
    'is poverty correlated with the share of veterans', 'does poverty correlate with the share of women', 'does poverty depend on women', 'poverty compared with women', 'compare women with poverty', 'show poverty and women together', 'poverty: women', 'poverty, women',
    'compare poverty with % of women', 'poverty and women and also unemployment', 'poverty and women and then show income', 'pobreza y mujeres y tambien desempleo', 'map women and show poverty', 'veterans and only poverty'];   // two datasets side by side, with the words that may stand between them
  for (const q of relate) { const r = keys.full(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.length >= 2 && r.dropped.length === 0, `"${q}" asks how two datasets relate: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!keys.parse(q).related, true, q); }
  for (const [q, k] of [['compare population with veterans', ['population', 'acs_veteran_pct']], ['population alongside veterans', ['population', 'acs_veteran_pct']], ['population next to veterans', ['population', 'acs_veteran_pct']], ['overlay veterans on population', ['acs_veteran_pct', 'population']],
    ['population compared with veterans', ['population', 'acs_veteran_pct']], ['households alongside people living alone', ['households', 'acs_living_alone_pct']],
    ['compara la población con los veteranos', ['population', 'acs_veteran_pct']], ['población junto a veteranos', ['population', 'acs_veteran_pct']]]) assert.deepStrictEqual(keys(q), k, `"${q}" names the total and the group side by side: both are asked`);
  for (const [q, k] of [['households where people live alone', 'acs_living_alone_pct'], ['hogares donde viven personas solas', 'acs_living_alone_pct'], ['population of veterans', 'acs_veteran_pct'], ['population with a disability', 'acs_disability_pct'], ['households with people living alone', 'acs_living_alone_pct']]) assert.deepStrictEqual(keys(q), [k], `"${q}" is the group's own dataset`);
  const named = keys.full('poverty among women and the share of veterans'); assert.deepStrictEqual(named.keys, ['poverty_pct', 'acs_veteran_pct']); assert.deepStrictEqual(named.dropped.map(d => d.text), ['women'], 'the share of the second group is named: it is a dataset of its own');
  assert.deepStrictEqual(keys('poverty among women is what the report is about, and so is the whole discussion of the veterans'), ['poverty_pct', 'acs_veteran_pct'], 'a group many words away is not part of the breakdown');
  assert.deepStrictEqual(keys('poverty among women in rich municipalities with veterans'), ['poverty_pct', 'median_hh_income', 'acs_veteran_pct'], 'a dataset that describes the places sits between the two groups: the second is asked with it');
  for (const q of ['poverty and women, who are veterans', 'poverty and women, particularly veterans', 'poverty and women also veterans', 'poverty and women too veterans', 'poverty and women and the veterans']) assert.deepStrictEqual(chatEnv().parse(q).relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_veteran_pct', 'poverty_pct']], `"${q}": two groups joined are one group, related to the dataset together`);
  assert.deepStrictEqual(chatEnv().parse('poverty and women and people living alone').relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_living_alone_pct', 'poverty_pct']]);
  for (const q of ['poverty among women near seniors', 'poverty among women with the elderly', 'poverty of children along with the elderly', 'poverty among veterans with seniors']) assert.deepStrictEqual(keys(q), ['poverty_pct', 'age65_pct'], `"${q}": the elderly, that main had a dataset for, are not part of a breakdown by a group that main had none for`);
  const rel2 = keys.full('poverty among women near veterans and income'); assert.deepStrictEqual(rel2.keys, ['poverty_pct', 'acs_veteran_pct', 'median_hh_income'], 'a group related to another dataset is a layer of its own'); assert.deepStrictEqual(rel2.dropped.map(d => d.text), ['women']);
  assert.deepStrictEqual(keys('population of people with disabilities'), ['acs_disability_pct'], 'people with disabilities is the group; "people with" is not a word between the total and the group');
  assert.deepStrictEqual(keys('poverty among U.S. women'), ['poverty_pct']); assert.deepStrictEqual(keys('poverty and u.s. women'), ['poverty_pct'], 'a full stop inside an abbreviation is not a connector');
});
test('chat: no question takes long to parse: a run of spaces, line breaks, one word repeated, a chain of municipality names', () => {
  const k = chatEnv(), e = k.env, p = k.parse, names = ['Aguas Buenas', 'San Sebastian', 'Barceloneta', 'Rio Grande', 'Juana Diaz', 'Ponce', 'San Juan', 'Caguas', 'Toa Alta', 'Vega Baja'];
  e.setApi({ places: () => [...names, 'Puerto Rico'], meta: () => ({}), datasets: () => [] });
  try {
    const qs = [];
    for (const n of [26, 40, 100, 200, 380]) for (const sp of [' ', '\n', ' \n', '\t']) qs.push('poverty' + sp.repeat(n) + 'among women', 'women' + sp.repeat(n) + 'and poverty', 'poverty' + sp.repeat(n) + 'compared with the share of women');
    for (const w of ['with', 'and', 'the', 'share', 'alta', 'high', 'of', 'where', 'compared with', 'next to', 'more', 'also']) qs.push('poverty ' + (w + ' ').repeat(Math.floor(380 / (w.length + 1))) + 'women', 'women ' + (w + ' ').repeat(Math.floor(380 / (w.length + 1))) + 'x');
    qs.push('poverty in ' + names.join(', ') + ', ' + names.join(' and ') + ' among women', 'women in ' + names.join(' ') + ' and poverty');
    let worst = 0, which = '';
    for (const q of qs) { const t0 = process.hrtime.bigint(); p(q.slice(0, 400)); const ms = Number(process.hrtime.bigint() - t0) / 1e6; if (ms > worst) { worst = ms; which = q.slice(0, 50); } }
    assert.strictEqual(p('poverty \n\t among   women').n, 'poverty among women', 'a run of white space is one space');
    assert.ok(worst < 250, `the slowest of ${qs.length} questions took ${worst.toFixed(0)} ms: ${which}`);
  } finally { e.setApi(null); }
});
test('chat: eighth check: a word that compares counts only before the two datasets, a far group is the breakdown, the verb of "where ... live" is not the group\'s, a mixed group is judged by kind, a word of relation counts only before the datasets, a total named beside a group has more connectors', () => {
  const keys = chatEnv(), p = keys.parse, GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const say = [
    'women with low income compared to last year', 'women with low income versus 2015', 'women with low income vs the island', 'women with low income in Ponce compared to Caguas', 'women with low income against last year', 'plot women with low income by town', 'chart veterans with high unemployment by town',
    'link women with low income', 'connect veterans with high unemployment', 'compare women with low income', 'compare veterans with high unemployment', 'mujeres con alta pobreza en comparación con 2015', 'compara mujeres con baja pobreza', 'compare last year women with poverty',   // "with" and a word of degree describes the group; a word that compares counts only just before the two datasets
    'compare poverty rates across all of the municipalities of the island over the last decade for women', 'compare the unemployment rate in the north of the island with the south and the west in 2020 for veterans', 'compara la pobreza en todos los municipios de la isla durante la ultima decada para las mujeres',
    'poverty was discussed at length in the report about the island but nobody mentioned the women',   // a group far from the dataset is the breakdown, whatever the words between
    'where is poverty highest among people living alone', 'where is rent for people living alone compared to last year', '¿dónde está el alquiler para personas que viven solas?',   // the verb of "where ... live" is not the group's own
    'poverty among women overlapping with the pandemic', 'poverty among women side by side with last year', 'pobreza de mujeres lado a lado con el año pasado', 'scatter plot of poverty among women by municipality', 'side by side with last year: poverty among women',   // the object of a word of relation is not a dataset
    'poverty: veterans versus the average resident', 'la pobreza: mujeres versus la población general', 'personas con discapacidad contra personas sin discapacidad: la pobreza',   // the counterpart
    'together poverty among women',   // "together" is not a word of relation any more
    'veteran in poverty across municipalities', 'women in poverty across municipalities', 'children in poverty by town across the island', 'mujeres en pobreza por municipio en toda la isla',   // a place phrase holds the dataset that describes the places only when the dataset is just before the noun or after it
  ];
  for (const q of say) { const r = keys.full(q); assert.ok(r.keys.length > 0 && !r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}" is about the other dataset, for the group: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!p(q).related, false, q); assert.notStrictEqual(p(q).intent, 'compare', `"${q}" compares nothing`); }
  assert.deepStrictEqual(keys('compare all of the share of the women with poverty'), ['poverty_pct'], 'six filler words between the verb and the datasets: the verb is not next to them');
  const crowd = keys.full('correlation of poverty among women in the municipalities of the island with the population'); assert.deepStrictEqual(crowd.keys, ['poverty_pct', 'population'], 'the word of relation is about the two datasets that are not groups: a total is near it (eleven words away)'); assert.deepStrictEqual(crowd.dropped.map(d => d.text), ['women']);
  assert.deepStrictEqual(keys('correlation of the share of the number of the rate of poverty among women'), ['poverty_pct'], 'ten filler words between the word of relation and the datasets: it is not next to them');
  assert.deepStrictEqual(keys('population with veterans'), ['acs_veteran_pct'], 'with, with no word that compares: the veteran share is the group\'s own dataset');
  for (const q of ['poverty and women compared to last year', 'median income and people with disabilities compared to last year', 'pobreza y mujeres comparado con el año pasado', 'poverty in addition to women', 'poverty then women', 'poverty followed by veterans', 'women overlaid on poverty', 'pobreza además de veteranos', 'pobreza luego mujeres', 'households in addition to veterans', 'poverty on top of women', 'poverty overlay on women']) { const r = keys.full(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.length >= 2 && r.dropped.length === 0, `"${q}" names two datasets side by side: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!p(q).related, true, q); }   // a time after the group is not its counterpart; more words that put two datasets side by side
  for (const q of ['compare population with a disability across municipalities', 'population with a disability compared to last year', 'población con discapacidad comparada con el año pasado', 'compare population with a disability']) assert.deepStrictEqual(keys(q), ['acs_disability_pct'], `"${q}": the group's own dataset, whatever the words that compare`);
  for (const [q, k] of [['compare poverty across municipalities for veterans and seniors', ['poverty_pct', 'age65_pct']], ['poverty across municipalities for veterans and seniors', ['poverty_pct', 'age65_pct']], ['compare unemployment by town for children and the elderly', ['laus_unemp_rate', 'age65_pct']], ['compara la pobreza por pueblo para mujeres y ancianos', ['poverty_pct', 'age65_pct']]]) assert.deepStrictEqual(keys(q), k, `"${q}": the group main had no dataset for is the breakdown, the elderly keep their dataset`);
  for (const [q, k] of [['población frente a mujeres', ['population', 'acs_female_pct']], ['población además de veteranos', ['population', 'acs_veteran_pct']], ['households in addition to people living alone', ['households', 'acs_living_alone_pct']], ['population then veterans', ['population', 'acs_veteran_pct']], ['población luego veteranos', ['population', 'acs_veteran_pct']],
    ['population near veterans', ['population', 'acs_veteran_pct']], ['population overlaid on veterans', ['population', 'acs_veteran_pct']], ['population apart from veterans', ['population', 'acs_veteran_pct']], ['población aparte de veteranos', ['population', 'acs_veteran_pct']], ['población en contraste con mujeres', ['population', 'acs_female_pct']],
    ['households followed by people living alone', ['households', 'acs_living_alone_pct']], ['población cerca de veteranos', ['population', 'acs_veteran_pct']], ['population on top of veterans', ['population', 'acs_veteran_pct']], ['population overlay on veterans', ['population', 'acs_veteran_pct']]]) assert.deepStrictEqual(keys(q), k, `"${q}" names the total and the group: both are asked`);
  assert.strictEqual(p('compare women and veterans').intent, 'compare', 'two group datasets named together may be compared');
  assert.strictEqual(p('compare poverty with women').intent, 'compare'); assert.strictEqual(p('compare poverty and unemployment').intent, 'compare'); assert.strictEqual(p('compare poverty for women and men').keys.length, 1);
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8');
  assert.ok(src.includes("chComparable(st) && has("), 'the answer that compares is given for a group and another dataset only when the question relates them');
});
test('chat: ninth check: two groups offered as a choice or set against each other, a group against a statistic, a group\'s own words and own total', () => {
  const keys = chatEnv(), p = keys.parse, GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const alone = (list, k = ['poverty_pct']) => { for (const q of list) { const r = keys.full(q); assert.deepStrictEqual(r.keys, k, `"${q}": the groups are the breakdown, the topic is alone: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.ok(r.dropped.length > 0, `"${q}" says what it leaves out`); assert.deepStrictEqual(p(q).relPairs, [], `"${q}" relates nothing`); assert.notStrictEqual(p(q).intent, 'compare', `"${q}" compares nothing`); } };
  alone([   // two groups offered as a choice, after a comma, a colon or a question word (the ninth check)
    'who has higher poverty, women or veterans', 'which has the higher poverty: women or veterans', 'whose poverty is higher, women or veterans', 'which group has more poverty, women or veterans', 'poverty rate: women or veterans', 'compare poverty: women or veterans',
    'compara la pobreza: mujeres o veteranos', '¿quién tiene más pobreza, las mujeres o los veteranos?', 'poverty: either women or veterans', 'poverty, women or children or veterans', 'poverty: women, or veterans', 'women or veterans: poverty', 'poverty: women or the veterans',
    'poverty: women or else veterans', 'poverty: women or maybe veterans', 'poverty: women and/or veterans', 'poverty: women/veterans',   // more ways to offer the choice
    'poverty: women but not veterans', 'poverty: women and not veterans', 'poverty: women except veterans', 'poverty: women rather than veterans', 'poverty: women instead of veterans', 'poverty: women as opposed to veterans', 'poverty: women unlike veterans', 'poverty: women relative to veterans',
    'poverty: women in comparison with veterans', 'poverty: women compared against veterans', 'pobreza: mujeres en lugar de veteranos', 'pobreza: mujeres en vez de veteranos', 'pobreza: mujeres a diferencia de veteranos', 'pobreza: mujeres pero no veteranos', 'pobreza: mujeres excepto veteranos',
    'pobreza: mujeres frente a veteranos', 'pobreza: mujeres respecto a veteranos', 'mujeres frente a veteranos: la pobreza', 'pobreza: mujeres contra veteranos', 'poverty: women in contrast to veterans', 'poverty: women than veterans', 'poverty: women other than veterans', 'poverty: women excluding veterans',
    'pobreza: mujeres en contraste con veteranos', 'pobreza: mujeres y no veteranos', 'pobreza: mujeres salvo veteranos',   // words of contrast, in English and Spanish
    'poverty: women vs people living alone', 'poverty: veterans against persons living alone', 'poverty, children versus people living alone', 'people living alone vs women: poverty', 'who has higher poverty, women vs persons living alone', 'poverty: women compared with people living alone',
    'poverty: women vs people with disabilities', 'mujeres vs residentes con discapacidad: la pobreza', 'poverty: women or people who live alone', 'mujeres o personas que viven solas: la pobreza', 'poverty: women versus the people who live alone', 'poverty: women vs adults with disabilities', 'poverty: women vs residents with disabilities',
    'pobreza: mujeres vs gente con discapacidad', 'pobreza: mujeres vs personas con discapacidad', 'poverty: the average vs people with disabilities', 'who has higher poverty, the average vs persons living alone',   // the words of a group's own name stand between the joiner and its hit
    'poverty: women versus the average', 'poverty: women versus the median', 'poverty: women versus the mean', 'poverty: women versus the total', 'poverty: women versus the typical resident', 'poverty, women compared to the average', 'who has higher poverty, women or the average', 'poverty: women relative to the average',
    'poverty: women as compared to the average', 'poverty: women in comparison with the average', 'poverty: women unlike the average', 'poverty: women, not the average', 'the average vs women: poverty', 'poverty: women versus the island average', 'poverty: women versus the national average',
    'pobreza: mujeres versus el promedio', 'pobreza: mujeres versus la mediana', 'pobreza: mujeres versus el total', 'pobreza: mujeres versus el promedio de la isla', 'pobreza, mujeres comparado con el promedio', 'pobreza: mujeres frente al promedio', 'pobreza: mujeres respecto al promedio', 'pobreza: mujeres en comparacion con el promedio',   // a statistic is a counterpart
    'pobreza: mujeres versus la población en general', 'poverty: women versus the general population', 'poverty: women versus the population in general',
  ]);
  assert.deepStrictEqual(keys('poverty: women versus the lowest'), ['poverty_pct']); assert.strictEqual(p('poverty: women versus the lowest').intent, 'rank');
  for (const [q, k] of [['poverty: women versus the average household', ['poverty_pct']], ['poverty: women versus the total population', ['poverty_pct']], ['poverty: women versus the whole population', ['poverty_pct']], ['poverty: women versus the entire population', ['poverty_pct']], ['poverty: women versus the overall population', ['poverty_pct']],
    ['poverty: women versus households overall', ['poverty_pct']]]) {
    const r = keys.full(q); assert.deepStrictEqual(r.keys, k, `"${q}": round 17: the population or the households set against a group that is left out go with it (no population sentence nobody asked for)`); assert.deepStrictEqual(r.dropped.map(d => d.key), ['acs_female_pct'], q); assert.deepStrictEqual(p(q).relPairs, [], q);
  }
  for (const q of ['poverty: women versus average income', 'poverty and women versus average income', 'poverty: women versus total jobs', 'poverty: women versus median rent', 'poverty: women versus the lowest rent']) { const r = keys.full(q); assert.ok(r.keys.includes('acs_female_pct') && r.dropped.length === 0, `"${q}": the statistic is the front of a dataset's name, not a counterpart: ${r.keys}`); }
  assert.deepStrictEqual(keys('poverty: women versus the highest'), ['poverty_pct']); assert.strictEqual(p('poverty: women versus the highest').intent, 'rank');
  for (const [q, k, d] of [['who has higher poverty, women or seniors', ['poverty_pct', 'age65_pct'], ['acs_female_pct']], ['unemployment: veterans or the elderly', ['laus_unemp_rate', 'age65_pct'], ['acs_veteran_pct']], ['compara la pobreza: mujeres o ancianos', ['poverty_pct', 'age65_pct'], ['acs_female_pct']], ['poverty: seniors vs people living alone', ['poverty_pct', 'age65_pct'], ['acs_living_alone_pct']]]) {
    const r = keys.full(q); assert.deepStrictEqual(r.keys, k, `"${q}": the elderly, that main had a dataset for, stay: ${r.keys}`); assert.deepStrictEqual(r.dropped.map(x => x.key), d, q);
  }
  for (const q of ['poverty: women', 'poverty, women', 'poverty: women and veterans', 'poverty, women and veterans', 'who has higher poverty, women and veterans', 'poverty and women, who are veterans']) { const r = keys.full(q); assert.ok(r.keys.includes('acs_female_pct') && r.dropped.length === 0 && p(q).related === true, `"${q}" names the groups as datasets of the question, as it did: ${r.keys}`); }   // what did not change: a list is a list, "and" is not a choice
  const both = (list) => { for (const q of list) { const r = keys.full(q), s = p(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.length >= 2 && r.dropped.length === 0, `"${q}" asks for the group and the other dataset side by side: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!s.related, true, q); } };
  both(['compare people with disabilities with poverty', 'compare people who live alone with unemployment', 'compare the share of persons with disabilities with rent', 'compare, by municipality, women with poverty', 'compara personas con discapacidad con la pobreza', 'compare persons living alone with poverty', 'compare % of women with poverty',
    'compare households living alone with poverty', 'compare poverty with households living alone', 'compare unemployment with population with a disability', 'compare the veteran population with poverty', 'compare population with a disability with unemployment', 'compare family households with children with poverty', 'compare the share of the population of veterans with poverty',
    'poverty and persons living alone', 'poverty and personas que viven solas', 'plot poverty against people who live alone', 'how does poverty relate to persons living alone', 'poverty and households living alone',   // the words of the group's own name before its hit and its own total are not words between the verb and the datasets
    'poverty: households living alone', 'unemployment and the population with a disability', 'compare poverty with households in which people live alone', 'compare poverty with the population of people with disabilities', 'compara la poblacion con discapacidad con la pobreza',
    'compare the share of people with a disability with poverty', 'compare the share of residents with a disability with poverty', 'compare adults with a disability with poverty', 'compare individuals with disabilities with poverty', 'compare those with disabilities with poverty', 'compara residentes con discapacidad con la pobreza', 'compara gente con discapacidad con la pobreza',   // who the group is: adults, individuals, those, residents
    'compare across municipalities women with poverty', 'compare per town women with poverty', 'compare in each municipality women with poverty', 'compara, por pueblo, mujeres con pobreza', 'compara en cada municipio mujeres con pobreza',   // where the answer is cut is not a word between the verb and the datasets
    'poverty and women and people who live alone', 'poverty and women and personas que viven solas', 'poverty and residents living alone', 'poverty and adults living alone', 'poverty and individuals living alone', 'poverty and those living alone', 'pobreza y personas viviendo solas', 'pobreza y gente viviendo sola']);   // the noun before a group's name after a connector
  for (const q of ['compare people with disabilities with poverty', 'compare poverty with households living alone', 'compare unemployment with population with a disability', 'compare the veteran population with poverty', 'compare poverty with households in which people live alone']) assert.strictEqual(p(q).intent, 'compare', `"${q}"`);
  assert.deepStrictEqual(p('poverty and women and people who live alone').relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_living_alone_pct', 'poverty_pct']], 'two groups joined by "and" and "people who": one group, related to the dataset together');
  assert.deepStrictEqual(keys('poverty and the population of the island and veterans'), ['poverty_pct', 'population', 'acs_veteran_pct'], 'a total that is not next to the group is another dataset between them: nothing is related');
  assert.deepStrictEqual(keys('compare women who are veterans with population'), ['acs_female_pct', 'acs_veteran_pct', 'population'], 'a word that compares before a group of two groups: the total named beside it keeps both');
  for (const [q, k, d] of []) {   // round 17: the total of a group left out goes with it (the three wordings are in the round 17 test)
    const r = keys.full(q); assert.deepStrictEqual(r.keys, k, `"${q}": the group is the breakdown; its own total is a dataset of the question, as on main: ${r.keys}`); assert.deepStrictEqual(r.dropped.map(x => x.key), d, q);
  }
  for (const q of ['where is poverty among women where I live', 'where is rent for people living alone where we live']) { const r = keys.full(q); assert.ok(!r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}": the speaker's "where I live" is not a place phrase of the group: ${r.keys}`); }
  assert.deepStrictEqual(keys('where do rich seniors live'), ['median_hh_income', 'age65_pct'], 'the verb of a place phrase is the group\'s when the group does the living');
  for (const q of ['compare women with low income compared to last year', 'compare last year women with poverty', 'compare poverty rates across all of the municipalities of the island over the last decade for women']) { const r = keys.full(q); assert.ok(!r.keys.some(k => GROUPKEYS.has(k)), `"${q}": a word that compares only counts just before the datasets: ${r.keys}`); }
  // the group's own words stand between the joiner and its hit, whoever the group is: each noun and each connector, in the pattern that sets two groups against each other, in the one that sets a statistic against a group, and in the one that joins two groups
  const WHO_EN = ['people', 'persons', 'residents', 'adults'], WHO_ES = ['personas', 'residentes', 'gente'];
  for (const n of WHO_EN) { alone([`poverty: women vs ${n} with disabilities`, `poverty: the average vs ${n} with disabilities`, `women vs ${n} with disabilities: poverty`]); assert.deepStrictEqual(p(`poverty and women and ${n} with disabilities`).relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_disability_pct', 'poverty_pct']], `two groups joined, the second named with "${n} with"`); }
  for (const n of WHO_ES) { alone([`pobreza: mujeres vs ${n} con discapacidad`, `pobreza: el promedio vs ${n} con discapacidad`, `mujeres vs ${n} con discapacidad: la pobreza`]); assert.deepStrictEqual(p(`pobreza y mujeres y ${n} con discapacidad`).relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_disability_pct', 'poverty_pct']], `two groups joined, the second named with "${n} con"`); }
  for (const c of ['who', 'that']) { alone([`poverty: women vs people ${c} live alone`, `poverty: the average vs people ${c} live alone`, `women vs people ${c} live alone: poverty`]); assert.deepStrictEqual(p(`poverty and women and people ${c} live alone`).relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_living_alone_pct', 'poverty_pct']], `two groups joined, the second named with "people ${c}"`); }
  alone(['pobreza: mujeres vs personas que viven solas', 'pobreza: el promedio vs personas que viven solas']); assert.deepStrictEqual(p('pobreza y mujeres y personas que viven solas').relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_living_alone_pct', 'poverty_pct']]);
  alone(['poverty: women vs residents living alone', 'poverty: women vs adults living alone', 'poverty: women vs persons living alone', 'pobreza: mujeres vs gente viviendo sola', 'pobreza: mujeres vs personas viviendo solas', 'pobreza: mujeres vs residentes viviendo solos']);   // the noun stands right before the hit: it is part of the group's name
  assert.deepStrictEqual(p('poverty and women and people with disabilities').relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_disability_pct', 'poverty_pct']]);
  assert.deepStrictEqual(p('pobreza y mujeres y personas con discapacidad').relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_disability_pct', 'poverty_pct']]);
  assert.deepStrictEqual(p('compare poverty with households in which one person lives alone').relPairs, [['acs_living_alone_pct', 'poverty_pct']], 'the total that a group counts is part of its phrase up to four words before it');
  assert.deepStrictEqual(p('compare veterans in the north and population with poverty').relPairs, [], 'a total that is not next to the group is another dataset between them: nothing is related');
});
test('chat: tenth check: the phrase of a group (its nouns, quantifier, age, own total and the words that close its name), the rest of a dataset\'s name, the words that link, set against and count as a time', () => {
  const keys = chatEnv(), p = keys.parse, GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const left = (list, topic = 'poverty_pct') => { for (const q of list) { const r = keys.full(q); assert.ok(r.keys.includes(topic) && !r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}": the group is the breakdown, the topic stays: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.deepStrictEqual(p(q).relPairs, [], `"${q}" relates nothing`); } };
  const both = (list) => { for (const q of list) { const r = keys.full(q), s = p(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.length >= 2 && r.dropped.length === 0, `"${q}" asks for the group and the other dataset side by side: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!s.related, true, q); } };
  // the phrase of a group: an age, a quantifier, "los que", the closing words, the households it counts; the same phrases are the group in a relation and the breakdown after "among"
  both(['compare persons aged 18 or more who have a disability with poverty', 'compare adults over 18 with disabilities with poverty', 'poverty and persons aged 18 or more who are veterans', 'poverty, adults over 18 who are disabled', 'poverty and all the people with disabilities', 'how does poverty relate to all residents with a disability',
    'compare poverty with the ones who live alone', 'compare military veterans with poverty', 'poverty and residents who are female and live here', 'compare people under 18 years old with poverty', 'compare households with one person with poverty', 'compare veteran households with poverty', 'compare households living with a disability with poverty',
    'compara todas las personas con discapacidad con la pobreza', 'pobreza y todos los residentes que viven con una discapacidad', 'compara la pobreza con los que viven solos', 'pobreza: todos los residentes que son veteranos de guerra', 'compara residentes menores de 18 años con la pobreza', 'compara residentes que viven solas en casa con la pobreza',
    'compara hogares con una sola persona con la pobreza', 'compara hogares con niños con la pobreza']);
  left(['poverty among adults over 18 with disabilities', 'poverty among persons aged 18 or more who have a disability', 'poverty among all the people with disabilities', 'poverty among those who live alone', 'poverty among military veterans', 'poverty among households living with a disability', 'poverty among veteran households', 'poverty among households with one person',
    'pobreza entre todas las personas con discapacidad', 'pobreza entre los que viven solos', 'pobreza entre residentes que viven solas en casa', 'pobreza entre residentes menores de 18 años']);
  left(['poverty: women vs those who live alone', 'pobreza: mujeres vs los que viven solos', 'pobreza: mujeres vs hogares con una sola persona', 'poverty: veteran households vs women', 'who has higher poverty, women or those who are veterans', 'poverty: women vs inhabitants who are veterans']);   // two groups, each with its own words, set against each other
  assert.deepStrictEqual(keys('households with children'), ['acs_under18_pct', 'households'], 'the households that a group counts are in its phrase: nothing is left out, as for the other groups beside their total');
  assert.deepStrictEqual(keys('households with veterans'), ['acs_veteran_pct', 'households']);
  assert.deepStrictEqual(keys('households with women'), ['households'], '"residents with women" is not a phrase: with is not a link for women');
  assert.deepStrictEqual(keys.full('hogares con jefatura femenina').dropped.map(d => d.key), ['acs_female_pct'], 'headship says whose households they are: it is not an own word');
  // the rest of a dataset's name that its rule left: a plain word or two next to it, a preposition and a noun, a word joined with a hyphen
  both(['federal funding and women', 'federal funding, women', 'federal funding versus veterans', 'women and health insurance', 'el ingreso del hogar y mujeres', 'el ingreso del hogar, mujeres', 'las viviendas vacías, mujeres', 'empleos en servicios y mujeres', 'propietarios con hipoteca y mujeres', 'women and private-sector jobs', 'tourism-related and women', 'women and self-employed', 'paga anual promedio y mujeres', 'compare employed residents with children', 'compare fema individual with veterans']);
  left(['women and men poverty', 'females and males poverty', 'children and adults poverty', 'veterans and non-veterans poverty', 'women and the general population poverty', 'female versus male poverty', 'women versus the general population poverty', 'poverty men and women', 'poverty among women and men']);   // but a word for people, a counterpart, a word of contrast is not the rest of a name
  // words that put two datasets side by side, beyond "compare": the verbs, "to" and "a" after them, the Spanish "al lado de"
  both(['link women to poverty', 'connect veterans to poverty', 'graph children with poverty', 'pair women with poverty', 'match veterans with poverty', 'combine children with poverty', 'juxtapose women and poverty', 'line up women with poverty', 'mix women with poverty', 'empareja mujeres con la pobreza', 'cruza mujeres con la pobreza',
    'empareja la pobreza al lado de mujeres', 'empareja mujeres a la pobreza']);
  left(['show women with poverty', 'view veterans with poverty', 'muestra mujeres con la pobreza']);   // a verb that does not link leaves "with" to describe the group
  // a word of relation right before a group and a dataset that are named side by side relates them, whatever other dataset stands near the word or before it; with a preposition between them, or with the group in front of the dataset, the group still says whose figure it is
  both(['overlay women on poverty and unemployment', 'overlay women on poverty and show unemployment', 'overlay women on poverty, unemployment', 'show unemployment, overlay women on poverty', 'unemployment: overlay women on poverty', 'unemployment first, then overlay women on poverty', 'superpone mujeres sobre la pobreza y el desempleo', 'muestra el desempleo y superpone mujeres sobre la pobreza', 'overlay veterans and women on poverty and unemployment']);
  left(['overlay poverty among women and unemployment', 'show unemployment, overlay poverty among women', 'overlay female poverty and unemployment', 'overlay women\'s poverty and unemployment']);
  assert.deepStrictEqual(keys('vacancy for veterans, overlay women on poverty'), ['vacancy_pct', 'acs_female_pct', 'poverty_pct'], 'a group before the word of relation stays the breakdown of the dataset it follows');
  // the words that set a group against its counterpart give the answer of "vs"
  for (const w of ['vs', 'vs.', 'v', 'versus', 'against', 'or', 'or else', 'or maybe', 'or perhaps', 'or even', 'or rather', 'or alternatively', 'and/or', '/', 'rather than', 'instead of', 'opposed to', 'as opposed to', 'in contrast to', 'in contrast with', 'unlike', 'than', 'but not', 'and not', 'not including', 'not', 'other than', 'except for', 'except', 'excluding', 'apart from', 'aside from', 'whereas', 'while', 'otherwise than', 'otherwise', 'rather', 'different from', 'different than', 'differently from', 'as against', 'contrasted with', 'contrasted to', 'contrary to', 'in place of', 'in lieu of', 'by contrast with', 'with the exception of', 'compared with', 'compared to', 'as compared to', 'in comparison with', 'in comparison to', 'relative to', 'nor']) { const q = `poverty: women ${w} veterans`; left([q]); assert.deepStrictEqual(keys.full(q).dropped.map(d => d.key), keys.full('poverty: women vs veterans').dropped.map(d => d.key), `"${w}" is read as "vs"`); }
  for (const w of ['o', 'o bien', 'o mas bien', 'u', 'ni', 'contra', 'versus', 'frente a', 'frente al', 'en contraste con', 'a diferencia de', 'a diferencia del', 'en vez de', 'en vez del', 'en lugar de', 'en lugar del', 'con respecto a', 'con respecto al', 'respecto de', 'respecto del', 'respecto a', 'respecto al', 'en comparación con', 'comparadas con', 'comparados a', 'mientras que', 'mientras', 'sino que', 'sino', 'distinto de', 'distintos del', 'diferente a', 'diferentes de', 'diferente del', 'aparte de', 'aparte del', 'más que', 'menos que', 'a excepción de', 'a excepción del', 'con excepción de', 'con excepción del', 'contrario a', 'contrario al', 'al contrario de', 'al contrario del', 'por el contrario', 'sin contar', 'excluyendo', 'en oposición a', 'en oposición al', 'pero no', 'y no', 'excepto', 'salvo']) { const q = `pobreza: mujeres ${w} veteranos`; left([q]); assert.deepStrictEqual(keys.full(q).dropped.map(d => d.key), keys.full('pobreza: mujeres vs veteranos').dropped.map(d => d.key), `"${w}" is read as "vs"`); }
  // a time: the counterpart of a group listed after a colon or a comma, never "women versus 2015" in a sentence
  left(['poverty: women vs 2015', 'poverty, women compared with last year']);
  left(['median income: people with disabilities vs last year', 'el ingreso mediano: mujeres vs el año pasado', 'el ingreso mediano, mujeres comparado con el año anterior', '¿quién tiene más el ingreso mediano, niños o el año pasado?'], 'median_hh_income');
  both(['median rent alongside women compared with 2019', 'commute time or women versus 2015', 'poverty and women versus 2015']);
  assert.deepStrictEqual(keys('la pobreza: mujeres vs toda la población'), ['poverty_pct'], 'round 17: the whole population is the counterpart, and goes with the group');
  assert.deepStrictEqual(keys('poverty and the population of the island and veterans'), ['poverty_pct', 'population', 'acs_veteran_pct'], 'a total counts as the counterpart only through a word of its own, not through another word of the question');
  // a place phrase does not take a group that has a preposition of its own
  left(['rent in poor municipalities in veterans', 'jobs in poor municipalities in people with disabilities', 'home values in poor municipalities in women who are veterans']);
  assert.ok(keys('where do veterans live in poor municipalities').includes('acs_veteran_pct'), 'a group that does the living in the places is placed, as before');
  // a person noun right after a dataset that is compared is the rest of the dataset's name; as the breakdown of an unemployment figure it is still the group's
  left(['unemployed people with disabilities'], 'laus_unemployed');
  assert.deepStrictEqual(p('unemployment and also the totals of women').relPairs, [['acs_female_pct', 'laus_unemp_rate']], '"the totals of women" names the figure of the group itself, a dataset of the question');
  // the strong words are whole words: "side by side" is not "de"
  assert.strictEqual(p('side by side with the pandemic: poverty among women').relPairs.length, 0);
  // each word of the vocabularies of the phrase is needed by a sentence of its own: the nouns before the name (as a relation, and set against another group), the joining and inner words, an age and a quantifier (with two free modifiers, so that a word that is not in the list is the third)
  for (const w of ['people', 'persons', 'person', 'residents', 'resident', 'adults', 'adult', 'individuals', 'individual', 'those', 'ones', 'everyone', 'everybody', 'folks', 'citizens', 'citizen', 'inhabitant', 'islanders', 'families', 'family', 'puerto', 'ricans', 'members', 'member', 'locals', 'neighbors', 'neighbours', 'humans', 'folk', 'dwellers', 'occupants']) { both([`poverty and ${w} with a disability`]); left([`poverty: women vs ${w} with a disability`]); }
  for (const w of ['personas', 'persona', 'residentes', 'residente', 'gente', 'adultos', 'adulto', 'individuos', 'individuo', 'ciudadanos', 'ciudadano', 'habitante', 'familias', 'familia', 'quienes', 'aquellos', 'aquellas', 'boricuas', 'puertorriquenos', 'puertorriquenas', 'islenos', 'islenas', 'miembros', 'miembro', 'vecinos', 'vecino', 'humanos']) { both([`pobreza y ${w} con una discapacidad`]); left([`pobreza: mujeres vs ${w} con una discapacidad`]); }
  for (const w of ['with', 'who', 'that', 'which', 'where', 'of', 'in', 'on', 'are', 'have', 'has', 'having', 'live', 'lives', 'living', 'reside', 'resides', 'a', 'an', 'the', 'some', 'any', 'aged', 'age', 'over', 'under', 'above', 'below', 'older', 'younger', 'more', 'less', 'old', 'years', 'year', 'than']) both([`poverty and people currently ${w} severe disability`]);
  for (const w of ['de', 'del', 'con', 'que', 'donde', 'en', 'sexo', 'genero', 'son', 'tienen', 'tiene', 'viven', 'vive', 'viviendo', 'residen', 'sufren', 'padecen', 'estan', 'un', 'una', 'el', 'la', 'los', 'las', 'alguna', 'anos', 'ano', 'edad', 'mayores', 'menores']) both([`pobreza y personas actualmente ${w} grave discapacidad`]);
  left(['poverty and people really very severe disability']);   // three modifiers are one too many
  for (const w of ['both', 'ambos', 'ambas']) left([`poverty: women vs ${w} people with a disability`]);   // a quantifier before the noun
  for (const w of ['but', 'among', 'amongst', 'for', 'by', 'between', 'entre', 'para', 'por', 'to', 'as', 'like', 'from']) left([`poverty and people ${w} veterans`]);   // a preposition ends the phrase of the group: the noun before it is not its noun
  for (const w of ['men', 'man', 'male', 'males', 'boy', 'boys', 'adults', 'adult', 'youth', 'youths', 'teens', 'teenagers', 'ones', 'everyone', 'everybody', 'others', 'rest', 'civilians']) left([`women and ${w} poverty`]);   // a word for a kind of people before the topic is the counterpart of the group
  for (const w of ['hombres', 'hombre', 'varones', 'varon', 'adultos', 'adulto', 'jovenes', 'joven', 'otros', 'demas', 'civiles']) left([`mujeres y ${w} pobreza`]);
  for (const w of ['last', 'previous', 'prior', 'past', 'baseline', 'year', 'years', 'pasado', 'anterior', 'ano', 'anos']) left([`poverty: women vs ${w}`]);   // a time after a colon is the counterpart of the group
  for (const w of ['rate', 'rates', 'figure', 'figures']) left([`poverty: women vs the ${w} for men`]);
  for (const w of ['tasa', 'tasas', 'cifra', 'cifras']) left([`pobreza: mujeres vs la ${w} de los hombres`]);
  left(['la pobreza: mujeres vs todos', 'la pobreza: mujeres vs todas', 'la pobreza: mujeres vs toda la isla', 'la pobreza: mujeres vs toda la población']);
  both(['compara la pobreza con todos los veteranos', 'compara la pobreza con todas las mujeres', 'compara la pobreza con toda la niñez', 'compare poverty with both women', 'compara la pobreza con ambos veteranos', 'compara la pobreza con ambas mujeres', 'compara la pobreza con las que viven solas']);   // the words of "all" and "both" are light words
  // what closes the name of a group, with the group first so that the words after it stand between it and the other dataset
  both(['compara veteranos de guerra con la pobreza', 'compara personas que viven solas en su casa con la pobreza', 'compare people who live alone at home with poverty', 'compare residents who are female and live here with poverty', 'compara residentes menores de 18 años de edad con la pobreza', 'compara residentes que viven solas en casa con la pobreza', 'compare people under 18 years old with poverty']);
  // the words that link, beside "compare": "to" and "a" after a verb that links, the Spanish "al lado de", the verbs with "with"
  both(['empareja mujeres al desempleo', 'empareja mujeres junto al desempleo', 'juxtapose women with poverty', 'relate women with poverty', 'relates women with poverty', 'related women with poverty', 'relaciona mujeres con la pobreza', 'women and average annual pay', 'compare employed residents alongside women']);
  assert.deepStrictEqual(keys('población al lado de veteranos'), ['population', 'acs_veteran_pct'], 'the total beside a group: both are asked');
  // a place phrase and a group after "en" or "in", with or without an article
  left(['renta en municipios pobres en veteranos', 'rent in poor municipalities in the veterans', 'rent in poor municipalities in all the veterans']);
  left(['women vs veteran residents: poverty'], 'poverty_pct');   // the words that follow the name of a group are in its phrase
  // the rest of a dataset's name: a preposition and one or two plain words, with every connector that may follow; the bounds
  both(['empleos en los servicios y mujeres', 'jobs in the services and women', 'propietarios con hipoteca fija y mujeres', 'empleos en servicios, mujeres', 'federal funding programs and women']);
  for (const c of ['and', 'or', 'vs', 'versus', 'alongside', 'plus']) both([`jobs in services ${c} women`]);
  for (const c of ['y', 'o', 'contra', 'junto a']) both([`empleos en servicios ${c} mujeres`]);
  both([]);   // "with" closes the name after a word that compares (eleventh check)
  left(['propietarios con hipoteca fija anual y mujeres'], 'owner_occupied_pct'); left(['federal funding programs benefits and women'], 'fed_direct_payments'); left(['poverty and people or veterans', 'renta en municipios pobres en los veteranos', 'poverty and relatively women', 'poverty: women instead of the typical resident', 'poverty: women instead of the typical person']);   // a word after a group is not the rest of the group's name   // three plain words are too many; "or" is not part of an age; a group after "en los" has its own preposition
  left(['compare veterans people residents families folks with poverty']);   // four nouns after a group are too many for its phrase
  both(['compare veterans people residents families with poverty', 'compare disabled persons with poverty', 'compare female citizens with poverty', 'compare households with a single person with poverty', 'compare households with 1 person with poverty', 'compara hogares con 1 persona con la pobreza', 'poverty and military veterans', 'poverty and war veterans']);
  both(['compare veterans in the population with poverty', 'compare women of the population with poverty', 'compare women among the population with poverty', 'compare women within the population with poverty', 'compare veterans in all the households with poverty', 'overlay veterans in the population on poverty', 'compara mujeres en la poblacion con la pobreza', 'compara mujeres de la poblacion con la pobreza', 'compara mujeres entre la poblacion con la pobreza', 'compara veteranos en los hogares con la pobreza', 'compara mujeres en toda la poblacion con la pobreza', 'compara mujeres en todos los hogares con la pobreza', 'superpone veteranos en la poblacion sobre la pobreza']);   // the total that a group counts, with the word that joins it to the group, is part of the group's phrase
  left(['poverty: women in the population vs men', 'poverty: women in the population vs the whole population', 'pobreza: mujeres en la poblacion vs hombres']);
  both(['compare self-employed residents with children', 'compare for me employed residents with children', 'compare the ones that really employed residents with children', 'median rent: women vs 300']);   // a word that compares is up to four words before the dataset
  left(['compare the ones that I really employed residents with children'], 'qcew_jobs');
  left(['el ingreso familiar: mujeres vs el año pasado'], 'median_hh_income');   // the rest of a name is not between a dataset and a group listed after a colon
  left(['poverty: women vs veterans residents or children', 'women versus the mainland poverty', 'women vs mainland poverty']);   // the words that follow a word of contrast are the counterpart's
  assert.ok(keys('jobs in poor municipalities in Ponce with veterans').includes('acs_veteran_pct'), 'a group that does not follow the place directly is placed');
  // the rest of a name, more shapes: a preposition of each kind, a connection after it, a word of contrast; the phrase of two groups; the topics that a rank word closes
  both(['rent per square foot and women', 'jobs with benefits and women', 'empleos de servicios y mujeres', 'jobs on weekends and women', 'el ingreso del hogar junto a mujeres', 'compare women and veterans persons with poverty']);
  left(['plot women with the highest poverty against last year', 'compara mujeres con mayor pobreza por pueblo', 'poverty: women vs 1999']);
  both(['compare, by municipality, the share of women with poverty', 'compare across municipalities the share of women with poverty', 'compare per municipality the share of women with poverty', 'compare in each municipality the share of women with poverty', 'compare by the municipality the share of women with poverty', 'compare by town the share of women with poverty', 'compare across towns the share of women with poverty',
    'compara por municipio el porcentaje de mujeres con la pobreza', 'compara por municipios el porcentaje de mujeres con la pobreza', 'compara por pueblo el porcentaje de mujeres con la pobreza', 'compara por pueblos el porcentaje de mujeres con la pobreza', 'compara en cada municipio el porcentaje de mujeres con la pobreza', 'compara por los municipios el porcentaje de mujeres con la pobreza', 'compara por el pueblo el porcentaje de mujeres con la pobreza']);   // where the answer is cut is not a word between the verb and the datasets, whichever way it is said
  both(['how does poverty relate to women who live alone', 'how does poverty relate to women that live alone', 'la pobreza se relaciona con mujeres que viven solas', 'la pobreza se relaciona con mujeres que son veteranas']);   // a relative pronoun between two groups is not the rest of a dataset's name
  both(['compare me the share of veterans with children with poverty', 'compara me el porcentaje de veteranos con niños con la pobreza', 'compare me the share of veterans who live alone with poverty', 'compare me the share of veterans that live alone with poverty', 'compara me el porcentaje de veteranos que viven solos con la pobreza']);   // the words that join the parts of a group's name are not among the words that stand between the verb and the group
  assert.ok(keys('jobs in poor municipalities in Ponce near veterans').includes('acs_veteran_pct'), 'a group that does not follow the place directly is placed');
  // what the mutation check of the tenth review asked to pin: "residents" against a group, the window of a word of relation, how far a group is beside another, a group tied to a group that is left out and to a dataset, "the rest of the population", how far a total is from the household type it counts, a comma between a total and its group
  left(['poverty: women vs residents', 'poverty: women versus the residents', 'poverty: veterans vs all residents', 'poverty: women or residents', 'who has higher poverty, women or residents']);
  both(['overlay across the island veterans on poverty']);
  left(['overlay for me all over the whole island veterans on poverty']);
  assert.deepStrictEqual(keys('poverty among women zeta eta theta iota veterans'), ['poverty_pct'], 'a group four words after the group that is the breakdown is part of it');
  assert.deepStrictEqual(keys('poverty among women zeta eta theta iota kappa lambda veterans'), ['poverty_pct'], 'six words');
  assert.deepStrictEqual(keys('poverty among women zeta eta theta iota kappa lambda mu veterans'), ['poverty_pct', 'acs_veteran_pct'], 'but not seven');
  assert.deepStrictEqual(keys('poverty among veterans near women and unemployment'), ['poverty_pct', 'laus_unemp_rate'], 'round 17: the first dataset in the order of the words decides: women are the breakdown of poverty');
  assert.deepStrictEqual(keys('rent zeta eta theta iota kappa, correlation of poverty among women'), ['median_gross_rent', 'poverty_pct'], 'another dataset five words before the word of relation: the word is about that one, and women are the breakdown of poverty');
  assert.deepStrictEqual(keys('rent zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau, correlation of poverty among women'), ['median_gross_rent', 'poverty_pct'], 'round 17: "among" makes the group the breakdown');
  assert.deepStrictEqual(keys('correlation of poverty among women zeta eta theta iota kappa lambda mu with the population'), ['poverty_pct', 'population'], 'round 17: the group is the breakdown of poverty');
  for (const q of ['poverty: women vs the rest of the population', 'poverty and women versus the rest of the population', 'women versus the rest of the population: poverty', 'poverty among women and the rest of the population', 'la pobreza: mujeres vs el resto de la poblacion']) { left([q]); assert.ok(!keys(q).includes('population'), `"the rest of the population" is the counterpart, not a dataset: ${q}`); }


  assert.deepStrictEqual(keys('households zeta eta theta iota kappa people living alone'), ['households', 'acs_living_alone_pct'], 'five words: they are');
  assert.deepStrictEqual(keys('people living alone zeta eta theta iota households'), ['acs_living_alone_pct', 'households']);   // round 17: outside the group's phrase the households are a dataset of their own
  assert.deepStrictEqual(keys('people living alone zeta eta theta iota kappa households'), ['acs_living_alone_pct', 'households']);
  assert.deepStrictEqual(keys('the population, people with disabilities'), ['population', 'acs_disability_pct'], 'a comma between a total and its group names both');
  assert.deepStrictEqual(keys('hogares; personas que viven solas'), ['households', 'acs_living_alone_pct']);
  // the word of relation right before a group and a dataset: how far, what stands between, which groups
  assert.deepStrictEqual(keys('show unemployment, overlay across the island women on poverty'), ['laus_unemp_rate', 'acs_female_pct', 'poverty_pct'], 'three words between the word and the group');
  assert.deepStrictEqual(keys('show unemployment, overlay for me all over the whole island women on poverty'), ['laus_unemp_rate', 'poverty_pct'], 'seven words are too many: the group is the breakdown of the first dataset');
  assert.deepStrictEqual(keys('show unemployment, overlay last year women on poverty'), ['laus_unemp_rate', 'poverty_pct'], 'a time between the word and the group: the word is about the time');
  assert.deepStrictEqual(keys('poverty among women zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma correlated with income'), ['poverty_pct', 'median_hh_income'], 'a word of relation between a group and a dataset, far from the dataset that the group qualifies, still leaves the group the breakdown: only a word right before them counts');
  assert.deepStrictEqual(keys('correlate poverty and seniors among unemployment'), ['poverty_pct', 'laus_unemp_rate'], 'the elderly keep their own rule: "among" makes them the breakdown');
  assert.deepStrictEqual(keys('show unemployment, overlay women on the population'), ['laus_unemp_rate'], 'round 17: the group is the breakdown of unemployment and its total goes with it');
  assert.deepStrictEqual(keys('show vacancy, overlay where veterans live and poverty'), ['vacancy_pct', 'poverty_pct'], 'a place phrase is not a partner');
  assert.deepStrictEqual(keys('overlay the population on veterans and unemployment'), ['population', 'acs_veteran_pct', 'laus_unemp_rate'], 'the total and the group that a word of relation puts side by side are both asked, whatever else the question holds');
  assert.deepStrictEqual(keys('overlay households on people living alone and unemployment'), ['households', 'acs_living_alone_pct', 'laus_unemployed']);
  assert.deepStrictEqual(keys('overlay across the island the population on veterans'), ['population', 'acs_veteran_pct'], 'a word of relation three words before a total and its group');
  assert.deepStrictEqual(keys('overlay across the island households on people living alone'), ['households', 'acs_living_alone_pct']);
  assert.deepStrictEqual(keys('compare the population with high people with disabilities'), ['acs_disability_pct'], 'round 17: the total before "with" and a group is the group\'s');
  const blank = keys.env.chBlank;   // the words of a phrase are blanked in the text that starts at `at`: a phrase that starts before it is cut there, one that ends after it at the end of the text
  assert.strictEqual(blank('abcdef', 3, [{ ps: 1, pe: 5 }]), '  cdef');
  assert.strictEqual(blank('abcdef', 3, [{ ps: 4, pe: 99 }]), 'a     ');
  assert.strictEqual(blank('abcdef', 0, [{ pos: 1, end: 3 }]), 'a  def', 'a group with no phrase is blanked by its name');
});
test('chat: eleventh check: whose figure it is after a noun outside the lists, a relation with a year, a plain preposition or a preposition inside a dataset\'s name between the datasets, a total inside the group\'s phrase, the average rate as the counterpart', () => {
  const keys = chatEnv(), p = keys.parse, GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const left = (list, topic = 'poverty_pct') => { for (const q of list) { const r = keys.full(q); assert.ok(r.keys.includes(topic) && !r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}": the group says whose figure it is, the topic stays: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.deepStrictEqual(p(q).relPairs, [], `"${q}" relates nothing`); } };
  const both = (list, topic = 'poverty_pct') => { for (const q of list) { const r = keys.full(q), s = p(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.includes(topic) && r.dropped.length === 0, `"${q}" asks for the group and the topic side by side: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!s.related, true, q); } };
  const own = (list, topic = 'poverty_pct') => { for (const q of list) { const r = keys.full(q), s = p(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.includes(topic) && !r.keys.includes('population') && !r.keys.includes('households') && r.dropped.length === 0, `"${q}": the group's own total is no dataset of the question: ${r.keys}`); assert.ok(s.relPairs.length > 0 && s.relPairs.every(([a, b]) => b === topic || a === topic), `"${q}" relates the group and the topic only: ${JSON.stringify(s.relPairs)}`); } };
  // a noun that no list holds, then "of ... with": the group says whose figure it is; the "with" that closes a name stays for the names that "per", "por" and "en" make, and after a word that compares
  left(['poverty of immigrants with disabilities', 'poverty of retirees with disabilities', 'the poverty of immigrants with disabilities', 'pobreza de jubilados con discapacidad', 'la pobreza de los jubilados con discapacidad']);
  left(['home values of retirees with children', 'el valor de la vivienda de jubilados con niños'], 'median_home_value'); left(['rent of students with children'], 'median_gross_rent'); left(['median income of tenants with children'], 'median_hh_income'); left(['unemployment of retirees with children'], 'laus_unemp_rate');
  left(['compara empleos del sector con mujeres'], 'qcew_jobs');   // round 17: "with" never closes a dataset's name
  left(['jobs in services with women', 'empleos en servicios con mujeres'], 'qcew_jobs'); left(['poverty in immigrants with disabilities', 'poverty on retirees with children', 'pobreza en jubilados con discapacidad']);   // without a word that compares, whatever the preposition, the group says whose figure it is
  both([], 'qcew_jobs');
  assert.deepStrictEqual(keys('jobs per resident with children'), ['jobs_per_employed_resident']);   // round 17: "with" never closes a dataset's name; the group is the breakdown
  // an explicit relation with a year phrase, a plain preposition or a preposition inside the other dataset's name between the two
  both(['overlay women in 2020 on poverty', 'correlate women in 2020 with poverty', 'scatter women in 2020 against poverty', 'overlay veterans in 2015 on poverty', 'superpone mujeres en 2020 sobre la pobreza']);
  both(['overlay poverty over women', 'overlay poverty onto women', 'superpone la pobreza sobre mujeres', 'superpone la pobreza encima de mujeres']); left(['overlay poverty atop women', 'overlay poverty above women', 'overlay poverty under women']);   // round 17: only the words of the rule
  both(['overlay veterans on the cost of rent', 'correlaciona veteranos con el costo del alquiler'], 'median_gross_rent'); both([], 'qcew_jobs');
  for (const w of ['over',  'onto']) both([`overlay poverty ${w} women`]);   // round 17: only the words of the rule put the two side by side
  for (const w of ['atop',  'above',  'below',  'under',  'beneath',  'upon',  'into',  'through',  'across',  'around',  'behind',  'from',  'via',  'toward',  'towards',  'without',  'after',  'before',  'during',  'since',  'until',  'about']) left([`overlay poverty ${w} women`]);
  for (const w of ['sobre']) both([`superpone la pobreza ${w} mujeres`]);   // round 17: "sobre" is a word of the rule
  for (const w of ['encima',  'debajo',  'tras',  'ante',  'hacia',  'desde',  'hasta',  'sin',  'segun',  'mediante',  'durante',  'dentro',  'fuera',  'detras',  'delante']) left([`superpone la pobreza ${w} mujeres`]);
  for (const w of ['encima']) both([`superpone la pobreza ${w} de mujeres`]);   // round 17: "encima de" is a word of the rule
  for (const w of ['debajo',  'detras',  'delante',  'dentro',  'fuera',  'lejos',  'alrededor',  'antes',  'despues']) left([`superpone la pobreza ${w} de mujeres`]);
  both(['overlay poverty on top of women']);
  left(['la pobreza del jubilado con discapacidad']);
  both(['overlay women by municipality on poverty', 'overlay women in each town on poverty', 'overlay women between 2015 and 2020 on poverty', 'superpone mujeres por municipio sobre la pobreza']);   // a place, a scope or a range of years between the two: the preposition is theirs, not of whose figure it is
  left(['overlay poverty among women', 'overlay women in 2020 among poverty', 'overlay poverty among the women', 'overlay poverty in Ponce among women', 'overlay poverty among all women', 'superpone la pobreza entre las mujeres', 'superpone la pobreza entre los veteranos', 'superpone la pobreza entre todas las mujeres', 'superpone la pobreza entre todos los veteranos', 'superpone la pobreza de la niñez']);   // a preposition right before the second of the two, with its articles, is still one
  // the total inside the group's phrase is one dataset with the group when another dataset is asked; named beside the group it is a dataset of the question
  own(['correlate the veteran population with poverty', 'scatter the veteran population against poverty', 'relationship between the female population and poverty', 'relationship between households living alone and poverty', 'correlate population with a disability with poverty', 'compare population with disabilities with poverty', 'relación entre la población femenina y la pobreza', 'correlaciona la población de veteranos con la pobreza', 'compara la población con discapacidad con la pobreza']);
  own(['compare inhabitants with disabilities with home values'], 'median_home_value');
  assert.deepStrictEqual(keys('compare population with veterans'), ['population', 'acs_veteran_pct'], 'no other dataset: the total and the group are compared');
  assert.deepStrictEqual(keys('households alongside people living alone and poverty'), ['households', 'acs_living_alone_pct', 'poverty_pct'], 'the total named before the phrase of the group, with a word that is not one of its own');
  assert.deepStrictEqual(keys('veterans alongside the population and poverty'), ['acs_veteran_pct', 'population', 'poverty_pct'], 'and after it');
  assert.deepStrictEqual(keys('correlate population with children as well as the elderly'), ['acs_under18_pct', 'age65_pct'], 'round 17: "population with children" is the children\'s total');
  assert.deepStrictEqual(keys('correlate population with veterans and households'), ['population', 'acs_veteran_pct', 'households'], 'another total is not another dataset');
  assert.deepStrictEqual(keys('overlay the population on veterans and unemployment'), ['population', 'acs_veteran_pct', 'laus_unemp_rate'], '"on" is the word of the overlay, not of the group');
  // what the mutation check of the eleventh review asked to pin: a short word that the dataset's rule left, a dataset between the compare word and the datasets, a year that filters, the dataset first, "el más alto", the total between a group and its counterpart, the pair of a total and its group, a long chain of own words
  both(['federal aid and women'], 'fed_awards_total');
  left([]);
  assert.deepStrictEqual(keys('link zeta eta theta iota kappa poverty to women'), ['poverty_pct', 'acs_female_pct'], 'the dataset first: the words before it are its name');
  both(['compare in 2020 women with poverty', 'compare since 2015 women with poverty', 'compara en 2020 mujeres con la pobreza']);
  assert.deepStrictEqual(keys('show unemployment, overlay in 2020 women on poverty'), ['laus_unemp_rate', 'acs_female_pct', 'poverty_pct']);
  left(['la pobreza: mujeres vs el más alto', 'la pobreza: mujeres vs el más bajo']);
  assert.deepStrictEqual(keys('women vs the whole population: poverty'), ['poverty_pct']); assert.deepStrictEqual(keys('veterans vs the whole population: rent'), ['median_gross_rent']);   // round 17: the counterpart goes with the group
  assert.deepStrictEqual(p('population and veterans').relPairs, [['acs_veteran_pct', 'population']], 'a total and the group named side by side are related');
  both(['poverty and people who are aged over 18 or more with a disability']); left([`poverty and people ${'who are '.repeat(12)}with a disability`]);
  both(['superpone veteranos sobre el nivel de pobreza', 'superpone mujeres sobre la tasa de pobreza', 'superpone veteranos sobre los niveles de pobreza']); both(['superpone mujeres sobre el nivel de desempleo'], 'laus_unemp_rate');   // "de" inside the dataset's name is no preposition of whose figure it is
  both(['women scatter poverty', 'show veterans overlapping poverty', 'mujeres correlacionadas pobreza']); both(['children overlay median income', 'compare children scatter median income', 'compara niños scatter ingreso mediano'], 'median_hh_income'); both([], 'qcew_jobs');   // a word that compares right after the group is no rest of its name
  // the average rate and the level of the island are the counterpart of the group
  left(['poverty: women vs the average rate', 'poverty: women vs the level of the island', 'la pobreza: mujeres vs el nivel de la isla', 'la pobreza: mujeres vs los niveles de la isla', 'la pobreza: mujeres vs la tasa promedio', 'la pobreza: mujeres vs la tasa mediana', 'la pobreza: mujeres vs la tasa media', 'poverty: women vs the levels for men']);
  left(['muéstrame el valor de la vivienda: veteranos de guerra versus la tasa promedio?', 'qué tal el valor de la vivienda: quienes que viven con discapacidad versus el nivel de la isla en Ponce'], 'median_home_value');
  // "rico" of Puerto Rico is no income; "la media" is no information job
  for (const q of ['Puerto Rico overall', 'Puerto Rico total', 'la media', 'Puerto Rico en conjunto']) assert.deepStrictEqual(keys(q), [], q);
  assert.deepStrictEqual(keys('poverty in Puerto Rico overall'), ['poverty_pct']);
});
test('chat: twelfth check: the last preposition decides whose figure it is, "of" after a statistic before a group, "with" when places or years are compared, the total before "with", words that link', () => {
  const keys = chatEnv(), p = keys.parse, e = keys.env, GROUPKEYS = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct', 'acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
  const left = (list, topic = 'poverty_pct') => { for (const q of list) { const r = keys.full(q); assert.ok(r.keys.includes(topic) && !r.keys.some(k => GROUPKEYS.has(k)) && r.dropped.length > 0, `"${q}": the group says whose figure it is, the topic stays: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.deepStrictEqual(p(q).relPairs, [], `"${q}" relates nothing`); } };
  const both = (list, topic = 'poverty_pct') => { for (const q of list) { const r = keys.full(q), s = p(q); assert.ok(r.keys.some(k => GROUPKEYS.has(k)) && r.keys.includes(topic) && r.dropped.length === 0, `"${q}" asks for the group and the topic side by side: ${r.keys} | left out ${r.dropped.map(d => d.text)}`); assert.strictEqual(!!s.related, true, q); } };
  // B1: a word between the preposition and the group (a determiner, a quantifier, an adjective) does not hide the preposition
  for (const w of ['these', 'those', 'many', 'most', 'some', 'our', 'local', 'only', 'just the', 'all the']) left([`overlay poverty among ${w} women`, `overlay poverty for ${w} veterans`]);
  left(['overlay poverty of only women', 'superpone la pobreza entre esas mujeres', 'superpone la pobreza entre muchas mujeres', 'superpone la pobreza para nuestras veteranas', 'superpone la pobreza entre solo las mujeres']);
  left(['overlay rent for our veterans', 'correlaciona el alquiler para muchos veteranos'], 'median_gross_rent'); left(['correlate rent within most veterans'], 'median_gross_rent');
  assert.strictEqual(p('correlate poverty among most women in Ponce').intent !== 'compare', true, 'no compare of the group and the topic');
  // B2: "of"/"de" after a statistic of the first dataset is whose figure it is when a group follows; "the share of" a group is the share
  left(['superpone el ingreso mediano de las mujeres', 'superpone el ingreso promedio de las mujeres', 'correlaciona el ingreso mediano de los veteranos'], 'median_hh_income');
  left(['superpone el ingreso per cápita de las mujeres', 'overlay income per capita of women'], 'per_capita_income');
  left(['overlay the poverty rate of women']);
  both(['poverty correlated with the share of women', 'correlate poverty with the percentage of veterans', 'superpone la pobreza sobre el porcentaje de mujeres']);
  both(['overlay women on the share of people in poverty', 'correlate women with the share of people in poverty', 'overlay women on people in poverty']);   // "people in" is the name of the dataset after it
  // B3: "with" does not close a name when the question compares places, a scope or years after the group
  left(['compare poverty of retirees with disabilities across municipalities', 'compare the poverty of retirees with disabilities by town', 'compara la pobreza de jubilados con discapacidad por pueblo', 'compare poverty of retirees with disabilities in 2015 and 2020']);
  e.setApi({ places: () => ['Ponce', 'Mayagüez', 'Caguas', 'Puerto Rico'], meta: () => ({}), datasets: () => [] });
  try {
    for (const q of ['compare poverty of retirees with disabilities in Ponce and Mayagüez', 'compara la pobreza de jubilados con discapacidad en Ponce y Mayagüez', 'compare poverty of retirees with children in Ponce, Mayagüez and Caguas']) { const r = p(q); assert.deepStrictEqual(r.keys, ['poverty_pct'], q); assert.deepStrictEqual(r.relPairs, [], q); }
    assert.deepStrictEqual(p('compare women with poverty in Ponce and Mayagüez').relPairs, [['acs_female_pct', 'poverty_pct']], 'a group named with a word that compares stays related');
  } finally { e.setApi(null); }
  both([]); both([], 'median_hh_income');   // the word that compares stands before the first of the two, more than four words before the group
  // B4: the total before "with" or "sobre" stays a dataset unless "with" follows the group
  for (const q of ['compare population with veterans and poverty', 'correlate population with veterans and poverty', 'compare total population with veterans and poverty', 'compara la población con veteranos y la pobreza', 'superpone la población sobre veteranos y la pobreza']) assert.deepStrictEqual(keys(q), ['population', 'acs_veteran_pct', 'poverty_pct'], q);
  for (const q of ['compare population with disabilities with poverty', 'correlate population with a disability with poverty', 'compara la población con discapacidad con la pobreza']) assert.deepStrictEqual(keys(q), ['acs_disability_pct', 'poverty_pct'], q);
  // words that link: "vincula", and signs after a word that compares
  both([]); both([], 'vacancy_pct'); both([], 'median_home_value');
  // what stays: a place, a scope or a year before the last preposition, a connector after a preposition
  both(['overlay women by municipality on poverty', 'overlay women between 2015 and 2020 on poverty', 'overlay poverty next to women', 'overlay poverty on top of women']); left(['overlay poverty in Ponce among women']);
  // the words of the lists of round 16, each in a loop (the mutation check of round 16)
  // round 17: the loops of plain prepositions after a place are gone with the rule they tested (chWhoseGap)
  // round 17: the loops of plain prepositions after a place are gone with the rule they tested (chWhoseGap)
  for (const w of ['share', 'shares', 'percentage', 'percentages', 'percent', 'proportion', 'proportions', 'number', 'numbers', 'count', 'counts']) both([`poverty correlated with the ${w} of women`]);
  for (const w of ['porcentaje', 'porcentajes', 'proporcion', 'numero', 'cantidad']) both([`la pobreza correlacionada con el ${w} de mujeres`]);
  for (const w of ['people', 'persons', 'residents']) both([`overlay women on ${w} in poverty`]);
  for (const w of ['personas', 'gente', 'residentes']) both([`superpone mujeres sobre ${w} en pobreza`]);
  both(['superpone mujeres encima de la pobreza']);   // a preposition of two words before a dataset
  both([], 'median_gross_rent');   // a word of the name of what follows stops the reading
  left(['map median income relationship between median income de women'], 'median_hh_income');   // a word of relation between them, then a statistic and "de" before the group
  for (const q of ['overlay the population onto veterans and poverty', 'overlay the population over veterans and poverty', 'superpone la población encima de veteranos y la pobreza']) assert.ok(keys(q).includes('population'), q);
  // the total inside the group's phrase is the group's whatever else is asked
  assert.deepStrictEqual(keys('correlate the veteran population with households'), ['acs_veteran_pct', 'households']);
  assert.deepStrictEqual(keys('relationship between the female population and households'), ['acs_female_pct', 'households']);
  assert.deepStrictEqual(keys('correlate the population of people with disabilities'), ['acs_disability_pct']);
  e.setApi({ places: () => ['Ponce', 'Mayagüez', 'Caguas', 'Puerto Rico'], meta: () => ({}), datasets: () => [] });
  try {
    for (const q of ['compare poverty of retirees with disabilities in Ponce, Mayagüez', 'compare poverty of retirees with disabilities in Ponce or Mayagüez', 'compara la pobreza de jubilados con discapacidad en Ponce o Mayagüez', 'compare poverty of retirees with disabilities in Ponce vs Mayagüez', 'compare poverty of retirees with disabilities over time']) assert.deepStrictEqual(p(q).relPairs, [], q);
  } finally { e.setApi(null); }
});
test('chat: round 17, the conservative rule (owner decision of 2026-10-12): the wordings whose answer it changed, with their answers now', () => {
  // a group main had no dataset for is related to another dataset only when the words between them are a list word ("and", a comma, "vs", "then", "next to"), a phrase of relation ("correlated with", "related to", "relacionada con"), or "with", "to", "on", "sobre", "against" after a word that compares standing before both; anything else makes it the breakdown, with the note
  const p = chatEnv().parse;
  for (const [q, k, rel] of [
    ["combine the following: vacancy with retirees with disabilities", ["vacancy_pct"], []],
    ["compara empleos en servicios con mujeres", ["qcew_jobs"], []],
    ["compara empleos por residente con mujeres", ["qcew_jobs"], []],
    ["compare Women and girls, % of all people with poverty", ["poverty_pct"], []],
    ["compare households with people living alone", ["acs_living_alone_pct"], []],
    ["compare jobs in services overlay women", ["qcew_jobs"], []],
    ["compare jobs in services with women", ["qcew_jobs"], []],
    ["compare poverty of immigrants with disabilities", ["poverty_pct"], []],
    ["compare the median household income of retired immigrants with children", ["median_hh_income"], []],
    ["correlaciona veteranos con el tiempo de viaje al trabajo", ["qcew_jobs"], []],
    ["correlación de la pobreza para mujeres", ["poverty_pct"], []],
    ["correlación del desempleo para mujeres", ["laus_unemp_rate"], []],
    ["correlación entre la pobreza para mujeres", ["poverty_pct"], []],
    ["correlate women in Ponce with poverty", ["poverty_pct"], []],
    ["correlation between poverty for women", ["poverty_pct"], []],
    ["hogares en contraste con mujeres", ["households"], []],
    ["overlay for me all over the island veterans on poverty", ["poverty_pct"], []],
    ["overlay poverty out of women", ["poverty_pct"], []],
    ["overlay women among the median rent", ["median_gross_rent"], []],
    ["overlay women in Ponce on poverty", ["poverty_pct"], []],
    ["overlay women out of poverty", ["poverty_pct"], []],
    ["plot poverty, people with disabilities with vacancy", ["poverty_pct", "acs_disability_pct", "vacancy_pct"], [["acs_disability_pct", "poverty_pct"]]],
    ["pobreza aparte de mujeres", ["poverty_pct"], []],
    ["pobreza cerca de mujeres", ["poverty_pct"], []],
    ["pobreza en contraste con mujeres", ["poverty_pct"], []],
    ["pobreza frente a mujeres", ["poverty_pct"], []],
    ["pobreza: mujeres versus la poblacion entera", ["poverty_pct"], []],
    ["pobreza: mujeres versus la poblacion total", ["poverty_pct"], []],
    ["por favor vincula en el mapa el valor de la vivienda con pacientes con discapacidad", ["median_home_value"], []],
    ["poverty among households living alone", ["poverty_pct"], []],
    ["poverty apart from women", ["poverty_pct"], []],
    ["poverty for households of people living alone", ["poverty_pct"], []],
    ["poverty where women live", ["poverty_pct"], []],
    ["poverty wherever veterans live", ["poverty_pct"], []],
    ["poverty with people who live alone", ["poverty_pct"], []],
    ["poverty with veterans", ["poverty_pct"], []],
    ["poverty: women versus the population as a whole", ["poverty_pct"], []],
    ["relationship of poverty for women", ["poverty_pct"], []],
    ["superpone la pobreza cerca de las mujeres", ["poverty_pct"], []],
    ["superpone las mujeres debajo de la pobreza", ["poverty_pct"], []],
    ["superpone mujeres en Ponce sobre la pobreza", ["poverty_pct"], []],
    ["unemployment among the population with a disability", ["laus_unemp_rate"], []],
    ["veterans apart from households", ["households"], []],
    ["vincula la pobreza con jubilados con discapacidad", ["poverty_pct"], []],
    ["vincula la pobreza con jubilados con niños", ["poverty_pct"], []],
    ["what happens to poverty when women increase", ["poverty_pct"], []]
  ]) { const r = p(q); assert.deepStrictEqual([r.keys, r.relPairs], [k, rel], q); }
});
test('chat: round 24 (twentieth check): the list form by its shape, and the total set against a left-out group goes with it', () => {
  const p = chatEnv().parse;
  const none = (list) => { for (const q of list) assert.deepStrictEqual(p(q).relPairs, [], q); };
  none(['poverty, these women vs the share of men', 'poverty: only women vs all households', 'poverty; these women vs the 2010s', 'la pobreza: solo las mujeres vs todos los hogares', 'poverty & women vs the male population',
    'poverty and women vs the share of men', 'poverty and women vs the rate for non-veterans', 'poverty, half of the women vs the 2010s', 'poverty, nearly all veterans vs everyone else']);   // H1
  for (const q of ['poverty; women vs all households', 'poverty: veterans vs veteran households']) assert.deepStrictEqual(p(q).keys, ['poverty_pct'], q);   // H2
  for (const q of ['poverty and women versus 2015', 'poverty and women compared to last year', 'poverty & women vs the 2010s', 'poverty and some women', 'poverty, some women', 'compare poverty with some women', 'poverty, these women', 'poverty: only women']) assert.ok(p(q).relPairs.length, q);   // "and" with a time, and lists with any determiner, still relate
  none(['poverty for women vs the 2010s', 'poverty among these women vs the share of men']);   // a preposition makes the gap more than a list: the group is whose figure
  none(['poverty women vs the 2010s']);   // no word between the dataset and the group: a list too
  for (const q of ['poverty and women vs a decade ago', 'la pobreza y mujeres vs antes de María']) assert.ok(p(q).relPairs.length, q);   // "and" with a time
  assert.ok(p('poverty: women vs all the other households').keys.includes('households'));   // three words before the total: it stays
  for (const q of ['la pobreza y algunas mujeres', 'la pobreza, algunos veteranos']) assert.ok(p(q).relPairs.length, q);   // "algunos", "algunas" before the group
});
test('chat: round 23 (nineteenth check): "the rate for men" with a determiner or "and" before the group, and a total as the counterpart', () => {
  const p = chatEnv().parse;
  const none = (list) => { for (const q of list) assert.deepStrictEqual(p(q).relPairs, [], q); };
  none(['poverty, all women vs the rate for men', 'poverty, all women against the rate for men', 'vacancy, all living alone against the rate for men', 'poverty, most veterans against the level of the island', 'poverty and women vs the rate for men', 'poverty, many women vs the 2010s', 'la pobreza, todas las mujeres frente a la tasa de los hombres']);   // G1
  none(['poverty: women vs all households', 'poverty, women vs other households', 'poverty: women vs the typical household', 'rent: women vs the male population', 'poverty: women vs the population at large', 'la pobreza: mujeres vs todos los hogares', 'la pobreza: mujeres vs la población masculina', 'poverty and women vs all households']);   // G2
  for (const q of ['poverty and women versus 2015', 'poverty: women versus total jobs', 'poverty: women vs unemployment', 'poverty, all women']) assert.ok(p(q).relPairs.length, q);   // "and" with a year, the front of a dataset's name, a dataset, a list
  none(['poverty and women vs the figure for men', 'poverty and women vs the level of the island', 'la pobreza y mujeres vs la cifra de los hombres', 'la pobreza y mujeres vs los niveles de la isla', 'la pobreza y mujeres vs el nivel de la isla',
    'la pobreza y mujeres vs la tasa promedio', 'la pobreza y mujeres vs la tasa mediana', 'la pobreza y mujeres vs el más alto', 'poverty: women and the population as a whole']);   // the counterparts that free() reads after "and"
  none(['poverty, all women vs the 2010s', 'poverty, most women vs a decade ago', 'la pobreza, todas las mujeres vs la década pasada', 'la pobreza, muchas mujeres vs la década pasada']);   // determiners after a comma
  for (const q of ['overlay women on those new local poverty', 'compare women with persons regional local rent', 'overlay women on residentes new local poverty', 'compare women with gente regional local rent']) assert.ok(p(q).relPairs.length, q);   // a word chGapCore strips, before the front of a name
  none(['la pobreza y mujeres vs todos los hogares', 'el alquiler y los veteranos vs todos los hogares']);   // "y" and an article before the group
  for (const q of ['link veterans compared with households', 'compare ninos against hogares across municipalities']) assert.ok(p(q).relPairs.length, q);   // outside a list, a total after a word of contrast is read as before
});
test('chat: round 22 (eighteenth check): after a colon or a comma whatever follows a word of contrast is the counterpart; "against" relates only with describing words in front of the dataset', () => {
  const p = chatEnv().parse;
  const none = (list) => { for (const q of list) assert.deepStrictEqual(p(q).relPairs, [], q); };
  none(['poverty: women vs the 2010s', 'poverty: women vs in the 2000s', 'poverty: women versus an earlier year', 'poverty, women compared with a few years ago', 'poverty: the female population unlike two years ago', 'poverty: the female population unlike pre-Maria', 'poverty: the female population unlike after the hurricane']);   // F1
  none(['compare women against Puerto Rico poverty', 'compara mujeres contra el continente pobreza', 'compara mujeres contra Estados Unidos pobreza', 'compara mujeres contra los estados pobreza', 'compara mujeres contra la nación pobreza']);   // F2
  for (const q of ['compare women against local poverty', 'compare women against statewide poverty', 'compare women against current poverty', 'compare women against regional rent', 'compara mujeres contra el nuevo alquiler', 'poverty: women vs unemployment', 'poverty: women and show it on the map', 'poverty: women in Ponce']) assert.ok(p(q).relPairs.length, q);
  assert.ok(p('poverty: women vs pre-Maria unemployment').relPairs.length);   // two words in front of a dataset are the front of its name
  none(['poverty: women vs earlier rates of unemployment']);   // three are a counterpart
  none(['poverty: women, vs the 2010s', 'la pobreza: mujeres, frente a la década pasada']);   // a comma before the word of contrast
  assert.ok(!p('muestra the average but not ninos, jobs').keys.includes('acs_under18_pct'));   // the group set against the average is left out
});
test('chat: round 21 (seventeenth check): a place a group is set against after "against", and the times a group is set against after a colon or a comma', () => {
  const p = chatEnv().parse;
  const none = (list) => { for (const q of list) assert.deepStrictEqual(p(q).relPairs, [], q); };
  none(['compare women against the mainland poverty', 'compare women against the island poverty', 'compare women against the mainland rent', 'compare veterans against the mainland poverty']);   // E1
  none(['poverty: women vs a decade ago', 'poverty: women relative to a decade ago', 'poverty: women except for a decade ago', 'la pobreza: mujeres vs antes del huracán', 'la pobreza: mujeres vs de 2010 a 2015']);   // E2, the time
  none(['poverty, the female population vs in 2015', 'home values, the disabled vs in 2015', 'poverty: the female population apart from in 2015', 'el alquiler, la población de veteranos vs en 2015']);   // E2, an article before the group
  none(['poverty: women vs the decade before', 'la pobreza: mujeres vs década pasada', 'la pobreza: mujeres vs antes de María']);   // the time words
  for (const q of ['compare women against local poverty', 'poverty, the women', 'poverty: the female population', 'compare veterans to island-wide poverty', 'compare women against island-wide poverty']) assert.ok(p(q).relPairs.length, q);
});
test('chat: round 20 (sixteenth check): a year after a word of contrast is the counterpart, a range of years is not, "over", "onto", "against" before the front of a dataset\'s name', () => {
  const p = chatEnv().parse;
  const rel = (list, topic) => { for (const q of list) assert.ok(p(q).relPairs.some(x => x.includes(topic)), q); };
  const none = (list) => { for (const q of list) assert.deepStrictEqual(p(q).relPairs, [], q); };
  none(['poverty: women except for 2015', 'vacancy: households living alone except for 2015', 'what about vacancy, households living alone except for 2015', 'please rent: individuals living alone except for 2015?']);   // D1
  none(['poverty: women versus in 2015', 'poverty: women vs for 2015', 'poverty: women unlike in 2015', 'la pobreza: mujeres a diferencia de en 2015', 'la pobreza: mujeres excepto para 2015', 'poverty: women vs 2015', 'la pobreza: mujeres frente a 2015']);   // D2
  rel(['compare women over local poverty', 'compare women against local poverty', 'compare women against the local poverty', 'compara mujeres contra la actual pobreza'], 'poverty_pct'); rel(['compara mujeres contra el nuevo alquiler'], 'median_gross_rent'); rel(['overlay women onto regional rent'], 'median_gross_rent'); rel(['link women against national home values'], 'median_home_value');   // D3
  rel(['poverty between 2015 and 2020 plotted against women', 'poverty in 2020 plotted against women'], 'poverty_pct'); rel(['compare rent between 2015 and 2020 plotted against women'], 'median_gross_rent');   // D4
  none(['compare women against men poverty', 'women versus the mainland poverty', 'compare poverty due to women']);
});
test('chat: round 19 (fifteenth check): "to/on" before the front of a dataset\'s name, a year before a phrase of relation, list words after plain words and after a name that ends in a preposition', () => {
  const p = chatEnv().parse;
  const rel = (list, topic) => { for (const q of list) assert.ok(p(q).relPairs.some(x => x.includes(topic)), q); };
  rel(['overlay women on local poverty', 'overlay women on the local poverty', 'compare veterans to island-wide poverty'], 'poverty_pct');   // C1: the words before the dataset are its front
  rel(['overlay women on national home values'], 'median_home_value'); rel(['compare children to current rent', 'overlay family households on regional rent'], 'median_gross_rent'); rel(['link women to post-Maria commute time'], 'commute_45plus_pct'); rel(['pair family households to local unemployment'], 'laus_unemp_rate');
  rel(['poverty in 2020 plotted against women'], 'poverty_pct'); rel(['compare rent in 2020 plotted against women'], 'median_gross_rent');   // C2: a year is no counterpart
  rel(['la pobreza actual seguido de las mujeres', 'la pobreza actual seguido de mujeres', 'la pobreza hoy seguida de las mujeres'], 'poverty_pct');   // C3
  rel(['el ingreso del hogar al lado de mujeres', 'compara el ingreso del hogar al lado de mujeres', 'superpone el ingreso del hogar al lado de las mujeres', 'el ingreso del hogar así como mujeres', 'el ingreso del hogar seguido de mujeres'], 'median_hh_income');   // C4
  rel(['compare jobs in services next to women', 'jobs in services along with women'], 'qcew_jobs');
  for (const q of ['compare poverty due to women', 'compara la pobreza debida a las mujeres', 'compare poverty based on women', 'compara la pobreza debida al número de mujeres']) assert.deepStrictEqual(p(q).relPairs, [], q);   // B4 still holds with the dataset first
});
test('chat: round 18 (fourteenth check): a scope before a list word, words of the rule that the rest of a name swallowed, "due to" after a word that compares, verbs of change, a bare year', () => {
  const p = chatEnv().parse;
  const rel = (list, topic = 'poverty_pct') => { for (const q of list) assert.ok(p(q).relPairs.some(x => x.includes(topic)), q); };
  const left = (list) => { for (const q of list) { const r = p(q); assert.deepStrictEqual(r.relPairs, [], q); assert.strictEqual(r.keys.length, 1, q); } };
  rel(['poverty by town and women', 'poverty by town or women', 'poverty by town vs women', 'poverty by town / women', 'compare poverty by town versus women', 'compare poverty by town against women', 'poverty by town contrasted with women', 'poverty by municipality and women']);   // B1: a scope is no counterpart
  rel(['compare rent by town compared with women'], 'median_gross_rent');
  rel(['la pobreza seguido de las mujeres', 'la pobreza seguida de las mujeres', 'poverty overlaid with the women']); rel(['show rent overlaid with the family households'], 'median_gross_rent');   // B2, B3: read as written too
  left(['compare poverty due to women', 'compare poverty specific to children', 'compare poverty unique to veterans', 'compare poverty common to women', 'compare poverty limited to children', 'compare poverty attributable to people with disabilities', 'compare poverty based on women', 'compara la pobreza propia a las mujeres', 'compara la pobreza debida a las mujeres']);   // B4: the figure of the group, no compare
  rel(['compare federal funding with women'], 'fed_awards_total');   // after the rest of a name "with" still counts
  rel(['poverty varies with women', 'poverty rises with women', 'poverty moves with women', 'poverty changes with women', 'poverty linked to women', 'women plotted against poverty', 'overlay women 2020 on poverty', 'superpone mujeres 2020 sobre la pobreza']);   // minors 1 and 2
});
test('chat: round 17, a place between the group and the dataset (its name is blanked in the page) does not cancel the relation', () => {
  const keys = chatEnv(), p = keys.parse, e = keys.env;
  e.setApi({ places: () => ['Ponce', 'Mayagüez', 'Caguas', 'Puerto Rico'], meta: () => ({}), datasets: () => [] });
  try {
    for (const q of ['overlay women in Ponce on poverty', 'superpone mujeres en Ponce sobre la pobreza', 'correlate women in Ponce with poverty']) assert.deepStrictEqual(p(q).relPairs, [['acs_female_pct', 'poverty_pct']], q);
    assert.deepStrictEqual(p('compare poverty of retirees with disabilities in Ponce and Mayagüez').relPairs, [], 'the group says whose figure it is');
  } finally { e.setApi(null); }
});
test('chat: round 17, the words and steps of the conservative rule, each pinned by a question (the mutation check of round 17)', () => {
  const p = chatEnv().parse;
  for (const [q, k, rel, intent] of [
    ["compare women with ademas income", ["median_hh_income"], [], "show"],   // CH_FUNC: no filler words
    ["muestra children and not median rent", ["median_gross_rent"], [], "show"],   // CH_FUNC: the words of a statistic
    ["compare households asociada people living alone and poverty", ["households", "acs_living_alone_pct", "poverty_pct"], [["acs_living_alone_pct", "poverty_pct"], ["acs_living_alone_pct", "households"]], "compare"],   // CH_LINKS: no CH_CMP
    ["compare women among the population with poverty", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // CH_OWN_INTO: no 'among'
    ["compara mujeres de la poblacion con la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // CH_OWN_INTO: no 'de'
    ["compara mujeres entre la poblacion con la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // CH_OWN_INTO: no 'entre'
    ["compare women of the population with poverty", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // CH_OWN_INTO: no 'of'
    ["compare women within the population with poverty", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // CH_OWN_INTO: no 'within'
    ["correlate children or federal grants along with people who live alone instead of people who live alone over time", ["acs_under18_pct", "fed_grants"], [["acs_under18_pct", "fed_grants"]], "compare"],   // R10 M09b: free: no 'people' exception
    ["where is el desempleo contra ninos: people who live alone en lugar de home values by town", ["laus_unemployed", "acs_under18_pct", "median_home_value"], [["acs_under18_pct", "laus_unemployed"], ["acs_under18_pct", "acs_living_alone_pct"]], "compare"],   // R10 M25: tied: every -> some
    ["compara mujeres en toda la poblacion con la pobreza", ["acs_female_pct", "population", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R10 M29: absorption: distance 2 -> 3
    ["households zeta eta theta iota kappa people living alone", ["households", "acs_living_alone_pct"], [], "show"],   // R10 M31: absorption: households 4 -> 6
    ["compara mujeres vincula la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R16 CH_CMP: no 'vincul'
    ["compara mujeres ! la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST signs: no '!'
    ["compara mujeres & la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST signs: no '&'
    ["compara mujeres ; la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST signs: no ';'
    ["compara mujeres ? la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST signs: no '?'
    ["la pobreza al lado de mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_LIST: no 'al lado de'
    ["la pobreza al lado del mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_LIST: no 'al lado del'
    ["la pobreza beside mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_LIST: no 'beside'
    ["compara mujeres e la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'e'
    ["women junto al poverty", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'junto al'
    ["compara mujeres junto con la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'junto con'
    ["compara mujeres seguido de la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'seguido de'
    ["compara mujeres together with la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'together with'
    ["compara mujeres u la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'u'
    ["compara mujeres vs. la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'vs\.?'
    ["compara mujeres y/o la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_LIST: no 'y\/o'
    ["who has higher women overlay personas con discapacidad across municipalities", ["acs_female_pct", "acs_disability_pct"], [["acs_female_pct", "acs_disability_pct"]], "show"],   // R17 CH_GAP_REL after a word that compares: against, con, a
    ["la pobreza superpone sobre mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_REL after a word that compares: sobre
    ["show unemployment, overlay women against poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'against'
    ["show unemployment, overlay women al lado de poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'al lado de'
    ["show unemployment, overlay women al lado del poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'al lado del'
    ["show unemployment, overlay women alongside poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'alongside'
    ["show unemployment, overlay women beside poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'beside'
    ["show unemployment, overlay women compared to poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'compared to'
    ["show unemployment, overlay women compared with poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'compared with'
    ["show unemployment, overlay women contra poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'contra'
    ["compara mujeres encima del la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_SIDE: no 'encima del'
    ["compara mujeres frente a la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_SIDE: no 'frente a'
    ["compara mujeres frente al la pobreza", ["acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_GAP_SIDE: no 'frente al'
    ["show unemployment, overlay women junto a poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'junto a'
    ["show unemployment, overlay women junto al poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'junto al'
    ["show unemployment, overlay women next to poverty", ["laus_unemp_rate", "acs_female_pct", "poverty_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 CH_GAP_SIDE: no 'next to'
    ["compare poverty with the parte of women", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 CH_SHARE_OF: no 'parte'
    ["compare mujeres o people who live alone alongside internet access versus poverty in Ponce", ["internet_subscription_pct", "poverty_pct"], [], "compare"],   // R17 chDirect: across a contrast
    ["la pobreza superpone an mujeres", ["poverty_pct"], [], "show"],   // R17 chGapCore strip: filler 'an' stripped
    ["la pobreza superpone esas mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 chGapCore strip: no 'esas'
    ["la pobreza superpone esos mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 chGapCore strip: no 'esos'
    ["la pobreza superpone estas mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 chGapCore strip: no 'estas'
    ["la pobreza superpone estos mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 chGapCore strip: no 'estos'
    ["poverty: women vs gente households", ["poverty_pct"], [], "show"],   // R17 chGapCore strip: no 'gente' (round 23: the households after "vs" are the counterpart of the group; round 24: and they go with it)
    ["poverty: women vs personas households", ["poverty_pct"], [], "show"],   // R17 chGapCore strip: no 'personas' (round 23: the households after "vs" are the counterpart of the group; round 24: and they go with it)
    ["poverty: women vs persons households", ["poverty_pct"], [], "show"],   // R17 chGapCore strip: no 'persons' (round 23: the households after "vs" are the counterpart of the group; round 24: and they go with it)
    ["poverty: women vs residentes households", ["poverty_pct"], [], "show"],   // R17 chGapCore strip: no 'residentes' (round 23: the households after "vs" are the counterpart of the group; round 24: and they go with it)
    ["la pobreza superpone these mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 chGapCore strip: no 'these'
    ["poverty: women vs the those household", ["poverty_pct"], [], "show"],   // R17 chGapCore strip: no 'those' (round 23: the households after "vs" are the counterpart of the group; round 24: and they go with it)
    ["compara la pobreza con toda la niñez", ["poverty_pct", "acs_under18_pct"], [["acs_under18_pct", "poverty_pct"]], "compare"],   // R17 chGapCore strip: no 'toda'
    ["compara la pobreza con todas las mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "compare"],   // R17 chGapCore strip: no 'todas'
    ["la pobreza superpone todo mujeres", ["poverty_pct", "acs_female_pct"], [["acs_female_pct", "poverty_pct"]], "show"],   // R17 chGapCore strip: no 'todo'
    ["compara la pobreza con todos los veteranos", ["poverty_pct", "acs_veteran_pct"], [["acs_veteran_pct", "poverty_pct"]], "compare"],   // R17 chGapCore strip: no 'todos'
    ["compare federal grants and the share of people living alone and the share of hogares", ["fed_grants", "acs_living_alone_pct", "households"], [["acs_living_alone_pct", "fed_grants"], ["acs_living_alone_pct", "households"]], "compare"],   // R17 chNamesBoth connectors: no 'and'
    ["overlay tourism jobs as well as children versus la pobreza with high personas con discapacidad versus 2015", ["tourism_jobs", "acs_under18_pct", "poverty_pct", "acs_disability_pct"], [["acs_under18_pct", "tourism_jobs"], ["acs_under18_pct", "poverty_pct"], ["acs_disability_pct", "poverty_pct"]], "compare"],   // R17 chSide: degree check after a group too
    ["compara me el porcentaje de veteranos con niños con la pobreza", ["acs_veteran_pct", "acs_under18_pct", "poverty_pct"], [["acs_under18_pct", "acs_veteran_pct"], ["acs_under18_pct", "poverty_pct"]], "compare"],   // chCompares joiners: no 'con'
    ["plot people with disabilities which has more ninos junto a el ingreso mediano, or the population across municipalities", ["acs_disability_pct", "acs_under18_pct", "median_hh_income", "population"], [["acs_under18_pct", "median_hh_income"]], "compare"],   // chCompares joiners: no 'with'
    ["compara empleos por residente y mujeres", ["qcew_jobs", "acs_female_pct"], [["acs_female_pct", "qcew_jobs"]], "compare"],   // chNameTail preps: no 'por'
    ["show children compared with median rent with high people with disabilities scatter the average household across municipalities", ["acs_under18_pct", "median_gross_rent", "acs_disability_pct", "households"], [["acs_under18_pct", "median_gross_rent"], ["acs_disability_pct", "median_gross_rent"], ["acs_disability_pct", "households"]], "compare"],   // chNameTail: a function word is a name
    ["commute time in commute time and people living alone con personas que viven solas", ["commute_45plus_pct"], [], "show"],   // chNameTail: a function word is a name
    ["muestra el desempleo de el alquiler in addition to family households of hogares versus 2015", ["laus_unemp_rate", "median_gross_rent", "acs_family_households_pct"], [["acs_family_households_pct", "median_gross_rent"]], "compare"],   // chNameTail: a short word is a name
    ["relate mujeres as well as children in households near ninos over time", ["acs_female_pct", "acs_under18_pct", "households"], [], "compare"],   // chQualifiers: the cluster ends at the name
    ["plot households among the elderly junto a family households", ["households"], [], "show"],   // chQualifiers: the elderly have a direct partner too
    ["compare households afecta people living alone and poverty", ["households", "acs_living_alone_pct", "poverty_pct"], [["acs_living_alone_pct", "poverty_pct"], ["acs_living_alone_pct", "households"]], "compare"],   // earlier: CH_CONN affects
    ["compare children luego poverty", ["acs_under18_pct", "poverty_pct"], [["acs_under18_pct", "poverty_pct"]], "compare"],   // earlier: |in addition to|ademas de|aparte de|apart from|frente a|en contraste c
    ["compare women with over income", ["acs_female_pct", "median_hh_income"], [["acs_female_pct", "median_hh_income"]], "compare"],   // earlier: |where|donde|wherever|
  ]) { const r = p(q); assert.deepStrictEqual([r.keys, r.relPairs, r.intent], [k, rel, intent], q); }
});
test('chat: the correlation of two datasets is told when no group dataset is in the question, or when the question asks how they relate', () => {
  const e = chatEnv().env;
  assert.strictEqual(e.chAsksRelation(['poverty_pct', 'laus_unemp_rate'], { related: false }), true, 'two datasets main had: as it always was');
  assert.strictEqual(e.chAsksRelation(['poverty_pct', 'acs_female_pct'], { related: false }), false, 'a group dataset that came with no word that names the two side by side: no relation is reported');
  assert.strictEqual(e.chAsksRelation(['poverty_pct', 'acs_female_pct'], { related: true }), true);
  const pair = [['acs_female_pct', 'poverty_pct']];
  assert.strictEqual(e.chAsksRelation(['poverty_pct', 'acs_female_pct'], { related: true, relPairs: pair }), true, 'the pair the question relates');
  assert.strictEqual(e.chAsksRelation(['acs_female_pct', 'poverty_pct'], { related: true, relPairs: pair }), true, 'in either order');
  assert.strictEqual(e.chAsksRelation(['poverty_pct', 'acs_female_pct'], { related: true, relPairs: [['acs_veteran_pct', 'poverty_pct']] }), false, 'the relation of another pair is not this one');
  assert.strictEqual(e.chAsksRelation(['poverty_pct', 'laus_unemp_rate', 'acs_female_pct'], { related: false, relPairs: [] }), true, 'the sentence is about the first two datasets, and main had both');
  assert.strictEqual(e.chAsksRelation(['acs_female_pct', 'poverty_pct', 'laus_unemp_rate'], { related: false, relPairs: [] }), false, 'a group dataset among the first two, with no relation asked');
  const p = chatEnv().parse;
  for (const q of ['poverty and women', 'does the share of women affect poverty', 'poverty versus women', '¿afecta el porcentaje de mujeres a la pobreza?', 'places with veterans have higher poverty']) assert.strictEqual(!!p(q).related, true, q);
  for (const q of ['women in poor municipalities', 'poverty among women', 'compare poverty for women and men', 'how did Hurricane Maria affect poverty among veterans', 'poverty among women near San Juan', 'compare poverty women', 'poverty for veterans along with women']) assert.strictEqual(!!p(q).related, false, q);
  assert.deepStrictEqual(p('poverty and women').relPairs, [['acs_female_pct', 'poverty_pct']], 'the pairs are recorded, not just that there is one');
  assert.deepStrictEqual(p('poverty and women and also unemployment').relPairs, [['acs_female_pct', 'poverty_pct'], ['acs_female_pct', 'laus_unemp_rate']]);
  assert.deepStrictEqual(p('poverty for veterans along with women').relPairs, [], 'a group tied only to a group that is left out is left out too');
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8'), part = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));
  assert.ok(part('async show(st)', 'async value(st)').includes('chAsksRelation(keys, st)'), 'the show answer tells the correlation only when the question relates the group to the other dataset, or when no group dataset is in it');
});
test('chat: a household type beside "households" is the dataset itself: nothing is left out', () => {
  const keys = chatEnv();
  for (const q of ['hogares de personas solas', 'hogares donde viven personas solas', 'hogares con personas solas', 'households living alone', 'households of people living alone']) {
    const r = keys.full(q);
    assert.deepStrictEqual(r.dropped, [], `"${q}" leaves nothing out`);
    assert.deepStrictEqual(r.keys, ['acs_living_alone_pct'], `"${q}" is the share of one-person households: the count of households is not asked`);
  }
  for (const [q, k] of [['one-person households as a share of households', 'acs_living_alone_pct'], ['What share of households are one-person households?', 'acs_living_alone_pct'], ['how many households live alone', 'acs_living_alone_pct'], ['What percent of households are family households?', 'acs_family_households_pct'], ['¿Qué porcentaje de hogares son hogares familiares?', 'acs_family_households_pct']]) assert.deepStrictEqual(keys.full(q).keys, [k], q);
  assert.deepStrictEqual(keys.full('households with elderly').keys, ['age65_pct', 'households'], 'a group that is not a household type leaves the households, and the group\'s own dataset leads');
  assert.deepStrictEqual(keys.full('households headed by women').keys, ['households'], 'a group that is not a household type still says whose households they are');
});
test('chat: the notes are as true as the figures: "more than" is not a request for a count, the margin is written in points for a share, and the answers carry it', () => {
  const e = chatEnv().env;
  assert.strictEqual(e.chRankNotes({ unit: '%' }, 'where is it more than half', 'where is it more than half', 'en'), '', '"more than" is not a request for a count');
  assert.ok(e.chRankNotes({ unit: '%' }, 'where do most veterans live', 'where do most veterans live', 'en').includes('percentage, not a count'));
  e.setApi({ moe: () => [4.2, null], meta: () => ({ type: 'rate' }) });
  assert.ok(e.chMoeText('acs_x', 2024, 0).includes('±4.2 pts'), 'a share has its margin of error in points');
  assert.strictEqual(e.chMoeText('acs_x', 2024, 1), '', 'no margin, no text');
  e.setApi(null);
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8'), part = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));
  assert.ok(part('async show(st)', 'async value(st)').includes('chMoeNote(st.lang)'), 'a show answer about a survey dataset says its figures have a margin of error');
  assert.ok(part('async value(st)', 'async rank(st)').includes('chMoeNote(st.lang)') && part('async value(st)', 'async rank(st)').includes('chMoeText('), 'a value comes with its margin and the note');
  assert.ok(part('async rank(st)', 'async compare(st)').includes('chRankNotes('), 'and a ranking with its notes');
});
test('chat: the text of a group left out is as the person wrote it, and the note says it without markup', () => {
  const keys = chatEnv(), p = keys.parse, e = keys.env;
  assert.deepStrictEqual(p('¿Cuál es la pobreza en Niños?').dropped, [{ key: 'acs_under18_pct', text: 'Niños' }]);
  assert.deepStrictEqual(p('Poverty among WOMEN').dropped.map(d => d.text), ['WOMEN']);
  const html = e.chDroppedNote([{ key: 'x', text: '<b>women' }], 'en');
  assert.ok(html.includes('&lt;b&gt;women') && !html.includes('<b>'));
  assert.ok(e.chDroppedNote([{ key: 'a', text: 'mujeres' }, { key: 'b', text: 'niños' }], 'es').includes('«mujeres» ni «niños»'));
  assert.ok(e.chDroppedNote([{ key: 'a', text: 'women' }], 'en').includes('“women”'));
});
test('chat: the direction and the rank words are read from what the datasets leave of the question', () => {
  const p = chatEnv().parse;
  for (const q of ['donde viven mas menores de edad', '¿Dónde viven más menores de edad?', 'menores de 18 años']) assert.strictEqual(p(q).dir, 'desc', q);
  assert.strictEqual(p('menos desempleo').dir, 'asc'); assert.strictEqual(p('lowest unemployment').dir, 'asc'); assert.strictEqual(p('where is unemployment highest').dir, 'desc');
  assert.strictEqual(p('donde viven mas menores de edad').intent, 'rank'); assert.strictEqual(p('¿Dónde es más alto el desempleo?').intent, 'rank');
  assert.notStrictEqual(p('menores de edad').intent, 'rank', 'the name of a dataset is not a rank word');
  assert.strictEqual(p('hogares unipersonales de ancianos').lang, 'es', 'a Spanish question about households is answered in Spanish');
});
test('chat: a dataset the page did not load is not offered, and a whole label names its dataset', () => {
  const keys = chatEnv(), e = keys.env, ds = [{ key: 'acs_living_alone_pct', label: 'One-person households, % of all households' }, { key: 'acs_family_households_pct', label: 'Family households, % of all households' },
    { key: 'acs_veteran_pct', label: 'Veterans, % of civilians 18 and older' }, { key: 'poverty_pct', label: 'Population below the poverty level' }];
  e.setApi({ datasets: () => ds, meta: (k) => ds.find(d => d.key === k) || null, places: () => ['Ponce', 'Puerto Rico'] });
  assert.deepStrictEqual(keys('One-person households, % of all households'), ['acs_living_alone_pct'], 'the words "households" after the comma add no second dataset');
  assert.deepStrictEqual(keys('Family households, % of all households'), ['acs_family_households_pct']);
  assert.deepStrictEqual(keys('Veterans, % of civilians 18 and older'), ['acs_veteran_pct']);
  assert.deepStrictEqual(e.chParse('where do most veterans live').keys, ['acs_veteran_pct']);
  const ds2 = ds.concat([{ key: 'acs_zeta', label: 'Zeta widgets, % of x' }, { key: 'acs_pov', label: 'Poverty, % of x' }]);   // the part of a label before its comma names the dataset when it has twelve letters or more
  e.setApi({ datasets: () => ds2, meta: (k) => ds2.find(d => d.key === k) || null, places: () => ['Ponce', 'Puerto Rico'] });
  assert.deepStrictEqual(keys('zeta widgets'), ['acs_zeta']);
  assert.deepStrictEqual(keys('poverty'), ['poverty_pct'], 'a shorter part of a label names nothing');
  e.setApi({ datasets: () => ds.slice(3), meta: (k) => ds.slice(3).find(d => d.key === k) || null, places: () => ['Ponce', 'Puerto Rico'] });   // the file of the series did not load
  const st = e.chParse('where do most veterans live');
  assert.deepStrictEqual(st.keys, [], 'a dataset the page does not have is dropped before any answer'); assert.strictEqual(st.intent, 'unknown');
  e.setApi(null);
});
test('chat: the notes under an answer are true for the dataset they sit under', () => {
  const e = chatEnv().env;
  assert.ok(e.chRankNotes({ unit: '%' }, 'where do most      live', 'where do most veterans live', 'en').includes('This ranks a percentage, not a count.'));
  assert.ok(e.chRankNotes({ unit: '%' }, 'donde viven mas        ', 'donde viven mas veteranos', 'es').includes('Esto ordena un porcentaje, no una cantidad.'));
  for (const [q, l] of [['donde es mas alto el desempleo', 'es'], ['donde es mas bajo el ingreso', 'es'], ['where is unemployment highest', 'en'], ['which municipality has the highest share of veterans', 'en'], ['most share of veterans', 'en']]) assert.strictEqual(e.chRankNotes({ unit: '%' }, q, q, l), '', `no percentage note for "${q}"`);
  assert.strictEqual(e.chRankNotes({ unit: '$' }, 'most', 'most', 'en'), '', 'only a percentage');
  for (const l of ['en', 'es']) {
    const n = e.chRankNotes({ unit: '', moe: {} }, '', '', l);
    assert.ok(/margin|margen/.test(n), l); assert.ok(!/hatch|rayad|small municipalities|municipios peque/i.test(n), 'the note holds for the datasets that have no hatched municipality');
  }
  assert.strictEqual(e.chRankNotes({ unit: '', moe: null }, '', '', 'en'), '', 'a dataset with no margins gets none');
  assert.ok(e.chWindowNote(2010, 2024, 'en').includes('share no year') && e.chWindowNote(2021, 2024, 'en').includes('share 2 of their five years') && e.chWindowNote(2023, 2024, 'en').includes('share 4 of their five years'));
  assert.ok(e.chWindowNote(2010, 2024, 'es').includes('no comparten ningún año') && e.chWindowNote(2021, 2024, 'es').includes('comparten 2 de sus cinco años'));
  assert.ok(e.chWindowNote(2024, 2021, 'en').includes('share 2 of their five years'), 'in either order');
  for (const n of [e.chMoeNote('es'), e.chWindowNote(2021, 2024, 'es'), e.chDroppedNote([{ text: 'x' }], 'es')]) assert.ok(!/estimaciones|rayas|todos los residentes/.test(n), `the Spanish of docs/i18n.md (estimado, las personas residentes): ${n}`);
});
test('economy.js: the status of the area buttons keeps every outcome when requests overlap, and a file that does not load is said', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'economy.js'), 'utf8'), at = src.indexOf('function ecAreaStatus');
  const status = new Function('T', 'SMALL_NAMES', src.slice(at, src.indexOf('function areaLevels', at)) + '\nreturn ecAreaStatus;')((x) => x, { barrio: 'Barrios', tract: 'Census tracts', 'block-group': 'Block groups' });
  assert.strictEqual(status([], false), null);
  assert.strictEqual(status([{ level: 'tract', msg: 'The download started.' }], true), null, 'a file is still loading: the line says so');
  assert.strictEqual(status([{ level: 'tract', msg: 'The download started.' }], false), 'The download started.');
  assert.strictEqual(status([{ level: 'block-group', msg: 'The areas could not be loaded. Try again in a moment.' }, { level: 'tract', msg: 'The download started.' }], false),
    'Block groups: The areas could not be loaded. Try again in a moment. Census tracts: The download started.', 'an error that came first is not lost when a later request succeeds');
  assert.ok(/outcomes\.push\(\{ level: b\.dataset\.eclevel, msg \}\)/.test(src) && /ecAreaStatus\(outcomes, !!\$\('#ecDlgBody'\)\.querySelector\('\[data-eclevel\]\[aria-busy\]'\)\)/.test(src), 'the buttons report to it');
  assert.ok(/const \[\{ docs, failed \}\] = await Promise\.all\(\[Core\.datasets\.fetchFiles\(/.test(src) && /toast\(T\('Some data did not load, so some datasets are missing\./.test(src), 'a file that does not load is said (datasets.load: see the test of the shared loader)');
  assert.ok(/notLoaded\(\) \{ return EC\.failed \|\| \[\]; \}/.test(src) && /EC\.failed = failed;/.test(src), 'and the chat can ask');
  const chat = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8');
  assert.ok(chat.includes('out.html += chDroppedNote(st.dropped, st.lang)'), 'the note that says which group was left out is added under the answer');
  assert.ok(chat.includes('html += chRankNotes(m, st.rest, st.n, st.lang);') && chat.includes('chWindowNote(r.from, r.to, st.lang)') && (chat.match(/chMoeNote\(st\.lang\)/g) || []).length >= 2 && chat.includes('chMoeText(k, r.year, i)'), 'the rank, trend, show and value answers carry their notes');
  assert.ok(src.includes("msg = T('The download started.')") && src.includes("T('In Excel, the long codes of block groups (GEOID) can show as 7.2E+11: import the column as text.')") && src.includes("levels.includes('block-group')"), 'the success text and the Excel note of the window');
  assert.ok(/api\.notLoaded && api\.notLoaded\(\)\.length\) return \{ html: chP\(esc\(st\.lang === 'es' \? 'Algunos datos no se cargaron/.test(chat) && chat.indexOf('api.notLoaded') < chat.indexOf('chAddWish(st.q)'), 'a question asked when a file failed is not saved as a wish');
});
// ── what an empty place says, the opt-out of the small-count flag and the starting classes, on the health series ──
test('health series: an empty place says so in the pop-up, the hover card, the inspector and the table text, not only in the legend', () => {
  const X = healthEngine(), L = X.makeLayer('hpsa_dh_score', 'fill', {}, []); L.id = 1;
  const evals = X.evaluate([L]), e1 = evals[1], names = X.geo.names;
  const none = names.findIndex((n, i) => i < 78 && e1.a[i] == null);
  assert.ok(none >= 0, 'the dental file leaves a municipality empty');
  assert.strictEqual(X.missing(L, none), 'No area shortage designation');
  assert.strictEqual(X.missing(L, X.geo.pr), null, 'the island has no score for another reason: a score is not added');
  assert.strictEqual(X.missing({ key: 'qcew_jobs' }, 0), null, 'a dataset that does not say what empty means keeps the dash');
  assert.strictEqual(popup.value(X, L, e1, none).txt, 'No area shortage designation');
  assert.strictEqual(popup.value(X, L, e1, X.geo.pr).txt, '—');
  assert.ok(popup.hover(X, [L], evals, none).includes('No area shortage designation'));
  assert.ok(popup.inspect(X, [L], evals, none, true).includes('No area shortage designation'));
  const full = names.findIndex((n, i) => i < 78 && e1.a[i] != null);
  assert.ok(!popup.value(X, L, e1, full).txt.includes('shortage'), 'a municipality with a score shows the score');
});

test('reliability: administrative counts (counted: false) are not flagged as fewer than 10 counted; other counts still are', () => {
  const X = healthEngine(), sites = X.makeLayer('hc_sites', 'fill', { norm: 'per1000' }, []); sites.id = 1;
  const r = reliability.assess(X, sites, X.evaluate([sites])[1]);
  assert.strictEqual(X.V.hc_sites.counted, false);
  assert.strictEqual(r.small, null, 'a health center site is a site: the count is not an estimate from a few cases');
  assert.strictEqual(r.n.flagged, 0);
  assert.ok(!reliability.notes(X, sites, X.evaluate([sites])[1]).some(n => n.kind === 'small'));
  const flagged = ['attractions_places', 'visitor_services_places', 'lodging_places', 'gastronomy_places', 'tourism_places'].map(k => { const L = X.makeLayer(k, 'fill', { norm: 'per1000' }, []); L.id = 1; return reliability.assess(X, L, X.evaluate([L])[1]).n.small; });
  assert.ok(flagged.some(n => n > 0), 'the rule still works for the counts that have not opted out: ' + flagged);
  assert.ok(X.list().filter(v => v.family === 'health').every(v => v.counted === false), 'every health dataset opts out');
});

test('health series: the legends start with natural breaks where quantiles leave empty classes, and every class holds a municipality', () => {
  const X = healthEngine();
  assert.deepStrictEqual(X.list().filter(v => v.classes === 'jenks').map(v => v.key).sort(), ['hc_sites', 'hc_vans', 'hpsa_dh_score', 'hpsa_mh_met', 'hpsa_mh_score', 'hpsa_pc_met']);
  assert.strictEqual(X.makeLayer('hc_vans', 'fill', {}, []).classes, 'jenks');
  assert.strictEqual(X.makeLayer('hc_vans', 'fill', { classes: 'quantile' }, []).classes, 'quantile', 'a link or a choice wins over the dataset\'s start');
  assert.strictEqual(X.makeLayer('qcew_jobs', 'fill', {}, []).classes, 'quantile', 'the datasets that did not ask keep quantiles');
  for (const v of X.list().filter(x => x.family === 'health')) {
    const L = X.makeLayer(v.key, 'fill', {}, []); L.id = 1;
    const e = X.evaluate([L])[1], b = X.breaks(L, e.y), n = new Array(b.edges.length - 1).fill(0);
    e.a.slice(0, X.geo.pr).filter(x => x != null).forEach(x => n[classify.classOf(b, x)]++);
    assert.ok(n.every(c => c > 0), `${v.key}: a class with no municipality (${n.join(', ')})`);
  }
  const s = X.encode([X.makeLayer('hc_vans', 'fill', {}, [])]);
  assert.ok(/\.j\./.test(s), 'the link says natural breaks, so it opens the same legend: ' + s);
});

// ── the chat: HRSA words ──
// The real functions of site/js/chat.js (concepts, language, intent, parse, the value cell, ties), with no page and no datasets unless a test hands them over (env.setApi).
function healthChat() {
  const s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8'), a = s.indexOf('const HPSA_NAMED'), b = s.indexOf('\n];', a) + 3;
  const mid = s.slice(s.indexOf('const STOP'), s.indexOf('function chFuzzy')), intent = s.slice(s.indexOf('function chIntent'), s.indexOf('// ── Data helpers')), line = (name) => s.slice(s.indexOf(`function ${name}(`), s.indexOf('\n', s.indexOf(`function ${name}(`)));
  const norm = (x) => (x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();   // common.js
  const code = `let API = null; const chApi = () => API; const I18N = { lang: 'en' }; const CH = { lastLang: null, ui: 'en', ctx: { keys: [], year: null, muni: null } }; const CH_CONTEXT = [];\n${s.slice(a, b)}\n${mid}\n${intent}\n${line('chVal')}\n${line('chCell')}\n`
    + 'return { chParse, chConcepts, chLang, chCell, chTie, chOneYear, CH, setApi: (x) => { API = x; } };';
  const env = new Function('norm', 'esc', 'fmt', 'T', code)(norm, (x) => String(x), (n) => String(n), (x) => x);
  const keys = (q) => env.chConcepts(norm(q)).keys; keys.lang = (q) => env.chLang(q, 'en'); keys.parse = env.chParse; keys.env = env;
  return keys;
}
test('chat: a shortage question finds the discipline it names, and the generic words only when none is named', () => {
  const keys = healthChat(), only = (q, k) => assert.deepStrictEqual(keys(q), [k], `"${q}" should find only ${k}, found ${keys(q)}`);
  only('dental shortage areas', 'hpsa_dh_short'); only('where are the dental shortage areas?', 'hpsa_dh_short'); only('areas de escasez dental', 'hpsa_dh_short');
  only('mental health shortage areas', 'hpsa_mh_short'); only('escasez de salud mental', 'hpsa_mh_short'); only('psychiatrists still needed', 'hpsa_mh_short');
  only('primary care shortage areas', 'hpsa_pc_short'); only('atencion primaria', 'hpsa_pc_short');
  only('health shortage areas', 'hpsa_pc_short'); only('hpsa', 'hpsa_pc_short'); only('escasez de profesionales de la salud', 'hpsa_pc_short');   // the generic words are the primary care measure only in a question about health
  assert.deepStrictEqual(keys('escasez'), [], 'a bare escasez names no dataset'); assert.deepStrictEqual(keys('shortage areas for teachers'), [], 'and the generic words need a health word');
  only('areas de escasez de atencion primaria', 'hpsa_pc_short'); only('federally qualified', 'hc_sites'); only('mental health clinics', 'hpsa_mh_short');
  assert.deepStrictEqual(keys('doctors in San Juan'), [], 'doctors and nurses name no dataset: the chat says there is no count of them');
  only('need met', 'hpsa_pc_met'); only('dental priority score', 'hpsa_dh_score'); only('dental clinics', 'hpsa_dh_short'); only('salud dental', 'hpsa_dh_short'); only('salud mental necesidad cubierta', 'hpsa_mh_met');   // each of the 11 datasets can be named
  only('health centers', 'hc_sites'); only('centros de salud', 'hc_sites'); only('mobile health vans', 'hc_vans'); only('unidades moviles', 'hc_vans');
  // the chips the chat offers, and the clinics of both languages
  only('necesidad de atencion primaria cubierta', 'hpsa_pc_met'); only('necesidad de salud mental cubierta', 'hpsa_mh_met'); only('necesidad dental cubierta', 'hpsa_dh_met'); only('puntaje de prioridad dental', 'hpsa_dh_score');
  only('clinicas dentales', 'hpsa_dh_short'); only('clinica dental', 'hpsa_dh_short'); only('clinicas de salud mental', 'hpsa_mh_short'); only('primary care clinics', 'hpsa_pc_short'); only('clinicas de atencion primaria', 'hpsa_pc_short');
  for (const q of ['dentist jobs', 'mental health jobs', 'primary care jobs']) assert.ok(!keys(q).some(k => /^hpsa_/.test(k)), `"${q}" is about jobs: ${keys(q)}`);
});
test('chat: a question about health in Spanish is answered in Spanish, and the intents are in place', () => {
  const keys = healthChat(), p = keys.parse;
  for (const q of ['escasez de dentistas', 'salud mental', 'dentistas', 'necesidad cubierta', 'centros de salud en Ponce', 'escasez de atencion primaria', 'puntaje de prioridad dental', 'cuidado dental', 'doctores en Ponce', 'necesidad de atencion primaria cubierta']) assert.strictEqual(keys.lang(q), 'es', q);
  for (const q of ['dental shortage areas', 'mental health', 'doctors in San Juan', 'primary care need met', 'where are the dentists', 'priority score']) assert.strictEqual(keys.lang(q), 'en', q);
  for (const q of ['how many nurses are in Ponce', 'enfermeras en Ponce', 'nurses', 'enfermeras']) assert.strictEqual(p(q).intent, 'practitioners', q);
  for (const q of ['how many doctors are in Ponce', 'medicos en Ponce']) assert.notStrictEqual(p(q).intent, 'practitioners', q + ': doctors are counted since step 8 of decision 107');
  assert.strictEqual(p('what health data do you have').intent, 'catalog'); assert.strictEqual(p('what housing data do you have').intent, 'catalog'); assert.notStrictEqual(p('what poverty data do you have').intent, 'catalog', 'a dataset that is named is shown'); assert.strictEqual(p('¿qué datos de salud tienen?').intent, 'catalog');
  assert.strictEqual(p('where is unemployment highest').intent, 'rank');
});
test('chat: a dataset carried over from the last answer does not make "how many nurses" a question about it', () => {
  const keys = healthChat(), env = keys.env, chParse = keys.parse;
  env.setApi({ datasets: () => [], meta: () => ({}), places: () => ['Ponce', 'Puerto Rico'] });
  env.CH.ctx.keys = ['poverty_pct'];   // the last answer was about poverty
  const st = chParse('how many nurses are in Ponce');
  assert.ok(st.fromCtx && st.keys.includes('poverty_pct'), 'the question starts with "how": the dataset of the last answer is carried over');
  assert.strictEqual(st.intent, 'practitioners', 'and it is still a question about nurses');
  assert.notStrictEqual(chParse('how has it changed').intent, 'practitioners');
  env.CH.ctx.keys = []; env.setApi(null);
});
test('chat: an empty place says what that means, not a dash; ties and a single date are said', () => {
  const keys = healthChat(), env = keys.env;
  env.setApi({ missing: (k, i) => k === 'x' && i === 3 ? 'No area shortage designation' : null, fmt: (k, x) => x == null ? '—' : String(x), unitLabel: () => ({ suffix: '', unit: '' }) });
  assert.strictEqual(env.chCell('x', null, 3, 'value'), 'No area shortage designation', 'a place with no designation says so');
  assert.strictEqual(env.chCell('x', null, 4, 'value'), '—', 'a dataset that does not say what empty means keeps the dash');
  assert.strictEqual(env.chCell('x', 0, 3, 'value'), '0', 'a real zero is a zero');
  env.setApi(null);
  const eight = Array.from({ length: 8 }, (_, i) => ({ i, name: 'p' + i, v: 0 })).concat([{ i: 9, name: 'q', v: 5 }]).sort((a, b) => b.v - a.v);
  assert.strictEqual(env.chTie(eight, eight.length - 1, 'en'), ', with 7 more at the same value'); assert.strictEqual(env.chTie(eight, eight.length - 1, 'es'), ', con 7 más con el mismo valor'); assert.strictEqual(env.chTie(eight, 0, 'en'), '');
  assert.ok(env.chOneYear({ ys: [2026], static: true }) && env.chOneYear({ ys: [2026] }) && env.chOneYear(null) && env.chOneYear({ ys: [2014, 2015], snapshot: true }) && !env.chOneYear({ ys: [2014, 2015] }));
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8');
  assert.ok(src.includes('chOneYear(api.meta(keys[0]))') && src.includes('chOneYear(m) ? [] :') && src.includes('if (chOneYear(m)) { return'), 'the chips and the trend answer ask');
  assert.ok(src.includes('chTie(l, 0, st.lang)') && src.includes('chTie(l, l.length - 1, st.lang)'), 'the highest and lowest say when they are tied');
  assert.ok(src.includes('chCell(k, r.values[i], i, lv.norm)'), 'the value answer reads the empty place through chCell');
  assert.ok(src.includes("norm(d.group + ' ' + T(d.group))"), 'the catalog finds a topic by the name of the group in the page language too');
  assert.ok(src.includes('chClip(chLabel(k), 34)') && !src.includes('chLabel(k).slice(0, 34)'), 'a label in a table header is cut at a word');
});
test('chat: doctors and physicians are not read as "still needed", and the health words that were there still find their jobs', () => {
  const keys = healthChat(), none = (q) => assert.ok(!keys(q).some(k => /^hpsa_/.test(k)), `"${q}" must not find a shortage measure, found ${keys(q)}`);
  for (const q of ['how many doctors are in Ponce', 'physicians', 'medicos en Ponce', 'doctors per resident', 'doctores en Ponce']) none(q);
  assert.ok(keys('health care jobs').includes('jobs_naics_62') && keys('hospitals').includes('jobs_naics_62') && keys('salud').includes('jobs_naics_62'));
  assert.deepStrictEqual(keys('federal money'), ['fed_awards_total'], 'the rules after the health ones are untouched');
});

test('every script of the site parses as a whole (the tests above load parts of some files, which would not see an error elsewhere in them)', () => {
  const vm = require('node:vm'), dirs = ['js', 'js/core'].map(d => path.join(__dirname, '..', 'site', d));
  for (const d of dirs) for (const f of fs.readdirSync(d).filter(n => n.endsWith('.js'))) assert.doesNotThrow(() => new vm.Script(fs.readFileSync(path.join(d, f), 'utf8'), { filename: f }), f);
});

test('scenario: model outputs are read only when the whole file is right, and never with contact details (plan item 15)', () => {
  const S = core('scenario'), ids = readData('municipios.geojson').features.map(f => String(f.properties.GEOID).slice(0, 5)).sort();
  const sample = fs.readFileSync(path.join(__dirname, '..', 'site', 'samples', 'model_output_sample.csv'), 'utf8');
  const ok = S.parseModel(sample, ids);
  assert.deepStrictEqual(ok.errors, []);
  assert.match(ok.header.model_name, /MADE-UP VALUES/, 'the sample says it is made up');
  assert.deepStrictEqual([ok.series.length, Object.keys(ok.series[0].years), ok.series[0].years['2030'].length], [1, ['2030', '2035'], 79]);
  assert.strictEqual(ok.series[0].years['2030'][78], null, 'the island has no value unless the file gives code 72');
  const head = sample.split(/\r?\n/).filter(l => l.startsWith('#')).join('\n'), body = (rows) => head + '\ngeography_key,geography_level,period,variable,value,unit\n' + rows.join('\n');
  const bad = (rows, re, h = head) => { const r = S.parseModel(h + '\ngeography_key,geography_level,period,variable,value,unit\n' + rows.join('\n'), ids); assert.ok(r.errors.some(e => re.test(e)), `${re}: ${r.errors}`); assert.deepStrictEqual(r.series, [], 'nothing is loaded from a file with an error'); };
  bad(['72999,municipio,2030,x,1,'], /not a municipio code/);
  bad(['72001,barrio,2030,x,1,'], /not supported/);
  bad(['72001,municipio,20x0,x,1,'], /period must be a year/);
  bad(['72001,municipio,2030,x,abc,'], /not a number/);
  bad(['72001,municipio,2030,x,1,', '72001,municipio,2030,x,2,'], /second value/);
  bad(['72001,municipio,2030,x,1,%', '72003,municipio,2030,x,2,$'], /two units/);
  bad(['72001,municipio,2030,x,1,'], /contact details|telephone/, head.replace(/# contact_label: .*/, '# contact_label: Ana 787-555-0123'));
  bad(['72001,municipio,2030,x,1,'], /e-mail/, head.replace(/# contact_label: .*/, '# contact_label: ana@example.org'));
  bad(['72001,municipio,2030,x,1,'], /no run_id/, head.replace(/# run_id: .*\n/, ''));
  const lu = S.parseModel(head + '\ngeography_key,geography_level,period,variable,value,unit,lower,upper\n72001,municipio,2030,x,5,,6,7', ids);
  assert.ok(lu.errors.some(e => /bracket/.test(e)), 'lower above the value');
  assert.deepStrictEqual(S.parseModel(body(['72,municipio,2030,x,9,']), ids).series[0].years['2030'][78], 9, 'code 72 is Puerto Rico as a whole');
  // the same rows as GeoJSON
  const h = Object.fromEntries(head.split('\n').map(l => /^#\s*([a-z_]+)\s*:\s*(.*)$/.exec(l)).map(m => [m[1], m[2]]));
  const g = S.parseModel(JSON.stringify({ type: 'FeatureCollection', model: h, features: [{ type: 'Feature', geometry: null, properties: { geography_key: '72001', geography_level: 'municipio', period: 2030, variable: 'x', value: 3, unit: '' } }] }), ids);
  assert.deepStrictEqual([g.errors, g.series[0].years['2030'][0]], [[], 3]);
  assert.strictEqual(S.personal('2026-10-15'), false, 'a date is not a telephone');
  // every header field and the unit are checked, and a telephone with no separators is one (review of PR #27)
  for (const [k, v] of [['run_id', 'jane@example.org'], ['model_version', '787-555-0123'], ['assumptions_url', 'https://example.org/?to=jane@example.org'], ['model_name', 'Llamar 7875550123'], ['licence', '(787)5550123']])
    bad(['72001,municipio,2030,x,1,'], /e-mail address or a telephone/, head.replace(new RegExp(`# ${k}: .*`), `# ${k}: ${v}`));
  bad(['72001,municipio,2030,x,1,787 555 0123'], /unit holds/);
  for (const t of ['7875550123', '(787)5550123', '(787) 555-0123', '+1 787 555 0123', '939.555.0199', '2026101512']) assert.ok(S.personal(t), t);   // the last is a date-hour: a known limit
  for (const t of ['2026-10-15', '20261015', 'run 2026-10-a', '1,234,567,890', 'version 1.2.3', '1760540000', 'run-1760540000', '1234567890', '0001234567', '20261015123045']) assert.strictEqual(S.personal(t), false, t);
  bad(['72001,municipio,2030,call 787-555-0123,1,'], /variable holds a telephone/);
});

test('scenario: an imported scenario is checked like a model file, and a bad one does not hide the rest (review of PR #27)', () => {
  const S = core('scenario'), ids = readData('municipios.geojson').features.map(f => String(f.properties.GEOID).slice(0, 5)).sort(), n = ids.length + 1;
  const m = S.parseModel(fs.readFileSync(path.join(__dirname, '..', 'site', 'samples', 'model_output_sample.csv'), 'utf8'), ids);
  const good = S.make({ name: 'A', label: 'Equipo', hash: 'e=poverty_pct.f', outputs: [], models: [{ header: m.header, series: m.series }] });
  assert.deepStrictEqual(S.check(good, n), []);
  const with_ = (f) => { const s = JSON.parse(JSON.stringify(good)); f(s); return S.check(s, n); };
  const refused = (f, re, why) => { const e = with_(f); assert.ok(e.some(x => re.test(x)), `${why}: ${e}`); };
  refused(s => { s.models[0].header.model_name = 'jane@example.org'; }, /model_name holds/, 'an e-mail in a model header');
  refused(s => { s.models[0].header.model_version = '787-555-0123'; }, /model_version holds/, 'a telephone in a model header');
  refused(s => { s.models[0].header.date = 'no date'; }, /YYYY-MM-DD/, 'a date that is not a date');
  refused(s => { s.models[0].header.assumptions_url = 'javascript:alert(1)'; }, /web address/, 'a link that is not a web address');
  refused(s => { s.models[0].series[0].variable = '<img src=x onerror=alert(1)>'; }, /variable/, 'HTML as a variable');
  refused(s => { s.models[0].series[0].unit = 'jane@example.org'; }, /unit/, 'contact details as a unit');
  refused(s => { s.models[0].series[0].variable = 'call 787 555 0123'; }, /telephone/, 'a telephone as a variable');
  refused(s => { s.outputs = [{ key: 'k 787-555-0123', label: 'x', unit: '', value: 1 }]; }, /outputs/, 'a telephone in a figure key');
  refused(s => { s.models[0].series = [null]; }, /not a series/, 'a series that is null');
  refused(s => { s.models[0].series[0].years['2030'] = [1, 2]; }, /numbers by place/, 'a series of the wrong length');
  refused(s => { s.models[0].series[0].years['2030'][0] = '1'; }, /numbers by place/, 'a value that is text');
  refused(s => { delete s.created; }, /date of creation/, 'no date of creation');
  refused(s => { s.label = 7; }, /label/, 'a label that is not text');
  refused(s => { s.notes = 'x'.repeat(5000); }, /notes/, 'notes too long');
  refused(s => { s.name = 'Llamar 7875550123'; }, /telephone/, 'a telephone with no separators in the name');
  refused(s => { s.outputs = [{ key: 'k', label: 'ana@example.org', unit: '', value: 1 }]; }, /outputs/, 'contact details in a figure label');
  assert.deepStrictEqual(S.read(JSON.stringify(good), n).errors, []);
  const extra = JSON.parse(JSON.stringify(good)); extra.author = 'ana@example.org'; extra.models[0].header.owner = 'ana@example.org'; extra.models[0].series[0].note = 'x'; extra.outputs = [{ key: 'k', label: 'x', unit: '', value: 1, who: 'ana@example.org' }];
  const kept = S.read(JSON.stringify(extra), n).scenario;
  assert.ok(kept && !JSON.stringify(kept).includes('ana@example.org') && !('note' in kept.models[0].series[0]), 'fields the observatory does not know are not kept');
  assert.deepStrictEqual(S.read(JSON.stringify(good), n).scenario, JSON.parse(JSON.stringify(good)), 'a scenario the observatory saved comes back whole');
  // the saved list: a stored scenario that fails the checks is left out and the sort does not fail on it
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'scenarios.js'), 'utf8');
  assert.match(src, /all\.filter\(x => !S_\.check\(x, EC\.PR \+ 1\)\.length\)/, 'list() keeps only scenarios that pass');
  assert.match(src, /String\(q\.created\)\.localeCompare/, 'the sort cannot throw on a missing date');
  assert.doesNotMatch(src.slice(src.indexOf('async function list'), src.indexOf('async function save')), /\.sort\([^)]*\)\s*;\s*}\s*catch/, 'a sort error is not taken for "no IndexedDB"');
});

test('scenario: a scenario keeps its view and figures, a file is checked, two are compared', () => {
  const S = core('scenario');
  const a = S.make({ name: 'Ruta A', label: 'Equipo FPR', hash: '#c=18.2,-66.2,9&e=poverty_pct.f', outputs: [{ key: 'route.length_km', label: 'length', unit: 'km', value: 10 }, { key: 'route.residents', label: 'residents', unit: '', value: 2000 }] });
  const b = S.make({ name: 'Ruta B', hash: 'c=18.2,-66.2,9', outputs: [{ key: 'route.length_km', label: 'length', unit: 'km', value: 12.5 }, { key: 'route.places', label: 'places', unit: '', value: 40 }] });
  assert.strictEqual(a.hash.startsWith('#'), false);
  assert.deepStrictEqual(S.check(a), []);
  const d = S.diff(a, b);
  assert.deepStrictEqual(d.find(r => r.key === 'route.length_km'), { key: 'route.length_km', label: 'length', unit: 'km', a: 10, b: 12.5, delta: 2.5, pct: 25 });
  assert.deepStrictEqual([d.find(r => r.key === 'route.residents').b, d.find(r => r.key === 'route.places').a], [null, null], 'a figure only one has');
  assert.deepStrictEqual(S.read(JSON.stringify(a)).errors, []);
  assert.ok(S.read('{').errors.length && S.read(JSON.stringify({ ...a, notes: 'call 787-555-0123' })).errors.some(e => /telephone/.test(e)));
  assert.ok(S.read(JSON.stringify({ ...a, hash: '<script>' })).errors.some(e => /link/.test(e)));
  const s1 = { variable: 'x', unit: '', years: { 2030: [1, null, 3], 2035: [1, 1, 1] } }, s2 = { variable: 'x', unit: '', years: { 2030: [2, 2, null] } };
  assert.deepStrictEqual(S.diffSeries(s1, s2).years, { 2030: [1, null, null] }, 'B − A where both have a value, for the periods both have');
});

test('3D view: the columns from any dataset load the engine only when chosen, with the versions the map page loads (plan item 16, B7)', () => {
  const site = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8');
  const html3d = site('3d.html'), index = site('index.html'), js = site('js/twin3d.js');
  const list = eval(/const ENGINE_JS = (\[[^\]]*\])/.exec(js)[1]);
  const loads = (html) => [...html.matchAll(/<script src="js\/(core\/[a-z]+\.js\?v=\d+)"/g)].map(m => m[1]);
  const onUse = [...site('js/app.js').matchAll(/'js\/(core\/[a-z]+\.js\?v=\d+)'/g)].map(m => m[1]);   // what the map loads on first use (the hexagons since 2026-11-09)
  const shell = [...site('js/econ_shell.js').matchAll(/'js\/(core\/[a-z]+\.js\?v=\d+)'/g)].map(m => m[1]);   // the Economy tab's engine, loaded on first use where the page loaded it before (Make room 4)
  const page = loads(index), at = page.findIndex(f => f.startsWith('core/legend.js'));
  const idx = [...page.slice(0, at), ...shell, ...page.slice(at), ...onUse], d3 = loads(html3d);
  assert.ok(list.length >= 9 && list.every(f => idx.includes(f)), `every script ENGINE_JS adds is the one index.html loads, same version: ${list.filter(f => !idx.includes(f))}`);
  assert.ok(list.every(f => !html3d.includes(f.split('?')[0])), '3d.html does not load the engine at start');
  const upToDatasets = idx.slice(0, idx.findIndex(f => f.startsWith('core/datasets.js')) + 1);
  assert.deepStrictEqual(upToDatasets.filter(f => !d3.includes(f) && !list.includes(f)), [], 'every core script the datasets need is on the 3D page or in ENGINE_JS');
  assert.match(html3d, /<option value="__any">/);
  // the columns build the layer the Economy tab adds (classes held across years) and give the chip the whole period resolution (review of PR #30)
  const vec = js.slice(js.indexOf('function engineVec'), js.indexOf('function engineDraw'));
  assert.match(vec, /function engineVec\(key, o = \{\}\)[\s\S]*E\.makeLayer\(key, 'fill', o, \[\]\)/);   // the menus pass nothing (the Economy tab's default rescaling); the chat (ask3d.js) passes the rescaling of its answer
  assert.match(vec, /E\.chip\(L, r\)/);
  assert.doesNotMatch(vec, /fixed: false/);
  const crime = E.V.crime_type1, before = crime.ys[0] - 2, L1 = E.makeLayer('crime_type1', 'fill', {}, []);
  assert.match(E.chip(L1, E.resolve('crime_type1', before)), /first data/, 'a year before the first data says so, not "latest at or before"');
  assert.strictEqual(L1.fixed, !crime.static, 'classes held across years unless the dataset has one year');
  // the map page's Spanish, merged into the 3D page when the engine loads, agrees with the 3D page's own on every shared term
  const bundle = (f) => { let d; const I18N = { add: (o) => { d = o; } }; new Function('I18N', site('i18n/' + f))(I18N); return d; };
  const m = { ...bundle('es.map.js'), ...bundle('es.map.economy.js') }, t = bundle('es.threed.js');   // twin3d.js engineLoad reads both
  assert.deepStrictEqual(Object.keys(t).filter(k => k in m && JSON.stringify(m[k]) !== JSON.stringify(t[k])), []);
});

test('study areas: a file of polygons is read whole or refused, keeps only names and shapes, and round-trips (plan item 16, C4)', () => {
  const S = core('study');
  const sq = (x, y, d = 0.01) => [[[x, y], [x + d, y], [x + d, y + d], [x, y + d], [x, y]]];
  const fc = (features) => JSON.stringify({ type: 'FeatureCollection', features });
  const F = (props, geometry) => ({ type: 'Feature', properties: props, geometry });
  const ok = S.parse(fc([F({ name: 'Barrio A', owner: 'ana@example.org', pop: 5 }, { type: 'Polygon', coordinates: sq(-66.1, 18.4) }), F({ NOMBRE: 'Barrio A' }, { type: 'Polygon', coordinates: [sq(-66.05, 18.4)[0].slice(0, 4)] })]));
  assert.deepStrictEqual(ok.errors, []);
  assert.deepStrictEqual(ok.areas.map(a => a.name), ['Barrio A', 'Barrio A (2)'], 'names from name or NOMBRE; a repeated name is told apart');
  assert.ok(!JSON.stringify(ok.areas).includes('ana@example.org') && !('properties' in ok.areas[0]), 'only the name and the shape are kept');
  assert.strictEqual(ok.areas[1].geometry.coordinates[0].length, 5, 'an open ring is closed');
  assert.strictEqual(S.parse(JSON.stringify({ type: 'Polygon', coordinates: sq(-66.1, 18.4) })).areas.length, 1, 'a bare polygon is one area');
  const bad = (text, re) => { const r = S.parse(text); assert.ok(r.errors.some(e => re.test(e)), `${re}: ${r.errors}`); assert.deepStrictEqual(r.areas, [], 'nothing is kept from a file with an error'); };
  bad(fc([F({}, { type: 'Point', coordinates: [-66.1, 18.4] })]), /not a polygon/);
  bad(fc([F({}, { type: 'Polygon', coordinates: [[[200000, 2000000], [210000, 2000000], [210000, 2010000], [200000, 2000000]]] })]), /not longitude and latitude/);
  bad(fc([F({}, { type: 'Polygon', coordinates: sq(-80.1, 25.7) })]), /outside Puerto Rico/);
  bad(fc([F({ name: 'Llamar 787-555-0123' }, { type: 'Polygon', coordinates: sq(-66.1, 18.4) })]), /telephone/);
  bad(fc(Array.from({ length: 201 }, () => F({}, { type: 'Polygon', coordinates: sq(-66.1, 18.4) }))), /more than 200 areas/);
  bad(fc([F({}, { type: 'Polygon', coordinates: [[[-66.1, 18.4], [-66.09, 18.4], [-66.1, 18.4]]] })]), /fewer than three corners/);
  bad('{', /not valid JSON/);
  // a set: made, exported, read back
  const set = S.make({ name: 'Corredor', source: 'Equipo FPR', description: 'Prueba', areas: ok.areas });
  assert.deepStrictEqual(S.check(set), []);
  const back = S.read(JSON.stringify(S.toGeoJSON(set)));
  assert.deepStrictEqual([back.errors, back.set && back.set.id, back.set && back.set.areas.length], [[], set.id, 2], 'an exported file reads back as the same set');
  assert.ok(S.read(fc([F({}, { type: 'Polygon', coordinates: sq(-66.1, 18.4) })])).errors.some(e => /no "study" description/.test(e)), 'plain GeoJSON needs a name and source from the form');
  assert.ok(S.check({ ...set, source: '' }).some(e => /no source/.test(e)));
  assert.ok(S.check({ ...set, description: 'escriba a ana@example.org' }).some(e => /e-mail/.test(e)));
  assert.ok(S.check({ ...set, areas: [{ name: 'x', geometry: { type: 'Polygon', coordinates: sq(-90, 18.4) } }] }).some(e => /outside Puerto Rico/.test(e)), 'a stored set is checked like a file');
});

test('study areas: area, point in polygon and the grid of points', () => {
  const S = core('study'), d = 0.01, x = -66.1, y = 18.2;
  const g = { type: 'Polygon', coordinates: [[[x, y], [x + d, y], [x + d, y + d], [x, y + d], [x, y]], [[x + .0025, y + .0025], [x + .0075, y + .0025], [x + .0075, y + .0075], [x + .0025, y + .0075], [x + .0025, y + .0025]]] };
  const full = d * 111.32 * Math.cos((y + d / 2) * Math.PI / 180) * d * 110.574;
  assert.ok(Math.abs(S.areaKm2(g) - full * 0.75) < 1e-9, 'the hole is taken out');
  assert.deepStrictEqual([S.inside(g, x + .001, y + .001), S.inside(g, x + .005, y + .005), S.inside(g, x - .001, y)], [true, false, false]);
  const s = S.sample(g, 4000);
  assert.ok(s.pts.every(([px, py]) => S.inside(g, px, py)) && Math.abs(s.pts.length * s.cellKm2 - S.areaKm2(g)) < 1e-9, 'every grid point is inside and they add up to the area');
  assert.ok(Math.abs(s.pts.length / 4000 - 0.75) < 0.05, `about three quarters of the grid (${s.pts.length})`);
});

test('study areas: an area drawn on a municipio gives that municipio back; a box across municipios is estimated and says how', () => {
  const S = core('study'), X = tabEngine(), fc = readData('municipios.geojson'), muni = readData('municipalities.json'), at = new Map(fc.features.map(f => [f.properties.municipality, f.geometry]));
  const names = X.geo.names.slice(0, X.geo.pr), munis = names.map(n => at.get(n)), pop = names.map(n => muni[n].population_2020);
  const blocks = readData('population_blocks.json'), flood = readData('flood.geojson').features.filter(f => f.properties.SFHA_TF !== 'F').map(f => f.geometry);
  const i = names.indexOf('San Juan'), m = S.measure(munis[i], { blocks, munis, stops: [], flood });
  assert.ok(Math.abs(m.residents - pop[i]) / pop[i] < 0.002, `residents by block centroid ${m.residents} vs ${pop[i]}`);
  // far from a stop: more than an 800 m walk (the 5th value of a block, 2026-10-16), never fewer than in a straight line
  const inSJ = blocks.filter(b => S.inside(munis[i], b[0], b[1]));
  assert.strictEqual(m.far, inSJ.filter(b => b[4] > 800).reduce((a, b) => a + b[2], 0), 'far by walking');
  assert.ok(m.far >= inSJ.filter(b => b[3] > 800).reduce((a, b) => a + b[2], 0), 'a walk is never shorter than the straight line');
  assert.strictEqual(S.measure(munis[i], { blocks: blocks.map(b => b.slice(0, 4)), munis, stops: [] }).far, inSJ.filter(b => b[3] > 800).reduce((a, b) => a + b[2], 0), 'an older file without the walk: the straight line');
  for (const k of ['population', 'qcew_jobs', 'qcew_wages']) { const e = S.estimate(X, m, k, null, pop); assert.deepStrictEqual([e.method, e.value], ['whole', X.values(k, {}).values[i]], k); }
  for (const k of ['poverty_pct', 'median_hh_income']) { const e = S.estimate(X, m, k, null, pop); assert.deepStrictEqual([e.method, e.value], ['avg-residents', X.values(k, {}).values[i]], k); }
  // the grid index finds the same flood points as testing every polygon, and the share is of the land
  const land = S.sample(munis[i]).pts.filter(([px, py]) => munis.some(g => S.inside(g, px, py)));
  const wet = land.filter(([px, py]) => flood.some(g => S.inside(g, px, py)));
  assert.ok(Math.abs(m.flood - wet.length / land.length * 100) < 1e-9, `flood share ${m.flood} vs ${wet.length / land.length * 100}`);
  const box = { type: 'Polygon', coordinates: [[[-66.12, 18.38], [-66.02, 18.38], [-66.02, 18.45], [-66.12, 18.45], [-66.12, 18.38]]] }, b = S.measure(box, { blocks, munis, stops: [] });
  assert.ok(b.munis.length >= 3, 'the box crosses several municipios');
  const given = b.munis.reduce((a, p) => a + p.residents, 0);
  assert.ok(given <= b.residents && given / b.residents > 0.999, `the residents inside are given to their municipio, but for blocks whose center is off the coast (${given} of ${b.residents})`);
  const p = S.estimate(X, b, 'population', null, pop), pv = S.estimate(X, b, 'poverty_pct', null, pop), j = S.estimate(X, b, 'qcew_jobs', null, pop);
  assert.deepStrictEqual([p.method, pv.method, j.method], ['residents', 'avg-residents', 'residents']);
  const share = b.munis.reduce((a, q) => a + X.values('population', {}).values[q.i] * q.residents / pop[q.i], 0);
  assert.ok(Math.abs(p.value - share) < 1e-6 && p.coverage === 1);
  const vals = b.munis.filter(q => q.residents).map(q => X.values('poverty_pct', {}).values[q.i]);
  assert.ok(pv.value >= Math.min(...vals) && pv.value <= Math.max(...vals), 'a weighted average lies between the municipios averaged');
  const landKey = X.list().find(v => v.type === 'count' && v.unit === 'km²').key, lv = S.estimate(X, b, landKey, null, pop);
  assert.ok(lv && lv.method === 'land', `a total of land is shared by land (${landKey})`);
  const people = X.list().filter(v => v.type === 'count' && (v.residents || v.denom)).map(v => S.estimate(X, b, v.key, null, pop)).filter(Boolean);
  assert.ok(people.length > 20 && people.every(e => e.method === 'residents'), 'counts of people (survey counts, exposure counts) are shared by residents');
});

test('study areas: the area around a point is a circle or a ring of the right area, and passes the checks (GIS tools step 1, decision 93)', () => {
  const S = core('study');
  for (const [r, r0] of [[400, 0], [800, 0], [5000, 0], [1600, 800], [20000, 0]]) {
    const g = S.ring(-66.06, 18.40, r, r0), want = Math.PI * (r * r - r0 * r0) / 1e6;
    assert.ok(Math.abs(S.areaKm2(g) / want - 1) < 1e-4, `${r0}-${r} m: ${S.areaKm2(g)} km² against ${want}`);
    assert.strictEqual(S.inside(g, -66.06, 18.40), r0 === 0, 'the center is in a circle and in the hole of a ring');
  }
  const off = S.ring(-66.06, 18.40, 1000);   // 1 km east and north of the center: just inside and just outside the edge
  const kx = 111320 * Math.cos(18.40 * Math.PI / 180);
  assert.deepStrictEqual([S.inside(off, -66.06 + 990 / kx, 18.40), S.inside(off, -66.06 + 1010 / kx, 18.40), S.inside(off, -66.06, 18.40 + 1010 / 110574)], [true, false, false]);
  const set = S.make({ name: 'Areas around points', source: 'Drawn in this browser (Area around a point)', areas: [{ name: '800 m around 18.4000, -66.0600 (San Juan)', geometry: S.ring(-66.06, 18.40, 800) }, { name: '800 m to 1.6 km around 18.4000, -66.0600', geometry: S.ring(-66.06, 18.40, 1600, 800) }] });
  assert.deepStrictEqual(S.check(set), [], 'coordinates in a name are not taken for a telephone number');
  const back = S.read(JSON.stringify(S.toGeoJSON(set)));
  assert.strictEqual(back.set.areas.length, 2, 'exported and read back');
  assert.ok(S.check(S.make({ name: 'x', source: 'y', areas: [{ name: 'a', geometry: S.ring(-68.05, 18.1, 20000) }] })).some(e => /outside Puerto Rico/.test(e)), 'a circle that leaves the box is refused');
});

test('study areas: zonal statistics of a surface image and barrio estimates (GIS tools step 1)', () => {
  const S = core('study');
  // a 2 x 2 image over a box: the step of each pixel is its place on a scale of 64 from 20 to 40; 0 = no value
  const f = S.raster(new Uint8Array([1, 64, 0, 32]), 2, 2, [-67, 18, -66, 19], 20, 40, 64);
  assert.deepStrictEqual([f(-66.9, 18.9), f(-66.1, 18.9), f(-66.9, 18.1), f(-65.5, 18.5)], [20, 40, null, null]);
  assert.ok(Math.abs(f(-66.1, 18.1) - (20 + 31 / 63 * 20)) < 1e-12);
  // a municipio's own boundary measured against a constant surface and its barrios: the barrio estimate of a barrio's own shape is that barrio's value
  const fc = readData('municipios.geojson'), munis = fc.features.map(f => f.geometry), bar = readData('barrios.geojson').features, veg = readData('vegetation_barrio.json');
  const v = veg.vars.find(x => x.key === 'veg_ndvi_med'), y = Object.keys(v.years).sort().pop(), byId = new Map(veg.geo.ids.map((id, i) => [id, v.years[y][i]]));
  const vals = bar.map(b => { const x = byId.get(b.properties.geoid); return x == null ? null : x; });
  const k = vals.findIndex((x, i) => x != null && bar[i].properties.km2 > 5);
  const ctx = { blocks: [], munis, stops: [], surfaces: [{ key: 'flat', at: () => 31.5 }, { key: 'west', at: (x) => x < bar[k].geometry.coordinates.flat(3)[0] ? 30 : null }], zones: { geoms: bar.map(b => b.geometry), vals: { veg: vals } } };
  const m = S.measure(bar[k].geometry, ctx);
  assert.ok(Math.abs(m.surf.flat.mean - 31.5) < 1e-12 && m.surf.flat.cover > 0.99, `a flat surface gives its value everywhere (${m.surf.flat.cover})`);
  assert.ok(m.surf.west.cover < 1, 'a surface with no value on part of the land says how much has one');
  assert.ok(Math.abs(m.zone.veg.value - vals[k]) < 1e-9, `the barrio's own shape gives its value (${m.zone.veg.value} against ${vals[k]})`);
  // a circle across barrios: the estimate lies between the values of the barrios it covers
  const c = S.ring(-66.06, 18.40, 1600), mc = S.measure(c, ctx), covered = vals.filter((x, i) => x != null && S.sample(c, 2000).pts.some(([px, py]) => S.inside(bar[i].geometry, px, py)));
  assert.ok(covered.length > 1 && mc.zone.veg.value >= Math.min(...covered) - 1e-9 && mc.zone.veg.value <= Math.max(...covered) + 1e-9, `${mc.zone.veg.value} within ${Math.min(...covered)}-${Math.max(...covered)}`);
  assert.strictEqual(S.measure(c, { blocks: [], munis, stops: [] }).surf, undefined, 'not measured unless asked');
});

test('study areas: Area around a point opens from Tools > Map tools (decision 97), and its texts have Spanish (GIS tools step 1)', () => {
  const eco = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'economy.js'), 'utf8'), index = fs.readFileSync(path.join(__dirname, '..', 'site', 'index.html'), 'utf8');
  assert.match(index, /data-mt="b:study:saAroundH"/, 'the entry in Tools > Map tools');
  assert.match(fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'maptools.js'), 'utf8'), /ecBenchOpen\(view\)/, 'the entry opens the Study areas view');
  assert.match(eco, /v === 'table' \|\| v === 'study'/, 'a link in a pop-up still opens the Study areas view');
  const sa = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'studyareas.js'), 'utf8');
  assert.match(sa, /addJs\('js\/core\/surfscale\.js\?v=4'\)/, 'the heat images load with the map\'s own reader, on request');
  assert.match(fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'app.js'), 'utf8'), /addJs\('js\/core\/surfscale\.js\?v=4'\)/, 'the same version as the map, so the file is not loaded twice');
});

test('study areas: the view loads on first use and every text has Spanish', () => {
  const eco = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'economy.js'), 'utf8'), index = fs.readFileSync(path.join(__dirname, '..', 'site', 'index.html'), 'utf8');
  assert.match(eco, /\['study', T\('Study areas'\)\]/);
  assert.match(eco, /'js\/core\/study\.js\?v=8', 'js\/studyareas\.js\?v=17'/);
  assert.ok(!/studyareas\.js|core\/study\.js/.test(index), 'not in the first load of the map');
  const es = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'es', 'studyareas.json'), 'utf8'));
  const sa = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'studyareas.js'), 'utf8'), block = sa.slice(sa.indexOf('const METHOD = {'), sa.indexOf('};', sa.indexOf('const METHOD = {')));
  const methods = [...block.matchAll(/: '([^']+)',/g)].map(m => m[1]);
  assert.strictEqual(methods.length, 5);
  assert.deepStrictEqual(methods.filter(m => !(m in es)), [], 'the method texts reach the screen through T(variable), so the checker cannot see them');
});

test('study areas: a small area keeps its share, and a whole municipio plus a piece of another is not called whole (review of PR #32)', () => {
  const S = core('study'), X = tabEngine(), muni = readData('municipalities.json'), at = new Map(readData('municipios.geojson').features.map(f => [f.properties.municipality, f.geometry]));
  const names = X.geo.names.slice(0, X.geo.pr), munis = names.map(n => at.get(n)), pop = names.map(n => muni[n].population_2020), ctx = { blocks: readData('population_blocks.json'), munis, stops: [] };
  const sq = { type: 'Polygon', coordinates: [[[-66.06, 18.40], [-66.055, 18.40], [-66.055, 18.405], [-66.06, 18.405], [-66.06, 18.40]]] }, sj = names.indexOf('San Juan');
  const m = S.measure(sq, ctx), inSJ = m.munis.find(p => p.i === sj).residents;
  assert.ok(m.residents > 500 && inSJ / pop[sj] < 0.01, `a neighborhood-size square: ${m.residents} residents, ${(inSJ / pop[sj] * 100).toFixed(2)}% of San Juan`);
  for (const k of ['population', 'qcew_jobs', 'qcew_wages']) {
    const e = S.estimate(X, m, k, null, pop);
    assert.ok(e && e.method === 'residents', `${k}: a small area keeps its share (${e && e.method})`);
  }
  const e = S.estimate(X, m, 'population', null, pop);
  assert.ok(Math.abs(e.value - X.values('population', {}).values[sj] * inSJ / pop[sj]) < 1e-6, 'San Juan population × the share of its residents inside');
  const ca = at.get('Cataño'), both = { type: 'MultiPolygon', coordinates: [...(ca.type === 'Polygon' ? [ca.coordinates] : ca.coordinates), sq.coordinates] };
  const mb = S.measure(both, ctx), eb = S.estimate(X, mb, 'population', null, pop), alone = X.values('population', {}).values[names.indexOf('Cataño')];
  assert.strictEqual(eb.method, 'residents', 'Cataño plus a piece of San Juan is not a sum of whole municipios');
  assert.ok(eb.value > alone, `the piece of San Juan is kept (${eb.value.toFixed(0)} > ${alone})`);
  const whole = S.estimate(X, S.measure(at.get('Cataño'), ctx), 'population', null, pop);
  assert.deepStrictEqual([whole.method, whole.value], ['whole', alone], 'Cataño alone is still its exact total');
});

test('study areas: the view measures one area at a time and stops when the choice changes', () => {
  const sa = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'studyareas.js'), 'utf8'), f = sa.slice(sa.indexOf('function measureAll'), sa.indexOf('async function results'));
  assert.match(f, /for \(let k = 0; k < set\.areas\.length; k\+\+\)/);
  assert.match(f, /await new Promise\(r => setTimeout\(r, 0\)\)/, 'the page gets the hand between areas');
  assert.match(f, /run = \(\) => `\$\{st\.sel\}\|\$\{st\.extra\}\|\$\{st\.land\}\|\$\{set\.areas\.length\}\|\$\{st\.pts \? st\.pts\.v : 0\}`/, 'the run is the set, the measures asked for, the number of areas and the file of points');
  assert.match(f, /if \(run\(\) !== key\) return null;/, 'another set, the extra or land measures, or an area added stop the work');
  assert.match(f, /if \(running && running\.key === key\) return running\.p;/, 'a redraw while measuring joins the run in progress');
  assert.match(sa, /await save\(set\); st\.sel = set\.id; st\.res = null; st\.page = 0;/, 'a new set opens on its first page');
  assert.match(sa, /Measuring area \{k\} of \{n\}…/);
});

test('study areas: the banded point-in-polygon test gives the same answer as testing every edge', () => {
  const S = core('study'), fc = readData('municipios.geojson').features, flood = readData('flood.geojson').features.filter(f => f.properties.SFHA_TF !== 'F');
  const plain = (g, x, y) => { const ring = (r) => { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
    return (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).some(p => ring(p[0]) && !p.slice(1).some(ring)); };
  let s = 20261015; const rnd = () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };   // mulberry32
  const big = [...fc.map(f => f.geometry), ...flood.map(f => f.geometry)].filter(g => (g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0]).length >= 64).slice(0, 120);
  let n = 0, inside = 0, seen = new Set();
  for (const g of big) {
    const b = S.bbox(g);
    for (let k = 0; k < 60; k++) { const x = b[0] + rnd() * (b[2] - b[0]), y = b[1] + rnd() * (b[3] - b[1]), a = S.inside(g, x, y); assert.strictEqual(a, plain(g, x, y), `${x}, ${y}`); n++; if (a) inside++; seen.add(`${x}|${y}`); }
  }
  assert.ok(big.length >= 100 && seen.size === n && inside > n * 0.2 && inside < n * 0.9, `${n} distinct points on ${big.length} large polygons, ${inside} inside`);
});

test('data files: a failed or cut-off download is tried again with the browser cache bypassed, and no page fetches data any other way', async () => {
  const site = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8');
  const common = site('js/common.js'), src = common.slice(common.indexOf('async function fetchRetry'), common.indexOf('const fetchJson'));
  const calls = [];
  const answers = [{ ok: false, status: 404 }, { ok: true, json: async () => { throw new SyntaxError('cut'); } }, { ok: true, json: async () => ({ n: 165 }) }];
  const fetchRetry = new Function('fetch', 'setTimeout', `${src}; return fetchRetry;`)(async (p, o) => { calls.push(o && o.cache || 'default'); return answers[calls.length - 1]; }, (f) => f());
  assert.deepStrictEqual(await fetchRetry('data/x.json'), { n: 165 });
  assert.deepStrictEqual(calls, ['default', 'reload', 'reload'], 'the retries bypass a cached bad answer');
  const always = new Function('fetch', 'setTimeout', `${src}; return fetchRetry;`)(async () => ({ ok: false, status: 500 }), (f) => f());
  await assert.rejects(always('data/x.json'), /500/, 'after three tries the error reaches the page');
  for (const f of fs.readdirSync(path.join(__dirname, '..', 'site', 'js')).filter(f => f.endsWith('.js') && f !== 'common.js')) {
    const bare = site('js/' + f).split('\n').filter(l => /\bfetch\(/.test(l) && !/nominatim/.test(l));
    assert.deepStrictEqual(bare, [], `${f} reads data through fetchJson or fetchRetry (common.js)`);
  }
});
// ── follow-ups to PRs #55 and #56 (branch conditions-followups) ──
test('chat: drive time to a hospital and nonprofit organizations reach their datasets in both languages, and the old answers stay', () => {
  const env = chatEnv().env, X = tabEngine(), cat = readData('catalog_index.json'), F = cat.index.fields;
  env.setApi({ datasets: () => X.info(), meta: (k) => X.V[k] || null, dictId: (k) => X.dictId(k), places: () => X.geo.names.slice() });
  env.CH.ask = {}; cat.index.rows.forEach(r => { if (r[F.indexOf('ask')]) env.CH.ask[r[F.indexOf('id')]] = r[F.indexOf('ask')]; });
  const p = (q) => env.chParse(q);
  for (const [q, keys, intent] of [
    ['drive time to a hospital by municipality', ['hosp_drive_min'], 'show'], ['tiempo en carro al hospital por municipio', ['hosp_drive_min'], 'show'],
    ['drive time to the hospital in Utuado', ['hosp_drive_min'], 'value'], ['tiempo de viaje al hospital en Orocovis', ['hosp_drive_min'], 'value'],
    ['¿Dónde hay más organizaciones sin fines de lucro?', ['npo_all'], 'rank'], ['organizaciones sin fines de lucro en Ponce', ['npo_all'], 'value'], ['nonprofit organizations', ['npo_all'], 'show'],
    ['trabajadores de organizaciones sin fines de lucro en Ponce', ['nonprofit_worker_pct'], 'value'], ['nonprofit workers', ['nonprofit_worker_pct'], 'show'], ['sin fines de lucro', ['nonprofit_worker_pct'], 'show'],
  ]) { const r = p(q); assert.deepStrictEqual([r.keys, r.intent], [keys, intent], q); }
  assert.deepStrictEqual(p('hospitals').keys, ['jobs_naics_62'], 'the word "hospitals" alone stays with the health-care jobs rule');
});
test('classify: when the lowest value fills two classes or more, it gets one class and the values above it get the other four', () => {
  const zeros = [...new Array(80).fill(0), ...Array.from({ length: 20 }, (_, i) => i + 1)];   // 80 places at 0, 20 at 1 ... 20
  const b = classify.make(zeros, { method: 'quantile' });
  assert.deepStrictEqual(b.edges, [0, 0, 6, 11, 16, 20]);
  assert.deepStrictEqual(legend.counts(b, zeros), [80, 6, 5, 5, 4], 'no empty class');
  assert.deepStrictEqual(classify.inner(zeros, 5), [0, 6, 11, 16], 'the 3D columns cut the same classes');
  const pool = [0, 0, 1, 2, 3, 4, 5, 6, 7, 8];   // the lowest value fills one class at most: the quantiles as before
  assert.deepStrictEqual(classify.make(pool, {}).edges, classify.quantileEdges(pool, 5));
  assert.deepStrictEqual(classify.make([3, 3, 3], {}).edges, [3, 3, 3, 3, 3, 3], 'every value the same');
  assert.deepStrictEqual(classify.make([0, 0, 0, 0, 0, 0, 0, 0, 0, 5], { k: 3 }).edges, [0, 0, 5, 5], 'three classes (a bivariate layer) too');
  const one = classify.make([...new Array(77).fill(0), 14], {});   // lead: one municipio above 0
  assert.deepStrictEqual(one.edges, [0, 0, 14, 14, 14, 14]);
  assert.deepStrictEqual([0, 1, 2, 3, 4].map(i => classify.single(one, i)), [true, false, true, true, true]);
  assert.deepStrictEqual([0, 1, 2, 3, 4].map(i => classify.hidden(one, i)), [false, false, true, true, true], 'a legend leaves out the classes no value can fall in');
  assert.strictEqual(classify.single(classify.make([-2, 3], { div: true, center: 0 }), 0), false, 'a scale around a center has no single-value class');
});
test('legend: the non-attainment datasets name a class of 0 once and show no empty "0.00% to 0.00%" class, by municipio and by barrio', () => {
  const X = tabEngine();
  for (const key of ['epa_naa_so2_pct', 'epa_naa_lead_pct']) {
    const L = X.makeLayer(key, 'fill', {}, []); L.id = 1;
    const e = X.evaluate([L])[1], html = stackLegend.blocks(X, [L], { 1: e }, false);
    assert.ok(!/0\.0+% to 0\.0+%/.test(html), `${key}: ${html}`);
    assert.ok(/<span class="sw" style="background:[^"]+"><\/span>0\.0+%<small>\d+<\/small>/.test(html), `${key}: the class of 0 is named by its value ("0.00%")`);
    const b = X.breaks(L, e.y), n = legend.counts(b, e.a.slice(0, X.geo.pr));
    assert.ok(n.every((c, i) => c > 0 || classify.hidden(b, i)), `${key}: every class it shows holds a municipio (${n})`);
  }
  const cb = readData('conditions_barrio.json');
  for (const key of ['epa_naa_so2_pct', 'epa_naa_lead_pct']) {
    const a = Object.values(cb.vars.find(v => v.key === key).years)[0].filter(x => x != null).sort((p, q) => p - q), b = classify.make(a, {}), n = legend.counts(b, a);
    assert.ok(n.every((c, i) => c > 0 || classify.hidden(b, i)) && n[0] > 800, `${key} by barrio: ${n}`);
  }
});
test('drive time to a hospital: the dataset says which barrios at 0 are uncertain, in its card and in Spanish', () => {
  const X = tabEngine();
  for (const key of ['hosp_drive_min', 'hosp_road_km']) {
    const c = reliability.cautions(X.V[key]).find(x => x.kind === 'dataset');
    assert.ok(c && /HHS/.test(c.text) && /0/.test(c.text), key);
  }
  assert.ok(!reliability.cautions(X.V.poverty_pct).some(x => x.kind === 'dataset'), 'a dataset with no caution of its own gets none');
  const es = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'es', 'labels_conditions.json'), 'utf8'));
  assert.ok(es[X.V.hosp_drive_min.caution], 'the caution has Spanish');
  const s = readData('conditions_series.json'), notes = s.notes.hospitals;
  assert.strictEqual(notes.located.osm + notes.located.osm_near + notes.located.hhs, notes.hospitals, 'every hospital is placed one way');
  assert.ok(s.vars.find(v => v.key === 'hosp_drive_min').definition.includes(`HHS's point falls in another barrio for ${notes.hhs_point_in_another_barrio}`), 'the definition gives the count');
});

// ── the dictionary page in Spanish (PR #10): the Spanish of dictionary_src/es/ next to the English, held entries in English ──
test('dictionary page: Spanish names, labels and how to read it are shown in Spanish, English is marked lang="en", and a held entry stays English', () => {
  const js = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'dictionary.js'), 'utf8');
  const block = js.slice(js.indexOf('const esOf ='), js.indexOf('// ── Load ──'));
  const make = (lang) => new Function('LANG', 'D', 'esc', 'I18N', 'window', `${block}; return { esOf, tx, lbl, lblHtml, nameOf };`)(lang,
    { data: { labels_es: { 'US dollars': 'dólares de EE. UU.', Municipality: 'Municipio' } } },
    (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'), { en: (h) => lang === 'es' && h ? `<span lang="en">${h}</span>` : h }, { addEventListener() {} });
  const es = make('es'), en = make('en');
  const open = { name: 'Jobs', name_es: 'Empleos', how_to_read: 'Read <it>.', how_to_read_es: 'Léalo.', unit: 'US dollars' };
  const held = { name: 'Federal grants', unit: 'US dollars', hold_es: true };
  assert.strictEqual(es.tx(open, 'name'), 'Empleos');
  assert.strictEqual(es.tx(open, 'how_to_read'), 'Léalo.', 'the Spanish of the detail file is shown once the entry is opened');
  assert.strictEqual(en.tx(open, 'how_to_read'), 'Read &lt;it>.', 'the English page shows the English, escaped');
  assert.strictEqual(es.tx(held, 'name'), '<span lang="en">Federal grants</span>', 'a text without Spanish is marked English');
  assert.strictEqual(es.lblHtml(open.unit, open), 'dólares de EE. UU.');
  assert.strictEqual(es.lblHtml(held.unit, held), '<span lang="en">US dollars</span>', 'a held entry shows its labels in English, even a label that has Spanish');
  assert.strictEqual(en.lblHtml(open.unit, open), 'US dollars');
  assert.strictEqual(es.lblHtml('Disaster recovery'), '<span lang="en">Disaster recovery</span>');
  assert.deepStrictEqual([es.nameOf(open), es.nameOf(held), en.nameOf(open)], ['Empleos', 'Federal grants', 'Jobs']);
  assert.doesNotMatch(js, /dictionary\.es\.json/, 'the Spanish comes with the list and detail files, not a separate file');
});
