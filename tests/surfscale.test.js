// The colours of the surface heat image (site/js/core/surfscale.js, decision 88): the page reads each pixel's step from its colour, so the palette it rebuilds from
// heat_surface.json must be the PNG's own palette, colour for colour (surface_image.py writes it with Python's rounding; a mismatch would drop those pixels).
// Run: node --test tests/surfscale.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const SITE = path.join(__dirname, '..', 'site');
const SS = require(path.join(SITE, 'js', 'core', 'surfscale.js'));

function plte(file) {
  const b = fs.readFileSync(file);
  for (let i = 8; i < b.length;) {
    const n = b.readUInt32BE(i), type = b.toString('latin1', i + 4, i + 8);
    if (type === 'PLTE') return [...Array(n / 3).keys()].map(k => [b[i + 8 + 3 * k], b[i + 9 + 3 * k], b[i + 10 + 3 * k]]);
    i += 12 + n;
  }
  throw new Error('no PLTE');
}

for (const name of ['heat_surface.json', 'night_heat_surface.json']) test(`${name}: the palette rebuilt from the scale is the image's own, step for step (index 0 transparent)`, () => {
  const meta = JSON.parse(fs.readFileSync(path.join(SITE, 'data', name), 'utf8'));
  const pal = plte(path.join(SITE, 'data', meta.image));
  assert.strictEqual(pal.length, SS.STEPS + 1);
  for (let k = 0; k < SS.STEPS; k++) assert.deepStrictEqual(SS.at(meta.scale.stops, k / (SS.STEPS - 1)).map(SS.roundEven), pal[k + 1], `step ${k + 1}`);
});

test('roundEven is Python\'s round(): halves go to the even neighbour', () => {
  assert.deepStrictEqual([0.5, 1.5, 2.5, 3.5, 2.4, 2.6, 7].map(SS.roundEven), [0, 2, 2, 4, 2, 3, 7]);
});
