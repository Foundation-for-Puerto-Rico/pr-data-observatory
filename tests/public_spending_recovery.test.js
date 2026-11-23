// The Public spending page's disaster recovery section (public_spending_recovery.js; HANDOFF decision 89): the page has the section and its boxes, the
// module is loaded after ready with its Spanish module ("after" in i18n_src/pages.json) and is not a first-load script, and the section keeps its
// caution that subawards are part of the prime grants.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');
globalThis.window = globalThis;
require('../site/js/public_spending_recovery.js');

test('the module exposes start', () => assert.strictEqual(typeof globalThis.PSRecovery.start, 'function'));

test('the page has the section, loads the module after ready with its Spanish module', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/pages.json'), 'utf8'));
  for (const id of ['recovery', 'psRecMap', 'psRecKey', 'psRecSide', 'psRecTable', 'psRecMeasure', 'psRecFrom']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(/data-age="spending_cdbgdr\.json" data-cycle="\d+"/.test(html));
  assert.ok(!html.includes('public_spending_recovery.js'), 'not a first-load script');
  assert.ok(/public_spending_recovery\.js\?v=\d+/.test(js));
  assert.ok(js.includes("I18N.load('after')"));
  const mod = pages.pages.publicspending.modules.after;
  assert.ok(mod.scripts.includes('public_spending_recovery.js') && mod.html.includes('recovery'));
  assert.ok(/never add the two/.test(html), 'the caution that subawards are part of the prime grants');
});

test('the prime grants, obligated and paid out (decision 109, step 3): each grant number gets its purpose, and the page has the bars', () => {
  assert.strictEqual(globalThis.PSRecovery.kind('B-18-DP-72-0002'), 'Mitigation');
  assert.strictEqual(globalThis.PSRecovery.kind('B-18-DP-72-0001'), 'Recovery, hurricanes Irma and María');
  assert.strictEqual(globalThis.PSRecovery.kind('B-18-DE-72-0001'), 'Electrical grid');
  assert.strictEqual(globalThis.PSRecovery.kind('B-23-DN-72-0001'), 'Recovery, Hurricane Fiona');
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  assert.ok(html.includes('id="psRecGrants"') && /four of the six grants over \$100 million/.test(html));
  const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'site/data/spending_cdbgdr.json'), 'utf8'));
  assert.deepStrictEqual(d.grants.map((g) => g[0]), d.awards);
  for (const [, o, p] of d.grants) assert.ok(p >= 0 && p <= o + 1);
});
