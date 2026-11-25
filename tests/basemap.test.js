// Tests for the base-map configuration (site/js/core/basemap.js, docs/basemap.md). Run: node --test tests/basemap.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const SITE = path.join(ROOT, 'site');
const B = require(path.join(SITE, 'js', 'core', 'basemap.js'));
const read = (f) => fs.readFileSync(path.join(SITE, f), 'utf8');

test('the four kinds of source are named apart, each with its license, link and role', () => {
  const roles = Object.values(B.SOURCES).map(s => s.role);
  for (const r of ['geographic data source', 'vector schema', 'tile provider', 'rendering library', 'terrain source']) assert.ok(roles.includes(r), r);
  for (const [id, s] of Object.entries(B.SOURCES)) {
    for (const k of ['name', 'url', 'licence', 'licence_url']) assert.ok(s[k], `${id}.${k}`);
    assert.match(s.url, /^https:\/\//, id); assert.match(s.licence_url, /^https:\/\//, id);
    if (s.credit) { assert.ok(s.credit.en && s.credit.es, `${id}: credit in both languages`); }
  }
  assert.strictEqual(B.SOURCES.osm.licence, 'Open Database License (ODbL) 1.0');
});

test('the base map credits OpenStreetMap (linked to its copyright page), OpenMapTiles and OpenFreeMap, in English and Spanish', () => {
  for (const v of ['2d', '3d']) {
    const en = B.credits(v, 'en'), es = B.credits(v, 'es');
    assert.match(en, /© <a href="https:\/\/www\.openstreetmap\.org\/copyright">OpenStreetMap<\/a> contributors/);
    assert.match(es, /© colaboradores de <a href="https:\/\/www\.openstreetmap\.org\/copyright">OpenStreetMap<\/a>/);
    for (const s of [en, es]) { assert.match(s, /OpenMapTiles/); assert.match(s, /OpenFreeMap/); }
  }
});

test('the terrain credit includes the U.S. Geological Survey line the terrain tiles ask for', () => {
  assert.match(B.terrainCredit('en'), /3DEP, SRTM and GMTED2010 data courtesy of the U\.S\. Geological Survey/);
  assert.match(B.terrainCredit('es'), /3DEP, SRTM y GMTED2010 cortesía del Servicio Geológico de EE\. UU\./);
  assert.match(B.terrainCredit('en'), /Mapzen/);
  assert.strictEqual(B.TERRAIN.encoding, 'terrarium');
});

test('the 3D view keeps the OpenFreeMap Liberty style; the 2D maps use an OpenFreeMap style too; no key and no OSMF tile server', () => {
  assert.strictEqual(B.style('3d'), 'https://tiles.openfreemap.org/styles/liberty');
  assert.match(B.style('2d'), /^https:\/\/tiles\.openfreemap\.org\/styles\/\w+$/);
  for (const p of Object.values(B.PROVIDERS)) assert.strictEqual(p.key, null, 'no provider needs a key today');
  assert.doesNotMatch(fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8'), /tile\.openstreetmap\.org/);
  assert.ok(B.isProvider('https://tiles.openfreemap.org/planet/x/1/2/3.pbf', '2d'));
  assert.ok(!B.isProvider('https://coast.noaa.gov/arcgis/rest/services/dc_slr/slr_3ft/MapServer/tile/1/2/3', '2d'));
});

test('a provider key would come from the non-committed file, never from this one', () => {
  const g = fs.readFileSync(path.join(ROOT, '.gitignore'), 'utf8');
  assert.match(g, /^site\/js\/basemap\.local\.js$/m);
  assert.strictEqual(B.LIBS.local.src, 'js/basemap.local.js');
});

test('the 2D maps load the same MapLibre file and integrity as the 3D view, and the vendored bridge with its license', () => {
  const h3 = read('3d.html');
  assert.ok(h3.includes(`<script src="${B.LIBS.maplibre.src}" integrity="${B.LIBS.maplibre.integrity}"`));
  assert.ok(h3.includes(`href="${B.LIBS.css.href}" integrity="${B.LIBS.css.integrity}"`));
  const dir = path.dirname(path.join(SITE, B.LIBS.bridge.src));
  for (const f of ['leaflet-maplibre-gl.js', 'LICENSE', 'VERSION.md']) assert.ok(fs.existsSync(path.join(dir, f)), f);
  assert.match(fs.readFileSync(path.join(dir, 'LICENSE'), 'utf8'), /Permission to use, copy, modify, and\/or distribute/);   // ISC
});

test('the deferred lists of routes.json are what basemap.js loads, and no page lists them in its HTML', () => {
  const R = JSON.parse(fs.readFileSync(path.join(ROOT, 'dictionary_src', 'routes.json'), 'utf8'));
  const want = ['js/core/basemap.js', B.LIBS.bridge.src, B.LIBS.maplibre.src, B.LIBS.css.href].sort();
  for (const r of ['map', 'wcrp']) {
    assert.deepStrictEqual([...R.routes[r].deferred].sort(), [...want, ...(r === 'map' ? ['js/mapextras.js', 'i18n/es.map.mapextras.js'] : [])].sort(), r);   // the map also loads its extras after ready (town names: js/mapextras.js)
    const html = read(R.routes[r].page);
    for (const f of want) assert.ok(!html.includes(f), `${r}: ${f} is not in the HTML`);
  }
  assert.match(read('js/app.js'), /addJs\('js\/core\/basemap\.js\?v=\d+'\)/);
  assert.match(read('js/app.js'), /addJs\('js\/mapextras\.js\?v=\d+'\)/);
  assert.match(read('js/wcrp.js'), /script\('js\/core\/basemap\.js\?v=\d+'\)/);
});

test('every map that drew OpenStreetMap raster tiles now asks basemap.js', () => {
  assert.match(read('js/app.js'), /Core\.basemap\.leaflet\(map/);
  assert.match(read('js/wcrp_social.js'), /W\.basemap\(S\.map\)/);
  assert.match(read('js/wcrp_vuln.js'), /W\.basemap\(V\.map\)/);
  const t = read('js/twin3d.js');
  for (const s of ["Core.basemap.style('3d', BM.name)", "Core.basemap.credits('3d', null, BM.next || BM.name)", 'Core.basemap.terrainCredit()', 'Core.basemap.FALLBACK_STYLE']) assert.ok(t.includes(s), s);
});

test('nothing in site/ uses or names the OpenStreetMap Foundation tile server (tile.openstreetmap.org)', () => {
  const bad = [];
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (/\.(html|js|css|json|geojson|md|txt|svg|xml)$/i.test(e.name) && fs.readFileSync(p, 'utf8').includes('tile.openstreetmap.org')) bad.push(path.relative(SITE, p));
    }
  };
  walk(SITE);
  assert.deepStrictEqual(bad, []);
});

test('the notice texts exist in both languages', () => {
  for (const k of ['loading', 'off', 'webgl', 'provider']) { assert.ok(B.TEXT[k].en); assert.ok(B.TEXT[k].es); }
  assert.match(B.TEXT.off.es, /^Mapa base no disponible/);
  assert.match(B.TEXT.webgl.es, /^Mapa base no disponible/);
});

// ── The switcher (HANDOFF decision 62): Positron, Liberty or no base map, on the 2D map and the 3D view ──────────────────────────────────────────────
const esBundle = (page) => { const t = read(`i18n/es.${page}.js`); const m = /I18N\.add\((\{.*\})\)/s.exec(t); return JSON.parse(m[1]); };

test('the switcher offers five OpenStreetMap styles, three USGS maps and no base map, named and described in both languages; each view keeps its default', () => {
  assert.deepStrictEqual(B.NAMES, ['positron', 'liberty', 'bright', 'dark', 'fiord', 'imagery', 'topo', 'relief', 'none']);   // decision 102 added bright to relief
  assert.strictEqual(B.OPTIONS.positron.name.es, 'Claro (Positron)');
  assert.strictEqual(B.OPTIONS.liberty.name.es, 'Detallado (Liberty)');
  assert.strictEqual(B.OPTIONS.none.name.es, 'Sin mapa base');
  for (const [n, o] of Object.entries(B.OPTIONS)) for (const k of ['name', 'desc']) { assert.ok(o[k].en && o[k].es, `${n}.${k}`); }
  assert.match(B.OPTIONS.liberty.desc.en, /streets, places, buildings/);
  assert.strictEqual(B.defaultOf('2d'), 'positron');
  assert.strictEqual(B.defaultOf('3d'), 'liberty');
  // every style but "none" names its provider, whose sources, licenses and credits are kept (SOURCES); "none" has none and loads nothing
  for (const n of B.NAMES.filter(x => x !== 'none')) {
    const o = B.OPTIONS[n], p = B.PROVIDERS[o.provider]; assert.ok(p && p.styles[o.style], n);
    for (const id of o.credits || p.credits) assert.ok(B.SOURCES[id].licence && B.SOURCES[id].credit.en && B.SOURCES[id].credit.es, `${n}: ${id}`);
    assert.ok(B.GROUPS[o.group], `${n}: its heading in the select`);
  }
  assert.strictEqual(B.OPTIONS.none.provider, null); assert.strictEqual(B.OPTIONS.none.group, undefined, '"No base map" stands apart, last');
  for (const g of Object.values(B.GROUPS)) assert.ok(g.en && g.es);
});

test('each style has its URL and credits; "none" is the plain style with no source, and its credit line is empty', () => {
  assert.strictEqual(B.style('2d', 'liberty'), 'https://tiles.openfreemap.org/styles/liberty');
  assert.strictEqual(B.style('3d', 'positron'), 'https://tiles.openfreemap.org/styles/positron');
  assert.strictEqual(B.style('3d', 'nonsense'), B.style('3d'));
  for (const v of ['2d', '3d']) {
    const st = B.style(v, 'none');
    assert.strictEqual(typeof st, 'object'); assert.deepStrictEqual(st.sources, {}); assert.ok(!st.glyphs && !st.sprite);
    assert.notStrictEqual(st, B.FALLBACK_STYLE, 'a copy: MapLibre keeps the object it is given');
    assert.strictEqual(B.credits(v, 'en', 'none'), ''); assert.strictEqual(B.credits(v, 'es', 'none'), '');
    for (const n of ['positron', 'liberty', 'bright', 'dark', 'fiord']) assert.match(B.credits(v, 'es', n), /colaboradores de .*OpenStreetMap.*OpenMapTiles.*OpenFreeMap/);
    for (const n of ['imagery', 'topo', 'relief']) {
      assert.match(B.credits(v, 'en', n), /^Base map: <a href="https:\/\/apps\.nationalmap\.gov\/services\/">U\.S\. Geological Survey, National Geospatial Program<\/a>/, n);
      assert.match(B.credits(v, 'es', n), /Servicio Geológico de EE\. UU\. \(USGS\), Programa Geoespacial Nacional/, n);
      assert.doesNotMatch(B.credits(v, 'en', n), /OpenStreetMap|OpenMapTiles/, `${n}: no OpenStreetMap in the USGS pictures`);
    }
    assert.match(B.credits(v, 'en', 'imagery'), / · Orthoimagery: USDA, USGS$/); assert.match(B.credits(v, 'es', 'imagery'), / · Ortoimágenes: USDA, USGS$/);
  }
  for (const k of ['none', 'noneLong', 'failed']) { assert.ok(B.TEXT[k].en && B.TEXT[k].es, k); assert.strictEqual(B.text(k, 'es'), B.TEXT[k].es); }
});

test('bm= in the address: read, written and replaced; old links and unknown names keep the defaults', () => {
  assert.strictEqual(B.fromHash('#c=18.4,-66.1,12&bm=liberty'), 'liberty');
  assert.strictEqual(B.fromHash('#bm=none&c=1,2,3'), 'none');
  assert.strictEqual(B.fromHash('c=1,2,3&bm=positron'), 'positron');
  for (const h of ['', '#', '#c=18.4,-66.1,12&l=muni', '#bm=satellite', '#xbm=liberty', '#bm=libertyx', '#Ponce&bm=']) assert.strictEqual(B.fromHash(h), null, h);
  assert.strictEqual(B.withHash('#c=1,2,3&bm=none&r=abc', 'liberty'), '#c=1,2,3&r=abc&bm=liberty');
  assert.strictEqual(B.withHash('', 'none'), '#bm=none');
  assert.strictEqual(B.withHash('#bm=none', null), '');
  assert.strictEqual(B.withHash('#Ponce&c=1,2,3', 'positron'), '#Ponce&c=1,2,3&bm=positron');
});

test('the viewer default in localStorage: used when the address has no bm=, ignored when unknown, and storage that throws is no error', () => {
  const had = Object.prototype.hasOwnProperty.call(globalThis, 'localStorage'), saved = globalThis.localStorage;
  const put = (v) => Object.defineProperty(globalThis, 'localStorage', { value: v, configurable: true, writable: true });
  try {
    const box = {};
    put({ getItem: k => (k in box ? box[k] : null), setItem: (k, v) => { box[k] = String(v); } });
    assert.strictEqual(B.pick('2d', ''), 'positron'); assert.strictEqual(B.pick('3d', '#c=1,2,3'), 'liberty');   // nothing kept: each view's own
    B.store('none'); assert.strictEqual(box[B.STORE], 'none');
    assert.strictEqual(B.pick('2d', ''), 'none'); assert.strictEqual(B.pick('3d', ''), 'none');
    assert.strictEqual(B.pick('3d', '#bm=positron'), 'positron', 'the address wins over the kept default');
    B.store('bogus'); assert.strictEqual(box[B.STORE], 'none', 'only offered names are kept');
    box[B.STORE] = 'old-style'; assert.strictEqual(B.pick('2d', ''), 'positron');
    put({ getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    assert.strictEqual(B.stored(), null); assert.doesNotThrow(() => B.store('liberty')); assert.strictEqual(B.pick('3d', ''), 'liberty');
  } finally { if (had) put(saved); else delete globalThis.localStorage; }
});

test('both pages have the switcher: its options are OPTIONS, in order, named as there in English and Spanish, with the default described', () => {
  for (const [page, file, bundle] of [['2d', 'index.html', 'map'], ['3d', '3d.html', 'threed']]) {
    const html = read(file), es = esBundle(bundle);
    const sel = /<label for="basemap">Base map<\/label><select id="basemap" aria-describedby="basemapDesc" disabled>(.*?)<\/select><p class="note" id="basemapDesc">([^<]*)<\/p>/.exec(html);
    assert.ok(sel, `${file}: the switcher`);
    const opts = [...sel[1].matchAll(/<option value="(\w+)"( selected)?>([^<]*)<\/option>/g)];
    assert.deepStrictEqual(opts.map(m => m[1]), B.NAMES, file);
    assert.deepStrictEqual(opts.filter(m => m[2]).map(m => m[1]), [B.defaultOf(page)], `${file}: the default is selected`);
    for (const m of opts) { assert.strictEqual(m[3], B.OPTIONS[m[1]].name.en, m[1]); assert.strictEqual(es[m[3]], B.OPTIONS[m[1]].name.es, `${bundle}: ${m[1]}`); }
    assert.strictEqual(sel[2], B.OPTIONS[B.defaultOf(page)].desc.en);
    assert.strictEqual(es[sel[2]], B.OPTIONS[B.defaultOf(page)].desc.es);
    assert.strictEqual(es['Base map'], 'Mapa base');
  }
  // the 2D map's switcher is first in its Reference group, the 3D view's first in its 3D scene group
  assert.match(read('index.html').replace(/\r\n/g, '\n'), /Reference<\/h2>\n    <div class="ctrl"><label for="basemap">/);
  assert.match(read('3d.html').replace(/\r\n/g, '\n'), /3D scene<\/h2>\n    <div class="ctrl"><label for="basemap">/);
});

test('bm= is carried: the 2D map writes it in its address and its 3D link, the 3D view in its address and its 2D link; the WCRP maps keep Positron', () => {
  const app = read('js/app.js'), t = read('js/twin3d.js');
  // since the shared view state (core/viewstate.js, docs/view-state.md) each view writes bm= with the rest of its state, and its link carries the whole address
  assert.match(app, /bm: bmLink \|\| null,/);
  assert.match(app, /l3\.href = '3d\.html' \+ location\.search \+ hash;/);
  assert.match(app, /Core\.basemap\.leaflet\(map, \{ style: bmLink \|\| B\.stored\(\)/);
  assert.match(app, /B\.control\(\$\('#basemap'\)/);
  assert.match(t, /bm: BM\.chosen \? BM\.name : null/);
  assert.match(t, /l2d\.href = 'index\.html' \+ location\.search \+ Core\.viewstate\.write\('3d', location\.hash, \{\}\)/);
  const sw = /async function switchBasemap\([\s\S]*?\n\}/.exec(t)[0];
  assert.ok(sw.indexOf('writeState(true)') > sw.indexOf('await applyStyle(next)'), 'the 3D view writes bm= once the new style is in');
  assert.match(t, /transformStyle: carryStyle/);
  assert.match(read('js/wcrp.js'), /Core\.basemap\.leaflet\(map\)/);
});

// ── Follow-ups of the post-merge check (2026-10-26) ─────────────────────────────────────────────────────────────────────────────────────────────────
// A fake page for leaflet(): a document, a Leaflet map with its credits control, and MapLibre layers whose events a test fires.
function fakePage() {
  const el = (tag) => ({ tag, style: {}, dataset: {}, children: [], attrs: {}, appendChild(c) { this.children.push(c); return c; }, setAttribute(k, v) { this.attrs[k] = v; }, getContext: () => ({}), addEventListener() {}, querySelector: () => null, remove() {} });
  const doc = { createElement: el, head: el('head'), querySelector: () => null, getElementById: () => null };
  const layers = [];
  const emitter = () => { const on = {}; return { on: (k, f) => (on[k] = on[k] || []).push(f), once: (k, f) => (on[k] = on[k] || []).push(f), fire: (k, e) => (on[k] || []).forEach(f => f(e)), areTilesLoaded: () => true, getCanvas: () => el('canvas') }; };
  const L = { maplibreGL: (o) => { const gl = emitter(); const lay = { o, gl, _map: null, addTo(m) { this._map = m; m.added.push(this); const t = this.getAttribution(); m.attributionControl.addAttribution(t); gl.on('load', () => { m.attributionControl.removeAttribution(t); m.attributionControl.addAttribution(t); }); return this; }, getMaplibreMap: () => gl, getContainer: () => el('div'), getAttribution: () => o.attributionControl.customAttribution }; layers.push(lay); return lay; } };
  const prefix = { v: '' };
  const credits = {};   // Leaflet's attribution counts, as L.Control.Attribution keeps them
  const ac = { options: { prefix: 'Leaflet' }, setPrefix: (p) => { prefix.v = p; }, addAttribution(t) { credits[t] = (credits[t] || 0) + 1; }, removeAttribution(t) { if (credits[t]) credits[t]--; } };
  const map = { added: [], credits, getContainer: () => ({ dataset: {} }), attributionControl: ac, removeLayer(l) { l._map = null; ac.removeAttribution(l.getAttribution()); } };
  return { doc, L, map, layers, prefix };
}
async function withPage(fn) {
  const keep = { document: globalThis.document, L: globalThis.L, maplibregl: globalThis.maplibregl };
  const f = fakePage();
  Object.assign(globalThis, { document: f.doc, L: f.L, maplibregl: {} });
  try { await fn(f); } finally { for (const [k, v] of Object.entries(keep)) { if (v === undefined) delete globalThis[k]; else globalThis[k] = v; } }
}
const tick = () => new Promise(r => setTimeout(r, 0));

test('a small map goes off when every tile it asked for failed, though fewer than eight (the WCRP vulnerability map needs about 6)', async () => {
  await withPage(async (f) => {
    const states = [];
    const h = B.leaflet(f.map, { onState: (s) => states.push(s) });
    await tick();
    const gl = f.layers[0].gl;
    gl.fire('load', {});
    assert.strictEqual(h.state, 'on');
    for (let i = 0; i < 6; i++) gl.fire('error', { tile: {}, sourceId: 'openmaptiles', error: { message: 'Failed to fetch' } });
    assert.strictEqual(h.state, 'on', 'six errors are under the run of eight');
    gl.fire('idle', {});
    assert.strictEqual(h.state, 'off'); assert.strictEqual(h.reason, 'tiles');
    assert.match(f.prefix.v, /Base map unavailable|Mapa base no disponible/);
    assert.deepStrictEqual(states, ['loading', 'on', 'off']);
  });
});

test('one failed tile among tiles that arrived does not turn the base map off; nor does an idle map with nothing asked', async () => {
  await withPage(async (f) => {
    const h = B.leaflet(f.map, {});
    await tick();
    const gl = f.layers[0].gl;
    gl.fire('load', {});
    gl.fire('sourcedata', { tile: {} }); gl.fire('sourcedata', { tile: {} });
    gl.fire('error', { tile: {}, sourceId: 'openmaptiles', error: { message: 'Failed to fetch' } });
    gl.fire('idle', {});
    assert.strictEqual(h.state, 'on');
    gl.fire('idle', {});   // a pan over tiles already in memory: nothing asked, nothing failed
    assert.strictEqual(h.state, 'on');
    for (let i = 0; i < 8; i++) gl.fire('error', { tile: {}, sourceId: 'openmaptiles', error: { message: 'x' } });
    assert.strictEqual(h.state, 'off', 'a run of eight still counts without waiting for idle');
  });
});

test('a switch drops the old layer and its events no longer count; "none" loads nothing; a failed base map tries again on a new pick', async () => {
  await withPage(async (f) => {
    const h = B.leaflet(f.map, { style: 'liberty' });
    await tick();
    assert.strictEqual(f.layers[0].o.style, B.style('2d', 'liberty'));
    h.set('positron'); await tick();
    assert.strictEqual(f.layers.length, 2); assert.strictEqual(f.layers[0]._map, null);
    for (let i = 0; i < 9; i++) f.layers[0].gl.fire('error', { tile: {}, sourceId: 'openmaptiles' });   // the old layer's tiles
    f.layers[1].gl.fire('load', {});
    assert.strictEqual(h.state, 'on');
    h.set('none'); await tick();
    assert.strictEqual(h.state, 'none'); assert.strictEqual(f.layers.length, 2, 'nothing loaded');
    assert.match(f.prefix.v, /Base map off|Mapa base desactivado/);
    h.set('liberty'); await tick();
    f.layers[2].gl.fire('error', { error: { message: 'style' } });   // the style fails before its first draw
    assert.strictEqual(h.state, 'off');
    h.set('positron'); await tick();
    assert.strictEqual(h.state, 'loading'); f.layers[3].gl.fire('load', {}); assert.strictEqual(h.state, 'on');
  });
});

test('a base-map failure has its own notice: never the message bar, which may hold an Undo', () => {
  assert.strictEqual(typeof B.notice, 'function');
  const bm = fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8');
  assert.doesNotMatch(bm, /activelayers|toast/);
  const app = read('js/app.js');
  assert.match(app, /onState: \(st, msg\) => \{ osmiSync\(st\); if \(st === 'off'\) Core\.basemap\.notice\(map\.getContainer\(\), msg\); \}/);   // osmiSync: the OSM inspector's toggle follows the base map (docs/basemap.md, section 8)
  const t = read('js/twin3d.js');
  assert.match(t, /const baseNotice = \(\) => Core\.basemap\.notice\(map\.getContainer\(\), /);
  for (const f of ['plainStyle', 'hideBase']) {
    const fn = new RegExp(`function ${f}\\(why[^)]*\\) \\{[\\s\\S]*?\\n\\}`).exec(t)[0];
    assert.match(fn, /baseNotice\(\)/, f); assert.doesNotMatch(fn, /toast\(/, f); assert.match(fn, /BM\.off = true; BM\.why = why;/, f); assert.match(fn, /setAttribution\(\)/, f);
  }
  const sw = /async function switchBasemap\([\s\S]*?\n\}/.exec(t)[0];
  assert.match(sw, /Core\.basemap\.notice\(/); assert.doesNotMatch(sw, /toast\(/);
});



test('the stop counts added again after a switch of base map are shown as their clusters are (review of PR #92)', () => {
  const t = read('js/twin3d.js'), add = /function addStopsCount\(before\) \{[\s\S]*?\n\}/.exec(t)[0];
  assert.match(add, /visibility: map\.getLayer\('stops-cluster'\) \? map\.getLayoutProperty\('stops-cluster', 'visibility'\) \|\| 'visible' : 'visible'/);
  assert.ok(fs.existsSync(path.join(ROOT, 'tests', 'browser', 'basemap_switch.js')), 'the browser check of the case');
});

test('a base map that goes off takes its credits with it, even when its map loads afterward (the bridge adds them again on load)', async () => {
  await withPage(async (f) => {
    const h = B.leaflet(f.map, {});
    await tick();
    const gl = f.layers[0].gl, text = f.layers[0].getAttribution();
    assert.strictEqual(f.map.credits[text], 1);
    for (let i = 0; i < 8; i++) gl.fire('error', { tile: {}, sourceId: 'openmaptiles', error: { message: 'Failed to fetch' } });   // fonts blocked: failed tiles
    assert.strictEqual(h.state, 'off'); assert.strictEqual(f.map.credits[text], 0);
    gl.fire('load', {});   // the layer is not removed yet (it waits for idle): the bridge's load handler puts the credits back
    assert.strictEqual(f.map.credits[text], 0, 'the base map is off: its credits stay off');
  });
});


test('a refused pick is not kept as the viewer default: the switcher does not store, each page stores once it has taken the pick', () => {
  const ctl = /function control\(sel, o\) \{[\s\S]*?\n  \}/.exec(fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8'))[0];
  assert.doesNotMatch(ctl, /store\(/);
  assert.match(read('js/app.js'), /onPick: n => \{ bmLink = n; bmH\.set\(n, \{ keep: true \}\); writeHash\(\); \}/, '2D keeps the pick once its style has loaded (leaflet keep)');
  assert.doesNotMatch(read('js/app.js'), /B\.store\(/, 'the 2D map never stores a pick before it loads');
  const sw = /async function switchBasemap\([\s\S]*?\n\}/.exec(read('js/twin3d.js'))[0];
  assert.ok(sw.indexOf('Core.basemap.store(name)') > sw.indexOf('await applyStyle(next)'), '3D stores only after the new style is in');
  assert.doesNotMatch(sw.slice(0, sw.indexOf('try {')), /store\(/);
});

test('3D failure rules (PR #94, kept): the style, its sprite or fonts before start → the plain style; 30 s with no style; a base-map source that does not load or eight tile errors in a row → the base map hidden', () => {
  const t = read('js/twin3d.js');
  assert.match(t, /if \(!started\) plainStyle\(/);
  assert.match(t, /const styleTimer = setTimeout\(\(\) => \{ if \(!started\) \{ if \(styleIn\) start\(\); else plainStyle\(/);
  assert.match(t, /if \(!e\.tile\) \{ hideBase\(\['source', e\.sourceId\]\); return; \}/);
  assert.match(t, />= MAX_TILE_ERRORS\) hideBase\(/);
  assert.match(t, /setupScene\(\); if \(BM\.off\) hideBaseLayers\(\);/);
});

test('3D, every base-map tile failing at the default view (review of PR #92): the clock rule (tileWatch) hides the base map, before or after start, and watches the sources', () => {
  const t = read('js/twin3d.js');
  assert.match(t, /const baseClock = Core\.basemap\.tileWatch\(\{/);
  assert.match(t, /loading: id => !!map\.getSource\(id\) && !map\.isSourceLoaded\(id\)/, 'tiles in flight are not failures');
  assert.match(t, /down: ids => \{ if \(!BM\.busy\) hideBase\(\['tiles', 'none arrived in 6 s', ids\.join\(\)\], ids\); \}/, 'the sources found down are watched');
  assert.match(t, /baseClock\.failed\(e\.sourceId\);/);
  assert.match(t, /tileErrors\[e\.sourceId\] = 0; baseClock\.arrived\(e\.sourceId\);/);
  assert.match(t, /if \(BM\.off && BM\.watching && BM\.watching\.includes\(e\.sourceId\)\) showBase\(\);/, 'tiles arriving after the clock rule bring the base map back');
  assert.doesNotMatch(t, /baseBad|baseGood|baseCheck/);
  const sw = /async function switchBasemap\([\s\S]*?\n\}/.exec(t)[0];
  assert.match(sw, /baseSources = \[\.\.\.BM\.base\.sources\]/, 'after a switch the rules watch the new style');
  assert.match(sw, /showBuildings\(\$\('#lyBuildings'\)\.checked\)/, 'buildings hidden with a failed base map come back');
});


test('3D credits: the base map once (our line on the provider\'s source, PR #94), the box always open, and never in the way of a map click', () => {
  const t = read('js/twin3d.js');
  assert.match(t, /src\.attribution = creditOn === e\.sourceId \? bmCredits\(\) : '';/);
  assert.match(t, /const bmCredits = \(\) => Core\.basemap\.credits\('3d', null, BM\.next \|\| BM\.name\);/, 'the credits of the style drawn, or going in');
  assert.match(t, /new maplibregl\.AttributionControl\(\{ compact: false, customAttribution: line \}\)/);
  assert.doesNotMatch(t, /compact: true/);
  assert.doesNotMatch(t, /removeAttribute\('open'\)/, 'nothing closes the credits');
  const css = read('css/twin3d.css');
  assert.match(css, /\.maplibregl-ctrl-bottom-left \.maplibregl-ctrl-attrib \{ pointer-events: none; \}/);
  assert.match(css, /\.maplibregl-ctrl-bottom-left \.maplibregl-ctrl-attrib a \{ pointer-events: auto; \}/);
});

// ── Follow-ups of the review of PR #92 (2026-10-26, branch basemap-followups) ────────────────────────────────────────────────────────────────────────
// A fake clock for tileWatch: the clock moves only when a test says so.
function fakeClock() {
  let now = 0, id = 0; const q = new Map();
  return {
    setTimeout: (f, ms) => { q.set(++id, { f, at: now + ms }); return id; },
    clearTimeout: (i) => q.delete(i),
    advance(ms) { const end = now + ms; for (;;) { const next = [...q.entries()].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0]; if (!next) break; q.delete(next[0]); now = next[1].at; next[1].f(); } now = end; },
    pending: () => q.size,
  };
}
function watch(loading = {}) {
  const c = fakeClock(), downs = [];
  const w = B.tileWatch({ clock: c, loading: id => !!loading[id], down: ids => downs.push([...ids]) });
  return { c, w, downs, loading };
}

test('the 3D clock rule: one failed tile while the others are held 7 s is no outage (review of PR #92: the base map hid at 6 s and stayed off)', () => {
  const { c, w, downs, loading } = watch({ openmaptiles: true });
  w.failed('openmaptiles');   // one tile fails, the others are held
  c.advance(6000); assert.deepStrictEqual(downs, [], 'one failure is under MIN_FAILED');
  loading.openmaptiles = false; w.arrived('openmaptiles'); c.advance(5000);
  assert.deepStrictEqual(downs, []); assert.strictEqual(B.MIN_FAILED, 2);
});

test('the 3D clock rule: failed tiles while others are still loading keep the window open; a tile that arrives clears the source', () => {
  const { c, w, downs, loading } = watch({ openmaptiles: true });
  w.failed('openmaptiles'); w.failed('openmaptiles'); w.failed('openmaptiles');
  c.advance(6000); assert.deepStrictEqual(downs, [], 'tiles in flight: not judged yet'); assert.ok(w.open(), 'the window stays open');
  c.advance(1000); w.arrived('openmaptiles'); loading.openmaptiles = false;   // the held tiles arrive at 7 s
  c.advance(5000); assert.deepStrictEqual(downs, []); assert.ok(!w.open());
});

test('the 3D clock rule: failed tiles with nothing in flight and none arrived → down at 6 s, per source; a slow source is judged once it settles', () => {
  const { c, w, downs, loading } = watch({ ne2_shaded: true });
  w.failed('openmaptiles'); w.failed('openmaptiles'); w.failed('ne2_shaded'); w.failed('ne2_shaded');
  c.advance(5999); assert.deepStrictEqual(downs, []);
  c.advance(1); assert.deepStrictEqual(downs, [['openmaptiles']], 'the settled source counts at once');
  const two = watch({ openmaptiles: true });
  two.w.failed('openmaptiles'); two.w.failed('openmaptiles'); two.c.advance(6000); assert.deepStrictEqual(two.downs, []);
  two.loading.openmaptiles = false; two.c.advance(1000); assert.deepStrictEqual(two.downs, [['openmaptiles']], 'settled at 7 s with none arrived: down');
  const ok = watch(); ok.w.failed('openmaptiles'); ok.w.failed('openmaptiles'); ok.w.arrived('openmaptiles'); ok.c.advance(6000);
  assert.deepStrictEqual(ok.downs, [], 'a tile arrived in the window: the provider answers');
});

test('the 3D clock rule: reset() clears a pending check (a switch of base map), and a later failure opens a new window', () => {
  const { c, w, downs } = watch();
  w.failed('openmaptiles'); w.failed('openmaptiles'); assert.strictEqual(c.pending(), 1);
  w.reset(); assert.strictEqual(c.pending(), 0); assert.ok(!w.open());
  c.advance(10000); assert.deepStrictEqual(downs, []);
  w.failed('openmaptiles'); w.failed('openmaptiles'); c.advance(6000); assert.deepStrictEqual(downs, [['openmaptiles']]);
  w.arrived('openmaptiles'); assert.ok(!w.open(), 'an arrival with no window open counts for nothing');
});

test('3D switch (review of PR #92): a pending clock check is cleared, a pending notice goes, BM.why is reset; recovery does the same', () => {
  const t = read('js/twin3d.js'), sw = /async function switchBasemap\([\s\S]*?\n\}/.exec(t)[0];
  const ok = sw.slice(sw.indexOf('await applyStyle(next)'), sw.indexOf('} catch'));
  assert.match(ok, /baseClock\.reset\(\)/, 'the old style\'s clock stops');
  assert.match(ok, /Core\.basemap\.clearNotice\(map\.getContainer\(\)\)/, 'a "could not be loaded" still shown goes');
  assert.match(ok, /Object\.assign\(BM, \{ name, chosen: true, off: false, why: null, hid: \{\}, watching: null, recovered: false \}\)/);
  const show = /function showBase\(\) \{[\s\S]*?\n\}/.exec(t)[0];
  assert.match(show, /Object\.assign\(BM, \{ off: false, why: null, hid: \{\}, watching: null, recovered: true \}\)/);
  assert.match(t, /if \(watch && !BM\.recovered\) watchBase\(watch\);/, 'watched once per style: no back and forth when only the fonts fail');
  assert.match(t, /hideBase\(\['tiles', 'a run of 8'\], \[e\.sourceId\]\)/, 'a run of eight is watched too');
  assert.match(show, /baseClock\.reset\(\)/); assert.match(show, /Core\.basemap\.clearNotice\(map\.getContainer\(\)\)/); assert.match(show, /baseCredit\(true\)/); assert.match(show, /setAttribution\(\)/);
  assert.match(show, /map\.removeLayer\(WATCH \+ id\)/, 'the watch layers go');
  assert.match(t, /ours = prev\.layers\.filter\(l => !base\.layers\.has\(l\.id\) && !l\.id\.startsWith\(WATCH\)\)/, 'a switch does not carry a watch layer');
  assert.match(t, /baseSources\.includes\(l\.source\) && !l\.id\.startsWith\(WATCH\)/, 'hiding the base map leaves its watch layer');
});

test('clearNotice takes away a pending notice and its timer; with none shown it does nothing', () => {
  const removed = [], n = { _t: 7, remove() { removed.push(1); } };
  const el = { querySelector: (q) => (q === ':scope > .bm-notice' ? n : null) };
  B.clearNotice(el); assert.deepStrictEqual(removed, [1]);
  assert.doesNotThrow(() => B.clearNotice({ querySelector: () => null })); assert.doesNotThrow(() => B.clearNotice(null)); assert.doesNotThrow(() => B.clearNotice({}));
});

test('2D: a pick is kept only once its style has loaded; a failed or overtaken pick is not; a style that loads takes away a pending failure notice', async () => {
  const had = Object.prototype.hasOwnProperty.call(globalThis, 'localStorage'), saved = globalThis.localStorage;
  const put = (v) => Object.defineProperty(globalThis, 'localStorage', { value: v, configurable: true, writable: true });
  const box = {}; put({ getItem: k => (k in box ? box[k] : null), setItem: (k, v) => { box[k] = String(v); } });
  try {
    await withPage(async (f) => {
      let note = null; const removed = [];
      const container = { dataset: {}, querySelector: () => note };
      f.map.getContainer = () => container;
      const h = B.leaflet(f.map, {}); await tick();
      f.layers[0].gl.fire('load', {});
      assert.strictEqual(box[B.STORE], undefined, 'the opening style is not a pick');
      h.set('liberty', { keep: true }); await tick();
      assert.strictEqual(box[B.STORE], undefined, 'not kept before its style loads');
      f.layers[1].gl.fire('error', { error: { message: 'style' } });   // the pick fails
      assert.strictEqual(h.state, 'off'); assert.strictEqual(box[B.STORE], undefined, 'a failed pick is not kept');
      note = { _t: 1, remove() { removed.push('notice'); note = null; } };   // the page shows the failure notice (app.js onState)
      h.set('positron', { keep: true }); await tick();
      h.set('liberty', { keep: true }); await tick();   // overtaken before it loaded
      f.layers[2].gl.fire('load', {}); assert.strictEqual(box[B.STORE], undefined, 'an overtaken pick is not kept');
      f.layers[3].gl.fire('load', {});
      assert.strictEqual(box[B.STORE], 'liberty'); assert.deepStrictEqual(removed, ['notice'], 'the style loaded: the pending notice goes');
      h.set('none', { keep: true }); assert.strictEqual(box[B.STORE], 'none', '"none" loads nothing: kept at once');
      h.set('positron'); await tick(); f.layers[4].gl.fire('load', {}); assert.strictEqual(box[B.STORE], 'none', 'a set() that is not a pick (an address) is not kept');
    });
  } finally { if (had) put(saved); else delete globalThis.localStorage; }
});

test('2D idle rule: one failed tile alone, then idle, is no outage; two or more with none arrived is', async () => {
  await withPage(async (f) => {
    const h = B.leaflet(f.map, {}); await tick();
    const gl = f.layers[0].gl; gl.fire('load', {});
    gl.fire('error', { tile: {}, sourceId: 'openmaptiles', error: { message: 'Failed to fetch' } }); gl.fire('idle', {});
    assert.strictEqual(h.state, 'on');
    gl.fire('error', { tile: {}, sourceId: 'openmaptiles' }); gl.fire('error', { tile: {}, sourceId: 'openmaptiles' }); gl.fire('idle', {});
    assert.strictEqual(h.state, 'off'); assert.strictEqual(h.reason, 'tiles');
  });
});

test('credits fold on a phone, the same way on every map (HANDOFF decision 65; docs/basemap.md, "Credits on a phone")', () => {
  assert.deepStrictEqual(B.TEXT.credits, { en: 'Map credits', es: 'Créditos del mapa' });
  assert.strictEqual(typeof B.fold, 'function');
  assert.strictEqual(B.fold(null), null, 'no box, no button');
  const src = fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8');
  assert.match(src, /PHONE = '\(max-width: 699px\)', FOLD_MS = 5000/, 'under 700 px, folded 5 s after the credit shows (the OSMF guidelines\' five seconds)');
  assert.match(src, /\['pointerdown', 'wheel'\]/, 'or at the first touch, click or wheel on the map');
  assert.match(src, /if \(ac && ac\.getContainer\) fold\(ac\.getContainer\(\), \{ map: el \}\);/, 'every Leaflet map with a base map (the 2D map, both WCRP maps)');
  assert.match(fs.readFileSync(path.join(SITE, 'js', 'twin3d.js'), 'utf8'), /Core\.basemap\.fold\(map\.getContainer\(\)\.querySelector\('\.maplibregl-ctrl-bottom-left > \.maplibregl-ctrl-attrib'\)/, 'the 3D view, each time its box is built');
  assert.match(src, /@media print\{\.cr-shut\{display:block!important\}/, 'printing shows the credits');
});

// ── More base maps (2026-11-13, HANDOFF decision 102): three more OpenFreeMap styles and three USGS National Map picture maps ────────────────────────────
test('the OpenFreeMap styles share one provider; the USGS maps are its public base map services, never the retiring Imagery Topo', () => {
  for (const n of ['bright', 'dark', 'fiord']) assert.strictEqual(B.style('2d', n), `https://tiles.openfreemap.org/styles/${n}`);
  const src = fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8');
  assert.doesNotMatch(src, /USGSImageryTopo\/MapServer/, 'USGSImageryTopo retires on 2026-11-16');
  const svc = { imagery: 'USGSImageryOnly', topo: 'USGSTopo', relief: 'USGSShadedReliefOnly' };
  for (const [n, s] of Object.entries(svc)) assert.strictEqual(B.PROVIDERS.usgs.styles[n].tiles, `https://basemap.nationalmap.gov/arcgis/rest/services/${s}/MapServer/tile/{z}/{y}/{x}`, n);
  assert.strictEqual(B.PROVIDERS.usgs.key, null);
  assert.ok(B.isProvider('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/12/1834/1296'));
  assert.ok(B.isProvider(B.credits('3d', 'es', 'topo')), 'the 3D view finds the USGS source by its credit');
  assert.ok(!B.isProvider('https://api.waterdata.usgs.gov/ogcapi/v1/collections'), 'the observatory\'s own USGS layers are not the base map');
  assert.ok(!B.isProvider(B.terrainCredit('es')), 'nor the terrain, whose credit names the USGS');
});

test('a USGS style is built here: a background, its picture tiles to zoom 16 with the credits on the source, and OpenFreeMap fonts for the 3D labels', () => {
  for (const n of ['topo', 'relief']) {
    const st = B.style('3d', n);
    assert.strictEqual(typeof st, 'object'); assert.strictEqual(st.version, 8); assert.strictEqual(st.glyphs, B.GLYPHS);
    assert.deepStrictEqual(Object.keys(st.sources), ['usgs']);
    assert.deepStrictEqual(st.layers.map(l => [l.id, l.type, l.source]), [['bm-bg', 'background', undefined], ['usgs', 'raster', 'usgs']]);
    const s = st.sources.usgs;
    assert.deepStrictEqual([s.type, s.tileSize, s.maxzoom, s.minzoom], ['raster', 256, 16, undefined]);
    assert.strictEqual(s.attribution, B.credits('3d', null, n));
    assert.notStrictEqual(B.style('3d', n), st, 'a new object each time: MapLibre keeps the one it is given');
  }
  // USGSImageryOnly answers 404 at zooms 9 and 10 over Puerto Rico: those are drawn from its zoom 8 tiles, enlarged, under the main source, which starts at 11
  const im = B.style('2d', 'imagery');
  assert.deepStrictEqual(im.layers.map(l => l.id), ['bm-bg', 'usgs-low', 'usgs']);
  assert.strictEqual(im.sources['usgs-low'].maxzoom, 8); assert.strictEqual(im.sources['usgs-low'].minzoom, undefined);
  assert.strictEqual(im.sources.usgs.minzoom, 11); assert.strictEqual(im.sources.usgs.maxzoom, 16);
  assert.strictEqual(im.sources['usgs-low'].tiles[0], im.sources.usgs.tiles[0]);
  assert.strictEqual(B.style('2d', 'relief').layers[0].paint['background-color'], '#fdfdfd', 'the relief sea: white in some tiles, see-through in others, so the background is that white');
});

test('bm= and the kept default take the new names; an old link keeps its default', () => {
  for (const n of ['bright', 'dark', 'fiord', 'imagery', 'topo', 'relief']) { assert.strictEqual(B.fromHash(`#c=18.4,-66.1,12&bm=${n}`), n); assert.ok(B.valid(n)); }
  assert.strictEqual(B.fromHash('#bm=hybrid'), null, 'no imagery-with-labels style (USGS retires it)');
  assert.strictEqual(B.withHash('#c=1,2,3', 'imagery'), '#c=1,2,3&bm=imagery');
  // the 2D map reads bm= before basemap.js has loaded, from its own list: the same names (an address with bm=topo opened on the kept default before)
  assert.strictEqual(/const BM_NAMES = \/\^\((.*)\)\$\/;/.exec(read('js/app.js'))[1], B.NAMES.join('|'));
  assert.doesNotMatch(read('js/app.js'), /positron\|liberty\|none/, 'no older list left');
});

test('the map inspector reads only the OpenStreetMap styles: both pages disable its toggle on a USGS map and say why, in both languages', () => {
  for (const n of ['positron', 'liberty', 'bright', 'dark', 'fiord']) assert.ok(B.inspectable(n), n);
  for (const n of ['imagery', 'topo', 'relief', 'none', 'bogus']) assert.ok(!B.inspectable(n), n);
  const msg = 'The inspector reads only the OpenStreetMap base maps: choose one of them to use it.';
  const app = read('js/app.js'), t = read('js/twin3d.js');
  assert.match(app, /const pics = st === 'on' && bmH && !Core\.basemap\.inspectable\(bmH\.name\);/);
  assert.match(t, /const pics = st === 'on' && !Core\.basemap\.inspectable\(BM\.name\);/);
  for (const s of [app, t]) { assert.ok(s.includes(`T('${msg}')`)); assert.match(s, /\.disabled = st !== 'on' \|\| pics;/); }
  assert.match(t, /started && !BM\.off && Core\.basemap\.inspectable\(BM\.name\)/, 'the 3D inspector\'s own check');
  for (const page of ['map', 'threed']) assert.ok(esBundle(page)[msg], page);
});

test('the select groups the styles by source under headings named in both languages; the 3D switch fetches a style URL only', () => {
  for (const file of ['index.html', '3d.html']) {
    const sel = /<select id="basemap"[^>]*>(.*?)<\/select>/.exec(read(file))[1];
    const groups = [...sel.matchAll(/<optgroup label="([^"]+)" data-group="(\w+)">(.*?)<\/optgroup>/g)];
    assert.deepStrictEqual(groups.map(g => g[2]), ['osm', 'usgs'], file);
    for (const g of groups) {
      assert.strictEqual(g[1], B.GROUPS[g[2]].en, file);
      assert.deepStrictEqual([...g[3].matchAll(/value="(\w+)"/g)].map(m => m[1]), B.NAMES.filter(n => B.OPTIONS[n].group === g[2]), `${file}: ${g[2]}`);
    }
    assert.match(sel, /<\/optgroup><option value="none">No base map<\/option>$/, `${file}: "No base map" last, on its own`);
  }
  for (const page of ['map', 'threed']) { const es = esBundle(page); for (const g of Object.values(B.GROUPS)) assert.strictEqual(es[g.en], g.es, page); }
  const ctl = /function control\(sel, o\) \{[\s\S]*?\n  \}/.exec(fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8'))[0];
  assert.match(ctl, /g\.label = GROUPS\[g\.dataset\.group\]\[l\]/, 'the headings are written in the page language');
  const sw = /async function switchBasemap\([\s\S]*?\n\}/.exec(read('js/twin3d.js'))[0];
  assert.match(sw, /next = typeof st === 'string' \? await fetchRetry\(st, r => r\.json\(\), \[1000\]\) : st;/);
  assert.match(sw, /BM\.next = name; creditOn = null;/, 'the new style\'s source takes the credits, whatever its id');
  assert.match(sw, /finally \{ BM\.busy = false; BM\.next = null;/);
});

test('the credits on a phone fold once a base map\'s credit is in the box: OpenStreetMap\'s or the USGS\'s', () => {
  const src = fs.readFileSync(path.join(SITE, 'js', 'core', 'basemap.js'), 'utf8');
  const re = new RegExp(/const CREDITED = \/(.*)\/;/.exec(src)[1]);
  for (const n of ['positron', 'imagery', 'topo']) for (const l of ['en', 'es']) assert.match(B.credits('2d', l, n).replace(/<[^>]+>/g, ''), re, `${n} ${l}`);
  assert.doesNotMatch(B.terrainCredit('es'), re, 'the terrain line alone does not start the fold');
});

test('3D buildings only over OpenStreetMap tiles: the base map\'s vector source is the provider\'s, and the buildings OpenStreetMap lacks go with no base buildings', () => {
  const t = read('js/twin3d.js');
  assert.match(t, /function vectorSourceId\(\) \{ const src = map\.getStyle\(\)\.sources; return Object\.keys\(src\)\.find\(k => src\[k\]\.type === 'vector' && Core\.basemap\.isProvider\(src\[k\]\.url \|\| \(src\[k\]\.tiles \|\| \[\]\)\[0\]\)\); \}/,
    'not the PMTiles of the buildings OpenStreetMap lacks, which a switch carries into a style with no vector source (a USGS map, "No base map")');
  const ex = /function baseExtras\(\) \{[\s\S]*?\n\}/.exec(t)[0];
  assert.match(ex, /if \(vs\) addGapBuildings\(\);\s*else if \(map\.getLayer\('buildings-3d-gap'\)\) map\.removeLayer\('buildings-3d-gap'\);/);
  assert.ok(!B.isProvider('pmtiles://http://127.0.0.1:8041/data/buildings_gap.pmtiles'));
  assert.ok(B.isProvider('https://tiles.openfreemap.org/planet'));
  assert.ok(fs.existsSync(path.join(ROOT, 'tests', 'browser', 'basemap_more.js')), 'the browser check of the new maps');
});
