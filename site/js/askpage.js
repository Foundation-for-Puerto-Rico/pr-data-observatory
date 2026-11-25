/* PR Data Observatory: "Ask the observatory" on the pages without a map: the data dictionary, Data management, the Knowledge Areas and the area profiles (docs/ask.md,
   "Pages without a map"). chatboot.js loads this file with chat.js the first time someone is about to use the Ask button, so no page's first load carries it.
   chat.js talks to a page through window.ECON.api, as on the 2D map (economy.js) and the 3D view (ask3d.js). Here the interface has the same datasets (the shared engine,
   js/core/engine.js, over the files of js/core/datasets.js, fetched when the chat opens) and no map: api.mapless tells chat.js to answer in the chat and to give an
   answer that needs the map a "Show on the map" button, which opens index.html (3d.html for the 3D view's own layers) with the question (#ask=, chatHandOver in chat.js).
   A button of an answer pressed afterward (the workbench, the scatter plot, a pattern) opens the 2D map with those datasets, as the 3D view does.
   api.page gives the chat what this page shows: its own greeting and questions, "what is this?" answered from the open dictionary entry or the page's own summary, and
   "this" or "here" read as that entry's dataset or the profile's municipio. Nothing typed leaves the browser. */
const AskPage = (() => {
  const PG = (document.querySelector('script[data-page]') || { dataset: {} }).dataset.page || '';
  const ENGINE_JS = ['core/text.js?v=1', 'core/palettes.js?v=2', 'core/classify.js?v=2', 'core/stats.js?v=4', 'core/time.js?v=1', 'core/format.js?v=2', 'core/normalize.js?v=4', 'core/reliability.js?v=4', 'core/engine.js?v=11', 'core/hexbin.js?v=1', 'core/adapters.js?v=15', 'core/datasets.js?v=29'];   // the versions index.html loads, so the browser can reuse them
  const G = { E: null, loading: null, failed: [] }, cur = { layers: [], select: null, year: null };
  // what chat.js needs from a map page and a page without a map lacks: one download per file (plan.js Data), the page's message (activelayers.js toast), the catalog (S.catalog)
  if (typeof Data === 'undefined') window.Data = (() => { const cache = {}; return { json(p) { if (!cache[p]) cache[p] = fetchJson(p).catch(e => { delete cache[p]; throw e; }); return cache[p]; } }; })();
  if (typeof S === 'undefined') window.S = {};
  document.body.classList.add('ask-page');   // chat.css: the chat over this page's own maps, below its tabs
  if (typeof toast === 'undefined') window.toast = (msg, ms = 3500) => {   // a short message at the foot of the chat
    let t = document.getElementById('chToast');
    if (!t) { document.body.insertAdjacentHTML('beforeend', '<div class="ch-toast" id="chToast" role="status" aria-live="polite" data-t="skip" data-no-glossary></div>'); t = document.getElementById('chToast'); }
    t.textContent = msg; t.classList.add('show'); clearTimeout(t.tm); t.tm = setTimeout(() => t.classList.remove('show'), ms);
  };
  const add = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
  /** The Spanish names of the datasets and the chat's words (the map page's bundle, es.map.js): only the keys this page does not translate, so its own text never changes. */
  async function spanish() {
    if (I18N.lang !== 'es') return;
    const add0 = I18N.add;
    I18N.add = (o) => add0(Object.fromEntries(Object.entries(o).filter(([k]) => !I18N.has(k))));
    try { await add('i18n/es.map.js'); await add('i18n/es.map.economy.js'); } catch { /* the names stay in English */ } finally { I18N.add = add0; }   // the Economy module's words load on first use on the map
  }
  function engine() {
    if (G.E) return Promise.resolve(G.E);
    return G.loading || (G.loading = (async () => {
      for (const f of ENGINE_JS) if (!document.querySelector(`script[src="js/${f}"]`)) await add('js/' + f);
      const [meta, muni, catalog] = await Promise.all([fetchJson('data/meta.json'), fetchJson('data/municipalities.json'), fetchJson('data/catalog.json').catch(() => null), spanish()]);
      if (catalog && !S.catalog) S.catalog = catalog;   // the chat's index of the dictionary (catalog_index.json) loads into it on first use (common.js withIndex)
      const E = Core.engine.create();
      G.failed = (await Core.datasets.load(E, (p) => fetchJson(p), muni, +((meta.generated_at || '').slice(0, 4)) || 2026, ['wcrp'])).failed || [];
      return (G.E = E);
    })().catch(e => { G.loading = null; throw e; }));
  }
  const En = () => G.E;
  const ready = async () => { try { await engine(); return true; } catch { return false; } };
  const answering = () => typeof CH !== 'undefined' && CH.busy;   // chat.js is building an answer: a step of it, not a press of one of its buttons
  /** The 2D map with these datasets on the Economy tab, the year and base, and the workbench view (or the composite builder): the address ask3d.js builds. */
  function link2d(tab, compose) {
    const E = En(), ls = [];
    cur.layers.forEach(l => { const L = E.makeLayer(l.key, l.mode, { norm: l.norm, real: l.real }, ls); if (L && !L.error) ls.push(L); });
    const parts = [cur.select ? encodeURIComponent(cur.select) : '', ls.length ? 'e=' + encodeURIComponent(E.encode(ls)) : '', cur.year != null ? 'ey=' + cur.year : '', E.base !== 2014 ? 'eb=' + E.base : '', compose ? 'wc=' + encodeURIComponent(compose.join(',')) : tab ? 'wb=' + tab : ''];
    return 'index.html' + location.search + '#' + parts.filter(Boolean).join('&');
  }
  function open2d(tab, compose) {
    if (answering() || !En()) return false;
    if (!cur.layers.length && !compose) { toast(I18N.lang === 'es' ? 'Haga una pregunta primero: el mapa 2D se abre con los datos de la respuesta.' : 'Ask a question first: the 2D map opens with the datasets of the answer.', 5000); return false; }
    window.open(link2d(tab, compose), '_blank', 'noopener');
    return true;
  }
  const api = {
    mapless: true,
    ready,
    datasets: () => En() ? En().info() : [],
    meta: (key) => (En() && En().V[key]) || null,
    dictId: (key) => En().dictId(key),
    places: () => En() ? En().geo.names.slice() : [],
    placeIndex: (name) => En() ? En().placeIndex(name) : -1,
    placeId(name) { const E = En(), i = E ? E.placeIndex(name) : -1; return i >= 0 && i < E.geo.pr ? E.geo.ids[i] : null; },
    years: () => En().years(),
    base: () => En().base,
    sources: () => En().sources,
    popAt: (y) => En().pop(y),
    values: (key, o) => En().values(key, o),
    fmt: (key, x, norm = 'value', real = false) => En().fmt({ key, norm, real }, x),
    moe: (key, year) => En().moe({ key, norm: 'value', real: false }, year) || null,
    notLoaded: () => G.failed || [],
    missing: (key, i) => En().missing({ key }, i),
    normOptions: (key) => Core.normalize.options(En().V[key]),
    unitLabel(key, norm = 'value') { const o = En().out({ key, norm }); return { suffix: o.suffix || '', unit: o.unit }; },
    defaultNorm: (key, mode = 'fill') => Core.normalize.defaultNorm(En().V[key], mode),
    state: () => ({ year: cur.year, base: En() ? En().base : null, selected: cur.select, layers: cur.layers.slice() }),
    /* the 2D map's ECON.api.show, with no map: what an answer would show is kept, for the buttons that open the 2D map; a button pressed after the answer opens it */
    async show(spec) {
      if (!(await ready())) return { applied: [], skipped: [{ reason: 'The economy data is not available.' }] };
      const E = En(), applied = [], skipped = [], ls = [];
      for (const l of spec.layers || []) {
        const v = E.V[l.key]; if (!v) { skipped.push({ key: l.key, reason: 'unknown dataset' }); continue; }
        if (ls.length >= 4) { skipped.push({ key: l.key, reason: 'four datasets at most' }); continue; }
        const mode = l.mode === 'symbol' ? 'symbol' : 'fill', norm = l.norm && Core.normalize.options(v).some(o => o[0] === l.norm) ? l.norm : Core.normalize.defaultNorm(v, mode);
        ls.push({ key: l.key, mode, norm, real: !!l.real }); applied.push({ key: l.key, mode, norm });
      }
      if (ls.length) cur.layers = ls; else if (spec.clear !== false) cur.layers = [];
      if (spec.base) E.base = spec.base;
      if ('year' in spec) cur.year = spec.year == null ? null : spec.year;
      if (spec.select !== undefined || spec.clear !== false) cur.select = spec.select && E.placeIndex(spec.select) >= 0 ? spec.select : null;
      if (!answering() && ls.length) open2d(spec.bench || 'table');   // a pattern's "Show on the map", pressed: the 2D map with its datasets
      return { applied, skipped };
    },
    clear() { cur.layers = []; cur.select = null; },
    setYear(y) { cur.year = y == null ? null : y; },
    benchOpen: (tab) => { open2d(tab); },
    compose(keys, now) { if (now) open2d('composite', keys.filter(k => En().V[k])); return false; },   // false: not opened while the answer is built; the answer offers a button (chat.js)
    trendPlaces() { /* the trend chart is on the 2D map */ },
    info(key) {   // the dictionary entry: here on the dictionary, in a new tab elsewhere
      if (answering()) return;
      const id = En().dictId(key);
      if (PG === 'dictionary') location.hash = id; else window.open('dictionary.html' + location.search + '#' + id, '_blank', 'noopener');
    },
    levelSeries: async () => null,   // values by barrio are on the 2D map
  };

  // ── What this page shows ────────────────────────────────────────────────────
  const KA = ['housing', 'wcrp', 'routes', 'gii'];
  const txt = (el) => el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
  const clip = (s, n = 420) => { if (s.length <= n) return s; const c = s.slice(0, n), i = c.lastIndexOf('. '); return i > 120 ? c.slice(0, i + 1) : c.replace(/\s+\S*$/, '') + '…'; };
  const area = () => { try { const a = new URLSearchParams(location.search).get('area'), E = En(); if (!a || !E) return null; const i = E.geo.ids.findIndex(id => String(id) === a); return i >= 0 && i < E.geo.pr ? E.geo.names[i] : null; } catch { return null; } };
  let lastEntry = null;   // the dictionary entry opened last
  document.addEventListener('toggle', e => { if (e.target.matches && e.target.matches('details.de') && e.target.open) lastEntry = e.target; }, true);
  function entry() {
    if (PG !== 'dictionary') return null;
    let h = ''; try { h = decodeURIComponent(location.hash.slice(1)); } catch { /* a broken % */ }
    const byHash = h && document.getElementById(h), el = [byHash, lastEntry, document.querySelector('details.de[open]')].find(x => x && x.matches && x.matches('details.de[open]'));
    if (!el) return null;
    const id = el.dataset.id, E = En(), key = E ? Object.keys(E.V).find(k => E.dictId(k) === id) : null;
    return { id, el, key, name: txt(el.querySelector('.de-name')), one: txt(el.querySelector('.de-one')) };
  }
  const WHAT = /^(?:que es (?:esto|esta pagina|esta entrada|este dato)|de que (?:trata|va) (?:esto|esta pagina)|que (?:significa|quiere decir) (?:esto|este dato)|explica(?:me)? (?:esto|esta pagina)|que hay en esta pagina|what(?:'s| is) (?:this|this page|this entry)(?: about)?|what does this (?:mean|page show)|explain this(?: page| entry)?|what is on this page)$/;
  const HELLO = {
    es: 'Pregúnteme sobre los datos del observatorio: qué significa un término, de dónde viene un dato, dónde algo es más alto o cómo ha cambiado. Respondo aquí con números calculados de los datos publicados, así que encuentro patrones, no causas. Lo que necesita un mapa se abre con «Ver en el mapa».',
    en: 'Ask me about the observatory’s data: what a term means, where a dataset comes from, where something is highest or how it has changed. I answer here with numbers computed from the published data, so I find patterns, not causes. What needs a map opens with “Show on the map”.',
  };
  const LEAD = {
    dictionary: { es: 'En el diccionario, «¿Qué es esto?» explica la entrada que tiene abierta.', en: 'In the dictionary, “What is this?” explains the entry you have open.' },
    datamgmt: { es: 'Esta página describe los archivos publicados; los datos no se cambian aquí. «¿De qué trata esta página?» la resume.', en: 'This page describes the published files; the data are not changed here. “What is this page about?” sums it up.' },
    ka: { es: 'En esta área de conocimiento, «¿De qué trata esta página?» la resume.', en: 'In this Knowledge Area, “What is this page about?” sums it up.' },
    profile: { es: 'En este perfil, «aquí» y «este municipio» quieren decir {m}.', en: 'On this profile, “here” and “this municipio” mean {m}.' },
  };
  const CHIPS = {
    dictionary: { es: ['¿Qué es esto?', '¿Qué es el margen de error?', '¿Dónde es más alto el desempleo?', '¿Qué datos faltan?'], en: ['What is this?', 'What is the margin of error?', 'Where is unemployment highest?', 'What data is missing?'] },
    datamgmt: { es: ['¿De qué trata esta página?', '¿Qué datos faltan?', '¿Qué es el margen de error?', '¿Dónde es más alta la pobreza?'], en: ['What is this page about?', 'What data is missing?', 'What is the margin of error?', 'Where is poverty highest?'] },
    housing: { es: ['¿De qué trata esta página?', '¿Dónde es más alta la renta mediana?', 'Vivienda vacante en San Juan', '¿Qué datos faltan?'], en: ['What is this page about?', 'Where is median rent highest?', 'Vacant housing in San Juan', 'What data is missing?'] },
    wcrp: { es: ['¿De qué trata esta página?', '¿Dónde es más alta la pobreza?', 'zonas inundables en Loíza', '¿Qué es el margen de error?'], en: ['What is this page about?', 'Where is poverty highest?', 'flood zones in Loíza', 'What is the margin of error?'] },
    routes: { es: ['¿De qué trata esta página?', 'muestra las rutas de guagua', 'Número de paradas de transporte colectivo en San Juan', 'transporte colectivo al trabajo'], en: ['What is this page about?', 'show the bus routes', 'how many bus stops in San Juan', 'take the bus to work'] },
    gii: { es: ['¿De qué trata esta página?', '¿Dónde es más alto el desempleo?', '¿Empleos y salarios se mueven juntos?', '¿Qué datos faltan?'], en: ['What is this page about?', 'Where is unemployment highest?', 'Do jobs and pay move together?', 'What data is missing?'] },
    profile: { es: ['Hábleme de {m}', 'pobreza en {m}', '¿Qué es el margen de error?', '¿Qué datos faltan?'], en: ['Tell me about {m}', 'poverty in {m}', 'What is the margin of error?', 'What data is missing?'] },
  };
  const lang = (l) => l === 'en' ? 'en' : 'es';
  const fill = (s, m) => s.replace(/\{m\}/g, m || '');
  const page = {
    name: PG,
    intro(l) {
      l = lang(l); const m = area(), key = KA.includes(PG) ? 'ka' : PG, lead = LEAD[key] && (PG !== 'profile' || m) ? ' ' + fill(LEAD[key][l], m) : '';
      const chips = ((CHIPS[PG] || CHIPS.dictionary)[l]).map(c => fill(c, m)).filter(c => !/\{m\}|^\s|\s$| en $| in $/.test(c));
      return { hello: HELLO[l] + lead, chips: PG === 'profile' && !m ? CHIPS.dictionary[l].slice(1) : chips };
    },
    /** "What is this?": the open dictionary entry, or this page's own title and summary; null for every other question, which the chat answers. */
    async answer(q, l) {
      const n = norm(q).replace(/[¿?¡!.]/g, ' ').replace(/\s+/g, ' ').trim();
      if (!WHAT.test(n)) return null;
      l = lang(l); const es = l === 'es';
      await ready();
      const e = entry(), P = (s) => `<p>${s}</p>`, B = (s) => `<b>${esc(s)}</b>`, chips = (CHIPS[PG] || CHIPS.dictionary)[l].slice(1);
      if (e) {
        const label = e.key && api.meta(e.key) ? T(api.meta(e.key).label) : '';
        if (e.key && typeof CH !== 'undefined') CH.ctx = { keys: [e.key], year: null, muni: null };   // "¿dónde es más alto ese dato?" asks about this entry's dataset
        return { html: P(`${B(e.name)}${e.one ? ': ' + esc(e.one) : ''}`) + `<p class="ch-note">${esc(es ? 'Es la entrada que tiene abierta: allí están la definición completa, las fuentes y cómo citarla.' : 'It is the entry you have open: it has the full definition, the sources and how to cite it.')}</p>`,
          actions: [], follow: e.key ? (es ? ['¿Dónde es más alto ese dato?', '¿Cómo ha cambiado ese dato?'] : ['Where is it highest?', 'How has it changed?']) : chips.slice(0, 2) };
      }
      const title = txt(document.querySelector('main h1, h1')), lede = clip([...document.querySelectorAll('main .lede, .hero .lede')].map(txt).filter(Boolean).join(' ') || txt(document.querySelector('main p')));
      let html = P(`${B(title)}${lede ? ': ' + esc(lede) : ''}`);
      const note = document.querySelector('.review-note');   // the page's "In review" notice (core/knowledge.js): the chat repeats it, in the same words
      if (note && note.lastElementChild) html += `<p class="ch-note">${esc(txt(note.lastElementChild))}</p>`;   // its text, not the icon
      if (PG === 'dictionary') html += `<p class="ch-note">${esc(es ? 'Abra una entrada y pregunte «¿Qué es esto?», o pregunte por un dato.' : 'Open an entry and ask “What is this?”, or ask about a dataset.')}</p>`;
      return { html, actions: [], follow: chips.map(c => fill(c, area())).slice(0, 3) };
    },
    /** "this" and "here" on this page: the open entry's dataset on the dictionary (read as "that dataset", which chat.js resolves to the dataset of the last answer,
        set here to the entry's), the municipio on a profile. viaLink: the question no longer names its dataset, so "Show on the map" opens the map with the answer's datasets. */
    rewrite(q) {
      const e = entry(), m = PG === 'profile' ? area() : null;
      let out = String(q); page.viaLink = false;
      if (e && e.key && api.meta(e.key)) {
        const es = /[áéíóúñ¿¡]|\b(?:esto|este|esta|dato|donde|cómo|como|qué|que)\b/i.test(out), that = es ? 'ese dato' : 'it';
        const r = out.replace(/\b(?:este dato|esta entrada|esta variable|este indicador|this entry|this dataset|this variable|this indicator)\b/gi, that).replace(/(^|[\s¿¡])(?:esto|this)(?=[\s?.!,]|$)/gi, (x, a) => a + that);
        if (r !== out && typeof CH !== 'undefined') { CH.ctx = { keys: [e.key], year: null, muni: null }; out = r; page.viaLink = true; }
      }
      if (m) out = out.replace(/\b(?:este municipio|this municipio|this municipality|this town)\b/gi, m).replace(/(^|[\s¿¡])(aquí|aqui|here)(?=[\s?.!,]|$)/gi, (x, a, w) => `${a}${/^h/i.test(w) ? 'in' : 'en'} ${m}`);
      return out;
    },
    /** The 2D map with the datasets of the answer just built (and its municipio): the Economy tab's own address. */
    mapLink: () => En() && cur.layers.length ? link2d('') : null,
  };
  api.page = page;
  window.ECON = { api };
  return { api, link2d };
})();
