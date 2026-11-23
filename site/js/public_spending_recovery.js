/* PR Data Observatory: the Public spending page's disaster recovery section (section 7; Public spending PR 9, HANDOFF decision 89). public_spending.js
   loads this file after the page is ready and calls PSRecovery.start(ctx) with its helpers and the municipio outlines (ctx.proj()); the file
   fetches data/spending_cdbgdr.json (cdbg_dr.py) itself. It maps the subawards of the Puerto Rico Department of Housing's CDBG-DR and CDBG-MIT
   grants by municipio, summed over the fiscal years chosen, per resident or in total, with the subawards that name no municipio and the prime
   grants beside the map, so the share that is placed is plain. Strings come translated from the caller (ctx.T). */
(function (root) {
  'use strict';
  const RAMP = ['#E6D9F0', '#C9B2E0', '#A585C9', '#7A5BA6', '#523A78'], NONE = '#eef0f3';
  let C, R, st = { m: 'per', a: 0 };

  function start(ctx) {
    C = ctx;
    C.fetchJson('data/spending_cdbgdr.json').then((d) => { R = d; setup(); }, (e) => {
      C.$('#psRecMap').innerHTML = `<p class="ps-p">${C.esc(C.T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }

  function setup() {
    const { $, T, esc } = C, ys = R.years;
    $('#psRecFrom').innerHTML = ys.map((y, i) => `<option value="${i}">${esc(T('Federal FY{year}', { year: y }))}</option>`).join('');
    $('#psRecFrom').value = '0';
    $('#psRecFrom').addEventListener('change', (e) => { st.a = +e.target.value; draw(); });
    $('#psRecMeasure').addEventListener('change', (e) => { st.m = e.target.value; draw(); });
    C.age('spending_cdbgdr.json', R);
    grants();
    draw();
  }

  function sum(arr) { return arr.slice(st.a).reduce((s, v) => s + v, 0); }

  function draw() {
    const { $, T, esc, big, usd, pct } = C, P = C.proj(), ids = R.geo.ids, at = new Map(ids.map((g, i) => [g, i]));
    const raw = ids.map((_, i) => R.by_muni.slice(st.a).reduce((s, yr) => s + yr[i], 0));
    const vals = raw.map((v, i) => (st.m === 'per' ? (R.population[i] ? v / R.population[i] : 0) : v));
    const pos = vals.filter((v) => v > 0).sort((a, b) => a - b), cut = pos.length ? [1, 2, 3, 4].map((k) => pos[Math.min(pos.length - 1, Math.floor(k * pos.length / 5))]) : [];
    const cls = (v) => (v > 0 ? cut.filter((c) => v >= c).length : -1), money = (v) => (st.m === 'per' ? usd(v) : big(v));
    const y0 = R.years[st.a], y1 = R.years[R.years.length - 1];
    const said = (i) => `${R.geo.names[i]}: ${vals[i] > 0 ? money(vals[i]) : T('no subawards')}`;
    let svg = `<svg viewBox="0 0 ${P.W} ${P.H}" width="100%" role="img" aria-label="${esc(T('Map: disaster recovery subawards by municipio, federal fiscal years {a} to {b}. The table below has the figures.', { a: y0, b: y1 }))}">`;
    for (const p of P.paths) {
      const i = at.get(p.id); if (i == null) continue;
      const c = cls(vals[i]);
      svg += `<path class="mu" d="${p.d}" fill="${c < 0 ? NONE : RAMP[c]}"><title>${esc(said(i))}</title></path>`;
    }
    $('#psRecMap').innerHTML = svg + '</svg>';
    const b = [0].concat(cut);
    $('#psRecKey').innerHTML = `<span><i style="background:${NONE}" aria-hidden="true"></i>${esc(T('no subawards'))}</span>` + RAMP.map((c, k) => `<span><i style="background:${c}" aria-hidden="true"></i>${esc(k === 0 ? T('under {b}', { b: money(cut[0]) }) : k < 4 ? T('{a} to {b}', { a: money(b[k]), b: money(cut[k]) }) : T('{a} or more', { a: money(cut[3]) }))}</span>`).join('');
    const placed = raw.reduce((s, v) => s + v, 0), un = sum(R.unplaced), subs = sum(R.subawards), prime = sum(R.prime);
    $('#psRecSide').innerHTML = `<h3>${esc(T('Federal fiscal years {a} to {b}', { a: y0, b: y1 }))}</h3><dl class="ps-dl">` +
      `<dt>${esc(T('Prime grants obligated to the Department of Housing'))}</dt><dd>${esc(big(prime))}</dd>` +
      `<dt>${esc(T('Subawards reported'))}</dt><dd>${esc(big(subs))}</dd>` +
      `<dt>${esc(T('On the map'))}</dt><dd>${esc(big(placed))}</dd>` +
      `<dt>${esc(T('Not placed in a municipio'))}</dt><dd>${esc(big(un))}</dd></dl>` +
      `<p class="ps-small">${esc(T('The subawards are {share} of the prime grants in these years; the rest is spent through the Department’s own programs and contracts and is not placed by USAspending.', { share: prime ? pct(100 * subs / prime, 0) : '—' }))}</p>` +
      `<h4>${esc(st.m === 'per' ? T('Disaster recovery subawards per resident: the ten highest municipios') : T('Disaster recovery subawards, in dollars: the ten highest municipios'))}</h4><ul class="ps-bars">${
        ids.map((_, i) => i).filter((i) => vals[i] > 0).sort((x, y) => vals[y] - vals[x]).slice(0, 10).map((i, k, arr) => `<li><span class="l">${esc(R.geo.names[i])}</span><span class="b"><i style="width:${(100 * vals[i] / vals[arr[0]]).toFixed(1)}%"></i></span><span class="v">${esc(money(vals[i]))}</span></li>`).join('')}</ul>`;
    $('#psRecTable').innerHTML = `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col">${esc(T('Dollars'))}</th><th scope="col">${esc(T('Per resident'))}</th></tr></thead><tbody>${
      ids.map((_, i) => i).sort((x, y) => R.geo.names[x].localeCompare(R.geo.names[y], C.loc())).map((i) => `<tr><th scope="row">${esc(R.geo.names[i])}</th><td>${esc(usd(raw[i]))}</td><td>${esc(R.population[i] ? usd(raw[i] / R.population[i]) : '—')}</td></tr>`).join('')}</tbody></table>`;
  }

  const KIND = { DM: 'Recovery, hurricanes Irma and María', DE: 'Electrical grid', DN: 'Recovery, Hurricane Fiona', DZ: 'Recovery, 2020 earthquakes', DF: 'Recovery, other disasters', DI: 'Recovery, 2008 floods' };
  /** A grant number's purpose: DP-0002 is the mitigation grant (CDBG-MIT); the other DP grants are 2017 hurricane recovery. Exported for the tests. */
  function kind(id) { const c = id.split('-')[2]; return c === 'DP' ? (id.endsWith('-0002') ? 'Mitigation' : KIND.DM) : KIND[c] || KIND.DF; }
  // ── The prime grants, obligated and paid out (decision 109, step 3) ──
  const OLD = /^B-(0\d|1[0-7])-/;   // the grant's own year: 2008 floods (B-08-DI) and the first Hurricane María grant (B-17-DM) were made before fiscal year 2020
  function grants() {
    const { $, T, esc, big, pct } = C, G = R.grants || [], mx = Math.max(1, ...G.map((g) => g[1])), O = G.reduce((s, g) => s + g[1], 0), P = G.reduce((s, g) => s + g[2], 0);
    $('#psRecGrants').innerHTML = `<p class="ps-head">${esc(T('All grants: {paid} paid out of {obligated} obligated ({share}), read on {date}', { paid: big(P), obligated: big(O), share: pct(100 * P / O, 0), date: R.grants_read }))}</p><ul class="ps-out" aria-label="${esc(T('Bars: each prime grant, obligated and paid out. The figures are beside each bar.'))}">${
      G.filter((g) => g[1] > 0).map(([id, o, p]) => `<li><span class="l">${esc(T(kind(id)))}<br><small>${esc(id)}</small></span><span class="b" title="${esc(T('{paid} of {obligated}', { paid: big(p), obligated: big(o) }))}"><i class="o" style="width:${(100 * o / mx).toFixed(1)}%"></i><i class="p" style="width:${(100 * p / mx).toFixed(1)}%"></i></span><span class="v">${esc(pct(100 * p / o, 0))}${OLD.test(id) ? ' *' : ''}</span></li>`).join('')}</ul><p class="ps-small">${esc(T('* Grants made before fiscal year 2020: USAspending has payments only from 2020, so the share paid out is understated. Do not compare these grants with the later ones.'))}</p>`;
  }

  root.PSRecovery = { start, kind };
})(typeof window !== 'undefined' ? window : globalThis);
