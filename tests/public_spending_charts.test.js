// The Public spending page's after-ready charts (public_spending_charts.js; HANDOFF decision 85): the hex grid has one hexagon for each of the 78
// municipios, no two in one cell, every label different and short, and the hexagons do not overlap; the page loads the file after ready and has
// the boxes the charts draw into.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
require('../site/js/public_spending_charts.js');
const C = globalThis.PSCharts;
const ROOT = path.join(__dirname, '..');

test('hex grid: the 78 municipios, one cell each, distinct short labels', () => {
  const m = C.hexMap();
  const geo = JSON.parse(fs.readFileSync(path.join(ROOT, 'site/data/municipios.geojson'), 'utf8'));
  const ids = geo.features.map((f) => String(f.properties.GEOID)).sort();
  assert.deepStrictEqual(m.paths.map((p) => p.id).sort(), ids);
  assert.strictEqual(new Set(m.paths.map((p) => `${p.x},${p.y}`)).size, 78, 'one municipio per cell');
  assert.strictEqual(new Set(m.paths.map((p) => p.abbr)).size, 78, 'labels differ');
  assert.ok(m.paths.every((p) => p.abbr.length >= 2 && p.abbr.length <= 3), 'labels are two or three letters');
});

test('hex grid: hexagons do not overlap and stay inside the drawing', () => {
  const m = C.hexMap();
  for (const p of m.paths) assert.ok(p.x > 0 && p.y > 0 && p.x < m.W && p.y < m.H);
  for (let i = 0; i < m.paths.length; i++) for (let j = i + 1; j < m.paths.length; j++) {
    const a = m.paths[i], b = m.paths[j];
    assert.ok(Math.hypot(a.x - b.x, a.y - b.y) > 50, `${a.id} and ${b.id} are too close`);   // neighboring centers are sqrt(3) * 30 = 52 apart
  }
});

test('the page loads the charts after ready and has their boxes', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  assert.ok(!html.includes('public_spending_charts.js'), 'not a first-load script');
  assert.ok(/public_spending_charts\.js\?v=\d+/.test(js));
  for (const id of ['psPipe', 'psPipeHead', 'psPipeKey', 'psPipeTable', 'psFlow', 'psFlowHead', 'psFlowKey', 'psPicaView']) assert.ok(html.includes(`id="${id}"`), id);
});
