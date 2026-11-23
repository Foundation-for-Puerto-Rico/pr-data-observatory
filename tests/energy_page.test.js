/* The Energy in Puerto Rico page (energy.html; HANDOFF decision 104, step 3): the figures it computes from data/energy.json.
     node --test tests/energy_page.test.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

global.T = (s, v) => s.replace(/\{(\w+)\}/g, (m, k) => (v && v[k] != null ? v[k] : m));
const E = require('../site/js/energy_page.js');
const d = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', 'energy.json'), 'utf8'));

test('the renewable share with rooftop exports is larger than from the plants alone, and the parts add up', () => {
  const y = Object.keys(d.annual_gwh).sort().pop(), s = E.shares(d.annual_gwh[y]);
  assert.ok(s.withRooftop > s.plants && s.rooftop > 0);
  const tot = Object.values(d.annual_gwh[y]).reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(s.total - tot) < 1e-6);
  assert.ok(s.withRooftop < 100 && s.plants < 100);
});

test('every full year has the eight sources and a total between 12 and 25 TWh', () => {
  for (const [y, v] of Object.entries(d.annual_gwh)) {
    assert.deepStrictEqual(Object.keys(v).sort(), ['coal', 'dg', 'gas', 'hydro', 'landfill', 'oil', 'solar', 'wind']);
    const t = Object.values(v).reduce((a, b) => a + b, 0);
    assert.ok(t > 12000 && t < 25000, `${y}: ${t} GWh`);
  }
});

test('the municipio rows: 78, batteries per 100 housing units and MWh per resident computed from the file', () => {
  const rows = E.muniRows(d.municipios);
  assert.strictEqual(rows.length, 78);
  const r = rows.find(x => x.name === 'San Juan');
  assert.ok(r.bess > 10000, 'San Juan adds LUMA\'s three areas (San Juan, Río Piedras, Santurce)');
  assert.ok(Math.abs(r.bess100 - r.bess / d.municipios.hu[d.municipios.ids.indexOf(r.id)] * 100) < 1e-9);
  assert.strictEqual(d.municipios.bess.reduce((a, b) => a + b, 0) > 150000, true);
});

test('the last-12-months sum needs every month', () => {
  assert.strictEqual(E.lastSum([1, 2, 3], 3), 6);
  assert.strictEqual(E.lastSum([1, null, 3], 3), null);
  assert.strictEqual(E.lastSum([1, 2], 3), null);
});
