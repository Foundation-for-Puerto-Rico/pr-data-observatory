// The Public spending page's Method card "Where each line's function comes from" (PSCharts.basis; HANDOFF decision 109, step 4).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');
globalThis.window = globalThis;
require('../site/js/public_spending_charts.js');

test('basis: a row per budget, agencies by default and mixed agencies', () => {
  const D = { columns: [{ year: 2027, stage: 'approved' }], agencies: { 187: 'Health insurance', '025': 'Custody' }, functions: ['health', 'other'],
    basis: { kinds: ['program', 'object', 'concept', 'agency'], column: 0, by_column: [[10, 10, 20, 60]], agencies: [['187', 50, 50, 1, 0], ['025', 30, 0, 3, 1]] } };
  const box = { innerHTML: '' }, T = (s, p) => (p ? s.replace(/\{(\w+)\}/g, (_, k) => p[k]) : s);
  PSCharts.basis(box, { D, T, esc: String, big: String, pct: (v) => v + '%', FUNCTION: { health: 'Health', other: 'Other' } });
  assert.ok(box.innerHTML.includes('60%') && box.innerHTML.includes('Health insurance') && box.innerHTML.includes('3 functions'));
});

test('the page has the card in the Method section, waiting for its Spanish module', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  assert.ok(/id="basis" data-t-wait/.test(html) && html.includes('id="psBasis"'));
  assert.ok(html.indexOf('id="basis"') > html.indexOf('id="method"'));
  const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/pages.json'), 'utf8'));
  assert.ok(pages.pages.publicspending.modules.after.html.includes('basis'));
});
