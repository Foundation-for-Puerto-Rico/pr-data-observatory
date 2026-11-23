/* Public spending, section 9: My municipio (decision 109, step 5; docs/spending.md). Loaded on first use by public_spending.js, with its Spanish module. */
(function (root) {
  'use strict';
  let C, M;
  const sum = (a) => a.reduce((s, v) => s + v, 0);

  function start(ctx, id) {
    C = ctx;
    C.fetchJson('data/spending_municipio.json').then((d) => { M = d; show(id); }, (e) => {
      C.$('#psMuni').innerHTML = `<p class="ps-p">${C.esc(C.T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }

  /** The four questions for one municipio row: [obligated, paid, pending, progress], each text or null when not published. Exported for the tests. */
  function answers(m) {
    const f = sum(m.fema_usd);
    return { obligated: m.cdbgdr + f, fema: f, closed: f ? m.fema_usd[0] / f : null, age: m.fema_age, over5: m.fema_over5, paid: null };
  }

  function show(id) {
    if (!M) return;
    const { $, T, esc, big, pct } = C, m = M.municipios.find((x) => String(x.id) === String(id));
    if (!m) { $('#psMuni').innerHTML = ''; return; }
    const a = answers(m), y = M.years, ctx = M.context, row = (k, v, w) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td><td>${w}</td></tr>`;
    const who = (s) => esc(T(s));
    let h = `<h3>${esc(m.name)}</h3><table class="ps-table"><thead><tr><th scope="col">${esc(T('Money in its territory'))}</th><th scope="col">${esc(T('Dollars'))}</th><th scope="col">${esc(T('Who runs it'))}</th></tr></thead><tbody>`;
    h += row(T('Capital plan, fiscal years {a} to {b} (planned)', { a: y.plan[0], b: y.plan[1] }), big(m.plan), m.plan_top.length ? esc(m.plan_top.map(([g, v]) => `${g} (${big(v)})`).join('; ')) : '—');
    h += row(T('Disaster recovery subawards, federal fiscal years {a} to {b} (obligated)', { a: y.cdbgdr[0], b: y.cdbgdr[1] }), big(m.cdbgdr), who('The Department of Housing, which passed them to municipalities, contractors and nonprofits'));
    h += row(T('FEMA Public Assistance, projects that name the municipio (obligated)'), big(a.fema), who('The applicant of each project (the municipio, Commonwealth agencies or nonprofits), with FEMA and COR3'));
    h += row(T('Federal awards of every type, federal fiscal year {y} (obligated)', { y: y.fed[1] }), big(m.fed_last), who('Federal agencies, paying benefits, grants and contracts to people and organizations in the municipio'));
    h += `</tbody></table>`;
    h += `<h4>${esc(T('The four questions'))}</h4><dl class="ps-dl ps-q">`;
    h += `<dt>${esc(T('1. How much recovery money is obligated?'))}</dt><dd>${esc(T('{total}: {sub} in disaster recovery subawards and {fema} in FEMA projects that name the municipio. The {sw} of FEMA money recorded as Statewide names no municipio, so this is only part of it.', { total: big(a.obligated), sub: big(m.cdbgdr), fema: big(a.fema), sw: pct(100 * ctx.fema_statewide_usd / ctx.fema_total_usd, 0) }))}</dd>`;
    h += `<dt>${esc(T('2. How much has been paid?'))}</dt><dd>${esc(T('Not published by municipio: USAspending reports no payments on subawards and OpenFEMA none on projects. Island-wide payments are in sections 5 and 7.'))}</dd>`;
    h += `<dt>${esc(T('3. How long has it been pending?'))}</dt><dd>${esc(a.age == null ? T('No open FEMA project names the municipio.') : T('FEMA money still open has a median age of {age} years since its first obligation; {over5} has been open more than five years.', { age: a.age.toLocaleString(C.loc()), over5: big(a.over5) }))}</dd>`;
    h += `<dt>${esc(T('4. What do we know of the progress?'))}</dt><dd>${esc(T('{share} of the FEMA dollars that name the municipio are in projects closed out. No open source reports the physical progress of the works.', { share: a.closed == null ? '—' : pct(100 * a.closed, 0) }))}</dd></dl>`;
    h += `<h4>${esc(T('What could be requested to evaluate execution'))}</h4><ul class="ps-p">${['From the municipio: its FEMA projects, their status and the documents still pending.',
      'From COR3: the project worksheets and reimbursement requests of the projects in the municipio.',
      'From the Department of Housing: the disaster recovery activities and draws in the municipio (its quarterly performance reports).',
      'From the agencies of the capital plan: the status of their projects in the municipio.'].map((s) => `<li>${esc(T(s))}</li>`).join('')}</ul>`;
    h += `<p class="ps-p"><a href="https://www.abretumunicipio.org/municipio/${encodeURIComponent(m.abre)}?year=${M.abre_year}" target="_blank" rel="noopener">${esc(T("The municipal government's own finances: {name} on ABRE Tu Municipio", { name: m.name }))}</a></p>`;
    const au = m.audit || [0, 0, 0, null], ay = y.audit;
    h += `<h4>${esc(T("The municipal government's own audits"))}</h4><dl class="ps-dl">`;
    h += `<dt>${esc(T('Single audits filed for {a} to {b}', { a: ay[0], b: ay[1] }))}</dt><dd>${esc(T('{k} of {n}', { k: au[0], n: ay[1] - ay[0] + 1 }))}</dd>`;
    h += `<dt>${esc(T('Findings on federal programs in those audits'))}</dt><dd>${esc(String(au[1]))}</dd>`;
    h += `<dt>${esc(T('Findings repeated from the audit before'))}</dt><dd>${esc(String(au[2]))}</dd></dl>`;
    h += `<p class="ps-small">${esc(T('A finding is not a loss: it says a rule was not followed or a control was weak. These are the audits of the municipal government only, not of other bodies in the municipio.'))}</p>`;
    h += `<p class="ps-p"><a href="unused-funds.html#findings">${esc(T('Audit findings that repeat, in all of Puerto Rico'))}</a></p>`;
    $('#psMuni').innerHTML = h;
  }

  root.PSMuni = { start, show, answers };
})(typeof window !== 'undefined' ? window : globalThis);
