// Measure distance and area, and Draw an area (site/js/core/measure.js; decision 97 step 2, docs/measure.md).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const M = require('../site/js/core/measure.js');

const hav = (a, b) => { const R = 6371.0088, r = Math.PI / 180, dl = (b[1] - a[1]) * r, dg = (b[0] - a[0]) * r; const h = Math.sin(dl / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dg / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };

test('a distance is the haversine distance; a path adds its segments', () => {
  const pairs = [[[-66.1057, 18.4655], [-66.6141, 18.0111]], [[-67.1397, 18.2011], [-65.6435, 18.3258]], [[-65.4429, 18.1263], [-65.2994, 18.3268]], [[-66.06, 18.40], [-66.0605, 18.4004]]];
  for (const [a, b] of pairs) { const f = M.lineKm([a, b]), h = hav(a, b); assert.ok(Math.abs(f - h) / h < 1e-9, `${f} against ${h}`); }
  assert.strictEqual(M.lineKm([[-66, 18]]), 0);
  assert.ok(Math.abs(M.lineKm([[-66, 18], [-66, 18.01], [-66.01, 18.01]]) - (M.lineKm([[-66, 18], [-66, 18.01]]) + M.lineKm([[-66, 18.01], [-66.01, 18.01]]))) < 1e-12, 'a path adds its segments');
});

test('the area of a square of 1 km is 1 km², closed or not, either way round; the perimeter closes it', () => {
  const lat = 18.2, dy = 1 / 110.574, dx = 1 / (111.32 * Math.cos(lat * Math.PI / 180));
  const sq = [[-66, lat - dy / 2], [-66 + dx, lat - dy / 2], [-66 + dx, lat + dy / 2], [-66, lat + dy / 2]];
  assert.ok(Math.abs(M.areaKm2(sq) - 1) < 1e-3, `${M.areaKm2(sq)}`);
  assert.ok(Math.abs(M.areaKm2([...sq, sq[0]]) - M.areaKm2(sq)) < 1e-12);
  assert.ok(Math.abs(M.areaKm2(sq.slice().reverse()) - M.areaKm2(sq)) < 1e-12);
  assert.ok(Math.abs(M.perimeterKm(sq) - 4) < 0.012, `${M.perimeterKm(sq)} (the square is drawn on the flat projection, the edge measured on the sphere)`);
  assert.strictEqual(M.areaKm2(sq.slice(0, 2)), 0);
  const g = M.polygon(sq); assert.strictEqual(g.type, 'Polygon'); assert.deepStrictEqual(g.coordinates[0][0], g.coordinates[0][4]);
  assert.strictEqual(M.polygon([...sq, sq[0]]).coordinates[0].length, 5, 'a closed path is not closed twice');
});

test('the area agrees with Study areas\' own measure, so a drawn area keeps its size', () => {
  const S = require('../site/js/core/study.js');
  const p = [[-66.12, 18.44], [-66.05, 18.45], [-66.03, 18.40], [-66.09, 18.37], [-66.13, 18.40]];
  const a = M.areaKm2(p), b = S.areaKm2(M.polygon(p));
  assert.ok(Math.abs(a - b) / b < 1e-6, `${a} against ${b}`);
});

test('edges that cross are found; a plain outline is not flagged', () => {
  assert.strictEqual(M.crosses([[0, 0], [1, 0], [1, 1], [0, 1]]), false);
  assert.strictEqual(M.crosses([[0, 0], [1, 1], [1, 0], [0, 1]]), true, 'a bow tie');
  assert.strictEqual(M.crosses([[0, 0], [2, 0], [2, 2], [1, 0.5], [0, 2]]), false, 'a concave outline');
  assert.strictEqual(M.crosses([[0, 0], [1, 0], [1, 1]]), false);
});

test('units: the cuerda of Ley 145 de 1968, hectares and acres', () => {
  assert.strictEqual(M.CUERDA_M2, 3930.395625);
  const u = M.units(M.CUERDA_M2 / 1e6);
  assert.ok(Math.abs(u.cuerdas - 1) < 1e-12 && Math.abs(u.ha - 0.3930395625) < 1e-12 && Math.abs(u.acres - 0.97123) < 1e-4, JSON.stringify(u));
  const g = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'dictionary_src', 'glossary.json'), 'utf8')).find(t => t.id === 'cuerda');
  assert.ok(g && g.plain.includes('3,930.395625') && g.plain_es.includes('3,930.395625'), 'the glossary gives the same value');
});

test('the tools load on use: Map tools loads them, the map page does not', () => {
  const read = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8');
  const mt = read('js/maptools.js'), html = read('index.html'), ui = read('js/measure.js');
  assert.match(mt, /addJs\('js\/core\/measure\.js\?v=\d+'\)\.then\(\(\) => addJs\('js\/measure\.js\?v=\d+'\)\)/);
  assert.doesNotMatch(html, /measure\.js/);
  assert.match(html, /data-mt="m:line"/); assert.match(html, /data-mt="m:area"/);
  for (const ic of ['straighten', 'draw']) assert.ok(/icon_names=([a-z0-9_,]+)/.exec(html)[1].split(',').includes(ic), ic);
  assert.match(ui, /c\[f\]\('click', onClick, true\)/, 'clicks are caught before the layers (capture phase)');
  assert.match(read('js/studyareas.js'), /return \{ render, list, save, remove, show, addDrawn \}/);
  const pages = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'pages.json'), 'utf8'));
  assert.deepStrictEqual(pages.pages.map.modules.measure, { scopes: ['measure'], scripts: ['core/measure.js', 'measure.js'] });
});
