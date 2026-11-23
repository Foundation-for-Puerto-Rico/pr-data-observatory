// The Reservoirs page's arithmetic (site/js/reservoirs_page.js), checked on the published file: the week and the percentiles are the map layer's
// (reservoirs.py, core/facilities.js), and the three states, the share of years and the water in the tank follow from them.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'reservoirs_page.js'));
const { figures, quantile, weekOf } = globalThis.ReservoirsPage;
const F = require(path.join(__dirname, '..', 'site', 'js', 'core', 'facilities.js'));
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));

test('the week of the year is the map layer\'s, and the percentile is linear between order statistics', () => {
  for (const d of ['2026-01-01', '2026-01-07', '2026-01-08', '2026-11-02', '2026-12-31', '2024-12-30']) assert.strictEqual(weekOf(d), F.weekOf(d), d);
  assert.strictEqual(quantile([1, 2, 3, 4, 5], 0.1), 1.4);
  assert.strictEqual(quantile([1, 2, 3, 4, 5], 0.9), 4.6);
});

test('on the published files, the page\'s usual range is the map layer\'s for every reservoir and week', () => {
  const H = read('reservoir_history.json'), L = read('reservoirs.geojson');
  const layer = Object.fromEntries(L.features.map(f => [f.properties.usgs, f.properties]));
  assert.strictEqual(H.reservoirs.length, L.features.length, 'the same reservoirs');
  for (const r of H.reservoirs) {
    const p = layer[r.usgs];
    for (let w = 0; w < 53; w++) {
      const yrs = r.wk[w].filter(v => v != null);
      if (yrs.length < 8) { assert.strictEqual(p.p10[w], null, `${r.name} week ${w}`); continue; }
      assert.ok(Math.abs(quantile(yrs, 0.1) - p.p10[w]) <= 0.011, `${r.name} week ${w}: p10`);
      assert.ok(Math.abs(quantile(yrs, 0.9) - p.p90[w]) <= 0.011, `${r.name} week ${w}: p90`);
    }
  }
});

test('the state, the share of years and the tank follow from the same week\'s years', () => {
  const wk = Array.from({ length: 53 }, () => [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]);
  const r = { now: 0, nowTime: '2026-03-10T12:00:00Z', wk, lo: 10, hi: 30, d0: '2026-03-01', day: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] };
  const at = (v) => figures({ ...r, now: v });
  assert.strictEqual(at(10.5).st, 'low');
  assert.strictEqual(at(17).st, 'usual');
  assert.strictEqual(at(24).st, 'high');
  assert.strictEqual(at(17).below, 7, 'seven of the fifteen years were lower');
  assert.strictEqual(at(17).pct, 47);
  assert.strictEqual(at(20).fill, 50, 'halfway between the lowest and the highest');
  assert.strictEqual(at(5).fill, 0, 'below the range: an empty tank, not a negative one');
  assert.strictEqual(at(17).d7, 17 - 3, 'the change in 7 days reads the daily value of 3 March');
  assert.strictEqual(figures({ ...r, now: 17, wk: Array.from({ length: 53 }, () => [1, 2, 3]) }).st, 'none', 'fewer than 8 years: no usual range');
});

test('the history file: a record for every reservoir, AAA\'s 19 marked, the old references left out', () => {
  const H = read('reservoir_history.json');
  assert.strictEqual(H.reservoirs.filter(r => r.aaa).length, 19);
  assert.deepStrictEqual(H.geo.ids, H.reservoirs.map(r => r.geoid));
  for (const r of H.reservoirs) {
    assert.strictEqual(r.wk.length, 53);
    assert.ok(r.wk.every(w => w.length === H.years[1] - H.years[0] + 1));
    assert.ok(r.lo <= r.hi);
    assert.ok(r.rec_lo >= r.lo - 3 * (r.hi - r.lo) - 1e-9, `${r.name}: the record low is within three ranges of the 2011-2025 low`);
    assert.ok(r.mon.filter(v => v != null).every(v => v >= r.lo - 3 * (r.hi - r.lo) - 1e-9), `${r.name}: no month on another reference`);
  }
  const toa = H.reservoirs.find(r => r.name === 'Toa Vaca');
  assert.ok(toa.m0 >= '2005-01', 'Toa Vaca reported a depth until 2005: its history starts in 2005');
});
