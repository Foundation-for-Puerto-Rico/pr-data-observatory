/* The Transmission lines layer of core/facilities.js (HANDOFF decision 104, step 2): color and width by voltage, a cable dashed, the pop-up, legend and note.
     node --test tests/facilities_lines.test.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const F = require('../site/js/core/facilities.js');
const d = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', 'power_lines.geojson'), 'utf8'));

test('Transmission lines is a line layer styled by voltage, with a switch, a file and a help text', () => {
  const L = F.LAYERS.powerlines;
  assert.strictEqual(L.id, 'lyPowerLines');
  assert.strictEqual(L.file, 'power_lines.geojson');
  assert.ok(L.line && L.line.colors && L.line.widths && !L.sized && !L.area);
  assert.ok(/not drawn/.test(F.HELP_TEXT.fac_powerlines[1]) && /about half mapped/.test(F.HELP_TEXT.fac_powerlines[1]));
  for (const f of d.features) assert.ok(L.line.colors[f.properties.kv], `no color for ${f.properties.kv} kV`);
});

test('the higher the voltage, the wider the line; a cable is dashed', () => {
  const w = (kv) => F.lineStyle('powerlines', { kv }).weight;
  assert.ok(w(230) > w(115) && w(115) > w(38));
  assert.ok(Array.isArray(F.lineStyle('powerlines', { kv: 38, cable: true }).dash));
  assert.strictEqual(F.lineStyle('powerlines', { kv: 230 }).dash, null);
});

test('the pop-up, legend and note give voltages and lengths, never a name or circuit; the note says substations are not drawn', () => {
  const p = d.features.find(f => f.properties.kv === 38 && !f.properties.cable).properties;
  const html = F.popup('powerlines', p, d);
  assert.ok(html.includes('38 kV') && /about half mapped/.test(html));
  const leg = F.legendHtml('powerlines', d);
  for (const kv of ['230 kV', '115 kV', '38 kV']) assert.ok(leg.includes(kv));
  const note = F.noteText('powerlines', d, 'Explore tab');
  assert.ok(note.includes(String(d.notes.substations)) && /not drawn/.test(note));
  assert.strictEqual(F.tip('powerlines', p), '38 kV transmission line');
});
