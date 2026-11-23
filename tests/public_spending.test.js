// The Public spending page (public-spending.html, public_spending.js; HANDOFF decision 78): the treemap layout fills its box exactly, keeps every
// item's area in proportion to its value, and the page keeps the In review notice, noindex and the elements the script draws into.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const P = require('../site/js/public_spending.js');
const ROOT = path.join(__dirname, '..');

test('squarify: the tiles cover the box, do not overlap the edges, and each area is in proportion to its value', () => {
  const items = [7.62, 4.42, 4.32, 4.12, 3.59, 3.48, 2.11, 1.76, 0.83, 0.78, 0.26, 0.2, 0.1].map((v, i) => ({ k: i, v }));
  const W = 800, H = 460, out = P.squarify(items, 0, 0, W, H), total = items.reduce((s, it) => s + it.v, 0);
  assert.strictEqual(out.length, items.length);
  const area = out.reduce((s, t) => s + t.w * t.h, 0);
  assert.ok(Math.abs(area - W * H) < 1e-6 * W * H, 'the tiles add up to the box');
  for (const t of out) {
    assert.ok(t.x >= -1e-9 && t.y >= -1e-9 && t.x + t.w <= W + 1e-6 && t.y + t.h <= H + 1e-6, 'inside the box');
    assert.ok(Math.abs(t.w * t.h / (W * H) - t.v / total) < 1e-9, 'area in proportion');
  }
});

test('wrap: lines no longer than asked, words kept whole', () => {
  assert.deepStrictEqual(P.wrap('Environment and natural resources', 12), ['Environment', 'and natural', 'resources']);
});

test('the page is out of review: no noindex, the notice box kept for the AI sentence, and every element the script uses', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site', 'public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site', 'js', 'public_spending.js'), 'utf8');
  assert.doesNotMatch(html, /noindex/, 'leadership approved the page on 2026-11-09 (decision 73 (7)): search engines may list it');
  assert.match(html, /data-ka-note/);
  assert.match(html, /data-ka="publicspending"/);
  // every element the script looks up is in the page, except those the script writes itself (a button inside a panel it fills)
  for (const id of new Set([...js.matchAll(/\$\('#(ps[A-Za-z]+)/g)].map((m) => m[1]))) if (!js.includes(`id="${id}"`)) assert.ok(html.includes(`id="${id}"`), `#${id} is in the page`);
});

test('decision 112, step 3: the Oversight Board, the way back from a function, where spent comes from, and the reading notes', () => {
  const html = fs.readFileSync(path.join(ROOT, 'site/public-spending.html'), 'utf8');
  const js = fs.readFileSync(path.join(ROOT, 'site/js/public_spending.js'), 'utf8');
  const es = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/es/public_spending.json'), 'utf8'));
  const after = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src/es/public_spending_after.json'), 'utf8'));
  const gap = html.slice(html.indexOf('id="gap"'), html.indexOf('id="funds"'));
  assert.ok(/the Oversight Board certifies the budget that follows the fiscal plan/.test(gap), 'the Board is in the stages');
  assert.ok(gap.includes('href="money-cycle.html#stages"') && fs.readFileSync(path.join(ROOT, 'site/money-cycle.html'), 'utf8').includes('id="stages"'));
  // the second "All functions" control sits in the head of the stages chart, and the script shows it only while a function is chosen
  assert.ok(/id="psBack2" hidden>.*?<\/button><span id="psPipeHead"/.test(gap));
  assert.ok(js.includes("$('#psBack2').hidden = !S.f;") && js.includes("$('#psBack2').addEventListener('click', back)"));
  assert.ok((gap.match(/“Gastado” column/g) || []).length >= 2 && /no figure from the Treasury Department/.test(gap), 'where spent comes from, at the charts');
  for (const [id, re] of [['budget', /Names that are easy to confuse/], ['concepts', /Debt service is the payment of principal and interest/], ['federal', /A grant is not repaid; a loan is/], ['municipio', /Why one municipio shows far more recovery money/], ['sources', /Article VI, section 8/]]) {
    const at = html.indexOf(`id="${id}"`), sec = html.slice(at, html.indexOf('</section>', at));
    assert.ok(re.test(sec), `${id}: ${re}`);
  }
  // the figures of the notes are the budget file's own
  const D = JSON.parse(fs.readFileSync(path.join(ROOT, 'site/data/spending_state.json'), 'utf8'));
  const ci = D.columns.reduce((b, c, i) => (c.stage === 'approved' && (b < 0 || c.year > D.columns[b].year) ? i : b), -1);
  const sum = (f) => D.rows.reduce((s, r) => s + (f(r) ? r[4][ci] : 0), 0), bn = (v) => (v / 1e9).toFixed(2);
  const debt = sum((r) => D.concepts[r[2]] === 'debt_service');
  assert.ok(html.includes(`$${bn(sum((r) => r[0] === '025'))} billion) are not the Treasury Department's own budget`), 'custody of Hacienda');
  assert.ok(html.includes(`debt: $${bn(debt)} billion in the approved budget for fiscal year ${D.columns[ci].year}`), 'debt service');
  // every new note has Spanish, and none of it is held back
  const all = Object.assign({}, es, after);
  for (const k of Object.keys(all)) if (/Names that are easy to confuse|Debt service is the payment|A grant is not repaid|Why one municipio shows|Where “spent” comes from|Law and roles|The budget in force is the one the Board certifies/.test(k)) assert.notStrictEqual(all[k], k, k.slice(0, 60));
  assert.strictEqual(Object.keys(all).filter((k) => /Names that are easy to confuse|Debt service is the payment|A grant is not repaid|Why one municipio shows|Where “spent” comes from|Law and roles|The budget in force is the one the Board certifies/.test(k)).length, 7);
});
