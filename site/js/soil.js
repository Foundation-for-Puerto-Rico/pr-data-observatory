/* PR Data Observatory: the Soils (soils.py, data/soils.geojson) and Landslide susceptibility layers of the 2D map, and their tables, legends and pop-up for the
   3D view too (js/soil3d.js draws them there). app.js and twin3d.js load this file and its Spanish (I18N.load('soil')) the first time either is switched on
   (soilLoad), so neither page's first load carries them (docs/performance.md); their legends are drawn here for the same reason. */
// Soil (soils.py, NRCS SSURGO): the soil type (its order, in the categorical hues in fixed order, largest first) and its origin, then four plain questions
// about each soil map unit, flooding first. Flooding runs magenta to green so each answer reads apart, clear of the FEMA layer's blues and the landslide layer's reds and yellows; the other answers are ordered, so each is one earth-brown
// ramp, darker for more of what the question asks (better farmland, more limits, steeper). No blue: that is the FEMA flood layer's. A legend row can be unticked to hide it: with nine colours on a map, that and the pop-up name each one
if (map.createPane) {   // the 2D map (Leaflet); the 3D view keeps the same order in twin3d.js (AREAS)
  map.createPane('soil'); map.getPane('soil').style.zIndex = 356;
  map.createPane('slide'); map.getPane('slide').style.zIndex = 353;   // under the soil layer: with its "does not flood" row unticked, the flooding soils show over the landslide map
}
const SOIL_NONE = '#d9d7d2';
const SOIL = {
  order: { field: 'order', rows: [
    ['Inceptisols', '#2a78d6', 'Inceptisols', 'young, little developed'], ['Ultisols', '#eb6834', 'Ultisols', 'weathered, acid clay'], ['Mollisols', '#1baf7a', 'Mollisols', 'dark, fertile topsoil'],
    ['Entisols', '#eda100', 'Entisols', 'very young: alluvium, sand'], ['Oxisols', '#e87ba4', 'Oxisols', 'very weathered, red'], ['Vertisols', '#008300', 'Vertisols', 'clays that swell and crack'],
    ['Alfisols', '#6250d6', 'Alfisols', 'moderately weathered, fertile'], ['Aridisols', '#e34948', 'Aridisols', 'dry climate'], [['Histosols', 'Spodosols'], '#8a8780', 'Other orders', 'Histosols (organic) and Spodosols (sandy)']] },
  origin: { field: 'origin', rows: [
    ['alluvial', '#2a78d6', 'Alluvial', 'river and stream deposits'], ['residual', '#eb6834', 'Residual', 'formed in place from the rock below'], ['colluvial', '#1baf7a', 'Colluvial', 'material moved down slopes'],
    ['coastal', '#eda100', 'Coastal and marine', 'beach sand, marine, estuarine and lagoon deposits'], ['organic', '#e87ba4', 'Organic', 'peat and plant material'], ['fill', '#008300', 'Fill', 'material moved by people']] },
  farm: { field: 'farm', rows: [
    ['prime', '#5c3314', 'Prime farmland', 'the best land to farm'], ['prime_if', '#874d22', 'Prime if irrigated or drained', ''],
    ['state', '#d09a68', 'Farmland important to Puerto Rico', ''], ['not', '#f3e4d4', 'Not prime farmland', '']] },
  build: { field: 'build', rows: [
    ['not', '#f3e4d4', 'Few limits', ''], ['somewhat', '#d09a68', 'Some limits', 'can be solved with design'], ['very', '#5c3314', 'Severe limits', 'costly or hard to solve']] },
  flood: { field: 'flood', rows: [
    ['frequent', '#6e1a5e', 'Floods often', ''], ['sometimes', '#b8479f', 'Floods at times', ''], ['wet', '#e8a9d6', 'Does not flood, but stays wet', 'poor drainage'], ['no', '#a9d3a0', 'Does not flood', ''],
    ['geo_wet', '#7a4a1f', 'Urban area on river, swamp or beach deposits', 'can flood; from the geologic map'], ['geo_dry', '#e0cdb4', 'Urban area on rock or older terraces', 'no sign of flooding; from the geologic map']] },   // magenta to green, browns for the geologic map: no blue (the FEMA layer) and no red, orange or yellow (the landslide layer)
  ph: { field: 'ph', ramp: true, rows: [
    [5.5, '#8c2d04', 'Strongly acid', 'pH 5.5 or less'], [6.5, '#e6a25d', 'Acid', 'pH 5.6–6.5'], [7.3, '#ece9e2', 'Neutral', 'pH 6.6–7.3'], [8.4, '#5fb3a1', 'Alkaline', 'pH 7.4–8.4'], [Infinity, '#1d6b5f', 'Strongly alkaline', 'over pH 8.4']] },
  om: { field: 'om', ramp: true, rows: [
    [1, '#edf5e1', 'Very little organic matter', 'under 1%'], [2, '#b7dba0', 'Little organic matter', '1–2%'], [4, '#74b464', 'Some organic matter', '2–4%'], [8, '#3a8a3d', 'Much organic matter', '4–8%'], [Infinity, '#1b5e20', 'Organic soil', 'over 8%']] },
  ec: { field: 'ec', ramp: true, rows: [
    [2, '#f2ecf7', 'Not saline', 'under 2 dS/m'], [4, '#cdb7e3', 'Very slightly saline', '2–4 dS/m'], [8, '#9f7cc9', 'Slightly saline', '4–8 dS/m'], [16, '#6c48a8', 'Moderately saline', '8–16 dS/m'], [Infinity, '#3f2373', 'Strongly saline', 'over 16 dS/m']] },
  caco3: { field: 'caco3', ramp: true, rows: [
    [0.5, '#f4f1e8', 'No lime', 'under 0.5% calcium carbonate'], [5, '#d6c9a6', 'Little lime', '0.5–5%'], [15, '#a8936a', 'Moderate lime', '5–15%'], [Infinity, '#6b5a37', 'Very high lime', 'over 15%']] },
  slope: { field: 'slope', ramp: true, rows: [
    [2, '#f3e4d4', 'Flat', '0–2%'], [5, '#e6c3a0', 'Gentle', '2–5%'], [12, '#d09a68', 'Moderate slope', '5–12%'], [20, '#b0703d', 'Strong slope', '12–20%'], [40, '#874d22', 'Steep', '20–40%'], [Infinity, '#5c3314', 'Very steep', 'over 40%']] },
};
const SOIL_ORDER = { Inceptisols: 'young, little developed', Ultisols: 'weathered, acid clay', Mollisols: 'dark, fertile topsoil', Entisols: 'very young: alluvium, sand', Oxisols: 'very weathered, red', Vertisols: 'clays that swell and crack', Alfisols: 'moderately weathered, fertile', Aridisols: 'dry climate', Histosols: 'organic', Spodosols: 'sandy' };
const SOIL_GEO = { Qa: 'alluvium', Qs: 'swamp deposits', Qb: 'beach deposits' };
const SOIL_PM = ['Residuum', 'Alluvium', 'Colluvium', 'Marine deposits', 'Estuarine deposits', 'Organic material', 'Fluviomarine deposits', 'Lagoonal deposits', 'Beach sand', 'Human-transported material', 'Flow deposits', 'Slope alluvium', 'Herbaceous organic material', 'Volcanic rock', 'Igneous, metamorphic and sedimentary rock', 'Limestone', 'Volcanic and sedimentary rock', 'Basalt', 'Igneous rock', 'Serpentinite', 'Conglomerate', 'Granodiorite', 'Diorite', 'Chert', 'Granite', 'Mudstone', 'Shale and siltstone', 'Tuff', 'Volcanic sandstone', 'Calcareous sandstone', 'Acid shale', 'Quartzite', 'Limestone, sandstone, and shale', 'Sedimentary rock', 'Coral limestone', 'Andesite', 'Sandstone'];   // the parent materials and rocks SSURGO names, so the page's string layer has them to translate
const SOIL_COVER = { 'Urban land': 'Urban land, in the soil map', 'Rock outcrop': 'Rock outcrop', 'Rubble land': 'Loose rock', Riverwash: 'River sand and gravel' };   // the land over the soil described, in the words of the soil survey
const SOIL_ORIGIN = { alluvial: 'Alluvial', residual: 'Residual', colluvial: 'Colluvial', coastal: 'Coastal and marine', organic: 'Organic', fill: 'Fill' };
let soilLayer = null;
function soilOff() { if (soilLayer) map.removeLayer(soilLayer); }
let soilRedraw = () => { if (soilLayer) soilLayer.setStyle(soilStyle); };   // after the menu or a legend row changes; js/soil3d.js sets its own
const soilHidden = new Set();
const soilMode = () => $('#soilProp').value;
function soilRow(m, v) {   // the legend row a value falls in, or -1
  if (v == null) return -1;
  const rows = SOIL[m].rows;
  return SOIL[m].ramp ? rows.findIndex(r => v <= r[0]) : rows.findIndex(r => Array.isArray(r[0]) ? r[0].includes(v) : r[0] === v);
}
const soilStyle = f => {
  const m = soilMode(), i = soilRow(m, f.properties[SOIL[m].field]);
  if (soilHidden.has(m + i)) return { opacity: 0, fillOpacity: 0 };
  return { color: '#ffffff', weight: .3, opacity: .6, fillColor: i < 0 ? SOIL_NONE : SOIL[m].rows[i][1], fillOpacity: i < 0 ? .35 : .75 };
};
function soilLegend() {
  const m = soilMode(), row = (i, color, label, note) => `<label class="row lu-cls"><input type="checkbox" data-soil="${m}${i}"${soilHidden.has(m + i) ? '' : ' checked'}><span class="sw" style="background:${color}"></span>${esc(T(label))}${note ? ` <small>${esc(T(note))}</small>` : ''}</label>`;
  $('#soilRows').innerHTML = `<div class="legend-title">${esc(T('Classes on the map'))} <small>${esc(T('untick to hide'))}</small></div>` + SOIL[m].rows.map((r, i) => row(i, r[1], r[2], r[3])).join('') + row(-1, SOIL_NONE, 'Not rated', 'no NRCS value for this view (also urban land with no geologic data, water, rock)')
    + (m === 'flood' ? `<div class="note"><b>${esc(T('Complements the FEMA flood zones; the official zone is the FEMA one.'))}</b></div>` : '');   // two layers about flooding: this one says which is official
}
/** The pop-up sections of the soil under a click (app.js's click card), leaving out the classes unticked in the legend. */
const soilAt = ll => featuresAt(S.soil, ll, f => { const m = soilMode(); return !soilHidden.has(m + soilRow(m, f.properties[SOIL[m].field])); }, 1).map(f => soilPopup(f.properties, false));
function soilPopup(p, wrap = true) {
  const ans = (m, v) => { const i = soilRow(m, v); return i < 0 ? `<span class="muted">${esc(T('not rated'))}</span>` : `<b>${esc(T(SOIL[m].rows[i][2]))}</b>`; };
  const slope = p.slope == null ? `<span class="muted">${esc(T('not rated'))}</span>` : `<b>${fmt(p.slope, 0)}%</b>${p.slope_l != null && p.slope_h != null ? ` <small>(${fmt(p.slope_l, 0)}–${fmt(p.slope_h, 0)}%)</small>` : ''}`;
  const lab = (m, v) => { const i = soilRow(m, v); return i < 0 ? '' : T(SOIL[m].rows[i][2]); };
  const chem = p.order ? [p.ph != null ? `pH ${fmt(p.ph, 1)} (${lab('ph', p.ph).toLowerCase()})` : '', p.om != null ? T('organic matter {v}%', { v: fmt(p.om, 1) }) : '', p.ec != null ? lab('ec', p.ec).toLowerCase() : '', p.caco3 != null ? lab('caco3', p.caco3).toLowerCase() : ''].filter(Boolean).join(' · ') : '';
  const tech = p.order ? [T('main soil {comp}, {pct}% of the unit', { comp: p.comp, pct: p.share }), `${T(p.order)} (${T(SOIL_ORDER[p.order] || '')})`, p.origin && SOIL_ORIGIN[p.origin] ? T(SOIL_ORIGIN[p.origin]) + (p.pm ? ` (${T(p.pm)}${p.pm_rock ? ', ' + T(p.pm_rock) : ''})` : '') : ''].filter(Boolean).join(' · ') : '';
  const body = `<h4>${icon('landscape', { size: 20, color: '#874d22' })}${esc(I18N.lang === 'es' && p.name_es ? p.name_es : p.name)}</h4>`
    + (p.cover ? `<div class="meta">${esc(T('{cover} covers {pct}% of the unit; the soil described is the one under it', { cover: T(SOIL_COVER[p.cover] || p.cover), pct: p.cover_share }))}</div>` : '')
    + `<div class="meta">${esc(T('To farm'))}: ${ans('farm', p.farm)}</div>`
    + `<div class="meta">${esc(T('To build houses'))}: ${ans('build', p.build)}</div>`
    + `<div class="meta">${esc(T(p.flood && p.flood.startsWith('geo') ? 'Signs of flooding, by the ground under the urban area' : 'Signs of flooding, by the soil'))}: ${ans('flood', p.flood)}</div>`
    + (p.flood && p.flood.startsWith('geo') ? `<div class="meta"><small>${esc(T('The soil survey maps this as Urban land only; the USGS geologic map (1:100,000) shows what it stands on'))}${p.geo ? ': ' + esc(T(SOIL_GEO[p.geo])) : ''}</small></div>` : '')
    + `<div class="meta">${esc(T('Slope'))}: ${slope}</div>`
    + (chem ? `<div class="meta">${esc(T('Chemical, top 30 cm'))}: ${esc(chem)}</div>` : '')
    + (tech ? `<div class="meta"><small>${esc(T('Technical detail'))}: ${esc(tech)}</small></div>` : '')
    + `<div class="src">${esc(T('NRCS ratings at planning scale; they do not replace a study of the site. The official flood zones are the FEMA zones. USDA NRCS, SSURGO'))}</div>`;
  return wrap ? `<div class="pop">${body}</div>` : `<div class="id-sec">${body}</div>`;
}
const SOIL_MENU = [['Type and physical', [['order', 'Soil type'], ['origin', 'What it formed from'], ['slope', 'Slope']]],
  ['Chemical', [['ph', 'Acidity (pH)'], ['om', 'Organic matter'], ['ec', 'Salinity'], ['caco3', 'Lime (calcium carbonate)']]],
  ['What it means', [['flood', 'Does the soil show signs of flooding or standing water?'], ['farm', 'Is it good land to farm?'], ['build', 'How suited is it to build houses?']]]];
function soilMenu() {   // drawn when the layer is switched on, once its Spanish has arrived: soil.js and I18N.load('soil') load side by side
  $('#soilLegend').innerHTML = `<div class="ctrl"><label for="soilProp">${esc(T('Show'))}</label><select id="soilProp">`
    + SOIL_MENU.map(([g, opts]) => `<optgroup label="${esc(T(g))}">` + opts.map(([v, t]) => `<option value="${v}">${esc(T(t))}</option>`).join('') + '</optgroup>').join('')
    + `</select></div><div id="soilRows"></div><div class="note">${esc(T('Data from the Natural Resources Conservation Service (NRCS) of the USDA at planning scale, for each soil map unit; they do not replace a study of the site.'))}</div>`;
  $('#soilProp').onchange = () => { soilLegend(); soilRedraw(); };
  $('#soilRows').addEventListener('change', e => { const k = e.target.dataset.soil; if (!k) return; e.target.checked ? soilHidden.delete(k) : soilHidden.add(k); soilRedraw(); });
}
async function loadSoil() {
  if (!$('#soilProp')) soilMenu();
  if (!soilLayer) {
    S.soil = await getJson('data/soils.geojson', T('soil'));
    if (!soilLayer) soilLayer = L.geoJSON(S.soil, { interactive: false, pane: 'soil', attribution: T('Soils: USDA NRCS, SSURGO'), style: soilStyle });
  }
  soilLegend();
  if ($('#lySoil').checked) soilLayer.addTo(map);
}
// Landslide susceptibility (USGS, Hughes and Schulz 2020): the published map's own tiles, from the copy its first author keeps on ArcGIS Online (the source
// landslide.py reads for the barrio figures). A picture of the five classes: the click card does not read it
const SLIDE_ROWS = [['#005ce6', 'Extremely high susceptibility', 'the top 1% of the island'], ['#ff0000', 'Very high susceptibility', 'the next 9%'], ['#ffaa00', 'High susceptibility', 'the next 20%'],
  ['#ffff00', 'Moderate susceptibility', 'the next 30%'], ['#cccccc', 'Low susceptibility', 'the least susceptible 40%']];
const SLIDE_TILES = 'https://tiles.arcgis.com/tiles/TQ9qkk0dURXSP7LQ/arcgis/rest/services/Susceptibilidad_Derrumbe_PR/MapServer/tile/{z}/{y}/{x}';
let slideLayer = null;
function slideLegend() {
  if (!$('#slideLegend').innerHTML) $('#slideLegend').innerHTML = `<div class="legend-title">${esc(T('Susceptibility to landslides triggered by intense rain'))}</div>`
    + SLIDE_ROWS.map(([c, name, note]) => `<div class="row"><span class="sw" style="background:${c}"></span>${esc(T(name))} <small>${esc(T(note))}</small></div>`).join('')
    + `<div class="note">${esc(T('Hughes and Schulz (2020), main island only; a planning map, not a study of a site.'))}</div>`;
}
function slideOn() {
  slideLegend();
  slideLayer = slideLayer || L.tileLayer(SLIDE_TILES,
    { pane: 'slide', opacity: .6, maxNativeZoom: 17, maxZoom: 20, bounds: [[17.86, -67.30], [18.54, -65.56]], attribution: T('Landslide susceptibility: USGS (Hughes and Schulz, 2020)') });
  if ($('#lySlide').checked) slideLayer.addTo(map);
}
function slideOff() { if (slideLayer) map.removeLayer(slideLayer); }
