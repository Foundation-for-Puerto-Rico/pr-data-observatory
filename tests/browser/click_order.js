// One click opens what is drawn on top, whichever layer was switched on first (twin3d.js, the click dispatcher; docs/layers.md, "Clicks"). Real mouse clicks on
// the 3D view, in two pages per language and width that switch the same layers on in opposite orders:
//  - a cluster of stops drawn over a circle of "Residents far from service" zooms in and opens no card (gaps on before or after the stops);
//  - flood zones, land use, Comunidades Especiales and barrios that overlap open ONE card with a section for each, as on the 2D map: the sections are the 2D map's
//    (access.js), the visible areas top first in a fixed drawing order, then the barrio, then a link to the municipality's card; the card at the same place is the
//    same in both pages, and the areas are stacked in the same order;
//  - a point drawn over areas opens its own card; land with nothing on it opens the municipality's card; the sea opens nothing;
//  - a card opens at its top (the first area's heading in view) with the focus on its close button, and stays inside the map (390 px too); with the columns on
//    and the camera tilted, the area card's link names the municipality of the ground; the places' heat map is under the route lines, their points over the
//    stops, and the stations under the WCRP pins whichever was switched on first;
//  - the route planner choosing a point: the click places it and opens no card, and does not zoom into a cluster;
//  - deck.gl first: a stop of "Service at this hour" over a cluster (no zoom) and over the same stop of the Stops layer, a route of the hour over a route line;
//    a storm track shows what pointing at it shows;
//  - the layers with no card (a vehicle, the line of a route profile) open no area card under them, and a stop under a vehicle still answers.
// The console stays clean and no Spanish is missing.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run --use-angle=d3d11 --enable-gpu   (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/click_order.js [base URL, default http://127.0.0.1:8041] [langs, default es,en] [widths, default 1400,390]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(','), widths = (process.argv[4] || '1400,390').split(',').map(Number);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
const view = (w) => ({ width: w, height: w < 500 ? 812 : 900, mobile: w < 500 });
const click = async (p, x, y) => { for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); };
const short = (s, n = 90) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
const seen = {};   // the card at the same place in the page of each order, to compare

// In the page: where things are drawn on the screen, and what the card shows. The kinds come from the view's own registry (CLICKABLE).
// With the terrain on (the default), each queryRenderedFeatures reads the terrain's coordinates back from the GPU: one 1-pixel read per point of the query and per
// source (MapLibre's Terrain.pointCoordinate), about 5 ms each on the test machine. A scan of the screen for a spot made thousands of them and could pass the 30 s
// limit of an eval (CDP then answered "Internal error"). While a helper runs, synchronously, no frame is drawn, so frame() serves those reads from ONE read of the
// whole coordinates buffer: the same bytes MapLibre would read, so the same features; the page's own clicks are not touched. Hidden layers are left out of the
// queries too (they give no feature, but each costs its source's reads), as the page's click handler does.
const HELPERS = `window.__k = (() => {
  const R = () => map.getContainer().getBoundingClientRect();
  const kind = (id) => (CLICKABLE.get(id) || {}).kind;
  const ids = () => [...CLICKABLE.keys()].filter(id => map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none');
  function frame(fn) {
    const tr = map.terrain; if (!tr) return fn();
    const own = Object.prototype.hasOwnProperty.call(tr, 'pointCoordinate'), orig = tr.pointCoordinate, gl = tr.painter.context.gl, read = gl.readPixels;
    let buf = null, W = 0;
    tr.pointCoordinate = function (p) {
      gl.readPixels = function (x, y, w, h, f, t, out) {   // only inside pointCoordinate: its 1-pixel read of the coordinates framebuffer it has just bound
        if (w !== 1 || h !== 1 || !(out instanceof Uint8Array)) return read.apply(gl, arguments);
        if (!buf) { W = Math.round(tr.painter.width / devicePixelRatio); const H = Math.round(tr.painter.height / devicePixelRatio); buf = new Uint8Array(W * H * 4); read.call(gl, 0, 0, W, H, f, t, buf); }
        const i = (y * W + x) * 4; out.set(buf.subarray(i, i + 4));
      };
      try { return orig.call(this, p); } finally { gl.readPixels = read; }
    };
    try { return fn(); } finally { if (own) tr.pointCoordinate = orig; else delete tr.pointCoordinate; }
  }
  const at = (q, b) => { const l = ids(); return l.length ? map.queryRenderedFeatures(b ? [[q.x - b, q.y - b], [q.x + b, q.y + b]] : [q.x, q.y], { layers: l }) : []; };
  const onCanvas = (q) => { const r = R(); if (q.x < 40 || q.y < 130 || q.x > r.width - 90 || q.y > r.height - 170) return false; const el = document.elementFromPoint(q.x + r.left, q.y + r.top); return !!el && el.classList.contains('maplibregl-canvas'); };
  const page = (q) => ({ x: Math.round(q.x + R().left), y: Math.round(q.y + R().top) });
  const local = (x, y) => ({ x: x - R().left, y: y - R().top });
  const deckHit = (q, l) => { try { const i = overlay.pickObject({ x: q.x, y: q.y, radius: 0, layerIds: l }); return i && i.object ? i : null; } catch (e) { return null; } };
  const anyDeck = (q) => deckHit(q, deckCards());
  const small = (q, b, allow) => at(q, b).filter(f => kind(f.layer.id) !== 'area' && kind(f.layer.id) !== 'base' && !(allow && allow.test(f.layer.id)));
  const text = (html) => { const d = document.createElement('div'); d.innerHTML = html; return d.textContent.replace(/\\s+/g, ' ').trim(); };
  // the 2D map's card for the areas under a pixel (access.js), the areas top first in the fixed order, the barrio last
  const ORDER = ['ce-fill', 'flood-fill', 'prot-fill', 'landuse-fill', 'barrios-hit'], MAX = { 'flood-fill': 2, 'prot-fill': 2 };
  const BUILD = { 'ce-fill': p => comunidadPopup(p, false), 'flood-fill': p => floodPopup(p, false), 'prot-fill': p => protPopup(p, false), 'landuse-fill': p => landusePopup(p, false), 'barrios-hit': p => barrioPopup(p, false) };
  function expectAreas(q) {
    const fs = at(q), secs = [];
    for (const id of ORDER) { const keys = []; for (const f of fs) { if (f.layer.id !== id) continue; const k = JSON.stringify(f.properties); if (!keys.includes(k) && keys.length < (MAX[id] || 1)) keys.push(k); } keys.forEach(k => secs.push(BUILD[id](JSON.parse(k)))); }
    const m = fs.find(f => kind(f.layer.id) === 'base');
    return text(areasPopup(secs, m && m.properties.municipality));
  }
  const api = {
    // a pixel inside every layer of 'need' (and only areas under it), with no point, line or cluster within 'box' px and no deck.gl object with a card
    areaSpot(need, o = {}) {
      const r = R(), box = o.box ?? 10, step = o.step || 19;
      for (let y = 150; y < r.height - 180; y += step) for (let x = 50; x < r.width - 100; x += step) {
        const q = { x, y }; if (!onCanvas(q)) continue;
        const fs = at(q), l = fs.map(f => f.layer.id); if (!need.every(n => l.includes(n))) continue;
        if (o.only && l.some(id => kind(id) === 'area' && !o.only.includes(id))) continue;
        if (small(q, box).length || anyDeck(q)) continue;
        return { ...page(q), ll: map.unproject([x, y]).toArray(), at: [...new Set(l)], expect: expectAreas(q) };
      }
      return null;
    },
    // a point feature of 'layers' whose pixel has, as its top clickable feature, one of 'layers'; o.need: other layers also under it (o.needRe: one matching this); o.allow: other small layers allowed near it;
    // o.scan: look for that pixel up to this many px from the point's center (a route line under a stop's circle, not always through its center)
    point(layers, o = {}) {
      const fs = map.queryRenderedFeatures({ layers: layers.filter(id => map.getLayer(id)) }), done = new Set(), allow = o.allow ? new RegExp(o.allow) : null;
      for (const f of fs) {
        if (f.geometry.type !== 'Point') continue; const c = f.geometry.coordinates, key = c.join(); if (done.has(key)) continue; done.add(key);
        const q0 = map.project(c), d = o.scan || 0, offs = []; let q = null, here = null, top = null;
        if (!onCanvas(q0) || (d && o.needRe && !at(q0, d).some(g => new RegExp(o.needRe).test(g.layer.id)))) continue;   // one box query before the pixels (a scan of every stop is slow)
        for (let dy = -d; dy <= d; dy++) for (let dx = -d; dx <= d; dx++) offs.push([dx, dy]);
        offs.sort((a, b) => Math.hypot(...a) - Math.hypot(...b));   // the center first
        for (const [dx, dy] of offs) {
          if (q) break; const t = { x: q0.x + dx, y: q0.y + dy }; if (!onCanvas(t)) continue;
          const h = at(t), tp = h.find(g => kind(g.layer.id) !== 'base'); if (!tp || !layers.includes(tp.layer.id)) continue;
          if ((o.need || []).some(n => !h.some(g => g.layer.id === n))) continue;
          if (o.needRe && !h.some(g => new RegExp(o.needRe).test(g.layer.id))) continue;
          q = t; here = h; top = tp;
        }
        if (!q) continue;
        if (small(q, o.box ?? 6).some(g => !layers.includes(g.layer.id) && !(allow && allow.test(g.layer.id)) && !(o.need || []).includes(g.layer.id))) continue;
        if (!o.deck && anyDeck(q)) continue;
        return { ...page(q), layer: top.layer.id, props: top.properties, at: [...new Set(here.map(g => g.layer.id))] };
      }
      return null;
    },
    // a deck.gl object of layer 'id' (positions: a datum's [lng, lat], or a path for lines) that is what the card layers pick at its pixel; o.top: the top MapLibre kind wanted under it
    deck(id, pos, o = {}) {
      const L = (overlay._props.layers || []).find(l => l && l.id === id); if (!L) return null;
      const P = new Function('d', 'return ' + pos);
      for (const d of L.props.data) {
        const v = P(d), cands = Array.isArray(v[0]) ? v.slice(1).map((b, i) => [(v[i][0] + b[0]) / 2, (v[i][1] + b[1]) / 2]) : [v];
        for (const c of cands) {
          const q = map.project(c); if (!onCanvas(q)) continue;
          const hit = anyDeck(q); if (!hit || hit.layer.id !== id) continue;
          const here = at(q), top = here.find(g => kind(g.layer.id) !== 'base');
          if (o.top && !(top && new RegExp(o.top).test(top.layer.id))) continue;
          if (o.bare && (top && kind(top.layer.id) !== 'area' || small(q, 8).length)) continue;
          if (o.land && !here.some(g => kind(g.layer.id) === 'base')) continue;
          return { ...page(q), top: top && top.layer.id, expect: text(deckCard(hit)[1]) };
        }
      }
      return null;
    },
    // a pixel where a layer with no card ('trips', 'rp-line') is drawn over land, with no point, line, cluster or deck.gl card near it; o.under: a point layer wanted under it.
    // The candidates: the points of o.under, or a minute behind the head of each vehicle in service, or the middle of each segment of the profile's line.
    async noCard(id, o = {}) {
      const cands = [];
      if (o.under) map.queryRenderedFeatures({ layers: [o.under] }).forEach(f => cands.push({ c: f.geometry.coordinates, props: f.properties }));
      else if (id === 'trips') for (const d of S.trips.trips) {
        if (tripStart(d) > S.clock - 120 || tripEnd(d) < S.clock) continue;
        const pts = tripPoints(S.trips, d), t = S.clock - 60, i = pts.findIndex(q => q[2] >= t); if (i < 1) continue;
        const a = pts[i - 1], b = pts[i], u = b[2] > a[2] ? (t - a[2]) / (b[2] - a[2]) : 0; cands.push({ c: [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u] });
      }
      else { const Lr = (overlay._props.layers || []).find(l => l && l.id === id); for (const path of (Lr ? Lr.props.data : [])) for (let i = 1; i < path.length; i++) cands.push({ c: [(path[i - 1][0] + path[i][0]) / 2, (path[i - 1][1] + path[i][1]) / 2] }); }
      S.pickNoCard = true; renderDeck(); await nextFrame();
      try {
        return frame(() => {   // after the frame deck.gl needed: from here on, synchronous
          for (const k of cands) {
            const q = map.project(k.c); if (!onCanvas(q) || anyDeck(q)) continue;
            const here = at(q), top = here.find(g => kind(g.layer.id) !== 'base');
            if (o.under ? !top || top.layer.id !== o.under : small(q, 8).length || !here.some(g => kind(g.layer.id) === 'base')) continue;
            const h = deckHit(q, DECK_NO_CARD); if (!h || h.layer.id !== id) continue;
            return { ...page(q), props: k.props, n: cands.length };
          }
          return null;
        });
      } finally { S.pickNoCard = false; renderDeck(); await nextFrame(); }
    },
    empty() { const r = R(); for (let y = 150; y < r.height - 180; y += 31) for (let x = 50; x < r.width - 100; x += 31) { const q = { x, y }; if (onCanvas(q) && !at(q, 12).length && !anyDeck(q)) return page(q); } return null; },
    project(ll) { return page(map.project(ll)); },
    card() {   // the card's text without the close button, read as text() reads an expected card (an icon's name runs into the words after it: "floodFlood zone AE")
      const all = document.querySelectorAll('.maplibregl-popup'), c = document.querySelector('.maplibregl-popup-content'), b = c && (c.querySelector('.pop') || c), clean = (t) => t.replace(/\\s+/g, ' ').trim();
      const br = b && b.getBoundingClientRect(), fv = b && [...b.querySelectorAll('h4')].find(h => { const r = h.getBoundingClientRect(); return r.top >= br.top - 2 && r.bottom <= br.bottom + 2; });   // the first heading in view
      const m = R(), cr = c && c.getBoundingClientRect(), a = document.activeElement;
      return { n: all.length, text: b ? clean(b.textContent) : '', html: c ? c.innerHTML : '', secs: c ? [...c.querySelectorAll('.id-sec h4')].map(h => clean(h.textContent)) : [], z: map.getZoom(),
        top: b ? Math.round(b.scrollTop) : 0, firstVisible: fv ? clean(fv.textContent) : '', focusClose: !!(a && a.classList.contains('maplibregl-popup-close-button')), inside: !cr || (cr.left >= m.left + 7 && cr.right <= m.right - 7) }; },
    close() { document.querySelectorAll('.maplibregl-popup').forEach(e => e.remove()); return 1; },
    stack() { return map.getStyle().layers.map(l => l.id).filter(id => AREAS.includes(id)); },
    order(ids) { const all = map.getStyle().layers.map(l => l.id); return ids.map(id => all.indexOf(id)); },
    // a pixel in a flood zone where a column of one municipality is drawn over the ground of another (columns on, camera tilted)
    colSpot() { const r = R(); for (let y = 150; y < r.height - 180; y += 13) for (let x = 50; x < r.width - 100; x += 13) { const q = { x, y }; if (!onCanvas(q)) continue; const fs = at(q), col = fs.find(f => f.layer.id === 'muni-cols'), hit = fs.find(f => f.layer.id === 'muni-hit');
      if (!col || !hit || col.properties.municipality === hit.properties.municipality || !fs.some(f => f.layer.id === 'flood-fill') || small(q, 6).length || anyDeck(q)) continue;
      return { ...page(q), col: col.properties.municipality, ground: hit.properties.municipality, link: T('Open the {name} profile', { name: hit.properties.municipality }) }; } return null; },
    transportText(i) { return text(transportPopup(S.transport[i])); },
    muniText(name) { return text(muniCard(name)); },
  };
  for (const k of ['areaSpot', 'point', 'deck', 'empty', 'colSpot']) { const f = api[k]; api[k] = (...a) => frame(() => f.apply(api, a)); }   // the scans
  return api;
})(), 1`;

async function settle(p, ms = 700) { await p.waitFor('map.loaded() && !map.isMoving()', 30000); await sleep(ms); }
async function jump(p, lng, lat, zoom, pitch = 0, bearing = 0) { await p.eval(`map.jumpTo({ center: [${lng}, ${lat}], zoom: ${zoom}, pitch: ${pitch}, bearing: ${bearing} }), 0`); await settle(p); }
async function setLy(p, id, on) { await p.eval(`(() => { const e = document.getElementById('${id}'); if (e.checked !== ${on}) e.click(); return 1; })()`); }
async function shown(p, id, on = true) { return p.waitFor(on ? `!!map.getLayer('${id}') && map.getLayoutProperty('${id}', 'visibility') !== 'none'` : `!map.getLayer('${id}') || map.getLayoutProperty('${id}', 'visibility') === 'none'`, 60000); }
async function find(p, expr, cams) { for (const c of cams) { await jump(p, ...c); const r = await p.eval(expr); if (r) return { ...r, cam: c }; } return null; }
// zoom: a click that should zoom in (a cluster): after the fixed wait, wait until the camera has zoomed in and rests (the 500 ms ease lagged under load)
async function clickCard(p, pt, wait = 900, zoom = false) { await p.eval('__k.close()'); const z0 = await p.eval('map.getZoom()'); await click(p, pt.x, pt.y); await sleep(wait); if (zoom) await p.waitFor(`map.getZoom() > ${z0} + .5 && !map.isMoving()`, 20000); return { ...(await p.eval('__k.card()')), z0 }; }

async function run(lang, w, order) {
  const L = `3D ${lang} ${w} order ${order}`; console.log(L);
  const p = await openPage(`${base}/3d.html?lang=${lang}#c=18.2000,-66.6000,11`, view(w));
  if (!check(await p.waitFor("document.querySelector('#loader.hide') && window.ActiveLayers && typeof Supply !== 'undefined'", 90000), `${L}: ready`)) { await p.close(); return; }
  if (w < 500) await p.eval('setPanel(false), 0');
  await p.eval(HELPERS);
  await setLy(p, 'lyRoutes', false); await setLy(p, 'lyTrips', false);
  const key = (what) => `${lang} ${w} ${what}`;
  let pt, s;

  // 1. a cluster of stops over a circle of residents far from service: the gaps switched on before the stops (order 1) or after them (order 2)
  for (const id of order === 1 ? ['lyGaps', 'lyStops'] : ['lyStops', 'lyGaps']) { await setLy(p, id, true); await shown(p, id === 'lyGaps' ? 'gaps-pts' : 'stops-cluster'); }
  pt = await find(p, `__k.point(['stops-cluster', 'stops-count'], { need: ['gaps-pts'], box: 3, allow: '^stops-' })`, [[-66.6, 18.2, 11], [-66.3, 18.25, 11], [-65.9, 18.2, 11], [-67.0, 18.2, 11], [-66.5, 18.25, 10], [-66.9, 18.2, 10]]);
  if (check(!!pt, `${L}: a cluster over a gaps circle (${pt ? pt.at.join(',') : 'none'})`)) {
    s = await clickCard(p, pt, 1600, true);
    check(s.n === 0 && s.z > s.z0 + .5, `${L}: the cluster zooms in (${s.z0.toFixed(1)} → ${s.z.toFixed(1)}) and opens no card ("${short(s.text, 60)}")`);
  }
  pt = await find(p, `__k.point(['gaps-pts'], { box: 6 })`, [[-66.6, 18.2, 12.5], [-66.3, 18.25, 12.5]]);
  if (check(!!pt, `${L}: a gaps circle alone`)) { s = await clickCard(p, pt); check(s.n === 1 && s.text.includes(String(pt.props.n)) && !s.secs.length, `${L}: its card ("${short(s.text, 60)}")`); }
  await setLy(p, 'lyGaps', false); await setLy(p, 'lyStops', false); await shown(p, 'stops-cluster', false);

  // 2. the areas, switched on in opposite orders: one card with every area, the same in both pages
  const areaOrder = order === 1 ? [['lyFlood', 'flood-fill'], ['lyLanduse', 'landuse-fill'], ['lyComunidades', 'ce-fill'], ['lyBarrios', 'barrios-hit']] : [['lyBarrios', 'barrios-hit'], ['lyComunidades', 'ce-fill'], ['lyLanduse', 'landuse-fill'], ['lyFlood', 'flood-fill']];
  for (const [ly, id] of areaOrder) { await setLy(p, ly, true); check(await shown(p, id), `${L}: ${id} on`); }
  check(JSON.stringify(await p.eval('__k.stack()')) === JSON.stringify(['landuse-fill', 'flood-fill', 'ce-fill', 'ce-line']), `${L}: the areas are stacked land use, flood, Comunidades Especiales from the bottom (${(await p.eval('__k.stack()')).join(', ')})`);
  const cases = [
    { what: 'flood zone inside a barrio (Cangrejo Arriba)', on: ['lyFlood', 'lyBarrios'], need: ['flood-fill', 'barrios-hit'], cams: [[-65.95, 18.43, 13], [-66.0, 18.44, 13]], first: /^flood/, n: 2 },
    { what: 'land use inside a barrio', on: ['lyLanduse', 'lyBarrios'], need: ['landuse-fill', 'barrios-hit'], cams: [[-66.15, 18.39, 13]], first: /^landscape/, n: 2 },
    { what: 'flood zone, land use, Comunidad Especial and barrio', on: ['lyFlood', 'lyLanduse', 'lyComunidades', 'lyBarrios'], need: ['ce-fill', 'flood-fill', 'landuse-fill', 'barrios-hit'], cams: [[-66.15, 18.40, 14], [-66.07, 18.42, 14], [-66.0, 18.40, 14], [-65.95, 18.43, 14], [-66.61, 18.01, 14], [-66.04, 18.23, 14]], first: /^groups/, n: 4 },
  ];
  for (const c of cases) {
    for (const [ly] of areaOrder) await setLy(p, ly, c.on.includes(ly));
    for (const [ly, id] of areaOrder) await shown(p, id, c.on.includes(ly));
    pt = await find(p, `__k.areaSpot(${JSON.stringify(c.need)}, { only: ${JSON.stringify(c.need)} })`, c.cams);
    if (!check(!!pt, `${L}: ${c.what}: a spot`)) continue;
    s = await clickCard(p, pt);
    check(s.n === 1 && s.secs.length === c.n && c.first.test(s.secs[0]) && /^location_cityBarrio /.test(s.secs[s.secs.length - 1]), `${L}: ${c.what}: one card, ${s.secs.length} sections, top area first and the barrio last (${s.secs.map(x => short(x, 28)).join(' | ')})`);
    check(s.top === 0 && s.firstVisible === s.secs[0] && s.focusClose, `${L}: ${c.what}: it opens at its top, the first area's heading in view ("${short(s.firstVisible, 30)}", scroll ${s.top}), the focus on its close button (${s.focusClose})`);
    check(s.inside, `${L}: ${c.what}: the card is inside the map`);
    check(s.text === pt.expect, `${L}: ${c.what}: the 2D map's sections, in the fixed order ("${short(s.text, 70)}"${s.text === pt.expect ? '' : ` vs "${short(pt.expect, 70)}"`})`);
    const k = key(c.what), mine = { ll: pt.ll, cam: pt.cam, text: s.text };
    if (seen[k]) {   // the other order's page saw this place: the same card here
      await jump(p, ...seen[k].cam);
      const q = await p.eval(`__k.project(${JSON.stringify(seen[k].ll)})`), t = await clickCard(p, q);
      check(t.text === seen[k].text, `${L}: ${c.what}: the same card as with the layers switched on in the other order ("${short(t.text, 60)}"${t.text === seen[k].text ? '' : ` vs "${short(seen[k].text, 60)}"`})`);
    } else seen[k] = mine;
    // the link to the municipality's card
    const name = await p.eval("(document.querySelector('#idOpenMuni') || {}).textContent || ''");
    if (check(!!name, `${L}: ${c.what}: a link to the municipality ("${short(name, 50)}")`)) {
      await p.eval("document.querySelector('#idOpenMuni').click(), 0"); await sleep(400);
      const m = await p.eval('__k.card()');
      check(m.n === 1 && /^location_city(?!Barrio )/.test(m.text) && !m.secs.length && /index\.html(\?[^"#]*)?#/.test(m.html), `${L}: ${c.what}: the link opens the municipality's card ("${short(m.text, 60)}")`);
    }
  }
  // the columns on and the camera tilted: the link names the municipality of the ground, not of a column drawn over the pixel
  await setLy(p, 'lyCols', true); await p.waitFor("map.getLayoutProperty('muni-cols', 'visibility') !== 'none'", 30000);
  pt = await find(p, '__k.colSpot()', [[-66.12, 18.42, 11.5, 60, 0], [-66.12, 18.42, 11.5, 60, 90], [-66.05, 18.40, 11, 65, 180], [-66.0, 18.42, 11.5, 60, 270]]);
  if (check(!!pt, `${L}: a flood zone under a column of another municipality (${pt ? pt.col + ' over ' + pt.ground : 'none'})`)) {
    s = await clickCard(p, pt); const link = await p.eval("(document.querySelector('#idOpenMuni') || {}).textContent || ''");
    check(s.n === 1 && link === pt.link, `${L}: the card's link names the ground's municipality ("${link}", the column's is ${pt.col})`);
  }
  await setLy(p, 'lyCols', false); await p.waitFor("map.getLayoutProperty('muni-cols', 'visibility') === 'none'", 30000);
  // a point drawn over the areas opens its own card
  await setLy(p, 'lyStops', true); await shown(p, 'stops-pts');
  pt = await find(p, `__k.point(['stops-pts'], { need: ['flood-fill', 'barrios-hit'], box: 8 })`, [[-66.07, 18.42, 15.5], [-66.0, 18.44, 15.5], [-65.95, 18.43, 15.5], [-66.15, 18.40, 15.5], [-66.11, 18.45, 15.5]]);
  if (check(!!pt, `${L}: a stop inside a flood zone and a barrio`)) {
    s = await clickCard(p, pt); const want = await p.eval(`__k.transportText(${pt.props.i})`);
    check(s.n === 1 && s.text === want && !s.secs.length, `${L}: the stop's card, no area section ("${short(s.text, 60)}")`);
  }
  await setLy(p, 'lyStops', false);
  for (const [ly, id] of areaOrder) { await setLy(p, ly, false); await shown(p, id, false); }
  // land with nothing on it: the municipality; the sea: nothing
  await jump(p, -66.15, 18.30, 12);
  pt = await p.eval('__k.areaSpot([], {})');
  if (check(!!pt, `${L}: land with nothing on it`)) { s = await clickCard(p, pt); check(s.n === 1 && /^location_city(?!Barrio )/.test(s.text) && !s.secs.length && s.inside, `${L}: the municipality's card, inside the map (${s.inside}; "${short(s.text, 50)}")`); }
  await jump(p, -66.13, 18.53, 12);
  pt = await p.eval('__k.empty()');
  if (check(!!pt, `${L}: the sea`)) { s = await clickCard(p, pt); check(s.n === 0, `${L}: a click on the sea opens nothing (${s.n})`); }

  // the route lines are drawn under the stops, as on the 2D map: a cluster or a stop on a route line answers
  await setLy(p, 'lyRoutes', true); await setLy(p, 'lyStops', true); await shown(p, 'routes-line'); await shown(p, 'stops-cluster');
  check(await p.eval("(() => { const ids = map.getStyle().layers.map(l => l.id); return ids.indexOf('routes-ferry') < ids.indexOf('stops-cluster') && ids.indexOf('routes-line') < ids.indexOf('stops-pts'); })()"), `${L}: the route lines are drawn under the stops`);
  pt = await find(p, `__k.point(['stops-cluster', 'stops-count'], { need: ['routes-line'], box: 3, allow: '^(stops-|routes-)' })`, [[-66.07, 18.42, 12], [-66.15, 18.39, 12], [-66.07, 18.42, 13]]);
  if (check(!!pt, `${L}: a cluster on a route line (${pt ? pt.at.join(',') : 'none'})`)) { s = await clickCard(p, pt, 1600, true); check(s.n === 0 && s.z > s.z0 + .5, `${L}: it zooms in (${s.z0.toFixed(1)} → ${s.z.toFixed(1)}), no card ("${short(s.text, 50)}")`); }
  pt = await find(p, `__k.point(['stops-pts'], { needRe: '^routes-', scan: 6, box: 6, allow: '^(stops-|routes-)' })`, [[-66.07, 18.42, 15.5], [-66.06, 18.42, 15.5], [-66.0, 18.44, 15.5], [-66.15, 18.40, 15.5], [-66.11, 18.45, 15.5], [-65.97, 18.38, 15.5], [-66.61, 18.01, 15.5], [-66.04, 18.23, 15.5]]);
  if (check(!!pt, `${L}: a stop on a route line`)) { s = await clickCard(p, pt); const want = await p.eval(`__k.transportText(${pt.props.i})`); check(s.n === 1 && s.text === want, `${L}: the stop's card, not the route's ("${short(s.text, 60)}")`); }
  // the places: their points over the route lines and the stops, their heat map under the route lines; the stations and the WCRP pins in one order on top
  await setLy(p, 'lyPlaces', true); await p.waitFor("!!map.getLayer('places-pts') && !!map.getLayer('places-heat')", 90000);
  for (const id of order === 1 ? ['lyHubs', 'lyWcrp'] : ['lyWcrp', 'lyHubs']) { await setLy(p, id, true); await shown(p, id === 'lyHubs' ? 'hubs-pts' : 'wcrp-pts'); }   // each drawn before the next is switched on
  const [heat, line, stopsAt, pts, hubs, wcrp] = await p.eval(`__k.order(['places-heat', 'routes-line', 'stops-pts', 'places-pts', 'hubs-pts', 'wcrp-pts'])`);
  check(heat < line && line < stopsAt && stopsAt < pts && pts < hubs && hubs < wcrp, `${L}: from the bottom: the places' heat map, the route lines, the stops, the places' points, the stations, the WCRP pins (${[heat, line, stopsAt, pts, hubs, wcrp].join(' < ')})`);
  for (const id of ['lyPlaces', 'lyHubs', 'lyWcrp']) await setLy(p, id, false);
  await setLy(p, 'lyRoutes', false); await setLy(p, 'lyStops', false); await shown(p, 'stops-cluster', false);

  // 3. the route planner choosing a point: the click places it, no card and no zoom
  await p.eval("showTab('route', { open: false }), 0"); await p.waitFor('!!Plan.root', 30000);
  if (w < 500) await p.eval('setPanel(false), 0');
  await setLy(p, 'lyStops', true); await setLy(p, 'lyFlood', true); await setLy(p, 'lyBarrios', true); await shown(p, 'stops-cluster'); await shown(p, 'flood-fill'); await shown(p, 'barrios-hit');
  pt = await find(p, `__k.point(['stops-cluster', 'stops-count'], { box: 4, allow: '^stops-' })`, [[-66.15, 18.39, 12], [-66.07, 18.42, 12]]);
  if (check(!!pt, `${L}: a cluster for the planner`)) {
    await p.eval("Plan.clear(), Plan.root.querySelectorAll('[data-act=pick]')[0].click(), 0"); if (w < 500) await p.eval('setPanel(false), 0');
    s = await clickCard(p, pt, 1600);
    await p.waitFor('!!Plan.stops[0].pt', 30000);   // Plan.mapPick names the point from the gazetteer, which it loads first: placed after that file arrives
    const a = await p.eval('({ picking: Plan.picking, placed: !!Plan.stops[0].pt })');
    check(s.n === 0 && Math.abs(s.z - s.z0) < .05 && a.placed && a.picking === -1, `${L}: picking point A on a cluster places it (${JSON.stringify(a)}), no zoom (${s.z0.toFixed(2)} → ${s.z.toFixed(2)}), no card ("${short(s.text, 50)}")`);
  }
  pt = await find(p, `__k.areaSpot(['flood-fill', 'barrios-hit'], { box: 12 })`, [[-65.95, 18.43, 13]]);
  if (check(!!pt, `${L}: a flood zone for the planner`)) {
    await p.eval("Plan.clear(), Plan.root.querySelectorAll('[data-act=pick]')[0].click(), 0"); if (w < 500) await p.eval('setPanel(false), 0');
    s = await clickCard(p, pt, 1200); await p.waitFor('!!Plan.stops[0].pt', 30000);
    check(s.n === 0 && await p.eval('!!Plan.stops[0].pt'), `${L}: picking point A in a flood zone places it, no card ("${short(s.text, 50)}")`);
    await p.eval('Plan.clear(), Plan.setClickMode(true), 0'); if (w < 500) await p.eval('setPanel(false), 0');
    s = await clickCard(p, pt, 1200); await p.waitFor('!!Plan.stops[0].pt', 30000);
    check(s.n === 0 && await p.eval('!!Plan.stops[0].pt && Plan.clickMode'), `${L}: "Add points by clicking the map" places a point, no card ("${short(s.text, 50)}")`);
    await p.eval('Plan.setClickMode(false), Plan.clear(), 0');
  }
  await setLy(p, 'lyStops', false); await setLy(p, 'lyFlood', false);

  // 4. deck.gl draws above MapLibre: its object answers
  await setLy(p, 'lySupStops', true); await p.waitFor("Supply.layers().some(l => l.id === 'sup-stops')", 60000);
  await setLy(p, 'lyStops', true); await shown(p, 'stops-cluster');
  pt = await find(p, `__k.deck('sup-stops', '[d.f.lng, d.f.lat]', { top: '^stops-(cluster|count)$' })`, [[-66.06, 18.42, 12.5], [-66.1, 18.40, 12.5], [-66.0, 18.40, 12.5]]);
  if (check(!!pt, `${L}: a stop of the hour over a cluster`)) { s = await clickCard(p, pt, 1600); check(s.n === 1 && s.text === pt.expect && Math.abs(s.z - s.z0) < .05, `${L}: the stop of the hour's card, no zoom (${s.z0.toFixed(2)} → ${s.z.toFixed(2)}; "${short(s.text, 60)}")`); }
  pt = await find(p, `__k.deck('sup-stops', '[d.f.lng, d.f.lat]', { top: '^stops-pts$' })`, [[-66.06, 18.42, 15.5], [-66.07, 18.42, 15.5], [-66.0, 18.44, 15.5]]);
  if (check(!!pt, `${L}: a stop of the hour over the same stop of the Stops layer`)) { s = await clickCard(p, pt); check(s.n === 1 && s.text === pt.expect, `${L}: the stop of the hour's card, not the plain stop's ("${short(s.text, 70)}")`); }
  await setLy(p, 'lyStops', false); await setLy(p, 'lySupStops', false);
  await setLy(p, 'lyRoutes', true); await shown(p, 'routes-line'); await setLy(p, 'lySupRoutes', true); await p.waitFor("Supply.layers().some(l => l.id === 'sup-routes')", 60000);
  pt = await find(p, `__k.deck('sup-routes', 'd.path', { top: '^routes-' })`, [[-66.06, 18.42, 13.5], [-66.07, 18.42, 13], [-66.0, 18.40, 13]]);
  if (check(!!pt, `${L}: a route of the hour over a route line`)) { s = await clickCard(p, pt); check(s.n === 1 && s.text === pt.expect && s.html.includes('data-route-profile'), `${L}: the route of the hour's card ("${short(s.text, 60)}")`); }
  await setLy(p, 'lySupRoutes', false); await setLy(p, 'lyRoutes', false);
  // a storm track shows, on a click, what pointing at it shows
  await setLy(p, 'lyStorms', true); await p.waitFor("(overlay._props.layers || []).some(l => l && l.id === 'storm-paths')", 60000);
  pt = await find(p, `__k.deck('storm-paths', 'd.track.map(q => [q[0], q[1]])', { land: true })`, [[-66.4, 18.2, 9], [-66.0, 18.3, 9.5]]);
  if (check(!!pt, `${L}: a storm track over land`)) { s = await clickCard(p, pt); check(s.n === 1 && s.text === pt.expect && !s.secs.length, `${L}: the storm's card, not the area's ("${short(s.text, 60)}")`); }
  await setLy(p, 'lyStorms', false);

  // 5. the layers with no card: no area card under them; a stop under a vehicle still answers
  await setLy(p, 'lyTrips', true); await p.waitFor("!!S.trips && (overlay._props.layers || []).some(l => l && l.id === 'trips')", 60000);
  await p.eval("(S.playing = false, setPlayIcons(), S.clock = 8 * 3600 + 600, syncClock(), renderDeck(), 0)");
  pt = null; for (const c of [[-66.06, 18.42, 13], [-66.07, 18.44, 14], [-66.1, 18.40, 13]]) { await jump(p, ...c); pt = await p.eval("__k.noCard('trips')"); if (pt) break; }
  if (check(!!pt, `${L}: a vehicle over land`)) { s = await clickCard(p, pt); check(s.n === 0, `${L}: a click on a vehicle opens no card of the area under it ("${short(s.text, 50)}")`); }
  await setLy(p, 'lyStops', true); await shown(p, 'stops-pts');
  pt = null;
  for (const clock of [8 * 3600 + 600, 7 * 3600 + 1200, 8 * 3600 + 2400, 12 * 3600, 17 * 3600 + 900]) {   // a vehicle passes a stop now and then: several times of day
    await p.eval(`(S.clock = ${clock}, syncClock(), renderDeck(), 0)`);
    for (const c of [[-66.06, 18.42, 15.5], [-66.07, 18.42, 15.5], [-66.065, 18.445, 15.5], [-66.07, 18.40, 15.5], [-66.0, 18.44, 15.5], [-66.11, 18.40, 15.5]]) { await jump(p, ...c, 0); pt = await p.eval("__k.noCard('trips', { under: 'stops-pts' })"); if (pt) break; }
    if (pt) break;
  }
  if (check(!!pt, `${L}: a stop under a vehicle`)) { s = await clickCard(p, pt); const want = await p.eval(`__k.transportText(${pt.props.i})`); check(s.n === 1 && s.text === want, `${L}: the stop under a vehicle answers ("${short(s.text, 60)}")`); }
  await setLy(p, 'lyStops', false); await setLy(p, 'lyTrips', false);
  const route = await p.eval("(() => { const o = [...document.querySelectorAll('#rpSel option')].find(o => /^ati\\|/.test(o.value)); return o && o.value; })()");
  if (check(!!route, `${L}: a route to profile`)) {
    await p.eval(`(async () => { await Supply.showRoute(${JSON.stringify(route)}, false); return 1; })()`);
    const along = await p.eval("(() => { const L = (overlay._props.layers || []).find(l => l && l.id === 'rp-line'), path = L ? L.props.data[0] : []; return [.3, .5, .7].map(t => path[Math.floor(t * (path.length - 1))]).filter(Boolean); })()");   // places along the profile's line
    pt = null; for (const c of along.flatMap(ll => [[ll[0], ll[1], 14], [ll[0], ll[1], 13]])) { await jump(p, ...c); pt = await p.eval("__k.noCard('rp-line')"); if (pt) break; }
    if (check(!!pt, `${L}: the line of the route profile over land`)) { s = await clickCard(p, pt); check(s.n === 0, `${L}: a click on the profile's line opens no area card ("${short(s.text, 50)}")`); }
    await p.eval(`(async () => { await Supply.showRoute('', false); return 1; })()`);
  }

  const errs = p.logs.filter(l => l.type === 'error' || l.type === 'EXCEPTION' || l.type === 'log.error');
  check(!errs.length, `${L}: no console errors ${errs.length ? JSON.stringify(errs).slice(0, 300) : ''}`);
  const missed = await p.eval('I18N.missed');
  check(!missed.length, `${L}: no Spanish missing ${missed.length ? JSON.stringify(missed).slice(0, 200) : ''}`);
  await p.close();
}

(async () => {
  for (const lang of langs) for (const w of widths) for (const order of [1, 2]) await run(lang, w, order);
  console.log(problems.length ? `\n${passed} passed, ${problems.length} problem(s):\n- ` + problems.join('\n- ') : `\nall ${passed} checks passed`);
  process.exitCode = problems.length ? 1 : 0;
  setTimeout(() => process.exit(), 50);
})().catch(e => { console.error(e); process.exit(2); });
