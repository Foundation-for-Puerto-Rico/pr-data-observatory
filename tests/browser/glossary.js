// The in-page glossary (site/js/core/glossary.js; docs/glossary.md) on every page, in each language and width. Needs a headless Chrome on port 9333 (or CDP_PORT) and a served copy of site/:
//   node tests/browser/glossary.js http://127.0.0.1:8041 [screenshots folder] [langs, default es,en] [widths, default 1400,390] [pages, default all]
// On each page it checks that the underlines appear once the page is ready, never in a heading (unless marked on purpose), a button, a link, a label, code, a map label
// or the chat; that every mark is focusable, a button and described by the tooltip; that the tooltip opens on hover (desktop), on keyboard focus and on a tap (phone),
// closes on Esc with the focus kept and on a tap outside, and stays inside the window; that a map pop-up opened later gets its marks; that the console stays clean, no
// Spanish is missing and nothing scrolls sideways. On the map it also pans for two seconds and checks that the glossary did no work meanwhile and the frames were not
// slower than with the underlines turned off. It reports the marks of each page and the main-thread time of the first pass. Exits 1 when a check fails, 2 on an error.
const { openPage } = require('./cdp.js');
const fs = require('fs'), path = require('path');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] || '', langs = (process.argv[4] || 'es,en').split(','), widths = (process.argv[5] || '1400,390').split(',').map(Number);
const ALL = [['map', 'index.html'], ['3d', '3d.html'], ['profile', 'profile.html?area=72127'], ['housing', 'housing.html'], ['wcrp', 'wcrp.html'], ['routes', 'route-analysis.html'], ['gii', 'gii.html'], ['dictionary', 'dictionary.html'], ['datamgmt', 'data-management.html']];
const pages = process.argv[6] ? ALL.filter(p => process.argv[6].split(',').includes(p[0])) : ALL;
const WANT = ['moe', 'block-group', 'sfha', 'geojson', 'domain-in-the-dictionary', 'data-file', 'estimate'];   // the words the project lead named: each must be marked somewhere
let fails = 0; const seen = {}, report = [];
const check = (ok, msg) => { if (!ok) { fails++; console.log('  FAIL ' + msg); } return ok; };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const STATE = `(() => {
  const marks = [...document.querySelectorAll('.gl-mark')], tip = document.getElementById('gl-tip');
  const bad = marks.filter(m => m.parentElement.closest('h1,h2,h3,h4,h5,h6,button,a,label,summary,select,option,code,pre,#chat,.leaflet-control,.maplibregl-ctrl,.leaflet-marker-pane,.leaflet-tooltip-pane,[translate=no],[aria-hidden=true]') && !m.closest('[data-gloss]:not([data-gloss=off])'));
  const attrs = marks.filter(m => m.tabIndex !== 0 || m.getAttribute('role') !== 'button');
  return { state: Core.glossary.state, marks: marks.length, ids: [...new Set(marks.map(m => m.dataset.gl))], bad: bad.slice(0, 5).map(m => m.parentElement.tagName + ': ' + m.textContent), attrs: attrs.length,
    tip: !!tip && tip.getAttribute('role') === 'tooltip', described: document.querySelectorAll('[aria-describedby="gl-tip"]').length, missed: I18N.missed, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, stats: Core.glossary.stats };
})()`;
// a mark that can be pointed at: inside the window, not covered, in the page's own language
const PICK = (sel) => `(() => {
  const vis = (m) => { const r = m.getClientRects()[0]; if (!r || r.width < 4) return null; const x = r.left + Math.min(6, r.width / 2), y = r.top + r.height / 2; if (x < 0 || y < 60 || x > innerWidth || y > innerHeight - 20) return null; const at = document.elementFromPoint(x, y); return at && (at === m || m.contains(at)) ? { x, y, text: m.textContent, id: m.dataset.gl } : null; };
  const all = [...document.querySelectorAll(${JSON.stringify(sel)})];
  for (const m of all) { const v = vis(m); if (v) return v; }
  for (const m of all) { m.scrollIntoView({ block: 'center' }); const v = vis(m); if (v) return v; }
  return null;
})()`;
const TIP = `(() => { const t = document.getElementById('gl-tip'); if (!t || t.hidden) return null; const r = t.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom, w: document.documentElement.clientWidth, h: innerHeight, text: t.innerText, links: [...t.querySelectorAll('a')].map(a => a.getAttribute('href')), en: !!t.querySelector('[lang=en]') }; })()`;

async function waitTip(p, want, ms = 4000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { const t = await p.eval(TIP); if (want ? t && !/…$/.test(t.text.trim()) : !t) return t || true; await sleep(100); }
  return null;
}
function inside(t, label) {
  check(t.l >= 15.5 && t.r <= t.w - 15.5 && t.t >= 15.5 && t.b <= t.h - 15.5, `${label}: the tooltip stays inside the window with a 16 px gutter (${Math.round(t.l)}–${Math.round(t.r)} of ${t.w}, ${Math.round(t.t)}–${Math.round(t.b)} of ${t.h})`);
}

async function onePage(name, file, lang, width) {
  const mobile = width < 600, label = `${name} ${lang} ${width}`;
  const p = await openPage(`${base}/${file}${file.includes('?') ? '&' : '?'}lang=${lang}`, { width, height: mobile ? 844 : 900, mobile });
  try {
    if (mobile) await p.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
    if (!check(await p.waitFor("window.Core && Core.glossary && Core.glossary.state === 'on'", 90000), `${label}: the glossary is on once the page is ready`)) return;
    await sleep(800);
    const s = await p.eval(STATE);
    s.ids.forEach(i => { seen[lang] = seen[lang] || new Set(); seen[lang].add(i); });
    report.push({ page: name, lang, width, marks: s.marks, terms: s.ids.length, first_pass_ms: s.stats.firstMs, longest_slice_ms: Math.round(s.stats.maxMs * 10) / 10 });
    console.log(`${label}: ${s.marks} marks of ${s.ids.length} terms, first pass ${s.stats.firstMs} ms of main thread in ${s.stats.slices} slices (longest ${s.stats.maxMs.toFixed(1)} ms)`);
    check(s.marks >= 10, `${label}: underlines appear (${s.marks})`);
    check(!s.bad.length, `${label}: no mark in a heading, control, link, label, code, map label or the chat (${s.bad.join(' | ')})`);
    check(!s.attrs, `${label}: every mark is focusable and a button (${s.attrs} are not)`);
    check(s.tip, `${label}: the tooltip is in the page`);
    check(s.described === 0, `${label}: with no tooltip open no word is described by it (${s.described} are)`);
    check(!s.missed.length, `${label}: no Spanish missing (${s.missed.join(' | ')})`);
    check(s.sw <= s.cw, `${label}: no sideways scroll (${s.sw} > ${s.cw})`);
    check(s.stats.maxMs < 50, `${label}: no slice of the first pass is a long task (${s.stats.maxMs.toFixed(1)} ms)`);
    const got = await p.eval("performance.getEntriesByType('resource').map(e => e.name).filter(n => /glossary_/.test(n)).map(n => n.split('/').pop().split('?')[0])");
    check(!got.some(f => /defs/.test(f)), `${label}: the definitions wait for the first use (${got.join(', ')})`);
    check(name === 'dictionary' ? !got.length : got.includes(`glossary_forms_${lang}.json`), `${label}: the match forms come from ${name === 'dictionary' ? "the dictionary's own copy" : 'glossary_forms_' + lang + '.json'} (${got.join(', ') || 'none'})`);
    if (name === '3d') await p.eval("showTab('about', { open: false }), true");   // the 3D view's first tab is the layer menu, whose groups start closed
    if (mobile && (name === 'map' || name === '3d')) { await p.eval("setPanel(true), true"); await sleep(500); }   // the side panel is off-canvas on a phone
    const where = '.gl-mark';
    let m = await p.eval(PICK(where));
    if (!check(m, `${label}: a mark can be pointed at`)) return;
    if (!mobile) {   // hover, then leave
      await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: m.x, y: m.y });
      const t = await waitTip(p, true);
      if (check(t, `${label}: hover on "${m.text}" opens the tooltip`)) {
        inside(t, label + ' hover');
        const dsc = await p.eval(`(() => { const d = [...document.querySelectorAll('[aria-describedby="gl-tip"]')], at = document.elementFromPoint(${m.x}, ${m.y}); return { n: d.length, it: d.length === 1 && !!at && d[0] === at.closest('.gl-mark') }; })()`);
        check(dsc.n === 1 && dsc.it, `${label}: only the word under the pointer is described by the tooltip (${dsc.n})`);
        check(t.links.some(h => /#g-/.test(h)), `${label}: the tooltip links to the Glossary (${t.links.join(' ')})`);
        check(lang === 'en' || !/See in the glossary|Source:/.test(t.text), `${label}: the tooltip is in Spanish`);
        if (shots) fs.writeFileSync(path.join(shots, `${name}_${lang}_${width}_hover.png`), Buffer.from((await p.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
      }
      await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: Math.max(2, width - 4), y: 70 });
      check(await waitTip(p, false, 2000), `${label}: the tooltip closes when the pointer leaves`);
      const after = await p.eval(`({ n: document.querySelectorAll('[aria-describedby="gl-tip"]').length, text: document.getElementById('gl-tip').textContent })`);
      check(after.n === 0 && after.text === '', `${label}: once closed, the tooltip is empty and describes no word (${after.n}, "${after.text.slice(0, 40)}")`);
      // Esc with the focus elsewhere (a search box first, else another field): the tooltip closes, the focus stays and the page gets the key
      const field = await p.eval(`(() => { const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }; const f = [...document.querySelectorAll('input[type=search]'), ...document.querySelectorAll('input[type=text], textarea, select, button')].find(e => vis(e) && !e.closest('#gl-tip')); if (!f) return null; window.__esc = 0; if (!window.__escWatch) { window.__escWatch = true; document.addEventListener('keydown', e => { if (e.key === 'Escape') window.__esc++; }); } f.focus(); return f.id || f.tagName; })()`);
      if (field) {
        m = await p.eval(PICK(where));
        await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: m.x, y: m.y });
        if (await waitTip(p, true)) {
          await p.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await p.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
          const esc = await p.eval(`({ closed: document.getElementById('gl-tip').hidden, at: document.activeElement ? (document.activeElement.id || document.activeElement.tagName) : '', page: window.__esc })`);
          check(esc.closed && esc.at === field && esc.page === 1, `${label}: Esc with the focus in ${field} closes the tooltip, keeps the focus there and reaches the page (${JSON.stringify(esc)})`);
        }
        await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: Math.max(2, width - 4), y: 70 });
        await p.eval("document.activeElement && document.activeElement.blur(), true");
      }
    } else {   // tap opens, tap again closes, tap outside closes
      const tap = async (x, y) => { await p.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y, radiusX: 1, radiusY: 1 }] }); await p.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); };   // a fingertip of 1 px: Chrome moves a wider tap to a link nearby
      m = await p.eval(PICK(where));
      await tap(m.x, m.y);
      const t = await waitTip(p, true);
      if (check(t, `${label}: a tap on "${m.text}" opens the tooltip`)) {
        inside(t, label + ' tap');
        if (shots) fs.writeFileSync(path.join(shots, `${name}_${lang}_${width}_tap.png`), Buffer.from((await p.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
        await tap(m.x, m.y);
        check(await waitTip(p, false, 2000), `${label}: a second tap closes it`);
        await tap(m.x, m.y); await waitTip(p, true);
        const out = await p.eval(`(() => {   // a spot of plain text with nothing to press within 40 px: Chrome moves a tap near a link onto the link
          const t = document.getElementById('gl-tip').getBoundingClientRect(), hot = 'a,button,input,select,label,summary,[role=button],[role=tab],.gl-mark,#gl-tip,.leaflet-container,.maplibregl-map,.backdrop';
          const free = (x, y) => [[0, 0], [40, 0], [-40, 0], [0, 40], [0, -40], [28, 28], [-28, -28], [28, -28], [-28, 28]].every(([dx, dy]) => { const e = document.elementFromPoint(x + dx, y + dy); return e && !e.closest(hot) && !(x + dx >= t.left - 4 && x + dx <= t.right + 4 && y + dy >= t.top - 4 && y + dy <= t.bottom + 4); });
          for (const e of document.querySelectorAll('h1,h2,h3,p,li')) { const r = e.getBoundingClientRect(); if (!r.width || r.top < 60 || r.bottom > innerHeight - 10) continue; const x = r.left + r.width / 2, y = r.top + r.height / 2; if (free(x, y)) return { x, y }; }
          return null; })()`);
        if (out) { const at = await p.eval('location.href'); await tap(out.x, out.y); check(await waitTip(p, false, 2000), `${label}: a tap outside closes it`); check(await p.eval('location.href') === at, `${label}: the tap outside stayed on the page`); }
      }
    }
    // keyboard: focus shows it at once, Enter moves into it, Esc closes it and keeps the focus on the word
    if (mobile && (name === 'map' || name === '3d')) { await p.eval("setPanel(true), true"); await sleep(500); }   // a tap outside may have closed the panel
    m = await p.eval(PICK(where));
    if (!check(m, `${label}: a mark can be focused`)) return;
    await p.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Shift', code: 'ShiftLeft', windowsVirtualKeyCode: 16 }); await p.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Shift', code: 'ShiftLeft', windowsVirtualKeyCode: 16 });
    await p.eval(`(() => { const r = document.elementFromPoint(${m.x}, ${m.y}); const k = r && r.closest('.gl-mark'); if (k) k.focus(); return !!k; })()`);
    const tf = await waitTip(p, true);
    if (check(tf, `${label}: keyboard focus on "${m.text}" opens the tooltip`)) {
      inside(tf, label + ' focus');
      check(await p.eval("(() => { const d = document.querySelectorAll('[aria-describedby=\"gl-tip\"]'); return d.length === 1 && d[0] === document.activeElement; })()"), `${label}: the focused word, and only it, is described by the tooltip`);
      await p.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      await sleep(200);
      check(await p.eval("!!document.getElementById('gl-tip').contains(document.activeElement)"), `${label}: Enter moves the focus into the tooltip`);
      await p.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
      check(await waitTip(p, false, 1500), `${label}: Esc closes the tooltip`);
      check(await p.eval("!!(document.activeElement && document.activeElement.classList.contains('gl-mark'))"), `${label}: and the focus goes back to the word`);
    }
    // a pop-up opened after load gets its marks
    const pop = lang === 'es' ? 'Este estimado tiene un margen de error.' : 'This estimate has a margin of error.';
    if (name === 'map') await p.eval(`L.popup().setLatLng(map.getCenter()).setContent('<div class="pop"><div class="meta">${pop}</div></div>').openOn(map), true`);
    if (name === '3d') await p.eval(`new maplibregl.Popup().setLngLat(map.getCenter()).setHTML('<div class="pop"><div class="meta">${pop}</div></div>').addTo(map), true`);
    if (name === 'map' || name === '3d') check(await p.waitFor("document.querySelectorAll('.leaflet-popup-content .gl-mark, .maplibregl-popup-content .gl-mark').length >= 2", 5000), `${label}: a pop-up opened later gets its marks`);
    if (name === '3d') {   // a layer of the facilities module, which loads on first use (core/facilities.js, facilities3d.js), and the pop-up of one of its points
      await p.eval("document.getElementById('lyFire').click(), true");
      if (check(await p.waitFor("typeof Facilities3D !== 'undefined' && !!map.getLayer('fac-fire')", 30000), `${label}: the fire stations layer loads`)) {
        await p.eval(`(async () => { const d = await (await fetch('data/fire_stations.geojson')).json(), f = d.features.find(x => x.properties.name); popup({ lng: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }, Core.facilities.popup('fire', f.properties, d)); return true; })()`);
        check(await p.waitFor("!!document.querySelector('.maplibregl-popup-content .src .gl-mark')", 5000), `${label}: a fire station's pop-up gets its marks (the source line names USGS)`);
      }
    }
    if (name === 'map' && !mobile) await panCheck(p, label);
    if (!mobile) {   // a word on two lines: the tooltip opens under the whole word, so its second line stays visible
      const two = await p.eval(`(() => { for (const m of document.querySelectorAll('.gl-mark')) { const r = m.getClientRects(); if (r.length < 2) continue; const a = r[0], at = document.elementFromPoint(a.left + 2, a.top + a.height / 2); if (a.top > 60 && r[r.length - 1].bottom < innerHeight - 200 && at && at.closest('.gl-mark') === m) return { x: a.left + 2, y: a.top + a.height / 2, bottom: m.getBoundingClientRect().bottom, top: m.getBoundingClientRect().top }; } return null; })()`);
      if (two) {
        await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: two.x, y: two.y });
        const t = await waitTip(p, true);
        check(t && (t.t >= two.bottom || t.b <= two.top), `${label}: a word on two lines is not covered by its tooltip (${t && Math.round(t.t)} against ${Math.round(two.bottom)})`);
        await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: Math.max(2, width - 4), y: 70 });
        await waitTip(p, false, 2000);
      }
    }
    if (name === 'dictionary' && !mobile) {   // "Hide the underlines": every mark goes, the focus comes back to where the word was, and the Glossary's switch turns them on again
      m = await p.eval(PICK(where));
      await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: m.x, y: m.y });
      if (await waitTip(p, true)) {
        const was = await p.eval(`(() => { const k = document.elementFromPoint(${m.x}, ${m.y}).closest('.gl-mark'); window.__glHost = k.parentElement; document.querySelector('#gl-tip .gl-hide').click(); return document.querySelectorAll('.gl-mark').length; })()`);
        check(was === 0 && await p.eval("localStorage.getItem('twin.gloss') === 'off' && document.getElementById('gl-tip').contains(document.activeElement)"), `${label}: "Hide the underlines" takes every mark off, keeps the choice and puts the focus on its note`);
        await p.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
        check(await p.eval("document.activeElement === window.__glHost"), `${label}: when the note closes, the focus is back where the word was, not on the page's body`);
        await p.eval("(() => { const c = document.getElementById('glSwitch'); c.click(); return c.checked; })()");
        check(await p.waitFor("Core.glossary.state === 'on' && document.querySelectorAll('.gl-mark').length > 50", 15000) && await p.eval("localStorage.getItem('twin.gloss') === null"), `${label}: the Glossary's switch turns the underlines on again`);
      }
      await p.eval("localStorage.removeItem('twin.gloss'), true");
    }
    const logs = p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon|ERR_INTERNET|net::/i.test(l.text));
    check(!logs.length, `${label}: a clean console (${logs.map(l => l.text).slice(0, 3).join(' | ')})`);
    check(!p.bad.some(b => /glossary/.test(b.url)), `${label}: every glossary file loads (${JSON.stringify(p.bad)})`);
  } finally { await p.close(); }
}

// Panning the map: the glossary does nothing while the map moves (no slice runs), and the frames are no slower than with the underlines off.
const PAN = `(async () => {
  const s0 = Core.glossary.stats.slices, frames = [];
  const box = document.getElementById('map'); box.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));   // as a drag would
  let last = performance.now();
  for (let i = 0; i < 120; i++) { map.panBy([i % 40 < 20 ? 14 : -14, 0], { animate: false }); await new Promise(r => requestAnimationFrame(r)); const n = performance.now(); frames.push(n - last); last = n; }
  box.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
  frames.sort((a, b) => a - b);
  return { slices: Core.glossary.stats.slices - s0, median: frames[frames.length >> 1], p90: frames[Math.floor(frames.length * .9)] };
})()`;
async function panCheck(p, label) {
  await p.eval("map.closePopup(), true");
  await sleep(600);
  const on = await p.eval(PAN);
  check(on.slices === 0, `${label}: no glossary work while the map pans (${on.slices} slices)`);
  const q = await openPage(`${base}/index.html?lang=${label.split(' ')[1]}`, { width: 1400, height: 900 });
  try {
    await q.eval("localStorage.setItem('twin.gloss', 'off'), true");
    await q.send('Page.reload', {});
    await sleep(500);
    await q.waitFor("window.Core && Core.glossary && Core.glossary.state === 'off'", 90000);
    await sleep(800);
    const off = await q.eval(PAN);
    await q.eval("localStorage.removeItem('twin.gloss'), true");
    console.log(`${label}: panning, frame time median ${on.median.toFixed(1)} ms (p90 ${on.p90.toFixed(1)}) with the underlines, ${off.median.toFixed(1)} ms (p90 ${off.p90.toFixed(1)}) without`);
    report.push({ page: 'map pan', lang: label.split(' ')[1], on_median_ms: +on.median.toFixed(1), on_p90_ms: +on.p90.toFixed(1), off_median_ms: +off.median.toFixed(1), off_p90_ms: +off.p90.toFixed(1) });
    check(on.median <= off.median * 1.25 + 2, `${label}: panning is not slower with the underlines (${on.median.toFixed(1)} against ${off.median.toFixed(1)} ms a frame)`);
  } finally { await q.close(); }
}

(async () => {
  if (shots) fs.mkdirSync(shots, { recursive: true });
  for (const lang of langs) for (const width of widths) for (const [name, file] of pages) {
    try { await onePage(name, file, lang, width); } catch (e) { fails++; console.log(`  FAIL ${name} ${lang} ${width}: ${e.message}`); }
  }
  if (pages.length === ALL.length) for (const lang of langs) check(WANT.every(i => seen[lang] && seen[lang].has(i)), `${lang}: the words the project lead named are marked (${WANT.filter(i => !(seen[lang] && seen[lang].has(i))).join(', ') || 'all'})`);
  console.log(JSON.stringify(report));
  console.log(fails ? `${fails} checks failed` : 'all checks passed');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
