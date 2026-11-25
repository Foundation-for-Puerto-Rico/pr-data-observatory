// Build my region and Count my points (GIS tools step 4; site/js/studyareas.js, core/study.js, profile.js). Run: node --test tests/study_tools.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const SITE = path.join(__dirname, '..', 'site');
const S = require(path.join(SITE, 'js', 'core', 'study.js'));
const read = (f) => fs.readFileSync(path.join(SITE, f), 'utf8');
const plain = (x) => JSON.parse(JSON.stringify(x));

test('count my points: a CSV or GeoJSON is read whole, with the rows it cannot use counted', () => {
  assert.deepStrictEqual(plain(S.points('name,lat,lon\n"A, b",18.4,-66.1\nx,,\nfar,40,-70\n', 'f.csv')), { pts: [[-66.1, 18.4]], rows: 3, bad: 1, outside: 1 });
  assert.deepStrictEqual(plain(S.points('id;latitud;longitud\n1;18,40;-66,10\n', 'f.csv')).pts, [[-66.1, 18.4]], 'a semicolon file with decimal commas');
  assert.deepStrictEqual(plain(S.points('Latitude\tLongitude\n18.2\t-66.5\n', 'f.txt')).pts, [[-66.5, 18.2]], 'tabs and capitals');
  assert.deepStrictEqual(plain(S.points('a,b\n1,2', 'f.csv')), { error: 'columns' });
  assert.deepStrictEqual(plain(S.points('lat,lon', 'f.csv')), { error: 'empty' });
  assert.deepStrictEqual(plain(S.points('{bad', 'f.geojson')), { error: 'json' });
  const gj = { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [-66, 18.3] } }, { type: 'Feature', geometry: { type: 'MultiPoint', coordinates: [[-66.2, 18.2], [-66.3, 18.25]] } }, { type: 'Feature', geometry: null }] };
  assert.deepStrictEqual(plain(S.points(JSON.stringify(gj), 'p.geojson')), { pts: [[-66, 18.3], [-66.2, 18.2], [-66.3, 18.25]], rows: 4, bad: 1, outside: 0 });
  assert.strictEqual(S.points('lat,lon\n' + '18.3,-66.1\n'.repeat(50), 'f.csv', 10).pts.length, 10, 'no more than the limit is kept');
});

test('count my points: the measure counts the points inside an area, and the view never draws them and hides counts under 5', () => {
  const sq = { type: 'Polygon', coordinates: [[[-66.2, 18.2], [-66.0, 18.2], [-66.0, 18.4], [-66.2, 18.4], [-66.2, 18.2]]] };
  const m = S.measure(sq, { blocks: [], munis: [], stops: [], mine: [[-66.1, 18.3], [-66.15, 18.25], [-65.5, 18.3]] });
  assert.strictEqual(m.mine, 2);
  assert.strictEqual(S.measure(sq, { blocks: [], munis: [], stops: [] }).mine, undefined, 'not counted without a file');
  const sa = read('js/studyareas.js');
  assert.match(sa, /const MIN_SHOWN = 5/);
  assert.match(sa, /n > 0 && n < MIN_SHOWN \? T\('fewer than \{n\}'/, 'a count of 1 to 4 is shown as "fewer than 5"');
  const start = sa.indexOf('// ── count my points'), block = sa.slice(start, sa.indexOf('// ── ', start + 10));   // to the next section
  assert.ok(!/L\.(marker|circleMarker|circle)\(|L\.geoJSON\([^)]*pts/.test(block), 'the points are never drawn');
  assert.ok(!/indexedDB|localStorage|save\(/.test(block), 'the file is not kept');
});

test('build my region: the parts merge into one area, and two or more municipios open a pooled regional profile', () => {
  const a = { type: 'Polygon', coordinates: [[[-66.2, 18.2], [-66.1, 18.2], [-66.1, 18.3], [-66.2, 18.3], [-66.2, 18.2]]] };
  const b = { type: 'MultiPolygon', coordinates: [[[[-66.1, 18.2], [-66.0, 18.2], [-66.0, 18.3], [-66.1, 18.3], [-66.1, 18.2]]]] };
  const g = S.merge([a, b]);
  assert.strictEqual(g.type, 'MultiPolygon');
  assert.ok(Math.abs(S.areaKm2(g) - S.areaKm2(a) - S.areaKm2(b)) < 1e-9);
  const prof = read('js/profile.js');
  assert.match(prof, /get\('ids'\)/, 'profile.html?ids=');
  assert.match(prof, /mine\.length >= 2/, 'two or more municipios');
  assert.match(prof, /\/\^72\\d\{3\}\$\/\.test\(g\)/, 'only municipio codes');
  assert.match(read('js/studyareas.js'), /'profile\.html\?ids=' \+ munis\.sort\(\)\.join\(','\)/);
});

test('download what\'s inside: outlines that overlap an area are found whole, small ones between the grid points too, far ones never', () => {
  const sq = (x, y, d) => ({ type: 'Polygon', coordinates: [[[x, y], [x + d, y], [x + d, y + d], [x, y + d], [x, y]]] });
  const area = sq(-66.2, 18.2, 0.1);
  const geoms = [sq(-66.25, 18.25, 0.1), sq(-66.0, 18.0, 0.05), sq(-66.15, 18.25, 0.0005), null, sq(-66.19, 18.21, 0.08)];
  assert.deepStrictEqual(plain(S.overlaps(area, geoms)), [0, 2, 4], 'the one across the edge, the tiny one inside, the one inside; not the far one');
  const sa = read('js/studyareas.js');
  assert.match(sa, /filter\(p => !p\.withheld && isFinite\(p\.lng\) && isFinite\(p\.lat\)\)/, 'withheld places are never in a file');
  assert.match(sa, /ST\.overlaps\(g, feats\.map\(f => f\.g\)\)/);
  assert.match(sa, /source = T\('PR Data Observatory, data\/\{file\}; license and credit in the data dictionary/, 'every file names its source');
});

test('walking time: the area within a walk along the real roads is inside the straight-line reach, smaller than the circle, and none at sea', () => {
  const vm = require('node:vm'), ctx = { Math, Map, Set, Float64Array, Int32Array, Uint32Array, Uint16Array, Uint8Array, Int16Array, DataView, ArrayBuffer };
  vm.runInNewContext(read('js/roads.js') + '\nthis.Roads = Roads;', ctx);
  const f = path.join(SITE, 'data', 'roads.bin');
  if (!fs.existsSync(f)) return;
  const b = fs.readFileSync(f), R = new ctx.Roads(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
  const x = -66.3063, y = 18.1866, m = 15 * 80, w = S.walkArea(R, x, y, m);   // Barranquitas, a 15-minute walk
  assert.ok(w && w.geometry.type === 'MultiPolygon');
  const km2 = S.areaKm2(w.geometry), circle = Math.PI * ((m + S.WALK.OFF_M) / 1000) ** 2;
  assert.ok(km2 > 0.1 && km2 < circle, `${km2} km² within the ${circle.toFixed(2)} km² of the straight-line reach`);
  const kx = Math.cos(y * Math.PI / 180) * 111320, ky = 110574, reach = m + S.WALK.OFF_M + S.WALK.CELL_M;
  for (const p of w.geometry.coordinates) for (const [lng, lat] of p[0]) assert.ok(Math.hypot((lng - x) * kx, (lat - y) * ky) <= reach + 1, 'no corner beyond the straight-line reach');
  assert.ok(S.inside(w.geometry, x, y), 'the start is inside');
  assert.ok(S.areaKm2(S.walkArea(R, x, y, 5 * 80).geometry) < km2, 'a shorter walk covers less');
  assert.strictEqual(S.walkArea(R, -66.0, 18.6, m), null, 'no road at sea');
  assert.deepStrictEqual(plain(S.check(S.make({ name: 'Walking areas', source: 'x', areas: [{ name: '15-minute walk', geometry: w.geometry }] }))), [], 'it is a valid study area');
});

test('property parcels (CRIM): only a link to CRIM\'s own viewer at the point, nothing read or drawn', () => {
  assert.strictEqual(S.crimUrl(-66.1057, 18.4655), 'https://catastro.crimpr.net/cdprpc/?center=-66.10570,18.46550&level=18');
  assert.strictEqual(S.crimUrl(-67.86, 18.08), 'https://catastro.crimpr.net/cdprpc/?center=-67.86000,18.08000&level=18', 'Mona is in Puerto Rico');
  assert.strictEqual(S.crimUrl(-70, 18.4), null, 'outside Puerto Rico');
  assert.strictEqual(S.crimUrl(NaN, 18.4), null, 'not a number');
  const js = read('js/studyareas.js');
  assert.ok(js.includes('data-crimpick') && js.includes('data-crimcentre'), 'the Tools section has both buttons');
  assert.ok(!/catastro\.crimpr\.net/.test(js), 'the view builds no CRIM address of its own: Core.study.crimUrl is the only one');
  const files = fs.readdirSync(path.join(SITE, 'js')).filter(f => f.endsWith('.js')).map(f => 'js/' + f).concat(fs.readdirSync(path.join(SITE, 'js', 'core')).map(f => 'js/core/' + f));
  const reads = files.filter(f => /catastro\.crimpr\.net\/(server|portal|proxy)/.test(read(f)));
  assert.deepStrictEqual(reads, [], 'no script calls CRIM\'s services (its license lets the parcels be seen only in its viewer)');
});
