/* Public spending, section 1: approved and reported as spent, by agency and fund (HANDOFF decision 112, step 2; docs/spending.md).
   Loaded on first use by public_spending.js, with its Spanish module 'agencies'. It reads the budget file the page already has: no new data. */
(function (root) {
  'use strict';
  let C, fund, year;
  /* The data sheets approve the Police inside the body with code 045 through fiscal year 2026 and report its spending under its own code (040)
     from the fiscal year 2027 sheets on: read apart, one shows spending with no budget and the other a budget barely spent. They are read as one. */
  const JOIN = { '040': '045' };
  const TOP = 15;

  /** The fiscal years that have both an approved and a spent column, newest first. */
  function years(D) {
    return D.columns.filter((c) => c.stage === 'actual' && D.columns.some((d) => d.year === c.year && d.stage === 'approved')).map((c) => c.year).sort((a, b) => b - a);
  }

  /** Approved and reported spent for one fiscal year and one fund: by agency (codes that moved joined), by concept of expense, and the totals. */
  function rows(D, y, fundKey) {
    const f = D.funds.indexOf(fundKey), ap = D.columns.findIndex((c) => c.year === y && c.stage === 'approved'), sp = D.columns.findIndex((c) => c.year === y && c.stage === 'actual');
    const by = {}, con = D.concepts.map((k) => [k, 0, 0]), joined = {};
    for (const [a, rf, rc, , v] of D.rows) {
      if (rf !== f || (!v[ap] && !v[sp])) continue;
      const id = JOIN[a] || a;
      if (JOIN[a]) joined[id] = a;
      const r = by[id] || (by[id] = { id, approved: 0, spent: 0 });
      r.approved += v[ap]; r.spent += v[sp]; con[rc][1] += v[ap]; con[rc][2] += v[sp];
    }
    const list = Object.values(by).map((r) => Object.assign(r, { name: joined[r.id] ? `${D.agencies[r.id]} + ${D.agencies[joined[r.id]]}` : D.agencies[r.id], joined: !!joined[r.id], diff: r.approved - r.spent }));
    const under = list.filter((r) => r.diff > 0).sort((a, b) => b.diff - a.diff), over = list.filter((r) => r.diff < 0).sort((a, b) => a.diff - b.diff);
    const add = (l, k) => l.reduce((s, r) => s + r[k], 0);
    return { under, over, same: list.length - under.length - over.length, approved: add(list, 'approved'), spent: add(list, 'spent'), under_usd: add(under, 'diff'), over_usd: -add(over, 'diff'),
      concepts: con.filter((c) => c[1] || c[2]), joined: list.some((r) => r.joined) };
  }

  function table(caption, list) {
    const { T, esc, usd, pct } = C;
    return `<div class="ps-tablebox"><table class="ps-table"><caption>${esc(caption)}</caption><thead><tr><th scope="col">${esc(T('Agency'))}</th><th scope="col">${esc(T('Approved'))}</th><th scope="col">${esc(T('Reported spent'))}</th><th scope="col">${esc(T('Difference'))}</th><th scope="col">${esc(T('Spent as a share of approved'))}</th></tr></thead><tbody>${
      list.map((r) => `<tr><th scope="row">${esc(r.name)}${r.joined ? ' *' : ''}</th><td>${esc(usd(r.approved))}</td><td>${esc(usd(r.spent))}</td><td>${esc(usd(r.approved - r.spent))}</td><td>${r.approved ? esc(pct(100 * r.spent / r.approved, 0)) : '—'}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function start(ctx, fundKey) { C = ctx; year = years(C.D)[0]; show(fundKey); }

  function show(fundKey) {
    const { $, T, esc, big, pct, D, FUND, CONCEPT } = C, box = $('#psAgencies'), ys = years(D);
    if (fundKey !== undefined) fund = fundKey;
    if (!fund || !ys.length) { box.innerHTML = ''; return; }
    const R = rows(D, year, fund), name = T(FUND[fund]), v = { fund: name, year };
    let h = `<div class="ps-controls"><label>${esc(T('Fiscal year'))} <select id="psAgYear">${ys.map((y) => `<option value="${y}"${y === year ? ' selected' : ''}>${y}</option>`).join('')}</select></label></div>`;
    h += `<p class="ps-p">${esc(T('{fund}, fiscal year {year}: {approved} approved and {spent} reported as spent ({share}). {n} agencies reported less than their approved budget, {under} together; {m} reported more, {over} together.',
      Object.assign({ approved: big(R.approved), spent: big(R.spent), share: R.approved ? pct(100 * R.spent / R.approved, 0) : '—', n: R.under.length, under: big(R.under_usd), m: R.over.length, over: big(R.over_usd) }, v)))}</p>`;
    h += `<p class="ps-small">${esc(T(fund === 'federal' ? 'Read with care: federal money is often awarded for several years, above all for disaster recovery, so a year with less spent than approved is expected. The difference does not say the money went unused.'
      : fund === 'special' ? 'Read with care: special funds are fees and other revenue set aside by law. When less comes in than was budgeted, less can be spent. The difference does not say the money was available.'
        : 'Read with care: the difference does not say why. It can come from reserves held back, payments made after June 30 or changes to the budget during the year, which the data sheets do not record.'))}</p>`;
    h += `<div class="card ps-chart">${table(T('{fund}, fiscal year {year}: the {k} agencies with the largest difference between approved and reported spent', Object.assign({ k: Math.min(TOP, R.under.length) }, v)), R.under.slice(0, TOP))}`;
    if (R.under.length > TOP) h += `<details class="ps-more"><summary>${esc(T('See all {n} agencies that reported less than approved', { n: R.under.length }))}</summary>${table(T('{fund}, fiscal year {year}: every agency that reported less than approved', v), R.under)}</details>`;
    if (R.over.length) h += `<details class="ps-more"><summary>${esc(T('See the {n} agencies that reported more than approved', { n: R.over.length }))}</summary>${table(T('{fund}, fiscal year {year}: agencies that reported more than approved', v), R.over)}<p class="ps-small">${esc(T('An agency can report more than its approved budget when money is moved to it during the year: the data sheets give the budget as approved, not as amended.'))}</p></details>`;
    h += `<details class="ps-more"><summary>${esc(T('See the same by concept of expense'))}</summary>${table(T('{fund}, fiscal year {year}: approved and reported spent by concept of expense', v), R.concepts.map(([k, a, s]) => ({ name: T(CONCEPT[k]), approved: a, spent: s }))).replace(esc(T('Agency')), esc(T('Concept of expense')))}</details></div>`;
    if (R.joined) h += `<p class="ps-small">${esc(T('* Two codes read as one: the data sheets approve the Police inside this body and report its spending under its own code.'))}</p>`;
    h += `<p class="ps-small">${esc(T('Reported spent is what each agency told the Office of Management and Budget during the next budget process, not the audited close.'))}</p>`;
    h += `<p class="ps-small">${esc(T(fund === 'federal' ? 'What happens to money not spent: federal money follows the rules and the period of each federal grant, not the fiscal year of the Commonwealth. The data sheets do not show what was done with each difference.'
      : fund === 'special' ? 'What happens to money not spent: in special revenue funds, the income of earlier fiscal years can be used, under the rules that apply to each fund (Manual of the Budget Process of OGP). The data sheets do not show what was done with each difference.'
        : 'What happens to money not spent: in the General Fund, an agency cannot use money of an earlier fiscal year unless the certified budget says so (Manual of the Budget Process of OGP). The data sheets do not show what was done with each difference.'))}</p>`;
    box.innerHTML = h;
    $('#psAgYear').addEventListener('change', (e) => { year = +e.target.value; show(); });
  }

  root.PSAgencies = { start, show, rows, years, JOIN };
})(typeof window !== 'undefined' ? window : globalThis);
