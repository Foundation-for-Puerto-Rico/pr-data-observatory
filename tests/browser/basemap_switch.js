// The base map switcher and the tile rules after a switch (docs/basemap.md), in a real browser.
//  1. 3D, a regression of the review of PR #92: stops on → no base map → stops off → Liberty. The counts on the clusters need the base map's fonts, so they are
//     dropped with no base map and added again with Liberty; they must come back hidden, as their clusters are, not drawn alone over the map. Then stops on again.
//  2. 3D, the review's case for the 6 s rule: the first vector tile fails and the others are held 7 s. The base map must stay (it used to hide at 6 s and stay off).
//     Again with the first three failing: tiles still in flight are not failures, so the rule waits for them.
//  3. 3D, every vector tile failing (a local server answers 500): the base map is hidden with its notice; a pick of "No base map" then takes the notice away and
//     resets BM.why; a pick of Liberty with the tiles answering draws the base map with its credits once.
//  4. 3D, every vector tile failing, then answering again: the base map comes back after a pan (its tiles arrive under the watch layer), with its credits once,
//     the buildings as their switch says, BM.why reset and the notice gone.
//  5. 2D: a pick whose style fails is not kept as the viewer's default and leaves the failure notice; a pick that loads is kept and takes the notice away.
// The TileJSON is rewritten through the DevTools protocol and the tiles come from a local server (tests/browser/tilejson.js) that passes them on from the provider.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=d3d11 --enable-gpu     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/basemap_switch.js [base URL, default http://127.0.0.1:8041] [cases, default 1,2,3,4,5] [tile server port, default 8097]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const { openPage } = require('./cdp.js');
const { rewriteTileJson, tileServer } = require('./tilejson.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', cases = (process.argv[3] || '1,2,3,4,5').split(','), tilePort = +process.argv[4] || 8097;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0; const check = (ok, what) => { console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) fails++; return ok; };
const READY = `document.getElementById('loader').classList.contains('hide') && !document.getElementById('basemap').disabled`;
const pick = (p, n) => p.eval(`(() => { const s = document.getElementById('basemap'); s.value = '${n}'; s.dispatchEvent(new Event('change')); return 1; })()`);
// the 3D base map now: off and why, the watched sources, the base layers drawn (the watch layers aside), the notice and the base-map credits in the credit box
const STATE = `(() => { const st = map.getStyle(), at = document.querySelector('.maplibregl-ctrl-attrib-inner'), credit = at ? at.innerHTML : '';
  const base = st.layers.filter(l => BM.base && BM.base.layers.has(l.id) && !l.id.startsWith('bm-watch-') && l.source);
  return { name: BM.name, off: BM.off, why: BM.why, watching: BM.watching, nBase: base.length, shown: base.filter(l => (l.layout || {}).visibility !== 'none').length,
    watch: st.layers.filter(l => l.id.startsWith('bm-watch-')).map(l => l.id), notice: [...document.querySelectorAll('.bm-notice')].map(n => n.textContent).join(' | '),
    osm: (credit.match(/openstreetmap\\.org\\/copyright/g) || []).length, ofm: (credit.match(/openfreemap\\.org/g) || []).length,
    buildings: map.getLayer('buildings-3d') ? (map.getLayoutProperty('buildings-3d', 'visibility') || 'visible') : 'absent', lyBuildings: document.getElementById('lyBuildings').checked }; })()`;
const state = (p) => p.eval(STATE);
const show = (s) => JSON.stringify(s).slice(0, 400);
// the console, less the lines for the tiles the test fails on purpose (the local tile server's 500s)
const errors = (p) => p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon|ERR_BLOCKED_BY_CLIENT|status of 500|127\.0\.0\.1:\d+\/t\//.test(l.text + (l.url || '')));

async function open3d(srv, mode, failFirst = 1) {   // a blank page, the TileJSON rewritten to the local server, then the 3D view on Liberty
  Object.assign(srv.st, { mode, failFirst, n: 0, failed: 0, held: 0, served: 0 });
  const p = await openPage('about:blank', { width: 1400, height: 900, noCache: true });
  await rewriteTileJson(p, (orig) => { srv.st.upstream = orig; return srv.url; });
  await p.send('Page.navigate', { url: `${base}/3d.html?lang=en#bm=liberty` });
  return p;
}

async function stopCounts() {
  console.log('\n1. 3D: stop counts after a switch');
  const p = await openPage(`${base}/3d.html?lang=en#bm=liberty`, { width: 1400, height: 900 });
  const vis = `JSON.stringify(['stops-cluster', 'stops-count', 'stops-pts'].map(id => map.getLayer(id) ? (map.getLayoutProperty(id, 'visibility') || 'visible') : 'absent'))`;
  try {
    check(await p.waitFor(READY, 90000), 'ready');
    await p.eval(`document.getElementById('lyStops').click(), 1`);
    check(await p.waitFor(`!!map.getLayer('stops-count') && !!map.getLayer('stops-cluster')`, 60000), 'stops on, with counts');
    await pick(p, 'none'); check(await p.waitFor(`BM.name === 'none' && !BM.busy`, 60000), 'no base map');
    check(await p.eval(vis) === JSON.stringify(['visible', 'absent', 'visible']), `counts dropped with no fonts (${await p.eval(vis)})`);
    await p.eval(`document.getElementById('lyStops').click(), 1`); await sleep(500);
    check(await p.eval(vis) === JSON.stringify(['none', 'absent', 'none']), `stops off (${await p.eval(vis)})`);
    await pick(p, 'liberty'); check(await p.waitFor(`BM.name === 'liberty' && !BM.busy`, 60000), 'Liberty');
    check(await p.eval(vis) === JSON.stringify(['none', 'none', 'none']), `the counts come back hidden with their clusters (${await p.eval(vis)})`);
    await p.waitFor('map.loaded()', 30000);
    const drawn = await p.eval(`map.queryRenderedFeatures({ layers: ['stops-count'] }).length`).catch(() => -1);
    check(drawn === 0, `no count drawn without its circle (${drawn})`);
    await p.eval(`document.getElementById('lyStops').click(), 1`); await sleep(800);
    check(await p.eval(vis) === JSON.stringify(['visible', 'visible', 'visible']), `stops on again: all shown (${await p.eval(vis)})`);
  } finally { await p.eval(`localStorage.removeItem('twin.basemap'), 1`).catch(() => {}); await p.close(); }
}

async function heldTiles(srv, failFirst) {
  console.log(`\n2. 3D: the first ${failFirst > 1 ? failFirst + ' vector tiles fail' : 'vector tile fails'}, the others are held 7 s (review of PR #92)`);
  const p = await open3d(srv, 'first-fails-rest-held', failFirst);
  try {
    const t0 = Date.now();
    while (Date.now() - t0 < 40000 && !srv.st.failed) await sleep(100);
    check(srv.st.failed >= 1, 'the first tile failed');
    const tFail = Date.now(); let hid = null;
    while (Date.now() - tFail < 8000) { const s = await state(p).catch(() => null); if (s && s.off) { hid = s; break; } await sleep(250); }
    check(!hid, `not hidden in the 8 s after the failure, while the other tiles are held${hid ? ` (hidden at ${((Date.now() - tFail) / 1000).toFixed(1)} s: ${show(hid)})` : ''}`);
    check(await p.waitFor(READY, 60000), 'ready');
    check(await p.waitFor('map.loaded() && map.areTilesLoaded()', 30000), 'the held tiles arrived');
    await sleep(1500);
    const s = await state(p);
    check(!s.off && s.shown > 0 && s.why === null && !s.notice && s.watch.length === 0, `the base map is drawn, with no notice (${show(s)}; tiles: ${JSON.stringify(srv.st).slice(0, 200)})`);
    check(s.osm === 1 && s.ofm === 1, `its credits once (${s.osm}, ${s.ofm})`);
    const e = errors(p); check(e.length === 0, `a clean console ${JSON.stringify(e).slice(0, 300)}`);
  } finally { await p.close(); }
}

async function allFailThenNone(srv) {
  console.log('\n3. 3D: every vector tile fails; then "No base map", then Liberty with the tiles answering');
  const p = await open3d(srv, 'fail');
  try {
    check(await p.waitFor(READY, 90000), 'ready');
    check(await p.waitFor('BM.off', 30000), 'the base map is hidden');
    let s = await state(p);
    check(s.shown === 0 && /could not be loaded/.test(s.notice) && s.osm === 0 && s.ofm === 0 && Array.isArray(s.why) && s.why[0] === 'tiles', `hidden, with the notice and no base-map credits (${show(s)})`);
    check(s.watching && s.watching.includes('openmaptiles') && s.watch.includes('bm-watch-openmaptiles'), `its vector source is watched (${s.watching})`);
    await pick(p, 'none'); check(await p.waitFor(`BM.name === 'none' && !BM.busy`, 30000), 'no base map picked');
    s = await state(p);
    check(!s.notice, `the switch took the pending notice away (${s.notice})`);
    check(s.why === null && s.off === false && s.watching === null, `BM.why reset (${show(s)})`);
    srv.st.mode = 'proxy';
    await pick(p, 'liberty'); check(await p.waitFor(`BM.name === 'liberty' && !BM.busy`, 60000), 'Liberty picked, the tiles answering');
    await p.waitFor('map.loaded() && map.areTilesLoaded()', 30000); await sleep(1500);
    s = await state(p);
    check(!s.off && s.shown > 0 && !s.notice && s.watch.length === 0 && s.osm === 1 && s.ofm === 1, `the base map is drawn, its credits once, no notice (${show(s)})`);
    check(await p.eval(`localStorage.getItem('twin.basemap')`) === 'liberty', 'the pick is kept once in');
    const e = errors(p); check(e.length === 0, `a clean console ${JSON.stringify(e).slice(0, 300)}`);
  } finally { await p.eval(`localStorage.removeItem('twin.basemap'), 1`).catch(() => {}); await p.close(); }
}

async function allFailThenBack(srv) {
  console.log('\n4. 3D: every vector tile fails, then the provider answers again');
  const p = await open3d(srv, 'fail');
  try {
    check(await p.waitFor(READY, 90000), 'ready');
    check(await p.waitFor('BM.off && !!BM.watching', 30000), 'the base map is hidden and its source watched');
    srv.st.mode = 'proxy';
    await p.eval(`map.jumpTo({ center: [-66.62, 18.01], zoom: Math.min(map.getZoom() + 1.5, 13) }), 1`);   // Ponce: tiles not asked for yet
    check(await p.waitFor('!BM.off', 30000), 'tiles arrive: the base map comes back');
    await p.waitFor('map.loaded() && map.areTilesLoaded()', 30000); await sleep(1500);
    const s = await state(p);
    check(s.shown > 0 && s.why === null && !s.notice && s.watch.length === 0 && s.watching === null, `drawn, BM.why reset, the notice gone, no watch layer (${show(s)})`);
    check(s.osm === 1 && s.ofm === 1, `its credits back, once (${s.osm}, ${s.ofm})`);
    check(s.buildings === (s.lyBuildings ? 'visible' : 'none'), `the buildings as their switch says (${s.buildings})`);
    const e = errors(p); check(e.length === 0, `a clean console ${JSON.stringify(e).slice(0, 300)}`);
  } finally { await p.close(); }
}

async function twoDKeep() {
  console.log('\n5. 2D: a pick is kept only once its style has loaded; a style that loads takes the failure notice away');
  const p = await openPage(`${base}/index.html?lang=en`, { width: 1400, height: 900, noCache: true });
  try {
    await p.eval(`localStorage.removeItem('twin.basemap'), 1`);
    check(await p.waitFor(`!!bmH && bmH.state === 'on' && !document.getElementById('basemap').disabled`, 90000), 'ready, Positron on');
    await p.send('Network.setBlockedURLs', { urls: ['*openfreemap.org/styles/liberty*'] });
    await pick(p, 'liberty');
    check(await p.waitFor(`bmH.state === 'off'`, 40000), 'the Liberty pick fails (its style blocked)');
    check(await p.eval(`localStorage.getItem('twin.basemap')`) === null, 'a failed pick is not kept');
    check(await p.eval(`!!document.querySelector('#map > .bm-notice')`), 'the failure notice shows');
    await p.send('Network.setBlockedURLs', { urls: [] });
    await pick(p, 'positron');
    check(await p.waitFor(`bmH.state === 'on'`, 40000), 'Positron loads');
    check(await p.eval(`localStorage.getItem('twin.basemap')`) === 'positron', 'the pick is kept once loaded');
    check(!(await p.eval(`!!document.querySelector('#map > .bm-notice')`)), 'the notice is gone');
    check(/bm=positron/.test(await p.eval('location.hash')), 'bm= in the address');
    const e = errors(p).filter(l => !/styles\/liberty|Failed to fetch/.test(l.text + (l.url || ''))); check(e.length === 0, `a clean console ${JSON.stringify(e).slice(0, 300)}`);
  } finally { await p.eval(`localStorage.removeItem('twin.basemap'), 1`).catch(() => {}); await p.close(); }
}

(async () => {
  const srv = await tileServer(tilePort);
  try {
    if (cases.includes('1')) await stopCounts();
    if (cases.includes('2')) { await heldTiles(srv, 1); await heldTiles(srv, 3); }
    if (cases.includes('3')) await allFailThenNone(srv);
    if (cases.includes('4')) await allFailThenBack(srv);
    if (cases.includes('5')) await twoDKeep();
  } finally { await srv.close(); }
  console.log(fails ? `FAILED ${fails}` : 'ALL OK'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
