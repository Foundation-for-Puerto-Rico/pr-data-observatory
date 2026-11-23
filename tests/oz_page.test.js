// The Opportunity Zones 2.0 page's arithmetic (site/js/oz_page.js) and the two files it and the map layer read (opportunity_zones.py, decision 103):
// the law's test on Treasury's figures gives Treasury's eligibility, the zones are within the limit, the barrios and municipios add up to Puerto Rico,
// and the map layer holds exactly the designated tracts with the same status.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'oz_page.js'));
const P = globalThis.OzPage;
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
const D = read('opportunity_zones.json'), L = read('oz_tracts.geojson');

test('the law\'s test on Treasury\'s published figures gives exactly Treasury\'s eligible tracts', () => {
  const ts = P.tracts(D);
  assert.strictEqual(ts.length, 981, 'every 2020 tract');
  const off = ts.filter(t => P.eligibleByRule(t.pov, t.mfi_pct) !== (t.status >= 0));
  assert.deepStrictEqual(off.map(t => t.id), [], 'no tract where the rule and Treasury disagree');
  assert.ok(P.eligibleByRule(10, 70) && !P.eligibleByRule(19.9, 70.1) && P.eligibleByRule(20, 125) && !P.eligibleByRule(20, 125.1) && P.eligibleByRule(25, null) && !P.eligibleByRule(null, null), 'the rule\'s edges');
});

test('the zones: within the limit of a quarter of the eligible tracts, rounded up, every one eligible and with residents', () => {
  const c = P.counts(D), p = D.pr, eligible = c[0] + c[1] + c[2];
  assert.strictEqual(c[1] + c[2], p.designated);
  assert.strictEqual(c[2], p.rural);
  assert.strictEqual(eligible, p.eligible);
  assert.strictEqual(p.limit, Math.ceil(p.eligible / 4));
  assert.ok(p.designated <= p.limit);
  assert.ok(P.tracts(D).filter(t => t.status > 0).every(t => t.pop > 0));
});

test('residents in zones: the tracts, the barrios and the municipios add up to Puerto Rico', () => {
  const zones = P.tracts(D).filter(t => t.status > 0), sum = (a, k) => a.reduce((s, x) => s + x[k], 0);
  assert.strictEqual(sum(zones, 'pop'), D.pr.pop_designated);
  assert.strictEqual(sum(P.munis(D), 'pop_designated'), D.pr.pop_designated);
  const B = D.barrios.map(r => Object.fromEntries(D.barrio_fields.map((f, i) => [f, r[i]])));
  assert.strictEqual(sum(B, 'pop_designated'), D.pr.pop_designated);
  assert.ok(B.every(b => b.pop_designated <= b.pop_eligible && b.pop_eligible <= b.pop));
  assert.strictEqual(P.munis(D).filter(m => m.designated > 0).length, D.pr.municipios_with_zone);
  const top = P.barrios(D, ''), one = P.barrios(D, D.municipios[0][0]);
  for (let k = 1; k < top.length; k++) assert.ok(top[k - 1].pop_designated >= top[k].pop_designated, 'the top barrios, most first');
  assert.ok(one.every(b => b.mun === D.municipios[0][0]) && one.length > 0, 'a municipio\'s barrios');
});

test('the map layer holds exactly the designated tracts, with their status, residents and figures', () => {
  const byId = new Map(P.tracts(D).map(t => [t.id, t]));
  assert.strictEqual(L.features.length, D.pr.designated);
  for (const f of L.features) {
    const p = f.properties, t = byId.get(p.g);
    assert.ok(t && t.status > 0, `${p.g} is a zone`);
    assert.strictEqual(p.c, t.status); assert.strictEqual(p.p, t.pop); assert.strictEqual(p.pv, t.pov); assert.strictEqual(p.mr, t.mfi_pct);
    assert.ok(['Polygon', 'MultiPolygon'].includes(f.geometry.type));
  }
  assert.strictEqual(L.notes.rural + L.notes.non_rural, L.features.length);
});

test('the shared layer: an area layer whose classes are kinds, with its legend, hover text and pop-up', () => {
  globalThis.Core = globalThis.Core || {};
  const F = require(path.join(__dirname, '..', 'site', 'js', 'core', 'facilities.js'));
  const A = F.LAYERS.oz.area;
  assert.strictEqual(F.LAYERS.oz.file, 'oz_tracts.geojson');
  assert.strictEqual(F.areaClass('oz', 1), 0); assert.strictEqual(F.areaClass('oz', 2), 1);
  assert.strictEqual(A.labels.length, A.colors.length);
  const p = L.features.find(f => f.properties.c === 2).properties;
  assert.match(F.legendHtml('oz'), /Zone, rural/);
  assert.match(F.tip('oz', p), /rural/);
  const html = F.popup('oz', p, L);
  assert.match(html, /opportunity-zones\.html/);
  assert.ok(html.includes(p.m), 'the municipio');
});
