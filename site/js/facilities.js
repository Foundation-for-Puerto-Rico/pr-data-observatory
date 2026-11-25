/* PR Data Observatory: public facilities on the 2D map (Leaflet). The layers, their pop-ups, notes and help texts are in core/facilities.js, shared with the 3D view
   (js/facilities3d.js). This script, the core file and their Spanish load the first time one of these layers or help buttons is used (app.js facLoad), and each
   file loads the first time its layer is switched on. The counts by municipio are datasets of the Economy tab (facility_series.json, community_series.json), not drawn here. */
const Facilities = (() => {
  const F = Core.facilities, st = { docs: {}, layers: {}, renderer: null };
  if (!map.getPane('facilities')) { map.createPane('facilities'); map.getPane('facilities').style.zIndex = 395; }   // above the routes, under the markers
  if (!map.getPane('facLines')) { map.createPane('facLines'); map.getPane('facLines').style.zIndex = 394; }   // line layers with line.under (the transmission lines), under the facility points
  const sw = (k) => $('#' + F.LAYERS[k].id);

  async function show(k) {
    const L0 = F.LAYERS[k];
    if (!st.layers[k]) {
      const d = st.docs[k] || (st.docs[k] = await getJson('data/' + L0.file, T(L0.label)));
      if (L0.hazards && k !== 'schools') { st.hz = st.hz || await getJson('data/' + F.HZ_FILE, T('Hazard areas of the facilities')).catch(() => null); F.attachHazards(k, d, st.hz); }   // each point's hazard flags, for its pop-up (facility_exposure.py)
      if (!st.layers[k]) {
        st.renderer = st.renderer || window.L.canvas({ pane: 'facilities' });
        st.lineRenderer = st.lineRenderer || window.L.canvas({ pane: 'facLines' });
        const low = L0.line && L0.line.under;
        st.layers[k] = window.L.geoJSON(d, { attribution: T(L0.attribution),
          style: (f) => f.geometry.type === 'Point' ? {} : L0.area ? { renderer: st.renderer, pane: 'facilities', color: '#ffffff', weight: .4, opacity: .8, fillColor: F.areaSpec(k).colors[F.areaClass(k, f.properties[F.areaSpec(k).prop])] || '#e0e0e0', fillOpacity: .72, bubblingMouseEvents: false }   // areas (L0.area: the FCC's broadband hexagons), filled by class
            : (ls => ({ renderer: low ? st.lineRenderer : st.renderer, pane: low ? 'facLines' : 'facilities', color: ls.color, weight: ls.weight, opacity: ls.opacity, dashArray: ls.dash ? ls.dash.join(' ') : null, bubblingMouseEvents: false }))(F.lineStyle(k, f.properties)),   // lines only (L0.line: FPR's traced routes, público routes, simulated connections); GeoJSON restyles every layer with it, the points too
          pointToLayer: (f, ll) => { if (!L0.sized) return window.L.circleMarker(ll, { renderer: st.renderer, pane: 'facilities', radius: 5, weight: 1.2, color: '#fff', fillColor: L0.color, fillOpacity: .95, bubblingMouseEvents: false });
            const z = F.sizedStyle(k, f.properties);   // power plants: area by MW, color by technology, a planned plant hollow and dashed (the file is sorted largest first, so small circles are drawn on top)
            return window.L.circleMarker(ll, { renderer: st.renderer, pane: 'facilities', radius: z.r, weight: z.planned ? 1.8 : 1, color: '#424242', dashArray: z.planned ? '4 3' : null, fillColor: z.color, fillOpacity: z.planned ? .25 : .85, bubblingMouseEvents: false }); },
          onEachFeature: (f, lyr) => lyr.bindPopup(() => F.popup(k, f.properties, d), { maxWidth: 300 }).bindTooltip(() => { const t = F.tip(k, f.properties); return esc(t != null ? t : f.properties.name || T(f.properties.type)); }, { direction: 'top', sticky: !!low }) });
      }
      F.noteEl(k, document).innerHTML = esc(F.noteText(k, d, T('Explore tab'))) + F.legendHtml(k, d);   // an area or sized layer's legend under its note
    }
    const on = sw(k).checked; if (on) st.layers[k].addTo(map);
    F.noteEl(k, document).hidden = !on;
    if (on && F.GAUGE[k]) F.live(k, st.docs[k]).then(() => { F.noteEl(k, document).textContent = F.noteText(k, st.docs[k], T('Explore tab')); });   // the latest USGS readings, each time the layer is switched on (at most every 10 minutes)
  }
  function hide(k) { if (st.layers[k]) map.removeLayer(st.layers[k]); const el = document.getElementById(`facNote-${k}`); if (el) el.hidden = true; }

  document.addEventListener('change', (e) => {   // an area layer's measure picker (the hexagon grid): restyle the drawn layer and its legend
    const k = e.target && e.target.dataset && e.target.dataset.facMeasure; if (!k || !F.LAYERS[k] || !F.LAYERS[k].area) return;
    F.LAYERS[k].area.pick = +e.target.value;
    if (st.layers[k]) st.layers[k].setStyle(st.layers[k].options.style);
    if (st.docs[k]) F.noteEl(k, document).innerHTML = esc(F.noteText(k, st.docs[k], T('Explore tab'))) + F.legendHtml(k, st.docs[k]);
  });
  F.addHelp(HELP);   // the help buttons of these layers (app.js loads this script on the first click)
  return { show, hide, LAYERS: F.LAYERS, TYPES: F.TYPES };
})();
