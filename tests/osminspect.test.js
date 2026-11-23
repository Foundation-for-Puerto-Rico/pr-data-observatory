// Tests for the OpenStreetMap feature inspector (site/js/core/osminspect.js; docs/basemap.md, section 8). Run: node --test tests/osminspect.test.js
//  - the OSM ID: Planetiler's osm_id × 10 + type code (1 node, 2 way, 3 relation; 0 other source or merged), never guessed
//  - the privacy rules: never housenumber or building; pools passed over; sensitive kinds shown generic, with no name and no link
//  - the kinds in plain words, and the pop-up's markup (escaped names, the link, the credit)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const M = require(path.join(__dirname, '..', 'site', 'js', 'core', 'osminspect.js'));
const f = (sourceLayer, id, properties) => ({ sourceLayer, id, properties });

test('osmRef: the type code is the last digit (1 node, 2 way, 3 relation) and the OSM ID the rest; the real IDs of OpenFreeMap tiles of 2026-10-25', () => {
  // decoded from tile 14/5183/7336 and checked against api.openstreetmap.org: San Juan, Calle Sur, a nursing home's way, the Isleta de San Juan relation
  assert.deepStrictEqual(M.osmRef(532005271, 'place'), { type: 'node', id: 53200527, url: 'https://www.openstreetmap.org/node/53200527' });
  assert.deepStrictEqual(M.osmRef(222234682, 'transportation_name'), { type: 'way', id: 22223468, url: 'https://www.openstreetmap.org/way/22223468' });
  assert.deepStrictEqual(M.osmRef(71170653, 'place'), { type: 'relation', id: 7117065, url: 'https://www.openstreetmap.org/relation/7117065' });
  assert.deepStrictEqual(M.osmRef('1133479432', 'transportation'), { type: 'way', id: 113347943, url: 'https://www.openstreetmap.org/way/113347943' }, 'an ID given as digits');
});

test('osmRef: no link for an ID it cannot read for sure', () => {
  for (const id of [222234680, 10, 0, 5, 11.5, -532005271, 2 ** 60, null, undefined, '', 'way/1', '12a', NaN, Infinity, {}])
    assert.strictEqual(M.osmRef(id, 'transportation'), null, `id ${String(id)}`);
  for (const id of [222234684, 222234689]) assert.strictEqual(M.osmRef(id, 'poi'), null, `type code ${id % 10} is not OSM's`);
  for (const layer of ['housenumber', 'building', 'boundary', 'something_else', undefined])
    assert.strictEqual(M.osmRef(532005271, layer), null, `layer ${layer}: its IDs are not taken as OSM's`);
  assert.strictEqual(M.osmRef(11, 'poi').url, 'https://www.openstreetmap.org/node/1', 'the smallest ID');
  assert.strictEqual(M.osmRef(Number.MAX_SAFE_INTEGER - 8, 'poi').type, 'relation', 'a safe integer up to 2^53');
});

test('describe: housenumbers, buildings, boundaries and layers of other sources show nothing; pools are passed over', () => {
  assert.strictEqual(M.describe(f('housenumber', 1234567892, { housenumber: '1052' })), null);
  assert.strictEqual(M.describe(f('building', 1234567892, { render_height: 9, name: 'Casa' })), null, 'even a building with a name');
  assert.strictEqual(M.describe(f('boundary', 1234567893, { admin_level: 6 })), null);
  assert.strictEqual(M.describe(f(undefined, 1234567892, { municipality: 'San Juan' })), null, 'an observatory layer has no source layer');
  assert.strictEqual(M.describe(f('water', 590361884, { class: 'swimming_pool' })), null);
  assert.strictEqual(M.describe(f('poi', 1234567892, { class: 'swimming', subclass: 'swimming_pool' })), null);
  assert.strictEqual(M.topmost([f('housenumber', 2, { housenumber: '5' }), f('building', 12, {}), f('place', 532005271, { class: 'city', name: 'San Juan' })]).name, 'San Juan', 'the next feature down is shown');
  assert.strictEqual(M.topmost([f('housenumber', 2, {}), f('building', 12, {})]), null);
  assert.ok(!M.SHOWN.has('housenumber') && !M.SHOWN.has('building') && !M.LINK_LAYERS.has('housenumber'));
});

test('describe: a sensitive kind shows a generic kind only, with no name and no link', () => {
  const cases = [['poi', { class: 'hospital', subclass: 'nursing_home' }, 'Health care'], ['poi', { class: 'hospital', subclass: 'clinic' }, 'Health care'], ['poi', { class: 'doctors', subclass: 'doctors' }, 'Health care'],
    ['poi', { class: 'dentist', subclass: 'dentist' }, 'Health care'], ['poi', { class: 'shelter', subclass: 'shelter' }, 'Social services'], ['poi', { class: 'social_facility', subclass: 'social_facility' }, 'Social services'],
    ['poi', { class: 'school', subclass: 'kindergarten' }, 'Child care or preschool'], ['poi', { class: 'lodging', subclass: 'guest_house' }, 'Lodging'], ['poi', { class: 'lodging', subclass: 'bed_and_breakfast' }, 'Lodging'],
    ['poi', { class: 'office', subclass: 'lawyer' }, 'Office'], ['poi', { class: 'office', subclass: 'physician' }, 'Health care'], ['poi', { class: 'office', subclass: 'therapist' }, 'Health care'], ['poi', { class: 'office', subclass: 'accountant' }, 'Office'], ['poi', { class: 'office' }, 'Office'],
    ['poi', { class: 'shop', subclass: 'erotic' }, 'Business'], ['poi', { class: 'shop', subclass: 'massage' }, 'Business'], ['place', { class: 'isolated_dwelling' }, 'Populated place'], ['place', { class: 'farm' }, 'Populated place']];
  for (const [layer, p, kind] of cases) {
    const d = M.describe(f(layer, 2953196362, { ...p, name: 'Dr. Juan del Pueblo', ref: 'X' }));
    assert.deepStrictEqual([d.kind, d.name, d.ref, d.osm, d.why], [kind, null, null, null, 'sensitive'], `${layer} ${p.class}/${p.subclass}`);
    const h = M.html(d);
    assert.ok(!/Juan del Pueblo|openstreetmap\.org\/(node|way|relation)/.test(h), 'neither the name nor a link in the pop-up');
    assert.match(h, /Name and link withheld/);
  }
});

test('describe: public places keep their name and link: hospitals, places of worship, schools, police, government offices, hotels', () => {
  for (const p of [{ class: 'hospital', subclass: 'hospital' }, { class: 'place_of_worship', subclass: 'place_of_worship' }, { class: 'school', subclass: 'school' }, { class: 'police', subclass: 'police' },
    { class: 'office', subclass: 'government' }, { class: 'lodging', subclass: 'hotel' }, { class: 'town_hall', subclass: 'townhall' }, { class: 'prison', subclass: 'prison' }]) {
    const d = M.describe(f('poi', 12345672, { ...p, name: 'Nombre público' }));
    assert.strictEqual(d.why, null, `${p.subclass}`); assert.strictEqual(d.name, 'Nombre público'); assert.strictEqual(d.osm.url, 'https://www.openstreetmap.org/way/1234567');
  }
  for (const s of ['government', 'diplomatic', 'ngo', 'educational_institution']) assert.ok(M.PUBLIC_OFFICE.has(s));
  assert.strictEqual(M.sensitive('poi', { class: 'office', subclass: 'government' }), null);
  assert.strictEqual(M.sensitive('transportation', { class: 'service', name: 'Calle Sur' }), null, 'roads are never sensitive');
});

test('kinds in plain words: roads, paths, places, water, areas; the subclass first; a fallback for every layer shown', () => {
  const k = (layer, p) => M.kindOf(layer, p);
  assert.strictEqual(k('transportation', { class: 'primary' }), 'Primary road');
  assert.strictEqual(k('transportation', { class: 'minor' }), 'Local street');
  assert.strictEqual(k('transportation', { class: 'path', subclass: 'footway' }), 'Footway');
  assert.strictEqual(k('transportation', { class: 'path', subclass: 'unknown' }), 'Path');
  assert.strictEqual(k('transportation', { class: 'primary_construction' }), 'Road under construction');
  assert.strictEqual(k('transportation', { class: 'transit', subclass: 'subway' }), 'Metro line');
  assert.strictEqual(k('poi', { class: 'bus', subclass: 'bus_stop' }), 'Bus stop');
  assert.strictEqual(k('poi', { class: 'something', subclass: 'new_value' }), 'Place of interest');
  assert.strictEqual(k('place', { class: 'quarter' }), 'City district');
  assert.strictEqual(k('water_name', { class: 'bay' }), 'Bay');
  assert.strictEqual(k('waterway', { class: 'stream' }), 'Stream');
  assert.strictEqual(k('landcover', { class: 'wood', subclass: 'forest' }), 'Woodland');
  assert.strictEqual(k('aerodrome_label', { class: 'international' }), 'International airport');
  for (const layer of M.SHOWN) assert.ok(k(layer, {}), `a kind for ${layer}`);
  const d = M.describe(f('transportation', 2925502072, { class: 'path', subclass: 'footway', brunnel: 'bridge' }));
  assert.deepStrictEqual([d.kind, d.bridge], ['Footway', true]);
  assert.strictEqual(M.describe(f('transportation_name', 222234682, { class: 'primary', name: ' Calle Sur ', ref: 'PR-25' })).ref, 'PR-25');
  assert.strictEqual(M.describe(f('poi', 12, { class: 'bus', subclass: 'bus_stop', ref: '9' })).ref, null, 'a road number only for roads');
});

test('no link: merged at this zoom (ends in 0) says to zoom in; water says the tiles carry no OSM ID', () => {
  const merged = M.describe(f('transportation', 222234680, { class: 'primary' }));
  assert.deepStrictEqual([merged.osm, merged.why], [null, 'merged']); assert.match(M.html(merged), /Zoom in and click again/);
  const water = M.describe(f('water', 29510, { class: 'ocean' }));
  assert.deepStrictEqual([water.kind, water.osm, water.why], ['Ocean', null, 'water']); assert.match(M.html(water), /drawn from coastline data/);
  // a lake of tile 14/5183/7336 carries its way (api.openstreetmap.org: way 421337002, natural=water)
  assert.strictEqual(M.describe(f('water', 4213370022, { class: 'lake', id: 421337002 })).osm.url, 'https://www.openstreetmap.org/way/421337002');
  const none = M.describe(f('poi', undefined, { class: 'cafe', subclass: 'cafe' }));
  assert.strictEqual(none.why, 'source');
});

test('the pop-up: kind, escaped name, road number, OSM element, the link (new tab, no glossary) and the OSM credit with ODbL', () => {
  const h = M.html(M.describe(f('transportation_name', 222234682, { class: 'service', name: '<b>Calle "Sur"</b>', ref: 'PR-1' })));
  assert.match(h, /<div class="osmi" data-layer="transportation_name">/);
  assert.match(h, /<div class="osmi-kind">Service road<\/div>/);
  assert.match(h, /<div class="osmi-name" translate="no">&lt;b&gt;Calle &quot;Sur&quot;&lt;\/b&gt;<\/div>/);
  assert.match(h, /Road number: PR-1/);
  assert.match(h, /OSM element: way 22223468/);
  assert.match(h, /<a class="osmi-link" href="https:\/\/www\.openstreetmap\.org\/way\/22223468" target="_blank" rel="noopener noreferrer" data-no-glossary>View on OpenStreetMap/);
  assert.match(h, /© <a href="https:\/\/www\.openstreetmap\.org\/copyright">OpenStreetMap<\/a> contributors · ODbL/);
  assert.match(M.html(null), /Nothing to show here/);
  assert.match(M.html(null), /openstreetmap\.org\/copyright/, 'the credit, even with nothing to show');
});

test('segDist: the distance from a point to a segment, in pixels', () => {
  assert.strictEqual(M.segDist({ x: 5, y: 3 }, { x: 0, y: 0 }, { x: 10, y: 0 }), 3);
  assert.strictEqual(M.segDist({ x: -4, y: 3 }, { x: 0, y: 0 }, { x: 10, y: 0 }), 5);
  assert.strictEqual(M.segDist({ x: 1, y: 1 }, { x: 0, y: 0 }, { x: 0, y: 0 }), Math.SQRT2);
});

test('pages: the toggle in both pages, keyboard-ready (a button with aria-pressed), out of the glossary; the module loads on first use only', () => {
  const site = path.join(__dirname, '..', 'site');
  for (const page of ['index.html', '3d.html']) {
    const h = fs.readFileSync(path.join(site, page), 'utf8');
    assert.match(h, /<button type="button" class="btn osmi-btn" id="osmInspect" aria-pressed="false" aria-describedby="osmInspectNote" data-no-glossary disabled>/, page);
    assert.match(h, /id="osmInspectNote"/);
    assert.doesNotMatch(h, /osminspect\.js/, `${page}: not in the first load`);
  }
  for (const js of ['app.js', 'twin3d.js']) assert.match(fs.readFileSync(path.join(site, 'js', js), 'utf8'), /addJs\('js\/core\/osminspect\.js\?v=\d+'\)/, js);
  assert.match(fs.readFileSync(path.join(site, 'js', 'twin3d.js'), 'utf8'), /dataset\.inspect === 'on'\) return;/, 'the 3D click handler steps aside');
  const pages = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'pages.json'), 'utf8')).pages;
  for (const pg of ['map', 'threed']) assert.deepStrictEqual(pages[pg].modules.osminspect, { scopes: ['osminspect'], scripts: ['core/osminspect.js'] });
});

test('motorway exits: the junction node of transportation_name is a "Motorway exit" with an exit number, not a road number', () => {
  const d = M.describe(f('transportation_name', 123456781, { class: 'motorway', subclass: 'junction', ref: '12A', name: 'Exit 12A' }));
  assert.deepStrictEqual([d.kind, d.ref, d.exit, d.osm.type], ['Motorway exit', '12A', true, 'node']);
  assert.match(M.html(d), /Exit number: 12A/); assert.doesNotMatch(M.html(d), /Road number/);
  assert.match(M.html(M.describe(f('transportation_name', 222234682, { class: 'primary', ref: 'PR-1' }))), /Road number: PR-1/);
});

test('landuse: the grounds of a kindergarten or child care are sensitive (generic kind, no name, no link)', () => {
  for (const c of ['kindergarten', 'childcare']) {
    const d = M.describe(f('landuse', 3600000002, { class: c, name: 'Cuido Los Nenes' }));
    assert.deepStrictEqual([d.kind, d.name, d.osm, d.why], ['Child care or preschool', null, null, 'sensitive'], c);
  }
  assert.strictEqual(M.describe(f('landuse', 3600000002, { class: 'school' })).kind, 'School grounds');
});

test('sameAlong: a road lends its ID or name only to the same road at the click; never a cross street, a ramp that leaves it, or one of two roads', () => {
  const P = (x, y) => ({ x, y }), line = (...pts) => [pts.map(([x, y]) => P(x, y))];
  const label = line([0, 100], [400, 100]), click = P(200, 101);
  const same = { key: 'same', lines: line([150, 100.5], [260, 100.5]) };
  const cross = { key: 'cross', lines: line([200, 0], [200, 300]) };                      // the cross street at the click (Calle de O'Donnell under Calle de San Francisco)
  const crossNear = { key: 'crossNear', lines: line([204, 0], [204, 300]) };
  const ramp = { key: 'ramp', lines: line([170, 101], [200, 101], [230, 115]) };           // a link that leaves the label within 40 px
  const parallel = { key: 'parallel', lines: line([100, 101.5], [300, 101.5]) };
  const far = { key: 'far', lines: line([0, 106], [400, 106]) };
  assert.strictEqual(M.sameAlong(click, label, [same, cross, crossNear, far]), 'same');
  assert.strictEqual(M.sameAlong(click, label, [cross]), null, 'a cross street alone is never lent');
  assert.strictEqual(M.sameAlong(click, label, [crossNear, far]), null);
  assert.strictEqual(M.sameAlong(click, label, [ramp]), null, 'a ramp that leaves the label');
  assert.strictEqual(M.sameAlong(click, label, [same, parallel]), null, 'two roads fit: none lends');
  assert.strictEqual(M.sameAlong(click, label, [same, { key: 'same', lines: line([260, 100.5], [330, 100.5]) }]), 'same', 'two pieces of one road are one key');
  assert.strictEqual(M.sameAlong(P(200, 140), label, [same]), null, 'a click away from the line');
  const elsewhere = { key: 'same', lines: line([0, 300], [400, 300]) };                  // another "Calle 1" of the same name, away from the click, listed first
  assert.strictEqual(M.alongMatch(click, label, [elsewhere, same]).c, same, 'the candidate that fits lends, not the first one of its name');
  const piece2 = { key: 'same', lines: line([190, 100.2], [210, 100.2]) };
  assert.strictEqual(M.alongMatch(click, label, [same, piece2]).c, piece2, 'of two fitting pieces of one road, the nearest');
  assert.strictEqual(M.alongMatch(click, label, [elsewhere]), null);
  const diag = line([0, 0], [300, 300]);
  assert.strictEqual(M.sameAlong(P(150, 151), diag, [{ key: 'd', lines: line([100, 101], [200, 201]) }, { key: 'h', lines: line([0, 150], [300, 150]) }]), 'd', 'any bearing');
});
