// The chat ("Ask the observatory") in Node, with no page: site/js/chat.js (and site/js/ask.js when the source has it) run over the real datasets, with a page stand-in
// (ECON.api) that records what an answer puts on the map: the datasets it shades or draws as symbols, the layers it switches on, the place it goes to, the workbench view
// it opens. The 2D stand-in follows economy.js (ecApi.show, ecSetContext), the 3D one ask3d.js (two datasets as columns, the scene and time layers it can switch on).
// Used by tests/ask_dev.js (the development set), tests/chat_lexicon_replay.js (ANSWERS=1: every answer of the replay, before and after) and tests/ask.test.js.
//   const R = require('./ask_runtime'); const env = R.env({ chatSrc, askSrc, lang: 'es', view: '2d' }); const o = await env.answer('transporte y vivienda');
'use strict';
const fs = require('fs'), path = require('path'), cp = require('child_process');
const ROOT = path.join(__dirname, '..');
const core = (n) => require(path.join(ROOT, 'site', 'js', 'core', n + '.js'));
const readData = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, 'site', 'data', f), 'utf8'));
const norm = (x) => (x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();   // common.js
const esc = (x) => x == null ? '' : String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');   // common.js
const fmt = (n, d = 0) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
globalThis.fmt = globalThis.fmt || fmt;

/** A file of the main branch (git show origin/main:<f>), or null when main has no such file. */
function gitShow(f, ref = 'origin/main') {
  try { return cp.execSync(`git show ${ref}:${f}`, { cwd: ROOT, maxBuffer: 1 << 27, stdio: ['ignore', 'pipe', 'ignore'] }).toString('utf8'); } catch (e) { return null; }
}
let ENGINE = null;
/** The datasets of the Economy tab, built from the published files as the map builds them (core/datasets.js). */
function engine() {
  if (ENGINE) return ENGINE;
  const engineMod = core('engine'), datasets = core('datasets');
  const X = engineMod.create(), muni = readData('municipalities.json'), meta = readData('meta.json'), docs = {};
  for (const f of datasets.FILES) docs[f.name] = readData(f.file);
  datasets.apply(X, docs, muni, +((meta.generated_at || '').slice(0, 4)) || 2026);
  return ENGINE = X;
}
/** The Spanish of the map page (site/i18n/es.map.js), as I18N.add receives it. */
function spanish(src) {
  const dict = {}; new Function('I18N', src)({ add: (d) => Object.assign(dict, d) });
  return dict;
}
function makeT(lang, dict) {
  const fill = (s, v) => v ? String(s).replace(/\{(\w+)\}/g, (m, k) => k in v ? String(v[k] == null ? '' : v[k]) : m) : String(s);
  return (k, v) => { let s = lang === 'es' && dict[k] !== undefined ? dict[k] : k; if (Array.isArray(s)) s = s[0]; return fill(s, v); };
}

// ── The page stand-in ──────────────────────────────────────────────────────────
const AREA = ['lyBarrios', 'lyFlood', 'lyProt', 'lyLanduse', 'lyRoutes', 'lyPlaces'];   // economy.js ecSetContext: on exactly when the answer names them
const CTX3D = ['lyPlaces', 'lyRoutes', 'lyFlood', 'lyProt', 'lyLanduse', 'lyBarrios', 'lyStops', 'lyHubs', 'lyTaxi', 'lyOz', 'lyPubHousing', 'lyLihtc', 'lyReservoirs', 'lyBroadband', 'lyRivers', 'lyGroundwater', 'lyRain', 'lyFire', 'lyPolice', 'lyTownhalls', 'lyLibraries', 'lyHistoric', 'lySlr', 'walkRings', 'lyComunidades', 'lyWcrp'];
const LEVEL_LOADED = {};   // level files read into the shared engine (economy.js ecLoadLevel, ecLoadLevelFile)
function makeApi(X, view, rec, T, catalog) {
  const normalize = core('normalize');
  const layers = [];   // { key, mode, norm, real }
  const st = { year: null, base: 2014, select: null };
  const on = (id, v) => { if (v) rec.layers.add(id); else rec.layers.delete(id); };
  const api = {
    view,
    async ready() { return true; },
    datasets: () => X.info(),
    meta: (key) => X.V[key] || null,
    dictId: (key) => X.dictId(key),
    places: () => X.geo.names.slice(),
    placeIndex: (name) => X.placeIndex(name),
    placeId(name) { const i = X.placeIndex(name); return i >= 0 && i < X.geo.pr ? X.geo.ids[i] : null; },
    years: () => X.years(),
    base: () => st.base,
    sources: () => X.sources,
    popAt: (y) => X.pop(y),
    values: (key, o) => X.values(key, o),
    fmt: (key, x, n = 'value', real = false) => X.fmt({ key, norm: n, real }, x),
    moe: (key, year) => X.moe({ key, norm: 'value', real: false }, year) || null,
    notLoaded: () => [],
    missing: (key, i) => X.missing({ key }, i),
    normOptions: (key) => normalize.options(X.V[key]),
    unitLabel(key, n = 'value') { const o = X.out({ key, norm: n }); return { suffix: o.suffix || '', unit: o.unit }; },
    defaultNorm: (key, mode = 'fill') => normalize.defaultNorm(X.V[key], mode),
    state: () => ({ year: st.year, base: st.base, selected: st.select, layers: layers.map(l => ({ ...l })) }),
    async show(spec) {
      rec.calls.push(['show', JSON.parse(JSON.stringify(spec))]);
      const applied = [], skipped = [];
      if (view === '3d') {
        const ls = [];
        for (const l of spec.layers || []) {
          const v = X.V[l.key]; if (!v) { skipped.push({ key: l.key, reason: 'unknown dataset' }); continue; }
          if (ls.length >= 2) { skipped.push({ key: l.key, reason: 'the 3D columns show two datasets' }); continue; }
          const n = l.norm && normalize.options(v).some(o => o[0] === l.norm) ? l.norm : normalize.defaultNorm(v, 'fill');
          ls.push({ key: l.key, mode: 'fill', norm: n, real: !!l.real }); applied.push({ key: l.key, mode: 'fill', norm: n });
        }
        if (ls.length) layers.splice(0, layers.length, ...ls); else if (spec.clear !== false) layers.length = 0;
        (spec.context || []).forEach(id => { if (CTX3D.includes(id) || (rec.ctx3 || []).includes(id)) on(id, true); });
      } else {
        if (spec.clear !== false) layers.length = 0;
        for (const l of spec.layers || []) {
          const v = X.V[l.key]; if (!v) { skipped.push({ key: l.key, reason: 'unknown dataset' }); continue; }
          let mode = l.mode || 'fill';
          if (mode === 'fill' && layers.filter(x => x.mode === 'fill').length >= 2) mode = 'symbol';
          const opts = { real: !!l.real };
          if (l.norm && normalize.options(v).some(o => o[0] === l.norm)) opts.norm = l.norm;
          const L = X.makeLayer(l.key, mode, opts, layers);
          if (L && !L.error) { layers.push({ key: L.key, mode: L.mode, norm: L.norm, real: !!L.real, level: l.level === 'barrio' && L.mode === 'fill' ? 'barrio' : '' }); applied.push({ key: l.key, mode: L.mode, norm: L.norm }); } else skipped.push({ key: l.key, reason: 'too many shaded layers' });
        }
        if (spec.context) {
          AREA.forEach(id => on(id, spec.context.includes(id)));
          spec.context.forEach(id => { if (!AREA.includes(id) && (rec.ctx2 || []).includes(id)) on(id, true); });
        }
      }
      if (spec.base) st.base = spec.base;
      if ('year' in spec) st.year = spec.year == null ? null : spec.year;
      if (spec.select) { const i = X.placeIndex(spec.select); if (i >= 0) st.select = X.geo.names[i]; }
      if (spec.zoom) rec.zoom = spec.zoom;
      if (spec.bench && view !== '3d') rec.bench = spec.bench;
      return { applied, skipped };
    },
    clear(o = {}) { rec.calls.push(['clear']); layers.length = 0; if (!o.keepPlace) st.select = null; },
    async levelSeries(key, level = 'barrio', year = null) {   // economy.js levelSeries; the 3D view has none (ask3d.js)
      if (view === '3d') return null;
      const v = X.V[key], A = core('adapters'); if (!v) return null;
      const F = catalog.index.fields, row = catalog.index.rows.find(r => r[F.indexOf('id')] === X.dictId(key)), have = (row && row[F.indexOf('levels')]) || [];
      if (!(A.levelsFor(v, have).includes(level) || (level === 'barrio' && (v.barrioFile || v.level)))) return null;
      if (v.barrioFile) { if (!LEVEL_LOADED[v.barrioFile]) { A.levelFile(X, readData(v.barrioFile), { level: 'barrio' }); LEVEL_LOADED[v.barrioFile] = 1; } }
      else if (!v.level && !LEVEL_LOADED[level]) {
        const doc = readData({ barrio: 'acs_barrio.json', tract: 'acs_tract.json', 'block-group': 'acs_blockgroup.json' }[level]), cw = readData('geo/crosswalk.json'), G = Object.fromEntries(cw.fields.map((f, i) => [f, i])), by = new Map(cw.units[level].map(r => [r[G.id], r]));
        A.levelFile(X, doc, { level, names: doc.geo.ids.map(id => { const r = by.get(id); return r ? { es: r[G.name_es], en: r[G.name_en] } : { es: id, en: id }; }) }); LEVEL_LOADED[level] = 1;
      }
      return X.series({ key, norm: 'value', real: false }, year, level);
    },
    setYear(y) { st.year = y == null ? null : y; },
    benchOpen: (tab) => { rec.calls.push(['bench', tab]); if (view !== '3d' || !rec.busy()) rec.bench = tab; },
    compose(keys, now) { rec.calls.push(['compose', keys, !!now]); if (view === '3d') return false; rec.compose = keys; },
    trendPlaces() {},
    info(key) { rec.calls.push(['info', key]); },
  };
  rec.data = () => layers.map(l => l.key);
  rec.dataModes = () => layers.map(l => l.level ? [l.key, l.mode, l.level] : [l.key, l.mode]);
  rec.state = st;
  return api;
}

/**
 * An environment: one copy of the chat (and of ask.js when given) over the real datasets, in one page language and view.
 *   chatSrc   the text of chat.js (default: this branch's)          askSrc  the text of ask.js (default: this branch's, when it exists; null: none)
 *   lang      the page language ('es' or 'en')                      view    '2d' (index.html) or '3d' (3d.html)
 *   data      'branch' (default) or 'main': the catalog files, the Spanish bundle and the wanted list of that branch
 */
function env({ chatSrc, askSrc, lang = 'en', view = '2d', data = 'branch' } = {}) {
  const read = (f) => data === 'main' ? gitShow(f) : fs.readFileSync(path.join(ROOT, f), 'utf8');
  chatSrc = chatSrc || fs.readFileSync(path.join(ROOT, 'site', 'js', 'chat.js'), 'utf8');
  if (askSrc === undefined) { const p = path.join(ROOT, 'site', 'js', 'ask.js'); askSrc = fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : null; }
  const X = engine();
  const es = { ...spanish(read('site/i18n/es.map.js') || ''), ...spanish(read('site/i18n/es.map.economy.js') || '') }, T = makeT(lang, es);   // the map's bundle and its Economy module's, as askpage.js reads them
  const catIndex = JSON.parse(read('site/data/catalog_index.json') || 'null') || (() => { const c = JSON.parse(read('site/data/catalog.json')); return { index: c.index, sources: c.sources }; })();
  const catalog = { ...JSON.parse(read('site/data/catalog.json')), index: catIndex.index, sources: catIndex.sources };
  const files = {
    'data/wanted.json': JSON.parse(read('site/data/wanted.json')), 'data/registry.json': JSON.parse(read('site/data/registry.json')),
    'data/catalog_es.json': JSON.parse(read('site/data/catalog_es.json') || '{}'),
    'data/glossary_forms_en.json': JSON.parse(read('site/data/glossary_forms_en.json') || '{"terms":[]}'), 'data/glossary_forms_es.json': JSON.parse(read('site/data/glossary_forms_es.json') || '{"terms":[]}'),
    'data/glossary_defs_en.json': JSON.parse(read('site/data/glossary_defs_en.json') || '{}'), 'data/glossary_defs_es.json': JSON.parse(read('site/data/glossary_defs_es.json') || '{}'),
  };
  const cwp = path.join(ROOT, 'site', 'data', 'geo', 'crosswalk.json'); if (fs.existsSync(cwp)) { let cw = null; Object.defineProperty(files, 'data/geo/crosswalk.json', { get: () => cw || (cw = JSON.parse(fs.readFileSync(cwp, 'utf8'))), enumerable: true }); }   // the barrio names (chat.js reads them for a barrio named alone)
  const gaz = path.join(ROOT, 'site', 'data', 'gazetteer.json'); if (fs.existsSync(gaz)) Object.defineProperty(files, 'data/gazetteer.json', { get: () => JSON.parse(fs.readFileSync(gaz, 'utf8')), enumerable: true });
  const rec = { calls: [], layers: new Set(), bench: null, compose: null, zoom: null, busy: () => !!(CHAT && CHAT.CH.busy), ctx2: [], ctx3: [] };
  // the point layers economy.js switches on (never off) and the ones ask3d.js can switch on, as the page under test declares them
  const ecoSrc = read('site/js/economy.js') || '', a3Src = read('site/js/ask3d.js') || '';
  const set = ecoSrc.slice(ecoSrc.indexOf('function ecSetContext'), ecoSrc.indexOf('function ecContextSync'));
  rec.ctx2 = [...set.matchAll(/'(ly\w+|walkRings)'/g)].map(m => m[1]);
  const c3 = /const CTX = (\[[^\]]+\])/.exec(a3Src), x3 = /const CTX_3D = (\[[^\]]+\])/.exec(a3Src);
  rec.ctx3 = [...(c3 ? eval(c3[1]) : []), ...(x3 ? eval(x3[1]) : [])];
  rec.switches = [...(read(view === '3d' ? 'site/3d.html' : 'site/index.html') || '').matchAll(/<input type="checkbox" id="(\w+)"/g)].map(m => m[1]);
  const html3 = read('site/3d.html') || '', sel = /<select id="metric"[\s\S]*?<\/select>/.exec(html3);
  rec.metrics3d = sel ? [...sel[0].matchAll(/<option value="(\w+)"[^>]*>([^<]+)</g)].filter(m => m[1] !== '__any').map(m => [m[1], m[2].replace(/&amp;/g, '&')]) : [];
  const api = makeApi(X, view, rec, T, catalog);
  const store = new Map();
  const I18N = { lang, date: (d) => d.toISOString().slice(0, 10), en: (h) => h, fmt };
  // the page as chat.js finds it: its switches (input#id, the layers on are rec.layers), the 3D column menu (#metric), the map (Leaflet in 2D, MapLibre in 3D)
  const switchEl = (id) => ({ id, type: 'checkbox', get checked() { return rec.layers.has(id); }, set checked(v) { if (v) rec.layers.add(id); else rec.layers.delete(id); }, dispatchEvent() {} });
  const metricEl = { value: '', get options() { return rec.metrics3d.map(([value, label]) => ({ value, textContent: label })); } };
  const document = { getElementById: (id) => view === '3d' && id === 'metric' ? metricEl : view === '3d' && id === 'lyCols' ? { checked: false } : rec.switches.includes(id) && id !== 'lyCols' ? switchEl(id) : null, createElement: () => ({}) };
  const map = view === '3d' ? { resize() {}, flyTo(o) { rec.zoom = { lat: o.center[1], lon: o.center[0], z: o.zoom }; } } : { invalidateSize() {}, flyTo(ll, z) { rec.zoom = { lat: ll[0], lon: ll[1], z }; } };
  const S = { catalog };
  const Data = { json: async (p) => { const k = p.split('?')[0]; if (k in files) return files[k]; throw new Error('no file ' + p); } };
  const g = {
    window: { ECON: { api } }, I18N, T, Tn: (n, one, other, v) => T(n === 1 ? one : other, { n, ...(v || {}) }), esc, fmt, norm, toast: () => {}, Data, S, withIndex: async (c) => c, fetchJson: Data.json,
    localStorage: { getItem: (k) => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
    navigator: {}, document, Event: function Event(type) { this.type = type; }, $: () => null, isMobile: () => false, map, setPanel: () => {}, Core: { layers: core('layers') },
    setMetric: async (v) => { rec.metric = v; }, showTab: () => {},
    ActiveLayers: { off: (ids) => { rec.calls.push(['alloff', ids]); if (ids == null) rec.layers.clear(); }, list: () => [...rec.layers], count: () => rec.layers.size },   // the layer chip's "Turn all off" (core/activelayers.js)
  };
  g.window.Core = g.Core;
  let Ask = null;
  if (askSrc) {   // ask.js: a UMD module (window.Ask in the page)
    const mod = { exports: {} };
    new Function('module', 'exports', 'window', 'globalThis', 'norm', askSrc)(mod, mod.exports, g.window, g.window, norm);
    Ask = mod.exports && Object.keys(mod.exports).length ? mod.exports : g.window.Ask;
  }
  g.Ask = Ask; g.window.Ask = Ask;
  const names = Object.keys(g);
  const body = `${chatSrc}\nreturn { CH, chParse, chIntent, Handlers, Tools, chAnswer: typeof chAnswer === 'function' ? chAnswer : null, chAskModule: typeof chAskModule === 'function' ? chAskModule : null, chWish };`;
  const CHAT = new Function(...names, body)(...names.map(k => g[k]));
  CHAT.CH.ui = lang;
  /** One question, from a page where nothing is on: what the answer shows. */
  async function answer(q, { keepState = false } = {}) {
    if (!keepState) { rec.calls = []; rec.layers.clear(); rec.bench = null; rec.compose = null; rec.zoom = null; rec.metric = null; api.clear(); rec.calls = []; CHAT.CH.ctx = { keys: [], year: null, muni: null }; }
    CHAT.CH.busy = true;
    let out, st, err = null;
    try {
      if (!CHAT.CH.wanted) { CHAT.CH.wanted = files['data/wanted.json']; CHAT.CH.registry = files['data/registry.json']; }
      if (!CHAT.CH.ask) { const F = catalog.index.fields, a = F.indexOf('ask'), id = F.indexOf('id'); CHAT.CH.ask = {}; if (a >= 0) catalog.index.rows.forEach(r => { if (r[a]) CHAT.CH.ask[r[id]] = r[a]; }); }
      if (CHAT.chAnswer) { const r = await CHAT.chAnswer(q); out = r.out; st = r.st; }
      else { st = CHAT.chParse(q); CHAT.CH.lastLang = st.lang; out = await (CHAT.Handlers[st.intent] || CHAT.Handlers.unknown)(st); }
    } catch (e) { err = e; out = { html: '', actions: [] }; st = st || {}; }
    finally { CHAT.CH.busy = false; }
    const text = String(out.html || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
    return {
      q, intent: st.intent || null, lang: st.lang || null, keys: (st.keys || []).slice(), data: rec.data(), modes: rec.dataModes(), layers: [...rec.layers].sort(), select: rec.state.select, zoom: rec.zoom,
      bench: rec.bench, compose: rec.compose, metric: rec.metric || null, text, html: out.html || '', actions: (out.actions || []).map(a => a.label), follow: [...(out.follow || []), ...(out.chips || [])], plan: out.plan || null, error: err ? String(err.stack || err) : null,
    };
  }
  return { answer, chat: CHAT, api, rec, X, T, Ask };
}

module.exports = { env, engine, gitShow, spanish, makeT, norm, ROOT };
