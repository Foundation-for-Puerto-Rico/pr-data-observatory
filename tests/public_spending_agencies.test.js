// The Public spending page's approved and reported spent by agency and fund (public_spending_agencies.js; HANDOFF decision 112, step 2):
// the figures add up to the budget file's own totals, the one join of agency codes holds, the funds are never mixed, the module and its
// Spanish load on first use, and the wording never calls a difference a surplus or a loss.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');
globalThis.window = globalThis;
require('../site/js/public_spending_agencies.js');
const D = JSON.parse(fs.readFileSync(path.join(ROOT, 'site/data/spending_state.json'), 'utf8'));

test('rows: a small budget, by hand', () => {
  const d = { funds: ['general', 'federal'], concepts: ['payroll', 'other'], agencies: { '001': 'A', '002': 'B', '045': 'Safety', '040': 'Police' },
    columns: [{ year: 2025, stage: 'actual' }, { year: 2025, stage: 'approved' }, { year: 2026, stage: 'approved' }],
    rows: [['001', 0, 0, 0, [60, 100, 0]], ['001', 0, 1, 0, [10, 10, 0]], ['002', 0, 0, 0, [50, 30, 0]], ['045', 0, 0, 0, [20, 90, 0]], ['040', 0, 0, 0, [65, 0, 0]], ['001', 1, 0, 0, [999, 999, 0]]] };
  assert.deepStrictEqual(PSAgencies.years(d), [2025]);
  const r = PSAgencies.rows(d, 2025, 'general');
  assert.strictEqual(r.approved, 230); assert.strictEqual(r.spent, 205);
  assert.deepStrictEqual(r.under.map((x) => [x.id, x.diff]), [['001', 40], ['045', 5]]);   // the Police joins the body that holds its budget
  assert.deepStrictEqual(r.over.map((x) => [x.id, x.diff]), [['002', -20]]);
  assert.strictEqual(r.under_usd, 45); assert.strictEqual(r.over_usd, 20); assert.ok(r.joined);
  assert.strictEqual(r.under[1].name, 'Safety + Police');
  assert.deepStrictEqual(r.concepts, [['payroll', 220, 195], ['other', 10, 10]]);
  assert.strictEqual(PSAgencies.rows(d, 2025, 'federal').approved, 999);   // another fund is another table
});

test('the published budget: every fund and year adds up to the file, and the differences balance', () => {
  const ys = PSAgencies.years(D);
  assert.ok(ys.length >= 2 && ys[0] > ys[1], 'newest first');
  for (const y of ys) {
    let ap = 0, sp = 0;
    for (const f of D.funds) {
      const r = PSAgencies.rows(D, y, f);
      ap += r.approved; sp += r.spent;
      assert.strictEqual(r.under_usd - r.over_usd, r.approved - r.spent, `${y} ${f}`);
      assert.ok(r.under.every((x, i, l) => !i || l[i - 1].diff >= x.diff), 'largest difference first');
      assert.ok(r.under.concat(r.over).every((x) => x.name), 'every agency has a name');
      assert.strictEqual(r.concepts.reduce((s, c) => s + c[1], 0), r.approved);
    }
    assert.strictEqual(ap, D.columns.find((c) => c.year === y && c.stage === 'approved').total, `approved ${y}`);
    assert.strictEqual(sp, D.columns.find((c) => c.year === y && c.stage === 'actual').total, `spent ${y}`);
  }
});

test('agency codes: after the joins, no large agency has only one of the two stages', () => {
  for (const y of PSAgencies.years(D)) {
    const tot = {};
    for (const f of D.funds) for (const r of PSAgencies.rows(D, y, f).under.concat(PSAgencies.rows(D, y, f).over)) { const t = tot[r.id] || (tot[r.id] = [0, 0]); t[0] += r.approved; t[1] += r.spent; }
    for (const [id, [a, s]] of Object.entries(tot)) assert.ok(!((a === 0) !== (s === 0) && Math.max(a, s) > 20e6), `${y} ${id} ${D.agencies[id]}: ${a} approved, ${s} spent: a code that moved? (JOIN, docs/spending.md)`);
  }
  for (const [from, to] of Object.entries(PSAgencies.JOIN)) assert.ok(D.agencies[from] && D.agencies[to], `${from} -> ${to}`);
});

test('the part is on the page and its module loads on first use, with its Spanish module', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  for (const id of ['psAgFund', 'psAgencies']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(html.indexOf('id="psAgFund"') > html.indexOf('id="gap"') && html.indexOf('id="psAgFund"') < html.indexOf('id="funds"'), 'inside section 1');
  assert.ok(!html.includes('public_spending_agencies.js'));
  assert.ok(/public_spending_agencies\.js\?v=\d+/.test(js) && js.includes("I18N.load('agencies')"));
  const routes = JSON.parse(fs.readFileSync(path.join(ROOT, 'dictionary_src/routes.json'), 'utf8')).routes.publicspending;
  assert.ok(!routes.deferred.includes('js/public_spending_agencies.js'), 'loaded on first use, not after ready');
  const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/pages.json'), 'utf8'));
  assert.deepStrictEqual(pages.pages.publicspending.modules.agencies.scripts, ['public_spending_agencies.js']);
});

test('wording: a difference is never called a surplus, a loss or money left over, and every string has Spanish', () => {
  const mod = fs.readFileSync(path.join(ROOT, 'site/js/public_spending_agencies.js'), 'utf8');
  const es = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/es/public_spending_agencies.json'), 'utf8'));
  const main = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/es/public_spending.json'), 'utf8'));
  const strings = [...mod.matchAll(/T\((?:fund === [^:]+\? )?'((?:[^'\\]|\\.)+)'/g)].map((m) => m[1]).concat([...mod.matchAll(/: '(Read with care[^']+)'/g)].map((m) => m[1]));
  assert.ok(strings.length >= 15, String(strings.length));
  for (const s of strings) {
    assert.ok(!/surplus|left over|leftover|\blost\b|\bloss\b|wasted|returned/i.test(s), s);
    assert.ok(es[s] || main[s], `no Spanish: ${s}`);
  }
  for (const v of Object.values(es)) assert.ok(!/sobrante|perdid|devuelt|desperdici/i.test(v), v);
});
