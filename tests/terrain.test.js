// The Slope and Contour lines layers of the 2D map (site/js/terrain.js; GIS tools step 2, docs/slope.md) and the threshold of core/surfscale.js.
// Run: node --test tests/terrain.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SITE = path.join(__dirname, '..', 'site');
const read = (f) => fs.readFileSync(path.join(SITE, f), 'utf8');

/** terrain.js in a sandbox with just enough of Leaflet and the page for its top level to run. */
function load() {
  const pane = { style: {} };
  const sandbox = { window: {}, module: { exports: {} }, console, Math, Float32Array, Image: function () {},
    map: { createPane() {}, getPane: () => pane, on() {}, off() {} }, L: { GridLayer: { extend: (o) => o } }, document: {} };
  sandbox.window = sandbox;
  vm.runInNewContext(read('js/terrain.js'), sandbox);
  return sandbox.module.exports;
}

test('contour lines: marching squares draws the levels across a slope, none on flat ground or under the sea', () => {
  const { marching, contourStep } = load();
  const N = 11, ramp = new Float32Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) ramp[r * N + c] = c * 10;   // rises 10 m a pixel to the east: 0 to 100 m
  const segs = marching(ramp, N, 20);
  assert.deepStrictEqual([...new Set(segs.map(s => s[0]))].sort((a, b) => a - b), [20, 40, 60, 80, 100], 'every multiple of the step above 0 up to the top');
  for (const [L, x0, y0, x1, y1] of segs) {
    assert.ok(Math.abs(x0 - x1) < 1e-9 && Math.abs(y0 - y1) === 1, 'on an east-facing slope each piece runs north to south');
    assert.ok(Math.abs(x0 - (L / 10 + 0.5)) < 1e-9, `the ${L} m line sits where the height is ${L} m (x ${x0})`);
  }
  assert.strictEqual(segs.filter(s => s[0] === 40).length, N - 1, 'one piece per row of cells');
  assert.strictEqual(marching(new Float32Array(N * N).fill(55), N, 10).length, 0, 'flat ground');
  assert.strictEqual(marching(new Float32Array(N * N).fill(-30), N, 10).length, 0, 'the sea');
  // a hill: each level a closed ring, so every endpoint is shared by two pieces
  const hill = new Float32Array(N * N);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) hill[r * N + c] = 100 - 10 * Math.hypot(r - 5, c - 5);
  const ring = marching(hill, N, 25).filter(s => s[0] === 75), ends = new Map();
  for (const [, x0, y0, x1, y1] of ring) for (const k of [`${x0.toFixed(6)},${y0.toFixed(6)}`, `${x1.toFixed(6)},${y1.toFixed(6)}`]) ends.set(k, (ends.get(k) || 0) + 1);
  assert.ok(ring.length >= 8 && [...ends.values()].every(n => n === 2), `the 75 m line is a closed ring (${ring.length} pieces)`);
  assert.deepStrictEqual(JSON.parse(JSON.stringify([9, 11, 12, 13, 14, 15].map(contourStep))), [100, 100, 50, 20, 10, 10]);
});

test('slope and contours: loaded on first use, with Spanish and help, in the layer menu', () => {
  const app = read('js/app.js'), index = read('index.html');
  assert.ok(!/terrain\.js/.test(index), 'not in the first load of the map');
  assert.match(app, /addJs\('js\/terrain\.js\?v=\d+'\)/);
  assert.match(app, /I18N\.load\('terrain'\)/);
  for (const id of ['lySlope', 'lyContours']) assert.match(index, new RegExp(`id="${id}"`));
  assert.match(app, /slope: 'lySlope', contours: 'lyContours'/);
  const help = read('js/help.js');
  assert.match(help, /slope: \[TK\('Slope'\)/);
  assert.match(help, /contours: \[TK\('Contour lines'\)/);
  const pages = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'pages.json'), 'utf8'));
  assert.deepStrictEqual(pages.pages.map.modules.terrain, { scopes: ['terrain'], scripts: ['terrain.js'] });
  // the three pages that load the heat reader ask for the same version, so it is fetched once
  const v = [app, read('js/twin3d.js'), read('js/studyareas.js'), read('js/terrain.js')].map(s => (s.match(/surfscale\.js\?v=(\d+)/) || [])[1]);
  assert.ok(v.every(x => x && x === v[0]), `one version of core/surfscale.js (${v})`);
});

test('the threshold: paint leaves out the steps below it, and each legend slider names its own image', async () => {
  const SS = require(path.join(SITE, 'js', 'core', 'surfscale.js'));
  const src = read('js/core/surfscale.js');
  assert.match(src, /min != null && value\(k\) < min - 1e-9 \? 0 :/, 'a step below the threshold is transparent');
  assert.match(src, /const key = \[scale\.low, scale.centre, scale.high, min]\.join\(\)/, 'a new threshold paints again');
  assert.match(src, /data-surf-min="\$\{me\}"/, 'the slider names its image');
  assert.match(src, /images\[\+r\.dataset\.surfMin\]/, 'and the handler finds it by that name');
  assert.match(src, /data-surf-own|surfOwn/, 'the slope layer repaints its own image');
  assert.strictEqual(typeof SS.open, 'function');
});

test('what drains here: the walk upstream follows dn and the minor branches (via), and the real network gives the Río Grande de Loíza basin', () => {
  const S = require(path.join(SITE, 'js', 'core', 'study.js'));
  //      0 -> 1 -> 2 (outlet); 3 -> 2; 4 is a minor branch that splits from 1 and reaches the sea on its own
  const dn = [1, 2, -1, 2, -1], via = [null, null, null, null, [1]];
  assert.deepStrictEqual(S.upstream(dn, 2).sort(), [0, 1, 2, 3]);
  assert.deepStrictEqual(S.upstream(dn, 4).sort(), [4], 'without via a minor branch has nothing upstream');
  assert.deepStrictEqual(S.upstream(dn, 4, via).sort(), [0, 1, 4], 'with via it gets the land above the split');
  const f = path.join(SITE, 'data', 'catchments.geojson');
  if (!fs.existsSync(f)) return;
  const fc = JSON.parse(fs.readFileSync(f, 'utf8')), d = fc.features.map(x => x.properties.dn), v = fc.features.map(x => x.properties.via || null);
  const loiza = fc.features.map((x, k) => k).filter(k => /Loiza/.test(fc.features[k].properties.name || ''));
  const km2 = (k) => S.upstream(d, k, v).reduce((a, j) => a + fc.features[j].properties.km2, 0);
  const best = Math.max(...loiza.map(km2)), nhd = fc.notes.mouths.find(m => /Loiza/.test(m.name)).nhdplus_km2;
  assert.ok(Math.abs(best / nhd - 1) < 0.03, `${best} km² against NHDPlus ${nhd}`);
  const at = S.locate(fc.features.map(x => x.geometry));
  assert.strictEqual(at(-65.0, 18.0), -1, 'the sea is in no catchment');
});
