// A click that a point or a cluster answers opens no card of the area under it (the review of PR #75), on the 2D map and the 3D view, in a real browser:
//  - a click on a cluster of stops, on land with barrios on, zooms in and opens no pop-up (no municipality or barrio card);
//  - 3D: a click on a stop of "Service at this hour" (Time tab, deck.gl) shows that stop's card, not the municipality's or the barrio's;
//  - 3D: a click on a facility point inside a barrio shows the facility, whichever layer was switched on first; a click on bare land shows the barrio.
// Each click is a real mouse click at the point's place on the screen. The console stays clean.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/cluster_clicks.js [base URL, default http://127.0.0.1:8041] [langs, default es,en] [widths, default 1400,390]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(','), widths = (process.argv[4] || '1400,390').split(',').map(Number);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
const view = (w) => ({ width: w, height: w < 500 ? 812 : 900, mobile: w < 500 });
const click = async (p, x, y) => { for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); };
const clean = (p, label) => { const e = p.logs.filter(l => l.type === 'error' || l.type === 'EXCEPTION' || l.type === 'log.error'); check(!e.length, `${label}: no console errors ${e.length ? JSON.stringify(e).slice(0, 300) : ''}`); };
const POPUP3D = "((document.querySelector('.maplibregl-popup-content') || {}).innerText || '').replace(/\\s+/g, ' ').trim()";

// a feature of a MapLibre layer drawn on land in the visible part of the map, as a point on the page; land: a municipality and a barrio under it
const onScreen3d = (layers) => `(() => { const r = document.getElementById('map').getBoundingClientRect(), panel = document.getElementById('panel'), pr = panel && panel.classList.contains('open') && r.width > 600 ? panel.getBoundingClientRect().right : 0;
  const fs = map.queryRenderedFeatures({ layers: ${JSON.stringify(layers)} });
  for (const f of fs) { const q = map.project(f.geometry.coordinates); if (q.x < pr + 30 || q.x > r.width - 90 || q.y < 140 || q.y > r.height - 170) continue;
    const under = map.queryRenderedFeatures([q.x, q.y], { layers: ['muni-hit', 'barrios-hit'] }).map(g => g.layer.id); if (under.length < 2) continue;
    return { x: Math.round(q.x + r.left), y: Math.round(q.y + r.top), n: fs.length }; }
  return { n: fs.length }; })()`;

async function run3d(lang, w) {
  const label = `3D ${lang} ${w}`; console.log(label);
  const p = await openPage(`${base}/3d.html?lang=${lang}#c=18.3900,-66.1500,11`, view(w));
  check(await p.waitFor("document.querySelector('#loader.hide') && window.ActiveLayers", 90000), `${label}: ready`);
  if (w < 500) await p.eval('setPanel(false), 0');
  // 1. a cluster of stops on land, with barrios on
  await p.eval("['lyBarrios', 'lyStops'].forEach(id => document.getElementById(id).click()), 0");
  check(await p.waitFor("!!map.getLayer('stops-cluster') && !!map.getLayer('barrios-hit')", 60000), `${label}: stops and barrios on`);
  await p.eval("map.jumpTo({ center: [-66.15, 18.39], zoom: 11, pitch: 0, bearing: 0 }), 0"); await p.waitFor('map.loaded() && !map.isMoving()', 30000); await sleep(1200);
  let pt = await p.eval(onScreen3d(['stops-cluster']));
  if (check(pt.x != null, `${label}: a cluster on land on the screen (${pt.n} drawn)`)) {
    const z0 = await p.eval('map.getZoom()');
    await p.eval("document.querySelectorAll('.maplibregl-popup').forEach(e => e.remove()), 0");
    await click(p, pt.x, pt.y); await sleep(1500);
    const s = await p.eval(`({ pop: ${POPUP3D}, z: map.getZoom() })`);
    check(!s.pop && s.z > z0 + .5, `${label}: a click on the cluster zooms in (${z0.toFixed(1)} → ${s.z.toFixed(1)}) and opens no card ("${s.pop.slice(0, 80)}")`);
  }
  // 2. a stop of "Service at this hour" (deck.gl), on land
  await p.eval("['lyStops', 'lyRoutes', 'lyTrips'].forEach(id => document.getElementById(id).checked && document.getElementById(id).click()); document.getElementById('lySupStops').click(), 0");
  await p.eval("map.jumpTo({ center: [-66.06, 18.42], zoom: 13.5, pitch: 0, bearing: 0 }), 0"); await p.waitFor('map.loaded() && !map.isMoving()', 30000);
  check(await p.waitFor("typeof Supply !== 'undefined' && Supply.layers().some(l => l.id === 'sup-stops')", 60000), `${label}: the stops of the hour are drawn`);
  await sleep(1500);
  pt = await p.eval(`(() => { const L = Supply.layers().find(l => l.id === 'sup-stops'), r = document.getElementById('map').getBoundingClientRect();
    for (const d of L.props.data) { const q = map.project([d.f.lng, d.f.lat]); if (q.x < 60 || q.x > r.width - 90 || q.y < 140 || q.y > r.height - 170) continue;
      if (map.queryRenderedFeatures([q.x, q.y], { layers: ['muni-hit', 'barrios-hit'] }).length < 2) continue; return { x: Math.round(q.x + r.left), y: Math.round(q.y + r.top), name: d.f.name }; }
    return {}; })()`);
  if (check(pt.x != null, `${label}: a stop of the hour on land on the screen`)) {
    await p.eval("document.querySelectorAll('.maplibregl-popup').forEach(e => e.remove()), 0");
    await click(p, pt.x, pt.y); await sleep(1200);
    const pop = await p.eval(POPUP3D);
    check(/^directions_bus/.test(pop), `${label}: a click on a stop of the hour ("${pt.name.replace(/\s+/g, ' ')}") shows a stop's card, not the area under it ("${pop.slice(0, 90)}")`);   // two stops a few metres apart (antes / después) can be picked either way
  }
  await p.eval("document.getElementById('lySupStops').click(), 0");
  // 3. a facility switched on before the barrios: its point still wins; bare land shows the barrio
  await p.eval("['lyBarrios'].forEach(id => document.getElementById(id).click()); document.getElementById('lyFire').click(), 0");
  await p.waitFor("!!map.getLayer('fac-fire') && map.getLayoutProperty('fac-fire', 'visibility') === 'visible'", 60000);
  await p.eval("document.getElementById('lyBarrios').click(), 0"); await p.waitFor("map.getLayoutProperty('barrios-hit', 'visibility') === 'visible'", 30000);
  await p.eval("map.jumpTo({ center: [-66.08, 18.42], zoom: 12.5, pitch: 0, bearing: 0 }), 0"); await p.waitFor('map.loaded() && !map.isMoving()', 30000); await sleep(1200);
  pt = await p.eval(onScreen3d(['fac-fire']));
  if (check(pt.x != null, `${label}: a fire station inside a barrio on the screen`)) {
    await p.eval("document.querySelectorAll('.maplibregl-popup').forEach(e => e.remove()), 0");   // the stop of the hour's card, still open, can cover the station on a phone
    await click(p, pt.x, pt.y); await sleep(900);
    const pop = await p.eval(POPUP3D);
    check(/^health_and_safety/.test(pop), `${label}: the fire station's card, not the barrio's ("${pop.slice(0, 70)}")`);
    const land = await p.eval(`(() => { const r = document.getElementById('map').getBoundingClientRect(); for (let dx = 60; dx < 400; dx += 20) for (const s of [1, -1]) { const x = ${pt.x} - r.left + s * dx, y = ${pt.y} - r.top + 60;
      if (x < 40 || x > r.width - 90 || y > r.height - 170) continue; const ids = map.queryRenderedFeatures([[x - 12, y - 12], [x + 12, y + 12]]).map(f => f.layer.id);
      if (ids.includes('barrios-hit') && !ids.some(id => /^(fac-|stops-|hubs-|routes-|taxi-|places-|wcrp-)/.test(id))) return { x: Math.round(x + r.left), y: Math.round(y + r.top) }; } return null; })()`);
    await p.eval("document.querySelectorAll('.maplibregl-popup').forEach(e => e.remove()), 0");
    if (land) await click(p, land.x, land.y); await sleep(900);
    const pop2 = await p.eval(POPUP3D);
    check(/^location_city Barrio/.test(pop2), `${label}: a click on bare land beside it shows the barrio ("${pop2.slice(0, 50)}")`);
  }
  clean(p, label); check(!(await p.eval('I18N.missed')).length, `${label}: no Spanish missing`);
  await p.close();
}

async function run2d(lang, w) {
  const label = `2D ${lang} ${w}`; console.log(label);
  const p = await openPage(`${base}/index.html?lang=${lang}#c=18.3900,-66.1500,12&l=muni,stops,barrios`, view(w));
  check(await p.waitFor("document.querySelector('#loader.hide') && window.ActiveLayers && !!S.transport && !!S.barrios && map.hasLayer(stopCluster)", 90000), `${label}: ready with stops and barrios`);
  if (w < 500) await p.eval('setPanel(false), 0');
  await sleep(1200);
  const pt = await p.eval(`(() => { const r = document.getElementById('map').getBoundingClientRect(); for (const el of document.querySelectorAll('.marker-cluster-stops')) { const b = el.getBoundingClientRect(), x = b.left + b.width / 2, y = b.top + b.height / 2;
      if (x < r.left + 40 || x > r.right - 80 || y < r.top + 120 || y > r.bottom - 120) continue; const ll = map.containerPointToLatLng([x - r.left, y - r.top]);
      if (featuresAt(S.barrios, ll, () => true, 1).length) return { x: Math.round(x), y: Math.round(y) }; } return {}; })()`);
  if (check(pt.x != null, `${label}: a cluster of stops inside a barrio on the screen`)) {
    const z0 = await p.eval('map.getZoom()');
    await click(p, pt.x, pt.y); await sleep(1500);
    const s = await p.eval("({ pop: !!document.querySelector('.leaflet-popup'), z: map.getZoom(), muni: S.selected })");
    check(!s.pop && s.z > z0 && !s.muni, `${label}: a click on the cluster zooms in (${z0} → ${s.z}) and opens no card or municipality`);
  }
  clean(p, label); check(!(await p.eval('I18N.missed')).length, `${label}: no Spanish missing`);
  await p.close();
}

(async () => {
  for (const lang of langs) for (const w of widths) { await run3d(lang, w); await run2d(lang, w); }
  console.log(problems.length ? `\n${passed} passed, ${problems.length} problem(s):\n- ` + problems.join('\n- ') : `\nall ${passed} checks passed`);
  process.exitCode = problems.length ? 1 : 0;
  setTimeout(() => process.exit(), 50);
})().catch(e => { console.error(e); process.exit(2); });
