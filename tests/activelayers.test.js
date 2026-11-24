// Tests for the "layers on" chip (site/js/core/activelayers.js) with the adapters of the 2D map (site/js/app.js) and the 3D view (site/js/twin3d.js), as the pages
// write them: each page's mount(...) call is read from its script and run against stand-ins for the page (checkboxes, the shading menu, the Economy tab, the route
// planner) that keep a URL hash the way the pages write it.
//  - the count is the length of the list, and the list holds exactly the layers that are on, for 400 random states of each page;
//  - "Turn all off" then Undo gives back the same hash, and so does each layer's own button then Undo;
//  - Límites (the municipality boundaries, in both views) and the 3D view's Scene settings are never counted or turned off; the route plan is listed but kept;
//  - the walk rings count while they are drawn (zoom 14 or closer, and stops or stations on), in both views.
// Run: node --test tests/activelayers.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const AL = require(path.join(__dirname, '..', 'site', 'js', 'core', 'activelayers.js'));
AL.describe = (el) => ({ name: el.label, group: el.group });   // the label of the switch; the page reads it from the menu
const src = (f) => fs.readFileSync(path.join(__dirname, '..', 'site', 'js', f), 'utf8').replace(/\r\n/g, '\n');
const mountCall = (s) => { const i = s.indexOf('Core.activelayers.mount('), j = s.indexOf("), $('#map'));", i); assert.ok(i > 0 && j > i, 'the page mounts the chip'); return s.slice(i + 'Core.activelayers.mount('.length, j + 1); };
let s0 = 20261019; const rnd = () => { s0 |= 0; s0 = s0 + 0x6D2B79F5 | 0; let t = Math.imul(s0 ^ s0 >>> 15, 1 | s0); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };   // mulberry32

// a checkbox of a layer menu: its change handler is the page's own path (here it only records that it ran)
function box(id, checked = false) { const e = { id, checked, label: 'L:' + id, group: 'G', changes: 0, dispatchEvent() { e.changes++; } }; return e; }
// the route planner (plan.js): stops, points on the map, clear()
function fakePlan() {
  const P = { root: {}, follow: true, stops: [{ text: '', pt: null }, { text: '', pt: null }], placed() { return this.stops.filter(s => s.pt); }, clear() { this.stops = [{ text: '', pt: null }, { text: '', pt: null }]; }, render() {}, stopsChanged() {}, encode() { const p = this.placed(); return p.length >= 2 ? p.map(s => `${s.pt.lat},${s.pt.lng}`).join(';') : ''; } };
  return P;
}

// ── the 2D map ────────────────────────────────────────────────────────────
function page2d() {
  const app = src('app.js'), LAYER_KEYS = eval('(' + app.match(/const LAYER_KEYS = (\{[^}]*\});/)[1] + ')');
  const els = {}; Object.values(LAYER_KEYS).forEach(id => { els[id] = box(id, id === 'lyMuni'); });
  els.choro = { id: 'choro', value: '', options: [''],   // the shading menu was retired (decision 81 (d)): it stays empty, and the chip lists no shading
     get selectedOptions() { return [{ text: 'S:' + this.value }]; }, dispatchEvent() {} };
  // the Economy tab (economy.js ecApi): layers with ids, the composite and the scenario
  const EC = { layers: [], ix: null, scenario: null, seq: 0 };
  const api = { active: () => EC.layers.map(l => ({ id: l.id, name: l.key, group: 'Economy' })), remove(id) { EC.layers = EC.layers.filter(l => l.id !== id); }, snap: () => ({ layers: EC.layers.slice(), ix: EC.ix, sc: EC.scenario }), restore(s) { EC.layers = s.layers.slice(); EC.ix = s.ix; EC.scenario = s.sc; }, clear(o = {}) { EC.layers = []; EC.ix = null; if (o.scenario) EC.scenario = null; } };
  const Plan = fakePlan(), ECON = { api };
  let adapter = null;
  const Core = { activelayers: { ...AL, mount: (a) => { adapter = a; } } }, $ = (q) => els[q.slice(1)], T = (s) => s;
  const map = { zoom: 12, hasLayer: (l) => l === ringLayer && els.walkRings.checked && map.zoom >= 14 && (els.lyStops.checked || els.lyHubs.checked) }, ringLayer = {};   // updateRings() (app.js): the rings are drawn at zoom 14 with stops or stations on
  new Function('Core', 'LAYER_KEYS', '$', 'T', 'ECON', 'Plan', 'map', 'ringLayer', 'Core.activelayers.mount(' + mountCall(app) + ');')(Core, LAYER_KEYS, $, T, ECON, Plan, map, ringLayer);
  // the hash as writeHash() writes it (app.js)
  const hash = () => ['l=' + Object.entries(LAYER_KEYS).filter(([, id]) => els[id].checked).map(([k]) => k).join(','), els.choro.value ? 's=' + els.choro.value : '', EC.layers.length ? 'e=' + EC.layers.map(l => l.key + '.' + l.id).join(',') : '', EC.ix ? 'ix=' + EC.ix : '', EC.scenario ? 'sc=' + EC.scenario : '', Plan.encode() ? 'r=' + Plan.encode() : ''].filter(Boolean).join('&');
  const randomize = () => {
    Object.values(els).forEach(e => { if ('checked' in e && e.id !== 'lyMuni') e.checked = rnd() < .3; });
    map.zoom = rnd() < .5 ? 15 : 12;
    els.choro.value = els.choro.options[Math.floor(rnd() * 3)];
    EC.layers = Array.from({ length: Math.floor(rnd() * 4) }, (_, i) => ({ id: ++EC.seq, key: 'ds' + i }));
    EC.ix = rnd() < .3 ? 'z.poverty_pct' : null; if (EC.ix && rnd() < .5) EC.layers.push({ id: ++EC.seq, key: 'user_composite' });
    EC.scenario = rnd() < .2 ? 'sc1' : null;
    Plan.stops = rnd() < .3 ? [{ text: 'Ponce', pt: { lat: 18.01, lng: -66.61 } }, { text: 'Near Plaza', pt: { lat: 18.02, lng: -66.6 } }] : [{ text: rnd() < .5 ? 'typed' : '', pt: null }, { text: '', pt: null }];
  };
  const expected = () => Object.values(LAYER_KEYS).filter(id => id !== 'lyMuni' && els[id].checked && (id !== 'walkRings' || map.hasLayer(ringLayer))).length + (els.choro.value ? 1 : 0) + EC.layers.length + (Plan.placed().length ? 1 : 0);
  return { adapter, els, EC, Plan, hash, randomize, expected, LAYER_KEYS, map };
}

test('2D: the count is the list, and the list is what is on', () => {
  const p = page2d();
  for (let k = 0; k < 400; k++) {
    p.randomize();
    const items = p.adapter.list();
    assert.strictEqual(items.length, p.expected(), 'count');
    assert.strictEqual(new Set(items.map(i => i.id)).size, items.length, 'one row per layer');
    for (const i of items) assert.ok(i.name, 'every row has a name');
    assert.ok(!items.some(i => i.id === 'lyMuni'), 'Límites is never listed');
  }
});

test('2D: Turn all off, then Undo, gives back the same hash; Límites and the route plan stay', () => {
  const p = page2d();
  let withPlan = 0, emptied = 0;
  for (let k = 0; k < 400; k++) {
    p.randomize();
    const before = p.hash(), planBefore = JSON.stringify(p.Plan.stops), cnt = p.adapter.list().length, snap = p.adapter.snapshot(), n = p.adapter.allOff(), after = p.adapter.list();
    assert.strictEqual(p.els.lyMuni.checked, true, 'Límites stays on');
    assert.strictEqual(JSON.stringify(p.Plan.stops), planBefore, 'the route plan, with what was typed, is kept');
    assert.deepStrictEqual(after.map(i => i.id), p.Plan.placed().length ? ['plan'] : [], 'only the kept route plan is left');
    assert.strictEqual(n, cnt - after.length, 'the message counts what went off');
    assert.ok(!/(^|&)(s|e|ix|sc)=/.test(p.hash()), 'shading, Economy layers, composite and scenario are off');
    if (after.length) withPlan++; else emptied++;
    p.adapter.restore(snap);
    assert.strictEqual(p.hash(), before, 'Undo');
  }
  assert.ok(withPlan > 20 && emptied > 20, `both cases were tried (${withPlan} with a plan, ${emptied} without)`);
});

test('2D: each layer\'s own button turns off that layer only, and Undo brings it back', () => {
  const p = page2d();
  for (let k = 0; k < 200; k++) {
    p.randomize();
    const items = p.adapter.list(); if (!items.length) continue;
    const pick = items[Math.floor(rnd() * items.length)], before = p.hash(), snap = p.adapter.snapshot();
    const n = p.adapter.off(pick.id), left = p.adapter.list().map(i => i.id), gone = items.filter(i => !left.includes(i.id)).map(i => i.id);
    assert.deepStrictEqual(left, items.filter(i => !gone.includes(i.id)).map(i => i.id), 'the others keep their order');
    assert.ok(gone.includes(pick.id) && gone.every(id => id === pick.id || (id === 'walkRings' && ['lyStops', 'lyHubs'].includes(pick.id))), pick.id + ': only that layer, and the rings it drew');
    assert.strictEqual(n, gone.length, 'the message counts what went off');
    p.adapter.restore(snap);
    assert.strictEqual(p.hash(), before);
  }
  p.els.lyMuni.checked = true; p.adapter.turnOff('lyMuni'); assert.strictEqual(p.els.lyMuni.checked, true, 'Límites cannot be turned off from the chip');
});

test('2D: the layers of the hash are the layers the chip can count (only Límites is left out)', () => {
  const p = page2d();
  assert.deepStrictEqual(Object.keys(p.LAYER_KEYS).filter(k => k !== 'muni').length, Object.keys(p.LAYER_KEYS).length - 1);
  Object.values(p.els).forEach(e => { if ('checked' in e) e.checked = true; });
  p.els.choro.value = ''; p.EC.layers = []; p.Plan.clear();
  p.map.zoom = 12; assert.strictEqual(p.adapter.list().length, Object.keys(p.LAYER_KEYS).length - 2, 'the walk rings are not drawn below zoom 14');
  p.map.zoom = 15; assert.strictEqual(p.adapter.list().length, Object.keys(p.LAYER_KEYS).length - 1);
  assert.strictEqual(p.adapter.list().find(i => i.id === 'walkRings').name, 'Walk rings', 'a short name');
});

// ── the 3D view ───────────────────────────────────────────────────────────
function page3d() {
  const s = src('twin3d.js'), html = fs.readFileSync(path.join(__dirname, '..', 'site', '3d.html'), 'utf8');
  const ids = [...html.matchAll(/<input type="checkbox" id="(ly\w+|walkRings)"( checked)?/g)].map(m => [m[1], !!m[2]]);
  const els = Object.fromEntries(ids.map(([id, on]) => [id, box(id, on)]));
  els.metric = { value: 'assets', selectedOptions: [{ text: 'Tourism places' }] };
  const Plan = fakePlan(), ENG = { E: null, h: 'poverty_pct' };
  let adapter = null;
  const Core = { activelayers: { ...AL, mount: (a) => { adapter = a; } } }, $ = (q) => els[q.slice(1)], T = (x) => x;
  const S = { slrAuto: false }, map = { zoom: 12 };
  const ringsDrawn = () => els.walkRings.checked && map.zoom >= 14 && (els.lyStops.checked || els.lyHubs.checked);   // twin3d.js: the rings are drawn from zoom 14 with stops or stations on
  new Function('Core', '$', 'T', 'ENG', 'Plan', 'S', 'ringsDrawn', 'measureSnap', 'measureRestore', 'Core.activelayers.mount(' + mountCall(s) + ');')(Core, $, T, ENG, Plan, S, ringsDrawn, () => null, () => {});   // the columns' keys in the address: tests/browser/view_state.js
  const hash = () => 'c=18.2,-66.4,9' + (Plan.encode() ? '&r=' + Plan.encode() : '');   // the 3D view writes the camera and the route plan (twin3d.js drawRoute)
  const state = () => JSON.stringify(Object.values(els).filter(e => 'checked' in e).map(e => e.checked));
  return { adapter, els, Plan, hash, state, ids, S, map, ringsDrawn };
}

test('3D: data layers and the columns count; the Scene settings and Límites never do', () => {
  const p = page3d(), KEPT = ['lyTerrain', 'lyBuildings', 'lyMuni'], data = p.ids.map(([id]) => id).filter(id => !KEPT.includes(id));
  assert.ok(p.els.lyMuni && !p.els.lyMuni.checked, 'Límites is off when the view opens (2026-11-13)');
  assert.deepStrictEqual(p.adapter.list().map(i => i.id).sort(), ['lyRoutes', 'lyTrips'], 'on at the start: routes and the scheduled vehicles');
  for (let k = 0; k < 400; k++) {
    Object.values(p.els).forEach(e => { if ('checked' in e) e.checked = rnd() < .4; });
    p.Plan.stops = rnd() < .3 ? [{ text: 'A', pt: { lat: 18, lng: -66 } }, { text: '', pt: null }] : [{ text: '', pt: null }, { text: '', pt: null }];
    p.map.zoom = rnd() < .5 ? 15 : 12;
    const items = p.adapter.list();
    assert.strictEqual(items.length, data.filter(id => p.els[id].checked && (id !== 'walkRings' || p.ringsDrawn())).length + (p.Plan.placed().length ? 1 : 0));
    assert.ok(!items.some(i => KEPT.includes(i.id)), 'Scene settings and Límites are not counted');
    const cols = items.find(i => i.id === 'lyCols'); if (cols) assert.strictEqual(cols.name, 'Tourism places', 'the columns by their measure');
    const before = p.hash(), st = p.state(), terrain = p.els.lyTerrain.checked, buildings = p.els.lyBuildings.checked, muni = p.els.lyMuni.checked, snap = p.adapter.snapshot();
    p.adapter.allOff();
    assert.strictEqual(p.els.lyTerrain.checked, terrain); assert.strictEqual(p.els.lyBuildings.checked, buildings); assert.strictEqual(p.els.lyMuni.checked, muni, 'Turn all off leaves Límites');
    assert.strictEqual(p.els.walkRings.checked, false, 'and unticks the walk rings, drawn or not');
    assert.deepStrictEqual(p.adapter.list().map(i => i.id), p.Plan.placed().length ? ['plan'] : []);
    assert.strictEqual(p.hash(), before, 'camera and route plan kept');
    p.adapter.restore(snap);
    assert.strictEqual(p.state(), st, 'Undo');
  }
  for (const [id] of p.ids) assert.ok(data.includes(id) || KEPT.includes(id));
  assert.ok(data.length >= 25, 'every data layer of the menus is counted');
  for (const id of ['lyBarrios', 'lyStops', 'lyTaxi', 'walkRings', 'lyOz', 'lyPubHousing', 'lyLihtc', 'lyReservoirs', 'lyBroadband', 'lyRivers', 'lyGroundwater', 'lyRain', 'lyFire', 'lyPolice', 'lyTownhalls', 'lyLibraries', 'lySchools', 'lyHistoric', 'lyGaps', 'lyXfer']) assert.ok(data.includes(id), id + ' is counted on the 3D view too');
});

test('the words: the chip uses the groups\' count in the layer menu', () => {
  const s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'core', 'activelayers.js'), 'utf8'), c = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'common.js'), 'utf8');
  assert.ok(s.includes("Tn(n, '{n} layer on', '{n} layers on', { n })") && c.includes("Tn(n, '{n} layer on', '{n} layers on', { n })"));
});

test('what is on (sig) changes with any layer or the route plan, so a later change withdraws Undo', () => {
  const p = page2d();
  p.randomize(); p.Plan.stops = [{ text: 'A', pt: { lat: 18, lng: -66 } }, { text: 'B', pt: { lat: 18.1, lng: -66.1 } }];
  p.adapter.allOff(); const after = p.adapter.sig();
  assert.strictEqual(p.adapter.sig(), after, 'stable while nothing changes');
  p.Plan.stops[1].pt.lng = -66.2; assert.notStrictEqual(p.adapter.sig(), after, 'a moved stop');
  p.Plan.stops[1].pt.lng = -66.1; assert.strictEqual(p.adapter.sig(), after);
  p.els.lyFlood.checked = true; assert.notStrictEqual(p.adapter.sig(), after, 'a layer switched on');
});

test('3D: Undo in the year mode gives back the sea level rise the mode switched on, so leaving the mode still turns it off', () => {
  const p = page3d();
  p.els.lySlr.checked = true; p.S.slrAuto = true;   // setMode('year') (twin3d.js)
  p.els.lySlr.dispatchEvent = () => { p.S.slrAuto = false; };   // its change handler: a hand on the switch
  const snap = p.adapter.snapshot(); p.adapter.allOff();
  assert.strictEqual(p.els.lySlr.checked, false);
  p.adapter.restore(snap);
  assert.strictEqual(p.els.lySlr.checked, true); assert.strictEqual(p.S.slrAuto, true);
});

test('2D: a zoom that hides or draws the walk rings is not a change of settings, so Undo stays (PR #65 review)', () => {
  const p = page2d();
  for (const id of ['lyFlood', 'lyStops', 'walkRings']) p.els[id].checked = true;
  p.map.zoom = 14; assert.ok(p.adapter.list().some(i => i.id === 'walkRings'), 'drawn at zoom 14');
  assert.strictEqual(p.adapter.off('lyFlood'), 1);
  const after = p.adapter.sig();
  p.map.zoom = 13; assert.ok(!p.adapter.list().some(i => i.id === 'walkRings'), 'not drawn at zoom 13');
  assert.strictEqual(p.adapter.sig(), after, 'the zoom leaves what is on the same');
  p.map.zoom = 15; assert.strictEqual(p.adapter.sig(), after);
  p.els.walkRings.checked = false; assert.notStrictEqual(p.adapter.sig(), after, 'unticking the rings is a change');
});

test('2D: Turn all off also unticks walk rings that are ticked but not drawn, and Undo ticks them again', () => {
  const p = page2d();
  for (const id of ['lyFlood', 'lyStops', 'walkRings']) p.els[id].checked = true;
  p.map.zoom = 12;
  const before = p.hash(), snap = p.adapter.snapshot();
  assert.ok(/rings/.test(before));
  assert.strictEqual(p.adapter.allOff(), 2, 'the message counts the rows of the list: flood and stops');
  assert.strictEqual(p.els.walkRings.checked, false, 'the hidden rings go off too');
  assert.ok(!/rings/.test(p.hash()), 'and leave the link');
  p.map.zoom = 15; assert.deepStrictEqual(p.adapter.list(), [], 'they do not come back at zoom 14');
  p.adapter.restore(snap); assert.strictEqual(p.hash(), before, 'Undo');
});

test('2D: a layer\'s button counts every row that went with it (stops off: the drawn walk rings go too)', () => {
  const p = page2d();
  for (const id of ['lyFlood', 'lyStops', 'walkRings']) p.els[id].checked = true;
  p.map.zoom = 15;
  assert.strictEqual(p.adapter.list().length, 3);
  assert.strictEqual(p.adapter.off('lyStops'), 2, 'stops and the rings');
  assert.deepStrictEqual(p.adapter.list().map(i => i.id), ['lyFlood']);
  assert.strictEqual(p.adapter.off('lyFlood'), 1);
  assert.strictEqual(p.adapter.off('lyFlood'), 0, 'a row that is no longer there');
  p.els.lyHubs.checked = true; p.els.lyStops.checked = true;
  assert.strictEqual(p.adapter.off('lyStops'), 1, 'the rings stay while stations are on');
});

test('3D: what is on (sig) follows the switches and the columns\' measure, nothing else', () => {
  const p = page3d(), a = p.adapter.sig();
  assert.strictEqual(p.adapter.sig(), a);
  p.els.lyCols.checked = true; const b = p.adapter.sig(); assert.notStrictEqual(b, a);
  p.els.metric.selectedOptions = [{ text: 'Population' }]; assert.notStrictEqual(p.adapter.sig(), b, 'another measure for the columns');
  p.els.lyCols.checked = false; assert.strictEqual(p.adapter.sig(), a);
});

test('3D: the walk rings count while they are drawn, and a zoom that hides them keeps Undo (as on the 2D map)', () => {
  const p = page3d();
  for (const id of ['lyFlood', 'lyStops', 'walkRings']) p.els[id].checked = true;
  p.els.lyRoutes.checked = p.els.lyTrips.checked = false;
  p.map.zoom = 13; assert.deepStrictEqual(p.adapter.list().map(i => i.id).sort(), ['lyFlood', 'lyStops'], 'not drawn at zoom 13');
  p.map.zoom = 14; assert.deepStrictEqual(p.adapter.list().map(i => i.id).sort(), ['lyFlood', 'lyStops', 'walkRings'], 'drawn at zoom 14');
  assert.strictEqual(p.adapter.list().find(i => i.id === 'walkRings').name, 'Walk rings', 'a short name');
  const sig = p.adapter.sig(); p.map.zoom = 12; assert.strictEqual(p.adapter.sig(), sig, 'the zoom changes no setting');
  p.map.zoom = 15; assert.strictEqual(p.adapter.off('lyStops'), 2, 'stops off take the drawn rings with them');
  p.els.lyStops.checked = true; p.els.lyHubs.checked = true; assert.strictEqual(p.adapter.off('lyStops'), 1, 'the rings stay while stations are on');
});
