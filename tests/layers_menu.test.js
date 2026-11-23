// The layer menus of the 2D map (site/index.html) and the 3D view (site/3d.html) against their one list, site/js/core/layers.js (docs/layers.md).
//  - each page has the registry's groups, in its order, with its titles and icons; every data group is in both views, so the two menus cannot drift apart;
//  - in each group, the rows and subheadings of that view, in order; every switch of the Layers tab (any checkbox, in a row, in a label.toggle or before its label, and any
//    select[data-layer-select]) is a registry row or a control of one (NOT_LAYERS); a group with no row in a view says where its layers are;
//  - each row's name and source as the registry has them, the source a name (translate="no") or translated; rows that are not counted carry class "nocount";
//  - the Spanish of every title, subheading, name and translated source, in each page's bundle, is the registry's;
//  - the l= keys of the 2D map (app.js LAYER_KEYS) are the published ones, and the registry's keys match them;
//  - tourism last: the visitor economy is the last group, the last Economy preset, the last "Also show on the map" switch and the last dataset group; the 3D columns open on population;
//  - "Also show on the map" holds its whole list, with the menu's names; sortGroups lists each group once;
//  - one view only (Core.layers.oneView()): the 3D scene, the 3D columns and the vehicle replay, and the 2D shading, each with its reason (why);
//  - the chat's context words (chat.js CH_CONTEXT) name layers that both views have, and the 3D view (ask3d.js CTX) and the 2D map (economy.js ecSetContext) switch them on.
// Run: node --test tests/layers_menu.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8').replace(/\r\n/g, '\n');
const LY = require(path.join(ROOT, 'site', 'js', 'core', 'layers.js'));
const PAGES = { '2d': { file: 'site/index.html', i18n: 'map' }, '3d': { file: 'site/3d.html', i18n: 'threed' } };
const decode = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
const allIds = new Set(LY.rows().map(r => r.id));
// the controls of the Layers tab that change a layer but are not one: each is listed with the row it belongs to (land-use classes carry data-lu and no id)
const NOT_LAYERS = { '2d': { worship: 'lyPlaces' }, '3d': {} };
const attr = (tag, a) => { const m = new RegExp(`\\s${a}="([^"]*)"`).exec(tag); return m ? m[1] : null; };   // an attribute of a tag, in any order

// a page's menu as written: [{ title, icon, tokens: ['h:<subheading>' | row id], chunk }]
function parse(view) {
  const html = read(PAGES[view].file), a = html.indexOf('id="tab-layers"'), b = html.indexOf('</section>', a);
  assert.ok(a > 0 && b > a, `${view}: the Layers tab`);
  const sec = html.slice(a, b), parts = sec.split('<h2 class="sec">').slice(1);
  return parts.map(chunk => {
    const h = /^<span class="ms-icon" aria-hidden="true" style="font-size:14px">(\w+)<\/span>([^<]+)<\/h2>/.exec(chunk);
    assert.ok(h, `${view}: a group heading is an icon and a title: ${chunk.slice(0, 80)}`);
    // every checkbox, wherever it stands (a row, a label.toggle, before its label), and every select that is a layer: by id, or [no id, its data-lu]
    const boxes = [...chunk.matchAll(/<input\s[^>]*>/g)].map(m => m[0]).filter(t => attr(t, 'type') === 'checkbox');
    const switches = new Set([...boxes.filter(t => attr(t, 'id')).map(t => attr(t, 'id')), ...[...chunk.matchAll(/<select\s[^>]*>/g)].map(m => m[0]).filter(t => /\sdata-layer-select[\s>=]/.test(t)).map(t => attr(t, 'id'))]);
    const filters = boxes.filter(t => !attr(t, 'id')).map(t => attr(t, 'data-lu'));
    const tokens = [...chunk.matchAll(/<h3 class="sec lsub">([^<]+)<\/h3>|\sid="(\w+)"/g)].map(m => m[1] ? 'h:' + decode(m[1]) : m[2]).filter(t => t.startsWith('h:') || allIds.has(t));
    return { icon: h[1], title: decode(h[2].trim()), tokens, chunk, switches, filters };
  });
}
const expected = (view) => LY.menu(view).map(g => ({ id: g.id, title: g.en, icon: g.icon, setting: !!g.setting, tokens: g.rows.map(r => r.head ? 'h:' + r.head.en : r.id), rows: g.rows }));

// a row as written: its name, its source (and whether it is marked translate="no"), whether it is counted
function rowOf(chunk, id) {
  const sel = new RegExp(`<label for="${id}">([^<]*)</label>`).exec(chunk);
  if (sel) return { name: decode(sel[1].trim()), src: null, counted: true };
  const i = chunk.indexOf(`id="${id}"`); assert.ok(i > 0, id);
  const div = chunk.lastIndexOf('<div class="layer', i), lab = chunk.lastIndexOf('<label', i);
  const counted = !(div >= 0 && div > chunk.lastIndexOf('</div>', i) && /^<div class="layer nocount"/.test(chunk.slice(div)));
  const rest = chunk.slice(chunk.indexOf('>', i) + 1), end = rest.search(/<\/label>|<button/);
  let body = rest.slice(0, end);
  const s = /<small class="src"( translate="no")?>([^<]*)<\/small>/.exec(body);
  body = body.replace(/<span class="sw[^"]*"[^>]*><\/span>/g, '').replace(/<span class="ms-icon"[^>]*>\w+<\/span>/g, '').replace(/<small[^>]*>[^<]*<\/small>/g, '').replace(/<\/?span[^>]*>/g, '');
  assert.ok(lab >= 0, `${id}: a label`);
  return { name: decode(body.replace(/\s+/g, ' ').trim()), src: s ? { text: decode(s[2]), name: !!s[1] } : null, counted };
}

// the Spanish a page's bundle has: the merge of its scopes (i18n_src/pages.json)
function spanish(page) {
  const pages = JSON.parse(read('i18n_src/pages.json')).pages, d = {};
  pages[page].scopes.forEach(s => Object.assign(d, JSON.parse(read(`i18n_src/es/${s}.json`))));
  return d;
}

for (const view of ['2d', '3d']) {
  test(`${view}: the groups, their order, titles and icons are the registry's`, () => {
    const got = parse(view), want = expected(view);
    assert.deepStrictEqual(got.map(g => g.title), want.map(g => g.title), 'group titles in order');
    assert.deepStrictEqual(got.map(g => g.icon), want.map(g => g.icon), 'group icons');
    const font = read(PAGES[view].file).match(/icon_names=([a-z0-9_,]+)/g).map(m => m.slice(11).split(','));
    font.forEach(names => want.forEach(g => assert.ok(names.includes(g.icon), `${g.icon} is in the page's icon font`)));
  });

  test(`${view}: every group holds the registry's rows and subheadings for this view, in order`, () => {
    const got = parse(view), want = expected(view);
    want.forEach((g, k) => {
      assert.deepStrictEqual(got[k].tokens, g.tokens, `${g.id}: rows`);
      got[k].switches.forEach(id => assert.ok(id && (allIds.has(id) || NOT_LAYERS[view][id]), `${g.id}: the switch ${id} is in js/core/layers.js (or a control of a row, NOT_LAYERS)`));
      Object.entries(NOT_LAYERS[view]).filter(([id]) => got[k].switches.has(id)).forEach(([id, row]) => assert.ok(g.tokens.includes(row), `${id} is a control of ${row}, in its group`));
      got[k].filters.forEach(lu => assert.ok(lu && g.tokens.includes('lyLanduse'), `${g.id}: a checkbox with no id is a land-use class (data-lu) of the land use row`));
      if (!g.rows.length) assert.match(got[k].chunk, /<p class="note" data-elsewhere>/, `${g.id}: a group with no layer in this view says where they are`);
    });
    const other = view === '2d' ? '3d' : '2d', here = new Set(got.flatMap(g => g.tokens));
    LY.rows().filter(r => !r.views.includes(view)).forEach(r => assert.ok(!here.has(r.id) && !read(PAGES[view].file).includes(`id="${r.id}"`), `${r.id} is a ${other} row only`));
  });

  test(`${view}: each row's name, source and count are the registry's`, () => {
    const got = parse(view), want = expected(view);
    want.forEach((g, k) => g.rows.filter(r => !r.head).forEach(r => {
      const w = rowOf(got[k].chunk, r.id);
      assert.strictEqual(w.name, r.en, `${r.id}: name`);
      if (!r.src) assert.strictEqual(w.src, null, `${r.id}: no source`);
      else {
        assert.ok(w.src, `${r.id}: a source`);
        assert.strictEqual(w.src.text, typeof r.src === 'string' ? r.src : r.src.en, `${r.id}: source`);
        assert.strictEqual(w.src.name, typeof r.src === 'string', `${r.id}: a source that is a name is marked translate="no"; a translated one is not`);
      }
      assert.strictEqual(w.counted, r.counted !== false, `${r.id}: counted`);
    }));
  });

  test(`${view}: the Spanish of the menu is the registry's`, () => {
    const es = spanish(PAGES[view].i18n), want = expected(view), bad = [];
    const check = (en, sp, what) => { const v = es[en]; if (sp === en ? !(v === undefined || v === en) : v !== sp) bad.push(`${what}: ${JSON.stringify(en)} is ${JSON.stringify(v)}, not ${JSON.stringify(sp)}`); };
    want.forEach(g => {
      const G = LY.GROUPS.find(x => x.id === g.id); check(G.en, G.es, 'group');
      g.rows.forEach(r => {
        if (r.head) return check(r.head.en, r.head.es, 'subheading');
        check(r.en, r.es, r.id);
        if (r.src && typeof r.src !== 'string') check(r.src.en, r.src.es, r.id + ' source');
      });
    });
    assert.deepStrictEqual(bad, []);
  });
}

test('the data groups are the same, in the same order, in both views; the visitor economy is last', () => {
  const ids = (v) => LY.menu(v).filter(g => !g.setting).map(g => g.id);
  assert.deepStrictEqual(ids('2d'), ids('3d'));
  assert.deepStrictEqual(ids('2d'), ['reference', 'economy', 'housing', 'education', 'environment', 'hazards', 'infrastructure', 'communities', 'visitor']);
  // by topic (decision 81 (e)): after Reference, the domains of dictionary_src/domains.json that have layers, in its order, each with the domain's name; every row in its home domain's group
  const D = JSON.parse(read('dictionary_src/domains.json')).domains, top = D.filter(d => !d.id.includes('.')).map(d => d.id);
  const topics = ids('2d').filter(g => g !== 'reference' && g !== 'visitor');
  assert.deepStrictEqual(topics, top.filter(d => topics.includes(d)), 'the topics in the order of the domains');
  topics.forEach(g => { const d = D.find(x => x.id === g), G = LY.GROUPS.find(x => x.id === g); assert.deepStrictEqual([G.en, G.es], [d.name.en, d.name.es], `${g}: the domain's name`); });
  LY.GROUPS.forEach(G => G.rows.filter(r => !r.head).forEach(r => {
    const want = r.domain === null ? (G.setting ? G.id : 'reference') : r.domain === 'economy.visitor-economy' ? 'visitor' : r.domain.split('.')[0];
    assert.strictEqual(G.id, want, `${r.id}: in the group of its home domain (${r.domain})`);
  }));
  assert.deepStrictEqual(LY.menu('3d').filter(g => g.setting).map(g => g.id), ['scene'], 'the 3D scene is the only setting group');
  assert.strictEqual(LY.menu('3d')[0].id, 'scene', 'and it comes first');
  assert.deepStrictEqual(LY.GROUPS.find(g => g.id === 'visitor').rows.map(r => r.id), ['lyPlaces']);
  const titles = LY.GROUPS.flatMap(g => [g.en, g.es]);
  assert.strictEqual(new Set(titles).size, titles.length, 'group titles are distinct');
});

test('the l= keys of the 2D map are the published ones, and the registry keys match them', () => {
  const app = read('site/js/app.js'), LAYER_KEYS = eval('(' + app.match(/const LAYER_KEYS = (\{[^}]*\});/)[1] + ')');
  assert.deepStrictEqual(Object.keys(LAYER_KEYS), ['surfheat', 'places', 'flood', 'slr', 'routes', 'stops', 'hubs', 'taxi', 'prot', 'landuse', 'soil', 'slide', 'slope', 'contours', 'watersheds', 'comunidades', 'wcrp', 'oz', 'pubhousing', 'lihtc', 'reservoirs', 'broadband', 'hexgrid', 'powerlines', 'plants', 'rivers', 'groundwater', 'rain', 'fire', 'police', 'libraries', 'schools', 'historic', 'townhalls', 'dumping', 'fprroutes', 'publicos', 'links', 'traffic', 'bridges', 'airports', 'ferries', 'evcharge', 'barrios', 'muni', 'rings', 'now', 'gaps', 'xfer'], 'links to the map keep working');
  LY.rows().filter(r => r.key).forEach(r => assert.strictEqual(LAYER_KEYS[r.key], r.id, r.key));
  LY.rows().filter(r => r.views.includes('2d') && /^ly|^walkRings$/.test(r.id)).forEach(r => assert.ok(r.key, `${r.id}: a 2D layer has its l= key`));
});

test('tourism last: Economy presets, "Also show on the map", dataset groups, the 3D columns', () => {
  const eco = read('site/js/economy.js');
  const presets = [...eco.slice(eco.indexOf('function ecRenderPresets'), eco.indexOf("$('#ecPresets').innerHTML")).matchAll(/\[T\('([^']+)'\), \[\[/g)].map(m => m[1]);
  assert.ok(presets.length >= 6, 'the presets are read'); assert.strictEqual(presets[presets.length - 1], 'Tourism economy');
  const ctx = [...eco.slice(eco.indexOf('function ecRenderContext'), eco.indexOf('function ecSetContext')).matchAll(/\['(\w+)', /g)].map(m => m[1]);
  const order = LY.rows().map(r => r.id);
  assert.deepStrictEqual(ctx, order.filter(id => ctx.includes(id)), '"Also show on the map" follows the menu');
  assert.strictEqual(ctx[ctx.length - 1], 'lyPlaces');
  const DS = require(path.join(ROOT, 'site', 'js', 'core', 'datasets.js'));
  const g = DS.sortGroups(['Tourism supply', 'Jobs and employers', 'Something new', 'Housing · Cost burden', 'Residents · Flood hazard · FEMA', 'People', 'Health care · Medicare', 'Infrastructure · Emergency services', 'Public safety', 'Infrastructure · Bridges', 'Vulnerability (WCRP) · Updated 2020–2024', 'Population · Household types']);
  assert.deepStrictEqual(g, ['People', 'Population · Household types', 'Jobs and employers', 'Housing · Cost burden', 'Health care · Medicare', 'Residents · Flood hazard · FEMA', 'Public safety', 'Infrastructure · Emergency services', 'Infrastructure · Bridges', 'Vulnerability (WCRP) · Updated 2020–2024', 'Something new', 'Tourism supply']);
  assert.match(eco, /Core\.panel\.browse\(E, \$\('#ecFind'\)\.value, ecGroupsOrder\(\)/, 'the Economy tab lists its groups in that order');
  assert.match(read('site/js/twin3d.js'), /Core\.datasets\.sortGroups\(\[\.\.\.groups\.keys\(\)\]\)/, 'so do the 3D columns');
  const metric = read('site/3d.html').match(/<select id="metric"[\s\S]*?<\/select>/)[0];
  assert.deepStrictEqual([...metric.matchAll(/<option value="(\w+)" selected>/g)].map(m => m[1]), ['population_2020'], 'the 3D columns open on population, not tourism');
});

test('"Also show on the map" holds the whole list of the layers the Economy tab sets, by the menu\'s names; sortGroups lists each group once', () => {
  const eco = read('site/js/economy.js'), body = eco.slice(eco.indexOf('function ecRenderContext'), eco.indexOf('function ecSetContext'));
  const items = [...body.matchAll(/\['(\w+)', (?:T\('([^']+)'\)|'([^']+)')\]/g)].map(m => [m[1], m[2] || m[3]]);
  const set = eco.slice(eco.indexOf('function ecSetContext'), eco.indexOf('function ecContextSync')), sets = [...set.matchAll(/\[('ly\w+'(?:, 'ly\w+')*)\]\.forEach/g)].flatMap(m => eval('[' + m[1] + ']'));
  const order = LY.rows().map(r => r.id), byMenu = (ids) => [...ids].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  assert.deepStrictEqual(items.map(i => i[0]), ['lyMuni', 'lyBarrios', 'lyProt', 'lyLanduse', 'lyFlood', 'lyRoutes', 'lyStops', 'lyPlaces'], 'the whole list');
  assert.deepStrictEqual(items.map(i => i[0]), byMenu(items.map(i => i[0])), 'in the menu\'s order');
  items.filter(([id]) => id !== 'lyMuni').forEach(([id]) => assert.ok(sets.includes(id), `${id}: the tab sets it from the chat too (ecSetContext)`));
  items.forEach(([id, name]) => assert.strictEqual(name, LY.rows().find(r => r.id === id).en, `${id}: the menu's name`));
  const DS = require(path.join(ROOT, 'site', 'js', 'core', 'datasets.js'));
  assert.deepStrictEqual(DS.sortGroups(['Tourism supply', 'People', 'Jobs and employers', 'People', 'Tourism supply', 'Something new', 'Jobs and employers']), ['People', 'Jobs and employers', 'Something new', 'Tourism supply'], 'each group once, in its place');
});

test('one view only: the 3D scene, the 3D columns and the vehicle replay, and the 2D shading, each with the reason it cannot be drawn in the other view', () => {
  const one = LY.oneView(), docs = read('docs/layers.md');
  assert.deepStrictEqual(one.map(r => [r.id, r.views.join()]), [['lyTerrain', '3d'], ['lyBuildings', '3d'], ['lyCols', '3d'], ['lyWatersheds', '2d'], ['lySlope', '2d'], ['lyContours', '2d'], ['lyTrips', '3d']]);
  one.forEach(r => { assert.ok(typeof r.why === 'string' && r.why.length > 30, `${r.id}: why`); assert.ok(docs.includes(r.en), `${r.id}: docs/layers.md names it`); });
  LY.rows().filter(r => r.views.length === 2).forEach(r => assert.ok(!r.why, `${r.id} is in both views: no reason to give`));
  for (const view of ['2d', '3d']) assert.ok(!read(PAGES[view].file).includes('data-elsewhere'), `${view}: every group has its layers in this view, so no note says they are elsewhere`);
});

test('the chat\'s context words switch on layers that both views draw, on the 2D map (ecSetContext) and the 3D view (ask3d.js CTX)', () => {
  const chat = read('site/js/chat.js'), a = chat.indexOf('const CH_CONTEXT = ['), CH = eval(chat.slice(a + 'const CH_CONTEXT = '.length, chat.indexOf('];', a) + 1));
  const ids = [...new Set(CH.map(c => c[1]))], CTX = eval(/const CTX = (\[[^\]]+\])/.exec(read('site/js/ask3d.js'))[1]);
  const eco = read('site/js/economy.js'), set = eco.slice(eco.indexOf('function ecSetContext'), eco.indexOf('function ecContextSync'));
  const lists = [...set.matchAll(/\[('ly\w+'(?:, 'ly\w+')*)\]\.forEach/g)].flatMap(m => eval('[' + m[1] + ']'));
  assert.deepStrictEqual([...CTX].sort(), [...ids].sort(), 'the 3D view switches on every layer the chat names');
  ids.forEach(id => {
    assert.ok(lists.includes(id), `${id}: the 2D map's Economy tab sets it`);
    const r = LY.rows().find(x => x.id === id); assert.ok(r && r.views.length === 2, `${id} is a layer of both views`);
    for (const v of ['2d', '3d']) assert.ok(read(PAGES[v].file).includes(`id="${id}"`), `${id} is on the ${v} page`);
  });
  const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[¿¡?!.]/g, '').trim();
  const ctx = (q) => CH.filter(([re]) => re.test(norm(q))).map(c => c[1]);
  const cases = { 'muestra las estaciones de bomberos': ['lyFire'], 'show the fire stations in Ponce': ['lyFire'], '¿Dónde están los cuarteles de la policía?': ['lyPolice'], 'show police stations': ['lyPolice'],
    'muestra las zonas de oportunidad': ['lyOz'], 'show the Opportunity Zones in Ponce': ['lyOz'], 'muestra las alcaldías': ['lyTownhalls'], 'city halls': ['lyTownhalls'], 'bibliotecas públicas en Caguas': ['lyLibraries'], 'show public libraries': ['lyLibraries'], 'muestra los lugares históricos': ['lyHistoric'],
    'historic places of San Juan': ['lyHistoric'], 'residenciales públicos en Bayamón': ['lyPubHousing'], 'show public housing': ['lyPubHousing'], 'muestra las paradas': ['lyStops'], 'bus stops in Carolina': ['lyStops'],
    'taxis y carga de vehículos eléctricos': ['lyTaxi', 'lyEvCharge'], 'muestra los aeropuertos': ['lyHubs'], 'muestra los puentes': ['lyBridges'], 'show the heliports': ['lyAirports'], 'muestra las lanchas a Culebra': ['lyFerries'], 'estaciones de carga en Ponce': ['lyEvCharge'], 'barrios de Ponce': ['lyBarrios'],
    '¿Dónde es más alta la pobreza?': [], 'propiedades residenciales en Dorado': [], 'unemployment rate by municipality': [] };
  for (const [q, want] of Object.entries(cases)) assert.deepStrictEqual(ctx(q), want, q);
});
