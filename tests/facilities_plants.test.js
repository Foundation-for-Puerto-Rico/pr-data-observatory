/* The Power plants layer of core/facilities.js (HANDOFF decision 104, step 1): circle area by MW, colour by main technology, a planned plant hollow, the pop-up and
   the legend, on the published file (power_plants.py).
     node --test tests/facilities_plants.test.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const F = require('../site/js/core/facilities.js');
const d = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', 'power_plants.geojson'), 'utf8'));

test('Power plants is a sized layer with a switch, a file, a help text and a colour for every technology the file holds', () => {
  const L = F.LAYERS.plants;
  assert.strictEqual(L.id, 'lyPlants');
  assert.strictEqual(L.file, 'power_plants.geojson');
  assert.ok(L.sized && !L.area && !L.line);
  assert.ok(F.HELP_TEXT.fac_plants && /owners are not shown/.test(F.HELP_TEXT.fac_plants[1]) && /Rooftop solar/.test(F.HELP_TEXT.fac_plants[1]));
  assert.ok(F.TYPES.includes('Power plant'), 'the type the file holds is translated');
  for (const f of d.features) assert.ok(L.sized.colors[f.properties.tech], `no colour for ${f.properties.tech}`);
  assert.strictEqual(new Set(Object.values(L.sized.colors)).size, L.sized.cats.length, 'one colour per technology');
});

test('circle AREA is in proportion to MW, with a smallest radius; a planned plant is drawn hollow', () => {
  const r = (p) => F.sizedStyle('plants', p).r;
  assert.ok(Math.abs((r({ mw: 400, tech: 'oil' }) / r({ mw: 100, tech: 'oil' })) ** 2 - 4) < 1e-9, 'four times the MW, four times the area');
  assert.strictEqual(r({ mw: 1, tech: 'solar' }), F.LAYERS.plants.sized.min);
  assert.ok(r({ mw: 0, bat_mw: 100, tech: 'battery' }) > F.LAYERS.plants.sized.min, 'a battery-only plant is sized by its batteries');
  const planned = d.features.find(f => f.properties.status === 'planned');
  if (planned) assert.strictEqual(F.sizedStyle('plants', planned.properties).planned, true);
  assert.strictEqual(F.sizedStyle('plants', d.features[0].properties).planned, false);
  assert.ok(d.features.every((f, i, a) => i === 0 || (a[i - 1].properties.mw || 0) >= (f.properties.mw || 0)), 'the file is sorted largest first, so small circles are drawn on top');
});

test('the pop-up gives MW by technology, years and EIA\'s number, never an owner; the 3D view\'s text values are read from the file', () => {
  const p = d.features.find(f => f.properties.eia && Object.keys(f.properties.by || {}).length > 1).properties;
  const html = F.popup('plants', p, d);
  for (const k of Object.keys(p.by)) assert.ok(html.includes(F.LAYERS.plants.sized.labels[k]), `the pop-up names ${k}`);
  assert.ok(html.includes(`plant/${p.eia}`), 'a link to the plant at EIA');
  assert.ok(!/owner|entity/i.test(html));
  const flat = { ...p, by: JSON.stringify(p.by) };   // what MapLibre hands a click
  assert.strictEqual(F.popup('plants', flat, d), html);
  for (const f of d.features) assert.ok(!('owner' in f.properties) && !('entity' in f.properties), 'no owner in the file');
});

test('the legend shows only the technologies in the file, the sizes and the planned circle; the note gives the totals', () => {
  const html = F.legendHtml('plants', d), have = new Set(d.features.map(f => f.properties.tech));
  for (const c of F.LAYERS.plants.sized.cats) assert.strictEqual(html.includes(`>${F.LAYERS.plants.sized.labels[c]}</span>`), have.has(c), c);
  assert.ok(html.includes('stroke-dasharray'));
  const note = F.noteText('plants', d, 'Explore tab');
  assert.ok(note.includes(String(d.notes.plants)) && /not in this inventory/.test(note));
  assert.ok(F.tip('plants', d.features[0].properties).includes(' MW'));
});

test('a built plant that EIA does not list yet (power_plants.py, energy_src/plants_added.json) is drawn dashed, says its stage and names its source, not EIA', () => {
  const built = d.features.filter(f => f.properties.status === 'built').map(f => f.properties);
  assert.ok(built.length >= 1, 'the file holds the built plants');
  for (const p of built) {
    assert.strictEqual(F.sizedStyle('plants', p).planned, true, `${p.name} is drawn dashed`);
    const html = F.popup('plants', p, d);
    assert.ok(html.includes('not yet in commercial operation'), p.name);
    assert.ok(p.stage === 'connected' ? html.includes('Connected to the grid') : html.includes('Construction complete'), p.name);
    assert.ok(html.includes(p.url.replace(/&/g, '&amp;')) && html.includes('OpenStreetMap'), 'the source and the outline');
    assert.ok(!html.includes('eia.gov'), 'no EIA link: EIA does not list it');
  }
  const note = F.noteText('plants', d, 'Explore tab');
  assert.ok(note.includes('built but not yet in commercial operation') && note.includes(String(d.notes.built_plants)), 'the note counts them apart from EIA\'s totals');
  assert.ok(/OpenStreetMap/.test(F.LAYERS.plants.attribution), 'OpenStreetMap is credited');
});
