/* Public spending, section 5: obligated and paid out (decision 96, step 2; docs/spending.md). Loaded after ready by public_spending.js. */
(function (root) {
  'use strict';
  let C, O, st = { g: 'all' };

  function start(ctx) {
    C = ctx;
    C.fetchJson('data/spending_outlays.json').then((d) => { O = d; setup(); }, (e) => {
      C.$('#psOut').innerHTML = `<p class="ps-p">${C.esc(C.T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }

  function setup() {
    const { $, T, esc } = C;
    $('#psOutGroup').innerHTML = [['all', T('Grants and contracts')], ['grants', T('Grants')], ['contracts', T('Contracts')]]
      .map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('');
    $('#psOutGroup').addEventListener('change', (e) => { st.g = e.target.value; draw(); });
    C.age('spending_outlays.json', O);
    draw();
  }

  const add = (a, b) => a.map((v, i) => v + b[i]);

  function summarize(d, g) {
    const rows = d.rows.filter((r) => g === 'all' || d.groups[r[2]] === g), n = d.years.length, z = () => new Array(n).fill(0);
    const byFn = new Map(), byYear = { o: z(), p: z() };
    for (const r of rows) {
      const f = d.functions[r[3]], e = byFn.get(f) || { o: 0, p: 0 };
      e.o += r[5].reduce((s, v) => s + v, 0); e.p += r[6].reduce((s, v) => s + v, 0); byFn.set(f, e);
      byYear.o = add(byYear.o, r[5]); byYear.p = add(byYear.p, r[6]);
    }
    const fns = [...byFn].map(([f, e]) => ({ f, o: e.o, p: e.p })).filter((x) => x.o > 0).sort((a, b) => b.o - a.o);
    return { fns, byYear };
  }

  function draw() {
    const { $, T, esc, big, pct, FUNCTION } = C, s = summarize(O, st.g), ys = O.years, y0 = ys[0], y1 = ys[ys.length - 1];
    const O_ = s.byYear.o.reduce((a, v) => a + v, 0), P_ = s.byYear.p.reduce((a, v) => a + v, 0), mx = s.fns.length ? s.fns[0].o : 1;
    $('#psOutHead').textContent = T('Signed in federal fiscal years {a} to {b}: {paid} paid out of {obligated} obligated ({share})', { a: y0, b: y1, paid: big(P_), obligated: big(O_), share: O_ ? pct(100 * P_ / O_, 0) : '—' });
    const name = (f) => T(FUNCTION[f] || f);
    $('#psOutYrs').innerHTML = `<ul class="ps-cols" aria-label="${esc(T('Columns: share paid out by the federal fiscal year the awards were signed. The table below has the figures.'))}">${ys.map((y, i) => { const o = s.byYear.o[i], sh = o ? 100 * s.byYear.p[i] / o : 0; return `<li><span class="v">${esc(o ? pct(sh, 0) : '—')}</span><span class="c"><i style="height:${sh.toFixed(1)}%"></i></span><span class="l">${y}</span></li>`; }).join('')}</ul>`;
    $('#psOut').innerHTML = `<ul class="ps-out" aria-label="${esc(T('Bars: obligated and paid out by function. The table below has the figures.'))}">${s.fns.map((x) =>
      `<li><span class="l">${esc(name(x.f))}</span><span class="b" title="${esc(T('{fn}: {paid} paid out of {obligated} obligated ({share})', { fn: name(x.f), paid: big(x.p), obligated: big(x.o), share: pct(100 * x.p / x.o, 0) }))}"><i class="o" style="width:${(100 * x.o / mx).toFixed(1)}%"></i><i class="p" style="width:${(100 * x.p / mx).toFixed(1)}%"></i></span><span class="v">${esc(pct(100 * x.p / x.o, 0))}</span></li>`).join('')}</ul>`;
    $('#psOutYears').innerHTML = `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Signed in'))}</th><th scope="col">${esc(T('Obligated'))}</th><th scope="col">${esc(T('Paid out'))}</th><th scope="col">${esc(T('Share paid out'))}</th></tr></thead><tbody>${
      ys.map((y, i) => `<tr><th scope="row">${esc(T('Federal FY{year}', { year: y }))}</th><td>${esc(big(s.byYear.o[i]))}</td><td>${esc(big(s.byYear.p[i]))}</td><td>${esc(s.byYear.o[i] ? pct(100 * s.byYear.p[i] / s.byYear.o[i], 0) : '—')}</td></tr>`).join('')}</tbody></table>` +
      `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Function'))}</th><th scope="col">${esc(T('Obligated'))}</th><th scope="col">${esc(T('Paid out'))}</th><th scope="col">${esc(T('Share paid out'))}</th></tr></thead><tbody>${
      s.fns.map((x) => `<tr><th scope="row">${esc(name(x.f))}</th><td>${esc(big(x.o))}</td><td>${esc(big(x.p))}</td><td>${esc(pct(100 * x.p / x.o, 0))}</td></tr>`).join('')}</tbody></table>`;
    const gs = st.g === 'all' ? O.groups : [st.g], tot = (k) => gs.reduce((a, g) => a + O.totals[g][k].reduce((s, v) => s + v, 0), 0);
    const pa = O.excluded['97.036'], paO = pa ? pa.obligated.reduce((a, v) => a + v, 0) : 0;
    $('#psOutNote').textContent = T('{over} awards report more paid out than obligated ({excess} in all); each counts here up to its obligated amount. {none} awards report no outlay yet; about a third of the contracts report none, so their share is understated. FEMA Public Assistance is left out ({pa} obligated in these awards): USAspending does not follow its projects.',
      { over: tot('over_n').toLocaleString(C.loc()), excess: big(tot('over_usd')), none: tot('no_outlay').toLocaleString(C.loc()), pa: big(paO) });
  }

  root.PSOutlays = { start, summarize };
})(typeof window !== 'undefined' ? window : globalThis);
