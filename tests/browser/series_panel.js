// The time series panel of the 3D view (site/js/series3d.js), in a real browser, with real mouse clicks and keys (the review of PR #86):
//  - nothing of the panel loads at first: a click on land with the columns off opens the municipality's card, with a "Time series" link, and loads no dataset;
//  - the link opens the panel and loads the datasets then; the focus moves to the chart; on a desktop the card stays and the panel does not cover its links, on a phone
//    (390 px) the card closes and the panel stays inside the screen;
//  - an ACS dataset (the default, poverty_pct, B17001) shows its 5-year windows with the margin of error (90%): a band, the tooltip, the screen reader's text and the note;
//  - the key (the municipality's line and Puerto Rico's) shows at every width, inside the panel and clear of the title, the buttons and the chart (2026-10-27: it was hidden under 860 px);
//  - the keys: Home, End and the four arrows move the chart's year, Page Up and Page Down five years; the year chosen with the keys shows its tooltip inside the window
//    and the tooltip closes when the focus leaves; with the columns off the columns' year (ENG.y) stays as it was; "Latest" goes back to the latest year;
//  - Esc and the close button give the focus back to the link (desktop) or to the map (phone, where the card has closed);
//  - with the "Any dataset" columns on, a click on land opens the panel on a desktop only; a click on a flood zone over the sea (no municipality under it) and a click in the
//    route planner's pick mode open no panel; on a phone a click on the map closes it;
//  - a clean console, no Spanish missing and no sideways scroll.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/series_panel.js [base URL, default http://127.0.0.1:8041] [langs, default es,en] [widths, default 1400,390] [screenshots folder]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(','), widths = (process.argv[4] || '1400,390').split(',').map(Number), shots = process.argv[5];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
const view = (w) => ({ width: w, height: w < 500 ? 812 : 900, mobile: w < 500 });
const click = async (p, x, y) => { for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); };
const KEYS = { Home: 36, End: 35, ArrowLeft: 37, ArrowRight: 39, ArrowUp: 38, ArrowDown: 40, PageUp: 33, PageDown: 34, Escape: 27 };
const key = async (p, k) => { for (const type of ['keyDown', 'keyUp']) await p.send('Input.dispatchKeyEvent', { type, key: k, code: k, windowsVirtualKeyCode: KEYS[k] }); await sleep(250); };
const shot = async (p, name) => { if (!shots) return; fs.mkdirSync(shots, { recursive: true }); const r = await p.send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(r.data, 'base64')); };

// In the page: places on the screen found from the map (no fixed pixels)
const KIT = `window.__s = (() => {
  const R = () => document.getElementById('map').getBoundingClientRect();
  const ids = () => [...CLICKABLE.keys()].filter(id => map.getLayer(id));
  const onCanvas = (x, y) => { const r = R(), el = document.elementFromPoint(x + r.left, y + r.top); return x > 40 && y > 130 && x < r.width - 90 && y < r.height - 170 && !!el && el.classList.contains('maplibregl-canvas'); };
  const box = (el) => { const b = el.getBoundingClientRect(); return { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
  const meets = (a, b) => a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b;
  return {
    // bare land: a municipality under the pixel and nothing else that a click answers
    land() { const r = R(), L = ids(); for (let y = 150; y < r.height - 180; y += 23) for (let x = 60; x < r.width - 100; x += 23) { if (map.queryRenderedFeatures([x, y], { layers: L }).some(f => f.layer.id !== 'muni-hit' && f.layer.id !== 'muni-cols') || !onCanvas(x, y)) continue; const fs = map.queryRenderedFeatures([[x - 6, y - 6], [x + 6, y + 6]], { layers: L }); if (fs.length && fs.every(f => f.layer.id === 'muni-hit' || f.layer.id === 'muni-cols')) return { x: Math.round(x + r.left), y: Math.round(y + r.top), name: fs.find(f => f.layer.id === 'muni-hit') && fs.find(f => f.layer.id === 'muni-hit').properties.municipality }; } return null; },
    // a flood zone over the sea: the flood zone and no municipality under the pixel
    sea() { const r = R(), L = ids(); for (let y = 150; y < r.height - 180; y += 17) for (let x = 60; x < r.width - 100; x += 17) { const f0 = map.queryRenderedFeatures([x, y], { layers: ['flood-fill', 'muni-hit'] }); if (f0.length !== 1 || f0[0].layer.id !== 'flood-fill' || !onCanvas(x, y)) continue; const fs = map.queryRenderedFeatures([[x - 4, y - 4], [x + 4, y + 4]], { layers: L }); if (fs.length && fs.every(f => f.layer.id === 'flood-fill')) return { x: Math.round(x + r.left), y: Math.round(y + r.top), zone: fs[0].properties.FLD_ZONE }; } return null; },
    link() { const b = document.querySelector('.maplibregl-popup [data-series]'); if (!b) return null; const q = box(b); return { x: Math.round((q.l + q.r) / 2), y: Math.round((q.t + q.b) / 2), name: b.dataset.series }; },
    state() { const el = document.getElementById('series'), a = document.activeElement, pop = document.querySelector('.maplibregl-popup');
      const P = el.hidden ? null : box(el), links = pop && pop.querySelector('.links'), L = links && box(links);
      return { ...Series.state, shown: !el.hidden, loaded: !!ENG.E, engY: ENG.y, h: ENG.h, focus: a ? (a.id || (a.dataset && a.dataset.series ? 'link:' + a.dataset.series : a.className)) : '', pop: !!pop,
        svg: !!document.querySelector('#srChart svg'), band: document.querySelectorAll('#srChart .sr-band').length, note: (document.getElementById('srNote').hidden ? '' : document.getElementById('srNote').textContent),
        vt: document.getElementById('srChart').getAttribute('aria-valuetext') || '', latest: !document.getElementById('srLatest').hidden,
        keys: (() => { const k = el.querySelector('.sr-keys'); if (!P || !k || getComputedStyle(k).display === 'none') return null; const K = box(k), others = [el.querySelector('.sr-title'), el.querySelector('.sr-pills'), document.getElementById('srChart')].map(box);
          return { inPanel: K.l >= P.l && K.r <= P.r && K.t >= P.t && K.b <= P.b, clear: !others.some(o => meets(o, K)), fits: k.scrollWidth <= k.clientWidth + 1, name: document.getElementById('srKeyM').textContent, pr: document.getElementById('srKeyPr').textContent }; })(),
        tip: (() => { const t = document.querySelector('#tip.show'); if (!t) return null; const b = box(t); return { text: t.innerText.split(String.fromCharCode(10)).join(' '), inScreen: b.l >= 0 && b.r <= innerWidth && b.t >= 0 && b.b <= innerHeight }; })(),
        panel: P, inScreen: !P || (P.l >= 0 && P.r <= innerWidth && P.t >= 0 && P.b <= innerHeight), covers: !!(P && L && meets(P, L)), sideways: document.documentElement.scrollWidth > innerWidth }; },
    chartMid() { const q = box(document.getElementById('srChart')); return { x: Math.round((q.l + q.r) / 2), y: Math.round((q.t + q.b) / 2) }; },
    ys() { const D = ENG.E && ENG.E.V[ENG.h]; return D ? D.ys : []; },
    closeCards() { document.querySelectorAll('.maplibregl-popup').forEach(e => e.remove()); return 1; },
  };
})(), 1`;

async function settle(p, ms = 900) { await p.waitFor('map.loaded() && !map.isMoving()', 30000); await sleep(ms); }
async function jump(p, lng, lat, zoom) { await p.eval(`map.jumpTo({ center: [${lng}, ${lat}], zoom: ${zoom}, pitch: 0, bearing: 0 }), 0`); await settle(p); }
async function findLand(p) { for (const c of [[-66.10, 18.20, 11], [-66.45, 18.25, 11], [-66.70, 18.20, 11], [-65.95, 18.25, 11]]) { await jump(p, ...c); const q = await p.eval('__s.land()', { timeout: 120000 }); if (q) return q; } return null; }

async function run(lang, w) {
  const L = `${lang} ${w}`, phone = w < 700; console.log(L);
  const p = await openPage(`${base}/3d.html?lang=${lang}#c=18.2200,-66.3000,10`, view(w));
  try {
    check(await p.waitFor("document.querySelector('#loader.hide') && window.Series && window.__s === undefined", 90000), `${L}: ready`);
    await p.eval(KIT);
    if (w < 500) await p.eval('setPanel(false), 0');
    let s = await p.eval('__s.state()');
    check(!s.loaded && !s.shown, `${L}: no dataset of the panel loaded at first, panel closed`);
    // 1. land, columns off: the card with its link; no panel, nothing loaded
    let q = await findLand(p);
    if (!check(!!q, `${L}: bare land on the screen`)) return;
    await p.eval('__s.closeCards()'); await click(p, q.x, q.y); await p.waitFor('!!__s.link()', 8000); await sleep(300);
    s = await p.eval('__s.state()'); let link = await p.eval('__s.link()');
    check(s.pop && !!link && link.name === q.name, `${L}: a click on land opens ${q.name}'s card with a "Time series" link`);
    check(!s.shown && !s.loaded, `${L}: with the columns off the click opens no panel and loads no dataset`);
    // 2. the link opens the panel; the datasets load then
    await click(p, link.x, link.y); await sleep(400);
    const vt0 = await p.eval("ENG.E ? 'loaded' : document.getElementById('srChart').getAttribute('aria-valuetext')");
    check(vt0 === 'loaded' || vt0 === (lang === 'es' ? 'Cargando los conjuntos de datos…' : 'Loading the datasets…'), `${L}: while the datasets load the panel says so ("${vt0}")`);
    check(await p.waitFor('Series.state.rows > 0 && !!document.querySelector("#srChart svg")', 240000), `${L}: the link opens the panel and draws the chart`);
    await sleep(500); s = await p.eval('__s.state()');
    check(s.loaded && s.name === q.name, `${L}: the datasets loaded when the panel opened (${s.name})`);
    check(s.focus === 'srChart', `${L}: the focus moves to the chart (${s.focus})`);
    check(!!s.keys && s.keys.inPanel && s.keys.clear && s.keys.fits && s.keys.name === q.name && s.keys.pr === 'Puerto Rico', `${L}: the key (${q.name}, Puerto Rico) shows inside the panel, clear of the title, the buttons and the chart (${JSON.stringify(s.keys)})`);
    if (phone) check(!s.pop && s.inScreen && !s.sideways, `${L}: on a phone the card closes and the panel stays inside the screen (${JSON.stringify(s.panel)})`);
    else check(s.pop && !s.covers && s.inScreen, `${L}: on a desktop the card stays and the panel does not cover its links`);
    await shot(p, `panel_${lang}_${w}`);
    // 3. ACS: 5-year windows with margins of error
    check(s.h === 'poverty_pct' && s.band > 0, `${L}: poverty (ACS B17001) draws its margin of error as a band (${s.band})`);
    check(lang === 'es' ? /estimados de 5 años/i.test(s.note) && /margen de error/.test(s.note) && /se solapan/.test(s.note) : /5-year estimates/.test(s.note) && /margin of error/.test(s.note) && /overlap/.test(s.note), `${L}: the note says 5-year estimates, overlapping periods and margin of error ("${s.note.slice(0, 90)}…")`);
    check(/\d{4}–\d{4}/.test(s.vt) && /±/.test(s.vt) && (lang === 'es' ? /estimado de 5 años/ : /5-year estimate/).test(s.vt), `${L}: the screen reader hears the period, the estimate and its margin ("${s.vt.slice(0, 110)}")`);
    check(await p.eval("[...document.querySelectorAll('#srNote .gl-mark')].length > 0 || localStorage.getItem('twin.gloss') === 'off' || !(window.Core && Core.glossary && Core.glossary.state === 'on')"), `${L}: the note's technical words are glossary terms (when the glossary is on)`);
    if (!phone) {
      const m = await p.eval('__s.chartMid()');
      await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: m.x, y: m.y }); await sleep(300);
      const tipText = await p.eval("(document.querySelector('#tip.show') || {}).innerText || ''");
      check(/\d{4}–\d{4}/.test(tipText) && /±/.test(tipText) && /90/.test(tipText), `${L}: the tooltip shows the period and the margin of error ("${tipText.replace(/\s+/g, ' ').slice(0, 100)}")`);
      await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 5, y: 5 });
    }
    // 4. the keys; the columns' year stays as it was with the columns off
    const ys = await p.eval('__s.ys()'), engY0 = s.engY;
    await p.eval("document.getElementById('srChart').focus(), 0");
    await key(p, 'Home'); s = await p.eval('__s.state()');
    check(s.sel === ys[0] && s.latest && s.engY === engY0, `${L}: Home goes to the first year (${s.sel}), "Latest" shows, the columns' year stays (${s.engY})`);
    await key(p, 'ArrowRight'); s = await p.eval('__s.state()');
    check(s.sel === ys[1], `${L}: the right arrow moves one year (${s.sel})`);
    await key(p, 'End'); s = await p.eval('__s.state()');
    check(s.sel === ys.at(-1), `${L}: End goes to the last year (${s.sel})`);
    // the other keys of a slider: Up and Down one year, Page Up and Page Down five; the year chosen with the keys shows its tooltip, inside the window
    await key(p, 'Home'); await key(p, 'ArrowUp'); s = await p.eval('__s.state()');
    check(s.sel === ys[1], `${L}: the up arrow moves one year on (${s.sel})`);
    await key(p, 'ArrowDown'); s = await p.eval('__s.state()');
    check(s.sel === ys[0], `${L}: the down arrow moves one year back (${s.sel})`);
    check(!!s.tip && s.tip.inScreen && s.tip.text.includes(String(ys[0])) && s.tip.text.includes(q.name) && s.tip.text.includes('Puerto Rico'), `${L}: the year chosen with the keys shows its tooltip inside the window ("${s.tip ? s.tip.text.slice(0, 90) : 'none'}")`);
    await key(p, 'PageUp'); s = await p.eval('__s.state()');
    check(s.sel === ys[Math.min(5, ys.length - 1)], `${L}: Page Up moves five years on (${s.sel})`);
    await key(p, 'PageDown'); s = await p.eval('__s.state()');
    check(s.sel === ys[0] && s.engY === engY0, `${L}: Page Down moves five years back (${s.sel}), the columns' year stays (${s.engY})`);
    await p.eval("document.getElementById('srSet').focus(), 0"); await sleep(200); s = await p.eval('__s.state()');
    check(!s.tip, `${L}: the keys' tooltip closes when the focus leaves the chart`);
    await p.eval("document.getElementById('srChart').focus(), 0");
    await key(p, 'Home');
    const lb = await p.eval("(() => { const b = document.getElementById('srLatest').getBoundingClientRect(); return { x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2) }; })()");
    await click(p, lb.x, lb.y); await sleep(300); s = await p.eval('__s.state()');
    check(s.sel === ys.at(-1) && !s.latest && s.y == null && s.engY === engY0, `${L}: "Latest" goes back to the latest year (${s.sel}) and hides itself`);
    // 5. Esc gives the focus back
    await p.eval("document.getElementById('srChart').focus(), 0"); await key(p, 'Escape'); s = await p.eval('__s.state()');
    check(!s.shown && (phone ? /maplibregl-canvas/.test(s.focus) : s.focus === 'link:' + q.name), `${L}: Esc closes the panel and the focus goes back to ${phone ? 'the map' : 'the link'} (${s.focus})`);
    // 6. the close button gives the focus back too
    if (!phone) { link = await p.eval('__s.link()'); if (link) await click(p, link.x, link.y); }
    else { await p.eval('__s.closeCards()'); await click(p, q.x, q.y); await sleep(1200); link = await p.eval('__s.link()'); if (link) await click(p, link.x, link.y); }
    await p.waitFor('Series.state.open && Series.state.rows > 0', 30000); await sleep(300);
    const cb = await p.eval("(() => { const b = document.getElementById('srClose').getBoundingClientRect(); return { x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2) }; })()");
    await click(p, cb.x, cb.y); await sleep(300); s = await p.eval('__s.state()');
    check(!s.shown && (phone ? /maplibregl-canvas/.test(s.focus) : s.focus === 'link:' + q.name), `${L}: the close button closes it and the focus goes back (${s.focus})`);
    // 7. the "Any dataset" columns on: a click on land opens the panel on a desktop only
    await p.eval("(() => { const m = document.getElementById('metric'); m.value = '__any'; m.dispatchEvent(new Event('change')); })(), 0");
    await p.waitFor("map.getLayoutProperty('muni-cols', 'visibility') === 'visible'", 30000); await settle(p);
    q = await findLand(p);
    if (check(!!q, `${L}: bare land with the columns on`)) {
      await p.eval('__s.closeCards()'); await click(p, q.x, q.y); await sleep(1500); s = await p.eval('__s.state()');
      check(phone ? !s.shown && s.pop : s.shown && s.pop && !s.covers, phone ? `${L}: on a phone a click on land with the columns on opens the card, not the panel` : `${L}: on a desktop a click on land with the columns on opens the card and the panel (${s.name}), the panel off the card's links`);
      if (!phone) {
        await p.eval("document.getElementById('srChart').focus(), 0"); await key(p, 'Home'); s = await p.eval('__s.state()');
        const sel = await p.eval("ENG.E.resolve(ENG.h, ENG.y).y");
        check(s.engY === ys[0] && sel === s.sel, `${L}: with the columns on the chart's year is the columns' year (${s.engY})`);
        await p.eval("Series.close(), (ENG.y = null), (document.getElementById('engY').value = ''), engineDraw(), 0");
      }
    }
    // 8. a flood zone over the sea opens no panel and throws nothing
    await p.eval("document.getElementById('lyFlood').click(), 0");
    await p.waitFor("!!map.getLayer('flood-fill') && map.getLayoutProperty('flood-fill', 'visibility') !== 'none'", 60000);
    let sea = null; for (const c of [[-66.02, 18.47, 13], [-65.75, 18.38, 13], [-66.15, 18.48, 13], [-67.17, 18.10, 13], [-65.60, 18.20, 12.5], [-66.02, 18.47, 13]]) { await jump(p, ...c); await sleep(1500); sea = await p.eval('__s.sea()', { timeout: 120000 }); if (sea) break; }
    if (check(!!sea, `${L}: a flood zone over the sea (${sea ? sea.zone : 'none'})`)) {
      const n0 = p.logs.length; await p.eval('__s.closeCards()'); await click(p, sea.x, sea.y); await sleep(1500); s = await p.eval('__s.state()');
      check(!s.shown && p.logs.slice(n0).every(l => !/error|EXCEPTION/.test(l.type)), `${L}: a click on it opens no panel (no "Loading…" forever) and no error`);
      await shot(p, `sea_${lang}_${w}`);
    }
    // 9. the route planner's pick mode opens no panel
    q = await findLand(p);
    await p.eval("showTab('route', { open: false }), 0"); await p.waitFor('!!Plan.root', 30000);
    await p.eval("Plan.clear(), Plan.root.querySelectorAll('[data-act=pick]')[0].click(), 0"); if (w < 500) await p.eval('setPanel(false), 0');
    if (q) { await p.eval('__s.closeCards()'); await click(p, q.x, q.y); await p.waitFor('!!Plan.stops[0].pt', 60000); await sleep(600); s = await p.eval('__s.state()');
      const pl = await p.eval('({ pt: !!Plan.stops[0].pt, picking: Plan.picking })');
      check(!s.shown && pl.pt, `${L}: in pick mode a click places the point and opens no panel (${JSON.stringify({ shown: s.shown, pop: s.pop, ...pl })})`); }
    await p.eval('Plan.clear(), 0');
    // 10. a phone: a click on the map closes the panel
    if (phone && q) {
      await p.eval(`Series.open(${JSON.stringify(q.name)}), 0`); await p.waitFor('Series.state.rows > 0', 30000);
      await p.eval('__s.closeCards()'); await click(p, q.x, Math.min(q.y, 300)); await sleep(1200); s = await p.eval('__s.state()');
      check(!s.shown, `${L}: on a phone a click on the map closes the panel`);
    }
    // 11. unknown names are ignored
    await p.eval("Series.open(undefined), Series.open('Atlantis'), 0"); s = await p.eval('__s.state()');
    check(!s.shown, `${L}: Series.open with no or an unknown name opens nothing`);
    const e = p.logs.filter(l => l.type === 'error' || l.type === 'EXCEPTION' || l.type === 'log.error');
    check(!e.length, `${L}: no console errors ${e.length ? JSON.stringify(e).slice(0, 300) : ''}`);
    check(!(await p.eval('I18N.missed')).length, `${L}: no Spanish missing ${JSON.stringify(await p.eval('I18N.missed')).slice(0, 200)}`);
    check(!(await p.eval('__s.state()')).sideways, `${L}: no sideways scroll`);
  } finally { await p.close(); }
}

(async () => {
  try { for (const lang of langs) for (const w of widths) await run(lang, w); }
  catch (e) { console.error(e); process.exit(2); }
  console.log(`\n${passed} passed, ${problems.length} failed`); problems.forEach(x => console.log('  - ' + x));
  process.exit(problems.length ? 1 : 0);
})();
