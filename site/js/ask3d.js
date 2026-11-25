/* PR Data Observatory: the "Ask the observatory" chat on the 3D view. chatboot.js adds the button and loads chat.js the first time someone uses it, as on the 2D map.
   chat.js talks to the page through window.ECON.api; this file gives the 3D view that interface over its own copy of the shared engine (ENG in twin3d.js), so every
   answer is computed from the same datasets. An answer shows on the map as the municipality columns: the first dataset is the height, the second (if any) the color.
   The 2D map's workbench (scatter plot, trend chart, table, inspector, composite) has no 3D form: its buttons in the chat open the 2D map in a new tab with the same
   datasets and year, on that view. A chart the chat would open by itself, while it builds an answer, is not opened here; the button stays in the answer. */
const Ask3D = (() => {
  const CTX = ['lyPlaces', 'lyRoutes', 'lyFlood', 'lyProt', 'lyLanduse', 'lyBarrios', 'lyStops', 'lyHubs', 'lyTaxi', 'lyBridges', 'lyAirports', 'lyFerries', 'lyEvCharge', 'lyOz', 'lyPowerLines', 'lyPlants', 'lyPubHousing', 'lyLihtc', 'lyReservoirs', 'lyBroadband', 'lyRivers', 'lyGroundwater', 'lyRain', 'lyFire', 'lyPolice', 'lyTownhalls', 'lyLibraries', 'lyHistoric'];   // the context layers the chat can turn on (chat.js CH_CONTEXT): all of them are on the 3D view too
  const cur = { layers: [], select: null };
  const En = () => ENG.E;
  const loaded = new Promise(ok => {   // the page's own data (municipalities, boundaries) and the map's layers: twin3d.js hides #loader once they are in
    const done = () => $('#loader') && $('#loader').classList.contains('hide');
    const watch = () => { if (done()) return ok(); new MutationObserver((_, o) => { if (done()) { o.disconnect(); ok(); } }).observe($('#loader'), { attributes: true, attributeFilter: ['class'] }); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch, { once: true }); else watch();
  });
  const busyOk = async () => { await loaded; try { await engineLoad(); } catch { return false; } if (!S.catalog) S.catalog = await Data.json('data/catalog.json').catch(() => null); return true; };   // the catalog gives the chat the fields of the registry ("salud", "environment")
  function link2d(tab, compose) {   // the 2D map with the chat's datasets on the Economy tab, the year and base, and the workbench view (or the composite builder with those inputs)
    const E = En(), ls = [];
    cur.layers.forEach(l => { const L = E.makeLayer(l.key, l.mode, { norm: l.norm, real: l.real }, ls); if (L && !L.error) ls.push(L); });
    const parts = [cur.select ? encodeURIComponent(cur.select) : '', ls.length ? 'e=' + encodeURIComponent(E.encode(ls)) : '', ENG.y != null ? 'ey=' + ENG.y : '', E.base !== 2014 ? 'eb=' + E.base : '', compose ? 'wc=' + encodeURIComponent(compose.join(',')) : 'wb=' + tab];
    return 'index.html' + location.search + '#' + parts.filter(Boolean).join('&');
  }
  const answering = () => typeof CH !== 'undefined' && CH.busy;   // chat.js is building an answer: a step of it, not a press of one of its buttons
  function open2d(tab, compose) {
    if (answering()) return false;
    if (!cur.layers.length && !compose) { toast(T('Ask a question first: the 2D map opens with the datasets of the answer.'), 5000); return false; }
    window.open(link2d(tab, compose), '_blank', 'noopener');
    return true;
  }
  async function draw() {
    const [h, c] = cur.layers;
    ENG.h = h.key; ENG.ho = { norm: h.norm, real: !!h.real }; ENG.c = c ? c.key : ''; ENG.co = c ? { norm: c.norm, real: !!c.real } : {};
    $('#metric').value = '__any'; $('#lyCols').checked = true;
    await setMetric('__any');
    $('#engH').value = ENG.h; $('#engC').value = ENG.c; $('#engY').value = ENG.y == null ? '' : String(ENG.y);
    showTab('layers', { open: false });   // the legend of the columns: the Layers tab, its group open
    const body = $('#metric').closest('.fold-body'), btn = body && body.parentElement.querySelector('.fold-toggle');
    if (btn && btn.getAttribute('aria-expanded') !== 'true') btn.click();
    refreshFolds();
  }
  const api = {
    ready: busyOk,
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
    notLoaded: () => ENG.failed || [],
    missing: (key, i) => En().missing({ key }, i),
    normOptions: (key) => Core.normalize.options(En().V[key]),
    unitLabel(key, norm = 'value') { const o = En().out({ key, norm }); return { suffix: o.suffix || '', unit: o.unit }; },
    defaultNorm: (key, mode = 'fill') => Core.normalize.defaultNorm(En().V[key], mode),
    state: () => ({ year: ENG.y, base: En() ? En().base : null, selected: cur.select, layers: cur.layers.slice() }),
    /* the same spec as the 2D map's ECON.api.show; bench is not opened here (see the top of this file) */
    async show(spec) {
      if (!(await busyOk())) return { applied: [], skipped: [{ reason: 'The economy data is not available.' }] };
      if (isMobile()) setPanel(false);
      const E = En(), applied = [], skipped = [], ls = [];
      for (const l of spec.layers || []) {
        const v = E.V[l.key]; if (!v) { skipped.push({ key: l.key, reason: 'unknown dataset' }); continue; }
        if (ls.length >= 2) { skipped.push({ key: l.key, reason: 'the 3D columns show two datasets' }); continue; }
        const norm = l.norm && Core.normalize.options(v).some(o => o[0] === l.norm) ? l.norm : Core.normalize.defaultNorm(v, 'fill');
        ls.push({ key: l.key, mode: 'fill', norm, real: !!l.real }); applied.push({ key: l.key, mode: 'fill', norm });
      }
      if (ls.length) cur.layers = ls; else if (spec.clear !== false) cur.layers = [];
      if (spec.base) E.base = spec.base;
      if ('year' in spec) ENG.y = spec.year == null ? null : spec.year;
      (spec.context || []).forEach(id => { const el = CTX.includes(id) && $('#' + id); if (el && !el.checked) { el.checked = true; el.dispatchEvent(new Event('change')); } });
      if (cur.layers.length) await draw();
      cur.select = null;
      if (spec.select) {
        const f = S.muniFc.features.find(x => x.properties.municipality === spec.select);
        if (f) { cur.select = spec.select; fitTo(featureBounds(f.geometry), { padding: 40, maxZoom: 12 }); }
      }
      return { applied, skipped };
    },
    clear() { cur.layers = []; cur.select = null; if (metricKey === '__any') { $('#lyCols').checked = false; setMetric(''); } },
    setYear(y) { ENG.y = y == null ? null : y; if (metricKey === '__any' && ENG.E) { $('#engY').value = ENG.y == null ? '' : String(ENG.y); engineDraw(); } },
    benchOpen: (tab) => { open2d(tab); },
    compose(keys, now) { if (now) open2d('composite', keys.filter(k => En().V[k])); return false; },   // false: not opened while the answer is built; the answer offers a button (chat.js)
    trendPlaces() { /* the trend chart is on the 2D map */ },
    info(key) { if (!answering()) window.open('dictionary.html' + location.search + '#' + En().dictId(key), '_blank', 'noopener'); },
    levelSeries: async () => null,   // the columns are by municipio: a ranking of barrios is on the 2D map
  };
  window.ECON = { api };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => ChatBoot.init(), { once: true }); else ChatBoot.init();
  // a question handed over by the 2D map's chat ("See in 3D": 3d.html#ask=…), asked here once the view is ready and then taken out of the address (it never leaves the browser)
  const asked = new URLSearchParams(location.hash.slice(1)).get('ask');
  if (asked) loaded.then(() => ChatBoot.load()).then(() => {
    Chat.handOver(asked);   // out of the address, asked, never a clear or a wish (chat.js chHandIn)
  }).catch(() => {});
  return { link2d };
})();
