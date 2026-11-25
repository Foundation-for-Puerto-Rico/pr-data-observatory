// The ready-made views of each topic (navigation plan PR 6, decision 81) against the map's data engine: every dataset a view shows is one the engine has, and every
// scale it asks for (norm) is one that dataset offers (Core.normalize.options), and every color ramp is one of core/palettes.js, so ECON.api.show draws the view as
// written; every layer is an l= key of app.js.
// The build checks the rest (catalog.py presets(); tests/test_catalog.py ReadyMadeViews).  Run: node --test tests/presets.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..'), SITE = path.join(ROOT, 'site');
const core = (n) => require(path.join(SITE, 'js', 'core', n + '.js'));
const read = (f) => JSON.parse(fs.readFileSync(path.join(SITE, 'data', f), 'utf8'));

test('every view draws what it names: known datasets, offered scales, known layers', async () => {
  const engine = core('engine'), datasets = core('datasets'), normalize = core('normalize'), palettes = core('palettes'); core('adapters');
  const E = engine.create();
  await datasets.load(E, (p) => Promise.resolve(read(p.replace(/^data\//, ''))), read('municipalities.json'), 2026);
  const app = fs.readFileSync(path.join(SITE, 'js', 'app.js'), 'utf8'), keys = new Set([...app.match(/const LAYER_KEYS = \{([^}]*)\}/)[1].matchAll(/(\w+): 'ly\w+'/g)].map(m => m[1]));
  const views = read('catalog_views.json').presets, bad = [];
  let n = 0;
  for (const [dom, vs] of Object.entries(views)) for (const v of vs) {
    n++;
    for (const [key, mode, o = {}] of v.show) {
      const norm = o.norm;
      if (o.ramp && !palettes.RAMPS[o.ramp]) bad.push(`${dom}.${v.id}: ${key} has no ramp ${o.ramp}`);
      if (!E.V[key]) { bad.push(`${dom}.${v.id}: no dataset ${key}`); continue; }
      if (norm && !normalize.options(E.V[key]).some(o => o[0] === norm)) bad.push(`${dom}.${v.id}: ${key} offers no scale ${norm}`);
      if (mode !== 'fill' && mode !== 'symbol') bad.push(`${dom}.${v.id}: ${key} as ${mode}`);
    }
    v.on.filter(k => !keys.has(k)).forEach(k => bad.push(`${dom}.${v.id}: no layer ${k}`));
  }
  assert.ok(n >= 20, `the views are read (${n})`);
  assert.deepStrictEqual(bad, []);
});
