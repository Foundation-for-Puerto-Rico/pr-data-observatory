/* PR Data Observatory — 3D + Time view. Shared helpers are in common.js.
   MapLibre GL renders terrain, buildings and the analytic layers (terrain-aware);
   deck.gl renders the animated layers (transit trips, hurricane tracks). All data is static JSON from build.py. */

const pad2 = (n) => String(n).padStart(2, '0');

const HELP = {
  places3d: [T('Tourism places'), T('Overture Maps places classified into the VIEWPR taxonomy, confidence ≥ 0.50, places of worship excluded. Heat at island scale, coloured points when zoomed in; points inside a FEMA flood hazard area have a dark rim. Holiday rentals and rented units named by a street address are counted in their municipality but not drawn. Private homes, residential buildings and care, shelter or treatment services are not tourism and are left out.')],
  comunidades: [T('Comunidades Especiales'), T('The 713 communities designated under Ley 1-2001, as delimited by the Junta de Planificación in 2006. Draped on the terrain; click inside one for its name, housing units and the hazards residents reported in the 2006 inventory. Communities designated after 2006 may be missing.')],
  wcrp: [T('WCRP communities'), T('The communities in FPR\'s Whole Community Resilience Planning program, with the state of each plan (approved by the Puerto Rico Department of Housing, or in progress) and the organisation that leads it. The plans draw their area only in a PDF map, so each community is one approximate point: the popup says where the point comes from. The marker is the centre figure of the WCRP logo: solid orange for an approved plan, an orange outline for a plan in progress.')],
  surfheat: [T("Surface heat, summer mornings and nights"), T("The temperature of the ground's surface (roofs, pavement, soil and tree canopy) on clear summer mornings, measured by the thermal sensor of Landsat 8 and 9 at about 10:30, June to September of the last three summers: the median of each 60 m cell's clear views. It is not the air temperature. Blue is cooler than Puerto Rico's median surface, red hotter; the mountains are cooler partly because they are higher. Mona, Monito and Desecheo are left out. The legend's Night switch shows instead how warm the surface stays on clear summer nights (NASA ECOSTRESS, 21:00 to 06:00).")],
  flood: [T('Flood zones'), T('Special Flood Hazard Areas (1% annual chance) in blue, 0.2% annual chance in light blue, from the National Flood Hazard Layer. Draped on the terrain.')],
  slr: [T('Sea level rise'), T('NOAA Sea Level Rise Viewer inundation tiles, streamed live. The Time tab turns a year and a NOAA 2022 scenario into the nearest whole foot (1–10 ft). Indicative, not a forecast.')],
  trips: [T('Scheduled vehicles'), T('Every scheduled weekday trip in the ATI and municipal GTFS feeds replayed against the clock: positions are interpolated between consecutive stops using the timetable, so they show where vehicles are scheduled to be, not real-time locations.')],
  storms: [T('Hurricane tracks'), T('NOAA HURDAT2 best tracks for every Atlantic cyclone since 1851 that passed within 250 km of Puerto Rico. Colour is the Saffir-Simpson category of the peak wind while near the island; the filter uses the same value.')],
  // the layers the 2D map has too: the same texts as its help (help.js), but the boundaries, which have columns here instead of shading
  muni: [T('Municipal boundaries'), T('2020 Census boundaries of the 78 municipios, on when the view opens. Click a municipality for its summary; Columns by municipality compares a measure across them.')],
  barrios: [T('Barrios'), T('Sub-municipal districts (the US Census Bureau calls them county subdivisions). Dashed outlines; click inside one for its tourism places, flood exposure and transit access. Boundaries are the 2020 Census subdivisions.')],
  stops: [T('Transit stops'), T('Boarding points: ATI GTFS stops (official, with routes served and weekday trips) plus OpenStreetMap bus stops island-wide (municipal systems, públicos). OSM stops within 30 m of an official stop are folded into it.')],
  taxi: [T('Taxi stands and EV charging'), T('Taxi stands and electric-vehicle charging stations mapped in OpenStreetMap. Ride-hailing (Uber) is shown per municipality as a yes/no listing because Uber publishes no coverage or availability data.')],
  walk: [T('400 m walk radius'), T('A quarter mile (400 m) is the standard planning distance people will walk to a bus stop. Rings are drawn when zoomed in; the statistics for tourism places and residents use the same straight-line distance.')],
  gaps: [T('Service gaps'), T('Census blocks with 40 or more residents whose nearest scheduled stop is more than an 800 m walk away, along mapped roads (a block with no mapped road within 150 m is measured in a straight line). Circle size follows the number of residents. Stops from expired timetables still count, so real gaps are larger. The road map has no footpaths, so the walk is an estimate.')],
  xfer: [T('Integration points'), T('Places where a stop of one transit system is within 250 m of a stop of another system. These are the natural places to align timetables, fares and signage.')],
};
const SCENARIOS = { // NOAA 2022 global mean sea level scenarios, metres above 2000 baseline (approx. from the report's tables)
  int_low:  { label: T('Intermediate-Low'),  pts: [[2020, .07], [2050, .24], [2100, .5], [2150, .8]] },
  int:      { label: T('Intermediate'),      pts: [[2020, .07], [2050, .3], [2100, 1.0], [2150, 1.9]] },
  int_high: { label: T('Intermediate-High'), pts: [[2020, .07], [2050, .37], [2100, 1.5], [2150, 2.9]] },
  high:     { label: T('High'),              pts: [[2020, .07], [2050, .44], [2100, 2.0], [2150, 3.9]] },
};
const CAT_COLORS = { 0: '#8C8E8E', 1: '#5FAFDA', 2: '#A6BF33', 3: '#FFA600', 4: '#FF4D38', 5: '#8C180D' };
// badge colours: FPR tint backgrounds with their dark text, all above 4.5:1
const STORM_BADGE = { 0: ['#E6E6E6', '#2A2E2E'], 1: ['#BDE0F2', '#205D7B'], 2: ['#E4EFB8', '#47560F'], 3: ['#FFE9A8', '#8A5200'], 4: ['#FFD0C9', '#B82415'], 5: ['#B82415', '#FFFFFF'] };
const RAMP = Core.palettes.RAMPS.blue;
const stormName = (s) => s.name === 'Unnamed' ? T('Unnamed') : s.name;   // HURDAT2 data: most storms before naming began are "Unnamed"
const KIND_LABEL = { transit_stop: T('Transit stop'), bus_station: T('Bus station'), rail_station: T('Rail station'), ferry_terminal: T('Ferry terminal'), airport: T('Airport') };   // stop kinds as a result label
const ROUTE_LABEL = { Bus: T('Bus'), Ferry: T('Ferry') };   // route types from the data; 'Público' and 'Tren Urbano' are names and stay as they are
const METRIC = {
  assets: { label: T('Tourism places'), d: 0 }, sfha_pct: { label: T('% in flood hazard area'), d: 0, pct: true }, transit_pct: { label: T('% within 400 m of any mapped stop'), d: 0, pct: true },
  acc_walk400_pct: { label: T('% within a 400 m walk of a stop with a current timetable'), d: 0, pct: true },
  acc_wfreq400_pct: { label: T('% within a 400 m walk of a frequent stop (20+ weekday departures)'), d: 0, pct: true },
  acc_cur400_pct: { label: T('% within 400 m (straight line) of a stop with a current timetable'), d: 0, pct: true },
  acc_freq400_pct: { label: T('% within 400 m (straight line) of a frequent stop (20+ weekday departures)'), d: 0, pct: true },
  acc_paper_pct: { label: T('% near only an expired or unscheduled stop'), d: 0, pct: true },
  assets_per_1000_residents: { label: T('Places per 1,000 residents'), d: 1 }, assets_per_km2: { label: T('Places per km²'), d: 1 }, population_2020: { label: T('Population 2020'), d: 0 },
  pop_change_pct: { label: T('Population change 2010→2020'), d: 1, pct: true, diverging: true },
  pop_walk_active_pct: { label: T('% of residents within a 400 m walk of a stop with a current timetable'), d: 0, pct: true },
  pop_served_pct: { label: T('% of residents within 400 m (straight line) of a scheduled stop (incl. expired timetables)'), d: 0, pct: true },
  pop_served_active_pct: { label: T('% of residents within 400 m (straight line) of a stop with a current timetable'), d: 0, pct: true },
  affordability_ratio: { label: T('Affordability ratio (value ÷ max loan)'), d: 2 }, median_home_value: { label: T('Median home value ($)'), d: 0 }, renter_cost_burden_pct: { label: T('% cost-burdened renters'), d: 0, pct: true }, seasonal_pct: { label: T('% seasonal / recreational units'), d: 1, pct: true }, protected_land_pct: { label: T('% Suelo Rústico Especialmente Protegido'), d: 0, pct: true },
  // the measures of the 2D map's shading menu (app.js CHORO) with their labels; its three "shown" measures count the places its filters let through, which this view does not have
  median_gross_rent: { label: T('Median gross rent ($/mo)'), d: 0 }, vacancy_pct: { label: T('% vacant units'), d: 0, pct: true }, gross_rent_change_pct: { label: T('Rent change 2012 → latest'), d: 0, pct: true, diverging: true }, urban_pct: { label: T('% Suelo Urbano'), d: 0, pct: true },
  pop_walk_pct: { label: T('% of residents within a 400 m walk of a scheduled stop (incl. expired timetables)'), d: 0, pct: true }, transit_stops: { label: T('Transit stops & stations'), d: 0 }, uber_listed: { label: T('Uber lists service'), d: 0, bool: true },
  in_sfha: { label: T('Places in flood hazard area'), d: 0 }, in_protected: { label: T('Places inside protected areas'), d: 0 }, with_website: { label: T('Places with a website'), d: 0 },
  acc_walk800_pct: { label: T('% of places within an 800 m walk of a stop with a current timetable'), d: 0, pct: true },
  acc_sat400_pct: { label: T('% of places within 400 m (straight line) of a stop with Saturday service'), d: 0, pct: true }, acc_sun400_pct: { label: T('% of places within 400 m (straight line) of a stop with Sunday service'), d: 0, pct: true },
};
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const VIEWS = { sj: { center: [-66.09, 18.44], zoom: 12.6, pitch: 62, bearing: -20 }, yunque: { center: [-65.79, 18.3], zoom: 11.5, pitch: 68, bearing: 30 }, ponce: { center: [-66.61, 18.0], zoom: 12.5, pitch: 60, bearing: 10 }, island: { center: [-66.45, 18.2], zoom: isMobile() ? 6.6 : 8.4, pitch: isMobile() ? 35 : 50, bearing: -8 } };

const S = { meta: {}, places: null, muni: {}, muniFc: null, flood: null, prot: null, routes: null, transport: null, trips: null, storms: null,
  cats: new Set(Object.keys(CATEGORY_META)), clock: 25200, playing: false, speed: 60, mode: 'day', stormYear: null, stormPlaying: false, pickNoCard: false };

// A blocked CDN would otherwise leave the loader spinning forever.
function failLoader(msg) {
  const l2d = document.querySelector('.views a[href^="index.html"]'); if (l2d && window.Core && Core.viewstate) l2d.href = 'index.html' + location.search + Core.viewstate.write('3d', location.hash, {});   // the 2D map, where this view was asked to open
  $('#loader').classList.add('error'); $('#loaderText').innerHTML = `${esc(msg)} ${Th('Check your connection, then <button type="button" class="btn" onclick="location.reload()">try again</button>.')}`; }
if (typeof maplibregl === 'undefined') { failLoader(T('The 3D map libraries did not load.')); throw new Error('3D libraries unavailable'); }
const webglOk = () => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; } };
if (!webglOk()) { failLoader(T('This browser or device cannot draw the 3D map (WebGL is unavailable). The 2D map and the Housing page work without it.')); throw new Error('WebGL unavailable'); }

// ── Map ────────────────────────────────────────────────────────────────────
// The base map (js/core/basemap.js, docs/basemap.md): bm= in the address, else the viewer's default kept in this browser, else Liberty. name: the style shown;
// chosen: bm= is written in the address and the 2D link (a pick, or a link that had it); off: the style failed at the start (the plain fallback is shown);
// base: the ids of the base style's layers and sources (what a switch replaces; everything else is the observatory's); images: what the view added with
// addImage (the WCRP pins), given again when a new style asks for them.
// The view state shared with the 2D map through the address (js/core/viewstate.js, docs/view-state.md). IN: what the address asked when the page opened.
// VS: ready, once the view has applied it (until then nothing writes the address); applying, while it does; measure, whether the columns were changed here
// (until then s=, e= and ey= stay as they came: the 2D map's Economy layers keep their ramps and classes); muni, the municipality whose card is open.
const IN = Core.viewstate.parse(location.hash);
const VS = { ready: false, applying: false, measure: false, muni: null, timer: 0, last: 0 };
// hid: the base layers hidden by a failure, with the visibility each had (put back if the tiles come again); watching: the sources whose tiles kept failing,
// still loading under an invisible layer each (watchBase), or null; recovered: the base map came back once on this style (it is not watched a second time).
const OSMI = { p: null, m: null };   // the OSM inspector, loaded on first use (osmiSync, below)
const BM = { name: Core.basemap.pick('3d', location.hash), chosen: !!Core.basemap.fromHash(location.hash), off: false, why: null, base: null, images: {}, ctl: null, busy: false, hid: {}, watching: null, recovered: false };
const map = new maplibregl.Map({
  container: 'map', style: Core.basemap.style('3d', BM.name), center: VIEWS.island.center, zoom: VIEWS.island.zoom, pitch: VIEWS.island.pitch, bearing: VIEWS.island.bearing,
  maxPitch: 80, minZoom: 5.5, maxBounds: [[-69.5, 16.8], [-63.5, 19.6]], antialias: true, attributionControl: false, hash: false, cooperativeGestures: window.self !== window.top,
  locale: { 'NavigationControl.ZoomIn': T('Zoom in'), 'NavigationControl.ZoomOut': T('Zoom out'), 'NavigationControl.ResetBearing': T('Reset bearing to north'), 'GeolocateControl.FindMyLocation': T('Find my location'), 'GeolocateControl.LocationNotAvailable': T('Location not available'), 'AttributionControl.ToggleAttribution': T('Toggle attribution'), 'Popup.Close': T('Close popup'), 'Marker.Title': T('Map marker'), 'CooperativeGesturesHandler.WindowsHelpText': T('Use Ctrl + scroll to zoom the map'), 'CooperativeGesturesHandler.MacHelpText': T('Use ⌘ + scroll to zoom the map'), 'CooperativeGesturesHandler.MobileHelpText': T('Use two fingers to move the map') },
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
// The base map's credits (OpenStreetMap, OpenMapTiles, OpenFreeMap, or the USGS National Map: js/core/basemap.js), in the page's language, in place of the provider's
// own on its source (its TileJSON brings them; a USGS style carries ours), so they show once, and only while the base map is drawn: the credit box lists the sources
// in use (PR #94). They are the credits of the style going in (BM.next during a switch). This listener comes before the credit box's own, which then reads the new
// text. The terrain source carries its own credit (setupScene).
let creditOn = null;
const bmCredits = () => Core.basemap.credits('3d', null, BM.next || BM.name);
map.on('sourcedata', e => {
  const src = e && e.sourceDataType === 'metadata' && map.getSource(e.sourceId);
  if (!src || !Core.basemap.isProvider(src.attribution, '3d')) return;
  if (!creditOn) creditOn = e.sourceId;
  src.attribution = creditOn === e.sourceId ? bmCredits() : '';
});
// The credit box: the data credits, and a short note when the base map is switched off ("Base map off") or unavailable. Open on a wide screen; on a phone it
// shows the full credits when the map opens, then folds behind a round "i" button (Core.basemap.fold: after 5 s or the first touch of the map; HANDOFF decision 65),
// like the 2D and WCRP maps. It lets map clicks through (twin3d.css); a switch of base map or a failure builds it again with the new note, in the state the viewer left.
const DATA_CREDITS = Th('Places © <a href="https://overturemaps.org/">Overture Maps Foundation</a> · FEMA NFHL · NOAA (SLR, HURDAT2) · USGS PAD-US · US Census · ATI GTFS');
let attrib = null;
function setAttribution() {
  const note = BM.off ? 'off' : BM.name === 'none' ? 'none' : null;
  const line = DATA_CREDITS + (note ? ` · <span class="bm-status">${esc(Core.basemap.text(note))}</span>` : '');
  if (attrib) map.removeControl(attrib);
  attrib = new maplibregl.AttributionControl({ compact: false, customAttribution: line }); map.addControl(attrib, 'bottom-left');
  Core.basemap.fold(map.getContainer().querySelector('.maplibregl-ctrl-bottom-left > .maplibregl-ctrl-attrib'), { map: map.getContainer() });
}
setAttribution();

// deck.gl (about 356 KB compressed) draws only the animated layers, so it loads once the view is ready (start), with the same file and integrity 3d.html had;
// until then renderDeck has nothing to draw on and deckAt finds nothing (docs/performance.md, "Make room 4").
const DECK = { src: 'https://unpkg.com/deck.gl@9.0.38/dist.min.js', integrity: 'sha384-tEG529toczQRv/bqd2PyHy5vTO49FMjQri0c1oB44gSkYiNouZz8L9yNTVx0YGl+' };
let overlay = null;
const deckLoad = () => (window.deck ? Promise.resolve() : addJs(DECK.src, DECK.integrity)).then(() => { overlay = new deck.MapboxOverlay({ interleaved: false, layers: [] }); map.addControl(overlay); renderDeck(); deckNoTab(); requestAnimationFrame(deckNoTab); })   // deck.gl's box gets its tabindex on its first frame
  .catch(() => toast(T('The vehicles and storm tracks could not be loaded. Check your connection and reload the page.'), 10000));
// deck.gl's layer over the map takes no input of its own (the map's canvas has the keys), but its box had tabindex 0: a Tab stop with no name after the map. Out of the Tab order.
const deckNoTab = () => { const w = map.getContainer().querySelector('#deckgl-overlay'), b = w && w.parentElement; if (b && b.getAttribute('tabindex') === '0') b.tabIndex = -1; };

function firstSymbolLayer() { return (map.getStyle().layers.find(l => l.type === 'symbol') || {}).id; }
// the base map's vector source (OpenFreeMap's): not one of the view's own (the buildings OpenStreetMap lacks, a PMTiles file), which a switch carries into a
// style that has none (a USGS map, "No base map")
function vectorSourceId() { const src = map.getStyle().sources; return Object.keys(src).find(k => src[k].type === 'vector' && Core.basemap.isProvider(src[k].url || (src[k].tiles || [])[0])); }
// Where a layer added on use goes. The areas (flood, land use, protected areas, Comunidades Especiales, sea level) go in under the barrio lines and the municipal
// lines (areasBefore), the four that a click answers in the order of AREAS from the bottom, as the panes of the 2D map, whichever was switched on first (areaBefore).
// The route lines, then the circles and points of SLOTS go above the areas and the columns and under the base map's labels, in this order from the bottom, so none
// of them hides the flood or land-use areas, and every point is drawn over the route lines, as on the 2D map (its routes pane is under its markers): a click on a
// stop or a cluster on a route line opens the stop or zooms in (the click dispatcher). The stations, WCRP pins, places and the planned route stay on top.
const SLOTS = ['routes-', 'gaps-', 'rings-', 'stops-', 'taxi-', 'xfer-', 'fac-'];
// the base map's first label; on a style with none (the plain fallback, "No base map"), the first of the layers kept on top (TOP_RE), else the top
const labelsBefore = () => (map.getStyle().layers.find(l => l.type === 'symbol' && l.source === vectorSourceId()) || map.getStyle().layers.find(l => TOP_RE.test(l.id)) || {}).id;
function slotBefore(prefix) { const up = SLOTS.slice(SLOTS.indexOf(prefix) + 1); return (map.getStyle().layers.find(l => up.some(p => l.id.startsWith(p))) || {}).id || labelsBefore(); }
const areasBefore = () => map.getLayer('barrios-hit') ? 'barrios-hit' : 'muni-line';
const AREAS = ['slide-img', 'landuse-fill', 'soil-fill', 'prot-fill', 'flood-fill', 'ce-fill', 'ce-line'];   // the landslide tiles and the soils (js/soil3d.js) in the order of the 2D map's panes
const areaBefore = (id) => AREAS.slice(AREAS.indexOf(id) + 1).find(x => map.getLayer(x)) || areasBefore();

function setupScene() {
  const TR = Core.basemap.TERRAIN;   // AWS Terrain Tiles, Terrarium encoding, and its credit with the USGS line its attribution page asks for (js/core/basemap.js)
  map.addSource('dem', { type: 'raster-dem', tiles: TR.tiles, encoding: TR.encoding, tileSize: TR.tileSize, maxzoom: TR.maxzoom, attribution: Core.basemap.terrainCredit() });
  map.addSource('dem-hill', { type: 'raster-dem', tiles: TR.tiles, encoding: TR.encoding, tileSize: TR.tileSize, maxzoom: TR.maxzoom });
  map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem-hill', paint: { 'hillshade-exaggeration': .35, 'hillshade-shadow-color': '#1f3a4a', 'hillshade-highlight-color': '#ffffff', 'hillshade-illumination-anchor': 'map', 'hillshade-illumination-direction': +$('#sunDir').value } }, firstSymbolLayer());
  setTerrain(true); setSky(); baseExtras();
}
function setSky() { try { map.setSky({ 'sky-color': '#9ec9e6', 'horizon-color': '#dfeef7', 'fog-color': '#dfeef7', 'sky-horizon-blend': .6, 'horizon-fog-blend': .7, 'fog-ground-blend': .85 }); } catch (e) { /* older MapLibre */ } }
/** The "3D buildings" switch drives both building layers: the base map's (OpenStreetMap) and the ones it lacks (buildings_gap.pmtiles; docs/buildings3d.md). */
const BLD = ['buildings-3d', 'buildings-3d-gap'];
function showBuildings(on) { BLD.forEach(id => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')); }
/** Overture's buildings that OpenStreetMap does not have (Google and Microsoft, traced by machine learning): one PMTiles file, read with the PMTiles library. */
let gapProto = false;
function addGapBuildings() {
  if (map.getLayer('buildings-3d-gap') || !window.pmtiles || !map.getLayer('buildings-3d')) return;
  if (!gapProto) { maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile); gapProto = true; }
  if (!map.getSource('bgap')) map.addSource('bgap', { type: 'vector', url: 'pmtiles://' + new URL('data/buildings_gap.pmtiles', location.href).href, attribution: '© <a href="https://docs.overturemaps.org/attribution" target="_blank" rel="noopener">Overture Maps Foundation</a>' });
  const ids = map.getStyle().layers.map(l => l.id), next = ids[ids.indexOf('buildings-3d') + 1];   // just over the base map's buildings
  const paint = {};
  ['fill-extrusion-opacity', 'fill-extrusion-vertical-gradient'].forEach(k => { const v = map.getPaintProperty('buildings-3d', k); if (v !== undefined) paint[k] = v; });
  map.addLayer({ id: 'buildings-3d-gap', type: 'fill-extrusion', source: 'bgap', 'source-layer': 'b', minzoom: 13, layout: { visibility: $('#lyBuildings').checked ? 'visible' : 'none' },
    paint: { ...paint, 'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'height'], 6], 0, '#e8e2d8', 30, '#c9c2b6', 90, '#8f877b'], 'fill-extrusion-height': ['coalesce', ['get', 'height'], 6], 'fill-extrusion-base': ['coalesce', ['get', 'min_height'], 0] } }, next);
}
/** What the base style feeds: the 3D buildings (its building tiles; none on "No base map") and the stop counts (its fonts), added when the style has them and they are missing. */
function baseExtras() {
  const vs = vectorSourceId();
  if (vs) {
    // the base style draws its own buildings (OpenFreeMap liberty: 'building-3d', no height fallback): drop them so ours is the only one and the switch hides all
    map.getStyle().layers.filter(l => l.type === 'fill-extrusion' && l.source === vs && l.id !== 'buildings-3d').forEach(l => map.removeLayer(l.id));
    const ids = map.getStyle().layers.map(l => l.id), above = ids[ids.indexOf('hillshade') + 1];   // just over the hillshade, under every data layer, as at the start
    if (!map.getLayer('buildings-3d')) map.addLayer({ id: 'buildings-3d', type: 'fill-extrusion', source: vs, 'source-layer': 'building', minzoom: 13, layout: { visibility: $('#lyBuildings').checked ? 'visible' : 'none' },
      paint: { 'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 6], 0, '#e8e2d8', 30, '#c9c2b6', 90, '#8f877b'], 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 6], 'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0], 'fill-extrusion-opacity': .85 } }, above || firstSymbolLayer());
  }
  if (vs) addGapBuildings();
  else if (map.getLayer('buildings-3d-gap')) map.removeLayer('buildings-3d-gap');   // they fill the base map's gaps: with no OpenStreetMap buildings ("No base map", a USGS map) they would stand alone
  if (map.getSource('stops') && !map.getLayer('stops-count')) addStopsCount(map.getLayer('stops-pts') ? 'stops-pts' : slotBefore('stops-'));
}
// ── The base map switcher (the 3D scene group; js/core/basemap.js) ──────────
// Only the base style changes. The observatory's sources and layers (terrain, hillshade, 3D buildings, every data layer) are carried into the new style by
// transformStyle, in their order: those under the old style's labels go under the new labels, the rest on top (TOP_RE when the old style had no labels).
// deck.gl draws on its own canvas and is untouched; click handlers are bound to layer ids and stay. Terrain and sky are set again once the style is in; the
// buildings and stop counts, which need the base tiles and fonts, are dropped on "No base map" and come back with a style that has them (baseExtras).
// The new style is fetched first, so a provider that does not answer leaves the map as it was.
const TOP_RE = /^(places-pts|hubs-|wcrp-|plan-)/;
const baseOf = (st) => ({ layers: new Set(st.layers.map(l => l.id)), sources: new Set(Object.keys(st.sources)) });
function addImage(id, img, opts) { BM.images[id] = { img, opts }; if (!map.hasImage(id)) map.addImage(id, img, opts); }
map.on('styleimagemissing', e => { const im = BM.images[e.id]; if (im && !map.hasImage(e.id)) map.addImage(e.id, im.img, im.opts); });
function carryStyle(prev, next) {
  const base = BM.base, ours = prev.layers.filter(l => !base.layers.has(l.id) && !l.id.startsWith(WATCH)), sources = { ...next.sources };   // a watch layer stays with its style
  Object.entries(prev.sources).forEach(([id, src]) => { if (!base.sources.has(id)) sources[id] = src; });
  const vs = Object.keys(next.sources).find(k => next.sources[k].type === 'vector');
  const own = next.layers.filter(l => !(l.type === 'fill-extrusion' && l.source === vs));   // the style's own buildings: ours is the only one (baseExtras)
  const keep = ours.filter(l => (!l.source || sources[l.source]) && !(l.type === 'symbol' && !next.glyphs && l.layout && l.layout['text-field']));
  const firstLabel = prev.layers.findIndex(l => l.type === 'symbol' && base.layers.has(l.id));
  const under = (l) => (firstLabel >= 0 ? prev.layers.indexOf(l) < firstLabel : !TOP_RE.test(l.id));
  const cut = own.findIndex(l => l.type === 'symbol'), at = cut < 0 ? own.length : cut;
  BM.nextBase = baseOf({ layers: own, sources: next.sources });
  return { ...next, sources, layers: [...own.slice(0, at), ...keep.filter(under), ...own.slice(at), ...keep.filter(l => !under(l))], terrain: prev.terrain, sky: prev.sky };
}
/** Puts a style under the observatory's layers (carryStyle) and sets again what the style does not carry. */
function applyStyle(next) {
  return new Promise((ok, fail) => {
    const t = setTimeout(() => fail(new Error('timeout')), 30000);
    map.once('style.load', () => { clearTimeout(t); BM.base = BM.nextBase; setTerrain($('#lyTerrain').checked); setSky(); baseExtras(); ok(); });
    map.setStyle(next, { diff: false, transformStyle: carryStyle });
  });
}
async function switchBasemap(name) {
  if (BM.busy || !started || (name === BM.name && !BM.off)) { if (BM.ctl) BM.ctl.set(BM.name); return; }   // refused: nothing is kept (the pick is stored only once it is on)
  BM.busy = true; $('#basemap').disabled = true;
  if (OSMI.m) OSMI.m.off();   // a new style ends the OSM inspector's mode, as in 2D (docs/basemap.md, section 8)
  try {
    // a style URL is fetched first (common.js: one retry, the cache bypassed); "none" and the USGS styles are objects built in core/basemap.js, whose tiles the
    // failure rules then watch
    const st = Core.basemap.style('3d', name), next = typeof st === 'string' ? await fetchRetry(st, r => r.json(), [1000]) : st;
    BM.next = name; creditOn = null;   // the new style's provider source takes the credits (bmCredits), whatever its id
    await applyStyle(next);
    Object.assign(BM, { name, chosen: true, off: false, why: null, hid: {}, watching: null, recovered: false });
    baseSources = [...BM.base.sources]; Object.keys(tileErrors).forEach(k => delete tileErrors[k]); baseClock.reset();   // the failure rules watch the new style; the old style's clock stops
    showBuildings($('#lyBuildings').checked);   // hidden with a failed base map
    Core.basemap.clearNotice(map.getContainer());   // a "could not be loaded" still shown is wrong now (review of PR #92)
    setAttribution(); osmiSync(); Core.basemap.store(name);
    writeState(true);
  } catch (e) {
    Core.basemap.notice(map.getContainer(), Core.basemap.text('failed')); BM.ctl.set(BM.name);   // its own notice: the message bar may hold an Undo
  } finally { BM.busy = false; BM.next = null; $('#basemap').disabled = false; }
}
// The OSM inspector: the "Inspect map" toggle under the base map; core/osminspect.js and its Spanish load the first time it is used (docs/basemap.md, section 8).
// It works only while an OpenStreetMap base map is drawn (not the USGS pictures); the click handler below steps aside while it is on (data-inspect).
function osmiSync() {
  const st = !started ? 'loading' : BM.off ? 'off' : BM.name === 'none' ? 'none' : 'on', b = $('#osmInspect');
  const pics = st === 'on' && !Core.basemap.inspectable(BM.name);   // a USGS style: picture tiles, nothing to inspect
  b.disabled = st !== 'on' || pics;
  $('#osmInspectNote').textContent = pics ? T('The inspector reads only the OpenStreetMap base maps: choose one of them to use it.') : st === 'none' ? T('Turn on a base map to inspect it.') : st === 'off' ? T('The base map is unavailable, so there is nothing to inspect.') : st === 'loading' ? T('Available once the base map has loaded.') : T('Click a street or place on the base map to see what it is in OpenStreetMap.');
  if ((st !== 'on' || pics) && OSMI.m) OSMI.m.off();
}
$('#osmInspect').onclick = () => (OSMI.p || (OSMI.p = Promise.all([I18N.load('osminspect'), Core.osminspect ? 0 : addJs('js/core/osminspect.js?v=3')]).then(() => (OSMI.m = Core.osminspect.maplibre(map, $('#osmInspect'), () => started && !BM.off && Core.basemap.inspectable(BM.name)))).catch(e => { OSMI.p = null; throw e; })))
  .then(m => m.toggle(), () => toast(T('The map inspector could not be loaded. Check your connection and try again.')));
function setTerrain(on) { map.setTerrain(on ? { source: 'dem', exaggeration: +$('#exag').value } : null); }

// ── Data layers (MapLibre, terrain-aware) ──────────────────────────────────
const CAT_COLOR = ['match', ['get', 'category'], 'ATTRACTIONS', '#338CB3', 'GASTRONOMY', '#79901E', 'ACCOMMODATIONS', '#FFA600', 'VISITOR_SERVICES', '#FF4D38', '#666'];

async function loadJson(path, label) { if (label) $('#loaderText').textContent = label; return fetchJson(path); }

/** The tourism places and their transit-access columns, once: drawn when they arrive. The count beside the layer says they are loading until then. */
function loadPlaces() {
  if (S.placesP) return S.placesP;
  $('#placesCount').textContent = `(${T('loading…')})`;
  S.placesP = Promise.all([loadJson('data/places.json'), fetchAccess()]).then(([places, accessFile]) => {
    S.places = places; S.access = attachAccess(places, accessFile, S.meta);   // null when the file is missing or belongs to another build: pop-ups then show only the any-mapped-stop distance
    addPlaces(); updatePlacesMode(); return places;
  }).catch(e => { S.placesP = null; $('#placesCount').textContent = `(${T('could not load')})`; toast(T('The tourism places could not be loaded. Switch the layer off and on to try again.'), 6000); throw e; });
  return S.placesP;
}
function placesFilter() {
  return ['all', ['in', ['get', 'category'], ['literal', [...S.cats]]], ['>=', ['get', 'confidence'], 0.5], ['!=', ['get', 'type'], 'Places of Worship']];
}
// The layers on top, from the bottom, whichever was switched on first: the stations, the WCRP pins, the planned route (added last each time it changes).
const TOPS = ['hubs-', 'wcrp-', 'plan-'];
const topBefore = (prefix) => { const up = TOPS.slice(TOPS.indexOf(prefix) + 1); return (map.getStyle().layers.find(l => up.some(p => l.id.startsWith(p))) || {}).id; };
const PLACES_UNDER = /^(wcrp-|hubs-|plan-)/;   // the layers drawn on top of the places: the WCRP pins, the stations, the planned route (the route lines are under them, as on the 2D map)
function addPlaces() {
  const fc = { type: 'FeatureCollection', features: S.places.filter(placeDrawn).map(p => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [p.lng, p.lat] }, properties: { name: p.name, category: p.category, type: p.type, municipality: p.municipality, confidence: p.confidence, sfha: p.sfha ? 1 : 0, flood_zone: p.flood_zone, transit_m: p.transit_m, transit_400m: p.transit_400m ? 1 : 0, ts_m: p.ts_m, ts_calls: p.ts_calls, ts_we: p.ts_we, tw_m: p.tw_m, tw_calls: p.tw_calls, tw_we: p.tw_we, tw_straight: p.tw_straight } })) };
  map.addSource('places', { type: 'geojson', data: fc });
  const before = map.getStyle().layers.map(l => l.id).find(id => PLACES_UNDER.test(id));   // the points: above the municipalities, their columns, the hazard layers (which go in under the municipal lines), the route lines and the base map's labels; under the layers that are added on top (none yet: the top)
  const heatBefore = map.getStyle().layers.map(l => l.id).find(id => /^routes-/.test(id)) || slotBefore('routes-');   // the heat map stays under the route lines, which would vanish under it in San Juan
  map.addLayer({ id: 'places-heat', type: 'heatmap', source: 'places', maxzoom: 13, filter: placesFilter(), paint: {
    'heatmap-weight': 1, 'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 7, .14, 9, .3, 11, .7, 13, 1.6], 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 7, 6, 10, 14, 13, 28],
    'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(143,202,232,0)', .12, 'rgba(143,202,232,.45)', .35, '#5FAFDA', .65, '#338CB3', 1, '#205D7B'], 'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 11, .85, 13, 0] } }, heatBefore);
  map.addLayer({ id: 'places-pts', type: 'circle', source: 'places', minzoom: 10.5, filter: placesFilter(), paint: {
    'circle-color': CAT_COLOR, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2, 14, 5, 17, 9], 'circle-opacity': ['interpolate', ['linear'], ['zoom'], 11, .4, 13, .95],
    'circle-stroke-color': ['case', ['==', ['get', 'sfha'], 1], '#0B3D5C', '#ffffff'], 'circle-stroke-width': ['case', ['==', ['get', 'sfha'], 1], 2, .8] } }, before);
  $('#placesCount').textContent = `(${fmt(S.places.filter(p => p.confidence >= .5 && p.type !== 'Places of Worship' && placeDrawn(p)).length)})`;
  clickable('places-pts', 'point', f => placeHtml(f.properties));
  hoverCursor('places-pts');
}
function updatePlacesMode() {
  if (!map.getLayer('places-heat')) return;   // the places arrive after the first paint (loadPlaces)
  const mode = $('#placesMode').value, on = $('#lyPlaces').checked;
  map.setLayoutProperty('places-heat', 'visibility', on && mode !== 'points' ? 'visible' : 'none');
  map.setLayoutProperty('places-pts', 'visibility', on && mode !== 'heat' ? 'visible' : 'none');
  map.setLayerZoomRange('places-heat', 0, mode === 'heat' ? 24 : 13);
  map.setLayerZoomRange('places-pts', mode === 'points' ? 0 : 10.5, 24);
}
function refreshPlacesFilter() { if (!map.getLayer('places-heat')) return; ['places-heat', 'places-pts'].forEach(id => map.setFilter(id, placesFilter())); }

let metricKey = '';
function addMunicipalities() {
  for (const f of S.muniFc.features) Object.assign(f.properties, S.muni[f.properties.municipality] || {});
  map.addSource('munis', { type: 'geojson', data: S.muniFc });
  map.addLayer({ id: 'muni-line', type: 'line', source: 'munis', paint: { 'line-color': '#205D7B', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, .6, 12, 1.6], 'line-opacity': .8 } }, firstSymbolLayer());
  map.addLayer({ id: 'muni-cols', type: 'fill-extrusion', source: 'munis', paint: { 'fill-extrusion-color': '#338CB3', 'fill-extrusion-height': 0, 'fill-extrusion-opacity': .55 } }, firstSymbolLayer());
  // an invisible flat layer keeps the municipalities clickable while the columns are off (the columns layer is hidden then: a column of height 0 still paints a blue sheet)
  map.addLayer({ id: 'muni-hit', type: 'fill', source: 'munis', paint: { 'fill-color': '#000000', 'fill-opacity': 0 } }, 'muni-cols');
  setMetric(metricKey);
  ['muni-cols', 'muni-hit'].forEach(id => { clickable(id, 'base', f => muniCard(f.properties.municipality)); hoverCursor(id); });   // the card when nothing else is under the click
}
/** The card of a municipality (a click on land with nothing else under it, or the link of an area card). */
function muniCard(name) {
  const m = S.muni[name]; if (!m) return '';
  return `<div class="pop"><h4>${icon('location_city', { size: 20, color: '#205D7B' })}${esc(m.municipality)}</h4><div class="meta">${esc(m.region)} · ${esc(m.pop_change_pct != null ? T('{n} residents (2020, {pct}% since 2010)', { n: fmt(m.population_2020), pct: (m.pop_change_pct > 0 ? '+' : '') + m.pop_change_pct }) : T('{n} residents (2020)', { n: fmt(m.population_2020) }))}</div><div class="meta">${Th('<b>{n}</b> tourism places · <b>{flood}%</b> in flood hazard area', { n: fmt(m.assets), flood: m.sfha_pct ?? '—' })}</div><div class="meta">${m.acc_walk400_pct != null ? Th('<b>{walk}%</b> within a 400 m walk of a stop with a current timetable · <b>{cur}%</b> in a straight line · <b>{transit}%</b> within 400 m of any mapped stop', { walk: m.acc_walk400_pct, cur: m.acc_cur400_pct ?? '—', transit: m.transit_pct ?? '—' }) : m.acc_cur400_pct != null ? Th('<b>{cur}%</b> within 400 m of a stop with a current timetable · <b>{transit}%</b> within 400 m of any mapped stop', { cur: m.acc_cur400_pct, transit: m.transit_pct ?? '—' }) : Th('<b>{transit}%</b> within 400 m of any mapped stop', { transit: m.transit_pct ?? '—' })}</div><div class="meta">${[esc(T('{n} stops & stations', { n: fmt(m.transit_stops) })), m.rail_stations ? esc(T('{n} Tren Urbano', { n: m.rail_stations })) : '', m.airports ? esc(Tn(m.airports, '{n} airport', '{n} airports')) : '', esc(m.uber_listed ? T('Uber listed') : T('Uber not listed'))].filter(Boolean).join(' · ')}</div><div class="links"><a href="${esc(cardLink2d(m.municipality))}" data-to2d="${esc(m.municipality)}">${esc(T('Open in 2D analysis'))} ${icon('open_in_new', { size: 12 })}</a>${window.Series ? `<button type="button" class="linklike" data-series="${esc(m.municipality)}">${esc(T('Time series'))}</button>` : ''}</div></div>`;   // the time series panel (series3d.js): its datasets load when it opens
}
function setMetric(key) {
  metricKey = key; Core.activelayers.changed();   // the chat sets the columns without a change event
  if (VS.ready && !VS.applying) { VS.measure = true; writeState(); }   // the columns changed here: s=, e= and ey= now say what they show
  const lg = $('#metricLegend');
  if (key === '__any') return engineColumns();   // any dataset of the Economy tab: the shared engine (above addFlood)
  $('#engineCtl').hidden = true;
  map.setLayoutProperty('muni-cols', 'visibility', key ? 'visible' : 'none');
  if (!key) { map.setPaintProperty('muni-cols', 'fill-extrusion-height', 0); lg.innerHTML = ''; return; }
  const c = METRIC[key];
  if (c.bool) {   // a yes/no listing (Uber): a column of one height where it is listed, a flat grey sheet where it is not
    const n = Object.values(S.muni).filter(m => m[key] === true).length, all = Object.values(S.muni).filter(m => m[key] != null).length, yes = ['==', ['get', key], true];
    map.setPaintProperty('muni-cols', 'fill-extrusion-color', ['case', yes, RAMP[3], '#E6E6E6']);
    map.setPaintProperty('muni-cols', 'fill-extrusion-height', ['case', yes, 6000, 0]);
    lg.innerHTML = Core.legend.swatches([RAMP[3], '#E6E6E6'], [T('Listed ({n})', { n }), T('Not listed ({n})', { n: all - n })], T('{label} · Uber cities page, checked {date}. A listing, not measured coverage.', { label: c.label, date: (S.meta.transport || {}).uber_checked || '' }));
    return;
  }
  const vals = Object.values(S.muni).map(m => m[key]).filter(v => v != null).sort((a, b) => a - b);
  const max = vals[vals.length - 1] ?? 1, min = vals[0] ?? 0;
  const q = Core.classify.inner(vals, 5);
  const sgn = (v, d) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmt(Math.abs(v), d)}${c.pct ? '%' : ''}`;
  if (c.diverging && max <= 0) {   // every value is a loss: one-sided scale
    const span = Math.abs(min) || 1;
    map.setPaintProperty('muni-cols', 'fill-extrusion-color', ['interpolate', ['linear'], ['abs', ['coalesce', ['get', key], 0]], 0, '#FFD0C9', span, '#B82415']);
    map.setPaintProperty('muni-cols', 'fill-extrusion-height', ['*', ['abs', ['coalesce', ['get', key], 0]], 12000 / span]);
    lg.innerHTML = Core.legend.swatches(['linear-gradient(90deg,#FFD0C9,#B82415)'], [sgn(max, 1), sgn(min, 1)], T('Column height and red shade = size of the loss. All {n} municipalities lost population between 2010 and 2020.', { n: vals.length }));
    return;
  }
  if (c.diverging) {
    const span = Math.max(Math.abs(min), Math.abs(max)) || 1;
    map.setPaintProperty('muni-cols', 'fill-extrusion-color', ['interpolate', ['linear'], ['coalesce', ['get', key], 0], -span, '#B82415', 0, '#F2F2F2', span, '#205D7B']);
    map.setPaintProperty('muni-cols', 'fill-extrusion-height', ['*', ['abs', ['coalesce', ['get', key], 0]], 12000 / span]);
    lg.innerHTML = Core.legend.swatches(['#B82415', '#F2F2F2', '#205D7B'], [sgn(min, 1), '0', sgn(max, 1)], T('Column height = size of change; red = loss, blue = gain.'));
    return;
  }
  // MapLibre needs the break values of a step to rise strictly. When several are tied (many municipalities at 0%) each is moved up by a hair: a tied class stays empty, as in the 2D map.
  const stops = Core.classify.risingStops(q);
  map.setPaintProperty('muni-cols', 'fill-extrusion-color', ['step', ['coalesce', ['get', key], 0], RAMP[0], stops[0], RAMP[1], stops[1], RAMP[2], stops[2], RAMP[3], stops[3], RAMP[4]]);
  map.setPaintProperty('muni-cols', 'fill-extrusion-height', ['*', ['coalesce', ['get', key], 0], 14000 / max]);
  lg.innerHTML = Core.legend.swatches(RAMP, [`${fmt(min, c.d)}${c.pct ? '%' : ''}`, `${fmt(q[1], c.d)}${c.pct ? '%' : ''}`, `${fmt(max, c.d)}${c.pct ? '%' : ''}`], T('{label} · column height ∝ value, colour by quintile.', { label: c.label }));
}

// ── Columns from any dataset of the Economy tab (plan item 16, B7) ──────────
// The 17 measures above stay as they were (municipalities.json). "Any dataset…" takes the column's height from one dataset and its colour from another (or the
// same), each normalised as a shaded map of the Economy tab starts it (counts per 1,000 residents, dollar totals per resident, the rest as published), in the year chosen.
// The shared engine, its data files and, in Spanish, the map page's names of the datasets load only then, so the 3D view's first load does not carry them (docs/engine.md).
const ENG = { E: null, loading: null, filled: false, h: 'poverty_pct', c: '', y: null, ho: {}, co: {}, failed: [] };   // ho, co: the rescaling the chat asked for (ask3d.js); the menus reset them
const ENGINE_JS = ['core/stats.js?v=4', 'core/time.js?v=1', 'core/format.js?v=2', 'core/normalize.js?v=4', 'core/reliability.js?v=4', 'core/engine.js?v=11', 'core/hexbin.js?v=1', 'core/adapters.js?v=15', 'core/datasets.js?v=27'];   // the versions index.html loads, so the browser can reuse them
function engineLoad() {
  if (ENG.E) return Promise.resolve(ENG.E);
  return ENG.loading || (ENG.loading = (async () => {
    const add = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
    for (const f of ENGINE_JS) if (!document.querySelector(`script[src="js/${f}"]`)) await add('js/' + f);
    if (I18N.lang === 'es') await Promise.all(['i18n/es.map.js', 'i18n/es.map.econ_terrain.js', 'i18n/es.map.economy.js'].map(f => add(f).catch(() => {})));   // the Spanish names of the datasets, groups and periods and its Economy module's (tests: they agree with this page's own Spanish), with the terrain and climate groups the 2D map loads with its data (econ_terrain)
    const E = Core.engine.create();
    ENG.failed = (await Core.datasets.load(E, (p) => loadJson(p), S.muni, +((S.meta.generated_at || '').slice(0, 4)) || 2026, ['wcrp'])).failed || [];
    return (ENG.E = E);
  })().catch(e => { ENG.loading = null; throw e; }));
}
function engineFill() {
  if (ENG.filled) return; ENG.filled = true;
  const E = ENG.E, groups = new Map();
  E.list().forEach(v => { if (!groups.has(v.group)) groups.set(v.group, []); groups.get(v.group).push(v); });
  const opts = Core.datasets.sortGroups([...groups.keys()]).map(g => [g, groups.get(g)]).map(([g, vs]) =>   // in the order of the Economy tab: the layer menu's themes, the visitor economy last
    `<optgroup label="${esc(T(g || ''))}">${vs.map(v => `<option value="${esc(v.key)}">${esc(T(v.label))}</option>`).join('')}</optgroup>`).join('');
  if (!E.V[ENG.h]) { ENG.unknown = !!ENG.fromAddress; ENG.h = E.list()[0].key; }   // a dataset of the address this view does not have (the WCRP ones): no columns
  if (ENG.c && !E.V[ENG.c]) ENG.c = '';
  for (const [k, o] of [[ENG.h, 'ho'], [ENG.c, 'co']]) if (ENG[o].norm && !(k && E.normOptions(k).some(n => n[0] === ENG[o].norm))) ENG[o] = {};   // a rescaling from the address the dataset does not offer
  $('#engH').innerHTML = opts; $('#engH').value = ENG.h;
  $('#engC').innerHTML = `<option value="">${esc(T('Same as the height'))}</option>${opts}`; $('#engC').value = ENG.c;
  $('#engY').innerHTML = `<option value="">${esc(T('Latest'))}</option>${[...E.years()].sort((a, b) => b - a).map(y => `<option>${y}</option>`).join('')}`;
  $('#engY').value = ENG.y != null ? String(ENG.y) : ''; if ($('#engY').value === '') ENG.y = null;   // a year from the address that no dataset has: the latest
  const changed = () => { VS.measure = true; engineDraw(); writeState(); };
  $('#engH').onchange = e => { ENG.h = e.target.value; ENG.ho = {}; changed(); };
  $('#engC').onchange = e => { ENG.c = e.target.value; ENG.co = {}; changed(); };
  $('#engY').onchange = e => { ENG.y = e.target.value ? +e.target.value : null; changed(); };
}
async function engineColumns() {
  const lg = $('#metricLegend');
  $('#engineCtl').hidden = false;
  if (!ENG.E) lg.innerHTML = `<div class="note" role="status">${esc(T('Loading the datasets…'))}</div>`;
  try { await engineLoad(); } catch { if (metricKey === '__any') lg.innerHTML = `<div class="note" role="status">${esc(T('The datasets could not be loaded. Check your connection and choose the option again.'))}</div>`; return; }
  if (metricKey !== '__any') return;   // another measure was chosen while they loaded
  engineFill();
  if (ENG.unknown) { ENG.unknown = false; VS.applying = true; try { $('#lyCols').checked = false; $('#lyCols').dispatchEvent(new Event('change')); } finally { VS.applying = false; } return; }   // the address keeps e=
  engineDraw();
}
/** One dataset as the columns read it: the layer the Economy tab would add for it (E.makeLayer: its rescaling, and one set of classes held across all years unless the dataset
    has one year), its values in the year chosen (or its latest), its title and its period ("first data 2017" when the dataset starts after the year chosen). */
function engineVec(key, o = {}) {
  const E = ENG.E, L = E.makeLayer(key, 'fill', o, []); if (!L || L.error) return null;
  const r = E.resolve(key, ENG.y), a = r.y == null ? null : E.calc(L, r.y); if (!a) return null;
  return { a, L, y: r.y, title: E.title(L, r.y), chip: E.chip(L, r) };
}
function engineDraw() {
  const E = ENG.E, lg = $('#metricLegend');
  E.year = ENG.y;   // the period chips say "latest at or before" the year chosen
  const H = engineVec(ENG.h, ENG.ho), C = ENG.c ? engineVec(ENG.c, ENG.co) : H;
  if (!H || !C) { map.setLayoutProperty('muni-cols', 'visibility', 'none'); lg.innerHTML = `<div class="note">${esc(T('This dataset has no values for that year.'))}</div>`; return; }
  const b = E.breaks(C.L, C.y), cols = b.div ? Core.palettes.DIVERGING : RAMP, at = new Map(E.geo.names.slice(0, E.geo.pr).map((n, i) => [n, i]));
  for (const f of S.muniFc.features) {
    const i = at.get(f.properties.municipality), h = i == null ? null : H.a[i], k = i == null ? -1 : Core.classify.classOf(b, C.a[i]);
    f.properties.__h = h == null || !isFinite(h) ? 0 : Math.abs(h);   // a negative value (a loss) stands as tall as a gain of the same size; the colour tells them apart when it is the same dataset
    f.properties.__col = k < 0 ? Core.palettes.NOVAL : cols[k];
  }
  map.getSource('munis').setData(S.muniFc);
  const hv = H.a.slice(0, E.geo.pr).filter(x => x != null && isFinite(x)), top = hv.reduce((m, x) => Math.abs(x) > Math.abs(m) ? x : m, 0);
  map.setLayoutProperty('muni-cols', 'visibility', 'visible');
  map.setPaintProperty('muni-cols', 'fill-extrusion-height', ['*', ['coalesce', ['get', '__h'], 0], 14000 / (Math.abs(top) || 1)]);
  map.setPaintProperty('muni-cols', 'fill-extrusion-color', ['coalesce', ['get', '__col'], Core.palettes.NOVAL]);
  const e = b.edges || [], lab = (x) => x == null || !isFinite(x) ? '' : esc(E.fmt(C.L, x, Math.abs(x) >= 1000));
  lg.innerHTML = `<div class="note">${Th('<b>Height:</b> {name}, {period}. The tallest column is {max}.', { name: H.title, period: H.chip, max: E.fmt(H.L, top) })}${hv.some(x => x < 0) ? ' ' + esc(T('A negative value stands as tall as a positive one of the same size.')) : ''}</div>`
    + Core.legend.swatches(cols, [lab(e[0]), lab(e[Math.floor(e.length / 2)]), lab(e[e.length - 1])], T('Colour: {name}, {period}, in five classes. Grey: no value.', { name: C.title, period: C.chip }));
  if (window.Series) Series.sync();   // the time series panel (series3d.js) follows the dataset and the year
}

async function addFlood() {
  if (map.getSource('flood')) return;
  S.flood = S.flood || await loadJson('data/flood.geojson');
  map.addSource('flood', { type: 'geojson', data: S.flood });
  map.addLayer({ id: 'flood-fill', type: 'fill', source: 'flood', filter: ['any', ['==', ['get', 'SFHA_TF'], 'T'], ['in', '0.2', ['coalesce', ['get', 'ZONE_SUBTY'], '']]], paint: {
    'fill-color': ['case', ['==', ['get', 'SFHA_TF'], 'T'], ['case', ['in', 'FLOODWAY', ['coalesce', ['get', 'ZONE_SUBTY'], '']], '#B82415', ['in', ['slice', ['get', 'FLD_ZONE'], 0, 1], ['literal', ['V']]], '#0B3D5C', '#1F5F8B'], '#8FCAE8'], 'fill-opacity': .45 } }, areaBefore('flood-fill'));
  clickable('flood-fill', 'area', f => floodPopup(f.properties, false));   // the sections of the area card are access.js's, as on the 2D map
}
// The surface heat images (heat.py: summer mornings, Landsat; ecostress.py: summer nights; surface_image.py; HANDOFF decision 88): one at a time, draped on the terrain over
// the hillshade and under the 3D buildings and every data layer. Its colours follow the ground in view by default (core/surfscale.js, loaded with it), or Puerto Rico's
let surfMode = 'view', surfTime = 'day';
const surfs = {}, SURF_FILE = { day: 'data/heat_surface.json', night: 'data/night_heat_surface.json' };
const surfOpen = (t) => surfs[t] || (surfs[t] = (async () => { const m = await loadJson(SURF_FILE[t]), o = await Core.surfscale.open('data/' + m.image, m); o.meta = m; return o; })().catch(e => { delete surfs[t]; throw e; }));
const surfCorners = (m) => { const [w, s, e, n] = m.bounds; return [[w, n], [e, n], [e, s], [w, s]]; };
async function addSurfHeat() {
  if (map.getSource('surfheat')) return;
  if (!window.Core.surfscale) await addJs('js/core/surfscale.js?v=4');
  const o = await surfOpen(surfTime);
  map.addSource('surfheat', { type: 'image', url: 'data/' + o.meta.image, coordinates: surfCorners(o.meta) });
  map.addLayer({ id: 'surfheat-img', type: 'raster', source: 'surfheat', paint: { 'raster-opacity': .8, 'raster-resampling': 'linear', 'raster-fade-duration': 0 } }, map.getLayer('buildings-3d') ? 'buildings-3d' : areaBefore('landuse-fill'));
  map.on('moveend', surfPaint); surfPaint();
}
function surfPaint() {   // after a move or a switch: the ground in view is the lower 60% of the screen, so a tilted camera's horizon and sky do not count
  if (!map.getLayer('surfheat-img') || map.getLayoutProperty('surfheat-img', 'visibility') === 'none') return;
  clearTimeout(surfPaint.t);
  surfPaint.t = setTimeout(async () => {
    const o = await surfOpen(surfTime), c = map.getCanvas(), W = c.clientWidth, H = c.clientHeight, pts = [[0, H * .4], [W, H * .4], [0, H], [W, H]].map(p => map.unproject(p));
    const box = [Math.min(...pts.map(p => p.lng)), Math.min(...pts.map(p => p.lat)), Math.max(...pts.map(p => p.lng)), Math.max(...pts.map(p => p.lat))];
    const sc = (surfMode === 'view' && o.stats(box)) || o.island;
    map.getSource('surfheat').updateImage({ url: await o.paint(sc), coordinates: surfCorners(o.meta) });
    $('#surfLegend').innerHTML = o.legend(sc, surfMode, surfTime);
  }, 250);
}
$('#surfLegend').addEventListener('click', e => { const m = e.target.closest('[data-surf-mode],[data-surf-time]'); if (!m) return; if (m.dataset.surfMode) surfMode = m.dataset.surfMode; else surfTime = m.dataset.surfTime; surfPaint(); });
async function addProtected() {
  if (map.getSource('prot')) return;
  S.prot = S.prot || await loadJson('data/protected.geojson');
  map.addSource('prot', { type: 'geojson', data: S.prot });
  map.addLayer({ id: 'prot-fill', type: 'fill', source: 'prot', paint: { 'fill-color': '#79901E', 'fill-opacity': .35, 'fill-outline-color': '#47560F' } }, areaBefore('prot-fill'));
  clickable('prot-fill', 'area', f => protPopup(f.properties, false));
}
async function addLanduse() {
  if (map.getSource('landuse')) return;
  const fc = await loadJson('data/landuse.geojson');
  map.addSource('landuse', { type: 'geojson', data: fc });
  map.addLayer({ id: 'landuse-fill', type: 'fill', source: 'landuse', filter: ['!', ['in', ['get', 'group'], ['literal', ['water', 'road']]]], paint: { 'fill-color': ['get', 'color'], 'fill-opacity': .45, 'fill-outline-color': 'rgba(42,46,46,.25)' } }, areaBefore('landuse-fill'));
  clickable('landuse-fill', 'area', f => landusePopup(f.properties, false));
}
async function addComunidades() {
  if (map.getSource('comunidades')) return;
  const fc = await loadJson('data/comunidades.geojson');
  map.addSource('comunidades', { type: 'geojson', data: fc });
  map.addLayer({ id: 'ce-fill', type: 'fill', source: 'comunidades', paint: { 'fill-color': '#FF4D38', 'fill-opacity': .25 } }, areaBefore('ce-fill'));
  map.addLayer({ id: 'ce-line', type: 'line', source: 'comunidades', paint: { 'line-color': '#FF4D38', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, .6, 15, 2] } }, areaBefore('ce-line'));
  clickable('ce-fill', 'area', f => comunidadPopup(f.properties, false));
}
async function addWcrp() {
  if (map.getSource('wcrp')) return;
  const img = (src) => new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = fail; i.src = src; });
  const [data, pin, open] = await Promise.all([loadJson('data/wcrp.geojson'), img('img/wcrp-pin.svg'), img('img/wcrp-pin-open.svg')]);
  if (map.getSource('wcrp')) return;
  addImage('wcrp-pin', pin, { pixelRatio: 2 }); addImage('wcrp-pin-open', open, { pixelRatio: 2 });   // the SVGs are drawn at 2x
  map.addSource('wcrp', { type: 'geojson', data });
  // the centre figure of the WCRP logo: solid for an approved plan, an outline for a plan in progress. Approved pins sort on top where plans share a point.
  const approved = ['==', ['get', 'estado'], 'plan_aprobado'];
  map.addLayer({ id: 'wcrp-pts', type: 'symbol', source: 'wcrp', layout: { 'icon-image': ['case', approved, 'wcrp-pin', 'wcrp-pin-open'], 'icon-anchor': 'bottom', 'icon-offset': [0, 2], 'icon-size': 1.3, 'icon-allow-overlap': true, 'icon-ignore-placement': true, 'symbol-sort-key': ['case', approved, 1, 0] } }, topBefore('wcrp-'));
  clickable('wcrp-pts', 'point', (f, all) => {   // plans that share a point all come back under the click; list each once
    const seen = new Set();
    return wcrpPopup(all.map(g => g.properties).filter(p => !seen.has(p.comunidad) && seen.add(p.comunidad)));
  });
  hoverCursor('wcrp-pts');
}
const GEO_NOTE = { stops: T('Approximate alignment: no road path was found, so the line joins the stops in order.'), roads: T('The feed has no route shape, so the line follows the road network between the stops.') };
// The pipeline writes this note in English with the ratio inside it: show it in the page language when it has the known wording, as written otherwise.
const orderNote = (n) => { const m = /^The feed lists this route's stops (alphabetically|out of travel order) \(zig-zag ratio ([\d.]+)\), so the order of visit is inferred and its times are not usable\.$/.exec(n || ''); return !m ? (n || T('The order of the stops is inferred.')) : m[1] === 'alphabetically' ? T("The feed lists this route's stops alphabetically (zig-zag ratio {ratio}), so the order of visit is inferred and its times are not usable.", { ratio: m[2] }) : T("The feed lists this route's stops out of travel order (zig-zag ratio {ratio}), so the order of visit is inferred and its times are not usable.", { ratio: m[2] }); };
const geoNote = (p) => { const t = p.geometry_source === 'roads_inferred' ? orderNote(p.order_note) : GEO_NOTE[p.geometry_source]; return t ? `<div class="meta">${esc(t)}</div>` : ''; };
async function addRoutes() {
  if (map.getSource('routes')) return;
  S.routes = S.routes || await loadJson('data/transit_routes.geojson');
  map.addSource('routes', { type: 'geojson', data: S.routes });
  // colour by operator: Tren Urbano red, ATI buses blue, municipal systems green, públicos (OpenStreetMap) gold; solid = follows the roads or the operator's shape, dashed = stop order inferred, dotted = no road path found
  const ROUTE_COLOR = ['case', ['==', ['get', 'mode'], 'rail'], '#B82415', ['==', ['get', 'operator'], 'osm'], '#B56D00', ['==', ['get', 'operator'], 'ati'], '#205D7B', '#607316'];
  map.addLayer({ id: 'routes-line', type: 'line', source: 'routes', filter: ['all', ['!=', ['get', 'mode'], 'ferry'], ['!=', ['get', 'geometry_source'], 'stops'], ['!=', ['get', 'geometry_source'], 'roads_inferred']], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ROUTE_COLOR, 'line-width': ['match', ['get', 'mode'], 'rail', 4, 2], 'line-opacity': .85 } }, slotBefore('routes-'));
  map.addLayer({ id: 'routes-inferred', type: 'line', source: 'routes', filter: ['==', ['get', 'geometry_source'], 'roads_inferred'], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ROUTE_COLOR, 'line-width': 2, 'line-opacity': .6, 'line-dasharray': [3, 2] } }, slotBefore('routes-'));
  map.addLayer({ id: 'routes-approx', type: 'line', source: 'routes', filter: ['all', ['!=', ['get', 'mode'], 'ferry'], ['==', ['get', 'geometry_source'], 'stops']], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ROUTE_COLOR, 'line-width': 2, 'line-opacity': .85, 'line-dasharray': [1, 2.5] } }, slotBefore('routes-'));
  map.addLayer({ id: 'routes-ferry', type: 'line', source: 'routes', filter: ['==', ['get', 'mode'], 'ferry'], paint: { 'line-color': '#338CB3', 'line-width': 2.5, 'line-opacity': .9, 'line-dasharray': [2, 2] } }, slotBefore('routes-'));
  const routeCard = (p) => `<div class="pop"><h4>${icon(p.mode === 'rail' ? 'subway' : p.mode === 'ferry' ? 'directions_boat' : 'directions_bus', { size: 20 })}${esc(p.short_name)} ${esc(p.long_name)}</h4><div class="meta">${esc(p.operator_name || '')} · ${esc(ROUTE_LABEL[p.label] || p.label)}${p.operator === 'osm' ? '' : ` · ${esc(Tn(p.trips_weekday, '{n} weekday trip', '{n} weekday trips', { n: fmt(p.trips_weekday) }))}`}</div>${geoNote(p)}<div class="src">${esc(p.operator === 'osm' ? T('© OpenStreetMap contributors') : p.operator === 'ati' ? T('ATI GTFS') : T('Municipal GTFS feed'))}</div></div>`;
  ['routes-line', 'routes-inferred', 'routes-approx', 'routes-ferry'].forEach(id => clickable(id, 'line', f => routeCard(f.properties)));
}
// ── The layers of transport.json, the barrios and the planning layers: the same data, cards and rules as the 2D map (access.js transportPopup, barrioPopup) ──
// transport.json is fetched once, by the first of these layers, the search or supply3d.js to ask; each layer keeps the index of its rows, so a click shows the 2D map's card for that row.
const transportData = () => S.transport ? Promise.resolve(S.transport) : Data.json('data/transport.json').then(t => (S.transport = S.transport || t));
const transportFc = (keep, extra = () => ({})) => ({ type: 'FeatureCollection', features: S.transport.map((f, i) => [f, i]).filter(([f]) => keep(f)).map(([f, i]) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [f.lng, f.lat] }, properties: { i, kind: f.kind, ...extra(f) } })) });
const transportPop = (id) => clickable(id, 'point', f => transportPopup(S.transport[f.properties.i]));
async function addHubs() {
  if (map.getSource('hubs')) return;
  await transportData(); if (map.getSource('hubs')) return;
  map.addSource('hubs', { type: 'geojson', data: transportFc(f => HUB_KINDS.includes(f.kind)) });
  map.addLayer({ id: 'hubs-pts', type: 'circle', source: 'hubs', paint: { 'circle-color': ['match', ['get', 'kind'], 'rail_station', '#B82415', 'ferry_terminal', '#338CB3', '#2A2E2E'], 'circle-radius': ['match', ['get', 'kind'], 'airport', 8, 6], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } }, topBefore('hubs-'));
  transportPop('hubs-pts'); hoverCursor('hubs-pts');
}
// About 4,240 stops: clustered (circles with their count) up to zoom 14, single points from zoom 15, as the 2D map's clusters
/** The count on each cluster of stops: only when the base map has fonts (not on the plain fallback, nor on "No base map"; baseExtras adds it when a style with fonts comes back). */
function addStopsCount(before) {
  const font = (map.getStyle().layers.find(l => l.type === 'symbol' && l.layout && Array.isArray(l.layout['text-font'])) || { layout: {} }).layout['text-font'];
  if (font && map.getStyle().glyphs) map.addLayer({ id: 'stops-count', type: 'symbol', source: 'stops', filter: ['has', 'point_count'], layout: { visibility: map.getLayer('stops-cluster') ? map.getLayoutProperty('stops-cluster', 'visibility') || 'visible' : 'visible', 'text-field': ['to-string', ['get', 'point_count']], 'text-font': font, 'text-size': 11, 'text-allow-overlap': true, 'text-ignore-placement': true }, paint: { 'text-color': '#ffffff' } }, before);   // only when the base map has fonts (not on the plain fallback)   // shown as its clusters are: added again after a switch of base map while the stops were off, it stays off
}
async function addStops() {
  if (map.getSource('stops')) return;
  await transportData(); if (map.getSource('stops')) return;
  const fc = transportFc(f => STOP_KINDS.includes(f.kind)), at = slotBefore('stops-');
  map.addSource('stops', { type: 'geojson', data: fc, cluster: true, clusterRadius: 40, clusterMaxZoom: 14, attribution: T('Stops: ATI GTFS · © OpenStreetMap contributors') });
  map.addLayer({ id: 'stops-cluster', type: 'circle', source: 'stops', filter: ['has', 'point_count'], paint: { 'circle-color': '#205D7B', 'circle-opacity': .88, 'circle-radius': ['step', ['get', 'point_count'], 11, 10, 14, 100, 18, 500, 22], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } }, at);
  addStopsCount(at);
  map.addLayer({ id: 'stops-pts', type: 'circle', source: 'stops', filter: ['!', ['has', 'point_count']], paint: { 'circle-color': ['match', ['get', 'kind'], 'bus_stop', '#5FAFDA', '#205D7B'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 3.5, 15, 5.5, 18, 8], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.2 } }, at);
  transportPop('stops-pts'); hoverCursor('stops-pts'); hoverCursor('stops-cluster');
  ['stops-cluster', 'stops-count'].forEach(id => clickable(id, 'cluster'));   // a click on a cluster, or on its count, zooms in (zoomCluster)
  $('#stopsCount').textContent = `(${fmt(fc.features.length)})`;
}
async function addTaxi() {
  if (map.getSource('taxi')) return;
  await transportData(); if (map.getSource('taxi')) return;
  map.addSource('taxi', { type: 'geojson', data: transportFc(f => TAXI_KINDS.includes(f.kind)), attribution: T('© OpenStreetMap contributors') });
  map.addLayer({ id: 'taxi-pts', type: 'circle', source: 'taxi', paint: { 'circle-color': ['match', ['get', 'kind'], ...TAXI_KINDS.flatMap(k => [k, KIND[k].color]), '#666666'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 4, 14, 6.5], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } }, slotBefore('taxi-'));
  transportPop('taxi-pts'); hoverCursor('taxi-pts');
}
// The 400 m walk rings around every stop, bus station, Tren Urbano station and ferry terminal (as on the 2D map), drawn from zoom 14 while stops or stations are on.
// A circle 400 m across on the ground: MapLibre's world is 512 px wide at zoom 0 and twice as wide at each zoom, and a metre at latitude φ is 1 / cos φ of a metre at the equator.
const ringR0 = (lat) => 400 * 512 / (40075016.686 * Math.cos(lat * Math.PI / 180));   // the radius in pixels at zoom 0
const ringsOn = () => $('#walkRings').checked && ($('#lyStops').checked || $('#lyHubs').checked);
const ringsDrawn = () => ringsOn() && map.getZoom() >= 14;
async function addRings() {
  if (map.getSource('rings')) return;
  await transportData(); if (map.getSource('rings')) return;
  map.addSource('rings', { type: 'geojson', data: transportFc(f => STOP_KINDS.includes(f.kind) || HUB_KINDS.includes(f.kind) && f.kind !== 'airport', f => ({ r0: ringR0(f.lat) })) });
  map.addLayer({ id: 'rings-400', type: 'circle', source: 'rings', minzoom: 14, layout: { visibility: 'none' }, paint: { 'circle-radius': ['interpolate', ['exponential', 2], ['zoom'], 0, ['get', 'r0'], 24, ['*', ['get', 'r0'], 2 ** 24]], 'circle-pitch-alignment': 'map', 'circle-pitch-scale': 'map', 'circle-color': '#205D7B', 'circle-opacity': .06, 'circle-stroke-color': '#205D7B', 'circle-stroke-width': .6 } }, slotBefore('rings-'));
}
function updateRings() { if (map.getLayer('rings-400')) map.setLayoutProperty('rings-400', 'visibility', ringsOn() ? 'visible' : 'none'); Core.activelayers.changed(); }
async function addBarrios() {
  if (map.getSource('barrios')) return;
  const fc = await Data.json('data/barrios.geojson'); if (map.getSource('barrios')) return;
  map.addSource('barrios', { type: 'geojson', data: fc, attribution: T('Barrios: US Census Bureau') });
  map.addLayer({ id: 'barrios-hit', type: 'fill', source: 'barrios', paint: { 'fill-color': '#000000', 'fill-opacity': 0 } }, 'muni-line');   // clickable inside, invisible
  map.addLayer({ id: 'barrios-line', type: 'line', source: 'barrios', paint: { 'line-color': '#205D7B', 'line-width': ['interpolate', ['linear'], ['zoom'], 9, .6, 14, 1.4], 'line-opacity': .8, 'line-dasharray': [3, 3] } }, 'muni-line');
  clickable('barrios-hit', 'area', f => barrioPopup(f.properties, false));   // a section of the area card, as on the 2D map
}
// The Route tab's planning layers, as the 2D map's Transit tab draws them (network.js setGaps, setXfer)
async function setGaps(on) {
  if (map.getLayer('gaps-pts')) map.setLayoutProperty('gaps-pts', 'visibility', on ? 'visible' : 'none');
  if (!on) { $('#gapNote').textContent = ''; return; }
  const blocks = await Data.json('data/population_blocks.json');
  if (!$('#lyGaps').checked) return;
  const walk = blocks.length > 0 && blocks[0].length > 4, dist = b => walk ? b[4] : b[3];   // [lon, lat, residents, metres straight, metres walked along mapped roads]
  const people = blocks.filter(b => dist(b) > 800).reduce((a, b) => a + b[2], 0), all = blocks.reduce((a, b) => a + b[2], 0);
  if (!map.getSource('gaps')) {
    map.addSource('gaps', { type: 'geojson', data: { type: 'FeatureCollection', features: blocks.filter(b => dist(b) > 800 && b[2] >= 40).map(b => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [b[0], b[1]] }, properties: { n: b[2], s: b[3], m: walk ? b[4] : null } })) } });
    map.addLayer({ id: 'gaps-pts', type: 'circle', source: 'gaps', paint: { 'circle-radius': ['min', 14, ['+', 2, ['*', ['sqrt', ['get', 'n']], .45]]], 'circle-color': '#FFA600', 'circle-opacity': .45, 'circle-stroke-color': '#B56D00', 'circle-stroke-width': .6 } }, slotBefore('gaps-'));
    clickable('gaps-pts', 'point', ({ properties: p }) => `<div class="pop"><div class="meta">${p.m != null ? (p.m >= 9999 ? Th('<b>{n}</b> residents · more than 1 km walking to the nearest scheduled stop ({s} m in a straight line)', { n: fmt(p.n), s: fmt(p.s) }) : Th('<b>{n}</b> residents · {m} m walking to the nearest scheduled stop ({s} m in a straight line)', { n: fmt(p.n), m: fmt(p.m), s: fmt(p.s) })) : Th('<b>{n}</b> residents · {m} m to the nearest scheduled stop', { n: fmt(p.n), m: fmt(p.s) })}</div></div>`);
    hoverCursor('gaps-pts');
  }
  $('#gapNote').innerHTML = walk ? Th('<b>{n}</b> residents ({pct}%) live more than an 800 m walk from any scheduled stop, along mapped roads. Circles show census blocks with 40 or more residents.', { n: fmt(people), pct: fmt(people / all * 100) })
    : Th('<b>{n}</b> residents ({pct}%) live more than 800 m from any scheduled stop. Circles show census blocks with 40 or more residents.', { n: fmt(people), pct: fmt(people / all * 100) });
}
async function setXfer(on) {
  if (map.getLayer('xfer-pts')) map.setLayoutProperty('xfer-pts', 'visibility', on ? 'visible' : 'none');
  if (!on) { $('#xferNote').textContent = ''; return; }
  const d = await Data.json('data/operators.json');
  if (!$('#lyXfer').checked) return;
  const ops = Object.fromEntries(d.operators.map(o => [o.id, o])), name = (id) => (ops[id] || {}).short || id;
  if (!map.getSource('xfer')) {
    map.addSource('xfer', { type: 'geojson', data: { type: 'FeatureCollection', features: d.transfers.map((x, i) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [x.lng, x.lat] }, properties: { i } })) } });
    map.addLayer({ id: 'xfer-pts', type: 'circle', source: 'xfer', paint: { 'circle-radius': 7, 'circle-color': '#ffffff', 'circle-opacity': .9, 'circle-stroke-color': '#205D7B', 'circle-stroke-width': 2 } }, slotBefore('xfer-'));
    clickable('xfer-pts', 'point', f => { const x = d.transfers[f.properties.i]; return `<div class="pop"><div class="meta">${Th('<b>{first}</b> “{firststop}”<br>↔ <b>{second}</b> “{secondstop}”<br><small>{d} m apart</small>', { first: name(x.a), firststop: x.an, second: name(x.b), secondstop: x.bn, d: fmt(x.d) })}</div></div>`; });
    hoverCursor('xfer-pts');
  }
  $('#xferNote').innerHTML = Th('<b>{n}</b> places where stops of two different systems are within 250 m of each other{drawn}. These are the natural places to coordinate timetables and fares.', { n: fmt(d.transfers_total), drawn: d.transfers_total > d.transfers.length ? ` ${T('(the closest {n} are drawn)', { n: fmt(d.transfers.length) })}` : '' });
}
let slrLayerFt = null;
function setSlr(on) {
  const ft = currentFeet();
  if (map.getLayer('slr')) map.removeLayer('slr');
  if (map.getSource('slr')) map.removeSource('slr');
  if (!on) return;
  map.addSource('slr', { type: 'raster', tiles: [`https://coast.noaa.gov/arcgis/rest/services/dc_slr/slr_${ft}ft/MapServer/tile/{z}/{y}/{x}`], tileSize: 256, maxzoom: 16, attribution: T('Sea level rise: NOAA OCM') });
  map.addLayer({ id: 'slr', type: 'raster', source: 'slr', paint: { 'raster-opacity': .7 } }, map.getLayer('flood-fill') ? 'flood-fill' : areasBefore());
  slrLayerFt = ft;
}
function currentFeet() {
  const sc = SCENARIOS[$('#scenario').value], y = +$('#year').value;
  let m = sc.pts[sc.pts.length - 1][1];
  for (let i = 1; i < sc.pts.length; i++) { const [y0, m0] = sc.pts[i - 1], [y1, m1] = sc.pts[i]; if (y <= y1) { m = m0 + (m1 - m0) * (y - y0) / (y1 - y0); break; } }
  const ft = Math.min(10, Math.max(1, Math.round(m * 3.28084)));
  $('#slrNote').innerHTML = Th('<b>{year}</b> · {scenario} ≈ <b>{ft} ft</b> ({m} m) above the 2000 baseline → showing the NOAA <b>{layer} ft</b> layer.', { year: y, scenario: sc.label, ft: (m * 3.28084).toFixed(1), m: m.toFixed(2), layer: ft });
  $('#slrLabel').textContent = T('{ft} ft · {year}', { ft, year: y });   // a narrow no-break space (U+202F, the SI separator of a value and its unit; Gotham draws U+00A0 far too wide): the label never wraps as "NOAA 1 / ft"
  return ft;
}

// ── deck.gl animated layers ────────────────────────────────────────────────
const MODE_RGB = { rail: [184, 36, 21], bus: [255, 166, 0], ferry: [51, 140, 179], muni: [166, 191, 51] };
const tripColor = (d) => d.o && d.o !== 'ati' && d.m === 'bus' ? MODE_RGB.muni : (MODE_RGB[d.m] || MODE_RGB.bus);   // municipal buses in green
function tripsLayer() {
  if (!S.trips || !$('#lyTrips').checked) return null;
  return new deck.TripsLayer({ id: 'trips', data: S.trips.trips, getPath: d => tripPoints(S.trips, d).map(p => [p[0], p[1]]), getTimestamps: d => tripPoints(S.trips, d).map(p => p[2]), getColor: tripColor,   // along the route line (common.js)
    widthMinPixels: 3, widthMaxPixels: 7, capRounded: true, jointRounded: true, trailLength: 420, currentTime: S.clock, fadeTrail: true, opacity: .95, shadowEnabled: false,
    pickable: !!S.pickNoCard });   // no card; pickable only for the click dispatcher's own query (noCardAt)
}
const stormText = (s) => s.cat_near_pr ? Th('<b>{name} {year}</b><br>Category {cat} near PR · peak {wind} kt · closest {dist} km', { name: stormName(s), year: s.year, cat: s.cat_near_pr, wind: s.wind_near_pr || '—', dist: fmt(s.min_dist_km) })
  : Th('<b>{name} {year}</b><br>Tropical storm near PR · peak {wind} kt · closest {dist} km', { name: stormName(s), year: s.year, wind: s.wind_near_pr || '—', dist: fmt(s.min_dist_km) });
let stormCache = { key: '', data: [], pts: [] };
function stormsLayers() {
  if (!S.storms || !$('#lyStorms').checked) return [];
  const y0 = +$('#stormY0').value, y1 = +$('#stormY1').value, minCat = +$('#stormCat').value;
  const key = [y0, y1, minCat, S.stormYear == null ? '' : Math.round(S.stormYear * 4)].join('|');
  if (key !== stormCache.key) {
    let d = S.storms.filter(s => s.year >= y0 && s.year <= y1 && (s.cat_near_pr ?? 0) >= minCat);
    if (S.stormYear != null) d = d.filter(s => s.year <= S.stormYear && s.year >= S.stormYear - 10);
    stormCache = { key, data: d, pts: d.flatMap(s => s.track.filter(p => p[3]).map(p => ({ ...s, p }))) };
    $('#stormCount').textContent = `(${d.length})`;
    renderStormList(d);
  }
  const data = stormCache.data;
  const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  const recent = (s) => S.stormYear == null ? 1 : Math.max(.15, 1 - (S.stormYear - s.year) / 10);
  return [
    new deck.PathLayer({ id: 'storm-paths', data, getPath: s => s.track.map(p => [p[0], p[1]]), getColor: s => [...rgb(CAT_COLORS[s.cat_near_pr ?? 0]), Math.round(220 * recent(s))], getWidth: s => 1.5 + (s.cat_near_pr || 0), widthUnits: 'pixels', widthMinPixels: 1.5, capRounded: true, jointRounded: true, pickable: true,
      onHover: ({ object, x, y }) => tip(object ? stormText(object) : null, x, y) }),   // a click shows the same text in a card (the click dispatcher)
    new deck.ScatterplotLayer({ id: 'storm-pts', data: stormCache.pts, getPosition: d => [d.p[0], d.p[1]], getRadius: d => 1500 + (d.p[3] || 0) * 60, getFillColor: d => [...rgb(CAT_COLORS[d.p[3] >= 137 ? 5 : d.p[3] >= 113 ? 4 : d.p[3] >= 96 ? 3 : d.p[3] >= 83 ? 2 : d.p[3] >= 64 ? 1 : 0]), Math.round(150 * recent(d))], radiusMinPixels: 1.5, radiusMaxPixels: 12, stroked: false }),
  ];
}
function renderDeck() { if (overlay) overlay.setProps({ layers: [...(window.Supply ? Supply.layers() : []), tripsLayer(), ...stormsLayers()].filter(Boolean) }); }   // service layers (supply3d.js) under the vehicles
function renderStormList(data) {
  const el = $('#stormList'); if (!el) return;
  const top = [...data].sort((a, b) => (b.cat_near_pr || 0) - (a.cat_near_pr || 0) || (b.wind_near_pr || 0) - (a.wind_near_pr || 0) || b.year - a.year).slice(0, 25);
  el.innerHTML = `<h3 class="sec">${esc(T('Strongest in window'))}</h3>` + top.map(s => `<button type="button" class="storm" data-id="${esc(s.id)}" aria-label="${esc(T('Show {name} {year} on the map', { name: stormName(s), year: s.year }))}"><span class="cat" style="background:${STORM_BADGE[s.cat_near_pr ?? 0][0]};color:${STORM_BADGE[s.cat_near_pr ?? 0][1]}">${s.cat_near_pr ? 'C' + s.cat_near_pr : esc(T('TS'))}</span><div>${esc(stormName(s))} <small>${esc(T('{year} · peak {wind} kt near PR · closest {dist} km', { year: s.year, wind: s.wind_near_pr || '—', dist: fmt(s.min_dist_km) }))}</small></div><span class="ms-icon" aria-hidden="true" style="color:#666">chevron_right</span></button>`).join('');
  el.querySelectorAll('.storm').forEach(d => d.onclick = () => { const s = S.storms.find(x => x.id === d.dataset.id); if (!s) return; const lons = s.track.map(p => p[0]), lats = s.track.map(p => p[1]); map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 60, pitch: 30, duration: reducedMotion ? 0 : 1500 }); });
}

// ── Time control ───────────────────────────────────────────────────────────
let lastT = null, raf = null;
function tick(t) {
  try { tickBody(t); } catch (e) { console.error('animation frame failed', e); }
  lastT = t; raf = requestAnimationFrame(tick);
}
function tickBody(t) {
  if (lastT != null) {
    const dt = Math.min(.25, (t - lastT) / 1000);   // a background tab must not jump the clock by hours
    if (S.mode === 'day' && S.playing) { S.clock = (S.clock + dt * S.speed) % 86400; syncClock(); renderDeck(); }
    if (S.mode === 'year' && S.yearPlaying) { S.yearF = (S.yearF ?? +$('#year').value) + dt * 12; const y = Math.min(2150, S.yearF); $('#year').value = Math.round(y / 5) * 5; $('#year').dispatchEvent(new Event('input')); if (y >= 2150) { S.yearPlaying = false; setPlayIcons(); } }
    if (S.mode === 'storms' && S.stormPlaying) { S.stormYear = Math.min(+$('#stormY1').value, (S.stormYear ?? +$('#stormY0').value) + dt * 4); if (S.stormYear >= +$('#stormY1').value) { S.stormPlaying = false; setPlayIcons(); } syncStormYear(); renderDeck(); }
  }
}
function syncClock() { const h = Math.floor(S.clock / 3600), m = Math.floor(S.clock % 3600 / 60); const label = `${pad2(h)}:${pad2(m)}`; $('#clockVal').textContent = label; $('#clock').value = S.clock; if (S.mode === 'day') { $('#tbRange').value = S.clock; $('#tbLabel').textContent = window.Supply ? Supply.dayLabel(label) : T('{time} · weekday transit', { time: label }); } const minute = Math.floor(S.clock / 60); if (window.Supply) Supply.onClock();
  if (S.trips && minute !== S.vehMinute) { S.vehMinute = minute; const n = S.trips.trips.reduce((a, d) => a + (tripStart(d) <= S.clock && tripEnd(d) >= S.clock ? 1 : 0), 0); $('#vehCount').textContent = Tn(n, '{n} vehicle in service', '{n} vehicles in service', { n: fmt(n) }); } tbSync(); }
function tbSync() { const r = $('#tbRange'); if (r) r.setAttribute('aria-valuetext', $('#tbLabel').textContent); }
// Year range follows the data file, so a yearly refresh needs no text edits.
function syncStormYears(h) {
  if (!h || !h.length) return;
  const first = Math.min(...h.map(s => s.year)), last = Math.max(...h.map(s => s.year));
  ['stormY0', 'stormY1'].forEach(id => { $('#' + id).min = first; $('#' + id).max = last; });
  $('#stormY0').value = first; $('#stormY1').value = last;
  $('#stormYearVal').textContent = `${first} – ${last}`;
  const t = $('#stormTitle'); if (t) t.textContent = T('Hurricanes {first}–{last}', { first, last });
}
function syncStormYear() { const y = Math.round(S.stormYear ?? +$('#stormY1').value); if (S.mode === 'storms') { $('#tbRange').value = y; $('#tbLabel').textContent = T('{year} · storms, trailing 10 years', { year: y }); tbSync(); } }
function setPlayIcons() { $('#tbPlay .ms-icon').textContent = (S.mode === 'day' ? S.playing : S.mode === 'storms' ? S.stormPlaying : S.yearPlaying) ? 'pause' : 'play_arrow'; $('#playTrips').innerHTML = `${icon(S.playing ? 'pause' : 'play_arrow', { size: 16 })}${esc(S.playing ? T('Pause') : T('Play'))}`; $('#playStorms').innerHTML = `${icon(S.stormPlaying ? 'pause' : 'play_arrow', { size: 16 })}${esc(S.stormPlaying ? T('Pause') : T('Play through the years'))}`; }
function setMode(mode) {
  S.mode = mode; document.querySelectorAll('.tb-modes button').forEach(b => { b.classList.toggle('active', b.dataset.mode === mode); b.setAttribute('aria-pressed', String(b.dataset.mode === mode)); });
  if (mode !== 'year') S.yearPlaying = false;
  if (mode !== 'year' && S.slrAuto) { S.slrAuto = false; $('#lySlr').checked = false; setSlr(false); }
  const r = $('#tbRange');
  if (mode === 'day') { r.min = 0; r.max = 86399; r.step = 60; syncClock(); }
  if (mode === 'year') { r.min = 2020; r.max = 2150; r.step = 5; r.value = $('#year').value; $('#tbLabel').textContent = T('{year} · {scenario} sea level', { year: $('#year').value, scenario: SCENARIOS[$('#scenario').value].label }); if (!$('#lySlr').checked) { $('#lySlr').checked = true; S.slrAuto = true; setSlr(true); } tbSync(); }
  if (mode === 'storms') { r.min = +$('#stormY0').value; r.max = +$('#stormY1').value; r.step = 1; S.stormYear = S.stormYear ?? +$('#stormY1').value; syncStormYear(); if (!$('#lyStorms').checked) { $('#lyStorms').checked = true; } renderDeck(); }
  setPlayIcons();
  refreshFolds();   // the year and storm modes switch layers on from the time bar
  if (typeof tbFoldApply === 'function') tbFoldApply();
}
function togglePlay() { if (S.mode === 'day') S.playing = !S.playing; else if (S.mode === 'year') { if (+$('#year').value >= 2150) { $('#year').value = 2020; $('#year').dispatchEvent(new Event('input')); } S.yearPlaying = !S.yearPlaying; S.yearF = +$('#year').value; } else if (S.mode === 'storms') { if (S.stormYear >= +$('#stormY1').value) S.stormYear = +$('#stormY0').value; S.stormPlaying = !S.stormPlaying; } setPlayIcons(); }

// ── One click, one answer (docs/layers.md, "Clicks") ─────────────────────────
// The same, whichever layer was switched on first, and as on the 2D map:
//  1. while the route planner is choosing a point, the click places it and does nothing else (no card, no zoom);
//  2. a deck.gl object with a card (the stops and routes of the hour, the stops of a route profile, a storm track) answers: deck.gl draws above every MapLibre layer;
//  3. otherwise the MapLibre feature drawn on top at the pixel answers (queryRenderedFeatures lists them top first): a cluster of stops zooms in, a point or a line
//     opens its card, and an area opens one card with a section for each area under the click (areaCard);
//  4. the vehicles and the line of a route profile have no card: a click on them opens no area card, but a point, line or cluster drawn under them still answers
//     (the vehicles move: a stop under a passing trail would not answer otherwise);
//  5. nothing under the click: the municipality's card on land, nothing on the sea.
// Each layer says once what it is (clickable): 'cluster', 'point', 'line', 'area', or 'base' for the municipalities (the card when nothing else is there).
const CLICKABLE = new Map();   // MapLibre layer id → { kind, card(feature, the features of that layer under the click) → html }
const clickable = (id, kind, card) => { CLICKABLE.set(id, { kind, card }); };
const DECK_NO_CARD = ['trips', 'rp-under', 'rp-line'];
const deckCards = () => ['storm-paths', ...(window.Supply ? Supply.cardLayers : [])];
const deckAt = (pt, layerIds) => { try { return overlay.pickObject({ x: pt.x, y: pt.y, radius: 0, layerIds }); } catch { return null; } };   // null before deck.gl is ready
// Whether a vehicle or the line of a route profile is at the pixel. These layers are pickable only for this query: deck.gl picks every pickable layer on each move
// of the pointer, and the vehicles take about 7 ms a pick (measured), which the view would pay all the time for the few clicks that need it. deck.gl applies new
// layers in its next frame, so the query waits for it.
const nextFrame = () => new Promise(ok => requestAnimationFrame(() => requestAnimationFrame(ok)));
async function noCardAt(pt) {
  if (!(S.trips && $('#lyTrips').checked) && !(window.Supply && Supply.profileShown)) return null;
  S.pickNoCard = true; renderDeck(); await nextFrame();
  try { return deckAt(pt, DECK_NO_CARD); } finally { S.pickNoCard = false; renderDeck(); }
}
function deckCard(i) {   // [where, html] for a deck.gl object, or null
  if (!i || !i.object) return null;
  if (i.layer.id === 'storm-paths') return [i.coordinate, `<div class="pop"><div class="meta">${stormText(i.object)}</div></div>`];   // what pointing at it shows
  return window.Supply ? Supply.card(i) : null;
}
let pop = null;
// A card opens with its top in view and the focus on its close button: MapLibre would focus its first link, which in a long card (several areas) is at the bottom,
// and scroll the card down to it. On a narrow map (a phone) a card opens above or below the point and its box moves in to stay inside the map, its tip on the point.
function popup(lngLat, html, muni) {
  if (pop) pop.remove();
  if (!html) return (pop = null);
  const W = map.getContainer().clientWidth, H = map.getContainer().clientHeight, q = map.project(lngLat);
  pop = new maplibregl.Popup({ maxWidth: '340px', focusAfterOpen: false, ...(W < 700 ? { anchor: q.y < H / 2 ? 'top' : 'bottom' } : {}) }).setLngLat(lngLat).setHTML(html).addTo(map);
  const el = pop.getElement(), body = el.querySelector('.pop'), close = el.querySelector('.maplibregl-popup-close-button');
  if (body) body.scrollTop = 0;
  if (close) close.focus({ preventScroll: true });
  const p = pop; fitPop(); map.on('move', fitPop); p.on('close', () => { map.off('move', fitPop); if (VS.muni && p.muni === VS.muni) { VS.muni = null; writeState(); } });
  if (muni) { p.muni = VS.muni = muni; writeState(); }   // a municipality's card: the selection the address and the 2D link carry
  return pop;
}
function fitPop() {
  const c = pop && pop.isOpen() && pop.getElement().querySelector('.maplibregl-popup-content'); if (!c) return;
  c.style.transform = '';
  const r = c.getBoundingClientRect(), m = map.getContainer().getBoundingClientRect(), g = 8;
  const dx = r.left < m.left + g ? m.left + g - r.left : r.right > m.right - g ? Math.max(m.left + g - r.left, m.right - g - r.right) : 0;
  if (Math.abs(dx) >= 1) c.style.transform = `translateX(${Math.round(dx)}px)`;
}
async function zoomCluster(f) {
  if (pop) pop.remove();
  try { const z = await map.getSource('stops').getClusterExpansionZoom(f.properties.cluster_id); map.easeTo({ center: f.geometry.coordinates, zoom: z, duration: reducedMotion ? 0 : 500 }); } catch { /* the cluster changed while zooming */ }
}
// The areas under a click in one card, as on the 2D map (app.js): a section for each (access.js), the visible areas in their drawing order, top first (at most two flood
// zones and two protected areas, one land-use class and one Comunidad Especial, as there), then the barrio, whose fill is invisible (last on the 2D map too), and a link
// to the municipality's card.
const AREA_MAX = { 'flood-fill': 2, 'prot-fill': 2 };
function areaCard(lngLat, fs, name) {
  const n = {}, seen = new Set(), secs = [], last = [];
  for (const f of fs) {
    const id = f.layer.id, c = CLICKABLE.get(id), key = id + JSON.stringify(f.properties);
    if (c.kind !== 'area' || seen.has(key) || (n[id] = (n[id] || 0) + 1) > (AREA_MAX[id] || 1)) continue;
    seen.add(key); (id === 'barrios-hit' ? last : secs).push(c.card(f));
  }
  const p = popup(lngLat, areasPopup([...secs, ...last], name)), b = p && p.getElement().querySelector('#idOpenMuni');
  if (b) b.onclick = () => popup(lngLat, muniCard(name), name);
}
let clickNo = 0;
map.on('click', async e => {
  if (map.getContainer().dataset.inspect === 'on') return;   // the OSM inspector answers (core/osminspect.js)
  const no = ++clickNo;   // a later click wins over one still waiting for deck.gl (noCardAt)
  if (Plan.picking >= 0) { Plan.mapPick(e.lngLat.lat, e.lngLat.lng); return; }
  if (Plan.clickMode) { Plan.appendPoint(e.lngLat.lat, e.lngLat.lng); return; }
  const d = deckCard(deckAt(e.point, deckCards()));
  if (d) { popup(d[0], d[1]); return; }
  const ids = [...CLICKABLE.keys()].filter(shownLayer), fs = ids.length ? map.queryRenderedFeatures(e.point, { layers: ids }) : [];
  const top = fs.find(f => CLICKABLE.get(f.layer.id).kind !== 'base'), c = top && CLICKABLE.get(top.layer.id);
  if (c && c.kind === 'cluster') { zoomCluster(top); return; }
  if (c && c.kind !== 'area') { popup(e.lngLat, c.card(top, fs.filter(f => f.layer.id === top.layer.id))); return; }
  const m = fs.find(f => CLICKABLE.get(f.layer.id).kind === 'base'), name = m && m.properties.municipality, ground = fs.find(f => f.layer.id === 'muni-hit');
  if (!c && !name) { popup(); return; }   // the sea
  const covered = await noCardAt(e.point); if (no !== clickNo) return;
  if (covered) popup(); else if (c) areaCard(e.lngLat, fs, ground && ground.properties.municipality); else popup(e.lngLat, muniCard(name), name);   // the areas' card links the municipality of the ground under them (a column drawn over the pixel, camera tilted, may be another's)
  const mg = (ground && ground.properties.municipality) || name;   // the time series panel (series3d.js) of the municipality on the ground; none over the sea (a flood zone offshore)
  if (!covered && mg && window.Series) Series.auto(mg);
});
// The pointer over a layer that answers a click. With the terrain on, each queryRenderedFeatures costs about 5 ms per source (MapLibre reads the terrain's
// coordinates back from the GPU for each point of a query), and a hidden layer costs as much as a shown one. MapLibre's own mouseenter and mouseleave ran one
// query per layer and per listener on every move of the pointer (8 queries, 20 to 50 ms a move, measured with flood zones, barrios and stops on): one query of the shown layers, at most
// once a frame and not during a drag, gives the same cursor.
const HOVER = new Set();
function shownLayer(id) { return !!map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none'; }   // a hidden layer has no feature to give, only a cost
let hoverAt = null, hoverRaf = 0, hoverOn = false;
function hoverCursor(id) { HOVER.add(id); }
function hoverCheck() {
  hoverRaf = 0; if (!hoverAt) return;
  const ids = [...HOVER].filter(shownLayer), on = ids.length > 0 && map.queryRenderedFeatures(hoverAt, { layers: ids }).length > 0;
  if (on !== hoverOn) { hoverOn = on; map.getCanvas().style.cursor = on ? 'pointer' : ''; }
}
map.on('mousemove', e => { if (e.originalEvent.buttons) return; hoverAt = e.point; if (!hoverRaf) hoverRaf = requestAnimationFrame(hoverCheck); });
map.on('mouseout', () => { hoverAt = null; if (hoverOn) { hoverOn = false; map.getCanvas().style.cursor = ''; } });
function tip(html, x, y) { const el = $('#tip'); if (!html) { el.classList.remove('show'); return; } el.innerHTML = html; el.style.left = (x + 14) + 'px'; el.style.top = (y + 14) + 'px'; el.classList.add('show'); }
initHelp(k => HELP[k]);
document.addEventListener('click', e => { const g = e.target.closest('[data-goto]'); if (g) { e.preventDefault(); showTab(g.dataset.goto); } });
function renderCatChips() {
  $('#catChips').innerHTML = Object.entries(CATEGORY_META).map(([c, m]) => `<button type="button" class="chip ${S.cats.has(c) ? '' : 'off'}" aria-pressed="${S.cats.has(c)}" data-cat="${c}" style="background:${m.soft};color:${m.text}">${icon(m.icon, { size: 15 })}${esc(categoryLabel(c))}</button>`).join('');
  $('#catChips').querySelectorAll('.chip').forEach(ch => ch.onclick = () => { const c = ch.dataset.cat; S.cats.has(c) ? S.cats.delete(c) : S.cats.add(c); ch.classList.toggle('off', !S.cats.has(c)); ch.setAttribute('aria-pressed', String(S.cats.has(c))); refreshPlacesFilter(); });
}
function renderAbout() { const m = S.meta; $('#snapshotLabel').innerHTML = `<b>${esc(snapshotLabel(m.label))}</b>`; }

// ── Navigation: buttons and keys ───────────────────────────────────────────
// The compass and zoom buttons come from MapLibre. These add what a 3D view needs: rotate, tilt, look straight down, home, and keys.
let lastPitch = 60;
const ease = (o) => map.easeTo({ ...o, duration: reducedMotion ? 0 : 450 });
const goHome = () => map.flyTo({ ...VIEWS.island, duration: reducedMotion ? 0 : 2200, essential: false });
const topDown = () => { if (map.getPitch() > 5) { lastPitch = map.getPitch(); ease({ pitch: 0, bearing: 0 }); } else ease({ pitch: lastPitch || 60 }); };
class NavPad {
  onAdd() {
    const el = this.el = document.createElement('div'); el.className = 'maplibregl-ctrl maplibregl-ctrl-group navpad'; el.setAttribute('role', 'group'); el.setAttribute('aria-label', T('View controls'));
    const btn = (name, label, fn) => { const b = document.createElement('button'); b.type = 'button'; b.title = label; b.setAttribute('aria-label', label); b.innerHTML = `<span class="ms-icon" aria-hidden="true">${name}</span>`; b.onclick = fn; el.appendChild(b); return b; };
    btn('rotate_left', T('Rotate the view left (Q)'), () => ease({ bearing: map.getBearing() - 30 }));
    btn('rotate_right', T('Rotate the view right (E)'), () => ease({ bearing: map.getBearing() + 30 }));
    btn('keyboard_arrow_up', T('Tilt up, towards the horizon'), () => ease({ pitch: Math.min(map.getMaxPitch(), map.getPitch() + 10) }));
    btn('keyboard_arrow_down', T('Tilt down, towards a top-down view'), () => ease({ pitch: Math.max(0, map.getPitch() - 10) }));
    btn('explore', T('Look straight down, or return to the tilted view (T)'), topDown);
    btn('home', T('Show the whole island (H)'), goHome);
    const help = btn('keyboard', T('How to move around: mouse, touch and keyboard'), () => { const h = $('#navHelp'); h.hidden = !h.hidden; help.setAttribute('aria-expanded', String(!h.hidden)); });
    help.setAttribute('aria-expanded', 'false'); help.setAttribute('aria-controls', 'navHelp');
    return el;
  }
  onRemove() { this.el.remove(); }
}
map.addControl(new NavPad(), 'bottom-right');
if (window.CleanView) map.addControl({ onAdd() { const d = document.createElement('div'); d.className = 'maplibregl-ctrl maplibregl-ctrl-group cv-ctl'; d.appendChild(CleanView.button()); return d; }, onRemove() {} }, 'bottom-right');   // Clean view (core/cleanview.js)
map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: false }, trackUserLocation: false, showAccuracyCircle: false }), 'bottom-right');
$('#navHelpClose').onclick = () => { $('#navHelp').hidden = true; };
map.getCanvas().setAttribute('aria-label', T('Interactive 3D map. Arrow keys pan, Shift and arrow keys rotate and tilt, plus and minus zoom.'));
document.addEventListener('keydown', e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'Escape') { if (!$('#navHelp').hidden) { $('#navHelp').hidden = true; } stopFly(); return; }
  const a = document.activeElement;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) || a.isContentEditable) return;
  if (e.key === '/') { e.preventDefault(); $('#search').focus(); return; }
  if (a !== document.body && !map.getContainer().contains(a)) return;   // letters only steer the map when nothing else has the focus
  const k = e.key.toLowerCase();
  if (k === 'n') ease({ bearing: 0 }); else if (k === 't') topDown(); else if (k === 'h') goHome();
  else if (k === 'q') ease({ bearing: map.getBearing() - 15 }); else if (k === 'e') ease({ bearing: map.getBearing() + 15 });
});

// ── Search ─────────────────────────────────────────────────────────────────
// Municipalities, tourism places, transit stops and routes, and the place index (barrios, towns, streets, PR routes, landmarks).
let transportRows = null, transportP = null, searchMarker = null;
const settle = (p) => p ? Promise.race([p, new Promise(r => setTimeout(r, 1500))]) : Promise.resolve();   // a first search waits briefly for the stop list
function warmSearch() {
  Gaz.load().catch(() => {});
  if (!transportP) transportP = Data.json('data/transport.json').then(d => { transportRows = d.filter(f => f.name && (f.source === 'ati_gtfs' || f.source === 'muni_gtfs' || ['rail_station', 'bus_station', 'ferry_terminal', 'airport'].includes(f.kind))); transportRows.forEach(f => { f._n = norm(f.name); }); }).catch(() => {});
}
const SEARCH_ZOOM = { municipio: 12, town: 14, village: 15, barrio: 14, neighborhood: 15, route: 14, road: 16, airport: 14, park: 15, beach: 16, peak: 15, water: 14 };
SearchDecorate.push(r => { const m = S.muni[r.label]; if (r.kind === 'municipio' && m) r.sub = T('Municipality · {n} tourism places · {pop} residents', { n: fmt(m.assets), pop: fmt(m.population_2020) }); });
SearchSources.push((pq) => {   // tourism places under the current category filter
  if (!S.places) return [];
  const hits = [];
  for (const p of S.places) {
    if (!p.name || !placeDrawn(p) || p.confidence < .5 || p.type === 'Places of Worship' || !S.cats.has(p.category)) continue;
    const nn = p._n || (p._n = norm(p.name));
    let s = textScore(nn, pq.n, pq.tokens);
    if (s === null) { const nt = p._t || (p._t = norm(`${p.type} ${typeLabel(p.type)}`)); if (nt.includes(pq.n)) s = 2.8; else continue; }
    hits.push({ score: s * 10 + 3, kind: 'tourism', label: p.name, sub: `${typeLabel(p.type)} · ${p.municipality}${p.sfha ? ` · ${T('flood hazard area')}` : ''}`, lat: p.lat, lng: p.lng, place: p, iconHtml: typeIcon(p.type, p.category, 24) });
  }
  return hits.sort((a, b) => a.score - b.score || a.label.length - b.label.length).slice(0, 8);
});
SearchSources.push(async (pq) => {   // scheduled stops, stations and terminals
  if (!transportRows) { warmSearch(); await settle(transportP); }
  if (!transportRows) return [];
  const out = [];
  for (const f of transportRows) { const s = textScore(f._n, pq.n, pq.tokens); if (s !== null) out.push({ score: s * 10 + 2.5, kind: 'stop', label: f.name, sub: `${KIND_LABEL[f.kind] || humanize(f.kind)}${f.operator_name ? ' · ' + f.operator_name : ''}${f.municipality ? ' · ' + f.municipality : ''}`, lat: f.lat, lng: f.lng, f }); }
  return out.sort((a, b) => a.score - b.score).slice(0, 6);
});
SearchSources.push((pq, { pointsOnly }) => {   // transit routes (lines, so the route planner skips them)
  if (pointsOnly || !S.routes) return [];
  const out = [];
  for (const f of S.routes.features) {
    const p = f.properties, n = p._n || (p._n = norm(`${p.short_name || ''} ${p.long_name || ''} ${p.operator_name || ''}`)), s = textScore(n, pq.n, pq.tokens);
    if (s !== null) out.push({ score: s * 10 + 2.5, kind: 'transit_route', label: (p.long_name && p.short_name && p.long_name.startsWith(p.short_name) ? p.long_name : `${p.short_name || ''} ${p.long_name || ''}`).trim(), sub: T('Transit route · {operator}', { operator: p.operator_name || '' }), feature: f });
  }
  return out.sort((a, b) => a.score - b.score).slice(0, 4);
});
function featureBounds(geom) {   // [[west, south], [east, north]]
  let w = 180, s = 90, e = -180, n = -90;
  (function walk(a) { if (typeof a[0] === 'number') { w = Math.min(w, a[0]); e = Math.max(e, a[0]); s = Math.min(s, a[1]); n = Math.max(n, a[1]); } else a.forEach(walk); })(geom.coordinates);
  return [[w, s], [e, n]];
}
const camMs = () => reducedMotion ? 0 : 2200;
function flyToPoint(lng, lat, zoom) { map.flyTo({ center: [lng, lat], zoom, pitch: Math.max(map.getPitch(), 50), bearing: map.getBearing(), duration: camMs(), essential: false }); }
function fitTo(bounds, opts = {}) { map.fitBounds(bounds, { padding: 70, maxZoom: 16, pitch: Math.max(map.getPitch(), 45), duration: camMs(), essential: false, ...opts }); }
function showSearchMarker(r, html) {
  if (searchMarker) searchMarker.remove();
  const body = html || `<div class="pop"><h4>${icon('place', { size: 20, color: '#B82415' })}<span>${esc(r.label)}</span></h4><div class="meta">${esc(r.sub || '')}</div></div>`;
  const links = `<div class="pop"><div class="links"><button type="button" class="linklike" data-plan="from">${esc(T('Route from here'))}</button><button type="button" class="linklike" data-plan="to">${esc(T('Route to here'))}</button></div></div>`;
  searchMarker = new maplibregl.Marker({ color: '#B82415' }).setLngLat([r.lng, r.lat]).setPopup(new maplibregl.Popup({ offset: 30, maxWidth: '320px' }).setHTML(body + links)).addTo(map);
  searchMarker._pick = { lat: r.lat, lng: r.lng, label: r.label, sub: r.sub || '' };
  setTimeout(() => searchMarker && searchMarker.togglePopup(), reducedMotion ? 0 : 1200);
}
function placeHtml(p) { return `<div class="pop"><h4>${typeIcon(p.type, p.category, 26)}<span>${esc(p.name || T('(unnamed)'))}</span></h4><div class="meta">${typeChip(p.type, p.category)}</div><div class="meta">${esc(p.municipality)}${p.sfha == 1 ? ` · ${Th('<b style="color:#0B3D5C">flood zone {zone}</b>', { zone: p.flood_zone })}` : ''}</div>${accessBlock(p)}<div class="src">Overture Maps</div></div>`; }
function accessBlock(p) { const a = accessPopup(p); return (a.badge ? `<div class="flags">${a.badge}</div>` : '') + a.lines; }
function onSearchPick(r) {
  if (isMobile()) setPanel(false);
  if (r.kind === 'municipio') { const f = S.muniFc && S.muniFc.features.find(x => x.properties.municipality === r.label); if (f) { fitTo(featureBounds(f.geometry), { padding: 40, maxZoom: 13 }); showSearchMarker(r); return; } }
  if (r.kind === 'transit_route') { fitTo(featureBounds(r.feature.geometry), { padding: 80 }); return; }
  if (r.kind === 'tourism') { flyToPoint(r.lng, r.lat, 17); showSearchMarker(r, placeHtml(r.place)); return; }
  if (r.kind === 'stop') { flyToPoint(r.lng, r.lat, 17); showSearchMarker(r, `<div class="pop"><h4>${icon('directions_bus', { size: 20, color: '#205D7B' })}<span>${esc(r.label)}</span></h4><div class="meta">${esc(r.sub)}</div>${r.f.routes && r.f.routes.length ? `<div class="meta"><b>${esc(T('Routes:'))}</b> ${r.f.routes.map(esc).join(', ')}</div>` : ''}</div>`); return; }
  if (r.bbox) fitTo([[r.bbox[0][1], r.bbox[0][0]], [r.bbox[1][1], r.bbox[1][0]]], { maxZoom: 17 }); else flyToPoint(r.lng, r.lat, SEARCH_ZOOM[r.kind] || 16);
  showSearchMarker(r);
}
document.addEventListener('click', e => {   // "Route from / to here" in the search marker's popup
  const b = e.target.closest('[data-plan]'); if (!b || !searchMarker) return;
  if (!Plan.root) { toast(T('The route planner is still loading.')); return; }
  Plan.setStop(b.dataset.plan === 'from' ? 0 : Plan.stops.length - 1, searchMarker._pick); showTab('route');
});
attachSearch($('#search'), $('#searchResults'), { warm: warmSearch, online: true, run: q => searchEverything(q, { bias: map.getCenter() }), onPick: onSearchPick, emptyText: T('No match. Try a street, town, landmark or stop name, or a PR route such as PR-52. Tourism places follow the category filter.') });
// the long hint only where it fits in the box with 8 px to spare, the short one otherwise (in Spanish the long one was cut at 1024 px, and on the 3D view at 1400)
let phCtx = null;
const searchPlaceholder = () => {
  const i = $('#search'), long = T('Search a place or street'), s = getComputedStyle(i), room = i.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
  phCtx = phCtx || document.createElement('canvas').getContext('2d'); phCtx.font = s.font;
  i.placeholder = isMobile() || (room > 0 && phCtx.measureText(long).width > room - 8) ? T('Search') : long;
};
searchPlaceholder(); mobileQuery.addEventListener('change', searchPlaceholder); new ResizeObserver(searchPlaceholder).observe($('#search')); if (document.fonts) document.fonts.ready.then(searchPlaceholder);

// ── Route planner (the logic is in plan.js and shared with the 2D map) ─────
const planMarkers = [];
// The route is drawn as fresh layers each time it changes (see the note at the end of this function for why).
let planGen = 0;
function setPlanData(features) {
  const prev = planGen; planGen++;
  const g = planGen, src = 'plan' + g, fc = { type: 'FeatureCollection', features };
  map.addSource(src, { type: 'geojson', data: fc });
  const part = (p) => ['==', ['get', 'part'], p];
  map.addLayer({ id: 'plan-casing' + g, type: 'line', source: src, filter: part('route'), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': .9 } });
  map.addLayer({ id: 'plan-line' + g, type: 'line', source: src, filter: part('route'), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#2A2E2E', 'line-width': 5 } });
  map.addLayer({ id: 'plan-gaps' + g, type: 'line', source: src, filter: part('gap'), layout: { 'line-cap': 'round' }, paint: { 'line-color': '#FF4D38', 'line-width': 4, 'line-dasharray': [.1, 2.2] } });
  if (prev) { for (const id of ['plan-gaps', 'plan-line', 'plan-casing']) if (map.getLayer(id + prev)) map.removeLayer(id + prev); if (map.getSource('plan' + prev)) map.removeSource('plan' + prev); }
  // Draped layers added after the terrain only paint on the terrain tiles that were current when they were added; re-reading an existing
  // source once the new tiles are in makes MapLibre repaint every terrain tile, so the whole route shows.
  map.once('idle', () => { const r = map.getSource('routes'); if (r && S.routes) r.setData(S.routes); });
}
const planHost = {
  center: () => { const c = map.getCenter(); return { lat: c.lat, lng: c.lng }; },
  picking(on) { map.getCanvas().style.cursor = on ? 'crosshair' : ''; if (on) { if (isMobile()) setPanel(false); toast(T('Click the map to place the point. Press Escape to stop.'), 5000); } },
  focusPoint(r) { if (Plan.placed().length < 2) { if (r.bbox) fitTo([[r.bbox[0][1], r.bbox[0][0]], [r.bbox[1][1], r.bbox[1][0]]], { maxZoom: 15 }); else flyToPoint(r.lng, r.lat, Math.max(map.getZoom(), 13)); } },
  async data() {
    const [blocks, transport, routes, flood, prot, ops, supply] = await Promise.all([Data.json('data/population_blocks.json'), S.transport || Data.json('data/transport.json'), S.routes || Data.json('data/transit_routes.geojson'), S.flood || Data.json('data/flood.geojson'), S.prot || Data.json('data/protected.geojson'), Data.json('data/operators.json'), Data.json('data/transit_supply.json').catch(() => null)]);
    return { blocks, transport, routes, flood, prot, ops: ops.operators, places: await loadPlaces().catch(() => null), muniFc: S.muniFc, supply };   // supply: the existing service near the route (optional)
  },
  fit(b) { stopFly(); fitTo([[b[0][1], b[0][0]], [b[1][1], b[1][0]]], { maxZoom: 16, pitch: Math.min(Math.max(map.getPitch(), 30), 60) }); if (isMobile()) toast(T('Route drawn. Close the panel to see it on the map.'), 5000); },
  extraButtons: () => `<div class="btn-row"><button type="button" class="btn primary" id="flyAlong">${icon('play_arrow', { size: 16 })}${esc(T('Fly along the route'))}</button></div>`,
  drawRoute(coords, stops) {
    const r = Plan.result, feats = [];
    if (coords && coords.length > 1) {
      feats.push({ type: 'Feature', properties: { part: 'route' }, geometry: { type: 'LineString', coordinates: coords } });
      if (r && !r.path.allOnRoads) r.path.legs.forEach((l, i) => { if (!l.ok) feats.push({ type: 'Feature', properties: { part: 'gap' }, geometry: { type: 'LineString', coordinates: coords.slice(r.path.legAt[i], (r.path.legAt[i + 1] ?? coords.length - 1) + 1) } }); });
    } else stopFly();
    setPlanData(feats);
    planMarkers.forEach(m => m.remove()); planMarkers.length = 0;
    stops.forEach((s, i) => {
      const el = document.createElement('div'); el.className = `plan-marker ${s.row === 0 ? 'a' : s.row === Plan.stops.length - 1 ? 'z' : 'v'}`; el.textContent = Plan.letter(s.row); el.title = T('{label} (drag to move)', { label: s.label });
      const m = new maplibregl.Marker({ element: el, draggable: true }).setLngLat([s.lng, s.lat]).addTo(map);
      m.on('dragend', () => { const p = m.getLngLat(); Plan.movePoint(i, p.lat, p.lng); });
      planMarkers.push(m);
    });
    Core.activelayers.changed();
    writeState(true);
  },
};
document.addEventListener('keydown', e => { if (e.key === 'Escape' && Plan.root && (Plan.picking >= 0 || Plan.clickMode)) { Plan.picking = -1; Plan.setClickMode(false); Plan.root.querySelectorAll('[data-act=pick]').forEach(x => x.setAttribute('aria-pressed', 'false')); } });

// A camera flight along the planned route: follows the line at a steady pace, looking ahead, until any input stops it.
let fly = null;
function stopFly() { if (!fly) return; cancelAnimationFrame(fly.raf); fly = null; const b = $('#flyAlong'); if (b) b.innerHTML = `${icon('play_arrow', { size: 16 })}${esc(T('Fly along the route'))}`; }
function flyAlong() {
  if (fly) { stopFly(); return; }
  const r = Plan.result; if (!r) return;
  if (reducedMotion) { toast(T('Motion is reduced in your settings, so the camera does not fly along the route.'), 6000); return; }
  const c = r.path.coords, cum = [0];
  for (let i = 1; i < c.length; i++) cum.push(cum[i - 1] + distM([c[i - 1][1], c[i - 1][0]], [c[i][1], c[i][0]]));
  const total = cum[cum.length - 1]; if (!total) return;
  const at = (d) => { let lo = 0, hi = cum.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (cum[m] <= d) lo = m; else hi = m; } const t = cum[hi] > cum[lo] ? (d - cum[lo]) / (cum[hi] - cum[lo]) : 0; return [c[lo][0] + (c[hi][0] - c[lo][0]) * t, c[lo][1] + (c[hi][1] - c[lo][1]) * t]; };
  const heading = (a, b) => (Math.atan2((b[0] - a[0]) * Math.cos(rad(a[1])), b[1] - a[1]) * 180 / Math.PI + 360) % 360;
  const speed = Math.max(120, Math.min(1500, total / 45));   // the whole route in about 45 seconds, never slower than 120 m/s
  let s = 0, last = performance.now(), bearing = heading(at(0), at(Math.min(total, 500)));
  fly = { raf: 0 };
  const b = $('#flyAlong'); if (b) b.innerHTML = `${icon('close', { size: 16 })}${esc(T('Stop flying'))}`;
  if (isMobile()) setPanel(false);
  const step = (now) => {
    if (!fly) return;
    const dt = Math.min(.1, (now - last) / 1000); last = now; s += speed * dt;
    if (s >= total) { stopFly(); return; }
    const p = at(s), target = heading(p, at(Math.min(total, s + 700)));
    bearing += (((target - bearing + 540) % 360) - 180) * Math.min(1, dt * 1.6);
    map.jumpTo({ center: p, bearing, pitch: 64, zoom: 14.8 });
    fly.raf = requestAnimationFrame(step);
  };
  map.jumpTo({ center: at(0), bearing, pitch: 64, zoom: 14.8 });
  fly.raf = requestAnimationFrame(step);
}
['mousedown', 'touchstart', 'wheel'].forEach(t => map.on(t, e => { if (fly && e.originalEvent) stopFly(); }));
function initPlanner() {
  const r = new URLSearchParams(location.hash.slice(1)).get('r');   // read before Plan.init rewrites the address
  $('#planBox').innerHTML = planMarkup(); planWire($('#planBox')); Plan.init(planHost, $('#planBox'));
  $('#planBox').addEventListener('click', e => { if (e.target.closest('#flyAlong')) flyAlong(); });
  if (r) { showTab('route', { open: false }); Plan.restore(r); }
}

// ── Wiring ─────────────────────────────────────────────────────────────────
initTabs(); initPanel(); initFolds($('#tab-layers'));
// The "layers on" chip at the top of the view (core/activelayers.js): the data layers of the menus and the municipality columns. The Scene group (terrain, buildings), the time bar and
// the camera are settings of the view, not data, so they are not counted and "Turn all off" leaves them as they are. Límites (the municipal lines) is the reference layer, as on
// the 2D map: on when the view opens, never counted. The walk rings count while they are drawn (zoom 14, and stops or stations on).
Core.activelayers.mount(Core.activelayers.combine(
  Core.activelayers.switches(['lyBarrios', 'lyCols', 'lyOz', 'lySurfHeat', 'lyFlood', 'lySlr', 'lyProt', 'lyDumping', 'lyBroadband', 'lyHexgrid', 'lyPowerLines', 'lyPlants', 'lyReservoirs', 'lyRivers', 'lyGroundwater', 'lyRain', 'lyLanduse', 'lySoil', 'lySlide', 'lyPubHousing', 'lyLihtc', 'lyRoutes', 'lyFprRoutes', 'lyPublicos', 'lyLinks', 'lyTraffic', 'lyBridges', 'lyAirports', 'lyFerries', 'lyEvCharge', 'lyStops', 'lyHubs', 'lyTaxi', 'walkRings', 'lyTrips', 'lyFire', 'lyPolice', 'lyTownhalls', 'lyLibraries', 'lySchools', 'lyHistoric', 'lyComunidades', 'lyWcrp', 'lyPlaces', 'lySupRoutes', 'lySupStops', 'lyStorms', 'lyGaps', 'lyXfer'].map(id => $('#' + id)),
    { lyCols: () => $('#metric').value === '__any' ? (ENG.E && ENG.E.V[ENG.h] ? T(ENG.E.V[ENG.h].label) : '') : $('#metric').selectedOptions[0].text, walkRings: () => T('Walk rings') },   // the columns by their measure
    { walkRings: () => ringsDrawn() }),
  Core.activelayers.plan(() => Plan.root ? Plan : null),
  Core.activelayers.state(() => S.slrAuto, v => { S.slrAuto = v; }),
  Core.activelayers.state(measureSnap, measureRestore)), $('#map'));   // and the columns' keys in the address (core/viewstate.js)   // Undo: sea level rise that the year mode switched on goes off again when the mode is left
document.querySelectorAll('.tb-modes button').forEach(b => b.onclick = () => setMode(b.dataset.mode));
// The time bar folds to its play button and clock (2026-11-11): by itself while nothing on the map moves in time (no vehicles, sea level or storms),
// and by the visitor's choice, kept for the visit (sessionStorage 'tbFold': '1' folded, '0' open). Folded, its play button still works.
function tbFoldApply() {
  let pick = null; try { pick = sessionStorage.getItem('tbFold'); } catch { /* storage blocked: follow the layers */ }
  const moving = ['#lyTrips', '#lySlr', '#lyStorms'].some(id => { const el = $(id); return el && el.checked; });
  const folded = pick === '1' || (pick === null && !moving), bar = $('#timebar'), b = $('#tbFold');
  bar.classList.toggle('folded', folded); b.setAttribute('aria-expanded', String(!folded));
  const label = T(folded ? 'Open the time bar' : 'Fold the time bar'); b.title = label; b.setAttribute('aria-label', label);
  b.querySelector('.ms-icon').textContent = folded ? 'keyboard_arrow_up' : 'keyboard_arrow_down';
}
$('#tbFold').onclick = () => { const folded = $('#timebar').classList.contains('folded'); try { sessionStorage.setItem('tbFold', folded ? '0' : '1'); } catch { /* storage blocked */ } tbFoldApply(); };
document.addEventListener('change', e => { if (e.target && /^ly(Trips|Slr|Storms)$/.test(e.target.id)) tbFoldApply(); });
tbFoldApply();
document.querySelectorAll('[data-fly]').forEach(b => b.onclick = () => map.flyTo({ ...VIEWS[b.dataset.fly], duration: reducedMotion ? 0 : 2500, essential: false }));
$('#lyTerrain').onchange = e => setTerrain(e.target.checked);
$('#exag').oninput = e => { $('#exagVal').textContent = `${(+e.target.value).toFixed(1)}×`; if ($('#lyTerrain').checked) setTerrain(true); };
$('#lyBuildings').onchange = e => showBuildings(e.target.checked);
$('#lyPlaces').onchange = () => { if ($('#lyPlaces').checked && !S.places) loadPlaces().catch(() => {}); updatePlacesMode(); }; $('#placesMode').onchange = updatePlacesMode;
// the checkbox turns the columns on and off; the menu picks the measure, and picking one turns them on (the change event updates the group's "layers on" count)
$('#lyCols').onchange = e => setMetric(e.target.checked ? $('#metric').value : '');
$('#metric').onchange = e => { const c = $('#lyCols'); if (c.checked) setMetric(e.target.value); else { c.checked = true; c.dispatchEvent(new Event('change')); } };
const layerToggle = (key, load, ids) => async e => { try { await once(key, load); ids.forEach(id => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', e.target.checked ? 'visible' : 'none')); } catch (err) { e.target.checked = false; refreshFolds(); toast(T('That layer could not be loaded. Check your connection and try again.'), 6000); } };
$('#lyFlood').onchange = layerToggle('flood', addFlood, ['flood-fill']);
$('#lyLanduse').onchange = layerToggle('landuse', addLanduse, ['landuse-fill']);
$('#lyProt').onchange = layerToggle('prot', addProtected, ['prot-fill']);
$('#lySurfHeat').onchange = async e => { await layerToggle('surfheat', addSurfHeat, ['surfheat-img'])(e); $('#surfLegend').style.display = e.target.checked ? '' : 'none'; surfPaint(); };
$('#lyComunidades').onchange = layerToggle('comunidades', addComunidades, ['ce-fill', 'ce-line']);
$('#lyWcrp').onchange = layerToggle('wcrp', addWcrp, ['wcrp-pts']);
$('#lyRoutes').onchange = layerToggle('routes', addRoutes, ['routes-line', 'routes-inferred', 'routes-approx', 'routes-ferry']);
$('#lyHubs').onchange = async e => { await layerToggle('hubs', addHubs, ['hubs-pts'])(e); updateRings(); };
// The layers the 2D map has too (docs/layers.md): Límites, barrios, stops, taxi stands and EV charging, the walk rings, the public facilities and the planning layers
$('#lyMuni').onchange = e => map.getLayer('muni-line') && map.setLayoutProperty('muni-line', 'visibility', e.target.checked ? 'visible' : 'none');
$('#lyBarrios').onchange = layerToggle('barrios', addBarrios, ['barrios-line', 'barrios-hit']);
$('#lyStops').onchange = async e => { await layerToggle('stops', addStops, ['stops-cluster', 'stops-count', 'stops-pts'])(e); updateRings(); };
$('#lyTaxi').onchange = layerToggle('taxi', addTaxi, ['taxi-pts']);
$('#walkRings').onchange = async e => { if (e.target.checked) try { await once('rings', addRings); } catch { e.target.checked = false; refreshFolds(); toast(T('That layer could not be loaded. Check your connection and try again.'), 6000); } updateRings(); };
map.on('zoomend', () => { if ($('#walkRings').checked) Core.activelayers.changed(); });   // the rings are drawn from zoom 14: the chip follows
['lyGaps', 'lyXfer'].forEach(id => { $('#' + id).onchange = async e => { try { await (id === 'lyGaps' ? setGaps : setXfer)(e.target.checked); } catch { e.target.checked = false; Core.activelayers.changed(); toast(T('That layer could not be loaded. Check your connection and try again.'), 6000); } }; });
// The public facilities: core/facilities.js (shared with the 2D map), js/facilities3d.js and their Spanish load the first time one of their layers or help buttons is used; each layer's file on first use
let facP = null, facJs = null;
const addJs = (src, integrity) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; if (integrity) { s.integrity = integrity; s.crossOrigin = 'anonymous'; } s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
const facLoad = () => facP || (facP = Promise.allSettled([I18N.load('facilities'), facJs = facJs || (Core.facilities ? Promise.resolve() : addJs('js/core/facilities.js?v=25')).then(() => addJs('js/facilities3d.js?v=14')).catch(e => { facJs = null; throw e; })]).then(r => { const bad = r.find(x => x.status === 'rejected'); if (bad) throw bad.reason; }).catch(e => { facP = null; throw e; }));
const FAC = { oz: 'lyOz', pubhousing: 'lyPubHousing', lihtc: 'lyLihtc', reservoirs: 'lyReservoirs', broadband: 'lyBroadband', hexgrid: 'lyHexgrid', powerlines: 'lyPowerLines', plants: 'lyPlants', rivers: 'lyRivers', groundwater: 'lyGroundwater', rain: 'lyRain', fire: 'lyFire', police: 'lyPolice', townhalls: 'lyTownhalls', libraries: 'lyLibraries', schools: 'lySchools', historic: 'lyHistoric', dumping: 'lyDumping', fprroutes: 'lyFprRoutes', publicos: 'lyPublicos', links: 'lyLinks', traffic: 'lyTraffic', bridges: 'lyBridges', airports: 'lyAirports', ferries: 'lyFerries', evcharge: 'lyEvCharge' };
Object.entries(FAC).forEach(([k, id]) => { $('#' + id).onchange = async e => { try { if (e.target.checked) { await facLoad(); await Facilities3D.show(k); } else if (typeof Facilities3D !== 'undefined') Facilities3D.hide(k); } catch { e.target.checked = false; refreshFolds(); toast(T('That layer could not be loaded. Check your connection and try again.'), 6000); } }; });
document.addEventListener('click', e => { const h = e.target.closest('[data-help^="fac_"]'), key = h && h.dataset.help; if (!h || HELP[key]) return; e.preventDefault(); e.stopPropagation(); facLoad().then(() => { if (HELP[key]) h.click(); }, () => toast(T('The help could not be loaded. Check your connection and try again.'), 5000)); }, true);   // a help text that has not arrived: load it, then press the button again
// Soils and Landslide susceptibility: js/soil.js (the 2D map's tables, legends and pop-up), js/soil3d.js and their Spanish, loaded the first time either layer or its help is used
let soilP = null;
const soilLoad = () => soilP || (soilP = Promise.all([I18N.load('soil'), typeof addSoil === 'function' ? 0 : addJs('js/soil.js?v=4').then(() => addJs('js/soil3d.js?v=2'))]).catch(e => { soilP = null; throw e; }));
$('#lySoil').onchange = async e => { await layerToggle('soil', async () => { await soilLoad(); soilMenu(); await addSoil(); }, ['soil-fill'])(e); if ($('#soilProp')) soilLegend(); $('#soilLegend').style.display = e.target.checked && $('#soilProp') ? '' : 'none'; };
$('#lySlide').onchange = async e => { await layerToggle('slide', async () => { await soilLoad(); addSlide(); }, ['slide-img'])(e); if (typeof slideLegend === 'function') slideLegend(); $('#slideLegend').style.display = e.target.checked && $('#slideLegend').innerHTML ? '' : 'none'; };
document.addEventListener('click', e => { const h = e.target.closest('[data-help="soil"],[data-help="slide"]'), key = h && h.dataset.help; if (!h || HELP[key]) return; e.preventDefault(); e.stopPropagation(); soilLoad().then(() => { if (HELP[key]) h.click(); }, () => toast(T('The help could not be loaded. Check your connection and try again.'), 5000)); }, true);
// ── Load on first use: the time series panel (series3d.js) and transit supply (supply3d.js; docs/performance.md, "Make room 4") ──
// Until series3d.js is in, window.Series stands in for it: the card still offers the "Time series" link, and the first open or auto loads the
// panel and passes the call on; series3d.js then puts its own Series in place (and its own click listener; this one stops at that point).
let seriesP = null;
const seriesLoad = () => seriesP || (seriesP = addJs('js/series3d.js?v=6').then(() => window.Series).catch(e => { seriesP = null; toast(T('The time series could not be loaded. Check your connection and try again.'), 6000); throw e; }));
window.Series = { stub: true, open: (...a) => seriesLoad().then(R => R && R.open(...a)),
  auto(name) { if (name && metricKey === '__any' && !matchMedia('(max-width: 699px)').matches) seriesLoad().then(R => R && R.auto(name)).catch(() => {}); },   // series3d.js auto: it opens by itself only with the columns on, and not on a phone
  close() {}, sync() {}, get state() { return { open: false, name: null, y: null, sel: null, rows: 0, hit: 0 }; } };
document.addEventListener('click', e => { if (!window.Series || !window.Series.stub) return; const b = e.target.closest('[data-series]'); if (b) { e.preventDefault(); window.Series.open(b.dataset.series, { opener: b, focus: true }).catch(() => {}); } });
// supply3d.js (the day of the timetable, Service at this hour, Existing routes): the Time and Route tabs load it, and so does any of its controls
// used before that; once it runs, Supply.init wires the controls itself, and the control that loaded it gets its change again.
let supplyP = null;
const supplyLoad = () => supplyP || (supplyP = addJs('js/supply3d.js?v=6').then(() => { syncClock(); renderDeck(); return window.Supply; }).catch(e => { supplyP = null; toast(T('That layer could not be loaded. Check your connection and try again.'), 6000); throw e; }));
document.querySelectorAll('#daySeg button').forEach(b => b.onclick = () => supplyLoad().then(S_ => S_ && S_.setDay(b.dataset.day)).catch(() => {}));
['lySupRoutes', 'lySupStops', 'supExpired'].forEach(id => { $('#' + id).onchange = e => { if (window.Supply) return; supplyLoad().then(() => e.target.dispatchEvent(new Event('change'))).catch(() => { e.target.checked = !e.target.checked; refreshFolds(); }); }; });
function onTabShown(name) { if (name === 'time' || name === 'route') supplyLoad().catch(() => {}); }   // common.js showTab calls it
$('#lySlr').onchange = e => { S.slrAuto = false; setSlr(e.target.checked); };
$('#lyTrips').onchange = renderDeck; $('#lyStorms').onchange = renderDeck; $('#stormCat').onchange = renderDeck;
$('#year').oninput = e => { $('#yearVal').textContent = e.target.value; const ft = currentFeet(); if ($('#lySlr').checked && ft !== slrLayerFt) setSlr(true); if (S.mode === 'year') { $('#tbRange').value = e.target.value; $('#tbLabel').textContent = T('{year} · {scenario} sea level', { year: e.target.value, scenario: SCENARIOS[$('#scenario').value].label }); } };
$('#scenario').onchange = () => { const ft = currentFeet(); if ($('#lySlr').checked && ft !== slrLayerFt) setSlr(true); if (S.mode === 'year') $('#tbLabel').textContent = T('{year} · {scenario} sea level', { year: $('#year').value, scenario: SCENARIOS[$('#scenario').value].label }); };
$('#clock').oninput = e => { S.clock = +e.target.value; syncClock(); renderDeck(); };
$('#exag').addEventListener('input', e => e.target.setAttribute('aria-valuetext', T('{n} times exaggeration', { n: (+e.target.value).toFixed(1) })));
// The light on the relief (terrain and climate plan, step 4): the hillshade's light comes from a compass direction tied to the map, so it stays put as the view turns
const FROM = ['the north', 'the northeast', 'the east', 'the southeast', 'the south', 'the southwest', 'the west', 'the northwest'];
$('#sunDir').oninput = e => { const v = +e.target.value, w = T(FROM[Math.round(v / 45) % 8]); $('#sunDirVal').textContent = w; e.target.setAttribute('aria-valuetext', T('Light from {dir}', { dir: w })); if (map.getLayer('hillshade')) map.setPaintProperty('hillshade', 'hillshade-illumination-direction', v); };
$('#year').addEventListener('input', e => e.target.setAttribute('aria-valuetext', T('Year {year}', { year: e.target.value })));
$('#clock').addEventListener('input', e => e.target.setAttribute('aria-valuetext', $('#clockVal').textContent));
$('#speed').onchange = e => S.speed = +e.target.value;
$('#playTrips').onclick = () => { if (S.mode !== 'day') setMode('day'); togglePlay(); };
$('#playStorms').onclick = () => { if (S.mode !== 'storms') setMode('storms'); togglePlay(); };
$('#tbPlay').onclick = togglePlay;
$('#tbRange').oninput = e => { const v = +e.target.value; if (S.mode === 'day') { S.clock = v; syncClock(); renderDeck(); } else if (S.mode === 'year') { $('#year').value = v; $('#year').dispatchEvent(new Event('input')); } else { S.stormYear = v; syncStormYear(); renderDeck(); } };
['stormY0', 'stormY1'].forEach(id => $('#' + id).oninput = () => { let a = +$('#stormY0').value, b = +$('#stormY1').value; if (a > b) { if (id === 'stormY0') $('#stormY1').value = a; else $('#stormY0').value = b; } $('#stormYearVal').textContent = `${$('#stormY0').value} – ${$('#stormY1').value}`; if (S.mode === 'storms') { $('#tbRange').min = $('#stormY0').value; $('#tbRange').max = $('#stormY1').value; } S.stormYear = null; renderDeck(); });

// The address and the 2D link (js/core/viewstate.js, docs/view-state.md): the camera (c= with the zoom in the 2D map's units, b=, p=), the layers, the columns'
// measure once changed here, the route, the base map and the municipality whose card is open; what this view does not use stays as it came. replaceState,
// at most every 400 ms (a flight writes once it ends), never a new history entry. Nothing is written before the view has applied the address it opened on.
function writeState(now) {
  if (!VS.ready) return;
  clearTimeout(VS.timer);
  const wait = now ? 0 : Math.max(0, 400 - (Date.now() - VS.last));
  VS.timer = setTimeout(writeNow, wait);
}
/** The address now: what writeState writes (camera, layers, columns once changed here, route, base map, the card), at once. */
function writeNow() {
    clearTimeout(VS.timer); VS.last = Date.now();
    const V = Core.viewstate, c = map.getCenter(), el = (id) => document.getElementById(id), was = V.parse(location.hash);
    const mine = {
      muni: VS.muni, c: V.cOf(c.lat, c.lng, V.fromMapLibre(map.getZoom())), b: String(+map.getBearing().toFixed(1)), p: String(+map.getPitch().toFixed(1)),
      l: V.layerTokens('3d', id => !!(el(id) && el(id).checked), id => !!(el(id) && el(id).defaultChecked)),
      r: (typeof Plan !== 'undefined' && Plan.encode()) || null, bm: BM.chosen ? BM.name : null,
    };
    if (VS.measure) {   // the columns, once changed here: a measure of the 2D shading (s=), or the Economy datasets (e=, ey=), or nothing
      const any = $('#lyCols').checked && metricKey === '__any', one = $('#lyCols').checked && metricKey && metricKey !== '__any';
      mine.s = one ? metricKey : was.s && !V.has(METRIC, was.s) ? undefined : null;   // the measure the columns show; a 2D measure the columns do not have stays
      mine.e = any ? V.econOf(ENG.h, ENG.c, was.e, { h: ENG.ho.norm, c: ENG.co.norm }) : null;
      mine.ey = any && ENG.y != null ? String(ENG.y) : null;
    }
    const hash = V.write('3d', location.hash, mine);
    history.replaceState(null, '', location.pathname + location.search + hash);
    syncViewLinks();
}
// Undo of "Turn all off" (core/activelayers.js, a state part after the switches): the columns' s=, e= and ey= exactly as they were, tokens of the 2D map this
// view does not draw included (switching the columns back on would rebuild e= from what the view draws), and whether they had been changed here.
function measureSnap() {
  if (VS.ready) writeNow();
  const raw = Core.viewstate.parse(location.hash).raw, keep = (k) => ({ raw: k in raw ? raw[k] : '' });   // the text as it came, never decoded (a broken % or a %26 stays as it is)
  return { measure: VS.measure, s: keep('s'), e: keep('e'), ey: keep('ey') };
}
function measureRestore(m) {
  if (!m || !VS.ready) return;
  clearTimeout(VS.timer); VS.measure = m.measure;
  history.replaceState(null, '', location.pathname + location.search + Core.viewstate.write('3d', location.hash, { s: m.s, e: m.e, ey: m.ey }));   // { raw: '' } takes the key out
  writeNow();
}
/** What the address asked (IN), applied once the view is ready: the layers (layerPlan), the columns (e= first, then s=) and the municipality, whose card opens
 *  (the camera goes to it when the address has no c=). Then the view writes the address and its 2D link from what it shows. */
function applyState() {
  VS.applying = true;
  try {
    const plan = Core.viewstate.layerPlan('3d', IN.l, id => !!(document.getElementById(id) || {}).defaultChecked);
    for (const [id, on] of Object.entries(plan)) { const el = document.getElementById(id); if (el && el.checked !== on) { el.checked = on; el.dispatchEvent(new Event('change')); } }
    const cols = IN.e ? Core.viewstate.econColumns(IN.e) : null, one = !cols && Core.viewstate.has(METRIC, IN.s);   // own keys only: s=constructor is no measure
    if (cols) { Object.assign(ENG, { fromAddress: true, h: cols.h, c: cols.c, y: IN.ey, ho: cols.hNorm ? { norm: cols.hNorm } : {}, co: cols.cNorm ? { norm: cols.cNorm } : {} }); $('#metric').value = '__any'; }
    else if (one) $('#metric').value = IN.s;
    if (cols || one) { $('#lyCols').checked = true; $('#lyCols').dispatchEvent(new Event('change')); }
    const f = IN.muni && S.muniFc && S.muniFc.features.find(x => norm(x.properties.municipality) === norm(IN.muni));
    if (f) {
      const b = [[180, 90], [-180, -90]], walk = (a) => { if (typeof a[0] === 'number') { b[0][0] = Math.min(b[0][0], a[0]); b[0][1] = Math.min(b[0][1], a[1]); b[1][0] = Math.max(b[1][0], a[0]); b[1][1] = Math.max(b[1][1], a[1]); } else a.forEach(walk); };
      walk(f.geometry.coordinates);
      if (!IN.c) map.fitBounds(b, { padding: 60, duration: 0 });
      popup([(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2], muniCard(f.properties.municipality), f.properties.municipality);
    }
  } finally { VS.applying = false; VS.ready = true; }
  if (map.isMoving()) map.once('moveend', () => writeState(true));   // a flight begun before ready (the planned route's fit of an old r= link): the camera where it ends
  writeState(true);
}
function syncViewLinks() {
  const l2d = document.querySelector('.views a[href^="index.html"]');
  if (l2d) l2d.href = 'index.html' + location.search + Core.viewstate.write('3d', location.hash, {});   // the whole state and the page's ?lang=; ask= is never carried
  document.querySelectorAll('a[data-to2d]').forEach(a => { a.href = cardLink2d(a.dataset.to2d); });   // an open card's link follows the address
}
/** A municipality card's link to the 2D map: the address with that municipality selected and no c= (the 2D map flies to it). */
function cardLink2d(name) { return 'index.html' + location.search + Core.viewstate.write('3d', location.hash, { muni: name, c: null }); }
document.addEventListener('click', e => { const a = e.target.closest && e.target.closest('a[data-to2d]'); if (a) { if (VS.ready) writeNow(); a.href = cardLink2d(a.dataset.to2d); } }, true);   // the state of this moment
map.on('moveend', () => writeState());
document.addEventListener('change', e => { if (VS.ready && e.target.closest && e.target.closest('#panel')) writeState(); }, true);   // a layer, the columns, a menu; capture: the chip's x and "Turn all off" fire change events that do not bubble (core/activelayers.js)
setTimeout(() => { if (!$('#loader').classList.contains('hide') && !$('#loader').classList.contains('error')) $('#loaderText').textContent += ' ' + T('This is taking longer than usual.'); }, 20000);
// The base map, when its provider fails (docs/basemap.md, section 4):
//  - before start, an error with no source and no tile is the style, its sprite or its fonts. With the provider down, blocked or unreachable the browser reports only
//    "Failed to fetch", with no URL, so the text cannot name the provider: any such error switches to the plain style, and the view starts on it;
//  - no style after STYLE_TIMEOUT_MS: the plain style too. A style that has loaded, with its tiles still coming, starts the view then, with the base map;
//  - a base-map source that does not load, or a run of tile errors from one (no tile arriving in between), before or after start, hides the base map's layers: the data stay,
//    over the style's plain background, and the base map's credits leave the credit box with them.
const FALLBACK_STYLE = Core.basemap.FALLBACK_STYLE;   // a plain background (js/core/basemap.js)
const STYLE_TIMEOUT_MS = 30000, MAX_TILE_ERRORS = 8;   // the rules of the 2D maps (LOAD_TIMEOUT_MS and MAX_TILE_ERRORS in js/core/basemap.js)
let started = false, styleIn = false, baseSources = [];
const tileErrors = {};   // per base-map source: tile errors in a row
// The notice is the base map's own (core/basemap.js), not the message bar, which may hold an Undo. BM.off: the base map is unavailable (the credits say so);
// BM.why: what failed, for a reader of the console. A pick in the switcher tries again.
const baseNotice = () => Core.basemap.notice(map.getContainer(), T('The base map could not be loaded. Showing the data on a plain background.'));
function plainStyle(why) {   // before start: the plain style, then start
  if (started || BM.off) return;
  BM.off = true; BM.why = why; clearTimeout(styleTimer); baseSources = []; baseNotice(); setAttribution();
  map.setStyle(FALLBACK_STYLE, { diff: false }); map.once('idle', start);
}
const WATCH = 'bm-watch-';   // the invisible layer that keeps a source the clock rule found down loading (watchBase)
const hideBaseLayers = () => map.getStyle().layers.filter(l => baseSources.includes(l.source) && !l.id.startsWith(WATCH)).forEach(l => {   // the view's buildings too
  if (!(l.id in BM.hid)) BM.hid[l.id] = map.getLayoutProperty(l.id, 'visibility') || 'visible';
  map.setLayoutProperty(l.id, 'visibility', 'none');
});
// The credit of the base map sits on the provider's source (creditOn): blank while the base map is hidden, as a source still loading under a watch layer is
// still listed by the credit box; put back when it returns.
const baseCredit = (on) => { const s = creditOn && map.getSource(creditOn); if (s) s.attribution = on ? bmCredits() : ''; };
function hideBase(why, watch) {   // the base map's tiles keep failing: its layers go, ours stay; `watch`: the sources to keep watching (the tile rules)
  if (BM.off) return;
  BM.off = true; BM.why = why; clearTimeout(styleTimer); baseNotice(); hideBaseLayers(); baseCredit(false);
  if (watch && !BM.recovered) watchBase(watch);   // once per style: with only the fonts failing, the tiles arrive under the watch layer and fail again with the labels
  setAttribution(); if (started) osmiSync();
}
// After a tile rule (the clock or a run of eight, below), each source found down keeps loading under one invisible layer, so that a tile that arrives later (a
// slow provider, or one back after an outage, seen after a pan) brings the base map back (showBase). A hidden layer's source asks for nothing, and its tiles in
// flight are dropped, so without it nothing could arrive.
function watchBase(ids) {
  const st = map.getStyle();
  BM.watching = ids.filter(id => {
    const l = st.layers.find(x => x.source === id && !x.id.startsWith(WATCH));
    if (!l) return false;
    if (!map.getLayer(WATCH + id)) map.addLayer(l.type === 'raster' ? { id: WATCH + id, type: 'raster', source: id, paint: { 'raster-opacity': 0 } }
      : { id: WATCH + id, type: 'fill', source: id, 'source-layer': l['source-layer'], paint: { 'fill-opacity': 0 } });   // never clicked: the click dispatcher lists its layers
    return true;
  });
}
function showBase() {   // a watched source's tiles arrive: the base map, its buildings and credits come back, and the notice goes
  if (!BM.off || !BM.watching) return;
  BM.watching.forEach(id => map.getLayer(WATCH + id) && map.removeLayer(WATCH + id));
  Object.entries(BM.hid).forEach(([id, v]) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', v));
  showBuildings($('#lyBuildings').checked);   // as its switch says now
  Object.assign(BM, { off: false, why: null, hid: {}, watching: null, recovered: true });
  Object.keys(tileErrors).forEach(k => delete tileErrors[k]); baseClock.reset();
  baseCredit(true); Core.basemap.clearNotice(map.getContainer()); setAttribution(); if (started) osmiSync();
}
const styleTimer = setTimeout(() => { if (!started) { if (styleIn) start(); else plainStyle(['no style in 30 s']); } }, STYLE_TIMEOUT_MS);
map.once('style.load', () => { if (BM.off) return; styleIn = true; baseSources = Object.keys(map.getStyle().sources); });   // the provider's style, before the view adds its own sources
// Besides a run of eight, the 2D maps' idle rule, on a clock (review of PR #92): the 3D view is seldom idle (its sources keep asking for the failed tiles), and its
// default view needs only about 4 tiles before start, under the run. 6 s after a failed base-map tile, if two or more of a source's tiles failed since then, none
// arrived and none is still loading, the provider counts as down and the base map is hidden, before or after start (Core.basemap.tileWatch). Tiles still
// loading keep the window open: a slow provider is not a dead one (follow-up of the review: one tile failed, the others were held 7 s, and the base map went at
// 6 s and stayed off). Per source: Liberty's shaded relief can load while its vector tiles all fail. A source found down is still watched (watchBase): its
// tiles arriving later bring the base map back (showBase).
const baseClock = Core.basemap.tileWatch({
  loading: id => !!map.getSource(id) && !map.isSourceLoaded(id),   // isSourceLoaded fires an error event, not a throw, for a source that is gone
  down: ids => { if (!BM.busy) hideBase(['tiles', 'none arrived in 6 s', ids.join()], ids); },
});
map.on('error', e => {
  if (BM.off || BM.busy) return;   // during a switch the old style's errors do not count
  if (e && (e.sourceId || e.tile)) {   // a source of the base map that does not load (its TileJSON) hides it; tiles count in a run, or all failing for 6 s
    if (!baseSources.includes(e.sourceId)) return;
    if (!e.tile) { hideBase(['source', e.sourceId]); return; }
    baseClock.failed(e.sourceId);   // the clock's window opens with the first failed tile
    if ((tileErrors[e.sourceId] = (tileErrors[e.sourceId] || 0) + 1) >= MAX_TILE_ERRORS) hideBase(['tiles', 'a run of 8'], [e.sourceId]);
    return;
  }
  if (!started) plainStyle(['style, sprite or fonts']);   // before start
});
map.on('sourcedata', e => {   // a tile arrived: the provider answers
  if (!(e && e.tile && baseSources.includes(e.sourceId))) return;
  tileErrors[e.sourceId] = 0; baseClock.arrived(e.sourceId);
  if (BM.off && BM.watching && BM.watching.includes(e.sourceId)) showBase();
});
map.on('load', start);
let slrWarned = false;
map.on('error', e => { if (e && e.sourceId === 'slr' && !slrWarned) { slrWarned = true; toast(T('NOAA sea level tiles are not responding right now. Try again in a moment.'), 6000); } });
map.getCanvas().addEventListener('webglcontextlost', ev => { ev.preventDefault(); toast(T('The graphics were interrupted. Reload the page to bring back vehicles and storms.'), 10000); });
const once = (() => { const pending = {}; return (key, fn) => { if (!pending[key]) pending[key] = fn().catch(e => { delete pending[key]; throw e; }); return pending[key]; }; })();
function toast(msg, ms = 4000) { Core.activelayers.toast(msg, ms); }   // core/activelayers.js: the same message, which can also carry an Undo button
async function start() {
  if (started) return; started = true; clearTimeout(styleTimer);
  try {
    if (IN.c) map.jumpTo({ center: [IN.c.lng, IN.c.lat], zoom: Math.max(5, Core.viewstate.toMapLibre(IN.c.z)), ...(IN.b != null ? { bearing: IN.b } : {}), ...(IN.p != null ? { pitch: IN.p } : {}) });   // the zoom of the address is the 2D map's
    BM.base = baseOf(map.getStyle());
    setupScene(); if (BM.off) hideBaseLayers();   // the base map went before start: the buildings drawn from its tiles go too
    BM.ctl = Core.basemap.control($('#basemap'), { value: BM.name, onPick: switchBasemap }); osmiSync();
    [S.meta, S.muni, S.muniFc] = await Promise.all([loadJson('data/meta.json', T('Loading snapshot…')), loadJson('data/municipalities.json', T('Loading municipality statistics…')), loadJson('data/municipios.geojson', T('Loading boundaries…'))]);
    renderAbout(); renderCatChips(); addMunicipalities(); currentFeet();
    await once('routes', addRoutes).catch(() => toast(T('Transit routes could not be loaded.')));
    initPlanner();
    $('#loader').classList.add('hide'); performance.mark('ready');   // the ready moment, noted before the files asked for just after it in this same step (tests/browser/throttle.js)
    applyState();   // the layers, the columns and the municipality of the address
    if ($('#lyPlaces').checked) loadPlaces().catch(() => {});   // the tourism places (about 2.2 MB compressed) start switched off (an owner decision of 2026-10-15) and load when the layer is first switched on; a failure is shown beside the layer and in a message (docs/performance.md)
    // animated data loads after first paint, and deck.gl, which draws it
    deckLoad();
    loadJson('data/trips.json').then(t => { S.trips = t; syncClock(); renderDeck(); }).catch(() => { $('#vehCount').textContent = T('Vehicle replay could not load.'); });
    loadJson('data/hurricanes.json').then(h => { S.storms = h; syncStormYears(h); renderDeck(); }).catch(() => { $('#stormCount').textContent = T('(could not load)'); });
    S.playing = !reducedMotion && !isMobile(); setPlayIcons(); raf = requestAnimationFrame(tick);
  } catch (e) {
    $('#loader').classList.add('error');
    $('#loaderText').innerHTML = Th('The map data did not load ({error}). Check your connection, then <button type="button" class="btn" onclick="location.reload()">try again</button>.', { error: e.message });
  }
}

// The lesson of the Learn page that teaches a layer (js/learn_links.js, written by learn.py; decision 106): a layer's "?" shows the link under its
// text, as on the 2D map. The link map loads the first time a help button is pressed, never with the page.
{
  let llP = null;
  const learnLinks = () => llP || (llP = addJs('js/learn_links.js?v=5').then(() => window.LEARN_LINKS || null, () => { llP = null; return null; }));
  document.addEventListener('click', (e) => {
    const h = e.target.closest('[data-help]'), a = $('#helpLearn'); if (!h || !a) return;
    a.hidden = true;
    learnLinks().then((L) => {
      const l = L && L.layers[h.dataset.help]; if (!l || !$('#helpPop').classList.contains('show') || helpTrigger !== h) return;
      a.href = 'learn.html#lesson-' + l[0]; a.textContent = T('Lesson: {title}', { title: l[1][I18N.lang === 'es' ? 'es' : 'en'] || l[1].en }); a.hidden = false;
    });
  });
}
