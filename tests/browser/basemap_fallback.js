// The base map's fallback (site/js/core/basemap.js, site/js/twin3d.js, docs/basemap.md section 4), in a real browser, with the provider (openfreemap.org) blocked.
// On the 2D map (index.html), the WCRP page (wcrp.html) and the 3D view (3d.html), in each language:
//  - openfreemap.org blocked: the page gets ready; the map is on its plain background; the notice shows in the page's language; the data layers are drawn; no base-map
//    credit stays in the credit box; no request goes to tile.openstreetmap.org; a clean console;
//  - 3D only: the vector tiles blocked after the style has loaded (the base map's layers are hidden, the data stay); the provider never answering (the style waits,
//    then the 30 s rule switches to the plain style); nothing blocked (the base map draws, with its credits once, and no notice); every vector tile on a host
//    that does not exist (the TileJSON rewritten, tests/browser/tilejson.js), at 1400 x 900 and 390 px: hidden within about 6 s of the first failed tile;
//  - with a second Chrome started with WebGL off (its port as the fourth argument): the 2D and WCRP maps go on with the WebGL notice; the 3D view says it cannot draw
//    and throws nothing but its own stop ("WebGL unavailable").
// Requests are blocked in the page and in its workers (tests/browser/cdp.js): MapLibre fetches its tiles in web workers.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   chrome --headless=new --remote-debugging-port=<port> --user-data-dir=<another scratch folder> --no-first-run --disable-webgl --disable-3d-apis
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/basemap_fallback.js [base URL, default http://127.0.0.1:8041] [langs, default es,en] [pages, default 2d,wcrp,3d] [WebGL-off Chrome port] [screenshots folder]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const { rewriteTileJson } = require('./tilejson.js');
const B = require('../../site/js/core/basemap.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(','), pages = (process.argv[4] || '2d,wcrp,3d').split(',');
const noGlPort = +process.argv[5] || 0, shots = process.argv[6];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (tag, what, ok, detail) => { if (ok) passed++; else problems.push(`${tag}: ${what}`); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${tag}: ${what}${ok || detail === undefined ? '' : '  ' + JSON.stringify(detail).slice(0, 600)}`); return ok; };
const shot = async (p, name) => { if (!shots) return; fs.mkdirSync(shots, { recursive: true }); const r = await p.send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(r.data, 'base64')); };
const READY = "performance.getEntriesByName('ready').length > 0";
const BLOCK = ['*openfreemap.org*'];
// the console: errors and exceptions, less the browser's own line for each blocked request (a blocked request is the test, not a fault of the page)
const consoleErrors = (logs, allow = []) => logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon/.test(l.text + (l.url || ''))
  && !/ERR_BLOCKED_BY_CLIENT/.test(l.text) && !allow.some(re => re.test(l.text)));
const noOsm = (p) => !p.failed().concat(p.bad).some(r => /tile\.openstreetmap\.org/.test(r.url));
// the base map's own notice over the map (core/basemap.js notice, since PR #92), not the page's message bar, which may hold an Undo
const toastSays = (re) => `(() => [...document.querySelectorAll('.bm-notice')].some(t => ${re}.test(t.textContent)))()`;
const NOTICE_TEXT = "[...document.querySelectorAll('.bm-notice')].map(t => t.textContent).join(' | ')";
const THREE_NOTICE = { es: /No se pudo cargar el mapa base\. Se muestran los datos sobre un fondo liso\./, en: /The base map could not be loaded\. Showing the data on a plain background\./ };
// the pixels the data layers paint on a Leaflet map's canvas renderers (both pages draw their areas and points on canvas), and its SVG shapes and markers
const INK = `const ink = (m) => [...m.querySelectorAll('.leaflet-pane canvas')].reduce((n, c) => { try { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 16) if (d[i]) n++; } catch (e) { /* no 2d context */ } return n; }, 0)
  + m.querySelectorAll('.leaflet-overlay-pane path, .leaflet-marker-pane > *').length;`;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// ── the 2D map ──
async function twoD(lang, opts, tag, why) {
  const p = await openPage(`${base}/index.html?lang=${lang}`, { width: 1400, height: 900, noCache: true, ...opts });
  check(tag, 'the page gets ready', await p.waitFor(READY, 60000));
  check(tag, 'the notice in the page\'s language', await p.waitFor(toastSays(new RegExp(esc(B.TEXT[why][lang]))), 30000), await p.eval(NOTICE_TEXT));
  const s = await p.eval(`(() => { ${INK} const m = document.getElementById('map'), at = m.querySelector('.leaflet-control-attribution'), st = at && at.querySelector('.bm-status.off');
    return { off: m.dataset.basemap, bg: getComputedStyle(m).backgroundColor, gl: !!m.querySelector('.leaflet-gl-layer:not([style*="display: none"])'),
      paths: ink(m), status: st && st.textContent, title: st && st.title, credit: at ? at.innerHTML : '' }; })()`);
  check(tag, 'the plain background, with no base map drawn', s.off === 'off' && s.bg === 'rgb(217, 230, 238)' && !s.gl, s);
  check(tag, 'the credit box says so, in the page\'s language', s.status === B.TEXT.off[lang] && s.title === B.TEXT[why][lang], s);
  check(tag, 'no base-map credit stays', !/openfreemap\.org|openmaptiles\.org/.test(s.credit), s.credit);
  check(tag, 'the data layers are drawn (the municipalities)', s.paths > 1000, s.paths);
  check(tag, 'no request to tile.openstreetmap.org', noOsm(p));
  const e = consoleErrors(p.logs); check(tag, 'a clean console', e.length === 0, e);
  await shot(p, `2d_${tag.replace(/\W+/g, '_')}`);
  await p.close();
}

// ── the WCRP page (the Social Capital map; the vulnerability map loads on approach) ──
async function wcrp(lang, opts, tag, why) {
  const p = await openPage(`${base}/wcrp.html?lang=${lang}`, { width: 1400, height: 900, noCache: true, ...opts });
  check(tag, 'the page gets ready', await p.waitFor(READY, 60000));
  const off = await p.waitFor("document.querySelector('#scMap').dataset.basemap === 'off'", 40000);
  await p.eval("document.querySelector('#vulnerability').scrollIntoView()");
  const vOff = await p.waitFor("!!document.querySelector('.leaflet-container[data-basemap=\"off\"]:not(#scMap)')", 40000);
  await sleep(500);
  const s = await p.eval(`(() => { ${INK} return [...document.querySelectorAll('.leaflet-container')].map(m => { const at = m.querySelector('.leaflet-control-attribution'), st = at && at.querySelector('.bm-status.off');
    return { id: m.id, off: m.dataset.basemap, bg: getComputedStyle(m).backgroundColor, data: ink(m),
      status: st && st.textContent, title: st && st.title, credit: at ? at.innerHTML : '' }; }); })()`);
  check(tag, 'both maps on the plain background', off && vOff && s.length >= 2 && s.every(m => m.off === 'off' && m.bg === 'rgb(238, 243, 246)'), s.map(m => [m.id, m.off, m.bg]));
  check(tag, 'each credit box says so, in the page\'s language', s.every(m => m.status === B.TEXT.off[lang] && m.title === B.TEXT[why][lang]), s.map(m => [m.status, m.title]));
  check(tag, 'no base-map credit stays', s.every(m => !/openfreemap\.org|openmaptiles\.org/.test(m.credit)), s.map(m => m.credit));
  check(tag, 'the data layers are drawn on both maps', await p.waitFor("!!document.querySelector('#scLegend b')", 10000) && s.every(m => m.data > 100), s.map(m => [m.id, m.data]));
  check(tag, 'no request to tile.openstreetmap.org', noOsm(p));
  const e = consoleErrors(p.logs); check(tag, 'a clean console', e.length === 0, e);
  await shot(p, `wcrp_${tag.replace(/\W+/g, '_')}`);
  await p.close();
}

// ── the 3D view ──
const S3 = `(() => { const st = map.getStyle(), at = document.querySelector('.maplibregl-ctrl-attrib-inner'), base = st.layers.filter(l => !l.id.startsWith('bm-watch-')).filter(l => /^(openmaptiles|ne2_shaded)$/.test(l.source) || (st.sources[l.source] && /openfreemap/.test(JSON.stringify(st.sources[l.source]))));
  const drawn = (ids) => { try { return map.queryRenderedFeatures({ layers: ids.filter(id => map.getLayer(id)) }).length; } catch (e) { return -1; } };
  return { why: BM.why, bg: (st.layers[0] || {}).id === 'bg' ? st.layers[0].paint['background-color'] : null, nBase: base.length, baseShown: base.filter(l => (l.layout || {}).visibility !== 'none').map(l => l.id).slice(0, 5),
    muni: drawn(['muni-hit']), routes: drawn(['routes-line', 'routes-inferred', 'routes-approx', 'routes-ferry']), terrain: !!map.getTerrain(), credit: at ? at.innerHTML : '', loader: document.getElementById('loader').className }; })()`;
async function threeD(lang, opts, tag, expect) {
  const p = await openPage(opts.url || `${base}/3d.html?lang=${lang}`, { width: opts.width || 1400, height: 900, noCache: true, ...opts });
  if (opts.hang) {   // the provider never answers: its requests are held, never sent on
    await p.send('Fetch.enable', { patterns: [{ urlPattern: '*openfreemap.org*' }] });
    await p.send('Page.navigate', { url: `${base}/3d.html?lang=${lang}` });
  }
  let tj = null;
  if (opts.badHost) {   // the TileJSON answered with its tiles on a host that does not exist: every vector tile fails at once
    tj = await rewriteTileJson(p, 'https://tiles.no-such-host.invalid/{z}/{x}/{y}.pbf');
    await p.send('Page.navigate', { url: `${base}/3d.html?lang=${lang}` });
  }
  const t0 = Date.now();
  if (opts.badHost) {   // the time from the rewritten TileJSON (no tile can fail before it; on a host that does not exist they fail at once) to the base map hidden
    const hid = await p.waitFor('BM.off', 60000, 100);
    const sec = tj.time ? (Date.now() - tj.time) / 1000 : -1;
    check(tag, `hidden within about 6 s of the first failed tile (${sec.toFixed(1)} s after the TileJSON; why: ${JSON.stringify(await p.eval('BM.why'))})`, hid && sec >= 0 && sec < 9, sec);
  }
  if (expect !== 'on') check(tag, 'the notice in the page\'s language', await p.waitFor(toastSays(THREE_NOTICE[lang]), opts.hang ? 50000 : 30000), await p.eval(NOTICE_TEXT));
  check(tag, 'the page gets ready', await p.waitFor(READY, opts.hang ? 60000 : 90000), await p.eval("(document.getElementById('loaderText')||{}).textContent"));
  if (opts.hang) check(tag, 'it waited for the style about 30 s, not for ever', (Date.now() - t0) > 25000 && (Date.now() - t0) < 55000, (Date.now() - t0) / 1000);
  await p.waitFor("map.loaded() && map.areTilesLoaded()", 20000); await sleep(1500);
  const s = await p.eval(S3);
  if (expect === 'plain') check(tag, 'the plain style, with no base-map layer', s.bg === B.FALLBACK_BG && s.nBase === 0, s);
  if (expect === 'hidden') check(tag, 'the base map\'s layers are hidden, the style kept', s.nBase > 0 && s.baseShown.length === 0, s);
  if (expect === 'on') {
    check(tag, 'the base map is drawn', s.nBase > 0 && s.baseShown.length > 0, s);
    check(tag, 'no notice', !(await p.eval(toastSays(THREE_NOTICE[lang]))));
    const n = (re) => (s.credit.match(re) || []).length;
    check(tag, 'the base-map credits show once, in the page\'s language', n(/openfreemap\.org/g) === 1 && n(/openmaptiles\.org/g) === 1 && n(/openstreetmap\.org\/copyright/g) === 1 && s.credit.includes(B.credits('3d', lang)), s.credit);
  } else check(tag, 'no base-map credit stays', !/openfreemap\.org|openmaptiles\.org/.test(s.credit), s.credit);
  check(tag, 'the terrain and the data layers are drawn (municipalities and routes)', s.terrain && s.muni > 0 && s.routes > 0, s);
  check(tag, 'no request to tile.openstreetmap.org', noOsm(p));
  const e = consoleErrors(p.logs); check(tag, 'a clean console', e.length === 0, e);
  await shot(p, `3d_${tag.replace(/\W+/g, '_')}`);
  await p.close();
}

async function noGl(lang) {   // a second Chrome with WebGL off
  const port = noGlPort, tag = `${lang} WebGL off`;
  if (pages.includes('2d')) await twoD(lang, { port }, `${tag} 2D`, 'webgl');
  if (pages.includes('wcrp')) await wcrp(lang, { port }, `${tag} WCRP`, 'webgl');
  if (pages.includes('3d')) {
    const p = await openPage(`${base}/3d.html?lang=${lang}`, { width: 1400, height: 900, noCache: true, port });
    await p.waitFor("document.getElementById('loader').classList.contains('error')", 30000); await sleep(3000);
    const t = await p.eval("document.getElementById('loaderText').textContent");
    check(`${tag} 3D`, 'it says the browser cannot draw the 3D map, in the page\'s language', lang === 'es' ? /WebGL no está disponible|no puede dibujar/.test(t) : /cannot draw the 3D map \(WebGL is unavailable\)/.test(t), t);
    const e = consoleErrors(p.logs, [/^Error: WebGL unavailable/]);
    check(`${tag} 3D`, 'nothing throws but its own stop (no ReferenceError from series3d.js or supply3d.js)', e.length === 0, e);
    await shot(p, `3d_${tag.replace(/\W+/g, '_')}`);
    await p.close();
  }
}

(async () => {
  for (const lang of langs) {
    console.log(`\n${lang}`);
    if (pages.includes('2d')) await twoD(lang, { block: BLOCK }, `${lang} 2D blocked`, 'provider');
    if (pages.includes('wcrp')) await wcrp(lang, { block: BLOCK }, `${lang} WCRP blocked`, 'provider');
    if (pages.includes('3d')) {
      await threeD(lang, { block: BLOCK }, `${lang} 3D blocked`, 'plain');
      await threeD(lang, { block: BLOCK, width: 390 }, `${lang} 3D blocked 390 px`, 'plain');
      await threeD(lang, { block: ['*openfreemap.org/planet/*', '*openfreemap.org/natural_earth/*'] }, `${lang} 3D tiles blocked after the style`, 'hidden');
      await threeD(lang, { hang: true, url: 'about:blank' }, `${lang} 3D provider never answers`, 'plain');
      await threeD(lang, {}, `${lang} 3D nothing blocked`, 'on');
      await threeD(lang, { badHost: true, url: 'about:blank' }, `${lang} 3D tiles on a host that does not exist`, 'hidden');
      await threeD(lang, { badHost: true, url: 'about:blank', width: 390 }, `${lang} 3D tiles on a host that does not exist, 390 px`, 'hidden');
    }
    if (noGlPort) await noGl(lang);
  }
  console.log(`\n${passed} passed, ${problems.length} failed`);
  problems.forEach(x => console.log('  - ' + x));
  process.exit(problems.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
