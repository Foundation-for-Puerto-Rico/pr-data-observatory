// The Public spending page's "Obligated and paid out" card (public_spending_outlays.js; HANDOFF decision 96, step 2): the module sums obligated and
// paid out by function and signing year for the group chosen, the page has the card and loads the module after ready with its Spanish module ("after"
// in i18n_src/pages.json), and the published file never shows more paid out than obligated in a function.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');
globalThis.window = globalThis;
require('../site/js/public_spending_outlays.js');

const D = { years: [2020, 2021], groups: ['grants', 'contracts'], functions: ['education', 'health'],
  rows: [['84.010', 'Title I', 0, 0, 0, [100, 50], [90, 10]], ['93.778', 'Medicaid', 0, 1, 0, [200, 0], [150, 0]], ['contracts:X', 'X', 1, 1, 2, [10, 10], [1, 0]]] };

test('summarize: by function, largest first, and by signing year, for the group chosen', () => {
  const s = PSOutlays.summarize(D, 'all');
  assert.deepStrictEqual(s.fns.map((x) => [x.f, x.o, x.p]), [['health', 220, 151], ['education', 150, 100]]);
  assert.deepStrictEqual(s.byYear, { o: [310, 60], p: [241, 10] });
  const g = PSOutlays.summarize(D, 'grants');
  assert.deepStrictEqual(g.fns.map((x) => [x.f, x.o, x.p]), [['health', 200, 150], ['education', 150, 100]]);
  assert.deepStrictEqual(PSOutlays.summarize(D, 'contracts').byYear, { o: [10, 10], p: [1, 0] });
});

test('the page has the card and loads the module after ready with its Spanish module', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/pages.json'), 'utf8'));
  for (const id of ['outlays', 'psOut', 'psOutHead', 'psOutGroup', 'psOutNote', 'psOutYears', 'psOutYrs']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(/data-age="spending_outlays\.json" data-cycle="\d+"/.test(html));
  assert.ok(!html.includes('public_spending_outlays.js'), 'not a first-load script');
  assert.ok(/public_spending_outlays\.js\?v=\d+/.test(js));
  const mod = pages.pages.publicspending.modules.after;
  assert.ok(mod.scripts.includes('public_spending_outlays.js') && mod.html.includes('outlays'));
});

test('the published file: paid out never passes obligated in any function', () => {
  const p = path.join(ROOT, 'site/data/spending_outlays.json');
  if (!fs.existsSync(p)) return;
  const d = JSON.parse(fs.readFileSync(p, 'utf8'));
  for (const x of PSOutlays.summarize(d, 'all').fns) assert.ok(x.p <= x.o, x.f);
});

test('the share paid out by signing year is a visible chart, with its caution (decision 109, step 1)', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  assert.ok(/id="psOutYrs"/.test(html) && /not that anyone failed to comply/.test(html));
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending_outlays.js'), 'utf8');
  assert.ok(js.includes("$('#psOutYrs')") && js.includes('ps-cols'));
});
