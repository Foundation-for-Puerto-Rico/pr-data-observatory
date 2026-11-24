/* PR Data Observatory — 2D map. Static: reads site/data/*.json built by build.py. Shared helpers are in common.js.
   Live layers: NOAA sea level rise tiles (no key). Everything else is local. */

// The texts of the help buttons are in js/help.js, loaded with their Spanish the first time a help button is pressed (helpLoad, below); the public facilities
// bring their own (facLoad). Until then HELP is empty.
const HELP = {};

// "Shade municipalities by" was retired on 2026-11-04 (navigation plan, decision 81 (d)): each of its 35 measures is a dataset of the layer engine, and a link with s=<measure> opens that
// dataset, shaded, with the normalisation that gave the same figure ([key] as published, [key, norm] per resident or per km²). The three "places shown" measures counted only the
// listings the filters let through; they open the count of every tourism place (the hexagon view of the Tourism places layer still follows the filters). catalog.py reads this list.
const SHADE_DS = { assets: ['tourism_places'], assets_per_1000_residents: ['tourism_places', 'per1000'], assets_per_km2: ['tourism_places', 'perkm2'], shown: ['tourism_places'], shown_per_1000_residents: ['tourism_places', 'per1000'], shown_per_km2: ['tourism_places', 'perkm2'], sfha_pct: ['sfha_pct'], in_sfha: ['in_sfha'], in_protected: ['in_protected'], with_website: ['with_website'], transit_pct: ['transit_pct'], acc_walk400_pct: ['acc_walk400_pct'], acc_wfreq400_pct: ['acc_wfreq400_pct'], acc_walk800_pct: ['acc_walk800_pct'], acc_cur400_pct: ['acc_cur400_pct'], acc_freq400_pct: ['acc_freq400_pct'], acc_sat400_pct: ['acc_sat400_pct'], acc_sun400_pct: ['acc_sun400_pct'], acc_paper_pct: ['acc_paper_pct'], transit_stops: ['transit_stops'], uber_listed: ['uber_listed'], affordability_ratio: ['affordability_ratio'], median_home_value: ['median_home_value'], median_gross_rent: ['median_gross_rent'], renter_cost_burden_pct: ['renter_cost_burden_pct'], vacancy_pct: ['vacancy_pct'], seasonal_pct: ['seasonal_pct'], gross_rent_change_pct: ['gross_rent_change_pct'], urban_pct: ['urban_pct'], protected_land_pct: ['protected_land_pct'], population_2020: ['population'], pop_walk_active_pct: ['pop_walk_active_pct'], pop_walk_pct: ['pop_walk_pct'], pop_served_pct: ['pop_served_pct'], pop_served_active_pct: ['pop_served_active_pct'] };
const RAMP = Core.palettes.RAMPS.blue;

const S = { places: [], placesLoaded: false, access: null, catalog: null, muni: {}, meta: {}, flood: null, prot: null, muniFc: null, transport: null, routes: null, cats: new Set(Object.keys(CATEGORY_META)), conf: 0.5, worship: false, selected: null, placesView: 'pins', shown: {} };

// ── Map ────────────────────────────────────────────────────────────────────
if (typeof L === 'undefined' || !L.markerClusterGroup) {
  document.getElementById('loader').classList.add('error');
  document.getElementById('loaderText').innerHTML = Th('The map library did not load. Check your connection, then <button type="button" class="btn" onclick="location.reload()">try again</button>.');
  throw new Error('Leaflet unavailable');
}
const PR_BOUNDS = [[17.86, -67.3], [18.52, -65.2]];
const embedded = window.self !== window.top;   // inside an iframe the wheel must scroll the host page until the visitor clicks the map
const map = L.map('map', { zoomControl: false, preferCanvas: true, scrollWheelZoom: !embedded, maxZoom: 19 });   // maxZoom: the zoom the old raster base map allowed (the clusters need one)
if (embedded) { map.on('focus', () => map.scrollWheelZoom.enable()); map.on('blur', () => map.scrollWheelZoom.disable()); }
map.fitBounds(PR_BOUNDS, { animate: false });
const viewKey = () => { const c = map.getCenter(); return c.lat.toFixed(4) + ',' + c.lng.toFixed(4) + ',' + map.getZoom(); };
let mapHome = viewKey();   // the whole-island view: re-centred in the free area when the On the map panel opens or closes, while nobody has moved the map
L.control.zoom({ position: 'bottomright', zoomInTitle: T('Zoom in'), zoomOutTitle: T('Zoom out') }).addTo(map);
L.control.scale({ imperial: true, position: 'bottomright' }).addTo(map);
if (window.CleanView) { const cv = L.control({ position: 'bottomright' }); cv.onAdd = () => { const d = L.DomUtil.create('div', 'leaflet-bar cv-ctl'); d.appendChild(CleanView.button()); L.DomEvent.disableClickPropagation(d); return d; }; cv.addTo(map); }   // Clean view (core/cleanview.js): above the zoom buttons
// The base map (OpenFreeMap vector tiles from OpenStreetMap data, drawn by MapLibre under every pane of this map) and its credits come from js/core/basemap.js,
// loaded after the map is ready (startBasemap, below), so it stays off the first load (docs/basemap.md).
map.attributionControl.setPrefix('');
map.on('popupopen', e => { const el = e.popup.getElement(), b = el && el.querySelector('.leaflet-popup-close-button'); if (b) b.setAttribute('aria-label', T('Close popup')); });   // Leaflet writes this label in English

const panes = { surfheat: 340, muni: 350, barrios: 352, prot: 360, flood: 370, comunidades: 375, slr: 380, hexes: 385, routes: 390, rings: 345 };
Object.entries(panes).forEach(([k, z]) => { map.createPane(k); map.getPane(k).style.zIndex = z; });

const cluster = L.markerClusterGroup({ attribution: Th('Places © <a href="https://overturemaps.org/">Overture Maps Foundation</a>'), chunkedLoading: false, maxClusterRadius: 55, disableClusteringAtZoom: 16, spiderfyOnMaxZoom: true, showCoverageOnHover: false });
let floodLayer = null, protLayer = null, muniLayer = null, slrLayer = null, luLayer = null, barrioLayer = null, ceLayer = null, wcrpLayer = null, labelLayer = L.layerGroup();
map.createPane('landuse'); map.getPane('landuse').style.zIndex = 355;

function floodStyle(f) {
  const z = f.properties.FLD_ZONE || '', sub = (f.properties.ZONE_SUBTY || '').toUpperCase();
  if (sub.includes('FLOODWAY')) return { pane: 'flood', color: '#B82415', weight: .5, fillColor: '#B82415', fillOpacity: .45 };
  if (z.startsWith('V')) return { pane: 'flood', color: '#0B3D5C', weight: .4, fillColor: '#0B3D5C', fillOpacity: .5 };
  if (z === 'X' && sub.includes('0.2')) return { pane: 'flood', color: '#8FCAE8', weight: .3, fillColor: '#8FCAE8', fillOpacity: .45 };
  if (z === 'X' || z === 'D') return { pane: 'flood', weight: 0, fillOpacity: 0 };
  return { pane: 'flood', color: '#1F5F8B', weight: .4, fillColor: '#1F5F8B', fillOpacity: .42 };
}
function protStyle() { return { pane: 'prot', color: '#47560F', weight: 1, fillColor: '#79901E', fillOpacity: .3, interactive: false }; }

// Point-in-polygon (featuresAt) lives in plan.js, shared with the 3D view.
const floodVisible = (f) => !['OPEN WATER', 'AREA NOT INCLUDED'].includes(f.properties.FLD_ZONE) && !(f.properties.FLD_ZONE === 'X' && !String(f.properties.ZONE_SUBTY || '').includes('0.2')) && f.properties.FLD_ZONE !== 'D';

// ── Mobility ───────────────────────────────────────────────────────────────
let routesLayer = null, ringLayer = L.layerGroup();
// The stops are added in chunks once the group is on the map (chunkedLoading); markercluster does not stop when the group leaves the map meanwhile and its next
// chunk throws ("Cannot read properties of null (reading 'getMinZoom')", seen when Stops went off under load right after it came on): the removal waits for the last chunk.
let stopsAdding = false; const stopsAdded = [];
const stopCluster = L.markerClusterGroup({ attribution: T('Stops: ATI GTFS · © OpenStreetMap contributors'), chunkedLoading: true, chunkProgress: (n, total) => { stopsAdding = n < total; if (!stopsAdding) setTimeout(() => stopsAdded.splice(0).forEach(f => f())); }, maxClusterRadius: 40, disableClusteringAtZoom: 15, showCoverageOnHover: false, iconCreateFunction: c => L.divIcon({ html: `<div style="background:#205D7B">${c.getChildCount()}</div>`, className: 'marker-cluster marker-cluster-stops', iconSize: [40, 40] }) });
const hubLayer = L.layerGroup([], { attribution: T('Stations: ATI GTFS, OpenStreetMap, FAA') }), taxiLayer = L.layerGroup([], { attribution: T('© OpenStreetMap contributors') });

function kindIcon(f, size = 24) {
  const k = KIND[f.kind] || { icon: 'place', color: '#666' };
  return L.divIcon({ className: 'asset-marker-wrap', html: `<div class="mob-marker" style="background:${k.color};width:${size}px;height:${size}px">${icon(k.icon, { size: Math.round(size * .6), color: '#fff' })}</div>`, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
}
const jsonInFlight = {};
function getJson(path, label) {
  // one download per file, however many times a layer is toggled while it loads
  if (!jsonInFlight[path]) {
    toast(T('Loading {label}…', { label }));
    jsonInFlight[path] = fetchJson(path)
      .catch(e => { delete jsonInFlight[path]; toast(T('Could not load {label}. Check your connection and try again.', { label }), 6000); throw e; });
  }
  return jsonInFlight[path];
}
async function loadTransport() {
  if (S.transport) return;
  const data = await getJson('data/transport.json', T('mobility data'));
  if (S.transport) return;
  S.transport = data;
  const stops = [], hubs = [], taxi = [];
  for (const f of S.transport) {
    const mk = L.marker([f.lat, f.lng], { icon: kindIcon(f, HUB_KINDS.includes(f.kind) ? 30 : 22), title: f.name });
    mk.bindPopup(() => transportPopup(f), { maxWidth: 320 });
    if (HUB_KINDS.includes(f.kind)) hubs.push(mk); else if (STOP_KINDS.includes(f.kind)) stops.push(mk); else if (TAXI_KINDS.includes(f.kind)) taxi.push(mk);
    if (STOP_KINDS.includes(f.kind) || HUB_KINDS.includes(f.kind) && f.kind !== 'airport') ringLayer.addLayer(L.circle([f.lat, f.lng], { radius: 400, pane: 'rings', color: '#205D7B', weight: .6, fillColor: '#205D7B', fillOpacity: .06, interactive: false }));
  }
  stopCluster.addLayers(stops); hubs.forEach(m => hubLayer.addLayer(m)); taxi.forEach(m => taxiLayer.addLayer(m));
  $('#stopsCount').textContent = `(${fmt(stops.length)})`;
}
async function loadRoutes() {
  if (routesLayer) return;
  S.routes = await getJson('data/transit_routes.geojson', T('transit routes'));
  if (routesLayer) return;
  routesLayer = L.geoJSON(S.routes, {
    pane: 'routes', bubblingMouseEvents: false, attribution: T('Routes: ATI, municipal GTFS feeds, OpenStreetMap'),
    style: routeStyle,
    onEachFeature: (f, l) => { l.bindPopup(() => routePopup(f.properties), { maxWidth: 340 }); l.on('mouseover', () => l.setStyle({ opacity: 1, weight: (l.options.weight || 3) + 2 })); l.on('mouseout', () => routesLayer.resetStyle(l)); },
  });
}
function updateRings() { const on = $('#walkRings').checked && map.getZoom() >= 14 && ($('#lyStops').checked || $('#lyHubs').checked); on ? map.addLayer(ringLayer) : map.removeLayer(ringLayer); Core.activelayers.changed(); }

function slrUrl(ft) { return `https://coast.noaa.gov/arcgis/rest/services/dc_slr/slr_${ft}ft/MapServer/tile/{z}/{y}/{x}`; }
function setSlr(on) {
  if (slrLayer) { map.removeLayer(slrLayer); slrLayer = null; }
  if (!on) return;
  const ft = +$('#slr').value;
  slrLayer = L.tileLayer(slrUrl(ft), { pane: 'slr', opacity: .65, maxNativeZoom: 16, attribution: T('Sea level rise: NOAA OCM') }).addTo(map);
  let warned = false;
  slrLayer.on('tileerror', () => { if (!warned) { warned = true; toast(T('NOAA sea level tiles are not responding right now. Try again in a moment.'), 6000); } });
  toast(T('NOAA sea level rise: {ft} ft scenario, streamed from NOAA', { ft }));
}

// ── Places ─────────────────────────────────────────────────────────────────
function visible(p) {
  return S.cats.has(p.category) && p.confidence >= S.conf && (S.worship || p.type !== 'Places of Worship');
}
function placePopup(p) {
  const m = catMeta(p.category);
  const flags = [];
  if (p.sfha) flags.push(`<span class="badge sfha">${icon('flood', { size: 14 })}${esc(T('Flood hazard area, zone {zone}', { zone: p.flood_zone }))}</span>`);
  else if (p.flood_zone) flags.push(`<span class="badge x500">${icon('flood', { size: 14 })}${esc(T('Zone {zone} (0.2% annual chance)', { zone: p.flood_zone }))}</span>`);
  if (p.protected_area) flags.push(`<span class="badge prot">${icon('shield', { size: 14 })}${esc(p.protected_area)}</span>`);
  const acc = accessPopup(p);
  if (acc.badge) flags.push(acc.badge);
  flags.push(`<span class="badge ${p.confidence < 0.5 ? 'low' : 'conf'}">${icon('verified', { size: 14 })}${esc(T('confidence {value}', { value: Number(p.confidence ?? 0).toFixed(2) }))}</span>`);
  if (p.duplicates) flags.push(`<span class="badge conf">${esc(Tn(p.duplicates, '{n} duplicate listing folded', '{n} duplicate listings folded'))}</span>`);
  const links = [];
  links.push(`<a href="https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lng}#map=18/${p.lat}/${p.lng}" target="_blank" rel="noopener noreferrer">OpenStreetMap ${icon('open_in_new', { size: 12 })}</a>`);
  return `<div class="pop"><h4>${typeIcon(p.type, p.category, 28)}<span>${esc(p.name || T('(unnamed)'))}</span></h4>
    <div class="meta">${typeChip(p.type, p.category)}</div>
    <div class="meta">${esc(p.municipality)} · ${esc((S.muni[p.municipality] || {}).region)}</div>
    <div class="flags">${flags.join('')}</div>${acc.lines}
    <div class="links">${links.join('')}</div>
    <div class="src">${esc(T('Overture Maps · listing source: {source} · {category}', { source: p.source ? humanize(p.source) : T('Unknown'), category: p.overture_category ? T(humanize(p.overture_category)) : '' }))}</div></div>`;   // source names (Meta, Foursquare...) are names, not translated; Overture categories are spelled out in the Spanish bundle
}
// The visitor-economy module: the 35,000 listings (places.json, about 2.4 MB gzip with the access columns) and their access columns (place_access.json) are not part of the first load.
// They are fetched the first time something needs them: the Tourism places switch, a download of a municipality's places, a search of the listings or the button in the Municipality tab.
let placesP = null;
function placesSizeText() {   // "3.0 MB", from the catalog's weights (gzip estimates made at build time); empty when the catalog did not load
  const w = (S.catalog || {}).weights || {}, b = ((w['places.json'] || {}).gz || 0) + ((w['place_access.json'] || {}).gz || 0);
  return !b ? '' : b >= 1e6 ? `${fmt(b / 1e6, 1)} MB` : `${fmt(Math.round(b / 1e3))} KB`;   // 1 MB is 1 million bytes, as in the dictionary
}
function ensurePlaces() {
  if (S.placesLoaded) return Promise.resolve();
  if (!placesP) placesP = (async () => {
    $('#placesCount').textContent = T('(loading…)');
    const [places, accessFile] = await Promise.all([getJson('data/places.json', T('tourism places')), fetchAccess()]);
    places.forEach((p, i) => { p.id = i; });   // stable within a build; the published file carries no ids
    S.places = places;
    S.access = attachAccess(places, accessFile, S.meta);   // null when the file is missing or belongs to another build: pop-ups then show only the any-mapped-stop distance
    S.placesLoaded = true;
    rebuildPlaces();
    if (S.selected) renderMuni(S.selected);
  })().catch(e => { placesP = null; rebuildPlaces(); throw e; });   // rebuildPlaces writes the size hint again
  return placesP;
}
let rebuildGen = 0, placesDirty = true;
function rebuildPlaces() {
  if (!S.placesLoaded) { const sz = placesSizeText(); $('#placesCount').textContent = sz ? T('({size} to load)', { size: sz }) : ''; return; }
  const gen = ++rebuildGen;   // a newer rebuild cancels the chunks of an older one
  cluster.clearLayers();
  const list = S.places.filter(visible), drawn = list.filter(placeDrawn);
  $('#placesCount').textContent = Tn(drawn.length, '({n} shown)', '({n} shown)', { n: fmt(drawn.length) });
  if (hexArea()) { placesDirty = true; drawHexes(); return; }   // counted in hexagons: the pins are built when the view goes back to pins
  // The map opens with only the municipal boundaries on. While the pins are off, the 35,000 markers are not built; they are built when the layer is switched on.
  if (!map.hasLayer(cluster)) { placesDirty = true; return; }
  placesDirty = false;
  const shown = drawn.map(p => {
    const mk = L.marker([p.lat, p.lng], { icon: assetMarkerIcon(p), title: p.name });
    mk.bindPopup(() => placePopup(p), { maxWidth: 340 });
    return mk;
  });
  let i = 0;
  const step = () => { if (gen !== rebuildGen) return; cluster.addLayers(shown.slice(i, i + 4000)); i += 4000; if (i < shown.length) setTimeout(step, 0); };
  step();
}

// Places counted in hexagons (plan item 6, B2). The listings the filters above let through are counted client-side in hexagons of equal area (Core.hexbin) instead of drawn as pins, and in every municipality
// (the "Tourism places shown" choropleths), so the count follows the filters. The method is written under the legend.
const hexArea = () => /^hex(\d+)$/.test(S.placesView) ? +S.placesView.slice(3) : 0;   // km² of one hexagon; 0 for pins
let hexLayer = null, hexLib = null;
function drawHexes() {
  if (hexLayer) { map.removeLayer(hexLayer); hexLayer = null; }
  const lg = $('#placesLegend'); lg.innerHTML = ''; hexMini = ''; renderMapLegend();
  if (!hexArea() || !S.placesLoaded || !$('#lyPlaces').checked) return;
  if (!Core.hexbin) { hexLib = hexLib || new Promise((ok, no) => { const s = document.createElement('script'); s.src = 'js/core/hexbin.js?v=1'; s.onload = ok; s.onerror = () => { hexLib = null; no(); }; document.head.appendChild(s); }); hexLib.then(drawHexes, () => toast(T('That layer could not be loaded. Check your connection and try again.'))); return; }   // loaded on first use: off the map's first load
  const list = S.places.filter(p => visible(p) && placeDrawn(p)), bins = Core.hexbin.bin(list, { area: hexArea() }), counts = bins.cells.map(c => c.n).sort((a, b) => a - b);
  if (!counts.length) { lg.innerHTML = `<div class="note">${esc(T('No places pass the filters.'))}</div>`; return; }
  const b = Core.classify.make(counts, { method: 'quantile', k: 5 }), hits = Core.legend.counts(b, counts);
  hexLayer = L.geoJSON({ type: 'FeatureCollection', features: Core.hexbin.features(bins) }, { pane: 'hexes', attribution: Th('Places © <a href="https://overturemaps.org/">Overture Maps Foundation</a>'), style: f => ({ color: '#fff', weight: .6, fillColor: RAMP[Core.classify.classOf(b, f.properties.n)], fillOpacity: .78 }),
    onEachFeature: (f, l) => l.bindTooltip(Tn(f.properties.n, '{n} place in this hexagon', '{n} places in this hexagon', { n: fmt(f.properties.n) }), { sticky: true }) }).addTo(map);
  const rows = RAMP.map((color, i) => ({ color, lo: i ? Math.floor(b.edges[i]) + 1 : b.edges[0], hi: b.edges[i + 1], n: hits[i] })).filter(r => r.n > 0 && r.lo <= r.hi)   // counts are whole numbers: a class above the first starts one above the break
    .map(r => ({ color: r.color, label: r.lo === r.hi ? fmt(r.lo) : T('{lo} to {hi}', { lo: fmt(r.lo), hi: fmt(r.hi) }), n: r.n }));
  lg.innerHTML = Core.stack.box(T('Places in each hexagon'), rows, esc(T('Points counted in each hexagon; hexagons are equal-area ({km2} km² each). {n} places in {h} hexagons. The filters above apply.', { km2: bins.km2, n: fmt(list.length), h: fmt(bins.cells.length) })), (n) => Tn(n, '{n} hexagon', '{n} hexagons', { n }));
  hexMini = Core.stack.mini(T('Places in each hexagon'), rows); renderMapLegend();   // the same classes on the map, which is where a link with the hexagon view opens
}
function setPlacesView(v) {
  S.placesView = v === 'pins' || /^hex(2|10|50)$/.test(v) ? v : 'pins'; $('#placesView').value = S.placesView;
  if ($('#lyPlaces').checked && S.placesLoaded) { if (hexArea()) { map.removeLayer(cluster); drawHexes(); } else { drawHexes(); map.addLayer(cluster); if (placesDirty) rebuildPlaces(); } }
  writeHash();
}

// ── Municipalities ─────────────────────────────────────────────────────────
function muniStyle(f) {
  const sel = S.selected === f.properties.municipality;
  return { pane: 'muni', color: sel ? '#FF4D38' : '#205D7B', weight: sel ? 3 : 1, fillColor: 'transparent', fillOpacity: 0 };
}
let hexMini = '';   // the legend drawn on the map itself: the hexagons of the places
function renderMapLegend() { const ml = $('#mapLegend'), html = hexMini; ml.innerHTML = html; ml.classList.toggle('show', !!html); }
function selectMuni(name, { fly = true } = {}) {
  S.selected = name; $('#muniSel').value = name;
  writeHash();
  if (muniLayer) muniLayer.setStyle(muniStyle);
  renderMuni(name);
  showTab('muni');
  if (fly && muniLayer) {
    const f = muniLayer.getLayers().find(l => l.feature.properties.municipality === name);
    if (f) map.fitBounds(f.getBounds().pad(0.15));
  }
}
function bar(label, v, total, color, iconName, cat) {
  const pct = total ? v / total * 100 : 0;
  return `<div class="bar">${typeIcon(null, cat, 22)}<div><div style="display:flex;justify-content:space-between;font-size:12px"><span>${esc(label)}</span><em>${fmt(v)} · ${pct.toFixed(0)}%</em></div><div class="track"><div class="fill" style="width:${pct}%;background:${color}"></div></div></div><span></span></div>`;
}
const muniGeoid = (name) => { const f = S.muniFc && S.muniFc.features.find(x => x.properties.municipality === name); return f ? String(f.properties.GEOID).slice(0, 5) : ''; };   // the code the area profile (profile.html) is opened with
function renderMuni(name) {
  const m = S.muni[name];
  if (!m) { $('#muniBody').innerHTML = `<div class="empty">${esc(T('No data for this municipality.'))}</div>`; return; }
  const loaded = S.placesLoaded;   // without the listings the panel shows the figures stored for the default filters (confidence 0.50 or higher, no places of worship)
  const live = loaded ? S.places.filter(p => p.municipality === name && visible(p)) : [];
  const liveSfha = live.filter(p => p.sfha).length, listSfha = live.filter(p => p.sfha && placeDrawn(p));
  const byCat = {}; live.forEach(p => byCat[p.category] = (byCat[p.category] || 0) + 1);
  const byType = {}; live.forEach(p => byType[p.type] = (byType[p.type] || 0) + 1);
  const topTypes = Object.entries(byType).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const share = (test, stored) => loaded ? (live.length ? (live.filter(test).length / live.length * 100).toFixed(0) + '%' : '0%') : (stored == null ? '—' : fmt(stored, 0) + '%');   // a live share of the places that pass the filters, or the stored one
  const nPlaces = loaded ? live.length : (m.assets || 0), nSfha = loaded ? liveSfha : (m.in_sfha || 0), nProt = loaded ? live.filter(p => p.protected_area).length : (m.in_protected || 0), nWeb = loaded ? live.filter(p => p.has_website).length : (m.with_website || 0);
  const catN = loaded ? byCat : (m.by_category || {});
  const loadNote = `<div class="note">${Th('Counts and shares use the default filters: confidence 0.50 or higher, places of worship left out. <button type="button" class="linklike" data-loadplaces="1">Load the place listings</button>{size} to filter them, see the top types and list the places in a flood hazard area.', { size: placesSizeText() ? ' ' + T('(about {size})', { size: placesSizeText() }) : '' })}</div>`;
  const rankAll = Object.values(S.muni).sort((a, b) => b.assets - a.assets).map(x => x.municipality);
  const rankSfha = Object.values(S.muni).filter(x => x.sfha_pct != null).sort((a, b) => b.sfha_pct - a.sfha_pct).map(x => x.municipality);
  $('#muniBody').innerHTML = `
    <div class="muni-head"><div><h2>${esc(name)}</h2><small>${esc(T('{region} · {pop} residents (Census 2020) · {area} km²', { region: m.region, pop: fmt(m.population_2020), area: fmt(m.land_km2) }))}</small>${muniGeoid(name) ? `<div class="muni-prof"><a href="profile.html?area=${muniGeoid(name)}"><span class="ms-icon" aria-hidden="true">bar_chart</span>${esc(T('Area profile: every dataset for {name}, with its rank and trend', { name }))}</a></div>` : ''}</div></div>
    <h3 class="sec">${icon('place', { size: 14 })}${esc(T('Visitor economy'))}</h3>
    <div class="kpis">
      <div class="kpi"><div class="v">${fmt(nPlaces)}</div><div class="l">${esc(loaded ? T('tourism places (current filters)') : T('tourism places (default filters)'))}</div></div>
      <div class="kpi ${(loaded ? liveSfha / Math.max(live.length, 1) * 100 : m.sfha_pct) > 25 ? 'warn' : ''}"><div class="v">${loaded ? (live.length ? (liveSfha / live.length * 100).toFixed(0) : 0) : fmt(m.sfha_pct, 0)}%</div><div class="l">${esc(T('in flood hazard area'))} ${helpBtn('sfha')}</div></div>
      <div class="kpi"><div class="v">${fmt(m.assets_per_1000_residents, 1)}</div><div class="l">${esc(T('places per 1,000 residents'))}</div></div>
      <div class="kpi"><div class="v">${fmt(m.assets_per_km2, 1)}</div><div class="l">${esc(T('places per km²'))}</div></div>
      <div class="kpi green"><div class="v">${fmt(nProt)}</div><div class="l">${esc(T('inside protected areas'))}</div></div>
      <div class="kpi"><div class="v">${fmt(nWeb)}</div><div class="l">${esc(T('with a website'))}</div></div>
    </div>
    ${loaded ? '' : loadNote}
    <h3 class="sec">${icon('commute', { size: 14 })}${esc(T('Mobility'))}</h3>
    <div class="kpis">
      ${(loaded ? S.access : 'acc_cur400_pct' in m) ? `<div class="kpi"><div class="v">${!m.transit_stops ? '—' : share(p => walkM(p) <= ACCESS.near, m.acc_walk400_pct ?? m.acc_cur400_pct)}</div><div class="l">${esc((loaded ? S.access.tw_m : 'acc_walk400_pct' in m) ? T('places within a 400 m walk of a stop with a current timetable') : T('places within 400 m of a stop with a current timetable'))} ${helpBtn('access')}</div></div>
      <div class="kpi"><div class="v">${!m.transit_stops ? '—' : share(p => walkM(p) <= ACCESS.near && walkCalls(p) >= ACCESS.frequent, m.acc_wfreq400_pct ?? m.acc_freq400_pct)}</div><div class="l">${esc(T('with frequent service (20+ weekday departures)'))}</div></div>` : ''}
      <div class="kpi"><div class="v">${!m.transit_stops ? '—' : share(p => p.transit_400m, m.transit_pct)}</div><div class="l">${esc(T('places within 400 m of any mapped stop'))} ${helpBtn('transit')}</div></div>
      <div class="kpi"><div class="v">${fmt(m.transit_stops)}</div><div class="l">${esc(T('stops & stations'))}</div></div>
      ${(() => { const r = m.pop_walk_active_pct ?? m.pop_served_active_pct ?? m.pop_served_pct;   // residents: walking along mapped roads when published, else the straight line
        const l = m.pop_walk_active_pct != null ? T('of residents within a 400 m walk of a stop with a current timetable') : m.pop_served_active_pct != null ? T('of residents within 400 m of a stop with a current timetable') : T('of residents within 400 m of a scheduled stop');
        return `<div class="kpi ${r != null && r < 25 ? 'warn' : ''}"><div class="v">${r != null ? fmt(r, 0) + '%' : '—'}</div><div class="l">${esc(l)}</div></div>`; })()}
    </div>
    ${m.stops_current != null ? `<div class="note">${esc(T('Stops: {current} with a current timetable · {expired} with an expired timetable · {osm} mapped by volunteers (no timetable)', { current: fmt(m.stops_current), expired: fmt(m.stops_expired), osm: fmt(m.stops_osm) }))}</div>` : ''}
    <div class="chips">
      ${m.rail_stations ? `<span class="chip" style="background:#FFD0C9;color:#B82415">${icon('subway', { size: 15 })}Tren Urbano <b>${m.rail_stations}</b></span>` : ''}
      ${m.bus_stations ? `<span class="chip" style="background:#E6E6E6;color:#2A2E2E">${icon('transfer_within_a_station', { size: 15 })}${esc(T('Bus stations'))} <b>${m.bus_stations}</b></span>` : ''}
      ${m.ferry_terminals ? `<span class="chip" style="background:#BDE0F2;color:#205D7B">${icon('directions_boat', { size: 15 })}${esc(T('Ferry'))} <b>${m.ferry_terminals}</b></span>` : ''}
      ${m.airports ? `<span class="chip" style="background:#E6E6E6;color:#2A2E2E">${icon('flight', { size: 15 })}${esc(T('Airports'))} <b>${m.airports}</b>${m.public_airports ? ` <small>${esc(Tn(m.public_airports, '({n} public)', '({n} public)'))}</small>` : ''}</span>` : ''}
      ${m.gtfs_stops ? `<span class="chip" style="background:#BDE0F2;color:#205D7B">${icon('directions_bus', { size: 15 })}${esc(T('Scheduled stops'))} <b>${m.gtfs_stops}</b></span>` : ''}
      ${m.taxi_stands ? `<span class="chip" style="background:#FFE9A8;color:#8A5200">${icon('local_taxi', { size: 15 })}${esc(T('Taxi stands'))} <b>${m.taxi_stands}</b></span>` : ''}
      ${m.ev_charging ? `<span class="chip" style="background:#E4EFB8;color:#47560F">${icon('ev_station', { size: 15 })}${esc(T('EV charging'))} <b>${m.ev_charging}</b></span>` : ''}
      ${m.muni_system ? `<span class="chip" style="background:${m.muni_system === 'current' || m.muni_system === 'expiring' ? '#E4EFB8' : m.muni_system === 'expired' ? '#FFD0C9' : '#E6E6E6'};color:${m.muni_system === 'expired' ? '#B82415' : '#2A2E2E'}">${icon('directions_bus', { size: 15 })}${esc(T('Municipal system: {status}', { status: { current: T('schedule published'), expiring: T('schedule expires soon'), expired: T('schedule expired'), none: T('no public schedule'), unknown: T('schedule dates unknown') }[m.muni_system] || m.muni_system }))}</span>` : ''}
      <button type="button" class="chip" style="background:${m.uber_listed ? '#E4EFB8' : '#E6E6E6'};color:${m.uber_listed ? '#47560F' : '#2A2E2E'}" data-help="uber">${icon('local_taxi', { size: 15 })}${esc(m.uber_listed ? T('Uber listed') : T('Uber not listed'))}</button>
    </div>
    <div class="note">${Th('Rank <b>#{tourism}</b> of 78 by tourism places (1 = most) · <b>#{flood}</b> by share in flood hazard area (1 = highest share). Ranks use the default filters, not your current ones.', { tourism: rankAll.indexOf(name) + 1, flood: rankSfha.indexOf(name) + 1 })}</div>
    <h3 class="sec">${icon('home_work', { size: 14 })}${esc(T('Housing · ACS {year}', { year: (S.meta.housing || {}).acs_latest || '' }))} ${helpBtn('housing')}</h3>
    <div class="kpis">
      <div class="kpi ${Math.round(m.affordability_ratio * 100) / 100 > 1 ? 'warn' : 'green'}"><div class="v">${m.affordability_ratio != null ? m.affordability_ratio.toFixed(2) + '×' : '—'}</div><div class="l">${esc(T('affordability ratio (value ÷ max loan)'))}</div></div>
      <div class="kpi"><div class="v">${m.median_home_value != null ? '$' + fmt(m.median_home_value / 1000, 0) + 'k' : '—'}</div><div class="l">${esc(T('median home value · rent {rent}/mo', { rent: '$' + fmt(m.median_gross_rent) }))}</div></div>
      <div class="kpi"><div class="v">${fmt(m.renter_cost_burden_pct, 0)}%</div><div class="l">${esc(T('cost-burdened renters'))}</div></div>
      <div class="kpi"><div class="v">${fmt(m.seasonal_pct, 1)}%</div><div class="l">${esc(T('seasonal / recreational units'))}</div></div>
    </div>
    <div class="note">${Th('Land use (PUT 2015): <b>{urban}%</b> urban · <b>{urbanizable}%</b> urbanizable · <b>{protected}%</b> especially protected · <a href="housing.html?m={name}#profile">full housing profile</a>', { urban: fmt(m.urban_pct, 0), urbanizable: fmt(m.urbanizable_pct, 0), protected: fmt(m.protected_land_pct, 0), name: encodeURIComponent(name) })}</div>
    <h3 class="sec">${esc(T('By category'))}</h3>
    <div class="bars">${Object.entries(CATEGORY_META).map(([c, meta]) => bar(categoryLabel(c), catN[c] || 0, nPlaces, meta.color, meta.icon, c)).join('')}</div>
    ${loaded ? `<h3 class="sec">${esc(T('Top types'))}</h3>
    <div class="chips">${topTypes.map(([t, n]) => `<span class="chip" style="background:${catMeta(categoryOfSubcategory(t)).soft};color:${catMeta(categoryOfSubcategory(t)).text}" data-type="${esc(t)}">${icon(typeIconName(t, categoryOfSubcategory(t)), { size: 15 })}${esc(typeLabel(t))} <b>${fmt(n)}</b></span>`).join('')}</div>` : ''}
    <h3 class="sec">${esc(T('Places in flood hazard area'))}</h3>
    ${!loaded ? `<div class="note">${esc(Tn(nSfha, '{n} place is in a flood hazard area. The list needs the place listings.', '{n} places are in a flood hazard area. The list needs the place listings.', { n: fmt(nSfha) }))}</div>` : liveSfha ? `${listSfha.length ? `<table class="rank"><thead><tr><th>${esc(T('Place'))}</th><th>${esc(T('Type'))}</th><th>${esc(T('Zone'))}</th></tr></thead><tbody>${listSfha.sort((a, b) => (a.name || '').localeCompare(b.name || '')).slice(0, 60).map(p => `<tr class="row" data-id="${esc(p.id)}"><td><button type="button" class="linklike" data-id="${esc(p.id)}">${esc(p.name || T('(unnamed)'))}</button></td><td>${esc(typeLabel(p.type))}</td><td>${esc(p.flood_zone)}</td></tr>`).join('')}</tbody></table>` : ''}${listSfha.length > 60 ? `<div class="note">${esc(T('Showing 60 of {n}.', { n: fmt(listSfha.length) }))}</div>` : ''}${liveSfha > listSfha.length ? `<div class="note">${esc(Tn(liveSfha - listSfha.length, '{n} more is counted, not listed (a private home or similar).', '{n} more are counted, not listed (private homes and similar).', { n: fmt(liveSfha - listSfha.length) }))}</div>` : ''}` : `<div class="note">${esc(T('None of the shown places fall inside a Special Flood Hazard Area.'))}</div>`}
    <div class="btn-row"><button class="btn" id="muniCsv">${icon('download', { size: 16 })}${esc(T('Download {name} places (CSV)', { name }))}</button><button class="btn" id="muniZoom">${icon('place', { size: 16 })}${esc(T('Zoom to'))}</button></div>`;
  $('#muniCsv').onclick = async () => {   // the download needs the listings: fetch them first when they are not loaded yet
    try { await ensurePlaces(); } catch { return; }
    downloadCsv(S.places.filter(p => p.municipality === name && visible(p) && placeDrawn(p)), `${name}_places.csv`);
  };
  $('#muniZoom').onclick = () => selectMuni(name);
  $('#muniBody').querySelectorAll('[data-loadplaces]').forEach(b => b.onclick = () => ensurePlaces().catch(() => {}));
  $('#muniBody').querySelectorAll('tr.row').forEach(tr => tr.onclick = () => flyToPlace(+tr.dataset.id));
}
function flyToPlace(id) {
  const p = S.placesLoaded && S.places[id];
  if (!p || !placeDrawn(p)) return;
  map.setView([p.lat, p.lng], 17);
  setTimeout(() => {
    const mk = cluster.getLayers().find(l => l.options.title === p.name && Math.abs(l.getLatLng().lat - p.lat) < 1e-6);
    if (mk) { cluster.zoomToShowLayer(mk, () => mk.openPopup()); } else L.popup({ maxWidth: 340 }).setLatLng([p.lat, p.lng]).setContent(placePopup(p)).openOn(map);
  }, 300);
  if (isMobile()) setPanel(false);
}

// ── Rankings ───────────────────────────────────────────────────────────────
// Rankings rank any dataset of the layer engine (navigation plan, decision 81 (e)): the menu lists every dataset by group, in the order of the layer menu, with the normalisations
// it allows; the value is the dataset's latest year. The datasets load the first time the tab opens (economy.js ready()).
let rankDesc = true, rankBuilt = false;
async function renderRank() {
  const by = $('#rankBy'), nm = $('#rankNorm'), api = typeof ECON !== 'undefined' && ECON.api;
  if (!rankBuilt) {
    if (!api || !(await api.ready())) { $('#rankBody').innerHTML = `<div class="note">${esc(T('The datasets could not be loaded. Check your connection and open the tab again.'))}</div>`; return; }
    const ds = api.datasets(), groups = Core.datasets.sortGroups([...new Set(ds.map(d => d.group))]);
    by.innerHTML = groups.map(g => `<optgroup label="${esc(T(g))}">${ds.filter(d => d.group === g).map(d => `<option value="${esc(d.key)}">${esc(T(d.label))}</option>`).join('')}</optgroup>`).join('');
    by.value = ds.some(d => d.key === 'population') ? 'population' : ds[0].key; by.disabled = false; rankBuilt = true;
  }
  const key = by.value, opts = api.normOptions(key);
  if (nm.dataset.key !== key) { nm.innerHTML = opts.map(([v, l]) => `<option value="${esc(v)}">${esc(T(l))}</option>`).join(''); nm.value = 'value'; nm.dataset.key = key; nm.disabled = opts.length < 2; }
  const norm = nm.value || 'value', r = api.values(key, { norm }), names = api.places(), pr = names.length - 1;
  if (!r) { $('#rankBody').innerHTML = `<div class="empty">${esc(T('No values for this dataset.'))}</div>`; return; }
  const rows = names.slice(0, pr).map((n, i) => [n, r.values[i]]).filter(x => x[1] != null).sort((a, b) => rankDesc ? b[1] - a[1] : a[1] - b[1]);
  const label = T(api.meta(key).label), isl = r.values[pr], n = rows.length;
  const mo = norm === 'value' && api.moe ? api.moe(key, r.year) : null, rr = mo && Core.stats.rankRanges(r.values, mo, pr);   // with margins: the ranks each place could hold
  const rng = (m) => { const t = Core.stats.rangeAt(rr, names.indexOf(m), n, rankDesc); return t && ` <small title="${esc(T('The ranks it could hold, given the margins of error (90%)'))}">${t}</small>`; };
  $('#rankBody').innerHTML = `<div class="note">${esc(T('{n} municipalities with a value, {year}.', { n: rows.length, year: r.year }))}${isl == null ? '' : ' ' + esc(T('Puerto Rico: {v}', { v: api.fmt(key, isl, norm) }))}</div>`
    + `<table class="rank"><thead><tr><th scope="col">#</th><th scope="col">${esc(T('Municipality'))}</th><th class="sorted" aria-sort="${rankDesc ? 'descending' : 'ascending'}" style="text-align:right"><button type="button" class="linklike sortbtn" id="rankHead">${esc(label)} ${rankDesc ? '▼' : '▲'}</button></th></tr></thead><tbody>
    ${rows.map(([n, v], i) => `<tr class="row ${n === S.selected ? 'me' : ''}" data-m="${esc(n)}"><td class="num">${i + 1}${rng(n)}</td><td><button type="button" class="linklike" data-m="${esc(n)}">${esc(n)}</button></td><td class="num"><b>${esc(api.fmt(key, v, norm))}</b></td></tr>`).join('')}</tbody></table>`;
  $('#rankHead').onclick = () => { rankDesc = !rankDesc; renderRank(); };
  $('#rankBody').querySelectorAll('tr.row').forEach(tr => tr.onclick = () => selectMuni(tr.dataset.m));
}
// "Show on the map": the ranked dataset, shaded, on the map
async function rankToMap() { const key = $('#rankBy').value; if (!key || typeof ECON === 'undefined') return; await ECON.api.show({ clear: false, stay: true, layers: [{ key, mode: 'fill', norm: $('#rankNorm').value || 'value' }] }); }

// ── CSV ────────────────────────────────────────────────────────────────────
// Nested objects (by_category, landuse_km2) become prefixed columns; contact fields are never exported.
const CSV_SKIP = new Set(['id', 'socials', 'phone', 'email']);
function flattenRow(m) {
  const o = {};
  for (const [k, v] of Object.entries(m)) {
    if (v && typeof v === 'object') { for (const [k2, v2] of Object.entries(v)) if (v2 == null || typeof v2 !== 'object') o[`${k}_${k2}`] = v2; }
    else o[k] = v;
  }
  return o;
}
function downloadCsv(rows, filename) {
  if (!rows.length) { toast(T('Nothing to export: no places match the current filters.')); return; }
  const flat = rows.map(flattenRow);
  const cols = [...flat.reduce((a, r) => { Object.keys(r).forEach(k => a.add(k)); return a; }, new Set())].filter(k => !CSV_SKIP.has(k));
  // Cells that start with = + - @ would run as formulas in Excel; a leading apostrophe keeps them text.
  const q = v => { if (v == null) return ''; let s = String(v); if (/^[=+\-@\t\r]/.test(s) && !(typeof v === 'number')) s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const csv = '﻿' + [cols.join(','), ...flat.map(r => cols.map(k => q(r[k])).join(','))].join('\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

// ── Search ─────────────────────────────────────────────────────────────────
// One box for municipalities, tourism places (under the current filters), transit stops and routes, and the place index
// (barrios, towns, streets, PR route numbers, landmarks). The matching code is in plan.js and is shared with the 3D view.
const SEARCH_ZOOM = { municipio: 12, town: 14, village: 15, barrio: 14, neighborhood: 15, route: 14, road: 16, airport: 14, park: 15, beach: 16, peak: 15, water: 14 };
let searchPin = null, transportRows = null, routeRows = null, transportP = null, routesP = null;
const settle = (p) => p ? Promise.race([p, new Promise(r => setTimeout(r, 1500))]) : Promise.resolve();   // a first search waits briefly for the stop and route lists
function warmSearch() {
  Gaz.load().catch(() => {});
  if (!transportP) transportP = Data.json('data/transport.json').then(d => { transportRows = d.filter(f => f.name && (f.source === 'ati_gtfs' || f.source === 'muni_gtfs' || ['rail_station', 'bus_station', 'ferry_terminal', 'airport'].includes(f.kind))); transportRows.forEach(f => { f._n = norm(f.name); }); }).catch(() => {});
  if (!routesP) routesP = Data.json('data/transit_routes.geojson').then(d => { routeRows = d.features.map(f => ({ f, n: norm(`${f.properties.short_name || ''} ${f.properties.long_name || ''} ${f.properties.operator_name || ''}`) })); }).catch(() => {});
}
SearchDecorate.push(r => { if (r.kind === 'municipio' && S.muni[r.label]) r.sub = T('Municipality · {n} tourism places', { n: fmt(S.muni[r.label].assets) }); });
SearchSources.push((pq, { pointsOnly } = {}) => {   // tourism places under the current category and confidence filters
  if (!S.placesLoaded) {   // the listings are not part of the first load: offer them once, as the last line of a search
    if (pointsOnly || pq.n.length < 3) return [];
    const sz = placesSizeText();
    return [{ score: 99, hint: true, kind: 'load-places', label: T('Search the tourism places too'), sub: sz ? T('Loads the place listings, about {size}', { size: sz }) : T('Loads the place listings'), iconHtml: icon('place', { size: 22, color: '#338CB3' }) }];
  }
  const hits = [];
  for (const p of S.places) {
    if (!p.name || !visible(p) || !placeDrawn(p)) continue;
    const nn = p._n || (p._n = norm(p.name));
    let s = textScore(nn, pq.n, pq.tokens);
    if (s === null) { const nt = p._t || (p._t = norm(`${p.type} ${typeLabel(p.type)}`)); if (nt.includes(pq.n)) s = 2.8; else continue; }
    hits.push({ score: s * 10 + 3, kind: 'tourism', label: p.name, sub: `${typeLabel(p.type)} · ${p.municipality}${p.sfha ? ` · ${T('flood hazard area')}` : ''}`, lat: p.lat, lng: p.lng, id: p.id, iconHtml: typeIcon(p.type, p.category, 24) });
  }
  return hits.sort((a, b) => a.score - b.score || a.label.length - b.label.length).slice(0, 8);
});
SearchSources.push(async (pq) => {   // scheduled stops, stations and terminals
  if (!transportRows) { warmSearch(); await settle(transportP); }
  if (!transportRows) return [];
  const out = [];
  for (const f of transportRows) { const s = textScore(f._n, pq.n, pq.tokens); if (s !== null) out.push({ score: s * 10 + 2.5, kind: 'stop', label: f.name, sub: `${(KIND[f.kind] || {}).label || T('Stop')}${f.operator_name ? ' · ' + f.operator_name : ''}${f.municipality ? ' · ' + f.municipality : ''}`, lat: f.lat, lng: f.lng, f, iconHtml: icon((KIND[f.kind] || {}).icon || 'directions_bus', { size: 22, color: (KIND[f.kind] || {}).color || '#205D7B' }) }); }
  return out.sort((a, b) => a.score - b.score).slice(0, 6);
});
SearchSources.push(async (pq, { pointsOnly }) => {   // transit routes (a line, not a point, so the route planner skips them)
  if (pointsOnly) return [];
  if (!routeRows) { warmSearch(); await settle(routesP); }
  if (!routeRows) return [];
  const out = [];
  for (const r of routeRows) { const s = textScore(r.n, pq.n, pq.tokens); if (s !== null) { const p = r.f.properties; out.push({ score: s * 10 + 2.5, kind: 'transit_route', label: (p.long_name && p.short_name && p.long_name.startsWith(p.short_name) ? p.long_name : `${p.short_name || ''} ${p.long_name || ''}`).trim(), sub: T('Transit route · {operator}', { operator: p.operator_name || '' }), feature: r.f }); } }
  return out.sort((a, b) => a.score - b.score).slice(0, 4);
});
function showSearchPin(lat, lng, label, sub) {
  if (searchPin) map.removeLayer(searchPin);
  searchPin = L.marker([lat, lng], { icon: L.divIcon({ className: 'search-pin-wrap', html: '<div class="search-pin"></div>', iconSize: [26, 26], iconAnchor: [13, 26] }), title: label, keyboard: false, zIndexOffset: 800 }).addTo(map)
    .bindPopup(`<div class="pop"><h4>${icon('place', { size: 20, color: '#B82415' })}<span>${esc(label)}</span></h4><div class="meta">${esc(sub || '')}</div><div class="links"><button type="button" class="linklike" data-plan="from">${esc(T('Route from here'))}</button><button type="button" class="linklike" data-plan="to">${esc(T('Route to here'))}</button></div></div>`, { maxWidth: 300 }).openPopup();
}
function flyToResult(r) {
  if (r.bbox) map.fitBounds(r.bbox, { maxZoom: 17 }); else map.setView([r.lat, r.lng], SEARCH_ZOOM[r.kind] || 16);
  showSearchPin(r.lat, r.lng, r.label, r.sub);
  if (isMobile()) setPanel(false);
}
function onSearchPick(r) {
  if (r.kind === 'load-places') { ensurePlaces().then(() => mainSearch.run()).catch(() => {}); return; }
  if (r.kind === 'municipio' && S.muni[r.label]) { selectMuni(r.label); if (isMobile()) setPanel(true); return; }
  if (r.kind === 'tourism') { flyToPlace(r.id); return; }
  if (r.kind === 'stop') { map.setView([r.lat, r.lng], 17); L.popup({ maxWidth: 320 }).setLatLng([r.lat, r.lng]).setContent(transportPopup(r.f)).openOn(map); if (isMobile()) setPanel(false); return; }
  if (r.kind === 'transit_route') { focusRoute(r.feature); return; }
  flyToResult(r);
}
document.addEventListener('click', e => {   // "Route from / to here" in the search pin's popup
  const b = e.target.closest('[data-plan]'); if (!b || !searchPin) return;
  if (typeof Plan === 'undefined' || !Plan.root) { planLoad().then(() => b.click(), () => toast(T('The route planner could not be loaded. Check your connection and try again.'))); return; }   // loads on first use (network.js)
  const ll = searchPin.getLatLng(), r = { lat: ll.lat, lng: ll.lng, label: searchPin.options.title, sub: '' };
  Plan.setStop(b.dataset.plan === 'from' ? 0 : Plan.stops.length - 1, r); map.closePopup(); showTab('transit'); $('#tab-transit').foldOpen($('#planBox'));
});
const mainSearch = attachSearch($('#search'), $('#searchResults'), { warm: warmSearch, online: true, run: q => searchEverything(q, { bias: map.getCenter() }), onPick: onSearchPick, emptyText: T('No match. Try a street, town, landmark or stop name, or a PR route such as PR-52. Tourism places are searched once they are loaded, and follow the category and confidence filters.') });
document.addEventListener('keydown', e => { if (e.key === '/' && !e.ctrlKey && !e.metaKey && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) { e.preventDefault(); $('#search').focus(); } });

// ── UI helpers ─────────────────────────────────────────────────────────────
let mtP = null;   // js/maptools.js: Tools › Map tools (decision 97), loaded the first time that pane opens
// A link that opens a map tool: #mt=<the data-mt of its button in Tools › Map tools>, from a lesson of the Learn page (decision 106, docs/view-state.md
// "One-time requests"). Read here, before the map rewrites its address; run once, when the map is ready, and only when the pane has a button with exactly
// that code, so the address can start no more than a visitor's own click could.
const MT_LINK = (/(?:^#|&)mt=([\w:.-]+)(?=&|$)/.exec(location.hash) || [])[1] || null;
// The lesson of the Learn page that teaches a tool or a layer (js/learn_links.js, written by learn.py; decision 106, step 2): loaded the first time a help
// button is pressed or the Tools pane opens. A layer's "?" shows the link under its text.
let llP = null;
const learnLinks = () => llP || (llP = addJs('js/learn_links.js?v=5').then(() => window.LEARN_LINKS || null, () => { llP = null; return null; }));
const lessonName = (l) => T('Lesson: {title}', { title: l[1][I18N.lang === 'es' ? 'es' : 'en'] || l[1].en });
document.addEventListener('click', (e) => {
  const h = e.target.closest('[data-help]'), a = $('#helpLearn'); if (!h || !a) return;
  a.hidden = true;
  learnLinks().then((L) => { const l = L && L.layers[h.dataset.help]; if (!l || !$('#helpPop').classList.contains('show') || helpTrigger !== h) return; a.href = 'learn.html#lesson-' + l[0]; a.textContent = lessonName(l); a.hidden = false; });
});
function openToolLink(spec) {
  if (!Array.from(document.querySelectorAll('#tab-maptools [data-mt]')).some(b => b.dataset.mt === spec)) return;
  showTab('maptools', { open: false });   // on a phone the tool opens over the map, not behind the panel
  if (mtP) mtP.then(() => { if (window.MapTools) MapTools.run(spec); }, () => { /* the pane says the tool could not be opened */ });
}
function onTabShown(name) { if (name === 'muni' && !S.selected && !$('#lyMuni').checked) $('#lyMuni').click();   // show where to click
  if (name === 'region') regionOpen(); else if (typeof Region !== 'undefined') Region.hide();
  if (name === 'rank') renderRank(); if (name === 'maptools') mtP = mtP || addJs('js/maptools.js?v=5').catch(() => { mtP = null; $('#tab-maptools').removeAttribute('data-t-wait'); }); if (name === 'about') { loadAboutText(); loadAboutNumbers(); } if (typeof econShown === 'function') econShown(name); if (typeof Catalog !== 'undefined') Catalog.shown(name); }
function toast(msg, ms = 3500) { Core.activelayers.toast(msg, ms); }   // core/activelayers.js: the same message, which can also carry an Undo button
initHelp(k => HELP[k]);

function renderCatChips() {
  $('#catChips').innerHTML = Object.entries(CATEGORY_META).map(([c, m]) => `<button type="button" class="chip ${S.cats.has(c) ? '' : 'off'}" aria-pressed="${S.cats.has(c)}" data-cat="${c}" style="background:${m.soft};color:${m.text}">${icon(m.icon, { size: 15 })}${esc(categoryLabel(c))}</button>`).join('');
  $('#catChips').querySelectorAll('.chip').forEach(ch => ch.onclick = () => {
    const c = ch.dataset.cat; S.cats.has(c) ? S.cats.delete(c) : S.cats.add(c);
    ch.classList.toggle('off', !S.cats.has(c)); ch.setAttribute('aria-pressed', String(S.cats.has(c)));
    rebuildPlaces(); if (S.selected) renderMuni(S.selected);
  });
}
function renderAbout() {
  const m = S.meta, c = m.counts || {}, t = m.transport || {}, kd = t.kinds || {};
  const stopsAndStations = (kd.transit_stop || 0) + (kd.bus_stop || 0) + (kd.bus_station || 0) + (kd.rail_station || 0) + (kd.ferry_terminal || 0);
  $('#aboutKpis').innerHTML = [[c.municipalities || 78, T('municipalities')], [c.population_2020, T('residents (2020 Census)')], [c.tourism_places, T('tourism places')], [(m.network || {}).routes, T('transit routes, all operators')], [stopsAndStations, T('stops and stations')]]
    .map(([v, l]) => `<div class="kpi"><div class="v">${fmt(v)}</div><div class="l">${esc(l)}</div></div>`).join('');
  $('#snapshotLabel').innerHTML = `<b>${esc(snapshotLabel(m.label))}</b>`; $('#snapshotLabel').title = T('Built {date}', { date: (m.generated_at || '').slice(0, 10) });
  $('#aboutBuilt').innerHTML = Th('Current snapshot: <b>{label}</b>, built {date}.', { label: snapshotLabel(m.label), date: (m.generated_at || '').slice(0, 10) });
  document.title = T('PR Data Observatory · Foundation for Puerto Rico');
  document.querySelectorAll('.snap').forEach(e => e.textContent = m.label ? snapshotLabel(m.label) : '');
}
let aboutText = null;
/** The About tab's own text: its Spanish (es.map.about.js, module "about" in i18n_src/pages.json) loads the first time the tab opens, so the map's first load does
    not carry it. Until then the tab's content waits unseen (data-t-wait: twin.css; aria-hidden, which the glossary leaves alone), then it is translated and the glossary reads it. */
function loadAboutText() {
  const tab = $('#tab-about');
  return aboutText || (aboutText = I18N.load('about').then(() => {
    const snap = (tab.querySelector('.snap') || {}).textContent || '';
    tab.querySelectorAll('.snap').forEach(e => { e.textContent = ''; });   // a sentence is translated as written in the page, with its snapshot label still empty
    I18N.apply(tab);
    tab.querySelectorAll('.snap').forEach(e => { e.textContent = snap; });
  }, e => { aboutText = null; console.error(e); }).finally(() => {
    tab.removeAttribute('data-t-wait'); tab.removeAttribute('aria-hidden');
    if (window.Core && Core.glossary && Core.glossary.mark) Core.glossary.mark(tab);
  }));
}
let aboutNumbers = null;
async function loadAboutNumbers() {   // the dictionary's size, fetched once when the About tab is first opened
  if (aboutNumbers) return; aboutNumbers = true;
  try {
    const d = await fetchJson('data/dictionary_summary.json');
    $('#aboutKpis').insertAdjacentHTML('beforeend', [[d.entries, T('documented datasets, variables and measures')], [d.data_sources, T('data sources, each with its license')]].map(([v, l]) => `<div class="kpi"><div class="v">${fmt(v)}</div><div class="l">${esc(l)}</div></div>`).join(''));
  } catch { /* the dictionary is optional here */ }
}

// ── Shareable state: #Municipality&c=lat,lng,zoom&l=layers&s=shading ──────────
// The schema is shared with the 3D view (js/core/viewstate.js, docs/view-state.md): what this map does not use (the 3D camera's b= and p=, a layer or a measure
// of the 3D view only, a key of a later version) is kept as it came, and the 3D link carries the whole address.
const LAYER_KEYS = { surfheat: 'lySurfHeat', places: 'lyPlaces', flood: 'lyFlood', slr: 'lySlr', routes: 'lyRoutes', stops: 'lyStops', hubs: 'lyHubs', taxi: 'lyTaxi', prot: 'lyProt', landuse: 'lyLanduse', soil: 'lySoil', slide: 'lySlide', slope: 'lySlope', contours: 'lyContours', watersheds: 'lyWatersheds', comunidades: 'lyComunidades', wcrp: 'lyWcrp', oz: 'lyOz', pubhousing: 'lyPubHousing', lihtc: 'lyLihtc', reservoirs: 'lyReservoirs', broadband: 'lyBroadband', hexgrid: 'lyHexgrid', powerlines: 'lyPowerLines', plants: 'lyPlants', rivers: 'lyRivers', groundwater: 'lyGroundwater', rain: 'lyRain', fire: 'lyFire', police: 'lyPolice', libraries: 'lyLibraries', schools: 'lySchools', historic: 'lyHistoric', townhalls: 'lyTownhalls', dumping: 'lyDumping', fprroutes: 'lyFprRoutes', publicos: 'lyPublicos', links: 'lyLinks', traffic: 'lyTraffic', bridges: 'lyBridges', airports: 'lyAirports', ferries: 'lyFerries', evcharge: 'lyEvCharge', barrios: 'lyBarrios', muni: 'lyMuni', rings: 'walkRings', now: 'lyNow', gaps: 'lyGaps', xfer: 'lyXfer' };
let hashTimer = null, ready = false;
// The base map the viewer chose (bm=<a name of OPTIONS in js/core/basemap.js>, which loads after ready, so the names are listed here too: a test keeps them
// equal), carried in the address and in the 3D link; null: none chosen, so each view opens on the viewer's default kept in this browser, or on its own
// (Positron here, Liberty in 3D). docs/basemap.md
const BM_NAMES = /^(positron|liberty|bright|dark|fiord|imagery|topo|relief|none)$/;
let bmLink = (/(?:^|&)bm=([a-z]+)(?=&|$)/.exec(location.hash.slice(1)) || [])[1] || null, bmH = null, bmCtl = null;
if (!BM_NAMES.test(bmLink || '')) bmLink = null;
function writeHash() {
  Core.activelayers.changed();   // every change of what the map shows comes through here: the "layers on" chip follows
  if (!ready) return;
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const VS = Core.viewstate, was = VS.parse(location.hash), c = map.getCenter(), el = (id) => $('#' + id);
    const econ = typeof ECON !== 'undefined' ? ECON.encode() : '', extra = typeof ECON !== 'undefined' ? ECON.extra() : [];
    const ex = {}; extra.forEach(x => { const i = x.indexOf('='); if (i > 0) { try { ex[x.slice(0, i)] = decodeURIComponent(x.slice(i + 1)); } catch { ex[x.slice(0, i)] = x.slice(i + 1); } } });
    const hash = VS.write('2d', location.hash, {
      muni: S.selected || null,
      c: VS.cOf(c.lat, c.lng, map.getZoom()),
      l: VS.layerTokens('2d', id => !!(el(id) && el(id).checked), id => !!(el(id) && el(id).defaultChecked)),
      s: was.s && !VS.has(SHADE_DS, was.s) ? undefined : null,   // a measure of the 3D columns only stays in the address; an old shading measure has become a dataset (e=)
      pv: hexArea() ? S.placesView : null,
      r: typeof Plan !== 'undefined' && Plan.root ? Plan.encode() || null : planInLink || null,   // before the planner has loaded, a link's route stays in the address
      e: econ || null, ey: econ ? ex.ey || null : null, eb: econ ? ex.eb || null : null,   // a composite or a scenario is kept even with no layer on the map
      ix: ex.ix || null, sc: ex.sc || null,
      slr: $('#lySlr').checked ? $('#slr').value : null,
      bm: bmLink || null,
      rg: rgLink || null,   // the region filter of Reference (decision 113)
    });
    history.replaceState(null, '', hash || location.pathname + location.search);
    const l3 = document.querySelector('.views a[href^="3d.html"]'); if (l3) l3.href = '3d.html' + location.search + hash;   // the whole state (docs/view-state.md)
    document.title = (S.selected ? S.selected + ' · ' : '') + T('PR Data Observatory · Foundation for Puerto Rico');
  }, 250);
}
/** The address's parts as they came (e=, ix=, sc= still encoded), by the rule of core/viewstate.js: a key twice, the first counts; no prototype, so a key
 *  "constructor" is just a key. muni: the bare municipality. */
function parseHash() {
  const P = Core.viewstate.parse(location.hash), o = Object.assign(Object.create(null), P.raw);
  delete o.muni; if (P.muni) o.muni = P.muni;
  return o;
}
function applyHash() {
  const h = parseHash();
  if (h.pv) { S.placesView = /^hex(2|10|50)$/.test(h.pv) ? h.pv : 'pins'; $('#placesView').value = S.placesView; }   // before the layers, so the listings are drawn as hexagons the first time
  if (h.l != null) {   // a key listed is on, "-key" off; a layer of both views not listed is off; one of this map only keeps its default (core/viewstate.js layerPlan)
    const plan = Core.viewstate.layerPlan('2d', h.l.split(','), id => !!($('#' + id) && $('#' + id).defaultChecked));
    for (const [id, on] of Object.entries(plan)) { const el = $('#' + id); if (el && el.checked !== on) { el.checked = on; el.dispatchEvent(new Event('change')); } }
  }
  if (h.slr && /^\d+$/.test(h.slr) && +h.slr >= 1 && +h.slr <= 10) { $('#slr').value = h.slr; $('#slr').dispatchEvent(new Event('input')); if ($('#lySlr').checked) setSlr(true); }
  if (h.muni) {
    const name = Object.keys(S.muni).find(k => norm(k) === norm(h.muni));
    if (name) selectMuni(name, { fly: !h.c }); else toast(T('No municipality named "{name}". Pick one from the search box.', { name: h.muni }), 6000);
  }
  if (rfCtl && (h.rg || null) !== rfCtl.value()) rgLink = rfCtl.set(h.rg || null);   // a pasted address with another region, or none
  if (BM_NAMES.test(h.bm || '') && h.bm !== bmLink) { bmLink = h.bm; if (bmH) { bmH.set(bmLink); bmCtl.set(bmLink); } }   // a pasted address with another base map
  const c = h.c && h.c.split(',').map(Number);
  if (c && c.length === 3 && c.every(Number.isFinite)) { const h = mapHome.split(',').map(Number); map.setView([c[0], c[1]], c[2], { animate: false }); if (c[2] === h[2] && Math.abs(c[0] - h[0]) < 1e-3) mapHome = viewKey(); }   // a link at the whole-island view (perhaps shifted beside the panel) is still home
  refreshFolds();
}
window.addEventListener('hashchange', () => { if (ready) applyHash(); });
map.on('moveend', writeHash);

// ── Click on the map: municipality, or whatever overlay is switched on at that point ──
map.on('click', e => {
  if (typeof Plan !== 'undefined' && (Plan.picking >= 0 || Plan.clickMode)) return;   // choosing a point for the route planner
  if (typeof ECON !== 'undefined' && ECON.claims()) return;   // the Economy tab answers its own clicks
  const sections = [];
  if ($('#lyFlood').checked && S.flood) featuresAt(S.flood, e.latlng, floodVisible, 2).forEach(f => sections.push(floodPopup(f.properties, false)));
  if ($('#lyProt').checked && S.prot) featuresAt(S.prot, e.latlng, () => true, 2).forEach(f => sections.push(protPopup(f.properties, false)));
  if ($('#lyLanduse').checked && S.landuse) featuresAt(S.landuse, e.latlng, f => !['water', 'road'].includes(f.properties.group) && luShown(f.properties), 1).forEach(f => sections.push(landusePopup(f.properties, false)));
  if (S.soil && $('#lySoil').checked) sections.push(...soilAt(e.latlng));   // js/soil.js
  if (window.slopeAt && $('#lySlope').checked) sections.push(...slopeAt(e.latlng));   // js/terrain.js
  if (window.shedAt && $('#lyWatersheds').checked) sections.push(...shedAt(e.latlng));
  if ($('#lyComunidades').checked && S.comunidades) featuresAt(S.comunidades, e.latlng, () => true, 1).forEach(f => sections.push(comunidadPopup(f.properties, false)));
  const bf = $('#lyBarrios').checked && S.barrios ? featuresAt(S.barrios, e.latlng, () => true, 1)[0] : null;
  if (bf) sections.push(barrioPopup(bf.properties, false));
  const mf = ($('#lyMuni').checked || $('#tab-muni').classList.contains('active')) && S.muniFc ? featuresAt(S.muniFc, e.latlng, () => true, 1)[0] : null;   // on the Municipality tab a click picks one, boundaries on or off
  const name = mf && mf.properties.municipality;
  if (!sections.length) { if (name) selectMuni(name, { fly: false }); return; }
  L.popup({ maxWidth: 340 }).setLatLng(e.latlng).setContent(areasPopup(sections, name)).openOn(map);   // the sections and the card are in access.js: the 3D view shows the same
  const b = $('#idOpenMuni'); if (b) b.onclick = () => { map.closePopup(); selectMuni(name, { fly: false }); };
});

// ── Wiring ─────────────────────────────────────────────────────────────────
// A failed layer download unchecks its box so the UI never claims a layer that is not there.
const guarded = (fn) => async (e) => { try { await fn(e); } catch { e.target.checked = false; if (e.target.id === 'lyFlood') $('#floodLegend').style.display = 'none'; } finally { writeHash(); refreshFolds(); } };
$('#lyPlaces').onchange = guarded(async e => { if (e.target.checked) { await ensurePlaces(); if ($('#lyPlaces').checked) { if (hexArea()) drawHexes(); else { map.addLayer(cluster); if (placesDirty) rebuildPlaces(); } } } else { map.removeLayer(cluster); drawHexes(); } });
$('#placesView').onchange = e => setPlacesView(e.target.value);
$('#conf').oninput = e => { S.conf = +e.target.value; $('#confVal').textContent = S.conf.toFixed(2); e.target.setAttribute('aria-valuetext', T('{value} minimum confidence', { value: S.conf.toFixed(2) })); };
$('#conf').onchange = () => { rebuildPlaces(); if (S.selected) renderMuni(S.selected); };
$('#worship').onchange = e => { S.worship = e.target.checked; rebuildPlaces(); if (S.selected) renderMuni(S.selected); };
$('#lyFlood').onchange = guarded(async e => { $('#floodLegend').style.display = e.target.checked ? '' : 'none'; if (e.target.checked) await loadFlood(); else if (floodLayer) map.removeLayer(floodLayer); });
$('#lySurfHeat').onchange = guarded(async e => { if (e.target.checked) await loadSurf(); else if (surfLayer) map.removeLayer(surfLayer); $('#surfLegend').style.display = e.target.checked ? '' : 'none'; });
$('#lyProt').onchange = guarded(async e => { if (e.target.checked) await loadProt(); else if (protLayer) map.removeLayer(protLayer); });
$('#lyLanduse').onchange = guarded(async e => { $('#luLegend').style.display = e.target.checked ? '' : 'none'; if (e.target.checked) await loadLanduse(); else if (luLayer) map.removeLayer(luLayer); });
$('#lyComunidades').onchange = guarded(async e => { if (e.target.checked) await loadComunidades(); else if (ceLayer) map.removeLayer(ceLayer); });
$('#lyWcrp').onchange = guarded(async e => { if (e.target.checked) await loadWcrp(); else if (wcrpLayer) map.removeLayer(wcrpLayer); });
$('#lyBarrios').onchange = guarded(async e => { if (e.target.checked) await loadBarrios(); else if (barrioLayer) map.removeLayer(barrioLayer); });
// Public facilities (js/core/facilities.js, shared with the 3D view, then js/facilities.js, and their Spanish: loaded the first time one of their layers or help buttons is used; each layer's file on first use)
let facP = null, facJs = null;
const addJs = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
const facLoad = () => facP || (facP = allIn([I18N.load('facilities'), facJs = facJs || (window.Core.facilities ? Promise.resolve() : addJs('js/core/facilities.js?v=25')).then(() => addJs('js/facilities.js?v=19')).catch(e => { facJs = null; throw e; })]).catch(e => { facP = null; throw e; }));
['oz', 'pubhousing', 'lihtc', 'fire', 'police', 'libraries', 'schools', 'historic', 'townhalls', 'reservoirs', 'broadband', 'hexgrid', 'powerlines', 'plants', 'rivers', 'groundwater', 'rain', 'dumping', 'fprroutes', 'publicos', 'links', 'traffic', 'bridges', 'airports', 'ferries', 'evcharge'].forEach(k => { $('#' + LAYER_KEYS[k]).onchange = guarded(async e => { if (e.target.checked) { await facLoad(); await Facilities.show(k); } else if (typeof Facilities !== 'undefined') Facilities.hide(k); }); });
// A help button whose text has not arrived: load it (the facilities' texts come with their script), then press the button again
let helpP = null, helpJs = null;
const helpLoad = () => helpP || (helpP = allIn([I18N.load('help'), helpJs = helpJs || new Promise((ok, fail) => { const s = document.createElement('script'); s.src = 'js/help.js?v=12'; s.onload = ok; s.onerror = () => { s.remove(); helpJs = null; fail(new Error(s.src)); }; document.body.appendChild(s); })]).catch(e => { helpP = null; throw e; }));
document.addEventListener('click', e => { const h = e.target.closest('[data-help]'), key = h && h.dataset.help; if (!h || HELP[key]) return; e.preventDefault(); e.stopPropagation(); (key.startsWith('fac_') ? facLoad() : helpLoad()).then(() => { if (HELP[key]) h.click(); }, () => toast(T('The help could not be loaded. Check your connection and try again.'), 5000)); }, true);
$('#lyMuni').onchange = e => { if (muniLayer) { e.target.checked ? (map.addLayer(muniLayer), map.getZoom() >= 10 && map.addLayer(labelLayer)) : (map.removeLayer(muniLayer), map.removeLayer(labelLayer)); } writeHash(); };
$('#lySlr').onchange = e => { setSlr(e.target.checked); writeHash(); };
$('#slr').oninput = e => { $('#slrVal').textContent = `${e.target.value} ft`; e.target.setAttribute('aria-valuetext', Tn(+e.target.value, '{n} foot of sea level rise', '{n} feet of sea level rise')); };
$('#slr').onchange = () => { if ($('#lySlr').checked) setSlr(true); writeHash(); };
$('#lyRoutes').onchange = guarded(async e => { $('#mobLegend').style.display = e.target.checked ? '' : 'none'; if (e.target.checked) { await loadRoutes(); if ($('#lyRoutes').checked) routesLayer.addTo(map); } else if (routesLayer) map.removeLayer(routesLayer); });
$('#lyStops').onchange = guarded(async e => { if (e.target.checked) { await loadTransport(); if ($('#lyStops').checked) map.addLayer(stopCluster); } else { const off = () => { if (!$('#lyStops').checked) map.removeLayer(stopCluster); updateRings(); }; if (stopsAdding) stopsAdded.push(off); else off(); } updateRings(); });
$('#lyHubs').onchange = guarded(async e => { if (e.target.checked) { await loadTransport(); if ($('#lyHubs').checked) map.addLayer(hubLayer); } else map.removeLayer(hubLayer); updateRings(); });
$('#lyTaxi').onchange = guarded(async e => { if (e.target.checked) { await loadTransport(); if ($('#lyTaxi').checked) map.addLayer(taxiLayer); } else map.removeLayer(taxiLayer); });
$('#walkRings').onchange = guarded(async () => { await loadTransport(); updateRings(); });
map.on('zoomend', updateRings);
$('#rankBy').onchange = () => { rankDesc = true; renderRank(); }; $('#rankNorm').onchange = renderRank; $('#rankMap').onclick = rankToMap;
$('#dlCsv').onclick = () => downloadCsv(Object.values(S.muni), `pr_digital_twin_municipalities_${(S.meta.label || 'snapshot').replace(/[^0-9A-Za-z-]+/g, '_')}.csv`);
initPanel(); initTabs(); initFolds($('#tab-layers'));
const regionWanted = (/[#&]rg=([\w-]+)/.exec(location.hash) || [])[1];   // a regional profile's "Open on the map" sends #rg=<id> (docs/regions.md); read now, before the map rewrites the address
const regionTab = !!regionWanted && !/[#&]c=/.test(location.hash);   // only that link opens the Region tab: an address the map wrote (it always has c=) keeps rg= for the region filter of Reference
// The "layers on" chip at the top of the map (core/activelayers.js). Límites, the municipality boundaries, is the reference layer: it stays on and is never counted.
Core.activelayers.mount(Core.activelayers.combine(
  Core.activelayers.switches(Object.entries(LAYER_KEYS).filter(([k]) => k !== 'muni').map(([, id]) => $('#' + id)), { walkRings: () => T('Walk rings') }, { walkRings: () => map.hasLayer(ringLayer) }),   // the rings count while they are drawn (zoom 14 and stops or stations on)
  Core.activelayers.econ(() => typeof ECON !== 'undefined' && ECON.api),
  Core.activelayers.plan(() => typeof Plan !== 'undefined' && Plan.root ? Plan : null)), $('#map'));
// Map space (review 2026-11-05): what covers the map, in px from each edge: the chip and message at the top, the On the map panel pinned on the right of a wide screen,
// the legend at the bottom. Pop-ups open inside what is left, and the island's whole view is centred in it (a pan, not a padded fit: that would drop a zoom level).
function mapInsets() {
  const m = $('#map').getBoundingClientRect(), i = { t: 56, r: 16, b: 16, l: 16 }, w = $('#alWrap'), p = $('#alPanel'), g = $('#econLegend');
  if (w && p && !w.hidden && !p.hidden && w.classList.contains('pinned')) { const b = p.getBoundingClientRect(); if (b.width) i.r = Math.max(i.r, m.right - b.left + 12); }
  if (g && g.offsetHeight && !g.classList.contains('docked')) i.b = Math.max(i.b, m.bottom - g.getBoundingClientRect().top + 12);
  return i;
}
const adjustPan = L.Popup.prototype._adjustPan;
if (adjustPan) L.Popup.prototype._adjustPan = function () { const i = mapInsets(); this.options.autoPanPaddingTopLeft = L.point(i.l, i.t); this.options.autoPanPaddingBottomRight = L.point(i.r, i.b); return adjustPan.apply(this, arguments); };
let pinnedOpen = false;
const reHome = () => {
  const r = mapInsets().r, on = r > 16; if (on === pinnedOpen) return; pinnedOpen = on;
  if (viewKey() !== mapHome) return;   // the visitor has moved the map: leave it
  map.fitBounds(PR_BOUNDS, { animate: false }); if (on) map.panBy([r / 2, 0], { animate: false });
  mapHome = viewKey();
};
if ($('#alWrap')) new MutationObserver(reHome).observe($('#alWrap'), { attributes: true, subtree: true, attributeFilter: ['class', 'hidden'] });
map.on('resize', () => { pinnedOpen = null; reHome(); });   // panel folded or window resized
// the long hint only where it fits in the box with 8 px to spare, the short one otherwise (in Spanish the long one was cut at 1024 px, and on the 3D view at 1400)
let phCtx = null;
const searchPlaceholder = () => {
  const i = $('#search'), long = T('Search a place or street'), s = getComputedStyle(i), room = i.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
  phCtx = phCtx || document.createElement('canvas').getContext('2d'); phCtx.font = s.font;
  i.placeholder = isMobile() || (room > 0 && phCtx.measureText(long).width > room - 8) ? T('Search') : long;
};
searchPlaceholder(); mobileQuery.addEventListener('change', searchPlaceholder); new ResizeObserver(searchPlaceholder).observe($('#search')); if (document.fonts) document.fonts.ready.then(searchPlaceholder);

async function loadJson(path, label) { $('#loaderText').textContent = T('Loading {label}…', { label }); return fetchJson(path); }
async function loadFlood() {
  if (!floodLayer) {
    S.flood = await getJson('data/flood.geojson', T('FEMA flood zones'));
    if (!floodLayer) floodLayer = L.geoJSON(S.flood, { interactive: false, style: floodStyle, filter: floodVisible, attribution: T('Flood zones: FEMA NFHL') });
  }
  if ($('#lyFlood').checked) floodLayer.addTo(map);
}
// The classes of the land-use plan: every class of the legend starts ticked; an unticked class is hidden on the map and in the click pop-up (landuse.py class_key: a
// code without its own colour, such as SREP-AE, draws as SREP)
const LU_KEYS = ['SU', 'SURP', 'SURNP', 'SRC', 'SREP', 'SREP-E', 'SREP-A', 'SREP-H', 'SREP-EH', 'SREP-AH'], luHidden = new Set();
const luKey = cls => { const c = String(cls || '').toUpperCase(); return LU_KEYS.includes(c) ? c : c.split('-')[0]; };
const luShown = p => !luHidden.has(luKey(p.cls));
const luStyle = f => luShown(f.properties) ? { color: f.properties.color, weight: .4, fillColor: f.properties.color, fillOpacity: .5, opacity: 1 } : { opacity: 0, fillOpacity: 0 };
$('#luLegend').addEventListener('change', e => { const k = e.target.dataset.lu; if (!k) return; e.target.checked ? luHidden.delete(k) : luHidden.add(k); if (luLayer) luLayer.setStyle(luStyle); });
// The land-use analysis (js/landuse_view.js and its Spanish, loaded the first time it opens): docks under the map like the Economy workbench, which it replaces while open
// A part that loads on first use is ready when its scripts and its Spanish are all in. This waits for every piece to settle before it fails, so a retry
// never starts while a script of the failed try is still on its way (it would be added twice; its top-level const would throw).
function allIn(parts) {
  return Promise.allSettled(parts).then(r => { const bad = r.find(x => x.status === 'rejected'); if (bad) throw bad.reason; });
}
let luViewP = null, luJs = null;
function openLanduse() {
  if (typeof ecBenchClose === 'function' && typeof EC !== 'undefined' && EC.bench && EC.bench.open) ecBenchClose();
  let box = $('#luBench'); if (!box) { document.body.insertAdjacentHTML('beforeend', `<section class="econ-bench lu-bench" id="luBench" aria-label="${esc(T('Land-use analysis'))}" hidden></section>`); box = $('#luBench'); }
  luJs = luJs || new Promise((ok, fail) => { const s = document.createElement('script'); s.src = 'js/landuse_view.js?v=3'; s.onload = ok; s.onerror = () => { s.remove(); luJs = null; fail(new Error(s.src)); }; document.body.appendChild(s); });   // kept once it has run: only its Spanish is tried again
  luViewP = luViewP || allIn([I18N.load('landuse'), luJs]).catch(e => { luViewP = null; throw e; });
  luViewP.then(() => LanduseView.open(box), () => toast(T('The land-use analysis could not be loaded. Check your connection and try again.')));
}
$('#luAnalyze').onclick = openLanduse;
// The Region tab (js/region.js and its Spanish, loaded the first time the tab opens): a region's municipios added up (docs/regions.md)
let regionP = null;
const regionOpen = () => (regionP = regionP || allIn([I18N.load('region'), typeof Region !== 'undefined' ? Promise.resolve() : addJs('js/region.js?v=3')]).catch(e => { regionP = null; throw e; }))
  .then(() => whenReady()).then(() => Region.open(), () => toast(T('The region profile could not be loaded. Check your connection and try again.')));
const whenReady = () => ready ? Promise.resolve() : new Promise(ok => { const t = setInterval(() => { if (ready) { clearInterval(t); ok(); } }, 100); });   // the tab adds up municipalities.json: wait for it
async function loadLanduse() {
  if (!luLayer) {
    S.landuse = await getJson('data/landuse.geojson', T('land use'));
    if (!luLayer) luLayer = L.geoJSON(S.landuse, { interactive: false, pane: 'landuse', attribution: T('Land use: Junta de Planificación'), filter: f => !['water', 'road'].includes(f.properties.group), style: luStyle });
    const z = (S.meta.landuse || {}).calificacion || {};
    $('#luZoning').textContent = z.available ? T('Zoning districts (Calificación) are not shown yet.') : T('Zoning districts (Calificación) are not shown: the Junta de Planificación service was unavailable when this snapshot was built.');
  }
  if ($('#lyLanduse').checked) luLayer.addTo(map);
}
// Soils and Landslide susceptibility: js/soil.js, loaded on first use
let soilP = null;
const soilLoad = () => soilP || (soilP = allIn([I18N.load('soil'), addJs('js/soil.js?v=4')]).catch(e => { soilP = null; throw e; }));
$('#lySoil').onchange = guarded(async e => { $('#soilLegend').style.display = e.target.checked ? '' : 'none'; if (e.target.checked) { await soilLoad(); await loadSoil(); } else if (typeof soilOff === 'function') soilOff(); });
$('#lySlide').onchange = guarded(async e => { $('#slideLegend').style.display = e.target.checked ? '' : 'none'; if (e.target.checked) { await soilLoad(); slideOn(); } else if (typeof slideOff === 'function') slideOff(); });
// Slope and Contour lines: js/terrain.js, loaded on first use (GIS tools step 2; docs/slope.md)
let terrP = null;
const terrainLoad = () => terrP || (terrP = allIn([I18N.load('terrain'), addJs('js/terrain.js?v=3')]).catch(e => { terrP = null; throw e; }));
[['lySlope', 'slopeLegend', 'slopeOn', 'slopeOff'], ['lyContours', 'contourLegend', 'contoursOn', 'contoursOff'], ['lyWatersheds', 'shedLegend', 'shedsOn', 'shedsOff']].forEach(([id, lg, on, off]) => { $('#' + id).onchange = guarded(async e => { $('#' + lg).style.display = e.target.checked ? '' : 'none'; if (e.target.checked) { await terrainLoad(); await window[on](); } else if (window[off]) window[off](); }); });
async function loadComunidades() {
  if (!ceLayer) {
    S.comunidades = await getJson('data/comunidades.geojson', 'Comunidades Especiales');   // the program's name, the same in Spanish
    if (!ceLayer) ceLayer = L.geoJSON(S.comunidades, { interactive: false, pane: 'comunidades', attribution: 'Comunidades Especiales: Junta de Planificación', style: { color: '#FF4D38', weight: 1.2, fillColor: '#FF4D38', fillOpacity: .2 } });
  }
  if ($('#lyComunidades').checked) ceLayer.addTo(map);
}
const WCRP_PIN = Object.fromEntries([['done', 'img/wcrp-pin.svg'], ['open', 'img/wcrp-pin-open.svg']].map(([k, url]) => [k, L.icon({ iconUrl: url, iconSize: [26, 33], iconAnchor: [13, 31] })]));
async function loadWcrp() {
  if (!wcrpLayer) {
    const fc = await getJson('data/wcrp.geojson', T('WCRP communities'));
    if (wcrpLayer) return;
    const at = new Map();   // group plans that share a point, so every one of them can be clicked
    fc.features.forEach(f => { const k = f.geometry.coordinates.join(); at.set(k, [...(at.get(k) || []), f.properties]); });
    wcrpLayer = L.layerGroup([...at].map(([k, list]) => {
      // the centre figure of the WCRP logo: solid for an approved plan, an outline for a plan in progress
      const [lng, lat] = k.split(',').map(Number), names = list.map(p => p.comunidad).join(' · ');
      return L.marker([lat, lng], { icon: list.some(p => p.estado === 'plan_aprobado') ? WCRP_PIN.done : WCRP_PIN.open, alt: names, zIndexOffset: 1000 })
        .bindTooltip(names, { direction: 'top', offset: [0, -28] }).bindPopup(() => wcrpPopup(list), { maxWidth: 320, offset: [0, -24] });
    }), { attribution: T('WCRP communities: Foundation for Puerto Rico') });
  }
  if ($('#lyWcrp').checked) wcrpLayer.addTo(map);
}
async function loadBarrios() {
  if (!barrioLayer) {
    S.barrios = await getJson('data/barrios.geojson', 'barrios');   // the same word in Spanish
    if (!barrioLayer) barrioLayer = L.geoJSON(S.barrios, { interactive: false, pane: 'barrios', attribution: T('Barrios: US Census Bureau'), style: { color: '#205D7B', weight: .8, dashArray: '3 3', fill: false, opacity: .8 } });
  }
  if ($('#lyBarrios').checked) barrioLayer.addTo(map);
}
// The surface heat images (heat.py: summer mornings, Landsat; ecostress.py: summer nights; surface_image.py; HANDOFF decision 88): one Web Mercator picture at a time,
// under every other layer. Its colours follow the land in view by default (core/surfscale.js, loaded with it), or Puerto Rico's own scale; the legend switches both
let surfLayer = null, surfMode = 'view', surfTime = 'day';
const surfs = {}, SURF_FILE = { day: 'data/heat_surface.json', night: 'data/night_heat_surface.json' };
const surfOpen = (t) => surfs[t] || (surfs[t] = (async () => { const m = await getJson(SURF_FILE[t], T('surface heat')), o = await Core.surfscale.open('data/' + m.image, m); o.meta = m; return o; })().catch(e => { delete surfs[t]; throw e; }));
async function loadSurf() {
  if (!window.Core.surfscale) await addJs('js/core/surfscale.js?v=4');
  const o = await surfOpen(surfTime), [w, s, e, n] = o.meta.bounds;
  if (!surfLayer) { surfLayer = L.imageOverlay('data/' + o.meta.image, [[s, w], [n, e]], { pane: 'surfheat', opacity: .8, interactive: false, attribution: T('Surface heat: USGS Landsat, NASA ECOSTRESS') }); map.on('moveend', surfPaint); }
  if ($('#lySurfHeat').checked) { surfLayer.addTo(map); surfPaint(); }
}
function surfPaint() {   // after a move or a switch: the image of the time shown, coloured for the land in view (or Puerto Rico), and the legend's numbers
  if (!surfLayer || !map.hasLayer(surfLayer)) return;
  clearTimeout(surfPaint.t);
  surfPaint.t = setTimeout(async () => {
    const o = await surfOpen(surfTime), [w, s, e, n] = o.meta.bounds, b = map.getBounds();
    const sc = (surfMode === 'view' && o.stats([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()])) || o.island;
    surfLayer.setBounds(L.latLngBounds([s, w], [n, e])); surfLayer.setUrl(await o.paint(sc)); $('#surfLegend').innerHTML = o.legend(sc, surfMode, surfTime);
  }, 250);
}
$('#surfLegend').addEventListener('click', e => { const m = e.target.closest('[data-surf-mode],[data-surf-time]'); if (!m) return; if (m.dataset.surfMode) surfMode = m.dataset.surfMode; else surfTime = m.dataset.surfTime; surfPaint(); });
async function loadProt() {
  if (!protLayer) {
    S.prot = await getJson('data/protected.geojson', T('protected areas'));
    if (!protLayer) protLayer = L.geoJSON(S.prot, { interactive: false, style: protStyle, attribution: T('Protected areas: USGS PAD-US') });
  }
  if ($('#lyProt').checked) protLayer.addTo(map);
}

(async function init() {
  try {
    // the first load is the snapshot, the municipality statistics and boundaries, and the catalog (domains and headline figures); the tourism listings load when the module is used (ensurePlaces)
    [S.meta, S.muni, S.muniFc, S.catalog] = await Promise.all([loadJson('data/meta.json', T('snapshot')), loadJson('data/municipalities.json', T('municipality statistics')), loadJson('data/municipios.geojson', T('boundaries')), fetchJson('data/catalog.json').catch(() => null)]);
    renderAbout(); renderCatChips();
    // a municipality with no mapped stops has no transit measurement, not a measured 0%: none of the place shares that depend on stops is shown for it
    Object.values(S.muni).forEach(m => { if (!m.transit_stops) ['transit_pct', 'acc_walk400_pct', 'acc_walk800_pct', 'acc_wfreq400_pct', 'acc_cur400_pct', 'acc_cur800_pct', 'acc_freq400_pct', 'acc_sat400_pct', 'acc_sun400_pct', 'acc_hub400_pct', 'acc_paper_pct'].forEach(k => { m[k] = null; }); });
    $('#muniSel').insertAdjacentHTML('beforeend', Object.keys(S.muni).sort((a, b) => a.localeCompare(b, 'es')).map(n => `<option>${esc(n)}</option>`).join(''));
    $('#muniSel').onchange = e => e.target.value && selectMuni(e.target.value);
    muniLayer = L.geoJSON(S.muniFc, {
      style: muniStyle, attribution: Th('Boundaries &amp; population: US Census 2020'),
      onEachFeature: (f, l) => {
        const n = f.properties.municipality;
        l.on('mouseover', () => { const m = S.muni[n]; $('#hoverInfo').innerHTML = Th('<b>{name}</b>{assets} tourism places · {pct}% in flood hazard area · {pop} residents', { name: n, assets: fmt(m?.assets), pct: m?.sfha_pct ?? '—', pop: fmt(m?.population_2020) }); $('#hoverInfo').classList.add('show'); l.setStyle({ weight: 2.5 }); });
        l.on('mouseout', () => { $('#hoverInfo').classList.remove('show'); muniLayer.resetStyle(l); });
        const c = l.getBounds().getCenter();
        labelLayer.addLayer(L.marker(c, { icon: L.divIcon({ className: 'muni-label', html: esc(n), iconSize: [100, 14], iconAnchor: [50, 7] }), interactive: false, pane: 'muni' }));
      },
    });
    if ($('#lyMuni').checked) map.addLayer(muniLayer);   // off when the map opens (2026-11-13); a link with l=muni, or the Municipality tab, turns it on
    map.on('zoomend', () => { map.getZoom() >= 10 && $('#lyMuni').checked ? map.addLayer(labelLayer) : map.removeLayer(labelLayer); });
    rebuildPlaces();   // the pins are off at the start and the listings are not loaded: this only writes the size hint beside the switch
    ready = true;
    applyHash();
    if (regionTab) showTab('region');   // a regional profile's "Open on the map": once the municipalities are in
    if (!location.hash) writeHash();
    if (document.readyState === 'loading') await new Promise(r => document.addEventListener('DOMContentLoaded', r, { once: true }));   // the scripts after this one (transit, economy, chat) must have run before their start hook is called
    if (typeof onMapReady === 'function') onMapReady();
  } catch (e) {
    $('#loader').classList.add('error');
    $('#loaderText').innerHTML = Th('The map data did not load ({error}). Check your connection, then <button type="button" class="btn" onclick="location.reload()">try again</button>.', { error: e.message });
    return;
  }
  $('#loader').classList.add('hide'); performance.mark('ready');   // the ready moment (tests/browser/throttle.js)
  if (MT_LINK) openToolLink(MT_LINK);
  startBasemap();
  startRegionFilter();
  Promise.all([addJs('js/mapextras.js?v=4'), I18N.load('mapextras')]).then(() => MapExtras.init(), () => { /* the extras are optional: the map works without them */ });   // town names, Islands (js/mapextras.js)
})();
/** The base map, after ready: js/core/basemap.js loads MapLibre and its Leaflet bridge and draws OpenFreeMap under the panes; without WebGL, or when the
 *  provider does not answer, the map goes on over its plain background with a notice (docs/basemap.md). It also wires the "Base map" switcher of the Layers
 *  tab (#basemap): a pick changes only the base map, is kept in the address (bm=) and the 3D link, and in this browser as the viewer's default. */
function startBasemap() {
  const off = () => map.getContainer().dataset.basemap = 'off';
  (window.Core.basemap ? Promise.resolve() : addJs('js/core/basemap.js?v=7')).then(() => {
    const B = Core.basemap;
    bmH = Core.basemap.leaflet(map, { style: bmLink || B.stored(), onState: (st, msg) => { osmiSync(st); if (st === 'off') Core.basemap.notice(map.getContainer(), msg); } });   // its own notice: the message bar may hold an Undo
    // a pick is kept as the viewer's default only once its style has loaded (keep), as in 3D; a style that loads also takes away a pending failure notice
    bmCtl = B.control($('#basemap'), { value: bmH.name, onPick: n => { bmLink = n; bmH.set(n, { keep: true }); writeHash(); } });
  }, () => { off(); osmiSync('off'); });
}
// The region filter of Reference (js/core/regionfilter.js and data/geo/regions.json, loaded on use: when the Reference group is first opened, or at ready when
// the address has rg=; docs/regions.md, "The region filter"; decision 113):
// a region's municipios outlined, the rest of the island faded, the map framed on it; the data layers are not cut. Kept in the address (rg=) and the 3D link.
let rgLink = Core.viewstate.parse(location.hash).rg, rfCtl = null;
/** Runs go() once el can be seen: now when `now` is set or el is not in a closed group of the Layers tab (common.js initFolds), else when its group opens. */
function whenShown(el, now, go) {
  const body = el && el.closest('.fold-body');
  if (now || !body || !body.hidden) return go();
  const mo = new MutationObserver(() => { if (!body.hidden) { mo.disconnect(); go(); } });
  mo.observe(body, { attributes: true, attributeFilter: ['hidden'] });
}
function startRegionFilter() {
  const fit = !/[#&]c=/.test(location.hash) || regionTab;   // an address with its own camera keeps it; the regional profile's link frames the region
  whenShown($('#regionFilter'), rgLink, () => (window.Core.regionfilter ? Promise.resolve() : addJs('js/core/regionfilter.js?v=1')).then(() => fetchJson('data/geo/regions.json')).then(d => {
    rfCtl = Core.regionfilter.control($('#regionFilter'), { regions: d.regions, features: S.muniFc.features, view: Core.regionfilter.leaflet(map, L), value: rgLink, fit, onPick: id => { rgLink = id; writeHash(); } });
    rgLink = rfCtl.value(); writeHash();   // an unknown region in the address is dropped
  }, () => { $('#regionFilterNote').textContent = T('The regions could not be loaded. Check your connection and reload the page.'); }));
}
// The OSM inspector: the "Inspect map" toggle under the base map; core/osminspect.js and its Spanish load the first time it is used (docs/basemap.md, section 8).
// It works only while an OpenStreetMap base map is drawn (not the USGS pictures); while it is on it takes the map's clicks before the observatory's layers.
let osmiP = null, osmiM = null;
function osmiSync(st) {
  const pics = st === 'on' && bmH && !Core.basemap.inspectable(bmH.name);   // a USGS style: picture tiles, nothing to inspect
  $('#osmInspect').disabled = st !== 'on' || pics;
  $('#osmInspectNote').textContent = pics ? T('The inspector reads only the OpenStreetMap base maps: choose one of them to use it.') : st === 'none' ? T('Turn on a base map to inspect it.') : st === 'off' ? T('The base map is unavailable, so there is nothing to inspect.') : st === 'loading' ? T('Available once the base map has loaded.') : T('Click a street or place on the base map to see what it is in OpenStreetMap.');
  if ((st !== 'on' || pics) && osmiM) osmiM.off();
}
$('#osmInspect').onclick = () => (osmiP || (osmiP = allIn([I18N.load('osminspect'), window.Core.osminspect ? 0 : addJs('js/core/osminspect.js?v=3')]).then(() => (osmiM = Core.osminspect.leaflet(map, () => bmH, $('#osmInspect')))).catch(e => { osmiP = null; throw e; })))
  .then(m => m.toggle(), () => toast(T('The map inspector could not be loaded. Check your connection and try again.')));
