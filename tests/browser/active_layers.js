// The "layers on" chip at the top of the 2D map and the 3D view (site/js/core/activelayers.js), in a real browser.
// It switches layers on from the menus, the Economy tab and the chat, opens a link with many layers, and uses the list's buttons, "Turn all off" and Undo, and the keyboard
// alone (Tab, Enter, Escape; Tab stops on each of the list's buttons in turn, never on a glossary mark). At each step the chip's number, its words and the list must agree; Límites (both views) and the Scene settings (3D) stay out of it; Undo gives back the
// same hash and goes away once something else changes; the focus never falls to the page's body; the console stays clean and no Spanish is missing. A second pass opens the
// list at five widths (1024 with the chat open) and checks that it ends above the map's buttons, scale, credits and the 3D time bar, and starts below an Undo message.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/active_layers.js [base URL, default http://127.0.0.1:8041] [folder for screenshots] [langs, default es,en] [widths, default 1400,390] [layout widths, default 1400,1024,768,390,320]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error, 3 when the run stopped before its end (a lost connection to Chrome, say).
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] || '', langs = (process.argv[4] || 'es,en').split(','), widths = (process.argv[5] || '1400,390').split(',').map(Number);
const layoutWidths = (process.argv[6] || '1400,1024,768,390,320').split(',').map(Number);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let finished = false, passed = 0;
process.on('exit', () => { if (!finished) { console.error('\nSTOPPED EARLY: the run did not reach its end'); process.exitCode = 3; } });
process.on('unhandledRejection', e => { console.error('unhandled', e); finished = true; process.exit(2); });
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
// wait for a condition in the page, then check it: a step is over when the page says so, not after a fixed time
const until = async (p, expr, what, ms = 20000) => { const ok = await p.waitFor(expr, ms, 100); if (!ok) console.log('    page: ' + JSON.stringify(await p.eval(`({ hash: location.hash, list: ActiveLayers.list().map(i => i.id), toast: (document.getElementById('toast') || {}).className, text: (document.getElementById('toastText') || {}).textContent, focus: document.activeElement.id || document.activeElement.tagName })`).catch(e => e.message))); return check(ok, what); };
const view = (w) => ({ width: w, height: w < 500 ? 812 : w < 900 ? 1024 : 900, mobile: w < 500 });

// what the page shows, read in the page: the chip, the list (when open), the count from the shared list, and the reference layers
const STATE = `(() => { const w = document.getElementById('alWrap'), c = document.getElementById('alChip'), items = ActiveLayers.list(), t = document.getElementById('toast'), b = document.getElementById('toastAct');
  return { n: ActiveLayers.count(), items: items.map(i => i.id), names: items.map(i => i.name), shown: !w.hidden, num: c.querySelector('.al-n').textContent, words: c.querySelector('.al-t').textContent,
    rows: document.getElementById('alPanel').hidden ? null : document.querySelectorAll('#alPanel li').length, note: !!document.querySelector('#alPanel .al-note'), all: !!document.querySelector('#alPanel .al-all'),
    open: c.getAttribute('aria-expanded'), hash: location.hash, undo: !!(t && t.classList.contains('show') && b && !b.hidden),
    focus: document.activeElement === document.body ? 'BODY' : document.activeElement && (document.activeElement.id || document.activeElement.className || document.activeElement.tagName), muni: !!(document.getElementById('lyMuni') || {}).checked,
    scene: ['lyTerrain', 'lyBuildings'].map(id => document.getElementById(id) && document.getElementById(id).checked).join(), missed: (I18N.missed || []).slice(), lang: I18N.lang }; })()`;
const SNAP3D = `JSON.stringify([location.hash, ...[...document.querySelectorAll('#panel input[type=checkbox]')].map(e => e.id + ':' + e.checked), document.getElementById('metric').value])`;
const SNAP = (page) => page === '2d' ? 'location.hash' : SNAP3D;
const KEYS = { Tab: 9, Enter: 13, Escape: 27 };
async function key(p, k, shift = false) {
  const o = { key: k, code: k, windowsVirtualKeyCode: KEYS[k], modifiers: shift ? 8 : 0 };
  await p.send('Input.dispatchKeyEvent', { type: 'keyDown', ...o, ...(k === 'Enter' ? { text: '\r' } : {}) });
  await p.send('Input.dispatchKeyEvent', { type: 'keyUp', ...o });
  await sleep(120);
}
async function shot(p, name) {
  if (!shots) return;
  const r = await p.send('Page.captureScreenshot', { format: 'png' });
  const f = path.join(shots, name + '.png'); fs.writeFileSync(f, Buffer.from(r.data, 'base64')); console.log('  shot ' + f);
}
function agree(s, label, page) {   // the chip, the shared list and the open list say the same thing
  check(s.n === s.items.length && s.shown === s.n > 0 && (!s.shown || s.num === String(s.n)), `${label}: chip ${s.num} "${s.words}" = ${s.items.length} in the list`);
  check(!s.shown || new RegExp(`^${s.n}\\b`).test(s.words) && (s.lang === 'es' ? (s.n === 1 ? /capa activa$/ : /capas activas$/) : (s.n === 1 ? /layer on$/ : /layers on$/)).test(s.words), `${label}: words "${s.words}"`);
  if (s.rows != null) check(s.rows === s.n && s.note === s.items.includes('plan') && s.all === s.items.some(i => i !== 'plan'), `${label}: ${s.rows} rows, the route note ${s.note ? 'shown' : 'not shown'}, Turn all off ${s.all ? 'shown' : 'hidden'}`);
  check(s.muni && !s.items.includes('lyMuni'), `${label}: Límites on and not counted`);   // the reference layer of both views (3D since phase B of the layer menus)
  if (page === '3d') check(s.scene === 'true,true' && !s.items.some(i => i === 'lyTerrain' || i === 'lyBuildings'), `${label}: Scene settings kept and not counted`);
}
// the 2D map writes its hash 250 ms after a change, and a route plan moves the map when it is computed: wait until the hash holds for a second
async function settle(p) { let last = null; for (let k = 0; k < 60; k++) { const h = await p.eval('location.hash'); if (h === last) return h; last = h; await sleep(1000); } return last; }
const n0 = (n) => `ActiveLayers.count() === ${n}`;
const clean = (p, label) => { const e = p.logs.filter(l => l.type === 'error' || l.type === 'EXCEPTION' || l.type === 'log.error'); check(!e.length, `${label}: no console errors ${e.length ? JSON.stringify(e).slice(0, 400) : ''}`); };
const openList = (p, label) => p.eval("document.getElementById('alChip').getAttribute('aria-expanded') === 'true' || document.getElementById('alChip').click()").then(() => until(p, "!!document.querySelector('#alPanel li')", `${label}: the list is open`));

// The glossary (core/glossary.js) works in idle slices once the page is ready: wait until it is on and has done its work, so a mark it would add is there before the Tab keys.
async function glossaryIdle(p, label) {
  check(await p.waitFor("window.Core && Core.glossary && Core.glossary.state === 'on'", 60000, 100), `${label}: the glossary is on`);
  let last = -1; for (let k = 0; k < 40; k++) { const n = await p.eval('Core.glossary.stats.slices'); if (n === last) break; last = n; await sleep(400); }
}
// The chip sits in the map (#map), which the glossary does not watch: its list was marked only when the glossary's first pass ran while the list was open, a race with
// the test's own clicks. That race was the intermittent failure of the 3D keyboard checks before the chip carried data-no-glossary (pull request 98): Tab stopped on
// the marked word of the first row instead of its × button, Enter then moved into the word's tooltip (its link, an <a>), and Escape left the focus on the word, so
// three checks failed together, more often under load and on the 3D view, whose glossary pass comes later. Asking the glossary to read the open list now
// (Core.glossary.mark) and waiting until a slice of its work has run makes that case happen every time, so a mark in the list fails here, by name.
async function markList(p, label, what) {
  await glossaryIdle(p, label);
  const n0 = await p.eval('Core.glossary.stats.slices');
  await p.eval("Core.glossary.mark(document.getElementById('alWrap')), 0");
  check(await p.waitFor(`Core.glossary.stats.slices > ${n0}`, 20000, 50), `${label} keyboard: the glossary read the open list${what}`);
  await glossaryIdle(p, label);
  const marks = await p.eval("document.querySelectorAll('#alWrap .gl-mark').length");
  check(marks === 0, `${label} keyboard: no glossary mark in the chip or its list${what} (${marks})`);
}
// From the chip, Tab walks the open list's buttons in order, one stop each, and never stops on a glossary mark: the chip carries data-no-glossary, so a layer's name
// (a technical word, often) is not a second stop inside the list, nor a focusable inside a focusable.
async function tabWalk(p, label) {
  await markList(p, label, '');
  const want = await p.eval("[...document.querySelectorAll('#alPanel button')].map(b => b.className)"), got = [];
  check(await p.eval("document.activeElement.id === 'alChip'"), `${label} keyboard: the walk starts on the chip`);
  for (let k = 0; k < want.length; k++) { await key(p, 'Tab'); got.push(await p.eval("document.activeElement.classList.contains('gl-mark') ? 'gl-mark' : document.activeElement.className")); }
  check(want.length > 1 && JSON.stringify(got) === JSON.stringify(want), `${label} keyboard: Tab moves control to control (${want.length} stops), never to a glossary mark (${got.join(' | ')})`);
}

async function keyboard(p, page, label) {
  // from the map itself: Tab (2D, the map's own element comes first) or Shift+Tab (3D, from the map's canvas) reaches the chip
  await p.eval("document.getElementById('alChip').getAttribute('aria-expanded') === 'true' && document.getElementById('alChip').click()");   // start closed
  if (page === '2d') { await p.eval("document.getElementById('map').focus()"); await key(p, 'Tab'); }
  else { await p.eval("document.querySelector('#map canvas').focus()"); await key(p, 'Tab', true); }
  let s = await p.eval(STATE); check(s.focus === 'alChip', `${label} keyboard: Tab reaches the chip (${s.focus})`);
  await key(p, 'Enter'); await until(p, "document.getElementById('alChip').getAttribute('aria-expanded') === 'true' && !!document.querySelector('#alPanel li')", `${label} keyboard: Enter opens the list`);
  const n = (await p.eval(STATE)).n;
  await markList(p, label, ', before the first Tab');
  await key(p, 'Tab'); s = await p.eval(STATE); check(/al-x/.test(s.focus), `${label} keyboard: Tab goes to the first layer's button (${s.focus})`);
  await key(p, 'Enter'); await until(p, n0(n - 1) + " && /al-x/.test(document.activeElement.className)", `${label} keyboard: Enter turns that layer off (${n} → ${n - 1}) and the next button has the focus`);
  agree(await p.eval(STATE), label + ' keyboard ×', page);
  await key(p, 'Escape'); s = await p.eval(STATE); check(s.open === 'false' && s.focus === 'alChip', `${label} keyboard: Escape closes the list and gives the focus back to the chip (${s.open}, ${s.focus})`);
  await key(p, 'Enter'); await until(p, "document.getElementById('alChip').getAttribute('aria-expanded') === 'true' && !!document.querySelector('#alPanel .al-all')", `${label} keyboard: Enter opens the list again`);
  await tabWalk(p, label);
  s = await p.eval(STATE); check(/al-all/.test(s.focus), `${label} keyboard: Tab reaches "Turn all off"`);
  if (page === '2d') await settle(p);
  const before = await p.eval(SNAP(page));
  await key(p, 'Enter'); await until(p, "document.activeElement.id === 'toastAct' && ActiveLayers.list().every(i => i.keep)", `${label} keyboard: Enter turns all off and the focus goes to Undo`);
  await key(p, 'Enter'); await until(p, `document.activeElement.id === 'alChip' && ${SNAP(page)} === ${JSON.stringify(before)}`, `${label} keyboard: Enter on Undo gives back the same ${page === '2d' ? 'hash' : 'layers and hash'}, the focus on the chip`, 30000);
}

// Undo goes away once something else changes, and the focus never falls to the body when its message is replaced
async function undoRules(p, label) {
  await openList(p, label); await until(p, "!!document.querySelector('#alPanel .al-all')", `${label}: Turn all off is there`);
  await p.eval("document.querySelector('#alPanel .al-all').click()");
  await until(p, "document.activeElement.id === 'toastAct'", `${label}: after Turn all off the focus is on Undo`);
  await p.eval("document.getElementById('lyFlood').click()");   // a layer switched on by hand
  await until(p, "!document.getElementById('toast').classList.contains('show') && document.activeElement !== document.body", `${label}: switching a layer on withdraws Undo, and the focus goes back to the chip or the map (not the body)`);
  await p.eval("document.getElementById('lyFlood').click()"); await until(p, "!document.getElementById('lyFlood').checked", `${label}: flood off again`);
  // a message that replaces Undo while it has the focus
  await p.eval("document.getElementById('lyProt').click()"); await until(p, "ActiveLayers.list().some(i => i.id === 'lyProt')", `${label}: protected areas on`);
  await openList(p, label); await p.eval("document.querySelector('#alPanel .al-all').click()"); await until(p, "document.activeElement.id === 'toastAct'", `${label}: focus on Undo`);
  await p.eval("toast('test message'), 0");
  await until(p, "document.activeElement !== document.body && document.activeElement.id !== 'toastAct'", `${label}: another message takes Undo's place, and the focus goes to the chip or the map`);
}

async function run2d(lang, width) {
  const label = `2D ${lang} ${width}`; console.log(label);
  const p = await openPage(`${base}/index.html?lang=${lang}`, view(width));
  await until(p, "document.querySelector('#loader.hide') && window.ActiveLayers", `${label}: the map is ready`, 60000);
  let s = await p.eval(STATE); agree(s, label + ' at the start', '2d'); check(s.n === 0, `${label}: nothing counted at the start`);
  // the menus: a click on each switch, a lazy facility layer and the shading menu
  await p.eval(`(() => { ['lyFlood', 'lyRoutes', 'lyFire', 'lyHistoric', 'lyBarrios'].forEach(id => document.getElementById(id).click()); const c = document.getElementById('choro'); c.value = 'population_2020'; c.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await until(p, n0(6), `${label}: six layers from the menus`, 30000); agree(await p.eval(STATE), label + ' menus', '2d');
  // the walk rings count only while they are drawn
  await p.eval("document.getElementById('lyStops').click(); document.getElementById('walkRings').click()");
  await until(p, n0(7) + " && document.getElementById('walkRings').checked", `${label}: stops on; the rings ticked but not drawn at this zoom, not counted`, 30000);
  await p.eval("map.setView([18.4655, -66.1057], 15, { animate: false }), 0");
  const rings = lang === 'es' ? 'Anillos de caminata' : 'Walk rings';
  await until(p, n0(8) + ` && ActiveLayers.list().some(i => i.id === 'walkRings' && i.name === ${JSON.stringify(rings)})`, `${label}: at zoom 15 the rings are drawn and counted as "${rings}"`, 30000);
  await p.eval("['walkRings', 'lyStops'].forEach(id => document.getElementById(id).click()); map.setView([18.2, -66.45], 9, { animate: false }); 0");
  await until(p, n0(6), `${label}: rings and stops off`);
  // the Economy tab: a ready-made view, then one of its layers hidden with its eye
  await p.eval("showTab('economy', { open: false })"); await until(p, "!!document.querySelector('#ecPresets [data-preset]')", `${label}: the Economy tab is ready`, 60000);
  await p.eval("document.querySelector('#ecPresets [data-preset]').click()");
  await until(p, "ActiveLayers.list().filter(i => /^ec/.test(i.id)).length >= 1 && !!document.querySelector('#ecLayers [data-act=vis]')", `${label}: Economy layers counted`);
  await p.eval("document.querySelector('#ecLayers [data-act=vis]').click()");
  const hid = lang === 'es' ? ' (oculta)' : ' (hidden)';
  await until(p, `ActiveLayers.list().some(i => /^ec/.test(i.id) && i.name.endsWith(${JSON.stringify(hid)}))`, `${label}: a hidden Economy layer stays counted, marked "${hid.trim()}"`);
  agree(await p.eval(STATE), label + ' Economy view', '2d');
  // the chat: a suggested question of the About tab
  const before = await p.eval("JSON.stringify(ActiveLayers.list().filter(i => /^ec/.test(i.id)).map(i => i.name))");
  await p.eval("document.querySelectorAll('#aboutAsk [data-ask]')[1].click()");
  await until(p, `typeof Chat !== 'undefined' && !Chat.state.busy && ActiveLayers.list().filter(i => /^ec/.test(i.id)).length >= 2 && JSON.stringify(ActiveLayers.list().filter(i => /^ec/.test(i.id)).map(i => i.name)) !== ${JSON.stringify(before)}`, `${label}: the chat's answer put its layers on the map`, 60000);
  agree(await p.eval(STATE), label + ' chat', '2d');
  await p.eval("document.getElementById('chBtn').click()"); await until(p, "!document.body.classList.contains('chat-open')", `${label}: chat closed`);
  // a composite and a route plan
  await p.eval("(async () => { ecIxApply({ t: 'z', items: [{ key: 'poverty_pct', dir: 0, w: 1 }, { key: 'laus_unemp_rate', dir: 0, w: 1 }] }, true); ecRender(); await Plan.restore('18.4655,-66.1057;18.4500,-66.0600'); })()");
  await until(p, "ActiveLayers.list().some(i => i.id === 'plan') && /&r=/.test(location.hash) && /ix=/.test(location.hash)", `${label}: the route plan is listed, the composite and route in the link`, 30000);
  await until(p, "!!Plan.result", `${label}: the route is computed`, 60000); await settle(p);   // and drawn: the map fits it
  s = await p.eval(STATE); agree(s, label + ' composite and route', '2d');
  const link = s.hash, names = s.names.slice().sort();
  await shot(p, `2d_${lang}_${width}_1chip`);
  await openList(p, label); s = await p.eval(STATE); agree(s, label + ' list open', '2d'); check(s.note, `${label}: the note about the route plan shows`);
  await shot(p, `2d_${lang}_${width}_2list`);
  // a layer's own button, and its Undo
  const h1 = s.hash;
  await p.eval("document.querySelector('#alPanel .al-x').click()"); await until(p, n0(s.n - 1), `${label}: × turns off one layer`);
  agree(await p.eval(STATE), label + ' one ×', '2d');
  await until(p, "(() => { const t = document.getElementById('toast').getBoundingClientRect(), l = document.getElementById('alPanel').getBoundingClientRect(); return document.getElementById('toast').classList.contains('show') && t.bottom <= l.top + 1; })()", `${label}: the Undo message shows above the open list, not under it`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `location.hash === ${JSON.stringify(h1)}`, `${label}: Undo after × gives back the hash`);
  // Turn all off and Undo; with only the route plan left, its note shows and Turn all off does not
  await openList(p, label); await p.eval("document.querySelector('#alPanel .al-all').click()");
  await until(p, "ActiveLayers.list().map(i => i.id).join() === 'plan' && /l=muni(&|$)/.test(location.hash) && !/(^|&)(s|e|ix|sc)=/.test(location.hash) && /&r=/.test(location.hash)", `${label}: all off but Límites and the route plan`);
  check(/^(Se apagaron \d+ capas|\d+ layers turned off)$/.test(await p.eval("document.getElementById('toastText').textContent")), `${label}: the message says how many went off`);
  await shot(p, `2d_${lang}_${width}_3undo`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `location.hash === ${JSON.stringify(h1)}`, `${label}: Undo gives back the same hash (${h1})`, 30000);
  await openList(p, label); await p.eval("document.querySelector('#alPanel .al-all').click()"); await until(p, "ActiveLayers.list().map(i => i.id).join() === 'plan'", `${label}: all off again`);
  await openList(p, label); s = await p.eval(STATE); check(s.note && !s.all && s.rows === 1, `${label}: the plan alone: its note, no Turn all off`);
  await shot(p, `2d_${lang}_${width}_4plan`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `location.hash === ${JSON.stringify(h1)}`, `${label}: Undo once more`, 30000);
  // keyboard only, then the rules of Undo
  await keyboard(p, '2d', label);
  await undoRules(p, label);
  // an outside click closes the list
  await openList(p, label);
  await p.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: width - 60, y: 400, button: 'left', clickCount: 1 }); await p.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: width - 60, y: 400, button: 'left', clickCount: 1 });
  await until(p, "document.getElementById('alChip').getAttribute('aria-expanded') === 'false'", `${label}: a click outside closes the list`);
  s = await p.eval(STATE); check(!s.missed.length, `${label}: no Spanish missing (${s.missed.join(' | ')})`); clean(p, label);
  await p.close();
  // the link, opened fresh: the same layers, by the same names (the Economy layers and the route arrive after the map is ready)
  const q = await openPage(`${base}/index.html?lang=${lang}${link}`, view(width));
  await until(q, "document.querySelector('#loader.hide') && window.ActiveLayers", `${label} link: the map is ready`, 60000);
  await until(q, `JSON.stringify(ActiveLayers.list().map(i => i.name).sort()) === ${JSON.stringify(JSON.stringify(names))}`, `${label}: the link restores the same ${names.length} layers`, 60000);
  s = await q.eval(STATE); agree(s, label + ' link', '2d'); check(!s.missed.length, `${label} link: no Spanish missing`); clean(q, label + ' link');
  await q.close();
}

// The second review of pull request 65: a zoom that hides the walk rings keeps Undo; "Turn all off" also unticks rings that are ticked but not drawn; the message of × counts
// every row that went (stops off at zoom 14 takes the drawn rings with it).
async function ringRules(lang, width) {
  const label = `2D ${lang} ${width} rings`; console.log(label);
  const start = '#c=18.45,-66.07,14&l=flood,stops,muni,rings';
  const p = await openPage(`${base}/index.html?lang=${lang}${start}`, view(width));
  // the layers of the address as a set: the link is typed flood,stops,muni,rings, and the map writes its own order (muni first) only at its first change, which
  // under load can come after settle(); the same layers in the other order are the same view (this made the four Undo checks below fail now and then)
  const L = "(new URLSearchParams(location.hash.slice(1)).get('l') || '').split(',').sort().join()";
  const msg = (n) => lang === 'es' ? (n === 1 ? `Se apagó ${n} capa` : `Se apagaron ${n} capas`) : (n === 1 ? `${n} layer turned off` : `${n} layers turned off`);
  const text = "document.getElementById('toastText').textContent", undoOn = "(document.getElementById('toast').classList.contains('show') && !document.getElementById('toastAct').hidden)";
  const x = (id) => `(document.getElementById('alChip').getAttribute('aria-expanded') === 'true' || document.getElementById('alChip').click(), document.querySelector('#alPanel .al-x[data-id=${id}]').click(), 0)`;
  await until(p, "document.querySelector('#loader.hide') && window.ActiveLayers && ActiveLayers.list().map(i => i.id).join() === 'lyFlood,lyStops,walkRings'", `${label}: the link opens with flood, stops and the drawn rings (3)`, 60000);
  await settle(p); const l0 = await p.eval(L);
  // 1. × on Flood, then zoom out to 13: the rings are no longer drawn, but no setting changed, so Undo stays
  await p.eval(x('lyFlood')); await until(p, `ActiveLayers.count() === 2 && ${undoOn} && ${text} === ${JSON.stringify(msg(1))}`, `${label}: × on Flood: "${msg(1)}" with Undo`);
  await p.eval("map.setZoom(13, { animate: false }), 0");
  await until(p, "map.getZoom() === 13 && ActiveLayers.list().map(i => i.id).join() === 'lyStops'", `${label}: at zoom 13 the rings leave the list`);
  await sleep(800); await p.eval("ActiveLayers.render(), 0");
  check(await p.eval(undoOn), `${label}: the zoom keeps Undo (no setting changed)`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `${L} === ${JSON.stringify(l0)} && document.getElementById('lyFlood').checked`, `${label}: Undo after the zoom brings Flood back (l=${l0})`, 30000);
  // 2. Turn all off at zoom 13: the ticked rings that are not drawn go off too, and stay off at zoom 14
  await openList(p, label); await p.eval("document.querySelector('#alPanel .al-all').click()");
  await until(p, `${L} === 'muni' && !document.getElementById('walkRings').checked && ${text} === ${JSON.stringify(msg(2))}`, `${label}: Turn all off unticks the hidden rings too (l=muni), "${msg(2)}"`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `${L} === ${JSON.stringify(l0)} && ActiveLayers.list().map(i => i.id).join() === 'lyFlood,lyStops' && document.getElementById('walkRings').checked`, `${label}: Undo gives back flood, stops and the ticked rings (not drawn at zoom 13)`, 30000);
  await openList(p, label); await p.eval("document.querySelector('#alPanel .al-all').click()"); await until(p, `${L} === 'muni'`, `${label}: all off again`);
  await p.eval("map.setZoom(14, { animate: false }), 0"); await until(p, "map.getZoom() === 14", `${label}: back at zoom 14`);
  await p.eval("document.getElementById('lyStops').click()");   // stops on again by hand: the rings stay off, as the list showed
  await until(p, "ActiveLayers.list().map(i => i.id).join() === 'lyStops' && !!stopCluster._map", `${label}: stops on again at zoom 14`, 30000);
  await sleep(500); check(await p.eval("!document.getElementById('walkRings').checked && !map.hasLayer(ringLayer)"), `${label}: the rings do not come back`);
  await p.eval("['lyFlood', 'walkRings'].forEach(id => document.getElementById(id).click())");
  await until(p, `${L} === ${JSON.stringify(l0)} && ActiveLayers.list().map(i => i.id).join() === 'lyFlood,lyStops,walkRings'`, `${label}: flood and the rings on again by hand (l=${l0})`, 30000);
  // 3. × on Stops at zoom 14: the rings go with it, and the message counts both
  await settle(p);
  await p.eval(x('lyStops')); await until(p, `ActiveLayers.list().map(i => i.id).join() === 'lyFlood' && ${text} === ${JSON.stringify(msg(2))}`, `${label}: × on Stops takes the drawn rings: "${msg(2)}"`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `${L} === ${JSON.stringify(l0)} && ActiveLayers.count() === 3`, `${label}: Undo gives back stops and the rings`, 30000);
  const s = await p.eval(STATE); agree(s, label + ' end', '2d'); check(!s.missed.length, `${label}: no Spanish missing`); clean(p, label);
  await p.close();
}

async function run3d(lang, width) {
  const label = `3D ${lang} ${width}`; console.log(label);
  const p = await openPage(`${base}/3d.html?lang=${lang}#c=18.3,-66.3,9&r=18.4655,-66.1057;18.4500,-66.0600`, view(width));
  await until(p, "document.querySelector('#loader.hide') && window.ActiveLayers && ActiveLayers.list().some(i => i.id === 'plan')", `${label}: the view is ready with the route of the link`, 90000);
  let s = await p.eval(STATE); agree(s, label + ' at the start', '3d'); check(s.items.join() === 'lyRoutes,lyTrips,plan', `${label}: routes, vehicles and the route counted (${s.items})`);
  await p.eval("['lyFlood', 'lyLanduse', 'lyCols', 'lyStorms'].forEach(id => document.getElementById(id).click())");
  await until(p, n0(7), `${label}: seven after the menus`); agree(await p.eval(STATE), label + ' menus', '3d');
  // the layers the 3D view shares with the 2D map since phase B: a lazy facility layer (its module and Spanish load on use), barrios, stops, and the walk rings, counted while drawn
  await p.eval("['lyFire', 'lyBarrios', 'lyStops', 'walkRings'].forEach(id => document.getElementById(id).click())");
  await until(p, n0(10) + " && typeof Facilities3D !== 'undefined' && !!map.getLayer('fac-fire') && !!map.getLayer('stops-pts') && !!map.getLayer('barrios-line')", `${label}: fire stations, barrios and stops counted (ten); the rings ticked, not drawn at zoom 9, not counted`, 60000);
  await p.eval("map.jumpTo({ center: [-66.1057, 18.4655], zoom: 15 }), 0");
  const rings = lang === 'es' ? 'Anillos de caminata' : 'Walk rings';
  await until(p, n0(11) + ` && ActiveLayers.list().some(i => i.id === 'walkRings' && i.name === ${JSON.stringify(rings)}) && map.getLayoutProperty('rings-400', 'visibility') === 'visible'`, `${label}: at zoom 15 the rings are drawn and counted as "${rings}"`, 30000);
  await p.eval("map.jumpTo({ center: [-66.3, 18.3], zoom: 9 }), 0");
  await until(p, n0(10), `${label}: back at zoom 9 the rings leave the list`);
  await p.eval("['lyFire', 'lyBarrios', 'lyStops', 'walkRings'].forEach(id => document.getElementById(id).click())");
  await until(p, n0(7) + " && map.getLayoutProperty('fac-fire', 'visibility') === 'none' && map.getLayoutProperty('stops-pts', 'visibility') === 'none'", `${label}: off again, and hidden on the map`);
  agree(await p.eval(STATE), label + ' new layers', '3d');
  // the chat: an answer that puts a dataset on the columns
  await p.eval("document.getElementById('chBtn').click()"); await until(p, "typeof Chat !== 'undefined'", `${label}: the chat loaded`, 60000);
  await p.eval(`Chat.ask(${JSON.stringify(lang === 'es' ? '¿Dónde es más alta la pobreza?' : 'Where is poverty highest?')})`);
  await until(p, "!Chat.state.busy && document.getElementById('metric').value === '__any' && ActiveLayers.list().some(i => i.id === 'lyCols' && !/^(Tourism|Lugares)/.test(i.name))", `${label}: the chat's dataset is on the columns`, 60000);
  agree(await p.eval(STATE), label + ' chat', '3d');
  await p.eval("document.getElementById('chBtn').click()"); await until(p, "!document.body.classList.contains('chat-open')", `${label}: chat closed`);
  await shot(p, `3d_${lang}_${width}_1chip`);
  await openList(p, label); s = await p.eval(STATE); agree(s, label + ' list open', '3d'); check(s.note, `${label}: the note about the route plan shows`);
  await shot(p, `3d_${lang}_${width}_2list`);
  // the 3D view writes its camera in the address (core/viewstate.js, at most every 400 ms): the snapshot waits for the camera to rest and that write to land
  await until(p, '!map.isMoving()', `${label}: the camera at rest`, 30000); await sleep(800);
  const before = await p.eval(SNAP3D);
  await p.eval("document.querySelector('#alPanel .al-all').click()");
  await until(p, "ActiveLayers.list().map(i => i.id).join() === 'plan'", `${label}: all off but the route plan`); s = await p.eval(STATE); check(s.scene === 'true,true', `${label}: terrain and buildings stay`);
  await shot(p, `3d_${lang}_${width}_3undo`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, `${SNAP3D} === ${JSON.stringify(before)}`, `${label}: Undo gives back every switch, the columns' measure and the hash`, 30000);
  // year mode: the sea level rise it switches on goes off again when the mode is left, after Turn all off and Undo too
  await p.eval("setMode('year'), 0"); await until(p, "document.getElementById('lySlr').checked && S.slrAuto", `${label}: the year mode switches sea level rise on`);
  await p.eval("ActiveLayers.off(null), 0"); await until(p, "!document.getElementById('lySlr').checked", `${label}: Turn all off turns it off`);
  await p.eval("document.getElementById('toastAct').click()"); await until(p, "document.getElementById('lySlr').checked && S.slrAuto", `${label}: Undo gives it back as the year mode's`);
  await p.eval("setMode('day'), 0"); await until(p, "!document.getElementById('lySlr').checked", `${label}: leaving the year mode turns it off`);
  await keyboard(p, '3d', label);
  await undoRules(p, label);
  s = await p.eval(STATE); check(!s.missed.length, `${label}: no Spanish missing (${s.missed.join(' | ')})`); clean(p, label);
  await p.close();
}

// The open list at a width: it ends above the map's buttons, scale and credits (and the 3D time bar) in its column, and the chip keeps its height.
const ROOM = `(() => { const l = document.getElementById('alPanel').getBoundingClientRect(), c = document.getElementById('alChip').getBoundingClientRect();
  const hard = [...document.querySelectorAll('#map .leaflet-control, #map .maplibregl-ctrl, #timebar')].map(e => [e.className.split(' ')[0] || e.id, e.getBoundingClientRect()]).filter(([, r]) => r.height && r.width && r.top > l.top + 20 && r.left < l.right && r.right > l.left);
  const hit = hard.filter(([, r]) => r.top < l.bottom - 1).map(([n, r]) => n + '@' + Math.round(r.top));
  const legend = [...document.querySelectorAll('#map .econ-legend, #map .map-legend.show')].map(e => e.getBoundingClientRect()).filter(r => r.height && r.left < l.right && r.right > l.left && r.top > l.top && r.top < l.bottom).length;
  const el = document.getElementById('alPanel'), scrolls = el.scrollHeight > el.clientHeight + 1;
  return { hit, chipH: Math.round(c.height), listH: Math.round(l.height), bottom: Math.round(l.bottom), legend, scrolls, mapH: Math.round(document.getElementById('map').getBoundingClientRect().height) }; })()`;
// two frames: the list is fitted again when the credits or the time bar change size (a ResizeObserver, which runs before a frame is painted)
const frames = (p) => p.eval('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))');
async function layout(page, lang, width) {
  const chat = width === 1024, label = `${page.toUpperCase()} ${lang} ${width}${chat ? ' chat open' : ''} layout`; console.log(label);
  const url = page === '2d' ? `${base}/index.html?lang=${lang}#c=18.4,-66.2,10&l=flood,routes,stops,hubs,taxi,prot,landuse,comunidades,wcrp,fire,police,libraries,historic,townhalls,barrios,muni&s=population_2020&r=18.4655,-66.1057;18.4500,-66.0600`
    : `${base}/3d.html?lang=${lang}#c=18.3,-66.3,9&r=18.4655,-66.1057;18.4500,-66.0600`;
  const p = await openPage(url, view(width));
  await until(p, "document.querySelector('#loader.hide') && window.ActiveLayers && ActiveLayers.list().some(i => i.id === 'plan')", `${label}: ready`, 90000);
  if (page === '3d') await p.eval("['lyFlood', 'lySlr', 'lyHubs', 'lyLanduse', 'lyProt', 'lyComunidades', 'lyWcrp', 'lyCols', 'lyStorms', 'lyFire', 'lyPolice', 'lyTownhalls', 'lyLibraries', 'lyHistoric', 'lyPubHousing', 'lyBarrios', 'lyStops', 'lyTaxi'].forEach(id => document.getElementById(id).click())");
  await until(p, "ActiveLayers.count() >= 12", `${label}: a long list`, 30000);
  if (chat) { await p.eval("document.getElementById('chBtn').click()"); await until(p, "document.body.classList.contains('chat-open') && typeof Chat !== 'undefined'", `${label}: chat open`, 60000); }
  await openList(p, label); await sleep(300);   // the map settles after the chat takes its side
  await p.eval("ActiveLayers.render(), 0"); await frames(p);
  const r = await p.eval(ROOM);
  check(!r.hit.length, `${label}: the list (bottom ${r.bottom}, ${r.listH} px of a ${r.mapH} px map${r.scrolls ? ', scrolls' : ''}) ends above the map's controls${page === '3d' ? ' and the time bar' : ''} ${r.hit.join(' ')}`);
  check(r.chipH === 34, `${label}: the chip keeps its height (${r.chipH} px)`);
  if (r.legend) console.log(`  note: the list covers a legend here (${r.legend})`);
  await shot(p, `layout_${page}_${lang}_${width}${chat ? '_chat' : ''}`);
  await p.eval("document.querySelector('#alPanel .al-x').click()");   // an Undo message while the list is open: the list starts below it
  await until(p, "(() => { const t = document.getElementById('toast'), a = t.getBoundingClientRect(), l = document.getElementById('alPanel').getBoundingClientRect(); return t.classList.contains('show') && a.bottom <= l.top + 1; })()", `${label}: an Undo message sits above the open list`);
  await frames(p); const r2 = await p.eval(ROOM); check(!r2.hit.length, `${label}: and the list still ends above the controls (bottom ${r2.bottom}, ${r2.listH} px) ${r2.hit.join(' ')}`);
  clean(p, label); check(!(await p.eval('I18N.missed')).length, `${label}: no Spanish missing`);
  await p.close();
}

(async () => {
  if (shots) fs.mkdirSync(shots, { recursive: true });
  for (const lang of langs) for (const w of widths) { await ringRules(lang, w); await run2d(lang, w); await run3d(lang, w); }
  for (const lang of langs) for (const w of layoutWidths) for (const page of ['2d', '3d']) await layout(page, lang, w);
  finished = true;
  console.log(problems.length ? `\n${passed} passed, ${problems.length} problem(s):\n- ` + problems.join('\n- ') : `\nall ${passed} checks passed`);
  process.exitCode = problems.length ? 1 : 0;
  setTimeout(() => process.exit(), 50);
})().catch(e => { console.error(e); finished = true; process.exit(2); });
