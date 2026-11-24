// The small fixes of the first-visit usability pass (2026-10-27, branch usability-pass), in a real browser, in each language and width:
//  - the Route analysis and Global Innovation Index pages start under their section bar, with no empty band where the Housing page has its year bar (the "In review"
//    notice within 24 px of the bar);
//  - the Route analysis comparison table: each column's sort button is at least 24 px tall (WCAG 2.5.8) and shows the focus ring when it has the keyboard focus;
//  - the data dictionary opened with no link stays at its top while its Spanish arrives (on a phone the redraw moved it down by about 450 px);
//  - the 2D map's Trend view (Economy workbench): the chart takes the keyboard focus, and the arrows, Page Up, Page Down, Home and End move the year, which the
//    chart's tooltip shows and a screen reader hears (aria-valuetext); the tooltip closes when the focus leaves;
//  - the search box of the 2D map and the 3D view shows its long hint ("Search a place or street") only where it fits, the short one ("Search") otherwise;
//  - a clean console and no Spanish missing.
// And the three decisions of 2026-10-29 (the project lead, from the list "Para decidir" of PR #100; HANDOFF decision 65), at every width given (the fixes above at 360 px and up):
//  - the top bar up to 860 px: every button and link answers in a 44 x 44 px square around it (elementFromPoint at 25 points of the square, so the squares of
//    two neighbours never overlap); nothing leaves the screen or the bar; no sideways scroll; on a phone, two rows in 92 px with Ask beside the language switch.
//    Every page with the top bar, at the width given, and at 360 px with 390;
//  - the map credits on a phone (under 700 px): the 2D map, the 3D view and both WCRP maps show the full credits when they open, fold them behind a round "i"
//    button after 5 s or at the first touch of the map, and the button (a 44 x 44 px target, named "Créditos del mapa" / "Map credits", aria-expanded) opens
//    them again with a tap, Enter or Space; on a wide screen the credits stay open with no button;
//  - the "In review" notice: the same words on WCRP, Route analysis and GII (one base sentence, plus the AI disclosure on the last two), with the tab's badge,
//    the yellow notice and noindex kept; none on Housing.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/usability.js [base URL, default http://127.0.0.1:8041] [langs, default es,en] [widths, default 1400,390,320]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(','), widths = (process.argv[4] || '1400,390,320').split(',').map(Number);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
const KEYS = { Home: 36, End: 35, ArrowLeft: 37, ArrowRight: 39, ArrowUp: 38, ArrowDown: 40, PageUp: 33, PageDown: 34, Tab: 9 };
const key = async (p, k, shift) => { for (const type of ['keyDown', 'keyUp']) await p.send('Input.dispatchKeyEvent', { type, key: k, code: k, windowsVirtualKeyCode: KEYS[k], modifiers: shift ? 8 : 0 }); await sleep(200); };
const open = (file, lang, w) => openPage(`${base}/${file}${file.includes('?') ? '&' : '?'}lang=${lang}`, { width: w, height: w < 600 ? 844 : 900, mobile: w < 600 });
const GLOSS = "!window.Core || !Core.glossary || Core.glossary.state === 'on' || Core.glossary.state === 'off'";
async function clean(p, L) {
  const e = p.logs.filter(l => l.type === 'error' || l.type === 'EXCEPTION' || l.type === 'log.error');
  check(!e.length, `${L}: no console errors ${e.length ? JSON.stringify(e).slice(0, 300) : ''}`);
  const m = await p.eval('window.I18N ? [...I18N.missed] : []');
  check(!m.length, `${L}: no Spanish missing ${JSON.stringify(m).slice(0, 200)}`);
}

async function researchTop(file, lang, w) {
  const L = `${file} ${lang} ${w}`, p = await open(file, lang, w);
  try {
    check(await p.waitFor("document.readyState === 'complete' && !!document.querySelector('.review-note')", 60000), `${L}: ready`);
    const g = await p.eval("(() => { const t = document.getElementById('toc').getBoundingClientRect(), n = document.querySelector('.review-note').getBoundingClientRect(); return { gap: Math.round(n.top - t.bottom), yearbar: !!document.getElementById('yearbar') }; })()");
    check(!g.yearbar && g.gap >= 0 && g.gap <= 24, `${L}: the page starts under its section bar, no band left for a year bar (${g.gap} px)`);
    if (file.startsWith('route')) {
      await p.waitFor("document.querySelectorAll('table.rc th button').length > 3", 30000);
      const b = await p.eval("(() => { const bs = [...document.querySelectorAll('table.rc th button')]; return { n: bs.length, min: Math.min(...bs.map(b => b.getBoundingClientRect().height)) }; })()");
      check(b.min >= 24, `${L}: the ${b.n} sort buttons of the comparison table are at least 24 px tall (${b.min.toFixed(1)})`);
      // the keyboard: Tab onto the first sort button, from the element just before it
      await p.eval("(() => { const b = document.querySelector('table.rc th button'), all = [...document.querySelectorAll('a[href], button, select, input, [tabindex]:not([tabindex=\"-1\"])')].filter(e => e.offsetParent), i = all.indexOf(b); all[i - 1].focus(); })(), 0");
      await key(p, 'Tab');
      const f = await p.eval("(() => { const a = document.activeElement, s = getComputedStyle(a); return { on: a === document.querySelector('table.rc th button'), vis: a.matches(':focus-visible'), style: s.outlineStyle, width: parseFloat(s.outlineWidth) }; })()");
      check(f.on && f.vis && f.style !== 'none' && f.width >= 2, `${L}: a sort button with the keyboard focus shows the focus ring (${JSON.stringify(f)})`);
    }
    await clean(p, L);
  } finally { await p.close(); }
}

async function dictionaryTop(lang, w) {
  const L = `dictionary ${lang} ${w}`, p = await open('dictionary.html', lang, w);
  try {
    check(await p.waitFor("document.querySelectorAll('#dList details.de').length > 0", 90000), `${L}: ready`);
    if (lang === 'es') check(await p.waitFor('!!(D.data && D.data.labels_es)', 90000), `${L}: the Spanish is in`);
    await sleep(2500);
    check(await p.eval('scrollY') === 0, `${L}: opened with no link, the page stays at its top (${await p.eval('scrollY')} px)`);
    await clean(p, L);
  } finally { await p.close(); }
}

async function searchHint(file, lang, w) {
  const L = `${file} search ${lang} ${w}`, p = await open(file, lang, w);
  try {
    check(await p.waitFor("document.readyState === 'complete' && typeof searchPlaceholder === 'function' && (!document.fonts || document.fonts.status === 'loaded')", 90000), `${L}: ready`);
    await sleep(800);
    const r = await p.eval("(() => { const i = document.getElementById('search'), s = getComputedStyle(i), c = document.createElement('canvas').getContext('2d'); c.font = s.font; return { ph: i.placeholder, text: Math.round(c.measureText(i.placeholder).width), room: Math.round(i.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)), long: T('Search a place or street'), short: T('Search') }; })()");
    check((r.ph === r.long || r.ph === r.short) && r.text <= r.room, `${L}: the search hint fits its box ("${r.ph}", ${r.text} of ${r.room} px)`);
  } finally { await p.close(); }
}

async function trendKeys(lang, w) {
  const L = `map trend ${lang} ${w}`, p = await open('index.html', lang, w);
  try {
    check(await p.waitFor(`document.readyState === 'complete' && window.ECON && ECON.api && (${GLOSS})`, 90000), `${L}: ready`);
    const key0 = await p.eval("(async () => { await ECON.api.ready(); const k = Object.keys(EC.V).find(k => /unemp/.test(k) && EC.V[k].ys.length > 5) || Object.keys(EC.V).find(k => EC.V[k].ys.length > 5); await ECON.api.show({ layers: [{ key: k }], select: 'Ponce', bench: 'trend' }); return k; })()", { timeout: 90000 });
    check(await p.waitFor("!!(EC.charts && EC.charts.tr && document.getElementById('trCanvas'))", 90000), `${L}: the Trend view draws its chart (${key0})`);
    await sleep(500);
    const c0 = await p.eval("(() => { const c = document.getElementById('trCanvas'); return { tab: c.tabIndex, role: c.getAttribute('role'), min: +c.getAttribute('aria-valuemin'), max: +c.getAttribute('aria-valuemax'), now: +c.getAttribute('aria-valuenow'), label: c.getAttribute('aria-label') || '' }; })()");
    check(c0.tab === 0 && c0.role === 'slider' && c0.now === c0.max && c0.min < c0.max && !!c0.label, `${L}: the chart is a slider for the keyboard, on the latest year (${JSON.stringify(c0)})`);
    await p.eval("document.getElementById('trCanvas').focus(), 0");
    const st = () => p.eval("(() => { const c = document.getElementById('trCanvas'), ch = EC.charts.tr, t = ch.tooltip; return { now: +c.getAttribute('aria-valuenow'), vt: c.getAttribute('aria-valuetext') || '', tip: t.getActiveElements().length, idx: t.getActiveElements().length ? t.getActiveElements()[0].index : -1, year: t.getActiveElements().length ? ch.data.labels[t.getActiveElements()[0].index] : null, focus: document.activeElement === c }; })()");
    const ys = await p.eval('EC.charts.tr.data.labels.map(Number)');
    await key(p, 'Home'); let s = await st();
    check(s.now === ys[0] && s.tip > 0 && s.year == ys[0] && s.vt.startsWith(String(ys[0])) && s.vt.includes('Puerto Rico') && s.vt.includes('Ponce'), `${L}: Home goes to the first year; the tooltip and the screen reader's text name it ("${s.vt.slice(0, 90)}")`);
    await key(p, 'ArrowRight'); s = await st(); check(s.now === ys[1] && s.year == ys[1], `${L}: the right arrow moves one year on (${s.now})`);
    await key(p, 'ArrowUp'); s = await st(); check(s.now === ys[2], `${L}: the up arrow moves one year on (${s.now})`);
    await key(p, 'ArrowDown'); await key(p, 'ArrowLeft'); s = await st(); check(s.now === ys[0], `${L}: the down and left arrows move back (${s.now})`);
    await key(p, 'PageUp'); s = await st(); check(s.now === ys[Math.min(5, ys.length - 1)], `${L}: Page Up moves five years on (${s.now})`);
    await key(p, 'End'); s = await st(); check(s.now === ys.at(-1) && s.year == ys.at(-1), `${L}: End goes to the last year (${s.now})`);
    await key(p, 'PageDown'); s = await st(); check(s.now === ys[Math.max(0, ys.length - 6)], `${L}: Page Down moves five years back (${s.now})`);
    await p.eval("document.getElementById('trL').focus(), 0"); await sleep(200); s = await st();
    check(!s.focus && s.tip === 0, `${L}: the tooltip closes when the focus leaves the chart`);
    await clean(p, L);
  } finally { await p.close(); }
}

// ── The three decisions of 2026-10-29 ── (ONLY=bar,credits,notice,pr100 in the environment runs some parts only; all by default)
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean), on = (k) => !ONLY.length || ONLY.includes(k);
const BAR_PAGES = ['index.html', '3d.html', 'housing.html', 'wcrp.html', 'route-analysis.html', 'gii.html', 'dictionary.html', 'data-management.html', 'profile.html'];
// every clickable thing of the top bar: the 44 px square around its centre (or its own box where that is larger) must answer to it at 25 points; the current page's
// view link takes no clicks on some pages (pointer-events: none) and is left out, like the search box (a text field, not a button)
const BAR = `(() => { const bar = document.querySelector('.topbar'), B = bar.getBoundingClientRect(), out = { bad: [], n: 0, sw: document.documentElement.scrollWidth, w: innerWidth };
  for (const t of [...bar.querySelectorAll('button, a, input')].filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden')) {
    const r = t.getBoundingClientRect(), name = (t.getAttribute('aria-label') || t.textContent || t.id || t.className).trim().replace(/\\s+/g, ' ').slice(0, 24);
    if (r.left < -0.5 || r.right > innerWidth + 0.5 || r.top < B.top - 0.5 || r.bottom > B.bottom + 0.5) out.bad.push(name + ' leaves the bar');
    if (t.tagName === 'INPUT' || getComputedStyle(t).pointerEvents === 'none' || innerWidth > 860) continue;
    out.n++;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2, hw = Math.max(22, r.width / 2), hh = Math.max(22, r.height / 2);
    pts: for (const fx of [-1, -0.5, 0, 0.5, 1]) for (const fy of [-1, -0.5, 0, 0.5, 1]) {
      const x = cx + fx * (hw - 1), y = cy + fy * (hh - 1), h = document.elementFromPoint(x, y);
      if (!h || !(h === t || t.contains(h))) { out.bad.push(name + ' misses ' + Math.round(x) + ',' + Math.round(y) + ' (' + (h ? (h.id || h.className || h.tagName) : 'none').toString().slice(0, 20) + ')'); break pts; }
    } }
  return out; })()`;
async function topBar(file, lang, w) {
  const L = `${file} bar ${lang} ${w}`, p = await open(file, lang, w);
  try {
    check(await p.waitFor("document.readyState === 'complete' && !!document.querySelector('.topbar .lang-switch') && !!document.getElementById('chBtn') && (!document.fonts || document.fonts.status === 'loaded')", 60000), `${L}: ready`);
    await p.waitFor("!document.querySelector('.loader') || document.querySelector('.loader').classList.contains('hide') || !document.querySelector('.loader').getClientRects().length", 90000);   // the 3D view's loader covers the page until it is ready
    await sleep(600);
    const r = await p.eval(BAR);
    check(r.sw <= r.w, `${L}: no sideways scroll (${r.sw} px of ${r.w})`);
    check(!r.bad.length, `${L}: nothing leaves the top bar${w <= 860 ? `, and its ${r.n} buttons and links each answer in 44 x 44 px` : ''} ${r.bad.slice(0, 4).join('; ')}`);
    if (w <= 560) {   // the phone's two rows: Ask beside the language switch; the search (where there is one) and the views below
      const g = await p.eval("(() => { const top = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : null; }; return { lang: top('.topbar .lang-switch'), chat: top('#chBtn'), views: top('.topbar .views'), bar: Math.round(document.querySelector('.topbar').getBoundingClientRect().height) }; })()");
      check(Math.abs(g.chat - g.lang) <= 4 && g.views > g.lang + 30 && g.bar === 92, `${L}: two rows in the 92 px bar, Ask beside the language switch (${JSON.stringify(g)})`);
    }
    await clean(p, L);
  } finally { await p.close(); }
}

const CR = "(() => [...document.querySelectorAll('.leaflet-control-attribution, .maplibregl-ctrl-attrib')].map(box => { const b = box.parentNode.querySelector(':scope > .cr-btn'), r = b && b.getBoundingClientRect(); return { shown: getComputedStyle(box).display !== 'none' && box.getClientRects().length > 0, text: box.textContent, hidden: !b || b.hidden || !b.getClientRects().length, exp: b && b.getAttribute('aria-expanded'), name: b && b.getAttribute('aria-label'), ctl: !!b && b.getAttribute('aria-controls') === box.id, tab: b ? b.tabIndex : null, rect: r ? [r.left, r.top, r.width, r.height] : null }; }))()";
const press = async (p, x, y) => { for (const type of ['mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); };
async function credits(file, lang, w) {
  const L = `${file} credits ${lang} ${w}`, phone = w < 700, n = file === 'wcrp.html' ? 2 : 1, name = lang === 'es' ? 'Créditos del mapa' : 'Map credits';
  const p = await open(file, lang, w);
  try {
    if (n > 1) for (const id of ['scMap', 'wmMap']) { await p.waitFor(`!!document.getElementById('${id}')`, 60000); await p.eval(`document.getElementById('${id}').scrollIntoView({ block: 'center' }), 0`); await sleep(1500); }   // the WCRP maps start when they come into view
    check(await p.waitFor(`document.querySelectorAll('.cr-btn').length >= ${n}`, 90000), `${L}: ready, ${n} credit box${n > 1 ? 'es' : ''} with ${n > 1 ? 'their' : 'its'} button`);
    check(await p.waitFor(`(${CR}).some(x => /OpenStreetMap/.test(x.text))`, 40000, 200), `${L}: the base map's credit arrives`);
    let c = await p.eval(CR);
    check(c.length === n && c.every(x => x.shown) && c.some(x => /OpenStreetMap/.test(x.text)), `${L}: the full credits show when the map opens (${c.map(x => x.shown + ' ' + x.text.slice(0, 60)).join(' | ')})`);
    if (!phone) {
      await sleep(6000); c = await p.eval(CR);
      check(c.every(x => x.shown && x.hidden && x.exp === 'true'), `${L}: a wide screen keeps the credits open, with no button (${JSON.stringify(c.map(x => [x.shown, x.hidden]))})`);
      await clean(p, L);
      return;
    }
    check(c.every(x => !x.hidden && x.exp === 'true' && x.name === name && x.ctl && x.tab === 0), `${L}: the button shows, named "${name}", open (aria-expanded), in the Tab order (${JSON.stringify(c.map(x => [x.hidden, x.exp, x.name, x.ctl, x.tab]))})`);
    check(await p.waitFor(`(${CR}).every(x => !x.shown && x.exp === 'false')`, 30000, 200), `${L}: the credits fold by themselves 5 s after the base map's credit shows`);
    for (let i = 0; i < n; i++) {
      await p.eval(`document.querySelectorAll('.cr-btn')[${i}].scrollIntoView({ block: 'center' }), 0`); await sleep(300);
      const [x, y, bw, bh] = (await p.eval(CR))[i].rect, cx = x + bw / 2, cy = y + bh / 2;
      check(bw >= 24 && bh >= 24 && bw <= 44, `${L} #${i + 1}: the button is visible (${bw} x ${bh} px)`);
      const hits = await p.eval(`(() => { const b = document.querySelectorAll('.cr-btn')[${i}]; let ok = 0; const miss = []; for (const fx of [-1, -0.5, 0, 0.5, 1]) for (const fy of [-1, -0.5, 0, 0.5, 1]) { const x = ${cx} + fx * 21, y = ${cy} + fy * 21, h = document.elementFromPoint(x, y); if (h === b) ok++; else miss.push(Math.round(x) + ',' + Math.round(y) + ':' + (h ? (h.className || h.tagName).toString().slice(0, 20) : 'none')); } return { ok, miss }; })()`);
      check(hits.ok === 25, `${L} #${i + 1}: the button answers in 44 x 44 px (${hits.ok} of 25 points; ${hits.miss.slice(0, 3).join(' ')})`);
      await press(p, cx, cy); await sleep(300);
      let s = (await p.eval(CR))[i];
      check(s.shown && s.exp === 'true' && /OpenStreetMap/.test(s.text) && /OpenMapTiles/.test(s.text) && /OpenFreeMap/.test(s.text) && (file !== '3d.html' || /USGS/.test(s.text)), `${L} #${i + 1}: a tap opens the full credits (${s.text.slice(0, 110)})`);
      await p.eval(`document.querySelectorAll('.cr-btn')[${i}].focus(), 0`);
      for (const type of ['keyDown', 'keyUp']) await p.send('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, ...(type === 'keyDown' ? { text: '\r' } : {}) });
      await sleep(250); s = (await p.eval(CR))[i];
      check(!s.shown && s.exp === 'false', `${L} #${i + 1}: Enter folds them`);
      for (const type of ['keyDown', 'keyUp']) await p.send('Input.dispatchKeyEvent', { type, key: ' ', code: 'Space', windowsVirtualKeyCode: 32, ...(type === 'keyDown' ? { text: ' ' } : {}) });
      await sleep(250); s = (await p.eval(CR))[i];
      check(s.shown && s.exp === 'true', `${L} #${i + 1}: Space opens them`);
    }
    if (file === 'index.html') {   // with land under the button a tap must not also click the map (review of #108: it selected San Lorenzo)
      await p.eval('map.setView([18.23, -66.04], 12, { animate: false }), 0'); await sleep(1500);
      const before = await p.eval('location.hash'), [x, y, bw, bh] = (await p.eval(CR))[0].rect;
      await press(p, x + bw / 2, y + bh / 2); await sleep(600);
      const after = await p.eval("({ hash: location.hash, popup: !!document.querySelector('.leaflet-popup') })");
      check(after.hash === before && !after.popup, `${L}: a tap on the button over land does not click the map (${before} -> ${after.hash}, popup ${after.popup})`);
    }
    await clean(p, L);
  } finally { await p.close(); }
  if (phone && file !== 'wcrp.html') {   // a touch of the map before the 5 s folds the credits at once
    const q = await open(file, lang, w);
    try {
      check(await q.waitFor("!!document.querySelector('.cr-btn') && document.querySelector('.cr-btn').getAttribute('aria-expanded') === 'true'", 90000), `${L} touch: ready, the credits open`);
      // a point where the map itself is on top (not a panel, a chip or a notice over it)
      const PT = ("(() => { const el = document.querySelector('.cr-btn').closest('.leaflet-container, .maplibregl-map'), m = el.getBoundingClientRect(); for (const fy of [0.5, 0.4, 0.6, 0.3, 0.7]) for (const fx of [0.5, 0.3, 0.7]) { const x = m.left + m.width * fx, y = m.top + m.height * fy, h = document.elementFromPoint(x, y); if (h && el.contains(h) && h.tagName === 'CANVAS') return [x, y]; } return [m.left + m.width / 2, m.top + m.height / 2]; })()");
      // the 3D view's loader covers the map until it is ready: a touch then is not a touch of the map. If the 5 s ran out meanwhile, the clock folded the
      // credits already and there is nothing left to touch (the 2D map, ready sooner, checks the touch).
      await q.waitFor("!document.querySelector('.loader') || !document.querySelector('.loader').getClientRects().length || document.querySelector('.loader').classList.contains('hide')", 60000);
      if ((await q.eval(CR))[0].exp === 'false') { check(true, `${L} touch: folded by the clock before the map was ready to touch`); return; }
      const pt = await q.eval(PT);
      await press(q, pt[0], pt[1]); await sleep(300);
      const s = (await q.eval(CR))[0];
      check(!s.shown && s.exp === 'false', `${L} touch: a touch of the map folds the credits at once (${JSON.stringify(pt)})`);
    } finally { await q.close(); }
  }
}

const NOTE = { es: 'En revisión: el contenido de esta página está en revisión y puede cambiar.', en: 'In review: the content of this page is under review and may change.' };
const AI = { es: 'Borrador preparado con ayuda de Claude (inteligencia artificial).', en: 'Draft prepared with the help of Claude (artificial intelligence).' };
async function reviewNotice(file, lang, w) {
  const L = `${file} notice ${lang} ${w}`, p = await open(file, lang, w), ai = file === 'route-analysis.html' || file === 'gii.html';
  try {
    check(await p.waitFor("document.readyState === 'complete' && !!document.querySelector('.ka-tabs a')", 60000), `${L}: ready`);
    const r = await p.eval("(() => { const n = [...document.querySelectorAll('.review-note')], b = n[0] && n[0].querySelector('b'); return { n: n.length, text: n[0] ? n[0].lastElementChild.textContent.replace(/\\s+/g, ' ').trim() : '', bold: b ? b.textContent : '', icon: !!(n[0] && n[0].querySelector('.ms-icon[aria-hidden=\"true\"]')), role: n[0] ? n[0].getAttribute('role') : null, badge: !!document.querySelector('.ka-tab[aria-current=\"page\"] .ka-mark'), noindex: !!document.querySelector('meta[name=robots][content*=noindex]'), bg: n[0] ? getComputedStyle(n[0]).backgroundColor : '' }; })()");
    if (file === 'housing.html') { check(r.n === 0 && !r.badge, `${L}: Housing has no notice and no badge`); return; }
    const want = NOTE[lang] + (ai ? ' ' + AI[lang] : '');
    check(r.n === 1 && r.text === want && r.bold === NOTE[lang].split(':')[0] + ':' && r.icon && r.role === 'note', `${L}: one notice, in the shared words ("${r.text}")`);
    check(r.badge && r.noindex && r.bg !== 'rgba(0, 0, 0, 0)', `${L}: the tab's badge, the yellow notice (${r.bg}) and noindex stay`);
    await clean(p, L);
  } finally { await p.close(); }
}

(async () => {
  try {
    for (const lang of langs) for (const w of widths) {
      console.log(`${lang} ${w}`);
      if (on('bar')) for (const f of BAR_PAGES) for (const ww of w === 390 ? [w, 360] : [w]) await topBar(f, lang, ww);
      if (on('credits')) for (const f of ['index.html', '3d.html', 'wcrp.html']) await credits(f, lang, w);
      if (on('notice')) for (const f of ['wcrp.html', 'route-analysis.html', 'gii.html', 'housing.html']) await reviewNotice(f, lang, w);
      if (w < 360 || !on('pr100')) continue;   // the fixes of PR #100, at the widths they were made for
      await researchTop('route-analysis.html', lang, w);
      await researchTop('gii.html', lang, w);
      await dictionaryTop(lang, w);
      await trendKeys(lang, w);
      for (const ww of w > 1000 ? [w, 1024] : [w]) { await searchHint('index.html', lang, ww); await searchHint('3d.html', lang, ww); }
    }
  } catch (e) { console.error(e); process.exit(2); }
  console.log(`\n${passed} passed, ${problems.length} failed`); problems.forEach(x => console.log('  - ' + x));
  process.exit(problems.length ? 1 : 0);
})();
