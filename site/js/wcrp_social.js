/* PR Data Observatory · Knowledge Area · WCRP (wcrp.html), section 1: the Social Capital map, the page's first map (2026-10-19): it loads with the page, its
   Spanish is in the page's bundle (scopes facilities and wcrp_social), and wcrp.js starts it (start: the map and the files) before the page's own files are in
   (init: the themes, the summary and the points). It reuses the observatory's own files, nothing copied: the facility points of the 2D map (public_housing, fire_stations,
   police_stations, libraries .geojson, built by facilities.py; historic_places, town_halls .geojson, built by community_assets.py), comunidades.geojson,
   protected.geojson and the WCRP points the page already holds; each file loads the first time its theme is switched on. The municipio summary reads the
   count files of the Economy tab (facility_series, community_series, infrastructure_series, care_series, health_series, exposure_municipio), the city
   halls of town_halls.geojson and wcrp_social.json (wcrp_social.py: the residents each rate divides by, the Comunidades Especiales of each municipio and
   the community-asset flags of the WCRP list); the barrio outlines (barrios.geojson) load only to zoom to a municipio. Sensitive places are counted, not drawn: health and treatment facilities (SAMHSA), community water systems
   outside PRASA (EPA ECHO) and historic places that are private homes (community_assets.py leaves them out of the points file). docs/wcrp.md. */
const Social = (() => {
  const TK = (t) => t;   // translated where it is shown, with T()
  const PTS = {   // the 2D map's facility layers (facilities.js): same files, colours and pop-up
    libraries: { file: 'libraries.geojson', color: '#0F7B6C', label: TK('Public libraries'), source: TK('USAC, E-Rate Supplemental Entity Information (updated {date})') },
    fire: { file: 'fire_stations.geojson', color: '#C62828', label: TK('Fire and EMS stations'), source: TK('USGS, National Structures Dataset (loaded up to {date})') },
    police: { file: 'police_stations.geojson', color: '#1F3A93', label: TK('Police stations'), source: TK('© OpenStreetMap contributors, ODbL (data of {date})') },
    pubhousing: { file: 'public_housing.geojson', color: '#6A3D9A', label: TK('Public housing developments'), source: TK('HUD, Public Housing Developments (date of coverage {date})') },
    historic: { file: 'historic_places.geojson', color: '#8C4A12', label: TK('Historic places'), source: TK('NPS, National Register of Historic Places (edited up to {date})') },
    townhalls: { file: 'town_halls.geojson', color: '#455A64', label: TK('City halls'), source: TK('© OpenStreetMap contributors, ODbL (data of {date})') },
  };
  const TYPES = [TK('Public housing development'), TK('Scattered-site public housing'), TK('Fire or EMS station'), TK('Municipal police'), TK('State police (Puerto Rico Police Bureau)'),
    TK('Police (agency not stated)'), TK('Main library'), TK('Library or branch'), TK('Library kiosk'), TK('Bookmobile'),
    TK('Historic building'), TK('Historic structure'), TK('Historic district'), TK('Historic site'), TK('Historic object'), TK('Listed place'), TK('City hall'), TK('City hall annex')];   // the types the files hold, for the language tool
  const THEMES = [
    { id: 'health', label: TK('Health'), layers: [] },
    { id: 'education', label: TK('Education and culture'), layers: ['libraries', 'historic'], on: true },
    { id: 'security', label: TK('Security'), layers: ['fire', 'police'], on: true },
    { id: 'community', label: TK('Community services'), layers: ['pubhousing', 'townhalls'], on: true },
    { id: 'ce', label: 'Comunidades Especiales', layers: ['ce'] },   // the program's name, the same in Spanish
    { id: 'wcrp', label: TK('WCRP communities'), layers: ['wcrp'], on: true },
    { id: 'environment', label: TK('Environment'), layers: ['protected'] },
  ];
  const FLAG = { centro_comunal: TK('Community center'), biblioteca: TK('Library'), biblioteca_electronica: TK('Electronic library'), parque_pasivo: TK('Passive park'), cancha: TK('Sports court'),
    asoc_residentes: TK("Residents' association"), asoc_recreativa: TK('Recreation association'), asoc_prevencion_crimen: TK('Crime-prevention association'), pdi: 'PDI' };   // the list's own column name; it does not define it
  const CE_COLOR = '#FF4D38', PROT_COLOR = '#47560F';
  const S = { map: null, docs: {}, asked: {}, layers: {}, on: new Set(THEMES.filter(t => t.on).map(t => t.id)), d: null, renderer: null };
  const RAMP = Core.palettes.RAMPS.red;

  // ── Map ──────────────────────────────────────────────────────────────────
  const factPop = (k, p, d) => `<div class="wm-pop"><h4>${esc(p.name || T('No name recorded'))}</h4><div class="meta">${esc(T(p.type))} · ${esc(p.municipio)}</div>${p.listed ? `<div class="meta">${esc(T('Listed: {date}', { date: p.listed }))}</div>` : ''}<div class="src">${esc(T(PTS[k].source, { date: d.vintage || '—' }))}</div></div>`;
  function cePop(p) {
    const yn = v => v == null ? T('not reported') : v ? T('yes') : T('no');
    const code = S.d.assets.poly[`${p.municipio}|${p.nombre}|${p.barrio || ''}`], F = S.d.assets.flags;
    let assets = `<div class="src">${esc(T('Not found in the WCRP Social Capital Mapping list.'))}</div>`;
    if (code) {
      const by = (c) => F.filter((f, i) => code[i] === c).map(f => esc(T(FLAG[f]))).join(', ');
      const has = by('1'), no = by('0'), nd = by('-');
      assets = `<div class="sc-assets"><b>${esc(T('Community assets in the WCRP Social Capital Mapping list (date not stated, about 2019–2021)'))}</b>`
        + (has ? `<div><span class="sc-yes">${esc(T('Has'))}</span> ${has}</div>` : '') + (no ? `<div><span class="sc-no">${esc(T('Does not have'))}</span> ${no}</div>` : '')
        + (nd ? `<div><span class="sc-nd">${esc(T('Not recorded'))}</span> ${nd}</div>` : '') + '</div>';
    }
    return `<div class="wm-pop"><h4>${esc(p.nombre)}</h4><div class="meta">Comunidad Especial · ${esc(p.municipio)}${p.barrio ? ` · Barrio ${esc(p.barrio)}` : ''}</div>`
      + `<div class="meta">${Th('<b>{n}</b> housing units · {km2} km²{type}', { n: fmt(p.viviendas), km2: fmt(p.km2, 2), type: p.tipo ? ` · ${p.tipo}` : '' })}</div>`
      + `<div class="meta">${esc(T('Reported in the 2006 inventory: flooding {flood} · landslides {slide}', { flood: yn(p.inundable), slide: yn(p.deslizamiento) }))}</div>${assets}`
      + `<div class="src">${esc(T('Junta de Planificación, delimitation of Comunidades Especiales (Ley 1-2001), 2006'))}</div></div>`;
  }
  const protPop = (p) => `<div class="wm-pop"><h4>${esc(p.Unit_Nm)}</h4><div class="meta">${esc(p.Mang_Name || '')} · ${esc(T('{n} acres', { n: fmt(p.GIS_Acres) }))}</div><div class="src">${esc(T('USGS, Protected Areas Database of the United States (PAD-US)'))}</div></div>`;

  async function layer(k) {
    if (S.layers[k]) return S.layers[k];
    if (k === 'wcrp') {
      return (S.layers[k] = L.geoJSON(W.comm, { pointToLayer: (f, ll) => L.marker(ll, { icon: L.icon({ iconUrl: `img/${f.properties.estado === 'plan_aprobado' ? 'wcrp-pin' : 'wcrp-pin-open'}.svg`, iconSize: [16, 20], iconAnchor: [8, 20], popupAnchor: [0, -18] }), title: f.properties.comunidad, pane: 'scTop' }),
        onEachFeature: (f, lyr) => lyr.bindPopup(() => wcrpPopup([f.properties]), { maxWidth: 300 }) }));
    }
    const file = k === 'ce' ? 'comunidades.geojson' : k === 'protected' ? 'protected.geojson' : PTS[k].file;
    const d = S.docs[k] || (S.docs[k] = await (S.asked[k] || fetchJson('data/' + file)));
    if (S.layers[k]) return S.layers[k];
    S.renderer = S.renderer || L.canvas({ pane: 'scVec' });   // one canvas for every area and point, so a click finds the shape on top
    if (k === 'ce') S.layers[k] = L.geoJSON(d, { renderer: S.renderer, style: { color: CE_COLOR, weight: 1.2, fillColor: CE_COLOR, fillOpacity: .25 }, onEachFeature: (f, lyr) => lyr.bindPopup(() => cePop(f.properties), { maxWidth: 320 }) });
    else if (k === 'protected') S.layers[k] = L.geoJSON(d, { renderer: S.renderer, style: { color: PROT_COLOR, weight: .8, fillColor: PROT_COLOR, fillOpacity: .2 }, onEachFeature: (f, lyr) => lyr.bindPopup(() => protPop(f.properties), { maxWidth: 300 }) });
    else {
      S.layers[k] = L.geoJSON(d, { pointToLayer: (f, ll) => L.circleMarker(ll, { renderer: S.renderer, radius: 5, weight: 1.2, color: '#fff', fillColor: PTS[k].color, fillOpacity: .95 }),
        onEachFeature: (f, lyr) => lyr.bindPopup(() => factPop(k, f.properties, d), { maxWidth: 300 }).bindTooltip(() => esc(f.properties.name || T(f.properties.type)), { direction: 'top' }) });
    }
    return S.layers[k];
  }
  async function sync() {
    const want = new Set(THEMES.filter(t => S.on.has(t.id)).flatMap(t => t.layers));
    $('#scStatus').textContent = want.size ? T('Loading…') : '';
    try {
      await Promise.all([...want].map(layer));
      const now = new Set(THEMES.filter(t => S.on.has(t.id)).flatMap(t => t.layers));   // what is wanted once the files are in (a theme may have changed meanwhile)
      for (const [k, l] of Object.entries(S.layers)) { if (now.has(k)) l.addTo(S.map); else l.remove(); }
      for (const k of ['protected', 'ce', ...Object.keys(PTS)]) if (now.has(k) && S.layers[k]) S.layers[k].bringToFront();   // areas under points
      $('#scStatus').textContent = '';
    } catch (e) {
      console.error(e);
      $('#scStatus').textContent = T('A layer could not be loaded. Check your connection and switch the theme on again.');
    }
    legend();
  }
  function legend() {
    const row = (sw, label, n) => `<div class="row">${sw}${esc(label)}${n == null ? '' : `<small>${esc(n)}</small>`}</div>`;
    const dot = (c) => `<i style="background:${c};border-radius:50%"></i>`, box = (c) => `<i style="background:${c}33;border-color:${c}"></i>`;
    const drawn = (k) => { const d = S.docs[k]; if (!d) return null; const n = d.notes || {}, all = n.developments || n.libraries || n.stations || d.features.length;
      if (n.counted_not_drawn) return T('{drawn} of {all} listings drawn', { drawn: fmt(n.listings_drawn), all: fmt(n.listings) });   // historic places: private homes are counted, not drawn
      return d.features.length < all ? T('{drawn} of {all} drawn', { drawn: fmt(d.features.length), all: fmt(all) }) : fmt(d.features.length); };
    let h = '';
    for (const t of THEMES) {
      if (!S.on.has(t.id)) continue;
      for (const k of t.layers) {
        if (PTS[k]) h += row(dot(PTS[k].color), T(PTS[k].label), drawn(k));
        else if (k === 'ce') h += row(box(CE_COLOR), 'Comunidades Especiales', S.docs.ce ? fmt(S.docs.ce.features.length) : null);
        else if (k === 'protected') h += row(box(PROT_COLOR), T('Protected areas (PAD-US)'), null);
        else if (k === 'wcrp') h += row('<img src="img/wcrp-pin.svg" alt="" width="12" height="15">', T('WCRP communities'), fmt(W.comm.features.length));
      }
    }
    if (S.on.has('health')) h += `<div class="sub">${esc(T('Health: counts by municipio in the summary below; health facility and treatment facility points are not published.'))}</div>`;
    if (S.on.has('education') && S.docs.historic) h += `<div class="sub">${esc(T('Historic places: {n} private homes and haciendas are counted in the summary, not drawn.', { n: fmt(S.docs.historic.notes.counted_not_drawn) }))}</div>`;
    if (S.on.has('community')) h += `<div class="sub">${esc(T('Community water systems outside PRASA: counts by municipio in the summary below; their locations are not published.'))}${S.docs.townhalls ? ' ' + esc(T('City halls: {g} municipios have none mapped in OpenStreetMap yet.', { g: fmt(S.docs.townhalls.notes.municipios_without_a_city_hall_mapped.length) })) : ''}</div>`;
    $('#scLegend').innerHTML = h ? `<b>${esc(T('Shown on the map'))}</b>${h}` : `<b>${esc(T('Switch a theme on'))}</b>`;
  }
  function zoom() {
    if (W.muni && !W.fc) { geo().then(zoom, e => { console.error(e); $('#scStatus').textContent = T('The data could not be loaded. Check your connection and reload the page.'); }); return; }   // the municipio's barrios, on first use
    const fs = W.fc ? W.fc.features.filter(f => W.muni && f.properties.municipality === W.muni) : [];
    if (fs.length) S.map.fitBounds(L.geoJSON({ type: 'FeatureCollection', features: fs }).getBounds(), { padding: [20, 20] }); else S.map.setView([18.22, -66.45], 9);
    if (S.outline) S.outline.remove();
    S.outline = fs.length ? L.geoJSON({ type: 'FeatureCollection', features: fs }, { pane: 'scBase', interactive: false, style: { color: '#2A2E2E', weight: 1, fill: false, opacity: .5 } }).addTo(S.map) : null;
  }

  // ── Municipio summary: every asset type, its rate, and the vulnerability ranks of the municipio's barrios ──
  const val = (doc, key, i) => { const v = doc && doc.vars.find(x => x.key === key); return v ? Object.values(v.years)[0][i] : null; };
  function rows(i) {
    const D = S.d, F = S.data, cs = D.comunidades, pop = D.population.values;
    const wcrpN = (pred) => W.comm.features.filter(f => (i === D.geo.names.length - 1 || f.properties.municipio === D.geo.names[i]) && pred(f.properties)).length;
    const exp = F.exposure, ePR = exp ? exp.total.pop.reduce((a, b) => a + (b || 0), 0) : 0;
    const expIn = (j) => j === D.geo.names.length - 1 ? exp.vars.protected.pop.reduce((a, b) => a + (b || 0), 0) : exp.vars.protected.pop[j];
    const expTot = (j) => j === D.geo.names.length - 1 ? ePR : exp.total.pop[j];
    const th = S.docs.townhalls, unmapped = new Set(th ? th.notes.municipios_without_a_city_hall_mapped : []);   // a municipio with none mapped has a city hall all the same: no count, not 0
    const halls = (j) => !th || unmapped.has(D.geo.names[j]) ? null : th.features.filter(f => j === D.geo.names.length - 1 || f.properties.municipio === D.geo.names[j]).length;   // every feature: city halls and their annexes
    return [
      [T('Health'), T('Hospitals (Medicare-certified)'), (j) => val(F.care, 'cms_hospitals', j), 'CMS'],
      [T('Health'), T('Health center sites (permanent)'), (j) => val(F.health, 'hc_sites', j), 'HRSA'],
      [T('Health'), T('Dialysis facilities'), (j) => val(F.care, 'cms_dialysis', j), 'CMS'],
      [T('Health'), T('Substance use and mental health treatment facilities (counted, not drawn)'), (j) => val(F.comm, 'bh_all', j), 'SAMHSA'],
      [T('Education and culture'), T('Public libraries'), (j) => val(F.fac, 'libraries', j), 'USAC'],
      [T('Education and culture'), T('Places on the National Register of Historic Places (private homes counted, not drawn)'), (j) => val(F.comm, 'nrhp_places', j), 'NPS'],
      [T('Security'), T('Fire and EMS stations'), (j) => val(F.fac, 'fire_stations', j), 'USGS'],
      [T('Security'), T('Police stations'), (j) => val(F.fac, 'police_stations', j), 'OpenStreetMap'],
      [T('Community services'), T('Public housing developments'), (j) => val(F.fac, 'ph_devs', j), 'HUD'],
      [T('Community services'), T('Public housing units'), (j) => val(F.fac, 'ph_units', j), 'HUD'],
      [T('Community services'), T('City halls mapped (with annexes)'), halls, 'OpenStreetMap'],
      [T('Community services'), T('Community water systems outside PRASA (counted, not drawn)'), (j) => val(F.infra, 'water_nonprasa', j), 'EPA ECHO'],
      [T('Community services'), T('Residents they serve'), (j) => val(F.infra, 'water_nonprasa_pop', j), 'EPA ECHO'],
      ['Comunidades Especiales', 'Comunidades Especiales', (j) => cs.polygons[j], T('Junta de Planificación, 2006')],
      ['Comunidades Especiales', T('Housing units in them'), (j) => cs.housing_units[j], T('Junta de Planificación, 2006')],
      [T('WCRP communities'), T('WCRP communities'), (j) => j === i ? wcrpN(() => true) : null, 'FPR', null, true],
      [T('WCRP communities'), T('with an approved plan'), (j) => j === i ? wcrpN(p => p.estado === 'plan_aprobado') : null, 'FPR', null, true],
      [T('Environment'), T('Residents inside a protected area (2020 Census)'), (j) => exp ? expIn(j) : null, 'PAD-US', (j) => exp ? expTot(j) : null],
    ].map(([theme, label, get, src, den, wcrpOnly]) => {   // wcrpOnly: a program list, not a rate of the municipio's residents
      const pr = D.geo.names.length - 1, rate = (j) => { const v = get(j), p = den ? den(j) : pop[j]; return v == null || !p ? null : v / p * 1000; };
      return { theme, label, src, n: get(i), rate: rate(i), prRate: rate(pr), wcrpOnly: !!wcrpOnly };
    });
  }
  function rankBar(ver, area, muni) {
    const n = [0, 0, 0, 0, 0]; let m = 0;
    W.ids.forEach((g, i) => { if (muni && muniOf(g) !== muni) return; const r = rankAt(ver, area, i); if (r) { n[r - 1]++; m++; } });
    if (!m) return '<td>—</td>';
    const bar = n.map((c, k) => c ? `<i style="width:${(100 * c / m).toFixed(1)}%;background:${RAMP[k]}" title="${esc(T('Level {rank}: {n} barrios', { rank: k + 1, n: c }))}"></i>` : '').join('');
    return `<td><span class="sc-bar" role="img" aria-label="${esc(T('Levels 1 to 5: {list}', { list: n.join(', ') }))}">${bar}</span><small>${esc(T('{n} of {m} in levels 4–5', { n: n[3] + n[4], m }))}</small></td>`;
  }
  function summary() {
    if (!S.d || !S.data) return;
    const D = S.d, names = D.geo.names, pr = names.length - 1, i = W.muni ? names.indexOf(W.muni) : pr, name = i === pr ? T('Puerto Rico') : names[i];
    $('#scMuni').value = W.muni;
    const R = rows(i), pop = D.population;
    let last = '';
    const body = R.map(r => { const th = r.theme !== last ? `<tr class="sc-theme"><th colspan="4" scope="colgroup">${esc(r.theme)}</th></tr>` : ''; last = r.theme;
      return `${th}<tr><th scope="row">${esc(r.label)} <small>${esc(r.src)}</small></th><td class="num">${r.n == null ? '—' : fmt(r.n)}</td><td class="num">${r.wcrpOnly || r.rate == null ? '—' : fmt(r.rate, 2)}</td><td class="num">${r.wcrpOnly || r.prRate == null ? '—' : fmt(r.prRate, 2)}</td></tr>`; }).join('');
    $('#scAssets').innerHTML = `<caption>${esc(T('Community assets of {name}', { name }))}</caption><thead><tr><th scope="col">${esc(T('Asset'))}</th><th scope="col" class="num">${esc(T('Count'))}</th><th scope="col" class="num">${esc(T('Per 1,000 residents'))}</th><th scope="col" class="num">${esc(T('Puerto Rico, per 1,000'))}</th></tr></thead><tbody>${body}</tbody>`;
    $('#scAssetsNote').textContent = T('Residents: {name}, {n} ({basis}). Residents inside a protected area are divided by the 2020 Census residents. Health is counted by municipio only: the observatory does not publish health facility points.', { name, n: fmt(pop.values[i]), basis: T('Census Bureau estimate for {year}', { year: pop.year }) })
      + ' ' + T('Treatment facilities: the 2024 survey of SAMHSA\'s directories. Water systems outside PRASA: those EPA records as privately owned; residents served count only the systems that serve one municipio. City halls: as mapped in OpenStreetMap, where {g} municipios have none mapped yet.', { g: fmt(S.docs.townhalls ? S.docs.townhalls.notes.municipios_without_a_city_hall_mapped.length : 0) });
    const A = D.assets, F = A.flags, ln = A.listed[i];
    $('#scFlags').innerHTML = `<caption>${esc(T('Comunidades Especiales of {name} in the WCRP Social Capital Mapping list: {n}', { name, n: fmt(ln) }))}</caption><thead><tr><th scope="col">${esc(T('Asset'))}</th><th scope="col" class="num">${esc(T('Communities with it'))}</th><th scope="col" class="num">${esc(T('Share'))}</th><th scope="col" class="num">${esc(T('Not recorded'))}</th><th scope="col" class="num">${esc(T('Puerto Rico share'))}</th></tr></thead><tbody>`
      + F.map(f => `<tr><th scope="row">${esc(T(FLAG[f]))}</th><td class="num">${fmt(A.yes[f][i])}</td><td class="num">${ln ? fmt(100 * A.yes[f][i] / ln, 0) + '%' : '—'}</td><td class="num">${fmt(A.unknown[f][i])}</td><td class="num">${fmt(100 * A.yes[f][pr] / A.listed[pr], 0)}%</td></tr>`).join('') + '</tbody>';
    $('#scRanks').innerHTML = `<caption>${esc(T('Vulnerability levels of the barrios of {name} (map 2)', { name }))}</caption><thead><tr><th scope="col">${esc(T('Area'))}</th><th scope="col">${esc(T('Original 2022'))}</th><th scope="col">${esc(T('Updated {window}', { window: W.doc.versions.rebuild.window }))}</th></tr></thead><tbody>`
      + AREAS.map(a => `<tr><th scope="row">${esc(T(AREA_NAME[a]))}</th>${rankBar('orig', a, W.muni)}${rankBar('rebuild', a, W.muni)}</tr>`).join('') + '</tbody>';
  }
  function byMuniTable() {
    const A = S.d.assets, names = S.d.geo.names;
    $('#scByMuni').innerHTML = `<thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col" class="num">${esc(T('In the list'))}</th>${A.flags.map(f => `<th scope="col" class="num">${esc(T(FLAG[f]))}</th>`).join('')}</tr></thead><tbody>`
      + names.map((n, i) => `<tr${i === names.length - 1 ? ' class="sc-total"' : ''}><th scope="row">${esc(i === names.length - 1 ? T('Puerto Rico') : n)}</th><td class="num">${fmt(A.listed[i])}</td>${A.flags.map(f => `<td class="num">${fmt(A.yes[f][i])}</td>`).join('')}</tr>`).join('') + '</tbody>';
    const m = A.match;
    $('#scMatch').textContent = T('{rows} communities in the list; {matched} matched to a polygon of the Junta\'s 2006 delimitation ({exact} by the same name, {barrio} by name and barrio, {close} by a close name in the same barrio); {polys} of its {all} polygons have flags.', { rows: fmt(m.rows), matched: fmt(m.matched_rows), exact: fmt(m.by_rule.exacto || 0), barrio: fmt(m.by_rule.barrio || 0), close: fmt(m.by_rule.parecido || 0), polys: fmt(m.polygons_matched), all: fmt(m.polygons) });
  }
  function saveCsv() {
    const q = v => { if (v == null) return ''; const s = String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const D = S.d, A = D.assets, names = D.geo.names;
    const R0 = rows(0);
    const head = [T('Municipio'), ...R0.filter(r => !r.wcrpOnly).flatMap(r => [`${r.label} (${r.src})`, `${r.label}: ${T('per 1,000 residents')}`]), T('Comunidades Especiales in the WCRP list'), ...A.flags.map(f => T(FLAG[f])), T('Residents ({year} estimate)', { year: D.population.year })];
    const out = names.map((n, i) => { const R = rows(i).filter(r => !r.wcrpOnly); return [i === names.length - 1 ? T('Puerto Rico') : n, ...R.flatMap(r => [r.n, r.rate == null ? null : +r.rate.toFixed(3)]), A.listed[i], ...A.flags.map(f => A.yes[f][i]), D.population.values[i]]; });
    const note = [T('Sources: HUD, USGS, OpenStreetMap contributors (ODbL), USAC, NPS, CMS, HRSA, SAMHSA, EPA ECHO, USGS PAD-US, Junta de Planificación (2006), Census Bureau; community assets: WCRP Social Capital Mapping list (PRDOH and FPR, date not stated, about 2019–2021). In review.')];
    const csv = '﻿' + [head, ...out, [], note].map(r => r.map(q).join(',')).join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = 'pr_municipios_wcrp_social_capital.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  // ── Start ────────────────────────────────────────────────────────────────
  const FILES = ['facility_series.json', 'care_series.json', 'health_series.json', 'exposure_municipio.json', 'community_series.json', 'infrastructure_series.json', 'town_halls.geojson'];
  function start() {   // at once: the map and the summary's files (the base map follows once the page is ready)
    S.map = L.map('scMap', { scrollWheelZoom: false, zoomControl: false, maxZoom: 17 }).setView([18.22, -66.45], 9);
    capPopups(S.map);   // js/wcrp.js: pop-ups no wider than the map
    L.control.zoom({ position: 'topright', zoomInTitle: T('Zoom in'), zoomOutTitle: T('Zoom out') }).addTo(S.map);
    W.basemap(S.map);   // js/wcrp.js: the base map and its credits, once the page is ready (docs/basemap.md)
    [['scBase', 390], ['scVec', 400], ['scTop', 620]].forEach(([n, z]) => { S.map.createPane(n).style.zIndex = z; });
    S.files = Promise.all(FILES.map(f => fetchJson('data/' + f)));
    for (const k of THEMES.filter(t => t.on).flatMap(t => t.layers).filter(k => PTS[k] && k !== 'townhalls')) {   // the default themes' points, with the page's files (the city halls come with FILES)
      S.asked[k] = fetchJson('data/' + PTS[k].file); S.asked[k].catch(() => { delete S.asked[k]; });   // a failed one is asked again when its theme is switched on
    }
    S.files.catch(() => {});   // init reports it
  }
  async function init(d) {   // d: wcrp_social.json, read by wcrp.js with the page's files (it names the municipios)
    $('#scThemes').innerHTML = THEMES.map(t => `<label class="sc-theme-${t.id}"><input type="checkbox" value="${t.id}"${S.on.has(t.id) ? ' checked' : ''}><span>${esc(T(t.label))}</span></label>`).join('');
    $('#scThemes').onchange = e => { if (e.target.checked) S.on.add(e.target.value); else S.on.delete(e.target.value); sync(); };
    $('#scCsv').onclick = saveCsv;
    S.d = d; byMuniTable();
    const [got] = await Promise.allSettled([S.files]);   // one count file that fails must not keep the map or the rest of the page from drawing
    if (got.status === 'fulfilled') {
      const [fac, care, health, exposure, comm, infra, halls] = got.value;
      S.data = { fac, care, health, exposure, comm, infra }; S.docs.townhalls = S.docs.townhalls || halls;   // the city halls are counted from the layer's own file, loaded once
      summary();
    } else console.error(got.reason);
    if (W.muni) zoom();
    await sync();
    if (!S.data) $('#scStatus').textContent = T('The data could not be loaded. Check your connection and reload the page.');
  }
  function setMuni() {   // wcrp.js: the page's one municipio changed (here, or in the vulnerability map's filter)
    $('#scMuni').value = W.muni;
    if (S.d) { zoom(); summary(); }
  }
  return { start, init, setMuni, TYPES };
})();
