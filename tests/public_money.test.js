// The FEMA disaster funding and need page's arithmetic (site/js/public_money.js): thirds by rank, the rank correlation and the median.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'public_money.js'));
const { thirds, spearman, median } = globalThis.PublicMoney;

test('78 values fall in three thirds of 26, in the order of the values', () => {
  const vals = Array.from({ length: 78 }, (_, i) => (i * 37) % 78);   // every value once, shuffled
  const { cls, cut } = thirds(vals);
  assert.deepStrictEqual([0, 1, 2].map(c => cls.filter(x => x === c).length), [26, 26, 26]);
  vals.forEach((v, i) => assert.strictEqual(cls[i], v < 26 ? 0 : v < 52 ? 1 : 2));
  assert.deepStrictEqual(cut, [26, 52]);
});

test('ties keep the order of the municipios, so the thirds stay the same size', () => {
  const { cls } = thirds(new Array(78).fill(5));
  assert.deepStrictEqual([0, 1, 2].map(c => cls.filter(x => x === c).length), [26, 26, 26]);
});

test('the rank correlation is 1 for the same order, -1 for the opposite, and uses ranks, not values', () => {
  const a = [1, 2, 3, 4, 5, 6];
  assert.ok(Math.abs(spearman(a, a) - 1) < 1e-12);
  assert.ok(Math.abs(spearman(a, a.slice().reverse()) + 1) < 1e-12);
  assert.ok(Math.abs(spearman(a, a.map(x => x ** 3)) - 1) < 1e-12);
  assert.ok(Math.abs(spearman([1, 2, 2, 3], [1, 2, 3, 4]) - 0.9486832980505138) < 1e-12);   // tied ranks are averaged (scipy.stats.spearmanr gives 0.9487)
});

test('the median of an even count is the mean of the two middle values', () => {
  assert.strictEqual(median([4, 1, 3, 2]), 2.5);
  assert.strictEqual(median([5, 1, 3]), 3);
});
