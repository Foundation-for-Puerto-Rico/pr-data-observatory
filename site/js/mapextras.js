/* PR Data Observatory: map extras that load after the map is ready, off its first load (like the base map; budget.py "deferred"). Map review 2026-11-05.
   - Town names above the shading: with a shaded layer on, the base map's own names sit under the colours and wash out. These sit in their own pane,
     above the shading and the symbols and below pop-ups: at zoom 9 the 20 most populous municipios (all 78 would collide), from zoom 10 every one.
   The Islands control was removed on 2026-11-12 (Francis: keep the map uncluttered; what matters is that the data covers every island).
   Uses app.js and econ_shell.js globals: map, S, esc, ecCentroid. */
const MapExtras = (() => {
  let names = null, big = new Set();

  function townNames() {
    if (!S.muniFc || typeof ecCentroid !== 'function') return;
    if (!map.getPane('townnames')) { const p = map.createPane('townnames'); p.style.zIndex = 640; p.style.pointerEvents = 'none'; }
    big = new Set(Object.values(S.muni).sort((a, b) => (b.population_2020 || 0) - (a.population_2020 || 0)).slice(0, 20).map(m => m.municipality));
    names = L.layerGroup(S.muniFc.features.map(f => {
      const c = ecCentroid(f.geometry), n = f.properties.municipality;
      return c && L.marker(c, { pane: 'townnames', interactive: false, keyboard: false, icon: L.divIcon({ className: 'town-name' + (big.has(n) ? ' town-big' : ''), html: `<span>${esc(n)}</span>`, iconSize: null }) });
    }).filter(Boolean));
    const show = () => {
      const on = document.body.classList.contains('econ-fill') && map.getZoom() >= 9;
      if (on !== map.hasLayer(names)) on ? names.addTo(map) : map.removeLayer(names);
      map.getContainer().classList.toggle('town-few', map.getZoom() < 10);
    };
    map.on('zoomend', show);
    new MutationObserver(show).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    show();
  }

  return { init() { townNames(); } };
})();
