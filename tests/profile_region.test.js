// Tests for the regional area profile (site/js/profile_region.js) and the regions file (site/data/geo/regions.json, regions.py).
// Run: node --test tests/profile_region.test.js   (python -m unittest tests.test_core_js runs it too)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..'), DATA = path.join(ROOT, 'site', 'data');
const read = (f) => JSON.parse(fs.readFileSync(path.join(DATA, f), 'utf8'));
const PR = require(path.join(ROOT, 'site', 'js', 'profile_region.js'));
const REG = read('geo/regions.json').regions;

// A small stand-in for the engine (the adapters give each dataset its type; the housing file does not, so a test names it): the series files, with calc() and moe() of one dataset in one year, in the order of economy_series.json's ids
const V = {}, ids = read('economy_series.json').geo.ids;
for (const f of ['economy_series.json', 'housing_series.json', 'population_series.json', 'labor_sex_series.json']) {
  const d = read(f), at = new Map(d.geo.ids.map((g, i) => [g, i]));
  for (const v of d.vars) {
    if (V[v.key] || !v.years) continue;   // a series the economy file only names (from: housing) is read from its own file
    const align = (o) => o && Object.fromEntries(Object.entries(o).map(([y, a]) => [y, ids.map(g => at.has(g) ? a[at.get(g)] : null)]));
    V[v.key] = { ...v, years: align(v.years), moe: align(v.moe) };
  }
}
const X = { V, calc: (L, y) => (V[L.key].years[y] || null), moe: (L, y) => (V[L.key].moe ? V[L.key].moe[y] || null : null) };
const idx = (g) => ids.indexOf(g);

test('regions.json: the ERSV has its 15 municipios and the seven tourism regions cover the 78 once each', () => {
  const ersv = REG.find(r => r.id === 'ersv');
  assert.strictEqual(ersv.ids.length, 15);
  const tour = REG.filter(r => r.kind === 'tourism');
  assert.strictEqual(tour.length, 7);
  const all = tour.flatMap(r => r.ids);
  assert.strictEqual(all.length, 78); assert.strictEqual(new Set(all).size, 78);
  for (const r of REG) assert.strictEqual(r.names.length, r.ids.length);
});

test('every pooled pair: count / base × 100 is the published rate in each municipio and for Puerto Rico (to its rounding)', () => {
  for (const [k, [n, d]] of Object.entries(PR.POOL)) {
    assert.ok(V[k] && V[n] && V[d], `${k}: the datasets of its pair exist`);
    const ys = Object.keys(V[k].years).filter(y => V[n].years[y] && V[d].years[y]);
    assert.ok(ys.length, `${k}: a year in common`);
    for (const y of ys) for (let i = 0; i < ids.length; i++) {
      const r = V[k].years[y][i], a = V[n].years[y][i], b = V[d].years[y][i];
      if (r == null || a == null || !b) continue;
      assert.ok(Math.abs(100 * a / b - r) <= 0.06, `${k} ${y} ${ids[i]}: ${100 * a / b} vs ${r}`);
    }
  }
});

test("the Eastern Region's pooled women's participation equals women_labor.py's figure, with its margin", () => {
  const W = read('women_labor.json').analysis.ersv['2024'].region.lfpr_f;
  const M = REG.find(r => r.id === 'ersv').ids.map(idx);
  const r = PR.agg(X, V.lfpr_women, M, '2024', {});
  assert.strictEqual(r.how, 'pool');
  assert.ok(Math.abs(r.value - W[0]) < 0.06, `${r.value} vs ${W[0]}`);
  assert.ok(Math.abs(r.moe - W[1]) < 0.06, `${r.moe} vs ${W[1]}`);
});

test('a count is the sum of its municipios, with the margin in quadrature; a region is left out when a municipio has no value', () => {
  const M = REG.find(r => r.id === 'ersv').ids.map(idx);
  const r = PR.agg(X, { ...V.vacant_units, type: 'count' }, M, '2024', {});
  const want = M.reduce((t, i) => t + V.vacant_units.years['2024'][i], 0), m = Math.sqrt(M.reduce((t, i) => t + V.vacant_units.moe['2024'][i] ** 2, 0));
  assert.strictEqual(r.how, 'sum'); assert.strictEqual(r.value, want); assert.ok(Math.abs(r.moe - m) < 1e-9);
  const holed = { ...X, calc: (L, y) => { const a = X.calc(L, y).slice(); a[M[0]] = null; return a; } };
  assert.strictEqual(PR.agg(holed, { ...V.vacant_units, type: 'count' }, M, '2024', {}), null);
});

test('any other rate is the residents-weighted average of its municipios, marked as an estimate', () => {
  const M = REG.find(r => r.id === 'ersv').ids.map(idx), pop = X.calc({ key: 'population' }, '2024');
  const r = PR.agg(X, V.poverty_pct, M, '2024', { pop });
  const w = M.reduce((t, i) => t + pop[i], 0), want = M.reduce((t, i) => t + V.poverty_pct.years['2024'][i] * pop[i], 0) / w;
  assert.strictEqual(r.how, 'avg'); assert.ok(Math.abs(r.value - want) < 1e-9); assert.strictEqual(r.moe, null);
});

test("population change is the region's population over its population in the base year, and a share of land is weighted by land area", () => {
  const M = REG.find(r => r.id === 'ersv').ids.map(idx), y = Object.keys(V.population.years).sort().pop(), now = V.population.years[y], base = V.population.years['2010'];
  const r = PR.agg(X, V.pop_change_since_2010_pct, M, y, {});
  assert.strictEqual(r.how, 'pool');
  assert.ok(Math.abs(r.value - 100 * (M.reduce((t, i) => t + now[i], 0) / M.reduce((t, i) => t + base[i], 0) - 1)) < 1e-9);
  assert.ok(PR.LAND.test('wetland_pct') && PR.LAND.test('ls_land_high_pct') && !PR.LAND.test('ls_res_high_pct') && !PR.LAND.test('cre_risk3_pct'), 'land shares, not shares of residents');
});
