// The view state the 2D map and the 3D view share through the address (site/js/core/viewstate.js, docs/view-state.md), in a real browser, in each language:
//  1. 2D: a municipality selected, flood zones and routes on, the municipios shaded, two Economy layers (one Shaded, one Symbol) and a year. The address says so,
//     and the 3D link is 3d.html + that address.
//  2. 3D, opened from that link: the camera where the 2D map was (the zoom one less), the same layers (the vehicles and the terrain, 3D only, as by default), the
//     columns from the Economy layers (height from the Symbol one, color from the Shaded one, the year), the municipality's card open; the address kept the
//     2D map's s= and e= as they were and added the camera's b= and p=. Then: flood zones off, storm tracks on, vehicles off, the camera turned and tilted, the
//     columns' height on another dataset. The address follows with replaceState (no new history entry), and the 2D link is index.html + that address.
//  3. 2D, opened from that link: flood zones off, routes on, the shading off (the 3D columns, changed there, show the Economy datasets only), the color layer kept, the new height as a Symbol layer, the municipality, the camera
//     where the 3D view was; the 3D-only layers and the camera's b= and p= kept in the address.
//  4. Old and bogus links: the 3D view on an address from before (c, bm) keeps its defaults; on one with bogus values and a dataset it does not have, it opens with
//     no columns and a clean console, and keeps the unknown parts in the address.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=d3d11 --enable-gpu     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/view_state.js [base URL, default http://127.0.0.1:8041] [langs, default es,en] [width, default 1400]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(','), width = +process.argv[4] || 1400;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (tag, what, ok, detail) => { if (ok) passed++; else problems.push(`${tag}: ${what}`); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${tag}: ${what}${ok || detail === undefined ? '' : '  ' + JSON.stringify(detail).slice(0, 500)}`); return ok; };
const errors = (p) => p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon|ERR_BLOCKED_BY_CLIENT/.test(l.text + (l.url || '')));
const READY = "performance.getEntriesByName('ready').length > 0";
const near = (a, b, d) => Math.abs(a - b) <= d;

async function run(lang) {
  const tag = (s) => `${lang} ${s}`;
  // ── 1. the 2D map ──
  let p = await openPage(`${base}/index.html?lang=${lang}#c=18.0500,-66.6000,11`, { width, height: 900, noCache: true });
  let k1, k2, k3, link3, hash2;
  try {
    check(tag('2D'), 'ready', await p.waitFor(READY + ' && !!window.Core && !!Core.viewstate', 90000));
    await p.eval(`(async () => { await ECON.api.ready(); return 1; })()`, { timeout: 60000 });
    // three municipal datasets the 3D columns also have (not the WCRP ones, which are by barrio), with a year in common
    [k1, k2, k3] = await p.eval(`ECON.api.datasets().filter(d => !/wcrp/i.test(d.key + ' ' + (d.group || '')) && !d.static).slice(0, 40).map(d => d.key).filter(k => !!EC.V[k] && !EC.V[k].level).slice(0, 3)`);
    check(tag('2D'), `three datasets to use (${k1}, ${k2}, ${k3})`, !!(k1 && k2 && k3));
    for (const id of ['lyFlood', 'lyRoutes']) await p.eval(`document.getElementById('${id}').click(), 1`);
    await p.eval(`(() => { const s = document.getElementById('choro'); s.value = 'vacancy_pct'; s.dispatchEvent(new Event('change')); return 1; })()`);
    await p.eval(`(() => { ecAdd('${k1}', 'fill'); ecAdd('${k2}', 'symbol'); ecRender(); ECON.api.setYear(2020); selectMuni('Ponce', { fly: false }); writeHash(); return 1; })()`);
    check(tag('2D'), 'the address is written', await p.waitFor(`/^#Ponce&/.test(location.hash) && /[&#]e=/.test(location.hash) && /s=vacancy_pct/.test(location.hash)`, 10000), await p.eval('location.hash'));
    hash2 = await p.eval('location.hash');
    const P = await p.eval(`JSON.stringify(Core.viewstate.parse(location.hash))`).then(JSON.parse);
    check(tag('2D'), 'layers, shading, Economy (Shaded, Symbol), municipality in the address', P.muni === 'Ponce' && P.l.includes('flood') && P.l.includes('routes') && P.s === 'vacancy_pct'
      && new RegExp(`^${k1}\\.f\\b`).test(P.e) && new RegExp(`,${k2}\\.s\\b`).test(P.e) && P.ey === 2020, P);
    link3 = await p.eval(`document.querySelector('.views a[href^="3d.html"]').getAttribute('href')`);
    check(tag('2D'), 'the 3D link carries the whole address and ?lang=', link3 === `3d.html?lang=${lang}` + hash2, [link3, hash2]);
    const e = errors(p); check(tag('2D'), 'a clean console', e.length === 0, e);
  } finally { await p.close(); }

  // ── 2. the 3D view, from the 2D link ──
  let link2, hash3, cam3;
  p = await openPage(`${base}/${link3}`, { width, height: 900, noCache: true });
  try {
    check(tag('3D'), 'ready, the address applied', await p.waitFor(READY + ' && VS.ready', 90000));
    const P2 = await p.eval(`JSON.stringify(Core.viewstate.parse(${JSON.stringify(hash2)}))`).then(JSON.parse);
    const cam = await p.eval(`(() => { const c = map.getCenter(); return { lat: c.lat, lng: c.lng, z: map.getZoom() }; })()`);
    check(tag('3D'), 'the camera where the 2D map was, the zoom one less', near(cam.lat, P2.c.lat, 0.002) && near(cam.lng, P2.c.lng, 0.002) && near(cam.z, P2.c.z - 1, 0.05), [cam, P2.c]);
    const ly = await p.eval(`Object.fromEntries(['lyFlood', 'lyRoutes', 'lyStops', 'lyTrips', 'lyTerrain', 'lyBuildings', 'lyMuni', 'lyCols'].map(id => [id, document.getElementById(id).checked]))`);
    check(tag('3D'), 'the same layers; the 3D-only vehicles and terrain as by default', ly.lyFlood && ly.lyRoutes && !ly.lyStops && ly.lyTrips && ly.lyTerrain && ly.lyBuildings && ly.lyMuni === (P2.l || []).includes('muni'), ly);   // Límites as the 2D map had it (off when it opens since 2026-11-13)
    check(tag('3D'), 'the columns: height from the Symbol layer, color from the Shaded one', await p.waitFor(`document.getElementById('lyCols').checked && metricKey === '__any' && ENG.filled && ENG.h === '${k2}' && ENG.c === '${k1}' && document.getElementById('engH').value === '${k2}' && ENG.y === 2020 && document.getElementById('engY').value === '2020'`, 60000),
      await p.eval(`({ cols: document.getElementById('lyCols').checked, metricKey, h: ENG.h, c: ENG.c })`));
    check(tag('3D'), 'the municipality\'s card is open', await p.waitFor(`VS.muni === 'Ponce' && !!document.querySelector('.maplibregl-popup .pop h4') && /Ponce/.test(document.querySelector('.maplibregl-popup .pop h4').textContent)`, 10000));
    await sleep(600);
    const H = await p.eval(`JSON.stringify(Core.viewstate.parse(location.hash))`).then(JSON.parse);
    check(tag('3D'), 'the address keeps the 2D map\'s s= and e= and adds the camera\'s b= and p=', H.s === 'vacancy_pct' && H.e === P2.e && H.b != null && H.p != null && H.muni === 'Ponce', H);
    check(tag('3D'), 'the card\'s 2D link selects Ponce and carries the state', await p.eval(`(() => { const a = document.querySelector('.maplibregl-popup .links a[href^="index.html"]'); const P = Core.viewstate.parse(a.getAttribute('href').slice(a.getAttribute('href').indexOf('#'))); return P.muni === 'Ponce' && !P.c && P.s === 'vacancy_pct'; })()`));
    const hist0 = await p.eval('history.length');
    // change: flood off, storms on, vehicles off, the camera, the columns' height
    for (const id of ['lyFlood', 'lyStorms', 'lyTrips']) await p.eval(`document.getElementById('${id}').click(), 1`);
    await p.eval(`map.jumpTo({ center: [-66.12, 18.42], zoom: 11.6, bearing: 30, pitch: 45 }), 1`);
    await p.eval(`(() => { const s = document.getElementById('engH'); s.value = '${k3}'; s.dispatchEvent(new Event('change')); return 1; })()`);
    for (let i = 0; i < 8; i++) { await p.eval(`map.panBy([5, 0], { duration: 0 }), 1`); await sleep(60); }   // a burst of moves: one write at the end
    await p.eval(`map.jumpTo({ center: [-66.12, 18.42], zoom: 11.6, bearing: 30, pitch: 45 }), 1`);
    await sleep(900);
    hash3 = await p.eval('location.hash');
    const H3 = await p.eval(`JSON.stringify(Core.viewstate.parse(location.hash))`).then(JSON.parse);
    cam3 = H3.c;
    check(tag('3D'), 'the address follows: layers (-trips, storms, no flood), camera (b=30, p=45, the zoom one more), the new height as a Symbol layer',
      !H3.l.includes('flood') && H3.l.includes('routes') && H3.l.includes('storms') && H3.l.includes('-trips') && H3.b === 30 && H3.p === 45
      && near(H3.c.lat, 18.42, 0.0002) && near(H3.c.lng, -66.12, 0.0002) && near(H3.c.z, 12.6, 0.01) && H3.e === `${P2.e.split(',')[0]},${k3}.s` && H3.s === null, H3);
    check(tag('3D'), 'replaceState only: no new history entry', await p.eval('history.length') === hist0);
    link2 = await p.eval(`document.querySelector('.views a[href^="index.html"]').getAttribute('href')`);
    check(tag('3D'), 'the 2D link carries the whole address and ?lang=', link2 === `index.html?lang=${lang}` + hash3, [link2, hash3]);
    // the card opened on load is still open: its "Open in 2D analysis" link follows the address (review of #97: it kept the state of the moment it opened)
    const card = await p.eval(`(() => { const a = document.querySelector('.maplibregl-popup a[data-to2d]'); return a ? a.getAttribute('href') : null; })()`);
    const C = card && await p.eval(`JSON.stringify(Core.viewstate.parse(${JSON.stringify(card.slice(card.indexOf('#')))}))`).then(JSON.parse);
    check(tag('3D'), 'the open card\'s 2D link carries the new layers, columns and camera, with Ponce and no c=', !!C && C.muni === 'Ponce' && !C.c && C.l.includes('storms') && !C.l.includes('flood') && C.e === H3.e && C.b === 30 && C.p === 45, C || card);
    const e = errors(p); check(tag('3D'), 'a clean console', e.length === 0, e);
  } finally { await p.close(); }

  // ── 3. back on the 2D map ──
  p = await openPage(`${base}/${link2}`, { width, height: 900, noCache: true });
  try {
    check(tag('2D back'), 'ready', await p.waitFor(READY, 90000));
    check(tag('2D back'), 'the Economy layers: the color kept, the new height as a Symbol layer', await p.waitFor(`typeof ECON === 'object' && ECON.api.state().layers.map(l => l.key + ':' + l.mode).join() === '${k1}:fill,${k3}:symbol'`, 60000),
      await p.eval(`typeof ECON === 'object' ? ECON.api.state().layers : null`));
    check(tag('2D back'), 'the year kept', await p.eval('ECON.api.state().year') === 2020, await p.eval('ECON.api.state().year'));
    const s = await p.eval(`({ flood: document.getElementById('lyFlood').checked, routes: document.getElementById('lyRoutes').checked, choro: document.getElementById('choro').value, sel: S.selected,
      lat: map.getCenter().lat, lng: map.getCenter().lng, z: map.getZoom() })`);
    check(tag('2D back'), 'flood off, routes on, the shading off (the 3D columns show the Economy datasets), Ponce selected', !s.flood && s.routes && !s.choro && s.sel === 'Ponce', s);
    check(tag('2D back'), 'the camera where the 3D view was', near(s.lat, cam3.lat, 0.002) && near(s.lng, cam3.lng, 0.002) && Math.abs(s.z - cam3.z) <= 0.6, [s, cam3]);
    await p.eval('writeHash(), 1'); await sleep(600);
    const H = await p.eval(`JSON.stringify(Core.viewstate.parse(location.hash))`).then(JSON.parse);
    check(tag('2D back'), 'the 3D-only layers and the camera\'s b= and p= stay in the address', H.l.includes('storms') && H.l.includes('-trips') && H.b === 30 && H.p === 45, H);
    const e = errors(p); check(tag('2D back'), 'a clean console', e.length === 0, e);
  } finally { await p.close(); }

  // ── 4. old and bogus links on the 3D view ──
  p = await openPage(`${base}/3d.html?lang=${lang}#c=18.2208,-66.5901,9&bm=liberty`, { width, height: 900, noCache: true });
  try {
    check(tag('3D old link'), 'ready', await p.waitFor(READY + ' && VS.ready', 90000));
    const s = await p.eval(`({ routes: document.getElementById('lyRoutes').checked, trips: document.getElementById('lyTrips').checked, cols: document.getElementById('lyCols').checked, z: map.getZoom(), bm: BM.name })`);
    check(tag('3D old link'), 'the defaults: routes and vehicles on, no columns; the zoom one less; Liberty', s.routes && s.trips && !s.cols && near(s.z, 8, 0.05) && s.bm === 'liberty', s);
    const e = errors(p); check(tag('3D old link'), 'a clean console', e.length === 0, e);
  } finally { await p.close(); }
  p = await openPage(`${base}/3d.html?lang=${lang}#Nowhere&c=abc&b=999&p=-4&l=routes,%3Cx%3E,flood&s=nope&e=no_such_dataset.f&ey=20x&later=1`, { width, height: 900, noCache: true });
  try {
    check(tag('3D bogus link'), 'ready', await p.waitFor(READY + ' && VS.ready', 90000));
    await p.waitFor("ENG.filled && !document.getElementById('lyCols').checked", 60000);
    const s = await p.eval(`({ routes: document.getElementById('lyRoutes').checked, flood: document.getElementById('lyFlood').checked, cols: document.getElementById('lyCols').checked, muni: VS.muni, hash: location.hash })`);
    check(tag('3D bogus link'), 'what reads is applied (routes, flood), the rest ignored: no columns, no card', s.routes && s.flood && !s.cols && s.muni === null, s);
    check(tag('3D bogus link'), 'the parts it cannot use stay in the address (e=, later=)', /e=no_such_dataset\.f/.test(s.hash) && /later=1/.test(s.hash), s.hash);
    const e = errors(p); check(tag('3D bogus link'), 'a clean console', e.length === 0, e);
  } finally { await p.close(); }
}

// ── Review of #97 ──
//  5. Names of Object.prototype as the municipality, s=, e= and layer keys, on both views: no error, no measure, no columns, the key kept in the address.
//  6. 3D, "Turn all off" then Undo on a link with three Economy layers (one the columns do not draw): s=, e= and ey= come back exactly, also after a change
//     of the columns' year first.
async function review(lang) {
  const tag = (s) => `${lang} ${s}`;
  for (const h of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) {
    const hash = `#${h}&s=${h}&e=${h}.f&l=${h},routes&${h}=1`;
    let p = await openPage(`${base}/3d.html?lang=${lang}${hash}`, { width, height: 900, noCache: true });
    try {
      check(tag(`3D ${h}`), 'ready', await p.waitFor(READY + ' && VS.ready', 90000));
      await p.waitFor(`!document.getElementById('lyCols').checked && (!ENG.fromAddress || ENG.filled)`, 60000); await sleep(800);
      const s = await p.eval(`({ cols: document.getElementById('lyCols').checked, metricKey, routes: document.getElementById('lyRoutes').checked, muni: VS.muni, hash: location.hash })`);
      check(tag(`3D ${h}`), 'no measure, no columns, no card; routes applied; the unknown key kept', !s.cols && s.metricKey === '' && s.routes && s.muni === null && s.hash.includes(`${h}=1`), s);
      const e = errors(p); check(tag(`3D ${h}`), 'a clean console', e.length === 0, e);
    } finally { await p.close(); }
    p = await openPage(`${base}/index.html?lang=${lang}${hash}`, { width, height: 900, noCache: true });
    try {
      check(tag(`2D ${h}`), 'ready', await p.waitFor(READY, 90000)); await sleep(1500);
      const s = await p.eval(`({ choro: document.getElementById('choro').value, routes: document.getElementById('lyRoutes').checked, sel: S.selected || null })`);
      check(tag(`2D ${h}`), 'no shading, no selection; routes applied', s.choro === '' && s.routes && !s.sel, s);
      const e = errors(p); check(tag(`2D ${h}`), 'a clean console', e.length === 0, e);
    } finally { await p.close(); }
  }
  // second review of #97: Undo of Turn all off keeps the raw text of s= and e= (a broken % threw in the snapshot; a decoded %26 planted keys)
  for (const [what, extra, key, raw] of [['a broken %', '&s=%ZZ', 's', '%ZZ'], ['an s= with %26', '&s=x%26ask%3Dhello%26c%3D0,0,1', 's', 'x%26ask%3Dhello%26c%3D0,0,1'],
    ['an e= with %26', '&e=x%26e%3Dplanted.f%26c%3D0,0,1', 'e', 'x%26e%3Dplanted.f%26c%3D0,0,1']]) {
    const T4 = tag(`3D Undo, ${what}`);
    const p = await openPage(`${base}/3d.html?lang=${lang}#c=18.21,-67.14,12&l=muni,flood${extra}`, { width, height: 900, noCache: true });
    try {
      check(T4, 'ready', await p.waitFor(READY + ' && VS.ready', 90000));
      await p.waitFor('!map.isMoving() && (!ENG.fromAddress || ENG.filled)', 60000); await sleep(900);
      await p.eval(`document.getElementById('alChip').click(), 1`); await p.waitFor(`!!document.querySelector('#alPanel .al-all')`, 10000);
      await p.eval(`document.querySelector('#alPanel .al-all').click(), 1`); await sleep(900);
      check(T4, 'Turn all off works (flood off)', await p.eval(`!document.getElementById('lyFlood').checked`));
      await p.eval(`document.getElementById('toastAct').click(), 1`); await sleep(1500);
      const s = await p.eval(`(() => { const P = Core.viewstate.parse(location.hash); return { raw: P.raw.${key}, keys: Object.keys(P.raw), c: P.c, link: document.querySelector('.views a[href^="index.html"]').getAttribute('href'), flood: document.getElementById('lyFlood').checked }; })()`);
      check(T4, `Undo: flood back, ${key}= exactly as it came, no key planted in the address or the 2D link`, s.flood && s.raw === raw && !s.keys.includes('ask') && s.keys.filter(k => k === 'e' || k === 'c').length === (key === 'e' ? 2 : 1) && s.c && s.c.lat === 18.21
        && !/[&#]ask=|[&#]e=planted|c=0,0,1/.test(s.link), s);
      const e = errors(p); check(T4, 'a clean console', e.length === 0, e);
    } finally { await p.close(); }
  }
  // third review of #97: the chip's x and "Turn all off" fire change events that do not bubble; the address and the 2D link must follow them at once, on
  // both views, and Undo must give back what was on
  for (const view of ['3d', '2d']) {
    const TC = tag(`${view.toUpperCase()} chip`), page = view === '3d' ? '3d.html' : 'index.html', other = view === '3d' ? 'index.html' : '3d.html';
    const p = await openPage(`${base}/${page}?lang=${lang}#c=18.21,-67.14,12&l=muni,flood,stops`, { width, height: 900, noCache: true });
    // the l= tokens of the data layers on (not "-key", not the 3D scene's settings) in the address and in the link to the other view
    const ON = `(() => { const on = (h) => (Core.viewstate.parse(h).l || []).filter(t => !t.startsWith('-') && !['terrain', 'buildings'].includes(t)).sort().join();
      const a = document.querySelector('.views a[href^="${other}"]'), href = a ? a.getAttribute('href') : ''; return JSON.stringify([on(location.hash), on(href.slice(href.indexOf('#')))]); })()`;
    const settle = async (want, what) => { const ok = await p.waitFor(`${ON} === ${JSON.stringify(JSON.stringify([want, want]))}`, 10000, 100); check(TC, what, ok, await p.eval(ON)); };
    try {
      check(TC, 'ready', await p.waitFor(READY + (view === '3d' ? ' && VS.ready' : ''), 90000));
      await p.waitFor('!map.isMoving()', 20000);
      const start = view === '3d' ? 'flood,muni,stops,trips' : 'flood,muni,stops';   // 3D: its vehicles on by default (a layer of one view); its routes off (a layer of both views the link does not name)
      await settle(start, 'the address and the link to start with');
      await p.eval(`document.getElementById('alChip').click(), 1`); await p.waitFor(`!!document.querySelector('#alPanel .al-x[data-id="lyFlood"]')`, 10000);
      await p.eval(`document.querySelector('#alPanel .al-x[data-id="lyFlood"]').click(), 1`);
      const afterX = start.replace('flood,', '');
      await settle(afterX, 'the x on flood zones: the address and the link drop flood at once');
      await p.waitFor(`!!document.querySelector('#alPanel .al-all')`, 10000);
      await p.eval(`document.querySelector('#alPanel .al-all').click(), 1`);
      await settle('muni', 'Turn all off: l= keeps only the municipal lines, in the address and the link');
      await p.eval(`document.getElementById('toastAct').click(), 1`);
      await settle(afterX, 'Undo: the layers back, in the address and the link');
      const e = errors(p); check(TC, 'a clean console', e.length === 0, e);
    } finally { await p.close(); }
  }
  // a broken % in the address of the WCRP and Data management pages names no section, and throws nothing
  for (const page of ['wcrp.html', 'data-management.html']) {
    const p = await openPage(`${base}/${page}?lang=${lang}#%`, { width, height: 900, noCache: true });
    try {
      check(tag(`${page} #%`), 'ready', await p.waitFor(READY, 60000)); await sleep(1500);
      const e = errors(p); check(tag(`${page} #%`), 'a clean console (no URIError)', e.length === 0, e);
    } finally { await p.close(); }
  }
  // an old r= link: the planned route's fit moves the camera; the address follows once it ends
  {
    const p = await openPage(`${base}/3d.html?lang=${lang}#c=18.43,-66.08,12&r=18.4655,-66.1057;18.4000,-66.0500`, { width, height: 900, noCache: true });
    try {
      check(tag('3D r= link'), 'ready', await p.waitFor(READY + ' && VS.ready', 90000));
      // the fit starts 1 to 9 s after ready on a slow machine: wait for it to move the camera, then poll until c= says where it rests (no fixed sleeps)
      check(tag('3D r= link'), 'the fit of the route moves the camera', await p.waitFor('Math.abs(map.getZoom() + 1 - 12) > 0.05', 30000, 200));
      const SAME = `(() => { const c = Core.viewstate.parse(location.hash).c, z = map.getZoom() + 1, m = map.getCenter(); return !map.isMoving() && !!c && Math.abs(c.z - z) <= 0.01 && Math.abs(c.lat - m.lat) <= 0.0001 && Math.abs(c.lng - m.lng) <= 0.0001; })()`;
      const ok = await p.waitFor(SAME, 30000, 250), s = await p.eval(`({ c: Core.viewstate.parse(location.hash).c, z: map.getZoom() + 1, lat: map.getCenter().lat, lng: map.getCenter().lng })`);
      check(tag('3D r= link'), 'c= is the camera after the fit of the route', ok, s);
    } finally { await p.close(); }
  }
  // a ramp named "constructor" in an Economy token (palettes.ramp by own names): the layer draws in blue, no error
  {
    const p = await openPage(`${base}/index.html?lang=${lang}#c=18.2,-66.5,9&e=qcew_jobs.f.per1000.constructor.q.1.1.0.85.0`, { width, height: 900, noCache: true });
    try {
      check(tag('2D ramp constructor'), 'ready, the Economy layer on', await p.waitFor(READY + ` && typeof ECON === 'object' && ECON.api.state().layers.length === 1`, 90000));
      check(tag('2D ramp constructor'), 'the address names the ramp drawn (blue), not "constructor"', await p.waitFor(`/[&#]e=qcew_jobs\\.f\\.per1000\\.blue\\./.test(decodeURIComponent(location.hash))`, 15000), await p.eval('location.hash'));
      const e = errors(p); check(tag('2D ramp constructor'), 'a clean console', e.length === 0, e);
    } finally { await p.close(); }
  }
  const link = '#Mayag%C3%BCez&c=18.21,-67.14,12&l=muni,flood,stops&e=qcew_jobs.f.per1000.blue.q.1.1.0.85.0%2Cqcew_private_jobs.f.per1000.green.q.1.1.0.85.0%2Cqcew_gov_jobs.s.value.gold.q.1.1.0.75.0&ey=2019&bm=liberty';
  for (const year of [null, 2020]) {
    const T3 = tag(`3D Undo${year ? ' after a change of year' : ''}`);
    const p = await openPage(`${base}/3d.html?lang=${lang}${link}`, { width, height: 900, noCache: true });
    try {
      check(T3, 'ready, the columns drawn', await p.waitFor(READY + ` && VS.ready && ENG.filled && metricKey === '__any'`, 90000));
      if (year) { await p.eval(`(() => { const s = document.getElementById('engY'); s.value = '${year}'; s.dispatchEvent(new Event('change')); return 1; })()`); }
      await p.waitFor('!map.isMoving()', 20000); await sleep(900);
      const keys = `JSON.stringify((({ s, e, ey }) => ({ s, e, ey }))(Core.viewstate.parse(location.hash)))`, before = await p.eval(keys);
      await p.eval(`document.getElementById('alChip').click(), 1`); await p.waitFor(`!!document.querySelector('#alPanel .al-all')`, 10000);
      await p.eval(`document.querySelector('#alPanel .al-all').click(), 1`); await sleep(900);
      const off = await p.eval(keys);
      check(T3, 'Turn all off takes the columns\' keys out', JSON.parse(off).e === null, off);
      await p.eval(`document.getElementById('toastAct').click(), 1`); await sleep(1500);
      const after = await p.eval(keys);
      check(T3, 'Undo gives back s=, e= and ey= exactly (the layer the columns do not draw included)', after === before, [before, after]);
      if (year) check(T3, 'the changed year kept', JSON.parse(after).ey === year, after); else check(T3, 'the three tokens whole', /qcew_private_jobs\.f\.per1000\.green/.test(JSON.parse(after).e), after);
      const e = errors(p); check(T3, 'a clean console', e.length === 0, e);
    } finally { await p.close(); }
  }
}

(async () => {
  for (const lang of langs) { console.log(`\n${lang}`); await run(lang); await review(lang); }
  console.log(`\n${passed} passed, ${problems.length} failed`);
  problems.forEach(x => console.log('  - ' + x));
  process.exit(problems.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
