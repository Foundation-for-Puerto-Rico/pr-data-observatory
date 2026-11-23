/* PR Data Observatory: Measure distance and area, and Draw an area, on the 2D map (Tools › Map tools, decision 97 step 2; docs/measure.md).
   js/maptools.js loads this file, core/measure.js and their Spanish (I18N.load('measure')) the first time either tool is used, so the map's first load does not carry them.
   A box at the top left of the map holds the tool: click the map to add points; double-click, or press Finish, to end; Esc or Clear starts again.
   - Distance: the length of the path, in metres or kilometres and in miles, along straight lines between the points (not along roads).
   - Area: the area the points outline, in km², hectares, cuerdas and acres, and its perimeter. A finished area can be added to Study areas (Draw an area), where it is
     measured like any study area: residents, transit and, on request, flood zones, heat and more.
   The clicks are caught on the map's box before any layer gets them (capture phase), as Study areas' "Pick a point" does, so a click does not also select a municipio.
   Nothing is sent anywhere; a drawn area is kept only if it is added to Study areas (this browser's storage). */
const Measure = (() => {
  const M = Core.measure, C = '#C2410C';   // a dark orange that reads on the light and the detailed base maps and is not a layer's colour
  const st = { mode: 'line', pts: [], done: false, hover: null, box: null, ctl: null, layer: null, raf: 0, dbl: false, msg: '' };

  const lenTxt = (km) => (km < 1 ? T('{v} m', { v: fmt(km * 1000, 0) }) : T('{v} km', { v: fmt(km, km < 10 ? 2 : 1) })) + ' (' + T('{v} mi', { v: fmt(km / 1.609344, km < 16 ? 2 : 1) }) + ')';
  const dec = (v) => v >= 100 ? 0 : v >= 10 ? 1 : 2;
  function areaTxt(km2) {
    const u = M.units(km2);
    return [km2 < 0.01 ? T('{v} m²', { v: fmt(u.m2, 0) }) : T('{v} km²', { v: fmt(km2, dec(km2)) }), T('{v} ha', { v: fmt(u.ha, dec(u.ha)) }), T('{v} cuerdas', { v: fmt(u.cuerdas, dec(u.cuerdas)) }), T('{v} acres', { v: fmt(u.acres, dec(u.acres)) })].join(' · ');
  }

  // ── drawing ──────────────────────────────────────────────────────────────
  function path() { const p = st.pts.map(l => [l.lng, l.lat]); if (!st.done && st.hover) p.push([st.hover.lng, st.hover.lat]); return p; }
  function draw() {
    st.raf = 0; if (!st.layer) return;
    st.layer.clearLayers();
    const p = path(), ll = p.map(q => [q[1], q[0]]);
    if (st.mode === 'area' && ll.length > 2) L.polygon(ll, { color: C, weight: 2, fillColor: C, fillOpacity: .12, interactive: false, dashArray: st.done ? null : '6 4' }).addTo(st.layer);
    else if (ll.length > 1) L.polyline(ll, { color: C, weight: 3, interactive: false, dashArray: st.done ? null : '6 4' }).addTo(st.layer);
    st.pts.forEach(l => L.circleMarker(l, { radius: 4, color: '#fff', weight: 2, fillColor: C, fillOpacity: 1, interactive: false }).addTo(st.layer));
  }
  const redraw = () => { if (!st.raf) st.raf = requestAnimationFrame(draw); if (st.box) read(); };   // the text at once, the drawing on the next frame
  function read() {
    const p = path(), out = st.box.querySelector('.ms-read'), add = st.box.querySelector('[data-ms-study]');
    let html = '';
    if (st.mode === 'line') html = p.length > 1 ? `<b>${esc(T('Distance'))}</b> ${esc(lenTxt(M.lineKm(p)))}` : esc(T('Click the map where the line starts.'));
    else if (p.length < 3) html = esc(p.length ? T('Add at least three points.') : T('Click the map where the area starts.'));
    else {
      const bad = M.crosses(p);
      html = `<b>${esc(T('Area'))}</b> ${esc(areaTxt(M.areaKm2(p)))}<br><b>${esc(T('Perimeter'))}</b> ${esc(lenTxt(M.perimeterKm(p)))}`
        + (bad ? `<div class="ms-warn">${esc(T('The edges cross, so this area is not meaningful. Undo points until they do not cross.'))}</div>` : '');
    }
    if (st.msg) html += `<div class="ms-msg">${esc(st.msg)}</div>`;
    out.innerHTML = html;
    add.hidden = !(st.mode === 'area' && st.done && st.pts.length > 2 && !M.crosses(path()));
    st.box.querySelector('[data-ms-finish]').disabled = st.done || st.pts.length < (st.mode === 'area' ? 3 : 2);
    st.box.querySelector('[data-ms-undo]').disabled = !st.pts.length;
    st.box.querySelector('.note').hidden = st.pts.length > 0;   // the instructions until the first point, then the room goes to the map (on a phone above all)
    st.box.querySelectorAll('[data-ms]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.ms === st.mode)));
  }

  // ── the map's clicks, caught before any layer (capture phase) ────────────
  const inCtl = (e) => e.target.closest && e.target.closest('.leaflet-control');
  function onClick(e) {
    if (inCtl(e) || (map.dragging && map.dragging.moved())) return;
    e.stopPropagation(); e.preventDefault();
    if (st.done) { st.pts = []; st.done = false; }
    st.msg = ''; st.pts.push(map.mouseEventToLatLng(e)); redraw();
  }
  function onDbl(e) {
    if (inCtl(e)) return; e.stopPropagation(); e.preventDefault();
    // a double-click also gave two clicks: drop the points it added at the same spot
    const at = map.mouseEventToContainerPoint(e);
    while (st.pts.length > 1 && map.latLngToContainerPoint(st.pts[st.pts.length - 1]).distanceTo(at) < 6 && map.latLngToContainerPoint(st.pts[st.pts.length - 2]).distanceTo(at) < 6) st.pts.pop();
    finish();
  }
  function onMove(e) { if (st.done || !st.pts.length) return; st.hover = map.mouseEventToLatLng(e); redraw(); }
  function onKey(e) { if (e.key === 'Escape') { e.stopPropagation(); if (st.pts.length) clear(); else close(); } }
  function listen(on) {
    const c = map.getContainer(), f = on ? 'addEventListener' : 'removeEventListener';
    c[f]('click', onClick, true); c[f]('dblclick', onDbl, true); c[f]('mousemove', onMove); document[f]('keydown', onKey, true);
    c.classList.toggle('sa-picking', on);
    if (on) { st.dbl = map.doubleClickZoom.enabled(); map.doubleClickZoom.disable(); } else if (st.dbl) map.doubleClickZoom.enable();
  }

  // ── actions ──────────────────────────────────────────────────────────────
  function finish() { if (st.pts.length < (st.mode === 'area' ? 3 : 2)) return read(); st.done = true; st.hover = null; redraw(); }
  function clear() { st.pts = []; st.done = false; st.hover = null; st.msg = ''; redraw(); }
  function undo() { if (st.done) st.done = false; st.pts.pop(); st.msg = ''; redraw(); }
  function setMode(m) { if (m === st.mode) return; st.mode = m; clear(); }
  async function toStudy() {
    const g = M.polygon(path()), km2 = M.areaKm2(path()), name = T('Drawn area of {v}', { v: km2 < 0.01 ? T('{v} m²', { v: fmt(km2 * 1e6, 0) }) : T('{v} km²', { v: fmt(km2, dec(km2)) }) });
    if (typeof ecBenchOpen !== 'function' && typeof econLoad === 'function') await econLoad().catch(() => null);   // the Analysis tab's scripts load on first use (js/econ_shell.js)
    if (typeof ecBenchOpen !== 'function' && typeof econLoad === 'function') { try { await econLoad(); } catch { /* econ_shell.js says what failed */ } }   // the Analysis tab's scripts load on first use (PR #104)
    if (typeof ecBenchOpen !== 'function') { st.msg = T('Study areas could not be opened. Check your connection and try again.'); return read(); }
    if (isMobile()) setPanel(false);
    ecBenchOpen('study');
    const ready = () => typeof StudyAreas !== 'undefined' && StudyAreas.addDrawn;   // a top-level const of js/studyareas.js, not a property of window
    for (let n = 0; n < 80 && !ready(); n++) await new Promise(r => setTimeout(r, 100));   // the view loads its module on first use
    if (!ready()) { st.msg = T('Study areas could not be opened. Check your connection and try again.'); return read(); }
    const msg = await StudyAreas.addDrawn(g, name); clear(); st.msg = msg; read();
  }

  function build() {
    const ctl = L.control({ position: 'topleft' });
    ctl.onAdd = () => {
      const d = L.DomUtil.create('div', 'ms-box leaflet-control');
      d.setAttribute('role', 'region'); d.setAttribute('aria-label', T('Measure distance and area'));
      d.innerHTML = `<div class="ms-head"><div class="ms-modes" role="group" aria-label="${esc(T('What to measure'))}"><button type="button" class="btn small" data-ms="line">${esc(T('Distance'))}</button><button type="button" class="btn small" data-ms="area">${esc(T('Area'))}</button></div>
        <button type="button" class="icon-btn" data-ms-close aria-label="${esc(T('Close the measuring tool'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div>
        <div class="ms-read" role="status" aria-live="polite"></div>
        <div class="note">${esc(T('Click the map to add points; double-click or press Finish to end. Lines are straight between the points, not along the roads. Esc starts again.'))}</div>
        <div class="btn-row"><button type="button" class="btn small" data-ms-undo>${esc(T('Undo the last point'))}</button><button type="button" class="btn small" data-ms-finish>${esc(T('Finish'))}</button><button type="button" class="btn small" data-ms-clear>${esc(T('Clear'))}</button>
        <button type="button" class="btn small primary" data-ms-study hidden><span class="ms-icon" aria-hidden="true">layers</span>${esc(T('Add as a study area'))}</button></div>`;
      L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
      d.addEventListener('click', (e) => {
        const b = e.target.closest('button'); if (!b) return;
        if (b.dataset.ms) setMode(b.dataset.ms); else if (b.hasAttribute('data-ms-undo')) undo(); else if (b.hasAttribute('data-ms-finish')) finish();
        else if (b.hasAttribute('data-ms-clear')) clear(); else if (b.hasAttribute('data-ms-study')) toStudy(); else if (b.hasAttribute('data-ms-close')) close();
      });
      return d;
    };
    ctl.addTo(map); st.ctl = ctl; st.box = ctl.getContainer();
    if (window.Core && Core.glossary && Core.glossary.mark) Core.glossary.mark(st.box);
  }
  function open(mode) {
    if (!st.ctl) { build(); st.layer = L.layerGroup().addTo(map); listen(true); }
    st.mode = mode === 'area' ? 'area' : 'line'; clear();
    st.box.querySelector(`[data-ms="${st.mode}"]`).focus();
  }
  function close() {
    if (!st.ctl) return;
    listen(false); st.ctl.remove(); st.ctl = null; st.box = null;
    if (st.layer) { st.layer.remove(); st.layer = null; }
    st.pts = []; st.done = false; st.hover = null; st.msg = '';
  }
  return { open, close, get state() { return { mode: st.mode, pts: st.pts.map(l => [l.lng, l.lat]), done: st.done }; } };
})();
