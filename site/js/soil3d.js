/* PR Data Observatory: the Soils and Landslide susceptibility layers of the 3D view, draped on the terrain by MapLibre. The tables, legends and pop-up are the
   2D map's (js/soil.js); twin3d.js loads that file, this one and their Spanish (I18N.load('soil')) the first time either layer or its help is used (soilLoad). */
Object.defineProperty(HELP, 'soil', { get: () => [T('Soils'), T('The soil survey of the USDA Natural Resources Conservation Service (NRCS, SSURGO): each area is a soil map unit, named after its main soil series, the texture of its surface and its slope. Choose what to show: the soil type and what it formed from, the slope, the chemistry of the top 30 cm (acidity, organic matter, salinity, lime), or three plain questions: signs of flooding, farming and building houses. Where the survey maps only urban land, the USGS geologic map says whether the ground below is river, swamp or beach deposits. Planning scale: it does not replace a study of the site, and the official flood zones are the FEMA ones.')], enumerable: true, configurable: true });   // translated when shown: the Spanish may arrive after this file
Object.defineProperty(HELP, 'slide', { get: () => [T('Landslide susceptibility'), T('The USGS map of how likely the ground is to slide when intense rain falls (Hughes and Schulz, 2020), made from the slope, the geology and the landslides of Hurricane María. It ranks the main island in five classes, from the most susceptible 1% to the least susceptible 40%. It shows where a landslide is more likely, not when or whether one will happen. Vieques and Culebra are not included.')], enumerable: true, configurable: true });   // translated when shown: the Spanish may arrive after this file
// The legend row of each soil map unit for the view chosen, as a MapLibre expression: what soilRow() in soil.js works out for one value, -1 for no value
function soilRowExpr(m) {
  const v = ['get', SOIL[m].field];
  const tests = SOIL[m].rows.flatMap((r, i) => [SOIL[m].ramp ? ['<=', v, r[0] === Infinity ? 1e9 : r[0]] : Array.isArray(r[0]) ? ['in', v, ['literal', r[0]]] : ['==', v, r[0]], i]);
  return ['case', ['==', v, null], -1, ...tests, -1];
}
// The colors and the rows unticked in the legend: a hidden row is filtered out, so a click there answers with the layers under it
soilRedraw = () => {
  if (!map.getLayer('soil-fill')) return;
  const m = soilMode(), row = soilRowExpr(m), hid = [...soilHidden].filter(k => k.startsWith(m) && /^-?\d+$/.test(k.slice(m.length))).map(k => +k.slice(m.length));
  map.setPaintProperty('soil-fill', 'fill-color', ['match', row, ...SOIL[m].rows.flatMap((r, i) => [i, r[1]]), SOIL_NONE]);
  map.setPaintProperty('soil-fill', 'fill-opacity', ['case', ['==', row, -1], .35, .75]);
  map.setFilter('soil-fill', hid.length ? ['!', ['in', row, ['literal', hid]]] : null);
};
async function addSoil() {
  if (map.getSource('soil')) return;
  S.soil = S.soil || await loadJson('data/soils.geojson', T('soil'));
  if (map.getSource('soil')) return;
  map.addSource('soil', { type: 'geojson', data: S.soil, attribution: T('Soils: USDA NRCS, SSURGO') });
  map.addLayer({ id: 'soil-fill', type: 'fill', source: 'soil', paint: { 'fill-outline-color': 'rgba(255,255,255,.6)' } }, areaBefore('soil-fill'));
  soilRedraw();
  clickable('soil-fill', 'area', f => soilPopup(f.properties, false));
}
function addSlide() {   // the published map's tiles, as on the 2D map: a picture of the five classes, which a click does not read
  if (map.getSource('slide')) return;
  map.addSource('slide', { type: 'raster', tiles: [SLIDE_TILES], tileSize: 256, maxzoom: 17, bounds: [-67.30, 17.86, -65.56, 18.54], attribution: T('Landslide susceptibility: USGS (Hughes and Schulz, 2020)') });
  map.addLayer({ id: 'slide-img', type: 'raster', source: 'slide', paint: { 'raster-opacity': .6, 'raster-fade-duration': 0 } }, areaBefore('slide-img'));
}
