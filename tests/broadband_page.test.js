// The Broadband gaps page's arithmetic (site/js/broadband_page.js), checked on the published files (broadband.py): the figures it quotes are the files',
// the share below 100/20 Mbps follows from the counts, the map's classes are fixed, and the barrio ranking by share keeps only barrios with enough locations.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'broadband_page.js'));
const P = globalThis.BroadbandPage;
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
const S = read('broadband_series.json'), B = read('broadband_barrio.json');

test('Puerto Rico\'s figures are the last and first values of the series file', () => {
  const F = P.figures(S), V = P.index(S), pr = S.geo.ids.length - 1, y1 = String(S.years[S.years.length - 1]), y0 = String(S.years[0]);
  assert.strictEqual(F.y1, +y1);
  assert.strictEqual(F.last.n, V.bb_locations[y1][pr]);
  assert.strictEqual(F.last.served, V.bb_served_pct[y1][pr]);
  assert.strictEqual(F.change.below_n, V.bb_below100_n[y1][pr] - V.bb_below100_n[y0][pr]);
  assert.ok(Math.abs(F.last.below - (F.last.under + F.last.unserved)) < 0.2, 'the share below 100/20 is underserved plus unserved, within rounding');
});

test('the map\'s classes are fixed and an area with no locations has no value', () => {
  assert.strictEqual(P.classOf(null, [1, 5, 15, 35]), -1);
  assert.strictEqual(P.classOf(0, [1, 5, 15, 35]), 0);
  assert.strictEqual(P.classOf(5, [1, 5, 15, 35]), 2);
  assert.strictEqual(P.classOf(99, [1, 5, 15, 35]), 4);
  assert.strictEqual(P.measure({ n: 0 }, 'below'), null);
  for (const k of Object.keys(P.MEASURES)) assert.strictEqual(P.MEASURES[k].ramp.length, P.MEASURES[k].breaks.length + 1, k);
});

test('the barrio rankings: by count over every barrio with locations, by share only over barrios with at least MIN_N', () => {
  const y = S.years[S.years.length - 1];
  const byN = P.rankBarrios(B, y, 'n'), byS = P.rankBarrios(B, y, 'share');
  assert.ok(byN.rows.length === 25 && byS.rows.length === 25);
  for (let k = 1; k < byN.rows.length; k++) assert.ok(byN.rows[k - 1].below_n >= byN.rows[k].below_n);
  for (let k = 1; k < byS.rows.length; k++) assert.ok(byS.rows[k - 1].below >= byS.rows[k].below);
  assert.ok(byS.rows.every(r => r.n >= P.MIN_N));
  assert.ok(byS.considered < byN.considered, 'the share ranking leaves out the small barrios');
  const total = B.vars.find(v => v.key === 'bb_below100_n').years[String(y)].reduce((a, b) => a + (b || 0), 0);
  assert.strictEqual(total, S.vars.find(v => v.key === 'bb_below100_n').years[String(y)][S.geo.ids.length - 1], 'the barrios add up to Puerto Rico');
});
