// The Public spending page's sector view (public_spending_sectors.js; HANDOFF decision 87): for one function it shows the budget, federal
// obligations and capital projects of that function only, never one total of them; for Education the estimate by municipio splits the Department
// of Education's spending by its share of students, so the estimates add up to the Department's spending; and the page has the section, the
// function picker and a data-age line for each data file, with its update cycle from the dataset contract.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');

// a minimal document: draw() only writes innerHTML
globalThis.window = globalThis;
require('../site/js/public_spending_sectors.js');
const S = globalThis.PSSectors;

const T = (s, o = {}) => s.replace(/\{(\w+)\}/g, (_, k) => o[k]);
const ctx = (sector, extra = {}) => ({
  sector, T, esc: (s) => String(s), big: (v) => `$${Math.round(v)}`, usd: (v) => `$${Math.round(v)}`, pct: (v) => `${v.toFixed(1)}%`, fmt: (v) => String(v), fn: (i) => i,
  FUNCTION: { education: 'Education', health: 'Health' }, fetchJson: () => new Promise(() => {}),
  D: { functions: ['education', 'health'], agencies: { '081': 'Educación', '071': 'Salud' },
    columns: [{ year: 2025, stage: 'actual' }, { year: 2025, stage: 'approved' }, { year: 2027, stage: 'approved' }],
    rows: [['081', 0, 0, 0, [900, 1000, 1100]], ['071', 0, 0, 1, [400, 500, 600]]] },
  F: { years: [2025], functions: ['education', 'health'], rows: [['84.010', 'Title I', 0, 0, 0, [70]], ['93.778', 'Medicaid', 0, 1, 0, [300]]] },
  PICA: { years: [2026, 2029], agencies: [['Escuelas', 'education'], ['Hospitales', 'health']], by_agency: [['Escuelas', [10, 20], 5], ['Hospitales', [1, 1], 0]], population: [100, 100] },
  ...extra,
});

test('one function only, each source on its own line', () => {
  const box = {}; S.draw(box, ctx('health'));
  assert.match(box.innerHTML, /FY2027 approved<\/dt><dd>\$600 /);
  assert.match(box.innerHTML, /\$400 of \$500 approved/);
  assert.match(box.innerHTML, /federal FY2025<\/dt><dd>\$300</);
  assert.match(box.innerHTML, /2026 to 2029<\/dt><dd>\$2</);
  assert.match(box.innerHTML, /per resident, FY2027<\/dt><dd>\$3</);   // 600 / 200 residents
  assert.ok(!/\$902|\$1500/.test(box.innerHTML), 'no line adds the sources together');
});

test('education: the estimate by municipio adds up to the Department of Education spending', () => {
  const EDU = { geo: { ids: ['72001', '72003', '72'], names: ['Adjuntas', 'Aguada', 'Puerto Rico'] }, vars: [{ key: 'sch_enroll', years: { 2024: [30, 60, 90] } }] };
  const box = {};
  const c = ctx('education', { fetchJson: () => Promise.resolve(EDU) });
  S.draw(box, c);
  return new Promise((ok) => setTimeout(ok, 0)).then(() => {
    const est = [...box.innerHTML.matchAll(/<td>\$(\d+)<\/td><\/tr>/g)].map((m) => +m[1]);
    assert.deepStrictEqual(est.sort((a, b) => a - b), [300, 600]);
    assert.strictEqual(est.reduce((s, v) => s + v, 0), 900, 'the estimates add up to the spending split');
    assert.match(box.innerHTML, /Spent per student<\/dt><dd>\$10</);   // 900 / 90 students
    assert.match(box.innerHTML, /An estimate, not spending reported by municipio/);
  });
});

test('the page has the sector section and a data-age line per file, with the contract cycle', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const contract = JSON.parse(fs.readFileSync(path.join(ROOT, 'dictionary_src/datasets.json'), 'utf8'));
  const list = Array.isArray(contract) ? contract : contract.datasets;
  for (const id of ['psSector', 'psSectorPick']) assert.ok(html.includes(`id="${id}"`), id);
  for (const f of ['spending_state.json', 'spending_pica.json', 'spending_federal.json']) {
    const m = html.match(new RegExp(`data-age="${f.replace('.', '\\.')}" data-cycle="(\\d+)"`));
    assert.ok(m, f);
    const cad = list.find((d) => d.file === f).cadence;
    assert.strictEqual(+m[1], { annual: 365, monthly: 31, daily: 1 }[cad], f);
  }
  assert.ok(!html.includes('public_spending_sectors.js'), 'loaded after ready, not at first load');
});
