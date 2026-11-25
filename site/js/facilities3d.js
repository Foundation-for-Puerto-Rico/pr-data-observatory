/* PR Data Observatory: the public facility layers on the 3D view (MapLibre): public housing developments, fire and EMS stations, police stations, city halls,
   public libraries, historic places, reservoir levels, river flow, groundwater levels, rainfall and FPR's Eastern Region baseline (illegal dumping sites, and the municipal routes FPR traced, drawn as lines). The layers, their pop-ups, notes and help texts are core/facilities.js, shared with the 2D map, so both views draw the same
   points, say the same about what is counted and not drawn, and show the same pop-up (name, type, municipio, listing date, source; no contact fields).
   This script, the core file and their Spanish load the first time one of these layers or help buttons is used (twin3d.js facLoad); each file loads the first time
   its layer is switched on. The points go above the areas and under the base map's labels (twin3d.js slotBefore); an area layer (the FCC's broadband
   hexagons, `area` in core/facilities.js) is filled by class under the 3D buildings, with its legend under the layer's note. A sized layer (EIA's power plants,
   `sized`) draws each circle with the radius and color core/facilities.js gives it, largest underneath; a planned plant is hollow (MapLibre has no dashed circles). */
const Facilities3D = (() => {
  const F = Core.facilities, docs = {};
  const sw = (k) => $('#' + F.LAYERS[k].id);
  let hz = null;   // facility_hazards.json, loaded with the first tested layer
  const stepOf = (k) => { const a = F.areaSpec(k); return ['step', ['to-number', ['get', a.prop], -1], '#e0e0e0', 0, a.colors[0], ...a.breaks.flatMap((b, i) => [b, a.colors[i + 1]])]; };
  document.addEventListener('change', (e) => {   // an area layer's measure picker (the hexagon grid): new fill colors and legend
    const k = e.target && e.target.dataset && e.target.dataset.facMeasure; if (!k || !F.LAYERS[k] || !F.LAYERS[k].area) return;
    F.LAYERS[k].area.pick = +e.target.value;
    if (map.getLayer('fac-' + k)) map.setPaintProperty('fac-' + k, 'fill-color', stepOf(k));
    if (docs[k]) F.noteEl(k, document).innerHTML = esc(F.noteText(k, docs[k], T('Columns by municipality → Any dataset'))) + F.legendHtml(k, docs[k]);
  });
  async function show(k) {
    const L0 = F.LAYERS[k], id = 'fac-' + k;
    const d = docs[k] || (docs[k] = await Data.json('data/' + L0.file));
    if (L0.hazards && k !== 'schools') { hz = hz || await Data.json('data/' + F.HZ_FILE).catch(() => null); F.attachHazards(k, d, hz); }   // each point's hazard flags, before the source is made, so a click carries them
    if (!map.getSource(id)) {
      if (L0.sized) for (const f of d.features) { const z = F.sizedStyle(k, f.properties); Object.assign(f.properties, { _r: z.r, _c: z.color, _p: z.planned ? 1 : 0 }); }   // drawing values, added once to the loaded copy
      map.addSource(id, { type: 'geojson', data: d, attribution: T(L0.attribution) });
      if (L0.area) {   // the FCC's broadband hexagons: filled by class under the 3D buildings, with a thin outline
        const step = stepOf(k);
        map.addLayer({ id, type: 'fill', source: id, paint: { 'fill-color': step, 'fill-opacity': .72, 'fill-outline-color': 'rgba(255,255,255,.6)' } }, map.getLayer('buildings-3d') ? 'buildings-3d' : slotBefore('fac-'));
      } else if (L0.sized) map.addLayer({ id, type: 'circle', source: id, layout: { 'circle-sort-key': ['-', 0, ['get', '_r']] }, paint: { 'circle-color': ['get', '_c'], 'circle-radius': ['get', '_r'],
        'circle-opacity': ['case', ['==', ['get', '_p'], 1], .25, .85], 'circle-stroke-color': ['case', ['==', ['get', '_p'], 1], ['get', '_c'], '#424242'], 'circle-stroke-width': ['case', ['==', ['get', '_p'], 1], 2, 1] } }, slotBefore('fac-'));
      else if (L0.line) {   // FPR's traced routes; the público routes; the simulated connections, colored by class, wider where more workers travel, dashed
        const l = L0.line === true ? {} : L0.line, w = l.width;
        const color = l.colors ? ['match', ['to-string', ['get', l.prop]], ...Object.entries(l.colors).flat(), L0.color] : L0.color;
        const byClass = l.widths && ['match', ['to-string', ['get', l.prop]], ...Object.entries(l.widths).flat(), 1.5];   // the transmission lines: a width for each voltage
        const width = w ? ['+', w.lo, ['*', w.hi - w.lo, ['sqrt', ['min', 1, ['/', ['max', 0, ['to-number', ['get', w.prop], 0]], w.max]]]]] : byClass ? ['interpolate', ['linear'], ['zoom'], 8, ['*', .7, byClass], 14, ['*', 1.6, byClass]] : l.weight ? ['interpolate', ['linear'], ['zoom'], 8, l.weight * .6, 14, l.weight * 1.5] : ['interpolate', ['linear'], ['zoom'], 8, 2, 14, 5];
        map.addLayer({ id, type: 'line', source: id, layout: { 'line-cap': l.dash ? 'butt' : 'round', 'line-join': 'round' }, paint: { 'line-color': color, 'line-width': width, 'line-opacity': l.opacity || .9, ...(l.dash ? { 'line-dasharray': [2, 1.6] } : {}) } }, l.under && map.getLayer(l.under) ? l.under : slotBefore('fac-'));   // line.under: drawn under that layer (cables are not dashed here: MapLibre's dash cannot vary by feature)
      }
      else map.addLayer({ id, type: 'circle', source: id, paint: { 'circle-color': L0.color, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 3.5, 12, 5, 16, 7.5], 'circle-opacity': .95, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.2 } }, slotBefore('fac-'));
      clickable(id, L0.area ? 'area' : L0.line ? 'line' : 'point', f => F.popup(k, f.properties, d));   // twin3d.js's click dispatcher shows it when the point is on top
      hoverCursor(id);
      F.noteEl(k, document).innerHTML = esc(F.noteText(k, d, T('Columns by municipality → Any dataset'))) + F.legendHtml(k, d);   // where this view shows the counts by municipio; an area layer's legend
    }
    const on = sw(k).checked;
    map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
    F.noteEl(k, document).hidden = !on;
    if (on && F.GAUGE[k]) F.live(k, d).then(() => { F.noteEl(k, document).textContent = F.noteText(k, d, T('Columns by municipality → Any dataset')); });   // the latest USGS readings, as on the 2D map
  }
  function hide(k) { if (map.getLayer('fac-' + k)) map.setLayoutProperty('fac-' + k, 'visibility', 'none'); const el = document.getElementById('facNote-' + k); if (el) el.hidden = true; }
  F.addHelp(HELP);   // the help buttons of these layers (twin3d.js loads this script on the first click of one)
  return { show, hide };
})();
