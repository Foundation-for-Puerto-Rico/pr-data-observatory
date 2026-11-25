// Tests for the view state the 2D map and the 3D view share through the address (site/js/core/viewstate.js, docs/view-state.md).
// Run: node --test tests/viewstate.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const SITE = path.join(ROOT, 'site');
const V = require(path.join(SITE, 'js', 'core', 'viewstate.js'));
const LY = require(path.join(SITE, 'js', 'core', 'layers.js'));
const read = (f) => fs.readFileSync(path.join(SITE, f), 'utf8');

test('a full address reads: the municipality, the camera, layers, measure, Economy, route and base map', () => {
  const h = '#Ponce&c=18.0111,-66.6141,12&b=-20.5&p=60&l=routes,stops,-trips&s=poverty_pct&pv=hex2&r=abc&e=income_pc.f.pc,poverty_pct.s&ey=2020&eb=2014&ix=a%2Cb&sc=x1&slr=3&bm=liberty';
  const P = V.parse(h);
  assert.strictEqual(P.muni, 'Ponce');
  assert.deepStrictEqual(P.c, { lat: 18.0111, lng: -66.6141, z: 12 });
  assert.strictEqual(P.b, -20.5); assert.strictEqual(P.p, 60);
  assert.deepStrictEqual(P.l, ['routes', 'stops', '-trips']);
  assert.strictEqual(P.s, 'poverty_pct'); assert.strictEqual(P.pv, 'hex2'); assert.strictEqual(P.r, 'abc');
  assert.strictEqual(P.e, 'income_pc.f.pc,poverty_pct.s'); assert.strictEqual(P.ey, 2020); assert.strictEqual(P.eb, 2014);
  assert.strictEqual(P.ix, 'a,b', 'ix= is decoded'); assert.strictEqual(P.sc, 'x1'); assert.strictEqual(P.slr, 3); assert.strictEqual(P.bm, 'liberty');
  assert.strictEqual(V.parse('#San%20Juan&c=18.4,-66.1,11').muni, 'San Juan');
  assert.strictEqual(V.parse('#Mayag%C3%BCez').muni, 'Mayagüez');
});

test('round trip: what a view writes reads back the same, and a view that changes nothing gives the address back as it was', () => {
  const h = '#Ponce&c=18.0111,-66.6141,12&b=-20.5&p=60&l=routes,stops,-trips&s=poverty_pct&r=abc&e=income_pc.f.pc%2Cpoverty_pct.s&ey=2020&ix=a%2Cb&bm=none';
  assert.strictEqual(V.write('2d', h, {}), h);
  assert.strictEqual(V.write('3d', h, {}), h);
  const w = V.write('2d', '', { muni: 'Cabo Rojo', c: V.cOf(18.08, -67.15, 11.5), l: ['routes', '-muni'], s: 'vacancy_pct', e: 'a.f,b.s', ey: '2021', bm: 'positron' });
  assert.strictEqual(w, '#Cabo%20Rojo&c=18.0800,-67.1500,11.5&l=routes,-muni&s=vacancy_pct&e=a.f%2Cb.s&ey=2021&bm=positron');
  const P = V.parse(w);
  assert.deepStrictEqual([P.muni, P.c, P.l, P.s, P.e, P.ey, P.bm], ['Cabo Rojo', { lat: 18.08, lng: -67.15, z: 11.5 }, ['routes', '-muni'], 'vacancy_pct', 'a.f,b.s', 2021, 'positron']);
  assert.strictEqual(V.write('2d', w, {}), w);
});

test('old links still read: the 2D map\'s own (bare municipality, c, l, s, e encoded) and the 3D view\'s (c, r, bm)', () => {
  const old2d = '#Arecibo&c=18.4500,-66.7300,11&l=flood,muni&s=sfha_pct&e=poverty_pct.f.value.blues.q.1.1.0.85.0&slr=2';
  const P = V.parse(old2d);
  assert.deepStrictEqual([P.muni, P.l, P.s, P.slr], ['Arecibo', ['flood', 'muni'], 'sfha_pct', 2]);
  assert.strictEqual(P.e, 'poverty_pct.f.value.blues.q.1.1.0.85.0');
  assert.strictEqual(V.write('2d', old2d, {}), old2d, 'an old 2D link is written back unchanged');
  const old3d = '#c=18.2208,-66.5901,9&r=xyz&bm=liberty';
  const Q = V.parse(old3d);
  assert.deepStrictEqual([Q.c, Q.r, Q.bm, Q.l, Q.b, Q.p], [{ lat: 18.2208, lng: -66.5901, z: 9 }, 'xyz', 'liberty', null, null, null]);
  assert.deepStrictEqual(V.layerPlan('3d', Q.l), {}, 'no l= (a link from before): every layer keeps its state');
});

test('bogus values are ignored, unknown keys are kept, one-time requests are dropped', () => {
  const P = V.parse('#c=91,-66,10&b=abc&p=120&s=<script>&ey=20x0&slr=11&bm=Sat%20map&pv=a-b&zz=1&l=routes,<b>,-x y');
  assert.deepStrictEqual([P.c, P.b, P.p, P.s, P.ey, P.slr, P.bm, P.pv], [null, null, null, null, null, null, null, null]);
  assert.deepStrictEqual(P.l, ['routes'], 'only keys that read');
  for (const c of ['18,-66', '18,-66,x', 'a,b,c', '18,-66,99', '', '18,-200,9']) assert.strictEqual(V.parse('#c=' + c).c, null, c);
  assert.strictEqual(V.parse('#%E0%A4%A').muni, '%E0%A4%A', 'a broken escape stays as it came');
  const w = V.write('3d', '#c=18,-66,9&future=1&ask=hello&wb=table&wc=a,b&l=routes', { c: V.cOf(18.1, -66.2, 10) });
  assert.strictEqual(w, '#c=18.1000,-66.2000,10&l=routes&future=1', 'future= kept after the known keys; ask=, wb= and wc= dropped');
  assert.strictEqual(V.write('2d', '#c=1,2,3&s=x', { s: null, c: null }), '', 'null takes a key out; nothing left, no hash');
  assert.strictEqual(V.parse('#c=1,2,3&c=4,5,6').c.lat, 1, 'a key twice: the first counts');
  const rebuilt = V.parse('#c=18.2%2C-66.5%2C9&l=routes%2C-trips&s=vacancy_pct');   // an address rebuilt by URLSearchParams (chat.js chHandIn)
  assert.deepStrictEqual([rebuilt.c, rebuilt.l], [{ lat: 18.2, lng: -66.5, z: 9 }, ['routes', '-trips']]);
});

test('layers: each view writes its own and keeps the other\'s; "-key" for a layer on by default that is off', () => {
  const on2 = new Set(['lyRoutes', 'lyNow']), def2 = new Set(['lyMuni']);
  const t2 = V.layerTokens('2d', id => on2.has(id), id => def2.has(id));
  assert.deepStrictEqual(t2, ['-muni', 'routes', 'now']);
  const on3 = new Set(['lyMuni', 'lyStorms', 'lyTerrain']), def3 = new Set(['lyMuni', 'lyRoutes', 'lyTrips', 'lyTerrain', 'lyBuildings']);
  const t3 = V.layerTokens('3d', id => on3.has(id), id => def3.has(id));
  assert.deepStrictEqual(t3, ['muni', '-routes', '-trips', 'storms', 'terrain', '-buildings']);
  // the 2D map rewrites an address the 3D view wrote: its layers from its switches, the 3D-only ones kept
  const h = V.write('2d', '#c=1,2,3&l=' + t3.join(','), { l: t2 });
  assert.deepStrictEqual(V.parse(h).l, ['-muni', 'routes', 'now', '-trips', 'storms', 'terrain', '-buildings']);
  // and the 3D view reads it back: its own as they were, the shared ones as the 2D map left them
  const plan3 = V.layerPlan('3d', V.parse(h).l, id => def3.has(id));
  assert.strictEqual(plan3.lyRoutes, true); assert.strictEqual(plan3.lyMuni, false); assert.strictEqual(plan3.lyTrips, false);
  assert.strictEqual(plan3.lyStorms, true); assert.strictEqual(plan3.lyTerrain, true); assert.strictEqual(plan3.lyBuildings, false);
  assert.strictEqual(plan3.lyFlood, false, 'a layer of both views not listed is off');
  assert.ok(!('lyNow' in plan3), 'a 2D-only layer is not drawn in 3D');
  // a link from the 2D map that does not name the 3D vehicles leaves them on (the 2D map cannot say)
  const plan = V.layerPlan('3d', ['routes', 'muni'], id => def3.has(id));
  assert.strictEqual(plan.lyTrips, true); assert.strictEqual(plan.lyTerrain, true); assert.strictEqual(plan.lyStorms, false);
  assert.deepStrictEqual(V.layerPlan('2d', ['routes', 'unknown', '-x']), Object.fromEntries(Object.values(V.LAYERS).filter(L => L['2d']).map(L => [L['2d'], L['2d'] === 'lyRoutes'])));
});

test('the layer keys are the published ones: app.js LAYER_KEYS and core/layers.js', () => {
  const app = read('js/app.js'), LAYER_KEYS = eval('(' + app.match(/const LAYER_KEYS = (\{[^}]*\});/)[1] + ')');
  const in2d = Object.fromEntries(Object.entries(V.LAYERS).filter(([, L]) => L['2d']).map(([k, L]) => [k, L['2d']]));
  assert.deepStrictEqual(Object.keys(in2d).sort(), Object.keys(LAYER_KEYS).sort());
  for (const [k, id] of Object.entries(LAYER_KEYS)) assert.strictEqual(in2d[k], id, k);
  for (const r of LY.rows()) {
    if (!r.id || r.head) continue;
    if (r.key) { const L = V.LAYERS[r.key]; assert.ok(L, r.key); for (const v of r.views) assert.strictEqual(L[v], r.id, `${r.key} in ${v}`); continue; }
    if (['choro', 'lyCols'].includes(r.id)) continue;   // the measure (s=, e=), not a layer
    const k = Object.keys(V.LAYERS).find(x => Object.values(V.LAYERS[x]).includes(r.id));
    assert.ok(k, `${r.id} has an l= key`);
    assert.deepStrictEqual(Object.keys(V.LAYERS[k]), r.views, `${r.id}: the views of core/layers.js`);
  }
  const ids3 = [...read('3d.html').matchAll(/id="(ly[A-Za-z]+|walkRings)"/g)].map(m => m[1]);
  for (const L of Object.values(V.LAYERS)) if (L['3d']) assert.ok(ids3.includes(L['3d']), L['3d'] + ' in 3d.html');
});

test('the 3D columns from the Economy layers: height from the Symbol layer (else the Shaded), color from the Shaded; and back', () => {
  assert.deepStrictEqual(V.econColumns('poverty_pct.f.value.blues'), { h: 'poverty_pct', c: '', hNorm: 'value', cNorm: null });
  assert.deepStrictEqual(V.econColumns('income_pc.f.pc,jobs.s.per1000'), { h: 'jobs', c: 'income_pc', hNorm: 'per1000', cNorm: 'pc' });
  assert.deepStrictEqual(V.econColumns('a.b,b.f'), { h: 'a', c: '', hNorm: null, cNorm: null }, 'by barrio counts as Shaded; the second Shaded is not used');
  assert.deepStrictEqual(V.econColumns('x.s'), { h: 'x', c: '', hNorm: null, cNorm: null });
  for (const e of ['', null, ',', '<b>.f']) assert.strictEqual(V.econColumns(e), null, String(e));
  const prev = 'income_pc.f.pc.reds.q.1.1.0.85.0,jobs.s.per1000.x.q.1.1.0.75.2';
  assert.strictEqual(V.econOf('jobs', 'income_pc', prev), prev, 'the same columns: the 2D map\'s layers stay as they were');
  assert.strictEqual(V.econOf('rent', 'income_pc', prev), 'income_pc.f.pc.reds.q.1.1.0.85.0,rent.s', 'a new height: the color keeps its token');
  assert.strictEqual(V.econOf('rent', '', prev), 'rent.f');
  assert.strictEqual(V.econOf('rent', 'rent', null, { h: 'pc' }), 'rent.f.pc');
  for (const [h, c] of [['a', ''], ['a', 'b']]) assert.deepStrictEqual(V.econColumns(V.econOf(h, c, '')), { h, c, hNorm: null, cNorm: null }, `${h}/${c} round trip`);
});

test('the zoom of the address is the 2D map\'s (Leaflet); MapLibre\'s is one less; c= has 4 decimals of degrees and 2 of zoom', () => {
  assert.strictEqual(V.toMapLibre(12), 11); assert.strictEqual(V.fromMapLibre(11.37), 12.37);
  assert.strictEqual(V.cOf(18.123456, -66.987654, 12.3456), '18.1235,-66.9877,12.35');
  assert.strictEqual(V.cOf(18, -66, 9), '18.0000,-66.0000,9');
});

test('both views use the schema: the 2D map writes and reads it, the 3D view reads it, writes its camera with replaceState (throttled), and both links carry the whole address', () => {
  const app = read('js/app.js'), t = read('js/twin3d.js');
  for (const page of ['index.html', '3d.html']) assert.match(read(page), /<script src="js\/core\/viewstate\.js\?v=\d+"><\/script>/, page);
  assert.match(app, /const hash = VS\.write\('2d', location\.hash, \{/);
  assert.match(app, /l: VS\.layerTokens\('2d'/);
  assert.match(app, /Core\.viewstate\.layerPlan\('2d', h\.l\.split\(','\)/);
  assert.match(app, /l3\.href = '3d\.html' \+ location\.search \+ hash;/, 'the 3D link keeps ?lang=');
  assert.match(t, /const IN = Core\.viewstate\.parse\(location\.hash\);/);
  assert.match(t, /if \(IN\.c\) map\.jumpTo\(\{ center: \[IN\.c\.lng, IN\.c\.lat\], zoom: Math\.max\(5, Core\.viewstate\.toMapLibre\(IN\.c\.z\)\)/);
  assert.match(t, /bearing: IN\.b/); assert.match(t, /pitch: IN\.p/);
  const ws = /function writeState\(now\) \{[\s\S]*?\n\}/.exec(t)[0];
  assert.match(ws, /if \(!VS\.ready\) return;/, 'nothing is written before the view has applied the address');
  assert.match(ws, /400 - \(Date\.now\(\) - VS\.last\)/, 'at most every 400 ms');
  assert.match(ws, /setTimeout\(writeNow, wait\)/);
  const wn = /function writeNow\(\) \{[\s\S]*?\n\}/.exec(t)[0];
  assert.match(wn, /history\.replaceState\(/); assert.doesNotMatch(t, /history\.pushState/);
  assert.match(wn, /c: V\.cOf\(c\.lat, c\.lng, V\.fromMapLibre\(map\.getZoom\(\)\)\), b: /);
  assert.match(t, /map\.on\('moveend', \(\) => writeState\(\)\);/);
  assert.match(t, /l2d\.href = 'index\.html' \+ location\.search \+ Core\.viewstate\.write\('3d', location\.hash, \{\}\)/, 'the 2D link keeps ?lang=');
  assert.match(t, /performance\.mark\('ready'\);[^\n]*\n\s*applyState\(\);/, 'the address is applied once the view is ready');
  assert.doesNotMatch(t, /history\.replaceState\(null, '', `#c=/, 'no writer of its own beside writeState');
  assert.match(t, /<a href="\$\{esc\(cardLink2d\(m\.municipality\)\)\}" data-to2d=/, 'the card\'s 2D link selects its municipality');
  assert.match(t, /function cardLink2d\(name\) \{ return 'index\.html' \+ location\.search \+ Core\.viewstate\.write\('3d', location\.hash, \{ muni: name, c: null \}\); \}/);
  assert.match(t, /querySelectorAll\('a\[data-to2d\]'\)\.forEach\(a => \{ a\.href = cardLink2d\(a\.dataset\.to2d\); \}\)/, 'an open card\'s link follows the address (review of #97)');
  assert.match(t, /Core\.activelayers\.state\(measureSnap, measureRestore\)/, 'Undo of Turn all off puts the columns\' keys back as they were (review of #97)');
  assert.match(t, /const l2d = [^\n]*if \(l2d && window\.Core && Core\.viewstate\) l2d\.href = 'index\.html' \+ location\.search \+ Core\.viewstate\.write/, 'without WebGL the 2D link carries the address');
  const chat = read('js/chat.js'), hand = /function chHandIn\(q\) \{[\s\S]*?\n\}/.exec(chat)[0];
  assert.doesNotMatch(hand, /URLSearchParams/, 'ask= is taken out without URLSearchParams ("#Ponce" would become "Ponce=")');
});

// ── Review of #97: keys that are names of Object.prototype, duplicates, and the caps on what is kept ─────────────────────────────────────────────────
const HOSTILE = ['constructor', '__proto__', 'toString', 'hasOwnProperty'];
test('a key or value named like Object.prototype (constructor, __proto__, toString, hasOwnProperty) is no measure, no layer and no special key', () => {
  const METRIC = { vacancy_pct: {} };
  for (const h of HOSTILE) {
    const P = V.parse(`#${h}&c=18,-66,9&s=${h}&e=${h}.f%2C${h}.s&l=${h},-${h},routes&${h}=1`);
    assert.strictEqual(P.muni, h, 'a municipality is just a name (the views look it up among theirs)');
    assert.strictEqual(V.has(METRIC, P.s), false, `s=${h}`);
    assert.strictEqual(V.has(METRIC, 'vacancy_pct'), true);
    assert.deepStrictEqual(V.layerPlan('3d', P.l), Object.fromEntries(Object.entries(V.LAYERS).filter(([, L]) => L['3d']).map(([k, L]) => [L['3d'], k === 'routes' ? true : V.shared(k) ? false : false])), `l=${h}`);
    assert.strictEqual(V.shared(h), false); assert.deepStrictEqual(V.foreignLayers('2d', [h, '-' + h]), [h, '-' + h], 'kept as a layer of no view');
    assert.deepStrictEqual(V.econColumns(P.e), /^[a-z0-9_]+$/.test(h) ? { h, c: '', hNorm: null, cNorm: null } : null, 'a name the engine looks up in its own datasets (E.V has no prototype); with capitals, no dataset key at all');
    assert.strictEqual(P.raw[h], '1', `${h}= is a key like any other`);
    assert.match(V.write('2d', `#c=1,2,3&${h}=1`, {}), new RegExp(`&${h}=1$`), `${h}= is kept`);
  }
  assert.strictEqual(Object.getPrototypeOf(V.parse('#a=1').raw), null);
});

test('a key twice: the first counts, in viewstate.parse and in the 2D map\'s parseHash (which uses it)', () => {
  assert.strictEqual(V.parse('#s=a&s=b').s, 'a'); assert.strictEqual(V.parse('#Ponce&Mayaguez').muni, 'Ponce');
  const app = read('js/app.js'), fn = /function parseHash\(\) \{[\s\S]*?\n\}/.exec(app)[0];
  assert.match(fn, /Core\.viewstate\.parse\(location\.hash\)/);
  const parseHash = new Function('Core', 'location', fn + '; return parseHash();');
  const h = parseHash({ viewstate: V }, { hash: '#Ponce&s=a&e=x.f%2Cy.s&s=b&Mayaguez&constructor=1' });
  assert.deepStrictEqual([h.muni, h.s, h.e, h.constructor], ['Ponce', 'a', 'x.f%2Cy.s', '1'], 'the first of each; e= still encoded for economy.js; constructor is a key');
  assert.match(read('js/economy.js'), /Core\.viewstate\.has\(SHADE_DS, EC\.pending\.s\)/); assert.match(app, /!VS\.has\(SHADE_DS, was\.s\)/);   // the retired shading menu: s= opens its dataset
  const t = read('js/twin3d.js');
  assert.match(t, /one = !cols && Core\.viewstate\.has\(METRIC, IN\.s\)/); assert.match(t, /!V\.has\(METRIC, was\.s\)/);
  assert.doesNotMatch(app + t, /(SHADE_DS|METRIC)\[(h|IN|was)\.s\]/, 'no lookup of a hash value through the prototype');
});

test('what a view keeps of keys it does not know is capped: 200 characters a value, 1,000 in all, 40 layer tokens of the other view', () => {
  const big = 'x'.repeat(60000);
  assert.strictEqual(V.write('3d', `#c=1,2,3&zz=${big}&ok=1`, {}), '#c=1,2,3&ok=1', 'a 60 KB value is dropped, a small one kept');
  const many = Array.from({ length: 30 }, (_, i) => `k${i}=${'y'.repeat(60)}`).join('&');
  const w = V.write('3d', '#c=1,2,3&' + many, {});
  assert.ok(w.length - '#c=1,2,3'.length <= V.KEEP.total, `the unknown part stays within ${V.KEEP.total} characters (${w.length})`);
  assert.ok(/k0=y/.test(w) && !/k29=/.test(w), 'the first ones are kept');
  assert.strictEqual(V.write('3d', '#e=' + 'a.f%2C'.repeat(100), {}).length > 200, true, 'a known key is not capped (e= can be long)');
  const toks = Array.from({ length: 100 }, (_, i) => 'z' + i).join(',');
  assert.strictEqual(V.parse(V.write('3d', '#l=' + toks, { l: ['routes'] })).l.length, 1 + V.KEEP.layers);
});

// ── Second review of #97: raw text for Undo, every written value encoded, prototype names in the palettes and the engine ─────────────────────────────
test('a value written is encoded, so it cannot add a key; { raw } passes an address\'s text through as it came', () => {
  assert.strictEqual(V.write('3d', '#c=1,2,3', { s: 'x&ask=hello&c=0,0,1' }), '#c=1,2,3&s=x%26ask%3Dhello%26c%3D0,0,1');
  const P = V.parse(V.write('3d', '#c=1,2,3', { s: 'x&ask=hello', r: 'a#b', pv: 'p q' }));
  assert.deepStrictEqual([P.c, P.raw.ask, P.r, P.raw.pv], [{ lat: 1, lng: 2, z: 3 }, undefined, 'a#b', 'p%20q'], 'no key added; the values read back');
  for (const raw of ['x%26ask%3Dhello%26c%3D0,0,1', '%ZZ', 'qcew_jobs.f.per1000.blue.q.1.1.0.85.0%2Cqcew_gov_jobs.s.value']) {
    const w = V.write('3d', '#c=18,-66,9', { s: { raw }, e: { raw }, ey: { raw: '' } });
    assert.strictEqual(w, `#c=18,-66,9&s=${raw}&e=${raw}`, `raw ${raw} through, unchanged; { raw: '' } takes a key out`);
    assert.deepStrictEqual(Object.keys(V.parse(w).raw), ['c', 's', 'e'], 'no key planted');
  }
  assert.doesNotThrow(() => V.parse('#s=%ZZ&e=%E0%A4%A'));
  const t = read('js/twin3d.js'), snap = /function measureSnap\(\) \{[\s\S]*?\n\}/.exec(t)[0];
  assert.doesNotMatch(snap, /decodeURIComponent/, 'the Undo snapshot never decodes (a broken % threw)');
  assert.match(snap, /\{ raw: k in raw \? raw\[k\] : '' \}/);
});

test('palettes.ramp and the engine\'s classes look up own names only (a link\'s ramp or class "constructor")', () => {
  const P = require(path.join(SITE, 'js', 'core', 'palettes.js'));
  for (const h of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) assert.strictEqual(P.ramp(h), P.RAMPS.blue, h);
  assert.match(read('js/core/engine.js'), /classes: Object\.prototype\.hasOwnProperty\.call\(CLASS_NAME, cl\) \? CLASS_NAME\[cl\] : undefined/);
});

// ── Third review of #97 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
test('3D follows the chip\'s x and "Turn all off" (change events that do not bubble): its change listener captures; a ramp not offered is written as drawn; a broken % on the WCRP and Data management pages throws nothing', () => {
  assert.match(read('js/twin3d.js'), /document\.addEventListener\('change', e => \{ if \(VS\.ready && e\.target\.closest && e\.target\.closest\('#panel'\)\) writeState\(\); \}, true\);/);
  assert.match(read('js/core/activelayers.js'), /new Event\('change'\)/, 'the chip fires a change that does not bubble (so 2D listeners in the bubble phase are not reached)');
  assert.match(read('js/core/engine.js'), /ramp: ramp && !Object\.prototype\.hasOwnProperty\.call\(palettes\.RAMPS, ramp\) \? 'blue' : ramp/);
  assert.match(read('js/wcrp.js'), /try \{ id = decodeURIComponent\(/); assert.match(read('js/datamgmt.js'), /try \{ h = decodeURIComponent\(location\.hash\.slice\(1\)\); \} catch/);
  assert.ok(+/js\/wcrp\.js\?v=(\d+)/.exec(read('wcrp.html'))[1] >= 10, 'wcrp.js at v=10 or later'); assert.ok(+/js\/datamgmt\.js\?v=(\d+)/.exec(read('data-management.html'))[1] >= 2, 'datamgmt.js at v=2 or later');
});
test('Límites (municipal boundaries) is off when either view opens; a link still turns it on or off (2026-11-13)', () => {
  for (const f of ['index.html', '3d.html']) {
    assert.match(read(f), /<input type="checkbox" id="lyMuni">/, `${f}: Límites starts unticked`);
    assert.doesNotMatch(read(f), /id="lyMuni" checked/, `${f}: not ticked by default`);
  }
  const app = read('js/app.js'), t3 = read('js/twin3d.js');
  assert.match(app, /\}\);\r?\n\s*if \(\$\('#lyMuni'\)\.checked\) map\.addLayer\(muniLayer\);/, '2D: the boundaries are drawn at load only when the switch is on');
  assert.doesNotMatch(app, /muniLayer = L\.geoJSON\([^;]*\}\)\.addTo\(map\)/, '2D: not added to the map unconditionally');
  assert.match(t3, /id: 'muni-line', type: 'line', source: 'munis', layout: \{ visibility: \$\('#lyMuni'\)\.checked \? 'visible' : 'none' \}/, '3D: the line follows the switch');
  const off = () => false;   // byDefault: Límites is no longer on by default
  for (const view of ['2d', '3d']) {
    assert.strictEqual(V.layerPlan(view, ['muni'], off).lyMuni, true, `${view}: l=muni turns it on`);
    assert.strictEqual(V.layerPlan(view, ['-muni'], off).lyMuni, false, `${view}: an older link's -muni keeps it off`);
    assert.strictEqual(V.layerPlan(view, ['flood'], off).lyMuni, false, `${view}: a link that does not name it leaves it off`);
    assert.deepStrictEqual(V.layerPlan(view, null, off), {}, `${view}: no l= changes nothing, so the default (off) holds`);
    assert.deepStrictEqual(V.layerTokens(view, id => id === 'lyMuni', off).filter(t => /muni/.test(t)), ['muni'], `${view}: on, it is written as muni`);
    assert.deepStrictEqual(V.layerTokens(view, () => false, off).filter(t => /muni/.test(t)), [], `${view}: off, it is not written`);
  }
});

test('rg= (the region filter of Reference, decision 113): read, written after bm=, kept by the other view, a bad id ignored', () => {
  assert.strictEqual(V.parse('#c=18.2,-66.5,9&rg=ersv').rg, 'ersv');
  assert.strictEqual(V.parse('#rg=reg-sol-norte').rg, 'reg-sol-norte');
  for (const bad of ['#rg=Ersv', '#rg=a%26b', '#rg=__proto__', '#rg=' + 'x'.repeat(41)]) assert.strictEqual(V.parse(bad).rg, null, bad);
  assert.strictEqual(V.write('2d', '', { c: V.cOf(18.2, -66.5, 9), bm: 'dark', rg: 'ersv' }), '#c=18.2000,-66.5000,9&bm=dark&rg=ersv');
  assert.strictEqual(V.write('3d', '#c=18.2000,-66.5000,9&rg=ersv', { b: '10' }), '#c=18.2000,-66.5000,9&b=10&rg=ersv', 'the 3D view keeps the 2D pick');
  assert.strictEqual(V.write('2d', '#c=18.2000,-66.5000,9&rg=ersv', { rg: null }), '#c=18.2000,-66.5000,9', '"All of Puerto Rico" takes it out');
});
