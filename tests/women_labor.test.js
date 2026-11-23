// Tests for the arithmetic of the Women in the labor force page (site/js/women_labor.js): it must give the figures women_labor.py publishes in
// data/women_labor.json ("analysis"), for every window, so the page and the pipeline never disagree. Run: node --test tests/women_labor.test.js
// (python -m unittest tests.test_core_js runs it too).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const W = require(path.join(ROOT, 'site', 'js', 'women_labor.js'));
const D = JSON.parse(fs.readFileSync(path.join(ROOT, 'site', 'data', 'women_labor.json'), 'utf8'));
const close = (a, b, msg, tol = 0.006) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);   // the file keeps two decimals

test('the formulas: sums add margins in quadrature, a proportion follows the Census Bureau formula, a difference is significant when larger than its margin', () => {
  assert.deepStrictEqual(W.esum([[100, 3], [50, 4]]), [150, 5]);
  assert.strictEqual(W.esum([[1, 1], null]), null);
  const p = W.prop([40, 6], [100, 8]);   // p = .4: sqrt(36 - .16*64) / 100 = sqrt(25.76) / 100
  close(p[0], 40, 'value'); close(p[1], 100 * Math.sqrt(25.76) / 100, 'margin', 1e-9);
  const q = W.prop([90, 2], [100, 30]);   // the root is negative: the ratio formula
  close(q[1], 100 * Math.sqrt(4 + 0.81 * 900) / 100, 'ratio margin', 1e-9);
  assert.deepStrictEqual(W.diff([10, 3], [5, 4]), { v: 5, m: 5, sig: false });
  assert.strictEqual(W.diff([10.1, 3], [5, 4]).sig, true);
});

test('the Eastern Region and the rest of Puerto Rico: the page computes what women_labor.py published, in every window', () => {
  const ids = D.groups.ersv.ids;
  assert.strictEqual(ids.length, 15);
  for (const w of D.window_ends) {
    const a = D.areas[String(w)], rest = Object.keys(D.names).filter(g => !ids.includes(g));
    const reg = W.combine(ids.map(g => a[g])), oth = W.combine(rest.map(g => a[g]));
    const mr = W.measures(reg), mo = W.measures(oth), want = D.analysis.ersv[String(w)];
    for (const k of ['lfpr_f', 'lfpr_m', 'lfpr_f_prime', 'unemp_f', 'women16']) {
      close(mr[k][0], want.region[k][0], `${w} region ${k}`); close(mr[k][1], want.region[k][1], `${w} region ${k} margin`);
      close(mo[k][0], want.rest[k][0], `${w} rest ${k}`);
    }
    const d = W.diff(mr.lfpr_f, mo.lfpr_f);
    close(d.v, want.vs_rest.lfpr_f.v, `${w} difference`); assert.strictEqual(d.sig, want.vs_rest.lfpr_f.sig, `${w} significance`);
    const g = W.diff(mr.lfpr_m, mr.lfpr_f);
    close(g.v, want.gender_gap.v, `${w} gender gap`);
    const k = W.ageSplit(reg, oth);
    close(k.from_age_mix, want.age_adjusted.from_age_mix, `${w} age mix`); close(k.from_rates, want.age_adjusted.from_rates, `${w} rates`);
    close(k.adjusted, want.age_adjusted.adjusted, `${w} adjusted`);
    close(k.from_age_mix + k.from_rates, mr.lfpr_f[0] - mo.lfpr_f[0], `${w} the two parts add up to the gap`, 1e-6);
  }
});

test('the island row equals the sum of its 78 municipios (the survey adds up)', () => {
  for (const w of D.window_ends) {
    const a = D.areas[String(w)], all = W.combine(Object.keys(D.names).map(g => a[g]));
    for (const s of ['m', 'f']) for (let i = 0; i < 7; i++) for (let k = 0; k < 4; k++) {
      assert.strictEqual(all[s][i][k][0], a['72'][s][i][k][0], `${w} ${s} age ${i} cell ${k}`);
    }
  }
});
