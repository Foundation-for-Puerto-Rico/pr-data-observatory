// The Public spending page's section 8 (public_spending_fema.js; HANDOFF decision 109, step 2): the module sums a municipio's stages, the page has the
// section and loads the module after ready with its Spanish module, and the section keeps its cautions (Statewide is not on the map; an old open project
// shows where to ask, not a failure; never added to section 5).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');
globalThis.window = globalThis;
require('../site/js/public_spending_fema.js');

test('muni: dollars by stage, share closed and dollars open over five years per resident', () => {
  const d = { by_muni: { usd: [[10, 30, 60], [0, 0, 0]], median_age: [4.5, null], over5_usd: [50, 0] }, population: [10, 0] };
  const a = PSFema.muni(d, 0);
  assert.strictEqual(a.total, 100); assert.strictEqual(a.closed, 0.1); assert.strictEqual(a.perRes, 5); assert.strictEqual(a.age, 4.5);
  const b = PSFema.muni(d, 1);
  assert.strictEqual(b.closed, null); assert.strictEqual(b.perRes, 0);
});

test('the page has the section, loads the module after ready, and keeps its cautions', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/pages.json'), 'utf8'));
  for (const id of ['fema', 'psFemaTiles', 'psFemaStage', 'psFemaAge', 'psFemaMeasure', 'psFemaMap', 'psFemaSide', 'psFemaMuni', 'psFemaTable']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(/data-age="spending_fema_pa\.json" data-cycle="\d+"/.test(html));
  assert.ok(!html.includes('public_spending_fema.js'), 'not a first-load script');
  assert.ok(/public_spending_fema\.js\?v=\d+/.test(js));
  const mod = pages.pages.publicspending.modules.after;
  assert.ok(mod.scripts.includes('public_spending_fema.js') && mod.html.includes('fema'));
  assert.ok(/Statewide/.test(html) && /not to a failure/.test(html) && /Never add these dollars/.test(html));
  assert.ok(html.includes('href="public-money.html"'), 'links to the Disaster funding and need page');
});
