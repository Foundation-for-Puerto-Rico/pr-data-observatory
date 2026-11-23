/* Public spending, section 8: FEMA Public Assistance by stage and age (decision 109, step 2; docs/spending.md). Loaded after ready by public_spending.js. */
(function (root) {
  'use strict';
  const RAMP = ['#FCE3C7', '#F7BF85', '#EE9147', '#C9641E', '#8A3F0E'], NONE = '#eef0f3', SC = { closed: '#2E7D4F', open: '#E39B2D', pending: '#9AA3B2' };
  const NAMES = { 4339: 'Hurricane María', 4336: 'Hurricane Irma', 4671: 'Hurricane Fiona', 4473: 'Earthquakes of 2020', 4493: 'COVID-19' };
  const CAT = { A: 'Debris removal', B: 'Emergency protective measures', C: 'Roads and bridges', D: 'Water control facilities', E: 'Public buildings and contents', F: 'Public utilities', G: 'Parks, recreation and other', Z: 'Management costs' };
  let C, F, st = { m: 'old' };
  const sum = (a) => a.reduce((s, v) => s + v, 0);

  function start(ctx) {
    C = ctx;
    C.fetchJson('data/spending_fema_pa.json').then((d) => { F = d; setup(); }, (e) => {
      C.$('#psFemaStage').innerHTML = `<p class="ps-p">${C.esc(C.T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }

  /** For one municipio (or the island when i < 0): dollars by stage, share closed, median age and dollars open over five years. Exported for the tests. */
  function muni(d, i) {
    const u = d.by_muni.usd[i], t = sum(u);
    return { usd: u, total: t, closed: t ? u[0] / t : null, age: d.by_muni.median_age[i], over5: d.by_muni.over5_usd[i], perRes: d.population[i] ? d.by_muni.over5_usd[i] / d.population[i] : 0 };
  }

  function setup() {
    const { $, T, esc, big, pct } = C, tot = sum(F.island.usd), sw = sum(F.statewide.usd);
    $('#psFemaTiles').innerHTML = [['all', tot, sum(F.island.count)]].concat(F.stages.map((s, k) => [s, F.island.usd[k], F.island.count[k]])).map(([s, v, n]) =>
      `<div class="ps-tile"><span>${esc(s === 'all' ? T('Obligated, all projects') : T({ closed: 'Closed out', open: 'Open', pending: 'Pending a review' }[s]))}</span><b>${esc(big(v))}</b><small>${esc(T('{n} projects', { n: n.toLocaleString(C.loc()) }))}${s === 'all' ? '' : ' · ' + esc(pct(100 * v / tot, 0))}</small></div>`).join('');
    $('#psFemaStage').innerHTML = `<div class="ps-stack" role="img" aria-label="${esc(T('Bar: obligated by stage. The tiles above have the figures.'))}">${F.stages.map((s, k) => `<i style="width:${(100 * F.island.usd[k] / tot).toFixed(1)}%;background:${SC[s]}"></i>`).join('')}</div>` +
      `<p class="ps-small">${esc(T('{sw} of the {tot} ({share}) is recorded as Statewide: those projects name no municipio and are not on the map.', { sw: big(sw), tot: big(tot), share: pct(100 * sw / tot, 0) }))}</p>`;
    $('#psFemaKey').innerHTML = F.stages.map((s) => `<span><i class="sw" style="background:${SC[s]}" aria-hidden="true"></i>${esc(T({ closed: 'Closed out', open: 'Open', pending: 'Pending a review' }[s]))}</span>`).join('');
    const mx = Math.max(...F.age_usd);
    $('#psFemaAge').innerHTML = `<ul class="ps-bars">${F.age_bins.map((b, k) => `<li><span class="l">${esc(T({ under_2: 'Under 2 years', '2_to_5': '2 to 5 years', '5_to_8': '5 to 8 years', '8_plus': '8 years or more' }[b]))}</span><span class="b"><i style="width:${(100 * F.age_usd[k] / mx).toFixed(1)}%;background:#E39B2D"></i></span><span class="v">${esc(big(F.age_usd[k]))}</span></li>`).join('')}</ul>` +
      `<p class="ps-small">${esc(T('Median age of the money still open, weighted by dollars: {age} years since its first obligation.', { age: F.median_age.toLocaleString(C.loc()) }))}</p>`;
    $('#psFemaMeasure').addEventListener('change', (e) => { st.m = e.target.value; draw(); });
    const dn = (x) => NAMES[x[0]] ? T(NAMES[x[0]]) : T('{type}, {year}', { type: T(x[1]), year: x[2] });
    $('#psFemaTable').innerHTML = `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Disaster'))}</th><th scope="col">${esc(T('Obligated'))}</th><th scope="col">${esc(T('Closed out'))}</th><th scope="col">${esc(T('Median age of what is open'))}</th></tr></thead><tbody>${
      F.disasters.slice(0, 8).map((x) => `<tr><th scope="row">${esc(dn(x))} (${x[0]})</th><td>${esc(big(sum(x[4])))}</td><td>${esc(pct(100 * x[4][0] / (sum(x[4]) || 1), 0))}</td><td>${esc(x[5] == null ? '—' : T('{age} years', { age: x[5].toLocaleString(C.loc()) }))}</td></tr>`).join('')}</tbody></table>` +
      `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Damage category'))}</th><th scope="col">${esc(T('Obligated'))}</th><th scope="col">${esc(T('Closed out'))}</th></tr></thead><tbody>${
      F.categories.map(([c, u]) => `<tr><th scope="row">${esc(c)} · ${esc(T(CAT[c] || c))}</th><td>${esc(big(sum(u)))}</td><td>${esc(pct(100 * u[0] / (sum(u) || 1), 0))}</td></tr>`).join('')}</tbody></table>`;
    C.age('spending_fema_pa.json', F);
    draw();
  }

  function draw() {
    const { $, T, esc, big, usd, pct } = C, P = C.proj(), ids = F.geo.ids, at = new Map(ids.map((g, i) => [String(g), i]));
    const rows = ids.map((_, i) => muni(F, i));
    const val = (r) => (st.m === 'old' ? r.perRes : st.m === 'closed' ? (r.closed == null ? null : 100 * r.closed) : r.age);
    const fmt = (v) => (v == null ? '—' : st.m === 'old' ? usd(v) : st.m === 'closed' ? pct(v, 0) : T('{age} years', { age: v.toLocaleString(C.loc()) }));
    const vals = rows.map(val), pos = vals.filter((v) => v != null && (st.m !== 'old' || v > 0)).sort((a, b) => a - b);
    const cut = pos.length ? [1, 2, 3, 4].map((k) => pos[Math.min(pos.length - 1, Math.floor(k * pos.length / 5))]) : [];
    const cls = (v) => (v == null || (st.m === 'old' && !v) ? -1 : cut.filter((c) => v >= c).length);
    let svg = `<svg viewBox="0 0 ${P.W} ${P.H}" width="100%" role="img" aria-label="${esc(T('Map: FEMA Public Assistance by municipio, the projects that name one. The table below has the figures.'))}">`;
    for (const p of P.paths) {
      const i = at.get(String(p.id)); if (i == null) continue;
      const c = cls(vals[i]);
      svg += `<path class="mu" d="${p.d}" fill="${c < 0 ? NONE : RAMP[c]}"><title>${esc(`${F.geo.names[i]}: ${fmt(vals[i])}`)}</title></path>`;
    }
    $('#psFemaMap').innerHTML = svg + '</svg>';
    const b = [pos[0]].concat(cut);
    $('#psFemaKey2').innerHTML = `<span><i style="background:${NONE}" aria-hidden="true"></i>${esc(T('none'))}</span>` + RAMP.map((c, k) => `<span><i style="background:${c}" aria-hidden="true"></i>${esc(k < 4 ? T('{a} to {b}', { a: fmt(b[k]), b: fmt(cut[k]) }) : T('{a} or more', { a: fmt(cut[3]) }))}</span>`).join('');
    const top = ids.map((_, i) => i).filter((i) => cls(vals[i]) >= 0).sort((x, y) => (st.m === 'closed' ? vals[x] - vals[y] : vals[y] - vals[x])).slice(0, 10);
    $('#psFemaSide').innerHTML = `<h4>${esc(T({ old: 'Most dollars open more than five years, per resident', closed: 'Lowest share closed out', age: 'Oldest money still open' }[st.m]))}</h4><ol class="ps-rank">${
      top.map((i) => `<li><span>${esc(F.geo.names[i])}</span><b>${esc(fmt(vals[i]))}</b></li>`).join('')}</ol>`;
    $('#psFemaMuni').innerHTML = `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col">${esc(T('Obligated'))}</th><th scope="col">${esc(T('Closed out'))}</th><th scope="col">${esc(T('Median age of what is open'))}</th><th scope="col">${esc(T('Open more than 5 years'))}</th></tr></thead><tbody>${
      ids.map((_, i) => i).sort((x, y) => F.geo.names[x].localeCompare(F.geo.names[y], C.loc())).map((i) => { const r = rows[i]; return `<tr><th scope="row">${esc(F.geo.names[i])}</th><td>${esc(big(r.total))}</td><td>${esc(r.closed == null ? '—' : pct(100 * r.closed, 0))}</td><td>${esc(r.age == null ? '—' : T('{age} years', { age: r.age.toLocaleString(C.loc()) }))}</td><td>${esc(big(r.over5))}</td></tr>`; }).join('')}</tbody></table>`;
  }

  root.PSFema = { start, muni };
})(typeof window !== 'undefined' ? window : globalThis);
