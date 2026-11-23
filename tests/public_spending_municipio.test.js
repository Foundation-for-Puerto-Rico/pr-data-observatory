// The Public spending page's My municipio section (public_spending_municipio.js; HANDOFF decision 109, step 5): the four answers of a municipio,
// the module and its Spanish load on first use (not in the HTML, not in the after-ready list), and the section links ABRE Tu Municipio.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');
globalThis.window = globalThis;
require('../site/js/public_spending_municipio.js');

test('answers: obligated adds the subawards and FEMA; paid is never published by municipio', () => {
  const a = PSMuni.answers({ cdbgdr: 10, fema_usd: [5, 10, 5], fema_age: 4.2, fema_over5: 3 });
  assert.strictEqual(a.obligated, 30); assert.strictEqual(a.closed, 0.25); assert.strictEqual(a.paid, null); assert.strictEqual(a.age, 4.2);
  assert.strictEqual(PSMuni.answers({ cdbgdr: 0, fema_usd: [0, 0, 0], fema_age: null, fema_over5: 0 }).closed, null);
});

test('the section is on the page and its module loads on first use, with its Spanish module', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  for (const id of ['municipio', 'psMuniPick', 'psMuni']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(!html.includes('public_spending_municipio.js'));
  assert.ok(/public_spending_municipio\.js\?v=\d+/.test(js) && js.includes("I18N.load('municipio')"));
  const routes = JSON.parse(fs.readFileSync(path.join(ROOT, 'dictionary_src/routes.json'), 'utf8')).routes.publicspending;
  assert.ok(!routes.deferred.includes('js/public_spending_municipio.js'), 'loaded on first use, not after ready');
  assert.ok(routes.on_use.includes('spending_municipio.json'));
  const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/pages.json'), 'utf8'));
  assert.deepStrictEqual(pages.pages.publicspending.modules.municipio.scripts, ['public_spending_municipio.js']);
  assert.ok(html.includes('https://www.abretumunicipio.org/'));
  const mod = fs.readFileSync(path.join(ROOT, 'site/js/public_spending_municipio.js'), 'utf8');
  assert.ok(mod.includes('https://www.abretumunicipio.org/municipio/'));
});
