// Save the map as an image (site/js/core/mapimage.js and site/js/mapimage.js; decision 97 step 3, docs/map-image.md).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const K = require('../site/js/core/mapimage.js');
const read = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8');

test('the scale bar is the longest round length that fits', () => {
  assert.deepStrictEqual(K.niceScale(100, 160), { m: 10000, px: 100, label: '10 km' });   // 16 km fit: 10 km
  assert.strictEqual(K.niceScale(10, 160).label, '1 km');                                  // 1.6 km fit
  assert.strictEqual(K.niceScale(2, 160).label, '200 m');                                  // 320 m fit
  assert.strictEqual(K.niceScale(0.5, 160).label, '50 m');                                 // 80 m fit
  assert.strictEqual(K.niceScale(400, 160).label, '50 km');                                // 64 km fit
  for (const mpp of [0.3, 3, 37, 512, 4000]) { const s = K.niceScale(mpp, 160); assert.ok(s.px <= 160 && s.px > 160 / 5, `${mpp}: ${s.px}`); assert.match(String(s.m / Math.pow(10, Math.floor(Math.log10(s.m)))), /^[125]$/); }
  assert.strictEqual(K.niceScale(0, 160), null);
});

test('the file is named by the date', () => {
  assert.strictEqual(K.fileName(new Date(2026, 10, 9)), 'pr-data-observatory-map-2026-11-09.png');
});

test('legend swatches: fills, lines, pins and colour ramps', () => {
  assert.deepStrictEqual(K.swatch({ cls: 'sw', bg: 'rgb(32, 93, 123)' }), { kind: 'fill', colors: ['rgb(32, 93, 123)', ''] });
  assert.strictEqual(K.swatch({ cls: 'sw line', bg: 'rgb(32, 93, 123)' }).kind, 'line');
  assert.deepStrictEqual(K.swatch({ cls: 'sw line', bg: 'rgba(0, 0, 0, 0)', border: 'rgb(92, 51, 20) 2px' }).colors, ['rgb(92, 51, 20)'], 'a contour line drawn by its border');
  assert.deepStrictEqual(K.swatch({ cls: 'sw pin', bg: 'rgb(255, 255, 255)', border: 'rgb(32, 93, 123)' }), { kind: 'pin', colors: ['rgb(255, 255, 255)', 'rgb(32, 93, 123)'] });
  const r = K.swatch({ bgImage: 'linear-gradient(90deg, rgb(247, 244, 234), rgb(201, 160, 90), rgb(62, 36, 16))' });
  assert.strictEqual(r.kind, 'ramp'); assert.strictEqual(r.colors.length, 3);
});

test('legends fill columns and say how many are left out', () => {
  const b = (n) => ({ title: 't', rows: Array(n).fill({ label: 'x' }) });
  const one = K.columns([b(5), b(4), b(2)], 900, 260);
  assert.strictEqual(one.placed.length, 3); assert.strictEqual(one.left, 0);
  assert.ok(one.placed.every(p => p.x + 260 <= 900));
  const many = K.columns(Array(20).fill(b(6)), 600, 260);
  assert.ok(many.left > 0 && many.placed.length + many.left === 20);
});

test('the tool loads on use from Map tools, and the base map stays readable', () => {
  const mt = read('js/maptools.js'), html = read('index.html');
  assert.match(mt, /addJs\('js\/core\/mapimage\.js\?v=\d+'\)\.then\(\(\) => addJs\('js\/mapimage\.js\?v=\d+'\)\)/);
  assert.doesNotMatch(html, /mapimage\.js/);
  assert.match(html, /data-mt="i:png"/);
  assert.ok(/icon_names=([a-z0-9_,]+)/.exec(html)[1].split(',').includes('image'));
  assert.match(read('js/core/basemap.js'), /preserveDrawingBuffer: true/, 'without it the base map reads as blank');
  const pages = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'pages.json'), 'utf8'));
  assert.deepStrictEqual(pages.pages.map.modules.mapimage, { scopes: ['mapimage'], scripts: ['core/mapimage.js', 'mapimage.js'] });
  assert.match(read('js/measure.js'), /typeof econLoad === 'function'/, 'Draw an area loads the Analysis engine first (PR #104)');
});
