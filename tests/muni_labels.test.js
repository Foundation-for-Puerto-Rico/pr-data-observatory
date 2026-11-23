/* The municipio names of the Límites layer and the base map's own town names: one of the two, never both (the names were written twice from zoom 10).
     node --test tests/muni_labels.test.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const read = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8');

test('the municipio labels are hidden while a base map is drawn or loading, and only then', () => {
  const css = read('css/twin.css');
  assert.match(css, /#map\[data-basemap="on"\] \.muni-label, #map\[data-basemap="loading"\] \.muni-label \{ display: none; \}/);
  assert.ok(!/data-basemap="(off|none)"\] \.muni-label/.test(css), 'with no base map, or one that failed, the labels stay');
  const bm = read('js/core/basemap.js');
  assert.match(bm, /el\.dataset\.basemap = state/, 'the base map writes its state on the map\'s element');
  assert.match(read('js/app.js'), /className: 'muni-label'/);
  assert.match(read('index.html'), /<main id="map"/);
});
