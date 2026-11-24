// The workspace (docs/workspace.md, docs/workspace-feature-parity.md): the shell every page shares, the map's timeline, the widgets' one rule and the workflows' geometry.
//  - every page loads css/ws.css last and has the eight areas in its rail, in order; the generators of the generated pages write the same;
//  - the map has the timeline's controls, each with a name a screen reader can say, and loads js/ws_map.js after the engine's shell;
//  - the timeline takes its years from the engine and names each layer's real period by the engine's own rule: no year is written in the script;
//  - a figure for part of the island is a sum for a count or a dollar total and the median of the municipal values otherwise, and says which;
//  - a point is inside an outline or not, a hole takes it out, and a point near an edge is found;
//  - the three workspace pages are registered for Spanish and for the page-weight budget, and read registries, not lists kept by hand.
// Run: node --test tests/workspace.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..'), SITE = path.join(ROOT, 'site');
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8').replace(/\r\n/g, '\n');
const pages = fs.readdirSync(SITE).filter(f => f.endsWith('.html')).sort();
const RAIL = ['explore.html', 'data.html', 'index.html', 'workflows.html', '3d.html', 'knowledge.html', 'dictionary.html', 'learn.html'];
const ICONS = ['account_tree', 'dark_mode', 'explore', 'grid_view', 'light_mode'];

/** A browser script run in a bare context: enough of a page for the script to define itself without starting. */
function load(file, extra = {}) {
  const el = () => ({ innerHTML: '', textContent: '', hidden: false, style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, setAttribute() {}, getAttribute: () => null, addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] });
  const window = { addEventListener() {}, matchMedia: () => ({ matches: false }), innerWidth: 1440, innerHeight: 900 };
  const ctx = { window, document: { readyState: 'loading', addEventListener() {}, getElementById: () => null, body: el(), documentElement: el() }, localStorage: { getItem: () => null, setItem() {} },
    T: (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s), Tn: (n, one, other, v) => (n === 1 ? one : other).replace(/\{(\w+)\}/g, (m, k) => (k === 'n' ? n : v && k in v ? v[k] : m)),
    esc: (s) => String(s), norm: (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim(), fmt: (n) => String(n), setTimeout, clearTimeout, console, ...extra };
  Object.assign(window, extra.windowProps || {});
  vm.createContext(ctx); vm.runInContext(read(file), ctx, { filename: file });
  return ctx;
}

test('every page loads the workspace stylesheet last and has the eight areas in its rail', () => {
  assert.ok(pages.length >= 28, 'the 25 pages and the three workspace pages');
  for (const p of pages) {
    const html = read('site/' + p);
    const css = [...html.matchAll(/<link rel="stylesheet" href="(css\/[^"?]+)/g)].map(m => m[1]);
    assert.strictEqual(css[css.length - 1], 'css/ws.css', `${p}: css/ws.css comes after the page's own stylesheets, so its tokens and overrides win`);
    assert.strictEqual(css.filter(c => c === 'css/ws.css').length, 1, p);
    const nav = /<nav class="views"[^>]*>([\s\S]*?)<\/nav>/.exec(html);
    assert.ok(nav, p);
    const hrefs = [...nav[1].matchAll(/<a class="btn" href="([a-z0-9\-]+\.html)[^"]*"/g)].map(m => m[1]);
    assert.deepStrictEqual(hrefs, RAIL, `${p}: the rail's areas, in order`);
    const cur = [...nav[1].matchAll(/href="([a-z0-9\-]+\.html)[^"]*" aria-current="page"/g)].map(m => m[1]);
    if (RAIL.includes(p)) assert.deepStrictEqual(cur, [p], `${p} marks itself in the rail`);
    for (const names of html.matchAll(/icon_names=([a-z0-9_,]+)/g)) for (const i of ICONS) assert.ok(names[1].split(',').includes(i), `${p}: the icon font holds ${i} (the rail and the light/dark switch)`);
    assert.match(html, /<script src="js\/i18n\.js\?v=\d+" data-page="\w+"><\/script>/, `${p}: i18n.js sets the theme before the first paint`);
  }
});

test('the generators of the generated pages write the same header', () => {
  const dir = path.join(ROOT, 'docs', 'analysis'), gens = fs.readdirSync(dir).map(d => path.join('docs', 'analysis', d, 'make_page.py')).filter(f => fs.existsSync(path.join(ROOT, f)));
  assert.ok(gens.length >= 14);
  for (const g of gens) {
    const s = read(g);
    if (!s.includes('<nav class="views"')) continue;
    for (const h of ['explore.html', 'data.html', 'workflows.html']) assert.strictEqual(s.split(`<a class="btn" href="${h}"`).length - 1, 1, `${g}: one ${h} link`);
    assert.ok(s.indexOf('href="explore.html"') < s.indexOf('href="data.html"') && s.indexOf('href="data.html"') < s.indexOf('href="workflows.html"'), g);
    assert.match(s, /<link rel="stylesheet" href="css\/ws\.css\?v=\d+">/, `${g}: css/ws.css`);
    for (const i of ICONS) assert.ok(s.includes(i), `${g}: the icon ${i}`);
  }
});

test('the theme is set before the first paint, kept in the browser, and told to the page', () => {
  const s = read('site/js/i18n.js');
  assert.match(s, /doc\.documentElement\.dataset\.theme = theme\(\);/, 'init() sets html[data-theme], and init() runs from the script in <head>');
  assert.match(s, /getItem\('twin\.theme'\) === 'light' \? 'light' : 'dark'/, 'the saved choice, else dark');
  assert.match(s, /new Event\('themechange'\)/);
  const css = read('site/css/ws.css');
  assert.match(css, /html\[data-theme=dark\] \{[^}]*--color-surface: var\(--ws-surface\)/, "the dark theme replaces twin.css's tokens");
  assert.doesNotMatch(css, /backdrop-filter/, 'no frosted glass (FPR brand, as tests/test_overlays.py asks of twin.css)');
  assert.doesNotMatch(css, /--ramp-|--flood-|--cat-|--protected/, "the data's own colours are never themed: a legend must keep matching its map");
});

test('the map has the timeline, named for a screen reader, and loads the workspace after the engine shell', () => {
  const html = read('site/index.html');
  assert.match(html, /<body class="ws-map">/);
  assert.match(html, /<input type="range" id="wtRange" min="0" max="0" step="1" value="0" aria-label="[^"]+" aria-describedby="wtLayers" disabled>/, 'a native range: arrow keys, Home and End, touch; disabled until the engine gives its years');
  for (const [id, attr] of [['wtPrev', 'aria-label'], ['wtNext', 'aria-label'], ['wtPlay', 'aria-label'], ['wtLatest', 'title'], ['wtSpeed', 'aria-label'], ['wsUndo', 'aria-label'], ['wsRedo', 'aria-label'], ['wsGrip', 'aria-label'], ['wsRightHide', 'aria-label']])
    assert.match(html, new RegExp(`id="${id}"[^>]*\\s${attr}="[^"]+"|\\s${attr}="[^"]+"[^>]*id="${id}"`), `${id} has a name`);
  assert.match(html, /id="wtLabel" aria-live="polite"/, 'the chosen period is announced');
  assert.match(html, /role="separator" aria-orientation="horizontal"[^>]*tabindex="0"/, 'the workbench grip can be reached and moved with the keyboard');
  const scripts = [...html.matchAll(/<script src="(js\/[^"?]+)/g)].map(m => m[1]);
  assert.ok(scripts.indexOf('js/ws_map.js') > scripts.indexOf('js/econ_shell.js') && scripts.indexOf('js/ws_map.js') > scripts.indexOf('js/app.js'), 'ws_map.js after app.js and econ_shell.js');
  assert.match(read('site/css/ws.css'), /body\.ws-map #alDock \.ec-year:not\(\.ec-base\), body\.ws-map #alDock #ecRange \{ display: none; \}/, 'the old year menu is hidden, not removed: the engine and the captures still read it');
});

test('the timeline takes its years from the engine: none is written in the script', () => {
  const s = read('site/js/ws_map.js').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
  assert.doesNotMatch(s, /\b(?:19\d\d|20[1-9]\d)\b/, 'no year is written in the code: the bounds, the ticks and the labels all come from the data');
  assert.match(s, /years = a\.years\(\)/, 'the steps are ECON.api.years()');
  assert.match(s, /a\.setYear\(y\)/, 'a move sets the engine\'s own year (ey= in the address)');
  assert.match(s, /TL\.raf = requestAnimationFrame/, 'rapid moves are applied once per frame; the last one wins');
  assert.match(s, /Math\.max\(reduced\(\) \? 2000 : 0/, 'reduced motion: never faster than one step in two seconds');
});

test('each layer names the period it really shows, by the engine rule', () => {
  const time = require(path.join(SITE, 'js', 'core', 'time.js'));
  const V = { acs: { ys: [2014, 2019, 2024], time: { type: 'window', windowYears: 5 } }, jobs: { ys: [2014, 2015, 2016, 2025], time: { type: 'period' } }, flood: { ys: [2026], time: { type: 'snapshot' } }, late: { ys: [2020, 2021], time: { type: 'period' } } };
  let year = 2026;
  const ECON = { api: { meta: (k) => V[k], state: () => ({ year, layers: [] }), years: () => [2014, 2015, 2016, 2019, 2020, 2021, 2024, 2025, 2026], places: () => [] } };
  const ctx = load('site/js/ws_map.js', { windowProps: { ECON, Core: { time } }, ECON, Core: { time } });
  const P = ctx.window.Workspace.period;
  assert.deepStrictEqual({ ...P('acs') }, { text: '2020–2024 (latest at or before 2026)', kind: 'before' }, 'a 2020–2024 survey estimate is never called a 2026 observation');
  assert.deepStrictEqual({ ...P('flood') }, { text: 'snapshot 2026', kind: 'fixed' });
  year = 2019; assert.deepStrictEqual({ ...P('acs') }, { text: '2015–2019', kind: 'exact' });
  assert.deepStrictEqual({ ...P('jobs') }, { text: '2016 (latest at or before 2019)', kind: 'before' }, 'no value is made up for 2017 to 2019');
  assert.deepStrictEqual({ ...P('late') }, { text: 'first data 2020', kind: 'early' });
  year = null; assert.deepStrictEqual({ ...P('jobs') }, { text: '2025', kind: 'exact' }, 'Latest: each dataset shows its own last period');
});

test('a figure for part of the island says what it is', () => {
  const time = require(path.join(SITE, 'js', 'core', 'time.js'));
  const V = { people: { type: 'count', ys: [2020] }, rate: { type: 'rate', ys: [2020] } };
  const ECON = { api: { meta: (k) => V[k], state: () => ({ year: null, layers: [] }), years: () => [2020], places: () => [] } };
  const A = load('site/js/ws_map.js', { windowProps: { ECON, Core: { time } }, ECON, Core: { time } }).window.Workspace._test.aggregate;
  const d = { v: [10, 20, null, 40, 100] };
  assert.deepStrictEqual({ ...A({ key: 'people', norm: 'value' }, d, [0, 1, 2, 3]) }, { v: 70, how: 'Sum of 3 municipios' }, 'a count as published is added up; a missing value is not a zero and is not counted');
  assert.deepStrictEqual({ ...A({ key: 'rate', norm: 'value' }, d, [0, 1, 3, 4]) }, { v: 30, how: 'Median of the values of 4 municipios' }, 'a rate is never averaged or pooled without its denominators');
  assert.deepStrictEqual({ ...A({ key: 'people', norm: 'per1000' }, d, [0, 1]) }, { v: 15, how: 'Median of the values of 2 municipios' }, 'a count shown per resident is a rate');
  assert.deepStrictEqual({ ...A({ key: 'rate', norm: 'value' }, d, [2]) }, { v: null, how: 'No value' });
});

test('a point is inside an outline, outside it, in a hole or near its edge', () => {
  const W = load('site/js/ws_flows.js').window.Workflows._test;
  const sq = [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]];   // a square with a square hole
  const ix = W.index([{ type: 'Feature', properties: { name: 'A' }, geometry: { type: 'Polygon', coordinates: sq } }, { type: 'Feature', properties: { name: 'B' }, geometry: { type: 'MultiPolygon', coordinates: [[[[20, 20], [21, 20], [21, 21], [20, 21], [20, 20]]]] } }, { type: 'Feature', properties: {}, geometry: null }]);
  assert.strictEqual(ix.length, 2, 'a feature with no shape is skipped');
  assert.strictEqual(W.hit(ix, 1, 1).p.name, 'A');
  assert.strictEqual(W.hit(ix, 5, 5), null, 'a hole takes the point out');
  assert.strictEqual(W.hit(ix, 20.5, 20.5).p.name, 'B');
  assert.strictEqual(W.hit(ix, 11, 1), null);
  const real = W.index([{ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[[-66.10, 18.40], [-66.09, 18.40], [-66.09, 18.41], [-66.10, 18.41], [-66.10, 18.40]]] } }]);
  assert.ok(W.edge(real, -66.09998, 18.405, 5) <= 5, 'about 2 m inside the west edge: close enough to fall on either side');
  assert.strictEqual(W.edge(real, -66.095, 18.405, 5), Infinity, 'the middle of the area is far from any edge');
});

test('the workspace pages read registries and are registered for Spanish and for the budget', () => {
  const routes = JSON.parse(read('dictionary_src/routes.json')).routes, i18n = JSON.parse(read('i18n_src/pages.json')).pages;
  for (const [name, page, script, files] of [['explore', 'explore.html', 'ws_explore.js', ['data/catalog.json', 'data/catalog_views.json']], ['data', 'data.html', 'ws_data.js', ['data/catalog.json', 'data/catalog_index.json']], ['workflows', 'workflows.html', 'ws_flows.js', ['data/registry.json', 'data/municipios.geojson']]]) {
    assert.strictEqual(routes[name].page, page); assert.strictEqual(i18n[name].file, page);
    assert.ok(i18n[name].scripts.includes(script), `${name}: i18n.py reads the strings of ${script}`);
    assert.ok(i18n[name].modules.glossary, `${name}: the glossary module`);
    const js = read('site/js/' + script);
    for (const f of files) { assert.ok(js.includes(`'${f}'`), `${script} reads ${f}`); assert.ok(routes[name].first.includes(f.replace('data/', '')), `routes.json: ${name} loads ${f} first`); }
    assert.match(read('site/' + page), new RegExp(`<script src="js/${script.replace('.', '\\.')}\\?v=\\d+"></script>`));
  }
  assert.ok(i18n.map.scripts.includes('ws_map.js') && i18n.map.scopes.includes('workspace'));
  assert.match(read('site/js/ws_flows.js'), /\/\\bpoints\\b\/i\.test\(f\.title/, "the sources are the registry's files of points, not a list");
  assert.doesNotMatch(read('site/js/ws_data.js'), /site\/workspace|\.\.\/data\//, 'no path into the prototype');
});

test('the Spanish of the workspace keeps every placeholder', () => {
  for (const f of ['workspace.json', 'workspace_pages.json']) {
    const d = JSON.parse(read('i18n_src/es/' + f));
    for (const [k, v] of Object.entries(d)) { if (k.startsWith('_')) continue;
      const want = (k.match(/\{\w+\}/g) || []).sort().join();
      for (const s of [].concat(v)) assert.strictEqual((s.match(/\{\w+\}/g) || []).sort().join(), want, `${f}: ${k}`);
    }
  }
});
