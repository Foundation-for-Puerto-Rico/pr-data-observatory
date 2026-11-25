/* PR Data Observatory — Economy tab for the 2D map.
   Loaded after network.js; uses the page's map, S, Data (plan.js), featuresAt, toast and the tab helpers.

   The idea: any number of economic datasets on the map at once, the way an analyst would want them.
   - Shaded (choropleth) layers for rates and levels; two shaded layers together become a bivariate map.
   - Sized symbols for counts (jobs, dollars), which a shaded map would misrepresent.
   - Per-layer normalization (per 1,000 residents, per km², share of Puerto Rico, share of jobs, location quotient, index, change since a base year),
     inflation adjustment for dollars, quantile / equal-interval / natural-breaks classes, colors fixed across years.
   - One year control for everything; a workbench (inspector, table, scatter, trend) linked to the map; every dataset's sources one click away.
   Data: data/economy_series.json (economy_series.py) plus the population, income and poverty series from data/housing_series.json.
   Language: every visible text goes through T / Tn / Th (docs/i18n.md). The labels and groups that come from the data files stay English in EC.V and are translated where they are shown
   (T(v.label), T(v.group)); ids, the URL state and sorting never depend on the language. */

const E = Core.engine.create();   // the shared layer engine (js/core, docs/engine.md): the datasets, the period each shows, normalization, classes, legend and pop-up text. This file is the tab's screen and its handlers.
const EC = { ready: false, loading: null, layers: [], seq: 0, selected: null, bench: { open: false, tab: 'inspect' }, charts: {}, trend: new Set(), centroids: [], panes: false };
// the engine's state is read and written through EC, so the rest of this file reads as it always did
['V', 'extras', 'sources', 'notes', 'built', 'snapYear', 'cpi', 'cpiRef', 'cache', 'year', 'base'].forEach(k => Object.defineProperty(EC, k, { get: () => E[k], set: (v) => { E[k] = v; }, enumerable: true }));
Object.defineProperties(EC, { NM: { get: () => E.geo.names }, PR: { get: () => E.geo.pr }, ids: { get: () => E.geo.ids }, area: { get: () => E.geo.area } });
const EC_LINES = Core.palettes.LINES;
const ecNorm = (s) => norm(s);
const ecLc = (s) => E.lc(s);

// ── Data ─────────────────────────────────────────────────────────────────────
async function ecLoad() {
  if (EC.ready) return;
  if (!EC.loading) EC.loading = (async () => {
    const index = withIndex(S.catalog).catch(() => null);   // the index of the dictionary (catalog_index.json), alongside: the levels below the municipio each dataset has (Catalog.levelsOf); without it, none are offered
    const lab = I18N.load('econ_terrain').catch(() => null);   // the Spanish names of the terrain and climate groups load with the data, not with the map (docs/i18n.md 15); without them, English
    const [{ docs, failed }] = await Promise.all([Core.datasets.fetchFiles(Data.json), lab]);   // every dataset file, in the order of js/core/datasets.js (the area profiles read the same list); an optional file that fails leaves its datasets out, and the page says so
    Core.datasets.apply(E, docs, S.muni, +((S.meta.generated_at || '').slice(0, 4)) || 2026);
    await index;
    EC.centroids = EC.NM.slice(0, EC.PR).map(n => { const f = S.muniFc.features.find(x => x.properties.municipality === n); return f ? ecCentroid(f.geometry) : null; });
    EC.ready = true; EC.failed = failed;
    if (failed.length) toast(T('Some data did not load, so some datasets are missing. Reload the page to try again.'), 8000);
  })().catch(e => { EC.loading = null; throw e; });
  return EC.loading;
}
const safeDecode = (s) => { try { return decodeURIComponent(s); } catch { return ''; } };   // a link with a broken % must not leave the tab empty
const ecYears = () => E.years();
const ecResolve = (key) => E.resolve(key);
const ecArr = (key, y) => E.arr(key, y);
const cpiFactor = (y) => E.cpiFactor(y);
const popAt = (y) => E.pop(y);

// ── Normalization and formats: Core.normalize and Core.format ────────────────
const ecNormOptions = (v) => Core.normalize.options(v);
const ecOut = (L) => E.out(L);
const ecCalc = (L, y) => E.calc(L, y);
const ecFmt = (L, x, compact) => E.fmt(L, x, compact);

// ── Classes and colors: Core.classify and Core.palettes ─────────────────────
const ecPool = (L, current) => E.pool(L, current);
const ecBreaks = (L, current, classes = 5) => E.breaks(L, current, classes);
const ecClass = (b, v, classes = 5) => Core.classify.classOf(b, v, classes);
const ecRampColors = (L) => E.ramp(L);

// ── Layers ───────────────────────────────────────────────────────────────────
function ecAdd(key, mode, opts = {}) {
  const L = E.makeLayer(key, mode, opts, EC.layers); if (!L) return null;
  if (L.error) { toast(T('A map can shade two datasets together (a bivariate map). Remove one shaded layer first, or show this one as symbols.'), 6000); return null; }
  L.id = ++EC.seq; EC.layers.push(L); return L;
}
const ecTitle = (L, y) => E.title(L, y);
function ecEval() { EC.eval = E.evaluate(EC.layers); }   // each layer's year and values for this render
function ecRender() {
  if (EC.ix) ecIxApply(EC.ix, false);   // the composite follows the year control: its inputs are read again
  ecEval(); ecRenderMap(); ecRenderLegend(); ecRenderLayers(); ecSyncBrowse(); ecRenderBench(); ecWriteHash();
  const n = EC.layers.length, s = $('#ecStatus'); if (s) s.textContent = n ? Tn(n, '{n} layer on the map', '{n} layers on the map') : T('No layers on the map');
  Core.activelayers.changed();   // the "layers on" chip
  document.body.classList.toggle('econ-on', EC.layers.some(l => l.visible)); document.body.classList.toggle('econ-fill', EC.layers.some(l => l.visible && l.mode === 'fill')); document.body.classList.toggle('econ-active', ecClaims());
}
function ecPanes() {
  if (EC.panes) return; EC.panes = true;
  [['econfill', 356], ['echatch', 358], ['econsym', 394], ['econsel', 396]].forEach(([k, z]) => { map.createPane(k); map.getPane(k).style.zIndex = z; map.getPane(k).style.pointerEvents = 'none'; });
  EC.selLayer = L.geoJSON(null, { pane: 'econsel', interactive: false, style: { color: '#2A2E2E', weight: 3, fill: false } }).addTo(map);
  EC.symGroup = L.layerGroup().addTo(map);
}
function ecFills() { return EC.layers.filter(l => l.mode === 'fill' && l.visible && EC.eval[l.id] && EC.eval[l.id].a); }
function ecRenderMap() {
  ecPanes();
  let fills = ecFills();
  const bar = ecBar();
  ecLevelDraw(bar); if (bar) fills = [];
  // shaded layer: one sheet whose colors come from the first (or the first two, as a bivariate map) visible shaded layers
  const colors = {};
  if (fills.length) E.fillColors(fills, EC.eval).forEach((c, i) => { colors[EC.NM[i]] = c; });
  if (fills.length) {
    if (!EC.fillLayer) EC.fillLayer = L.geoJSON(S.muniFc, { pane: 'econfill', interactive: false, style: () => ({ color: '#fff', weight: .8, fillColor: Core.palettes.NOVAL, fillOpacity: .85 }) });
    if (!map.hasLayer(EC.fillLayer)) EC.fillLayer.addTo(map);
    EC.fillLayer.setStyle(f => ({ color: '#fff', weight: .8, fillColor: colors[f.properties.municipality] || Core.palettes.NOVAL, fillOpacity: fills[0].opacity }));
  } else if (EC.fillLayer && map.hasLayer(EC.fillLayer)) map.removeLayer(EC.fillLayer);
  ecHatch(fills.length ? E.flagged(fills.slice(0, 2), EC.eval) : []);   // places whose value is less reliable are hatched over their color
  // symbols
  EC.symGroup.clearLayers();
  EC.layers.filter(l => l.mode === 'symbol' && l.visible && EC.eval[l.id] && EC.eval[l.id].a).forEach(L => {
    const rel = E.reliability(L, EC.eval[L.id]).flagged;   // a less reliable value gets a dashed dark outline
    const ring = ecFills().length > 0;   // over a shaded map (municipio or barrio) the symbols are hollow rings with a white halo, so the colors under them stay readable (review 2026-11-05); alone they are filled
    E.symbols(L, EC.eval[L.id], isMobile()).rows.filter(r => EC.centroids[r.i]).forEach(r => {
      const o = { pane: 'econsym', interactive: false, radius: r.r, dashArray: rel[r.i] ? '3 3' : null };
      if (ring) EC.symGroup.addLayer(window.L.circleMarker(EC.centroids[r.i], { ...o, color: '#fff', weight: 4.5, fill: false, dashArray: null }));
      EC.symGroup.addLayer(window.L.circleMarker(EC.centroids[r.i], ring ? { ...o, color: rel[r.i] ? '#2A2E2E' : r.fill, weight: 2, fill: false } : { ...o, color: rel[r.i] ? '#2A2E2E' : '#fff', weight: rel[r.i] ? 1.6 : 1.2, fillColor: r.fill, fillOpacity: L.opacity }));
    });
  });
  if (EC.selected != null) EC.selLayer.clearLayers().addData(S.muniFc.features.filter(f => f.properties.municipality === EC.NM[EC.selected]));
}

const ecBar = () => { const f = ecFills(); return f.length === 1 && f[0].level === 'barrio' ? f[0] : null; };
// Scripts loaded on first use, in order. One promise per file, shared by every view that needs it (Core.scenario serves two), so a file still loading or
// already run is never added again (its top-level const would throw); a failed one is removed and forgotten, so the next try loads it.
const ecJs = {};
const ecScripts = (files) => files.reduce((p, src) => p.then(() => ecJs[src] || (ecJs[src] = new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); delete ecJs[src]; fail(new Error(src)); }; document.body.appendChild(s); }))), Promise.resolve());
function ecLevelDraw(L) {   // a shaded layer by barrio: js/econ_level.js and its Spanish (I18N.load), loaded on first use
  if (typeof EconLevel !== 'undefined' && (EC.lvOk || !L)) return EconLevel.draw(L);
  if (L) (EC.lvP = EC.lvP || allIn([I18N.load('econ_level'), ecScripts(['js/econ_level.js?v=8'])]).then(() => { EC.lvOk = true; }, e => { EC.lvP = null; throw e; })).then(ecRender, () => toast(T('The barrio values could not be loaded. Check your connection and try again.')));
}
// Places whose value is less reliable (reliability.js) are hatched over their color: a pattern and not a color, so it reads in any color vision and in print; a dark line with a white one beside it, so it shows on pale and dark colors alike. `places` are indexes.
function ecHatch(places) {
  if (!places.length) { if (EC.hatchLayer && map.hasLayer(EC.hatchLayer)) map.removeLayer(EC.hatchLayer); return; }
  const names = new Set(places.map(i => EC.NM[i]));
  if (!EC.hatchLayer) EC.hatchLayer = L.geoJSON(null, { pane: 'echatch', interactive: false, renderer: L.svg({ pane: 'echatch' }), style: { stroke: false, fill: true, fillColor: 'url(#ec-hatch)', fillOpacity: 1 } });
  EC.hatchLayer.clearLayers().addData(S.muniFc.features.filter(f => names.has(f.properties.municipality)));
  if (!map.hasLayer(EC.hatchLayer)) EC.hatchLayer.addTo(map);
  const svg = map.getPane('echatch').querySelector('svg');
  if (svg && !svg.querySelector('#ec-hatch')) svg.insertAdjacentHTML('afterbegin', '<defs><pattern id="ec-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#2A2E2E" stroke-opacity=".6" stroke-width="1.4"/><line x1="2.2" y1="0" x2="2.2" y2="6" stroke="#fff" stroke-opacity=".6" stroke-width="1"/></pattern></defs>');
}

// ── Legend ───────────────────────────────────────────────────────────────────
const ecChip = (L) => E.chip(L, EC.eval[L.id]);
function ecRenderLegend() {
  const box = $('#econLegend'); if (!box) return;
  if (EC.legendClosed === undefined) EC.legendClosed = isMobile();   // on a phone the legend starts folded so the map stays visible
  const parts = Core.stack.blocks(E, EC.layers, EC.eval, isMobile()), bar = ecBar();
  if (bar && EC.lvOk) parts[0] = EconLevel.legend(bar);
  box.innerHTML = parts.length ? `<button type="button" class="el-toggle" aria-expanded="${!EC.legendClosed}" id="elToggle"><span class="ms-icon" aria-hidden="true">layers</span>${esc(T('Legend ({n})', { n: parts.length }))}<span class="ms-icon el-chev" aria-hidden="true">${EC.legendClosed ? 'keyboard_arrow_down' : 'keyboard_arrow_up'}</span></button><div class="el-body" ${EC.legendClosed ? 'hidden' : ''}>${parts.join('')}<button type="button" class="linklike el-table" data-ecbench="table">${esc(T('View the map as a table'))}</button></div>` : '';   // every map can be read as a table (WCAG): the workbench's Table view
  box.classList.toggle('show', !!parts.length); ecPlaceLegend();
  document.body.style.setProperty('--ec-stack', parts.length && !box.classList.contains('docked') ? (parseFloat(getComputedStyle(box).bottom) || 34) + box.offsetHeight + 8 + 'px' : '34px');   // where the map's own legend goes: above this one
  const t = $('#elToggle'); if (t) t.onclick = () => { EC.legendClosed = !EC.legendClosed; ecRenderLegend(); };
}
// wide screen: the legend sits at the top of the open On the map panel, else on the map
function ecPlaceLegend() {
  const box = $('#econLegend'), d = $('#alDock'), w = $('#alWrap'); if (!box || !d || !w) return;
  if (!EC.legObs) (EC.legObs = new MutationObserver(ecPlaceLegend)).observe(w, { attributes: true, subtree: true, attributeFilter: ['class', 'hidden'] });
  const on = w.classList.contains('pinned') && w.classList.contains('open') && !d.hidden, host = on ? d : $('#map');
  if (box.parentNode !== host) on ? d.prepend(box) : host.appendChild(box);
  box.classList.toggle('docked', on);
}

// ── Hover, click, inspector ──────────────────────────────────────────────────
const ecClaims = () => !!(EC.ready && EC.tab && EC.layers.some(l => l.visible));
const ecSwatch = (L) => Core.popup.swatch(E, L);
const ecValue = (L, i) => Core.popup.value(E, L, EC.eval[L.id], i);
function ecInspect(i, compact) {
  return Core.popup.inspect(E, EC.layers, EC.eval, i, compact, (k) => {
    const top = (EC.extras.top_sector || {})[String(ecResolve('qcew_jobs').y)], ts = top && top[k];
    return ts ? `<div class="note">${Th('Largest employer group: <b>{name}</b> ({pct}% of jobs).', { name: T(ts[0]), pct: ts[1] })}</div>` : '';
  });
}
const ecSpark = (L, i) => Core.popup.spark(E, L, EC.eval[L.id], i);
function ecHover(e) {
  const h = $('#econHover'); if (!h) return;
  if (!ecClaims() || isMobile()) { h.classList.remove('show'); return; }
  const f = featuresAt(S.muniFc, e.latlng, () => true, 1)[0]; if (!f) { h.classList.remove('show'); return; }
  h.innerHTML = Core.popup.hover(E, EC.layers, EC.eval, EC.NM.indexOf(f.properties.municipality)); h.classList.add('show');
}
function ecSelect(i, latlng, openBench) {
  EC.selected = i; EC.trend.add(i); EC.trend.add(EC.PR);
  ecRenderMap();
  if (latlng) L.popup({ maxWidth: 380, className: 'ec-pop' }).setLatLng(latlng).setContent(`<div class="pop">${ecInspect(i, true)}<div class="links"><button type="button" class="linklike" data-ecbench="1">${esc(T('Open in the workbench'))}</button> · <a href="profile.html?area=${EC.ids[i]}">${esc(T('Area profile'))}</a></div></div>`).openOn(map);
  if (openBench) ecBenchOpen('inspect');
  else if (EC.bench.open) ecRenderBench();
}

// ── Panel ────────────────────────────────────────────────────────────────────
const ecGroupsOrder = () => Core.datasets.sortGroups(E.list().map(v => v.group));   // the themes of the layer menu, the visitor economy last (core/datasets.js sortGroups)
function ecSkeleton() {
  return `<div class="note ec-lede">${esc(T("Analyze the data on the map: shade municipalities by a rate, size symbols by a count, and combine as many layers as you like. Start from a view, or find datasets by topic in Home. Click the map for every layer's value at that place."))}</div>
    <div class="ec-year" role="group" aria-label="${esc(T('Year for all layers'))}"><span class="ec-yl">${esc(T('Year'))}</span><button type="button" class="icon-btn small" id="ecPrev" aria-label="${esc(T('Previous year'))}"><span class="ms-icon" aria-hidden="true">chevron_left</span></button><select id="ecYear" aria-label="${esc(T('Year'))}"></select><button type="button" class="icon-btn small" id="ecNext" aria-label="${esc(T('Next year'))}"><span class="ms-icon" aria-hidden="true">chevron_right</span></button><button type="button" class="btn small" id="ecPlay"><span class="ms-icon" aria-hidden="true">play_arrow</span><span>${esc(T('Play'))}</span></button></div>
    <input type="range" id="ecRange" aria-label="${esc(T('Year slider'))}" class="ec-range">
    <div class="ec-year ec-base"><label for="ecBase">${esc(T('Change measured from'))}</label><select id="ecBase"></select></div>
    <h2 class="sec">${esc(T('Start from a view'))}</h2><div class="ec-presets" id="ecPresets"></div>
    <h2 class="sec">${esc(T('Layers on the map'))} <span class="ec-count" id="ecCount"></span></h2><div id="ecLayers"></div><div class="note" id="ecStatus" aria-live="polite"></div>
    <div class="btn-row"><button type="button" class="btn primary" id="ecBenchBtn"><span class="ms-icon" aria-hidden="true">table_view</span>${esc(T('Workbench'))}</button><button type="button" class="btn" id="ecClear">${esc(T('Clear all'))}</button><button type="button" class="btn" id="ecCopy"><span class="ms-icon" aria-hidden="true">link</span>${esc(T('Copy link'))}</button></div>
    <h2 class="sec">${esc(T('Also show on the map'))}</h2><div id="ecContext"></div>
    <h2 class="sec">${esc(T('Datasets'))} <span class="ec-count" id="ecDsCount"></span></h2>
    <div class="ctrl"><label for="ecFind" class="sr-only">${esc(T('Find a dataset'))}</label><input type="search" id="ecFind" class="ec-find" placeholder="${esc(T('Find a dataset: jobs, pay, poverty…'))}" autocomplete="off"></div>
    <div id="ecBrowse"></div>
    <h2 class="sec">${esc(T('Reading these maps'))}</h2>
    <div class="note">${Th('<b>Shade rates, size counts.</b> A shaded map of jobs would mostly show how big a municipality is. Counts start as sized symbols; shade them per 1,000 residents, per km² or as a share to compare places. Classes stay fixed across years so a color means the same thing in every year.')}</div>
    <div class="note">${Th('<b>Where the work is versus where people live.</b> Jobs, wages and establishments are counted at the workplace (QCEW); income, poverty and commuting describe residents (ACS). San Juan and Guaynabo look rich in jobs partly because workers commute in. “Jobs per employed resident” shows it.')}</div>
    <div class="note">${Th('<b>Dollars.</b> Tick “inflation-adjusted” on a dollar layer to compare years in {year} dollars. The index is the US one, not a Puerto Rico index, so it is only an approximation of how prices changed on the island. ACS dollars are already in the final year of each five-year window.', { year: EC.cpiRef || T('recent') })}</div>
    <div class="note">${Th('<b>Small places and withheld data.</b> Survey figures (ACS, LAUS) are noisy for small municipalities; margins of error (±) are shown where published. The jobs data hide cells that would identify one employer, so some sectors are blank in small municipalities. The informal economy is not in the jobs data; self-employed residents are a rough window on it.')}</div>
    <div class="note">${Th('<b>Hatching.</b> A hatched municipality has a less reliable value: a margin of error above 30% of the estimate, or fewer than 10 counted. The legend says which, and the values in the pop-up are in italics.')}</div>
    <h2 class="sec">${esc(T('Sources'))}</h2><div id="ecSources"></div>`;
}
function ecRenderPresets() {
  const P = [[T('Jobs and pay'), [['qcew_avg_pay', 'fill', {}], ['qcew_jobs', 'symbol', {}]]], [T('Poverty and unemployment'), [['poverty_pct', 'fill', {}], ['laus_unemp_rate', 'fill', {}], ['laus_unemployed', 'symbol', {}]]], [T('Job centers and commuting'), [['jobs_per_employed_resident', 'fill', {}], ['commute_45plus_pct', 'fill', {}], ['qcew_jobs', 'symbol', {}]], ['lyRoutes']], [T('Public money'), [['fed_awards_total', 'fill', { norm: 'perCapita' }], ['fema_pa_obligated', 'symbol', {}]]], [T('Government and self-employment'), [['gov_job_share_pct', 'fill', {}], ['self_employed_pct', 'fill', {}]]], [T('Tourism economy'), [['tourism_jobs', 'fill', { norm: 'shareJobs' }], ['accommodation_jobs', 'symbol', {}]], ['lyPlaces']]];   // the visitor economy last, as everywhere
  $('#ecPresets').innerHTML = P.map((p, i) => `<button type="button" class="chip" data-preset="${i}" style="background:#BDE0F2;color:#205D7B">${esc(p[0])}</button>`).join('');
  $('#ecPresets').onclick = e => { const b = e.target.closest('[data-preset]'); if (!b) return; const p = P[+b.dataset.preset]; ecIxApply(null); EC.layers = []; p[1].forEach(([k, m, o]) => { if (EC.V[k]) ecAdd(k, m, o); }); ecSetContext(p[2] || []); ecRender(); toast(Tn(EC.layers.length, '{name}: {n} layer. Click the map to see them all at a place.', '{name}: {n} layers. Click the map to see them all at a place.', { name: p[0] }), 5000); };
}
function ecRenderLayers() {
  const box = $('#ecLayers'); if (!box) return;
  $('#ecCount').textContent = EC.layers.length ? `(${EC.layers.length})` : '';
  if (!EC.layers.length) { box.innerHTML = `<div class="empty">${esc(T('No layers yet. Pick a view above or add a dataset below.'))}</div>`; return; }
  EC.layers.forEach(L => { L.levels = L.mode === 'fill' && (areaHas(L.key, 'barrio') || (EC.V[L.key] || {}).barrioFile || (EC.V[L.key] || {}).level) ? ['barrio'] : null; if (!L.levels) L.level = ''; });   // js/econ_level.js; barrioFile: a dataset with its own barrio file (docs/conditions.md); level: a dataset with barrio values only, loaded with the others (WCRP, docs/wcrp.md)
  box.innerHTML = EC.layers.map((L, k) => Core.panel.layerCard(E, L, k, EC.layers.length, EC.eval[L.id], ecOn, EC.layers.filter(l => l.mode === 'fill').length >= 2)).join('');   // the card's Shaded and Symbol switches are the dataset list's two checkboxes
}
const ecOn = (key, mode) => EC.layers.some(l => l.key === key && l.mode === mode);
function ecToggle(k, mode, on, at) {   // dataset k on the map as shading or symbols ('fill', 'symbol'), or that taken off: the dataset list and the Shaded and Symbol switches of the cards; a new layer from a card goes under it (at). False when a third shaded layer was refused (ecAdd says why)
  const name = T(EC.V[k].label);
  if (on && !ecOn(k, mode)) { const L = ecAdd(k, mode); if (!L) { ecRender(); return false; } if (at != null) EC.layers.splice(at, 0, EC.layers.pop()); }
  if (!on) EC.layers = EC.layers.filter(l => !(l.key === k && l.mode === mode));
  ecRender();   // then the message, which ecRender would overwrite with the layer count
  const st = $('#ecStatus'); if (st) st.textContent = !on ? T('Removed {name} from the map.', { name }) : mode === 'fill' ? T('Added {name} as a shaded layer.', { name }) : T('Added {name} as symbols.', { name });
  return true;
}
function ecSyncBrowse() { document.querySelectorAll('#ecBrowse .ec-ds').forEach(ds => ds.querySelectorAll('input[data-add]').forEach(c => { c.checked = ecOn(ds.dataset.key, c.dataset.add); })); }   // in place, so open groups stay open
function ecRenderBrowse() {
  const r = Core.panel.browse(E, $('#ecFind').value, ecGroupsOrder(), 'Jobs and employers', ecOn);
  $('#ecBrowse').innerHTML = r.html; $('#ecDsCount').textContent = `(${r.n})`;
}
function ecRenderContext() {
  const items = [['lyMuni', T('Municipal boundaries')], ['lyBarrios', 'Barrios'], ['lyProt', T('Protected areas')], ['lyLanduse', T('Land use 2015')], ['lyFlood', T('Flood zones')], ['lyRoutes', T('Transit routes')], ['lyStops', T('Transit stops')], ['lyPlaces', T('Tourism places')]];   // the Layers tab's names, in its order (js/core/layers.js)
  $('#ecContext').innerHTML = items.map(([id, label]) => `<label class="ec-ctx"><input type="checkbox" data-proxy="${id}" ${$('#' + id) && $('#' + id).checked ? 'checked' : ''}> ${esc(label)}</label>`).join('');
  $('#ecContext').onchange = e => { const c = e.target.closest('[data-proxy]'); if (!c) return; const el = $('#' + c.dataset.proxy); if (el) { el.checked = c.checked; el.dispatchEvent(new Event('change')); } };
}
function ecSetContext(on) {   // exactly these context layers stay on (the municipality outline is left as it is), so a view is not buried under 2,000 place pins
  ['lyBarrios', 'lyFlood', 'lyProt', 'lyLanduse', 'lyRoutes', 'lyPlaces'].forEach(id => { const el = $('#' + id), want = on.includes(id); if (el && el.checked !== want) { el.checked = want; el.dispatchEvent(new Event('change')); } });
  ['lyStops', 'lyHubs', 'lyTaxi', 'lyBridges', 'lyAirports', 'lyFerries', 'lyEvCharge', 'lyOz', 'lyPowerLines', 'lyPlants', 'lyPubHousing', 'lyLihtc', 'lyReservoirs', 'lyBroadband', 'lyRivers', 'lyGroundwater', 'lyRain', 'lyFire', 'lyPolice', 'lyTownhalls', 'lyLibraries', 'lySchools', 'lyHistoric'].forEach(id => { const el = $('#' + id); if (el && on.includes(id) && !el.checked) { el.checked = true; el.dispatchEvent(new Event('change')); } });   // the point layers the chat names: switched on, never off, as on the 3D view (ask3d.js)
  ecContextSync();
}
function ecContextSync() { document.querySelectorAll('#ecContext [data-proxy]').forEach(c => { const el = $('#' + c.dataset.proxy); if (el) c.checked = el.checked; }); }
function ecRenderSources() {
  const used = new Set(); Object.values(EC.V).forEach(v => (v.sources || []).forEach(s => used.add(s)));
  $('#ecSources').innerHTML = [...used].map(id => EC.sources[id]).filter(Boolean).map(s => `<div class="src"><b>${esc(s.name)}</b><span>${esc(s.license || '')}</span><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>${(s.extra || []).map(x => `<a href="${esc(x[1])}" target="_blank" rel="noopener">${esc(x[0])}</a>`).join('')}</div>`).join('');
}
function ecInitYear() {
  const ys = ecYears(), max = ys[ys.length - 1], min = ys[0];
  $('#ecYear').innerHTML = `<option value="latest">${esc(T('Latest'))}</option>` + [...ys].reverse().map(y => `<option>${y}</option>`).join('');
  const r = $('#ecRange'); r.min = min; r.max = max; r.step = 1; r.value = max;
  $('#ecBase').innerHTML = ys.filter(y => y < max).map(y => `<option>${y}</option>`).join(''); $('#ecBase').value = String(EC.base);
  const set = (y, keep) => { EC.year = y == null || y === 'latest' ? null : +y; $('#ecYear').value = EC.year == null ? 'latest' : String(EC.year); r.value = EC.year == null ? max : EC.year; if (!keep) ecStopPlay(); ecRender(); };
  $('#ecYear').onchange = e => set(e.target.value); r.oninput = e => set(+e.target.value);
  const step = d => set(Math.min(max, Math.max(min, (EC.year == null ? max : EC.year) + d)));
  $('#ecPrev').onclick = () => step(-1); $('#ecNext').onclick = () => step(1);
  $('#ecBase').onchange = e => { EC.base = +e.target.value; ecRender(); };
  EC.setYear = set;
  $('#ecPlay').onclick = () => { if (EC.timer) { ecStopPlay(); return; } let y = EC.year == null || EC.year >= max ? min : EC.year; set(y, true); $('#ecPlay').innerHTML = `<span class="ms-icon" aria-hidden="true">pause</span><span>${esc(T('Pause'))}</span>`; EC.timer = setInterval(() => { y++; if (y > max) { ecStopPlay(); return; } set(y, true); }, 1400); };
}
function ecStopPlay() { if (EC.timer) { clearInterval(EC.timer); EC.timer = null; } const p = $('#ecPlay'); if (p) p.innerHTML = `<span class="ms-icon" aria-hidden="true">play_arrow</span><span>${esc(T('Play'))}</span>`; }
function ecWire() {
  $('#ecFind').oninput = ecRenderBrowse;
  $('#ecBrowse').onclick = e => { const ds = e.target.closest('.ec-ds'); if (ds && e.target.closest('[data-act=info]')) ecInfo(ds.dataset.key); };
  $('#ecBrowse').onchange = e => {   // a checkbox puts that dataset on the map as shading or symbols, or takes it off
    const c = e.target.closest('input[data-add]'), ds = c && c.closest('.ec-ds'); if (!ds) return;
    if (!ecToggle(ds.dataset.key, c.dataset.add, c.checked)) { c.checked = false; return; }
    if (c.checked && isMobile()) toast(T('Added {name}. Close the panel to see the map.', { name: T(EC.V[ds.dataset.key].label) }), 4000);
  };
  $('#ecLayers').addEventListener('click', e => { const card = e.target.closest('.ec-layer'); if (!card) return; const i = EC.layers.findIndex(l => l.id === +card.dataset.id), L = EC.layers[i]; const b = e.target.closest('[data-act]'); if (!b || !L) return;
    const act = b.dataset.act, byKeyboard = e.detail === 0;   // Enter or Space on a button is a click without a pointer
    if (({ vis: () => { L.visible = !L.visible; }, up: () => { if (i > 0) [EC.layers[i - 1], EC.layers[i]] = [EC.layers[i], EC.layers[i - 1]]; }, down: () => { if (i < EC.layers.length - 1) [EC.layers[i + 1], EC.layers[i]] = [EC.layers[i], EC.layers[i + 1]]; }, del: () => { EC.layers.splice(i, 1); }, info: () => { ecInfo(L.key); return 'noRender'; }, mode: () => { ecToggle(L.key, b.dataset.mode, b.getAttribute('aria-pressed') !== 'true', i + 1); return 'noRender'; } })[act]() === 'noRender') { if (act === 'mode') {   // the card was rebuilt, or went with its layer: focus goes to the same switch of the dataset's card that is left
      const at = EC.layers.find(l => l.key === L.key), to = at && document.querySelector(`#ecLayers .ec-layer[data-id="${at.id}"] [data-mode="${b.dataset.mode}"]`); (to || $('#ecBenchBtn')).focus(); } return; }
    ecRender();
    if (byKeyboard) {   // the card was rebuilt: put focus back on the same button, or on the button of the layer that took its place; a move button that is disabled now (the layer is at an end) hands focus to the other one, then to Hide
      const at = act === 'del' ? EC.layers[Math.min(i, EC.layers.length - 1)] : L, find = a => at && document.querySelector(`#ecLayers .ec-layer[data-id="${at.id}"] [data-act="${a}"]`);
      const to = [act, act === 'up' ? 'down' : act === 'down' ? 'up' : 'vis', 'vis'].map(find).find(el => el && !el.disabled) || $('#ecBenchBtn');
      if (to) to.focus();
    } });
  const focusables = () => [...document.querySelectorAll('#ecLayers a[href], #ecLayers button:not([disabled]), #ecLayers input:not([disabled]), #ecLayers select:not([disabled]), #ecLayers summary')];
  $('#ecLayers').addEventListener('keydown', e => { EC.key = { key: e.key, shift: e.shiftKey }; }, true); document.addEventListener('pointerdown', () => { EC.key = null; }, true);   // a click elsewhere (the place search, say) must not send focus back into a card
  const onField = e => { const f = e.target.closest('[data-f]'); if (!f) return; const kbd = EC.key, at = kbd ? focusables().indexOf(f) : -1; const card = e.target.closest('.ec-layer'), L = EC.layers.find(l => l.id === +card.dataset.id); if (!L) return; const k = f.dataset.f; L[k] = f.type === 'checkbox' ? f.checked : f.type === 'range' ? +f.value : f.value; if (k === 'classes' && L.classes === 'manual' && !L.breaks) L.breaks = E.manualDefault(L, EC.eval[L.id].y); if (k === 'norm' && L.norm === 'change' && EC.base >= (ecYears().pop() || 0)) toast(T('Pick an earlier base year in "Change measured from".'), 4000); if (k === 'breaks' && L.classes === 'manual' && L.breaks && !Core.classify.parseBreaks(L.breaks, 5)) toast(T('Type four numbers in rising order, for example 10, 20, 30, 40. Until then the classes are quantiles.'), 6000); const open = card.querySelector('details').open; ecRender(); const nc = $(`.ec-layer[data-id="${L.id}"] details`); if (nc && open) nc.open = true;
    if (kbd && at >= 0) { const to = focusables()[at + (kbd.key === 'Tab' ? (kbd.shift ? -1 : 1) : 0)]; if (to) to.focus(); }
    EC.key = null; };
  $('#ecLayers').addEventListener('change', onField); $('#ecLayers').addEventListener('input', e => { if (e.target.type === 'range') onField(e); });
  $('#ecClear').onclick = () => { ecIxApply(null); EC.layers = []; EC.selected = null; EC.selLayer.clearLayers(); ecRender(); };
  $('#ecCopy').onclick = async () => { ecWriteHash(true); try { await navigator.clipboard.writeText(location.href); toast(T('Link copied: it reopens these layers and this year.'), 4000); } catch { toast(T('Copy the address from the browser bar: it holds your layers.'), 5000); } };
  $('#ecBenchBtn').onclick = () => EC.bench.open ? ecBenchClose() : ecBenchOpen('inspect');
  let resizing; window.addEventListener('resize', () => { clearTimeout(resizing); resizing = setTimeout(ecRenderLegend, 150); });   // the legend's height depends on the width: the map's own legend stacks above it
}

// ── Workbench ────────────────────────────────────────────────────────────────
function ecBenchOpen(tab) { if (typeof LanduseView !== 'undefined') LanduseView.close(); EC.bench.open = true; if (tab) EC.bench.tab = tab; document.body.classList.add('bench-open'); $('#econBench').hidden = false; setTimeout(() => map.invalidateSize(), 60); ecRenderBench(); }
function ecBenchClose() { EC.bench.open = false; document.body.classList.remove('bench-open'); $('#econBench').hidden = true; Object.values(EC.charts).forEach(c => c && c.destroy()); EC.charts = {}; setTimeout(() => map.invalidateSize(), 60); }
function ecVisible() { return EC.layers.filter(l => l.visible && EC.eval[l.id] && EC.eval[l.id].a); }
function ecRenderBench() {
  if (!EC.bench.open) return;
  const tabs = [['inspect', T('Inspector')], ['table', T('Table')], ['scatter', T('Scatter')], ['trend', T('Trend')], ['matrix', T('Correlations')], ['multiples', T('Small multiples')], ['swipe', T('Compare two maps')], ['composite', T('Composite')], ['scenarios', T('Scenarios')], ['study', T('Study areas')]], t = EC.bench.tab;
  $('#econBench').innerHTML = `<div class="eb-head"><div class="eb-tabs" role="tablist" aria-label="${esc(T('Workbench views'))}">${tabs.map(([id, l]) => `<button type="button" role="tab" aria-selected="${id === t}" class="${id === t ? 'active' : ''}" data-bt="${id}">${l}</button>`).join('')}</div><span class="eb-year">${esc(EC.year == null ? T('Latest year') : EC.year)}</span><button type="button" class="icon-btn small" id="ebClose" aria-label="${esc(T('Close the workbench'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div><div class="eb-body" id="ebBody" role="tabpanel"></div>`;
  $('#ebClose').onclick = ecBenchClose;
  $('#econBench').querySelector('.eb-tabs').onclick = e => { const b = e.target.closest('[data-bt]'); if (b) { EC.bench.tab = b.dataset.bt; ecRenderBench(); } };
  Object.values(EC.charts).forEach(c => c && c.destroy()); EC.charts = {};
  if (WB_VIEWS.has(t) && !EC.wbOk) { ecBenchLater(t); return; }
  ({ inspect: ecBenchInspect, table: ecBenchTable, scatter: () => ecBenchScatter(), trend: () => ecBenchTrend(), matrix: () => ecBenchMatrix(), multiples: () => ecBenchMultiples(), swipe: () => ecBenchSwipe(), composite: () => ecBenchComposite(), scenarios: ecBenchScenarios, study: ecBenchStudy })[t]();   // the arrows: js/workbench.js may not be in yet
}
const ecMuniSelect = (id, sel) => `<select id="${id}" aria-label="${esc(T('Municipality'))}">${EC.NM.map((n, i) => `<option value="${i}"${i === sel ? ' selected' : ''}>${esc(n)}</option>`).join('')}</select>`;
function ecBenchInspect() {
  const i = EC.selected == null ? EC.PR : EC.selected;
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>${esc(T('Place'))} ${ecMuniSelect('ebMuni', i)}</label><span class="note">${esc(T('Every visible layer at once, beside Puerto Rico as a whole, with the trend over the years. Click the map or pick a place.'))}</span></div><div class="eb-scroll">${ecInspect(i, false)}</div>`;
  $('#ebMuni').onchange = e => { const k = +e.target.value; EC.selected = k === EC.PR ? null : k; EC.trend.add(k); ecRenderMap(); ecRenderBench(); };
  $('#ebBody').onclick = ecBenchClicks;
}
function ecBenchClicks(e) { const b = e.target.closest('[data-ecinfo]'); if (b) ecInfo(b.dataset.ecinfo); }
function ecBenchTable() {
  const vis = ecVisible(); if (!vis.length) { $('#ebBody').innerHTML = `<div class="empty">${esc(T('Add a layer to see the table.'))}</div>`; return; }
  const st = EC.tbl = EC.tbl || { col: -1, dir: -1, find: '' };
  let rows = EC.NM.map((n, i) => ({ n, i, vals: vis.map(L => EC.eval[L.id].a[i]) }));
  const pr = rows.pop(); if (st.find) rows = rows.filter(r => ecNorm(r.n).includes(ecNorm(st.find)));
  if (st.col >= 0) rows.sort((a, b) => ((a.vals[st.col] == null) - (b.vals[st.col] == null)) || st.dir * ((a.vals[st.col] ?? 0) - (b.vals[st.col] ?? 0))); else rows.sort((a, b) => a.n.localeCompare(b.n, 'es'));
  rows = [pr, ...rows];
  const rel = vis.map(L => E.reliability(L, EC.eval[L.id]));
  const sL = st.col >= 0 && vis[st.col], sm = sL && E.moe(sL, EC.eval[sL.id].y), rr = sm && Core.stats.rankRanges(EC.eval[sL.id].a, sm, EC.PR), nn = rr ? rr.filter(Boolean).length : 0;
  const rk = (i) => { const t = Core.stats.rangeAt(rr, i, nn, st.dir < 0); return t && `<small class="rk" title="${esc(T('The ranks it could hold, given the margins of error (90%)'))}">${t}</small>`; };
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>${esc(T('Find'))} <input type="search" id="ebFind" value="${esc(st.find)}" placeholder="${esc(T('Municipality'))}"></label><span class="ec-count">${esc(Tn(rows.length - 1, '{n} municipality', '{n} municipalities'))} · ${esc(Tn(vis.length, '{n} layer', '{n} layers'))}</span><button type="button" class="btn small" id="ebCsv"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download CSV'))}</button></div>${rel.some(x => x.n.flagged) ? `<div class="note rel-note">${esc(Core.reliability.flagKey())}</div>` : ''}<div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('Table of the visible layers by municipality, scrollable'))}"><table class="ec-tbl wide"><thead><tr><th scope="col"><button type="button" class="sortb" data-c="-1">${esc(T('Municipality'))}${st.col < 0 ? ' ▲' : ''}</button></th>${vis.map((L, c) => `<th scope="col" class="num"><button type="button" class="sortb" data-c="${c}">${esc(T(EC.V[L.key].label))}${st.col === c ? (st.dir > 0 ? ' ▲' : ' ▼') : ''}</button><small>${esc(ecChip(L))}${L.norm !== 'value' ? ' · ' + esc(ecLc(T((ecNormOptions(EC.V[L.key]).find(o => o[0] === L.norm) || [0, L.norm])[1]))) : ''}</small></th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr class="${r.i === EC.PR ? 'total' : ''} ${r.i === EC.selected ? 'me' : ''}"><th scope="row">${esc(r.n)}</th>${vis.map((L, c) => `<td class="num${rel[c].flagged[r.i] ? ' unrel' : ''}">${esc(r.vals[c] == null && E.missing(L, r.i) || ecFmt(L, r.vals[c]))}${rel[c].flagged[r.i] ? `<span class="sr-only"> (${esc(Core.reliability.lessReliable())})</span>` : ''}${c === st.col && r.i !== EC.PR ? rk(r.i) : ''}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  $('#ebFind').oninput = e => { st.find = e.target.value; ecBenchTable(); $('#ebFind').focus(); };
  $('#ebBody').querySelector('thead').onclick = e => { const b = e.target.closest('.sortb'); if (!b) return; const c = +b.dataset.c; st.dir = st.col === c ? -st.dir : (c < 0 ? 1 : -1); st.col = c; ecBenchTable(); };
  $('#ebCsv').onclick = () => ecSaveCsv('pr_economy_layers.csv', ['GEOID', T('Municipality'), ...vis.map(L => `${T(EC.V[L.key].label)} (${ecChip(L)}; ${L.norm})`)], EC.NM.map((n, i) => [EC.ids[i], n, ...vis.map(L => EC.eval[L.id].a[i])]));
  $('#ebBody').onclick = ecBenchClicks;
}
// Chart.js is loaded the first time the Scatter or Trend view opens, not with the page (plan item 13: the map's first load stays within its budget; docs/performance.md)
const CHART_JS = { src: 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js', integrity: 'sha384-bs/nf9FbdNouRbMiFcrcZfLXYPKiPaGVGplVbv7dLGECccEXDW+S3zjqSKR5ZEaD' };
function ecChartLib() {
  if (typeof Chart !== 'undefined') return Promise.resolve();
  return EC.chartP || (EC.chartP = new Promise((ok, fail) => { const s = document.createElement('script'); Object.assign(s, CHART_JS, { crossOrigin: 'anonymous', onload: ok, onerror: () => { EC.chartP = null; s.remove(); fail(new Error('chart')); } }); document.head.appendChild(s); }));
}
/** True when Chart.js is there; else shows that it is loading, draws the view again when it arrives, or says it could not load. */
function ecNeedChart(tab) {
  if (typeof Chart !== 'undefined') return true;
  $('#ebBody').innerHTML = `<div class="empty" role="status">${esc(T('Loading the chart…'))}</div>`;
  ecChartLib().then(() => { if (EC.bench.open && EC.bench.tab === tab) ecRenderBench(); }, () => { if (EC.bench.open && EC.bench.tab === tab) $('#ebBody').innerHTML = `<div class="empty" role="status">${esc(T('The chart could not be loaded. Check your connection and open the view again.'))}</div>`; });
  return false;
}
// The other views (Scatter, Trend, Correlations, Small multiples, Compare two maps, Composite) are in js/workbench.js: it loads with core/minimap.js and its Spanish
// the first time one of them opens, so the map's first load does not carry them (docs/performance.md). Scatter and Trend start loading Chart.js at the same time.
const WB_VIEWS = new Set(['scatter', 'trend', 'matrix', 'multiples', 'swipe', 'composite']);
function ecWorkbenchLib() {
  if (EC.wbOk) return Promise.resolve();
  return EC.wbP || (EC.wbP = allIn([I18N.load('workbench'), ecScripts(['js/core/minimap.js?v=1', CX_JS, 'js/workbench.js?v=2'])]).then(() => { EC.wbOk = true; }, e => { EC.wbP = null; throw e; }));
}
function ecBenchLater(tab) {   // "Loading…" until the view's script is in, then the view; a message when it could not be loaded
  const body = $('#ebBody');
  body.innerHTML = `<div class="empty" role="status">${esc(T('Loading…'))}</div>`;
  if (tab === 'scatter' || tab === 'trend') ecChartLib().catch(() => null);   // ecNeedChart says so if it fails
  ecWorkbenchLib().then(() => { if (EC.bench.open && EC.bench.tab === tab) ecRenderBench(); }, () => { if (EC.bench.open && EC.bench.tab === tab) body.innerHTML = `<div class="empty" role="status">${esc(T('The view could not be loaded. Check your connection and open it again.'))}</div>`; });
}

// ── Workbench: the composite index a person builds (plan B6; Core.composite; docs/workbench.md) ──
const TK = (s) => s;   // an English text that is translated where it is shown, with T(): the language tool reads it like T()
const IX = 'user_composite', IX_LABEL = TK('User-built composite, not an official index');
const IX_T = { z: TK('z-scores (standard deviations from the average municipality)'), mm: TK('0 to 100 between the lowest and the highest municipality'), pct: TK('percentile rank (0 to 100)') };
function ecIxInputs(spec) {   // each input as its shaded layer would show it: the normalization a shaded map starts with, in the year the year control picks
  return spec.items.map(it => { const v = EC.V[it.key], n = Core.normalize.defaultNorm(v, 'fill'), r = E.values(it.key, { year: E.year, norm: n }); return { v, norm: n, normLabel: E.normLabel({ key: it.key, norm: n }), year: r ? r.year : null, a: r ? r.values : new Array(EC.PR + 1).fill(null) }; });
}
function ecIxMethod(spec, ins) {
  const list = spec.items.map((it, k) => `${T(ins[k].v.label)} (${ecLc(ins[k].normLabel)}, ${ins[k].year ?? '—'}; ${it.dir < 0 ? T('lower is better') : T('higher is better')}; ${T('weight {w}', { w: it.w })})`).join('; ');
  return T('User-built composite, not an official index. Each input is put on one scale across the 78 municipalities ({scale}), turned round where a lower value is better, and averaged with its weight. A municipality with less than 80% of the weight present is left blank. Inputs: {list}.', { scale: T(IX_T[spec.t]), list });
}
const CX_JS = 'js/core/composite.js?v=3';   // loaded on first use, off the map's first load (review 2026-11-05: room for the map's own fixes)
function ecIxApply(spec, addLayer) {   // the composite as a dataset of the engine, so it can be shaded, inspected, put in the table and linked like any other
  if (spec && !Core.composite) { ecScripts([CX_JS]).then(() => { ecIxApply(spec, addLayer); ecRender(); }); return; }
  EC.ix = spec;
  if (!spec) { delete E.V[IX]; E.cache = {}; EC.layers = EC.layers.filter(l => l.key !== IX); return; }
  const ins = ecIxInputs(spec), res = Core.composite.compute(ins.map(x => x.a), spec, EC.PR), Y = Math.max(...ins.map(x => x.year || 0)) || E.snapYear;
  E.add({ key: IX, group: 'Composite', label: IX_LABEL, unit: '', d: spec.t === 'z' ? 2 : 1, type: 'ratio', static: true, noIsland: true, time: { type: 'snapshot' }, family: 'derived', ys: [Y], years: { [Y]: res.score },
    sources: [...new Set(ins.flatMap(x => x.v.sources || []))], ref: T('Computed in your browser from the inputs listed in its definition'), definition: ecIxMethod(spec, ins), dictId: 'measures.composite_index', ix: { spec, ins, res } });
  if (addLayer && !EC.layers.some(l => l.key === IX) && EC.layers.filter(l => l.mode === 'fill').length < 2) ecAdd(IX, 'fill', { ramp: 'green', classes: 'quantile' });   // a map shades two datasets at most: the person is told (ecBenchComposite)
}

// ── Workbench: scenarios and model outputs (plan item 15; js/scenarios.js and Core.scenario, loaded the first time the view opens; docs/scenarios.md) ──
function ecScenarioLib() {   // the scripts and their Spanish (I18N.load): the view renders once both are in
  if (EC.scOk) return Promise.resolve();
  return EC.scP || (EC.scP = allIn([I18N.load('scenarios'), ecScripts(['js/core/scenario.js?v=2', 'js/scenarios.js?v=3'])]).then(() => { EC.scOk = true; }, e => { EC.scP = null; throw e; }));
}
function ecBenchScenarios() {
  const body = $('#ebBody');
  if (!EC.scOk) {
    body.innerHTML = `<div class="empty" role="status">${esc(T('Loading the scenarios…'))}</div>`;
    ecScenarioLib().then(() => { if (EC.bench.open && EC.bench.tab === 'scenarios') ecRenderBench(); }, () => { if (EC.bench.open && EC.bench.tab === 'scenarios') body.innerHTML = `<div class="empty" role="status">${esc(T('The scenarios could not be loaded. Check your connection and open the view again.'))}</div>`; });
    return;
  }
  Scenarios.render(body);
}

// ── Workbench: study areas (plan item 16, C4; js/studyareas.js and Core.study, loaded the first time the view opens; docs/study-areas.md) ──
function ecStudyLib() {   // Core.scenario holds the contact-details check; the Scenarios view may have loaded it (ecScripts shares it then)
  if (EC.saOk) return Promise.resolve();
  return EC.saP || (EC.saP = allIn([I18N.load('studyareas'), ecScripts(['js/core/scenario.js?v=2', 'js/core/study.js?v=8', 'js/studyareas.js?v=17'])]).then(() => { EC.saOk = true; }, e => { EC.saP = null; throw e; }));
}
function ecBenchStudy() {
  const body = $('#ebBody');
  if (!EC.saOk) {
    body.innerHTML = `<div class="empty" role="status">${esc(T('Loading the study areas…'))}</div>`;
    ecStudyLib().then(() => { if (EC.bench.open && EC.bench.tab === 'study') ecRenderBench(); }, () => { if (EC.bench.open && EC.bench.tab === 'study') body.innerHTML = `<div class="empty" role="status">${esc(T('The study areas could not be loaded. Check your connection and open the view again.'))}</div>`; });
    return;
  }
  StudyAreas.render(body);
}

// ── Dataset information and sources ──────────────────────────────────────────
function ecSaveCsv(name, header, rows) {
  const q = v => { if (v == null) return ''; let s = String(v); if (/^[=+\-@\t\r]/.test(s) && typeof v !== 'number') s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const csv = '﻿' + [header, ...rows].map(r => r.map(q).join(',')).join('\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
// ── Areas below the municipio (plan item 7, docs/small-area.md) ──────────────
// A level is read when a person asks for it: the file (0.5 to 1.5 MB compressed) and the crosswalk that names its areas. The values then answer E.series(layer, period, level); the map shows municipios only.
const SMALL_FILES = { barrio: 'acs_barrio.json', tract: 'acs_tract.json', 'block-group': 'acs_blockgroup.json' };
const SMALL_NAMES = { barrio: 'Barrios', tract: 'Census tracts', 'block-group': 'Block groups' };
EC.levelLoads = {};
function ecLoadLevel(level) {
  if (!SMALL_FILES[level]) return Promise.reject(new Error('no such level: ' + level));
  if (EC.levelLoads[level]) return EC.levelLoads[level];
  return EC.levelLoads[level] = (async () => {
    await ecLoad();
    const [doc, cw] = await Promise.all([Data.json('data/' + SMALL_FILES[level]), Data.json('data/geo/crosswalk.json')]);
    const F = Object.fromEntries(cw.fields.map((f, i) => [f, i])), by = new Map(cw.units[level].map(r => [r[F.id], r]));
    Core.adapters.levelFile(E, doc, { level, names: doc.geo.ids.map(id => { const r = by.get(id); return r ? { es: r[F.name_es], en: r[F.name_en] } : { es: id, en: id }; }) });
    return doc;
  })().catch(e => { delete EC.levelLoads[level]; throw e; });
}
// A dataset that brings its own barrio values names their file (barrioFile, conditions.py): read the first time such a layer is shaded by barrio, as a level of the datasets it holds
EC.fileLoads = {};
function ecLoadLevelFile(file) {
  return EC.fileLoads[file] || (EC.fileLoads[file] = (async () => { await ecLoad(); Core.adapters.levelFile(E, await Data.json('data/' + file), { level: 'barrio' }); })().catch(e => { delete EC.fileLoads[file]; throw e; }));
}
async function ecLevelCsv(key, level) {
  await ecLoadLevel(level);
  const t = Core.adapters.levelTable(E, key, level, { name: (n) => n && (I18N.lang === 'es' ? n.es : n.en), municipality: (id) => { const i = EC.ids.indexOf(id.slice(0, 5)); return i < 0 ? '' : EC.NM[i]; } });
  if (!t) { const err = new Error('no values below the municipality'); err.noLevel = true; throw err; }
  ecSaveCsv(`pr_${level}_${key}.csv`, t.header, t.rows);
}
/** What the status line of the area buttons says: nothing while another file is still loading; when the last one ends, how every request ended (named by its level when there are several). */
function ecAreaStatus(outcomes, busy) {
  if (busy || !outcomes.length) return null;
  return outcomes.length === 1 ? outcomes[0].msg : outcomes.map(o => `${T(SMALL_NAMES[o.level])}: ${o.msg}`).join(' ');
}
const areaLvls = key => Core.adapters.levelsFor(EC.V[key], (typeof Catalog !== 'undefined' && Catalog.levelsOf(E.dictId(key))) || []), areaHas = (key, l) => areaLvls(key).includes(l);
function areaLevels(key) {   // the buttons for the levels below the municipio this dataset has values for: the dictionary says which, and only ACS datasets are in the level files
  const levels = areaLvls(key);   // coarse to fine; Catalog is a script-level const, not a property of window
  return levels.length ? `<div class="ds-meta"><div>${esc(T('Also for areas smaller than the municipality, with margins of error (CSV):'))}</div><div class="btn-row">${levels.map(l => `<button type="button" class="btn small" data-eclevel="${l}" aria-label="${esc(T('Download {area} (CSV)', { area: T(SMALL_NAMES[l]) }))}"><span class="ms-icon" aria-hidden="true">download</span>${esc(T(SMALL_NAMES[l]))}</button>`).join('')}</div><div class="note" id="ecLvStatus" role="status" aria-live="polite"></div><div class="note">${esc(T('Survey estimates for small areas are rough: read each value with its margin of error.'))}</div>${levels.includes('block-group') ? `<div class="note">${esc(T('In Excel, the long codes of block groups (GEOID) can show as 7.2E+11: import the column as text.'))}</div>` : ''}</div>` : '';
}
function ecInfo(key) {
  const v = EC.V[key]; if (!v) return;
  const dlg = $('#ecDlg'), srcs = (v.sources || []).map(id => EC.sources[id]).filter(Boolean);
  const yrs = v.static ? T('A single snapshot ({year})', { year: v.ys[0] }) : Tn(v.ys.length, '{from}–{to} ({n} year)', '{from}–{to} ({n} years)', { from: v.ys[0], to: v.ys[v.ys.length - 1] });
  const unpl = key.startsWith('fed_') && !key.startsWith('fed_prog_') && EC.extras.fed_unplaced_share ? `<div class="ds-meta"><div>${Th('<b>Share of federal awards that name no municipality, by fiscal year (all award types):</b> {list}', { list: Object.entries(EC.extras.fed_unplaced_share).sort().map(([y, s]) => `${y}: ${s}%`).join(' · ') })}</div></div>` : '';
  const fema = key === 'fema_pa_obligated' && EC.extras.fema_pa_statewide_share ? `<div class="ds-meta"><div>${Th('<b>Share recorded as statewide, by declaration year:</b> {list}', { list: Object.entries(EC.extras.fema_pa_statewide_share).sort().map(([y, s]) => `${y}: ${s}%`).join(' · ') })}</div></div>` : '';
  const sw = key !== 'fema_pa_obligated' && (EC.extras.statewide_share || {})[key] ? `<div class="ds-meta"><div>${Th('<b>Share that cannot be placed in a municipality (statewide), by year:</b> {list}', { list: Object.entries(EC.extras.statewide_share[key]).sort().map(([y, s]) => `${y}: ${s}%`).join(' · ') })}</div></div>` : '';
  const extra = { qcew_jobs: T('Jobs at employers covered by unemployment insurance. Self-employed and informal workers are not counted. Some small-municipality cells are withheld.'), laus_unemp_rate: T('Model-based and smoothed over time and across areas.') }[key] || '';
  $('#ecDlgTitle').textContent = T(v.label);
  $('#ecDlgBody').innerHTML = `<div class="ds-tags"><span class="tag paper">${esc(T(v.group))}</span><span class="tag live">${esc(v.tag ? T(v.tag) : v.type === 'count' ? T('count') : v.type === 'total$' ? T('dollar total') : v.type === 'level$' ? T('dollar level') : v.type === 'rate' ? T('rate') : v.type === 'ratio' ? T('ratio') : v.type)}</span></div>${I18N.lang !== 'en' && key !== IX ? `<div class="note">${esc(T('The definition and reference are in English for now.'))}</div>` : ''}
    <div class="ds-def">${I18N.en(esc(v.definition))}</div>${extra ? `<div class="ds-def">${esc(extra)}</div>` : ''}
    <div class="ds-meta"><div>${Th('<b>Reference:</b> {ref}', { ref: v.ref || '' })}</div><div>${Th('<b>Years:</b> {years}', { years: yrs })}${v.moe ? ' · ' + esc(T('margins of error at 90% confidence are published and shown in the inspector')) : ''}</div><div>${Th('<b>Geography:</b> 78 municipalities and Puerto Rico · <b>Data built:</b> {built}', { built: v.built || EC.built || '' })}</div>${v.unit === '$' ? `<div>${Th('<b>Dollars:</b> as published for each year. Tick "inflation-adjusted" on the layer to compare years in constant dollars (US CPI-U, which is not a Puerto Rico index).')}</div>` : ''}</div>${fema}${sw}${unpl}
    <div class="ds-meta"><div>${Th('<b>Full entry:</b> <a href="{href}">meaning, method, cautions and how to cite in the data dictionary</a>', { href: 'dictionary.html#' + E.dictId(key) })}</div></div>
    <h3 class="sec">${esc(T('Cautions'))}</h3><ul class="ds-cautions">${Core.reliability.cautions(v).map(c => `<li>${esc(c.text)}</li>`).join('')}</ul>
    <h3 class="sec">${esc(T('Sources'))}</h3>${srcs.length ? srcs.map(s => `<div class="src"><b>${esc(s.name)}</b><span>${esc(s.license || '')}${s.note ? ' · ' + esc(s.note) : ''}</span><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>${(s.extra || []).map(x => `<a href="${esc(x[1])}" target="_blank" rel="noopener">${esc(x[0])}</a>`).join('')}</div>`).join('') : `<div class="note">${esc(T('Source details are on the Housing page for this series.'))}</div>`}
    <div class="btn-row"><button type="button" class="btn" data-ecadd="fill">${esc(T('Shade the map'))}</button><button type="button" class="btn" data-ecadd="symbol">${esc(T('Show as symbols'))}</button><button type="button" class="btn" id="ecDlCsv"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download all years (CSV)'))}</button></div>${areaLevels(key)}`;
  $('#ecDlgBody').onclick = e => { const b = e.target.closest('[data-ecadd]'); if (b) { const L = ecAdd(key, b.dataset.ecadd); if (L) { ecRender(); dlg.close(); showTab('economy', { open: false }); } } };
  const outcomes = [];
  $('#ecDlgBody').querySelectorAll('[data-eclevel]').forEach(b => { b.onclick = async () => {   // aria-disabled, not disabled: focus stays on the button; the message is in the window, which is the only part of the page a screen reader reads while it is open
    if (b.getAttribute('aria-disabled') === 'true') return;
    const st = $('#ecLvStatus'); b.setAttribute('aria-disabled', 'true'); b.setAttribute('aria-busy', 'true'); if (st) st.textContent = T('Loading the areas…');
    let msg;
    try { await ecLevelCsv(key, b.dataset.eclevel); msg = T('The download started.'); } catch (err) { msg = err && err.noLevel ? T('There are no values for this dataset below the municipality.') : T('The areas could not be loaded. Try again in a moment.'); } finally { b.removeAttribute('aria-disabled'); b.removeAttribute('aria-busy'); }
    outcomes.push({ level: b.dataset.eclevel, msg });
    const said = ecAreaStatus(outcomes, !!$('#ecDlgBody').querySelector('[data-eclevel][aria-busy]'));   // while another file is still loading its message stays; the last one to end says how every request ended, for a screen reader too
    if (st && said != null) { st.textContent = said; outcomes.length = 0; }
  }; });
  $('#ecDlCsv').onclick = () => { const hasM = !!v.moe; ecSaveCsv(`pr_economy_${key}.csv`, ['GEOID', T('Municipality'), ...v.ys.flatMap(y => hasM ? [String(y), T('{year} margin of error', { year: y })] : [String(y)])], EC.NM.map((n, i) => [EC.ids[i], n, ...v.ys.flatMap(y => hasM ? [(v.years[y] || [])[i], ((v.moe || {})[y] || [])[i]] : [(v.years[y] || [])[i]])])); };
  if (!dlg.open) dlg.showModal();
}

// ── URL state ────────────────────────────────────────────────────────────────
const ecEncode = () => E.encode(EC.layers);
function ecWriteHash() { if (typeof writeHash === 'function') writeHash(); }
function ecRestore(str, year, base) {
  EC.layers = [];
  E.decode(str).forEach(({ key, mode, opts }) => { const L = ecAdd(key, mode, opts), ok = (n) => ecNormOptions(EC.V[key]).some(o => o[0] === n); if (L && !ok(L.norm)) { const d = Core.normalize.defaultNorm(EC.V[key], L.mode); L.norm = ok(d) ? d : 'value'; } });   // a view the dataset does not offer (an old link: the population per 1,000 residents) becomes its own start, as in Core.engine restore()
  if (base && /^\d{4}$/.test(base)) EC.base = +base;
  if (year && /^\d{4}$/.test(year)) EC.year = +year;
}

// ── API for the chat and other tools ─────────────────────────────────────────
// datasets(), meta() and normOptions() return the English labels and groups (data): the caller translates them with T() where it shows them. fmt() and unitLabel() return text in the page language.
const ecApi = {
  async ready() { return !!(await econBoot()); },
  datasets() { return E.info(); },
  meta(key) { return EC.V[key] || null; },
  dictId(key) { return E.dictId(key); },
  places() { return EC.NM.slice(); },
  placeIndex(name) { return E.placeIndex(name); },
  placeId(name) { const i = E.placeIndex(name); return i >= 0 && i < EC.PR ? EC.ids[i] : null; },   // the five-digit code of a municipio (the area profile's ?area=)
  compose(keys) { if (!Core.composite) return void ecScripts([CX_JS]).then(() => ecApi.compose(keys));   EC.ixDraft = { t: 'z', items: keys.filter(k => EC.V[k] && k !== IX).slice(0, Core.composite.MAX_ITEMS).map(key => ({ key, dir: 0, w: 1 })) }; showTab('economy', { open: false }); ecBenchOpen('composite'); },   // the chat opens the composite builder with these inputs; the person sets directions and weights
  years: ecYears,
  base: () => EC.base,
  sources: () => EC.sources,
  popAt,
  values(key, o) { return E.values(key, o); },
  fmt(key, x, norm = 'value', real = false) { return ecFmt({ key, norm, real }, x); },
  moe(key, year) { return E.moe({ key, norm: 'value', real: false }, year) || null; },   // the 90% margins of a survey dataset, in the order of the places, or null
  notLoaded() { return EC.failed || []; },   // the optional files that did not load
  missing(key, i) { return E.missing({ key }, i); },   // what an empty place means for the dataset (a shortage area: "No area shortage designation"), or null
  normOptions: (key) => ecNormOptions(EC.V[key]),
  unitLabel(key, norm = 'value') { const o = ecOut({ key, norm }); return { suffix: o.suffix || '', unit: o.unit }; },
  defaultNorm(key, mode = 'fill') { return Core.normalize.defaultNorm(EC.V[key], mode); },
  state() { return { year: EC.year, base: EC.base, selected: EC.selected == null ? null : EC.NM[EC.selected], layers: EC.layers.map(l => ({ key: l.key, mode: l.mode, norm: l.norm, visible: l.visible, real: l.real })) }; },
  /* spec: { clear, layers:[{key, mode:'fill'|'symbol', norm, real, ramp}], year (number | null = latest), base, context:[ids], select:name, bench:'inspect'|'table'|'scatter'|'trend', info:key } */
  async show(spec) {
    if (!(await ecApi.ready())) return { applied: [], skipped: [{ reason: 'The economy data is not available.' }] };
    if (!spec.stay) showTab('economy', { open: false }); if (isMobile()) setPanel(false);   // stay: Explore, Rankings and old links keep their tab; the On the map panel lists the layer
    const applied = [], skipped = [];
    if (spec.clear !== false) { ecIxApply(null); EC.layers = []; }
    if (spec.base) { EC.base = spec.base; const bs = $('#ecBase'); if (bs) bs.value = String(EC.base); }
    if ('year' in spec) { const sel = $('#ecYear'); EC.setYear(spec.year == null ? null : spec.year, true); }
    for (const l of spec.layers || []) {
      const v = EC.V[l.key]; if (!v) { skipped.push({ key: l.key, reason: 'unknown dataset' }); continue; }
      let mode = l.mode || 'fill';
      if (mode === 'fill' && EC.layers.filter(x => x.mode === 'fill').length >= 2) mode = 'symbol';
      const opts = { ramp: l.ramp, real: !!l.real, classes: l.classes, fixed: l.fixed, level: l.level };
      if (l.norm && ecNormOptions(v).some(o => o[0] === l.norm)) opts.norm = l.norm;
      const L = ecAdd(l.key, mode, opts);
      if (L) applied.push({ key: l.key, mode: L.mode, norm: L.norm }); else skipped.push({ key: l.key, reason: 'too many shaded layers' });
    }
    if (spec.context) ecSetContext(spec.context);
    if (spec.select) { const i = ecApi.placeIndex(spec.select); if (i >= 0) { EC.selected = i; EC.trend.add(i); EC.trend.add(EC.PR); } }
    ecRender();
    if (spec.select && EC.selected != null && EC.centroids[EC.selected]) map.flyTo(EC.centroids[EC.selected], Math.max(map.getZoom(), 10), { duration: .8 });
    if (spec.bench) ecBenchOpen(spec.bench);
    if (spec.info) ecInfo(spec.info);
    return { applied, skipped };
  },
  clear(o = {}) { ecIxApply(null); EC.layers = []; if (o.scenario) EC.scenario = null; if (!o.keepPlace) { EC.selected = null; if (EC.selLayer) EC.selLayer.clearLayers(); } if (EC.booted) ecRender(); },
  // for the "layers on" chip (core/activelayers.js): the layers by name, one removed, and the state that "Turn all off" changes, kept for its Undo
  active: () => EC.layers.map(l => ({ id: l.id, name: T(EC.V[l.key].label) + (l.visible ? '' : ' ' + T('(hidden)')), group: `${T('Economy')} · ${l.mode === 'fill' ? T('Shaded') : T('Symbols')}` })),
  remove(id) { EC.layers = EC.layers.filter(l => l.id !== id); ecRender(); },
  snap: () => ({ layers: EC.layers.slice(), ix: EC.ix, sc: EC.scenario }),
  restore(s) { EC.scenario = s.sc; ecIxApply(s.ix || null, false); EC.layers = s.layers.slice(); if (EC.booted) ecRender(); },
  setYear(y) { EC.setYear(y == null ? null : y, true); },
  async levelSeries(key, level = 'barrio', year = null) {   // a dataset's values below the municipio (the chat's ranking of the barrios of a place), read the first time; null when it has none
    const v = EC.V[key]; if (!v || !(areaHas(key, level) || (level === 'barrio' && (v.barrioFile || v.level)))) return null;
    try { if (v.barrioFile) await ecLoadLevelFile(v.barrioFile); else if (!v.level) await ecLoadLevel(level); } catch { return null; }
    return E.series({ key, norm: 'value', real: false }, year, level);
  },
  benchOpen: ecBenchOpen, info: ecInfo, trendPlaces(list) { list.forEach(n => { const i = ecApi.placeIndex(n); if (i >= 0) EC.trend.add(i); }); },
};

// ── Start ────────────────────────────────────────────────────────────────────
function econBoot() {
  if (EC.bootP) return EC.bootP;
  EC.booted = true;
  return EC.bootP = (async () => {
    const root = $('#econRoot');
    try { await ecLoad(); } catch (e) { EC.booted = false; EC.bootP = null; root.innerHTML = `<div class="note">${esc(T('The economy data could not be loaded ({error}). Check your connection and open the tab again.', { error: e.message }))}</div>`; return false; }
    root.innerHTML = ecSkeleton();
    ecInitYear(); ecRenderPresets(); ecRenderBrowse(); ecRenderContext(); ecRenderSources(); ecWire();
    if (Core.activelayers.dock) {   // the year, the layer cards and their buttons live in the On the map panel (navigation plan, decision 81)
      const lay = $('#ecLayers'), head = lay.previousElementSibling, row = $('#ecStatus').nextElementSibling;
      Core.activelayers.dock([root.querySelector('.ec-year:not(.ec-base)'), $('#ecRange'), root.querySelector('.ec-base'), head, lay, $('#ecStatus'), row]);
      root.querySelector('.ec-lede').insertAdjacentHTML('afterend', `<div class="note ec-docked">${esc(T('The layers on the map, their year and their settings are in the On the map panel.'))} <button type="button" class="linklike" id="ecToPanel">${esc(T('Open the panel'))}</button></div>`);
      $('#ecToPanel').onclick = () => { if (window.ActiveLayers) ActiveLayers.open(); };
    }
    const h = EC.pending;   // the link the page opened with: the address has been rewritten since
    if (h.sc) { try { await ecScenarioLib(); await Scenarios.restore(safeDecode(h.sc)); } catch { /* the scenario is not in this browser: the layers of the link that need it are skipped */ } }   // a scenario's model outputs first: the layers of the link may shade them
    if (h.ix) { try { await ecScripts([CX_JS]); } catch { /* offline: the link opens without its composite */ } }
    if (h.ix && Core.composite) ecIxApply(Core.composite.decode(safeDecode(h.ix), k => k !== IX && !!EC.V[k]), false);   // the composite first: the layers of the link may shade it
    if (h.e) { ecRestore(safeDecode(h.e), h.ey, h.eb); $('#ecBase').value = String(EC.base); if (EC.year != null) { $('#ecYear').value = String(EC.year); $('#ecRange').value = EC.year; } }
    ecRender();
    if (/^(inspect|table|scatter|trend|composite)$/.test(h.wb || '')) ecBenchOpen(h.wb);   // a link from the 3D view's chat opens that workbench view
    else if (h.wc) ecApi.compose(safeDecode(h.wc).split(','));   // or the composite builder with those inputs (ecApi.compose keeps the known datasets)
    return true;
  })();
}
function econShown(name) {
  EC.tab = name === 'economy';
  if (EC.tab) { if (!EC.booted) econBoot(); else ecContextSync(); }
  else { const h = $('#econHover'); if (h) h.classList.remove('show'); }
  document.body.classList.toggle('econ-active', ecClaims());
}
function econInit() {
  const m = $('#map');
  m.insertAdjacentHTML('beforeend', `<div class="econ-legend" id="econLegend" aria-label="${esc(T('Economy layers legend'))}"></div><div class="econ-hover" id="econHover" aria-hidden="true"></div>`);
  document.body.insertAdjacentHTML('beforeend', `<section class="econ-bench" id="econBench" aria-label="${esc(T('Economy workbench'))}" hidden></section><dialog id="ecDlg" class="data-dlg" aria-labelledby="ecDlgTitle"><div class="dlg-head"><h2 id="ecDlgTitle"></h2><button type="button" class="icon-btn" id="ecDlgClose" aria-label="${esc(T('Close'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div><div class="dlg-body" id="ecDlgBody"></div></dialog>`);
  $('#ecDlgClose').onclick = () => $('#ecDlg').close(); $('#ecDlg').addEventListener('click', e => { if (e.target === $('#ecDlg')) $('#ecDlg').close(); });
  map.on('mousemove', e => { if (EC.raf) return; EC.raf = requestAnimationFrame(() => { EC.raf = null; ecHover(e); }); });
  map.on('mouseout', () => { const h = $('#econHover'); if (h) h.classList.remove('show'); });
  map.on('click', e => { if (!ecClaims()) return; if (typeof Plan !== 'undefined' && (Plan.picking >= 0 || Plan.clickMode)) return; const f = featuresAt(S.muniFc, e.latlng, () => true, 1)[0]; if (f) ecSelect(EC.NM.indexOf(f.properties.municipality), e.latlng, false); });
  const ecClick = e => { const y = e.target.closest('[data-ecyear]'); if (y) EC.setYear(+y.dataset.ecyear);   // the legend's "Match periods" (core/stack.js)
    const b = e.target.closest('[data-ecbench]'); if (b) { map.closePopup(); const v = b.dataset.ecbench; if (isMobile()) setPanel(false); ecBenchOpen(v === 'table' || v === 'study' ? v : 'inspect'); } const i = e.target.closest('[data-ecinfo]'); if (i && !e.target.closest('#econBench')) ecInfo(i.dataset.ecinfo); };
  document.addEventListener('click', ecClick);
  $('#econLegend').addEventListener('click', e => { ecClick(e); e.stopPropagation(); });   // docked in the On the map panel, whose clicks never reach the document (core/activelayers.js)
  const fromLink = !(window.ECON && window.ECON.shell) || !!window.ECON.fromLink;   // loaded for the link the page opened with, not later by another tab's need
  EC.pending = window.ECON && window.ECON.shell && window.ECON.opened ? window.ECON.opened : parseHash();   // the address the page opened with (js/econ_shell.js read it before the map rewrote it)
  window.ECON = { api: ecApi, claims: ecClaims, loadLevel: ecLoadLevel, loadLevelFile: ecLoadLevelFile, encode: () => EC.ready ? ecEncode() : (EC.pending.e ? safeDecode(EC.pending.e) : ''), extra: () => EC.ready ? [EC.year != null ? 'ey=' + EC.year : '', EC.base !== 2014 ? 'eb=' + EC.base : '', EC.ix ? 'ix=' + encodeURIComponent(Core.composite.encode(EC.ix)) : '', EC.scenario ? 'sc=' + encodeURIComponent(EC.scenario.id) : ''].filter(Boolean) : [EC.pending.ey ? 'ey=' + EC.pending.ey : '', EC.pending.eb ? 'eb=' + EC.pending.eb : '', EC.pending.ix ? 'ix=' + EC.pending.ix : '', EC.pending.sc ? 'sc=' + EC.pending.sc : ''].filter(Boolean) };
  if (fromLink && (EC.pending.e || EC.pending.ix || EC.pending.sc || EC.pending.wb || EC.pending.wc)) { showTab('economy', { open: false }); }
  else if (typeof SHADE_DS !== 'undefined' && Core.viewstate.has(SHADE_DS, EC.pending.s)) {   // an old link of the retired shading menu (app.js SHADE_DS, decision 81 (d)): its dataset, shaded
    const [key, norm = 'value'] = SHADE_DS[EC.pending.s];
    ecApi.show({ clear: false, stay: true, layers: [{ key, mode: 'fill', norm }] }).then(() => ecWriteHash(), () => null);
  }
}
if (window.ECON && window.ECON.shell) econInit();   // loaded on first use by js/econ_shell.js: the map is ready already
else { const _onMapReady = window.onMapReady; window.onMapReady = async function () { econInit(); if (_onMapReady) await _onMapReady(); }; }   // loaded with the page (another page): start first, the transit loader that runs after can be slow and must not hold the tab back
