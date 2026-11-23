/* PR Data Observatory · Knowledge Area · WCRP (wcrp.html), section 2: the vulnerability map. Loaded by wcrp.js (loadVuln) when the section comes near, when one
   of the explanations it fills opens, or at once for an address that names a view of it, with its Spanish (es.wcrp.vuln.js) and the barrio outlines
   (barrios.geojson). The Risk and Vulnerability Indicators by barrio, the original as published (2022) and the observatory's updated version ("Updated 2020–2024"; 'rebuild' in ids and data keys) with the same method on the
   survey and the local conditions (wcrp_rvi.py, conditions.py), on one map with one legend ("What the levels mean": the five levels in the map's colours, what
   they mean, the inputs of the area shown and what the version is). Change (the rebuild's level minus the original's) is not in the version selector: it
   opens from "More about the comparison" (showChange) or an old link (#v=change), with a way back. The input values behind a barrio (wcrp_rvi_inputs.json) load
   with the first pop-up, with the observatory's landslide susceptibility by barrio (landslide_barrio.json, landslide.py), shown beside the index with the age
   groups, never as an input. It also fills the closed explanations below the map: the method, the inputs, the checks, the comparison, the sources. docs/wcrp.md. */
const Vuln = (() => {
  const TK = (t) => t;   // translated where it is shown, with T()
  const RANK_NAME = [TK('Low'), TK('Medium-low'), TK('Medium'), TK('Medium-high'), TK('High')];
  const RANK_NOTE = [TK('among the 20% least vulnerable barrios'), null, null, null, TK('among the 20% most vulnerable barrios')];   // a level holds a fifth of the barrios ranked
  const CHANGE_NAME = [TK('2 or more levels lower'), TK('1 level lower'), TK('Same level'), TK('1 level higher'), TK('2 or more levels higher')];
  const SUB_NAME = { quality: TK('neighbourhood quality'), problems: TK('housing problems'), telecom: TK('telecommunications'), transport: TK('transportation') };
  // Each input in plain words, for the legend's line about the area shown ("Looks at: ..."); both versions' keys (tests/test_wcrp_rvi.py checks that every input has one).
  const PLAIN = {
    o_public_assist_pct: TK('public assistance'), public_assist_hh_pct: TK('public assistance'),
    o_poverty_pct: TK('poverty'), poverty_pct: TK('poverty'),
    o_unemployed_pct: TK('unemployment'), unemployment_rate_pct: TK('unemployment'),
    o_not_enrolled_3_24_pct: TK('young people (3 to 24) not in school'), not_enrolled_3_24_pct: TK('young people (3 to 24) not in school'),
    o_no_diploma_pct: TK('adults without a high school diploma'), acs_no_hs_pct: TK('adults without a high school diploma'),
    o_nonattainment: TK('air pollution (sulfur dioxide or lead)'), nonattainment_flag: TK('air pollution (sulfur dioxide or lead)'),
    o_impaired_water: TK('polluted water bodies'), impaired_water_flag: TK('polluted water bodies'),
    o_rmp_sites: TK('facilities that handle dangerous chemicals'), rmp_sites: TK('facilities that handle dangerous chemicals'),
    o_dumps: TK('landfills'), landfill_flag: TK('landfills'),
    o_solid_waste: TK('other solid waste facilities'),
    o_npl_sites: TK('toxic waste sites (Superfund)'), npl_sites: TK('toxic waste sites (Superfund)'),
    o_tri_facilities: TK('industries that report toxic releases'), tri_facilities: TK('industries that report toxic releases'),
    o_lead_paint_pct: TK('homes built before 1960 (lead paint)'), built_pre1960_pct: TK('homes built before 1960 (lead paint)'),
    o_disability_pct: TK('disability'), acs_disability_pct: TK('disability'),
    o_uninsured_pct: TK('no health insurance'), acs_uninsured_pct: TK('no health insurance'),
    o_hospital_min: TK('time to the nearest hospital'), hospital_drive_min: TK('time to the nearest hospital'),
    o_vacancy_pct: TK('empty homes'), vacancy_pct: TK('empty homes'),
    o_built_pre1990_pct: TK('homes built before 1990'), built_pre1990_pct: TK('homes built before 1990'),
    o_severe_problems_pct: TK('severe housing problems'), severe_problems_pct: TK('severe housing problems'),
    o_intersections_sqmi: TK('few street intersections'), intersection_density: TK('few street intersections'),
    o_no_vehicle_pct: TK('homes without a vehicle'), no_vehicle_hh_pct: TK('homes without a vehicle'),
    o_no_computer_pct: TK('homes without a computer'), no_computer_pct: TK('homes without a computer'),
    o_no_internet_pct: TK('homes without internet'), no_internet_pct: TK('homes without internet'),
    o_no_broadband_pct: TK('homes without broadband'), no_broadband_pct: TK('homes without broadband'),
  };
  const NOT_INPUT = new Set(['o_per_capita_income']);   // the original's table shows it; the white paper does not use it
  const CHANGE = Core.palettes.DIVERGING.slice().reverse();   // change: blue is a lower level in the updated version, red a higher one
  const V = { map: null, layer: null, commLayer: null, inputs: null, inputsP: null, inAt: null, ls: null, last: 'orig' };

  const changeAt = (area, i) => { const a = rankAt('orig', area, i), b = rankAt('rebuild', area, i); return a == null || b == null ? null : b - a; };
  const changeClass = (d) => d == null ? -1 : d <= -2 ? 0 : d === -1 ? 1 : d === 0 ? 2 : d === 1 ? 3 : 4;
  const verLabel = (ver) => ver === 'orig' ? T('Original 2022 (ACS 2015–2019)') : T('Updated {window}', { window: verWindow(ver) });
  const pct = (x, d = 1) => x == null ? '—' : fmt(x, d) + '%';
  function colorOf(i) {
    if (W.ver === 'change') { const c = changeClass(changeAt(W.area, i)); return c < 0 ? NOVAL : CHANGE[c]; }
    const r = rankAt(W.ver, W.area, i); return r == null ? NOVAL : RAMP[r - 1];
  }
  const inMuni = (f) => !W.muni || f.properties.municipality === W.muni;

  // ── Map ────────────────────────────────────────────────────────────────────
  function initMap() {
    V.map = L.map('wmMap', { scrollWheelZoom: false, zoomControl: false, maxZoom: 17 }).setView([18.22, -66.45], 9);
    capPopups(V.map);
    L.control.zoom({ position: 'topright', zoomInTitle: T('Zoom in'), zoomOutTitle: T('Zoom out') }).addTo(V.map);
    W.basemap(V.map);   // js/wcrp.js (docs/basemap.md)
    V.layer = L.geoJSON(W.fc, { style: styleOf, onEachFeature: (f, lyr) => {
      lyr.bindTooltip(() => tipOf(f), { sticky: true });
      lyr.on('click', (e) => openPopup(f, e.latlng));
    } }).addTo(V.map);
  }
  function styleOf(f) {
    const i = W.at.get(f.properties.geoid), on = inMuni(f);
    return { color: '#fff', weight: on && W.muni ? .9 : .4, fillColor: i == null ? NOVAL : colorOf(i), fillOpacity: on ? .82 : .12, opacity: on ? 1 : .3 };
  }
  function tipOf(f) {
    const i = W.at.get(f.properties.geoid), p = f.properties;
    let line;
    if (i == null) line = T('No data');
    else if (W.ver === 'change') { const a = rankAt('orig', W.area, i), b = rankAt('rebuild', W.area, i); line = a == null || b == null ? T('No data') : T('Level {from} in the original 2022, {to} in the updated version', { from: a, to: b }); }
    else { const r = rankAt(W.ver, W.area, i); line = r == null ? T('No data') : W.ver[0] === 'w' ? T('Level {rank} ({name})', { rank: r, name: T(RANK_NAME[r - 1]) }) : T('Level {rank} ({name}) · index {value} of 100', { rank: r, name: T(RANK_NAME[r - 1]), value: fmt(W.v[W.ver][W.area][i], 2) }); }
    return `<b>${esc(p.barrio)}</b> · ${esc(p.municipality)}<br>${esc(T(AREA_NAME[W.area]))}: ${esc(line)}`;
  }
  function render() {
    V.layer.setStyle(styleOf);
    renderKey();
    writeHash();
  }

  // ── The legend: what the levels mean, in the map's colours; the inputs of the area shown; what the version is ──
  const inputsOf = (ver, area) => W.doc.method[ver === 'orig' ? 'orig' : 'rebuild'].filter(x => x.area === area && !NOT_INPUT.has(x.key));
  const plain = (x) => T(PLAIN[x.key] || x.label);
  function areaLine() {
    if (W.area === 'overall') return T('Combines the six areas with equal weight.');
    const names = inputsOf(W.ver === 'change' ? 'orig' : W.ver, W.area).map(plain);
    let s = T('Looks at: {list}.', { list: I18N.list([...new Set(names)]) });
    if (W.ver === 'change') {   // the inputs the updated version has no current source for
      const now = new Set(inputsOf('rebuild', W.area).map(plain)), out = names.filter(n => !now.has(n));
      if (out.length) s += ' ' + T('The updated version leaves out: {list}.', { list: I18N.list(out) });
    }
    return s;
  }
  function verLine() {
    const v = W.doc.versions;
    if (W.ver === 'orig') return T('Original 2022: the index as published in 2022, with Census data from {window} and other official sources.', { window: v.orig.window });
    if (W.ver === 'rebuild' || W.ver[0] === 'w') return T('Updated {window}: the same method with {window} Census data and current official sources.', { window: verWindow(W.ver) });
    return T("Change: each barrio's level in the updated version minus its level in the original 2022 index.");
  }
  function renderKey() {
    const change = W.ver === 'change', n = [0, 0, 0, 0, 0]; let none = 0;
    W.fc.features.forEach(f => { if (!inMuni(f)) return; const i = W.at.get(f.properties.geoid), c = i == null ? -1 : change ? changeClass(changeAt(W.area, i)) : (rankAt(W.ver, W.area, i) || 0) - 1; if (c < 0) none++; else n[c]++; });
    const row = (sw, name, note, k) => `<li>${sw}<span class="lv"><span class="nm">${esc(name)}</span>${note ? `<span class="ds">${esc(note)}</span>` : ''}</span><small class="n">${esc(Tn(k, '{n} barrio', '{n} barrios', { n: fmt(k) }))}</small></li>`;
    const chip = (bg, ink, txt) => `<span class="rk" style="background:${bg};color:${ink}">${txt}</span>`;
    $('#wmLevels').innerHTML = (change
      ? CHANGE.map((c, k) => row(chip(c, '#2A2E2E', ''), T(CHANGE_NAME[k]), null, n[k])).join('') + row(chip(NOVAL, '#2A2E2E', ''), T('No level in one of the two versions'), null, none)
      : RAMP.map((c, k) => row(chip(c, inkOn(k + 1), k + 1), T(RANK_NAME[k]), RANK_NOTE[k] && T(RANK_NOTE[k]), n[k])).join('') + row(chip(NOVAL, '#2A2E2E', ''), T('No residents or no data'), null, none));
    $('#wmKeyTitle').textContent = change ? T('How the level changes from 2022 to the updated version') : T('What the levels mean');
    $('#wmKeySub').hidden = !W.muni;
    $('#wmKeySub').textContent = W.muni ? T('Barrios of {name}. Levels compare them with every barrio of Puerto Rico.', { name: W.muni }) : '';
    $('#wmAreaLine').innerHTML = `<b>${esc(T(AREA_NAME[W.area]))}.</b> ${esc(areaLine())}`;
    $('#wmVerLine').textContent = verLine();
    $('#wmChange').hidden = !change;
    syncVer();
  }

  // ── Pop-up: the levels in both versions and the inputs of the area shown ───
  function loadInputs() {   // the landslide file is context: if it fails, the inputs still show and the pop-up says so
    return V.inputsP || (V.inputsP = Promise.all([fetchJson('data/wcrp_rvi_inputs.json'), fetchJson('data/landslide_barrio.json').catch(e => { console.warn(e); return null; })]).then(([d, ls]) => {
      V.inputs = d; V.inAt = new Map(d.geo.ids.map((g, i) => [g, i]));
      V.ls = ls && { at: new Map(ls.geo.ids.map((g, i) => [g, i])), v: Object.fromEntries(ls.vars.map(v => [v.key, Object.values(v.years)[0]])), why: Object.fromEntries(ls.vars.map(v => [v.key, v.noValueWhy || []])) };
    }, e => { V.inputsP = null; throw e; }));
  }
  function contextHTML(geoid, j) {   // beside the index, not inputs: the age groups of the rebuild's survey window and the landslide susceptibility (docs/wcrp.md)
    const M = W.doc.method, r = V.inputs.rebuild; if (!M.context || !r.context) return '';
    const age = M.context.map(x => { const v = r.context[x.key][j], m = r.context_moe[x.key][j]; return `<tr><td>${esc(T(x.label))}</td><td class="num">${v == null ? '—' : esc(pct(v) + (m == null ? '' : ` ± ${fmt(m, 1)}`))}</td></tr>`; }).join('');
    let ls;
    if (!V.ls) ls = `<tr><td colspan="2">${esc(T('The landslide susceptibility could not be loaded.'))}</td></tr>`;
    else {
      const k = V.ls.at.get(geoid), mapped = k != null && V.ls.v.ls_land_high_pct && V.ls.v.ls_land_high_pct[k] != null;
      ls = (M.hazards || []).map(x => { const a = V.ls.v[x.key], v = k == null || !a ? null : a[k], why = v == null && (V.ls.why[x.key] || []).find(w => w.ids && w.ids.includes(geoid));
        return `<tr><td>${esc(T(x.label))}</td><td class="num">${v != null ? esc(pct(v)) : esc(why ? T(why.why) : mapped ? '—' : T('not mapped (main island only)'))}</td></tr>`; }).join('');
    }
    return `<table><thead><tr><th scope="col">${esc(T('Beside the index, not inputs'))}</th><th class="num" scope="col"></th></tr></thead><tbody>${age}${ls}</tbody></table>`
      + `<div class="src">${esc(T('Age groups: survey estimates for {window} with their margins of error. Landslides: USGS susceptibility map, 2020. Neither changes a level.', { window: W.doc.versions.rebuild.window }))}</div>`;
  }
  const chip = (r) => r == null ? '—' : `<span class="rk" style="background:${RAMP[r - 1]};color:${inkOn(r)}">${r}</span>`;
  function popupHTML(f, withInputs) {
    const p = f.properties, i = W.at.get(p.geoid);
    const rows = AREAS.map(a => `<tr${a === W.area ? ' class="on"' : ''}><td>${esc(T(AREA_NAME[a]))}</td><td class="num">${i == null ? '—' : chip(rankAt('orig', a, i))}</td><td class="num">${i == null ? '—' : chip(rankAt('rebuild', a, i))}</td></tr>`).join('');
    let inputs = `<div class="src">${esc(T('Loading the inputs…'))}</div>`;
    if (withInputs === false) inputs = `<div class="src">${esc(T('The inputs could not be loaded. Check your connection and click the barrio again.'))}</div>`;
    else if (V.inputs) inputs = inputsHTML(p.geoid);
    return `<div class="wm-pop"><h4>${esc(p.barrio)}</h4><div class="meta">${esc(p.municipality)} · ${esc(T('Level 1 is low, 5 is high vulnerability'))}</div>
      <table><thead><tr><th scope="col">${esc(T('Area'))}</th><th scope="col" class="num">${esc(T('Original'))}</th><th scope="col" class="num">${esc(T('Updated'))}</th></tr></thead><tbody>${rows}</tbody></table>${inputs}</div>`;
  }
  function inputsHTML(geoid) {
    const j = V.inAt.get(geoid), M = W.doc.method, area = W.area;
    if (j == null) return '';
    const o = V.inputs.orig, r = V.inputs.rebuild, fmtIn = (v, unit) => v == null ? '—' : unit === '%' ? pct(v) : unit === '$' ? '$' + fmt(v, 0) : fmt(v, unit === 'min' ? 1 : v % 1 ? 1 : 0);
    if (area === 'overall') {
      return `<table><thead><tr><th scope="col">${esc(T('Residents (survey estimate)'))}</th><th scope="col" class="num">${esc(T('Original'))}</th><th scope="col" class="num">${esc(T('Updated'))}</th></tr></thead><tbody><tr><td>${esc(T('Residents'))}</td><td class="num">${o.population[j] == null ? '—' : fmt(o.population[j], 0)}</td><td class="num">${r.population[j] == null ? '—' : fmt(r.population[j], 0)}</td></tr></tbody></table><div class="src">${esc(T('The overall index adds the six area percentiles. Choose an area to see its inputs.'))}</div>${contextHTML(geoid, j)}`;
    }
    const oi = M.orig.filter(x => x.area === area), ri = M.rebuild.filter(x => x.area === area);
    const rowO = oi.map(x => `<tr><td>${esc(T(x.label))}</td><td class="num">${esc(fmtIn(o.values[x.key][j], x.unit))}</td></tr>`).join('');
    const rowR = ri.map(x => `<tr><td>${esc(T(x.label))}</td><td class="num">${esc(fmtIn(r.values[x.key][j], x.unit == null ? '%' : x.unit))}</td></tr>`).join('');
    return `<table><thead><tr><th scope="col">${esc(T('Original inputs (ACS 2015–2019 and others)'))}</th><th class="num" scope="col"></th></tr></thead><tbody>${rowO}</tbody></table>
      <table><thead><tr><th scope="col">${esc(T('Inputs of the updated version (ACS {window} and current sources)', { window: W.doc.versions.rebuild.window }))}</th><th class="num" scope="col"></th></tr></thead><tbody>${rowR}</tbody></table>
      <div class="src">${esc(T('Survey estimates for one barrio are rough: read them with care.'))}${area === 'health' && r.values.hospital_drive_min && r.values.hospital_drive_min[j] == null && r.population[j] ? ' ' + esc(T('No road leads from this barrio to a general hospital: its health level uses the other two inputs.')) : ''}</div>`;
  }
  function openPopup(f, latlng) {
    const pop = L.popup({ maxWidth: 340 }).setLatLng(latlng).setContent(popupHTML(f)).openOn(V.map);
    if (!V.inputs) loadInputs().then(() => pop.isOpen() && pop.setContent(popupHTML(f)), () => pop.isOpen() && pop.setContent(popupHTML(f, false)));
  }

  // ── Controls, the change view, CSV ─────────────────────────────────────────
  function zoomMuni() {
    const fs = W.fc.features.filter(f => W.muni && f.properties.municipality === W.muni);
    if (fs.length) V.map.fitBounds(L.geoJSON({ type: 'FeatureCollection', features: fs }).getBounds(), { padding: [20, 20] }); else V.map.setView([18.22, -66.45], 9);
  }
  function setVersion(v) {   // V.last: the version to go back to from the change view
    if (W.ver !== 'change') V.last = W.ver;
    W.ver = v; render();
  }
  /** "Show on the map the barrios whose level changes" (More about the comparison): the change view, scrolled into sight, with the way back in focus. */
  function showChange() {
    V.map.closePopup(); setVersion('change');
    $('#vulnerability .wm-card').scrollIntoView({ block: 'start' });
    $('#wmChange').focus({ preventScroll: true });
  }
  function back() {
    setVersion(V.last || 'orig');
    $('#wmVer').focus();
  }
  function initControls() {
    $('#wmArea').value = W.area;   // the areas and the version's name: wcrp.js (initVulnControls), so a choice made before this script arrived is kept
    $('#wmBack').textContent = T('Back to Original 2022 and Updated {window}', { window: W.doc.versions.rebuild.window });
    $('#wmArea').onchange = e => { W.area = e.target.value; V.map.closePopup(); render(); };
    $('#wmVer').oninput = e => setVersion(W.steps[+e.target.value]);
    $('#wmBack').onclick = back;
    $('#wmComm').onchange = e => toggleCommunities(e.target.checked);
    $('#wmCsv').onclick = saveCsv;
  }
  function toggleCommunities(on) {
    if (!V.commLayer) V.commLayer = L.geoJSON(W.comm, { pointToLayer: (f, ll) => L.marker(ll, { icon: L.icon({ iconUrl: `img/${f.properties.estado === 'plan_aprobado' ? 'wcrp-pin' : 'wcrp-pin-open'}.svg`, iconSize: [16, 20], iconAnchor: [8, 20], popupAnchor: [0, -18] }), title: f.properties.comunidad }),
      onEachFeature: (f, lyr) => lyr.bindPopup(() => wcrpPopup([f.properties]), { maxWidth: 300 }) });
    if (on) V.commLayer.addTo(V.map); else V.commLayer.remove();
  }
  function saveCsv() {
    const q = v => { if (v == null) return ''; const s = String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const byId = new Map(W.fc.features.map(f => [f.properties.geoid, f.properties]));
    const head = ['GEOID', T('Barrio'), T('Municipality'), ...['orig', 'rebuild'].flatMap(ver => AREAS.flatMap(a => [`${T(AREA_NAME[a])} · ${verLabel(ver)} · ${T('index (0-100)')}`, `${T(AREA_NAME[a])} · ${verLabel(ver)} · ${T('level (1-5)')}`]))];
    const rows = W.ids.map((g, i) => [g, (byId.get(g) || {}).barrio, (byId.get(g) || {}).municipality, ...['orig', 'rebuild'].flatMap(ver => AREAS.flatMap(a => [W.v[ver][a][i], rankAt(ver, a, i)]))]);
    const note = [T('Source: WCRP Risk and Vulnerability Indicators (Hunter College for Foundation for Puerto Rico, 2022), as published; updated version by the PR Data Observatory with the same method on ACS {window}. In review; the original states no license.', { window: W.doc.versions.rebuild.window })];
    const csv = '﻿' + [head, ...rows, [], note].map(r => r.map(q).join(',')).join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = 'pr_barrios_wcrp_vulnerability.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  // ── The explanations, built from the data: the comparison, the inputs, the checks, the errors, the sources ──
  function renderComparison() {
    const C = W.doc.checks, R = C.rebuild_vs_original, F = C.fewer_inputs_vs_original, S = C.rebuild_vs_older_window, w = W.doc.versions.rebuild.window;
    $('#cmpLede').textContent = T('Out of {n} barrios with a level in both versions, {changed}% have a different overall level in the updated version and {moved}% move two levels or more. The table gives each area.', { n: fmt(R.overall.n), changed: fmt(R.overall.changed_pct, 0), moved: fmt(R.overall.moved2_pct, 0) });
    const cell = (x) => `<td class="num">${pct(x.changed_pct, 0)}</td><td class="num">${pct(x.moved2_pct, 0)}</td><td class="num">${x.spearman == null ? '—' : fmt(x.spearman, 2)}</td>`;
    $('#cmpTable').innerHTML = `<thead><tr><th scope="col">${esc(T('Area'))}</th><th scope="col" class="num">${esc(T('Level changes'))}</th><th scope="col" class="num">${esc(T('Moves 2+ levels'))}</th><th scope="col" class="num">${esc(T('Rank correlation'))}</th><th scope="col" class="num">${esc(T('Original values, updated inputs: level changes'))}</th><th scope="col" class="num">${esc(T('Two survey periods: level changes'))}</th></tr></thead><tbody>`
      + AREAS.map(a => `<tr><th scope="row">${esc(T(AREA_NAME[a]))}</th>${cell(R[a])}<td class="num">${pct(F[a].changed_pct, 0)}</td><td class="num">${pct(S[a].changed_pct, 0)}</td></tr>`).join('') + '</tbody>';
    $('#cmpWhy').textContent = T('Four things move the levels. First, the method does not give back the original\'s economy and environment indices from their own inputs, and the updated version leaves out one input (see How the index is built): ranking the original\'s own 2015–2019 values with the updated version\'s inputs changes {fewer}% of overall levels, almost all through economy and environment. Second, several inputs now come from newer sources that define them differently. Third, five years passed. Fourth, survey estimates for barrios are rough: the updated version run on two survey periods that share two years ({older} and {w}), with the same values for the inputs that are not from the survey, gives a different overall level to {older_pct}% of barrios. A rank correlation of 1 means the same order; 0 means no relation.', { fewer: fmt(F.overall.changed_pct, 0), older: S.window, w, older_pct: fmt(S.overall.changed_pct, 0) });
  }
  function renderInputs() {
    const M = W.doc.method, w = W.doc.versions.rebuild.window;
    const by = (list, a) => list.filter(x => x.area === a);
    const rows = AREAS.filter(a => a !== 'overall').map(a => {
      const orig = by(M.orig, a).filter(x => !NOT_INPUT.has(x.key)).map(x => esc(T(x.label))).join('<br>');
      const reb = by(M.rebuild, a).map(x => esc(T(x.label)) + (x.sub ? ` <small>(${esc(T(SUB_NAME[x.sub]))})</small>` : '') + (x.note ? '<sup>*</sup>' : '')).join('<br>');
      const miss = by(M.missing, a).map(x => `<b>${esc(T(x.label))}</b>: ${esc(T(x.why))}`).join('<br>');
      return `<tr><th scope="row">${esc(T(AREA_NAME[a]))}</th><td>${orig}</td><td>${reb}</td><td class="${miss ? 'miss' : ''}">${miss || esc(T('None'))}</td></tr>`;
    }).join('');
    $('#inputsTable').innerHTML = `<thead><tr><th scope="col">${esc(T('Area'))}</th><th scope="col">${esc(T('Original 2022 (ACS 2015–2019 and others)'))}</th><th scope="col">${esc(T('Updated {window} (ACS and current sources)', { window: w }))}</th><th scope="col">${esc(T('Left out of the updated version, and why'))}</th></tr></thead><tbody>${rows}</tbody>`;
    const C = W.doc.checks, part = C.partial_inputs, D = C.definitions, nh = D.health_without_hospital;
    const byGeo = new Map(W.fc.features.map(f => [f.properties.geoid, f.properties])), gs = nh.geoids || [];
    const placeOf = (code) => { const mine = gs.filter(g => g.slice(2, 5) === code), p = byGeo.get(mine[0]) || {}; return mine.length === 1 ? `${p.barrio} (${p.municipality})` : p.municipality || code; };   // a municipio, or the one barrio of it (Isla de Mona)
    $('#inputsNote').textContent = T('The updated version reads the inputs the observatory already holds for barrios (acs_barrio.json) and five more tables of the same survey period (public assistance, year built, computers, broadband and school enrollment). The environment, hospital, severe housing problems and street inputs come from the observatory\'s local conditions (conditions_barrio.json), each in its own source\'s latest vintage. The original does not say which survey cells it used for each input, so the two versions can define an input slightly differently (for example, the original counts {orig_nc}% of households in the average barrio without a computer, the updated version {reb_nc}%).', { orig_nc: fmt(C.means.o_no_computer_pct, 0), reb_nc: fmt(C.means.no_computer_pct, 0) })
      + ' ' + T('Barrios ranked with an input missing in the updated version: {list}.', { list: AREAS.filter(a => a !== 'overall' && part[a]).map(a => T('{n} in {area}', { n: fmt(part[a]), area: T(AREA_NAME[a]).toLowerCase() })).join(', ') })
      + ' ' + T('{n} barrios with a health level have no drive time to a hospital, because no road leads from them to one ({munis}): their health level uses disability and health insurance only, which leaves out how far they are from hospital care.', { n: fmt(nh.barrios), munis: nh.municipios.map(placeOf).join(', ') });
    const diff = M.rebuild.filter(x => x.note), n = (k, ver) => fmt(D[k][ver]);
    const counts = { impaired_water_flag: T('Barrios flagged: {reb} of {rr} in the updated version, {orig} of {ro} in the original.', { reb: n('impaired_water', 'rebuild'), rr: n('ranked', 'rebuild'), orig: n('impaired_water', 'orig'), ro: n('ranked', 'orig') }),
      landfill_flag: T('Barrios flagged: {reb} in the updated version, {orig} in the original.', { reb: n('landfill', 'rebuild'), orig: n('landfill', 'orig') }),
      nonattainment_flag: T('Barrios flagged: {reb} in the updated version, {orig} in the original.', { reb: n('nonattainment', 'rebuild'), orig: n('nonattainment', 'orig') }),
      rmp_sites: T('Facilities counted in the barrios: {reb} in the updated version, {orig} in the original.', { reb: n('rmp_sites', 'rebuild'), orig: n('rmp_sites', 'orig') }) };
    $('#inputsDiff').innerHTML = diff.map(x => `<li><b>${esc(T(x.label))}.</b> ${esc(T(x.note))}${counts[x.key] ? ' ' + esc(counts[x.key]) : ''}</li>`).join('');
  }
  function renderContext() {   // what the updated version shows beside the index, and why it is not an input (from wcrp_rvi.py: CONTEXT_NOTE, HAZARD_NOTE)
    const M = W.doc.method; if (!M.context) return;
    $('#contextList').innerHTML = [
      `<b>${esc(T('Age groups'))}.</b> ${esc(M.context.map(x => T(x.label)).join('; '))}. ${esc(T(M.context_note))}`,
      `<b>${esc(T('Landslide susceptibility'))}.</b> ${esc((M.hazards || []).map(x => T(x.label)).join('; '))}. ${esc(T(M.hazards_note))}`,
    ].map(x => `<li>${x}</li>`).join('');
  }
  function renderRepro() {
    const R = W.doc.checks.reproduced, rows = [['econ', 'econ'], ['edu', 'edu'], ['envir', 'envir'], ['health', 'health'], ['housing', 'housing'], ['housing_two_sub_indicators', 'housing'], ['infra', 'infra'], ['overall', 'overall']];
    $('#reproLede').textContent = T('Applied to the original\'s own published inputs, the method as written here should give back the original\'s published index. It does for overall, education, health, housing and infrastructure: the order of the barrios is the same (rank correlation 1.00) and almost every barrio keeps its level. It does not for economy and environment, whose published inputs do not give back their published index; the white paper does not explain the difference. Housing matches when its three inputs are added together, not as the two sub-indicators the white paper describes.');
    const H = R.econ_income_as_higher_no_unemployment;
    $('#reproHypo').textContent = H ? T('A possible explanation for economy, to confirm with Hunter College: the published economy index is much closer to one built from public assistance, poverty and per capita income, with higher income counted as more vulnerable and without unemployment (rank correlation {h} instead of {e}; {same}% of barrios keep their level). If that is how it was computed, the published economy index counts income the wrong way round and leaves out unemployment. The updated version keeps the method the white paper describes.', { h: fmt(H.spearman, 2), e: fmt(R.econ.spearman, 2), same: fmt(H.same_rank_pct, 0) }) : '';
    $('#reproTable').innerHTML = `<thead><tr><th scope="col">${esc(T('Area'))}</th><th scope="col" class="num">${esc(T('Rank correlation with the published index'))}</th><th scope="col" class="num">${esc(T('Barrios with the same level'))}</th></tr></thead><tbody>`
      + rows.map(([k, a]) => `<tr><th scope="row">${esc(T(AREA_NAME[a]))}${k === 'housing_two_sub_indicators' ? ` <small>(${esc(T('as two sub-indicators'))})</small>` : ''}</th><td class="num">${R[k].spearman == null ? '—' : fmt(R[k].spearman, 2)}</td><td class="num">${pct(R[k].same_rank_pct)}</td></tr>`).join('') + '</tbody>';
  }
  function renderErrors() {
    const E = W.doc.checks.known_errors, pr = E.econ_pr_columns;
    $('#errorsList').innerHTML = [
      Th('<b>Mislabelled comparison columns.</b> The dashboard compares each barrio with its municipio and with Puerto Rico. In the economy panel the municipio column shows unemployment under the label "public assistance", public assistance under "poverty" and poverty under "unemployed", and the Puerto Rico column shows {pa}% (public assistance) as poverty, which is {pov}%. The housing panel\'s municipio column is shifted too. The barrio values are labelled correctly. This page shows only barrio values.', { pa: fmt(pr.public_assistance, 1), pov: fmt(pr.poverty, 1) }),
      Th('<b>Lead-paint shares above 100%.</b> The municipio values of the lead-paint indicator (homes built before 1960) run from {lo}% to {hi}%; {n} municipio values are above 100%, which is impossible for a share. The barrio values used in the index are all at or below 100%.', { lo: fmt(E.lead_paint_municipio_range[0], 1), hi: fmt(E.lead_paint_municipio_range[1], 1), n: fmt(E.lead_paint_municipio_over_100) }),
      Th('<b>Homes built before 1990.</b> The share reaches {max}% in {n} barrios of the original.', { max: fmt(E.built_pre1990_barrio_max, 1), n: fmt(E.built_pre1990_barrio_over_100) }),
      Th('<b>No license.</b> The ArcGIS services that publish the original state no license or access terms (their license and access fields are empty). The observatory shows the values as published and credits Hunter College and FPR. FPR publishes them with the program\'s approval. That is not an open license: to re-use them, ask the Puerto Rico Department of Housing and FPR.'),
    ].map(x => `<li>${x}</li>`).join('');
  }
  function renderSources() {
    const o = W.doc.versions.orig, svc = (o.services || [])[0] || {};
    $('#srcOrig').innerHTML = Th('<b>Original.</b> Hunter College for Foundation for Puerto Rico, Risk and Vulnerability Indicators (RVI) dashboard, WCRP program: services All_Indicator and Master_Data_Table_Update of the PlanningCDBG account on ArcGIS Online, data last edited {edited}, read on {read}. License: none stated. <a href="{url}" target="_blank" rel="noopener">Service</a>.', { edited: svc.data_last_edit || '2022-03', read: o.harvested, url: svc.url || '#' });
    $('#srcRebuild').innerHTML = Th('<b>Updated {window}.</b> US Census Bureau, American Community Survey 5-year estimates {window} (tables B01003, B15002, B17001, B18101, B19057, B23025, B25002, B25034, B25044, B27010, B28002, B28003, B14003), barrio rows; method of the RVI white paper (Hunter College, 2021), applied by the PR Data Observatory (wcrp_rvi.py).', { window: W.doc.versions.rebuild.window })
      + ' ' + Th('Local conditions by barrio (<a href="dictionary.html#conditions.epa_tri">data dictionary</a>): US EPA Toxics Release Inventory (reporting year 2024), Facility Registry Service (Risk Management Plan facilities, Superfund sites), ATTAINS (2024 cycle), Green Book and Landfill Methane Outreach Program; US Department of Housing and Urban Development, CHAS 2016–2020 by census tract; US Census Bureau, TIGER/Line 2026; drive time to a general hospital (CMS list) along © OpenStreetMap roads (ODbL), estimated by the observatory.');
  }

  // ── Start (wcrp.js: once the script, its Spanish, the outlines and the page's files are in) ──
  function init() {
    if (W.ver === 'change') V.last = 'orig';
    initControls(); initMap(); render(); if (W.muni) zoomMuni();
    if ($('#wmComm').checked) toggleCommunities(true);
    renderComparison(); renderInputs(); renderContext(); renderRepro(); renderErrors(); renderSources();
    $('#wmStatus').textContent = '';
  }
  function setMuni() {   // wcrp.js: the page's one municipio changed (here, or in the Social Capital summary)
    $('#wmMuni').value = W.muni; render(); zoomMuni();
  }
  return { init, setMuni, showChange };
})();
