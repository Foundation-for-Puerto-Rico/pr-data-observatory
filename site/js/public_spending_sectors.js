/* PR Data Observatory: the Public spending page's sector view (section 6; Public spending PR 8, HANDOFF decision 87). public_spending.js loads this
   file after the page is ready and calls PSSectors.draw(box, ctx) with the files it already has and its helpers; for Education it also asks for
   education_series.json (public school students), once.
   For the function chosen it sets side by side, never added together: the Commonwealth budget (spending_state.json), federal obligations
   (spending_federal.json), the capital projects of the four-year program (spending_pica.json, by the function of each agency) and dollars per
   resident (one population basis: the Census Bureau's estimate for July 1 2025, the one the capital projects map uses). For Education it adds the
   Department of Education's spending per public school student and an estimate by municipio (decision 73 (5)): the Department's spending split by
   each municipio's share of the students, labeled as an estimate and never added into any total. */
(function (root) {
  'use strict';
  let EDU = null, eduAsked = false, LAST = null;   // LAST: the newest call, redrawn when the student counts arrive
  const EDU_AGENCY = '081';   // Departamento de Educación in OGP's codes

  function draw(box, c) {
    LAST = c;
    const { D, F, PICA, T, big, usd, pct, esc, fn } = c, f = c.sector;
    if (!D) return;
    const col = (y, st) => D.columns.findIndex((x) => x.year === y && x.stage === st);
    const appr = D.columns.filter((x) => x.stage === 'approved').sort((a, b) => b.year - a.year)[0];
    const spentCols = D.columns.filter((x) => x.stage === 'actual').map((x) => x.year).filter((y) => col(y, 'approved') >= 0).sort();
    const ys = spentCols[spentCols.length - 1];
    const sum = (ci, filt) => D.rows.reduce((s, r) => s + (filt(r) ? r[4][ci] || 0 : 0), 0);
    const isF = (r) => D.functions[r[3]] === f, ciA = D.columns.indexOf(appr);
    const aF = sum(ciA, isF), aAll = sum(ciA, () => true);
    const rows = [];
    rows.push([T('Commonwealth budget, FY{year} approved', { year: appr.year }), `${big(aF)} · ${T('{share} of the budget', { share: pct(100 * aF / aAll, 1) })}`]);
    if (ys) {
      const s = sum(col(ys, 'actual'), isF), a = sum(col(ys, 'approved'), isF);
      rows.push([T('Spent in FY{year}', { year: ys }), a ? T('{spent} of {approved} approved ({share})', { spent: big(s), approved: big(a), share: pct(100 * s / a, 0) }) : big(s)]);
    }
    if (F) {
      const yi = F.years.length - 1, v = F.rows.reduce((s, r) => s + (F.functions[r[3]] === f ? r[5][yi] : 0), 0);
      rows.push([T('Federal obligations, federal FY{year}', { year: F.years[yi] }), big(v)]);
    }
    let pica = 0;
    if (PICA) {
      const fnOf = new Map(PICA.agencies.map(([a, g]) => [a, g]));
      PICA.by_agency.forEach(([a, m, u]) => { if (fnOf.get(a) === f) pica += m.reduce((s, x) => s + x, 0) + u; });
      rows.push([T('Capital projects, fiscal years {a} to {b}', { a: PICA.years[0], b: PICA.years[PICA.years.length - 1] }), big(pica)]);
      const pop = PICA.population.reduce((s, x) => s + (x || 0), 0);
      if (pop) rows.push([T('Approved budget per resident, FY{year}', { year: appr.year }), usd(aF / pop)]);
    }
    // the function's largest agencies in the approved budget
    const byA = new Map();
    D.rows.forEach((r) => { if (isF(r) && r[4][ciA]) byA.set(r[0], (byA.get(r[0]) || 0) + r[4][ciA]); });
    const top = [...byA].sort((a, b) => b[1] - a[1]).slice(0, 6), mx = top.length ? top[0][1] : 1;
    let html = `<h3>${esc(T(c.FUNCTION[f]))}</h3><dl class="ps-dl">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
    if (top.length) html += `<h4>${esc(T('Largest agencies, FY{year} approved', { year: appr.year }))}</h4><ul class="ps-bars">${top.map(([a, v]) => `<li><span class="l">${esc(D.agencies[a])}</span><span class="b"><i style="width:${(100 * v / mx).toFixed(1)}%"></i></span><span class="v">${esc(big(v))}</span></li>`).join('')}</ul>`;
    if (f === 'education') html += education(c, ys, col);
    html += `<p class="ps-small">${esc(T("The figures come from different sources and stages and are never added together: the budget is the Commonwealth's, federal obligations include money that also passes through the budget, and the capital program is a plan."))}</p>`;
    box.innerHTML = html;
    if (f === 'education' && !EDU && !eduAsked) {
      eduAsked = true;
      c.fetchJson('data/education_series.json').then((d) => { EDU = d; if (LAST.sector === 'education') draw(box, LAST); }, () => {});
    }
  }

  function education(c, ys, col) {
    const { D, T, big, usd, esc, fmt } = c;
    if (!EDU || !ys) return `<p class="ps-small">${esc(T('Loading public school students…'))}</p>`;
    const v = EDU.vars.find((x) => x.key === 'sch_enroll'), sy = String(ys - 1);   // FY2025 runs July 2024 to June 2025: the 2024-25 school year
    if (!v || !v.years[sy]) return '';
    const ids = EDU.geo.ids, arr = v.years[sy], pr = arr[ids.indexOf('72')];
    const dept = D.rows.reduce((s, r) => s + (r[0] === EDU_AGENCY ? r[4][col(ys, 'actual')] || 0 : 0), 0);
    if (!pr || !dept) return '';
    const munis = ids.map((id, i) => [id, EDU.geo.names[i], arr[i]]).filter(([id, , n]) => id !== '72' && n != null).sort((a, b) => b[2] - a[2]);
    return `<h4>${esc(T('Per public school student'))}</h4><dl class="ps-dl"><dt>${esc(T('Department of Education, spent in FY{year}', { year: ys }))}</dt><dd>${esc(big(dept))}</dd>` +
      `<dt>${esc(T('Students in public schools, {a}-{b} school year', { a: ys - 1, b: String(ys).slice(2) }))}</dt><dd>${esc(fmt(pr))}</dd>` +
      `<dt>${esc(T('Spent per student'))}</dt><dd>${esc(usd(dept / pr))}</dd></dl>` +
      `<details class="ps-more"><summary>${esc(T('An estimate by municipio'))}</summary><p class="ps-small">${esc(T("An estimate, not spending reported by municipio: the Department of Education's FY{year} spending split by each municipio's share of the public school students. It is never added into any total.", { year: ys }))}</p>` +
      `<div class="ps-tablebox"><table class="ps-table"><thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col">${esc(T('Students'))}</th><th scope="col">${esc(T('Estimated dollars'))}</th></tr></thead><tbody>${
        munis.map(([, name, n]) => `<tr><th scope="row">${esc(name)}</th><td>${esc(fmt(n))}</td><td>${esc(usd(dept * n / pr))}</td></tr>`).join('')}</tbody></table></div></details>`;
  }

  root.PSSectors = { draw };
})(typeof window !== 'undefined' ? window : globalThis);
