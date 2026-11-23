// The Inflation page's arithmetic (site/js/inflation.js): month counts, the joined history and projection, the budget calculator.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'inflation.js'));
const { series, budget, mi, mk } = globalThis.Inflation;
const D = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', 'inflation.json'), 'utf8'));

test('month counts go both ways', () => {
  assert.strictEqual(mk(mi('2026-09')), '2026-09');
  assert.strictEqual(mi('2027-01') - mi('2026-12'), 1);
});

test('the projection starts where the history ends, and every month appears once', () => {
  const rows = series(D), o = rows.find(r => r.k === D.projection.origin.pr);
  assert.strictEqual(o.prP, o.pr, 'the dashed line starts at the last observed rate');
  const keys = rows.map(r => r.k);
  assert.strictEqual(new Set(keys).size, keys.length);
  assert.strictEqual(keys[0], '2000-01');
  assert.strictEqual(keys[keys.length - 1], D.projection.end);
});

test('a budget spent in the base month splits by the basket weights and adds up', () => {
  const g = [{ key: 'a', weight: 60, pr_index: [100, 110] }, { key: 'b', weight: 40, pr_index: [100, 100] }];
  const r = budget(g, '2007-01', 1000);
  assert.strictEqual(r.rows[0].then, 600);
  assert.ok(Math.abs(r.now - (660 + 400)) < 1e-9);
  assert.strictEqual(budget(g, '2006-12', 1000), null, 'before the series: nothing');
});

test('with the real groups, the budget follows the all-items index closely', () => {
  const r = budget(D.groups, '2020-01', 100);
  const s0 = mi(D.monthly.start), idx = (k) => D.monthly.pr_index[mi(k) - s0];
  const official = 100 * idx(D.latest.pr) / idx('2020-01');
  assert.ok(Math.abs(r.now - official) < 1.5, `basket ${r.now.toFixed(2)} vs index ${official.toFixed(2)}`);
});

test('buying power: an income that did not rise, and the raise that restores it', () => {
  const { lostPower } = globalThis.Inflation;
  const r = lostPower(30000, 100, 125);
  assert.strictEqual(r.keeps, 24000, 'buys what $24,000 bought at the old prices');
  assert.ok(Math.abs(r.pct - 20) < 1e-9);
  assert.strictEqual(r.needed, 37500);
  assert.strictEqual(r.raise, 7500);
  assert.deepStrictEqual(lostPower(30000, 100, 100).raise, 0, 'no price change, no loss');
});
