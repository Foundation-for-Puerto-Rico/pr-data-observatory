// The OpenStreetMap feature inspector (site/js/core/osminspect.js; docs/basemap.md, section 8), in a real browser, on the 2D map and the 3D view, in Spanish
// and English, at 1400 and 390 px, over Old San Juan at zoom 17 on the Liberty style (it draws house numbers there):
//   - the toggle is reached and switched on with the keyboard (focus, Enter): aria-pressed, the bar over the map, the module and its Spanish loaded on first use;
//   - a click on a named place (its label) shows its kind, its name and its OSM link, the link built from the feature's tile ID (osm_id × 10 + type code);
//   - a click on a named road (the middle of its longest segment on screen) shows a road kind, its name and a way link (or the "zoom in" note when merged);
//   - house numbers are never shown: a click on one (in the tiles at zoom 19; neither style draws them) shows another layer or nothing, and no point of a 12 × 12 grid over the map describes a house number or a building;
//   - while it is on, the observatory's own click does nothing (2D: no municipality selected; 3D: no card); Esc leaves (focus back on the toggle on a wide screen),
//     and a click then does what it always did (2D: the municipality is selected; 3D: its card opens);
//   - "No base map" disables the toggle with its reason, and leaves the mode; the console stays clean;
//   - 2D (review of PR #99): with the mode on, the chip (mouse and Enter), "Turn all off" and its Undo and the Economy legend's toggle still work, and on a phone
//     the focus moves to the bar's Leave button, and Esc then moves it to the menu button.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=d3d11 --enable-gpu     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/osm_inspect.js [base URL, default http://127.0.0.1:8041] [views, default 2d,3d] [languages, default es,en] [widths, default 1400,390] [screenshots folder]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs');
const path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', views = (process.argv[3] || '2d,3d').split(','), langs = (process.argv[4] || 'es,en').split(','),
  widths = (process.argv[5] || '1400,390').split(',').map(Number), shots = process.argv[6] || null;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0, checks = 0; const check = (ok, what) => { checks++; console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) fails++; return ok; };
const KEYS = { Enter: 13, Escape: 27 };
async function key(p, k) {
  const o = { key: k, code: k, windowsVirtualKeyCode: KEYS[k] };
  await p.send('Input.dispatchKeyEvent', { type: 'keyDown', ...o, ...(k === 'Enter' ? { text: '\r' } : {}) });
  await p.send('Input.dispatchKeyEvent', { type: 'keyUp', ...o });
  await sleep(150);
}
async function click(p, x, y) { for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); await sleep(700); }
async function shot(p, name) {
  if (!shots) return;
  fs.mkdirSync(shots, { recursive: true });
  const r = await p.send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(r.data, 'base64'));
}
// In the page: the MapLibre map of the base map (2D: the bridge's), the box the clicks may land in (the map, less its controls, the bar and the edges), and
// the screen point of a lng/lat
const GL = (v) => v === '2d' ? `bmH.layer.getMaplibreMap()` : `map`;
const HELPERS = (v) => `const gl = ${GL(v)}, cv = gl.getCanvas().getBoundingClientRect(), mr = document.getElementById('map').getBoundingClientRect();
  const box = { l: mr.left + 70, r: mr.right - 70, t: mr.top + 90, b: mr.bottom - 110 };
  const scr = (c) => { const q = gl.project(c); return { x: cv.left + q.x, y: cv.top + q.y }; };
  const inBox = (s) => s.x > box.l && s.x < box.r && s.y > box.t && s.y < box.b;`;
// a named place label inside the box: its screen point, name and the link its tile ID gives
const PLACE = (v) => `(() => { ${HELPERS(v)}
  for (const f of gl.queryRenderedFeatures().filter(f => f.sourceLayer === 'place' && f.properties.name && f.geometry.type === 'Point')) {
    const s = scr(f.geometry.coordinates); if (!inBox(s)) continue;
    const t = { 1: 'node', 2: 'way', 3: 'relation' }[f.id % 10];
    return { x: s.x, y: s.y, name: f.properties.name, url: t ? 'https://www.openstreetmap.org/' + t + '/' + Math.floor(f.id / 10) : null };
  } return null; })()`;
// a named road: the middle of the longest segment on screen of a named transportation_name line inside the box
const ROAD = (v) => `(() => { ${HELPERS(v)}
  const cands = [];
  for (const f of gl.querySourceFeatures('openmaptiles', { sourceLayer: 'transportation_name' })) {
    if (!f.properties.name || !/^(primary|secondary|tertiary|minor|trunk)$/.test(f.properties.class)) continue;
    const lines = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.type === 'MultiLineString' ? f.geometry.coordinates : [];
    for (const line of lines) for (let i = 1; i < line.length; i++) {
      const a = scr(line[i - 1]), b = scr(line[i]), m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, len = Math.hypot(b.x - a.x, b.y - a.y);
      if (inBox(m)) cands.push({ x: m.x, y: m.y, len, name: f.properties.name });
    }
  }
  // the longest segment whose middle no other label covers (a place's or a point of interest's label on top is the topmost feature there, rightly)
  const clear = (c) => { const x = c.x - cv.left, y = c.y - cv.top; return !gl.queryRenderedFeatures([[x - 6, y - 6], [x + 6, y + 6]]).some(g => g.layer.type === 'symbol' && g.sourceLayer && !/^transportation/.test(g.sourceLayer)); };
  return cands.sort((a, b) => b.len - a.len).find(clear) || null; })()`;
const HOUSE = (v) => `(() => { ${HELPERS(v)}
  for (const f of gl.querySourceFeatures('openmaptiles', { sourceLayer: 'housenumber' }).filter(f => f.geometry.type === 'Point')) { const s = scr(f.geometry.coordinates); if (inBox(s)) return { x: s.x, y: s.y, n: f.properties.housenumber }; }
  return null; })()`;
// every point of a 12 × 12 grid over the box: what the inspector would show there
const GRID = (v) => `(() => { ${HELPERS(v)}
  const seen = {}; let n = 0;
  for (let i = 0; i < 12; i++) for (let j = 0; j < 12; j++) {
    const x = box.l + (box.r - box.l) * (i + .5) / 12 - cv.left, y = box.t + (box.b - box.t) * (j + .5) / 12 - cv.top, d = Core.osminspect.at(gl, { x, y });
    const k = d ? d.layer : 'nothing'; seen[k] = (seen[k] || 0) + 1; n++;
  } return { n, seen }; })()`;
const POP = `(() => { const e = document.querySelector('.osmi-popup .osmi'); if (!e) return null; const q = (s) => { const x = e.querySelector(s); return x ? x.textContent : null; };
  return { layer: e.dataset.layer, kind: q('.osmi-kind'), name: q('.osmi-name'), ref: q('.osmi-ref'), el: q('.osmi-el'), note: q('.osmi-note') || q('.osmi-none'), link: (e.querySelector('a.osmi-link') || {}).href || null,
    target: (e.querySelector('a.osmi-link') || {}).target || null, credit: !!e.querySelector('.osmi-credit a[href="https://www.openstreetmap.org/copyright"]') }; })()`;
const STATE = `(() => { const b = document.getElementById('osmInspect'), m = document.getElementById('map');
  return { pressed: b.getAttribute('aria-pressed'), disabled: b.disabled, on: m.dataset.inspect === 'on', bar: !!m.querySelector('.osmi-bar'), note: document.getElementById('osmInspectNote').textContent,
    focus: document.activeElement && document.activeElement.id, pops: document.querySelectorAll('.osmi-popup').length, glMarks: b.querySelectorAll('.gl-mark').length }; })()`;
// the panel (on a phone), its Layers tab and the layer group the toggle is in (the groups start folded)
const OPEN = `(() => { if (typeof setPanel === 'function') setPanel(true); const t = document.getElementById('t-layers'); if (t) t.click();
  const body = document.getElementById('osmInspect').closest('.fold-body'); if (body && body.hidden) { const h = document.querySelector('[aria-controls="' + body.id + '"]'); if (h) h.click(); } return 1; })()`;
const CLOSE = `document.querySelectorAll('.osmi-popup .leaflet-popup-close-button, .osmi-popup .maplibregl-popup-close-button').forEach(b => b.click()), 1`;
const LINK_RE = /^https:\/\/www\.openstreetmap\.org\/(node|way|relation)\/[1-9]\d*$/;

async function run(v, lang, width) {
  const label = `${v} ${lang} ${width}`;
  console.log(`\n${label}`);
  const page = v === '2d' ? 'index.html' : '3d.html', mobile = width < 700;
  const p = await openPage(`${base}/${page}?lang=${lang}#c=18.4655,-66.1100,17${v === '3d' ? '&b=0&p=0' : ''}&bm=liberty`, { width, height: mobile ? 800 : 900, mobile, noCache: true });
  try {
    check(await p.waitFor(`document.getElementById('loader').classList.contains('hide') && !document.getElementById('osmInspect').disabled`, 120000), 'ready, the toggle enabled once the base map is on');
    const s0 = await p.eval(STATE);
    check(s0.pressed === 'false' && !s0.on && s0.glMarks === 0, `off at first, no glossary mark in the toggle (${JSON.stringify(s0)})`);
    check(!(await p.eval(`!!(window.Core && Core.osminspect)`)), 'the module is not loaded before first use');
    // keyboard: open the Layers tab (and the panel on a phone), focus the toggle, Enter
    await p.eval(OPEN); await sleep(400);
    await p.eval(`document.getElementById('osmInspect').focus(), 1`);
    check(await p.eval(`document.activeElement.id`) === 'osmInspect', 'the toggle takes the focus');
    await key(p, 'Enter');
    check(await p.waitFor(`document.getElementById('map').dataset.inspect === 'on'`, 30000), 'Enter switches inspect mode on');
    const s1 = await p.eval(STATE);
    check(s1.pressed === 'true' && s1.bar, `aria-pressed true and the bar over the map (${JSON.stringify(s1)})`);
    check(await p.eval(`!!Core.osminspect && (I18N.lang === 'en' || T('View on OpenStreetMap') === 'Ver en OpenStreetMap')`), 'the module and its Spanish loaded on first use');
    if (mobile) check(await p.eval(`!document.body.classList.contains('panel-open') && (document.getElementById('panel') ? getComputedStyle(document.getElementById('panel')).visibility !== 'hidden' || true : true)`), 'on a phone the panel makes way for the map');
    await p.waitFor(`${GL(v)}.loaded()`, 60000); await sleep(500);
    const before = v === '2d' ? await p.eval(`S.selected || null`) : null;
    // a named place: one whose label is drawn clear of the panel and the map's controls; else the map is centred on one place after another until a label is drawn
    let pl = await p.eval(PLACE(v));
    const cands = await p.eval(`(() => { const gl = ${GL(v)}, is = (f) => f.properties.name && f.geometry.type === 'Point', seen = new Set();
      return [...gl.queryRenderedFeatures().filter(f => f.sourceLayer === 'place' && is(f)), ...gl.querySourceFeatures('openmaptiles', { sourceLayer: 'place' }).filter(is)]
        .filter(f => !seen.has(f.properties.name) && seen.add(f.properties.name)).slice(0, 6).map(f => f.geometry.coordinates); })()`);
    for (const c of pl ? [] : cands) {
      await p.eval(v === '2d' ? `map.panTo([${c[1]}, ${c[0]}], { animate: false }), 1` : `map.jumpTo({ center: [${c[0]}, ${c[1]}] }), 1`);
      await sleep(800); await p.waitFor(`${GL(v)}.loaded()`, 60000); await sleep(400);
      if ((pl = await p.eval(PLACE(v)))) break;
    }
    if (check(!!pl, `a named place in view (${pl && pl.name})`)) {
      await click(p, pl.x, pl.y);
      const pop = await p.eval(POP);
      check(pop && pop.layer === 'place' && pop.name === pl.name && !!pop.kind, `place: kind and name (${JSON.stringify(pop)})`);
      check(pop && pop.link === pl.url && LINK_RE.test(pop.link || '') && pop.target === '_blank', `place: the link from its tile ID (${pop && pop.link} = ${pl.url})`);
      check(pop && pop.credit, 'the OpenStreetMap credit, linked to its copyright page');
      check(pop && /\d/.test(pop.el || '') && (lang === 'es' ? /^Elemento de OSM: (nodo|vía|relación) \d+$/ : /^OSM element: (node|way|relation) \d+$/).test(pop.el), `the OSM element in the page's language (${pop && pop.el})`);
      await shot(p, `osmi_${v}_${lang}_${width}_place`);
    }
    if (v === '2d') check(await p.eval(`S.selected || null`) === before, 'while on, the click selects no municipality');
    else check(await p.eval(`document.querySelectorAll('.maplibregl-popup:not(.osmi-popup)').length`) === 0, 'while on, the click opens no card');
    // a named road
    await p.eval(CLOSE); await sleep(300);   // the place's pop-up would take the next click
    const rd = await p.eval(ROAD(v));
    if (check(!!rd, `a named road in view (${rd && rd.name})`)) {
      await click(p, rd.x, rd.y);
      const pop = await p.eval(POP);
      check(pop && /^transportation/.test(pop.layer) && !!pop.kind, `road: a road kind (${JSON.stringify(pop)})`);
      check(pop && pop.name === rd.name, `road: its name (${pop && pop.name} = ${rd.name})`);
      check(pop && (pop.link ? /\/way\/\d+$/.test(pop.link) && LINK_RE.test(pop.link) : /zoom|acerque/i.test(pop.note || '')), `road: a way link, or the zoom-in note (${pop && (pop.link || pop.note)})`);
      await shot(p, `osmi_${v}_${lang}_${width}_road`);
    }
    // house numbers
    await p.eval(CLOSE); await sleep(300);
    await p.eval(v === '2d' ? `map.setZoom(19, { animate: false }), 1` : `map.jumpTo({ zoom: 18 }), 1`);   // house numbers are drawn from zoom 17 of MapLibre (18 of Leaflet)
    await sleep(800); await p.waitFor(`${GL(v)}.loaded()`, 60000); await sleep(400);
    const hn = await p.eval(HOUSE(v));
    if (hn) {
      await click(p, hn.x, hn.y);
      const pop = await p.eval(POP);
      check(pop && pop.layer !== 'housenumber' && pop.name !== hn.n && pop.kind !== hn.n, `a click on house number ${hn.n} shows no house number (${JSON.stringify(pop)})`);
    } else check(false, 'a house number drawn in view');
    const grid = await p.eval(GRID(v), { timeout: 180000 });   // 144 queries: about 25 s in 3D on a pitched view
    check(!grid.seen.housenumber && !grid.seen.building && grid.n === 144, `grid: no house number or building described (${JSON.stringify(grid.seen)})`);
    // Esc leaves
    await key(p, 'Escape'); await sleep(400);   // Leaflet fades a pop-up out in 200 ms
    const s2 = await p.eval(STATE);
    check(!s2.on && s2.pressed === 'false' && !s2.bar && s2.pops === 0, `Esc leaves inspect mode and closes the pop-up (${JSON.stringify(s2)})`);
    if (!mobile) check(s2.focus === 'osmInspect', 'the focus goes back to the toggle');
    // the observatory's click, as before
    const mr = await p.eval(`(() => { const r = document.getElementById('map').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    if (v === '2d') { await click(p, mr.x, mr.y); check(await p.eval(`S.selected`) === 'San Juan', 'off: a click selects the municipality, as before'); }
    else { check(await p.waitFor(`(map.getContainer().dataset.inspect !== 'on')`, 2000), 'off'); await click(p, mr.x, mr.y); check(await p.waitFor(`document.querySelectorAll('.maplibregl-popup:not(.osmi-popup)').length === 1`, 5000), 'off: a click opens the municipality card, as before'); }
    check(await p.eval(`document.querySelectorAll('.osmi-popup').length`) === 0, 'off: no inspector pop-up');
    // no base map: the toggle is disabled with its reason, and the mode leaves
    await p.eval(OPEN); await sleep(300);
    await p.eval(`document.getElementById('osmInspect').click(), 1`);
    check(await p.waitFor(`document.getElementById('map').dataset.inspect === 'on'`, 5000), 'on again');
    await p.eval(`(() => { const s = document.getElementById('basemap'); s.value = 'none'; s.dispatchEvent(new Event('change')); return 1; })()`);
    check(await p.waitFor(`document.getElementById('osmInspect').disabled`, 30000), '"No base map" disables the toggle');
    const s3 = await p.eval(STATE);
    check(!s3.on && s3.pressed === 'false' && !s3.bar && (lang === 'es' ? /Active un mapa base/ : /Turn on a base map/).test(s3.note), `and leaves inspect mode, with its reason (${s3.note})`);
    const errs = p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon|ERR_BLOCKED_BY_CLIENT|AbortError/.test(l.text + (l.url || '')));
    check(!errs.length, `a clean console (${errs.map(l => l.text).slice(0, 3).join(' | ')})`);
  } finally { await p.close(); }
}

// 2D only (review of PR #99): while the mode is on, the controls inside the map's container keep working: the "layers on" chip (mouse and Enter), "Turn all
// off" and the Undo of its message, and the Economy legend's toggle; none of these clicks opens an inspector pop-up, and the mode stays on.
async function controls(lang, width) {
  console.log(`\n2d controls ${lang} ${width}`);
  const mobile = width < 700;
  const p = await openPage(`${base}/index.html?lang=${lang}#c=18.4655,-66.1100,15&l=stops&e=qcew_jobs.f&bm=liberty`, { width, height: mobile ? 800 : 900, mobile, noCache: true });
  const at = (sel) => p.eval(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e || !e.getClientRects().length) return null; const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
  const pops = () => p.eval(`document.querySelectorAll('.osmi-popup').length`);
  try {
    check(await p.waitFor(`document.getElementById('loader').classList.contains('hide') && !document.getElementById('osmInspect').disabled && !!document.getElementById('elToggle') && !document.getElementById('alWrap').hidden`, 120000), 'ready, with a layer on (the chip) and an Economy layer (its legend)');
    await p.eval(OPEN); await sleep(300);
    await p.eval(`document.getElementById('osmInspect').click(), 1`);
    check(await p.waitFor(`document.getElementById('map').dataset.inspect === 'on'`, 30000), 'inspect mode on');
    if (mobile) check(await p.eval(`document.activeElement && document.activeElement.closest('.osmi-bar') !== null`), 'on a phone the focus moves to the bar (the toggle is hidden in the closed panel)');
    await p.eval(CLOSE); await sleep(300);
    const chip = await at('#alChip');
    if (check(!!chip, 'the chip is shown')) {
      await click(p, chip.x, chip.y);
      check(await p.eval(`document.getElementById('alChip').getAttribute('aria-expanded')`) === 'true', 'a click opens the chip\'s list');
      check(await pops() === 0, 'no inspector pop-up');
      await click(p, chip.x, chip.y);
      check(await p.eval(`document.getElementById('alChip').getAttribute('aria-expanded')`) === 'false', 'a second click closes it');
      await p.eval(`document.getElementById('alChip').focus(), 1`); await key(p, 'Enter');
      check(await p.eval(`document.getElementById('alChip').getAttribute('aria-expanded')`) === 'true', 'Enter on the focused chip opens the list');
      check(await p.eval(`document.getElementById('map').dataset.inspect`) === 'on', 'Enter is not taken by the inspector: the mode stays on');
      const all = await at('#alPanel .al-all');
      if (check(!!all, '"Turn all off" in the list')) {
        await click(p, all.x, all.y);
        check(await p.waitFor(`!document.getElementById('lyStops').checked`, 5000), '"Turn all off" works');
        const undo = await at('#toastAct');
        if (check(!!undo, 'its message with Undo')) {
          await click(p, undo.x, undo.y);
          check(await p.waitFor(`document.getElementById('lyStops').checked`, 10000), 'Undo in the message works');
        }
      }
    }
    await p.eval(`(() => { const t = document.getElementById('alChip'); if (t && t.getAttribute('aria-expanded') === 'true') t.click(); return 1; })()`); await sleep(300);
    const el = await at('#elToggle');
    if (check(!!el, 'the Economy legend\'s toggle is shown')) {
      const before = await p.eval(`document.getElementById('elToggle').getAttribute('aria-expanded')`);
      await click(p, el.x, el.y);
      const after = await p.eval(`document.getElementById('elToggle') && document.getElementById('elToggle').getAttribute('aria-expanded')`);
      check(after !== before, `the legend's toggle works (${before} → ${after})`);
    }
    check(await pops() === 0 && await p.eval(`document.getElementById('map').dataset.inspect`) === 'on', 'no inspector pop-up from the controls, and the mode stays on');
    if (mobile) {   // Esc from the bar: the mode ends and the focus goes to the menu button (the toggle is in the closed, inert panel)
      await p.eval(`document.querySelector('.osmi-bar button').focus(), 1`); await key(p, 'Escape');
      check(await p.eval(`document.getElementById('map').dataset.inspect !== 'on' && document.activeElement && document.activeElement.id === 'menuBtn'`), 'on a phone, Esc leaves and the focus goes to the menu button');
    }
    const errs = p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon|ERR_BLOCKED_BY_CLIENT|AbortError/.test(l.text + (l.url || '')));
    check(!errs.length, `a clean console (${errs.map(l => l.text).slice(0, 3).join(' | ')})`);
  } finally { await p.close(); }
}

(async () => {
  for (const v of views) for (const lang of langs) for (const w of widths) await run(v, lang, w);
  if (views.includes('2d')) for (const lang of langs) for (const w of widths) await controls(lang, w);
  console.log(`\n${checks - fails}/${checks} checks passed`);
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
