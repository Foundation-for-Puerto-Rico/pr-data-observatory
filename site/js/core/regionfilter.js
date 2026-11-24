/* PR Data Observatory core: the region filter of the Layers tab's Reference group, on the 2D map (index.html, Leaflet) and the 3D view (3d.html, MapLibre)
   (docs/regions.md, "The region filter"; HANDOFF decision 113).

   A region is a list of whole municipios, the same list as the map's Region tab and the regional profile (data/geo/regions.json, written by regions.py): the
   Eastern Region of FPR's Eastern Region Strategic Vision (ERSV) and the Puerto Rico Tourism Company's seven tourism regions. No region is defined here.

   Picking a region outlines its municipios, lays a light veil over the rest of the island and frames the map on the region. It does not cut the data layers:
   what is drawn outside the region stays on the map, faded, and every legend, count, ranking and download still covers all of Puerto Rico. (Cutting each layer
   to a region would change what its numbers mean in every panel; the Region tab and the regional profile already give a region's own figures.)

   The pick is kept in the address as rg=<id> (core/viewstate.js, docs/view-state.md), in both views and in their links to each other. app.js and twin3d.js load
   this file and the regions file on use: the first time the Reference group opens, or at ready when the address has rg=. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('regionfilter', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, esc } = dep('text');
  const ID_RE = /^[a-z0-9-]+$/;   // the ids of regions.py: "ersv" and the crosswalk's "reg-…" codes
  const LINE = '#1d2433', VEIL = '#ffffff', VEIL_OPACITY = 0.55;
  const KINDS = [['planning', 'FPR planning regions'], ['tourism', 'Tourism regions']];   // the optgroups, in this order (as in the Region tab)

  const codeOf = (f) => String((f.properties || {}).GEOID || '').slice(0, 5);   // a municipio's county code (municipios.geojson: GEOID)
  /** The region of `id` in `regions`, or null (own ids only: an address cannot name a prototype key). */
  const find = (regions, id) => (typeof id === 'string' && ID_RE.test(id) && (regions || []).find(r => r.id === id)) || null;
  /** A region's municipios and the others: { inside, outside } features of `features` (municipios.geojson), by county code. */
  function split(features, ids) {
    const want = new Set(ids || []), inside = [], outside = [];
    for (const f of features || []) (want.has(codeOf(f)) ? inside : outside).push(f);
    return { inside, outside };
  }
  /** The bounding box of features: [[west, south], [east, north]], or null when there is no coordinate. */
  function bbox(features) {
    let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    const walk = (a) => { if (typeof a[0] === 'number') { if (a[0] < w) w = a[0]; if (a[0] > e) e = a[0]; if (a[1] < s) s = a[1]; if (a[1] > n) n = a[1]; } else a.forEach(walk); };
    for (const f of features || []) if (f && f.geometry) walk(f.geometry.coordinates);
    return w <= e && s <= n ? [[w, s], [e, n]] : null;
  }
  const lang = () => (root.I18N && root.I18N.lang === 'es' ? 'es' : 'en');
  const nameOf = (r, l) => (r.name && (r.name[l] || r.name.en)) || r.id;
  /** The select's options: "All of Puerto Rico", then each kind's regions in an optgroup, each with its number of municipios. */
  function options(regions, l) {
    const opt = (r) => `<option value="${esc(r.id)}">${esc(nameOf(r, l))} (${(r.ids || []).length})</option>`;
    return `<option value="">${esc(T('All of Puerto Rico'))}</option>` + KINDS.map(([k, label]) => {
      const rs = (regions || []).filter(r => r.kind === k);
      return rs.length ? `<optgroup label="${esc(T(label))}">${rs.map(opt).join('')}</optgroup>` : '';
    }).join('');
  }

  /** The 2D map: the veil and the outlines in their own pane, above the data layers' panes and canvas and under the markers and pop-ups; never clickable, so
   *  every layer under it still answers a click. */
  function leaflet(map, L) {
    if (!map.getPane('regionfilter')) { const p = map.createPane('regionfilter'); p.style.zIndex = 410; p.style.pointerEvents = 'none'; }
    const renderer = L.svg({ pane: 'regionfilter' });
    let group = null;
    return {
      show(parts, fit) {
        if (group) map.removeLayer(group);
        const veil = L.geoJSON({ type: 'FeatureCollection', features: parts.outside }, { pane: 'regionfilter', renderer, interactive: false, style: { stroke: false, fillColor: VEIL, fillOpacity: VEIL_OPACITY } });
        const line = L.geoJSON({ type: 'FeatureCollection', features: parts.inside }, { pane: 'regionfilter', renderer, interactive: false, style: { color: LINE, weight: 2.5, opacity: 0.9, fill: false } });
        group = L.layerGroup([veil, line]).addTo(map);
        if (fit && parts.inside.length) map.fitBounds(line.getBounds().pad(0.08));
      },
      clear() { if (group) { map.removeLayer(group); group = null; } },
    };
  }

  /** The 3D view: one GeoJSON source and two layers (the veil, a flat fill draped on the terrain, and the outlines), under the base map's labels (o.before()).
   *  o.fit(bounds) frames the camera (twin3d.js fitTo). A base map switch carries them into the new style (twin3d.js carryStyle). */
  function maplibre(map, o) {
    const SRC = 'region-filter', VEIL_ID = 'region-veil', LINE_ID = 'region-line';
    const tag = (f, inside) => ({ type: 'Feature', geometry: f.geometry, properties: { in: inside ? 1 : 0 } });
    const vis = (v) => [VEIL_ID, LINE_ID].forEach(id => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', v));
    return {
      show(parts, fit) {
        const data = { type: 'FeatureCollection', features: [...parts.outside.map(f => tag(f, false)), ...parts.inside.map(f => tag(f, true))] };
        if (map.getSource(SRC)) map.getSource(SRC).setData(data);
        else map.addSource(SRC, { type: 'geojson', data });
        const before = o && o.before ? o.before() : undefined;
        if (!map.getLayer(VEIL_ID)) map.addLayer({ id: VEIL_ID, type: 'fill', source: SRC, filter: ['==', ['get', 'in'], 0], paint: { 'fill-color': VEIL, 'fill-opacity': VEIL_OPACITY } }, before);
        if (!map.getLayer(LINE_ID)) map.addLayer({ id: LINE_ID, type: 'line', source: SRC, filter: ['==', ['get', 'in'], 1], paint: { 'line-color': LINE, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.6, 12, 3], 'line-opacity': 0.9 } }, before);
        vis('visible');
        const b = fit ? bbox(parts.inside) : null;
        if (b && o && o.fit) o.fit(b);
      },
      clear() { vis('none'); },
    };
  }

  /** Wires the select: its options, its note (aria-describedby) and the drawing. o: { regions, features (municipios.geojson's), view (leaflet() or
   *  maplibre()), value (the address's rg=), fit (frame the map on the address's region: false when the address has its own camera), onPick(id|null) }.
   *  Returns { set(id) (a pasted address), value() }. */
  function control(sel, o) {
    if (!sel) return null;
    const doc = root.document, note = doc && doc.getElementById(sel.getAttribute('aria-describedby') || ''), first = note ? note.innerHTML : '';
    sel.innerHTML = options(o.regions, lang());
    const mark = () => { const G = root.Core && root.Core.glossary; if (note && G && G.mark) try { G.mark(note); } catch (e) { /* the glossary is optional */ } };
    function apply(id, fit) {
      const r = find(o.regions, id);
      sel.value = r ? r.id : '';
      if (!r) { o.view.clear(); if (note) note.innerHTML = first; return null; }
      const parts = split(o.features, r.ids);
      o.view.show(parts, fit);
      if (note) {
        note.innerHTML = esc(T('{name}: its {n} municipios are outlined and the rest of the island is faded. The data layers are not cut: their legends, counts and rankings still cover all of Puerto Rico.', { name: nameOf(r, lang()), n: parts.inside.length }))
          + ` <a href="profile.html?region=${encodeURIComponent(r.id)}">${esc(T('Regional profile'))}</a>`;
        mark();
      }
      return r.id;
    }
    sel.disabled = false;
    apply(o.value, o.fit !== false);
    sel.addEventListener('change', () => { const id = apply(sel.value, true); o.onPick(id); });
    return { set: (id) => apply(id, true), value: () => sel.value || null };
  }

  return { find, split, bbox, options, leaflet, maplibre, control, ID_RE };
});
