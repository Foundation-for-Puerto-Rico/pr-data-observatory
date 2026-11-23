/* PR Data Observatory: the regional area profile (profile.html?region=ersv; docs/regions.md). Loaded by profile.html with profile.js, whose engine and helpers it uses.
   A region is a list of whole municipios (data/geo/regions.json, regions.py). Each dataset of the page gets three values: the region, the rest of Puerto Rico
   (the other municipios) and Puerto Rico, and the region's trend. How a region's value is made depends on the dataset, and the row says which:
     Σ  a count or a dollar total: the sum of its municipios, exact; its 90% margin is the square root of the summed squared margins (ACS Handbook, ch. 8);
     ⊕  a share whose parts are published (women's labor force participation): the sum of the parts over the sum of the base, with the margin of a proportion;
     ≈  every other rate, ratio, median or level: the average of its municipios' values weighted by their residents, an estimate (a median of medians is not the
        region's median), with no margin.
   A value is left out (—) when one of its municipios has none, so a region's sum is never short of a municipio. */
const ProfRegion = (() => {
  'use strict';
  // Rates whose numerator and base are datasets too, so a region's rate is pooled exactly. Each pair was checked on 2026-10-31: count / base × 100 equals the
  // published rate in all 79 areas to its rounding (tests/profile_region.test.js keeps that true).
  const POOL = {
    lfpr_women: ['women_in_lf', 'women_16plus'], vacancy_pct: ['vacant_units', 'housing_units'], seasonal_pct: ['seasonal_units', 'housing_units'],
    other_vacant_pct: ['other_vacant_units', 'housing_units'], census_vacancy_pct: ['census_vacant_units', 'census_housing_units'],
    laus_unemp_rate: ['laus_unemployed', 'laus_labor_force'], gov_job_share_pct: ['qcew_gov_jobs', 'qcew_jobs'],
    acs_age_under3_pct: ['acs_age_under3', 'acs_population'], acs_age3to4_pct: ['acs_age3to4', 'acs_population'], acs_age5to17_pct: ['acs_age5to17', 'acs_population'],
    acs_age18to24_pct: ['acs_age18to24', 'acs_population'], acs_age25to44_pct: ['acs_age25to44', 'acs_population'], acs_age45to64_pct: ['acs_age45to64', 'acs_population'],
    acs_age65plus_pct: ['acs_age65plus', 'acs_population'], acs_under18_pct: ['acs_under18', 'acs_population'], acs_age18to44_pct: ['acs_age18to44', 'acs_population'],
  };
  const MARK = { sum: 'Σ', pool: '⊕', avg: '≈', 'avg-land': '≈' };
  const CHANGE = { pop_change_since_2010_pct: 2010, pop_change_since_2020_pct: 2020 };   // population change: the region's population over its population in the base year (checked: equal to the published rate in all 79 areas)
  const LAND = /^(epa_naa_.+_pct|street_intersection_density|landslides_maria_km2|wetland_pct|ls_(land|cls)_.+_pct)$/;   // shares and densities of land: weighted by land area
  const RES2020 = /^ls_res_.+_pct$/;   // shares of the 2020 census residents
  const snapOf = (key) => { const A = typeof Core !== 'undefined' && Core.adapters; return A && A.SNAPSHOT_FIELDS ? A.SNAPSHOT_FIELDS.find(f => f.key === key) : null; };

  /** The value of one dataset in year y for the municipios `ids` (indexes of the engine), and how it was made. W: { pop (residents of year y), field(i, name) (a value of
      municipalities.json) }. A field of municipalities.json follows the rule its island figure uses (adapters.js SNAPSHOT_FIELDS): a ratio of two fields is pooled, an
      average uses the same weight (land or 2020 residents). */
  function agg(X, v, ids, y, W = {}) {
    const L0 = { key: v.key, norm: 'value' }, field = W.field || (() => null), sumOf = (f) => ids.reduce((t, i) => t + f(i), 0);
    if (POOL[v.key] && X.V[POOL[v.key][0]] && X.V[POOL[v.key][1]]) {
      const [nk, dk] = POOL[v.key], n = X.calc({ key: nk, norm: 'value' }, y), d = X.calc({ key: dk, norm: 'value' }, y), nm = X.moe({ key: nk, norm: 'value' }, y), dm = X.moe({ key: dk, norm: 'value' }, y);
      if (!n || !d || ids.some(i => n[i] == null || d[i] == null)) return null;
      const N = sumOf(i => n[i]), Dn = sumOf(i => d[i]); if (!Dn) return null;
      const Nm = nm ? Math.sqrt(sumOf(i => (nm[i] || 0) ** 2)) : null, Dm = dm ? Math.sqrt(sumOf(i => (dm[i] || 0) ** 2)) : null, p = N / Dn;
      let u = Nm != null && Dm != null ? Nm ** 2 - p * p * Dm ** 2 : null; if (u != null && u < 0) u = Nm ** 2 + p * p * Dm ** 2;
      return { value: 100 * p, moe: u != null ? 100 * Math.sqrt(u) / Dn : null, how: 'pool' };
    }
    if (CHANGE[v.key] && X.V.population) {
      const now = X.calc({ key: 'population', norm: 'value' }, y), base = X.calc({ key: 'population', norm: 'value' }, CHANGE[v.key]);
      if (!now || !base || ids.some(i => now[i] == null || !base[i])) return null;
      return { value: 100 * (sumOf(i => now[i]) / sumOf(i => base[i]) - 1), moe: null, how: 'pool' };
    }
    const snap = snapOf(v.key);
    if (snap && snap.island && snap.island.ratio) {
      const [nf, df] = snap.island.ratio; if (ids.some(i => field(i, nf) == null || field(i, df) == null)) return null;
      const Dn = sumOf(i => field(i, df)); return Dn ? { value: 100 * sumOf(i => field(i, nf)) / Dn, moe: null, how: 'pool' } : null;
    }
    const a = X.calc(L0, y); if (!a || ids.some(i => a[i] == null || !isFinite(a[i]))) return null;
    if (v.type === 'count' || v.type === 'total$') {
      const m = X.moe(L0, y);
      return { value: sumOf(i => a[i]), moe: m && ids.every(i => m[i] != null) ? Math.sqrt(sumOf(i => m[i] ** 2)) : null, how: 'sum' };
    }
    const byLand = (snap && snap.island && snap.island.mean === 'land_km2') || LAND.test(v.key);
    const wf = byLand ? (i) => X.geo.area[i] : (snap && snap.island && snap.island.mean) || RES2020.test(v.key) ? (i) => field(i, (snap && snap.island && snap.island.mean) || 'population_2020') : (i) => (W.pop || [])[i];
    if (ids.some(i => !(wf(i) > 0))) return null;
    const w = sumOf(wf);
    return { value: sumOf(i => a[i] * wf(i)) / w, moe: null, how: byLand ? 'avg-land' : 'avg' };
  }

  /** One row: the region, the rest of Puerto Rico and Puerto Rico in the dataset's latest year, and the region's trend. */
  function rowOf(X, v, M, rest, popOf) {
    const raw = X.values(v.key, {}); if (!raw) return null;
    const y = raw.year, L0 = { key: v.key, norm: 'value' }, r = agg(X, v, M, y, popOf(y)); if (!r) return null;
    const o = rest.length ? agg(X, v, rest, y, popOf(y)) : null, prv = raw.values[X.geo.pr];
    const trend = v.static ? null : v.ys.slice(-15).map(yy => { const a = agg(X, v, M, yy, popOf(yy)); return a ? [yy, a.value] : null; }).filter(Boolean);
    return { v, L: L0, L0, y, chip: X.chip(L0, { y, exact: true }), r, o, prv, trend };
  }

  function render(reg, ctx) {
    const { X, prIdx, P, dname, spark, lang } = ctx, name = reg.name[lang] || reg.name.en;
    const M = reg.ids.map(g => X.geo.ids.indexOf(g)).filter(i => i >= 0 && i < prIdx), inM = new Set(M), rest = X.geo.ids.slice(0, prIdx).map((_, i) => i).filter(i => !inM.has(i));
    const popAll = {}, popOf = (y) => popAll[y] !== undefined ? popAll[y] : (popAll[y] = { pop: X.V.population ? X.calc({ key: 'population', norm: 'value' }, X.resolve('population', y).y) : null, field: (i, f) => { const m = P.muni[X.geo.names[i]]; return m && m[f] != null ? m[f] : null; } });
    document.title = T('{name} · Regional profile · PR Data Observatory', { name });
    $('#pTitle').textContent = name;
    const pop20 = M.reduce((t, i) => t + ((P.muni[X.geo.names[i]] || {}).population_2020 || 0), 0), land = M.reduce((t, i) => t + ((P.muni[X.geo.names[i]] || {}).land_km2 || 0), 0);
    $('#pLede').textContent = T('Region of {n} municipios · {pop} residents (Census 2020) · {area} km² of land · {source}', { n: M.length, pop: fmt(pop20), area: fmt(land), source: reg.source[lang] || reg.source.en });
    $('#pMap').href = reg.kind === 'custom' ? 'index.html' : 'index.html#rg=' + encodeURIComponent(reg.id);   // a region of the visitor's own has no map view of its own
    const fills = X.geo.names.slice(0, prIdx).map((_, k) => inM.has(k) ? '#205D7B' : '#E6E6E6');
    P.paths = P.paths || Core.minimap.project(P.fc, X.geo.names.slice(0, prIdx), 600);
    $('#pMapFig').innerHTML = Core.minimap.svg(P.paths, fills, { label: T('Map of Puerto Rico with the municipios of {name} marked', { name }), strong: inM, titles: X.geo.names.slice(0, prIdx) })
      + `<div class="mm-legend"><span><i style="background:#205D7B"></i>${esc(name)}</span><span><i style="background:#E6E6E6"></i>${esc(T('Rest of Puerto Rico'))}</span></div>`;
    $('#pPeers').innerHTML = `<h2>${esc(T('Its municipios'))}</h2><ol>${M.map(i => X.geo.names[i]).sort((a, b) => a.localeCompare(b, 'es')).map(n => `<li><a href="profile.html?area=${X.geo.ids[X.geo.names.indexOf(n)]}">${esc(n)}</a></li>`).join('')}</ol>`;
    const rows = X.list().map(v => rowOf(X, v, M, rest, popOf)).filter(Boolean);
    P.rows = rows;
    const byDom = new Map(); rows.forEach(r => { r.dom = P.parent.get(P.domainOf.get(X.dictId(r.v.key))) || 'other'; if (!byDom.has(r.dom)) byDom.set(r.dom, []); byDom.get(r.dom).push(r); });
    const all = [...P.domains.map(d => d.id).filter(id => byDom.has(id)), ...[...byDom.keys()].filter(k => !P.domains.some(d => d.id === k))], order = P.complete ? all : all.slice(0, 1);
    const val = (x, L) => x ? `${esc(X.fmt(L, x.value))}${x.moe != null ? ` <small class="moe">± ${esc(X.fmt(L, x.moe))}</small>` : ''}` : '—';
    const how = { sum: T('Sum of its municipios (exact)'), pool: T('Pooled: the sum of the parts over the sum of the base (exact)'), avg: T('Average of its municipios weighted by residents (estimate)'), 'avg-land': T('Average of its municipios weighted by land area (estimate)') };
    const cell = (r) => `<tr><th scope="row">${esc(T(r.v.label))}<small>${esc(r.chip)}</small></th><td class="num"><span class="rg-mark" title="${esc(how[r.r.how])}">${MARK[r.r.how]}</span> ${val(r.r, r.L0)}</td><td class="num">${val(r.o, r.L0)}</td><td class="num">${r.prv == null ? '—' : esc(X.fmt(r.L0, r.prv))}</td><td>${spark(r.trend, r.L0)}</td></tr>`;
    $('#pSections').innerHTML = order.map(id => {
      const rs = byDom.get(id), groups = new Map(); rs.forEach(r => { const g = r.v.group; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(r); });
      return `<section class="d-block pf-sec" id="dom-${esc(id)}" aria-labelledby="h-${esc(id)}"><h2 id="h-${esc(id)}">${esc(dname(id))} <small>${esc(Tn(rs.length, '{n} dataset', '{n} datasets'))}</small></h2>
        <div class="tbl-wrap" tabindex="0" role="region" aria-label="${esc(T('{field}: datasets for {name}, scrollable', { field: dname(id), name }))}"><table class="pt pf-tbl"><thead><tr><th scope="col">${esc(T('Dataset'))}</th><th scope="col" class="num">${esc(name)}</th><th scope="col" class="num">${esc(T('Rest of Puerto Rico'))}</th><th scope="col" class="num">${esc(T('Puerto Rico'))}</th><th scope="col">${esc(T('Trend'))}</th></tr></thead>
        ${[...groups].map(([g, gr]) => `<tbody><tr class="pf-g"><th colspan="5" scope="colgroup">${esc(T(g))}</th></tr>${gr.map(cell).join('')}</tbody>`).join('')}</table></div></section>`;
    }).join('') + (P.complete ? '' : `<p class="note pf-wait" role="status">${esc(T('Loading the other fields…'))}</p>`);
    $('#profNav').innerHTML = `<h2 class="side-h">${esc(T('On this page'))}</h2>` + order.map(id => `<a href="#dom-${esc(id)}">${esc(dname(id))} <small>${byDom.get(id).length}</small></a>`).join('');
    const left = X.list().length - rows.length;
    $('#pNote').textContent = [P.notice || '', T('Each value of the region is built from its municipios: Σ a count or total, added up (exact, with its margin of error); ⊕ a share whose parts are published, pooled (exact); ≈ any other rate, median or level, the average of its municipios weighted by residents, or by land area for a share of land (an estimate: the average of municipio medians is not the region\'s median). The rest of Puerto Rico is built the same way from the other municipios.'),
      P.complete && left ? Tn(left, '{n} dataset has no value for one or more of these municipios and is left out.', '{n} datasets have no value for one or more of these municipios and are left out.') : ''].filter(Boolean).join(' ');
  }

  function csv(reg, ctx) {
    const { X, P, dname, lang } = ctx, name = reg.name[lang] || reg.name.en;
    const q = v => { if (v == null) return ''; let s = String(v); if (/^[=+\-@\t\r]/.test(s) && typeof v !== 'number') s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const head = [T('Field'), T('Group'), T('Dataset'), T('Year'), name, T('Margin of error'), T('Method'), T('Rest of Puerto Rico'), T('Puerto Rico')];
    const how = { sum: T('Sum of its municipios (exact)'), pool: T('Pooled: the sum of the parts over the sum of the base (exact)'), avg: T('Average of its municipios weighted by residents (estimate)'), 'avg-land': T('Average of its municipios weighted by land area (estimate)') };
    const rows = P.rows.map(r => [dname(r.dom), T(r.v.group), T(r.v.label), r.chip, r.r.value, r.r.moe, how[r.r.how], r.o ? r.o.value : null, r.prv]);
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + [head, ...rows].map(r => r.map(q).join(',')).join('\n')], { type: 'text/csv;charset=utf-8' }));
    a.download = `pr_region_profile_${reg.id}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  if (typeof module === 'object' && module.exports) module.exports = { agg, POOL, CHANGE, LAND };
  return { agg, rowOf, render, csv, POOL };
})();
