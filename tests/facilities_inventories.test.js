/* The federal transportation inventories of core/facilities.js (HANDOFF decision 105, step 4): bridges and tunnels, airports and heliports, ferry routes and
   public EV charging stations, on the published files (transport_inventories.py): the circles, the hollow ones, the pop-ups, the notes and the legends.
     node --test tests/facilities_inventories.test.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const F = require('../site/js/core/facilities.js');
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
const B = read('bridges.geojson'), A = read('airports.geojson'), R = read('ferry_routes.geojson'), E = read('ev_stations.geojson');

test('the four layers have a switch, a file, a help text and the types their files hold', () => {
  for (const [k, id, file, d] of [['bridges', 'lyBridges', 'bridges.geojson', B], ['airports', 'lyAirports', 'airports.geojson', A], ['ferries', 'lyFerries', 'ferry_routes.geojson', R], ['evcharge', 'lyEvCharge', 'ev_stations.geojson', E]]) {
    const L = F.LAYERS[k];
    assert.strictEqual(L.id, id);
    assert.strictEqual(L.file, file);
    assert.ok(F.HELP_TEXT['fac_' + k], k);
    for (const f of d.features) assert.ok(F.TYPES.includes(f.properties.type), `${k}: type ${f.properties.type} is not translated`);
  }
  assert.ok(F.LAYERS.ferries.line && !F.LAYERS.ferries.sized, 'the ferries are lines');
});

test('a bridge: area by daily traffic, color by condition, a closed bridge hollow; a tunnel gray', () => {
  const r = (p) => F.sizedStyle('bridges', p).r;
  assert.ok(Math.abs((r({ a: 160000, c: 'F' }) / r({ a: 40000, c: 'F' })) ** 2 - 4) < 1e-9, 'four times the traffic, four times the area');
  assert.strictEqual(r({ a: 0, c: 'G' }), F.LAYERS.bridges.sized.min);
  assert.strictEqual(F.sizedStyle('bridges', { a: 100, c: 'P', o: 'K' }).planned, true);
  assert.strictEqual(F.sizedStyle('bridges', { a: 100, c: 'P', o: 'A' }).planned, false);
  for (const f of B.features) assert.ok(F.LAYERS.bridges.sized.colors[f.properties.c], `no color for condition ${f.properties.c}`);
  const closed = B.features.find(f => f.properties.o === 'K').properties;
  assert.match(F.popup('bridges', closed, B), /Closed/);
  const scour = B.features.find(f => f.properties.s).properties;
  assert.match(F.popup('bridges', scour, B), /Scour critical/);
  const tun = B.features.find(f => f.properties.type === 'Tunnel').properties;
  assert.match(F.popup('bridges', tun, B), /Tunnel number/);
  assert.strictEqual(F.tip('bridges', tun), tun.name);
  assert.match(F.noteText('bridges', B, 'Explore tab'), new RegExp(`${B.notes.poor} in poor condition`));
});

test('airports: one radius, color by kind; the private facilities owned privately are only counted', () => {
  assert.strictEqual(F.sizedStyle('airports', { cat: 'heliport' }).r, F.LAYERS.airports.sized.r);
  assert.ok(A.features.every(f => !(f.properties.use === 'private' && f.properties.own === 'private')), 'no private facility owned privately is drawn');
  assert.strictEqual(A.features.filter(f => f.properties.cat === 'commercial').length, 3, 'San Juan, Aguadilla and Ponce');
  assert.match(F.noteText('airports', A, 'Explore tab'), new RegExp(`${A.notes.private_not_drawn} private`));
  assert.ok(!/<svg width/.test(F.legendHtml('airports', A)), 'one radius: no size key');
  assert.match(F.popup('airports', A.features[0].properties, A), /FAA identifier/);
});

test('ferry routes: wider where more passengers travel, never a straight line', () => {
  const w = (p) => F.lineStyle('ferries', p).weight;
  assert.ok(w({ pax: 600000 }) > w({ pax: 100000 }));
  for (const f of R.features) assert.ok(f.geometry.coordinates.length > 2, f.properties.name);
  assert.match(F.popup('ferries', R.features[0].properties, R), /passengers in 2024/);
});

test('EV charging: area by ports, green with DC fast charging, a station temporarily unavailable hollow; no phone or address in the file', () => {
  assert.ok(F.sizedStyle('evcharge', { ports: 4, kind: 'l2' }).r > F.sizedStyle('evcharge', { ports: 1, kind: 'l2' }).r);
  assert.strictEqual(F.sizedStyle('evcharge', { ports: 2, kind: 'dc', status: 'unavailable' }).planned, true);
  const text = JSON.stringify(E).toLowerCase();
  for (const word of ['phone', 'street_address', 'telefono']) assert.ok(!text.includes(word), word);
  assert.match(F.legendHtml('evcharge', E), /temporarily unavailable/);
  assert.match(F.popup('evcharge', E.features[0].properties, E), /charging port/);
});

test('the power plants keep their legend and their planned circle', () => {
  const d = read('power_plants.geojson');
  const html = F.legendHtml('plants', d);
  assert.match(html, /MW, by circle area/);
  assert.match(html, /planned, under construction, or not yet in commercial operation/);
  assert.match(html, /fill="#F0E442"/);
});
