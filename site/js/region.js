/* PR Data Observatory: the map's Region tab (docs/regions.md). Loaded by app.js the first time the tab opens, with its Spanish (module "region").
   A region is a list of whole municipios (data/geo/regions.json, written by regions.py): the Eastern Region of FPR's Eastern Region Strategic Vision
   and the seven tourism regions. Its figures are built from its municipios' published values (data/municipalities.json), the way a region's own count
   would be: counts are added, and a share is the sum of its parts over the sum of its base (pooled), never an average of the municipio shares.
   A median (home value, rent, income) cannot be added up, so the tab gives the range of its municipios instead. Women's labor force participation is
   pooled from data/labor_sex_series.json (women in the labor force over women 16 and over), with its 90% margin by the Census Bureau's formulas.
   The region is outlined on the map; its municipios open the Municipality tab; the full regional profile is profile.html?region=<id>. */
const Region = (() => {
  'use strict';
  const R = { list: null, labor: null, layer: null, cur: null };
  const has = (ms, k) => ms.every(m => m[k] != null);
  const sum = (ms, k) => has(ms, k) ? ms.reduce((t, m) => t + +m[k], 0) : null;   // null when a municipio has no value: a region's sum is never short of a municipio
  const pct = (v, d = 1) => v == null || !isFinite(v) ? '—' : fmt(v, d) + '%';
  const num = (v, d = 0) => v == null || !isFinite(v) ? '—' : fmt(v, d);
  const div = (a, b, k = 1) => a == null || !b ? null : k * a / b;
  /** A share pooled over the municipios: sum of (share × base) over sum of base; null when a municipio lacks it. */
  const pooled = (ms, k, base) => { if (!has(ms, k)) return null; const b = sum(ms, base); return b ? ms.reduce((t, m) => t + m[k] * (+m[base] || 0), 0) / b : null; };
  const range = (ms, k) => { const v = ms.map(m => m[k]).filter(x => x != null); return v.length ? [Math.min(...v), Math.max(...v)] : null; };
  const kpi = (v, l, cls = '') => `<div class="kpi ${cls}"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`;

  async function load() {
    if (R.list) return;
    const [g, labor] = await Promise.all([fetchJson('data/geo/regions.json'), fetchJson('data/labor_sex_series.json').catch(() => null)]);
    R.list = g.regions; R.labor = labor;
    const sel = $('#regionSel'), lang = I18N.lang === 'es' ? 'es' : 'en';
    const opt = (r) => `<option value="${esc(r.id)}">${esc(r.name[lang] || r.name.en)} (${r.ids.length})</option>`;
    sel.innerHTML = `<option value="">${esc(T('Choose a region…'))}</option><optgroup label="${esc(T('FPR planning regions'))}">${R.list.filter(r => r.kind === 'planning').map(opt).join('')}</optgroup>` +
      `<optgroup label="${esc(T('Tourism regions'))}">${R.list.filter(r => r.kind === 'tourism').map(opt).join('')}</optgroup>`;
    sel.onchange = () => sel.value ? show(sel.value) : hide(true);
  }

  /** Women's labor force participation of the region: pooled counts of the latest window, with the margin of a proportion (ACS Handbook, ch. 8). */
  function women(ids) {
    const d = R.labor; if (!d) return null;
    const v = (k) => d.vars.find(x => x.key === k), y = String(d.years[d.years.length - 1]), at = new Map(d.geo.ids.map((g, i) => [g, i]));
    const add = (k) => { let e = 0, m = 0; for (const g of ids) { const i = at.get(g); const x = v(k).years[y][i], mm = (v(k).moe[y] || [])[i]; if (x == null) return null; e += x; m += (mm || 0) ** 2; } return [e, Math.sqrt(m)]; };
    const lf = add('women_in_lf'), pop = add('women_16plus'); if (!lf || !pop || !pop[0]) return null;
    const p = lf[0] / pop[0]; let u = lf[1] ** 2 - p * p * pop[1] ** 2; if (u < 0) u = lf[1] ** 2 + p * p * pop[1] ** 2;
    const pr = d.geo.ids.indexOf('72'), prv = pr >= 0 ? v('lfpr_women').years[y][pr] : null;
    return { rate: 100 * p, moe: 100 * Math.sqrt(u) / pop[0], women: pop[0], window: `${+y - 4}–${y}`, pr: prv };
  }

  function outline(r) {
    if (R.layer) map.removeLayer(R.layer);
    const want = new Set(r.ids), feats = S.muniFc.features.filter(f => want.has(String(f.properties.GEOID).slice(0, 5)));
    R.layer = L.geoJSON({ type: 'FeatureCollection', features: feats }, { interactive: false, style: { color: '#1d2433', weight: 2.5, fillColor: '#FFA600', fillOpacity: 0.18 } }).addTo(map);
    map.fitBounds(R.layer.getBounds().pad(0.08));
  }

  function show(id) {
    const r = R.list.find(x => x.id === id); if (!r) return;
    R.cur = id; $('#regionSel').value = id;
    const lang = I18N.lang === 'es' ? 'es' : 'en', name = r.name[lang] || r.name.en;
    const ms = r.names.map(n => S.muni[n]).filter(Boolean);
    if (ms.length !== r.ids.length) { hide(); $('#regionBody').innerHTML = `<div class="empty">${esc(T('No data for this region.'))}</div>`; return; }
    outline(r);
    const pop = sum(ms, 'population_2020'), pop10 = sum(ms, 'population_2010'), land = sum(ms, 'land_km2'), places = sum(ms, 'assets');
    const huAcs = sum(ms, 'housing_units_acs'), w = women(r.ids), rng = (k, money) => { const x = range(ms, k); return x ? (money ? `$${fmt(x[0])}–$${fmt(x[1])}` : `${pct(x[0], 0)}–${pct(x[1], 0)}`) : '—'; };
    const walk = pooled(ms, 'pop_walk_active_pct', 'population_2020');
    $('#regionBody').innerHTML = `
      <div class="muni-head"><div><h2>${esc(name)}</h2><small>${esc(T('{n} municipios · {pop} residents (Census 2020) · {area} km²', { n: ms.length, pop: num(pop), area: num(land) }))}</small>
        <div class="muni-prof"><a href="profile.html?region=${encodeURIComponent(id)}"><span class="ms-icon" aria-hidden="true">bar_chart</span>${esc(T('Regional profile: every dataset for {name}, built from its municipios', { name }))}</a></div></div></div>
      <div class="chips rg-munis">${r.names.map(n => `<button type="button" class="chip" data-muni="${esc(n)}">${esc(n)}</button>`).join('')}</div>
      <p class="note">${esc(T('Source of the region: {source}. Counts are added; shares are pooled (the sum of the parts over the sum of the base), never averaged. A median cannot be added up: the tab gives the range of its municipios.', { source: r.source[lang] || r.source.en }))}</p>
      <h3 class="sec">${icon('groups', { size: 14 })}${esc(T('People'))}</h3>
      <div class="kpis">
        ${kpi(num(pop), T('residents (Census 2020)'))}
        ${kpi(pct(div(pop, pop10, 100) == null ? null : div(pop, pop10, 100) - 100), T('change in residents, 2010 to 2020'), pop < pop10 ? 'warn' : '')}
        ${w ? kpi(`${pct(w.rate)} <small>± ${fmt(w.moe, 1)}</small>`, T("women 16 and over in the labor force ({window}); Puerto Rico {pr}", { window: w.window, pr: pct(w.pr) })) : ''}
        ${kpi(num(div(pop, land)), T('residents per km²'))}
      </div>
      ${w ? `<p class="note"><a href="women-labor.html#a=${encodeURIComponent(id)}">${esc(T('Women in the labor force in {name}: ages, children, change over time', { name }))}</a></p>` : ''}
      <h3 class="sec">${icon('place', { size: 14 })}${esc(T('Visitor economy'))}</h3>
      <div class="kpis">
        ${kpi(num(places), T('tourism places (default filters)'))}
        ${kpi(pct(div(sum(ms, 'in_sfha'), places, 100), 0), T('in flood hazard area'), div(sum(ms, 'in_sfha'), places) > 0.25 ? 'warn' : '')}
        ${kpi(num(div(places, pop, 1000), 1), T('places per 1,000 residents'))}
        ${kpi(num(div(places, land), 1), T('places per km²'))}
        ${kpi(num(sum(ms, 'in_protected')), T('inside protected areas'), 'green')}
        ${kpi(num(sum(ms, 'with_website')), T('with a website'))}
      </div>
      <h3 class="sec">${icon('commute', { size: 14 })}${esc(T('Mobility'))}</h3>
      <div class="kpis">
        ${kpi(pct(walk, 0), T('of residents within a 400 m walk of a stop with a current timetable'), walk != null && walk < 25 ? 'warn' : '')}
        ${kpi(pct(pooled(ms, 'transit_pct', 'assets'), 0), T('places within 400 m of any mapped stop'))}
        ${kpi(num(sum(ms, 'transit_stops')), T('stops & stations'))}
        ${kpi(num(sum(ms, 'airports')), T('airports'))}
      </div>
      <h3 class="sec">${icon('home_work', { size: 14 })}${esc(T('Housing · ACS {year}', { year: (S.meta.housing || {}).acs_latest || '' }))}</h3>
      <div class="kpis">
        ${kpi(num(sum(ms, 'housing_units_2020')), T('housing units (Census 2020)'))}
        ${kpi(pct(div(sum(ms, 'vacant_units'), huAcs, 100)), T('vacant units (survey)'))}
        ${kpi(pct(div(sum(ms, 'seasonal_units'), huAcs, 100)), T('seasonal / recreational units'))}
        ${kpi(rng('median_home_value', true), T('median home value: range of its municipios'))}
        ${kpi(rng('median_gross_rent', true), T('median rent: range of its municipios'))}
        ${kpi(rng('poverty_pct'), T('people in poverty: range of its municipios'))}
      </div>
      <div class="btn-row"><button class="btn" id="regionZoom">${icon('place', { size: 16 })}${esc(T('Zoom to'))}</button></div>`;
    $('#regionBody').querySelectorAll('[data-muni]').forEach(b => b.onclick = () => selectMuni(b.dataset.muni));
    $('#regionZoom').onclick = () => R.layer && map.fitBounds(R.layer.getBounds().pad(0.08));
  }

  /** Leaves the region on the panel and takes its outline off the map (another tab, or "Choose a region…"). */
  function hide(clear) { if (R.layer) { map.removeLayer(R.layer); R.layer = null; } if (clear) { R.cur = null; $('#regionBody').innerHTML = `<div class="empty">${esc(T('Choose a region to see its profile: its municipios added up, with the same measures as Place › Municipality.'))}</div>`; } }

  async function open() {
    await load();
    const want = typeof regionWanted === 'string' ? regionWanted : null;   // app.js read #rg=<id> from the link (profile.html's "Open on the map")
    show(R.cur || (want && R.list.some(r => r.id === want) ? want : 'ersv'));
  }
  return { open, show, hide, women, pooled };
})();
