// The Urban heat page's arithmetic (site/js/urban_heat.js): the rank correlation, the median and the margin-of-error rule.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'urban_heat.js'));
const { spearman, median, unreliable } = globalThis.UrbanHeat;

test('the rank correlation is 1 for the same order, -1 for the opposite, uses ranks, and averages ties', () => {
  const a = [1, 2, 3, 4, 5, 6];
  assert.ok(Math.abs(spearman(a, a) - 1) < 1e-12);
  assert.ok(Math.abs(spearman(a, a.slice().reverse()) + 1) < 1e-12);
  assert.ok(Math.abs(spearman(a, a.map(x => Math.exp(x))) - 1) < 1e-12);
  assert.ok(Math.abs(spearman([1, 2, 2, 3], [1, 2, 3, 4]) - 0.9486832980505138) < 1e-12);
  assert.strictEqual(spearman([1, 1, 1], [1, 2, 3]), null, 'no variation: no correlation');
});

test('the median of an even count is the mean of the two middle values; of nothing, null', () => {
  assert.strictEqual(median([4, 1, 3, 2]), 2.5);
  assert.strictEqual(median([5, 1, 3]), 3);
  assert.strictEqual(median([]), null);
});

test('the margin-of-error rule is the observatory\'s: above 30% of the estimate, or any margin on zero', () => {
  assert.strictEqual(unreliable(10, 3), false);
  assert.strictEqual(unreliable(10, 3.1), true);
  assert.strictEqual(unreliable(0, 0.5), true);
  assert.strictEqual(unreliable(0, 0), false);
  assert.strictEqual(unreliable(10, null), false);
  assert.strictEqual(unreliable(null, 5), false);
});
